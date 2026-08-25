import { apiRequest } from "./client";
import type {
  ImageCandidatesResponse,
  PostInput,
  PostRecord,
  RecommendationRun,
} from "@/types/api";

export const createPost = (input: PostInput): Promise<PostRecord> =>
  apiRequest("/posts", { method: "POST", body: JSON.stringify(input) });

export const embedPost = (postId: string): Promise<unknown> =>
  apiRequest(`/posts/${postId}/embedding`, { method: "POST" });

export const retrieveCandidates = (
  postId: string,
): Promise<ImageCandidatesResponse> =>
  apiRequest(`/posts/${postId}/image-candidates?top_k=5`);

export const createRecommendation = (
  postId: string,
): Promise<RecommendationRun> =>
  apiRequest(`/posts/${postId}/recommendations?top_k=5`, { method: "POST" });
