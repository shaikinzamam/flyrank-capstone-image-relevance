"use client";

import { useCallback, useEffect, useState } from "react";
import { getLatestEvaluation } from "@/lib/api/evaluation";
import type { EvaluationRun } from "@/types/api";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { EvaluationDashboardView } from "./EvaluationDashboardView";

export function EvaluationDashboard() {
  const [report, setReport] = useState<EvaluationRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { try { setReport(await getLatestEvaluation()); } catch (reason) { setError(reason instanceof Error ? reason.message : "Evaluation report could not be loaded."); } }, []);
  // The callback only updates state after the API promise settles.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);
  if (error) return <ErrorState message={error} onRetry={() => { setError(null); void load(); }} />;
  if (!report) return <LoadingState label="Loading persisted metrics" />;
  return <EvaluationDashboardView report={report} />;
}
