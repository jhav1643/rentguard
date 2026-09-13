# Rollback Runbook

Two levels of rollback: **service rollback** (single Helm release) and
**full release rollback** (all services to a previous tag).

## When to roll back

- Deploy succeeded but smoke tests fail
- Error rate / latency spike after deploy
- RAG or classifier quality regression in prod
- Any P0/P1 incident traced to a recent deploy

## Prerequisites

- AWS credentials with EKS + ECR access
- `kubectl` configured: `aws eks update-kubeconfig --name rentguard-demo-eks --region us-east-1`
- `helm` v3.15+
- Know the previous good tag (check GitHub Actions → last successful `Deploy to EKS` run)

---

## Option 1 — Rollback a single service (fastest)

Use when only one service is misbehaving.

### 1.1 See release history

    helm history rag -n rentguard-prod

Output: list of revisions. Revision N-1 is your rollback target.

### 1.2 Rollback

    helm rollback rag <REVISION> -n rentguard-prod --wait --timeout 5m

### 1.3 Verify

    kubectl rollout status deployment/rag-rag-api -n rentguard-prod --timeout=180s
    kubectl get pods -n rentguard-prod -l app.kubernetes.io/instance=rag

---

## Option 2 — Redeploy a known-good image tag

Use when you want to move forward to an older, known-good image
instead of reverting the release state.

    helm upgrade --install rag infra/helm/rag-api \
      -f ci-cd/helm/values-common.yaml \
      -f ci-cd/helm/values-prod.yaml \
      --set global.imageTag=<GOOD_SHA> \
      --namespace rentguard-prod \
      --wait --atomic --timeout 5m

Same command for `backend`, `classifier`, `ingestion` — change the release name and chart path.

---

## Option 3 — Full release rollback (all services)

Use when multiple services were deployed together and are all affected.

Run for each release in this order (reverse dependency order):

    helm rollback ingestion  -n rentguard-prod --wait
    helm rollback classifier -n rentguard-prod --wait
    helm rollback backend    -n rentguard-prod --wait
    helm rollback rag        -n rentguard-prod --wait

Then verify:

    kubectl get pods -n rentguard-prod
    kubectl get events -n rentguard-prod --sort-by=.lastTimestamp | tail -20

---

## Option 4 — Emergency: scale down

If a bad deploy is causing a production incident and rollback is slow:

    kubectl scale deployment rag-rag-api -n rentguard-prod --replicas=0

This stops the bleeding immediately. Communicate to users, then rollback
properly with Option 1 or 2.

---

## Post-rollback checklist

- [ ] Rollback completed and pods are Running
- [ ] Health endpoints return 200
- [ ] Error rate back to baseline in CloudWatch
- [ ] Incident channel updated
- [ ] Postmortem ticket opened (use `ci-cd/templates/postmortem-template.md` if present)
- [ ] Root cause identified before next deploy

---

## Common failure modes

| Symptom | Likely cause | Action |
|---|---|---|
| `helm rollback` fails with "no revision" | Release never deployed successfully | Use Option 2 with a good SHA |
| Pods stuck in `ImagePullBackOff` | Wrong tag or ECR permissions | Check tag exists: `aws ecr describe-images --repository-name rentguard-rag-api` |
| Pods `CrashLoopBackOff` after rollback | ConfigMap / Secret changed | Roll back config separately, or use Option 2 with explicit values |
| PVC mount failure | EFS unavailable | Check `kubectl describe pvc -n rentguard-prod` |