"use client";

import { useCallback, useEffect, useState } from "react";
import { getImageDetails, listImages } from "@/lib/api/images";
import type { ImageDetail } from "@/types/api";
import { ThreeDImageCard } from "./ThreeDImageCard";
import { CardSkeletons, ErrorState } from "@/components/ui/AsyncState";

export function ImageLibrary() {
  const [images, setImages] = useState<ImageDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const assets = await listImages();
      setImages(await Promise.all(assets.map((asset) => getImageDetails(asset.id))));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Image library could not be loaded."); }
    finally { setLoading(false); }
  }, []);
  // The callback only updates state after API promises settle.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);
  if (loading) return <CardSkeletons />;
  if (error) return <ErrorState message={error} onRetry={() => { setLoading(true); setError(null); void load(); }} />;
  if (!images.length) return <div className="glass rounded-2xl p-10 text-center"><h2 className="display text-2xl font-bold">The library is ready for its first image</h2><p className="muted mt-2">Upload and process images through the backend to see them here.</p></div>;
  return <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{images.map(({ asset, metadata }) => <ThreeDImageCard key={asset.id} id={asset.id} imageId={asset.id} alt={metadata?.caption ?? asset.filename} subject={metadata?.subject ?? asset.filename} category={metadata?.category ?? "Awaiting analysis"} confidence={metadata?.confidence} tags={metadata?.tags ?? []} status={metadata?.is_low_confidence ? "low confidence" : asset.processing_status} caption={metadata?.caption} />)}</div>;
}
