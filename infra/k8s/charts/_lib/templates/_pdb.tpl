{{/*
_pdb.tpl — PodDisruptionBudget, guarantees a minimum number of replicas
survive voluntary disruptions (node drains, cluster upgrades) per
docs/containerization-and-orchestration.md section 3.2.
*/}}

{{- define "nutriapp-lib.pdb" -}}
{{- $pdb := .Values.pdb | default dict }}
{{- if $pdb.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "nutriapp-lib.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "nutriapp-lib.labels" . | nindent 4 }}
spec:
  {{- if $pdb.minAvailable }}
  minAvailable: {{ $pdb.minAvailable }}
  {{- else }}
  maxUnavailable: {{ $pdb.maxUnavailable | default 1 }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "nutriapp-lib.selectorLabels" . | nindent 6 }}
{{- end }}
{{- end -}}
