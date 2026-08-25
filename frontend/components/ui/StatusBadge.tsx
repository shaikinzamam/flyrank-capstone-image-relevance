export function StatusBadge({ status }: { status: string }) {
  const safe = ["accepted", "approved", "processed", "trusted", "correct"].some((word) => status.toLowerCase().includes(word));
  const danger = ["rejected", "mismatch", "failed", "incorrect"].some((word) => status.toLowerCase().includes(word));
  const style = safe ? "border-emerald-300/25 bg-emerald-300/10 text-emerald-200" : danger ? "border-red-300/25 bg-red-300/10 text-red-200" : "border-amber-300/25 bg-amber-300/10 text-amber-100";
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-bold uppercase tracking-wider ${style}`}>{status.replaceAll("_", " ")}</span>;
}
