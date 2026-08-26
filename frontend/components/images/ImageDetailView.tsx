"use client";

import { useCallback, useEffect, useState } from "react";
import { getImageDetails } from "@/lib/api/images";
import type { ImageDetail } from "@/types/api";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { AuthenticatedImage } from "./AuthenticatedImage";

export function ImageDetailView({ id }: { id: string }) {
  const [detail, setDetail] = useState<ImageDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { try { setDetail(await getImageDetails(id)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Image details could not be loaded."); } }, [id]);
  // The callback only updates state after the API promise settles.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);
  if (error) return <ErrorState message={error} onRetry={() => { setError(null); void load(); }} />;
  if (!detail) return <LoadingState label="Loading image evidence" />;
  const { asset, metadata, embeddings } = detail;
  return <div className="grid gap-7 lg:grid-cols-[1.15fr_.85fr]">
    <section className="glass overflow-hidden rounded-3xl"><div className="relative aspect-[4/3] bg-slate-950"><AuthenticatedImage imageId={asset.id} fill priority alt={metadata?.caption ?? asset.filename} className="object-contain" sizes="(max-width: 1024px) 100vw, 60vw" /></div><div className="p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">Original file</p><h1 className="display mt-1 text-3xl font-bold">{asset.filename}</h1></div><StatusBadge status={asset.processing_status} /></div>{metadata?.caption && <p className="muted mt-4 leading-7">{metadata.caption}</p>}</div></section>
    <aside className="space-y-5"><Panel title="Vision metadata">{metadata ? <dl className="space-y-3 text-sm"><Row label="Subject" value={metadata.subject} /><Row label="Subject code" value={metadata.subject_code} /><Row label="Category" value={metadata.category} /><Row label="Confidence" value={`${Math.round(metadata.confidence * 100)}%`} /><Row label="Provider" value={`${metadata.vision_provider} · ${metadata.vision_model}`} /><Row label="Metadata" value={metadata.is_low_confidence ? "Flagged low confidence" : metadata.metadata_status} /></dl> : <p className="muted text-sm">Vision analysis has not been persisted yet.</p>}</Panel>
      {metadata && <><Panel title="Tags"><TagList values={metadata.tags} /></Panel><Panel title="Attributes & objects"><p className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">Attributes</p><TagList values={metadata.attributes} /><p className="mb-2 mt-4 text-xs font-bold uppercase tracking-wider text-slate-500">Objects</p><TagList values={metadata.objects} /></Panel></>}
      <Panel title="Embedding state">{embeddings.length ? embeddings.map((embedding) => <div key={embedding.id} className="rounded-xl border border-white/8 bg-white/[.025] p-3 text-sm"><p className="font-semibold">{embedding.embedding_model}</p><p className="muted mt-1 break-all text-xs">{embedding.embedding_version}</p><p className="mt-2 text-xs text-emerald-200">{embedding.dimensions} dimensions</p></div>) : <p className="muted text-sm">No embedding has been generated.</p>}</Panel>
    </aside>
  </div>;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) { return <section className="glass rounded-2xl p-5"><h2 className="display mb-4 text-lg font-bold">{title}</h2>{children}</section>; }
function Row({ label, value }: { label: string; value: string }) { return <div className="flex justify-between gap-4 border-b border-white/6 pb-2"><dt className="muted">{label}</dt><dd className="text-right capitalize text-slate-100">{value}</dd></div>; }
function TagList({ values }: { values: string[] }) { return <div className="flex flex-wrap gap-2">{values.map((value) => <span className="tag" key={value}>{value}</span>)}</div>; }
