export type ProcessingStatus =
  | "uploaded"
  | "queued"
  | "processing"
  | "processed"
  | "failed";

export type GuardDecision =
  | "ACCEPTED"
  | "INVALID_METADATA"
  | "LOW_CONFIDENCE"
  | "SUBJECT_MISMATCH"
  | "CATEGORY_MISMATCH"
  | "REQUIRED_TAG_MISSING"
  | "LOW_SIMILARITY";

export interface ImageAsset {
  id: string;
  filename: string;
  storage_key: string;
  mime_type: string;
  byte_size: number;
  sha256: string;
  processing_status: ProcessingStatus;
  created_at: string;
  updated_at: string;
}

export interface ImageMetadata {
  id: string;
  image_id: string;
  subject: string;
  subject_code: string;
  category: string;
  caption: string;
  tags: string[];
  attributes: string[];
  objects: string[];
  confidence: number;
  is_low_confidence: boolean;
  metadata_status: "trusted" | "flagged";
  vision_provider: string;
  vision_model: string;
  schema_version: string;
  created_at: string;
  updated_at: string;
}

export interface ImageEmbeddingSummary {
  id: string;
  embedding_model: string;
  embedding_version: string;
  dimensions: number;
  created_at: string;
  updated_at: string;
}

export interface ImageDetail {
  asset: ImageAsset;
  metadata: ImageMetadata | null;
  embeddings: ImageEmbeddingSummary[];
}

export interface PostInput {
  title: string;
  body: string;
  expected_subject?: string | null;
  expected_category?: string | null;
  required_tags: string[];
}

export interface PostRecord extends PostInput {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface ProcessingJob {
  id: string;
  job_type: "image_processing" | "post_embedding";
  status: "pending" | "running" | "completed" | "completed_with_errors" | "failed";
  total_items: number;
  processed_items: number;
  failed_items: number;
  progress: number;
  idempotency_key: string;
  failure_summary: string | null;
  reused: boolean;
}

export interface ImageCandidate {
  rank: number;
  image_id: string;
  similarity_score: number;
  subject: string;
  category: string;
  caption: string;
  tags: string[];
  vision_confidence: number;
  is_low_confidence: boolean;
}

export interface ImageCandidatesResponse {
  post_id: string;
  embedding_model: string;
  embedding_version: string;
  dimensions: number;
  candidates: ImageCandidate[];
}

export interface CandidateDecision {
  recommendation_id: string;
  image_id: string;
  rank: number;
  similarity_score: number;
  vision_confidence: number;
  decision: GuardDecision;
  reason_code: GuardDecision;
  explanation: string;
}

export interface RecommendationRun {
  run_id: string;
  post_id: string;
  status: "matched" | "no_confident_match";
  matching_config_version: string;
  embedding_model: string;
  embedding_version: string;
  recommendation: CandidateDecision | null;
  reason_code: "NO_CONFIDENT_MATCH" | null;
  rejected_candidates: CandidateDecision[];
  created_at: string;
}

export interface ReviewRecord {
  id: string;
  recommendation_id: string;
  decision: "approved" | "rejected";
  comment: string | null;
  reviewer_id: string | null;
  created_at: string;
}

export interface RecommendationDetail {
  id: string;
  run_id: string;
  post: PostRecord;
  candidate_image: ImageAsset;
  rank: number;
  similarity_score: number;
  image_subject: string;
  image_subject_code: string;
  image_category: string;
  image_tags: string[];
  expected_subject: string | null;
  expected_category: string | null;
  required_tags: string[];
  vision_confidence: number;
  metadata_valid: boolean;
  is_low_confidence: boolean;
  guard_decision: GuardDecision;
  guard_reason_code: GuardDecision;
  explanation: string;
  human_review_permitted: boolean;
  human_review_state: "pending" | "approved" | "rejected";
  current_review: ReviewRecord | null;
  created_at: string;
}

export interface EvaluationCandidateResult {
  fixture_image_id: string;
  rank: number;
  similarity_score: number;
  decision: GuardDecision;
  reason_code: GuardDecision;
  explanation: string;
  expected_decision: GuardDecision;
  decision_correct: boolean;
  acceptable: boolean;
  unsafe: boolean;
}

export interface EvaluationExampleResult {
  example_id: string;
  expected_result: string;
  actual_result: string;
  selected_image_id: string | null;
  correct: boolean;
  expected_subject: string | null;
  expected_category: string | null;
  candidates: EvaluationCandidateResult[];
}

export interface EvaluationRun {
  run_id: string;
  created_at: string;
  evaluator_version: string;
  dataset_version: string;
  config_version: string;
  embedding_model: string;
  embedding_version: string;
  minimum_similarity: number;
  minimum_vision_confidence: number;
  total_examples: number;
  eligible_recommendation_examples: number;
  correct_top1: number;
  incorrect_top1: number;
  correct_no_confident_match: number;
  incorrect_refusals: number;
  unsafe_acceptance_count: number;
  correct_safe_rejections: number;
  top1_precision: number;
  issued_recommendation_precision: number;
  safe_acceptance_precision: number;
  unsafe_rejection_recall: number;
  examples: EvaluationExampleResult[];
}
