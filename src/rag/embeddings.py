"""
src/rag/embeddings.py
─────────────────────
Embedding generator using sentence-transformers via LangChain's
HuggingFaceEmbeddings wrapper. Singleton pattern — model loads once.
"""

from langchain_huggingface import HuggingFaceEmbeddings
from src.config import settings

_embeddings_instance: HuggingFaceEmbeddings | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Returns a singleton HuggingFaceEmbeddings instance.
    Model is downloaded once and cached locally by sentence-transformers.
    """
    global _embeddings_instance
    if _embeddings_instance is None:
        print(f"[embeddings] Loading model: {settings.embedding_model}")
        _embeddings_instance = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        print("[embeddings] Model loaded.")
    return _embeddings_instance


if __name__ == "__main__":
    emb = get_embeddings()
    test = emb.embed_query("How do I enable SAML SSO?")
    print(f"[embeddings] Vector dim: {len(test)}")
    print(f"[embeddings] First 5 values: {test[:5]}")