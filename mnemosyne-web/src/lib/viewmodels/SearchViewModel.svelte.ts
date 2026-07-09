/** Portfolio-wide search across repositories (spec: web-ui). */
import { ApiError } from '$lib/api/http';
import type { IntelligenceApi, RepositoriesApi } from '$lib/api/mnemosyneApi';
import type { RepositoryBrief, SearchResult } from '$lib/models';

type Kind = 'docs' | 'code' | 'issues' | 'repositories';

export class SearchViewModel {
  query = $state('');
  kind = $state<Kind>('docs');
  organization = $state('');
  organizations = $state<string[]>([]);
  results = $state<SearchResult[]>([]);
  repos = $state<RepositoryBrief[]>([]);
  busy = $state(false);
  searched = $state(false);
  error = $state<string | null>(null);

  constructor(
    private intelligenceApi: IntelligenceApi,
    private repositoriesApi: RepositoriesApi
  ) {}

  /** Populate the organization dropdown from indexed repo owners (best-effort). */
  async loadOrganizations(): Promise<void> {
    try {
      const page = await this.repositoriesApi.list(1, 100);
      this.organizations = Array.from(
        new Set(page.items.map((r) => r.full_name.split('/')[0]))
      ).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
    } catch {
      // dropdown is a convenience; ignore load failures
    }
  }

  async run(): Promise<void> {
    const q = this.query.trim();
    if (q.length < 2 || this.busy) return;
    this.busy = true;
    this.error = null;
    this.results = [];
    this.repos = [];
    const org = this.organization || undefined;
    try {
      if (this.kind === 'repositories') {
        this.repos = (await this.repositoriesApi.find(q)).repositories;
      } else {
        this.results = (await this.intelligenceApi.search(q, this.kind, org)).results;
      }
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'search failed';
    } finally {
      this.busy = false;
      this.searched = true;
    }
  }
}
