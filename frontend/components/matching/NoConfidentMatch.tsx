import type { CandidateDecision } from "@/types/api";

export function NoConfidentMatch({ rejected }: { rejected: CandidateDecision[] }) {
  const reasons = [...new Set(rejected.map((item) => item.reason_code.replaceAll("_", " ").toLowerCase()))];
  return <section role="status" className="glass rounded-3xl border-amber-300/20 p-8 text-center"><div className="mx-auto grid size-14 place-items-center rounded-2xl border border-amber-300/25 bg-amber-300/10 text-2xl text-amber-100" aria-hidden="true">∅</div><h2 className="display mt-5 text-3xl font-bold">No confident match</h2><p className="muted mx-auto mt-3 max-w-xl">None of the available images passed the deterministic safety checks. No rejected candidate is presented as usable.</p>{reasons.length > 0 && <div className="mt-5 flex flex-wrap justify-center gap-2">{reasons.map((reason) => <span className="tag capitalize" key={reason}>{reason}</span>)}</div>}</section>;
}
