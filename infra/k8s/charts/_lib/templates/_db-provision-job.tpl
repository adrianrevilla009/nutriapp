{{/*
_db-provision-job.tpl — creates a service's OWN logical database + role
inside the shared RDS instance, from inside the cluster, as a Helm
pre-install/pre-upgrade hook Job.

WHY THIS EXISTS (implementation plan section 9.1): Terraform's
`postgresql` provider needs network reachability into the VPC's private
subnet, which neither a human's laptop nor a CI runner has by default (no
bastion/VPN — implementation plan section 9.3 resolved EKS endpoint
access differently, and deliberately does not stand up a bastion for
this either). Per-service database/role creation therefore happens here,
in-cluster, rather than as a Terraform `postgresql_database` /
`postgresql_role` resource. Do not revert to a Terraform-level database
resource for this — see infra/terraform/modules/rds/main.tf's header
comment for the same note from the other direction.

IDEMPOTENCY (mandatory — CLAUDE.md section 2.4 applies the same
principle here as to message consumers): the embedded script only
CREATEs the role/database if they do not already exist, and only writes
a freshly generated password to Secrets Manager on that first-creation
path. Re-running on every `helm upgrade` must never rotate or clobber an
already-issued credential a running app pod depends on.

REQUIRED VALUES (a consuming chart, e.g. identity-service's, sets these
— typically sourced from this platform layer's Terraform outputs,
module.secrets.db_provision_irsa_role_arns / db_credential_secret_arns /
module.rds.* in infra/terraform/environments/dev/main.tf):
  dbProvision.enabled                 bool, default false (opt-in)
  dbProvision.image.repository/tag    an image with `psql` + `aws` CLI
  dbProvision.awsRegion               string
  dbProvision.rdsHost / rdsPort       shared RDS instance connection info
  dbProvision.rdsAdminDatabase        default "postgres"
  dbProvision.rdsMasterSecretArn      Secrets Manager ARN, master creds
  dbProvision.dbCredentialSecretArn   Secrets Manager ARN, THIS service's
                                       own (empty-container) db-credentials
                                       secret, created by
                                       infra/terraform/modules/secrets
  dbProvision.databaseName            defaults to the chart name
  dbProvision.roleName                defaults to the chart name
  dbProvision.irsaRoleArn             IRSA role ARN scoped to exactly the
                                       two secrets above (module.secrets.
                                       db_provision_irsa_role_arns[svc])
*/}}

{{- define "nutriapp-lib.dbProvisionJob" -}}
{{- $dbProvision := .Values.dbProvision | default dict }}
{{- if $dbProvision.enabled }}
{{- $dbProvisionImage := $dbProvision.image | default dict }}
{{- $databaseName := $dbProvision.databaseName | default (include "nutriapp-lib.name" . | replace "-" "_") }}
{{- $roleName := $dbProvision.roleName | default (include "nutriapp-lib.name" . | replace "-" "_") }}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "nutriapp-lib.name" . }}-db-provision
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "nutriapp-lib.labels" . | nindent 4 }}
  annotations:
    eks.amazonaws.com/role-arn: {{ required "dbProvision.irsaRoleArn is required" $dbProvision.irsaRoleArn | quote }}
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-10"
    "helm.sh/hook-delete-policy": before-hook-creation
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "nutriapp-lib.name" . }}-db-provision-script
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "nutriapp-lib.labels" . | nindent 4 }}
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-10"
    "helm.sh/hook-delete-policy": before-hook-creation
data:
  provision.sh: |
    #!/bin/sh
    set -eu

    echo "Fetching RDS master credentials from Secrets Manager..."
    MASTER_JSON=$(aws secretsmanager get-secret-value \
      --region "${AWS_REGION}" \
      --secret-id "${RDS_MASTER_SECRET_ARN}" \
      --query SecretString --output text)
    MASTER_USER=$(echo "${MASTER_JSON}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["username"])')
    MASTER_PASS=$(echo "${MASTER_JSON}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["password"])')

    export PGPASSWORD="${MASTER_PASS}"
    CONN="-h ${RDS_HOST} -p ${RDS_PORT} -U ${MASTER_USER} -d ${RDS_ADMIN_DATABASE} -v ON_ERROR_STOP=1"

    ROLE_EXISTS=$(psql ${CONN} -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_ROLE}'")

    if [ "${ROLE_EXISTS}" = "1" ]; then
      echo "Role ${DB_ROLE} already exists — skipping creation and password rotation (idempotent no-op)."
      exit 0
    fi

    echo "Role ${DB_ROLE} does not exist — creating role + database (first run)."
    NEW_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')

    psql ${CONN} -c "CREATE ROLE \"${DB_ROLE}\" WITH LOGIN PASSWORD '${NEW_PASSWORD}';"
    psql ${CONN} -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_ROLE}\";"
    psql ${CONN} -c "REVOKE ALL ON DATABASE \"${DB_NAME}\" FROM PUBLIC;"

    # Append-only audit-log privilege separation (CLAUDE.md §2.8,
    # observability-audit SKILL.md): a NOLOGIN role the app can `SET ROLE`
    # into for audit writes only. Created here (running as RDS master,
    # which has CREATEROLE) rather than in the service's own Alembic
    # migration, because ${DB_ROLE} itself is not granted CREATEROLE —
    # only the role's *owner* (master) can create it and grant membership.
    # The migration that later creates the actual audit_log table only
    # needs to GRANT/REVOKE table-level privileges to this already-existing
    # role, which table ownership alone is sufficient for.
    AUDIT_WRITER_ROLE="${DB_ROLE}_audit_writer"
    psql ${CONN} -c "CREATE ROLE \"${AUDIT_WRITER_ROLE}\" NOLOGIN;"
    psql ${CONN} -c "GRANT \"${AUDIT_WRITER_ROLE}\" TO \"${DB_ROLE}\";"

    DATABASE_URL="${DB_URL_SCHEME}://${DB_ROLE}:${NEW_PASSWORD}@${RDS_HOST}:${RDS_PORT}/${DB_NAME}"

    SECRET_PAYLOAD=$(python3 -c "import json; print(json.dumps({\"username\": \"${DB_ROLE}\", \"password\": \"${NEW_PASSWORD}\", \"database\": \"${DB_NAME}\", \"host\": \"${RDS_HOST}\", \"port\": ${RDS_PORT}, \"database_url\": \"${DATABASE_URL}\"}))")

    aws secretsmanager put-secret-value \
      --region "${AWS_REGION}" \
      --secret-id "${DB_CREDENTIAL_SECRET_ARN}" \
      --secret-string "${SECRET_PAYLOAD}"

    echo "Role ${DB_ROLE} and database ${DB_NAME} created; credentials written to ${DB_CREDENTIAL_SECRET_ARN}."
---
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "nutriapp-lib.name" . }}-db-provision
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "nutriapp-lib.labels" . | nindent 4 }}
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-5"
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
spec:
  backoffLimit: 2
  activeDeadlineSeconds: 300
  template:
    metadata:
      labels:
        {{- include "nutriapp-lib.selectorLabels" . | nindent 8 }}
        nutriapp.io/component: db-provision
    spec:
      restartPolicy: Never
      serviceAccountName: {{ include "nutriapp-lib.name" . }}-db-provision
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
        - name: db-provision
          image: "{{ required "dbProvision.image.repository is required" $dbProvisionImage.repository }}:{{ required "dbProvision.image.tag is required" $dbProvisionImage.tag }}"
          command: ["/bin/sh", "/scripts/provision.sh"]
          env:
            - name: AWS_REGION
              value: {{ required "dbProvision.awsRegion is required" $dbProvision.awsRegion | quote }}
            - name: RDS_HOST
              value: {{ required "dbProvision.rdsHost is required" $dbProvision.rdsHost | quote }}
            - name: RDS_PORT
              value: {{ $dbProvision.rdsPort | default 5432 | quote }}
            - name: RDS_ADMIN_DATABASE
              value: {{ $dbProvision.rdsAdminDatabase | default "postgres" | quote }}
            - name: DB_URL_SCHEME
              value: {{ $dbProvision.urlScheme | default "postgresql" | quote }}
            - name: RDS_MASTER_SECRET_ARN
              value: {{ required "dbProvision.rdsMasterSecretArn is required" $dbProvision.rdsMasterSecretArn | quote }}
            - name: DB_CREDENTIAL_SECRET_ARN
              value: {{ required "dbProvision.dbCredentialSecretArn is required" $dbProvision.dbCredentialSecretArn | quote }}
            - name: DB_NAME
              value: {{ $databaseName | quote }}
            - name: DB_ROLE
              value: {{ $roleName | quote }}
          volumeMounts:
            - name: script
              mountPath: /scripts
              readOnly: true
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
      volumes:
        - name: script
          configMap:
            name: {{ include "nutriapp-lib.name" . }}-db-provision-script
            defaultMode: 0755
{{- end }}
{{- end -}}
