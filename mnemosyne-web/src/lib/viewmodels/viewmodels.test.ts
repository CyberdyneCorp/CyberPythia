import { describe, expect, it } from 'vitest';
import { ApiError } from '$lib/api/http';
import type { Repository, SyncJob } from '$lib/models';
import { RepositoryListViewModel } from './RepositoryListViewModel.svelte';
import { AskViewModel } from './AskViewModel.svelte';
import { ConnectionsViewModel } from './ConnectionsViewModel.svelte';
import { AuthViewModel } from './AuthViewModel.svelte';
import { CodeSearchViewModel } from './CodeSearchViewModel.svelte';
import { IntelligenceViewModel, RepositoryHealthViewModel } from './IntelligenceViewModel.svelte';
import { DeliveryViewModel, RepositoryDeliveryViewModel } from './DeliveryViewModel.svelte';

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
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
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
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    expect(await vm.connect('ghp_bad')).toBe(false);
    expect(vm.error).toBe('missing: issues');
  });

  it('delete reloads on success', async () => {
    let deleted = false;
    const githubApi = {
      deleteConnection: async () => {
        deleted = true;
      },
      listConnections: async () => []
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    await vm.remove('c1');
    expect(deleted).toBe(true);
    expect(vm.error).toBeNull();
  });

  it('syncs an organization and reports the queued count', async () => {
    const githubApi = {
      syncAll: async (org: string) => ({ enqueued: 12, skipped: 3 }),
      listConnections: async () => []
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    await vm.syncOrganization('CyberdyneCorp');
    expect(vm.orgMessage).toContain('12 sync(s) queued');
    expect(vm.orgMessage).toContain('3 skipped');
    expect(vm.error).toBeNull();
  });

  it('delete surfaces the error instead of swallowing it', async () => {
    const githubApi = {
      deleteConnection: async () => {
        throw new ApiError(504, 'timeout', 'gateway timeout');
      },
      listConnections: async () => []
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    await vm.remove('c1');
    expect(vm.error).toBe('gateway timeout');
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
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
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
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    await vm.loadDeliveries();
    expect(vm.deliveries).toHaveLength(1);

    const failing = { webhookDeliveries: async () => { throw new Error('boom'); } };
    const vm2 = new ConnectionsViewModel(failing as never, {} as never, {} as never);
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

describe('DeliveryViewModel', () => {
  it('loads the delivery scorecard', async () => {
    const api = {
      deliveryScorecard: async () => ({
        scorecard: [
          {
            repository_id: 'r1',
            full_name: 'cyberdyne/a',
            has_data: true,
            median_cycle_days: 3.2,
            throughput_direction: 'down',
            backlog_shrinking: true,
            at_risk_milestones: 1
          }
        ]
      })
    };
    const vm = new DeliveryViewModel(api as never);
    await vm.loadScorecard();
    expect(vm.scorecard).toHaveLength(1);
    expect(vm.scorecard[0].throughput_direction).toBe('down');
    expect(vm.error).toBeNull();
  });

  it('surfaces scorecard load errors', async () => {
    const api = {
      deliveryScorecard: async () => {
        throw new ApiError(500, 'server', 'down');
      }
    };
    const vm = new DeliveryViewModel(api as never);
    await vm.loadScorecard();
    expect(vm.error).toBe('down');
  });
});

describe('RepositoryDeliveryViewModel', () => {
  it('loads per-repo flow, forecast, work-mix, milestones', async () => {
    const api = {
      flow: async () => ({
        has_data: true,
        resolution_seconds: { n: 3, p50: 1, p85: 2, p95: 3 },
        merge_seconds: { n: 0, p50: null, p85: null, p95: null },
        wip_issues: 4,
        wip_prs: 1,
        issue_aging: { '0-7': 2, '7-30': 1, '30-90': 0, '90+': 1 },
        pr_aging: {},
        untriaged_issues: 1
      }),
      forecast: async () => ({
        has_data: true,
        open_issues: 9,
        close_rate_per_day: 2,
        projected_days_to_clear: 4.5,
        projected_clear_date: '2026-07-12',
        reason: null
      }),
      throughput: async () => ({ has_data: false, points: [], reason: 'insufficient history' }),
      workMix: async () => ({
        has_data: true,
        distribution: { feature: 2, bug: 1, tech_debt: 0, docs: 0, other: 0 },
        bug_ratio: 0.33
      }),
      milestones: async () => ({
        milestones: [
          {
            number: 1,
            title: 'v1',
            state: 'open',
            percent_complete: 50,
            open_issues: 2,
            closed_issues: 2,
            due_on: '2026-08-01',
            projected_completion: '2026-07-20',
            at_risk: false
          }
        ]
      })
    };
    const vm = new RepositoryDeliveryViewModel(api as never, 'r1');
    await vm.load();
    expect(vm.flow?.wip_issues).toBe(4);
    expect(vm.forecast?.projected_clear_date).toBe('2026-07-12');
    expect(vm.workMix?.distribution.feature).toBe(2);
    expect(vm.milestones).toHaveLength(1);
  });
});

describe('ConnectionsViewModel sync activity', () => {
  it('loads sync runs + jobs, swallows errors', async () => {
    const githubApi = {
      syncRuns: async () => [
        {
          id: 'r1', trigger: 'scheduler', started_at: '2026-07-08T03:00:00Z',
          finished_at: '2026-07-08T03:20:00Z', discovered: 345, newly_enabled: 1,
          skipped_archived: 107, enqueued: 238, skipped: 0, failed: 2
        }
      ],
      syncJobs: async () => [
        {
          id: 'j1', repository_id: 'x', repository_full_name: 'cyberdyne/a', mode: 'project_intelligence',
          status: 'failed', triggered_by: 'scheduler', started_at: '2026-07-08T03:01:00Z',
          finished_at: '2026-07-08T03:02:00Z', errors: ['GitHubRateLimitError: rate limited']
        }
      ]
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    await vm.loadSyncActivity();
    expect(vm.syncRuns[0].enqueued).toBe(238);
    expect(vm.syncJobs[0].status).toBe('failed');

    const failing = {
      syncRuns: async () => { throw new Error('boom'); },
      syncJobs: async () => []
    };
    const vm2 = new ConnectionsViewModel(failing as never, {} as never, {} as never);
    await vm2.loadSyncActivity();
    expect(vm2.syncRuns).toEqual([]);
  });
});

describe('ConnectionsViewModel organizations', () => {
  it('loads and toggles organizations', async () => {
    let stored = true;
    const githubApi = {
      organizations: async () => [
        { login: 'cyberdyne', sync_enabled: true, total_repos: 2, enabled_repos: 2 },
        { login: 'aminitech', sync_enabled: true, total_repos: 236, enabled_repos: 236 }
      ],
      setOrganizationSync: async (login: string, enabled: boolean) => {
        stored = enabled;
        return { login, sync_enabled: enabled, total_repos: 236, enabled_repos: 236 };
      }
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    await vm.loadOrganizations();
    expect(vm.organizations).toHaveLength(2);
    await vm.toggleOrganization('aminitech', false);
    expect(stored).toBe(false);
    expect(vm.organizations.find((o) => o.login === 'aminitech')?.sync_enabled).toBe(false);
  });
});

describe('RepositoryListViewModel organization filter', () => {
  it('derives organizations and filters by org + text together', async () => {
    const api = {
      listAll: async () => [
        repo({ id: 'r1', full_name: 'CyberdyneCorp/auth', enabled: true }),
        repo({ id: 'r2', full_name: 'CyberdyneCorp/pythia', enabled: true }),
        repo({ id: 'r3', full_name: 'aminitech/x', enabled: false })
      ]
    };
    const vm = new RepositoryListViewModel(api as never, 1);
    await vm.load();
    expect(vm.organizations).toEqual(['aminitech', 'CyberdyneCorp']);

    vm.organizationFilter = 'CyberdyneCorp';
    expect(vm.filtered.map((r) => r.id)).toEqual(['r1', 'r2']);

    vm.filter = 'auth';
    expect(vm.filtered.map((r) => r.id)).toEqual(['r1']);

    vm.organizationFilter = '';
    vm.filter = '';
    expect(vm.filtered).toHaveLength(3);
  });
});

describe('RepositoryListViewModel bulk selection', () => {
  it('enables all filtered repos in one call and updates state', async () => {
    let capturedIds: string[] = [];
    let capturedEnabled = false;
    let calls = 0;
    const api = {
      listAll: async () => [
        repo({ id: 'r1', full_name: 'CyberdyneCorp/a', enabled: false }),
        repo({ id: 'r2', full_name: 'CyberdyneCorp/b', enabled: false }),
        repo({ id: 'r3', full_name: 'aminitech/x', enabled: false })
      ],
      bulkSelection: async (ids: string[], enabled: boolean) => {
        calls += 1;
        capturedIds = ids;
        capturedEnabled = enabled;
        return { updated: ids.length };
      }
    };
    const vm = new RepositoryListViewModel(api as never, 1);
    await vm.load();
    vm.organizationFilter = 'CyberdyneCorp';
    await vm.bulkSetSelection(true, 'code_metadata' as never);
    expect(calls).toBe(1); // one request, not per-repo
    expect([...capturedIds].sort()).toEqual(['r1', 'r2']); // only the filtered org
    expect(capturedEnabled).toBe(true);
    expect(vm.repositories.find((r) => r.id === 'r1')?.enabled).toBe(true);
    expect(vm.repositories.find((r) => r.id === 'r3')?.enabled).toBe(false); // untouched
  });

  it('surfaces bulk errors', async () => {
    const api = {
      listAll: async () => [repo({ id: 'r1', full_name: 'o/a', enabled: true })],
      bulkSelection: async () => {
        throw new ApiError(500, 'server', 'bulk boom');
      }
    };
    const vm = new RepositoryListViewModel(api as never, 1);
    await vm.load();
    await vm.bulkSetSelection(false);
    expect(vm.error).toBe('bulk boom');
  });
});

describe('ConnectionsViewModel index organization', () => {
  it('un-indexes an org and zeroes its enabled count', async () => {
    let called: { org: string; enabled: boolean } | null = null;
    const githubApi = {
      organizations: async () => [
        { login: 'aminitech', sync_enabled: true, total_repos: 200, enabled_repos: 94 }
      ],
      bulkSelectionByOrg: async (org: string, enabled: boolean) => {
        called = { org, enabled };
        return { updated: 94 };
      }
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    await vm.loadOrganizations();
    await vm.indexOrganization('aminitech', false);
    expect(called).toEqual({ org: 'aminitech', enabled: false });
    expect(vm.organizations[0].enabled_repos).toBe(0);
  });

  it('index-all sets enabled_repos to total', async () => {
    const githubApi = {
      organizations: async () => [
        { login: 'CyberdyneCorp', sync_enabled: true, total_repos: 50, enabled_repos: 10 }
      ],
      bulkSelectionByOrg: async () => ({ updated: 50 })
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    await vm.loadOrganizations();
    await vm.indexOrganization('CyberdyneCorp', true, 'project_intelligence' as never);
    expect(vm.organizations[0].enabled_repos).toBe(50);
  });
});

describe('ConnectionsViewModel API keys', () => {
  it('creates a key, reveals plaintext once, and prepends it to the list', async () => {
    let createdWith: { label: string; days: number | null } | null = null;
    const apiKeysApi = {
      list: async () => [],
      create: async (label: string, days: number | null) => {
        createdWith = { label, days };
        return {
          id: 'k1', label, prefix: 'mnem_ab12cd34', created_by: 'admin-1',
          created_at: '2026-07-08T00:00:00Z', expires_at: '2026-10-06T00:00:00Z',
          revoked: false, key: 'mnem_secretplaintext'
        };
      }
    };
    const vm = new ConnectionsViewModel({} as never, {} as never, apiKeysApi as never);
    const ok = await vm.createApiKey('claude-agent', 90);
    expect(ok).toBe(true);
    expect(createdWith).toEqual({ label: 'claude-agent', days: 90 });
    expect(vm.newKey?.key).toBe('mnem_secretplaintext');
    expect(vm.apiKeys.map((k) => k.id)).toEqual(['k1']);
    vm.dismissNewKey();
    expect(vm.newKey).toBeNull();
  });

  it('surfaces the API error and keeps newKey null on failure', async () => {
    const apiKeysApi = {
      create: async () => {
        throw new ApiError(422, 'invalid', 'label required');
      }
    };
    const vm = new ConnectionsViewModel({} as never, {} as never, apiKeysApi as never);
    const ok = await vm.createApiKey('', null);
    expect(ok).toBe(false);
    expect(vm.newKey).toBeNull();
    expect(vm.error).toBe('label required');
  });

  it('marks a key revoked in place', async () => {
    const apiKeysApi = {
      list: async () => [
        {
          id: 'k1', label: 'a', prefix: 'mnem_x', created_by: 'admin-1',
          created_at: '2026-07-08T00:00:00Z', expires_at: null, revoked: false
        }
      ],
      revoke: async () => undefined
    };
    const vm = new ConnectionsViewModel({} as never, {} as never, apiKeysApi as never);
    await vm.loadApiKeys();
    await vm.revokeApiKey('k1');
    expect(vm.apiKeys[0].revoked).toBe(true);
  });

  it('removes a key from the list on delete', async () => {
    let removed: string | null = null;
    const apiKeysApi = {
      list: async () => [
        {
          id: 'k1', label: 'a', prefix: 'mnem_x', created_by: 'admin-1',
          created_at: '2026-07-08T00:00:00Z', expires_at: null, revoked: true
        },
        {
          id: 'k2', label: 'b', prefix: 'mnem_y', created_by: 'admin-1',
          created_at: '2026-07-08T00:00:00Z', expires_at: null, revoked: false
        }
      ],
      remove: async (id: string) => {
        removed = id;
      }
    };
    const vm = new ConnectionsViewModel({} as never, {} as never, apiKeysApi as never);
    await vm.loadApiKeys();
    await vm.deleteApiKey('k1');
    expect(removed).toBe('k1');
    expect(vm.apiKeys.map((k) => k.id)).toEqual(['k2']);
  });
});

describe('SearchViewModel', () => {
  it('runs a docs search and stores results', async () => {
    let calledWith: unknown[] | null = null;
    const intelligenceApi = {
      search: async (q: string, kind: string, org?: string) => {
        calledWith = [q, kind, org];
        return { results: [{ repository_id: 'r1', full_name: 'org/a', title: 'Doc', score: 0.9 }] };
      }
    };
    const { SearchViewModel } = await import('./SearchViewModel.svelte');
    const vm = new SearchViewModel(intelligenceApi as never, {} as never);
    vm.query = 'auth';
    vm.kind = 'docs';
    await vm.run();
    expect(calledWith).toEqual(['auth', 'docs', undefined]);
    expect(vm.results[0].full_name).toBe('org/a');
    expect(vm.searched).toBe(true);
  });

  it('uses the resolver for kind=repositories', async () => {
    const repositoriesApi = {
      find: async () => ({ repositories: [{ repository_id: 'r1', full_name: 'org/a', description: null, primary_language: 'Go', indexing_mode: 'x', last_synced_at: null }] })
    };
    const { SearchViewModel } = await import('./SearchViewModel.svelte');
    const vm = new SearchViewModel({} as never, repositoriesApi as never);
    vm.query = 'auth';
    vm.kind = 'repositories';
    await vm.run();
    expect(vm.repos[0].full_name).toBe('org/a');
  });

  it('ignores queries under 2 chars', async () => {
    const { SearchViewModel } = await import('./SearchViewModel.svelte');
    const vm = new SearchViewModel({} as never, {} as never);
    vm.query = 'a';
    await vm.run();
    expect(vm.searched).toBe(false);
  });
});

describe('IntelligenceViewModel org detail', () => {
  it('loads rollup + activity + stale when an org is selected', async () => {
    const api = {
      recentActivity: async () => ({ recently_synced: [], recent_issues: [], recent_pull_requests: [] }),
      staleIssues: async () => ({ stale: [{ repository_id: 'r1', full_name: 'org/a', number: 1, title: 't', updated_at: 'x', stale_days: 40 }] }),
      stalePrs: async () => ({ stale: [] }),
      organizationIntelligence: async (org: string) => ({
        organization: org, total_repositories: 3, scored: 2, average_health: 80,
        median_health: 82, grade_distribution: { A: 2 }, at_risk_milestones: 1,
        throughput_directions: {}, backlog_shrinking_repos: 0, most_active: [], abandoned: [], bug_heavy: []
      }),
      organizationReadiness: async (org: string) => ({
        organization: org, total: 2,
        distribution: { MVP: 1, READY: 0, DONE: 1 },
        repositories: [
          { repository_id: 'r1', full_name: 'org/a', gate: 'DONE', missing_for_ready: [], missing_for_done: [] },
          { repository_id: 'r2', full_name: 'org/b', gate: 'MVP', missing_for_ready: ['ci', 'tests'], missing_for_done: [] }
        ]
      }),
      organizationRegressions: async (org: string) => ({
        organization: org,
        regressions: [{ repository_id: 'r1', full_name: 'org/a', from_gate: 'READY', to_gate: 'MVP', date: '2026-07-11' }]
      }),
      organizationVulnerabilities: async (org: string) => ({
        organization: org, total_critical: 3, total_high: 1,
        repositories: [{ repository_id: 'r2', full_name: 'org/b', critical: 3, high: 1 }]
      }),
      organizationCapabilities: async (org: string) => ({
        organization: org, repositories: 2, capabilities: ['auth', 'billing'], total_open_bugs: 5, projects: []
      }),
      openspecCoverage: async (org: string) => ({
        organization: org, total: 3, coverage: 0.67,
        with_openspec: [{ repository_id: 'r1', full_name: 'org/a', primary_language: 'Go', openspec_changes: 2, last_synced_at: 'x' }],
        without_openspec: [{ repository_id: 'r2', full_name: 'org/b', primary_language: null, openspec_changes: 0, last_synced_at: null }]
      })
    };
    const vm = new IntelligenceViewModel(api as never);
    await vm.loadOrgDetail('CyberdyneCorp');
    expect(vm.orgIntel?.organization).toBe('CyberdyneCorp');
    expect(vm.staleIssues.length).toBe(1);
    expect(vm.readiness?.distribution.DONE).toBe(1);
    expect(vm.readiness?.repositories[1].missing_for_ready).toEqual(['ci', 'tests']);
    expect(vm.regressions?.regressions[0].to_gate).toBe('MVP');
    expect(vm.vulnerabilities?.total_critical).toBe(3);
    expect(vm.capabilities?.capabilities).toEqual(['auth', 'billing']);
    expect(vm.openspec?.coverage).toBe(0.67);
    expect(vm.openspec?.without_openspec[0].full_name).toBe('org/b');
  });

  it('clears the rollup when no org is selected (whole portfolio)', async () => {
    const api = {
      recentActivity: async () => ({ recently_synced: [], recent_issues: [], recent_pull_requests: [] }),
      staleIssues: async () => ({ stale: [] }),
      stalePrs: async () => ({ stale: [] }),
      organizationIntelligence: async () => { throw new Error('should not be called'); },
      organizationReadiness: async () => { throw new Error('should not be called'); },
      openspecCoverage: async () => { throw new Error('should not be called'); }
    };
    const vm = new IntelligenceViewModel(api as never);
    await vm.loadOrgDetail('');
    expect(vm.orgIntel).toBeNull();
    expect(vm.readiness).toBeNull();
    expect(vm.openspec).toBeNull();
  });
});

describe('RepositoryDetailViewModel capabilities', () => {
  it('loads capabilities on the capabilities tab', async () => {
    const api = {
      capabilities: async () => ({
        full_name: 'org/a', description: 'd', primary_language: 'Go',
        capabilities: ['auth'], openspec_changes: 1, documentation_topics: ['Readme'],
        documents: 1, issues: { open: 2, closed: 3, bugs: 1 }, pull_requests: { open: 0, merged: 4 }
      })
    };
    const { RepositoryDetailViewModel } = await import('./RepositoryDetailViewModel.svelte');
    const vm = new RepositoryDetailViewModel(api as never, 'r1');
    await vm.open('capabilities');
    expect(vm.capabilities?.capabilities).toEqual(['auth']);
    expect(vm.capabilities?.issues.bugs).toBe(1);
  });

  it('generates a feature document', async () => {
    const api = {
      featureDocument: async () => ({ document: '# Features\n- x', sources: [], grounded: true })
    };
    const { RepositoryDetailViewModel } = await import('./RepositoryDetailViewModel.svelte');
    const vm = new RepositoryDetailViewModel(api as never, 'r1');
    await vm.generateFeatureDoc();
    expect(vm.featureDoc?.document).toContain('# Features');
  });

  it('loads, adds, and deletes memories', async () => {
    const store: { id: string; content: string; kind: string }[] = [
      { id: 'm1', content: 'existing', kind: 'note' }
    ];
    const api = {
      memories: async () => ({ memories: [...store] }),
      createMemory: async (_id: string, content: string, kind: string) => ({
        id: 'm2', content, kind, author: 'a', created_at: 'x',
        repository_id: 'r1', organization: null
      }),
      deleteMemory: async () => {}
    };
    const { RepositoryDetailViewModel } = await import('./RepositoryDetailViewModel.svelte');
    const vm = new RepositoryDetailViewModel(api as never, 'r1');
    await vm.open('memory');
    expect(vm.memories.map((m) => m.id)).toEqual(['m1']);
    expect(await vm.addMemory('  chose pgvector  ', 'decision')).toBe(true);
    expect(vm.memories[0]).toMatchObject({ id: 'm2', content: 'chose pgvector', kind: 'decision' });
    await vm.deleteMemory('m1');
    expect(vm.memories.map((m) => m.id)).toEqual(['m2']);
  });

  it('ignores an empty memory', async () => {
    const { RepositoryDetailViewModel } = await import('./RepositoryDetailViewModel.svelte');
    const vm = new RepositoryDetailViewModel({} as never, 'r1');
    expect(await vm.addMemory('   ', 'note')).toBe(false);
  });
});

describe('IntelligenceViewModel server-scoped portfolio', () => {
  it('captures the org list on the unscoped load and passes the scope when set', async () => {
    const calls: (string | undefined)[] = [];
    const api = {
      portfolio: async (org?: string) => {
        calls.push(org);
        const items = org
          ? [{ repository_id: 'r1', full_name: 'org1/a', has_data: true, overall: 90, grade: 'A' }]
          : [
              { repository_id: 'r1', full_name: 'org1/a', has_data: true, overall: 90, grade: 'A' },
              { repository_id: 'r2', full_name: 'org2/b', has_data: true, overall: 80, grade: 'B' }
            ];
        return { total_repositories: items.length, scored: items.length, leaderboard: items, most_active: [], abandoned: [], bug_heavy: [] };
      }
    };
    const vm = new IntelligenceViewModel(api as never);
    await vm.loadPortfolio(); // unscoped → derive org list
    expect(vm.organizations).toEqual(['org1', 'org2']);
    await vm.loadPortfolio('org1'); // scoped → org list stays complete
    expect(calls).toEqual([undefined, 'org1']);
    expect(vm.organizations).toEqual(['org1', 'org2']);
    expect(vm.overview?.total_repositories).toBe(1);
  });
});

describe('ConnectionsViewModel GitHub App manifest', () => {
  it('fetches the manifest bootstrap for an org', async () => {
    const githubApi = {
      appManifest: async (org: string) => ({
        manifest: { name: `Mnemosyne-${org}` },
        post_url: `https://github.com/organizations/${org}/settings/apps/new?state=s`,
        state: 's'
      })
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    const boot = await vm.fetchAppManifest('CyberdyneCorp');
    expect(boot?.post_url).toContain('CyberdyneCorp/settings/apps/new');
  });

  it('surfaces an error and returns null on failure', async () => {
    const githubApi = {
      appManifest: async () => {
        throw new ApiError(403, 'admin_required', 'admin only');
      }
    };
    const vm = new ConnectionsViewModel(githubApi as never, {} as never, {} as never);
    expect(await vm.fetchAppManifest('x')).toBeNull();
    expect(vm.error).toBe('admin only');
  });
});
