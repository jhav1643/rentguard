# Helm Environment Values

Per-environment overrides for charts under `infra/helm/`.

## Usage (from deploy workflow)

    helm upgrade --install rag infra/helm/rag-api \
      -f ci-cd/helm/values-common.yaml \
      -f ci-cd/helm/values-staging.yaml \
      --set image.tag=${{ inputs.image_tag }} \
      --wait --atomic --timeout 5m

Layering order (later overrides earlier):
1. Chart defaults (`infra/helm/<chart>/values.yaml`)
2. `values-common.yaml`
3. `values-<env>.yaml`
4. `--set` (image tag, secrets from CI)

## Rules

- Do NOT put secrets in these files. Use K8s Secrets via External Secrets
  or `--set` from GitHub Secrets.
- Do NOT put `latest` image tags here. Tags come from CI at deploy time.
- Every value that differs between envs MUST live here, not in the chart.