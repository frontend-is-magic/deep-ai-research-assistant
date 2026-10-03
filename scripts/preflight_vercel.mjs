/** Local-only Vercel Services HTTP preflight; no login, linking, deployment or model calls. */
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtemp, mkdir, copyFile, cp, readFile, readdir, readlink, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, dirname, join } from 'node:path';
import { createServer } from 'node:net';
import { randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';

const root = process.cwd();
const require = createRequire(resolve(root, 'frontend/package.json'));
const packagePath = require.resolve('vercel/package.json');
const pkg = JSON.parse(await readFile(packagePath, 'utf8'));
assert.equal(pkg.version, '62.2.0', 'Preflight uses the locked CLI version');
const temporary = await mkdtemp(join(tmpdir(), 'research-vercel-local-'));
const project = join(temporary, 'project');
const config = join(temporary, 'empty-cli-config');
const owned = new Map();
const ports = new Set();
let child, tracker, logs = '';
const delay = milliseconds => new Promise(done => setTimeout(done, milliseconds));

async function inventory() {
  // Process metadata only; never inspect process environments, command arguments or auth files.
  const entries = await readdir('/proc');
  const stats = new Map();
  for (const pid of entries.filter(value => /^\d+$/.test(value))) {
    try {
      const value = await readFile(`/proc/${pid}/stat`, 'utf8');
      const parts = value.slice(value.lastIndexOf(')') + 2).split(' ');
      stats.set(Number(pid), { parent: Number(parts[1]), group: Number(parts[2]), start: parts[19] });
    } catch {}
  }
  let added;
  do {
    added = false;
    for (const [pid, value] of stats) {
      if (!owned.has(pid) && (pid === child?.pid || (owned.has(value.parent) && owned.get(value.parent) === stats.get(value.parent)?.start) || value.group === child?.pid)) {
        owned.set(pid, value.start); added = true;
      }
    }
  } while (added);
  const sockets = new Set();
  for (const [pid, start] of owned) {
    if (stats.get(pid)?.start !== start) continue;
    try {
      for (const fd of await readdir(`/proc/${pid}/fd`)) {
        try { const link = await readlink(`/proc/${pid}/fd/${fd}`); const match = /^socket:\[(\d+)\]$/.exec(link); if (match) sockets.add(match[1]); } catch {}
      }
    } catch {}
  }
  for (const name of ['tcp', 'tcp6']) {
    for (const row of (await readFile(`/proc/net/${name}`, 'utf8')).trim().split('\n').slice(1)) {
      const values = row.trim().split(/\s+/);
      if (values[3] === '0A' && sockets.has(values[9])) ports.add(parseInt(values[1].split(':')[1], 16));
    }
  }
  return stats;
}
async function available(port = 0) {
  const server = createServer();
  await new Promise((done, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', done); });
  const selected = server.address().port;
  await new Promise(done => server.close(done));
  return selected;
}
async function request(base, path, status, init) {
  const response = await fetch(base + path, { ...init, signal: AbortSignal.timeout(10000) });
  assert.equal(response.status, status, `${path}: expected ${status}, received ${response.status}`);
  return response;
}
async function cleanup() {
  clearInterval(tracker);
  if (child) {
    let stats = await inventory();
    for (const signal of ['SIGTERM', 'SIGKILL']) {
      for (const [pid, start] of owned) if (stats.get(pid)?.start === start) { try { process.kill(pid, signal); } catch {} }
      await delay(signal === 'SIGTERM' ? 1500 : 300);
      stats = await inventory();
    }
    for (const port of ports) await available(port);
    console.log(`Vercel local cleanup PASS: ${ports.size} owned listening ports released.`);
  }
  await rm(temporary, { recursive: true, force: true });
}
try {
  await mkdir(project); await mkdir(config);
  const paths = execFileSync('git', ['ls-files', '-z'], { cwd: root }).toString().split('\0').filter(path => path === 'vercel.json' || path.startsWith('backend/') || path.startsWith('frontend/'));
  for (const path of paths) { await mkdir(dirname(join(project, path)), { recursive: true }); await copyFile(join(root, path), join(project, path)); }
  await cp(resolve(root, 'frontend/node_modules'), join(project, 'frontend/node_modules'), { recursive: true, verbatimSymlinks: true });
  await cp(resolve(root, 'backend/.venv'), join(project, 'backend/.venv'), { recursive: true, verbatimSymlinks: true });
  const port = await available(); ports.add(port);
  // Fresh custom config, no inherited Vercel/model/database/identity credentials.
  const workspaceToken = randomUUID();
  const providerToken = randomUUID();
  const env = Object.fromEntries(['PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'NODE_EXTRA_CA_CERTS', 'HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'NO_PROXY', 'UV_SYSTEM_CERTS', 'UV_NATIVE_TLS', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE'].filter(key => process.env[key]).map(key => [key, process.env[key]]));
  // Keep pnpm outside the copy: Vercel may rebuild the copied node_modules during install.
  Object.assign(env, { PATH: resolve(root, 'frontend/node_modules/.bin') + ':' + process.env.PATH, UV_SYSTEM_CERTS: 'true', CI: '1', NO_COLOR: '1', VERCEL_TELEMETRY_DISABLED: '1', DO_NOT_TRACK: '1', DEEPSEEK_API_KEY: '', VERCEL: '1', PLAYGROUND_ACCESS_TOKEN: providerToken, WORKSPACE_IDENTITIES: JSON.stringify({ preflight: workspaceToken }), MAINTAINER_TOKEN: '', DATABASE_URL: '' });
  child = spawn(process.execPath, [resolve(dirname(packagePath), pkg.bin.vercel), 'dev', '-L', '--listen', `127.0.0.1:${port}`, '--global-config', config, '--non-interactive'], { cwd: project, env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
  const capture = data => { logs = (logs + data.toString().replace(/(https?:\/\/)[^/\s@]+@/g, '$1[redacted]@')).slice(-32000); };
  child.stdout.on('data', capture); child.stderr.on('data', capture);
  child.on('error', error => { logs += error.message; });
  let tracking = false;
  tracker = setInterval(() => { if (!tracking) { tracking = true; void inventory().finally(() => { tracking = false; }); } }, 250);
  const base = `http://127.0.0.1:${port}`;
  let ready = false;
  for (let index = 0; index < 120; index++) {
    if (child.exitCode !== null) throw Error(`Vercel CLI exited ${child.exitCode}: ${logs.slice(-6000)}`);
    try { ready = (await fetch(base + '/api/health', { signal: AbortSignal.timeout(1000) })).ok; } catch {}
    if (ready) break;
    await delay(500);
  }
  assert.ok(ready, `Vercel local startup timed out: ${logs.slice(-6000)}`);
  const html = await (await request(base, '/', 200)).text();
  assert.ok(html.includes('id="root"'));
  const assets = [...html.matchAll(/<script[^>]+src="([^"]+)"/g)].map(match => match[1]);
  assert.ok(assets.length >= 2, 'Homepage must expose its dev client and application script');
  for (const asset of assets) {
    assert.ok(asset.startsWith('/'), 'Scripts must use the same origin');
    const response = await request(base, asset, 200);
    assert.match(response.headers.get('content-type') || '', /javascript/);
    assert.ok((await response.text()).length > 0);
  }
  const health = await (await request(base, '/api/health', 200)).json();
  assert.equal(health.framework, 'fastapi');
  const post = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const demo = await (await request(base, '/api/ask', 200, post({ prompt: 'API 超时' }))).json();
  assert.equal(demo.model_calls, 0); assert.equal(demo.outcome, 'complete');
  for (const path of ['/api/library', '/api/runs']) {
    const denied = await request(base, path, 401);
    assert.equal((await denied.json()).error, 'workspace_access_required');
    assert.equal(denied.headers.get('cache-control'), 'no-store');
  }
  assert.equal((await (await request(base, '/api/ask', 401, post({ prompt: 'API', mode: 'deepseek' }))).json()).error, 'access_required');
  const provider = post({ prompt: 'API', mode: 'deepseek' });
  provider.headers['X-Playground-Token'] = providerToken;
  assert.equal((await (await request(base, '/api/ask', 503, provider)).json()).error, 'provider_not_configured');
  const missingDatabase = await request(base, '/api/runs', 503, { headers: { Authorization: `Bearer ${workspaceToken}` } });
  assert.equal((await missingDatabase.json()).error, 'durable_storage_required');
  assert.equal(missingDatabase.headers.get('cache-control'), 'no-store');
  console.log('Vercel local PASS: CLI62.2.0 dev -L, same-origin homepage/static/FastAPI/demo/identity/provider fail-closed; isolated empty config; 0 real model calls; no deployment.');
} finally { await cleanup(); }
