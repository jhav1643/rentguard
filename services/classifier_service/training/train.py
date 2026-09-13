import importlib.util
import re
import sys
from pathlib import Path
import logging 
import joblib
import matplotlib
matplotlib.use("Agg")  # headless -- just saving PNGs, no display needed
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import yaml
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.utils.class_weight import compute_sample_weight

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

PARAMS_PATH = ROOT_DIR / "params.yml"
if not PARAMS_PATH.exists():
    PARAMS_PATH = ROOT_DIR / "params.yaml"

with open(PARAMS_PATH, "r") as f:
    params = yaml.safe_load(f)

mlflow_util_path = ROOT_DIR / "services" / "classifier_service" / "mlflow" / "mlflow_util.py"
spec = importlib.util.spec_from_file_location("mlflow_util_mod", mlflow_util_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load MLflow util from {mlflow_util_path}")

mlflow_util_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mlflow_util_mod)
configure_mlflow = mlflow_util_mod.configure_mlflow

# Use absolute paths to avoid issues when script is run from different directories
FEATURES_DIR = ROOT_DIR / "data" / "features"
ARTIFACTS_DIR = ROOT_DIR / "services" / "classifier_service" / "training" / "artifacts"

RANDOM_STATE = params["train"]["random_state"]
REGISTERED_MODEL_NAME = params["mlflow"]["registered_model_name"]


def load_split(name: str):
    data = np.load(FEATURES_DIR / f"{name}.npz", allow_pickle=True)
    return data["X"], data["y"]


def load_label_encoder():
    return joblib.load(FEATURES_DIR / "label_encoder.joblib")


def sanitize_metric_key(label: str) -> str:
    """
    MLflow metric keys can only contain alphanumeric characters, underscores,
    dashes, periods, and spaces (spaces are technically allowed but can cause
    issues). We replace all non-alphanumeric characters (except underscore)
    with underscores.
    """
    return re.sub(r"[^a-zA-Z0-9_]", "_", label)


def plot_confusion_matrix(y_true, y_pred, class_names, save_path: Path):
    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names)
    fig, ax = plt.subplots(figsize=(6, 5))
    disp.plot(ax=ax, cmap="Blues", colorbar=False)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)


def train_and_log(model, model_name: str, params: dict, X_train, y_train, X_val, y_val, class_names):
    """
    Train a model with balanced sample weights, evaluate on validation set,
    log metrics and artifacts to MLflow, and return the run ID, model URI, and
    performance. The model is logged but NOT registered here; registration is
    done only for the best candidate later.
    """
    sample_weight = compute_sample_weight("balanced", y_train)

    with mlflow.start_run(run_name=model_name):
        mlflow.log_param("model_type", model_name)
        for k, v in params.items():
            mlflow.log_param(k, v)

        model.fit(X_train, y_train, sample_weight=sample_weight)
        y_pred = model.predict(X_val)

        macro_f1 = f1_score(y_val, y_pred, average="macro")
        accuracy = (y_pred == y_val).mean()

        mlflow.log_metric("train_macro_f1", macro_f1)
        mlflow.log_metric("train_accuracy", accuracy)

        report = classification_report(
            y_val, y_pred, target_names=class_names, output_dict=True, zero_division=0
        )
        for label in class_names:
            metrics = report[label]
            key = sanitize_metric_key(label)
            mlflow.log_metric(f"val_f1_{key}", metrics["f1-score"])
            mlflow.log_metric(f"val_precision_{key}", metrics["precision"])
            mlflow.log_metric(f"val_recall_{key}", metrics["recall"])

        print(f"\n=== {model_name} ===")
        print(f"Val macro-F1: {macro_f1:.4f} | Val accuracy: {accuracy:.4f}")
        print(classification_report(y_val, y_pred, target_names=class_names, zero_division=0))

        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        cm_path = ARTIFACTS_DIR / f"{model_name}_confusion_matrix.png"
        plot_confusion_matrix(y_val, y_pred, class_names, cm_path)
        mlflow.log_artifact(str(cm_path))

        # FIX 1: log the model with name= but WITHOUT registered_model_name=.
        # Capture the returned ModelInfo so we can register explicitly later
        # using its canonical model_uri. This avoids MLflow 3's fallback to
        # a models:/m-<id> source that breaks evaluate.py's loading logic.
        model_info = mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            input_example=X_train[:5],
        )

        return {
            "model_name": model_name,
            "macro_f1": macro_f1,
            "accuracy": accuracy,
            "run_id": mlflow.active_run().info.run_id,
            "model_uri": model_info.model_uri,   # FIX 1: return the canonical URI
        }


def run_training():
    configure_mlflow()
    logging.getLogger("alembic").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    X_train, y_train = load_split("train")
    X_val, y_val = load_split("val")
    label_encoder = load_label_encoder()
    class_names = list(label_encoder.classes_)

    print(f"Loaded train: {X_train.shape}, val: {X_val.shape}")
    print(f"Classes: {class_names}")

    results = []

    # Candidate 1: Logistic Regression baseline
    logreg = LogisticRegression(
        max_iter=params["train"]["logistic"]["max_itr"],
        random_state=RANDOM_STATE,
    )
    results.append(
        train_and_log(
            logreg,
            "logistic_regression_baseline",
            {"max_iter": params["train"]["logistic"]["max_itr"]},
            X_train, y_train, X_val, y_val, class_names,
        )
    )

    # Candidate 2: Gradient Boosting
    gb = GradientBoostingClassifier(
        n_estimators=params["train"]["gradient_booster"]["n_estimators"],
        max_depth=params["train"]["gradient_booster"]["max_depth"],
        learning_rate=params["train"]["gradient_booster"]["learning_rate"],
        random_state=RANDOM_STATE,
    )
    results.append(
        train_and_log(
            gb,
            "gradient_boosting_candidate",
            {
                "n_estimators": params["train"]["gradient_booster"]["n_estimators"],
                "max_depth": params["train"]["gradient_booster"]["max_depth"],
                "learning_rate": params["train"]["gradient_booster"]["learning_rate"],
            },
            X_train, y_train, X_val, y_val, class_names,
        )
    )

    print("\n=== Comparison (validation set) ===")
    for r in results:
        print(
            f"{r['model_name']}: val_macro_f1={r['macro_f1']:.4f}, "
            f"val_accuracy={r['accuracy']:.4f}, run_id={r['run_id']}"
        )

    best = max(results, key=lambda r: r["macro_f1"])
    print(f"\nBest candidate on val set: {best['model_name']} (macro_f1={best['macro_f1']:.4f})")

    # FIX 2: register using the canonical model_uri returned by log_model(),
    # NOT a reconstructed runs:/<run_id>/model path. In MLflow 3 the artifact
    # no longer lives at that run-relative path, so the reconstructed URI
    # would produce an empty-source registration.
    mlflow.register_model(best["model_uri"], REGISTERED_MODEL_NAME)
    print(
        f"Registered best model '{REGISTERED_MODEL_NAME}' "
        f"from run {best['run_id']} (uri={best['model_uri']})"
    )

    print(
        "NOTE: this is a val-set comparison for candidate selection only. "
        "The final Production promotion decision happens in evaluate.py, "
        "based on the held-out TEST set."
    )

    return results


if __name__ == "__main__":
    # Run as: python -m services.classifier_service.training.train
    run_training()