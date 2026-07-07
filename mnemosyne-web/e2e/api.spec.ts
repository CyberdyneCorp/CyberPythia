import { expect, test } from '@playwright/test';
import { API_URL, apiToken } from './helpers';

test.describe('deployed REST API', () => {
  test('health is ok and reports all dependencies', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/v1/health`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.status).toBe('ok');
    expect(body.checks).toEqual({ database: 'ok', redis: 'ok', object_storage: 'ok' });
  });

  test('openapi.json and /docs are served', async ({ request }) => {
    const spec = await request.get(`${API_URL}/openapi.json`);
    expect(spec.status()).toBe(200);
    const paths = Object.keys((await spec.json()).paths);
    expect(paths).toContain('/api/v1/repos');
    expect((await request.get(`${API_URL}/docs`)).status()).toBe(200);
  });

  test('rejects anonymous and invalid tokens with the error model', async ({ request }) => {
    const anonymous = await request.get(`${API_URL}/api/v1/repos`);
    expect(anonymous.status()).toBe(401);
    const invalid = await request.get(`${API_URL}/api/v1/repos`, {
      headers: { Authorization: 'Bearer bogus' }
    });
    expect(invalid.status()).toBe(401);
    const body = await invalid.json();
    expect(body.error.code).toBe('unauthenticated');
    expect(body.error.correlation_id).toBeTruthy();
  });

  test('authenticated user can list repositories and connections', async ({ request }) => {
    const token = await apiToken(request);
    const headers = { Authorization: `Bearer ${token}` };

    const repos = await request.get(`${API_URL}/api/v1/repos`, { headers });
    expect(repos.status()).toBe(200);
    expect(await repos.json()).toHaveProperty('items');

    // test user is admin: connections endpoint must respond
    const connections = await request.get(`${API_URL}/api/v1/github/connections`, { headers });
    expect(connections.status()).toBe(200);
  });

  test('unknown repository yields 404 with error model', async ({ request }) => {
    const token = await apiToken(request);
    const response = await request.get(
      `${API_URL}/api/v1/repos/00000000-0000-0000-0000-000000000000/summary`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    expect(response.status()).toBe(404);
    expect((await response.json()).error.code).toBe('not_found');
  });
});
