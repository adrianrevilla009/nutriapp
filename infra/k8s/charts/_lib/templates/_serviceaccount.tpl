{{/*
_serviceaccount.tpl — ServiceAccount with the IRSA annotation (ADR-0007).
serviceAccount.irsaRoleArn is REQUIRED — a service without a scoped IRSA
role cannot reach its own secrets, per docs/secrets-management.md section
4 ("no shared 'god' IAM role that can read every secret in the account").
*/}}

{{- define "nutriapp-lib.serviceAccount" -}}
{{- $serviceAccount := required "serviceAccount is required (must at minimum set serviceAccount.irsaRoleArn — ADR-0007)" .Values.serviceAccount }}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "nutriapp-lib.serviceAccountName" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "nutriapp-lib.labels" . | nindent 4 }}
  annotations:
    eks.amazonaws.com/role-arn: {{ required "serviceAccount.irsaRoleArn is required (IRSA annotation, ADR-0007)" $serviceAccount.irsaRoleArn | quote }}
    {{- with $serviceAccount.annotations }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
automountServiceAccountToken: {{ $serviceAccount.automount | default true }}
{{- end -}}
