"""ELO Rating System for head-to-head model comparison.

Implements the same ELO methodology used by LMSYS Chatbot Arena to produce
a ranking of LLMs from pairwise human or LLM-as-judge comparisons.

The ELO system provides several advantages over simple average scores:
- Accounts for the strength of opponents (beating a strong model is worth more)
- Converges over time to stable relative rankings
- Easy to interpret: ~100 ELO points ≈ 64% win-rate in head-to-head

Reference:
    LMSYS Chatbot Arena: Benchmarking LLMs in the Wild
    https://chat.lmsys.org/?leaderboard
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class _MatchRecord:
    """Internal record of a single head-to-head match."""

    timestamp: str
    model_a: str
    model_b: str
    winner: str  # "model_a", "model_b", or "tie"
    category: str = "general"
    rating_a_before: float = 1500.0
    rating_b_before: float = 1500.0
    rating_a_after: float = 1500.0
    rating_b_after: float = 1500.0


class EloScorer:
    """Maintains ELO ratings for registered LLM models.

    Example::

        scorer = EloScorer()
        scorer.record_match("openai-gpt4o", "claude-3.5-sonnet", "model_a")
        leaderboard = scorer.get_leaderboard()
        for model_id, rating, games in leaderboard[:5]:
            print(f"{model_id}: {rating:.0f} ({games} games)")
    """

    def __init__(self, k_factor: float = 32, default_rating: float = 1500) -> None:
        """Initialise the ELO scorer.

        Args:
            k_factor: Maximum rating change per match.  Higher values make
                ratings more volatile.  32 is standard; 16 is used for
                established players in chess.
            default_rating: Starting ELO for all new models.
        """
        self.k_factor = k_factor
        self.default_rating = default_rating
        self.ratings: dict[str, float] = {}
        self.matches_played: dict[str, int] = {}
        self._history: list[_MatchRecord] = []
        self._rating_history: dict[str, list[tuple[str, float]]] = {}
        # category → model → rating
        self._category_ratings: dict[str, dict[str, float]] = {}

    # ── ELO math ──────────────────────────────────────────────────────────────

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Compute the expected score for player A against player B.

        Returns:
            Float in (0, 1) — probability that A beats B.
        """
        return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400.0))

    def _update_ratings(
        self,
        rating_a: float,
        rating_b: float,
        winner: str,
    ) -> tuple[float, float]:
        """Compute new ratings after a match.

        Args:
            rating_a: Current rating of model A.
            rating_b: Current rating of model B.
            winner: ``"model_a"``, ``"model_b"``, or ``"tie"``.

        Returns:
            Tuple of (new_rating_a, new_rating_b).
        """
        ea = self.expected_score(rating_a, rating_b)
        eb = 1.0 - ea

        if winner == "model_a":
            sa, sb = 1.0, 0.0
        elif winner == "model_b":
            sa, sb = 0.0, 1.0
        else:  # tie
            sa, sb = 0.5, 0.5

        new_a = rating_a + self.k_factor * (sa - ea)
        new_b = rating_b + self.k_factor * (sb - eb)
        return new_a, new_b

    # ── Public API ────────────────────────────────────────────────────────────

    def record_match(
        self,
        model_a: str,
        model_b: str,
        winner: str,
        category: str = "general",
    ) -> None:
        """Record a head-to-head match and update ELO ratings.

        Args:
            model_a: First model ID.
            model_b: Second model ID.
            winner: ``"model_a"``, ``"model_b"``, or ``"tie"``.
            category: Optional category for per-category leaderboards.
        """
        # Initialise ratings if needed
        if model_a not in self.ratings:
            self.ratings[model_a] = self.default_rating
            self.matches_played[model_a] = 0
        if model_b not in self.ratings:
            self.ratings[model_b] = self.default_rating
            self.matches_played[model_b] = 0

        ra_before = self.ratings[model_a]
        rb_before = self.ratings[model_b]
        ra_after, rb_after = self._update_ratings(ra_before, rb_before, winner)

        self.ratings[model_a] = ra_after
        self.ratings[model_b] = rb_after
        self.matches_played[model_a] += 1
        self.matches_played[model_b] += 1

        ts = datetime.now(timezone.utc).isoformat()

        # Track rating history
        for mid, new_r in [(model_a, ra_after), (model_b, rb_after)]:
            if mid not in self._rating_history:
                self._rating_history[mid] = []
            self._rating_history[mid].append((ts, new_r))

        # Update category-specific ratings
        if category not in self._category_ratings:
            self._category_ratings[category] = {}
        cat = self._category_ratings[category]
        if model_a not in cat:
            cat[model_a] = self.default_rating
        if model_b not in cat:
            cat[model_b] = self.default_rating
        cat_a_new, cat_b_new = self._update_ratings(cat[model_a], cat[model_b], winner)
        cat[model_a] = cat_a_new
        cat[model_b] = cat_b_new

        self._history.append(
            _MatchRecord(
                timestamp=ts,
                model_a=model_a,
                model_b=model_b,
                winner=winner,
                category=category,
                rating_a_before=ra_before,
                rating_b_before=rb_before,
                rating_a_after=ra_after,
                rating_b_after=rb_after,
            )
        )

    def get_leaderboard(self) -> list[tuple[str, float, int]]:
        """Return overall leaderboard sorted by rating (descending).

        Returns:
            List of ``(model_id, rating, matches_played)`` tuples.
        """
        return sorted(
            [
                (mid, self.ratings[mid], self.matches_played.get(mid, 0))
                for mid in self.ratings
            ],
            key=lambda x: x[1],
            reverse=True,
        )

    def get_category_leaderboard(
        self, category: str
    ) -> list[tuple[str, float, int]]:
        """Return the leaderboard for a specific evaluation category.

        Args:
            category: Category name (e.g. ``"reasoning"``).

        Returns:
            Sorted list of ``(model_id, rating, matches_played)``.
        """
        cat_ratings = self._category_ratings.get(category, {})
        return sorted(
            [
                (mid, rating, self.matches_played.get(mid, 0))
                for mid, rating in cat_ratings.items()
            ],
            key=lambda x: x[1],
            reverse=True,
        )

    def get_rating_history(
        self, model_id: str
    ) -> list[tuple[str, float]]:
        """Return the rating history for a model.

        Args:
            model_id: Model identifier.

        Returns:
            List of ``(ISO-timestamp, rating)`` tuples, oldest first.
        """
        return list(self._rating_history.get(model_id, []))

    def get_rating(self, model_id: str) -> float:
        """Return the current ELO rating for a model.

        Returns ``default_rating`` if the model has never played.
        """
        return self.ratings.get(model_id, self.default_rating)

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Persist all ratings and history to a JSON file.

        Args:
            path: Destination file path.
        """
        data: dict[str, Any] = {
            "k_factor": self.k_factor,
            "default_rating": self.default_rating,
            "ratings": self.ratings,
            "matches_played": self.matches_played,
            "rating_history": self._rating_history,
            "category_ratings": self._category_ratings,
            "history": [
                {
                    "timestamp": r.timestamp,
                    "model_a": r.model_a,
                    "model_b": r.model_b,
                    "winner": r.winner,
                    "category": r.category,
                    "rating_a_before": r.rating_a_before,
                    "rating_b_before": r.rating_b_before,
                    "rating_a_after": r.rating_a_after,
                    "rating_b_after": r.rating_b_after,
                }
                for r in self._history
            ],
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def load(self, path: str | Path) -> None:
        """Load ratings and history from a JSON file.

        Args:
            path: Source file path.
        """
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        self.k_factor = data.get("k_factor", self.k_factor)
        self.default_rating = data.get("default_rating", self.default_rating)
        self.ratings = data.get("ratings", {})
        self.matches_played = data.get("matches_played", {})
        self._rating_history = data.get("rating_history", {})
        self._category_ratings = data.get("category_ratings", {})
        self._history = [
            _MatchRecord(**r) for r in data.get("history", [])
        ]
