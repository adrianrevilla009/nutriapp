import Link from "next/link";
import { useTranslations } from "next-intl";
import type { AnalyzePhotoResponse } from "@/schemas/food-recognition";
import { ConfidenceBadge } from "@/components/features/recognition/ConfidenceBadge";

export interface CandidateListProps {
  result: AnalyzePhotoResponse;
}

/**
 * Builds the /search deep link a chosen candidate navigates to (journey 2
 * implementation plan section 1's flow) -- q pre-fills/auto-submits the
 * search, the ai* params carry enough context for /log/[productId] to
 * later construct an ai_detected-sourced LogFoodEntryRequest without any
 * client-side state surviving the navigation.
 */
function candidateSearchHref(
  analysisId: string,
  candidateName: string,
  portionMinG: number,
  portionMaxG: number,
): string {
  const params = new URLSearchParams({
    q: candidateName,
    aiAnalysisId: analysisId,
    aiCandidateName: candidateName,
    aiPortionMinG: String(portionMinG),
    aiPortionMaxG: String(portionMaxG),
  });
  return `/search?${params.toString()}`;
}

/**
 * Renders up to 3 AI-detected candidates (never more, never silently
 * collapsed to one) plus a manual-search fallback that is ALWAYS present,
 * regardless of status -- accessibility-standards SKILL.md's requirement
 * that this flow never assume the user can visually review the photo or
 * candidates: every candidate's accessible name carries its full
 * decision-relevant content (name, confidence %, portion range) as text.
 */
export function CandidateList({ result }: CandidateListProps) {
  const t = useTranslations("photoLog");

  const heading =
    result.status === "detected"
      ? t("candidatesDetectedHeading")
      : result.status === "uncertain"
        ? t("candidatesUncertainHeading")
        : t("unavailableHeading");

  return (
    <div className="page">
      <h2>{heading}</h2>
      {result.status === "unavailable" ? <p>{t("unavailableBody")}</p> : null}
      {result.candidates.length > 0 ? (
        <ul className="result-list" aria-label={t("candidatesListLabel")}>
          {result.candidates.map((candidate, index) => {
            const percent = Math.round(candidate.confidence * 100);
            const accessibleName = t("candidateAccessibleName", {
              name: candidate.name,
              percent,
              min: candidate.portion_range_min_g,
              max: candidate.portion_range_max_g,
            });
            return (
              <li key={`${candidate.name}-${index}`} className="result-item">
                <div>
                  <strong>{candidate.name}</strong>
                  <p>
                    <ConfidenceBadge confidence={candidate.confidence} />
                    {" — "}
                    {t("portionRange", {
                      min: candidate.portion_range_min_g,
                      max: candidate.portion_range_max_g,
                    })}
                  </p>
                </div>
                <Link
                  href={candidateSearchHref(
                    result.analysis_id,
                    candidate.name,
                    candidate.portion_range_min_g,
                    candidate.portion_range_max_g,
                  )}
                  className="btn btn-primary"
                  aria-label={accessibleName}
                >
                  {t("useThisCandidate")}
                </Link>
              </li>
            );
          })}
        </ul>
      ) : null}
      {/* Always present, not conditional on status -- media-recognition-
          conventions SKILL.md: the user is always free to reject a
          plausible-looking suggestion, not just a low-confidence one. */}
      <Link href="/search" className="btn btn-secondary">
        {t("searchManually")}
      </Link>
    </div>
  );
}
