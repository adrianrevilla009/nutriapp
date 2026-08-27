{{/*
`.Values.service.additionalPorts` (optional) mirrors _deployment.tpl's
same key — each entry becomes an additional Service port, targeting the
matching named container port by name (not by number), so the Service and
Deployment can never drift apart on which containerPort a given name
means. See _deployment.tpl's header comment for the motivating use case.
*/}}
{{- define "nutriapp-lib.service" -}}
{{- $service := .Values.service | default dict }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "nutriapp-lib.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "nutriapp-lib.labels" . | nindent 4 }}
spec:
  type: {{ $service.type | default "ClusterIP" }}
  ports:
    - port: {{ $service.port | default 8000 }}
      targetPort: http
      protocol: TCP
      name: http
    {{- range $service.additionalPorts }}
    - port: {{ required "service.additionalPorts[].port is required" .port }}
      targetPort: {{ required "service.additionalPorts[].name is required" .name }}
      protocol: TCP
      name: {{ .name }}
    {{- end }}
  selector:
    {{- include "nutriapp-lib.selectorLabels" . | nindent 4 }}
{{- end -}}
