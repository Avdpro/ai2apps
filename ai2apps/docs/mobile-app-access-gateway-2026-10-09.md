# Mobile App 设备策略与通用公网通道

日期：2026-10-09。当前状态：设备设置及现有 App 限制已实现于源码；通用 sandbox 资源及 context Bridge 已实现、默认未激活，Cloud 尚未变更，未做实机发布声明。

## 本地已实现

账户 → 设备 → 远程访问 → Mobile 可用应用。设置按 Installation/App 持久保存，新增 schema v85。Owner 在本机管理；手机的 Owner 租约及普通成员不能修改此设置。接口为 GET /v1/platform/remote/mobile-apps、PUT /v1/platform/remote/mobile-apps/{app_key}，PUT JSON 为 {"enabled":true|false}。

已接入 Mobile 目录、挂载列表、启动、聚焦、原生 App 页面和主要功能接口，以及 Studio 专属接口。默认保留已有七个内置 App；其它 App 默认关闭。当前 Cloud/客户端固定公网通道尚在，自建应用展示“通用远程通道尚未启用”，不开通无效开关。

本开关控制 Mobile 使用，不授予访客身份，不发布公开 Open-Entry。已传输到浏览器的内容无法撤回，已开始的任务不自动取消。Studio 的 Gallery/模型等共享依赖与独立 App 入口分开：关闭 Gallery 独立入口不阻止已开放 Studio 的素材选择。整个 Mobile 管理 API 不对公网导出。

## 已批准及已实现的客户端边界

2026-10-09 用户明确批准：限定本人 Owner 有效登录会话、App 开关、实例/挂载和 sandbox。新增路径已通过自动审批。身份约束指账号本人登录的客户端，不是对物理手机硬件的识别。

资源接口要求公网上必须为经过 Cloud 验证的 Owner 租约；旧配对会话不能代替这个校验。本地要求已认证 core/Owner。每个请求均检查 mount 有效、placement=mobile、renderer=sandbox、实例匹配、当前用户实例权限及当前开启状态。

已实现 POST `/v1/mobile/app-mounts/{mount_id}/bridge`：目前只接受 `{"method":"context"}`，返回 appId/instanceId/viewMountId/surface 与空 capabilities。禁止额外字段、任意 URL、工具或未授权能力。Shell 验证实际 iframe 来源、mountToken、instanceId 后通过此接口完成 opaque frame 握手。**第一阶段只支持无需后端能力的 sandbox 页面；模型生成/文件/Agent 等 Bridge 未实现，不能声明所有自建 App 都已可用。**

Cloud 完成本文资源/启动/Bridge 路径部署并验收后，才可在目标 Local 配置 `AI2APPS_MOBILE_PACKAGE_GATEWAY_READY=1` 并重启；默认关闭，在关闭状态管理界面禁用自建 App 开关且目录不暴露这些 App。

具体边界：

1. 动态启动仅接受设备当前可见目录中的 App，并同时校验 Mobile Ready、启用策略和当前访问者的原有 App 权限；不得仅凭 App ID 或 Owner Cookie 放行。
2. 新增 GET `/mobile/app-resource/{mount_id}/{instance_id}/{resource:path}`，每次要求有效会话、同设备 Host、actor 所属的有效 Mobile mount、匹配 instance、启用策略和 sandbox renderer。资源由现有 digest 校验/规范化读取器提供，不接受磁盘绝对路径、目录穿越和跨 App mount。
3. Mobile Shell 生成该受限路径；Package iframe 保持 opaque sandbox，不加 allow-same-origin，不继承开发环境放宽规则。来源必须对应具体 iframe，握手必须匹配 mount token 和 instance。
4. 不开放 `/admin/*`、通用文件系统、任意 URL 代理、任意平台 API 或管理能力。
5. 通用 Bridge 需要另外落地方法级能力授权：绑定 actor/App/instance/mount，交集计算 manifest 声明与设备授权；缺省拒绝。当前 Mobile Shell 仅已有导航握手，不能将显示 HTML 声称为完整可运行任意 App。
6. 第一阶段仅支持安全 Package sandbox 页面；schema/safe-html 等 renderer 和需要新能力的 App 必须在 UI 明示暂不可用。完整生成型自建 App 的验收应覆盖 Bridge 后再声明完成。

## Cloud 交接需求

Cloud 的设备反向代理应允许上述固定协议形状，而不是维护自建 App ID 清单。保留现有 native App API 冻结清单，不能用宽泛 `/v1/*` 替代。

新增通道方法仅 POST `/v1/mobile/apps/{app_key}/open` 和 GET 上述 app-resource 模式；app_key 为单段，mount/instance 为规定的 ID 格式。沿用设备域名绑定、上传/流量限制、流式转发和原有有效租约检查。新资源路径保留 Local sandbox CSP、无缓存和 nosniff；无 CSP 时拒绝嵌入。不要修改本机管理 API 的拒绝规则。

Cloud 需追加上述 context Bridge 的精确 POST 路径，保留 Origin/Owner/租约限制；客户端方法 allowlist 仅 context。后续能力扩展另行提供方法与权限合同，不能预先开放通用 proxy。新增 App 不应要求 Cloud 审核具体 ID，但客户端协议本身需在双端验收后启用。

## 必测项目

- 禁用后目录、直接启动、已知 instance 聚焦和直接页面/API均拒绝；重新启用恢复。
- 普通用户不能修改设置，账号/Installation 隔离；权限不足者不能靠开启 App 获得额外能力。
- 自建 App 默认关闭；启用后不同 actor、跨 App/mount、过期/撤销租约、资源路径穿越均拒绝。
- Sandbox 无设备 Cookie/管理凭据，恶意 iframe 消息无法冒用其它 App。
- 未授权能力 Bridge 调用拒绝，带能力的真实 App 在 iPhone Safari 完整调用/回看/重开通过。
- 原七个内置 App 与桌面入口回归，Cloud 未升级时 UI 不承诺自建 App 已可用。


## 本轮源码验证

55 项 Python 与 6 项 Mobile 导航 Node 测试通过，包括匿名拒绝、关闭 App 拒绝、跨实例/非 Mobile mount 拒绝、Origin 拒绝、撤销后资源/Bridge 拒绝、CSP 不含 allow-same-origin、任意 Bridge 方法拒绝。没有 iPhone 或生产 Cloud 联调验收；Cloud 未部署，目标 Local 未重启。


## Cloud 部署后的 Dev 激活（2026-10-09）

- Cloud 已部署 mobile-app-access-gateway-20261009-v1，交接路径和 CSP 合同已核对一致。
- Helper 过滤非白名单环境变量，Ready 增加实例独立配置：由可信 AI2APPS_RUN_DESCRIPTOR_PATH 定位同实例 config/mobile-package-gateway.json，内容精确为 {"enabled":true,"protocol":"mobile-app-access-gateway-v1"}。显式环境变量仍优先，0 可关闭；文件缺失/格式错误默认关闭，不读取请求提供的路径。
- 仅 dev 写入配置并通过标准 HelperControlClient 重启。新 PID 80734，端口 62813，boot 8dadc33c-ef75-481f-bbd7-42a9f76a7171。没有重启 App-Dev/Test 或复制其状态。
- Chrome 从固定用户 URL 正常恢复 Owner 会话，Mobile 首页实际显示 Owner session connected 和内置 App；Dev 原生窗口标题及账户“远程访问”列表核实目标设备和 Mobile 开关正常加载。
- 44 项 policy/Owner gateway/Owner lease 回归通过，包括实例独立配置与缺省拒绝测试。
- 当前该设备目录没有独立 sandbox Package。真实 Package 打开/返回/重开、实际租约安全矩阵及 iPhone Safari 未完成；已请求用户指定 Package 或允许创建最小无私有数据测试 App。本轮未开启任何自建 App。
