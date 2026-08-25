import { apiRequest, apiUrl, assertArray } from "./client";
import type { ImageAsset, ImageDetail } from "@/types/api";

export async function listImages(): Promise<ImageAsset[]> {
  const response: unknown = await apiRequest("/images");
  assertArray(response, "image library");
  return response as ImageAsset[];
}

export function getImageDetails(id: string): Promise<ImageDetail> {
  return apiRequest(`/images/${id}/details`);
}

export function imageContentUrl(id: string): string {
  return apiUrl(`/images/${id}/content`);
}
