# AaAT Channels MVP v1

状态：代码已实现，App-Dev 已重启并完成只读 API 与既有 Agent-Chat 核心路径实机验收；此前发现的重复用户消息问题已另行修复。此 MVP 实现提案阶段 A/B 的静态频道与只读调用子集，不代表整份提案已实现。

## 已实现范围

- 可信 Provider 注册中的可选 `channels` 元组，每个 `ChannelBinding` 绑定一个频道及一个只读角色。它不是另一份业务能力注册。
- 内置情报中心（list/search/read）、Gallery（search/read）、Knowledge（search/read）根频道。情报中心的实际子频道通过原 `intelligence.channels` 查询；动态资源仍使用 owner 原始引用与参数，未实现通用动态频道/资源结果外壳。
- 已认证系统管理端的 `GET /v1/platform/channels` 与 `POST /v1/platform/channels/read`。两者均要求有权访问的现有 Session，并继承当前系统管理 API 的权限要求，不接受请求体指定调用身份或额外授权。
- 调用通过原 Tool Gateway：保留 capability、Session、业务资源 ACL、超时、持久 Tool invocation 与审计。不会创建 Chat 或模型回合。
- 原 Provider 版本及具体能力固定；版本变化、撤销、禁用均拒绝新调用，不切换其他 Provider。需要选择参数、配置或 owner invocation_policy 的调用不走此入口。
- 目录只投影当前 Gateway 可执行的注册能力；缺少 capability grant 的频道可能不可见，不会通过发现自动申请授权。

未实现任意 App/Package 委托、写操作、无 Run 确认、v1 内系统 AI 纠错、持久逻辑 request/attempt 去重、跨源语义检索和 UI 面板。不可把此管理端接口直接开放给 Package frame。没有修改当前 Agent-Chat 执行链，也没有迁移旧纠错/确认/恢复行为。

## 接口使用

先使用当前认证身份和已有 Session 查询：

```http
GET /v1/platform/channels?session_id=<owned-session>&query=素材&limit=20&offset=0
```

响应含 `schema=ai2apps.channels/v1`、`items`、可见静态频道总数、`next_offset`、scope/coverage/truncated。分页不是持久快照；注册或权限变化后重新发现。频道 `ref` 是 owner + local_id + interface_version，每个 operation 提供 role、capability、provider、provider_version。自然语言 query 仅对声明的名称、别名及类型做确定性匹配，不推断业务 ID。

从发现结果原样选择操作；可通过现有 `GET /v1/platform/capability-providers/{provider}/parameters` 读取 owner 当前参数契约。按精确字段提交：

```json
{
  "session_id": "<owned-session>",
  "owner": "ai2apps.gallery",
  "local_id": "library",
  "interface_version": "1",
  "provider_id": "<operation.provider>",
  "provider_version": "<operation.provider_version>",
  "role": "search",
  "arguments": {"query": "sample", "limit": 20}
}
```

提交地址是 `POST /v1/platform/channels/read`。arguments 不能包含 provider/parameters 路由字段；owner 参数不做静默裁剪或 AI 修正。返回原 owner `output` 及 Gateway `invocation_id`；查询该 invocation 沿用既有鉴权接口。仅只读操作可执行；不要将重发请求解释为效果操作幂等保障。

## 开发与版本保护

`ChannelBinding` 定义于 `services/channels.py`，Provider 新增的 channels 默认空。内置 owner 在原 register 调用声明 binding，业务 handler、Provider 版本、Agent Tool schema 与旧 catalog 投影不变。Package 当前导出接口不接受此扩展。

宿主创建的 ToolCallContext 可携带 `pinned_provider=(capability, provider, version)`；该字段不是模型或 HTTP arguments，Gateway 派发时保留它。Router 仅在该字段存在时启用新入口守卫，普通 Agent-Chat context 的默认值为 None。新入口不写共享 Provider 成功偏好或冷却记录，避免改变旧 Chat 的候选排序。prepare 的异步间隙发生 Provider 替换时，现有注册实例检查阻止执行。

新共享模块加入 AaAT 正向依赖分类，原因是只依赖通用 Gateway/Provider 契约，不含 App 身份分支或业务数据解释；没有新增业务例外。

## 验证

从 Git 根目录运行：

```sh
.venv/bin/python -m pytest ai2apps/tests/test_channels.py ai2apps/tests/test_builtin_app_aaat.py ai2apps/tests/test_capability_routing.py ai2apps/tests/test_aaat_architecture.py -q
.venv/bin/python ai2apps/tests/run_aaat_boundaries.py -q
```

测试使用隔离数据和真实 Local handler；模型执行为原回归夹具，不代表实机或真实模型验收。隔离测试阶段未重启 Local；后续按用户授权重启 App-Dev 并完成实机验收，未构建 App、未修改 Cloud。

本轮验证：新增频道测试 11 项、现有 owner/路由/架构 53 项、完整 AaAT 门禁 711 项全部通过；最后的共享偏好隔离修正另有 27 项定向验证通过。详细范围、执行顺序和实机限制见 [验收记录](acceptance/aaat-channels-mvp-20261101/README.md)。

后续版本：[系统只读参数纠错 v2](aaat-read-parameter-repair-v2.md)已作为显式独立入口实现；v1 与 Agent-Chat 不自动迁移。先前发现的重复用户消息问题已在 [后续修复](acceptance/chat-agent-input-identity-20261101/README.md)中完成。
