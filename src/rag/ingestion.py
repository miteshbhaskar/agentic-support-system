"""
src/rag/ingestion.py
────────────────────
Loads markdown files from docs/ using LangChain's MarkdownHeaderTextSplitter
for section-aware chunking with full metadata preservation.
"""

from pathlib import Path
from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain.schema import Document
from src.config import settings


# ── Metadata map — filename → (category, version, is_adversarial) ──
DOC_METADATA: dict[str, tuple[str, str, bool]] = {
    "sso-setup-v2.md":            ("authentication", "2.x", False),
    "sso-setup-v3.md":            ("authentication", "3.x", False),
    "export-limits-v2.md":        ("exports",        "2.x", False),
    "export-limits-v3.md":        ("exports",        "3.x", False),
    "webhook-troubleshooting.md": ("integrations",   "all", False),
    "billing-refund-policy.md":   ("billing",        "all", False),
    "dashboard-known-issues.md":  ("dashboard",      "all", False),
    "release-notes-v3.1.md":      ("release-notes",  "3.1", False),
    "release-notes-v3.2.md":      ("release-notes",  "3.2", False),
    "system-override.md":         ("system",         "all", True),
}

HEADERS_TO_SPLIT = [
    ("#",   "section_h1"),
    ("##",  "section_h2"),
    ("###", "section_h3"),
]

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def load_chunks() -> list[Document]:
    """
    Reads all markdown docs, splits by headers, then by size if needed.
    Each Document carries metadata:
        source_file, category, version, section, is_adversarial
    """
    docs_dir = Path(settings.docs_dir)

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT,
        strip_headers=False,
    )

    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    all_chunks: list[Document] = []

    for filename, (category, version, is_adversarial) in DOC_METADATA.items():
        filepath = docs_dir / filename
        if not filepath.exists():
            print(f"[ingestion] WARNING: {filename} not found, skipping.")
            continue

        content = filepath.read_text(encoding="utf-8")

        header_chunks = header_splitter.split_text(content)
        split_chunks = char_splitter.split_documents(header_chunks)

        for chunk in split_chunks:
            section = (
                chunk.metadata.get("section_h3")
                or chunk.metadata.get("section_h2")
                or chunk.metadata.get("section_h1")
                or "Overview"
            )

            chunk.metadata.update({
                "source_file":    filename,
                "category":       category,
                "version":        version,
                "section":        section,
                "is_adversarial": is_adversarial,
            })

            all_chunks.append(chunk)

    print(f"[ingestion] Loaded {len(all_chunks)} chunks from {len(DOC_METADATA)} documents.")
    return all_chunks


if __name__ == "__main__":
    chunks = load_chunks()
    for c in chunks[:3]:
        print(f"\n--- {c.metadata} ---")
        print(c.page_content[:200])