import type { EvaluationRun } from "@/types/api";
import { StatusBadge } from "@/components/ui/StatusBadge";

export function EvaluationDashboardView({ report }: { report: EvaluationRun }) {
  const metrics = [
    ["Evaluation examples", report.total_examples.toString()],
    ["Correct top-1", report.correct_top1.toString()],
    ["Correct refusals", report.correct_no_confident_match.toString()],
    ["Unsafe acceptances", report.unsafe_acceptance_count.toString()],
    ["Official top-1 precision", report.top1_precision.toFixed(4)],
    ["Issued-recommendation precision", report.issued_recommendation_precision.toFixed(4)],
    ["Unsafe rejection recall", report.unsafe_rejection_recall.toFixed(4)],
  ];
  return <><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{metrics.map(([label, value]) => <article className="glass rounded-2xl p-5" key={label}><p className="text-sm text-slate-400">{label}</p><p className="display mt-2 text-3xl font-bold">{value}</p></article>)}</div><div className="mt-6 rounded-2xl border border-amber-300/15 bg-amber-300/[.045] p-4 text-sm text-amber-50">Metrics are measured on the bounded deterministic {report.dataset_version} dataset and do not represent real-world universal accuracy.</div><section className="mt-10"><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">Per-example evidence</p><h2 className="display mt-2 text-3xl font-bold">Evaluation cases</h2></div><p className="muted text-sm">Config {report.config_version}</p></div><div className="mt-5 overflow-hidden rounded-2xl border border-white/10"><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-white/[.045] text-xs uppercase tracking-wider text-slate-400"><tr><th className="p-4">Example</th><th className="p-4">Expected</th><th className="p-4">Actual</th><th className="p-4">Selected</th><th className="p-4">Result</th><th className="p-4">Guard evidence</th></tr></thead><tbody>{report.examples.map((example) => { const hardNegative = example.candidates.some((candidate) => candidate.reason_code === "SUBJECT_MISMATCH"); return <tr key={example.example_id} className={`border-t border-white/7 ${hardNegative ? "bg-red-300/[.025]" : "bg-black/10"}`}><td className="p-4 font-semibold">{example.example_id}{hardNegative && <span className="ml-2 text-xs text-red-200">hard negative</span>}</td><td className="p-4 text-slate-300">{example.expected_result}</td><td className="p-4 text-slate-300">{example.actual_result}</td><td className="p-4 text-slate-400">{example.selected_image_id ?? "None"}</td><td className="p-4"><StatusBadge status={example.correct ? "correct" : "incorrect"} /></td><td className="p-4 text-xs text-slate-400">{[...new Set(example.candidates.map((candidate) => candidate.reason_code))].join(", ")}</td></tr>; })}</tbody></table></div></div></section></>;
}
