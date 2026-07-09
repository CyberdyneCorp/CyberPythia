/** Intelligence dashboard: portfolio overview + per-repo health (spec: web-ui). */
import { ApiError } from '$lib/api/http';
import type { IntelligenceApi } from '$lib/api/mnemosyneApi';
import type {
  OrganizationIntelligence,
  PortfolioOverview,
  RecentActivity,
  RepositoryHealth,
  StaleItem
} from '$lib/models';

export class IntelligenceViewModel {
  overview = $state<PortfolioOverview | null>(null);
  organizations = $state<string[]>([]); // stable full list (from the unscoped load)
  orgIntel = $state<OrganizationIntelligence | null>(null);
  activity = $state<RecentActivity | null>(null);
  staleIssues = $state<StaleItem[]>([]);
  stalePrs = $state<StaleItem[]>([]);
  busy = $state(false);
  error = $state<string | null>(null);

  constructor(private api: IntelligenceApi) {}

  /** Load the (optionally org-scoped) portfolio. The org list is captured once from
   *  the first unscoped load so the dropdown stays complete when scoped. */
  async loadPortfolio(organization?: string): Promise<void> {
    this.busy = true;
    this.error = null;
    try {
      this.overview = await this.api.portfolio(organization);
      if (!organization && this.overview) {
        this.organizations = Array.from(
          new Set(this.overview.leaderboard.map((e) => e.full_name.split('/')[0]))
        ).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
      }
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'failed to load portfolio';
    } finally {
      this.busy = false;
    }
  }

  /** Org rollup + activity + stale, scoped to `org` ('' = whole portfolio). */
  async loadOrgDetail(org: string): Promise<void> {
    const scope = org || undefined;
    try {
      const [activity, issues, prs] = await Promise.all([
        this.api.recentActivity(scope, 10),
        this.api.staleIssues(scope, 30, 10),
        this.api.stalePrs(scope, 30, 10)
      ]);
      this.activity = activity;
      this.staleIssues = issues.stale;
      this.stalePrs = prs.stale;
      this.orgIntel = org ? await this.api.organizationIntelligence(org) : null;
    } catch {
      // supplementary panels are best-effort; ignore load failures
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
