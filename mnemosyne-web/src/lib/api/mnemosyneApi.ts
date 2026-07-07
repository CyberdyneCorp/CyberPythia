/** Typed API clients over HttpClient (MVVM: viewmodels depend on these, views never do). */
import type { HttpClient } from '$lib/api/http';
import type {
  AskResult,
  Connection,
  ConnectionTest,
  ContextPack,
  Document,
  DocumentSummary,
  IndexingMode,
  Issue,
  Metrics,
  OpenSpecChange,
  Page,
  PullRequest,
  Repository,
  RepositorySummary,
  SearchMatch,
  SourceFile,
  SyncJob
} from '$lib/models';

export class GitHubApi {
  constructor(private http: HttpClient) {}

  connect(token: string): Promise<Connection> {
    return this.http.post('/api/v1/github/connect', { token });
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
  discover(connectionId: string): Promise<Repository[]> {
    return this.http.post(`/api/v1/repos/discover/${connectionId}`);
  }
  updateSelection(id: string, enabled: boolean, mode?: IndexingMode): Promise<Repository> {
    return this.http.patch(`/api/v1/repos/${id}`, { enabled, indexing_mode: mode ?? null });
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
