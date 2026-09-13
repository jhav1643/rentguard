# Eval Gates

Threshold + promotion scripts called by CI/CD workflows.

## Files

| File | Called by | Purpose |
|---|---|---|
| `thresholds.yaml` | All gates | Central config — no magic numbers in workflows |
| `model_eval_gate.py` | `model-eval-gate.yml` | Fail if classifier metrics below threshold |
| `model_promotion_gate.py` | `model-promotion-gate.yml` | Compare candidate vs production in MLflow, flip alias |
| `rag_gate.py` | `rag-eval-gate.yml` | Score RAG outputs against golden set, fail on regression |

## Local run

    python ci-cd/eval/model_eval_gate.py \
      --metrics metrics/eval_metrics.json \
      --thresholds ci-cd/eval/thresholds.yaml

    python ci-cd/eval/model_promotion_gate.py \
      --model-name rentguard-classifier \
      --thresholds ci-cd/eval/thresholds.yaml \
      --dry-run true

## Rules

- Never hardcode thresholds in workflows. Always read from `thresholds.yaml`.
- Every gate exits 0 (pass) or 1 (fail). No soft warnings.
- Every gate writes a JSON report for audit.