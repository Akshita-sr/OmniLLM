"""Load evaluation tasks from YAML or JSON files.

Supports loading individual files, entire directories, and filtering by
category — making it easy to build custom evaluation suites.

YAML task format::

    tasks:
      - id: my-task-001
        category: reasoning
        prompt: "What is 2+2?"
        reference_answer: "4"
        grading_type: exact_match   # or: llm_judge, custom
        judge_pattern: reference_based
        judge_prompt: "Score 1.0 for 4, 0.0 otherwise."
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import yaml

from omnillm.evaluator import EvalTask


class TaskLoader:
    """Load :class:`~omnillm.evaluator.EvalTask` objects from YAML/JSON files.

    Example::

        loader = TaskLoader()
        tasks = loader.load_from_directory("config/tasks/")
        reasoning_tasks = loader.load_by_category("config/tasks/", "reasoning")
    """

    # ── Single-file loaders ──────────────────────────────────────────────────

    def load_from_yaml(self, path: str | Path) -> list[EvalTask]:
        """Load tasks from a single YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            List of :class:`EvalTask` objects.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the YAML structure is invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Task file not found: {path}")
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return self._parse_task_list(data, source=str(path))

    def load_from_json(self, path: str | Path) -> list[EvalTask]:
        """Load tasks from a single JSON file.

        The JSON file must contain either a list of task objects or a dict
        with a ``"tasks"`` key containing such a list.

        Args:
            path: Path to the JSON file.

        Returns:
            List of :class:`EvalTask` objects.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Task file not found: {path}")
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            data = {"tasks": data}
        return self._parse_task_list(data, source=str(path))

    # ── Directory loaders ────────────────────────────────────────────────────

    def load_from_directory(self, dir_path: str | Path) -> list[EvalTask]:
        """Load all tasks from YAML and JSON files in a directory.

        Files are processed in alphabetical order.

        Args:
            dir_path: Path to the directory containing task files.

        Returns:
            Combined list of :class:`EvalTask` objects from all files.
        """
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        tasks: list[EvalTask] = []
        for path in sorted(dir_path.iterdir()):
            if path.suffix in (".yaml", ".yml"):
                tasks.extend(self.load_from_yaml(path))
            elif path.suffix == ".json":
                tasks.extend(self.load_from_json(path))
        return tasks

    def load_by_category(
        self, dir_path: str | Path, category: str
    ) -> list[EvalTask]:
        """Load tasks from a directory, filtering by category.

        Args:
            dir_path: Directory containing task files.
            category: Category name to filter by (e.g. ``"reasoning"``).

        Returns:
            Filtered list of :class:`EvalTask` objects.
        """
        all_tasks = self.load_from_directory(dir_path)
        return [t for t in all_tasks if t.category == category]

    # ── Internal parser ──────────────────────────────────────────────────────

    def _parse_task_list(
        self, data: dict, source: str = "<unknown>"
    ) -> list[EvalTask]:
        """Parse a dict containing a ``"tasks"`` list into EvalTask objects.

        Args:
            data: Dict with ``"tasks"`` key containing a list of task dicts.
            source: Source file path for error messages.

        Returns:
            List of :class:`EvalTask` objects.

        Raises:
            ValueError: If the structure is invalid.
        """
        raw_tasks = data.get("tasks", [])
        if not isinstance(raw_tasks, list):
            raise ValueError(
                f"Expected 'tasks' to be a list in {source}, "
                f"got {type(raw_tasks).__name__}"
            )

        results: list[EvalTask] = []
        for i, item in enumerate(raw_tasks):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Task #{i} in {source} must be a dict, got {type(item).__name__}"
                )
            task_id = item.get("id", f"task-{i}")
            category = item.get("category", "general")
            prompt = item.get("prompt", "")
            if not prompt:
                raise ValueError(f"Task '{task_id}' in {source} has no 'prompt'")

            judge_pattern_raw = item.get(
                "judge_pattern",
                item.get("grading_type", "referenceless"),
            )
            # Map grading_type aliases to judge_pattern values
            _aliases: dict[str, Literal["referenceless", "reference_based", "pairwise"]] = {
                "llm_judge": "referenceless",
                "exact_match": "referenceless",
                "custom": "referenceless",
            }
            judge_pattern = _aliases.get(
                judge_pattern_raw, judge_pattern_raw  # type: ignore[arg-type]
            )

            results.append(
                EvalTask(
                    id=task_id,
                    category=category,
                    prompt=prompt,
                    reference_answer=item.get("reference_answer"),
                    judge_prompt=item.get("judge_prompt"),
                    judge_pattern=judge_pattern,  # type: ignore[arg-type]
                )
            )
        return results
