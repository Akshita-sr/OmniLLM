"""Track and analyse API costs across models and sessions."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class _Record:
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)
    session_id: str = "default"


class CostTracker:
    """Track and analyse API costs across models and sessions.

    Example::

        tracker = CostTracker()
        tracker.record("openai-gpt4o", 500, 300, 0.0045, session_id="eval-1")
        print(f"Total: ${tracker.get_total_cost():.4f}")
        for model, cost in tracker.get_cost_by_model().items():
            print(f"  {model}: ${cost:.4f}")
    """

    def __init__(self) -> None:
        self._records: list[_Record] = []

    def record(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        session_id: str = "default",
    ) -> None:
        """Record a single API call's cost.

        Args:
            model_id: Model identifier.
            input_tokens: Number of input/prompt tokens.
            output_tokens: Number of output/completion tokens.
            cost_usd: Cost in US dollars.
            session_id: Optional session label for grouping.
        """
        self._records.append(
            _Record(
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                session_id=session_id,
            )
        )

    def get_total_cost(self) -> float:
        """Return total accumulated cost across all models and sessions."""
        return sum(r.cost_usd for r in self._records)

    def get_cost_by_model(self) -> dict[str, float]:
        """Return cost per model, sorted by total cost descending."""
        totals: dict[str, float] = {}
        for r in self._records:
            totals[r.model_id] = totals.get(r.model_id, 0.0) + r.cost_usd
        return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))

    def get_cost_by_session(self) -> dict[str, float]:
        """Return cost per session ID."""
        totals: dict[str, float] = {}
        for r in self._records:
            totals[r.session_id] = totals.get(r.session_id, 0.0) + r.cost_usd
        return totals

    def get_token_usage(self) -> dict[str, dict[str, int]]:
        """Return token usage per model (input, output, total)."""
        usage: dict[str, dict[str, int]] = {}
        for r in self._records:
            if r.model_id not in usage:
                usage[r.model_id] = {"input": 0, "output": 0, "total": 0}
            usage[r.model_id]["input"] += r.input_tokens
            usage[r.model_id]["output"] += r.output_tokens
            usage[r.model_id]["total"] += r.input_tokens + r.output_tokens
        return usage

    def get_summary(self) -> dict[str, object]:
        """Return a summary dict of all cost and usage statistics."""
        return {
            "total_cost_usd": self.get_total_cost(),
            "total_calls": len(self._records),
            "by_model": self.get_cost_by_model(),
            "by_session": self.get_cost_by_session(),
            "token_usage": self.get_token_usage(),
        }

    def get_summary_table(self) -> object:
        """Return a Rich Table object for console display.

        Returns:
            A ``rich.table.Table`` ready to pass to ``Console.print()``.
        """
        try:
            from rich.table import Table

            table = Table(title="Cost Summary", show_header=True)
            table.add_column("Model", style="cyan")
            table.add_column("Calls", justify="right")
            table.add_column("Input Tokens", justify="right")
            table.add_column("Output Tokens", justify="right")
            table.add_column("Cost (USD)", justify="right", style="green")

            by_model: dict[str, dict[str, object]] = {}
            for r in self._records:
                if r.model_id not in by_model:
                    by_model[r.model_id] = {
                        "calls": 0, "input": 0, "output": 0, "cost": 0.0
                    }
                by_model[r.model_id]["calls"] = int(by_model[r.model_id]["calls"]) + 1  # type: ignore[arg-type]
                by_model[r.model_id]["input"] = int(by_model[r.model_id]["input"]) + r.input_tokens  # type: ignore[arg-type]
                by_model[r.model_id]["output"] = int(by_model[r.model_id]["output"]) + r.output_tokens  # type: ignore[arg-type]
                by_model[r.model_id]["cost"] = float(by_model[r.model_id]["cost"]) + r.cost_usd  # type: ignore[arg-type]

            for model_id, stats in sorted(
                by_model.items(), key=lambda x: float(x[1]["cost"]), reverse=True  # type: ignore[arg-type]
            ):
                table.add_row(
                    model_id,
                    str(stats["calls"]),
                    str(stats["input"]),
                    str(stats["output"]),
                    f"${float(stats['cost']):.6f}",  # type: ignore[arg-type]
                )

            return table
        except ImportError:
            return self.get_summary()

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Save all records to a JSON file.

        Args:
            path: Destination file path.
        """
        data = [
            {
                "model_id": r.model_id,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": r.cost_usd,
                "timestamp": r.timestamp,
                "session_id": r.session_id,
            }
            for r in self._records
        ]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def load(self, path: str | Path) -> None:
        """Load records from a JSON file (appends to existing records).

        Args:
            path: Source file path.
        """
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for item in data:
            self._records.append(
                _Record(
                    model_id=item["model_id"],
                    input_tokens=item.get("input_tokens", 0),
                    output_tokens=item.get("output_tokens", 0),
                    cost_usd=item.get("cost_usd", 0.0),
                    timestamp=item.get("timestamp", time.time()),
                    session_id=item.get("session_id", "default"),
                )
            )
