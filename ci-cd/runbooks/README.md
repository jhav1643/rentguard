# Runbooks

Operational procedures for CI/CD incidents and routine operations.

## Index

| Runbook | When to use |
|---|---|
| `rollback.md` | Bad deploy is live — revert a service or full release |
| `model-promotion.md` | Manually promote or roll back a classifier model |
| `failed-deploy.md` | Helm deploy failed mid-rollout |

## Rules

- Every runbook is written for someone who is **not** the author.
- If you needed to think for more than 30 seconds, add it here.
- Keep commands copy-pasteable.
- Never write secrets in a runbook — reference where to get them.