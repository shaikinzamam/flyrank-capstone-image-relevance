"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const links = [
  ["Home", "/"], ["Images", "/images"], ["Match", "/match"], ["Evaluation", "/evaluation"],
] as const;

export function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b border-white/8 bg-[#071016]/80 backdrop-blur-xl">
      <nav className="page-shell flex min-h-16 items-center justify-between" aria-label="Primary navigation">
        <Link href="/" className="display flex items-center gap-2 text-lg font-bold">
          <span className="grid size-8 place-items-center rounded-lg border border-emerald-200/25 bg-emerald-300/10 text-emerald-200" aria-hidden="true">A</span>
          Aperture Guard
        </Link>
        <button className="rounded-lg border border-white/10 px-3 py-2 text-sm md:hidden" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-controls="mobile-nav">Menu</button>
        <div id="mobile-nav" className={`${open ? "flex" : "hidden"} absolute left-4 right-4 top-17 flex-col gap-1 rounded-xl border border-white/10 bg-[#0b1720] p-3 shadow-2xl md:static md:flex md:flex-row md:border-0 md:bg-transparent md:p-0 md:shadow-none`}>
          {links.map(([label, href]) => (
            <Link key={href} href={href} onClick={() => setOpen(false)} aria-current={pathname === href ? "page" : undefined} className={`rounded-lg px-3 py-2 text-sm transition ${pathname === href ? "bg-white/8 text-white" : "text-slate-400 hover:text-white"}`}>{label}</Link>
          ))}
        </div>
      </nav>
    </header>
  );
}
