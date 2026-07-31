export type ProviderStatus =
  | "succeeded"
  | "error"
  | "timed_out"
  | "rate_limited"
  | "disabled";

export interface SiteResponse {
  id: string;
  project_id: string;
  url: string;
  created_at: string;
  updated_at: string;
}

export interface CompetitorResponse {
  id: string;
  project_id: string;
  name: string;
  url: string;
  aliases: string[];
  created_at: string;
  updated_at: string;
}

export interface ProjectResponse {
  id: string;
  name: string;
  aliases: string[];
  site: SiteResponse | null;
  competitors: CompetitorResponse[];
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  aliases: string[];
  site: { url: string } | null;
  competitors: Array<{ name: string; url: string; aliases: string[] }>;
}

export interface ProviderAvailabilityResponse {
  name: string;
  model_identifier: string;
  enabled: boolean;
  disabled_reason: string | null;
}

export interface Citation {
  url: string;
  title: string | null;
  start_index: number | null;
  end_index: number | null;
  cited_text: string | null;
  published_at: string | null;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cached_tokens: number | null;
  reasoning_tokens: number | null;
}

export interface ProviderError {
  code: string;
  message: string;
  retryable: boolean;
  http_status: number | null;
  attempts: number;
}

export interface PromptExecutionResponse {
  provider: string;
  model_identifier: string;
  prompt: string;
  response_text: string;
  citations: Citation[];
  raw_response: Record<string, unknown>;
  token_usage: TokenUsage;
  latency_ms: number;
  status: ProviderStatus;
  error: ProviderError | null;
}

export interface AnalysisStartResponse {
  analysis_id: string;
  status: "succeeded" | "completed_with_errors" | "failed";
  started_at: string;
  completed_at: string;
  results: PromptExecutionResponse[];
  persisted: boolean;
}

export interface AnalysisCitationResponse {
  id: string;
  response_id: string;
  ordinal: number;
  url: string;
  normalized_domain: string | null;
  title: string | null;
  start_index: number | null;
  end_index: number | null;
  cited_text: string | null;
  published_at: string | null;
  normalization_rule_version: string;
}

export interface AnalysisEntityResponse {
  id: string;
  response_id: string;
  entity_key: string;
  name: string;
  kind: string;
  matched_aliases: string[];
  mention_count: number;
  first_mention_start: number;
  first_mention_relative: number;
  position_bucket: string;
  mentions: Array<Record<string, unknown>>;
  extraction_method: string;
  extraction_rule_version: string;
}

export interface AnalysisScoreResponse {
  id: string;
  analysis_run_id: string;
  name: string;
  numerator: number;
  denominator: number;
  value: number | null;
  percentage: number | null;
  is_defined: boolean;
  method: string;
  rule_version: string;
  is_objective_truth: boolean | null;
  disclaimer: string | null;
}

export interface ClaimEvidenceResponse {
  id: string;
  source_type: string;
  source_id: string;
  source_reference: string;
  url: string | null;
  excerpt: string;
  relevance_score: number;
  retrieval_rule_version: string;
}

export interface AnalysisClaimResponse {
  id: string;
  response_id: string;
  ordinal: number;
  claim_text: string;
  start_index: number;
  end_index: number;
  classification:
    | "supported"
    | "partially_supported"
    | "unsupported"
    | "contradicted"
    | "unverifiable";
  confidence: number;
  explanation: string;
  classifier: string;
  model_identifier: string | null;
  response_prompt: string;
  response_provider: string;
  segmentation_rule_version: string;
  evidence: ClaimEvidenceResponse[];
}

export interface CrawlJobResponse {
  id: string;
  site_id: string;
  status: "pending" | "running" | "succeeded" | "failed";
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  celery_task_id: string | null;
  page_count: number;
  error_count: number;
  created_at: string;
  updated_at: string;
}

export interface AnalysisRunResponse {
  id: string;
  project_id: string;
  crawl_job_id: string | null;
  status: "pending" | "running" | "succeeded" | "completed_with_errors" | "failed";
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface HealthResponse {
  status: "ok";
}

export interface ReadinessResponse {
  status: "ok" | "unavailable";
}

export interface AnalysisBundle {
  analysis: AnalysisStartResponse;
  citations: AnalysisCitationResponse[];
  entities: AnalysisEntityResponse[];
  scores: AnalysisScoreResponse[];
  claims: AnalysisClaimResponse[];
}
