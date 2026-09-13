import os
 
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpointEmbeddings
 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
 
HF_TOKEN = os.getenv("EMBEDDING_TOKEN")
MODEL_NAME = os.getenv("MODEL_NAME") 
 
if not HF_TOKEN:
    raise ValueError(
        "EMBEDDING_TOKEN is not configured. "
        "Add your Hugging Face token to the .env file."
    )
 
if not MODEL_NAME:
    raise ValueError(
        "MODEL_NAME is not configured. "
        "Add your model name to the .env file."
    )
 
_embedding_instance = None
 
 
def get_embeddings() -> HuggingFaceEndpointEmbeddings:
    
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = HuggingFaceEndpointEmbeddings(
            model=MODEL_NAME,
            task="feature-extraction",
            huggingfacehub_api_token=HF_TOKEN,
        )
    return _embedding_instance
 
 
def validate_chunks(all_chunks: list[dict]) -> None:
    """Validates chunks BEFORE they're sent for embedding. Raises on the
    first problem found so bad data never silently reaches the API call
    (and burns a rate-limited batch on garbage input).
 
    Call this from pipeline.py right before vectorstore.add_chunks(),
    not from get_embeddings().
    """
    if not all_chunks:
        raise ValueError("all_chunks cannot be empty.")
 
    for index, chunk in enumerate(all_chunks):
        if not isinstance(chunk, dict):
            raise TypeError(
                f"Expected dict for chunk at index {index}, "
                f"got {type(chunk).__name__}."
            )
 
        text = chunk.get("text")
        if not text or not text.strip():
            raise ValueError(f"Chunk at index {index} has empty 'text'.")
 
        metadata = chunk.get("metadata")
        if not metadata or "chunk_id" not in metadata:
            raise ValueError(
                f"Chunk at index {index} is missing 'metadata.chunk_id' "
                f"(required as the vectorstore document id)."
            )
 
 
if __name__ == "__main__":
    # Isolated sanity check -- no chunks needed, just confirms the model
    # itself returns a usable vector before anything else depends on it.
    embeddings = get_embeddings()
    test_vector = embeddings.embed_query(
        "Security deposit shall not exceed 10 months rent"
    )
    print(f"Embedding model: {MODEL_NAME}")
    print(f"Vector length: {len(test_vector)}")
    print(f"First 5 values: {test_vector[:5]}")
 