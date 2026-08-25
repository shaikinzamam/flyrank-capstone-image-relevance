"use client";

import { motion, useMotionValue, useReducedMotion, useSpring } from "motion/react";
import type { PointerEvent } from "react";
import { StatusBadge } from "@/components/ui/StatusBadge";

const cards = [
  { subject: "Dog", status: "rejected", className: "translate-x-10 translate-y-12 -rotate-6 opacity-45", z: "-54px" },
  { subject: "Gray Wolf", status: "rejected", className: "-translate-x-6 translate-y-6 rotate-3 opacity-70", z: "-26px" },
  { subject: "Red Fox", status: "accepted", className: "", z: "18px" },
];

export function HeroCardStack() {
  const reduced = useReducedMotion();
  const x = useSpring(useMotionValue(0), { stiffness: 120, damping: 22 });
  const y = useSpring(useMotionValue(0), { stiffness: 120, damping: 22 });
  function move(event: PointerEvent<HTMLDivElement>) {
    if (reduced || event.pointerType === "touch") return;
    const box = event.currentTarget.getBoundingClientRect();
    x.set(((event.clientX - box.left) / box.width - .5) * 10);
    y.set(-((event.clientY - box.top) / box.height - .5) * 10);
  }
  return (
    <div className="relative mx-auto h-[390px] min-w-0 w-full max-w-[430px] [perspective:1100px]" onPointerMove={move} onPointerLeave={() => { x.set(0); y.set(0); }} aria-label="Illustration of fox accepted while wolf and dog are rejected">
      <motion.div className="absolute inset-8" style={{ rotateY: x, rotateX: y, transformStyle: "preserve-3d" }}>
        {cards.map((card) => (
          <div key={card.subject} className={`glass absolute inset-0 overflow-hidden rounded-[1.6rem] p-5 ${card.className}`} style={{ transform: `translateZ(${card.z})` }}>
            <div className="flex items-center justify-between"><span className="eyebrow">Candidate</span><StatusBadge status={card.status} /></div>
            <div className="mt-5 grid h-44 place-items-center rounded-2xl border border-white/8 bg-[radial-gradient(circle_at_50%_35%,rgba(111,227,193,.18),transparent_55%),linear-gradient(145deg,#172833,#0b161e)]">
              <span className="display text-5xl font-bold text-white/90">{card.subject.split(" ").map((word) => word[0]).join("")}</span>
            </div>
            <h3 className="display mt-5 text-2xl font-bold">{card.subject}</h3>
            <p className="muted mt-1 text-sm">Deterministic subject evidence</p>
          </div>
        ))}
      </motion.div>
    </div>
  );
}
