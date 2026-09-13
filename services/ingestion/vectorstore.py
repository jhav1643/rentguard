
import importlib
import logging
import shutil
import sys
from pathlib import Path

from langchain_chroma import Chroma

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PERSIST_DIR = PROJECT_ROOT / "data" / "vectorstore" / "chroma"
COLLECTION_NAME = "rentguard_legal_docs"

_vectorstore_instance = None


def _get_embeddings():
    """Lazy import of the embedder to avoid circular dependencies."""
    module = importlib.import_module("services.common.embedder")
    return module.get_embeddings()


def _reset_persisted_vectorstore() -> None:
    """Clears stale Chroma state at both the collection and filesystem layers.

    Chroma stores collection metadata in SQLite and the embedding dimension is part of
    that persisted schema. Deleting only the directory can leave the old collection
    definition behind when the embedding model changes across runs.
    """
    global _vectorstore_instance

    try:
        if _vectorstore_instance is not None:
            logger.warning(
                "Deleting stale Chroma collection '%s' before recreating it.",
                COLLECTION_NAME,
            )
            _vectorstore_instance.delete_collection()
    except Exception as exc:
        logger.warning("Chroma collection delete failed: %s", exc)

    if PERSIST_DIR.exists():
        logger.warning(
            "Removing persisted Chroma files at %s due to stale embedding metadata.",
            PERSIST_DIR,
        )
        shutil.rmtree(PERSIST_DIR, ignore_errors=True)

    _vectorstore_instance = None


def get_vectorstore(embeddings=None) -> Chroma:
    """Returns a singleton Chroma vectorstore instance.
    If embeddings is None, fetches the default from services.common.embedder.
    """
    global _vectorstore_instance
 
    if _vectorstore_instance is None:
        if embeddings is None:
            embeddings = _get_embeddings()
 
        PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        _vectorstore_instance = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=str(PERSIST_DIR),
        )
        logger.info("Initialized Chroma vectorstore at %s", PERSIST_DIR)
    return _vectorstore_instance
 
 
def add_chunks(vectorstore: Chroma, chunks: list[dict], batch_size: int = 64) -> None:
    """Embeds and stores chunks in batches. Raises an exception if any batch fails."""
    if not chunks:
        logger.info("No chunks to add.")
        return
    if batch_size <= 0:
        raise ValueError(f"batch_size must be a positive integer, got {batch_size}.")
 
    texts = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    ids = [c["metadata"]["chunk_id"] for c in chunks]
 
    total = len(texts)
    failed_batches = []
 
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        try:
            vectorstore.add_texts(
                texts=texts[start:end],
                metadatas=metadatas[start:end],
                ids=ids[start:end],
            )
            logger.info("Embedded and stored chunks %d-%d of %d", start, end, total)
        except Exception as e:
            error_text = str(e)
            if "dimension" in error_text.lower() and "collection expecting" in error_text.lower():
                logger.warning(
                    "Detected stale persisted Chroma collection with incompatible embedding dimension. Resetting local vectorstore and retrying."
                )
                _reset_persisted_vectorstore()
                vectorstore = get_vectorstore(getattr(vectorstore, "_embedding_function", None))
                try:
                    vectorstore.add_texts(
                        texts=texts[start:end],
                        metadatas=metadatas[start:end],
                        ids=ids[start:end],
                    )
                    logger.info("Retry succeeded for chunks %d-%d of %d", start, end, total)
                    continue
                except Exception as retry_error:
                    logger.error("Retry failed on batch %d-%d: %s", start, end, retry_error)
                    failed_batches.append((start, end, retry_error))
                    continue
            logger.error("Failed on batch %d-%d: %s", start, end, e)
            failed_batches.append((start, end, e))
 
    if failed_batches:
        raise RuntimeError(
            f"Failed to store {len(failed_batches)} batch(es). "
            f"First error: {failed_batches[0][2]}"
        )
 
 
def query_by_jurisdiction(vectorstore: Chroma, query: str, jurisdiction: str, k: int = 5):
    """Retrieval filtered by jurisdiction metadata."""
    if not query or not query.strip():
        raise ValueError("query cannot be empty.")
    return vectorstore.similarity_search(
        query,
        k=k,
        filter={"jurisdiction": jurisdiction.lower().strip()},
    )
 
 
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    embeddings = _get_embeddings()
    store = get_vectorstore(embeddings)
    logger.info("Vectorstore ready at: %s", PERSIST_DIR)
    logger.info("Embeddings: %s", embeddings)