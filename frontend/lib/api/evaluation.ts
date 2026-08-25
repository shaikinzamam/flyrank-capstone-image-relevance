import { apiRequest } from "./client";
import type { EvaluationRun } from "@/types/api";

export const getLatestEvaluation = (): Promise<EvaluationRun> =>
  apiRequest("/evaluation/latest");
