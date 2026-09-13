# Failed Deploy Runbook

The `Deploy to EKS` workflow uses `helm upgrade --install --wait --atomic`.
This means: if the rollout fails, Helm automatically reverts to the previous
revision. So a failed deploy usually does NOT leave prod broken — but it
DOES leave work to do.

## Step 1 — Confirm the workflow actually failed

GitHub → Actions → **Deploy to EKS** → last run.
Check which service failed (matrix step name).

## Step 2 — Confirm prod is still healthy

    kubectl get pods -n rentguard-prod
    helm history <release> -n rentguard-prod | tail -5

The last `deployed` revision should be the OLD one (Helm `--atomic` reverted).
If it's not, jump to `rollback.md` Option 1.

## Step 3 — Read the failure reason

From the workflow log, look for:
- `Error: UPGRADE FAILED:` — Helm-level error
- `ImagePullBackOff` — bad tag or ECR auth
- `CrashLoopBackOff` — container starts then dies (check app logs)
- `context deadline exceeded` — `--timeout` too short

## Step 4 — Fix and retry

| Failure | Fix |
|---|---|
| Bad image tag | Re-run with correct `image_tag` input |
| Image not in ECR | Check `build-and-push.yml` ran for that SHA |
| Bad config | Fix `ci-cd/helm/values-<env>.yaml`, commit, re-run |
| App crash on start | Check `kubectl logs <pod> -n rentguard-prod --previous` |
| Timeout | Increase `--timeout` or check node capacity |

Retry:

    GitHub → Actions → Deploy to EKS → Run workflow → same tag

## Step 5 — If prod IS actually broken

Use `ci-cd/runbooks/rollback.md` immediately. Do not debug forward in prod.

## Step 6 — After resolution

- [ ] Post in incident channel: what broke, how long, what fixed it
- [ ] Open postmortem if user impact > 5 minutes
- [ ] Add a threshold or test to catch this class of failure earlier