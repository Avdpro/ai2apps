# Mobile App 通用挂载与设备策略

更新：2026-10-10。本文描述当前机制；2026-10-09 的 sandbox/context 阶段不是新增 App 的固定入口白名单。

## 接入方式

Mobile Shell 通过动态 App 目录启动应用。新应用继续使用固定协议：

- `POST /v1/mobile/apps/{app_key}/open`
- `GET /mobile/app-resource/{mount_id}/{instance_id}/{resource:path}`
- `POST /v1/mobile/app-mounts/{mount_id}/bridge`

新增 App 不增加 Cloud App ID 清单，也不增加公开的 `/admin/*` 或 `/v1/platform/*` 通配代理。设备的 Mobile 开关仍按 Installation/App 保存：它决定此设备是否允许使用该 App，不是协议白名单，也不授予访客权限。已有七个历史入口保留兼容处理；新应用默认关闭，由设备 Owner 激活。

自建 sandbox App 已有通用页面、资源、context 握手链路；用户反馈贪吃蛇已按此链路通过。页面可显示不等于已获得所有模型、文件和 Agent 能力。

## 两种资源与能力合同

### Package sandbox

`mobile.ready=true` 且声明可解析的 sandbox Entry。由现有 Package 资源读取器执行路径规范化和 digest 校验。iframe 保持 opaque sandbox，不增加 allow-same-origin。Bridge 只接受 `{"method":"context"}`，返回空 capabilities；未授权方法、额外参数均拒绝。第三方 Package 不能通过 mobile.gateway 声明可信 host 权限。

### 可信内置 host App

内置定义可在 `mobile.gateway` 声明模板、静态 assets、自己的 API module/factory/prefix。声明是安装端可信配置，不能来自请求，也不能来自第三方 Package。目录返回 mobile_gateway 标记；设备开关统一判断声明是否可运行，不检查新增 App ID 名单。

模板以 `entry` 资源挂载，声明的静态资源以 `assets/` 获取。未声明资源、路径穿越、非 Mobile 挂载、跨实例、关闭 App 均拒绝。模板采用 Mobile base；不渲染长期 API 凭据。

Bridge 的 `request` 消息含 verb、path、base64 body 和受限 headers。API path 只能落在该 App 声明的 prefix 下，verb 限 GET/POST/PUT/PATCH/DELETE；不接受外部 URL、Authorization/Cookie、其它平台或管理接口。后台在独立 ASGI App 中装配该模块路由，保留原有 actor/资源归属校验；principal 从已验证挂载请求注入，不接受客户端指定用户。上传上限 21MiB，非法编码拒绝。返回 status/contentType/base64 body。文件或图片的 GET 使用同一挂载资源的 `api/` 分支，仍限定 App prefix。

共用适配器：`web/mobile_app_gateway.py` 与 `web/static/js/mobile_app_gateway.js`。不要为每个新 App 复制公网 API 清单。

## 情报中心

`apps/system.py` 声明 Mobile Ready、页面 assets 与 Intelligence 自身 API。手机入口为频道列表；频道页仅文章/热点/稿件、频道 Chat 和更多菜单；文章卡片单列，返回图标及边缘右滑导航，不另设底部导航。

聊天、热点和稿件调用 App 自身后台。更新频道由已有 Local durable collector 执行，手机轮询当前数据，不公开整个 Browser Workspace SSE。上传文件沿用原来的文章导入接口。URL 收录通过 Intelligence 的 import-link 接口在 Local 提交共享 WebAgent read_page，继承 Profile/actor/session、公开 URL 校验和页面清理合同，再复用原有翻译及归类；手机不获得原始浏览器控制端点。

## 激活与重启

可信 `AI2APPS_RUN_DESCRIPTOR_PATH` 定位当前实例的 `config/mobile-package-gateway.json`，精确内容：`{"enabled":true,"protocol":"mobile-app-access-gateway-v1"}`。显式环境变量仍优先；缺失或错误默认关闭。不要复制其它实例状态。然后由 Owner 通过设备 Mobile 开关激活 App。

Python/API 变更重启当前 Local；若修改 omlx/ 或嵌入 Runtime，按 App Dev 工作流使用固定 build-app-dev-environment.sh 重建，只退出 app-dev 对应进程，保持长期实例数据。不要改用临时 App 名或修改其它实例。

## 安全和验证

所有公网资源/Bridge 需要 Cloud 验证的 Owner 租约、同设备 Host/Origin、当前有效 Mobile mount、实例匹配、原有实例权限、启用策略。每次请求重新校验，关闭或租约撤销后拒绝。普通成员和手机 Owner 租约不能修改设备开关。已送达浏览器的内容无法撤回；已启动后台工作不因关闭开关自动取消。

新增回归覆盖 API prefix/verb/header/body 拒绝、跨 actor 注入隔离、上传、第三方 host 拒绝、静态资源穿越、关闭 App/跨实例/租约撤销拒绝。真实 iPhone 和 Cloud 联调结果必须单独记录，不能以模拟浏览器测试声称完成。

## App Dev 激活记录（2026-10-10）

仅 app-dev 写入通用网关配置并通过既有 MobileAppPolicy 开启 `ai2apps.intelligence`。标准 build-app-dev-environment.sh 已重建固定 App，旧包归档为 `AI2Apps-app-dev-20261010-144144.app`。新 Local PID 86313、端口 56925、boot `8df7e753-761c-4c9c-b186-b3f58d6a5ea0`。原生窗口实际显示 `AI2Apps-App-Dev: App-Dev 127.0.0.1:56925`。bundle ID/instance/cloud Runtime/开发源码根契约、verify-release-app.sh、codesign deep strict 均通过。

重启后账户 → 设备 → Mobile 可用应用实际显示 Intel Center 已开启，支持标记有效。64 项 Python 回归（包括模板及声明资源）和 11 项前端卡片/聊天/写作测试通过；隔离 Chrome 手机导航测试通过。旧摘要引用映射测试补齐此前主来源字段合同，不改变业务逻辑。

真实手机和生产 Cloud 完整访问未验收。隔离测试浏览器无法使用已注册设备的离线激活；测试用 Cloud 成员激活被自动审批拒绝，因可能改变账户/设备状态，未执行。没有修改 Cloud 或其它实例。


## App / Mini-App Cloud 模型调用（2026-10-16）

Mobile App API 可能运行在仅挂载自身路由的独立 ASGI 容器中，不能假设 request.app 包含 /v1/chat/completions。前台非流式 Cloud 调用统一使用 ai2apps.model_invocation.invoke_app_cloud_chat(runtime, payload, principal=principal, session_id=..., consumer_app_id=..., app_instance_id=...)，通过系统 ModelInvocationService 执行，不向当前 App 容器发模型 HTTP 请求，也不复制 Cookie/Authorization。

业务接口须先完成原有 Owner、App、资源、mount 和 capability 校验。principal 必须来自已认证依赖；Mini-App 的 consumer_app_id 和 app_instance_id 来自宿主验证后的声明和 mount，不能取自请求正文。调用保留 actor、Installation、membership epoch、计费和 Session 身份；Cloud 身份变化仍由服务层拒绝。后台 durable Task 继续按持久记录的 actor 解析身份。Package 模型沿用共享前台/后台调用入口，不因本次 Cloud 路由修复改变调度。

已迁移：情报中心编辑/稿件、Todo Emoji、Studio Mini-App 文本/翻译/缩写、Agent 展示与编译、访客 HTML AI 编辑。普通 Owner Chat/Studio 网关已有专用模型入口，不向 Mobile 通用 App API 扩张任意模型路由或认证白名单。
