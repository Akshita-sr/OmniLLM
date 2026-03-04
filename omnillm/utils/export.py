"""Export evaluation results to CSV, JSON, and Markdown formats."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from omnillm.evaluator import EvalResult


class ResultExporter:
    """Export evaluation results to various file formats.

    Example::

        exporter = ResultExporter()
        exporter.to_json(results, "results/eval_2026.json")
        exporter.to_csv(results, "results/eval_2026.csv")
        exporter.to_markdown(results, "results/eval_2026.md")

        # For console display:
        table = exporter.to_rich_table(results)
        from rich.console import Console
        Console().print(table)
    """

    # ── Serialisation helpers ─────────────────────────────────────────────────

    @staticmethod
    def _result_to_dict(result: "EvalResult") -> dict[str, Any]:
        """Convert an :class:`~omnillm.evaluator.EvalResult` to a serialisable dict."""
        return {
            "task_id": result.task_id,
            "model_id": result.model_id,
            "category": result.category,
            "score": result.score,
            "latency_ms": result.response.latency_ms,
            "cost_usd": result.response.cost_usd,
            "input_tokens": result.response.input_tokens,
            "output_tokens": result.response.output_tokens,
            "judge_reasoning": result.judge_reasoning,
            "notes": result.notes,
            "error": result.response.error,
        }

    # ── Export methods ────────────────────────────────────────────────────────

    def to_csv(
        self,
        results: list["EvalResult"],
        path: str | Path,
    ) -> None:
        """Export results to a CSV file.

        Args:
            results: List of :class:`~omnillm.evaluator.EvalResult` objects.
            path: Output file path.
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        rows = [self._result_to_dict(r) for r in results]
        if not rows:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def to_json(
        self,
        results: list["EvalResult"],
        path: str | Path,
        indent: int = 2,
    ) -> None:
        """Export results to a JSON file.

        Args:
            results: List of evaluation results.
            path: Output file path.
            indent: JSON indentation level.
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = [self._result_to_dict(r) for r in results]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=indent)

    def to_markdown(
        self,
        results: list["EvalResult"],
        path: str | Path,
    ) -> None:
        """Export results to a Markdown table.

        Args:
            results: List of evaluation results.
            path: Output file path.
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# OmniLLM Evaluation Results\n",
            "| Task ID | Model | Category | Score | Latency (ms) | Cost (USD) |",
            "|---------|-------|----------|-------|--------------|------------|",
        ]
        for r in results:
            lines.append(
                f"| {r.task_id} | {r.model_id} | {r.category} "
                f"| {r.score:.3f} | {r.response.latency_ms:.0f} "
                f"| ${r.response.cost_usd:.6f} |"
            )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def to_rich_table(self, results: list["EvalResult"]) -> Any:
        """Build a Rich Table for console display.

        Args:
            results: List of evaluation results.

        Returns:
            A ``rich.table.Table`` or a plain list of dicts if Rich is not
            available.
        """
        try:
            from rich.table import Table

            table = Table(title="Evaluation Results", show_header=True)
            table.add_column("Task", style="dim")
            table.add_column("Model", style="cyan")
            table.add_column("Category", style="magenta")
            table.add_column("Score", justify="right", style="bold green")
            table.add_column("Latency", justify="right")
            table.add_column("Cost", justify="right", style="yellow")

            for r in results:
                score_color = (
                    "green" if r.score >= 0.8 else "yellow" if r.score >= 0.5 else "red"
                )
                table.add_row(
                    r.task_id,
                    r.model_id,
                    r.category,
                    f"[{score_color}]{r.score:.3f}[/{score_color}]",
                    f"{r.response.latency_ms:.0f}ms",
                    f"${r.response.cost_usd:.6f}",
                )
            return table
        except ImportError:
            return [self._result_to_dict(r) for r in results]

    def get_summary_stats(
        self, results: list["EvalResult"]
    ) -> dict[str, dict[str, float]]:
        """Compute summary statistics per model.

        Args:
            results: List of evaluation results.

        Returns:
            Dict mapping model_id → stats dict with keys:
            ``avg_score``, ``avg_latency_ms``, ``total_cost_usd``, ``num_tasks``.
        """
        stats: dict[str, dict[str, Any]] = {}
        for r in results:
            mid = r.model_id
            if mid not in stats:
                stats[mid] = {
                    "scores": [],
                    "latencies": [],
                    "total_cost": 0.0,
                    "num_tasks": 0,
                }
            stats[mid]["scores"].append(r.score)
            stats[mid]["latencies"].append(r.response.latency_ms)
            stats[mid]["total_cost"] += r.response.cost_usd
            stats[mid]["num_tasks"] += 1

        return {
            mid: {
                "avg_score": sum(s["scores"]) / len(s["scores"]) if s["scores"] else 0.0,
                "avg_latency_ms": sum(s["latencies"]) / len(s["latencies"]) if s["latencies"] else 0.0,
                "total_cost_usd": s["total_cost"],
                "num_tasks": s["num_tasks"],
            }
            for mid, s in stats.items()
        }
