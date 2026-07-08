/** Admin GitHub connection screen state (spec: web-ui). */
import { ApiError } from '$lib/api/http';
import type { GitHubApi, RepositoriesApi } from '$lib/api/mnemosyneApi';
import type {
  Connection,
  ConnectionTest,
  IndexingMode,
  Organization,
  Repository,
  SyncJobSummary,
  SyncRun,
  WebhookDelivery
} from '$lib/models';

export class ConnectionsViewModel {
  connections = $state<Connection[]>([]);
  testResults = $state<Record<string, ConnectionTest>>({});
  discovered = $state<Repository[] | null>(null);
  deliveries = $state<WebhookDelivery[]>([]);
  syncRuns = $state<SyncRun[]>([]);
  syncJobs = $state<SyncJobSummary[]>([]);
  organizations = $state<Organization[]>([]);
  busy = $state(false);
  error = $state<string | null>(null);

  constructor(
    private githubApi: GitHubApi,
    private repositoriesApi: RepositoriesApi
  ) {}

  async load(): Promise<void> {
    this.connections = await this.githubApi.listConnections();
  }

  async connect(token: string): Promise<boolean> {
    this.busy = true;
    this.error = null;
    try {
      await this.githubApi.connect(token);
      await this.load();
      return true;
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'connection failed';
      return false;
    } finally {
      this.busy = false;
    }
  }

  async connectApp(
    appId: string,
    installationId: string,
    privateKey: string,
    webhookSecret: string
  ): Promise<boolean> {
    this.busy = true;
    this.error = null;
    try {
      await this.githubApi.connectApp(appId, installationId, privateKey, webhookSecret);
      await this.load();
      return true;
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'app connection failed';
      return false;
    } finally {
      this.busy = false;
    }
  }

  async loadDeliveries(): Promise<void> {
    try {
      this.deliveries = await this.githubApi.webhookDeliveries();
    } catch {
      // deliveries are best-effort; ignore load failures
    }
  }

  async loadSyncActivity(): Promise<void> {
    try {
      [this.syncRuns, this.syncJobs] = await Promise.all([
        this.githubApi.syncRuns(),
        this.githubApi.syncJobs()
      ]);
    } catch {
      // sync activity is best-effort; ignore load failures
    }
  }

  async loadOrganizations(): Promise<void> {
    try {
      this.organizations = await this.githubApi.organizations();
    } catch {
      // organizations are best-effort; ignore load failures
    }
  }

  async toggleOrganization(login: string, syncEnabled: boolean): Promise<void> {
    const updated = await this.githubApi.setOrganizationSync(login, syncEnabled);
    this.organizations = this.organizations.map((o) => (o.login === login ? updated : o));
  }

  orgBusy = $state<string | null>(null);

  /** Index (enable) or un-index (disable) every repository in an organization. */
  async indexOrganization(login: string, enabled: boolean, mode?: IndexingMode): Promise<void> {
    if (this.orgBusy) return;
    this.orgBusy = login;
    this.error = null;
    try {
      await this.githubApi.bulkSelectionByOrg(login, enabled, mode);
      // reflect the new enabled count without a full reload
      this.organizations = this.organizations.map((o) =>
        o.login === login ? { ...o, enabled_repos: enabled ? o.total_repos : 0 } : o
      );
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'organization index update failed';
    } finally {
      this.orgBusy = null;
    }
  }

  async test(connectionId: string): Promise<void> {
    this.testResults = {
      ...this.testResults,
      [connectionId]: await this.githubApi.testConnection(connectionId)
    };
  }

  async remove(connectionId: string): Promise<void> {
    await this.githubApi.deleteConnection(connectionId);
    await this.load();
  }

  async discover(connectionId: string): Promise<void> {
    this.busy = true;
    this.error = null;
    try {
      this.discovered = await this.repositoriesApi.discover(connectionId);
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'discovery failed';
    } finally {
      this.busy = false;
    }
  }
}
