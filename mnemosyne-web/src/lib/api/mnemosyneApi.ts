/** Typed API clients over HttpClient (MVVM: viewmodels depend on these, views never do). */
import type { HttpClient } from '$lib/api/http';
import type {
  AskResult,
  CodeChunkMatch,
  Connection,
  ConnectionTest,
  ContextPack,
  Document,
  FileContent,
  DocumentSummary,
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
  Page,
  PortfolioOverview,
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

export class RepositoriesApi {
  constructor(private http: HttpClient) {}

  list(page = 1, pageSize = 100): Promise<Page<Repository>> {
    return this.http.get(`/api/v1/repos?page=${page}&page_size=${pageSize}`);
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

  portfolio(): Promise<PortfolioOverview> {
    return this.http.get('/api/v1/intelligence/portfolio');
  }
  health(repoId: string): Promise<RepositoryHealth> {
    return this.http.get(`/api/v1/intelligence/repositories/${repoId}/health`);
  }
  maintenanceRisk(repoId: string): Promise<MaintenanceRisk> {
    return this.http.get(`/api/v1/intelligence/repositories/${repoId}/maintenance-risk`);
  }
  deliveryScorecard(): Promise<{ scorecard: DeliveryScorecardEntry[] }> {
    return this.http.get('/api/v1/intelligence/delivery-scorecard');
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
}
