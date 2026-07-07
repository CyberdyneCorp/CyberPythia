/**
 * API client: bearer attachment + one refresh-and-retry on 401 (spec: web-ui).
 */
import { config } from '$lib/config';

export interface TokenProvider {
  getAccessToken(): Promise<string | null>;
  refreshAccessToken(): Promise<string | null>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string
  ) {
    super(message);
  }
}

export class HttpClient {
  constructor(
    private tokens: TokenProvider,
    private baseUrl: string = config.apiBaseUrl,
    private fetchFn: typeof fetch = fetch
  ) {}

  private async send(method: string, path: string, body: unknown, token: string | null) {
    return this.fetchFn(`${this.baseUrl}${path}`, {
      method,
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: body !== undefined ? JSON.stringify(body) : undefined
    });
  }

  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let token = await this.tokens.getAccessToken();
    let response = await this.send(method, path, body, token);

    if (response.status === 401) {
      token = await this.tokens.refreshAccessToken();
      if (token) {
        response = await this.send(method, path, body, token);
      }
    }
    if (!response.ok) {
      let code = 'error';
      let message = response.statusText;
      try {
        const payload = await response.json();
        code = payload?.error?.code ?? code;
        message = payload?.error?.message ?? message;
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(response.status, code, message);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>('GET', path);
  }
  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('POST', path, body);
  }
  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('PATCH', path, body);
  }
  delete<T>(path: string): Promise<T> {
    return this.request<T>('DELETE', path);
  }
}
