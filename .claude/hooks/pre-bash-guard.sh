#!/bin/bash
# Pre-tool-use guard for the Bash tool.
# Blocks destructive or high-risk commands per CLAUDE.md section 7
# (Non-negotiable Guardrails). A blocked command requires explicit manual
# confirmation from the human before it can proceed.
#
# This hook reads the proposed tool call as JSON from stdin (Claude Code's
# PreToolUse hook contract) and extracts the "command" field.

COMMAND=$(cat | python3 -c "import sys, json; print(json.load(sys.stdin).get('tool_input', {}).get('command', ''))" 2>/dev/null)

# Patterns considered destructive or requiring explicit human confirmation
# before execution, per CLAUDE.md section 7:
#   - git push / force-push / branch deletion
#   - destructive database operations (DROP, TRUNCATE)
#   - migration commands (may contain destructive changes; see
#     .claude/skills/database-migrations/SKILL.md)
#   - recursive/forced filesystem deletion
#   - direct writes to .claude/settings.json (hook/permission changes)
#   - terraform/kubectl/AWS CLI mutations against real infrastructure (see
#     pre-terraform-guard.sh for the Terraform-specific hook; these patterns
#     are a defense-in-depth backstop in case a mutating command is issued
#     via a generic Bash call rather than a `terraform` invocation directly)
#   - bulk/production-scale scraping runs and user-data deletion commands
BLOCKED_PATTERNS="git push|git branch -D|git branch --delete --force|rm -rf|DROP TABLE|DROP DATABASE|DROP COLUMN|TRUNCATE|alembic upgrade|alembic downgrade|migrate|\.claude/settings\.json|terraform apply|terraform destroy|kubectl delete|kubectl.*--all-namespaces.*delete|aws.*delete-|aws.*terminate-|helm uninstall|helm delete"

if echo "$COMMAND" | grep -Eiq "$BLOCKED_PATTERNS"; then
  echo "BLOCKED: potentially destructive command detected." >&2
  echo "Command: $COMMAND" >&2
  echo "This action requires explicit human confirmation before it can run." >&2
  echo "See CLAUDE.md section 7 (Non-negotiable Guardrails)." >&2
  exit 1
fi

exit 0
