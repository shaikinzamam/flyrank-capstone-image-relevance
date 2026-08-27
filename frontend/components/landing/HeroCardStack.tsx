"use client";

import { motion, useMotionValue, useReducedMotion, useSpring } from "motion/react";
import { useEffect, useState, type PointerEvent } from "react";
import { AuthenticatedImage } from "@/components/images/AuthenticatedImage";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getDemoHeroImage } from "@/lib/api/images";

const cards = [
  { subject: "Dog", status: "rejected", className: "translate-x-10 translate-y-12 -rotate-6 opacity-45", z: "-54px" },
  { subject: "Gray Wolf", status: "rejected", className: "-translate-x-6 translate-y-6 rotate-3 opacity-70", z: "-26px" },
  { subject: "Red Fox", status: "accepted", className: "", z: "18px" },
];

export function HeroCardStack() {
  const reduced = useReducedMotion();
  const x = useSpring(useMotionValue(0), { stiffness: 120, damping: 22 });
  const y = useSpring(useMotionValue(0), { stiffness: 120, damping: 22 });
  const [heroImageId, setHeroImageId] = useState<string | null>();

  useEffect(() => {
    let active = true;
    void getDemoHeroImage()
      .then((image) => {
        if (active) setHeroImageId(image?.id ?? null);
      })
      .catch(() => {
        if (active) setHeroImageId(null);
      });
    return () => {
      active = false;
    };
  }, []);

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
            <div className="relative mt-5 grid h-44 place-items-center overflow-hidden rounded-2xl border border-white/8 bg-[radial-gradient(circle_at_50%_35%,rgba(111,227,193,.18),transparent_55%),linear-gradient(145deg,#172833,#0b161e)]">
              {card.status === "accepted" ? (
                <HeroFoxPreview imageId={heroImageId} />
              ) : (
                <span className="display text-5xl font-bold text-white/90">{card.subject.split(" ").map((word) => word[0]).join("")}</span>
              )}
            </div>
            <p className="display mt-5 text-2xl font-bold">{card.subject}</p>
            <p className="muted mt-1 text-sm">Deterministic subject evidence</p>
          </div>
        ))}
      </motion.div>
    </div>
  );
}

function HeroFoxPreview({ imageId }: { imageId: string | null | undefined }) {
  if (imageId === undefined) {
    return (
      <div
        role="status"
        aria-label="Loading Red fox demo candidate"
        className="absolute inset-0 animate-pulse bg-slate-900"
      />
    );
  }
  if (imageId === null) {
    return (
      <div
        role="img"
        aria-label="Red fox demo candidate"
        className="absolute inset-0 flex items-center justify-center bg-slate-950 p-4 text-center text-sm font-semibold text-slate-400"
      >
        Preview unavailable
      </div>
    );
  }
  return (
    <AuthenticatedImage
      imageId={imageId}
      alt="Red fox demo candidate"
      fill
      priority
      sizes="(max-width: 1024px) 100vw, 430px"
      className="object-cover"
    />
  );
}
