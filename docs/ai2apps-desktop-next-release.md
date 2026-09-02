# AI2Apps Desktop 下一版 Release 台账

状态：滚动维护中的唯一下一版入口

当前生产基线：AI2Apps `0.1.0` Build `2249`

生产清单：`https://coder.ai2apps.com/updates/stable.json`

基线回执：`docs/ai2apps-desktop-build-2249-release-receipt-2026-09-03.md`

候选 Build：尚未分配；构建时必须严格大于 `2249`

## 1. 用途

本文件只记录“当前生产 Release 之后，已经完成或正在进行、需要评估是否进入下一版
Desktop App 的工作”。它不是长期 Roadmap，也不代替 Git、测试报告或最终 Build 回执。

AI2Apps 经常从混合工作区构建，`git diff` 无法可靠回答某项工作是否已经进入上一版。
因此每项可能改变 Desktop 用户收到的 App、内嵌 Local、Helper、Shell、AceFox、更新器、
Runtime profile、安装行为或发布流程的工作，都必须在完成该项工作的同一轮登记到这里。

登记是默认自动动作，不需要用户另行说“加入台账”。执行开发工作的 Agent 必须在结束当轮
工作前创建或更新相应条目；即使功能尚未完成或被外部条件阻塞，也应分别以
`in_progress` 或 `blocked` 记录。只有未产生任何可发行改动的纯调查、讨论和诊断可以不登记。

## 2. 状态定义

| 状态 | 含义 |
| --- | --- |
| `in_progress` | 实现或验证尚未完成，不能进入 Release |
| `blocked` | 实现已基本完成，但存在明确的外部依赖或验收阻塞 |
| `ready` | 代码、测试、迁移和发布说明齐全，可以进入候选构建 |
| `deferred` | 已明确决定不进入下一版，必须写明原因和目标版本 |
| `included` | 已进入某个完成验收的 Build，并已复制到该 Build 回执 |

`included` 只能在最终公证 DMG、Cloud 发布和目标 Mac 端到端升级完成后填写，不能因为
源码合并、App 构建成功或上传完成就提前标记。

## 3. 下一版候选工作

### NXR-001：Package 多源竞速、分片校验与断点续传

- 状态：`in_progress`
- 类型：客户端功能、下载可靠性、ACPF/Discover 共用基础设施
- 用户可见结果：Package/Runtime 安装可读取签名 Snapshot 中任意数量的
  `artifact.sources`，按 piece 并发竞速，坏源或停滞源不会阻塞其他源；支持校验后断点
  续传，并保留旧单源完整下载兼容。
- 需要进入 App 的文件：
  - `ai2apps/packages/registry.py`
  - `ai2apps/api/packages.py`
  - `ai2apps/provisioning/orchestrator.py`
- 发行测试：
  - `tests/test_ai2apps_registry_v1.py`
  - `tests/test_ai2apps_provisioning.py`
- 已完成验证：相关 pytest `63/63` 通过；Ruff 通过；生产 Cloud 单源 Range fixture
  piece hash 匹配；旧单源 fallback 测试通过。
- Cloud 依赖进展（2026-09-03）：ModelScope `HEAD` 缺少 `Content-Length` 的严格
  `GET bytes=0-0` 回退已经部署生产；Cloud 使用生产校验器完成 457,410,846 字节制品、
  全量 SHA-256、piece manifest 与 Range 预检，265/265 测试通过。此项只解除服务端
  校验兼容阻塞，不代表外部 Source 已进入匿名 Snapshot。
- Source 发布进展（2026-09-03）：GitHub Source 已由 step-up admin 正式激活；公共
  Repository Snapshot v101 已匿名确认发布 Cloud + GitHub。ModelScope 正式复验的新
  validation 已完整通过；Cloud 状态转换热修上线后，该 Source 已由 step-up admin 正式
  激活。公共 Snapshot v102 的签名和 pin 验证通过，匿名清单已包含 Cloud、ModelScope、
  GitHub 三源；三个源的首个 8 MiB Range 均返回 `206`，大小和 piece SHA-256 完全一致。
- 客户端生产实测（2026-09-03）：使用当前客户端实现从公共 Snapshot v102 下载
  `ai2apps/runtime-omlx 1.5.7`，55 个分片全部完成，Cloud 与 GitHub 均实际成为过竞速
  胜出源；最终文件大小为 457,410,846 字节，完整 SHA-256 为
  `b7f5e0bddcf285908ddd75465c02bdd35a9f6aa90690c739054a75295ea4bd49`，与签名清单一致。
  ModelScope 本次因速度未胜出，但其独立 Range 206 和分片摘要验证已经通过。
- 客户端专项测试（2026-09-03）：Registry 与 Provisioning 共 63 项测试通过，覆盖多源
  竞速、超过并发数的候选源、停滞源淘汰、坏源回退、已验证分片断点恢复和旧单源兼容。
- Build 2249 对照：直接检查 Build 2249 已公证 DMG 内嵌
  `AI2AppsLocal/app/ai2apps`，上述三项客户端实现未包含在 2249 中。
- 源码可复现性（2026-09-03）：`ai2apps/provisioning/orchestrator.py` 与
  `tests/test_ai2apps_provisioning.py` 已随本轮 development checkpoint 纳入版本控制，不再
  依赖 dirty-tree 隐式打包。
- 剩余发行验证：使用最终候选 App 完成一次 UI 安装验收；完成前不得改为 `ready`。
- Release notes 建议：Package 与 Runtime 下载现支持多源竞速、逐分片完整性校验和断点
  续传；单个镜像不可用时可自动由其他镜像继续。
- 纳入 Build：待定。

## 4. 发布流程工作

### NXR-PROCESS-001：建立下一版 Release 滚动台账

- 状态：`ready`
- 类型：发布治理；不改变 App 二进制功能。
- 内容：建立本文件，并将登记、构建门禁、归档和重置规则加入 `AGENTS.md` 与
  `docs/ai2apps-desktop-release-runbook.md`。
- 验收：未来 Desktop 发布必须先逐项处理本文件，不再仅根据工作区 diff 临时整理范围。
- 纳入 Build：不适用；随下一次源码提交生效。

## 5. 构建下一版前的强制门禁

发布负责人必须逐项执行：

1. 匿名读取生产 `stable.json`，确认本文件基线 Build 仍是当前生产 Build；不一致时先更新
   基线和回执引用。
2. 为每个 `ready`/`blocked` 项明确决定：纳入、修复后纳入或 `deferred`。不得默默遗漏。
3. `blocked` 项不得进入候选，除非阻塞已解除、证据已补齐并改为 `ready`。
4. 将每个拟纳入项映射到具体源码文件、测试、配置/迁移、用户可见 Release notes 和回退
   方式。
5. 对上一版最终 DMG 的实际内嵌内容与候选 staging App 做内容差异核对；不要只比较 Git
   commit，尤其不能把未跟踪文件当作可重现来源。
6. 正式发布要求所有拟纳入文件已提交并推送，工作树满足 Desktop Runbook 的 clean-tree
   门禁。任何 dirty-tree 例外都必须重新获得明确批准。
7. 在 Release notes 与 Build 回执中逐项引用本文件的 NXR ID。

如果候选构建包含本文件未登记的用户可见或安全相关差异，停止构建，先补登记和测试证据。

## 6. 发布完成后的归档与重置

当新 Build 完成端到端验收后：

1. 将所有实际纳入项的 NXR ID、说明、测试和例外复制到该 Build 的不可变发布回执；
2. 把对应项状态改为 `included`，填写纳入 Build；
3. 保留 `deferred` 项并更新目标版本，不得丢失；
4. 将本文件生产基线更新为新 Build、生产清单摘要和新回执；
5. 从“下一版候选工作”移走已经归档的 `included` 详情，只保留新基线之后的开放项；历史
   事实以 Build 回执为准；
6. 重新匿名核对 `stable.json`，确认台账基线与生产一致。

台账更新本身必须和导致状态变化的源码或发布回执一起进入版本控制，不能只存在于聊天记录。
