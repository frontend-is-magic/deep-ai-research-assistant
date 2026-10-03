# Deep AI Research Assistant

有证据、有边界的技术研究助手，来自 Deep AI Station 的 Agent 毕业项目。当前仓库是已验证骨架，云端任务将在 develop 持续实现资料版本、研究任务、持久化和评测，不把演示骨架当作成品。

- 原教程：[三个 Agent 毕业课](https://deep-ai-station.vercel.app/lesson/agent-research-agent)
- 来源：[deep-ai-station @ 428fadd](https://github.com/frontend-is-magic/deep-ai-station/tree/428fadd5a713710c3931d61fc6befd1cf571dbef/starters/agent)
- [开发任务与验收](docs/PRODUCT.md) · [现有骨架运行方法](docs/STARTER.md) · [实际验收证据](EVIDENCE.md)

前端 React + TypeScript / Tailwind / Jotai，后端 uv / FastAPI / Ruff。真实模型使用 DeepSeek 的 OpenAI 兼容 messages / tool_calls 格式、固定 DeepSeek API 地址与服务端 DEEPSEEK_API_KEY；默认演示无需密钥。敏感配置、私钥、认证缓存、日志和本地数据库均应忽略，仅保留空值模板。

分支：main 保持已验收状态，develop 开发；提交使用中文前缀。已有测试验证三种证据场景、引用校验、取消和预算边界，真实模型与该独立项目的生产部署尚未验收。
