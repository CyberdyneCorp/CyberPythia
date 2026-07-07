/** Code Context tab: semantic code search + on-demand file content (spec: code-context). */
import { ApiError } from '$lib/api/http';
import type { CodeApi } from '$lib/api/mnemosyneApi';
import type { CodeChunkMatch } from '$lib/models';

export class CodeSearchViewModel {
  query = $state('');
  results = $state<CodeChunkMatch[]>([]);
  busy = $state(false);
  error = $state<string | null>(null);
  notIndexed = $state(false);

  constructor(
    private api: CodeApi,
    private repoId: string
  ) {}

  async search(): Promise<void> {
    const q = this.query.trim();
    if (q.length < 2 || this.busy) return;
    this.busy = true;
    this.error = null;
    this.notIndexed = false;
    try {
      this.results = await this.api.search(this.repoId, q);
    } catch (error) {
      if (error instanceof ApiError && error.code === 'source_not_indexed') {
        this.notIndexed = true;
      } else if (error instanceof ApiError && error.code === 'repository_not_synced') {
        this.error = 'This repository has not been synced yet.';
      } else {
        this.error = error instanceof ApiError ? error.message : 'code search failed';
      }
    } finally {
      this.busy = false;
    }
  }
}
