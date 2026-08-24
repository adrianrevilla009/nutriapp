{{/*
_helpers.tpl — naming and label helpers shared by every other named
template in this library chart. Every consuming chart's templates call
`include "nutriapp-lib.<name>" .` passing their OWN top-level `.`
context directly (not re-scoped under a subchart key) — the values keys
these templates read (image, resources, probes, service, serviceAccount,
hpa, pdb, networkPolicy, dbProvision) are expected at the TOP LEVEL of
the consuming chart's own values.yaml. See README.md.
*/}}

{{- define "nutriapp-lib.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "nutriapp-lib.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "nutriapp-lib.labels" -}}
app.kubernetes.io/name: {{ include "nutriapp-lib.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
nutriapp.io/service: {{ include "nutriapp-lib.name" . }}
{{- end -}}

{{- define "nutriapp-lib.selectorLabels" -}}
app.kubernetes.io/name: {{ include "nutriapp-lib.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "nutriapp-lib.serviceAccountName" -}}
{{- (.Values.serviceAccount | default dict).name | default (include "nutriapp-lib.fullname" .) -}}
{{- end -}}
