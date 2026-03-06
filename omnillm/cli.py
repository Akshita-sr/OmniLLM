"""Terminal-based dashboard for OmniLLM using Click + Rich.

All commands produce rich, coloured output using the Rich library.
No complex GUI — everything works in a standard terminal.

Usage::

    omnillm models
    omnillm evaluate --models openai-gpt4o --category reasoning
    omnillm ask "Explain quantum computing" --all
    omnillm council "What is consciousness?" --strategy synthesis
    omnillm route "Simple greeting" --budget 0.001
    omnillm leaderboard
    omnillm costs
    omnillm export --format csv

Can also be invoked as::

    python -m omnillm.cli <command>
"""

from __future__ import annotations
from dotenv import load_dotenv

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_gateway(config: str | None = None):
    """Create and return a configured LLMGateway."""
    from omnillm.gateway import LLMGateway

    cfg_path = config or str(Path(__file__).parent.parent / "config" / "models.yaml")
    return LLMGateway(config_path=cfg_path)


def _load_dotenv() -> None:
    """Load .env file if python-dotenv is available."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("0.1.0", prog_name="omnillm")
def cli() -> None:
    """🧠 OmniLLM — Compare, Route, and Orchestrate Every LLM.

    A living, plugin-based platform for multi-LLM comparison, smart routing,
    consensus ensembles, and robotics integration.
    """
    _load_dotenv()


# ── omnillm models ────────────────────────────────────────────────────────────

@cli.command("models")
@click.option("--config", "-c", default=None, help="Path to models.yaml")
@click.option("--type", "model_type", default=None, type=click.Choice(["cloud", "local"]),
              help="Filter by type")
def models_cmd(config: str | None, model_type: str | None) -> None:
    """List all registered LLM models."""
    gateway = _get_gateway(config)

    table = Table(title="Registered LLM Models", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Provider", style="blue")
    table.add_column("Model Name")
    table.add_column("$/1M Input", justify="right", style="yellow")
    table.add_column("$/1M Output", justify="right", style="yellow")
    table.add_column("Description")

    for model_id in gateway.list_models():
        info = gateway.get_model_info(model_id)
        if model_type and info.get("type") != model_type:
            continue
        mtype = info.get("type", "cloud")
        type_style = "green" if mtype == "local" else "blue"
        table.add_row(
            model_id,
            f"[{type_style}]{mtype}[/{type_style}]",
            info.get("provider", ""),
            info.get("model", ""),
            f"${info.get('cost_per_1m_input', 0):.3f}",
            f"${info.get('cost_per_1m_output', 0):.3f}",
            info.get("description", ""),
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(gateway.list_models())} models registered[/dim]")


# ── omnillm ask ───────────────────────────────────────────────────────────────

@cli.command("ask")
@click.argument("prompt")
@click.option("--all", "ask_all", is_flag=True, help="Ask all registered models")
@click.option("--model", "-m", multiple=True, help="Model ID(s) to ask")
@click.option("--temperature", "-t", default=0.7, show_default=True)
@click.option("--max-tokens", default=1024, show_default=True)
@click.option("--config", default=None, help="Path to models.yaml")
def ask_cmd(
    prompt: str,
    ask_all: bool,
    model: tuple[str, ...],
    temperature: float,
    max_tokens: int,
    config: str | None,
) -> None:
    """Send a prompt to one or more models and display responses."""
    gateway = _get_gateway(config)

    if ask_all:
        model_ids = gateway.list_models()
    elif model:
        model_ids = list(model)
    else:
        model_ids = gateway.list_cloud_models()[:2]
        console.print(
            f"[dim]No model specified. Using: {', '.join(model_ids)}[/dim]"
        )

    messages = [{"role": "user", "content": prompt}]

    async def _run():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Querying {len(model_ids)} model(s)...", total=None
            )
            responses = await gateway.query_multiple(
                model_ids, messages, temperature=temperature, max_tokens=max_tokens
            )
            progress.update(task, completed=True)
        return responses

    responses = asyncio.run(_run())

    console.print(f"\n[bold]Prompt:[/bold] {prompt}\n")
    for resp in responses:
        if resp.is_error:
            console.print(
                Panel(
                    f"[red]Error: {resp.error}[/red]",
                    title=f"[red]{resp.model_id}[/red]",
                    border_style="red",
                )
            )
        else:
            meta = (
                f"[dim]Latency: {resp.latency_ms:.0f}ms | "
                f"Tokens: {resp.input_tokens}+{resp.output_tokens} | "
                f"Cost: ${resp.cost_usd:.6f}[/dim]"
            )
            console.print(
                Panel(
                    resp.content + "\n\n" + meta,
                    title=f"[cyan]{resp.model_id}[/cyan]",
                    border_style="cyan",
                )
            )


# ── omnillm evaluate ──────────────────────────────────────────────────────────

@cli.command("evaluate")
@click.option("--models", "-m", multiple=True, help="Model IDs to evaluate")
@click.option("--category", "-c", default=None, help="Task category to run")
@click.option("--output", "-o", default=None, help="Output file path (JSON)")
@click.option("--judge", default="openai-gpt4o", show_default=True, help="Judge model ID")
@click.option("--config", default=None, help="Path to models.yaml")
def evaluate_cmd(
    models: tuple[str, ...],
    category: str | None,
    output: str | None,
    judge: str,
    config: str | None,
) -> None:
    """Run benchmark evaluation across models and task categories."""
    from omnillm.evaluator import Evaluator
    from omnillm.tasks import ALL_TASKS, TASKS_BY_CATEGORY

    gateway = _get_gateway(config)

    model_ids = list(models) if models else gateway.list_cloud_models()[:3]
    tasks = TASKS_BY_CATEGORY.get(category, ALL_TASKS) if category else ALL_TASKS

    console.print(
        f"[bold]Evaluating[/bold] {len(model_ids)} model(s) on "
        f"{len(tasks)} task(s)"
        + (f" (category: [cyan]{category}[/cyan])" if category else "")
    )

    evaluator = Evaluator(gateway, judge_model=judge)

    async def _run():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            ptask = progress.add_task("Running benchmark...", total=None)
            results = await evaluator.run_benchmark(tasks, model_ids)
            progress.update(ptask, completed=True)
        return results

    results = asyncio.run(_run())

    # Results table
    table = Table(title="Benchmark Results", show_header=True)
    table.add_column("Task", style="dim")
    table.add_column("Model", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Latency", justify="right")
    table.add_column("Cost", justify="right", style="yellow")

    for r in results:
        score_color = "green" if r.score >= 0.8 else "yellow" if r.score >= 0.5 else "red"
        table.add_row(
            r.task_id,
            r.model_id,
            r.category,
            f"[{score_color}]{r.score:.3f}[/{score_color}]",
            f"{r.response.latency_ms:.0f}ms",
            f"${r.response.cost_usd:.6f}",
        )

    console.print(table)

    if output:
        from omnillm.utils.export import ResultExporter
        exporter = ResultExporter()
        exporter.to_json(results, output)
        console.print(f"\n[green]Results saved to {output}[/green]")


# ── omnillm compare ───────────────────────────────────────────────────────────

@cli.command("compare")
@click.argument("prompt")
@click.option("--model-a", default="openai-gpt4o", show_default=True)
@click.option("--model-b", default="claude-3.5-sonnet", show_default=True)
@click.option("--config", default=None)
def compare_cmd(prompt: str, model_a: str, model_b: str, config: str | None) -> None:
    """Pairwise comparison of two models on a single prompt."""
    from omnillm.evaluator import Evaluator, EvalTask

    gateway = _get_gateway(config)
    evaluator = Evaluator(gateway)

    task = EvalTask(
        id="compare-task",
        category="general",
        prompt=prompt,
        judge_pattern="pairwise",
    )

    async def _run():
        with Progress(SpinnerColumn(), TextColumn("Comparing models..."), console=console) as p:
            ptask = p.add_task("", total=None)
            result = await evaluator.evaluate_pairwise(task, model_a, model_b)
            p.update(ptask, completed=True)
        return result

    result = asyncio.run(_run())

    winner_str = {
        "model_a": f"[green]🏆 {model_a}[/green]",
        "model_b": f"[green]🏆 {model_b}[/green]",
        "tie": "[yellow]🤝 Tie[/yellow]",
    }.get(result.winner, result.winner)

    console.print(Panel(
        f"**Prompt:** {prompt}\n\n"
        f"**Winner:** {winner_str}\n\n"
        f"**Reasoning:**\n{result.judge_reasoning[:500]}",
        title="Pairwise Comparison Result",
        border_style="cyan",
    ))


# ── omnillm council ───────────────────────────────────────────────────────────

@cli.command("council")
@click.argument("prompt")
@click.option("--strategy", default="synthesis",
              type=click.Choice(["majority_vote", "weighted", "synthesis"]),
              show_default=True)
@click.option("--models", "-m", multiple=True, help="Council model IDs")
@click.option("--config", default=None)
def council_cmd(
    prompt: str,
    strategy: str,
    models: tuple[str, ...],
    config: str | None,
) -> None:
    """Use the Multi-Model Consensus Engine (LLM Council)."""
    import yaml
    from omnillm.consensus import ConsensusConfig, ConsensusEngine

    gateway = _get_gateway(config)

    # Determine council models
    if models:
        council_models = list(models)
    else:
        cfg_path = config or str(Path(__file__).parent.parent / "config" / "models.yaml")
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        council_models = cfg.get("consensus", {}).get(
            "default_council", gateway.list_cloud_models()[:4]
        )

    cfg_obj = ConsensusConfig(
        council_models=council_models,
        judge_model=gateway.list_cloud_models()[0] if gateway.list_cloud_models() else "openai-gpt4o",
        strategy=strategy,  # type: ignore[arg-type]
    )
    engine = ConsensusEngine(gateway, cfg_obj)
    messages = [{"role": "user", "content": prompt}]

    async def _run():
        with Progress(SpinnerColumn(), TextColumn("Consulting the LLM Council..."), console=console) as p:
            ptask = p.add_task("", total=None)
            result = await engine.query_council(messages)
            p.update(ptask, completed=True)
        return result

    result = asyncio.run(_run())

    # Display individual responses
    console.print(f"\n[bold cyan]Council Members:[/bold cyan] {', '.join(council_models)}\n")
    for resp in result.individual_responses:
        if resp.is_error:
            console.print(Panel(
                f"[red]Error: {resp.error}[/red]",
                title=f"[red]{resp.model_id}[/red]", border_style="red"
            ))
        else:
            console.print(Panel(
                resp.content[:400] + ("..." if len(resp.content) > 400 else ""),
                title=f"[dim]{resp.model_id}[/dim]",
                border_style="dim",
            ))

    # Display synthesised answer
    agreement_color = "green" if result.agreement_score >= 0.7 else "yellow"
    console.print(Panel(
        result.final_answer + f"\n\n[dim]Agreement: [{agreement_color}]{result.agreement_score:.0%}[/{agreement_color}] | "
        f"Strategy: {result.strategy_used}[/dim]",
        title="[bold green]🧠 Council Consensus[/bold green]",
        border_style="green",
    ))


# ── omnillm route ─────────────────────────────────────────────────────────────

@cli.command("route")
@click.argument("prompt")
@click.option("--budget", default=None, type=float, help="Max cost per query (USD)")
@click.option("--strategy", default="BEST_VALUE",
              type=click.Choice(["BEST_QUALITY", "LOWEST_COST", "LOWEST_LATENCY",
                                 "BEST_VALUE", "LOCAL_PREFERRED"]),
              show_default=True)
@click.option("--category", default=None, help="Task category hint")
@click.option("--config", default=None)
def route_cmd(
    prompt: str,
    budget: float | None,
    strategy: str,
    category: str | None,
    config: str | None,
) -> None:
    """Use the Smart Router to select the best model for a prompt."""
    from omnillm.router import RoutingStrategy, SmartRouter

    router = SmartRouter(config_path=config)

    if category:
        decision = router.route(
            task_category=category,
            budget_usd=budget,
            strategy=RoutingStrategy(strategy),
        )
    else:
        decision = router.route_by_complexity(prompt, budget_usd=budget)

    console.print(Panel(
        f"[bold]Prompt:[/bold] {prompt}\n\n"
        f"[bold]Selected Model:[/bold] [cyan]{decision.model_id}[/cyan]\n"
        f"[bold]Strategy:[/bold] {decision.strategy_used.value}\n"
        f"[bold]Confidence:[/bold] {decision.confidence:.2%}\n"
        f"[bold]Est. Cost:[/bold] ${decision.estimated_cost:.6f}\n"
        f"[bold]Est. Latency:[/bold] {decision.estimated_latency_ms:.0f}ms\n\n"
        f"[dim]{decision.reason}[/dim]",
        title="🚦 Routing Decision",
        border_style="cyan",
    ))


# ── omnillm leaderboard ───────────────────────────────────────────────────────

@cli.command("leaderboard")
@click.option("--category", default=None, help="Filter by evaluation category")
@click.option("--scores-file", default=None, help="Path to ELO scores JSON file")
def leaderboard_cmd(category: str | None, scores_file: str | None) -> None:
    """Display the ELO leaderboard."""
    from omnillm.scorer import EloScorer

    scorer = EloScorer()
    if scores_file and Path(scores_file).exists():
        scorer.load(scores_file)

    if not scorer.ratings:
        console.print(
            "[yellow]No ELO data yet. Run evaluations to populate the leaderboard.[/yellow]"
        )
        console.print("[dim]Tip: omnillm evaluate -m openai-gpt4o -m claude-3.5-sonnet[/dim]")
        return

    board = scorer.get_category_leaderboard(category) if category else scorer.get_leaderboard()

    table = Table(
        title=f"ELO Leaderboard{f' — {category}' if category else ''}",
        show_header=True,
    )
    table.add_column("Rank", justify="right", style="dim")
    table.add_column("Model", style="cyan")
    table.add_column("ELO Rating", justify="right", style="bold")
    table.add_column("Games", justify="right")

    for rank, (model_id, rating, games) in enumerate(board, 1):
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
        table.add_row(medal, model_id, f"{rating:.0f}", str(games))

    console.print(table)


# ── omnillm costs ─────────────────────────────────────────────────────────────

@cli.command("costs")
@click.option("--data-file", default=None, help="Path to cost tracker JSON file")
def costs_cmd(data_file: str | None) -> None:
    """Display cost breakdown per model."""
    from omnillm.utils.cost_tracker import CostTracker

    tracker = CostTracker()
    if data_file and Path(data_file).exists():
        tracker.load(data_file)

    if not tracker._records:  # noqa: SLF001
        console.print("[yellow]No cost data yet. Run some queries to track costs.[/yellow]")
        return

    table = tracker.get_summary_table()
    console.print(table)
    console.print(f"\n[bold green]Total: ${tracker.get_total_cost():.6f} USD[/bold green]")


# ── omnillm export ────────────────────────────────────────────────────────────

@cli.command("export")
@click.option("--format", "fmt", default="json",
              type=click.Choice(["csv", "json", "markdown"]),
              show_default=True)
@click.option("--input", "input_file", default=None, help="Input JSON results file")
@click.option("--output", "-o", default=None, help="Output file path")
def export_cmd(fmt: str, input_file: str | None, output: str | None) -> None:
    """Export evaluation results to CSV, JSON, or Markdown."""
    from omnillm.utils.export import ResultExporter

    if not input_file:
        console.print("[red]Please specify an --input JSON results file.[/red]")
        sys.exit(1)

    if not Path(input_file).exists():
        console.print(f"[red]Input file not found: {input_file}[/red]")
        sys.exit(1)

    with open(input_file) as f:
        data = json.load(f)

    # Build lightweight result proxies for export
    from dataclasses import dataclass
    from omnillm.gateway import ModelResponse
    from omnillm.evaluator import EvalResult

    results = []
    for item in data:
        resp = ModelResponse(
            model_id=item.get("model_id", ""),
            content="",
            latency_ms=item.get("latency_ms", 0),
            cost_usd=item.get("cost_usd", 0),
            input_tokens=item.get("input_tokens", 0),
            output_tokens=item.get("output_tokens", 0),
            error=item.get("error"),
        )
        results.append(EvalResult(
            task_id=item.get("task_id", ""),
            model_id=item.get("model_id", ""),
            response=resp,
            score=item.get("score", 0),
            category=item.get("category", ""),
            judge_reasoning=item.get("judge_reasoning", ""),
            notes=item.get("notes", ""),
        ))

    if output is None:
        output = f"results/export.{fmt}"

    exporter = ResultExporter()
    if fmt == "csv":
        exporter.to_csv(results, output)
    elif fmt == "markdown":
        exporter.to_markdown(results, output)
    else:
        exporter.to_json(results, output)

    console.print(f"[green]Exported {len(results)} results to {output}[/green]")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
