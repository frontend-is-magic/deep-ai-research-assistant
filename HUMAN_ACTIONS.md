# 一次性人工事项 · 交回主线

统一使用已有对话「Deep AI Station｜一次性人工配置」(01a10121-db57-71e3-bcc2-7f09e96dc54b)。本云端不能访问该对话，不新建替代对话；本文件供主线转交。

1. **生产 PostgreSQL**：维护者选择已授权托管库，在 Vercel backend 服务的托管 secrets 配置 DATABASE_URL（TLS、可用事务池连接、受限专用数据库角色），确认地区、备份恢复、保留/删除策略。适配器与事务迁移已备妥；CI 使用临时测试库，无须提供生产 URL 给云端。不要使用 Vercel 临时 SQLite；本地教学继续 RESEARCH_DB_PATH + 持久卷。首次连接可建表与幂等种子；正式部署前独立备份并验证迁移权限。
2. **工作台身份**：在 backend 托管 secrets 配置 WORKSPACE_IDENTITIES（稳定用户 ID → 独立随机令牌）与独立 MAINTAINER_TOKEN，不在聊天、Git 或 VITE_ 中传递。确认资料可公开录入、报告策略、HTTPS、令牌轮换与吊销。受控令牌身份和 owner 隔离已实现；公开注册/SSO 尚未提供。
3. **DeepSeek 预算**：默认 demo，不需要模型凭据。维护者仅在服务端配置 DEEPSEEK_API_KEY、DEEPSEEK_MODEL 与 PLAYGROUND_ACCESS_TOKEN，先设置供应商费用上限并单独授权真实验收预算。固定官方 endpoint，数据库共享十次/分钟限流与单研究三轮/两工具约束已备妥，但不替代供应商账单或预算。未经授权不做真实调用。
4. **Vercel 发布**：主线已观察既有 bloodymoons-projects 的 Vercel 连接器返回403（scope授权不足），需在上述既有人工配置聊天恢复对应项目/团队授权；不绕过认证、不新建账户或服务。根目录 vercel.json 的两个 Services 已备妥，当前官方 Services 为 beta；确认维护者项目可用性，项目 Framework Preset 选择 Services，Python 3.12、60 秒函数 maxDuration。执行循环25秒之外还有初始化/同步DB/收尾，不能把整个HTTP请求视为25秒硬上限。连接独立仓库，生产分支维持 main，预览可用 develop。配置 backend secrets 后发布预览，再验同域 `/api/health`、受保护工作台、无配置失败关闭、重复执行及冷启动。supportsCancellation 当前只支持 Node.js；Python 云端真实客户端断开传播与审计清理须单独验收，本地ASGI证据不能替代。云端没有创建账号/购买服务/调用部署，本地与 CI 不替代实际 Vercel 构建和路由验收。
5. **原生浏览器与合并**：主线用 Codex 内置 Browser 检查身份、三类研究、报告详情、资料版本、两种下载、queued 明确执行、刷新/重启恢复、键盘/窄屏、错误重试、取消及退出隐私。独立记录原生证据；不远控用户桌面。审阅 PR #1、CI 与 EVIDENCE.md 后决定 main 验收合并；云端继续 develop，不自动改 main。

GitHub 代码同步使用现有连接，无须新配 Git 凭据。本轮全部模型为 demo/mock，没有购买额度、重置卡、付费模型或沙箱调用。
