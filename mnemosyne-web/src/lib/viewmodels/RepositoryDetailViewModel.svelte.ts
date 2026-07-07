/** Repository detail tabs state (spec: web-ui). Lazy-loads per tab. */
import { ApiError } from '$lib/api/http';
import type { RepositoriesApi } from '$lib/api/mnemosyneApi';
import type {
  Document,
  DocumentSummary,
  Issue,
  Metrics,
  OpenSpecChange,
  PullRequest,
  RepositorySummary,
  SourceFile
} from '$lib/models';

export type Tab =
  | 'overview'
  | 'documentation'
  | 'openspec'
  | 'issues'
  | 'pull-requests'
  | 'files'
  | 'metrics'
  | 'code-context'
  | 'agent-context';

export class RepositoryDetailViewModel {
  tab = $state<Tab>('overview');
  summary = $state<RepositorySummary | null>(null);
  docs = $state<DocumentSummary[]>([]);
  selectedDoc = $state<Document | null>(null);
  openspec = $state<OpenSpecChange[]>([]);
  issues = $state<Issue[]>([]);
  pullRequests = $state<PullRequest[]>([]);
  files = $state<SourceFile[]>([]);
  metrics = $state<Metrics | null>(null);
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

  async openDoc(docId: string): Promise<void> {
    this.selectedDoc = await this.api.doc(this.repoId, docId);
  }

  closeDoc(): void {
    this.selectedDoc = null;
  }
}
