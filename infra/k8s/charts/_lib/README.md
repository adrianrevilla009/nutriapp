# infra/k8s/charts/_lib

Shared Helm **library chart** (`type: library`) for every NutriApp
service chart, per ADR-0006 and
`docs/containerization-and-orchestration.md` section 3.1. A library
chart contributes named templates only — it renders no manifests of its
own and is never `helm install`ed directly.

## How a consuming chart uses this

1. Add it as a dependency in the consuming chart's `Chart.yaml`:

   ```yaml
   dependencies:
     - name: nutriapp-lib
       version: "0.1.0"
       repository: "file://../_lib"
   ```

   then `helm dependency build` (or `update`) inside the consuming
   chart's directory.

2. In each of the consuming chart's own `templates/*.yaml` files,
   `include` the named template, passing the consuming chart's own
   top-level `.` context **directly** — not re-scoped under a subchart
   key:

   ```yaml
   # templates/deployment.yaml
   {{ include "nutriapp-lib.deployment" . }}
   ```

   ```yaml
   # templates/service.yaml
   {{ include "nutriapp-lib.service" . }}
   ```

   ...and so on for `nutriapp-lib.hpa`, `nutriapp-lib.pdb`,
   `nutriapp-lib.networkPolicy`, `nutriapp-lib.serviceAccount`, and
   `nutriapp-lib.dbProvisionJob` (each wraps its own `if .Values.X.enabled`
   guard, so it's safe to always include them — they no-op when
   disabled).

   This means every values key these templates read (`image`,
   `resources`, `probes`, `service`, `serviceAccount`, `hpa`, `pdb`,
   `networkPolicy`, `dbProvision`) is expected at the **top level** of
   the consuming chart's own `values.yaml` — see `values.yaml` in this
   directory for the full shape and defaults.

3. **Copy `values.schema.json.template`** from this directory into the
   consuming chart's own root, renamed to `values.schema.json`, so
   `helm lint`/`helm install` enforce it against that chart's own
   top-level values.

   This file is deliberately named `*.template` in `_lib` itself, not
   `values.schema.json` — verified empirically while validating this
   chart: if a library chart ships its own `values.schema.json`, Helm
   *additionally* (and unavoidably) validates it against the parent's
   values namespaced under the dependency's alias (a `nutriapp-lib:` key)
   every time any consuming chart declares `nutriapp-lib` as a
   `dependencies:` entry. That namespaced section is always empty/undefined
   under this project's convention (named templates are invoked with the
   consumer's full top-level `.` context — see step 2 — never a
   subchart-scoped one), so the cascade always fails `helm lint` with
   confusing "irsaRoleArn is required" / "image.repository is required"
   errors that have nothing to do with the consumer's actual, valid
   top-level values. Naming it `*.template` avoids Helm auto-discovering
   and enforcing it in that unwanted place, while still keeping one
   canonical source consuming charts copy from (not yet automated into a
   build step that keeps copies in sync — a `devops-agent` follow-up if
   drift becomes a problem).

## Named templates provided

| Template | Renders | Notes |
|---|---|---|
| `nutriapp-lib.deployment` | `Deployment` | resources.requests/limits, liveness+readiness probes, and ServiceAccount are all `required` — a chart missing them fails to render, per `.claude/skills/containerization/SKILL.md`. |
| `nutriapp-lib.service` | `Service` | |
| `nutriapp-lib.serviceAccount` | `ServiceAccount` | IRSA annotation (`serviceAccount.irsaRoleArn`) is `required`. |
| `nutriapp-lib.hpa` | `HorizontalPodAutoscaler` | CPU-based by default; `hpa.customMetrics` for queue-depth/latency-based scaling (e.g. `food-recognition-service`). |
| `nutriapp-lib.pdb` | `PodDisruptionBudget` | |
| `nutriapp-lib.networkPolicy` | `NetworkPolicy` | Adds this service's explicit ALLOW ingress rules on top of the namespace-wide default-deny-ingress policy created once per environment by `infra/terraform/environments/<env>/namespace.tf`. `networkPolicy.ingressRules` is `required` when enabled — no implicit allow-all. |
| `nutriapp-lib.dbProvisionJob` | `ServiceAccount` + `ConfigMap` + `Job` (Helm `pre-install,pre-upgrade` hook) | Creates this service's own logical database + role inside the shared RDS instance. See the template file's header comment and the implementation plan section 9.1 for the full rationale and required values. Idempotent — safe on every `helm upgrade`; only creates the role/database and writes a new secret on first run, never rotates an existing one. |

## Validation performed for this chart

`helm lint`/`helm template` run directly against `infra/k8s/charts/_lib/`
succeed trivially and render nothing — that is expected and correct for
a library chart. Real validation requires a consuming chart; this was
done with a throwaway test-harness chart (not committed) during
`/implementation-execution` — see that stage's report for the exact
`helm lint`/`helm template` output. `identity-service`'s own chart
(`infra/k8s/charts/identity-service/`, owned by its own plan) is the
first real consumer.
