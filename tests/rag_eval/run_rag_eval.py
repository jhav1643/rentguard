"""
RentGuard — RAG Evaluation
Runs a curated set of real questions through the ACTUAL retrieval +
generation pipeline, then scores the results with RAGAS.

Compatible with:
    ragas==0.1.16
    datasets==2.21.0
    pandas==2.2.2

Run as:
    python -m tests.rag_eval.run_rag_eval
"""

import json
import logging
import traceback
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import Dataset

# Silence RAGAS deprecation noise BEFORE importing ragas submodules.
# These APIs still work in 0.1.16; we'll migrate when we upgrade RAGAS.
warnings.filterwarnings("ignore", category=DeprecationWarning, module="ragas")

from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.agent_orchestrator.llm import get_llm
from services.common.embedder import get_embeddings
from services.ingestion.retrieval import retrieve

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

EVAL_DATASET_PATH = Path(__file__).parent / "eval_dataset.csv"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_CSV = RESULTS_DIR / "rag_eval_results.csv"
SUMMARY_JSON = RESULTS_DIR / "rag_eval_summary.json"

RETRIEVAL_K = 3

METRIC_NAMES = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]

GENERATION_PROMPT_TEMPLATE = """Answer the question using ONLY the context below. \
If the context doesn't contain the answer, say so explicitly rather than guessing.

Context:
{context}

Question: {question}

Answer:"""

REQUIRED_DATASET_COLUMNS = {"question", "jurisdiction", "ground_truth"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Embedding sanity check (catches the InferenceClient.post bug early)
# --------------------------------------------------------------------------- #

def _validate_embeddings(embeddings: Any) -> None:
    """Verify the embeddings object actually works before the full run.

    The HuggingFaceEndpointEmbeddings + huggingface_hub>=0.28 combination
    raises AttributeError only when embed_query() is called, deep inside
    retrieval. This probe surfaces the problem immediately with a clear
    message instead of failing 10 times in a row.
    """
    try:
        vec = embeddings.embed_query("sanity check")
    except AttributeError as exc:
        if "post" in str(exc):
            raise RuntimeError(
                "Embeddings backend is broken: huggingface_hub>=0.28 removed "
                "InferenceClient.post(), which langchain-huggingface's "
                "HuggingFaceEndpointEmbeddings still calls. Fix one of:\n"
                "  A) pin 'huggingface-hub<0.28' in requirements.txt, OR\n"
                "  B) switch get_embeddings() to local HuggingFaceEmbeddings, OR\n"
                "  C) switch to an OpenAI-compatible embeddings provider."
            ) from exc
        raise

    if not vec or not isinstance(vec, list):
        raise RuntimeError(
            f"Embeddings returned an unexpected type: {type(vec).__name__}. "
            "Expected a non-empty list of floats."
        )
    logger.info("Embeddings sanity check passed (dim=%d).", len(vec))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _extract_answer_text(response: Any) -> str:
    """Normalise whatever the LLM returns into a plain string."""
    if response is None:
        return ""
    if hasattr(response, "content"):
        return str(response.content)
    return str(response)


def _extract_contexts(retrieved: Any) -> list[str]:
    """Normalise the retriever output into a list of plain-text chunks."""
    if not retrieved:
        return []

    contexts: list[str] = []
    for i, chunk in enumerate(retrieved):
        if isinstance(chunk, dict):
            if "text" in chunk:
                contexts.append(str(chunk["text"]))
            elif "content" in chunk:
                contexts.append(str(chunk["content"]))
            else:
                raise ValueError(
                    f"Retriever chunk {i} is a dict but has no 'text'/'content' key. "
                    f"Keys found: {list(chunk.keys())}"
                )
        elif isinstance(chunk, str):
            contexts.append(chunk)
        else:
            raise ValueError(
                f"Unexpected retriever chunk type at index {i}: {type(chunk).__name__}"
            )
    return contexts


# --------------------------------------------------------------------------- #
# Dataset loading & validation
# --------------------------------------------------------------------------- #

def load_eval_dataset() -> pd.DataFrame:
    if not EVAL_DATASET_PATH.exists():
        raise FileNotFoundError(f"{EVAL_DATASET_PATH} not found.")

    df = pd.read_csv(EVAL_DATASET_PATH)

    missing = REQUIRED_DATASET_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"eval_dataset.csv is missing required columns: {sorted(missing)}. "
            f"Found columns: {list(df.columns)}"
        )

    before = len(df)
    df = df.dropna(subset=["question", "ground_truth"])
    df = df[df["question"].astype(str).str.strip() != ""]
    df = df[df["ground_truth"].astype(str).str.strip() != ""]
    if len(df) < before:
        logger.warning("Dropped %d incomplete rows from eval dataset.", before - len(df))

    if df.empty:
        raise ValueError("Evaluation dataset is empty after cleaning.")

    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Pipeline execution (uses the REAL production retrieve + generation)
# --------------------------------------------------------------------------- #

def run_rag_pipeline_for_question(
    question: str,
    jurisdiction: str,
    llm: Any,
) -> tuple[str, list[str]]:
    """Runs the REAL retrieve() + generation, mirroring the agent's answer path."""
    retrieved = retrieve(query=question, jurisdiction=jurisdiction, k=RETRIEVAL_K)
    contexts = _extract_contexts(retrieved)

    context_text = "\n\n".join(contexts) if contexts else "No relevant context found."
    prompt = GENERATION_PROMPT_TEMPLATE.format(context=context_text, question=question)

    response = llm.invoke(prompt)
    answer = _extract_answer_text(response)

    return answer, contexts


def build_ragas_dataset(eval_df: pd.DataFrame, llm: Any) -> Dataset:
    questions: list[str] = []
    answers: list[str] = []
    contexts_list: list[list[str]] = []
    ground_truths: list[str] = []

    total = len(eval_df)
    for idx, row in eval_df.iterrows():
        q_preview = str(row["question"])[:60]
        logger.info("Running (%d/%d): %s...", idx + 1, total, q_preview)

        try:
            answer, contexts = run_rag_pipeline_for_question(
                question=row["question"],
                jurisdiction=row.get("jurisdiction", ""),
                llm=llm,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Pipeline failed for question %d: %s", idx + 1, exc)
            logger.debug(traceback.format_exc())
            answer, contexts = "", []

        logger.info("    retrieved %d context chunk(s)", len(contexts))

        questions.append(row["question"])
        answers.append(answer)
        contexts_list.append(contexts)
        ground_truths.append(row["ground_truth"])

    return Dataset.from_dict(
        {
            "question": questions,
            "answer": answers,
            "contexts": contexts_list,
            "ground_truth": ground_truths,
        }
    )


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #

def _results_to_dataframe(results: Any) -> pd.DataFrame:
    """Handle both old (`.to_pandas()`) and new RAGAS result APIs."""
    if hasattr(results, "to_pandas"):
        return results.to_pandas()
    return pd.DataFrame(results)


def run_evaluation() -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    eval_df = load_eval_dataset()
    logger.info("Loaded %d evaluation questions.", len(eval_df))

    llm = get_llm()
    embeddings = get_embeddings()

    # Fail fast if the embeddings backend is broken.
    _validate_embeddings(embeddings)

    ragas_dataset = build_ragas_dataset(eval_df, llm)

    logger.info("Scoring with RAGAS (this calls the LLM/embeddings again per metric)...")
    from ragas.run_config import RunConfig

    results = evaluate(
        dataset=ragas_dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=LangchainLLMWrapper(llm),
        embeddings=LangchainEmbeddingsWrapper(embeddings),
        run_config=RunConfig(
            max_workers=1,        # sequential — one LLM call at a time
            timeout=180,          # allow slow responses
            max_retries=5,        # retry failed calls
            max_wait=120,         # cap backoff wait
        ),
        raise_exceptions=True,
    )

    results_df = _results_to_dataframe(results)
    results_df.to_csv(RESULTS_CSV, index=False)

    summary: dict[str, Any] = {
        name: float(results_df[name].mean())
        for name in METRIC_NAMES
        if name in results_df.columns
    }
    summary["num_questions"] = len(eval_df)

    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info("=== RAG Evaluation Summary ===")
    for metric, score in summary.items():
        logger.info("  %s: %s", metric, score)
    logger.info("Full per-question results saved to %s", RESULTS_CSV)
    logger.info("Summary saved to %s", SUMMARY_JSON)

    return summary


if __name__ == "__main__":
    run_evaluation()