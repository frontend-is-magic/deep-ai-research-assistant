# Deep AI Research Assistant

有证据、有边界的技术研究助手，来自 Deep AI Station 的 Agent 毕业项目。develop 已在学习骨架上新增版本化资料、私人研究任务、报告与持久化评测，可在 SQLite 持久卷或 PostgreSQL 环境运行；在线生产部署与真实模型尚未验收。

- 原教程：[三个 Agent 毕业课](https://deep-ai-station.vercel.app/lesson/agent-research-agent)
- 来源：[deep-ai-station @ 428fadd](https://github.com/frontend-is-magic/deep-ai-station/tree/428fadd5a713710c3931d61fc6befd1cf571dbef/starters/agent)
- [开发任务与验收](docs/PRODUCT.md) · [现有骨架运行方法](docs/STARTER.md) · [实际验收证据](EVIDENCE.md)

前端 React + TypeScript / Tailwind / Jotai，后端 uv / FastAPI / Ruff。真实模型使用 DeepSeek 的 OpenAI 兼容 messages / tool_calls 格式、固定 DeepSeek API 地址与服务端 DEEPSEEK_API_KEY；默认演示无需密钥。敏感配置、私钥、认证缓存、日志和本地数据库均应忽略，仅保留空值模板。

分支：main 保持已验收状态，develop 开发；提交使用中文前缀。已有测试验证三种证据场景、引用校验、取消和预算边界，真实模型与该独立项目的生产部署尚未验收。

## develop 首轮工作台

新增能力与权限契约见 [WORKSPACE.md](docs/WORKSPACE.md)。后端仍可按 STARTER 运行；额外在服务端托管环境注入 WORKSPACE_IDENTITIES 后，页面“私人研究工作台”可创建、恢复、删除与导出自己的报告。访问令牌留在内存，公开演示继续无需身份。

本地验证（仓库根目录）：

```sh
uv sync --locked --project backend
pnpm --dir frontend install --frozen-lockfile
uv run --project backend python -m pytest backend tests
uv run --project backend python scripts/evaluate.py
pnpm --dir frontend check
node --test frontend/src/response.test.mjs
pnpm --dir frontend exec playwright install chromium
node scripts/run_headless.mjs
```

headless 使用随机临时身份和临时 SQLite，启动独立端口 8010/5174，三种证据案例、桌面/窄屏、下载、键盘、身份拒绝、刷新和 API 进程重启后恢复均使用实际 HTTP。端口占用时退出，不操作现有服务。模型密钥强制为空，不产生模型调用。

`vercel.json` 从仓库根以 Vercel Services（当前 beta）分别构建 Vite 与 FastAPI，路由 `/api/*` 到 Python API；占位函数已删除。服务端 DATABASE_URL 使用托管 PostgreSQL，禁止 Vercel 临时 SQLite。创建与请求内有界执行分离，数据库租约、共享调用限流、取消及恢复见 [架构决策](docs/ADR-002-vercel-persistence.md)。配置托管 secrets 后即可进行发布验收；本轮未连接生产资源或发布。[HUMAN_ACTIONS.md](HUMAN_ACTIONS.md) 汇总唯一人工配置交接。


真实 PostgreSQL 验证由 CI 临时 postgres:17 服务执行。开发者也可在独立测试库设置 TEST_DATABASE_URL 后运行 pytest；测试创建随机 schema 并清理，勿指向生产。`RESEARCH_E2E_POSTGRES=1 node scripts/run_headless.mjs` 使用该测试 URL 走真实 React→API→PostgreSQL 和 API 重启链路；默认继续 SQLite。所有验收禁用真实模型。
