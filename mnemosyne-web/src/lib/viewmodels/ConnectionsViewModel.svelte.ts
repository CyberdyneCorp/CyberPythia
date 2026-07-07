/** Admin GitHub connection screen state (spec: web-ui). */
import { ApiError } from '$lib/api/http';
import type { GitHubApi, RepositoriesApi } from '$lib/api/mnemosyneApi';
import type { Connection, ConnectionTest, Repository, WebhookDelivery } from '$lib/models';

export class ConnectionsViewModel {
  connections = $state<Connection[]>([]);
  testResults = $state<Record<string, ConnectionTest>>({});
  discovered = $state<Repository[] | null>(null);
  deliveries = $state<WebhookDelivery[]>([]);
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
