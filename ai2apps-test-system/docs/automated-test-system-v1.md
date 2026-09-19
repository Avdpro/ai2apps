# AI2Apps 自动测试系统 V1

## 1. 目标

AI2Apps 自动测试系统（下称 ATS）以固定的 `AI2Apps-test.app` 为发布形态验收对象，覆盖从“不启动 App”的静态检查到完整桌面 UE 流程。一次测试由 Codex 发起后应能无人值守完成，并产出机器可读结果、中文 HTML/Markdown 报告、失败截图、日志和可复现命令。

系统必须支持按优先级、产品区域、测试层和变更影响选择测试范围。优先级表示“本轮必须执行到哪一层”，不等同于缺陷严重度。

V1 的固定测试对象：

- App：`apps/ai2apps-acefox/.build/AI2Apps-test.app`
- Bundle ID：`com.ai2apps.desktop.test`
- Instance：`test`
- 数据：`~/Library/Application Support/AI2Apps/instances/test`
- 缓存：`~/Library/Caches/AI2Apps/instances/test`
- Runtime：与生产一致的 `cloud` Runtime，禁止源码热挂载
- Browser：包内 AceFox，通过受保护的 WebDriver BiDi Gateway 做页面级自动化

`AI2Apps-App-Dev` 只用于快速开发回归，不得替代 Test App 的发布形态验收。生产 `default` 实例永远不属于自动清理、注入或写测试数据的范围。

## 2. 当前产品测试面

ATS 从产品注册表和已安装 Package 动态发现测试面，不维护第二份硬编码产品目录。当前版本至少包含以下区域：

| 区域 | 当前对象 |
| --- | --- |
| 原生壳与 Helper | Launcher、Helper、Updater、实例隔离、Local 启停/恢复、菜单栏状态、签名与 Runtime 清单 |
| 系统 App | Dashboard、Account、Models、Environment、Discover、Trust Center、Settings、Logs、Sharing |
| 主要 App | Chat、Agents、AI Browser、Messager、Gallery、Knowledge、Read Aloud、Video Studio、Imagine Studio、Terminal、Coder、Bench |
| 内置 Mini-Entry | Agent、Chat、Gallery、Knowledge 的 Sidebar/Inline 入口 |
| 重点 Packaged Mini-App | `ai2apps/media-voice-studio-suite` 中的转写、音轨分离、音频换声、视频字幕、视频换声五个组件 |
| Package/Runtime | `.ai2app`、`.ai2service`、`.ai2agent`、Runtime/Model Package 的校验、安装、禁用、升级、回滚和能力供应 |
| Browser | AI Browser Profile、窗口/标签页、BiDi 鉴权、上下文绑定、读取、截图、输入、下载及断线恢复 |

标为 development 的产品面可以进入 P2/P3，但不能阻塞发布，除非本次候选明确把它列为发布功能。

## 3. 测试分层

### L0：静态与契约检查（不启动任何 App）

目标是在几十秒到数分钟内发现语法、导入、契约、资源和打包错误。

- Python：`compileall`、Ruff、关键模块导入、类型检查的增量子集。
- JavaScript：对 `ai2apps/web/static/js` 和 Package Web 资源做语法解析；禁止只用文本搜索代替解析。
- HTML/CSS：模板解析、重复 ID、缺失 label/alt、不可达静态资源、无效 CSS、危险内联脚本与 CSP 冲突。
- JSON/YAML：Package、App、Mini-App、Service、Runtime、SBOM 和 Provisioning Profile 的正式 validator。
- Swift：`swift build`，以及不启动 App 的 Contracts/Supervisor/Updater 单元测试。
- 资源完整性：i18n key、图标、Help、Mini-App Entry、清单 file index、签名 envelope、License/SBOM。
- 发布 Bundle 静态检查：`verify-release-app.sh`、codesign、entitlements、bundle/instance/profile、坏链接、ABI、可变构建残留。
- 安全边界：Test 构建不得出现 Development 标志或源码挂载；凭证、Cookie、Bearer Token 不得进入报告。

### L1：模块与 Helper 测试（不展示主 App UI）

- 运行现有 Python 单元/组件测试和 Swift Tests，统一收集 JUnit。
- Helper 状态机：starting、ready、degraded、failed、restart、adopt、quit。
- 固定端口冲突、过期 descriptor、跨实例 descriptor、进程身份复验、三次健康检查失败自动恢复。
- Launcher/Helper/Local 的单例、重入、崩溃恢复和只终止自己拥有的进程。
- `test`、`app-dev`、`dev`、`default` 四类实例的目录、端口、Profile、Cookie、日志和模型状态隔离。
- Test 专属数据重置：只清理 `test` 的 Support/Cache，保留 Hugging Face 用户缓存和所有其他实例。
- 诊断导出：模式为 `0600`，字段完整，不含日志正文、Prompt、Cookie、Token、用户文件或 actor ID。
- Helper 菜单与四态图标可用 Computer Use 验证，但状态注入应由 Test-only 控制夹具完成。

### L2：Local API、App Host 与 Package 集成

- 用 Test Helper 启动嵌入式 Local，等待已认证 health/bootstrap ready。
- 对 Platform API、数据库迁移、App registry、mount、capability broker、任务/事件流做真实 HTTP/WebSocket 集成。
- 逐一打开系统 App 和主要 App，验证入口、标题、首屏、空态、加载态、错误态、路由和 API 契约。
- 内置 Mini-Entry 验证 mount 生命周期、侧栏/inline placement、AppInstance 归属、关闭/重开和权限。
- Browser 测试必须使用受保护的 WebDriver BiDi Gateway；禁止以自定义 DOM 接口或焦点猜测替代 browsing context 绑定。
- 使用本地固定响应、固定媒体小样和 fake provider 完成功能流程。真实 Cloud、真实大模型与大下载不是 P0/P1 的默认依赖。

### L3：桌面 UE、交互与视觉质量

页面内部交互优先使用 BiDi；macOS 原生窗口、菜单栏 Helper、系统文件选择器、权限弹窗、窗口切换和最终人眼可见状态使用 Computer Use。每个动作后重新读取可访问性树或 BiDi 状态，不复用过期 element index。

每个重要页面至少验证：

- 启动、首次使用、正常、空、加载、错误、离线、窄窗口和大字号状态。
- Dock、Launcher、侧栏、沉浸模式、返回/关闭、键盘导航、焦点环、滚动和窗口缩放。
- 文案不截断、不重叠、不溢出；对齐、间距、层级、颜色、图标、圆角和阴影符合统一设计语言。
- WCAG AA 颜色对比、语义角色、可访问名称、Tab 顺序和键盘可操作性。
- 中英文至少各一轮关键路径；伪本地化用于发现硬编码宽度和漏翻译。
- 截图采用稳定区域掩码后做像素/结构差异；同时由 Codex 视觉审查按固定 rubric 打分。

视觉审查不能只给“好看/不好看”。每条问题必须包含页面、状态、窗口尺寸、截图标注、违反的设计规则、严重度和建议。视觉模型的单次主观判断只产生 review 项；要阻塞发布，必须同时满足确定性规则失败、基线显著回退，或两次独立复核一致。

### L4：真实能力与长程稳定性

- 已发布 Cloud 的只读/低成本 acceptance。
- 指定真实 Local/Cloud 模型的 Chat、图像、音频、视频和 Knowledge 黄金样例。
- Packaged Mini-App 的真实 Runtime/Service/Checkpoint 安装与端到端输出验证。
- 冷启动、热启动、Local/Browser 重启、断网恢复、持续运行、内存/CPU/磁盘增长和泄漏。
- 更新候选、安装后首次启动、回滚和数据迁移。

L4 默认只在 nightly、发布候选或显式请求时运行。涉及付费、对外发布、账号安全验证、永久删除或新的系统权限时必须 fail closed；无人值守并不扩大授权范围。

## 4. 优先级与选择规则

| 优先级 | 目标时长 | 默认层 | 必测内容 | 典型触发 |
| --- | ---: | --- | --- | --- |
| P0 Blocker | 5–10 分钟 | L0 + L1 核心 + L2 smoke | 语法/契约、Helper ready、Test 实例隔离、Shell 首屏、每个发布 App 可打开、核心 Mini-Entry mount、无崩溃 | 每次改动、提交前 |
| P1 Critical | 20–40 分钟 | L0–L3 核心 | P0 + 核心业务 happy path、错误恢复、中英文关键路径、视觉/可访问性冒烟、重点 Packaged Mini-App mock 流程 | 合并前、日常候选 |
| P2 Full | 1–3 小时 | L0–L3 全量 + L4 小样 | 全 App 状态矩阵、所有 Mini-App、Package 生命周期、跨 App 工作流、浏览器、媒体样例、性能预算 | nightly、Beta 候选 |
| P3 Release | 数小时 | 全部 | 干净实例、签名 Bundle、真实依赖、更新/回滚、长稳、完整视觉审查、发布门禁报告 | 正式发布候选 |

执行 `--priority P1` 表示运行所有 P0 和 P1 用例。还应支持：

```text
ai2apps-test run --priority P0
ai2apps-test run --priority P1 --area chat,knowledge,browser
ai2apps-test run --priority P2 --layer ui,visual --locale zh-CN,en-US
ai2apps-test run --changed-from <git-ref>
ai2apps-test run --case package.media-voice.video-subtitles
ai2apps-test resume <run-id>
```

`--changed-from` 只能增加受影响测试，不能移除 P0 固定门禁。选择器可组合 `priority / layer / area / app / package / capability / locale / destructive / network / duration`。

## 5. 编排机制

### 5.1 单一入口

Python 编排器位于 `src/ai2apps_test/`，主入口为 `bin/ai2apps-test`；父仓库的 `scripts/ai2apps-test` 只保留兼容转发。编排器不重新实现 pytest、Swift Test、Bundle verifier、BiDi 或 Computer Use，而是调用并归一化这些执行器。

建议目录：

```text
src/ai2apps_test/
  cli.py
  catalog.py
  planner.py
  runner.py
  state.py
  redact.py
  reporters/
  executors/
    command.py
    pytest.py
    swift.py
    helper.py
    http.py
    bidi.py
    computer_use.py
    visual.py
  schemas/
../tests/ats/
  catalog/
    gates.yaml
    system-apps.yaml
    main-apps.yaml
    builtin-mini-apps.yaml
    packaged-mini-apps.yaml
  scenarios/
  fixtures/
  baselines/
artifacts/runs/<run-id>/
```

### 5.2 Catalog 与场景

每个用例有稳定 ID，并声明：

```yaml
id: package.media-voice.video-subtitles.happy-path
priority: P1
layer: ui
areas: [video-studio, packaged-mini-app]
requires: [test-app, local, fake-media-provider]
state: clean
locale: [zh-CN, en-US]
steps:
  - open_app: ai2apps.video-studio
  - mount_mini_app: ai2apps.media-voice.video-subtitles
  - upload_fixture: fixtures/video/short-dialogue.mp4
  - invoke: media.video_subtitles
  - assert_artifact: {kind: video, probe: playable}
  - assert_visual: video-subtitles-result
cleanup: restore-snapshot
```

场景 DSL 只描述产品意图。执行器决定用 HTTP、BiDi 还是 Computer Use 完成动作；报告同时记录高层步骤和实际底层动作。禁止把坐标作为主要定位方式。可访问名称、稳定 test ID、App/Mini-App ID、mount ID 和 BiDi context ID 是首选定位符。

### 5.3 状态与隔离

每次运行采用以下生命周期：

1. 校验 App 路径、bundle ID、instance ID、Build、签名、Runtime Profile 和 Test-only reset capability。
2. 确认所有将被停止或清理的进程、目录都属于 `test`；发现不明确对象立即停止。
3. 保存 Test 实例的可恢复快照，记录快照哈希和当前 Build；绝不读取或复制其他实例状态。
4. 需要 Cloud 身份的用例按 Run 原子租用一个固定测试账号；Cloud 清除旧绑定、轮换密码并临时启用，Harness 通过 Test Local 登录，Secret 只进入 Keychain。
5. 通过受签名 Test-only 控制入口重置或载入命名 fixture。正式 Helper 的人工“重置数据…”仍保留确认 UI。
6. 启动 Helper/Local/Shell，按状态契约等待，不使用固定 sleep。
7. 运行计划；每个用例有独立超时、重试策略、污染标记和取证钩子。
8. 收集证据并执行幂等 cleanup；失败时保留现场副本，下一用例仍从已知状态开始。
9. 结束时先注销 Test Local Session，再让 Cloud 撤销设备、轮换密码并禁用账号；最后恢复测试前快照。Cloud TTL 必须兜底回收崩溃 Run。

需要为自动化增加一个仅 Test Bundle 可用的本地控制工具，例如：

```text
ai2apps-test-control --bundle-id com.ai2apps.desktop.test \
  --instance test reset --confirm-instance test
```

该工具必须校验签名 capability、App 绝对路径、bundle/instance 双重身份和目标目录 realpath；它不能接受 `default`、通配符、任意路径或远程请求。

### 5.4 确定性与重试

- 用例自己声明是否允许重试；语法、契约、安全和数据一致性失败不重试。
- UI 仅可对明确的瞬时等待失败重试一次，第二次运行使用全新状态并保留两次证据。
- 时间、随机数、网络返回、模型输出和媒体样例尽量固定。
- AI 输出用结构、工具调用、引用、拒绝策略和语义评分判断，不对完整自然语言做逐字比较。
- 任何 skip 都必须有机器可读原因。P0/P1 的 required 用例被 skip 等同失败。

## 6. 各产品面的最低用例合同

### 系统与主 App

每个发布 App 必须自动生成一组共同合同：注册可发现、可启动、首屏 ready、无控制台未处理异常、主导航可操作、刷新恢复、关闭重开、权限失败可理解、空/错/加载状态合格、中文/英文无截断、键盘可达。

在共同合同之上增加领域流程：

- Chat：选模型、发送、流式输出、停止、重试、历史、新会话、附件、Knowledge 开关、Agent 模式。
- Knowledge：建库、导入文本/文件/网页、检索、引用、删除恢复、Sidebar 当前页上下文。
- Discover/Models：分类、分页、详情、校验、安装计划、进度、失败重试、禁用/升级/回滚。
- AI Browser：Profile、受保护 BiDi、标签页、页面读取/截图/输入、下载、断线重连和 context 绑定。
- Gallery：各媒体类型、预览、来源、导入/导出、跨 Studio 回流。
- Read Aloud / Video / Imagine：能力探测、ACPF、Mini-App mount、任务状态、产物预览与 Gallery 落库。
- Agents/Coder/Terminal：创建、编辑、运行、停止、日志、失败恢复、文件/工具权限边界。
- Account/Trust/Settings/Logs：未登录与已登录投影、权限/Secret、Safe Mode、设置持久化、日志脱敏。

### 内置 Mini-Entry

每个内置 Mini-Entry 必须验证：正确 AppInstance、placement、mount token、打开/关闭/切换、与主 App 状态同步、窄侧栏布局、权限收敛、错误隔离。Chat/Knowledge 浏览器上下文测试要以显式 BiDi context ID 为证据。

### Packaged Mini-App

Package 既作为一个原子发布单元测试，也逐个测试组件工作流：

1. source contract 与开发挂载回归；
2. 确定性构建、file index、签名、SBOM 和 catalog projection；
3. 干净 Test 实例安装；
4. 各声明 Studio 中可发现并可 mount；
5. sandbox/CSP、mount-bound broker、未声明 capability 拒绝；
6. unmet dependency、ACPF、重启续接、失败重试；
7. mock provider 的 P1 流程和真实 provider 的 P2/P3 流程；
8. disable、upgrade、rollback、remove 后 catalog 与打开页面的一致性；
9. Package 间 ID 冲突和内置 ID 保留规则。

首个重点套件的五个组件都必须有短小、可分发、无隐私数据的黄金媒体 fixture，并对输出做格式级和内容级探测，而不是只检查 HTTP 200 或文件存在。

## 7. UE 与视觉评分

每张基线由 `app + route + state + locale + viewport + appearance + build` 唯一标识。默认桌面矩阵：

- 1440×900 标准窗口；
- 1100×720 最小支持窗口；
- 1440×900 + 200% 文本缩放；
- light appearance；dark appearance 在 P2 起执行。

视觉 rubric 总分 100：

| 维度 | 分值 | 自动证据 |
| --- | ---: | --- |
| 布局与响应式 | 25 | 溢出/遮挡检测、关键框位置、截图 |
| 视觉一致性 | 20 | token、组件、图标、间距、圆角 |
| 信息层级与可读性 | 20 | 字号、对比度、密度、空态/错误态 |
| 交互反馈 | 15 | hover/focus/pressed/loading/success/error |
| 可访问性 | 15 | AX tree、名称/角色、Tab 顺序、对比度 |
| 完成度 | 5 | 占位符、调试文案、破图、未翻译文本 |

P1 核心页低于 85、任一维度低于 60%，或出现遮挡主操作/不可读文字/键盘死路，均失败。纯像素 diff 不直接判失败；动态区域先遮罩，结构性差异再进入 Codex 复核。

## 8. 无人值守规则

运行前做一次 preflight，把所有不可无人值守的条件一次性列出。通过后，执行期间无需用户介入。

- 测试账号、fake provider、固定 fixture 和预授权测试权限由命名 Profile 提供；Secret 只从 Keychain/环境句柄读取，禁止进入场景 YAML、命令行和报告。
- CAPTCHA、管理员密码、Apple 公证、购买/付费、外部发布、生产数据写入不属于自动回归路径。
- 系统权限必须在专用 Test 机器预置；若出现未预期授权弹窗，截屏并以 `environment_blocked` 失败，不擅自扩大权限。
- Cloud 不可用时，依赖 Cloud 的 P2/P3 用例可以按策略标为 blocked；本地 P0/P1 仍继续执行并单独给出结论。
- 测试只写 `test` 实例、临时目录和 run artifacts。任何目标身份不明确时 fail closed。

## 9. 报告与证据

每次运行产出：

```text
artifacts/runs/<run-id>/
  plan.json
  environment.json
  result.json
  report.html
  report.md
  junit.xml
  timeline.jsonl
  commands/
  logs/
  screenshots/
  visual-diffs/
  diagnostics/
```

报告首页必须回答：

- 测了哪个 Git revision、哪个 Test App Build、哪个 Runtime/AceFox/Package 版本；
- 选择了什么优先级和范围，哪些没有测试及原因；
- 发布门禁结论：PASS / FAIL / BLOCKED；
- P0–P3、产品区域和测试层的通过率、耗时与 flaky 情况；
- 缺陷按 S0–S3 严重度排序，并附最短复现步骤和证据链接；
- 与上一成功基线相比新增、修复、复发和性能/视觉回退；
- Test 实例最终是否已恢复，以及是否残留进程、mount、Package 或临时文件。

缺陷严重度独立于测试优先级：S0 为安全/数据破坏/无法启动，S1 为核心流程不可用，S2 为有绕行的功能或显著 UE 问题，S3 为轻微视觉/文案问题。

`result.json` 是门禁事实源；HTML/Markdown 由它生成。日志和 DOM/AX dump 在写盘前统一脱敏，Bearer、Authorization、Cookie、路径中的用户名、Prompt 和用户文件内容均不得进入报告。

## 10. 发布门禁

- P0：零失败、零 required skip、零新 flaky；否则禁止继续候选流程。
- P1：P0 全绿，核心业务和核心视觉全绿；允许明确豁免的非发布 development 功能失败。
- P2：所有发布功能全绿；性能和视觉无超过预算的回退；Package 生命周期完整。
- P3：P2 全绿，加签名发布形态、真实能力、更新/回滚和长稳通过。
- BLOCKED 不能解释为 PASS。报告必须区分产品缺陷、测试缺陷、环境缺陷和外部依赖故障。

豁免必须包含 owner、原因、适用 Build 范围和失效日期；不能在运行时临时把失败改成 skip。

## 11. 实施顺序

以下 Phase 是工程建设顺序，不是最终测试范围。ATS 第一个正式可用版本必须能选择
P0–P3、完整登记当前全部发布测试面，并明确显示尚未实现的用例；未实现、未分类或
缺少证据的 required 用例不能被计为 PASS。开发过程中可以先让 P0 可执行，但不能把
“只有 P0”称为完整 ATS 交付。

### Phase A：可执行骨架

建立 CLI、catalog、run directory、JUnit/JSON/HTML 汇总和脱敏；接入现有 pytest、Swift Test、`verify-release-app.sh`。完成 P0 的静态、Helper ready、Shell 首屏和 App 可打开测试。

### Phase B：Test 控制与确定性集成

实现受签名 Test-only reset/snapshot/fixture 控制；接入真实 Local API、fake providers、App/Mini-Entry 共同合同，并让每个用例可独立重放。

### Phase C：BiDi + Computer Use UE

完成页面场景执行器、macOS Computer Use 执行器、截图/AX/console/network 取证、中文/英文和窗口矩阵。先覆盖 Chat、Discover、Knowledge、AI Browser、Read Aloud、Video Studio、Imagine Studio。

### Phase D：Packaged Mini-App 与 Release Gate

覆盖签名安装、能力供应、五个媒体工作流、升级/回滚，增加真实模型小样、性能预算、长稳、候选更新和趋势报告。

## 12. V1 验收标准

V1 完成需同时满足：

- 一条命令可选 P0/P1/P2/P3 并生成确定的执行计划；
- P0 可在无人介入下从静态检查运行到 Test App Shell/App/Mini-Entry smoke；
- P1 覆盖核心 App、四个内置 Mini-Entry 和五个重点 Packaged Mini-App mock happy path；
- 所有 UI 失败自动保存截图、AX/BiDi 状态、console/network 摘要和复现步骤；
- 报告可明确给出候选是否可进入下一阶段，而不要求人工翻日志；
- 自动化无法触碰生产实例或未声明目录，报告中不含 Secret/用户数据；
- 同一 Build、同一 fixture 连续运行三次，无产品变化时不得产生不一致门禁结论。

## 13. Phase A 的具体命令与 Codex 接入

### 13.1 命令行含义

仓库内首先提供无需安装的固定入口：

```shell
cd /Users/avdpropang/sdk/omlx-moe-cache
./bin/ai2apps-test run --priority P0
```

`ai2apps-test run --priority P0` 是安装到 PATH 后的等价短命令。Phase A 不要求用户先全局安装，因此文档、CI 和 Codex 默认使用带 `./scripts/` 的仓库入口。

建议同时提供以下子命令：

```text
./bin/ai2apps-test doctor
./bin/ai2apps-test plan --priority P0 --format json
./bin/ai2apps-test run --priority P0 [--driver codex|terminal]
./bin/ai2apps-test next --run <run-id> --format json
./bin/ai2apps-test record --run <run-id> --result <result-fragment.json>
./bin/ai2apps-test finalize --run <run-id>
./bin/ai2apps-test report --run <run-id> --open
```

- `doctor`：只检查依赖、Test App 身份、权限和环境，不运行测试。
- `plan`：展开最终用例，不改变系统状态；Codex 和人都能预览。
- `run`：创建 run、执行所有普通脚本步骤，并在需要 Codex 时写出 agent job。
- `next`：返回下一个待执行的 Codex/UI job，输出稳定 JSON；无任务时返回 `done`。
- `record`：写入一个由 Codex 完成的步骤结果和证据路径。
- `finalize`：校验用例完整性、清理 Test 实例并生成报告。
- `report`：重新生成或打开既有报告，不重新测试。

CLI 退出码固定为：`0=PASS`、`1=FAIL`、`2=BLOCKED`、`3=HARNESS_ERROR`。不能把 BLOCKED 或缺失的 Codex job 当作通过。

### 13.2 Phase A 的 P0 实际流水线

```text
doctor
  -> 创建 run / 固化环境与执行计划
  -> L0 Python、JS、HTML/CSS、JSON/YAML 契约检查
  -> Swift build/test 与精选 Python P0 tests
  -> verify-release-app.sh 静态验证 AI2Apps-test.app
  -> 校验 test/default/app-dev/dev 实例边界
  -> 启动准确路径的 AI2Apps-test.app
  -> 等待 Helper/Local ready（状态轮询，不使用固定 sleep）
  -> Local API 与 Shell bootstrap smoke
  -> Codex + Computer Use 验证原生窗口与 P0 App/Mini-Entry 首屏
  -> 收集证据、清理、finalize
  -> result.json + report.html + report.md + junit.xml
```

Phase A 接入现有测试，而不是立即把 3652 个测试全部放进 P0。首批 P0 Python 集合应覆盖 `client_bootstrap`、`helper_control`、`shell`、`platform_schema`、`security_boundaries`、`package_contract_v1` 和 Test App icon/identity；其他现有测试在 catalog 中逐步归入 P1/P2。

### 13.3 两种 driver 模式

`--driver codex` 是完整 P0 的标准模式。选择器和 `--unattended` 模式由 Harness 自动启动一个受限的 Codex CLI 子进程：

1. Harness 执行 `doctor`、固化 plan，并完成确定性脚本、pytest、Swift、Helper/API 和账号预检。
2. CLI 遇到原生 UI/视觉步骤时启动 `codex exec`，其权限固定为 `workspace-write`、无交互式提权，并只将 Run ID 和稳定规程放入 stdin。
3. Codex 循环调用 `next`：Shell、App/Mini-Entry 启动和原生/可见 UI 使用 Computer Use；只有明确的 AI Browser 网页 Case 在 Harness 提供并验证 Test-bound Gateway/context 后使用 BiDi；随后截图并生成结构化结果。
4. Codex 用 `record` 交回结果；CLI 校验 case ID、证据存在性和结果 schema。
5. 所有 job 完成后由父 Harness 执行 `finalize`、释放账号并生成最终报告。
6. Codex 无法启动或提前退出时，Run 保持 `awaiting_agent`，Test Center 显示可复制的精确接管指令，不得把缺失工作算作完成。

`--driver terminal` 适合开发者直接在终端运行。它完成所有脚本/API/BiDi 步骤；若计划包含 Computer Use job，则最终状态为 BLOCKED，并提示改用 Codex，而不是跳过后返回成功。

### 13.4 Codex companion skill

Codex Skill 位于本项目 `.agents/skills/ai2apps-test/SKILL.md`。它只保存稳定操作规程，不保存具体测试答案：

- 总是先运行 `doctor` 和 `plan`；
- 只允许目标 bundle `com.ai2apps.desktop.test`、instance `test` 和固定 App 绝对路径；
- 特权 Shell chrome 不是 BiDi browsing context，Shell 导航、App/Mini-Entry 启动和可见 UI 使用 Computer Use；
- 仅明确的 AI Browser 网页 Case 可使用 Harness 提供并验证的 Test-bound BiDi Gateway/context，禁止用通用浏览器 BiDi 连接代替 Test Shell；
- 每次 UI 动作后重新读取界面状态；
- 如何消费 `next` JSON、保存截图、构造 result fragment 和调用 `record`；
- 遇到权限、账号、外部付费、生产写入或身份不明时记录 BLOCKED；
- 完成或失败后都必须执行安全的 `finalize` 并汇报报告路径。

这样用户以后只需在 Codex 中说：

```text
对当前 AI2Apps-test 执行 P0 自动测试，完成后给我报告。
```

Codex 会通过 companion skill 知道如何调用 CLI 和 Computer Use。CLI 仍然可以独立被 CI、终端或未来其他 agent 调用，测试事实不会依赖某次聊天上下文。

### 13.5 Phase A 最小文件清单

```text
bin/ai2apps-test
src/ai2apps_test/__init__.py
src/ai2apps_test/cli.py
src/ai2apps_test/catalog.py
src/ai2apps_test/runner.py
src/ai2apps_test/state.py
src/ai2apps_test/redact.py
src/ai2apps_test/reporters/json_report.py
src/ai2apps_test/reporters/html_report.py
src/ai2apps_test/executors/command.py
src/ai2apps_test/executors/pytest.py
src/ai2apps_test/executors/swift.py
src/ai2apps_test/executors/helper.py
src/ai2apps_test/executors/http.py
../tests/ats/catalog/p0.yaml
../tests/ats/schemas/case.schema.json
../tests/ats/schemas/result.schema.json
.agents/skills/ai2apps-test/SKILL.md
```

Phase A 的 UI 执行器不需要把 Computer Use SDK嵌入产品代码；UI 动作由运行该任务的 Codex 工具完成，CLI 仅通过 `next/record` 交换结构化 job 和结果。到 Phase C 再增加更完整的 BiDi 场景、视觉基线和多窗口矩阵。

## 14. 产品升级与测试面自动演进

### 14.1 三层测试目录

ATS 的 catalog 不是一张人工维护的 App 名单，而是由三层合并生成：

1. **运行时发现层**：读取系统 App registry、内置 Mini-Entry、路由、Capability Profile、已安装的签名 Package/App/Mini-App/Service/Runtime 清单。
2. **通用合同层**：根据组件类型自动生成共同测试。例如任何发布 App 自动获得注册、打开、首屏、错误、刷新、关闭重开、console、i18n、键盘和视觉 smoke；任何 Mini-App 自动获得 discover、mount、placement、sandbox、capability 和 lifecycle 合同。
3. **功能场景层**：第一方功能在源码旁声明自己的 happy path、边界、真实能力和发布场景，补充通用合同无法推导的产品语义。

因此新增一个 App 后，即使没有手工修改中央目录，它也会立刻进入 inventory，并至少被通用合同覆盖。缺少功能场景时，覆盖门禁报告 `unclassified_component` 或 `missing_required_scenario`，不能静默漏测。

### 14.2 Inventory Lock 与覆盖门禁

每次 `plan` 都生成实际 inventory，并与仓库中的已审阅快照比较：

```text
../tests/ats/inventory.lock.json
```

快照只保存稳定产品身份和测试分类，不复制业务 manifest。每个发布组件至少记录：

```json
{
  "id": "ai2apps.video-studio",
  "kind": "app",
  "releaseStatus": "shipping",
  "owner": "media",
  "introduced": "0.1.0",
  "requiredPriorities": ["P0", "P1", "P2", "P3"],
  "scenarioProfile": "video-studio"
}
```

发现以下变化时，P0 的 `coverage.inventory` 用例直接失败：

- 新 App/Mini-App/Package/Service/Runtime/Capability/公开路由没有分类；
- shipping 组件没有 P0/P1 场景，或发布候选没有要求的 P2/P3 场景；
- manifest 声明的 Entry、placement、permission、capability 或 lifecycle 已变，但场景仍绑定旧合同；
- 组件删除后仍有孤立场景、基线或 fixture；
- 用 skip、空场景或无断言步骤冒充覆盖。

`inventory.lock.json` 的变化必须与功能代码和测试场景在同一变更中审阅。更新 lock 只能承认产品面变化，不能自动豁免缺失测试。

### 14.3 新功能的 Definition of Done

每个第一方新增功能必须在同一变更中完成：

- 声明稳定组件/能力/路由 ID 和 release status；
- 自动生成的 P0 common contract 可通过；
- 至少一个 P1 happy path 和一个失败恢复场景；
- P2 状态矩阵、跨 App/Package 影响、i18n、可访问性和视觉基线；
- P3 是否需要真实模型、真实 Cloud、升级迁移、性能或长稳测试的明确分类；
- fixture、敏感数据策略、cleanup 和报告断言；
- 更新 inventory lock，并证明没有降低既有覆盖。

纯 development 功能也必须登记，但可将 P2/P3 标为非发布门禁；一旦状态改为 shipping，计划编译器自动提高 required gate，缺失测试立即失败。

### 14.4 P0–P3 的累积关系

P0–P3 是同一个 catalog 的四个累积视图，不是四套互相漂移的工程：

```text
P0 = 所有发布面的生存、安全与覆盖门禁
P1 = P0 + 所有核心 happy path、恢复、基础 UE
P2 = P1 + 全状态矩阵、跨组件、全视觉/语言/可访问性
P3 = P2 + 真实依赖、迁移、更新/回滚、性能与长稳
```

运行 P3 必然包含 P0、P1 和 P2。新增 shipping App 不允许只增加 P3 用例而绕过低层门禁，也不允许只通过通用“页面能打开”测试而没有产品功能场景。

### 14.5 版本和基线演进

- 用例 ID 保持稳定；行为改变时更新断言并记录 `contractVersion`，而不是随意新建近似重复用例。
- 数据迁移、Package 升级和回滚场景保留至少“上一发布版 -> 当前候选”的路径。
- 视觉基线按 App/状态/语言/窗口/appearance 版本化；必须通过显式 baseline review 更新，测试运行不能自行接受新截图。
- 删除功能时同时验证旧数据、旧 deep link、旧 Package 或旧设置得到可解释的迁移/退役行为。
- 每份报告记录 inventory digest、catalog digest 和 baseline digest，确保以后能重现“当时到底测了什么”。

### 14.6 建议的产品声明方式

内置 App 和 Mini-Entry 继续以现有系统 registry 为产品事实源；Package 继续以签名 `ai2apps.json`、`app.yaml` 和 Service/Runtime manifest 为事实源。测试元数据放在源码旁的 `tests/acceptance.yaml` 或仓库 `../tests/ats/profiles/<id>.yaml`，不向生产 manifest 塞入仅测试使用的步骤。

第三方 Package 没有第一方 acceptance 文件时，仍自动执行完整通用合同、安全边界和 manifest 驱动的能力测试；其自定义业务语义不作为 AI2Apps Desktop 自身的发布门禁，除非该 Package 被列为重点/捆绑/官方发布组件。

## 15. 测试计划选择器

### 15.1 默认启动体验

面向用户启动 ATS 时，默认先打开独立的本地 **AI2Apps Test Center**，展示本次实际发现的测试面和测试项目，不立即执行：

```shell
./bin/ai2apps-test
```

等价显式命令为：

```shell
./bin/ai2apps-test select --priority P1
```

选择器不是 AI2Apps 产品内置 App，也不运行在被测 Test App 中；它属于测试 Harness，避免测试控制面和被测产品互相污染。它仅监听随机 loopback 端口并使用单次 run token。开始后同一页面转为进度控制面；测试结束、测试被中止或开始前取消后关闭服务。

自动化调用保持非交互：

```shell
./bin/ai2apps-test run --priority P0 --driver codex --unattended
./bin/ai2apps-test run --plan ../tests/ats/plans/release-full.yaml --driver codex --unattended
```

### 15.2 分组与三态复选框

选择器按实际 inventory 动态生成树，而不是硬编码当前 App 名称。建议顶层分组：

```text
本次测试
├── 基础门禁与静态检查
├── 原生 Shell / Helper / Launcher / Updater
├── 系统 App
├── 主要 App
├── 内置 Mini-Entry
├── Packaged App
│   ├── Package 生命周期
│   └── Package 中的 Mini-App
├── Runtime / Service / Model Package
├── AI Browser / WebDriver BiDi
├── 跨 App 工作流
├── UE / 视觉 / 多语言 / 可访问性
└── 真实能力 / Cloud / 性能 / 长稳
```

每个分组和叶子项目都有复选框：

- 勾选组：选择组内全部可选项目；
- 取消组：取消组内全部项目；
- 只选择部分子项：父组显示半选状态；
- 展开 App：显示 common contract、功能场景、错误恢复、视觉和各语言子项目；
- 展开 Package：显示签名/安装/升级/回滚，以及它贡献的每个 Mini-App；
- 支持搜索、仅看选中、仅看变更影响、仅看失败历史和按 P0–P3 过滤。

每一项显示：稳定 ID、P0–P3 badge、预计耗时、执行器、依赖、是否需要网络/真实模型/数据重置、上次结果和本次变更影响。新发现但未分类的组件用醒目状态显示，不能被默认隐藏。

### 15.3 优先级预设与手工选择

页面顶部提供：

- `P0 快速门禁`
- `P1 核心回归`
- `P2 全量产品`
- `P3 发布候选`
- `仅测试本次变更`
- `自定义`

选择 P2 会累积选择 P0、P1、P2；选择 P3 会累积选择全部四级。用户手工修改预设后，模式显示为“自定义（基于 P2）”，并持续显示已选用例数、预计耗时和未选范围。

依赖项采用以下规则：

- 选择功能场景时自动选择它依赖的静态、安全、启动、fixture 和 common contract；
- 取消被依赖项目时，界面要求同时取消所有下游场景，或恢复该依赖；
- 不允许生成依赖不闭合的执行计划；
- 可以取消任何测试组，但取消 required gate 后，本次结果只能是 `SCOPED_PASS`、`FAIL` 或 `BLOCKED`，不能是完整 `PASS`；
- P3 发布判定必须选择全部 shipping 组件的 required P0–P3 用例。

### 15.4 启动前确认页

选择完成后显示一次摘要：

```text
目标：AI2Apps-test Build 2195 / instance test
范围：P1 自定义
已选：286 项（P0 74、P1 212）
未选：视觉深色模式、真实 Cloud、长稳等 418 项
预计：31 分钟
需要：启动 Test App、重置 test 实例、网络否、真实模型否
结论能力：SCOPED_PASS（Discover 组已被取消）
```

用户可以选择“开始测试”“返回修改”“保存为命名计划”或“取消”。一旦开始，最终选择被写成：

```text
artifacts/runs/<run-id>/selection.json
```

其中保存 inventory/catalog/baseline digest、每个选中和排除的 case ID、排除原因、依赖展开结果和预计耗时。运行期间不能静默改变选择；产品动态变化导致计划失效时必须重新编译计划并报告 BLOCKED。

### 15.5 与 Codex 的交互

在 Codex 中可以说：

```text
打开 AI2Apps 测试选择器，我选择完后自动开始并给我报告。
```

Codex 的流程：

1. 执行 `doctor`，再启动 `select` 的 loopback Test Center；
2. 将选择器显示在 Codex 面板或浏览器中；
3. 等待用户在选择器中点击“开始测试”；
4. `select` 固化选择并立即输出 run ID，同时保持进度控制面运行；
5. CLI 执行确定性/API/BiDi 用例，并自动启动受限 Codex 子进程消费 Computer Use jobs；
6. 父 Harness 无论 Case 成功或失败都继续到 finalize，并展示详细报告；若 Codex 启动失败则保留 Run 和手工接管指令。

“开始测试”是本轮唯一必要的人机交互。开始后，如果没有出现权限、账号、安全或外部依赖阻断，整轮运行不再询问用户。

用户也可以直接说：

```text
按 P2 全量计划测试 AI2Apps，不用再让我选择。
```

此时 Codex 使用 `--priority P2 --unattended`，不打开选择器。保存的命名计划可以由人、Codex、CI 和 nightly 共用，但每次仍需对当前 inventory 重新解析，保证新 App 不会因为使用旧计划而漏测。

### 15.6 页面运行状态

用户点击开始后，Test Center 切换为实时进度页：显示当前组/用例、通过/失败/阻断/跳过/待执行数量、完成百分比、分组明细和报告位置。“当前发现的问题”面板实时列出失败或阻断 Case、所属组、错误摘要、输出尾部及证据位置。普通 Case 失败、超时、依赖阻断或执行器异常只结束当前 Case，默认继续独立 Case；只有状态无法读取/持久化等 Harness 基础设施错误才终止整轮。用户可点击“中止测试”；Harness 只终止本轮启动的精确子进程组，当前及未开始 Case 标为 `skipped`，生成 `CANCELLED` 部分报告。关闭页面本身不终止测试。

停止操作只停止测试 Harness 自己启动且身份复验通过的 `test` 进程；随后仍执行证据收集和安全 cleanup。停止后的结论为 BLOCKED，不删除已完成结果。

## 16. 复杂鼠标、拖放与时间轴测试

### 16.1 执行器选择

复杂交互属于正式 UE 测试面，不能只用 API 修改结果后检查页面。按交互边界选择执行器：

- 同一 HTML/WebView 内的拖动、排序、缩放、框选和时间轴操作，优先使用 WebDriver BiDi `input.performActions` 的真实 pointer 序列；
- 跨 browsing context 时，由 BiDi 读取各 context/iframe 的当前几何位置，再在顶层坐标系执行 pointer actions；
- Gallery 到另一个原生窗口/WebView、系统文件区或依赖 macOS dragboard 的拖放，使用 Computer Use 的真实鼠标 drag；
- 原生菜单、窗口、系统 picker 和浏览器外目标始终使用 Computer Use；
- DOM/AX 均无法定位的 Canvas 区域可以使用截图视觉锚点，但此类用例标记较低稳定性，并推动产品补充可访问语义和稳定几何锚点。

禁止为了让测试通过而直接调用产品内部 reducer、伪造最终数据库状态或注入 `drop` 事件。BiDi `script.evaluate` 可以读取 DOM、bounding box 和可见状态，但用户交互结果必须由真实 pointer/keyboard 输入产生。

### 16.2 拖拽动作合同

每次拖拽不是简单的固定坐标录制，而是运行时解析：

1. 读取当前窗口、滚动、缩放、目标 App 和 browsing context；
2. 用稳定 ID、可访问名称或语义角色找到源对象和目标；
3. 读取最新 bounding box、可见区域、时间轴比例和合法 drop zone；
4. 在源对象安全中心或指定 handle 执行 pointer down；
5. 按声明的轨迹分段移动，必要时经过进入目标、自动滚动或 hover 展开阶段；
6. 到达容差区后 pointer up；
7. 重新读取 UI 和产品状态，验证操作结果；
8. 保存拖前、拖中关键帧、拖后截图和输入轨迹。

场景可以表达：

```yaml
- drag:
    source: {app: ai2apps.gallery, item: fixture.image.landscape-01}
    target:
      app: ai2apps.video-studio
      component: video-composer
      slot: overlay-input
    executor: auto
    path: natural
    assert:
      assetImported: fixture.image.landscape-01
      targetHighlightedDuringDrag: true
      previewVisible: true
```

`executor: auto` 由计划编译器根据 context 边界选择 BiDi 或 Computer Use，并在报告中记录实际选择。

### 16.3 Video Composer 时间轴矩阵

Clip 时间轴至少测试：

- 从 Gallery/Asset Browser 拖入空轨道和指定素材槽；
- 拖到非法区域时拒绝并保持原状态；
- 同轨移动到精确时间；
- 跨轨移动；
- 与相邻 Clip 交换、吸附、覆盖或插入行为；
- 拖动左右 trim handle；
- 改变 Clip 长度后的音画/字幕关联；
- 多选、组移动、复制拖动和取消拖动；
- 时间轴缩放、水平滚动后继续拖动；
- 拖到视口边缘触发自动滚动；
- Undo/Redo 恢复正确；
- 保存、关闭、重开后位置不变；
- 窄窗口、高 DPI、不同语言下 hit target 仍可用。

精确时间位置不能靠截图主观判断。测试从当前时间轴 ruler/model 取得像素到时间的映射，例如把 Clip 从 `1.0s` 移到 `4.5s`，拖后同时断言项目模型的 `start=4.5`、UI bounding box 在允许误差内，以及预览/导出时间关系正确。

### 16.4 三重断言

复杂拖拽至少有三类证据中的两类，核心时间轴操作必须三类都有：

1. **交互证据**：drag started、目标高亮、pointer up、无意外 dialog/console error；
2. **语义状态**：项目/时间轴模型、API 或持久化数据反映正确 asset、track、start、duration、order；
3. **视觉结果**：Clip/缩略图位于预期区域，无重叠、裁切、漂移，关键帧截图通过结构检查。

对最终媒体流程再增加输出探测：生成的视频可解码、时长合理、关键帧/音轨/字幕与时间轴一致。仅出现缩略图或仅返回 HTTP 200 不算通过。

### 16.5 稳定性要求

- 测试窗口大小、display scale、App zoom、时间轴 zoom、语言和 fixture 必须固定并记录；
- 每次拖动前重新读取位置，禁止保存跨运行绝对坐标；
- 目标最小 hit area 和允许误差由组件合同声明；
- 动画结束、autosave 完成和模型 revision 更新使用状态等待，不使用固定 sleep；
- 瞬时 pointer/渲染问题最多从干净状态重试一次，两次轨迹和证据全部保留；
- 测试期间检测到用户鼠标/键盘介入时暂停该 UI case，避免把竞争输入判为产品缺陷；
- 复杂交互应在专用 Test App 窗口和固定 Desktop 环境运行。

### 16.6 产品可测试性要求

Video Composer、Gallery 和其他可拖拽组件应提供正常产品可访问性，而不是测试后门：

- 稳定的 DOM/test identity 或 AX identifier；
- draggable、drop target、track、Clip、trim handle 的语义角色和可访问名称；
- 可读取的当前选择、时间、轨道、duration 和 drop effect；
- 键盘等价操作，用于可访问性和拖拽失败时的独立产品能力验证；
- 动画/保存/渲染完成的确定状态信号。

若只能依靠截图猜测一个无语义 Canvas 的像素，Codex仍可尝试 Computer Use 拖拽，但不应把这种脆弱用例作为唯一发布门禁。ATS 应报告 `testability_gap`，直到组件提供稳定锚点和可验证状态。
