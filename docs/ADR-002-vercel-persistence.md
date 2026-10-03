# ADR 002：Vercel 持久化与请求内有界执行

2026-10-03。接受；生产托管资源仍由维护者配置。

查阅当前官方 [Python runtime](https://vercel.com/docs/functions/runtimes/python)、[Services](https://vercel.com/docs/services)、[服务配置](https://vercel.com/docs/services/config-reference)、[路由](https://vercel.com/docs/services/routing)、[函数时限](https://vercel.com/docs/functions/configuring-functions/duration)、[FastAPI BackgroundTasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)、[PostgreSQL 锁](https://www.postgresql.org/docs/current/explicit-locking.html) 和 [Psycopg 事务](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)。Services 当前为 beta，支持同部署中独立构建 Vite 与 FastAPI、共享域名路由；配置按服务分配，保留原始请求路径。实际平台发布验证需托管权限，不能以本地 API 或 CI 替代。

决定使用根 `vercel.json` 的两个 services：frontend Vite 静态资源；backend FastAPI `app:app`，Python 3.12 / uv.lock 冻结安装，函数时限 60 秒。删除原先 API 503 占位。`DATABASE_URL` 选择 PostgreSQL；Vercel 缺失该配置时失败关闭，绝不回退临时 SQLite。SQLite 仍供持久卷本地教学。

`POST /api/runs` 仅持久化 queued 记录和当时的资料版本快照。客户端随后发 `POST /api/runs/{id}/execute`，执行循环设置 25 秒 asyncio 超时，期间独立轮询详情；初始化、同步数据库操作及收尾在该范围外，同步操作也不能由事件循环超时即时抢占，因此整个 HTTP 请求没有 25 秒硬上限。平台另配置 60 秒函数 maxDuration，需实际云端验收。运行的 asyncio task 在响应前取消/等待完成，绝不依赖返回响应后的进程存活。重新连接看到 queued 可明确执行；不会默默恢复有费用的任务。

数据库短事务串行化状态转换、版本分配和初始化：SQLite BEGIN IMMEDIATE；PostgreSQL transaction advisory lock。运行租约用数据库时间，期限 60 秒，独立随机执行令牌只保存在数据库列中，所有 checkpoint 需要匹配令牌及有效租约。同 run 只有 queued 可 claim；活跃重复请求返回 409，终态返回原记录，不再次调用。取消保留租约直到 worker 回收或过期，阻止删除/复活；跨冷启动新实例不会干扰仍有效的执行。硬中断后首次读取将过期 running 标为 interrupted，保留已读资料/用量，未知用量明确标记，不自动重放模型请求。

数据库连接/锁/语句均有限时；PostgreSQL 每个短事务独立连接、禁用 prepared statements，适合外部事务池连接 URL。连接串只取服务端环境；错误返回固定分类，不回显数据库凭据。迁移和种子在事务内，缺失 ID 幂等补齐，已有维护者版本不覆盖。身份始终由服务端 WORKSPACE_IDENTITIES 映射，owner 条件在每次数据库操作中落实，私人端点 no-store。

代价：该执行形态只适用于三轮/两工具的短研究；关闭客户端可能取消正在执行的请求，硬杀进程最多等租约过期才可确认中断。长期研究应采用独立持久队列/工作流，不扩大当前时限伪装可靠。数据库短事务暂用全局锁，优先正确性，小规模工作台可接受；高吞吐可改为行锁及专用版本锁，必须保留并发回归。CI 使用临时 PostgreSQL 验证真实事务、重复 claim、取消、过期、重启和 React→API；所有模型为 demo/mock。

取消是数据库操作准入屏障：每次模型轮次和只读工具开始前检查有效租约及 running；进度检查点在保留审计后若看到 cancelled/interrupted 立即停止 generate。100ms 监测只负责取消等待中的请求，不承担下一轮准入正确性。取消前已经准入/发出的 HTTP 请求无法撤销供应商计费；若该响应先返回，保留本轮已知用量与轨迹，随后不执行它的 tool_calls、不发下一轮。若响应未返回，pending_model_call 继续标记未知用量。取消与租约过期均不允许复活终态；同令牌的迟到响应只可补齐审计，不能继续执行。


Vercel 项目 Framework Preset 必须选择 **Services**；本地验证使用固定 CLI 的 `vercel dev -L`，以当前官方 services/root/rewrites 为准。该预检不登录、不连接项目、不发布远端，不能替代云端构建。官方 [Functions API Reference](https://vercel.com/docs/functions/functions-api-reference#cancel-requests) 当前仅对 Node.js 提供 supportsCancellation；本项目 Python 不设置它。Uvicorn/原始ASGI的断开证据仍有效，但不能推断Vercel Python云端一定传播disconnect或保留清理时间，必须在托管预览单独验证。显式数据库cancel和租约过期恢复仍是可审计边界。
