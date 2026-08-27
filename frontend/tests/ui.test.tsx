import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LandingHero } from "@/components/landing/LandingHero";
import { AuthenticatedImage } from "@/components/images/AuthenticatedImage";
import { ThreeDImageCard, calculateTilt } from "@/components/images/ThreeDImageCard";
import { CandidateList } from "@/components/matching/CandidateList";
import { MismatchGuardPanel } from "@/components/matching/MismatchGuardPanel";
import { NoConfidentMatch } from "@/components/matching/NoConfidentMatch";
import { ReviewPanel } from "@/components/review/ReviewPanel";
import { EvaluationDashboardView } from "@/components/evaluation/EvaluationDashboardView";
import { ErrorState } from "@/components/ui/AsyncState";
import type { CandidateDecision, EvaluationRun, RecommendationDetail } from "@/types/api";

const imageFetch = vi.fn();
const createObjectURL = vi.fn(() => "blob:authenticated-image");
const revokeObjectURL = vi.fn();

beforeEach(() => {
  vi.stubEnv(
    "NEXT_PUBLIC_API_KEY",
    "frk_browser_test_8Jw3qD6sK9vN2xF5mR7tY4uP1aC0",
  );
  imageFetch.mockResolvedValue(
    new Response(new Blob(["image-bytes"], { type: "image/png" }), {
      status: 200,
      headers: { "Content-Type": "image/png" },
    }),
  );
  vi.stubGlobal("fetch", imageFetch);
  URL.createObjectURL = createObjectURL;
  URL.revokeObjectURL = revokeObjectURL;
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.clearAllMocks();
});

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

  it("renders typed image card metadata from an authenticated blob", async () => {
    const { unmount } = render(<ThreeDImageCard imageId="image-1" alt="A fox" subject="Red Fox" category="animal" confidence={.96} tags={["snow", "forest"]} status="processed" />);
    expect(await screen.findByRole("img", { name: "A fox" })).toHaveAttribute(
      "src",
      "blob:authenticated-image",
    );
    expect(screen.getByText("96%")).toBeInTheDocument();
    expect(screen.getByText("snow")).toBeInTheDocument();
    unmount();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:authenticated-image");
  });

  it("sends bearer authentication when fetching protected image bytes", async () => {
    vi.stubEnv(
      "NEXT_PUBLIC_API_KEY",
      "frk_browser_test_8Jw3qD6sK9vN2xF5mR7tY4uP1aC0",
    );
    vi.resetModules();
    const { fetchImageContent } = await import("@/lib/api/images");
    await fetchImageContent("image-1");
    const [, request] = imageFetch.mock.calls.at(-1) as [string, RequestInit];
    expect(new Headers(request.headers).get("Authorization")).toBe(
      "Bearer frk_browser_test_8Jw3qD6sK9vN2xF5mR7tY4uP1aC0",
    );
    expect(imageFetch.mock.calls.at(-1)?.[0]).toBe(
      "http://localhost:8000/images/image-1/content",
    );
  });

  it("sends the configured demo key from the JSON API client", async () => {
    vi.resetModules();
    const { apiRequest } = await import("@/lib/api/client");
    await apiRequest("/images");

    const [, request] = imageFetch.mock.calls.at(-1) as [string, RequestInit];
    expect(new Headers(request.headers).get("Authorization")).toBe(
      "Bearer frk_browser_test_8Jw3qD6sK9vN2xF5mR7tY4uP1aC0",
    );
  });

  it("reports a clear configuration error when the browser key is blank", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_KEY", "");
    vi.resetModules();
    const { apiRequest } = await import("@/lib/api/client");

    await expect(apiRequest("/images")).rejects.toMatchObject({
      message: "Demo API key is not configured",
      status: 0,
    });
    expect(imageFetch).not.toHaveBeenCalled();
  });

  it("rejects a placeholder browser key before making a request", async () => {
    vi.stubEnv(
      "NEXT_PUBLIC_API_KEY",
      "frk_YOUR_CURRENT_DEMO_KEY_12345678901234567890",
    );
    vi.resetModules();
    const { apiRequest } = await import("@/lib/api/client");

    await expect(apiRequest("/images")).rejects.toThrow(
      "Demo API key is not configured",
    );
    expect(imageFetch).not.toHaveBeenCalled();
  });

  it("shows accessible fallback alt text when protected image fetching fails", async () => {
    imageFetch.mockRejectedValueOnce(new Error("network unavailable"));
    render(
      <div className="relative h-40">
        <AuthenticatedImage imageId="image-2" alt="A gray wolf" fill />
      </div>,
    );
    expect(await screen.findByRole("img", { name: "A gray wolf" })).toHaveTextContent(
      "Preview unavailable",
    );
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
