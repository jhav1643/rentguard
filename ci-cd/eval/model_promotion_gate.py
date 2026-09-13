#!/usr/bin/env python3
"""Model promotion gate.

Compares a candidate MLflow model version against the current
`production` alias. If the candidate beats prod on F1, AUC, latency,
and per-slice metrics — and the improvement is statistically
significant — promotes candidate to `production` alias.

Usage:
    python ci-cd/eval/model_promotion_gate.py \
        --model-name rentguard-classifier \
        --candidate-alias candidate \
        --prod-alias production \
        --thresholds ci-cd/eval/thresholds.yaml \
        --dry-run true \
        --output ci-cd/reports/promotion_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml
from mlflow.tracking import MlflowClient


# ---------------------------------------------------------------------------
# MLflow helpers
# ---------------------------------------------------------------------------

def get_version_by_alias(client: MlflowClient, name: str, alias: str) -> str | None:
    try:
        mv = client.get_model_version_by_alias(name, alias)
        return mv.version
    except Exception:
        return None


def get_run_metrics(client: MlflowClient, model_name: str, version: str) -> dict:
    mv = client.get_model_version(model_name, version)
    run = client.get_run(mv.run_id)
    return dict(run.data.metrics)


def get_run_params(client: MlflowClient, model_name: str, version: str) -> dict:
    mv = client.get_model_version(model_name, version)
    run = client.get_run(mv.run_id)
    return dict(run.data.params)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def bootstrap_ci_lower(
    candidate_scores: list[float],
    prod_scores: list[float],
    samples: int = 1000,
    confidence: float = 0.95,
) -> float:
    """Lower bound of a bootstrap CI on (candidate - prod) mean."""
    rng = np.random.default_rng(42)
    cand = np.asarray(candidate_scores)
    prod = np.asarray(prod_scores)
    n = min(len(cand), len(prod))
    if n == 0:
        return float("-inf")

    deltas = []
    for _ in range(samples):
        i = rng.integers(0, n, n)
        deltas.append(cand[i].mean() - prod[i].mean())
    alpha = (1 - confidence) / 2
    return float(np.quantile(deltas, alpha))


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------

def compare(cand: dict, prod: dict, cfg: dict) -> tuple[bool, list[str], dict]:
    failures: list[str] = []
    checks: dict = {}

    # 1. Macro-F1 delta
    f1_c = float(cand.get("test_macro_f1", 0))
    f1_p = float(prod.get("test_macro_f1", 0))
    f1_pass = (f1_c - f1_p) >= float(cfg["min_f1_delta"])
    checks["macro_f1"] = {
        "candidate": f1_c, "production": f1_p,
        "delta": f1_c - f1_p, "required_delta": cfg["min_f1_delta"],
        "pass": f1_pass,
    }
    if not f1_pass:
        failures.append(
            f"macro_f1 delta {f1_c - f1_p:.4f} < required {cfg['min_f1_delta']}"
        )

    # 2. AUC — must not drop
    auc_c = float(cand.get("test_auc", 0))
    auc_p = float(prod.get("test_auc", 0))
    auc_pass = (auc_p - auc_c) <= float(cfg["max_auc_drop"])
    checks["auc"] = {
        "candidate": auc_c, "production": auc_p,
        "drop": auc_p - auc_c, "max_drop": cfg["max_auc_drop"],
        "pass": auc_pass,
    }
    if not auc_pass:
        failures.append(f"auc dropped {auc_p - auc_c:.4f} > max {cfg['max_auc_drop']}")

    # 3. Latency — must not regress more than allowed
    lat_c = float(cand.get("latency_p95_ms", 0))
    lat_p = float(prod.get("latency_p95_ms", 0))
    if lat_p > 0:
        regression = (lat_c - lat_p) / lat_p
        lat_pass = regression <= float(cfg["max_latency_regression"])
        checks["latency_p95_ms"] = {
            "candidate": lat_c, "production": lat_p,
            "regression": regression, "max_regression": cfg["max_latency_regression"],
            "pass": lat_pass,
        }
        if not lat_pass:
            failures.append(
                f"latency regression {regression:.2%} > max {cfg['max_latency_regression']:.2%}"
            )
    else:
        checks["latency_p95_ms"] = {"pass": True, "note": "prod latency missing"}

    # 4. Critical slices — no drop beyond max_slice_drop
    cs_c = cand.get("per_slice_macro_f1", {}) or {}
    cs_p = prod.get("per_slice_macro_f1", {}) or {}
    slice_checks = {}
    for slice_name in cfg.get("critical_slices", []):
        s_c = float(cs_c.get(slice_name, 0))
        s_p = float(cs_p.get(slice_name, 0))
        drop = s_p - s_c
        s_pass = drop <= float(cfg["max_slice_drop"])
        slice_checks[slice_name] = {
            "candidate": s_c, "production": s_p,
            "drop": drop, "max_drop": cfg["max_slice_drop"],
            "pass": s_pass,
        }
        if not s_pass:
            failures.append(
                f"slice '{slice_name}' drop {drop:.4f} > max {cfg['max_slice_drop']}"
            )
    checks["critical_slices"] = slice_checks

    return len(failures) == 0, failures, checks


def statistical_check(
    cand_scores: list[float],
    prod_scores: list[float],
    cfg: dict,
) -> tuple[bool, dict]:
    """Bootstrap CI on (candidate - prod) mean F1 across eval samples."""
    if not cand_scores or not prod_scores:
        return True, {"skipped": "no per-sample scores available"}

    lower = bootstrap_ci_lower(
        cand_scores, prod_scores,
        samples=int(cfg.get("bootstrap_samples", 1000)),
        confidence=float(cfg.get("bootstrap_confidence", 0.95)),
    )
    passed = lower > 0
    return passed, {
        "ci_lower": lower,
        "samples": cfg.get("bootstrap_samples"),
        "confidence": cfg.get("bootstrap_confidence"),
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-name", required=True)
    p.add_argument("--candidate-alias", default="candidate")
    p.add_argument("--prod-alias", default="production")
    p.add_argument("--thresholds", required=True)
    p.add_argument("--candidate-version", default="")
    p.add_argument("--dry-run", default="false")
    p.add_argument("--output", default="ci-cd/reports/promotion_report.json")
    args = p.parse_args()

    dry_run = str(args.dry_run).lower() in ("1", "true", "yes")
    with open(args.thresholds) as f:
        thresholds = yaml.safe_load(f)
    cfg = thresholds["promotion"]

    client = MlflowClient()

    # Resolve versions
    cand_version = args.candidate_version or get_version_by_alias(
        client, args.model_name, args.candidate_alias
    )
    if not cand_version:
        print(f"ERROR: no candidate version found for alias '{args.candidate_alias}'")
        return 1

    prod_version = get_version_by_alias(client, args.model_name, args.prod_alias)

    report: dict = {
        "gate": "model_promotion",
        "model_name": args.model_name,
        "candidate_version": cand_version,
        "production_version": prod_version,
        "dry_run": dry_run,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # First promotion ever — no prod to compare against
    if not prod_version:
        report["decision"] = "bootstrap"
        report["reason"] = "no production alias exists; promoting candidate"
        if not dry_run:
            client.set_registered_model_alias(args.model_name, args.prod_alias, cand_version)
        report["promoted"] = not dry_run
        _write(args.output, report)
        print(json.dumps(report, indent=2))
        return 0

    cand_metrics = get_run_metrics(client, args.model_name, cand_version)
    prod_metrics = get_run_metrics(client, args.model_name, prod_version)

    passed, failures, checks = compare(cand_metrics, prod_metrics, cfg)

    # Statistical check (optional — only if per-sample scores are logged)
    cand_scores = _extract_per_sample(cand_metrics)
    prod_scores = _extract_per_sample(prod_metrics)
    stat_pass, stat_info = statistical_check(cand_scores, prod_scores, cfg)
    checks["statistical"] = stat_info

    report["checks"] = checks
    report["failures"] = failures
    report["candidate_metrics"] = _slim(cand_metrics)
    report["production_metrics"] = _slim(prod_metrics)

    final_pass = passed and stat_pass
    report["decision"] = "promote" if final_pass else "reject"

    if final_pass and not dry_run:
        client.set_registered_model_alias(args.model_name, args.prod_alias, cand_version)
        report["promoted"] = True
        report["promoted_at"] = datetime.now(timezone.utc).isoformat()
    else:
        report["promoted"] = False

    _write(args.output, report)
    print(json.dumps(report, indent=2))

    return 0 if final_pass else 1


def _extract_per_sample(metrics: dict) -> list[float]:
    """Optional hook: if per-sample F1 is logged as 'sample_f1_0..N', return it."""
    scores = []
    i = 0
    while f"sample_f1_{i}" in metrics:
        scores.append(float(metrics[f"sample_f1_{i}"]))
        i += 1
    return scores


def _slim(metrics: dict) -> dict:
    keys = [
        "test_macro_f1", "test_precision", "test_recall", "test_auc",
        "latency_p95_ms", "per_slice_macro_f1",
    ]
    return {k: metrics.get(k) for k in keys if k in metrics}


def _write(path: str, report: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())