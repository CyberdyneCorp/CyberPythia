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

export interface Organization {
  login: string;
  sync_enabled: boolean;
  total_repos: number;
  enabled_repos: number;
}

export interface AppManifestBootstrap {
  manifest: Record<string, unknown>;
  post_url: string;
  state: string;
}

export interface ApiKey {
  id: string;
  label: string;
  prefix: string;
  created_by: string;
  created_at: string;
  expires_at: string | null;
  revoked: boolean;
}

/** Creation response — carries the plaintext key exactly once. */
export interface ApiKeyCreated extends ApiKey {
  key: string;
}

export interface SyncRun {
  id: string;
  trigger: string;
  started_at: string;
  finished_at: string;
  discovered: number;
  newly_enabled: number;
  skipped_archived: number;
  enqueued: number;
  skipped: number;
  failed: number;
}

export interface SyncJobSummary {
  id: string;
  repository_id: string;
  repository_full_name: string | null;
  mode: string;
  status: string;
  triggered_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  errors: string[];
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

export interface HealthComponent {
  name: string;
  weight: number;
  score: number | null;
  inputs: Record<string, unknown>;
}

export interface HealthFinding {
  severity: 'info' | 'warning' | 'critical';
  message: string;
  metric: string;
}

export interface RepositoryHealth {
  has_data: boolean;
  overall: number | null;
  grade: string | null;
  components: HealthComponent[];
  findings: HealthFinding[];
}

export interface PortfolioEntry {
  repository_id: string;
  full_name: string;
  has_data: boolean;
  overall: number | null;
  grade: string | null;
}

export interface PortfolioOverview {
  total_repositories: number;
  scored: number;
  leaderboard: PortfolioEntry[];
  most_active: string[];
  abandoned: string[];
  bug_heavy: string[];
}

export interface MaintenanceRisk {
  has_data: boolean;
  level: string;
  reasons: string[];
}

export interface PercentileBlock {
  n: number;
  p50: number | null;
  p85: number | null;
  p95: number | null;
}

export interface FlowMetrics {
  has_data: boolean;
  resolution_seconds: PercentileBlock;
  merge_seconds: PercentileBlock;
  wip_issues: number;
  wip_prs: number;
  issue_aging: Record<string, number>;
  pr_aging: Record<string, number>;
  untriaged_issues: number;
}

export interface TrendPoint {
  date: string;
  closed_issues: number;
  open_issues: number;
  net_flow: number;
}

export interface ThroughputTrend {
  has_data: boolean;
  points: TrendPoint[];
  reason: string | null;
}

export interface BacklogForecast {
  has_data: boolean;
  open_issues: number;
  close_rate_per_day: number | null;
  projected_days_to_clear: number | null;
  projected_clear_date: string | null;
  reason: string | null;
}

export interface WorkMix {
  has_data: boolean;
  distribution: Record<string, number>;
  bug_ratio: number | null;
}

export interface MilestoneProgress {
  number: number;
  title: string;
  state: string;
  percent_complete: number | null;
  open_issues: number;
  closed_issues: number;
  due_on: string | null;
  projected_completion: string | null;
  at_risk: boolean;
}

export interface DeliveryScorecardEntry {
  repository_id: string;
  full_name: string;
  has_data: boolean;
  median_cycle_days: number | null;
  throughput_direction: string | null;
  backlog_shrinking: boolean | null;
  at_risk_milestones: number;
}

export interface OrganizationIntelligence {
  organization: string;
  total_repositories: number;
  scored: number;
  average_health: number | null;
  median_health: number | null;
  grade_distribution: Record<string, number>;
  at_risk_milestones: number;
  throughput_directions: Record<string, number>;
  backlog_shrinking_repos: number;
  most_active: string[];
  abandoned: string[];
  bug_heavy: string[];
}

export type ReadinessGate = 'MVP' | 'READY' | 'DONE';

export interface ReadinessRepo {
  repository_id: string;
  full_name: string;
  gate: ReadinessGate;
  missing_for_ready: string[];
}

export interface OrganizationReadiness {
  organization: string;
  total: number;
  distribution: Record<ReadinessGate, number>;
  repositories: ReadinessRepo[];
}

export interface OpenSpecCoverageRepo {
  repository_id: string;
  full_name: string;
  primary_language: string | null;
  openspec_changes: number;
  last_synced_at: string | null;
}

export interface OpenSpecCoverage {
  organization: string;
  total: number;
  with_openspec: OpenSpecCoverageRepo[];
  without_openspec: OpenSpecCoverageRepo[];
  coverage: number;
}

/** A cross-repo search hit; fields present depend on `kind`. */
export interface SearchResult {
  repository_id: string;
  full_name: string;
  path?: string;
  title?: string;
  symbol?: string | null;
  start_line?: number;
  excerpt?: string;
  number?: number;
  state?: string;
  labels?: string[];
  score: number;
}

export interface StaleItem {
  repository_id: string;
  full_name: string;
  number: number;
  title: string;
  labels?: string[];
  author?: string | null;
  updated_at: string;
  stale_days: number;
}

export interface RecentActivity {
  recently_synced: { repository_id: string; full_name: string; last_synced_at: string }[];
  recent_issues: {
    repository_id: string;
    full_name: string;
    number: number;
    title: string;
    state: string;
    updated_at: string;
  }[];
  recent_pull_requests: {
    repository_id: string;
    full_name: string;
    number: number;
    title: string;
    state: string;
    merged: boolean;
    updated_at: string;
  }[];
}

export interface RepositoryCapabilities {
  full_name: string;
  description: string | null;
  primary_language: string | null;
  capabilities: string[];
  openspec_changes: number;
  documentation_topics: string[];
  documents: number;
  issues: { open: number; closed: number; bugs: number };
  pull_requests: { open: number; merged: number };
}

export interface FeatureDocument {
  document: string;
  sources: { path: string }[];
  grounded: boolean;
}

export interface RepositoryBrief {
  repository_id: string;
  full_name: string;
  description: string | null;
  primary_language: string | null;
  indexing_mode: string;
  last_synced_at: string | null;
}
