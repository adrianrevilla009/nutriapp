"""ExportOutcome -- the `outcome` recorded on every `export_audit_log` row
(docs/observability-and-audit.md section 4.2: "outcome (success/failure)").

`REJECTED` is this service's own, more specific realization of a
non-success outcome for a request stopped by a pre-condition gate
(entitlement check or request validation) before any report data was
read -- distinct from a hypothetical unexpected `FAILURE` (e.g. a
downstream I/O error surfacing after the gate passed). Security review
found that rejected/probing attempts against Pro-gated export data were
never audited at all (docs/observability-and-audit.md section 4.1 mandates
auditing "data export requests", not just successful ones) -- this value
object exists so `GetReportHandler` can record that fact with the same
type-safety as a successful export, rather than a free-form string.
"""

from __future__ import annotations

from enum import Enum


class ExportOutcome(str, Enum):
    SUCCESS = "success"
    REJECTED = "rejected"
