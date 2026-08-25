import Link from "next/link";
import { HeroCardStack } from "./HeroCardStack";

const flow = ["Article", "Semantic Retrieval", "Mismatch Guard", "Safe Recommendation"];

export function LandingHero() {
  return (
    <>
      <section className="page-shell grid min-h-[calc(100vh-4rem)] grid-cols-[minmax(0,1fr)] items-center gap-12 py-16 lg:grid-cols-[1.08fr_.92fr]">
        <div className="min-w-0">
          <p className="eyebrow">Evidence-led visual intelligence</p>
          <h1 className="display mt-5 max-w-3xl break-words text-[2.7rem] font-bold leading-[.98] sm:text-6xl xl:text-7xl">Find the Right Image. <span className="text-emerald-200">Reject the Wrong One.</span></h1>
          <p className="muted mt-6 max-w-2xl text-lg leading-8">AI-powered image understanding, semantic retrieval, deterministic mismatch protection, and human review.</p>
          <div className="mt-8 flex flex-wrap gap-3"><Link className="btn-primary" href="/images">Explore Image Library <span aria-hidden="true">→</span></Link><Link className="btn-secondary" href="/match">Try Article Matching</Link></div>
          <div className="mt-12 flex max-w-2xl flex-wrap items-center gap-2" aria-label="Recommendation pipeline">{flow.map((step, index) => <div key={step} className="flex items-center gap-2"><span className="rounded-lg border border-white/10 bg-white/[.035] px-3 py-2 text-xs font-semibold text-slate-300">{step}</span>{index < flow.length - 1 && <span className="text-emerald-200" aria-hidden="true">↓</span>}</div>)}</div>
        </div>
        <HeroCardStack />
      </section>
      <section className="page-shell grid gap-4 pb-24 md:grid-cols-3"><Feature number="01" title="Understand" text="Structured vision metadata makes every image inspectable." /><Feature number="02" title="Retrieve" text="Semantic ranking finds related candidates without declaring a winner." /><Feature number="03" title="Protect" text="A deterministic guard can refuse every unsafe candidate." /></section>
    </>
  );
}

function Feature({ number, title, text }: { number: string; title: string; text: string }) { return <article className="glass rounded-2xl p-6"><span className="eyebrow">{number}</span><h2 className="display mt-3 text-xl font-bold">{title}</h2><p className="muted mt-2 text-sm leading-6">{text}</p></article>; }
