"""RAG Pipeline using ChromaDB and optional LangChain document loaders.

This module implements the retrieval-augmented generation pipeline used in
the Embodied LLM Arena experiment.  It supports:

- Indexing documents from PDF, CSV, and plain-text files
- Semantic similarity search over a persistent ChromaDB collection
- Assembling augmented prompts with retrieved context
- RAG faithfulness scoring (via LLM-as-judge)
- Hallucination detection by comparing responses against retrieved chunks

The pipeline works with or without ``chromadb`` installed:
- With ChromaDB: full semantic search over the knowledge base
- Without ChromaDB (fallback): keyword-based search over in-memory documents

Usage::

    from omnillm.rag import RAGPipeline
    from omnillm.gateway import LLMGateway

    gateway = LLMGateway()
    rag = RAGPipeline(gateway=gateway, model_id="openai-gpt4o-mini")
    rag.index_directory("knowledge_base/")

    response = await rag.query("What time does the lab open?")
    print(response.answer)
    print(f"Faithfulness: {response.faithfulness_score:.2f}")
    print(f"Sources: {[c['source'] for c in response.retrieved_chunks]}")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from omnillm.gateway import LLMGateway


@dataclass
class DocumentChunk:
    """A single chunk of a retrieved document.

    Attributes:
        text: The chunk text content.
        source: Source file or document name.
        chunk_id: Unique identifier for this chunk.
        metadata: Additional metadata (page number, section, etc.).
        similarity_score: Relevance score from the vector store (0–1).
    """

    text: str
    source: str
    chunk_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    similarity_score: float = 0.0


@dataclass
class RAGResponse:
    """Response from the RAG pipeline.

    Attributes:
        answer: The LLM-generated answer, grounded in retrieved context.
        retrieved_chunks: Document chunks retrieved for this query.
        faithfulness_score: How faithfully the answer uses the retrieved
            context (0–1, scored by LLM-as-judge).  -1.0 means not scored.
        hallucination_detected: Whether the answer contains claims not
            supported by the retrieved chunks.
        model_id: Which LLM backend generated the answer.
        rag_enabled: Whether RAG was active for this response.
        latency_ms: Total pipeline latency (retrieval + LLM) in milliseconds.
    """

    answer: str
    retrieved_chunks: list[DocumentChunk] = field(default_factory=list)
    faithfulness_score: float = -1.0
    hallucination_detected: bool = False
    model_id: str = ""
    rag_enabled: bool = True
    latency_ms: float = 0.0


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for OmniLLM.

    Indexes a knowledge base of documents and uses semantic search to
    retrieve relevant context before LLM generation.  Designed for the
    Embodied LLM Arena experiment's T1 (Info Retrieval) and T2 (Navigation)
    task types.

    Example::

        from omnillm.rag import RAGPipeline
        from omnillm.gateway import LLMGateway

        gateway = LLMGateway()
        rag = RAGPipeline(gateway=gateway, model_id="openai-gpt4o-mini")
        rag.index_text("Lab opens at 9 AM.", source="schedule.txt")
        response = await rag.query("What time does the lab open?")
        print(response.answer)
    """

    def __init__(
        self,
        gateway: LLMGateway,
        model_id: str = "openai-gpt4o-mini",
        collection_name: str = "omnillm_knowledge",
        persist_directory: str | Path | None = None,
        top_k: int = 4,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        judge_model: str | None = None,
    ) -> None:
        """Initialise the RAG pipeline.

        Args:
            gateway: Initialised :class:`~omnillm.gateway.LLMGateway` instance.
            model_id: LLM model to use for answer generation.
            collection_name: ChromaDB collection name for document storage.
            persist_directory: Directory to persist the ChromaDB collection.
                If ``None``, uses in-memory storage.
            top_k: Number of document chunks to retrieve per query.
            chunk_size: Character length for document chunking.
            chunk_overlap: Overlap between adjacent chunks (in characters).
            judge_model: Model ID for faithfulness scoring.  Defaults to
                ``model_id`` if not provided.
        """
        self.gateway = gateway
        self.model_id = model_id
        self.collection_name = collection_name
        self.persist_directory = Path(persist_directory) if persist_directory else None
        self.top_k = top_k
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.judge_model = judge_model or model_id

        # In-memory document store (fallback when ChromaDB is not available)
        self._documents: list[DocumentChunk] = []
        self._chroma_client: Any | None = None
        self._collection: Any | None = None

        self._try_init_chromadb()

    # ── ChromaDB initialisation ───────────────────────────────────────────────

    def _try_init_chromadb(self) -> None:
        """Attempt to initialise ChromaDB.  Silently falls back if unavailable."""
        try:
            import chromadb  # type: ignore[import-untyped]

            if self.persist_directory:
                self.persist_directory.mkdir(parents=True, exist_ok=True)
                self._chroma_client = chromadb.PersistentClient(
                    path=str(self.persist_directory)
                )
            else:
                self._chroma_client = chromadb.Client()

            self._collection = self._chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except ImportError:
            pass  # Fall back to in-memory keyword search

    @property
    def uses_chromadb(self) -> bool:
        """Whether the ChromaDB vector store is active."""
        return self._collection is not None

    # ── Document indexing ─────────────────────────────────────────────────────

    def index_text(
        self,
        text: str,
        source: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Index a text string into the knowledge base.

        Splits the text into overlapping chunks and stores them.

        Args:
            text: Raw text content to index.
            source: Source name (file name or label) for attribution.
            metadata: Optional additional metadata to attach to each chunk.

        Returns:
            Number of chunks indexed.
        """
        chunks = self._split_text(text, source, metadata or {})
        if self._collection is not None:
            self._index_to_chromadb(chunks)
        else:
            self._documents.extend(chunks)
        return len(chunks)

    def index_file(self, path: str | Path) -> int:
        """Index a single file (TXT, CSV, or PDF) into the knowledge base.

        PDF support requires ``pypdf``.  CSV files are indexed row by row.

        Args:
            path: Path to the file to index.

        Returns:
            Number of chunks indexed.
        """
        path = Path(path)
        suffix = path.suffix.lower()

        if suffix == ".txt":
            text = path.read_text(encoding="utf-8")
            return self.index_text(text, source=path.name)

        if suffix == ".csv":
            return self._index_csv(path)

        if suffix == ".pdf":
            return self._index_pdf(path)

        # Treat unknown file types as plain text
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return self.index_text(text, source=path.name)
        except Exception:
            return 0

    def index_directory(self, directory: str | Path) -> int:
        """Index all supported files in a directory (recursively).

        Args:
            directory: Root directory to scan for documents.

        Returns:
            Total number of chunks indexed.
        """
        directory = Path(directory)
        total = 0
        for pattern in ("**/*.txt", "**/*.csv", "**/*.pdf"):
            for filepath in directory.glob(pattern):
                total += self.index_file(filepath)
        return total

    # ── Retrieval and generation ──────────────────────────────────────────────

    async def query(
        self,
        question: str,
        system_prompt: str | None = None,
        score_faithfulness: bool = False,
        model_id: str | None = None,
    ) -> RAGResponse:
        """Generate a RAG-grounded answer for a question.

        Args:
            question: The user's question.
            system_prompt: Optional system prompt to prepend.
            score_faithfulness: If True, uses LLM-as-judge to score how
                faithfully the response uses the retrieved context.
            model_id: Optional one-off model override.  When provided, the
                answer is generated with this model instead of the pipeline's
                default ``self.model_id``.  Used by the LangGraph nodes so
                Condition B (local Llama) actually exercises Ollama through
                the same RAG retrieval as Condition A.

        Returns:
            :class:`RAGResponse` with answer, retrieved chunks, and scores.
        """
        import time

        start = time.perf_counter()

        retrieved = self.retrieve(question)
        context = self._format_context(retrieved)

        system = system_prompt or (
            "You are a helpful assistant. Answer the user's question using ONLY "
            "the provided context. If the answer is not in the context, say so clearly."
        )

        if context:
            user_content = (
                f"Context:\n{context}\n\nQuestion: {question}"
            )
        else:
            user_content = question

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

        effective_model = model_id or self.model_id
        llm_response = await self.gateway.query(effective_model, messages)
        latency_ms = (time.perf_counter() - start) * 1000

        rag_response = RAGResponse(
            answer=llm_response.content,
            retrieved_chunks=retrieved,
            model_id=effective_model,
            rag_enabled=bool(retrieved),
            latency_ms=latency_ms,
        )

        if score_faithfulness and retrieved and not llm_response.is_error:
            rag_response.faithfulness_score = await self._score_faithfulness(
                question, llm_response.content, retrieved
            )
            rag_response.hallucination_detected = self._detect_hallucination(
                llm_response.content, retrieved
            )

        return rag_response

    def retrieve(self, query: str) -> list[DocumentChunk]:
        """Retrieve the top-k most relevant document chunks for a query.

        Uses ChromaDB cosine similarity if available, otherwise falls back
        to simple keyword overlap scoring.

        Args:
            query: The search query.

        Returns:
            List of up to ``top_k`` :class:`DocumentChunk` objects, sorted by
            relevance (most relevant first).
        """
        if self._collection is not None:
            return self._retrieve_chromadb(query)
        return self._retrieve_keyword(query)

    # ── Faithfulness scoring ──────────────────────────────────────────────────

    async def _score_faithfulness(
        self,
        question: str,
        answer: str,
        chunks: list[DocumentChunk],
    ) -> float:
        """Score how faithfully the answer uses the retrieved context (0–1).

        Uses LLM-as-judge: the judge checks whether each claim in the answer
        is supported by the retrieved document chunks (RAG faithfulness).

        Args:
            question: Original question.
            answer: Generated answer to evaluate.
            chunks: Retrieved document chunks used as context.

        Returns:
            Faithfulness score in [0, 1].
        """
        context = self._format_context(chunks)
        prompt = (
            f"You are a factuality judge. Score how faithfully the answer uses ONLY "
            f"information from the given context (0.0 = completely hallucinated, "
            f"1.0 = every claim is supported by the context).\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            f"Answer: {answer}\n\n"
            f'Respond ONLY with valid JSON: {{"score": <float 0.0-1.0>, "reasoning": "<brief explanation>"}}'
        )
        messages = [{"role": "user", "content": prompt}]
        resp = await self.gateway.query(self.judge_model, messages, temperature=0.0)
        if resp.is_error:
            return -1.0
        try:
            raw = resp.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            return float(min(max(data.get("score", 0.5), 0.0), 1.0))
        except (json.JSONDecodeError, ValueError, KeyError):
            match = re.search(r"\b([01](?:\.\d+)?|\d*\.\d+)\b", resp.content)
            if match:
                return float(min(max(float(match.group(1)), 0.0), 1.0))
            return -1.0

    def _detect_hallucination(
        self, answer: str, chunks: list[DocumentChunk]
    ) -> bool:
        """Lightweight hallucination check: are key answer phrases in the context?

        Flags the response as a potential hallucination if fewer than 20% of
        significant answer words appear in any retrieved chunk.  This is a
        conservative heuristic — use ``_score_faithfulness`` for reliable scoring.

        Args:
            answer: Generated answer.
            chunks: Retrieved document chunks.

        Returns:
            True if hallucination is likely.
        """
        if not chunks:
            return False

        all_context = " ".join(c.text.lower() for c in chunks)
        # Consider only words longer than 4 characters to avoid stopwords
        answer_words = [w for w in re.findall(r"\b\w{5,}\b", answer.lower())]
        if not answer_words:
            return False

        found = sum(1 for w in answer_words if w in all_context)
        coverage = found / len(answer_words)
        return coverage < 0.20

    # ── Private helpers ───────────────────────────────────────────────────────

    def _split_text(
        self,
        text: str,
        source: str,
        metadata: dict[str, Any],
    ) -> list[DocumentChunk]:
        """Split text into overlapping chunks."""
        chunks: list[DocumentChunk] = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        text=chunk_text,
                        source=source,
                        chunk_id=f"{source}::{idx}",
                        metadata={**metadata, "chunk_index": idx},
                    )
                )
            start += self.chunk_size - self.chunk_overlap
            idx += 1
        return chunks

    def _index_csv(self, path: Path) -> int:
        """Index a CSV file, treating each row as a document chunk."""
        import csv

        total = 0
        with path.open(encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for i, row in enumerate(reader):
                text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
                if text.strip():
                    self.index_text(
                        text,
                        source=path.name,
                        metadata={"row": i},
                    )
                    total += 1
        return total

    def _index_pdf(self, path: Path) -> int:
        """Index a PDF file using pypdf if available."""
        try:
            import pypdf  # type: ignore[import-untyped]

            total = 0
            reader = pypdf.PdfReader(str(path))
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    total += self.index_text(
                        text,
                        source=path.name,
                        metadata={"page": page_num + 1},
                    )
            return total
        except ImportError:
            # Fall back: read as binary and decode what we can
            try:
                text = path.read_bytes().decode("utf-8", errors="replace")
                return self.index_text(text, source=path.name)
            except Exception:
                return 0

    def _index_to_chromadb(self, chunks: list[DocumentChunk]) -> None:
        """Upsert chunks into the ChromaDB collection."""
        if not chunks or self._collection is None:
            return
        self._collection.upsert(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[{"source": c.source, **c.metadata} for c in chunks],
        )

    def _retrieve_chromadb(self, query: str) -> list[DocumentChunk]:
        """Query ChromaDB for the top-k most relevant chunks."""
        if self._collection is None:
            return []
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(self.top_k, self._collection.count()),
            )
            chunks: list[DocumentChunk] = []
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]
            ids = results.get("ids", [[]])[0]
            for doc, meta, dist, cid in zip(docs, metas, dists, ids):
                chunks.append(
                    DocumentChunk(
                        text=doc,
                        source=meta.get("source", "unknown"),
                        chunk_id=cid,
                        metadata=meta,
                        similarity_score=max(0.0, 1.0 - dist),
                    )
                )
            return chunks
        except Exception:
            return []

    def _retrieve_keyword(self, query: str) -> list[DocumentChunk]:
        """Keyword overlap retrieval (fallback when ChromaDB is unavailable)."""
        query_words = set(re.findall(r"\b\w{3,}\b", query.lower()))
        if not query_words or not self._documents:
            return []

        scored: list[tuple[float, DocumentChunk]] = []
        for chunk in self._documents:
            chunk_words = set(re.findall(r"\b\w{3,}\b", chunk.text.lower()))
            overlap = len(query_words & chunk_words)
            if overlap > 0:
                score = overlap / (len(query_words | chunk_words) + 1e-9)
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, chunk in scored[: self.top_k]:
            results.append(
                DocumentChunk(
                    text=chunk.text,
                    source=chunk.source,
                    chunk_id=chunk.chunk_id,
                    metadata=chunk.metadata,
                    similarity_score=score,
                )
            )
        return results

    @staticmethod
    def _format_context(chunks: list[DocumentChunk]) -> str:
        """Format retrieved chunks into a readable context block."""
        if not chunks:
            return ""
        parts: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            parts.append(f"[{i}] (Source: {chunk.source})\n{chunk.text}")
        return "\n\n".join(parts)
