.PHONY: help dev-keys up down logs test test-identity test-profile test-diary lint fmt migrate-identity migrate-profile migrate-diary

help:
	@echo "Targets: dev-keys, up, down, logs, test, test-identity, test-profile, test-diary, lint, fmt, migrate-identity, migrate-profile, migrate-diary"

# Generates a local-dev-only RSA key pair for identity-service's JWT
# signing (ADR-0022). Production keys are provisioned by the
# platform-infra `secrets` Terraform module (tls_private_key resource),
# never committed here.
dev-keys:
	mkdir -p .dev-keys/identity
	openssl genrsa -out .dev-keys/identity/identity_jwt_private_key.pem 2048
	openssl rsa -in .dev-keys/identity/identity_jwt_private_key.pem \
		-pubout -out .dev-keys/identity/identity_jwt_public_key.pem
	@echo "Dev JWT key pair written to .dev-keys/identity/ (gitignored)."

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f

# Runs a single service's test suite. Usage: make test SERVICE=identity-service
test:
	cd services/$(SERVICE) && python -m pytest tests/unit tests/contract tests/integration \
		--cov=domain --cov=application --cov=infrastructure --cov-report=term-missing

test-identity:
	$(MAKE) test SERVICE=identity-service

test-profile:
	$(MAKE) test SERVICE=profile-service

test-diary:
	$(MAKE) test SERVICE=diary-service

lint:
	pre-commit run --all-files

fmt:
	cd services/$(SERVICE) && ruff format .

migrate-identity:
	cd services/identity-service && alembic upgrade head

migrate-profile:
	cd services/profile-service && alembic upgrade head

migrate-diary:
	cd services/diary-service && alembic upgrade head
