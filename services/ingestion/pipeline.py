
import importlib
import json
import logging
import sys
from pathlib import Path

from pre_commit import store

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

embedder_module = importlib.import_module("services.common.embedder")
chunker_module = importlib.import_module("services.ingestion.chunker")
loader_module = importlib.import_module("services.ingestion.loaders.loader")
vectorstore_module = importlib.import_module("services.ingestion.vectorstore")

get_embeddings = embedder_module.get_embeddings
validate_chunks = embedder_module.validate_chunks
chunk_documents = chunker_module.chunk_documents
load_all_documents = loader_module.load_all_documents
add_chunks = vectorstore_module.add_chunks
get_vectorstore = vectorstore_module.get_vectorstore
 
logger = logging.getLogger(__name__)
 
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHUNK_CACHE_PATH = PROJECT_ROOT / "data" / "processed" / "chunks" / "chunks.json"
 
 
def cache_chunks(chunks: list[dict]) -> None:
    """Saves chunked output to disk so re-runs don't need to re-parse
    and re-chunk PDFs from scratch (parsing is cheap here, but this
    also gives you an inspectable artifact to eyeball chunk quality).
    """
    CHUNK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHUNK_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    logger.info("Cached %d chunks to %s", len(chunks), CHUNK_CACHE_PATH)
 
 
def get_existing_chunk_ids(vectorstore) -> set:
    """Returns the set of chunk_ids already stored in the vector store,
    so we can skip re-embedding them. Uses the underlying chromadb
    collection directly since LangChain's Chroma wrapper doesn't expose
    a simple "list all ids" method itself.
    """
    try:
        existing = vectorstore._collection.get(include=[])
        return set(existing.get("ids", []))
    except Exception:
        logger.warning("Could not fetch existing ids (assuming empty store).", exc_info=True)
        return set()
 
 
def filter_new_chunks(chunks: list[dict], existing_ids: set) -> list[dict]:
    new_chunks = [c for c in chunks if c["metadata"]["chunk_id"] not in existing_ids]
    skipped = len(chunks) - len(new_chunks)
    if skipped:
        logger.info("Skipping %d chunk(s) already present in vector store.", skipped)
    return new_chunks
 
 
def verify_chunk_distribution(chunks: list[dict]) -> None:
    from collections import Counter
 
    source_counts = Counter(c["metadata"].get("source", "unknown") for c in chunks)
    logger.info("Chunk distribution by source file:")
    for source, count in source_counts.items():
        logger.info("  %s: %d chunks", source, count)
 
 
def run_pipeline() -> list[dict]:
    logger.info("Step 1/5: Loading documents...")
    documents = load_all_documents()
    if not documents:
        raise RuntimeError("No documents loaded from data/raw. Aborting pipeline.")
 
    logger.info("\nStep 2/5: Chunking documents...")
    chunks = chunk_documents(documents)
    if not chunks:
        raise RuntimeError("Chunking produced no chunks. Aborting pipeline.")
    verify_chunk_distribution(chunks)
 
    logger.info("\nStep 3/5: Validating chunks...")
    validate_chunks(chunks)
    cache_chunks(chunks)
 
    logger.info("\nStep 4/5: Setting up embeddings + vector store...")
    embeddings = get_embeddings()
    store = get_vectorstore(embeddings)
 
    existing_ids = get_existing_chunk_ids(store)
    new_chunks = filter_new_chunks(chunks, existing_ids)
 
    if not new_chunks:
        logger.info("No new chunks to embed. Vector store already up to date.")
    else:
        logger.info("\nStep 5/5: Embedding and storing %d new chunk(s)...", len(new_chunks))
        add_chunks(store, new_chunks)
 
    total = len(existing_ids) + len(new_chunks)
    logger.info("Pipeline completed. Vector store contains %d chunk(s) total.", total)
    return chunks
 
 
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_pipeline()
    logger.info("Done.")
    actual_count = store._collection.count()
    logger.info(f"Pipeline completed. Vector store contains {actual_count} chunk(s) total.")
