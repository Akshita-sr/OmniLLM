"""RAG (Retrieval-Augmented Generation) pipeline for OmniLLM.

Provides knowledge-grounded responses by retrieving relevant document chunks
from a vector store before calling the LLM, ensuring factual accuracy and
reducing hallucinations.

Architecture::

    User Query
        │
        ▼
    RAGPipeline.query(question)
        │
        ├─▶ Embed question (sentence-transformers or OpenAI embeddings)
        │
        ├─▶ ChromaDB similarity search → top-k document chunks
        │
        ├─▶ Assemble augmented prompt: system + retrieved context + user question
        │
        └─▶ LLMGateway.query(model_id, augmented_messages)
                │
                └─▶ RAGResponse(answer, retrieved_chunks, faithfulness_score)

Designed for the Embodied LLM Arena experiment:

- **T1 (Info Retrieval)**: lab schedule, personnel bios, project descriptions
- **T2 (Navigation)**: room maps, building layouts, directions
- RAG-on vs. RAG-off conditions are tested to isolate the RAG contribution.

Optional dependencies (install with ``pip install omnillm[hri]``):
- ``chromadb`` — vector store
- ``langchain-community`` — document loaders (PDF, CSV, TXT)
- ``sentence-transformers`` — local embedding model
"""

from omnillm.rag.pipeline import RAGPipeline, RAGResponse

__all__ = ["RAGPipeline", "RAGResponse"]
