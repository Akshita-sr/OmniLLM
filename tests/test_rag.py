"""Tests for omnillm.rag — RAG pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omnillm.gateway import LLMGateway, ModelResponse
from omnillm.rag.pipeline import DocumentChunk, RAGPipeline, RAGResponse

CONFIG_PATH = Path(__file__).parent.parent / "config" / "models.yaml"


def make_mock_gateway(content: str = "The lab opens at 9 AM.") -> LLMGateway:
    """Create a gateway with a mocked LiteLLM response."""
    gw = LLMGateway(config_path=CONFIG_PATH)
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 50
    mock_usage.completion_tokens = 20
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage = mock_usage
    return gw, mock_resp


class TestDocumentChunk:
    def test_creation_with_defaults(self):
        chunk = DocumentChunk(text="Hello world", source="test.txt")
        assert chunk.text == "Hello world"
        assert chunk.source == "test.txt"
        assert chunk.similarity_score == 0.0
        assert chunk.metadata == {}

    def test_creation_with_all_fields(self):
        chunk = DocumentChunk(
            text="Lab info",
            source="lab.txt",
            chunk_id="lab.txt::0",
            metadata={"page": 1},
            similarity_score=0.85,
        )
        assert chunk.chunk_id == "lab.txt::0"
        assert chunk.similarity_score == pytest.approx(0.85)


class TestRAGResponse:
    def test_defaults(self):
        resp = RAGResponse(answer="Test answer")
        assert resp.answer == "Test answer"
        assert resp.retrieved_chunks == []
        assert resp.faithfulness_score == pytest.approx(-1.0)
        assert resp.hallucination_detected is False
        assert resp.rag_enabled is True

    def test_with_chunks(self):
        chunks = [DocumentChunk(text="Lab opens 9AM", source="schedule.txt")]
        resp = RAGResponse(
            answer="Lab opens at 9 AM",
            retrieved_chunks=chunks,
            faithfulness_score=0.95,
        )
        assert len(resp.retrieved_chunks) == 1
        assert resp.faithfulness_score == pytest.approx(0.95)


class TestRAGPipelineInit:
    def test_init_default_params(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        rag = RAGPipeline(gateway=gw)
        assert rag.model_id == "openai-gpt4o-mini"
        assert rag.top_k == 4
        assert rag.chunk_size == 512

    def test_init_custom_params(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        rag = RAGPipeline(gateway=gw, model_id="claude-haiku", top_k=3, chunk_size=256)
        assert rag.model_id == "claude-haiku"
        assert rag.top_k == 3
        assert rag.chunk_size == 256

    def test_uses_chromadb_false_when_not_installed(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        with patch.dict("sys.modules", {"chromadb": None}):
            rag = RAGPipeline(gateway=gw)
        assert rag.uses_chromadb is False


class TestRAGPipelineIndexing:
    def setup_method(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        # Ensure no ChromaDB (use fallback keyword search)
        with patch.dict("sys.modules", {"chromadb": None}):
            self.rag = RAGPipeline(gateway=gw)

    def test_index_text_returns_chunk_count(self):
        count = self.rag.index_text("This is a test document about the lab schedule.", source="test.txt")
        assert count >= 1

    def test_index_text_stores_chunks(self):
        self.rag.index_text("Lab opens at 9 AM. Lab closes at 6 PM.", source="schedule.txt")
        assert len(self.rag._documents) >= 1

    def test_index_text_with_metadata(self):
        self.rag.index_text("Test content", source="doc.txt", metadata={"section": "intro"})
        assert self.rag._documents[0].metadata.get("section") == "intro"

    def test_index_creates_overlapping_chunks(self):
        long_text = "A" * 1200
        count = self.rag.index_text(long_text, source="long.txt")
        assert count >= 2

    def test_index_file_txt(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_text("Lab is on the third floor. The cafeteria is in the basement.")
        count = self.rag.index_file(f)
        assert count >= 1

    def test_index_file_csv(self, tmp_path: Path):
        f = tmp_path / "data.csv"
        f.write_text("name,value\nprofessor,Dr Smith\nhours,9-6")
        count = self.rag.index_file(f)
        assert count >= 1

    def test_index_directory(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("Document A content about lab hours.")
        (tmp_path / "b.txt").write_text("Document B content about research projects.")
        count = self.rag.index_directory(tmp_path)
        assert count >= 2


class TestRAGPipelineRetrieval:
    def setup_method(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        with patch.dict("sys.modules", {"chromadb": None}):
            self.rag = RAGPipeline(gateway=gw, top_k=2)
        self.rag.index_text("The lab opens at 9 AM on weekdays.", source="schedule.txt")
        self.rag.index_text("Professor Smith studies machine learning.", source="personnel.txt")
        self.rag.index_text("Room 305 is on the third floor near the elevator.", source="map.txt")

    def test_retrieve_returns_chunks(self):
        chunks = self.rag.retrieve("What time does the lab open?")
        assert len(chunks) >= 1
        assert all(isinstance(c, DocumentChunk) for c in chunks)

    def test_retrieve_relevant_chunks(self):
        chunks = self.rag.retrieve("Where is Room 305?")
        texts = [c.text for c in chunks]
        assert any("305" in t or "floor" in t.lower() for t in texts)

    def test_retrieve_empty_when_no_docs(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        with patch.dict("sys.modules", {"chromadb": None}):
            empty_rag = RAGPipeline(gateway=gw)
        chunks = empty_rag.retrieve("anything")
        assert chunks == []

    def test_retrieve_respects_top_k(self):
        chunks = self.rag.retrieve("lab room professor floor")
        assert len(chunks) <= self.rag.top_k

    def test_format_context_empty(self):
        context = RAGPipeline._format_context([])
        assert context == ""

    def test_format_context_with_chunks(self):
        chunks = [
            DocumentChunk(text="Lab opens at 9 AM", source="schedule.txt"),
            DocumentChunk(text="Room 305 is on floor 3", source="map.txt"),
        ]
        context = RAGPipeline._format_context(chunks)
        assert "schedule.txt" in context
        assert "Lab opens at 9 AM" in context
        assert "[1]" in context
        assert "[2]" in context


class TestRAGPipelineQuery:
    def setup_method(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        with patch.dict("sys.modules", {"chromadb": None}):
            self.rag = RAGPipeline(gateway=gw)
        self.rag.index_text("The lab opens at 9 AM.", source="schedule.txt")

    @pytest.mark.asyncio
    async def test_query_returns_rag_response(self):
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 50
        mock_usage.completion_tokens = 20
        mock_choice = MagicMock()
        mock_choice.message.content = "The lab opens at 9 AM."
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage = mock_usage

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            response = await self.rag.query("What time does the lab open?")

        assert isinstance(response, RAGResponse)
        assert response.answer == "The lab opens at 9 AM."
        assert response.rag_enabled is True
        assert response.latency_ms > 0

    @pytest.mark.asyncio
    async def test_query_rag_on_attaches_chunks(self):
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 50
        mock_usage.completion_tokens = 20
        mock_choice = MagicMock()
        mock_choice.message.content = "Answer"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage = mock_usage

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            response = await self.rag.query("lab opening hours")

        assert len(response.retrieved_chunks) >= 1

    @pytest.mark.asyncio
    async def test_query_no_docs_returns_not_rag_enabled(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        with patch.dict("sys.modules", {"chromadb": None}):
            empty_rag = RAGPipeline(gateway=gw)

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_choice = MagicMock()
        mock_choice.message.content = "I don't know."
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage = mock_usage

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            response = await empty_rag.query("any question")

        assert response.rag_enabled is False


class TestHallucinationDetection:
    def setup_method(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        with patch.dict("sys.modules", {"chromadb": None}):
            self.rag = RAGPipeline(gateway=gw)

    def test_no_hallucination_when_answer_matches_context(self):
        chunks = [DocumentChunk(
            text="The laboratory opens at nine o'clock in the morning.",
            source="schedule.txt",
        )]
        result = self.rag._detect_hallucination(
            "The laboratory opens at nine in the morning.", chunks
        )
        assert result is False

    def test_hallucination_detected_when_no_overlap(self):
        chunks = [DocumentChunk(text="The cafeteria serves lunch.", source="food.txt")]
        result = self.rag._detect_hallucination(
            "The quantum reactor produces seventeen terawatts of hyperdimensional energy.", chunks
        )
        assert result is True

    def test_no_hallucination_when_no_chunks(self):
        result = self.rag._detect_hallucination("anything", [])
        assert result is False


# ── Knowledge base layout (merged from test_new_components.py) ────────────────
# Lives in test_rag.py because the KB is what the RAG pipeline indexes.

class TestKnowledgeBase:
    KB_DIR = Path(__file__).parent.parent / "knowledge_base"

    def test_knowledge_base_directory_exists(self):
        assert self.KB_DIR.exists(), f"knowledge_base/ dir not found at {self.KB_DIR}"

    def test_kb_has_some_content(self):
        files = [p for p in self.KB_DIR.iterdir() if p.is_file()]
        assert len(files) > 0, "KB is empty — run: python -m omnillm.rag.builder --rebuild"
