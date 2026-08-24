{{/*
_probes.tpl — standard liveness/readiness/startup probes, hitting each
service's /health and /ready endpoints per
docs/containerization-and-orchestration.md section 3.1. A service that is
up but not ready (e.g. still connecting to its database) must not
receive traffic — hence readiness is checked separately from liveness.
*/}}

{{- define "nutriapp-lib.livenessProbe" -}}
{{- $liveness := (.Values.probes | default dict).liveness | default dict -}}
httpGet:
  path: {{ $liveness.path | default "/health" }}
  port: http
initialDelaySeconds: {{ $liveness.initialDelaySeconds | default 10 }}
periodSeconds: {{ $liveness.periodSeconds | default 15 }}
timeoutSeconds: {{ $liveness.timeoutSeconds | default 3 }}
failureThreshold: {{ $liveness.failureThreshold | default 3 }}
{{- end -}}

{{- define "nutriapp-lib.readinessProbe" -}}
{{- $readiness := (.Values.probes | default dict).readiness | default dict -}}
httpGet:
  path: {{ $readiness.path | default "/ready" }}
  port: http
initialDelaySeconds: {{ $readiness.initialDelaySeconds | default 5 }}
periodSeconds: {{ $readiness.periodSeconds | default 10 }}
timeoutSeconds: {{ $readiness.timeoutSeconds | default 3 }}
failureThreshold: {{ $readiness.failureThreshold | default 3 }}
{{- end -}}

{{/*
startupProbe: opt-in (Values.probes.startup.enabled), for services with
expensive cold starts (nutrition-assistant-service, food-recognition-service
loading model weights) per docs/containerization-and-orchestration.md
section 5 — a generous startupProbe protects them from being killed
during legitimate warm-up.
*/}}
{{- define "nutriapp-lib.startupProbe" -}}
{{- $probes := .Values.probes | default dict }}
{{- $startup := $probes.startup | default dict }}
{{- $readiness := $probes.readiness | default dict -}}
httpGet:
  path: {{ $startup.path | default $readiness.path | default "/ready" }}
  port: http
initialDelaySeconds: {{ $startup.initialDelaySeconds | default 0 }}
periodSeconds: {{ $startup.periodSeconds | default 10 }}
failureThreshold: {{ $startup.failureThreshold | default 30 }}
{{- end -}}
