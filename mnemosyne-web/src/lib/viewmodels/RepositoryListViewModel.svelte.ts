/** Repository dashboard state: selection, sync trigger, live status (spec: web-ui). */
import { ApiError } from '$lib/api/http';
import type { RepositoriesApi } from '$lib/api/mnemosyneApi';
import type { IndexingMode, Repository, SyncJob } from '$lib/models';

const POLL_INTERVAL_MS = 2500;

export class RepositoryListViewModel {
  repositories = $state<Repository[]>([]);
  syncJobs = $state<Record<string, SyncJob>>({});
  loading = $state(false);
  error = $state<string | null>(null);
  filter = $state('');
  organizationFilter = $state('');

  constructor(
    private api: RepositoriesApi,
    private pollIntervalMs: number = POLL_INTERVAL_MS
  ) {}

  async load(): Promise<void> {
    this.loading = true;
    this.error = null;
    try {
      const repos = await this.api.listAll();
      // indexed repositories first, then alphabetical (345+ discovered repos
      // buried the enabled ones on the deployed dashboard)
      this.repositories = repos.sort((a, b) =>
        a.enabled === b.enabled
          ? a.full_name.localeCompare(b.full_name)
          : a.enabled
            ? -1
            : 1
      );
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'failed to load repositories';
    } finally {
      this.loading = false;
    }
  }

  /** Distinct organization logins (owners) present in the loaded repositories, sorted. */
  get organizations(): string[] {
    const owners = new Set(this.repositories.map((r) => r.full_name.split('/')[0]));
    return [...owners].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
  }

  get filtered(): Repository[] {
    const needle = this.filter.trim().toLowerCase();
    const org = this.organizationFilter;
    return this.repositories.filter((r) => {
      if (org && r.full_name.split('/')[0] !== org) return false;
      if (needle && !r.full_name.toLowerCase().includes(needle)) return false;
      return true;
    });
  }

  async setSelection(repo: Repository, enabled: boolean, mode?: IndexingMode): Promise<void> {
    const updated = await this.api.updateSelection(repo.id, enabled, mode);
    this.repositories = this.repositories.map((r) => (r.id === updated.id ? updated : r));
  }

  async triggerSync(repo: Repository): Promise<void> {
    this.error = null;
    try {
      const job = await this.api.sync(repo.id);
      this.syncJobs = { ...this.syncJobs, [repo.id]: job };
      void this.pollUntilDone(repo.id);
    } catch (error) {
      if (error instanceof ApiError && error.code === 'sync_already_running') {
        void this.pollUntilDone(repo.id);
      } else {
        this.error = error instanceof ApiError ? error.message : 'sync failed';
      }
    }
  }

  /** Poll sync status until it settles; refresh the repo row at the end. */
  async pollUntilDone(repoId: string): Promise<void> {
    for (;;) {
      const job = await this.api.syncStatus(repoId);
      if (job) this.syncJobs = { ...this.syncJobs, [repoId]: job };
      if (!job || job.status === 'succeeded' || job.status === 'failed') break;
      await new Promise((resolve) => setTimeout(resolve, this.pollIntervalMs));
    }
    await this.load();
  }

  syncStateFor(repoId: string): string | null {
    return this.syncJobs[repoId]?.status ?? null;
  }
}
