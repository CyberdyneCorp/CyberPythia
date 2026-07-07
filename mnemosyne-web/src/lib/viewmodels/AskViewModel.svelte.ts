/** Agent-context tab: ask a question or build a context pack (spec: web-ui). */
import { ApiError } from '$lib/api/http';
import type { ContextApi } from '$lib/api/mnemosyneApi';
import type { AskResult, ContextPack } from '$lib/models';

export class AskViewModel {
  question = $state('');
  mode = $state<'ask' | 'context-pack'>('ask');
  askResult = $state<AskResult | null>(null);
  contextPack = $state<ContextPack | null>(null);
  busy = $state(false);
  error = $state<string | null>(null);

  constructor(
    private api: ContextApi,
    private repoId: string
  ) {}

  async submit(): Promise<void> {
    const query = this.question.trim();
    if (query.length < 3 || this.busy) return;
    this.busy = true;
    this.error = null;
    this.askResult = null;
    this.contextPack = null;
    try {
      if (this.mode === 'ask') {
        this.askResult = await this.api.ask(this.repoId, query);
      } else {
        this.contextPack = await this.api.buildContextPack(this.repoId, query);
      }
    } catch (error) {
      if (error instanceof ApiError && error.code === 'repository_not_synced') {
        this.error = 'This repository has not been synced yet — ask an admin to run a sync.';
      } else {
        this.error = error instanceof ApiError ? error.message : 'request failed';
      }
    } finally {
      this.busy = false;
    }
  }
}
