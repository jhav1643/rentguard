# Model Promotion Runbook

Controls how a new classifier model moves from `candidate` to `production`
in MLflow, and how to roll it back if it misbehaves.

## Model lifecycle

    training run → registered version → alias: candidate
                                             ↓
                              promotion gate (automatic)
                                             ↓
                                        alias: production
                                             ↓
                               classifier-service picks it up on restart

## When promotion happens

- Automatically: after `Model Eval Gate` succeeds on `main`, the
  `Model Promotion Gate` workflow runs and compares candidate vs
  current production using `ci-cd/eval/thresholds.yaml`.
- Manually: run the `Model Promotion Gate` workflow with `dry_run=false`.

## Promotion criteria (from thresholds.yaml)

- `candidate.test_macro_f1 >= production.test_macro_f1 + min_f1_delta`
- `candidate.test_auc >= production.test_auc`
- `candidate.latency_p95_ms <= production.latency_p95_ms * (1 + max_latency_regression)`
- No critical slice drops more than `max_slice_drop`
- Improvement is statistically significant (bootstrap CI)

If ANY condition fails, the gate exits non-zero and no alias change happens.

---

## Manual promotion

### 1. Dry run (safe — no changes)

GitHub UI → Actions → **Model Promotion Gate** → Run workflow
- `dry_run = true`
- leave `candidate_version` empty to use the latest registered version

Review the `promotion_report.json` artifact.

### 2. Promote for real

Re-run with `dry_run = false`.

The gate script will:
1. Set alias `candidate` → chosen version
2. Compare vs alias `production`
3. If pass: set alias `production` → candidate version
4. Write report to `ci-cd/reports/promotion_report.json`

### 3. Restart classifier-service to pick up new model

    kubectl rollout restart deployment classifier-classifier-service -n rentguard-prod
    kubectl rollout status deployment classifier-classifier-service -n rentguard-prod --timeout=180s

---

## Roll back a model

If the promoted model turns out to be worse in production:

### 1. Find the previous production version

    mlflow models list-versions --name rentguard-classifier
    # or in the MLflow UI: Models → rentguard-classifier → Aliases history

### 2. Point production alias back

    python ci-cd/eval/model_promotion_gate.py \
      --model-name rentguard-classifier \
      --force-promote-version <OLD_VERSION> \
      --prod-alias production

Or in the MLflow UI:
- Models → rentguard-classifier → version `<OLD_VERSION>`
- Add alias `production` to it (this removes it from the newer version)

### 3. Restart classifier-service

    kubectl rollout restart deployment classifier-classifier-service -n rentguard-prod

### 4. Verify

    kubectl logs -n rentguard-prod deploy/classifier-classifier-service | grep "model_version"

---

## Evidence to keep

After every promotion or rollback, archive:

- `promotion_report.json` (from the workflow artifact)
- MLflow run IDs of both candidate and old production
- The git SHA that triggered training
- Date, operator name, reason

Store under `ci-cd/reports/promotion-reports/<date>-<version>.json`.

---

## Common failure modes

| Symptom | Cause | Action |
|---|---|---|
| Gate fails on latency | New model slower | Retrain or accept tradeoff — do NOT bypass |
| Gate fails on slice drop | Regression on a critical class | Investigate before promoting |
| Alias not visible to service | Service uses a different MLflow URI | Check `MLFLOW_TRACKING_URI` env in deployment |
| Service not picking up new model | No rollout restart | Run step 3 above |