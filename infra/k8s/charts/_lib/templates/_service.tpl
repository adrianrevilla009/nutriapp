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
  selector:
    {{- include "nutriapp-lib.selectorLabels" . | nindent 4 }}
{{- end -}}
