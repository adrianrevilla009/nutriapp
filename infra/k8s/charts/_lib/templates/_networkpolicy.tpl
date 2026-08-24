{{/*
_networkpolicy.tpl — per-service ALLOW rules layered on top of the
namespace-wide default-deny-ingress NetworkPolicy created once per
environment by infra/terraform/environments/<env>/namespace.tf. Each
service supplies exactly the ingress rules it needs (from Kong, from
named peer services, from Prometheus for scraping) via
.Values.networkPolicy.ingressRules — raw NetworkPolicy `ingress` entries,
merged in as-is, per docs/containerization-and-orchestration.md section
3.2.
*/}}

{{- define "nutriapp-lib.networkPolicy" -}}
{{- $networkPolicy := .Values.networkPolicy | default dict }}
{{- if $networkPolicy.enabled }}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "nutriapp-lib.fullname" . }}-allow
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "nutriapp-lib.labels" . | nindent 4 }}
spec:
  podSelector:
    matchLabels:
      {{- include "nutriapp-lib.selectorLabels" . | nindent 6 }}
  policyTypes:
    - Ingress
  ingress:
    {{- toYaml (required "networkPolicy.ingressRules is required when networkPolicy.enabled=true — a service chart must state its explicit allow rules, never rely on an implicit allow-all" $networkPolicy.ingressRules) | nindent 4 }}
{{- end }}
{{- end -}}
