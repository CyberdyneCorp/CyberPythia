/** Typed API clients over HttpClient (MVVM: viewmodels depend on these, views never do). */
import type { HttpClient } from '$lib/api/http';
import type {
  ApiKey,
  ApiKeyCreated,
  AppManifestBootstrap,
  AskResult,
  CodeChunkMatch,
  Connection,
  ConnectionTest,
  ContextPack,
  Document,
  FeatureDocument,
  FileContent,
  DocumentSummary,
  RepositoryCapabilities,
  IndexingMode,
  Issue,
  BacklogForecast,
  DeliveryScorecardEntry,
  FlowMetrics,
  MaintenanceRisk,
  Metrics,
  MilestoneProgress,
  OpenSpecChange,
  Organization,
  OrganizationIntelligence,
  Page,
  PortfolioOverview,
  RecentActivity,
  RepositoryBrief,
  SearchResult,
  StaleItem,
  PullRequest,
  Repository,
  RepositoryHealth,
  ThroughputTrend,
  WorkMix,
  RepositorySummary,
  WebhookDelivery,
  SearchMatch,
  SourceFile,
  SyncJob,
  SyncJobSummary,
  SyncRun
} from '$lib/models';

export class GitHubApi {
  constructor(private http: HttpClient) {}

  connect(token: string): Promise<Connection> {
    return this.http.post('/api/v1/github/connect', { token });
  }
  connectApp(
    appId: string,
    installationId: string,
    privateKey: string,
    webhookSecret: string
  ): Promise<Connection> {
    return this.http.post('/api/v1/github/app/connect', {
      app_id: appId,
      installation_id: installationId,
      private_key: privateKey,
      webhook_secret: webhookSecret
    });
  }
  discoverAppRepos(connectionId: string): Promise<Repository[]> {
    return this.http.post(`/api/v1/github/app/installations/${connectionId}/repos`);
  }
  webhookDeliveries(): Promise<WebhookDelivery[]> {
    return this.http.get('/api/v1/admin/webhook-deliveries');
  }
  organizations(): Promise<Organization[]> {
    return this.http.get('/api/v1/github/organizations');
  }
  setOrganizationSync(login: string, syncEnabled: boolean): Promise<Organization> {
    return this.http.patch(`/api/v1/github/organizations/${encodeURIComponent(login)}`, {
      sync_enabled: syncEnabled
    });
  }
  appManifest(organization: string): Promise<AppManifestBootstrap> {
    return this.http.get(
      `/api/v1/github/app/manifest?organization=${encodeURIComponent(organization)}`
    );
  }
  bulkSelectionByOrg(
    organization: string,
    enabled: boolean,
    mode?: IndexingMode
  ): Promise<{ updated: number }> {
    return this.http.post('/api/v1/repos/selection', {
      organization,
      enabled,
      indexing_mode: mode ?? null
    });
  }
  syncRuns(): Promise<SyncRun[]> {
    return this.http.get('/api/v1/admin/sync-runs');
  }
  syncJobs(): Promise<SyncJobSummary[]> {
    return this.http.get('/api/v1/admin/sync-jobs');
  }
  listConnections(): Promise<Connection[]> {
    return this.http.get('/api/v1/github/connections');
  }
  testConnection(id: string): Promise<ConnectionTest> {
    return this.http.post(`/api/v1/github/connections/${id}/test`);
  }
  deleteConnection(id: string): Promise<void> {
    return this.http.delete(`/api/v1/github/connections/${id}`);
  }
}

export class ApiKeysApi {
  constructor(private http: HttpClient) {}

  list(): Promise<ApiKey[]> {
    return this.http.get('/api/v1/api-keys');
  }
  create(label: string, expiresInDays: number | null): Promise<ApiKeyCreated> {
    return this.http.post('/api/v1/api-keys', {
      label,
      expires_in_days: expiresInDays
    });
  }
  revoke(id: string): Promise<void> {
    return this.http.post(`/api/v1/api-keys/${id}/revoke`);
  }
  remove(id: string): Promise<void> {
    return this.http.delete(`/api/v1/api-keys/${id}`);
  }
}

export class RepositoriesApi {
  constructor(private http: HttpClient) {}

  list(page = 1, pageSize = 100): Promise<Page<Repository>> {
    return this.http.get(`/api/v1/repos?page=${page}&page_size=${pageSize}`);
  }
  /** Fuzzy-resolve a vague query into matching repositories. */
  find(query: string, limit = 10): Promise<{ repositories: RepositoryBrief[] }> {
    const params = new URLSearchParams({ query, limit: String(limit) });
    return this.http.get(`/api/v1/repos/find?${params}`);
  }
  /** All discovered repositories (follows pagination, hard-capped at 20 pages). */
  async listAll(): Promise<Repository[]> {
    const items: Repository[] = [];
    let page: number | null = 1;
    for (let i = 0; i < 20 && page !== null; i++) {
      const result: Page<Repository> = await this.list(page, 100);
      items.push(...result.items);
      page = result.next_page;
    }
    return items;
  }
  discover(connectionId: string): Promise<Repository[]> {
    return this.http.post(`/api/v1/repos/discover/${connectionId}`);
  }
  updateSelection(id: string, enabled: boolean, mode?: IndexingMode): Promise<Repository> {
    return this.http.patch(`/api/v1/repos/${id}`, { enabled, indexing_mode: mode ?? null });
  }
  bulkSelection(
    ids: string[],
    enabled: boolean,
    mode?: IndexingMode
  ): Promise<{ updated: number }> {
    return this.http.post('/api/v1/repos/selection', {
      repository_ids: ids,
      enabled,
      indexing_mode: mode ?? null
    });
  }
  sync(id: string): Promise<SyncJob> {
    return this.http.post(`/api/v1/repos/${id}/sync`);
  }
  syncStatus(id: string): Promise<SyncJob | null> {
    return this.http.get(`/api/v1/repos/${id}/sync-status`);
  }
  summary(id: string): Promise<RepositorySummary> {
    return this.http.get(`/api/v1/repos/${id}/summary`);
  }
  docs(id: string): Promise<Page<DocumentSummary>> {
    return this.http.get(`/api/v1/repos/${id}/docs?page_size=100`);
  }
  doc(id: string, docId: string): Promise<Document> {
    return this.http.get(`/api/v1/repos/${id}/docs/${docId}`);
  }
  openspec(id: string): Promise<OpenSpecChange[]> {
    return this.http.get(`/api/v1/repos/${id}/openspec`);
  }
  issues(id: string, state?: string): Promise<Page<Issue>> {
    const query = state ? `&state=${state}` : '';
    return this.http.get(`/api/v1/repos/${id}/issues?page_size=100${query}`);
  }
  pullRequests(id: string, state?: string): Promise<Page<PullRequest>> {
    const query = state ? `&state=${state}` : '';
    return this.http.get(`/api/v1/repos/${id}/pull-requests?page_size=100${query}`);
  }
  files(id: string): Promise<Page<SourceFile>> {
    return this.http.get(`/api/v1/repos/${id}/files?page_size=100`);
  }
  metrics(id: string): Promise<Metrics> {
    return this.http.get(`/api/v1/repos/${id}/metrics`);
  }
  capabilities(id: string): Promise<RepositoryCapabilities> {
    return this.http.get(`/api/v1/repos/${id}/capabilities`);
  }
  featureDocument(id: string): Promise<FeatureDocument> {
    return this.http.post(`/api/v1/repos/${id}/feature-document`);
  }
}

export class ContextApi {
  constructor(private http: HttpClient) {}

  search(repoId: string, query: string): Promise<SearchMatch[]> {
    return this.http.post(`/api/v1/repos/${repoId}/search`, { query });
  }
  ask(repoId: string, question: string): Promise<AskResult> {
    return this.http.post(`/api/v1/repos/${repoId}/ask`, { question });
  }
  buildContextPack(repoId: string, query: string): Promise<ContextPack> {
    return this.http.post(`/api/v1/repos/${repoId}/context-pack`, { query });
  }
}

export class CodeApi {
  constructor(private http: HttpClient) {}

  search(repoId: string, query: string): Promise<CodeChunkMatch[]> {
    return this.http.post(`/api/v1/repos/${repoId}/code-search`, { query });
  }
  fileContent(repoId: string, fileId: string): Promise<FileContent> {
    return this.http.get(`/api/v1/repos/${repoId}/files/${fileId}/content`);
  }
}

export class IntelligenceApi {
  constructor(private http: HttpClient) {}

  portfolio(organization?: string): Promise<PortfolioOverview> {
    const q = organization ? `?organization=${encodeURIComponent(organization)}` : '';
    return this.http.get(`/api/v1/intelligence/portfolio${q}`);
  }
  health(repoId: string): Promise<RepositoryHealth> {
    return this.http.get(`/api/v1/intelligence/repositories/${repoId}/health`);
  }
  maintenanceRisk(repoId: string): Promise<MaintenanceRisk> {
    return this.http.get(`/api/v1/intelligence/repositories/${repoId}/maintenance-risk`);
  }
  deliveryScorecard(organization?: string): Promise<{ scorecard: DeliveryScorecardEntry[] }> {
    const q = organization ? `?organization=${encodeURIComponent(organization)}` : '';
    return this.http.get(`/api/v1/intelligence/delivery-scorecard${q}`);
  }
  flow(repoId: string): Promise<FlowMetrics> {
    return this.http.get(`/api/v1/intelligence/repositories/${repoId}/flow`);
  }
  throughput(repoId: string): Promise<ThroughputTrend> {
    return this.http.get(`/api/v1/intelligence/repositories/${repoId}/throughput`);
  }
  forecast(repoId: string): Promise<BacklogForecast> {
    return this.http.get(`/api/v1/intelligence/repositories/${repoId}/forecast`);
  }
  workMix(repoId: string): Promise<WorkMix> {
    return this.http.get(`/api/v1/intelligence/repositories/${repoId}/work-mix`);
  }
  milestones(repoId: string): Promise<{ milestones: MilestoneProgress[] }> {
    return this.http.get(`/api/v1/intelligence/repositories/${repoId}/milestones`);
  }
  organizationIntelligence(org: string): Promise<OrganizationIntelligence> {
    return this.http.get(
      `/api/v1/intelligence/organizations/${encodeURIComponent(org)}/intelligence`
    );
  }
  search(
    query: string,
    kind: 'docs' | 'code' | 'issues',
    organization?: string,
    limit = 20
  ): Promise<{ results: SearchResult[] }> {
    const params = new URLSearchParams({ query, kind, limit: String(limit) });
    if (organization) params.set('organization', organization);
    return this.http.get(`/api/v1/intelligence/search?${params}`);
  }
  staleIssues(organization?: string, thresholdDays = 30, limit = 50): Promise<{ stale: StaleItem[] }> {
    const params = new URLSearchParams({ threshold_days: String(thresholdDays), limit: String(limit) });
    if (organization) params.set('organization', organization);
    return this.http.get(`/api/v1/intelligence/stale-issues?${params}`);
  }
  stalePrs(organization?: string, thresholdDays = 30, limit = 50): Promise<{ stale: StaleItem[] }> {
    const params = new URLSearchParams({ threshold_days: String(thresholdDays), limit: String(limit) });
    if (organization) params.set('organization', organization);
    return this.http.get(`/api/v1/intelligence/stale-prs?${params}`);
  }
  recentActivity(organization?: string, limit = 15): Promise<RecentActivity> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (organization) params.set('organization', organization);
    return this.http.get(`/api/v1/intelligence/recent-activity?${params}`);
  }
}
