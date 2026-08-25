import type { Metadata } from "next";
import { EvaluationDashboard } from "@/components/evaluation/EvaluationDashboard";

export const metadata: Metadata = { title: "Evaluation" };
export default function EvaluationPage() { return <div className="page-shell py-14"><p className="eyebrow">Measured safety</p><h1 className="display mt-3 text-4xl font-bold sm:text-5xl">Evaluation dashboard</h1><p className="muted mb-10 mt-3 max-w-2xl">Actual persisted metrics and per-example guard evidence from the backend.</p><EvaluationDashboard /></div>; }
