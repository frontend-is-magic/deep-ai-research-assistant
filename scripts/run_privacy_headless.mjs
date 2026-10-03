/** Real React with delayed mock API/body/error completion; no model, backend or secrets. */
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtemp, rm, cp, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(resolve('frontend/package.json'));
const { chromium } = require('@playwright/test');
const baseline = process.argv.includes('--baseline');
const root = process.cwd();
const temporary = await mkdtemp(resolve(tmpdir(), 'research-privacy-'));
let server; let browser;
try {
  let frontend = resolve(root, 'frontend');
  if (baseline) {
    frontend = resolve(temporary, 'frontend');
    await cp(resolve(root, 'frontend/src'), resolve(frontend, 'src'), { recursive: true });
    for (const name of ['index.html', 'vite.config.ts', 'package.json']) await cp(resolve(root, 'frontend', name), resolve(frontend, name));
    await symlink(resolve(root, 'frontend/node_modules'), resolve(frontend, 'node_modules'), 'dir');
    await writeFile(resolve(frontend, 'src/workspace.tsx'), execFileSync('git', ['show', '0191fac:frontend/src/workspace.tsx']));
  }
  let occupied = false;
  try { occupied = (await fetch('http://127.0.0.1:5175')).status > 0; } catch {}
  assert.equal(occupied, false, 'Privacy test port 5175 must be free');
  server = spawn(process.execPath, [resolve(root, 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5175', '--strictPort'], { cwd: frontend, stdio: 'ignore' });
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch('http://127.0.0.1:5175')).ok) break; } catch {}
    await new Promise(done => setTimeout(done, 100));
  }
  browser = await chromium.launch({ headless: true });
  const failures = [];
  const scenarios = baseline ? ['poll-list'] : ['poll-list', 'refresh-list', 'selected-detail', 'detail-body', 'connect-library', 'error', 'start', 'cancel', 'delete', 'export'];
  for (const scenario of scenarios) {
    for (const destination of baseline ? ['bob'] : ['logout', 'bob', 'bob-pending']) {
      const context = await browser.newContext();
      const page = await context.newPage();
      const pageErrors = [];
      let downloads = 0;
      page.on('pageerror', e => pageErrors.push(e.message));
      page.on('download', () => downloads++);
      await page.addInitScript(() => {
        const realFetch = window.fetch.bind(window);
        let sequence = 0;
        const state = window.__privacyMock = { plans: [], requests: [], pending: {}, settled: [] };
        const report = {
          run_id: 'alice-run', mode: 'demo', workflow: 'research-agent', outcome: 'insufficient_evidence',
          answer: 'ALICE_PRIVATE_ANSWER', sources: [], citations: [], model_calls: 0, tool_calls: 1,
          usage: null, usage_complete: true, trace: [],
        };
        const privateRun = { run_id: 'alice-run', prompt: 'ALICE_PRIVATE_PROMPT', status: 'completed', failure_reason: null, result: report, read_documents: [] };
        state.privateRun = privateRun;
        state.library = [{ id: 'alice-library', title: 'ALICE_PRIVATE_LIBRARY', version: 1, acquisition: 'manual', recorded_at: 'now', content_hash: 'hash', url: null, kind: 'public-manual' }];
        state.release = (id, reject = false) => {
          const pending = state.pending[id];
          if (!pending) throw Error('Unknown delayed completion');
          delete state.pending[id];
          if (reject) pending.reject(new Error('ALICE_PRIVATE_ERROR'));
          else pending.resolve(pending.value);
        };
        window.fetch = async (input, init = {}) => {
          const path = new URL(String(input), location.href).pathname;
          if (!path.startsWith('/api/')) return realFetch(input, init);
          const token = new Headers(init.headers).get('Authorization') || '';
          const method = init.method || 'GET';
          const request = { id: ++sequence, path, token, method, aborted: init.signal?.aborted || false };
          init.signal?.addEventListener('abort', () => { request.aborted = true; }, { once: true });
          state.requests.push(request);
          let payload = path === '/api/health' ? { status: 'ok', framework: 'fastapi', documents: 5, workflow: 'research-agent' }
            : path === '/api/library' ? { documents: token === 'Bearer alice-test' ? state.library : [] }
              : path === '/api/runs' && method === 'GET' ? { runs: token === 'Bearer alice-test' ? [privateRun] : [] }
                : privateRun;
          const index = state.plans.findIndex(plan => plan.path === path && (plan.token || 'Bearer alice-test') === token && (plan.method || 'GET') === method);
          const plan = index < 0 ? null : state.plans.splice(index, 1)[0];
          if (plan?.payload) payload = plan.payload;
          const response = new Response(JSON.stringify(payload), { status: plan?.status || 200, headers: { 'Content-Type': 'application/json' } });
          // Intentionally ignore abort when completing. Generation checks must still protect every write.
          const delayed = value => new Promise((resolve, reject) => { state.pending[plan.id] = { resolve, reject, value, request }; }).finally(() => state.settled.push(plan.id));
          if (plan?.body) {
            response.json = () => delayed(payload);
            response.blob = () => delayed(new Blob([JSON.stringify(payload)]));
            return response;
          }
          return plan ? delayed(response) : response;
        };
      });
      await page.goto('http://127.0.0.1:5175');
      const workspace = page.getByRole('region', { name: '持久化研究工作台' });
      async function plan(value) { await page.evaluate(value => window.__privacyMock.plans.push(value), value); }
      async function login(token) {
        await page.getByLabel('工作台访问令牌').fill(token);
        await page.getByRole('button', { name: '连接工作台' }).click();
        await page.getByRole('button', { name: '退出工作台' }).waitFor();
      }
      async function waitPending(id) { await page.waitForFunction(id => Boolean(window.__privacyMock.pending[id]), id); }
      async function release(id, reject = false) { await page.evaluate(({ id, reject }) => window.__privacyMock.release(id, reject), { id, reject }); }
      const privateRun = await page.evaluate(() => window.__privacyMock.privateRun);
      if (scenario === 'connect-library') {
        await plan({ id: 'old', path: '/api/library', body: true });
        await page.getByLabel('工作台访问令牌').fill('alice-test');
        await page.getByRole('button', { name: '连接工作台' }).click();
      } else {
        if (scenario === 'poll-list' || scenario === 'cancel') {
          await plan({ id: 'initial', path: '/api/runs', payload: { runs: [{ ...privateRun, status: 'running', result: null }] } });
          await page.getByLabel('工作台访问令牌').fill('alice-test');
          await page.getByRole('button', { name: '连接工作台' }).click();
          await waitPending('initial'); await release('initial');
          await page.getByRole('button', { name: '退出工作台' }).waitFor();
        } else await login('alice-test');
        if (scenario === 'poll-list') {
          await plan({ id: 'selection', path: '/api/runs/alice-run', payload: { ...privateRun, status: 'running', result: null } });
          await workspace.getByRole('button', { name: 'ALICE_PRIVATE_PROMPT · running', exact: true }).click();
          await waitPending('selection'); await release('selection');
          await plan({ id: 'old', path: '/api/runs' });
        } else if (scenario === 'selected-detail' || scenario === 'detail-body') {
          await plan({ id: 'old', path: '/api/runs/alice-run', body: scenario === 'detail-body' });
          await workspace.getByRole('button', { name: 'ALICE_PRIVATE_PROMPT · completed', exact: true }).click();
        } else if (scenario === 'start') {
          await plan({ id: 'old', path: '/api/runs', method: 'POST' });
          await page.getByRole('button', { name: '开始研究' }).click();
        } else if (scenario === 'delete') {
          await plan({ id: 'old', path: '/api/runs/alice-run', method: 'DELETE' });
          await page.getByRole('button', { name: '删除自己的记录' }).click();
        } else if (scenario === 'cancel') {
          await plan({ id: 'selection', path: '/api/runs/alice-run', payload: { ...privateRun, status: 'running', result: null } });
          await workspace.getByRole('button', { name: 'ALICE_PRIVATE_PROMPT · running', exact: true }).click();
          await waitPending('selection'); await release('selection');
          await plan({ id: 'old', path: '/api/runs/alice-run/cancel', method: 'POST' });
          await page.getByRole('button', { name: '取消研究' }).click();
        } else if (scenario === 'export') {
          await workspace.getByRole('button', { name: 'ALICE_PRIVATE_PROMPT · completed', exact: true }).click();
          await page.getByRole('button', { name: '导出 JSON', exact: true }).waitFor();
          await plan({ id: 'old', path: '/api/runs/alice-run/export', body: true });
          await page.getByRole('button', { name: '导出 JSON', exact: true }).click();
        } else {
          await plan({ id: 'old', path: '/api/runs' });
          await page.getByRole('button', { name: '刷新报告' }).click();
        }
      }
      await waitPending('old');
      if (scenario === 'connect-library') {
        await page.getByLabel('工作台访问令牌').fill(destination === 'logout' ? '' : 'bob-test');
      } else {
        const logout = page.getByRole('button', { name: '退出工作台' });
        if (await logout.isDisabled()) {
          failures.push(`${scenario}/${destination}: cannot exit during old action`);
          await context.close(); continue;
        }
        await logout.click();
      }
      const aborted = await page.evaluate(() => window.__privacyMock.pending.old.request.aborted);
      // The exact reviewed baseline lacks cancellation; keep testing it to prove visible leak.
      if (!aborted && !baseline) failures.push(`${scenario}/${destination}: old request not aborted`);
      if (destination === 'bob') await login('bob-test');
      if (destination === 'bob-pending') {
        await plan({ id: 'bob', path: '/api/runs', token: 'Bearer bob-test', payload: { runs: [] } });
        await page.getByLabel('工作台访问令牌').fill('bob-test');
        await page.getByRole('button', { name: '连接工作台' }).click(); await waitPending('bob');
        assert.equal(await page.getByRole('button', { name: '连接工作台' }).isDisabled(), true);
      }
      await release('old', scenario === 'error');
      await page.waitForFunction(() => window.__privacyMock.settled.includes('old'));
      await page.waitForTimeout(100);
      if (destination === 'bob-pending') {
        if (!(await page.getByRole('button', { name: '连接工作台' }).isDisabled())) failures.push(`${scenario}/${destination}: old finally cleared Bob busy`);
        await release('bob'); await page.getByRole('button', { name: '退出工作台' }).waitFor();
      }
      const visible = await page.locator('body').innerText();
      if (/ALICE_PRIVATE_|alice-run/.test(visible)) failures.push(`${scenario}/${destination}: old private content became visible`);
      if (await page.getByRole('alert').count()) failures.push(`${scenario}/${destination}: stale error became visible`);
      if (destination === 'logout' && await page.getByRole('button', { name: '退出工作台' }).count()) failures.push(`${scenario}/${destination}: stale connect restored session`);
      if (downloads) failures.push(`${scenario}/${destination}: stale export downloaded`);
      assert.deepEqual(pageErrors, []);
      await context.close();
    }
  }
  if (baseline) {
    assert.ok(failures.includes('poll-list/bob: old private content became visible'), 'Must reproduce the reviewed Alice -> Bob leak');
    console.log(`Baseline 0191fac privacy regression reproduced: ${failures.length} failed assertions; Alice poll list appears in Bob session.`);
  } else {
    assert.deepEqual(failures, []);
    console.log('Privacy headless PASS: 30 delayed completion scenarios; old lists/details/library/errors/busy/start/cancel/delete/export suppressed after logout or identity change; abort signals verified; mock ignores cancellation; 0 model calls.');
  }
} finally {
  await browser?.close();
  if (server && server.exitCode === null) {
    const ended = new Promise(done => server.once('exit', done));
    server.kill('SIGTERM');
    const timer = setTimeout(() => server.kill('SIGKILL'), 5000);
    await ended; clearTimeout(timer);
  }
  await rm(temporary, { recursive: true, force: true });
}
