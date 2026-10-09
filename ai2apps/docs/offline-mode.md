# 未绑定设备脱机模式

首版范围（2026-10-07，经用户确认）：仅没有 Cloud 安装绑定、没有设备登记记录的桌面实例可选择脱机使用。已绑定设备保持原行为，不提供解绑或模式切换。

## 使用

首次启动原生 AI2Apps Shell，登录页提供“脱机使用”。不要求 AI2Apps 帐号、密码或设备登记。进入后首页与帐号页显示脱机模式。已有 BYOK 配置、本地模型与本机 App 可继续使用；BYOK 仍需要供应商网络。Cloud 模型、公网设备共享、Cloud 帐号、成员、消息和其他帐号服务不可用。

匿名公开 Registry 浏览和已发布模型/Runtime 下载仍可使用（需要网络），使用不携带帐号 Cookie 或 Authorization 的独立通道；签名、摘要、Range 和信任检查保持不变。发布、帐号和计费服务仍禁用。此模式不是禁止所有网络访问。

## 身份与边界

- 启用接口要求有效的原生 Shell 会话证明、本机 Host/连接来源和同源检查。仅访问 loopback 或持有推理 API Key 不能启用。
- 使用独立 `offline.<本机安全身份>` 主体与原有实例专属 HttpOnly Local Cookie，不写入 Cloud installation/member 表，不伪造云端成员。
- 模式与会话摘要原子写入本机平台目录，文件权限 0600；原始会话令牌不落盘。重启恢复原主体；登出撤销会话而保留脱机模式。损坏状态拒绝启动，不静默恢复 Cloud。
- 恢复本地后台任务时只接受与本机安全身份和持久化模式一致的离线主体。Cloud 成员解析器仍拒绝该主体。
- Installation 和浏览器 Cloud 客户端统一在网络发送前拒绝帐号请求（403/offline_mode）。不携带 Cloud 认证到 BYOK；直连供应商路径继续使用用户自己的密钥。
- 停止 Cloud defaults、设备连接/访问投影和消息轮询；脱机启动不启动这些后台任务与模型共享 Provider。
- 本版不提供脱机转帐号、帐号转脱机或数据合并流程；保留未来显式迁移设计空间。

## 验证

`ai2apps/tests/test_offline_mode.py` 覆盖无绑定创建、禁止已绑定创建、令牌摘要、重启、失效/撤销、跨实例拒绝、损坏状态、Cloud 零发送、匿名 Registry、真实 Server 认证依赖、原生 Shell 引导和 BYOK 直连模拟。

开发环境使用标准 `build-app-dev-environment.sh` 重建固定 App，保留长期 app-dev 数据。现有 App Dev 已绑定帐号，因此不能用于实际启用脱机的全新设备验收；不为测试重置、复制或解绑现有环境。本轮已按用户授权重置并构建独立 Test：脱机入口、重启恢复和模拟 BYOK 对话通过；真实本地模型被旧 Qwen3.5 Package 的 Runtime 兼容问题阻塞，见 [Test 验收记录](offline-test-20261007.md)。

Cloud 后端没有修改，也不需要 Cloud API 变更。
