"""
src/tools/knowledge_base_tool.py
─────────────────────────────────
Tool for hybrid RAG search over product documentation.
Combines vector store + BM25 + reranking + guard filtering.
"""

from src.tools.base import BaseTool, ToolError
from src.rag.retriever import hybrid_search, build_bm25_index
from src.rag.reranker import rerank
from src.rag.guard import filter_results
from src.rag.ingestion import load_chunks
from src.config import settings

_bm25_ready = False

# Intents where cross-encoder reranking is worth the latency cost
RERANK_INTENTS = {"sso_setup", "csv_export_issue", "webhook_issue", "plan_limits"}


def _ensure_bm25():
    """Build BM25 index once on first use."""
    global _bm25_ready
    if not _bm25_ready:
        chunks = load_chunks()
        build_bm25_index(chunks)
        _bm25_ready = True


class KnowledgeBaseTool(BaseTool):
    """
    Searches product documentation using hybrid retrieval.
    Input:  query, version (optional), category (optional), intent (optional)
    Output: list of ranked, filtered result dicts with citations
    """

    async def _execute(
        self,
        query: str,
        version: str | None = None,
        category: str | None = None,
        intent: str | None = None,
    ) -> list[dict]:
        if not query or not query.strip():
            raise ToolError(self.name, "query is required", retryable=False)

        _ensure_bm25()

        # Hybrid search (dense + BM25)
        results = hybrid_search(
            query=query,
            version=version,
            category=category,
            exclude_adversarial=True,
        )

        if not results:
            return []

        # Selective reranking — only for intents where precision matters
        use_rerank = (intent in RERANK_INTENTS) if intent else True
        if use_rerank:
            results = rerank(query, results, top_k=settings.rag_top_k_final)
        else:
            # Just use combined_score, add rerank_score alias
            for r in results:
                r["rerank_score"] = r["combined_score"]
            results = results[:settings.rag_top_k_final]

        # Guard filter
        results = filter_results(results)

        return results


if __name__ == "__main__":
    import asyncio

    async def test():
        tool = KnowledgeBaseTool()

        print("Test 1 - SSO (rerank ON):")
        result = await tool.run(query="How do I configure SAML SSO?", version="3.2", intent="sso_setup")
        print(f"  success={result.success} latency={result.latency_ms}ms")
        if result.success:
            for r in result.data:
                print(f"  [{r['rerank_score']:.2f}] {r['source_file']} | {r['section']}")

        print("\nTest 2 - incident check (rerank OFF):")
        result = await tool.run(query="Is there an outage?", intent="incident_check")
        print(f"  success={result.success} latency={result.latency_ms}ms")
        if result.success:
            for r in result.data:
                print(f"  [{r['rerank_score']:.2f}] {r['source_file']} | {r['section']}")

    asyncio.run(test())