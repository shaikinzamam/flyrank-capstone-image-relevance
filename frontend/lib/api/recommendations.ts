import { apiRequest } from "./client";
import type { RecommendationDetail, ReviewRecord } from "@/types/api";

export const getRecommendation = (id: string): Promise<RecommendationDetail> =>
  apiRequest(`/recommendations/${id}`);

export const getReviews = (id: string): Promise<ReviewRecord[]> =>
  apiRequest(`/recommendations/${id}/reviews`);

export const reviewRecommendation = (
  id: string,
  decision: "approve" | "reject",
  comment?: string,
): Promise<ReviewRecord> =>
  apiRequest(`/recommendations/${id}/${decision}`, {
    method: "POST",
    body: JSON.stringify({ comment: comment?.trim() || null }),
  });
