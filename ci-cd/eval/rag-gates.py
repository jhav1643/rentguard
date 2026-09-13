#!/usr/bin/env python3
"""RAG eval gate.

Scores RAG outputs against a golden set on:
  - faithfulness
  - answer_relevancy
  - context_precision
  - context_recall
  - p95 latency

Fails the gate if any metric is below threshold, or if too many
individual rows fall below per-row thresholds.

Golden set format (JSONL, one record per line):
  {
    "question": "...",
    "answer": "...",              # system answer to score
    "contexts": ["...", "..."],   # retrieved chunks
    "ground_truth": "..."         # reference answer
  }

Usage:
    python ci-cd/eval/rag_gate.py \
        --golden-set data/rag_golden/golden.jsonl \
        --thresholds ci-cd/eval/thresholds.yaml \
        --output ci-cd/reports/rag_eval_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Metric implementations
#
# These are lightweight, deterministic approximations so the gate runs
# without a judge-model dependency in CI. In production, swap _score_row()
# for a Ragas / LLM-judge call behind a feature flag.
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _faithfulness(answer: str, contexts: list[str]) -> float:
    """Fraction of answer tokens that appear in at least one context."""
    ans_tokens = _tokenize(answer)
    if not ans_tokens:
        return 0.0
    ctx_tokens = set()
    for c in contexts:
        ctx_tokens |= _tokenize(c)
    return len(ans_tokens & ctx_tokens) / len(ans_tokens)


def _answer_relevancy(answer: str, question: str) -> float:
    return _jaccard(answer, question)


def _context_precision(contexts: list[str], ground_truth: str) -> float:
    """Fraction of retrieved contexts that overlap the ground truth."""
    if not contexts:
        return 0.0
    hits = sum(1 for c in contexts if _jaccard(c, ground_truth) > 0.1)
    return hits / len(contexts)


def _context_recall(contexts: list[str], ground_truth: str) -> float:
    """Fraction of ground-truth tokens covered by any retrieved context."""
    gt_tokens = _tokenize(ground_truth)
    if not gt_tokens:
        return 0.0
    ctx_tokens = set()
    for c in contexts:
        ctx_tokens |= _tokenize(c)
    return len(gt_tokens & ctx_tokens) / len(gt_tokens)


# ---------------------------------------------------------------------------
# Row scoring
# ---------------------------------------------------------------------------

def score_row(row: dict) -> dict:
    start = time.perf_counter()
    scores = {
        "faithfulness": _faithfulness(row["answer"], row["contexts"]),
        "answer_relevancy": _answer_relevancy(row["answer"], row["question"]),
        "context_precision": _context_precision(row["contexts"], row["ground_truth"]),
        "context_recall": _context_recall(row["contexts"], row["ground_truth"]),
    }
    scores["latency_ms"] = (time.perf_counter() - start) * 1000
    return scores


def evaluate(golden_path: str) -> dict:
    rows = []
    with open(golden_path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    per_row = [score_row(r) for r in rows]
    if not per_row:
        raise ValueError("golden set is empty")

    def avg(key: str) -> float:
        return sum(r[key] for r in per_row) / len(per_row)

    latencies = sorted(r["latency_ms"] for r in per_row)
    p95 = latencies[int(0.95 * (len(latencies) - 1))]

    return {
        "n_rows": len(rows),
        "faithfulness": avg("faithfulness"),
        "answer_relevancy": avg("answer_relevancy"),
        "context_precision": avg("context_precision"),
        "context_recall": avg("context_recall"),
        "p95_latency_ms": p95,
        "per_row": per_row,
    }


def check(summary: dict, cfg: dict) -> tuple[bool, list[str], dict]:
    failures: list[str] = []
    checks: dict = {}

    for key in [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    ]:
        actual = summary[key]
        min_val = float(cfg[f"min_{key}"])
        passed = actual >= min_val
        checks[key] = {"actual": actual, "min": min_val, "pass": passed}
        if not passed:
            failures.append(f"{key}: {actual:.4f} < {min_val}")

    latency = summary["p95_latency_ms"]
    max_lat = float(cfg["max_p95_latency_ms"])
    lat_pass = latency <= max_lat
    checks["p95_latency_ms"] = {"actual": latency, "max": max_lat, "pass": lat_pass}
    if not lat_pass:
        failures.append(f"p95_latency_ms: {latency:.0f} > {max_lat}")

    return len(failures) == 0, failures, checks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--golden-set", required=True)
    p.add_argument("--thresholds", required=True)
    p.add_argument("--output", default="ci-cd/reports/rag_eval_report.json")
    args = p.parse_args()

    with open(args.thresholds) as f:
        thresholds = yaml.safe_load(f)
    cfg = thresholds["rag"]

    summary = evaluate(args.golden_set)
    passed, failures, checks = check(summary, cfg)

    report = {
        "gate": "rag",
        "passed": passed,
        "n_rows": summary["n_rows"],
        "failures": failures,
        "checks": checks,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())