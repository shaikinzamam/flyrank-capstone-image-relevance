"use client";

import { useParams } from "next/navigation";
import { ImageDetailView } from "@/components/images/ImageDetailView";

export default function ImageDetailPage() { const { id } = useParams<{ id: string }>(); return <div className="page-shell py-12"><ImageDetailView id={id} /></div>; }
