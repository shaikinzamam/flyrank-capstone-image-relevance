"use client";

import { useCallback, useEffect, useState } from "react";
import { AuthenticatedImage } from "@/components/images/AuthenticatedImage";
import { getRecommendation, getReviews } from "@/lib/api/recommendations";
import type { RecommendationDetail, ReviewRecord } from "@/types/api";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ReviewPanel } from "./ReviewPanel";

export function RecommendationReviewView({ id }: { id: string }) {
  const [detail, setDetail] = useState<RecommendationDetail | null>(null);
  const [history, setHistory] = useState<ReviewRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { try { const [nextDetail, nextHistory] = await Promise.all([getRecommendation(id), getReviews(id)]); setDetail(nextDetail); setHistory(nextHistory); } catch (reason) { setError(reason instanceof Error ? reason.message : "Recommendation could not be loaded."); } }, [id]);
  // The callback only updates state after API promises settle.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);
  if (error) return <ErrorState message={error} onRetry={() => { setError(null); void load(); }} />;
  if (!detail) return <LoadingState label="Loading immutable evidence" />;
  return <div className="grid gap-7 lg:grid-cols-[1.06fr_.94fr]"><section className="glass overflow-hidden rounded-3xl"><div className="relative aspect-[16/10] bg-slate-950"><AuthenticatedImage imageId={detail.candidate_image.id} fill priority alt={`${detail.image_subject} candidate for ${detail.post.title}`} className="object-contain" sizes="(max-width: 1024px) 100vw, 55vw" /></div><div className="p-6 sm:p-8"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="eyebrow">Immutable AI evidence</p><h1 className="display mt-2 text-3xl font-bold capitalize">{detail.image_subject}</h1><p className="muted mt-1">Candidate for “{detail.post.title}”</p></div><StatusBadge status={detail.guard_decision} /></div><div className="mt-6 grid gap-3 sm:grid-cols-2"><Evidence label="Semantic rank" value={`#${detail.rank}`} /><Evidence label="Similarity" value={`${Math.round(detail.similarity_score * 100)}%`} /><Evidence label="Vision confidence" value={`${Math.round(detail.vision_confidence * 100)}%`} /><Evidence label="Reason code" value={detail.guard_reason_code} /><Evidence label="Expected subject" value={detail.expected_subject ?? "Not specified"} /><Evidence label="Detected subject" value={detail.image_subject} /></div><div className="mt-5 rounded-2xl border border-white/8 bg-black/15 p-5"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Guard explanation</p><p className="mt-2 leading-7 text-slate-200">{detail.explanation}</p></div></div></section><ReviewPanel recommendation={detail} history={history} onReviewed={load} /></div>;
}

function Evidence({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-white/8 bg-white/[.025] p-4"><p className="text-xs uppercase tracking-wider text-slate-500">{label}</p><p className="mt-1 break-words font-bold capitalize">{value.replaceAll("_", " ")}</p></div>; }
