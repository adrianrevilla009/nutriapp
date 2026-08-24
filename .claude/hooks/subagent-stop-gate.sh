#!/bin/bash
# SubagentStop hook.
# Runs when a subagent (e.g. identity-agent, core-domain-agent, qa-agent, ...)
# finishes and is about to return its result to the parent session.
#
# Purpose: enforce a minimal quality gate before a subagent's work is
# considered "done" and handed back — specifically, that the subagent did not
# silently skip the human-in-the-loop pipeline defined in CLAUDE.md section 6
# by attempting to commit, push, or open a PR itself.
#
# This hook reads the subagent's transcript/result as JSON from stdin
# (Claude Code's SubagentStop hook contract).

RESULT=$(cat)

# If the subagent's own output claims it committed, pushed, or opened a PR
# without those being explicit, separate commands the human approved
# (/create-commit, /create-pr), flag it for human review rather than silently
# accepting the result.
SUSPICIOUS_PATTERNS="git push|git commit|pull request opened|PR created|pr create"

if echo "$RESULT" | grep -Eiq "$SUSPICIOUS_PATTERNS"; then
  echo "NOTICE: this subagent's result mentions committing, pushing, or" >&2
  echo "opening a PR. Verify this happened only via the explicit" >&2
  echo "/create-commit or /create-pr commands with prior human approval," >&2
  echo "per CLAUDE.md section 6, before accepting this result as final." >&2
  # Non-blocking: this is a notice for the human/parent session to verify,
  # not an automatic hard block, since legitimate summaries may mention
  # these words without having actually executed them.
fi

exit 0
