"use client";

import { useState } from "react";
import { createPost, embedPost, waitForJob, retrieveCandidates, createRecommendation } from "@/lib/api/posts";
import type { ImageCandidatesResponse, PostInput, RecommendationRun } from "@/types/api";
import { CandidateList } from "./CandidateList";
import { MismatchGuardPanel } from "./MismatchGuardPanel";
import { NoConfidentMatch } from "./NoConfidentMatch";
import { ErrorState } from "@/components/ui/AsyncState";

const initial: PostInput = { title: "", body: "", expected_subject: "", expected_category: "", required_tags: [] };

export function MatchWorkflow() {
  const [form, setForm] = useState(initial);
  const [tagText, setTagText] = useState("");
  const [stage, setStage] = useState<string | null>(null);
  const [raw, setRaw] = useState<ImageCandidatesResponse | null>(null);
  const [guarded, setGuarded] = useState<RecommendationRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError(null); setRaw(null); setGuarded(null);
    try {
      const input = { ...form, expected_subject: form.expected_subject || null, expected_category: form.expected_category || null, required_tags: tagText.split(",").map((tag) => tag.trim()).filter(Boolean) };
      setStage("Creating article"); const post = await createPost(input);
      setStage("Queueing semantic embedding"); const job = await embedPost(post.id);
      setStage("Generating semantic embedding"); await waitForJob(job.id);
      setStage("Retrieving semantic candidates"); setRaw(await retrieveCandidates(post.id));
      setStage("Applying deterministic mismatch guard"); setGuarded(await createRecommendation(post.id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Matching could not be completed."); }
    finally { setStage(null); }
  }
  const decisions = guarded ? [...guarded.rejected_candidates, ...(guarded.recommendation ? [guarded.recommendation] : [])].sort((a, b) => a.rank - b.rank) : [];
  return <div className="space-y-12"><form onSubmit={submit} aria-busy={stage !== null} className="glass rounded-3xl p-6 sm:p-8"><div className="grid gap-5 md:grid-cols-2"><Field label="Article title"><input required maxLength={300} className="field" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="How red foxes survive winter" /></Field><Field label="Expected subject"><input maxLength={100} className="field" value={form.expected_subject ?? ""} onChange={(event) => setForm({ ...form, expected_subject: event.target.value })} placeholder="red fox" /></Field><Field wide label="Article body"><textarea required rows={6} className="field resize-y" value={form.body} onChange={(event) => setForm({ ...form, body: event.target.value })} placeholder="Write or paste the article text…" /></Field><Field label="Expected category"><input maxLength={50} className="field" value={form.expected_category ?? ""} onChange={(event) => setForm({ ...form, expected_category: event.target.value })} placeholder="animal" /></Field><Field label="Required tags"><input className="field" value={tagText} onChange={(event) => setTagText(event.target.value)} placeholder="snow, winter" /><span className="muted mt-1 block text-xs">Comma-separated; up to 20 tags, 50 characters each</span></Field></div><button disabled={stage !== null} className="btn-primary mt-6" type="submit">{stage ? <><span className="size-4 animate-spin rounded-full border-2 border-black/20 border-t-black" aria-hidden="true" />{stage}…</> : "Create & match article"}</button><span className="sr-only" role="status" aria-live="polite">{stage ? `${stage} in progress` : ""}</span></form>
    {error && <ErrorState message={error} />}
    {raw && <CandidateList candidates={raw.candidates} />}
    {guarded && <section aria-labelledby="guarded-result"><p className="eyebrow">Phase 8 · safety decision</p><h2 id="guarded-result" className="display mt-2 text-3xl font-bold">Guarded Recommendation</h2><p className="muted mt-2">Immutable deterministic evidence is shown separately from semantic rank.</p><div className="mt-6 space-y-4">{decisions.map((decision) => <MismatchGuardPanel key={decision.recommendation_id} decision={decision} candidate={raw?.candidates.find((candidate) => candidate.image_id === decision.image_id)} expectedSubject={form.expected_subject} final={guarded.recommendation?.recommendation_id === decision.recommendation_id} />)}</div>{guarded.status === "no_confident_match" && <div className="mt-6"><NoConfidentMatch rejected={guarded.rejected_candidates} /></div>}</section>}
  </div>;
}

function Field({ label, wide, children }: { label: string; wide?: boolean; children: React.ReactNode }) { return <label className={wide ? "md:col-span-2" : ""}><span className="mb-2 block text-sm font-bold text-slate-200">{label}</span>{children}</label>; }
