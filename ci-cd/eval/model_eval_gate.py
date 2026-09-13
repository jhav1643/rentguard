#!/usr/bin/env python3
"""Absolute-threshold gate for classifier eval metrics.

Fails if any metric in metrics/eval_metrics.json is below the
thresholds in thresholds.yaml.

Usage:
    python ci-cd/eval/model_eval_gate.py \
        --metrics metrics/eval_metrics.json \
        --thresholds ci-cd/eval/thresholds.yaml \
        --output ci-cd/reports/model_eval_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def check(metrics: dict, thresholds: dict) -> tuple[bool, list[str], dict]:
    cfg = thresholds["classifier"]
    failures: list[str] = []
    results: dict = {}

    # Overall metric checks
    for key, min_val in [
        ("test_macro_f1", cfg["min_macro_f1"]),
        ("test_precision", cfg["min_precision"]),
        ("test_recall", cfg["min_recall"]),
        ("test_auc", cfg["min_auc"]),
    ]:
        actual = metrics.get(key)
        if actual is None:
            failures.append(f"{key}: missing from metrics file")
            results[key] = {"actual": None, "min": min_val, "pass": False}
            continue
        passed = float(actual) >= float(min_val)
        results[key] = {"actual": float(actual), "min": float(min_val), "pass": passed}
        if not passed:
            failures.append(f"{key}: {actual:.4f} < {min_val}")

    # Slice checks
    slices = metrics.get("per_slice_macro_f1", {})
    slice_results = {}
    for slice_name, min_val in cfg.get("slice_min_macro_f1", {}).items():
        actual = slices.get(slice_name)
        if actual is None:
            failures.append(f"slice '{slice_name}': missing")
            slice_results[slice_name] = {"actual": None, "min": min_val, "pass": False}
            continue
        passed = float(actual) >= float(min_val)
        slice_results[slice_name] = {
            "actual": float(actual), "min": float(min_val), "pass": passed
        }
        if not passed:
            failures.append(f"slice '{slice_name}': {actual:.4f} < {min_val}")
    results["per_slice_macro_f1"] = slice_results

    return len(failures) == 0, failures, results


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--metrics", required=True)
    p.add_argument("--thresholds", required=True)
    p.add_argument("--output", default="ci-cd/reports/model_eval_report.json")
    args = p.parse_args()

    metrics = load_json(args.metrics)
    thresholds = load_yaml(args.thresholds)
    passed, failures, results = check(metrics, thresholds)

    report = {
        "gate": "model_eval",
        "passed": passed,
        "failures": failures,
        "results": results,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())