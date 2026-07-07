import { describe, expect, it } from 'vitest';
import { ApiError } from '$lib/api/http';
import type { Repository, SyncJob } from '$lib/models';
import { RepositoryListViewModel } from './RepositoryListViewModel.svelte';
import { AskViewModel } from './AskViewModel.svelte';
import { ConnectionsViewModel } from './ConnectionsViewModel.svelte';
import { AuthViewModel } from './AuthViewModel.svelte';

function repo(overrides: Partial<Repository> = {}): Repository {
  return {
    id: 'r1',
    full_name: 'cyberdyne/a',
    description: 'demo',
    visibility: 'private',
    default_branch: 'main',
    primary_language: 'Python',
    archived: false,
    enabled: true,
    indexing_mode: 'project_intelligence',
    last_synced_at: null,
    ...overrides
  };
}

function job(status: SyncJob['status']): SyncJob {
  return {
    id: 'j1',
    repository_id: 'r1',
    mode: 'project_intelligence',
    status,
    steps: [],
    started_at: null,
    finished_at: null
  };
}

describe('RepositoryListViewModel', () => {
  it('loads repositories with indexed ones first', async () => {
    const api = {
      listAll: async () => [
        repo({ id: 'r2', full_name: 'aaa/first-alpha', enabled: false }),
        repo({ id: 'r1', full_name: 'zzz/indexed', enabled: true })
      ]
    };
    const vm = new RepositoryListViewModel(api as never, 1);
    await vm.load();
    expect(vm.repositories.map((r) => r.id)).toEqual(['r1', 'r2']);
    expect(vm.error).toBeNull();
  });

  it('filters by full name', async () => {
    const api = {
      listAll: async () => [
        repo({ id: 'r1', full_name: 'CyberdyneCorp/CyberdyneAuth' }),
        repo({ id: 'r2', full_name: 'aminitech/other' })
      ]
    };
    const vm = new RepositoryListViewModel(api as never, 1);
    await vm.load();
    vm.filter = 'cyberdyneauth';
    expect(vm.filtered.map((r) => r.id)).toEqual(['r1']);
  });

  it('surfaces load errors', async () => {
    const api = {
      listAll: async () => {
        throw new ApiError(503, 'upstream_unavailable', 'auth down');
      }
    };
    const vm = new RepositoryListViewModel(api as never, 1);
    await vm.load();
    expect(vm.error).toBe('auth down');
  });

  it('updates selection in place', async () => {
    const api = {
      listAll: async () => [repo()],
      updateSelection: async (_id: string, enabled: boolean) => repo({ enabled })
    };
    const vm = new RepositoryListViewModel(api as never, 1);
    await vm.load();
    await vm.setSelection(vm.repositories[0], false);
    expect(vm.repositories[0].enabled).toBe(false);
  });

  it('polls sync status until it settles', async () => {
    const statuses = [job('running'), job('running'), job('succeeded')];
    let calls = 0;
    const api = {
      listAll: async () => [repo()],
      sync: async () => job('pending'),
      syncStatus: async () => statuses[Math.min(calls++, statuses.length - 1)]
    };
    const vm = new RepositoryListViewModel(api as never, 1);
    await vm.triggerSync(repo());
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(vm.syncStateFor('r1')).toBe('succeeded');
    expect(calls).toBeGreaterThanOrEqual(3);
  });

  it('starts polling instead of erroring on sync conflict', async () => {
    const api = {
      listAll: async () => [repo()],
      sync: async () => {
        throw new ApiError(409, 'sync_already_running', 'busy');
      },
      syncStatus: async () => job('succeeded')
    };
    const vm = new RepositoryListViewModel(api as never, 1);
    await vm.triggerSync(repo());
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(vm.error).toBeNull();
    expect(vm.syncStateFor('r1')).toBe('succeeded');
  });
});

describe('AskViewModel', () => {
  it('asks and stores grounded answers', async () => {
    const api = {
      ask: async () => ({ answer: 'A [README.md]', sources: [], grounded: true }),
      buildContextPack: async () => ({}) as never,
      search: async () => []
    };
    const vm = new AskViewModel(api as never, 'r1');
    vm.question = 'what is this?';
    await vm.submit();
    expect(vm.askResult?.grounded).toBe(true);
    expect(vm.error).toBeNull();
  });

  it('ignores too-short questions', async () => {
    let called = false;
    const api = {
      ask: async () => {
        called = true;
        return { answer: '', sources: [], grounded: false };
      }
    };
    const vm = new AskViewModel(api as never, 'r1');
    vm.question = 'a';
    await vm.submit();
    expect(called).toBe(false);
  });

  it('translates repository_not_synced into a friendly message', async () => {
    const api = {
      ask: async () => {
        throw new ApiError(409, 'repository_not_synced', 'never synced');
      }
    };
    const vm = new AskViewModel(api as never, 'r1');
    vm.question = 'anything at all';
    await vm.submit();
    expect(vm.error).toContain('has not been synced');
  });

  it('builds context packs in pack mode', async () => {
    const api = {
      buildContextPack: async () => ({ query: 'q', risks: [] }) as never
    };
    const vm = new AskViewModel(api as never, 'r1');
    vm.mode = 'context-pack';
    vm.question = 'implement backend';
    await vm.submit();
    expect(vm.contextPack).not.toBeNull();
  });
});

describe('ConnectionsViewModel', () => {
  it('connect success reloads and clears error', async () => {
    const connections: unknown[] = [];
    const githubApi = {
      connect: async () => {
        connections.push({ id: 'c1' });
        return { id: 'c1' } as never;
      },
      listConnections: async () => connections as never
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never);
    expect(await vm.connect('ghp_x_1234')).toBe(true);
    expect(vm.connections).toHaveLength(1);
  });

  it('connect failure surfaces API message', async () => {
    const githubApi = {
      connect: async () => {
        throw new ApiError(400, 'missing_permissions', 'missing: issues');
      },
      listConnections: async () => []
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never);
    expect(await vm.connect('ghp_bad')).toBe(false);
    expect(vm.error).toBe('missing: issues');
  });
});

describe('AuthViewModel', () => {
  const user = { expired: false, profile: { name: 'Sarah' } };

  it('entitled when the API accepts the caller', async () => {
    const auth = { getUser: async () => user };
    const api = { list: async () => ({ items: [], page: 1, page_size: 1, next_page: null }) };
    const vm = new AuthViewModel(auth as never, api as never);
    await vm.initialize();
    expect(vm.signedIn).toBe(true);
    expect(vm.displayName).toBe('Sarah');
    expect(vm.entitlement).toBe('entitled');
  });

  it('denied on 403', async () => {
    const auth = { getUser: async () => user };
    const api = {
      list: async () => {
        throw new ApiError(403, 'missing_entitlement', 'no');
      }
    };
    const vm = new AuthViewModel(auth as never, api as never);
    await vm.initialize();
    expect(vm.entitlement).toBe('denied');
  });

  it('signed out on 401', async () => {
    const auth = { getUser: async () => user };
    const api = {
      list: async () => {
        throw new ApiError(401, 'unauthenticated', 'expired');
      }
    };
    const vm = new AuthViewModel(auth as never, api as never);
    await vm.initialize();
    expect(vm.signedIn).toBe(false);
  });
});
