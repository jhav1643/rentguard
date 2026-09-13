from pathlib import Path

from langchain_community.document_loaders import (
    DirectoryLoader,
    Docx2txtLoader,
    PyMuPDFLoader,
    TextLoader,
)

RAW_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

loader_mapping = {
    "pdf": PyMuPDFLoader,
    "txt": TextLoader,
    "docx": Docx2txtLoader,
}

def get_loader(ext: str):
    if ext not in loader_mapping:
        raise ValueError(
            f"Unsupported extension '{ext}'. Supported: {list(loader_mapping)}"
        )
    return loader_mapping[ext]


def build_loader(extension: str, glob_pattern: str) -> DirectoryLoader:
    """Builds a DirectoryLoader for a given extension, with resilience
    to individual bad/corrupt files (silent_errors) so one broken PDF
    doesn't halt the entire ingestion run."""
    loader_kwargs = {}
    if extension == "txt":
        # Avoid crashes on non-UTF-8 government/legal text exports.
        loader_kwargs = {"encoding": "utf-8", "autodetect_encoding": True}

    return DirectoryLoader(
        str(RAW_DATA_DIR),
        glob=glob_pattern,
        loader_cls=get_loader(extension),
        loader_kwargs=loader_kwargs,
        show_progress=True,
        silent_errors=True,  # log + skip bad files instead of crashing the run
        use_multithreading=True,
        recursive=True,      # ensure ** glob patterns recurse into subdirectories
    )


def tag_jurisdiction(documents):
    """Injects a 'jurisdiction' metadata field based on the immediate
    parent folder name, e.g. data/raw/legal_docs/delhi/act.pdf -> 'delhi'.
    This is required for jurisdiction-filtered retrieval later in the RAG
    pipeline, and was missing entirely in the original loader."""
    for doc in documents:
        source_path = Path(doc.metadata.get("source", ""))
        jurisdiction = source_path.parent.name.lower() if source_path else "unknown"
        doc.metadata["jurisdiction"] = jurisdiction
    return documents


def load_all_documents():
    all_docs = []

    for extension, pattern in [
        ("pdf", "**/*.pdf"),
        ("txt", "**/*.txt"),
        ("docx", "**/*.docx"),
    ]:
        loader = build_loader(extension, pattern)
        docs = list(loader.lazy_load())
        docs = tag_jurisdiction(docs)
        print(f"Loaded {len(docs)} '{extension}' document(s).")
        all_docs.extend(docs)

    return all_docs


if __name__ == "__main__":
    print("Loading all documents from data/raw/...")
    print(f"RAW_DATA_DIR: {RAW_DATA_DIR}")
    all_docs = load_all_documents()