/**
 * CyberdyneAuth OIDC service (spec: auth / web-ui; design D3).
 *
 * Authorization-code + PKCE via oidc-client-ts against the CyberdyneAuth
 * discovery document. Refresh tokens rotate; oidc-client-ts handles the
 * exchange, we expose access-token retrieval + a forced-refresh hook for
 * the API client's 401 retry.
 */
import { UserManager, WebStorageStateStore, type User } from 'oidc-client-ts';
import { config } from '$lib/config';

function buildManager(origin: string): UserManager {
  return new UserManager({
    authority: config.authIssuer,
    client_id: config.authClientId,
    redirect_uri: `${origin}/auth/callback`,
    post_logout_redirect_uri: origin,
    response_type: 'code', // PKCE is automatic
    scope: 'openid email profile offline_access',
    automaticSilentRenew: true,
    userStore: new WebStorageStateStore({ store: window.localStorage })
  });
}

export class CyberdyneAuthService {
  private manager: UserManager;

  constructor(manager?: UserManager) {
    this.manager = manager ?? buildManager(window.location.origin);
  }

  signIn(returnTo?: string): Promise<void> {
    return this.manager.signinRedirect({ state: returnTo ?? window.location.pathname });
  }

  /** Handle /auth/callback; returns the path to navigate back to. */
  async completeSignIn(): Promise<string> {
    const user = await this.manager.signinRedirectCallback();
    return typeof user.state === 'string' ? user.state : '/';
  }

  async signOut(): Promise<void> {
    await this.manager.removeUser();
  }

  async getUser(): Promise<User | null> {
    return this.manager.getUser();
  }

  async getAccessToken(): Promise<string | null> {
    const user = await this.manager.getUser();
    return user && !user.expired ? user.access_token : null;
  }

  /** Forced refresh for the API client's single 401 retry (spec: web-ui). */
  async refreshAccessToken(): Promise<string | null> {
    try {
      const user = await this.manager.signinSilent();
      return user?.access_token ?? null;
    } catch {
      await this.manager.removeUser();
      return null;
    }
  }
}

let instance: CyberdyneAuthService | null = null;

export function authService(): CyberdyneAuthService {
  if (!instance) instance = new CyberdyneAuthService();
  return instance;
}
