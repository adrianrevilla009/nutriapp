# infra/k8s/images/db-provision/Dockerfile
#
# Shared utility image for infra/k8s/charts/_lib's `_db-provision-job.tpl`
# Helm hook (platform-infra plan section 9.1): every service's
# pre-install/pre-upgrade Job that creates its own logical database/role
# inside the shared RDS instance runs this same image. Not a NutriApp
# "service" in the CLAUDE.md section 2.2 sense — a single shared platform
# utility, reused unchanged by every future service's db-provision Job.
#
# Needs exactly what infra/k8s/charts/_lib/templates/_db-provision-job.tpl's
# embedded provision.sh script calls: `psql`, `aws` (Secrets Manager
# get/put), and `python3` (stdlib only — json, secrets — no extra packages).

FROM python:3.12-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir awscli~=1.34 \
    && useradd --uid 1000 --create-home --shell /usr/sbin/nologin dbprovision

USER dbprovision
WORKDIR /home/dbprovision

# No ENTRYPOINT/CMD needed: the Job (infra/k8s/charts/_lib/templates/_db-provision-job.tpl)
# always sets `command: ["/bin/sh", "/scripts/provision.sh"]` explicitly,
# mounting the script from a ConfigMap — this image only needs to provide
# the three CLI tools on PATH.
