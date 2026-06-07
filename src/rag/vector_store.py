"""
src/rag/vector_store.py
───────────────────────
ChromaDB vector store interface.
Handles storing and retrieving document chunks with metadata.
"""

from pathlib import Path
from langchain_chroma import Chroma
from langchain.schema import Document
from src.config import settings
from src.rag.embeddings import get_embeddings

_store_instance: Chroma | None = None


def get_vector_store() -> Chroma:
    """
    Returns singleton ChromaDB instance.
    Persists to disk at settings.chroma_persist_dir.
    """
    global _store_instance
    if _store_instance is None:
        Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        _store_instance = Chroma(
            collection_name=settings.chroma_collection_name,
            embedding_function=get_embeddings(),
            persist_directory=settings.chroma_persist_dir,
        )
    return _store_instance


def add_chunks(chunks: list[Document]) -> None:
    """Add document chunks to the vector store."""
    store = get_vector_store()

    # Convert is_adversarial bool to int — ChromaDB only supports str/int/float
    for chunk in chunks:
        chunk.metadata["is_adversarial"] = int(chunk.metadata.get("is_adversarial", 0))

    store.add_documents(chunks)
    print(f"[vector_store] Added {len(chunks)} chunks to ChromaDB.")


def similarity_search(
    query: str,
    k: int = None,
    filter: dict = None,
) -> list[Document]:
    """
    Dense semantic search against the vector store.
    filter: ChromaDB metadata filter e.g. {"version": "3.x"}
    """
    store = get_vector_store()
    k = k or settings.rag_top_k_dense
    return store.similarity_search(query, k=k, filter=filter)


def similarity_search_with_score(
    query: str,
    k: int = None,
    filter: dict = None,
) -> list[tuple[Document, float]]:
    """Dense search returning (document, score) tuples."""
    store = get_vector_store()
    k = k or settings.rag_top_k_dense
    return store.similarity_search_with_relevance_scores(query, k=k, filter=filter)


def get_collection_count() -> int:
    """Returns total number of chunks stored."""
    store = get_vector_store()
    return store._collection.count()


if __name__ == "__main__":
    from src.rag.ingestion import load_chunks

    chunks = load_chunks()
    add_chunks(chunks)

    count = get_collection_count()
    print(f"[vector_store] Total chunks in store: {count}")

    results = similarity_search_with_score("How do I enable SAML SSO?", k=3)
    print("\n[vector_store] Test search results:")
    for doc, score in results:
        print(f"  score={score:.3f} | {doc.metadata.get('source_file')} | {doc.metadata.get('section')}")