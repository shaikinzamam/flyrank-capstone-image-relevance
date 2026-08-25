"use client";

import Image from "next/image";
import Link from "next/link";
import { motion, useMotionValue, useReducedMotion, useSpring } from "motion/react";
import type { PointerEvent } from "react";
import { StatusBadge } from "@/components/ui/StatusBadge";

export interface ThreeDImageCardProps {
  id?: string;
  imageUrl: string;
  alt: string;
  subject: string;
  category: string;
  confidence?: number | null;
  tags: string[];
  status: string;
  caption?: string;
}

export function calculateTilt(
  horizontalRatio: number,
  verticalRatio: number,
  reducedMotion: boolean,
  touchPointer: boolean,
) {
  if (reducedMotion || touchPointer) return { rotateX: 0, rotateY: 0 };
  return {
    rotateX: -(verticalRatio - 0.5) * 8,
    rotateY: (horizontalRatio - 0.5) * 8,
  };
}

export function ThreeDImageCard(props: ThreeDImageCardProps) {
  const reduced = useReducedMotion();
  const rotateX = useSpring(useMotionValue(0), { stiffness: 180, damping: 24 });
  const rotateY = useSpring(useMotionValue(0), { stiffness: 180, damping: 24 });

  function tilt(event: PointerEvent<HTMLElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    const tilt = calculateTilt(
      (event.clientX - box.left) / box.width,
      (event.clientY - box.top) / box.height,
      Boolean(reduced),
      event.pointerType === "touch",
    );
    rotateY.set(tilt.rotateY);
    rotateX.set(tilt.rotateX);
  }

  function reset() { rotateX.set(0); rotateY.set(0); }

  const content = (
    <motion.article
      onPointerMove={tilt}
      onPointerLeave={reset}
      onPointerCancel={reset}
      style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
      className="glass group relative h-full overflow-hidden rounded-2xl"
      whileHover={reduced ? undefined : { y: -4 }}
      transition={{ type: "spring", stiffness: 220, damping: 24 }}
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-slate-900" style={{ transform: "translateZ(18px)" }}>
        <Image loader={({ src }) => src} unoptimized src={props.imageUrl} alt={props.alt} fill sizes="(max-width: 768px) 100vw, 33vw" className="object-cover transition duration-500 group-hover:scale-[1.025]" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#09131b]/80 via-transparent to-transparent" />
        <div className="absolute left-3 top-3"><StatusBadge status={props.status} /></div>
      </div>
      <div className="relative p-5" style={{ transform: "translateZ(28px)" }}>
        <p className="eyebrow">{props.category}</p>
        <h2 className="display mt-1 text-xl font-bold capitalize">{props.subject}</h2>
        {props.caption && <p className="muted mt-2 line-clamp-2 text-sm">{props.caption}</p>}
        <div className="mt-4 flex flex-wrap gap-2">{props.tags.slice(0, 4).map((tag) => <span className="tag" key={tag}>{tag}</span>)}</div>
        {props.confidence != null && <p className="mt-4 text-sm text-slate-300">Vision confidence <strong className="text-white">{Math.round(props.confidence * 100)}%</strong></p>}
      </div>
    </motion.article>
  );
  return props.id ? <Link href={`/images/${props.id}`} onBlur={reset} className="block h-full rounded-2xl [perspective:900px]">{content}</Link> : <div className="h-full [perspective:900px]">{content}</div>;
}
