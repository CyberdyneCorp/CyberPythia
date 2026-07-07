/**
 * Session state (MVVM). Entitlement is probed against the API — the token's
 * claims are opaque to the frontend; the backend is the authority (spec: auth).
 */
import type { CyberdyneAuthService } from '$lib/auth/cyberdyneAuthService';
import { ApiError } from '$lib/api/http';
import type { RepositoriesApi } from '$lib/api/mnemosyneApi';

export type EntitlementState = 'unknown' | 'entitled' | 'denied';

export class AuthViewModel {
  signedIn = $state(false);
  displayName = $state<string | null>(null);
  entitlement = $state<EntitlementState>('unknown');
  loading = $state(true);

  constructor(
    private auth: CyberdyneAuthService,
    private repositoriesApi: RepositoriesApi
  ) {}

  async initialize(): Promise<void> {
    this.loading = true;
    try {
      const user = await this.auth.getUser();
      this.signedIn = !!user && !user.expired;
      this.displayName = (user?.profile?.name ?? user?.profile?.email ?? null) as string | null;
      if (this.signedIn) await this.probeEntitlement();
    } finally {
      this.loading = false;
    }
  }

  private async probeEntitlement(): Promise<void> {
    try {
      await this.repositoriesApi.list(1, 1);
      this.entitlement = 'entitled';
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        this.entitlement = 'denied';
      } else if (error instanceof ApiError && error.status === 401) {
        this.signedIn = false;
      } else {
        this.entitlement = 'unknown';
      }
    }
  }

  signIn(returnTo?: string): Promise<void> {
    return this.auth.signIn(returnTo);
  }

  async signOut(): Promise<void> {
    await this.auth.signOut();
    this.signedIn = false;
    this.displayName = null;
    this.entitlement = 'unknown';
  }
}
