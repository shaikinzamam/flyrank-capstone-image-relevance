"use client";

import { useParams } from "next/navigation";
import { RecommendationReviewView } from "@/components/review/RecommendationReviewView";

export default function RecommendationPage() { const { id } = useParams<{ id: string }>(); return <div className="page-shell py-12"><RecommendationReviewView id={id} /></div>; }
