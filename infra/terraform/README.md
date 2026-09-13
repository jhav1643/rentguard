# Terraform: VPC, IAM, S3, EKS

Reusable Terraform modules and two environments for the RentGuard
platform.

- **`envs/dev`** — Floci-backed. Local, free, disposable. Use it
  freely; nothing it creates costs money or touches real AWS.
- **`envs/demo`** — real AWS. EKS is gated behind `deploy_eks` and
  defaults to `false`. You must deliberately opt into the cost.

---

## Layout

```
infra/terraform/
├── README.md                 <- this file
├── modules/
│   ├── vpc/                  <- VPC, subnets, IGW, optional NAT, optional flow logs
│   ├── iam/                  <- EKS control-plane role + EKS node-group role
│   ├── s3/                   <- one bucket, versioned, encrypted, public-access-blocked
│   └── eks/                  <- EKS control plane + one managed node group
└── envs/
    ├── dev/                  <- Floci at localhost:4566
    └── demo/                 <- real AWS, EKS opt-in
```

Every module is plain reusable HCL. No environment-specific
assumptions are baked into any module — all variation lives in the
env files.

---

## The four modules

| Module | Creates | Notable defaults |
|---|---|---|
| `vpc` | VPC, public + private subnets, IGW, route tables, optional NAT, optional flow logs | `enable_nat_gateway = false`, `enable_flow_logs = false` |
| `iam` | EKS control-plane role, EKS node-group role, AWS-managed policy attachments | IRSA/OIDC deliberately not implemented (see below) |
| `s3` | One bucket, versioning, SSE, public-access block, optional lifecycle rules | `force_destroy = false` (env files override to `true`) |
| `eks` | EKS control plane, one managed node group | `kubernetes_version = "1.29"`, `capacity_type = "ON_DEMAND"` |

Each module's `variables.tf` documents every input with a
description. Nothing is hidden.

---

## Key decisions worth remembering

### NAT Gateway is off by default
The VPC module defaults `enable_nat_gateway = false`. A single NAT
gateway costs roughly **$32/month** on real AWS, plus data processing.
It is only worth paying for when something actually lives in the
private subnets — typically the EKS worker nodes in the demo
environment. This is a deliberate trade-off, not an oversight.

In `envs/dev` it stays off unconditionally (Floci doesn't route).
In `envs/demo` it is gated on `var.deploy_eks`, so you only pay for
NAT when you've opted into EKS.

### EKS is gated in demo, on by default in dev
- **`envs/dev`**: `deploy_eks` defaults to `true`. Free locally, and
  you usually want the EKS path exercised on every apply.
- **`envs/demo`**: `deploy_eks` defaults to `false`. The EKS control
  plane alone costs **~$73/month** the moment it exists. You must
  pass `-var="deploy_eks=true"` explicitly.

When `deploy_eks = false`, the EKS module is not created at all
(`count = 0`), and the EKS outputs return the string
`"EKS not deployed (deploy_eks=false)"` rather than a real endpoint.

### Kubernetes version pinned to a supported release
`envs/demo` pins Kubernetes `1.31`, which is in standard support. The
EKS extended-support surcharge is **~$0.60/hr per cluster
(~$438/month)** on top of the standard ~$73/month. An unsupported
version is more expensive than the control plane itself. Check the
[EKS version calendar](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html)
before bumping.

### Subnet usage differs between dev and demo
- **`envs/dev`**: EKS gets `public_subnet_ids` only. Floci does not
  emulate private-subnet egress, so this is correct locally.
- **`envs/demo`**: EKS gets `concat(private_subnet_ids, public_subnet_ids)`.
  The control plane ENIs land across both; worker nodes go in private
  subnets. This is why NAT is enabled in demo when EKS is on — the
  private nodes need outbound internet to pull images.

### IRSA / OIDC is deliberately not implemented yet
There is no OIDC provider, and there are no per-service-account IAM
roles. This is called out explicitly at the top of
`modules/iam/main.tf`. It is a legitimate next step, not a silent
skip.

Why it's separate: a proper IRSA setup has to be applied *after* the
cluster exists (the OIDC provider is derived from the cluster), which
means it naturally belongs in a second pass or a separate module with
an explicit dependency on the EKS cluster.

### S3 buckets are disposable in both envs
`force_destroy = true` in both `envs/dev` and `envs/demo` so
`terraform destroy` doesn't fail on leftover objects. This is a
deliberate choice for the two non-production environments. Any real
production bucket should keep the module default of `false`.

### Cluster Autoscaler won't fight Terraform
`modules/eks` sets `ignore_changes = [scaling_config[0].desired_size]`
on the node group. Without it, every `terraform plan` after the
Cluster Autoscaler runs would try to reset the node count back to
`var.desired_size`. If you want Terraform to own the count strictly,
remove that block.

### Control-plane log types won't fight Terraform either
Same pattern on `enabled_cluster_log_types`: if someone toggles them
in the AWS console, Terraform leaves them alone. Flow logs are off by
default in the VPC module because CloudWatch Logs ingestion costs
money and Floci doesn't emulate them.

---

## Running `envs/dev` (Floci)

No AWS account, no credentials, no cost.

### One-time
Install Floci and start it:

```bash
floci start
```

Floci exposes an AWS-compatible endpoint at `http://localhost:4566`.
The dev provider block points `ec2`, `eks`, `iam`, `s3`, and `sts` at
it, with dummy credentials (`test` / `test`) that Floci accepts but
never checks.

**EKS emulation in Floci requires Docker in rootful mode.** Floci
backs its EKS emulation with a real k3s node, which needs
kernel-level access (e.g. `/var/dmesg`). Rootless Docker or Podman
will fail.

### Apply

```bash
cd infra/terraform/envs/dev
terraform init
terraform apply
```

If Docker is rootless or otherwise unavailable, skip EKS:

```bash
terraform apply -var="deploy_eks=false"
```

### Destroy

```bash
terraform destroy
```

State is local (`terraform.tfstate` in `envs/dev/`). Destroy and
re-apply as often as you like.

---

## Running `envs/demo` (real AWS)

### One-time: state bucket

`envs/demo` uses an S3 backend:

```
bucket = "rentguard-demo-terraform-state"
key    = "envs/demo/terraform.tfstate"
region = "us-east-1"
```

That bucket must exist before `terraform init` will succeed. Create
it once, out of band:

```bash
aws s3api create-bucket \
  --bucket rentguard-demo-terraform-state \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket rentguard-demo-terraform-state \
  --versioning-configuration Status=Enabled
```

If you'd rather not use remote state for the first run, comment out
the `backend "s3"` block in `envs/demo/provider.tf`, apply once with
local state, then uncomment and run `terraform init -migrate-state`.

### One-time: credentials

Configure real AWS credentials via `aws configure` or environment
variables. Nothing is hardcoded anywhere in the code.

### Apply — IAM, S3, VPC only

```bash
cd infra/terraform/envs/demo
terraform init
terraform apply
```

With `deploy_eks = false` (the default), this creates only the VPC,
the two IAM roles, and the S3 bucket. No EKS, no NAT gateway, no
ongoing compute cost beyond S3 storage.

**Confirm those look right before proceeding.**

### Then, and only then, consider EKS

```bash
terraform apply -var="deploy_eks=true"
```

This creates the EKS control plane (~$73/month) and turns on the NAT
gateway (~$32/month). Expect roughly **$105/month** for as long as
the cluster exists.

### Tear down EKS first

```bash
terraform destroy -target=module.eks
```

This removes the control plane, the node group, and the NAT gateway.
Do this the moment you're done demoing so nothing is left running by
accident.

Then destroy the rest if desired:

```bash
terraform destroy
```

---

## Cost summary (real AWS)

| Resource | Approx cost | When |
|---|---|---|
| EKS control plane | ~$73/month | `deploy_eks = true` in demo |
| NAT gateway (single) | ~$32/month | `deploy_eks = true` in demo |
| EKS node group (1× `t3.medium`) | ~$30/month | `deploy_eks = true` in demo |
| EKS extended support | ~$438/month | only if `kubernetes_version` is out of standard support (not the default) |
| VPC flow logs | ~$0.50/GB ingested | only if `enable_flow_logs = true` (not the default) |
| S3 storage | negligible | always |

`envs/dev` costs nothing.

---

## Floci compatibility notes

These are the parts of the config that are load-bearing against Floci
and are worth remembering if something breaks:

- **Endpoint overrides** in `envs/dev/provider.tf` point every AWS
  service the modules use at `localhost:4566`. If Floci adds or
  renames a service endpoint, this is where you fix it.
- **`s3_use_path_style = true`** is required. Virtual-hosted-style
  bucket URLs (`bucket.localhost`) don't resolve.
- **Inline tag specifications** at create time were previously dropped
  by Floci; the modules tag everything inline via
  `merge(var.tags, {...})`. If tags vanish on apply, that's the first
  thing to check.
- **`ModifyVpcAttribute`** was a no-op in older Floci versions; the
  VPC module sets `enable_dns_support` and `enable_dns_hostnames` at
  create time so it doesn't depend on that call.
- **EKS** works but requires rootful Docker, as noted above.
- **NAT gateways and flow logs** are accepted at the API level but not
  functionally emulated. They're off in dev anyway.
- **IAM policy evaluation is not enforced.** Floci accepts whatever
  the role is allowed to assume; it does not actually evaluate
  policies. This makes the IAM module useful for structure but
  useless as a security test.

---

## What's not here (and why)

| Not included | Reason |
|---|---|
| IRSA / OIDC | Requires an apply *after* the cluster exists. See the note in `modules/iam/main.tf`. |
| Managed add-ons (vpc-cni, coredns, kube-proxy) | EKS installs sensible defaults. Floci doesn't emulate add-on lifecycle. |
| VPC endpoints | Environment-specific; Floci support has been patchy. Add per-environment when needed. |
| Bucket policies | Inherently environment-specific. Attaching one from a module default would be wrong for someone. |
| Object uploads in Terraform | Terraform is a poor fit for managing S3 object contents. Use the CLI or CI. |
| Security groups | The default SG is created by AWS with the VPC; EKS creates its own. A module default here would conflict. |

---

## Common tasks

**Format check** (run before committing):

```bash
terraform fmt -recursive infra/terraform
```

**Validate without applying**:

```bash
cd infra/terraform/envs/dev && terraform validate
cd infra/terraform/envs/demo && terraform validate
```

**See what would change**:

```bash
cd infra/terraform/envs/demo && terraform plan -var="deploy_eks=false"
```

**Inspect a specific output**:

```bash
cd infra/terraform/envs/demo && terraform output cluster_endpoint
```