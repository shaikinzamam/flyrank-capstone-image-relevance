import type { Metadata } from "next";
import { ImageLibrary } from "@/components/images/ImageLibrary";

export const metadata: Metadata = { title: "Image Library" };
export default function ImagesPage() { return <div className="page-shell py-14"><p className="eyebrow">Vision corpus</p><h1 className="display mt-3 text-4xl font-bold sm:text-5xl">Image Library</h1><p className="muted mb-10 mt-3 max-w-2xl">Inspect processed visual evidence, confidence, and embedding readiness.</p><ImageLibrary /></div>; }
