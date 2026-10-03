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

检查点补强精确提交 42525fe3e4d1bf6f37930b920a7a78313474a689；[CI run 37130498829](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37130498829) quality 全部成功，包括 52 后端/敏感测试、3 固定评测、13 前端响应契约及完整 headless。本地工作区与远端 develop 对应 commit 已同步，main 未改动。

收尾新增保护：维护者不能将既有 conflict-fixture 替换为 public-manual（409 fixture_is_immutable），空白标题/正文拒绝（422），关键词统一 trim/lowercase，空 DB 路径采用开发默认。相应断言纳入现有版本/权限测试，本地 52 项重新通过。此修复的远端精确提交/CI 待下一证据条目填写；README/STARTER 已区分旧骨架与新增工作台，未把旧 demo 当作本轮成果。

## 首轮代码验收点

最后代码修复提交 **ded4c2e289a4af2b01887114529b1b9277ae3f32**（fix: 保护合成证据类别并补全验收说明）。[对应 CI run 37130690555](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37130690555) / job 111225022137 已全部成功，冻结依赖、Ruff、52 后端/敏感测试、React 格式/类型/构建、13 响应契约、3 固定证据评测以及完整 headless 均通过。前面条目中对此提交的“待验证”已经由此实际结果补齐。

可运行交付为 develop 的 React + FastAPI 工作台，运行方法见 README.md / docs/WORKSPACE.md；持久卷环境与托管身份配置齐备后，可独立管理自己的研究记录。代码验收点包括版本化维护者资料录入、私人任务/列表/详情/删除/导出、SQLite 重启恢复、活动任务审计检查点和预算/引用边界。仍无真实模型费用或生产部署。

最终工作区检查：git diff --check 无问题；python scripts/check_secrets.py 扫描 39 个暂存区 blob 与 39 个工作区文件（含 ZIP 成员规则）通过；本地对应远端 develop，保留初始化修复 533291b。main 未修改，父教程仓库未检出或修改。

人工交接仅 HUMAN_ACTIONS.md：托管身份/维护者权限、持久化 API/部署、DeepSeek 费用与 secrets、主线原生 Browser 验收及 main/发布决定。不重复创建人工配置对话。Vercel 配置/503 占位可审查，但未执行 Vercel 构建/部署；生产数据库、共享预算、真实模型语义核验及原生 Browser 仍未验证。公开注册/SSO、通用语义冲突检测、网络抓取和隔离沙箱不在本轮实现中。

## 2026-10-03 · 主线独立审查修复 P1/P2

审查基准 0191fac818cbc26e549f1879a1f74ccac40a6f92。主线确认 P1：Alice running 报告轮询终态后，旧 GET /api/runs 延迟返回能污染 Bob 会话列表；P2：逐条提交种子且以“库非空”跳过整批初始化，首次中断后永久缺资料。这两项之前未被已通过的测试覆盖，已通过的旧 CI 不能证明不存在竞态。

P1 修复：所有工作台操作携带不可变 session generation/令牌/AbortController；身份输入变化、连接新会话、退出与卸载均使旧会话失效并取消全部旧请求。response/body await 之后再次核验代次，每次列表、详情、库、报告、错误及 busy 回写均被同一快照保护。轮询自己的取消控制器阻止旧详情回填；终态列表刷新完整等待并受保护。退出始终可用，不被 busy 锁住；旧导出不得触发下载，旧 finally 不得解除 Bob 的 busy。

新增 scripts/run_privacy_headless.mjs 使用真实 React/Vite + 纯 mock API，故意让 mock 忽略取消，覆盖 10 个异步入口 × 退出/Bob 已连接/Bob 仍连接中，共 30 个延迟完成场景。另 --baseline 在独立临时源码副本加载 0191fac 的 workspace.tsx，要求真实复现主线报告的 poll-list/bob 可见泄漏；不改工作树。CI checkout 全历史以读取精确审查基准。此前的实际 HTTP API headless 保留，不被纯 mock 测试替代。

已实际运行：pnpm 10.32.1 --dir frontend check（格式/TypeScript/Vite）通过，node --test frontend/src/response.test.mjs 13 通过，node --check scripts/run_privacy_headless.mjs 通过。云端 playwright install --only-shell chromium 仍收到无效 ZIP，node scripts/run_privacy_headless.mjs 因缺浏览器退出且清理自建进程；没有声称本地 headless 成功。P1 的 baseline/30 场景实际 CI 结果及修复 commit 待后续精确证据补齐。

P2 已先实跑独立对照：把 git show 0191fac:backend/storage.py 加载到内存模块，再对新 backend/test_storage.py 执行 pytest；三个断言均按预期失败（第 1/3 条提交后中断仍仅 1/3 篇，已有维护者修订时仍缺四篇）。工作树未替换旧源码。修复为按缺失种子 ID 幂等补齐，不覆盖已有 ID 或增加其版本。修复后 uv run --project backend python -m pytest backend tests 共 55 通过（原 52 + 新 3），Ruff 格式/检查通过；重启后原有维护者 v2 内容、版本、哈希与时间保持不变。

本轮不改变 main、不调用真实模型、不购买额度、不要求新的人工配置。每个提交前继续扫描暂存区/工作区/ZIP；精确提交及新增 CI 成功/失败将在后续条目如实记录。

## 主线审查 P1/P2 最终复核结果

| 修复 | 实际远端 commit | GitHub CI |
| --- | --- | --- |
| P1 旧会话响应/状态隔离 | 57d47775b281eb71972c9fa40228d954a2768e4c | [37132354790](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37132354790)，quality 全部成功 |
| P2 不完整种子初始化恢复 | bb7913bebdf0156e39fa563f3239d1853ea8a7e2 | [37132384660](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37132384660)，quality 全部成功 |

后一个 CI 的 job 111229902403 实际日志已读取，结果为：

- `55 passed, 1 warning`：含第 1/3 条种子提交后抛异常、重启补齐五篇、维护者 v2 不覆盖的三个新增测试。Starlette 弃用警告沿用基线。
- `Headless PASS: 6 desktop/mobile research flows, 12 downloads, keyboard submit, denied identity, reload and API restart recovery, logout privacy; 0 page errors; 0 model calls.`：原真实 HTTP React→API→SQLite 验收保留并通过。
- `Baseline 0191fac privacy regression reproduced: 1 failed assertions; Alice poll list appears in Bob session.`：独立临时源码副本中真实复现主线报告，不是把旧版测试成功当作修复成功；该负对照步骤以确认泄漏为预期结果。
- `Privacy headless PASS: 30 delayed completion scenarios; old lists/details/library/errors/busy/start/cancel/delete/export suppressed after logout or identity change; abort signals verified; mock ignores cancellation; 0 model calls.`：实际 React 与 mock API、10 入口 × 3 会话状态通过。分别测试 logout、Bob 已连接且列表空、Bob 连接仍挂起；旧详情/列表/资料库/错误不能回填，旧 finally 不能清除 Bob busy，旧导出不能下载。取消被故意忽略，成功依赖 generation 回写检查而不只依赖 AbortController。

可重复命令（仓库根）：

```sh
uv run --project backend python -m pytest backend tests
pnpm --dir frontend check
node --test frontend/src/response.test.mjs
pnpm --dir frontend exec playwright install --with-deps chromium
node scripts/run_headless.mjs
node scripts/run_privacy_headless.mjs --baseline
node scripts/run_privacy_headless.mjs
uv run --project backend python scripts/check_secrets.py
```

P2 的负对照实际命令将 `git show 0191fac:backend/storage.py` 经 exec 加载到独立 namespace，以旧 SQLiteStore 替换进程内 storage.SQLiteStore，然后 `pytest.main(['backend/test_storage.py', '-q'])`；三项测试按预期失败，其中首次提交后 remaining_ids=['api']。这只修改该验证进程的模块，不修改仓库源码。当前实现的三项同测试通过。

P1 所有异步入口复核：connect 的两项并发响应合并后才提交当前会话；refresh/select/poll/create/cancel/delete/export 的每个 response/body await 与异步回写前检查同一代次；error/finally 的 busyRef/state 同样受保护。poll 清理会中断其请求且停止后续 refresh；logout/身份变化会中断整个旧会话，连模型访问码、问题输入、已选报告和错误一起清除。仅前端会话失效，不能据此断言后台研究任务已取消或供应商未计费。

截至代码复核点 bb7913b，无用户人工依赖、无新增 credentials、无真实模型/费用调用，main 不变。云端本地 headless 因浏览器下载限制未跑通；上述浏览器证据来自 GitHub Ubuntu CI，原生 Codex Browser/生产部署/真实模型的未验证边界继续保持。现有草稿 PR #1 已更新，不另开 PR 或人工配置对话。

## Vercel 持久化增量 · 2026-10-03 · 本地证据

主线对 bb7913 的独立复验（用户回传，区别于本分支 CI）：同脚本先复现 0191fac 泄漏，再验证延迟 fetch/JSON × 忽略取消/禁用 abort 四种组合；旧响应实际交付仍不进入 Bob 列表/详情/错误，Bob 后续刷新正常。SQLite 1/5 恢复 5/5，维护者 v2 的正文/标题/时间/hash/自定义字段及 v1 历史逐字保留，重复初始化三次稳定。主线确认 3 个新增 storage 测试及 PR CI 37132384660 / push CI 37132382202 成功；本段为独立复验转述，不冒称云端新跑。

本轮新增 PostgreSQLStore / psycopg[binary]==3.3.3（uv.lock 冻结），SQLite v2 租约迁移、数据库共享容量/调用限流、create 与请求内 execute 分离、资料创建快照、跨实例取消与租约过期恢复。根 Vercel Services 配置路由实际 FastAPI，删除 503 占位；设计与官方资料见 ADR-002。缺少生产 DATABASE_URL 仍失败关闭，不能声称已部署。

实际本地命令与结果：

- `uv add --project backend 'psycopg[binary]==3.3.3'`、`uv sync --locked --project backend`：成功，28 个锁定包。
- `uv run --project backend ruff check backend scripts tests`、`ruff format --check backend scripts tests`：通过。
- 无 PostgreSQL URL 的 `python -m pytest backend tests -q`：63 passed / 11 skipped；其中 9 个 PostgreSQL 契约因未配置测试库跳过，2 个 SQLite 分组的 PG 专用测试跳过。
- 在本容器安装临时 PostgreSQL 16.15、启动本地 cluster、创建隔离 research_test 库；`TEST_DATABASE_URL=postgresql:///research_test uv run --project backend python -m pytest backend tests -q`：72 passed / 2 intentionally skipped，3.47s。没有生产数据库或外部服务账号；测试随机 schema 创建并清理。真实并发八连接同 run 仅一枚租约；四连接写版本得到 2/3/4/5；跨实例重复执行不重复 mock 调用；取消/超时/断开返回前 worker 已退出；审计跨新实例保持；过期 worker 无法写回；种子事务中断回滚且维护者历史保留。
- `npx --yes pnpm@10.32.1 --dir frontend check`：格式、TypeScript、Vite 生产构建通过。
- `node --test frontend/src/response.test.mjs`：13/13；`python scripts/evaluate.py`：3/3固定契约，零模型。
- `python scripts/check_secrets.py`：工作区/暂存区/ZIP 检查通过（提交前再次扫描）。

CI 已配置临时 postgres:17 服务、同契约真实 PostgreSQL 测试及第二轮 PostgreSQL React→API→数据库重启/queued 明确执行验收。提交 SHA 和实际 CI 结果将在推送后补记；此时尚未运行新的 CI headless，不据此声称通过。原生 Browser、实际 Vercel Services 构建/路由、生产 TLS/备份和 DeepSeek 真实用量尚未验证，集中在 HUMAN_ACTIONS。

### 已推送提交与实际 CI

实现提交：[19e5a91e8a98f379f22bc0416e7d6a9cb1911ac2](https://github.com/frontend-is-magic/deep-ai-research-assistant/commit/19e5a91e8a98f379f22bc0416e7d6a9cb1911ac2)，`feat: 增加PostgreSQL租约与Vercel请求内研究执行`。GitHub API 创建 tree 后与本地 git tree SHA 35aa45501f2f3525187ef039915026f629ef2692 完全一致；更新 develop 为非强推，fetch/rebase 同步后工作区干净。main 仍为 533291b025a53a703384976b2f3605641399a52d。

[PR CI 37134189156](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37134189156) completed/success；quality job 111235218963 的实际日志：

- PostgreSQL17 service 初始化成功，后端 `72 passed, 2 skipped, 1 warning in 5.03s`。两项 skip 是 SQLite 参数组的 PostgreSQL 专用线程/事务测试，不是 PostgreSQL 缺失。保留 FastAPI/httpx 测试客户端弃用警告。
- 冻结 uv/pnpm 安装、Ruff 检查及格式、前端格式/类型/构建、13 响应契约全部 success；敏感检查 `45 index blobs, 45 worktree files and embedded ZIP members checked`。
- 3 fixed contracts passed，0 model calls。
- `SQLite storage verified`；headless 实际 `6 desktop/mobile research flows, 12 downloads, keyboard submit, denied identity, reload and API restart recovery, queued cold-start explicit execution, logout privacy; 0 page errors; 0 model calls`。
- `PostgreSQL storage verified`；第二轮 headless 同样六种桌面/窄屏流程、十二导出、真实 API 重启、queued 在新进程中明确执行，0页面错误/0模型调用。
- `Baseline 0191fac privacy regression reproduced: 1 failed assertions; Alice poll list appears in Bob session`；负对照保持有效。
- `Privacy headless PASS: 30 delayed completion scenarios`；退出/切换身份后的旧列表、详情、资料、错误、busy、创建/取消/删除/下载均被压制，abort信号确实发出而mock故意忽略取消，0模型调用。

同一 [draft PR #1](https://github.com/frontend-is-magic/deep-ai-research-assistant/pull/1) 已更新范围与边界。上面的浏览器证据来自 GitHub Ubuntu 的真实 Chromium headless，不是云端本机原生 Browser，也不是实际 Vercel 平台验收。生产 DATABASE_URL/TLS/备份、托管身份、Services beta 项目可用性与实际平台构建/路由、DeepSeek 真实费用/语义仍未验证，HUMAN_ACTIONS 已给出具体交接。所有自动实现与 CI 均已完成，缺少生产凭据没有成为代码开发阻塞。

### 追加：真实 HTTP 断开边界修复

19e5a91 / c774274 的 CI 确实全部成功（c774274 CI 37134421800 也 completed/success），但原来的断开单元测试替换了 Request.is_disconnected，未覆盖真实网络与中间件。补做本地 Uvicorn 真实 socket 客户端取消后发现任务仍 running：HTTP 风格 Cache-Control 中间件消耗了断开事件，不能据原 CI 宣称及时观察真实断开。

改为纯 ASGI PrivateCache，只包装 send 添加 no-store，不读取/改写 receive。新增 `test_real_http_disconnect_stops_worker_and_persists_audit` 在随机独占端口启动真实 Uvicorn，客户端真实关闭执行连接，验证 cancelled/client_disconnected、worker 已退出、已读版本/未知用量保存，并在新存储实例复验；没有 patch Request，也没有真实供应商 HTTP。

实际负对照：临时仅恢复 c774274 的 HTTP 缓存中间件，运行 `TEST_DATABASE_URL=postgresql:///research_test ... pytest backend/test_durable.py -k real_http_disconnect -q`，SQLite/PostgreSQL 两组均因 running != cancelled 失败，2 expected failures；随后 finally 恢复工作区。修复后的完整后端/敏感测试为 `74 passed, 2 skipped, 1 warning in 4.04s`，真实 PostgreSQL16 与真实 socket；Ruff check/format通过。新提交对应 CI 将重新验证 PostgreSQL17 与全部 headless，推送后检查。

修复提交：[5520d4027ea27939d58d6a9d7e7ead83a6840244](https://github.com/frontend-is-magic/deep-ai-research-assistant/commit/5520d4027ea27939d58d6a9d7e7ead83a6840244)，`fix: 保留真实客户端断开事件并持久化取消审计`；tree 与本地 7292a7cab199847647b0ace79031df99f2c02f1d 一致。[CI 37134705024](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37134705024) completed/success，quality job 111236759854。

实际日志确认 `74 passed, 2 skipped, 1 warning in 5.83s`，新增真实 HTTP 断开回归在 SQLite/PostgreSQL17 两组都执行成功。冻结安装、Ruff、前端格式/类型/构建、13 响应契约、3 固定评测及 45 tracked/worktree/ZIP 敏感检查通过；两种存储 headless 各 6 流程/12 导出、API 重启与 queued 明确执行通过；0191fac 负对照依旧重现，30 隐私延迟回归通过，0 headless 页面错误与0真实模型调用。证据和 HUMAN_ACTIONS 已备妥，main 未修改；生产 Vercel 与原生 Browser 仍交主线验证。

## 追加主线审查：取消确认后的模型轮次竞态

主线独立复现 5520d40：第二 app 确认取消后，原 worker 的 checkpoint 保存 cancelled 却仍返回可继续，导致后两轮 MockTransport 请求在 cancelled 状态下发出，最终 model_calls=3 / usage=33；先前绿色 CI 没覆盖这条精确顺序。这里记录独立审查与云端新回归，不把既有 CI 重新解释为边界通过。

修复：checkpoint_run 将“审计可保存”和“执行可继续”分开；取消/过期可保存本轮迟到的已知 usage/轨迹，但返回停止，ExecutionStopped 直接打断 generate。模型与工具另有 before_operation 数据库门禁，100ms 监测仅负责等待中的请求。取消前已准入/在途调用的收费不能撤回；已返回这一轮的用量保留完整，未返回仍标未知。过期租约的原令牌可做审计补齐，始终保留 interrupted，不能继续/复活；删除后或令牌不匹配不能写回。

新增真实 SQLite/PostgreSQL 跨 app 竞态测试：第一轮 MockTransport 在返回前通过第二 app 确认 cancel（另测租约过期）；第一轮响应正常交付后，provider 请求数/model_calls 恒为 1，工具0，实际 usage=11、用量轨迹保留，终态取消/中断且新 app 查询一致，重复 execute 不再调用。没有真实供应商 HTTP。修正旧 slow mock，使其明确 pending_model_call=true，与“尚未返回用量的在途调用”契约一致；不再把所有取消的完整已知用量强行标未知。

实际本地完整检查：`TEST_DATABASE_URL=postgresql:///research_test uv run --project backend python -m pytest backend tests -q`：78 passed / 2 intentionally skipped / 1 warning，4.57s；两种数据库真实 HTTP 断开与新取消/租约竞态定向 `-k 'real_http_disconnect or confirmed_before_provider_response'`：6 passed，1.67s。3固定评测、Ruff check/format通过。

负对照临时仅恢复 5520d40 的 durable/engine/workspace，运行新 cancel 两组测试：SQLite/PostgreSQL 均2 expected failures，实际 model_calls=3、usage=33；finally 恢复当前文件。负对照不进入真实模型，不提交旧实现。新提交与 CI 结果推送后补记；此前0c8be46的文档CI37134887376成功，但不作为本次取消竞态已验证的证据。

### 取消屏障精确提交与绿色 CI 回执

修复：[3e1da918caa9ebf503b5946e0e421aaf0957e14d](https://github.com/frontend-is-magic/deep-ai-research-assistant/commit/3e1da918caa9ebf503b5946e0e421aaf0957e14d)，`fix: 以数据库取消屏障阻断后续模型和工具调用`；GitHub tree 与本地 91d6f9461518c33775d9d58454ece590083fd715 一致，非强推 develop。

[CI 37135583272](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37135583272) completed/success，quality job 111239333652。实际日志 `78 passed, 2 skipped, 1 warning in 6.81s`：取消 ACK 后第一轮交付、租约过期同语义、真实 socket 断开分别在 SQLite 与 PostgreSQL17 执行；两项 skip 仍是 SQLite 参数组的 PG 专用测试。冻结安装、Ruff、前端格式/类型/构建、13 响应契约、3固定评测、45 tracked/worktree/ZIP敏感检查全通过。SQLite/PostgreSQL headless各6流程/12导出、API重启和queued明确执行通过；0191fac负对照重现，30隐私延迟场景通过，0页面错误、0真实模型调用。

主线精确 3e1da91 独立复验（用户回传，新的 clean public checkout / 冻结依赖，与上述云端 CI 区分）：原取消脚本 cancel ACK 后无新请求，model_calls=1 / tool_calls=0 / usage=11 / usage_complete=true，新读持久化一致；原始 ASGI http.disconnect 与 handler task cancel 保留前一轮usage11、pending第二轮、usage_complete=false和3步trace；五种跨owner操作均404/no-store。主线本地 test_durable 11passed/14skipped，因无本地PG，实际PG依据本次CI；0真实模型调用，未发现新问题。本轮取消审计至此收束。

部署边界更新：主线报告 Vercel 连接器访问既有 bloodymoons-projects 返回403（scope授权不足），已归入既有一次性人工配置聊天，不绕过认证。此权限问题与代码/CI实现区分，HUMAN_ACTIONS更新；实际Vercel平台部署仍未验证，独立只读配置审查由主线进行。

## 固定 Vercel CLI 本地同域预检（恢复交付）

依据当前官方 [Services local development](https://vercel.com/docs/services#local-development) 使用 `vercel dev -L`，保留 services/root/rewrites，不使用旧 experimentalServices。固定 vercel 62.2.0、pnpm 10.32.1 并锁定依赖。`node scripts/preflight_vercel.mjs` 在临时源码/依赖副本、全新空 CLI config 下运行，不登录、关联或部署，不读取原认证缓存；仅保留工具链网络/TLS配置，清空数据库与模型密钥，身份令牌临时随机生成。

已完成实际本地命令：`frontend/node_modules/.bin/pnpm --dir frontend check`（格式、TypeScript、Vite 构建通过）；`node scripts/preflight_vercel.mjs` 最终通过：首页与全部 script 静态资源同域200、FastAPI health200、demo complete且model_calls=0；私人入口401/no-store、真实模式缺访问码401、缺模型配置503、Vercel缺数据库503/no-store。实际输出 `Vercel local PASS: CLI62.2.0 dev -L`，随后 `Vercel local cleanup PASS: 6 owned listening ports released.`。清理仅针对自有进程及已记录监听，逐端口重新绑定验证；无真实模型调用、无远端部署、无 Browser 验收。

前置失败及修正也保留：目录软链接方案被 pnpm 的 UNSAFE_MODULES_DIR 拒绝，改为临时真实副本与固定 pnpm；隔离环境遗漏代理/TLS根导致公开依赖 DNS/UnknownIssuer，改为保留既有代理/证书设置并启用 UV_SYSTEM_CERTS，未禁用 TLS。失败轮次均清理4个自有端口，最终轮次清理6个。CI 增加同一脚本（5分钟步限）；对应提交/CI回执推送后补记。

部署说明与 HUMAN_ACTIONS 明确 Framework Preset 为 Services；[supportsCancellation 当前仅 Node.js](https://vercel.com/docs/functions/functions-api-reference)，Python 云端断开传播另需平台验收。25秒只约束执行循环，初始化/同步数据库/收尾在外，不能视为整个HTTP硬上限。托管数据库、身份 secrets、生产授权/费用预算与实际发布仍未验证，统一交既有人工配置聊天。

### 首次 CI 安装路径修正

精确 [756f8885947cd46f5d6f77d019f6754a5d9781dd](https://github.com/frontend-is-magic/deep-ai-research-assistant/commit/756f8885947cd46f5d6f77d019f6754a5d9781dd) 的 [CI37138314317](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37138314317) 在新增预检失败；其前置后端/格式/冻结安装/13契约/评测已通过，后续 headless 被跳过。日志显示 Vercel 重新创建临时 node_modules，随后从该目录执行的 pnpm worker 退出；失败路径仍成功释放4个监听。改为 PATH 指向原工作区固定 pnpm10.32.1（副本外），Vercel 安装仅改临时项目，避免安装器自身随临时 node_modules 被重建。保留此失败回执，下一提交重新验证。

### 固定 CLI 预检绿色回执

修正精确提交 [f7f674da526cfb4b3eb8ad2e5b51a120123ebbc8](https://github.com/frontend-is-magic/deep-ai-research-assistant/commit/f7f674da526cfb4b3eb8ad2e5b51a120123ebbc8)，[PR CI37138472386](https://github.com/frontend-is-magic/deep-ai-research-assistant/actions/runs/37138472386)，quality job111247763415 completed/success。实际日志：CLI62.2.0同域预检 PASS，6个自有监听释放；78passed/2intentional skipped/1warning（6.61s），冻结安装、前端格式/类型/构建、13响应契约、3固定评测、46文件/ZIP敏感扫描全部通过。SQLite/PostgreSQL headless各6流程/12导出，重启/queued冷启动、旧0191fac隐私负对照及30延迟场景均通过，0页面错误/0真实模型调用。

本地修正后 `node scripts/preflight_vercel.mjs` 也再次 PASS/释放6端口。现有[草稿PR#1](https://github.com/frontend-is-magic/deep-ai-research-assistant/pull/1)更新，develop非强推；远端main核对仍533291b025a53a703384976b2f3605641399a52d。上述结论限本地CLI与CI，不代表已发布Vercel、Python平台断连已验证、原生Browser验收或真实模型/收费验证。人工事项仍集中HUMAN_ACTIONS与既有唯一人工对话。
