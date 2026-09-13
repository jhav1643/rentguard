import os
from pathlib import Path

import yaml
import mlflow

ROOT_DIR = Path(__file__).resolve().parents[3]
PARAMS_PATH = ROOT_DIR / "params.yml"
if not PARAMS_PATH.exists():
    PARAMS_PATH = ROOT_DIR / "params.yaml"

with open(PARAMS_PATH, "r") as f:
    params = yaml.safe_load(f)

EXPERIMENT_NAME = params["mlflow"]["experiment_name"]
DEFAULT_TRACKING_URI = "sqlite:///mlflow.db"  # project-root mlflow.db
 
 
def configure_mlflow() -> str:
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI)
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)
    print (f"\nMLflow tracking URI: {mlflow.get_tracking_uri()}")
    return tracking_uri
 