{{/*
_hpa.tpl — CPU-based by default; a service needing a custom metric (e.g.
food-recognition-service on queue depth) supplies
.Values.hpa.customMetrics (raw HPA `metrics` entries, merged in as-is)
per docs/containerization-and-orchestration.md section 3.2.
*/}}

{{- define "nutriapp-lib.hpa" -}}
{{- $hpa := .Values.hpa | default dict }}
{{- if $hpa.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "nutriapp-lib.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "nutriapp-lib.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "nutriapp-lib.fullname" . }}
  minReplicas: {{ $hpa.minReplicas | default 2 }}
  maxReplicas: {{ $hpa.maxReplicas | default 5 }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ $hpa.targetCPUUtilizationPercentage | default 70 }}
    {{- if $hpa.targetMemoryUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ $hpa.targetMemoryUtilizationPercentage }}
    {{- end }}
    {{- with $hpa.customMetrics }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
{{- end }}
{{- end -}}
