import { useEffect, useRef, useState } from 'react';
import { Button } from './components/ui/button';
import { parseAnswer, responseError, safeHttpsUrl, type Answer } from './response';

type Run = {
  run_id: string;
  prompt: string;
  status: string;
  failure_reason: string | null;
  result?: unknown;
  read_documents?: {
    id: string;
    title: string;
    version: number;
    content_hash: string;
    recorded_at: string;
    acquisition: string;
    url: string | null;
    kind: string;
  }[];
};

export function Workspace({ onReport }: { onReport: (answer: Answer | null) => void }) {
  const [token, setToken] = useState('');
  const [connected, setConnected] = useState(false);
  const [prompt, setPrompt] = useState('API 超时');
  const [mode, setMode] = useState('demo');
  const [providerToken, setProviderToken] = useState('');
  const [runs, setRuns] = useState<Run[]>([]);
  const [active, setActive] = useState<Run | null>(null);
  const [library, setLibrary] = useState<Run['read_documents']>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const running = active?.status === 'queued' || active?.status === 'running';
  async function api(path: string, init: RequestInit = {}) {
    const response = await fetch(path, {
      cache: 'no-store',
      signal: AbortSignal.timeout(10000),
      ...init,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...init.headers,
      },
    });
    if (!response.ok) throw new Error(responseError(await response.json()));
    return response;
  }
  async function refresh() {
    const value = await (await api('/api/runs')).json();
    setRuns(value.runs);
  }
  async function action(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : '请求失败');
    } finally {
      setBusy(false);
    }
  }
  async function select(id: string) {
    const run: Run = await (await api(`/api/runs/${id}`)).json();
    setActive(run);
    onReport(run.result ? parseAnswer(run.result) : null);
  }
  useEffect(() => {
    if (!running || !active) return;
    const current = generation.current;
    let stopped = false;
    let polling = false;
    const timer = setInterval(() => {
      if (polling || stopped) return;
      polling = true;
      void (async () => {
        try {
          const run: Run = await (await api(`/api/runs/${active.run_id}`)).json();
          if (stopped || current !== generation.current) return;
          setActive(run);
          if (run.result) onReport(parseAnswer(run.result));
          if (run.status !== 'queued' && run.status !== 'running') await refresh();
        } catch (e) {
          if (!stopped && current === generation.current)
            setError(e instanceof Error ? e.message : '状态读取失败');
        } finally {
          polling = false;
        }
      })();
    }, 500);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [active?.run_id, running, token, onReport]);
  return (
    <section aria-label="持久化研究工作台" className="space-y-4 rounded-xl border bg-white p-5">
      <h2 className="text-xl font-semibold">私人研究工作台</h2>
      <p className="text-sm text-slate-600">
        独立身份保护报告。访问令牌只保留在内存；重新登录可恢复历史记录。资料链接为人工录入来源，没有抓取网页。
      </p>
      <label className="block">
        工作台访问令牌
        <input
          aria-label="工作台访问令牌"
          type="password"
          autoComplete="off"
          value={token}
          disabled={connected}
          onChange={(e) => setToken(e.target.value)}
          className="mt-2 block w-full rounded border p-2"
        />
      </label>
      {!connected ? (
        <Button
          disabled={busy || !token}
          onClick={() =>
            void action(async () => {
              await refresh();
              const data = await (await api('/api/library')).json();
              setLibrary(data.documents);
              setConnected(true);
            })
          }
        >
          连接工作台
        </Button>
      ) : (
        <Button
          disabled={busy}
          onClick={() => {
            generation.current++;
            setConnected(false);
            setToken('');
            setProviderToken('');
            setRuns([]);
            setActive(null);
            setLibrary([]);
            onReport(null);
          }}
        >
          退出工作台
        </Button>
      )}
      {connected && (
        <>
          <details>
            <summary>资料库 · {library?.length} 篇当前版本</summary>
            <ul>
              {library?.map((doc) => (
                <li key={doc.id} className="my-3 break-words text-sm">
                  {doc.title} · v{doc.version} · {doc.acquisition}
                  <br />
                  {doc.recorded_at}
                  <br />
                  来源类别：{doc.kind}
                  <br />
                  {safeHttpsUrl(doc.url) ? (
                    <a
                      href={safeHttpsUrl(doc.url)!}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline"
                    >
                      {doc.url}
                    </a>
                  ) : (
                    '合成练习，无外链'
                  )}
                  <br />
                  SHA-256 {doc.content_hash}
                </li>
              ))}
            </ul>
          </details>
          <label className="block">
            研究问题
            <textarea
              aria-label="研究问题"
              maxLength={1000}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="mt-2 block w-full rounded border p-2"
            />
          </label>
          <label className="block">
            研究模式
            <select
              aria-label="研究模式"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="mt-2 block w-full rounded border p-2"
            >
              <option value="demo">演示 · 零模型调用</option>
              <option value="deepseek">DeepSeek · 会产生费用</option>
            </select>
          </label>
          {mode === 'deepseek' && (
            <label className="block">
              模型访问码
              <input
                aria-label="模型访问码"
                type="password"
                autoComplete="off"
                value={providerToken}
                onChange={(e) => setProviderToken(e.target.value)}
                className="mt-2 block w-full rounded border p-2"
              />
            </label>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={
                busy || running || !prompt.trim() || (mode === 'deepseek' && !providerToken)
              }
              onClick={() =>
                void action(async () => {
                  const run = await (
                    await api('/api/runs', {
                      method: 'POST',
                      headers: { 'X-Playground-Token': providerToken },
                      body: JSON.stringify({ prompt, mode }),
                    })
                  ).json();
                  setActive(run);
                  onReport(null);
                  await refresh();
                })
              }
            >
              开始研究
            </Button>
            <Button disabled={busy} onClick={() => void action(refresh)}>
              刷新报告
            </Button>
            {running && (
              <Button
                onClick={() =>
                  void action(async () => {
                    setActive(
                      await (
                        await api(`/api/runs/${active!.run_id}/cancel`, { method: 'POST' })
                      ).json(),
                    );
                    await refresh();
                  })
                }
              >
                取消研究
              </Button>
            )}
          </div>
          {active && (
            <div aria-label="任务详情" className="space-y-2 break-words">
              <p role="status">
                状态：{active.status} · run_id：{active.run_id}
              </p>
              {active.failure_reason && <p role="alert">失败原因：{active.failure_reason}</p>}
              <ul>
                {active.read_documents?.map((doc) => (
                  <li key={doc.id}>
                    {doc.title} · 已读 v{doc.version} · {doc.content_hash}
                  </li>
                ))}
              </ul>
              <div className="flex gap-2">
                {['markdown', 'json'].map((format) => (
                  <Button
                    key={format}
                    disabled={busy || running}
                    onClick={() =>
                      void action(async () => {
                        const blob = await (
                          await api(`/api/runs/${active.run_id}/export?format=${format}`)
                        ).blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `report-${active.run_id}.${format === 'markdown' ? 'md' : 'json'}`;
                        a.click();
                        setTimeout(() => URL.revokeObjectURL(url), 1000);
                      })
                    }
                  >
                    导出 {format === 'markdown' ? 'Markdown' : 'JSON'}
                  </Button>
                ))}
              </div>
            </div>
          )}
          <h3 className="font-semibold">报告列表</h3>
          <ul className="space-y-2">
            {runs.map((run) => (
              <li key={run.run_id} className="rounded border p-3">
                <button
                  className="w-full break-words text-left underline"
                  disabled={busy}
                  onClick={() => void action(() => select(run.run_id))}
                >
                  {run.prompt} · {run.status}
                </button>
                <Button
                  disabled={busy || ['queued', 'running'].includes(run.status)}
                  onClick={() =>
                    void action(async () => {
                      await api(`/api/runs/${run.run_id}`, { method: 'DELETE' });
                      if (active?.run_id === run.run_id) {
                        setActive(null);
                        onReport(null);
                      }
                      await refresh();
                    })
                  }
                >
                  删除自己的记录
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
      {error && (
        <p role="alert" className="break-words text-red-800">
          {error}；输入保留，可重新连接或刷新重试。
        </p>
      )}
    </section>
  );
}
