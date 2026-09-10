import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { renderWithProviders } from "./test-utils";
import { CandidateList } from "@/components/features/recognition/CandidateList";
import {
  analyzePhotoDetectedFixture,
  analyzePhotoUncertainFixture,
  analyzePhotoUnavailableFixture,
} from "../fixtures/food-recognition.fixtures";

describe("CandidateList", () => {
  it("renders exactly 3 candidates for a 'detected' result, each with an accessible name carrying name/confidence/portion", () => {
    renderWithProviders(<CandidateList result={analyzePhotoDetectedFixture} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);

    const first = analyzePhotoDetectedFixture.candidates[0]!;
    const percent = Math.round(first.confidence * 100);
    const link = screen.getByRole("link", {
      name: new RegExp(
        `${first.name}.*${percent}%.*${first.portion_range_min_g}.*${first.portion_range_max_g}`,
        "i",
      ),
    });
    expect(link).toBeInTheDocument();
  });

  it("renders distinct heading copy for 'uncertain' vs 'detected'", () => {
    const { unmount } = renderWithProviders(<CandidateList result={analyzePhotoDetectedFixture} />);
    const detectedHeading = screen.getByRole("heading", { level: 2 }).textContent;
    unmount();

    renderWithProviders(<CandidateList result={analyzePhotoUncertainFixture} />);
    const uncertainHeading = screen.getByRole("heading", { level: 2 }).textContent;

    expect(detectedHeading).not.toBe(uncertainHeading);
  });

  it("renders no candidate items for 'unavailable', only the manual-search fallback", () => {
    renderWithProviders(<CandidateList result={analyzePhotoUnavailableFixture} />);
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /search manually/i })).toBeInTheDocument();
  });

  it.each([
    { label: "detected", fixture: analyzePhotoDetectedFixture },
    { label: "uncertain", fixture: analyzePhotoUncertainFixture },
    { label: "unavailable", fixture: analyzePhotoUnavailableFixture },
  ])("the 'search manually' action is present in every status ($label)", ({ fixture }) => {
    renderWithProviders(<CandidateList result={fixture} />);
    const link = screen.getByRole("link", { name: /search manually/i });
    expect(link).toHaveAttribute("href", "/search");
    // No stale AI context ever leaks into the manual path.
    expect(link.getAttribute("href")).not.toContain("ai");
  });

  it("clicking a candidate links to /search with q/aiAnalysisId/aiPortionMinG/aiPortionMaxG", () => {
    renderWithProviders(<CandidateList result={analyzePhotoDetectedFixture} />);
    const first = analyzePhotoDetectedFixture.candidates[0]!;
    const percent = Math.round(first.confidence * 100);
    const link = screen.getByRole("link", {
      name: new RegExp(`${first.name}.*${percent}%`, "i"),
    });
    const href = link.getAttribute("href")!;
    // URLSearchParams encodes a space as "+", not "%20".
    expect(href).toContain(`q=${first.name.replace(/ /g, "+")}`);
    expect(href).toContain(`aiAnalysisId=${analyzePhotoDetectedFixture.analysis_id}`);
    expect(href).toContain(`aiPortionMinG=${first.portion_range_min_g}`);
    expect(href).toContain(`aiPortionMaxG=${first.portion_range_max_g}`);
  });

  it("confidence is rendered as literal digit text for every candidate, never color-only", () => {
    renderWithProviders(<CandidateList result={analyzePhotoDetectedFixture} />);
    for (const candidate of analyzePhotoDetectedFixture.candidates) {
      const percent = Math.round(candidate.confidence * 100);
      expect(screen.getByText(new RegExp(`confidence:\\s*${percent}%`, "i"))).toBeInTheDocument();
    }
  });

  it("every candidate is reachable via keyboard (a real, focusable link)", () => {
    renderWithProviders(<CandidateList result={analyzePhotoDetectedFixture} />);
    const links = screen.getAllByRole("link");
    // 3 candidates + the manual-search fallback.
    expect(links.length).toBeGreaterThanOrEqual(4);
    for (const link of links) {
      expect(link.tagName).toBe("A");
      expect(link).toHaveAttribute("href");
    }
  });

  it("has no critical/serious axe violations in the detected state", async () => {
    const { container } = renderWithProviders(
      <CandidateList result={analyzePhotoDetectedFixture} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("has no critical/serious axe violations in the unavailable state", async () => {
    const { container } = renderWithProviders(
      <CandidateList result={analyzePhotoUnavailableFixture} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
