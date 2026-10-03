# 持久化研究工作台

本轮新增 /api/library 和 /api/runs。原 /api/ask 保留为公开、无保存的骨架演示接口；真实模式仍需模型访问码。私人报告仅通过受保护的工作台 API 访问。

## 身份与运行

服务端环境 WORKSPACE_IDENTITIES 为 JSON 对象，键是稳定用户 ID，值是独立随机访问令牌；由维护者通过托管 secrets 配置，不提交、不打印。Authorization: Bearer 令牌决定报告所有者，客户端不能传 owner。令牌只在 React 内存保存，退出清除；换令牌保留用户 ID 可继续访问历史。第一轮为受控小规模工作台，不提供公开注册，须使用 HTTPS，身份枚举、令牌吊销和轮换由维护者管理。

MAINTAINER_TOKEN 单独保护 POST /api/library，并同时要求工作台身份。只允许公开来源的人工摘录，kind=public-manual、acquisition=manual-transcription；当前固定 HTTPS 主机白名单为 FastAPI、MCP、OpenAI 文档和 DeepSeek 文档。提供链接不意味着程序获取页面，也不意味着课程摘录是官方原文。既有合成材料继续标识 conflict-fixture。没有自动抓取、任意 URL 工具或代码执行。

POST /api/runs 接收 prompt、mode，返回 202 与 run_id，仅保存 queued 及当前资料快照。POST /api/runs/{id}/execute 独立请求 claim 数据库租约，最多 25 秒请求内等待研究完成；React 创建后发执行请求，同时独立轮询。queued → running → completed / failed / cancelled；关闭页面/退出导致执行请求断开可能取消研究。重启保留 queued，页面详情可明确执行；有效 running 租约不受另一个冷启动影响，过期则 interrupted/lease_expired，绝不自动重放付费调用。取消不能证明供应商没有计费。数据库约束最多四个活跃租约、全局每分钟十次模型请求；共享限流是安全上限，不能替代供应商费用预算。

GET /api/runs 最多列出最近 100 条；详情、取消、删除及导出都验证所有者，其他身份请求统一返回 404。活动任务需先取消再删除；已取消 worker 尚未回收时删除返回 409，待回收或租约过期可删。详情保存实际读取的版本化原文、引用、操作摘要、已知用量和失败原因，导出不包含令牌或 owner。JSON 是完整审计记录，Markdown 为阅读报告。引用校验只证明读取与原文子串存在，语义仍须人工核验。

## SQLite 与恢复

RESEARCH_DB_PATH 默认为 data/research.sqlite3。SQLiteStore 提供 Store 协议，可通过 create_app(storage_factory=...) 替换。schema_migrations v1 创建不可变 documents(id,version,payload) 与按所有者隔离的 runs；每次录入递增版本并计算正文 SHA-256 与 UTC 录入时间。启动幂等初始化五篇种子，不重复写版本。研究开始时冻结当前资料副本，后续更新不会改变引用校验和保存的已读原文。

仅运行单个 Uvicorn worker，数据库及 WAL/SHM 放持久卷，限制目录权限，安排加密备份和保留策略。本地 SQLite 不使用进程任务表；短事务租约控制执行。SQLite 调用在同一事件循环，适用于小规模开发，不宣称高并发生产容量。v2 增加租约、创建时间索引字段和共享模型请求限流表，旧 running 无租约记录首次读取时标为 interrupted/process_restarted。后续结构升级必须增加迁移和测试。

## PostgreSQL 与 Vercel

DATABASE_URL 存在时选择 PostgreSQLStore；每个短事务独立连接，数据库事务锁保护迁移、版本写入、claim/cancel/checkpoint，按执行令牌及数据库时间约束写入。连接/语句/锁有限时，失败返回 database_unavailable，不回显连接串。Vercel 使用 Services 的 frontend/backend 同域部署；配置详见 [ADR 002](ADR-002-vercel-persistence.md)。VERCEL 环境缺少 DATABASE_URL 时失败关闭 durable_storage_required，不建立临时 SQLite。生产需维护者配置 TLS 数据库 URL、备份、身份托管 secrets，尚未进行生产部署和真实模型调用。

研究每次完成资料操作、收到供应商用量、发起模型 HTTP 请求之前都保存审计检查点。正在等待的模型轮次将 usage_complete 标为 false；硬中断恢复保留之前已知用量和已读版本，不将未返回的供应商用量视为零。仍可能存在网络已发起而供应商未报告的费用，不能由本地数据库计算最终账单。

## 会话切换与部分初始化恢复

每次工作台身份输入变化、连接、退出和组件卸载都失效旧会话并取消它的所有请求。旧响应即使已经收到或无法真正取消，也须通过当前 session generation 才能更新列表、详情、报告、错误、busy 或发起下载。退出不被进行中的操作锁住。执行请求内监测断开，退出会尽力停止；确切停止状态仍须后续登录查询，或使用明确取消接口。

SQLite 启动按缺失种子 ID 幂等补齐，修复首次录入过程中中断留下的部分资料库；已有维护者修订不被覆盖或重新写版本。迁移版本存在不再被当作种子批次完整的证据。

## 取消与下一轮的原子边界

取消确认后的数据库状态直接约束模型/工具准入，不能仅依赖周期轮询。进度检查点保存当前审计后若遇到 cancelled/interrupted 会立即停止，另有每次模型/工具开始前的租约检查。取消前已准入、已经在途的请求仍可能收费；其响应若已返回，保存已知用量及“模型用量”轨迹，但不执行响应里的工具、不发下一轮。未返回的请求保持 usage_complete=false；所有已发轮次完整用量已经返回时，取消记录也可 usage_complete=true，这只表示审计完整，不表示没有费用。租约过期的同令牌迟到响应只能补充审计，不改回 running、不自动重试；记录已删除或令牌不匹配则拒绝写入。
