#!/usr/bin/env python3
"""
RAG evaluation gate for RentGuard.

Reads metrics from either:
  - a pre-computed baseline JSON (default: metrics/rag_eval_baseline.json)
  - or runs tests/rag_eval/run_rag_eval.py and uses its output

Compares against ci-cd/eval/thresholds.yaml and exits non-zero on failure.
Designed to be runnable from GitHub Actions and locally.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger("rag_gate")


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Thresholds file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Thresholds file did not parse to a mapping: {path}")
    return data


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Metrics file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Metrics file did not parse to a mapping: {path}")
    return data


# ---------------------------------------------------------------------------
# Running the eval harness
# ---------------------------------------------------------------------------
def run_eval_harness(
    dataset: Path,
    output: Path,
    extra_args: Optional[list] = None,
) -> Dict[str, Any]:
    """Run tests/rag_eval/run_rag_eval.py and return its JSON output."""
    script = REPO_ROOT / "tests" / "rag_eval" / "run_rag_eval.py"
    if not script.exists():
        raise FileNotFoundError(f"Eval harness not found: {script}")

    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(script),
        "--dataset",
        str(dataset),
        "--output",
        str(output),
    ]
    if extra_args:
        cmd.extend(extra_args)

    logger.info("Running eval harness: %s", " ".join(cmd))
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        logger.info("Harness stdout:\n%s", result.stdout)
    if result.stderr:
        logger.warning("Harness stderr:\n%s", result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"Eval harness exited with code {result.returncode}"
        )

    return load_json(output)


# ---------------------------------------------------------------------------
# Threshold checks
# ---------------------------------------------------------------------------
def _get(d: Dict[str, Any], *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _check_min(
    results: Dict[str, Any],
    key: str,
    minimum: float,
    label: str,
) -> bool:
    actual = results.get(key)
    if actual is None:
        logger.warning("[SKIP] %s missing from metrics", label)
        return True

    ok = float(actual) >= float(minimum)
    status = "PASS" if ok else "FAIL"
    logger.info(
        "[%s] %s = %.4f (min %.4f)", status, label, float(actual), float(minimum)
    )
    return ok


def _check_max(
    results: Dict[str, Any],
    key: str,
    maximum: float,
    label: str,
) -> bool:
    actual = results.get(key)
    if actual is None:
        logger.warning("[SKIP] %s missing from metrics", label)
        return True

    ok = float(actual) <= float(maximum)
    status = "PASS" if ok else "FAIL"
    logger.info(
        "[%s] %s = %.4f (max %.4f)", status, label, float(actual), float(maximum)
    )
    return ok


def _check_per_slice(
    results: Dict[str, Any],
    slice_key: str,
    thresholds: Dict[str, float],
) -> bool:
    slices = results.get(slice_key) or {}
    if not isinstance(slices, dict) or not slices:
        logger.warning("[SKIP] no per-slice metrics found under %r", slice_key)
        return True

    all_ok = True
    for slice_name, min_value in thresholds.items():
        actual = slices.get(slice_name)
        if actual is None:
            logger.warning("[SKIP] slice %r missing", slice_name)
            continue
        ok = float(actual) >= float(min_value)
        status = "PASS" if ok else "FAIL"
        logger.info(
            "[%s] %s[%s] = %.4f (min %.4f)",
            status,
            slice_key,
            slice_name,
            float(actual),
            float(min_value),
        )
        all_ok = all_ok and ok
    return all_ok


def evaluate_thresholds(
    metrics: Dict[str, Any],
    thresholds: Dict[str, Any],
) -> bool:
    rag_cfg = thresholds.get("rag", {}) or {}
    obs_cfg = thresholds.get("observability", {}) or {}

    checks = []

    # Core RAGAS metrics (higher is better)
    checks.append(
        _check_min(
            metrics,
            "faithfulness",
            rag_cfg.get("faithfulness", 0.75),
            "faithfulness",
        )
    )
    checks.append(
        _check_min(
            metrics,
            "answer_relevancy",
            rag_cfg.get("answer_relevancy", 0.70),
            "answer_relevancy",
        )
    )
    checks.append(
        _check_min(
            metrics,
            "context_precision",
            rag_cfg.get("context_precision", 0.65),
            "context_precision",
        )
    )
    checks.append(
        _check_min(
            metrics,
            "context_recall",
            rag_cfg.get("context_recall", 0.70),
            "context_recall",
        )
    )

    # Latency (lower is better)
    checks.append(
        _check_max(
            metrics,
            "p95_latency_ms",
            rag_cfg.get("p95_latency_ms", 8000),
            "p95_latency_ms",
        )
    )

    # Observability-derived metrics
    if "empty_retrieval_rate" in obs_cfg:
        checks.append(
            _check_max(
                metrics,
                "empty_retrieval_rate",
                obs_cfg["empty_retrieval_rate"],
                "empty_retrieval_rate",
            )
        )
    if "citation_fail_rate" in obs_cfg:
        checks.append(
            _check_max(
                metrics,
                "citation_fail_rate",
                obs_cfg["citation_fail_rate"],
                "citation_fail_rate",
            )
        )

    # Per-slice checks (optional)
    per_slice = rag_cfg.get("per_slice") or {}
    if per_slice:
        checks.append(_check_per_slice(metrics, "per_slice", per_slice))

    return all(checks)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def write_summary(
    metrics: Dict[str, Any],
    passed: bool,
    output: Path,
) -> None:
    summary = {
        "passed": passed,
        "metrics": metrics,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    logger.info("Wrote gate summary to %s", output)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RentGuard RAG eval gate")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=REPO_ROOT / "tests" / "rag_eval" / "eval_dataset.csv",
        help="Path to eval dataset CSV",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=REPO_ROOT / "ci-cd" / "eval" / "thresholds.yaml",
        help="Path to thresholds YAML",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=REPO_ROOT / "metrics" / "rag_eval_baseline.json",
        help="Pre-computed metrics JSON. If missing, the harness is run.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "metrics" / "rag_gate_summary.json",
        help="Where to write the gate summary JSON",
    )
    parser.add_argument(
        "--run-harness",
        action="store_true",
        help="Force running the eval harness even if a baseline exists",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    thresholds = load_yaml(args.thresholds)

    try:
        if args.run_harness or not args.baseline.exists():
            metrics = run_eval_harness(args.dataset, args.baseline)
        else:
            logger.info("Using existing baseline: %s", args.baseline)
            metrics = load_json(args.baseline)
    except Exception as exc:
        logger.error("Failed to obtain metrics: %s", exc)
        return 2

    passed = evaluate_thresholds(metrics, thresholds)
    write_summary(metrics, passed, args.output)

    if passed:
        logger.info("RAG gate PASSED")
        return 0

    logger.error("RAG gate FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())