/** Repository detail tabs state (spec: web-ui). Lazy-loads per tab. */
import { ApiError } from '$lib/api/http';
import type { RepositoriesApi } from '$lib/api/mnemosyneApi';
import type {
  AgentMemory,
  Document,
  DocumentSummary,
  FeatureDocument,
  Issue,
  Metrics,
  OpenSpecChange,
  PullRequest,
  RepositoryCapabilities,
  RepositorySummary,
  SourceFile
} from '$lib/models';

export type Tab =
  | 'overview'
  | 'capabilities'
  | 'documentation'
  | 'openspec'
  | 'issues'
  | 'pull-requests'
  | 'files'
  | 'metrics'
  | 'memory'
  | 'code-context'
  | 'agent-context';

export class RepositoryDetailViewModel {
  tab = $state<Tab>('overview');
  summary = $state<RepositorySummary | null>(null);
  capabilities = $state<RepositoryCapabilities | null>(null);
  featureDoc = $state<FeatureDocument | null>(null);
  featureDocBusy = $state(false);
  docs = $state<DocumentSummary[]>([]);
  selectedDoc = $state<Document | null>(null);
  openspec = $state<OpenSpecChange[]>([]);
  issues = $state<Issue[]>([]);
  pullRequests = $state<PullRequest[]>([]);
  files = $state<SourceFile[]>([]);
  metrics = $state<Metrics | null>(null);
  memories = $state<AgentMemory[]>([]);
  error = $state<string | null>(null);
  loading = $state(false);

  constructor(
    private api: RepositoriesApi,
    public repoId: string
  ) {}

  async open(tab: Tab): Promise<void> {
    this.tab = tab;
    this.error = null;
    this.loading = true;
    try {
      switch (tab) {
        case 'overview':
          this.summary = await this.api.summary(this.repoId);
          break;
        case 'capabilities':
          this.capabilities = await this.api.capabilities(this.repoId);
          break;
        case 'documentation':
          this.docs = (await this.api.docs(this.repoId)).items;
          break;
        case 'openspec':
          this.openspec = await this.api.openspec(this.repoId);
          break;
        case 'issues':
          this.issues = (await this.api.issues(this.repoId)).items;
          break;
        case 'pull-requests':
          this.pullRequests = (await this.api.pullRequests(this.repoId)).items;
          break;
        case 'files':
          this.files = (await this.api.files(this.repoId)).items;
          break;
        case 'metrics':
          this.metrics = await this.api.metrics(this.repoId);
          break;
        case 'memory':
          this.memories = (await this.api.memories(this.repoId)).memories;
          break;
        case 'code-context':
        case 'agent-context':
          break;
      }
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : `failed to load ${tab}`;
    } finally {
      this.loading = false;
    }
  }

  async generateFeatureDoc(): Promise<void> {
    if (this.featureDocBusy) return;
    this.featureDocBusy = true;
    this.error = null;
    try {
      this.featureDoc = await this.api.featureDocument(this.repoId);
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'failed to generate document';
    } finally {
      this.featureDocBusy = false;
    }
  }

  async addMemory(content: string, kind: string): Promise<boolean> {
    if (!content.trim()) return false;
    this.error = null;
    try {
      const created = await this.api.createMemory(this.repoId, content.trim(), kind);
      this.memories = [created, ...this.memories];
      return true;
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'failed to save memory';
      return false;
    }
  }

  async deleteMemory(memoryId: string): Promise<void> {
    this.error = null;
    try {
      await this.api.deleteMemory(this.repoId, memoryId);
      this.memories = this.memories.filter((m) => m.id !== memoryId);
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'failed to delete memory';
    }
  }

  async openDoc(docId: string): Promise<void> {
    this.selectedDoc = await this.api.doc(this.repoId, docId);
  }

  closeDoc(): void {
    this.selectedDoc = null;
  }
}
