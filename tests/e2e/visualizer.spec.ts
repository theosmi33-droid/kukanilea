import { test, expect } from '@playwright/test';

test('visualizer endpoints are reachable without 404/500', async ({ request }) => {
  const sourceRes = await request.get('/api/visualizer/sources');
  expect([200, 302, 401, 403]).toContain(sourceRes.status());

  const projectsRes = await request.get('/api/visualizer/projects');
  expect([200, 302, 401, 403]).toContain(projectsRes.status());

  const summaryRes = await request.post('/api/visualizer/summary', {
    data: { source: '' },
  });
  expect([400, 302, 401, 403]).toContain(summaryRes.status());
});
