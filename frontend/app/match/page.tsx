import type { Metadata } from "next";
import { MatchWorkflow } from "@/components/matching/MatchWorkflow";

export const metadata: Metadata = { title: "Article Matching" };
export default function MatchPage() { return <div className="page-shell py-14"><p className="eyebrow">Guided pipeline</p><h1 className="display mt-3 text-4xl font-bold sm:text-5xl">Match an article safely</h1><p className="muted mb-10 mt-3 max-w-2xl">Create the post, generate its embedding, inspect raw retrieval, then apply the deterministic guard—in one guided flow.</p><MatchWorkflow /></div>; }
