"""
RentGuard — Feature Engineering
Transforms labeled clause rows into model-ready RAW features:
  - text embeddings (via services.common.embedder -- same model used in RAG)
  - regex-extracted numeric signals (deposit months, notice days, escalation %)
  - boolean "red flag" keyword features (self-help eviction, non-refundable, etc.)

Deliberately does NOT one-hot encode categoricals (clause_type,
legal_basis, monthly_rent_bracket) or impute missing numeric values
here. Those steps require fitting on the TRAIN split only (to avoid
leakage into val/test) and must be saved as artifacts for consistent
reuse at inference time -- that happens in data_prep.py via a proper
sklearn ColumnTransformer, not here.
"""
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import yaml

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from services.common.embedder import get_embeddings
except ModuleNotFoundError:
    import importlib.util

    embedder_path = ROOT_DIR / "services" / "common" / "embedder.py"
    spec = importlib.util.spec_from_file_location("embedder_dyn", embedder_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load embedder from {embedder_path}")
    embedder_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(embedder_mod)
    get_embeddings = embedder_mod.get_embeddings

PARAMS_PATH = ROOT_DIR / "params.yml"
if not PARAMS_PATH.exists():
    PARAMS_PATH = ROOT_DIR / "params.yaml"

if PARAMS_PATH.exists():
    with open(PARAMS_PATH, "r") as f:
        params = yaml.safe_load(f)
else:
    # fallback to default params if file missing
    params = {"feature": {"batch_size": 32}}  # default batch size

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------- Regex-based numeric feature extraction ----------

_MONTHS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*months?\b", re.IGNORECASE)
_DAYS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*days?\b", re.IGNORECASE)
_PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _first_match(pattern: re.Pattern, text: str) -> float:
    """Return the first numeric match as a float, or NaN if none found."""
    match = pattern.search(text)
    return float(match.group(1)) if match else np.nan


def extract_numeric_features(text: str, clause_type: str) -> Dict[str, float]:
    """Extracts clause-type-specific numeric signals.

    Returns NaN for any signal not relevant to this clause_type or not
    found in the text -- NaN is intentional; imputation is a train-time
    decision (data_prep.py), not this function's job.
    """
    features = {
        "deposit_months": np.nan,
        "notice_days": np.nan,
        "lockin_months": np.nan,
        "escalation_pct": np.nan,
    }

    if clause_type == "security_deposit":
        features["deposit_months"] = _first_match(_MONTHS_PATTERN, text)

    elif clause_type in ("notice_lockin", "termination_eviction"):
        features["notice_days"] = _first_match(_DAYS_PATTERN, text)
        features["lockin_months"] = _first_match(_MONTHS_PATTERN, text)

    elif clause_type == "rent_escalation":
        features["escalation_pct"] = _first_match(_PERCENT_PATTERN, text)
        features["lockin_months"] = _first_match(_MONTHS_PATTERN, text)  # revision frequency

    return features


# ---------- Red-flag keyword features (checked across ALL clause types) ----------
# These are general_law-style signals (illegal/unfair regardless of
# clause_type or rent bracket), so they're checked unconditionally
# rather than gated by clause_type like the numeric features above.

RED_FLAG_PATTERNS = {
    "flag_non_refundable": r"non-?refundable",
    "flag_sole_discretion": r"sole discretion",
    "flag_without_notice": r"without\s+(?:any\s+)?notice",
    "flag_self_help_lockout": r"change\s+locks|disconnect|forcibly|repossess|remove.*belongings",
    "flag_waiver_of_rights": r"\bwaive[sd]?\b|no recourse|without recourse",
    "flag_any_time_clause": r"at any time",
    "flag_regardless_of_reason": r"regardless of reason|irrespective of reason|for any reason whatsoever",
}


def extract_red_flags(text: str) -> Dict[str, bool]:
    """Return a dictionary of boolean flags based on keyword patterns."""
    return {
        flag_name: bool(re.search(pattern, text, re.IGNORECASE))
        for flag_name, pattern in RED_FLAG_PATTERNS.items()
    }


# ---------- Embeddings ----------

def embed_clauses(clause_texts: List[str], batch_size: int = None) -> np.ndarray:
    """Embeds clause texts using the same embedding model used elsewhere.

    Batched to avoid rate‑limiting or timeouts on large requests.
    """
    if batch_size is None:
        batch_size = params.get("feature", {}).get("batch_size", 32)

    if not clause_texts:
        logger.warning("Empty clause_texts list; returning empty array.")
        return np.array([])

    embeddings = get_embeddings()
    all_vectors = []

    for start in range(0, len(clause_texts), batch_size):
        batch = clause_texts[start : start + batch_size]
        vectors = embeddings.embed_documents(batch)
        all_vectors.extend(vectors)
        logger.debug("Embedded clauses %d-%d of %d", start, start + len(batch), len(clause_texts))

    return np.array(all_vectors)


# ---------- Main entry point ----------

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Takes the labeled clauses DataFrame and returns an enriched copy with raw features.

    Added columns:
      - numeric: deposit_months, notice_days, lockin_months, escalation_pct
      - boolean: flag_* red-flag keyword columns (converted to 0/1 integers)
      - embedding: one vector per row (as a list), stored in a single column

    Categorical encoding and numeric imputation are intentionally NOT done here.
    """
    required_cols = {"clause_text", "clause_type"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Input DataFrame is missing required columns: {missing}")

    df = df.copy()

    # Numeric features (clause-type-aware)
    numeric_records = [
        extract_numeric_features(text, ctype)
        for text, ctype in zip(df["clause_text"], df["clause_type"])
    ]
    numeric_df = pd.DataFrame(numeric_records, index=df.index)
    numeric_df = numeric_df.astype("float64")

    # Red-flag boolean features (clause-type-agnostic)
    flag_records = [extract_red_flags(text) for text in df["clause_text"]]
    flags_df = pd.DataFrame(flag_records, index=df.index)

    # Convert boolean flags to integer (0/1) to be compatible with numeric imputation
    flags_df = flags_df.astype(int)

    # Embeddings
    logger.info("Embedding %d clauses...", len(df))
    embedding_vectors = embed_clauses(df["clause_text"].tolist())
    df["embedding"] = list(embedding_vectors)

    result = pd.concat([df, numeric_df, flags_df], axis=1)

    logger.info(
        "Feature engineering complete: %d rows, %d numeric + %d flag features added.",
        len(result),
        len(numeric_df.columns),
        len(flags_df.columns),
    )
    return result


if __name__ == "__main__":
    # Manual test only. Run as:
    # python -m services.classifier_service.training.feature_engineering
    sample = pd.DataFrame(
        {
            "clause_text": [
                "Tenant shall pay a security deposit of 6 months' rent, refundable within 45 days of vacating.",
                "Landlord may change locks if rent is delayed by more than 3 days.",
            ],
            "clause_type": ["security_deposit", "notice_lockin"],
        }
    )

    result = build_features(sample)
    print(result[["clause_text", "deposit_months", "notice_days", "flag_self_help_lockout"]])