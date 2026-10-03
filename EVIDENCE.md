# 毕业项目验收证据

- 源码 commit、语言、环境与依赖版本：
- 冻结安装、格式、构建与测试命令及实际结果：
- 浏览器 → API 的演示提问与实际引用：
- 无证据问题、非法参数、超长输入与实际错误：
- 取消是否停止请求，供应商可能已计费的边界：
- 真实模型调用、托管预算与用量（未配置就写未验证）：
- 部署 URL、健康接口、生产浏览器流程与回滚入口：
- 账号、持久化、资料上传和其他尚未实现内容：

只记录可复现结果，不写密钥、Cookie、验证码或原始认证状态。骨架测试通过不能代替你的修改、真实服务或生产验收。

## 2026-10-03 · 首轮实际增量

基础提交 533291b 已从远端 develop fast-forward 保留；main 未修改。首个后端功能提交 faba508c6e497bd5c9b01c6c94cc827f5f0837b4，增加版本化资料库、身份保护的任务/报告 API、SQLite v1 与中断恢复、冻结实际读取原文。后续 React/评测提交的精确 SHA 由下次证据更新补充，避免自引用 commit。

环境：Node v24.19.0、Python 3.12.14、pnpm 10.32.1（通过 npx 调用精确版本）；uv 使用仓库锁文件。环境默认 pnpm 是 11.25.0，其供应链时间策略拒绝既有锁文件；未改既有依赖版本，改用项目要求的 10.32.1。新增精确锁定 @playwright/test 1.58.2。

实际运行：

| 命令 | 结果 |
| --- | --- |
| uv sync --locked --project backend | 通过 |
| npx --yes pnpm@10.32.1 --dir frontend install --frozen-lockfile | 通过 |
| uv run --project backend ruff check backend scripts tests | 通过 |
| uv run --project backend ruff format --check backend scripts tests | 通过 |
| uv run --project backend python -m pytest backend tests | 51 通过；含新增 8 项参数化工作台测试；一项 Starlette TestClient 依赖弃用警告 |
| uv run --project backend python scripts/evaluate.py | 3 固定证据契约通过，0 模型调用 |
| npx --yes pnpm@10.32.1 --dir frontend check | 格式、TypeScript、Vite 构建通过 |
| node --test frontend/src/response.test.mjs | 13 通过 |
| node --check scripts/run_headless.mjs | 通过语法检查 |
| uv run --project backend python scripts/check_secrets.py | 暂存区/工作区/ZIP 扫描通过，提交前再次执行 |
| npx --yes agent-browser install | 云端失败：浏览器下载版本信息证书错误 |
| pnpm 10.32.1 --dir frontend exec playwright install chromium | 云端失败：CDN 返回下载内容不是有效 ZIP |
| node scripts/run_headless.mjs | 云端启动 React/API 后因缺少浏览器可执行文件退出；已清理测试进程和临时数据，未声称链路通过 |

GitHub CI：[faba508 · run 37129640102](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37129640102) quality 全部成功，冻结安装、51 后端/敏感测试、前端检查与 13 响应契约均成功。该 CI 尚不包含后续 React 工作台 headless；后续提交已加入固定评测与真实 HTTP headless 步骤，结果另记。

实际 API 测试覆盖三个证据场景、无身份 401、跨用户列表隔离及详情/删除 404、维护者 403、非允许来源 422、更新后旧报告保留 v1/新报告读取 v2、重启保留报告、活动任务重启 interrupted、取消保留已读原文、上游失败保留已知调用/部分用量、伪造/未读引用拒绝，以及 Vercel 缺持久存储时 503。调用全部 demo/mock，不产生模型费用。

语义核验与机械检查分开：演示答案复述实际已读正文，冲突资料明确标合成且不裁定真假，无匹配返回固定证据不足。这里未完成真实模型回答的人工作品质量评估、事实逐项支持性评分或真实语义冲突识别；引用存在性不等于语义正确。

React 审查：独立工作台组件，凭据仅内存，读请求超时/禁止缓存，轮询串行并在退出/切换时忽略旧响应，退出/删除当前报告清除展示；原公开演示与私人存储分开。下载使用 Blob，不把令牌放 URL。

[草稿 PR #1](https://github.com/frontend-is-magic/deep-ai-research-assistant/pull/1)。CLI HTTPS push 无可用用户名；改用已连接 GitHub 的 tree/commit/ref API 普通更新 develop，再 fetch/rebase 等价本地提交；未查看或输出认证缓存，没有强推。

未验证：原生 Codex Browser、云端 headless（待 GitHub CI）、真实 DeepSeek/真实断连计费、生产部署、Vercel 构建和反向代理、托管数据库/持久任务队列/共享费用预算、SSO 和公开注册。Vercel 配置目前只交付前端且 API 占位安全返回 503，不能作为独立在线研究产品发布。所有人工事项汇总 HUMAN_ACTIONS.md，其他开发照常。

## React 工作台 CI 与运行中审计补强

React/评测增量实际提交 fd0942a973d0aaf2541d9580b5cc33df306bbc2a。对应 [CI run 37130204009](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37130204009) 已全部成功，含 headless，不再列为“CI 待验证”。实际 job 111223639238 日志确认：

> Headless PASS: 6 desktop/mobile research flows, 12 downloads, keyboard submit, denied identity, reload and API restart recovery, logout privacy; 0 page errors; 0 model calls.

这是 GitHub Ubuntu headless 上实际 React/Vite → HTTP FastAPI → SQLite 的结果；云端本地因浏览器下载受限未跑通，原生 Codex Browser 验收仍交回主线。没有将 CI headless 等同于原生 Browser 或真实模型验收。

后续补强使资料操作、用量返回及每轮模型调用前写审计检查点；增加真实 engine + MockTransport 的挂起第三轮测试：已知 2 轮用量与已读 v1 原文在 running 状态已进入 SQLite，恢复为 interrupted 后仍保留，未知第三轮不计作零。最终补强 commit/CI 由 Git 历史和后续证据条目定位。
