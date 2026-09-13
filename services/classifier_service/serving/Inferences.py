 
import re
from pathlib import Path
 
import joblib
import mlflow
import numpy as np
import pandas as pd
 
from services.classifier_service.mlflow.mlflow_util import configure_mlflow
from services.classifier_service.training.feature_engineering import build_features
 
FEATURES_DIR = Path("data/features")
REGISTERED_MODEL_NAME = "rentguard-risk-classifier"
CHAMPION_ALIAS = "champion"
 
# Heuristic keyword -> clause_type guesser. NOT a trained model --
# see module docstring limitation #1. Ordered roughly by specificity;
# first match wins.
CLAUSE_TYPE_KEYWORDS = {
    "security_deposit": [r"security deposit", r"\bdeposit\b"],
    "notice_lockin": [r"notice period", r"lock-?in"],
    "maintenance": [r"maintenance", r"repair"],
    "rent_escalation": [r"rent.*increase", r"escalat"],
    "termination_eviction": [r"terminat", r"evict"],
    "rent_payment": [r"due date", r"payment of rent"],
    "utilities_outgoings": [r"electricity", r"water bill", r"utilit"],
    "dispute_resolution": [r"dispute", r"arbitrat"],
    "possession_handover": [r"handover", r"meter reading"],
    "possession_condition": [r"condition of the (premises|property)", r"inventory"],
    "landlord_entry_privacy": [r"enter the premises", r"inspection"],
    "subletting": [r"sublet", r"sub-let"],
    "documentation": [r"signed copy", r"written agreement"],
}
 
 
def guess_clause_type(clause_text: str) -> str:
    """Keyword-based heuristic -- see module docstring limitation #1."""
    text_lower = clause_text.lower()
    for clause_type, patterns in CLAUSE_TYPE_KEYWORDS.items():
        if any(re.search(p, text_lower) for p in patterns):
            return clause_type
    return "documentation"  # weakest-signal fallback, not a confident guess
 
 
def derive_legal_basis(monthly_rent_bracket: str) -> str:
    """Simplified rule -- see module docstring limitation #3."""
    return "statutory" if monthly_rent_bracket == "le_3500" else "market_convention"
 
 
_model_cache = None
_preprocessor_cache = None
_label_encoder_cache = None
 
 
def load_champion_model():
    global _model_cache
    if _model_cache is None:
        configure_mlflow()
        model_uri = f"models:/{REGISTERED_MODEL_NAME}@{CHAMPION_ALIAS}"
        _model_cache = mlflow.sklearn.load_model(model_uri)
    return _model_cache
 
 
def load_preprocessing_artifacts():
    global _preprocessor_cache, _label_encoder_cache
    if _preprocessor_cache is None:
        _preprocessor_cache = joblib.load(FEATURES_DIR / "preprocessor.joblib")
        _label_encoder_cache = joblib.load(FEATURES_DIR / "label_encoder.joblib")
    return _preprocessor_cache, _label_encoder_cache
 
 
def predict_risk(clause_text: str, monthly_rent_bracket: str) -> dict:
    """Predicts risk label for a single clause.
 
    Args:
        clause_text: the clause text (e.g. from clause_splitter.split_lease())
        monthly_rent_bracket: "le_3500" or "above_3500" -- MUST be
            supplied by the caller (asked of the user), not guessed.
 
    Returns:
        {
            "risk_label": str,
            "confidence": float | None,
            "clause_type_guess": str,   # heuristic -- see limitation #1
            "legal_basis_used": str,     # simplified rule -- see limitation #3
        }
    """
    if monthly_rent_bracket not in ("le_3500", "above_3500"):
        raise ValueError(
            "monthly_rent_bracket must be 'le_3500' or 'above_3500' -- "
            "this cannot be inferred from clause text and must be "
            "supplied by the caller (ask the user)."
        )
 
    clause_type = guess_clause_type(clause_text)
    legal_basis = derive_legal_basis(monthly_rent_bracket)
 
    row = pd.DataFrame(
        [
            {
                "clause_text": clause_text,
                "clause_type": clause_type,
                "legal_basis": legal_basis,
                "monthly_rent_bracket": monthly_rent_bracket,
            }
        ]
    )
    row = build_features(row)
 
    preprocessor, label_encoder = load_preprocessing_artifacts()
    print("DEBUG dtypes:\n", row[["deposit_months", "notice_days", "lockin_months", "escalation_pct"]].dtypes)
    structured = preprocessor.transform(row)
    if hasattr(structured, "toarray"):
        structured = structured.toarray()
    embedding_matrix = np.stack(row["embedding"].values)
    X = np.hstack([structured, embedding_matrix])
 
    model = load_champion_model()
    prediction = model.predict(X)[0]
    probabilities = model.predict_proba(X)[0] if hasattr(model, "predict_proba") else None
 
    risk_label = label_encoder.inverse_transform([prediction])[0]
    confidence = float(np.max(probabilities)) if probabilities is not None else None
 
    return {
        "risk_label": risk_label,
        "confidence": confidence,
        "clause_type_guess": clause_type,
        "legal_basis_used": legal_basis,
    }
 
 
if __name__ == "__main__":
    # Manual test only. Run as:
    # python -m services.classifier_service.serving.inference
    test_clause = (
        "Tenant shall pay a security deposit of 11 months' rent "
        "at the time of signing the agreement."
    )
    result = predict_risk(test_clause, monthly_rent_bracket="above_3500")
    print(result)
 