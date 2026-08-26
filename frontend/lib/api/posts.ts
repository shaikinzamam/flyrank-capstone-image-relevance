import { apiRequest } from "./client";
import type {
  ImageCandidatesResponse,
  PostInput,
  PostRecord,
  RecommendationRun,
  ProcessingJob,
} from "@/types/api";

export const createPost = (input: PostInput): Promise<PostRecord> =>
  apiRequest("/posts", { method: "POST", body: JSON.stringify(input) });

export const embedPost = (postId: string): Promise<ProcessingJob> =>
  apiRequest(`/posts/${postId}/embedding`, {
    method: "POST",
    body: JSON.stringify({ idempotency_key: `post-embedding-${postId}-${crypto.randomUUID()}` }),
  });

export async function waitForJob(jobId: string): Promise<ProcessingJob> {
  for (let attempt = 0; attempt < 480; attempt += 1) {
    const job = await apiRequest<ProcessingJob>(`/jobs/${jobId}`);
    if (job.status === "completed") return job;
    if (job.status === "failed" || job.status === "completed_with_errors") {
      throw new Error(job.failure_summary ?? "Background embedding failed.");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 250));
  }
  throw new Error("Background embedding did not finish in time.");
}

export const retrieveCandidates = (
  postId: string,
): Promise<ImageCandidatesResponse> =>
  apiRequest(`/posts/${postId}/image-candidates?top_k=5`);

export const createRecommendation = (
  postId: string,
): Promise<RecommendationRun> =>
  apiRequest(`/posts/${postId}/recommendations?top_k=5`, { method: "POST" });
