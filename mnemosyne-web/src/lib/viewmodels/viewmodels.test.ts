import { describe, expect, it } from 'vitest';
import { ApiError } from '$lib/api/http';
import type { Repository, SyncJob } from '$lib/models';
import { RepositoryListViewModel } from './RepositoryListViewModel.svelte';
import { AskViewModel } from './AskViewModel.svelte';
import { ConnectionsViewModel } from './ConnectionsViewModel.svelte';
import { AuthViewModel } from './AuthViewModel.svelte';
import { CodeSearchViewModel } from './CodeSearchViewModel.svelte';
import { IntelligenceViewModel, RepositoryHealthViewModel } from './IntelligenceViewModel.svelte';

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

describe('CodeSearchViewModel', () => {
  it('returns code matches', async () => {
    const api = {
      search: async () => [
        {
          path: 'src/gpu.cpp',
          symbol_name: 'dispatch',
          chunk_type: 'function',
          start_line: 1,
          end_line: 5,
          excerpt: 'void dispatch()',
          score: 0.9
        }
      ]
    };
    const vm = new CodeSearchViewModel(api as never, 'r1');
    vm.query = 'dispatch';
    await vm.search();
    expect(vm.results).toHaveLength(1);
    expect(vm.notIndexed).toBe(false);
  });

  it('flags not-indexed repositories', async () => {
    const api = {
      search: async () => {
        throw new ApiError(409, 'source_not_indexed', 'not indexed');
      }
    };
    const vm = new CodeSearchViewModel(api as never, 'r1');
    vm.query = 'anything';
    await vm.search();
    expect(vm.notIndexed).toBe(true);
    expect(vm.error).toBeNull();
  });

  it('ignores too-short queries', async () => {
    let called = false;
    const api = {
      search: async () => {
        called = true;
        return [];
      }
    };
    const vm = new CodeSearchViewModel(api as never, 'r1');
    vm.query = 'x';
    await vm.search();
    expect(called).toBe(false);
  });
});

describe('ConnectionsViewModel — GitHub App', () => {
  it('connectApp success reloads', async () => {
    const conns: unknown[] = [];
    const githubApi = {
      connectApp: async () => {
        conns.push({ id: 'c1', kind: 'github_app' });
        return { id: 'c1' } as never;
      },
      listConnections: async () => conns as never
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never);
    expect(await vm.connectApp('1', '99', '-'.repeat(50), 'sec')).toBe(true);
    expect(vm.connections).toHaveLength(1);
  });

  it('loadDeliveries populates activity, swallows errors', async () => {
    const githubApi = {
      webhookDeliveries: async () => [
        {
          delivery_id: 'd1',
          event: 'push',
          action: null,
          repository_full_name: 'cyberdyne/a',
          outcome: 'processed',
          received_at: '2026-07-07T00:00:00Z'
        }
      ]
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never);
    await vm.loadDeliveries();
    expect(vm.deliveries).toHaveLength(1);

    const failing = { webhookDeliveries: async () => { throw new Error('boom'); } };
    const vm2 = new ConnectionsViewModel(failing as never, {} as never);
    await vm2.loadDeliveries();
    expect(vm2.deliveries).toEqual([]);
  });
});

describe('IntelligenceViewModel', () => {
  it('loads the portfolio overview', async () => {
    const api = {
      portfolio: async () => ({
        total_repositories: 2,
        scored: 1,
        leaderboard: [
          { repository_id: 'r1', full_name: 'cyberdyne/a', has_data: true, overall: 88, grade: 'B' }
        ],
        most_active: ['cyberdyne/a'],
        abandoned: [],
        bug_heavy: ['cyberdyne/a']
      })
    };
    const vm = new IntelligenceViewModel(api as never);
    await vm.loadPortfolio();
    expect(vm.overview?.scored).toBe(1);
    expect(vm.overview?.leaderboard[0].grade).toBe('B');
    expect(vm.error).toBeNull();
  });

  it('surfaces portfolio load errors', async () => {
    const api = { portfolio: async () => { throw new ApiError(500, 'server', 'nope'); } };
    const vm = new IntelligenceViewModel(api as never);
    await vm.loadPortfolio();
    expect(vm.error).toBe('nope');
    expect(vm.overview).toBeNull();
  });
});

describe('RepositoryHealthViewModel', () => {
  it('loads a repository health score', async () => {
    const api = {
      health: async () => ({
        has_data: true,
        overall: 91,
        grade: 'A',
        components: [{ name: 'documentation', weight: 0.25, score: 100, inputs: {} }],
        findings: []
      })
    };
    const vm = new RepositoryHealthViewModel(api as never, 'r1');
    await vm.load();
    expect(vm.health?.grade).toBe('A');
    expect(vm.health?.components).toHaveLength(1);
  });
});
