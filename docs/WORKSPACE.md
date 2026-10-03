# 持久化研究工作台

本轮新增 /api/library 和 /api/runs。原 /api/ask 保留为公开、无保存的骨架演示接口；真实模式仍需模型访问码。私人报告仅通过受保护的工作台 API 访问。

## 身份与运行

服务端环境 WORKSPACE_IDENTITIES 为 JSON 对象，键是稳定用户 ID，值是独立随机访问令牌；由维护者通过托管 secrets 配置，不提交、不打印。Authorization: Bearer 令牌决定报告所有者，客户端不能传 owner。令牌只在 React 内存保存，退出清除；换令牌保留用户 ID 可继续访问历史。第一轮为受控小规模工作台，不提供公开注册，须使用 HTTPS，身份枚举、令牌吊销和轮换由维护者管理。

MAINTAINER_TOKEN 单独保护 POST /api/library，并同时要求工作台身份。只允许公开来源的人工摘录，kind=public-manual、acquisition=manual-transcription；当前固定 HTTPS 主机白名单为 FastAPI、MCP、OpenAI 文档和 DeepSeek 文档。提供链接不意味着程序获取页面，也不意味着课程摘录是官方原文。既有合成材料继续标识 conflict-fixture。没有自动抓取、任意 URL 工具或代码执行。

POST /api/runs 接收 prompt、mode，返回 202 与 run_id。queued → running → completed / failed / cancelled；进程重启时未完成任务标为 interrupted/process_restarted，不自动重放付费调用。完成 outcome 独立表示证据充分、不足、冲突。断开页面不取消后台任务；取消必须显式 POST /api/runs/{id}/cancel。取消不能证明供应商没有计费。最多四个活跃任务；每实例模型请求限流沿用骨架，非共享生产预算。

GET /api/runs 最多列出最近 100 条；详情、取消、删除及导出都验证所有者，其他身份请求统一返回 404。活动任务需先取消再删除。详情保存实际读取的版本化原文、引用、操作摘要、已知用量和失败原因，导出不包含令牌或 owner。JSON 是完整审计记录，Markdown 为阅读报告。引用校验只证明读取与原文子串存在，语义仍须人工核验。

## SQLite 与恢复

RESEARCH_DB_PATH 默认为 data/research.sqlite3。SQLiteStore 提供 Store 协议，可通过 create_app(storage_factory=...) 替换。schema_migrations v1 创建不可变 documents(id,version,payload) 与按所有者隔离的 runs；每次录入递增版本并计算正文 SHA-256 与 UTC 录入时间。启动幂等初始化五篇种子，不重复写版本。研究开始时冻结当前资料副本，后续更新不会改变引用校验和保存的已读原文。

仅运行单个 Uvicorn worker，数据库及 WAL/SHM 放持久卷，限制目录权限，安排加密备份和保留策略。不得运行多个独立实例共享进程任务表。SQLite 调用在同一事件循环，适用于小规模开发，不宣称高并发生产容量。迁移目前只有 v1；后续结构升级必须增加迁移和测试。

VERCEL 环境没有注入持久存储实现时，私人工作台返回 503 durable_storage_required。临时目录 SQLite 不能承担可靠生产持久化；Vercel 仅先发布前端并代理到有持久卷的 API，或先实现托管数据库及持久任务队列。未进行生产部署和真实模型调用。
