# 一次性人工事项 · 交回主线

统一使用已有对话「Deep AI Station｜一次性人工配置」(01a10121-db57-71e3-bcc2-7f09e96dc54b)。本云端不能访问该对话，不新建替代对话；本文件供主线转交。

1. **工作台身份**：在持久化 API 的托管 secrets 中配置 WORKSPACE_IDENTITIES（稳定用户 ID → 独立随机令牌），维护者单独配置 MAINTAINER_TOKEN；不在聊天、Git 或 VITE_ 中传递。先确认资料可公开录入、报告保留与删除策略。受控令牌身份已实现；公开注册/SSO、共享预算尚未实现。
2. **存储与部署**：选择单 worker 且有持久卷的 API 环境，配置 RESEARCH_DB_PATH、HTTPS、备份与限制目录权限；或授权托管数据库/队列并继续实现适配器。Vercel 配置目前只构建前端，所有 API 请求安全返回 503 durable_api_not_configured。连接已授权的持久 API 后替换该占位函数/配置；未发布生产，不将 Vercel 临时 SQLite 当生产存储。
3. **DeepSeek**：仅服务端配置 DEEPSEEK_API_KEY、DEEPSEEK_MODEL 与 PLAYGROUND_ACCESS_TOKEN，先设置供应商费用上限并单独授权真实调用费用，再进行真实模型验收。当前 mock/demo 开发不需要提供密钥。
4. **原生浏览器验收**：主线用 Codex 内置 Browser 检查登录、三类研究、报告详情、资料版本、两种下载、刷新/重启恢复、键盘/窄屏、错误重试、取消及退出隐私。云端 headless 与原生验收分别记证据；不远控用户桌面。
5. **发布与合并**：主线审阅 PR #1、CI 与 EVIDENCE.md 后决定 main 验收合并和 Vercel 连接/发布；本轮不自动改 main。

GitHub 代码同步已通过现有连接完成，不需要为本轮另行配置 Git 命令行凭据。没有购买额度、重置卡或真实模型调用。
