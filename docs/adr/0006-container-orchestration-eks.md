# ADR-0006: Container orchestration on Amazon EKS, no service mesh

## Status
Accepted

## Date
2026-08-23

## Context
Services must run as containers in a production AWS environment with
independent scaling, rolling deploys, and resource isolation per service
(CLAUDE.md 2.2). We need to choose a container orchestration platform and
decide whether a service mesh is warranted given the current team size (one
contributor + AI agents) and traffic scale (pre-launch product).

## Decision
Use **Amazon EKS** (managed Kubernetes) as the orchestration platform, with
services deployed via **Helm charts** (one chart per service, sharing a common
library chart for boilerplate: probes, resource limits, HPA, NetworkPolicy).

**No service mesh (Istio/Linkerd) for now.** mTLS between services, retries,
and circuit breaking are already handled at the application layer
(`pybreaker`/`tenacity`, per CLAUDE.md 2.6) and via Kubernetes NetworkPolicies
for traffic segmentation. A mesh adds meaningful operational complexity
(sidecar injection, control plane, another thing to debug at 2am) that is not
justified yet. Revisit if: (a) the team grows and needs mesh-level traffic
policy without code changes, or (b) mTLS between pods becomes a hard
compliance requirement.

Ingress: **AWS Load Balancer Controller** (ALB Ingress) at the cluster edge,
terminating TLS, routing to the API Gateway/BFF service, which is the single
entry point per ARCHITECTURE.md.

## Considered Alternatives
- **ECS/Fargate** — simpler operationally (no control plane to manage,
  no node group patching), but weaker ecosystem fit for the CQRS/event-driven
  patterns already chosen (fewer off-the-shelf operators for things like
  RabbitMQ, Qdrant) and less transferable Kubernetes experience. Rejected, but
  documented as the pragmatic fallback if EKS operational overhead proves too
  high for a solo maintainer — see Follow-up actions.
- **Self-managed Kubernetes (kOps/kubeadm on EC2)** — full control, but the
  operational burden of managing the control plane is not worth it versus a
  managed offering at this scale. Rejected.
- **Istio service mesh from day one** — rejected per Decision; premature for
  current scale and team size.

## Consequences
### Positive
- Managed control plane reduces operational burden versus self-managed K8s.
- Rich ecosystem: Helm, External Secrets Operator, cluster-autoscaler,
  Prometheus Operator, all have first-class EKS support.
- HPA per service gives independent scaling matching the per-service
  deployability requirement.

### Negative / Trade-offs
- EKS control plane + node costs are non-trivial even at low traffic — see
  `docs/cost-management.md` for mitigations (Fargate profiles for low-traffic
  services, spot instances for non-critical workloads, scale-to-zero for
  non-prod environments outside working hours).
- Kubernetes has a real learning curve; agents and the human maintainer must
  follow `.claude/skills/containerization/SKILL.md` and
  `docs/containerization-and-orchestration.md` strictly to avoid
  misconfiguration (missing resource limits, missing probes).
- No mesh means mTLS between services is not yet enforced at the network
  layer — tracked as a security backlog item, not blocking for MVP since all
  cross-service traffic stays inside the cluster's private network.

### Follow-up actions
- If solo-maintainer operational load on EKS becomes unsustainable, propose
  ADR-0006-revision migrating to ECS/Fargate — the hexagonal/container-based
  design makes this a deployment-layer change only, not an application
  rewrite.
- Re-evaluate service mesh need once more than 2-3 people operate the system.

## References
- ADR-0003 (microservices per domain)
- ADR-0002 (CQRS and event sourcing scope)
- `docs/containerization-and-orchestration.md`
- `docs/cost-management.md`
