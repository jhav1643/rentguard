import importlib.util
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

feature_path = Path(__file__).resolve().with_name("feature_engineering.py")
spec = importlib.util.spec_from_file_location("feature_engineering_mod", feature_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load feature engineering module from {feature_path}")

feature_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feature_mod)

RED_FLAG_PATTERN = getattr(feature_mod, "RED_FLAG_PATTERNS", getattr(feature_mod, "RED_FLAG_PATTERN", {}))
build_features = feature_mod.build_features

PARAMS_PATH = ROOT_DIR / "params.yml"
if not PARAMS_PATH.exists():
    PARAMS_PATH = ROOT_DIR / "params.yaml"

with open(PARAMS_PATH, "r") as f:
    params = yaml.safe_load(f)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths (avoid chaining .parent too much; use resolve().parents[2])
LABELED_CSV_PATH = ROOT_DIR / "data" / "labeled" / "clauses_expanded_CLEANED.csv"
FEATURES_PATH = ROOT_DIR / "data" / "features"

# Column definitions
NUMERIC_COLS = ["deposit_months", "notice_days", "lockin_months", "escalation_pct"]
FLAG_COLS = list(RED_FLAG_PATTERN.keys())
CATEGORICAL_COLS = ["clause_type", "legal_basis", "monthly_rent_bracket"]
TARGET_COL = "risk_label"

# Split parameters
TEST_SIZE = params["data"]["test_size"]
VAL_SIZE = params["data"]["variable_size"]
RANDOM_STATE = params["data"]["random_state"]
MIN_EXAMPLES_WARNING_THRESHOLD = params["data"]["threshold"]


def load_labeled_data() -> pd.DataFrame:
    """Load labeled data and optionally exclude rows flagged for review."""
    if not LABELED_CSV_PATH.exists():
        raise FileNotFoundError(f"Labeled data CSV file not found at {LABELED_CSV_PATH}")

    df = pd.read_csv(LABELED_CSV_PATH)
    df["flagged_for_review"] = df["flagged_for_review"].astype(bool)
    # Then filter
    df = df[~df["flagged_for_review"]]

    # Fix typo: 'clumns' -> 'columns'
    if "flagged_for_review" in df.columns:
        flagged_count = df["flagged_for_review"].sum()
        if flagged_count:
            logger.info(
                "Excluding %d row(s) flagged for legal review "
                "(legal_basis/monthly_rent_bracket mismatch) from training.",
                flagged_count,
            )
            df = df[~df["flagged_for_review"]]

    return df


def stratified_three_way_split(df: pd.DataFrame):
    """
    Split data into train, validation, and test sets.
    Stratification is attempted on clause_type + risk_label; if any combination
    has fewer than 3 examples, fall back to stratifying on risk_label only.
    """
    # Create a combined stratification key
    combined_key = df["clause_type"] + "_" + df[TARGET_COL]
    combo_counts = combined_key.value_counts()
    min_combo_count = combo_counts.min()

    if min_combo_count >= 3:
        stratify_key = combined_key
        logger.info("Stratifying by clause type and risk label.")
    else:
        stratify_key = df[TARGET_COL]
        logger.info(
            "Some clause_type+risk_label combinations have only %d example(s) -- "
            "falling back to stratifying on risk_label only.",
            min_combo_count,
        )

    # First split: train vs (val + test)
    train_df, temp_df = train_test_split(
        df,
        test_size=VAL_SIZE + TEST_SIZE,
        stratify=stratify_key,
        random_state=RANDOM_STATE,
    )

    # For the second split, we need the stratification key for temp_df
    if isinstance(stratify_key, pd.Series):
        # Recompute the key for temp_df based on the same logic
        temp_stratify_key = temp_df["clause_type"] + "_" + temp_df[TARGET_COL]
        # If any combo in temp_df has <2 examples, fall back to risk_label
        if temp_stratify_key.value_counts().min() < 2:
            temp_stratify_key = temp_df[TARGET_COL]
    else:
        # stratify_key was already the target column
        temp_stratify_key = temp_df[TARGET_COL]

    # Second split: val vs test (relative sizes)
    relative_test_size = TEST_SIZE / (VAL_SIZE + TEST_SIZE)
    val_df, test_df = train_test_split(
        temp_df,
        test_size=relative_test_size,
        stratify=temp_stratify_key,
        random_state=RANDOM_STATE,
    )

    return train_df, val_df, test_df


def check_class_balance(df: pd.DataFrame, split_name: str):
    """Log class distribution and warn about very small classes."""
    counts = df[TARGET_COL].value_counts()
    logger.info("%s set -- %d rows, class distribution:\n%s", split_name, len(df), counts)

    thin_classes = counts[counts < MIN_EXAMPLES_WARNING_THRESHOLD]
    if not thin_classes.empty:
        logger.warning(
            "The following class(es) in the %s set have fewer than %d examples:\n%s",
            split_name,
            MIN_EXAMPLES_WARNING_THRESHOLD,
            thin_classes,
        )


def build_preprocessor() -> ColumnTransformer:
    """Build a ColumnTransformer for numeric, categorical, and flag columns."""
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    # For flag columns, we also impute missing values (e.g., with 0) to avoid NaN.
    flag_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERIC_COLS),
            ("cat", categorical_transformer, CATEGORICAL_COLS),
            ("flag", flag_transformer, FLAG_COLS),
        ]
    )

    return preprocessor


def assemble_feature_matrix(
    df: pd.DataFrame, preprocessor: ColumnTransformer, fit: bool
) -> np.ndarray:
    """
    Transform the tabular features with the preprocessor and concatenate
    with the embedding vectors.
    """
    df = df.copy()

    # Boolean red-flag columns are created by feature_engineering.py as bools, but
    # sklearn's SimpleImputer does not accept boolean dtypes. Cast them to integer
    # so missing values can be imputed with 0 without breaking the fit/transform.
    for col in FLAG_COLS:
        if col in df.columns and pd.api.types.is_bool_dtype(df[col]):
            df[col] = df[col].astype(np.int8)

    # Ensure embedding column is present and all vectors have the same shape
    if "embedding" not in df.columns:
        raise KeyError("DataFrame must contain an 'embedding' column.")
    if df["embedding"].isnull().any():
        raise ValueError("Embedding column contains null values.")

    # Transform tabular features
    if fit:
        transformed = preprocessor.fit_transform(df)
    else:
        transformed = preprocessor.transform(df)

    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()

    # Stack embeddings into a 2D array
    embeddings = np.stack(df["embedding"].to_numpy())
    logger.debug("Embedding shape: %s", embeddings.shape)

    # Concatenate along columns
    return np.hstack((transformed, embeddings))


def run_data_prep():
    FEATURES_PATH.mkdir(parents=True, exist_ok=True)

    logger.info("Step 1: Loading labeled data...")
    df = load_labeled_data()

    logger.info("Step 2: Building features (embedding + numeric + flags)...")
    df = build_features(df)
    df.to_parquet(FEATURES_PATH / "clause_features.parquet", index=False)
    logger.info("Features saved to: %s", FEATURES_PATH / "clause_features.parquet")

    logger.info("Step 3: Splitting into train, val, test sets...")
    train_df, val_df, test_df = stratified_three_way_split(df)

    check_class_balance(train_df, "train")
    check_class_balance(val_df, "val")
    check_class_balance(test_df, "test")

    logger.info("Step 4: Preprocessing data on TRAIN split...")
    preprocessor = build_preprocessor()
    label_encoder = LabelEncoder()

    X_train = assemble_feature_matrix(train_df, preprocessor, fit=True)
    y_train = label_encoder.fit_transform(train_df[TARGET_COL])

    X_val = assemble_feature_matrix(val_df, preprocessor, fit=False)
    y_val = label_encoder.transform(val_df[TARGET_COL])

    X_test = assemble_feature_matrix(test_df, preprocessor, fit=False)
    y_test = label_encoder.transform(test_df[TARGET_COL])

    logger.info(
        "Feature matrix shapes -- train: %s, val: %s, test: %s",
        X_train.shape,
        X_val.shape,
        X_test.shape,
    )
    logger.info("Label classes: %s", list(label_encoder.classes_))

    logger.info("Step 5: Saving artifacts...")
    np.savez(
        FEATURES_PATH / "train.npz",
        X=X_train,
        y=y_train,
        clause_id=train_df["clause_id"].values,
    )
    np.savez(
        FEATURES_PATH / "val.npz",
        X=X_val,
        y=y_val,
        clause_id=val_df["clause_id"].values,
    )
    np.savez(
        FEATURES_PATH / "test.npz",
        X=X_test,
        y=y_test,
        clause_id=test_df["clause_id"].values,
    )

    joblib.dump(preprocessor, FEATURES_PATH / "preprocessor.joblib")
    joblib.dump(label_encoder, FEATURES_PATH / "label_encoder.joblib")

    logger.info("Data prep complete. Artifacts saved to %s", FEATURES_PATH)
    return X_train, y_train, X_val, y_val, X_test, y_test


if __name__ == "__main__":
    # Run as: python -m services.classifier_service.training.data_prep
    run_data_prep()