"""Status vocabulary for a photo analysis attempt and its published
`FoodPhotoAnalyzed` event (implementation plan section 1, acceptance
criterion 2 / section 5).

- "detected": at least one candidate met the confidence threshold.
- "uncertain": candidates exist but all fall below the confidence
  threshold -- still returned to the caller, never discarded, but the
  response makes explicit that no confident match was found.
- "unavailable": the vision provider could not be reached (circuit open,
  retries exhausted, timeout), returned an unparseable response, or the
  feature is disabled via its feature flag -- manual entry is the only
  fallback, never a stale/cached guess presented as fresh.
"""

from __future__ import annotations

from typing import Literal

AnalysisStatus = Literal["detected", "uncertain", "unavailable"]
