import importlib.util
import json
import re
import sys
from pathlib import Path
import logging

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import yaml
from mlflow import MlflowClient
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    classification_report,
    confusion_matrix,
    f1_score,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

PARAMS_PATH = ROOT_DIR / "params.yml"
if not PARAMS_PATH.exists():
    PARAMS_PATH = ROOT_DIR / "params.yaml"

with open(PARAMS_PATH, "r") as f:
    params = yaml.safe_load(f)

mlflow_util_path = Path(__file__).resolve().parents[1] / "mlflow" / "mlflow_util.py"
spec = importlib.util.spec_from_file_location("mlflow_util", mlflow_util_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load MLflow helper from {mlflow_util_path}")

feature_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feature_mod)

EXPERIMENT_NAME = feature_mod.EXPERIMENT_NAME
configure_mlflow = feature_mod.configure_mlflow

FEATURES_DIR = ROOT_DIR / "data" / "features"
ARTIFACTS_DIR = ROOT_DIR / "services" / "classifier_service" / "training" / "artifacts"
METRICS_DIR = ROOT_DIR / "metrics"

REGISTERED_MODEL_NAME = params["mlflow"]["registered_model_name"]
CHAMPION_ALIAS = params["mlflow"]["champion_alias"]


def load_test_split():
    data = np.load(FEATURES_DIR / "test.npz", allow_pickle=True)
    return data["X"], data["y"]


def load_label_encoder():
    return joblib.load(FEATURES_DIR / "label_encoder.joblib")


def sanitize_metric_key(label: str) -> str:
    """Replace any non-alphanumeric character (except underscore) with '_'."""
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


def get_all_model_versions(client: MlflowClient):
    """Return all registered versions sorted by version number ascending."""
    versions = client.search_model_versions(f"name='{REGISTERED_MODEL_NAME}'")
    # MLflow version strings are numeric; convert to int for proper sorting
    return sorted(versions, key=lambda v: int(v.version))


def evaluate_version(version, X_test, y_test, class_names) -> dict:
    """
    Load a registered model version from the registry and evaluate it on the
    held-out test set. Uses the version's canonical `source` URI rather than
    reconstructing a run-relative path, which is required for MLflow 3.
    """
    # FIX 3: resolve the version's canonical source URI via the client. In
    # MLflow 2 this is typically runs:/<run_id>/model; in MLflow 3 it is a
    # models:/m-<id> URI pointing at the LoggedModel tree. Using mv.source
    # works correctly in both.
    client = MlflowClient()
    mv = client.get_model_version(REGISTERED_MODEL_NAME, str(version.version))
    model = mlflow.sklearn.load_model(mv.source)

    y_pred = model.predict(X_test)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    accuracy = (y_pred == y_test).mean()

    report = classification_report(
        y_test, y_pred, target_names=class_names, output_dict=True, zero_division=0
    )

    return {
        "version": version.version,
        "run_id": version.run_id,
        "test_macro_f1": macro_f1,
        "test_accuracy": accuracy,
        "report": report,
        "y_pred": y_pred,
    }


def run_evaluation():
    configure_mlflow()
    client = MlflowClient()

    # FIX 4: removed the two stray lines that referenced an undefined `version`
    # variable and loaded a model that was never used in this function:
    #
    #     mv = client.get_model_version("rentguard-risk-classifier", str(version))
    #     model = mlflow.sklearn.load_model(mv.source)
    #
    # They were leftover dead code and would raise NameError before reaching
    # evaluate_version().

    X_test, y_test = load_test_split()
    label_encoder = load_label_encoder()
    class_names = list(label_encoder.classes_)

    print(f"Loaded test set: {X_test.shape}")

    versions = get_all_model_versions(client)
    if not versions:
        raise RuntimeError(
            f"No registered versions found for '{REGISTERED_MODEL_NAME}'. "
            f"Run train.py first."
        )

    print(f"Found {len(versions)} registered version(s) to evaluate on TEST set.\n")

    results = []
    for version in versions:
        try:
            result = evaluate_version(version, X_test, y_test, class_names)
        except ValueError as e:
            if "features" in str(e) and "expecting" in str(e):
                logger.warning(
                    f"Skipping model version {version.version} "
                    f"due to feature dimension mismatch: {e}"
                )
                continue
            raise

        results.append(result)
        print(
            f"Version {result['version']} (run_id={result['run_id']}): "
            f"test_macro_f1={result['test_macro_f1']:.4f}, "
            f"test_accuracy={result['test_accuracy']:.4f}"
        )

    # Pick the winner based on TEST macro-F1
    best = max(results, key=lambda r: r["test_macro_f1"])
    print(
        f"\nBest on TEST set: version {best['version']} "
        f"(test_macro_f1={best['test_macro_f1']:.4f})"
    )

    # Log a dedicated evaluation run capturing the final decision
    with mlflow.start_run(run_name="test_set_evaluation"):
        mlflow.log_param("evaluated_versions", [r["version"] for r in results])
        mlflow.log_param("promoted_version", best["version"])
        mlflow.log_metric("test_macro_f1", best["test_macro_f1"])
        mlflow.log_metric("test_accuracy", best["test_accuracy"])

        for label in class_names:
            metrics = best["report"][label]
            key = sanitize_metric_key(label)
            mlflow.log_metric(f"test_f1_{key}", metrics["f1-score"])
            mlflow.log_metric(f"test_precision_{key}", metrics["precision"])
            mlflow.log_metric(f"test_recall_{key}", metrics["recall"])

        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        cm_path = ARTIFACTS_DIR / f"version_{best['version']}_test_confusion_matrix.png"
        plot_confusion_matrix(y_test, best["y_pred"], class_names, cm_path)
        mlflow.log_artifact(str(cm_path))

    # Promote via alias (modern MLflow approach)
    client.set_registered_model_alias(
        name=REGISTERED_MODEL_NAME,
        alias=CHAMPION_ALIAS,
        version=best["version"],
    )
    print(f"\nSet alias '{CHAMPION_ALIAS}' -> version {best['version']}")
    print(f"Servable at: models:/{REGISTERED_MODEL_NAME}@{CHAMPION_ALIAS}")

    # Save a git-diffable metrics file for DVC
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    eval_summary = {
        "promoted_version": best["version"],
        "test_macro_f1": best["test_macro_f1"],
        "test_accuracy": best["test_accuracy"],
        "per_class_f1": {
            label: best["report"][label]["f1-score"] for label in class_names
        },
        "all_versions_compared": [
            {"version": r["version"], "test_macro_f1": r["test_macro_f1"]}
            for r in results
        ],
    }
    with open(METRICS_DIR / "eval_metrics.json", "w") as f:
        json.dump(eval_summary, f, indent=2)
    print(f"Saved {METRICS_DIR / 'eval_metrics.json'} for DVC tracking.")

    return eval_summary


if __name__ == "__main__":
    # Run as: python -m services.classifier_service.training.evaluate
    summary = run_evaluation()
    print("\nEvaluation complete. Summary:")
    print(json.dumps(summary, indent=2))