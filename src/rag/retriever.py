"""
src/rag/retriever.py
────────────────────
Hybrid retrieval combining dense (ChromaDB) and sparse (BM25) search.
Results are merged, deduplicated, and scored.
"""

from langchain.schema import Document
from langchain_community.retrievers import BM25Retriever
from src.config import settings
from src.rag.vector_store import similarity_search_with_score

_bm25_instance: BM25Retriever | None = None
_bm25_corpus: list[Document] = []


def build_bm25_index(chunks: list[Document]) -> None:
    """
    Build BM25 index from document chunks.
    Must be called once after ingestion before hybrid search is used.
    """
    global _bm25_instance, _bm25_corpus
    _bm25_corpus = chunks
    _bm25_instance = BM25Retriever.from_documents(
        chunks,
        k=settings.rag_top_k_sparse,
    )
    print(f"[retriever] BM25 index built with {len(chunks)} chunks.")


def get_bm25() -> BM25Retriever:
    if _bm25_instance is None:
        raise RuntimeError("BM25 index not built. Call build_bm25_index() first.")
    return _bm25_instance


def _build_metadata_filter(
    version: str | None,
    category: str | None,
    exclude_adversarial: bool = True,
) -> dict | None:
    """Build ChromaDB metadata filter from optional version and category."""
    filters = []

    # Always block adversarial docs at DB level
    if exclude_adversarial:
        filters.append({"is_adversarial": {"$eq": 0}})

    if version:
        major = version.split(".")[0] + ".x"
        filters.append({
            "$or": [
                {"version": {"$eq": version}},
                {"version": {"$eq": major}},
                {"version": {"$eq": "all"}},
            ]
        })

    if category:
        filters.append({"category": {"$eq": category}})

    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    return {"$and": filters}


def hybrid_search(
    query: str,
    version: str | None = None,
    category: str | None = None,
    exclude_adversarial: bool = True,
) -> list[dict]:
    """
    Hybrid search: dense + sparse combined.

    Returns list of dicts:
        text, source_file, section, category, version,
        is_adversarial, dense_score, sparse_score, combined_score
    """
    chroma_filter = _build_metadata_filter(version, category, exclude_adversarial)

    # ── Dense retrieval ───────────────────────────────────────────
    dense_results = similarity_search_with_score(
        query,
        k=settings.rag_top_k_dense,
        filter=chroma_filter,
    )

    # ── Sparse BM25 retrieval ─────────────────────────────────────
    bm25 = get_bm25()
    sparse_results = bm25.invoke(query)

    # ── Merge and score ───────────────────────────────────────────
    seen: dict[str, dict] = {}

    for doc, score in dense_results:
        key = doc.page_content[:100]
        seen[key] = {
            "text":          doc.page_content,
            "source_file":   doc.metadata.get("source_file", ""),
            "section":       doc.metadata.get("section", ""),
            "category":      doc.metadata.get("category", ""),
            "version":       doc.metadata.get("version", ""),
            "is_adversarial": bool(doc.metadata.get("is_adversarial", 0)),
            "dense_score":   round(score, 4),
            "sparse_score":  0.0,
            "combined_score": round(score, 4),
        }

    for rank, doc in enumerate(sparse_results):
        key = doc.page_content[:100]
        sparse_score = round(1.0 - (rank / len(sparse_results)), 4)
        if key in seen:
            seen[key]["sparse_score"] = sparse_score
            seen[key]["combined_score"] = round(
                0.6 * seen[key]["dense_score"] + 0.4 * sparse_score, 4
            )
        else:
            seen[key] = {
                "text":          doc.page_content,
                "source_file":   doc.metadata.get("source_file", ""),
                "section":       doc.metadata.get("section", ""),
                "category":      doc.metadata.get("category", ""),
                "version":       doc.metadata.get("version", ""),
                "is_adversarial": bool(doc.metadata.get("is_adversarial", 0)),
                "dense_score":   0.0,
                "sparse_score":  sparse_score,
                "combined_score": round(0.4 * sparse_score, 4),
            }

    # ── Filter adversarial ────────────────────────────────────────
    results = list(seen.values())
    if exclude_adversarial:
        results = [r for r in results if not r["is_adversarial"]]

    # ── Sort by combined score ────────────────────────────────────
    results.sort(key=lambda x: x["combined_score"], reverse=True)

    # Filter by minimum relevance score
    results = [r for r in results if r["combined_score"] >= settings.rag_min_relevance_score]

    return results[:settings.rag_top_k_final]


if __name__ == "__main__":
    from src.rag.ingestion import load_chunks
    from src.rag.vector_store import add_chunks, get_collection_count

    chunks = load_chunks()
    build_bm25_index(chunks)

    results = hybrid_search("How do I enable SAML SSO?", version="3.2")
    print("\n[retriever] Hybrid search results:")
    for r in results:
        print(f"  combined={r['combined_score']} dense={r['dense_score']} sparse={r['sparse_score']}")
        print(f"  {r['source_file']} | {r['section']} | adversarial={r['is_adversarial']}")
        print()