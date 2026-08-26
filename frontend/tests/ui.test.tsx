import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { LandingHero } from "@/components/landing/LandingHero";
import { ThreeDImageCard, calculateTilt } from "@/components/images/ThreeDImageCard";
import { CandidateList } from "@/components/matching/CandidateList";
import { MismatchGuardPanel } from "@/components/matching/MismatchGuardPanel";
import { NoConfidentMatch } from "@/components/matching/NoConfidentMatch";
import { ReviewPanel } from "@/components/review/ReviewPanel";
import { EvaluationDashboardView } from "@/components/evaluation/EvaluationDashboardView";
import { ErrorState } from "@/components/ui/AsyncState";
import type { CandidateDecision, EvaluationRun, RecommendationDetail } from "@/types/api";

const decision: CandidateDecision = {
  recommendation_id: "recommendation-1", image_id: "image-1", rank: 1,
  similarity_score: 0.93, vision_confidence: 0.96,
  decision: "SUBJECT_MISMATCH", reason_code: "SUBJECT_MISMATCH",
  explanation: "Expected red fox, but the image was classified as gray wolf.",
};

const detail: RecommendationDetail = {
  id: "recommendation-1", run_id: "run-1", rank: 1, similarity_score: .9,
  vision_confidence: .95, image_subject: "red fox", image_subject_code: "red_fox",
  image_category: "animal", image_tags: ["winter"], expected_subject: "red fox",
  expected_category: "animal", required_tags: [], metadata_valid: true,
  is_low_confidence: false, guard_decision: "ACCEPTED", guard_reason_code: "ACCEPTED",
  explanation: "Subject and category match.", human_review_permitted: true,
  human_review_state: "pending", current_review: null, created_at: "2026-08-25T12:00:00Z",
  post: { id: "post-1", title: "Foxes", body: "Winter foxes", expected_subject: "red fox", expected_category: "animal", required_tags: [], created_at: "2026-08-25T12:00:00Z", updated_at: "2026-08-25T12:00:00Z" },
  candidate_image: { id: "image-1", filename: "fox.png", storage_key: "safe/fox.png", mime_type: "image/png", byte_size: 10, sha256: "a".repeat(64), processing_status: "processed", created_at: "2026-08-25T12:00:00Z", updated_at: "2026-08-25T12:00:00Z" },
};

describe("Phase 11 interface", () => {
  it("renders the landing page value proposition", () => {
    render(<LandingHero />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Find the Right Image");
    expect(screen.getByRole("link", { name: /Explore Image Library/ })).toHaveAttribute("href", "/images");
  });

  it("renders typed image card metadata", () => {
    render(<ThreeDImageCard imageUrl="http://localhost:8000/images/1/content" alt="A fox" subject="Red Fox" category="animal" confidence={.96} tags={["snow", "forest"]} status="processed" />);
    expect(screen.getByRole("img", { name: "A fox" })).toBeInTheDocument();
    expect(screen.getByText("96%")).toBeInTheDocument();
    expect(screen.getByText("snow")).toBeInTheDocument();
  });

  it("renders raw candidates in semantic rank order", () => {
    render(<CandidateList candidates={[{ rank: 2, image_id: "two", similarity_score: .8, subject: "fox", category: "animal", caption: "Fox", tags: [], vision_confidence: .9, is_low_confidence: false }, { rank: 1, image_id: "one", similarity_score: .93, subject: "wolf", category: "animal", caption: "Wolf", tags: [], vision_confidence: .96, is_low_confidence: false }]} />);
    const ranks = screen.getAllByLabelText(/Rank/);
    expect(ranks.map((node) => node.textContent)).toEqual(["#1", "#2"]);
    expect(screen.getByText(/not yet safety-filtered/)).toBeInTheDocument();
  });

  it("renders a rejected guard decision with reason and explanation", () => {
    render(<MismatchGuardPanel decision={decision} expectedSubject="red fox" candidate={{ rank: 1, image_id: "image-1", similarity_score: .93, subject: "gray wolf", category: "animal", caption: "Wolf", tags: [], vision_confidence: .96, is_low_confidence: false }} />);
    expect(screen.getByText("rejected")).toBeInTheDocument();
    expect(screen.getByText("SUBJECT_MISMATCH")).toBeInTheDocument();
    expect(screen.getByText(/Expected red fox/)).toBeInTheDocument();
  });

  it("renders the safe no-confident-match state", () => {
    render(<NoConfidentMatch rejected={[decision]} />);
    expect(screen.getByRole("heading", { name: "No confident match" })).toBeInTheDocument();
    expect(screen.getByText(/No rejected candidate/)).toBeInTheDocument();
  });

  it("shows review controls for a guard-accepted recommendation", () => {
    render(<ReviewPanel recommendation={detail} history={[]} onReviewed={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });

  it("does not expose an approve control for guard-rejected evidence", () => {
    render(<ReviewPanel recommendation={{ ...detail, guard_decision: "SUBJECT_MISMATCH", guard_reason_code: "SUBJECT_MISMATCH", human_review_permitted: false }} history={[]} onReviewed={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByText(/cannot be approved/)).toBeInTheDocument();
  });

  it("renders evaluation metrics from the supplied API report", () => {
    const report = { total_examples: 10, correct_top1: 3, correct_no_confident_match: 7, unsafe_acceptance_count: 0, top1_precision: .3, issued_recommendation_precision: .875, unsafe_rejection_recall: .9, dataset_version: "evaluation-v1", config_version: "phase8-v1", examples: [] } as unknown as EvaluationRun;
    render(<EvaluationDashboardView report={report} />);
    const precision = screen.getByText("Official top-1 precision").parentElement;
    expect(within(precision!).getByText("0.3000")).toBeInTheDocument();
    const issued = screen.getByText("Issued-recommendation precision").parentElement;
    expect(within(issued!).getByText("0.8750")).toBeInTheDocument();
    expect(screen.getByText(/bounded deterministic evaluation-v1/)).toBeInTheDocument();
  });

  it("renders a human-readable API error and retry action", () => {
    const retry = vi.fn(); render(<ErrorState message="The API is unreachable." onRetry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.getByRole("alert")).toHaveTextContent("API is unreachable");
    expect(retry).toHaveBeenCalledOnce();
  });

  it("disables pointer tilt for reduced motion and touch", () => {
    expect(calculateTilt(1, 0, true, false)).toEqual({ rotateX: 0, rotateY: 0 });
    expect(calculateTilt(1, 0, false, true)).toEqual({ rotateX: 0, rotateY: 0 });
    expect(calculateTilt(1, 0, false, false)).toEqual({ rotateX: 4, rotateY: 4 });
  });

  it("has no detectable accessibility violations in core static views", async () => {
    const { container, rerender } = render(<LandingHero />);
    const options = { rules: { "color-contrast": { enabled: false } } };
    expect((await axe.run(container, options)).violations).toEqual([]);

    rerender(<ReviewPanel recommendation={detail} history={[]} onReviewed={vi.fn()} />);
    expect((await axe.run(container, options)).violations).toEqual([]);

    const report = { total_examples: 10, correct_top1: 3, correct_no_confident_match: 7, unsafe_acceptance_count: 0, top1_precision: .3, issued_recommendation_precision: 1, unsafe_rejection_recall: 1, dataset_version: "evaluation-v1", config_version: "phase8-v1", examples: [] } as unknown as EvaluationRun;
    rerender(<EvaluationDashboardView report={report} />);
    expect((await axe.run(container, options)).violations).toEqual([]);
  });
});
