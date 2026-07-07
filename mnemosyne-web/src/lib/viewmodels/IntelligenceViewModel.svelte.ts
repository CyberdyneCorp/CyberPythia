/** Intelligence dashboard: portfolio overview + per-repo health (spec: web-ui). */
import { ApiError } from '$lib/api/http';
import type { IntelligenceApi } from '$lib/api/mnemosyneApi';
import type { PortfolioOverview, RepositoryHealth } from '$lib/models';

export class IntelligenceViewModel {
  overview = $state<PortfolioOverview | null>(null);
  busy = $state(false);
  error = $state<string | null>(null);

  constructor(private api: IntelligenceApi) {}

  async loadPortfolio(): Promise<void> {
    this.busy = true;
    this.error = null;
    try {
      this.overview = await this.api.portfolio();
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'failed to load portfolio';
    } finally {
      this.busy = false;
    }
  }
}

/** Health panel on the repository detail page. */
export class RepositoryHealthViewModel {
  health = $state<RepositoryHealth | null>(null);
  busy = $state(false);
  error = $state<string | null>(null);

  constructor(
    private api: IntelligenceApi,
    private repoId: string
  ) {}

  async load(): Promise<void> {
    this.busy = true;
    this.error = null;
    try {
      this.health = await this.api.health(this.repoId);
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'failed to load health';
    } finally {
      this.busy = false;
    }
  }
}
