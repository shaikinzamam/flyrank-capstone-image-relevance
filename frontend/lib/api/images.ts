import { ApiError, apiBlobRequest, apiRequest, assertArray } from "./client";
import type { ImageAsset, ImageDetail } from "@/types/api";

export async function listImages(): Promise<ImageAsset[]> {
  const response: unknown = await apiRequest("/images");
  assertArray(response, "image library");
  return response as ImageAsset[];
}

const DEMO_HERO_IMAGE_FILENAME = "red_fox_01.jpg";

export async function getDemoHeroImage(): Promise<ImageAsset | null> {
  const images = await listImages();
  return (
    images.find(
      (image) => image.filename.toLowerCase() === DEMO_HERO_IMAGE_FILENAME,
    ) ?? null
  );
}

export function getImageDetails(id: string): Promise<ImageDetail> {
  return apiRequest(`/images/${id}/details`);
}

export async function fetchImageContent(
  id: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const blob = await apiBlobRequest(`/images/${id}/content`, { signal });
  if (!blob.type.startsWith("image/")) {
    throw new ApiError("The protected image response has an invalid content type.", 502);
  }
  return blob;
}
