# CI/CD — Phase 8

End-to-end CI/CD for the RentGuard platform.

## Pipelines

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci-test.yml` | PR + push to `main` | Lint + unit tests |
| `build-and-push.yml` | After `Test` succeeds on `main` | Build Docker images, push to ECR (SHA tags only) |
| `model-eval-gate.yml` | Training files change | Classifier metric thresholds (from `eval/thresholds.yaml`) |
| `model-promotion-gate.yml` | After `Model Eval Gate` succeeds, or manual | Compare candidate vs production in MLflow, flip alias if better |
| `rag-eval-gate.yml` | RAG files change | Golden-set scoring: faithfulness, relevancy, context precision/recall, latency |
| `security-scan.yml` | PR, push to `main`, weekly | Trivy (fs + images), pip-audit, gitleaks |
| `deploy-eks.yml` | Manual | Helm deploy to EKS with `--atomic` + rollback |

## Folder map

    ci-cd/
    ├── workflows/      Draft GitHub Actions files.
    ├── eval/           Gate scripts + central thresholds.yaml.
    ├── helm/           Per-env Helm values layered at deploy time.
    ├── runbooks/       Operational procedures (rollback, promotion, failed deploy).
    └── reports/        Gate output (gitignored, kept for local runs).

## How to promote a workflow to live

1. Edit inside `ci-cd/workflows/`.
2. Review on a PR.
3. Copy to `<repo-root>/.github/workflows/`.
4. Edit only the live copy after that.

GitHub only reads `.github/workflows/` at the repo root. This folder is the
staging/draft area.

## Thresholds — single source of truth

All gate thresholds live in `ci-cd/eval/thresholds.yaml`.
Do not hardcode numbers in workflows. Change the YAML, commit, done.

## Image tagging policy

- Every image is pushed with tag = git commit SHA.
- `:latest` is **not** pushed.
- Deploys always reference an explicit SHA.

## Secrets

Currently: long-lived IAM user keys via GitHub Secrets (MVP).
Target: GitHub OIDC → IAM role (no stored keys). Tracked as an ADR-level
follow-up; deliberately deferred.

Required secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `MLFLOW_TRACKING_URI`
- `EMBEDDING_TOKEN`
- `RAG_MODEL_NAME`
- `RAG_GOLDEN_BUCKET`

## Runbooks

- `runbooks/rollback.md` — bad deploy is live
- `runbooks/model-promotion.md` — promote or roll back a classifier model
- `runbooks/failed-deploy.md` — Helm deploy failed mid-rollout

## Known gaps (Phase 8)

- OIDC migration not done — uses long-lived keys
- DVC S3 remote not configured yet — `model-eval-gate.yml` will fail until it is
- Staging environment not yet provisioned — `deploy-eks.yml` targets demo EKS
- `latest` tag still referenced in older docs; workflows use SHA only
- RAG golden set must exist at `data/rag_golden/golden.jsonl` or in S3

## Local usage

Run a gate locally the same way CI does:

    python ci-cd/eval/model_eval_gate.py \
      --metrics metrics/eval_metrics.json \
      --thresholds ci-cd/eval/thresholds.yaml

    python ci-cd/eval/model_promotion_gate.py \
      --model-name rentguard-classifier \
      --thresholds ci-cd/eval/thresholds.yaml \
      --dry-run true

    python ci-cd/eval/rag_gate.py \
      --golden-set data/rag_golden/golden.jsonl \
      --thresholds ci-cd/eval/thresholds.yaml