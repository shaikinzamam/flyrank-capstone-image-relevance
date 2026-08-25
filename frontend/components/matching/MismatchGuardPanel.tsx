"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { CandidateDecision, ImageCandidate } from "@/types/api";

export function MismatchGuardPanel({ decision, candidate, expectedSubject, final }: { decision: CandidateDecision; candidate?: ImageCandidate; expectedSubject?: string | null; final?: boolean }) {
  const reduced = useReducedMotion();
  const accepted = decision.decision === "ACCEPTED";
  return <motion.article initial={reduced ? false : { opacity: 0, y: 10, z: 0 }} animate={{ opacity: 1, y: 0, z: accepted ? 8 : -14 }} transition={{ type: "spring", stiffness: 180, damping: 24 }} className={`glass rounded-2xl border p-5 ${accepted ? "border-emerald-300/25" : "border-red-300/20"}`}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="eyebrow">Semantic rank #{decision.rank}</p><h3 className="display mt-2 text-2xl font-bold capitalize">{candidate?.subject ?? "Persisted candidate"}</h3></div><StatusBadge status={accepted ? "accepted" : "rejected"} /></div>
    <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Evidence label="Article expected" value={expectedSubject ?? "Not specified"} /><Evidence label="Candidate" value={candidate?.subject ?? "See persisted detail"} /><Evidence label="Similarity" value={`${Math.round(decision.similarity_score * 100)}%`} /><Evidence label="Vision confidence" value={`${Math.round(decision.vision_confidence * 100)}%`} /></div>
    <div className="mt-4 rounded-xl border border-white/8 bg-black/15 p-4"><div className="flex flex-wrap items-center gap-3"><span className="text-xs font-bold uppercase tracking-wider text-slate-500">Reason</span><code className={accepted ? "text-emerald-200" : "text-red-200"}>{decision.reason_code}</code>{final && <span className="text-xs font-bold text-emerald-200">FINAL RECOMMENDATION</span>}</div><p className="muted mt-2 text-sm leading-6">{decision.explanation}</p></div>
    <Link href={`/recommendations/${decision.recommendation_id}`} className="btn-secondary mt-4">Inspect evidence{accepted ? " & review" : ""}</Link>
  </motion.article>;
}

function Evidence({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-white/7 bg-white/[.025] p-3"><p className="text-xs uppercase tracking-wider text-slate-500">{label}</p><p className="mt-1 font-bold capitalize">{value}</p></div>; }
