"""
RentGuard — Retriever
Top‑level function to retrieve relevant legal chunks for a query,
filtered by jurisdiction.
"""
 
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.common.embedder import get_embeddings
from services.ingestion.vectorstore import get_vectorstore
 
logger = logging.getLogger(__name__)
 
# Dynamically determine allowed jurisdictions from folders under data/raw.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
ALLOWED_JURISDICTIONS = (
    {d.name.lower() for d in RAW_DATA_DIR.iterdir() if d.is_dir()}
    if RAW_DATA_DIR.exists()
    else set()
)
 
 
def retrieve(query: str, jurisdiction: str, k: int = 5) -> list[dict]:
    """Returns top-k relevant chunks for a query, filtered to a single
    jurisdiction. Raises early on bad input rather than silently
    returning an empty/wrong result.
    """
    if not query or not query.strip():
        raise ValueError("query cannot be empty.")
    if k <= 0:
        raise ValueError(f"k must be a positive integer, got {k}.")
 
    jurisdiction = jurisdiction.lower().strip()
    if jurisdiction not in ALLOWED_JURISDICTIONS:
        raise ValueError(
            f"Unknown jurisdiction '{jurisdiction}'. "
            f"Allowed: {sorted(ALLOWED_JURISDICTIONS)}"
        )
 
    embeddings = get_embeddings()
    store = get_vectorstore(embeddings)  # returns singleton
 
    try:
        results = store.similarity_search(
            query,
            k=k,
            filter={"jurisdiction": jurisdiction},
        )
    except Exception as e:
        raise RuntimeError(f"Retrieval failed for query '{query}': {e}") from e
 
    if not results:
        logger.info("No matches found for jurisdiction='%s', query='%s'", jurisdiction, query)
        return []
 
    return [
        {
            "text": doc.page_content,
            "source": doc.metadata.get("source"),
            "jurisdiction": doc.metadata.get("jurisdiction"),
            "chunk_id": doc.metadata.get("chunk_id"),
        }
        for doc in results
    ]
 
 
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_results = retrieve(
        query="What is the maximum security deposit a landlord can charge?",
        jurisdiction="delhi",
        k=3,
    )
    for i, r in enumerate(test_results):
        print(f"\n--- Result {i + 1} ---")
        print(f"Source: {r['source']}")
        print(f"Text: {r['text'][:300]}")
        print(f"Jurisdiction: {r['jurisdiction']}")
        print(f"Chunk ID: {r['chunk_id']}")