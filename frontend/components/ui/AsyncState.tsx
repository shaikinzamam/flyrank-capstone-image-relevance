export function LoadingState({ label = "Loading" }: { label?: string }) {
  return <div role="status" className="glass flex min-h-40 items-center justify-center gap-3 rounded-2xl p-8 text-slate-300"><span className="size-5 animate-spin rounded-full border-2 border-emerald-200/25 border-t-emerald-200" aria-hidden="true" />{label}…</div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div role="alert" className="glass rounded-2xl border-red-300/20 p-6"><p className="font-bold text-red-100">Something needs attention</p><p className="mt-2 text-sm text-slate-300">{message}</p>{onRetry && <button className="btn-secondary mt-4" onClick={onRetry}>Try again</button>}</div>;
}

export function CardSkeletons({ count = 6 }: { count?: number }) {
  return <div role="status" aria-label="Loading image library" className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: count }, (_, index) => <div key={index} className="glass h-96 animate-pulse rounded-2xl" />)}</div>;
}
