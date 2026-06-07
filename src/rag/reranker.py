"""
src/rag/reranker.py
───────────────────
Reranks hybrid search results using cross-encoder scoring.
Falls back to combined_score ordering if cross-encoder unavailable.
"""

from langchain.schema import Document

try:
    from sentence_transformers import CrossEncoder
    _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    CROSS_ENCODER_AVAILABLE = True
    print("[reranker] Cross-encoder loaded.")
except Exception:
    CROSS_ENCODER_AVAILABLE = False
    print("[reranker] Cross-encoder unavailable, using combined_score fallback.")


def rerank(query: str, results: list[dict], top_k: int = None) -> list[dict]:
    """
    Reranks retrieval results for a given query.

    If cross-encoder is available:
        scores each (query, chunk_text) pair directly — more accurate
        than cosine similarity alone.
    Otherwise:
        returns results already sorted by combined_score.

    Args:
        query:   the original search query
        results: list of dicts from hybrid_search()
        top_k:   how many to return (defaults to all)

    Returns:
        reranked list of result dicts with added 'rerank_score' field
    """
    if not results:
        return results

    if CROSS_ENCODER_AVAILABLE:
        pairs = [[query, r["text"]] for r in results]
        scores = _cross_encoder.predict(pairs)

        for result, score in zip(results, scores):
            result["rerank_score"] = round(float(score), 4)

        results.sort(key=lambda x: x["rerank_score"], reverse=True)
    else:
        for result in results:
            result["rerank_score"] = result["combined_score"]

    return results[:top_k] if top_k else results


if __name__ == "__main__":
    from src.rag.ingestion import load_chunks
    from src.rag.retriever import hybrid_search, build_bm25_index

    chunks = load_chunks()
    build_bm25_index(chunks)

    raw = hybrid_search("How do I configure SAML SSO?", version="3.2")
    reranked = rerank("How do I configure SAML SSO?", raw)

    print("\n[reranker] Results after reranking:")
    for r in reranked:
        print(f"  rerank={r['rerank_score']} combined={r['combined_score']}")
        print(f"  {r['source_file']} | {r['section']}")
        print()