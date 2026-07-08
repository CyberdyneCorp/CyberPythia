/** Frontend composition root (browser only). */
import { authService } from '$lib/auth/cyberdyneAuthService';
import { HttpClient } from '$lib/api/http';
import {
  ApiKeysApi,
  CodeApi,
  ContextApi,
  GitHubApi,
  IntelligenceApi,
  RepositoriesApi
} from '$lib/api/mnemosyneApi';

export interface AppContext {
  auth: ReturnType<typeof authService>;
  githubApi: GitHubApi;
  repositoriesApi: RepositoriesApi;
  contextApi: ContextApi;
  codeApi: CodeApi;
  intelligenceApi: IntelligenceApi;
  apiKeysApi: ApiKeysApi;
}

let context: AppContext | null = null;

export function appContext(): AppContext {
  if (!context) {
    const auth = authService();
    const http = new HttpClient(auth);
    context = {
      auth,
      githubApi: new GitHubApi(http),
      repositoriesApi: new RepositoriesApi(http),
      contextApi: new ContextApi(http),
      codeApi: new CodeApi(http),
      intelligenceApi: new IntelligenceApi(http),
      apiKeysApi: new ApiKeysApi(http)
    };
  }
  return context;
}
