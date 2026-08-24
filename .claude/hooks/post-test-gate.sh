#!/bin/bash
# PreToolUse guard for the Bash tool, specific to /create-commit and
# /create-pr.
#
# Purpose (specification): CLAUDE.md section 6 requires Test Execution
# (/test-execution) and Test Review (/test-review) to happen before a
# change is committed or a PR is opened. Today that ordering depends on
# the agent following the pipeline voluntarily. This hook is the
# technical backstop: it blocks a commit/PR attempt within a session that
# has not recorded a passing test-execution marker.
#
# This is a specification stub, not a working implementation: the actual
# marker mechanism (e.g. a session-scoped file written by
# /test-execution on success, checked here) is defined during the
# implementation of the identity-service reference pipeline
# (CLAUDE.md section 13), not invented ad hoc by this hook in isolation.
# Until that marker mechanism exists, this hook is documented and present
# but intentionally permissive (always exits 0) so it does not block
# work before the marker mechanism it depends on is actually built.
#
# This hook reads the proposed tool call as JSON from stdin (Claude
# Code's PreToolUse hook contract) and extracts the "command" field.

COMMAND=$(cat | python3 -c "import sys, json; print(json.load(sys.stdin).get('tool_input', {}).get('command', ''))" 2>/dev/null)

# Only act on commands that look like a commit or PR creation attempt.
if echo "$COMMAND" | grep -Eiq "git commit|gh pr create"; then
  # Specification of the intended check (not yet implemented):
  #   1. Look for a session-scoped marker written by /test-execution on a
  #      successful run (e.g. .claude/.session-test-pass, gitignored,
  #      timestamped, tied to the current branch/commit range).
  #   2. If the marker is missing, or older than the latest uncommitted
  #      change, BLOCK with exit 1 and instruct the agent to run
  #      /test-execution and /test-review first.
  #   3. If present and current, exit 0.
  #
  # TODO(implementation): wire the actual marker check here as part of
  # the identity-service reference implementation. Until then this hook
  # is a documented no-op, not a silent gap — see CLAUDE.md section 6.
  exit 0
fi

exit 0
