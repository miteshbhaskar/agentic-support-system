"""
scripts/ingest_docs.py
──────────────────────
One-time ingestion script. Run this once to populate ChromaDB.
After this, the vector store persists to disk and is ready for use.

Usage:
    python -m scripts.ingest_docs
"""

import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.ingestion import load_chunks
from src.rag.vector_store import get_vector_store, add_chunks, get_collection_count
from src.rag.retriever import build_bm25_index
from src.config import settings


def main():
    print("=" * 55)
    print(" FlowDesk RAG Ingestion")
    print("=" * 55)

    # ── Check if already ingested ─────────────────────────────────
    store = get_vector_store()
    existing = get_collection_count()

    if existing > 0:
        print(f"\n[ingest] ChromaDB already contains {existing} chunks.")
        answer = input("[ingest] Re-ingest and overwrite? (y/N): ").strip().lower()
        if answer != "y":
            print("[ingest] Skipped. Using existing store.")
            return
        # Clear existing collection
        store._collection.delete(where={"source_file": {"$ne": ""}})
        print("[ingest] Cleared existing chunks.")

    # ── Load and chunk documents ──────────────────────────────────
    print("\n[ingest] Loading and chunking documents...")
    chunks = load_chunks()

    # ── Add to ChromaDB ───────────────────────────────────────────
    print("[ingest] Embedding and storing in ChromaDB...")
    add_chunks(chunks)

    # ── Build BM25 index (in-memory, just verify) ─────────────────
    build_bm25_index(chunks)

    # ── Verify ────────────────────────────────────────────────────
    final_count = get_collection_count()
    print(f"\n[ingest] Done. Total chunks in store: {final_count}")

    # ── Summary by source ─────────────────────────────────────────
    print("\n[ingest] Chunks per document:")
    source_counts: dict[str, int] = {}
    for chunk in chunks:
        src = chunk.metadata.get("source_file", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    for src, count in sorted(source_counts.items()):
        adversarial = "[ADVERSARIAL]" if chunk.metadata.get("is_adversarial") and src == chunk.metadata.get("source_file") else ""
        print(f"  {src:<40} {count:>3} chunks")

    print("\n[ingest] Vector store ready at:", settings.chroma_persist_dir)
    print("=" * 55)


if __name__ == "__main__":
    main()