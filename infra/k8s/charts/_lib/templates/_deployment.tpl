{{/*
_deployment.tpl — the mandatory-fields Deployment
(.claude/skills/containerization/SKILL.md): resources.requests/limits,
liveness+readiness probes, ServiceAccount with IRSA. `required` guards on
image and resources fail the render (and thus `helm lint`/`helm
template`/`helm install`) rather than silently deploying an unbounded
or untraceable container.
*/}}

{{- define "nutriapp-lib.deployment" -}}
{{- $rollingUpdate := .Values.rollingUpdate | default dict }}
{{- $securityContext := .Values.securityContext | default dict }}
{{- $service := .Values.service | default dict }}
{{- $image := required "image is required" .Values.image }}
{{- $resources := required "resources is required (.claude/skills/containerization/SKILL.md — requests and limits are mandatory)" .Values.resources }}
{{- $probes := .Values.probes | default dict }}
{{- $startup := $probes.startup | default dict }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "nutriapp-lib.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "nutriapp-lib.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount | default 1 }}
  revisionHistoryLimit: {{ .Values.revisionHistoryLimit | default 5 }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: {{ $rollingUpdate.maxSurge | default 1 }}
      maxUnavailable: {{ $rollingUpdate.maxUnavailable | default 0 }}
  selector:
    matchLabels:
      {{- include "nutriapp-lib.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "nutriapp-lib.labels" . | nindent 8 }}
        {{- with .Values.podLabels }}
        {{- toYaml . | nindent 8 }}
        {{- end }}
      annotations:
        {{- with .Values.podAnnotations }}
        {{- toYaml . | nindent 8 }}
        {{- end }}
    spec:
      serviceAccountName: {{ include "nutriapp-lib.serviceAccountName" . }}
      securityContext:
        runAsNonRoot: true
        runAsUser: {{ $securityContext.runAsUser | default 1000 }}
        fsGroup: {{ $securityContext.fsGroup | default 1000 }}
      containers:
        - name: {{ include "nutriapp-lib.name" . }}
          image: "{{ required "image.repository is required" $image.repository }}:{{ required "image.tag is required (git SHA, never latest — docs/containerization-and-orchestration.md section 1)" $image.tag }}"
          imagePullPolicy: {{ $image.pullPolicy | default "IfNotPresent" }}
          ports:
            - name: http
              containerPort: {{ $service.port | default 8000 }}
              protocol: TCP
          {{- with .Values.envFrom }}
          envFrom:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- with .Values.env }}
          env:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          resources:
            requests:
              cpu: {{ required "resources.requests.cpu is required (.claude/skills/containerization/SKILL.md)" (dig "requests" "cpu" nil $resources) | quote }}
              memory: {{ required "resources.requests.memory is required (.claude/skills/containerization/SKILL.md)" (dig "requests" "memory" nil $resources) | quote }}
            limits:
              cpu: {{ required "resources.limits.cpu is required (.claude/skills/containerization/SKILL.md)" (dig "limits" "cpu" nil $resources) | quote }}
              memory: {{ required "resources.limits.memory is required (.claude/skills/containerization/SKILL.md)" (dig "limits" "memory" nil $resources) | quote }}
          livenessProbe:
            {{- include "nutriapp-lib.livenessProbe" . | nindent 12 }}
          readinessProbe:
            {{- include "nutriapp-lib.readinessProbe" . | nindent 12 }}
          {{- if $startup.enabled }}
          startupProbe:
            {{- include "nutriapp-lib.startupProbe" . | nindent 12 }}
          {{- end }}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: {{ $securityContext.readOnlyRootFilesystem | default true }}
            capabilities:
              drop: ["ALL"]
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
{{- end -}}
