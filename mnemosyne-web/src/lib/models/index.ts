// Models mirroring the Mnemosyne API schemas (spec: rest-api).

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  next_page: number | null;
}

export interface Connection {
  id: string;
  owner: string;
  owner_type: string;
  kind: string;
  token_hint: string;
  permissions: string[];
  status: string;
  installation_id: string | null;
}

export interface WebhookDelivery {
  delivery_id: string;
  event: string;
  action: string | null;
  repository_full_name: string | null;
  outcome: string;
  received_at: string;
}

export interface ConnectionTest {
  ok: boolean;
  status: string;
  permissions?: string[];
  rate_limit?: { limit: number; remaining: number };
}

export type IndexingMode =
  | 'docs_only'
  | 'project_intelligence'
  | 'code_metadata'
  | 'code_context'
  | 'full_context';

export interface Repository {
  id: string;
  full_name: string;
  description: string | null;
  visibility: string;
  default_branch: string;
  primary_language: string | null;
  archived: boolean;
  enabled: boolean;
  indexing_mode: IndexingMode;
  last_synced_at: string | null;
}

export interface SyncStep {
  step: string;
  status: string;
  error: string | null;
  items_processed: number;
}

export interface SyncJob {
  id: string;
  repository_id: string;
  mode: IndexingMode;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  steps: SyncStep[];
  started_at: string | null;
  finished_at: string | null;
}

export interface DocumentSummary {
  id: string;
  path: string;
  type: string;
  title: string;
  quarantined: boolean;
  captured_at: string | null;
}

export interface Document extends DocumentSummary {
  content: string | null;
}

export interface OpenSpecChange {
  change_id: string;
  path: string;
  status: string;
  proposal: string | null;
  design: string | null;
  tasks: string | null;
  affected_specs: string[];
}

export interface Issue {
  number: number;
  title: string;
  state: string;
  author: string | null;
  labels: string[];
  assignees: string[];
  created_at: string | null;
  closed_at: string | null;
  resolution_time_seconds: number | null;
  comments_count: number;
}

export interface PullRequest {
  number: number;
  title: string;
  state: string;
  merged: boolean;
  author: string | null;
  reviewers: string[];
  created_at: string | null;
  merged_at: string | null;
  time_to_merge_seconds: number | null;
  time_to_first_review_seconds: number | null;
  additions: number;
  deletions: number;
}

export interface SourceFile {
  path: string;
  extension: string | null;
  language: string | null;
  size_bytes: number;
  is_binary: boolean;
  is_important: boolean;
  important_kind: string | null;
}

export interface RepositorySummary {
  repository: Repository;
  summary: Record<string, unknown> | null;
  computed_at: string | null;
}

export interface Metrics {
  issue_metrics: Record<string, unknown>;
  pr_metrics: Record<string, unknown>;
  summary: Record<string, unknown>;
  computed_at: string;
}

export interface SearchMatch {
  path: string;
  title: string;
  doc_type: string;
  excerpt: string;
  score: number;
}

export interface AskResult {
  answer: string;
  sources: { path: string; title: string; score: number }[];
  grounded: boolean;
}

export interface ContextPack {
  id: string;
  repository_id: string;
  query: string;
  mode: IndexingMode;
  repository_summary: string;
  relevant_docs: { path: string; title: string; doc_type: string; score: number; excerpt?: string }[];
  relevant_openspec_changes: { change_id: string; path: string; status: string; score: number }[];
  relevant_issues: { number: number; title: string; state: string; score: number }[];
  relevant_pull_requests: { number: number; title: string; state: string; score: number }[];
  relevant_files: { path: string; kind: string | null; score: number }[];
  risks: string[];
  suggested_next_steps: string[];
  excluded_categories: string[];
  sync_timestamp: string | null;
  created_at: string | null;
}

export interface CodeChunkMatch {
  path: string;
  symbol_name: string | null;
  chunk_type: string;
  start_line: number;
  end_line: number;
  excerpt: string;
  score: number;
}

export interface FileContent {
  path: string;
  language: string | null;
  size_bytes: number;
  content: string;
}
