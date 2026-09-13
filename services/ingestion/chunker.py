
import logging
import sys
import uuid
from pathlib import Path

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
 
logger = logging.getLogger(__name__)
 
DEFAULT_LEGAL_SEPARATORS = [
    "\nChapter ", "\nCHAPTER ", "\nSection ", "\nSECTION ",
    "\nArticle ", "\nARTICLE ", "\nPart ", "\nPART ",
    "\n\n", "\n", ". ", "? ", "! ", "; ", ": ", ", ", " ", "",
]
 
CHUNK_SIZE_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 150
 
_encoding = tiktoken.get_encoding("cl100k_base")
 
 
def _token_length(text: str) -> int:
    return len(_encoding.encode(text))
 
 
def get_splitter(
    chunk_size_tokens: int = CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> RecursiveCharacterTextSplitter:
    if chunk_overlap_tokens >= chunk_size_tokens:
        raise ValueError(
            "chunk_overlap_tokens must be smaller than chunk_size_tokens "
            f"(got overlap={chunk_overlap_tokens}, size={chunk_size_tokens})."
        )
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size_tokens,
        chunk_overlap=chunk_overlap_tokens,
        length_function=_token_length,
        separators=DEFAULT_LEGAL_SEPARATORS,
    )
 
 
def chunk_documents(documents) -> list[dict]:
    """Splits documents into chunks. Returns plain dicts
    ({"text": ..., "metadata": ...}), not LangChain Document objects,
    to keep this pipeline decoupled from LangChain's object model.
    """
    splitter = get_splitter()
    all_chunks = []
 
    for doc in documents:
        if not doc.page_content or not doc.page_content.strip():
            logger.warning("Skipping empty document: %s", doc.metadata.get("source"))
            continue
 
        split_texts = splitter.split_text(doc.page_content)
 
        for i, chunk_text in enumerate(split_texts):
            chunk_metadata = dict(doc.metadata)
            chunk_metadata.update(
                {
                    "chunk_id": str(uuid.uuid4()),
                    "chunk_index": i,
                    "chunk_count": len(split_texts),
                    "token_count": _token_length(chunk_text),
                }
            )
            all_chunks.append({"text": chunk_text, "metadata": chunk_metadata})
 
    logger.info("\nTotal chunks created: %d", len(all_chunks))
    return all_chunks
 
 
if __name__ == "__main__":
    # Manual test only. Run as: python -m services.ingestion.chunker
    # (from the project root).
    logging.basicConfig(level=logging.INFO)
    from services.ingestion.loaders.loader import load_all_documents
 
    docs = load_all_documents()
    chunks = chunk_documents(docs)
 
    for chunk in chunks[:2]:
        print("\nMetadata:", chunk["metadata"])
        print("Text preview:", chunk["text"][:300])
        print("-" * 80)
 
    print(f"\nTotal chunks: {len(chunks)}")