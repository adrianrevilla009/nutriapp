#!/bin/bash
# Pre-tool-use guard specifically for Terraform commands.
# Per docs/terraform-and-infrastructure.md section 4 and CLAUDE.md section 7:
# `terraform plan` (and read-only commands like `validate`/`fmt`/`show`) are
# always allowed — they are side-effect-free against real infrastructure.
# `terraform apply` and `terraform destroy` are NEVER executed by an agent,
# under any flag combination (including `-auto-approve`), and require the
# human to run them directly or approve a manual-trigger CI workflow.
#
# This hook reads the proposed tool call as JSON from stdin (Claude Code's
# PreToolUse hook contract) and extracts the "command" field.

COMMAND=$(cat | python3 -c "import sys, json; print(json.load(sys.stdin).get('tool_input', {}).get('command', ''))" 2>/dev/null)

# Only act on commands that actually invoke terraform/tofu.
if echo "$COMMAND" | grep -Eiq "\b(terraform|tofu)\b"; then
  if echo "$COMMAND" | grep -Eiq "\b(terraform|tofu)\b.*\b(apply|destroy)\b"; then
    echo "BLOCKED: terraform apply/destroy detected." >&2
    echo "Command: $COMMAND" >&2
    echo "Agents never run terraform apply or destroy, with or without" >&2
    echo "-auto-approve. Run 'terraform plan' instead and present the plan" >&2
    echo "output for explicit human review and execution." >&2
    echo "See docs/terraform-and-infrastructure.md section 4 and" >&2
    echo "CLAUDE.md section 7 (Non-negotiable Guardrails)." >&2
    exit 1
  fi
fi

exit 0
