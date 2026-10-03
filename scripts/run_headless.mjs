/** Real React -> HTTP API acceptance, demo only; temporary identities and SQLite. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';
const require = createRequire(resolve('frontend/package.json'));
const { chromium } = require('@playwright/test');
const root = process.cwd();
const temporary = await mkdtemp(resolve(tmpdir(), 'research-e2e-'));
const token = randomUUID();
const processes = new Set();
const env = { ...process.env, WORKSPACE_IDENTITIES: JSON.stringify({ acceptance: token }), RESEARCH_DB_PATH: resolve(temporary, 'research.sqlite3'), DEEPSEEK_API_KEY: '', PLAYGROUND_ACCESS_TOKEN: '', MAINTAINER_TOKEN: '' };
function launch(command, args, cwd = root) {
  const child = spawn(command, args, { cwd, env, stdio: 'ignore' });
  processes.add(child);
  child.on('error', () => {});
  return child;
}
async function stop(child) {
  if (child.exitCode !== null) return;
  const ended = new Promise(done => child.once('exit', done));
  child.kill('SIGTERM');
  const timeout = setTimeout(() => child.kill('SIGKILL'), 5000);
  await ended; clearTimeout(timeout); processes.delete(child);
}
async function ready(url) {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(url)).ok) return; } catch {}
    await new Promise(done => setTimeout(done, 100));
  }
  throw Error('Acceptance server failed to start');
}
const startAPI = () => launch('uv', ['run', '--locked', '--project', 'backend', 'uvicorn', 'app:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8010', '--no-access-log']);
let api; let browser;
try {
  // Do not accidentally exercise or stop another user's server.
  for (const port of [8010, 5174]) {
    let occupied = false;
    try { occupied = (await fetch(`http://127.0.0.1:${port}`)).status > 0; } catch {}
    assert.equal(occupied, false, `Port ${port} must be free`);
  }
  api = startAPI();
  launch(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5174', '--strictPort'], resolve(root, 'frontend'));
  await Promise.all([ready('http://127.0.0.1:8010/api/health'), ready('http://127.0.0.1:5174')]);
  browser = await chromium.launch({ headless: true });
  const errors = [];
  const cases = JSON.parse(await readFile(resolve(root, 'backend/eval-cases.json'), 'utf8'));
  let persistedID;
  for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport, acceptDownloads: true });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:5174');
    await page.getByRole('heading', { name: '私人研究工作台' }).waitFor();
    assert.equal(await page.locator('vite-error-overlay').count(), 0);
    const workspace = page.getByRole('region', { name: '持久化研究工作台' });
    await page.getByLabel('工作台访问令牌').fill('invalid-test-identity');
    await page.getByRole('button', { name: '连接工作台' }).click();
    await page.getByRole('alert').filter({ hasText: 'workspace_access_required' }).waitFor();
    async function login() {
      await page.getByLabel('工作台访问令牌').fill(token);
      await page.getByRole('button', { name: '连接工作台' }).click();
      await page.getByRole('button', { name: '开始研究' }).waitFor();
    }
    await login();
    for (const entry of cases) {
      await page.getByLabel('研究问题', { exact: true }).fill(entry.prompt);
      const started = page.waitForResponse(response => response.url().endsWith('/api/runs') && response.request().method() === 'POST');
      await page.getByRole('button', { name: '开始研究' }).focus();
      await page.keyboard.press('Enter');
      const identity = (await (await started).json()).run_id;
      await page.getByRole('status').filter({ hasText: `状态：completed · run_id：${identity}` }).waitFor();
      const report = await page.request.get(`http://127.0.0.1:5174/api/runs/${identity}`, { headers: { Authorization: `Bearer ${token}` } });
      const run = await report.json();
      assert.equal(run.result.outcome, entry.outcome);
      assert.equal(run.result.model_calls, 0);
      assert.deepEqual(run.result.sources.map(source => source.id).sort(), entry.sources.sort());
      assert.equal(run.result.tool_calls, entry.tool_calls);
      for (const format of ['JSON', 'Markdown']) {
        const downloading = page.waitForEvent('download');
        await page.getByRole('button', { name: `导出 ${format}`, exact: true }).click();
        const download = await downloading;
        const text = await readFile(await download.path(), 'utf8');
        assert.ok(text.includes(identity));
        assert.ok(!text.includes(token));
        if (format === 'JSON') assert.equal(JSON.parse(text).result.outcome, entry.outcome);
      }
      persistedID = identity;
    }
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Mobile overflow');
    await page.reload(); await login();
    assert.ok((await workspace.innerText()).includes('取消计费冲突'));
    await context.close();
  }
  await stop(api); api = startAPI(); await ready('http://127.0.0.1:8010/api/health');
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:5174');
  await page.getByLabel('工作台访问令牌').fill(token);
  await page.getByRole('button', { name: '连接工作台' }).click();
  const run = await (await page.request.get(`http://127.0.0.1:5174/api/runs/${persistedID}`, { headers: { Authorization: `Bearer ${token}` } })).json();
  assert.equal(run.status, 'completed');
  const workspace = page.getByRole('region', { name: '持久化研究工作台' });
  const reportButton = workspace.getByRole('button', { name: '取消计费冲突 · completed', exact: true }).first();
  await reportButton.click();
  await page.getByRole('status').filter({ hasText: '状态：completed' }).waitFor();
  await page.getByRole('button', { name: '退出工作台' }).click();
  assert.equal(await page.getByRole('region', { name: '回答', exact: true }).count(), 0);
  assert.equal(await page.getByLabel('工作台访问令牌').inputValue(), '');
  assert.deepEqual(errors, []);
  console.log('Headless PASS: 6 desktop/mobile research flows, 12 downloads, keyboard submit, denied identity, reload and API restart recovery, logout privacy; 0 page errors; 0 model calls.');
} finally {
  await browser?.close();
  await Promise.all([...processes].map(stop));
  await rm(temporary, { recursive: true, force: true });
}
