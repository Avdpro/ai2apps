# Discover Cloud 1.77 客户端接入

## 已实现

- Registry 先协商 capabilityCatalog 的必要契约字段，兼容服务附带的筛选/分页元数据；
  新目录走 capabilities-v1，缺失特性回退旧关键词目录。旧服务不支持的结构化筛选明确拒绝，
  网络、索引或新响应校验失败不降级成“零候选”。不声称语义搜索或自动翻译。
- Discover App 与 discover.packages AaAT 保留精确 release、Agent 三态、匹配/未知/排除原因、
  outcome/counts 和稳定分页。被排除的卡片不能安装，也不进入 AaAT candidates；
  declared 只表示签名声明，runtime_verified 仍为 false。新 App/Mini-App 目录不掺入模型 Service。
- Local Contract v1 支持签名 capabilityCatalog，使用与 Cloud 相同的 JSON schema；
  校验真实 App entrypoint/Mini-App 身份、Agent 声明版本/导出和重复身份，Mini-App 对照已校验
  artifact 内的 app.yaml 索引。构建/签名/验包复用标准实现，schema 文件进入 wheel 数据清单。
- 新卡片选择绑定 package/version/manifestSha256/artifactSha256。详情页不换成最新版本；
  安装继续走原 signed Registry manager，下载验签后、依赖预检/安装前比较两个摘要，
  重新读取签名仓库确认 published 状态。摘要变化拒绝并要求重新审核。
- 依赖重启 continuation 持久保存原 target，恢复不替换版本/摘要，不因已安装较新版本
  自动把旧 target 当作完成。旧不带 target 的安装调用保留兼容。
- 成功的 pinned 安装返回 capabilityDiscovery；只观察原已安装 artifact 身份、active effective
  definition、当前 actor 的 App 访问权和实际注册的 Provider。删除/升级/替换后再次查询会返回
  not_installed/installed_release_differs/inactive_or_replaced，不缓存旧可用结论。

## 仍未完成，不能宣称闭环

Cloud 的 agent exports 是发现摘要，不包含可直接执行的可信本地 handler、输入 JSON Schema、
授权/确认策略或已验证的隔离 RPC。当前 PackageRuntimeBinder 只绑定已有 Service tools；
没有把 App capabilityCatalog JSON 自动转换成 handler。

因此安装后观察器明确返回 adapter_required/no_aaat_declaration，或“已有注册能力但接口仍需核验”，
callable=false。它不是执行适配器，也没有实现 Package Provider 的自动注册/撤销。
下一步仍须制定/接入 Package 所属隔离运行时的实际 AaAT 导出协议与生命周期，验证精确
Package/version/digest、App/Mini-App identity、接口版本、actor/Installation/Session、权限、
参数确认和卸载撤销后，才能把原 Chat 草稿继续到业务调用。

当前推荐到安装仍在 Discover 原有界面；没有新增 Chat 推荐选择的持久交接，也没有用目录
声明跳过业务确认。ACPF 的已有 Chat 持久会话继续工作。

## 发布者与生产数据

Cloud 1.77 已部署，仍无新版能力声明的生产包；现有 Package 保持 unverified。
此次未改写或发布生产包、未安装模型、未接受真实许可。新声明须随新的不可变 release
通过原签名发布流程发布，且须等更新后的 Local 进入目标客户端。

## 验证

- Python 合并回归 84 项：Registry 安装/依赖、签名 Contract、目录旧协议、新协议协商、
  未核验/排除、目标双摘要拒绝、续装恢复、安装状态观察等。
- 新 Discover JS 单元 2 项及既有原生目录分页回归通过。
- AaAT 边界门禁 255 项通过；共享 AS 没有业务特例。
- App-Dev 真实只读联调与最终源码激活记录见下。新签名包使用临时 fixture，
  不等同于真实生产发布、干净实例安装或隔离 AaAT 调用成功。

### App-Dev 真实只读验收

固定 app-dev 已从生产协商并读取能力目录：无关键词时 40 张精确 release 卡片、全部未核验；
`avatar` 查询显示 3 张未核验候选、37 张排除项。三张候选均为同一 Talking Portrait Mini-App
的不同精确版本（0.1.1/0.1.2/0.1.3），不是三个可执行 Provider。排除项默认收起，可查看原因。
没有执行 Package 发布、安装、许可确认或业务生成。旧模型 Service 不混入此新目录。

最终固定 App-Dev 端口 58138：中文 `数字人` 显示匹配 0、未核验 0、排除 40，
排除卡片默认隐藏，页面提供“查看不匹配项 (40)”。App 与 Helper 的 source root、
Local 的 builtin_apps 实际导入路径和线上服务的 discover.js 字节均与本 checkout 一致。
既有目录 JS 回归为 4 通过、1 跳过；后者不是执行成功证明。

后续实现状态：原文“仍未完成”记录的是 Cloud 1.77 首次接入时点。后续已增加签名 App-to-isolated-Service 导出协议、生命周期对账与 Discover 持久安装交接；具体范围和限制以 [后续记录](package-aaat-lifecycle-20261023.md) 为准，不能将旧生产包视为已升级。
