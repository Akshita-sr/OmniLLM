"""Tests for omnillm.utils.experiment_logger — ExperimentLogger.

Updated 2026-05-22 with the unified-routing refactor:
  - the legacy `condition` field is gone (was the A/B/C/D/E design)
  - a new `mode` field replaces it (laptop / choregraphe / real / real_laptop_mic)
  - `log_interaction` is keyword-only for all optional fields
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnillm.utils.experiment_logger import ExperimentLogger, InteractionRecord


class TestInteractionRecord:
    def test_defaults(self):
        r = InteractionRecord(
            session_id="s1",
            participant_id="P001",
            task_type="info_retrieval",
            utterance="What time?",
            response="9 AM.",
            model_id="openai-gpt4o-mini",
        )
        assert r.latency_ms == 0.0
        assert r.rag_enabled is False
        assert r.rag_faithfulness == pytest.approx(-1.0)
        assert r.judge_score == pytest.approx(-1.0)
        assert r.task_success is None
        assert r.language == "en"
        assert r.mode == ""
        assert r.timestamp is not None

    def test_all_fields(self):
        r = InteractionRecord(
            session_id="s2",
            participant_id="P002",
            task_type="navigation",
            utterance="Where is Room 305?",
            response="Turn left and go to the third floor.",
            model_id="gemini-flash",
            mode="choregraphe",
            latency_ms=380.5,
            input_tokens=120,
            output_tokens=40,
            cost_usd=0.000012,
            rag_enabled=True,
            rag_faithfulness=0.92,
            rag_chunk_count=3,
            judge_score=0.88,
            task_success=True,
            language="en",
            gesture_used="point_left",
        )
        assert r.latency_ms == pytest.approx(380.5)
        assert r.rag_faithfulness == pytest.approx(0.92)
        assert r.gesture_used == "point_left"
        assert r.task_success is True
        assert r.mode == "choregraphe"


class TestExperimentLogger:
    def setup_method(self):
        self.logger = ExperimentLogger()

    def test_log_interaction_returns_record(self):
        record = self.logger.log_interaction(
            session_id="s1",
            participant_id="P001",
            task_type="info_retrieval",
            utterance="What are the lab hours?",
            response="The lab is open 9-6.",
            model_id="openai-gpt4o-mini",
        )
        assert isinstance(record, InteractionRecord)

    def test_log_interaction_stores_record(self):
        self.logger.log_interaction(
            session_id="s1",
            participant_id="P001",
            task_type="social_conversation",
            utterance="Hello!",
            response="Hi! How can I help?",
            model_id="claude-haiku",
        )
        records = self.logger.get_records()
        assert len(records) == 1

    def test_log_interaction_stamps_mode(self):
        self.logger.log_interaction(
            "s1", "P001", "info_retrieval", "q", "a", "m", mode="real",
        )
        assert self.logger.get_records()[0].mode == "real"

    def test_get_records_filter_by_session(self):
        for sid in ["s1", "s2", "s1"]:
            self.logger.log_interaction(sid, "P001", "info_retrieval", "q", "a", "m")
        records = self.logger.get_records(session_id="s1")
        assert len(records) == 2
        assert all(r.session_id == "s1" for r in records)

    def test_get_records_filter_by_mode(self):
        for m in ["laptop", "choregraphe", "laptop", "real"]:
            self.logger.log_interaction("s1", "P001", "info_retrieval", "q", "a", "m", mode=m)
        records = self.logger.get_records(mode="laptop")
        assert len(records) == 2
        assert all(r.mode == "laptop" for r in records)

    def test_get_records_filter_by_task_type(self):
        for t in ["navigation", "info_retrieval", "navigation"]:
            self.logger.log_interaction("s1", "P001", t, "q", "a", "m")
        records = self.logger.get_records(task_type="navigation")
        assert len(records) == 2

    def test_get_records_filter_by_model_id(self):
        for mid in ["openai-gpt4o-mini", "claude-haiku", "openai-gpt4o-mini"]:
            self.logger.log_interaction("s1", "P001", "social_conversation", "q", "a", mid)
        records = self.logger.get_records(model_id="openai-gpt4o-mini")
        assert len(records) == 2

    def test_get_summary_empty(self):
        summary = self.logger.get_summary()
        assert summary["total_interactions"] == 0

    def test_get_summary_with_records(self):
        self.logger.log_interaction(
            "s1", "P001", "info_retrieval", "q", "a", "openai-gpt4o-mini",
            mode="laptop", latency_ms=300.0, judge_score=0.9, task_success=True,
        )
        self.logger.log_interaction(
            "s1", "P002", "navigation", "q2", "a2", "llama3-8b-local",
            mode="choregraphe", latency_ms=500.0, judge_score=0.7, task_success=False,
        )
        summary = self.logger.get_summary()
        assert summary["total_interactions"] == 2
        assert "openai-gpt4o-mini" in summary["by_model"]
        assert "llama3-8b-local" in summary["by_model"]
        assert "laptop" in summary["by_mode"]
        assert "choregraphe" in summary["by_mode"]

    def test_get_summary_avg_latency(self):
        self.logger.log_interaction("s1", "P001", "info_retrieval", "q", "a", "m", latency_ms=200.0)
        self.logger.log_interaction("s1", "P001", "info_retrieval", "q", "a", "m", latency_ms=400.0)
        summary = self.logger.get_summary()
        assert summary["by_model"]["m"]["avg_latency_ms"] == pytest.approx(300.0)

    def test_save_and_load(self, tmp_path: Path):
        self.logger.log_interaction(
            "s1", "P001", "multilingual", "Bonjour", "Hello!", "gemini-flash",
            mode="real", language="fr",
        )
        path = tmp_path / "records.json"
        self.logger.save(path)
        assert path.exists()

        new_logger = ExperimentLogger()
        new_logger.load(path)
        records = new_logger.get_records()
        assert len(records) == 1
        assert records[0].language == "fr"
        assert records[0].model_id == "gemini-flash"
        assert records[0].mode == "real"

    def test_load_ignores_unknown_keys_from_legacy_dumps(self, tmp_path: Path):
        """Old dumps that still carry the deleted `condition` field must load."""
        legacy_path = tmp_path / "legacy.json"
        legacy_path.write_text(json.dumps([
            {
                "session_id": "s1",
                "participant_id": "P001",
                "condition": "A",   # ← legacy field, no longer in the dataclass
                "task_type": "info_retrieval",
                "utterance": "q",
                "response": "a",
                "model_id": "m",
            }
        ]))
        logger = ExperimentLogger()
        logger.load(legacy_path)
        assert len(logger.get_records()) == 1

    def test_save_creates_valid_json(self, tmp_path: Path):
        self.logger.log_interaction("s1", "P001", "info_retrieval", "q", "a", "m")
        path = tmp_path / "records.json"
        self.logger.save(path)
        with open(path) as fh:
            data = json.load(fh)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["session_id"] == "s1"

    def test_agreement_score_defaults_to_none(self):
        """Non-council strategies leave agreement_score as None."""
        record = self.logger.log_interaction(
            "s1", "P001", "info_retrieval", "q", "a", "openai-gpt4o-mini",
        )
        assert record.agreement_score is None

    def test_agreement_score_round_trips_through_save_load(self, tmp_path: Path):
        """Regression: council's agreement_score must survive save → load.

        Pre-2026-05-24 the field didn't exist in InteractionRecord, so the
        consensus diagnostic was lost. Locks in the Part 7 Embodied Veracity
        prerequisite.
        """
        self.logger.log_interaction(
            "s1", "P001", "info_retrieval", "Where is the lab?", "On the 3rd floor.",
            "council:openai-gpt4o-mini+claude-haiku+gemini-2.5-flash",
            agreement_score=0.85,
        )
        path = tmp_path / "records.json"
        self.logger.save(path)

        new_logger = ExperimentLogger()
        new_logger.load(path)
        records = new_logger.get_records()
        assert len(records) == 1
        assert records[0].agreement_score == pytest.approx(0.85)

    def test_save_csv(self, tmp_path: Path):
        self.logger.log_interaction("s1", "P001", "navigation", "q", "a", "m")
        path = tmp_path / "records.csv"
        self.logger.save_csv(path)
        assert path.exists()
        content = path.read_text()
        assert "session_id" in content
        assert "s1" in content

    def test_total_cost_in_summary(self):
        self.logger.log_interaction("s1", "P001", "info_retrieval", "q", "a", "m", cost_usd=0.001)
        self.logger.log_interaction("s1", "P001", "info_retrieval", "q", "a", "m", cost_usd=0.002)
        summary = self.logger.get_summary()
        assert summary["total_cost_usd"] == pytest.approx(0.003)

    def test_success_rate_in_summary(self):
        self.logger.log_interaction(
            "s1", "P001", "info_retrieval", "q", "a", "m",
            mode="laptop", task_success=True,
        )
        self.logger.log_interaction(
            "s2", "P001", "info_retrieval", "q", "a", "m",
            mode="laptop", task_success=False,
        )
        summary = self.logger.get_summary()
        assert summary["by_mode"]["laptop"]["success_rate"] == pytest.approx(0.5)
