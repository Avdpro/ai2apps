# Mobile Agent 客户端准备层验收

日期：2026-10-21
状态：本文件记录准备层的历史隔离验收。后续已实现 Desktop 批准连接的签名接入，当前状态见 [v1 实现与验收](desktop-approved-mobile-agent-20261021.md)。App-only 已不再是产品边界，生产能力仍默认关闭。

## 实现

- Mobile 加载共享 AaAT 图文渲染器，购物类纯数据 table 横向滚动，cards 单列，图片按原始受保护 URL 加载，失败明确占位，不放宽图片权限或 CSP。
- 共享参数表单仅新增可注入 transport，原桌面默认行为不变。复用描述符、字段、保存 revision、提交与取消守卫，无 App 业务分支。
- 新 Mobile Agent 客户端处理 waiting_input、普通表单/文本、菜单、批准/拒绝、预算询问、取消，以及实际 status_line 进度和真实终态。轮询不重建编辑中的表单；不支持的复杂交互明确保留等待，禁止提交缺失字段。
- App 专属 handoff 由目标 App 完成；当前没有已登记的原生 Mobile handoff adapter 时提示桌面继续，不伪造完成回执。Phone 目标 App 打开/身份链留待 Cloud/native 联调。
- Session 恢复 API 复用 Session 所有权检查与根 Run 查询。刷新、网络恢复、回前台只读取任务/草稿/消息；跨会话迟到响应被丢弃。已持久化图文由消息恢复，不与 Run 重复显示。
- 提交通用交互保留相同 response_id 与 payload；不确定网络结果不允许改成另一选择再次发送。创建调用携带请求幂等键。取消和未知状态不会触发替代业务执行。
- Agent 模型默认复用能力声明策略，不按型号推断；显式选择不静默替换。

## 关闭状态与审批边界

Owner 网关白名单没有开放任何 Agent 路径。Mobile 模板默认不启用 Agent，普通 Chat 是状态标签而非无效切换按钮。

直接注册新的控制代理被自动审批拒绝，原因为扩大 Agent 控制面且身份约束证据不足。安全替代为 `web/mobile_agent_transport.py` 工厂：生产 Shell 未 include_router，默认 capability callback 返回 False；仅隔离测试注入 fixture 授权。未尝试通过其它路径注册或绕开拒绝。

传输工厂仅有精确 method/path 清单，不转发任意目标、Authorization 或客户端身份；未来接入要求绑定已验证的实际 actor，禁止替换成 Desktop/Owner/legacy API key。App 专属授权、图片资源的远程受限传输和手机目标 App handoff 须按最终 Cloud/native 合同联调，不能将浏览器 fixture 当作这些权限已可用。

## 验证

- Python：实际 General + SQLite + Platform 参数 API + fixture Mobile adapter，覆盖参数编辑、Agent runtime 重启、原草稿恢复、重复提交只执行一次、取消后提交409、完成视图与消息持久化。另覆盖默认拒绝、伪造 App Header 无效、方法/路径限制、精确 actor/请求体/幂等键保留、Owner 现有边界拒绝、Session 查询隔离。10 项通过。
- 原 Owner 网关25项通过，普通网页没有获得 Agent 访问能力。
- JS 单测37项通过：含参数表单、Mobile 模型/流式回复、通用图文、延迟恢复隔离、未知网络结果的同回应幂等、只读恢复与实际 partial 保留。
- 完整 Mobile 模板的390px离线浏览器：参数编辑→刷新恢复→确认提交→进度→预算等待/用户继续→图文完成→再次刷新，只创建1个Run；实际图片加载，页面不横向溢出，原始链接保留。Owner页面无可点击Chat切换或Agent入口、不发Agent请求。2 项通过。
- 最终 AaAT 架构门禁173项通过（76.58s），已包含10项Mobile后端契约。Owner网关/租约/Mobile访问策略组合59项通过（9.57s）。最终前端及完整浏览器组合39项通过，无跳过。

没有重启/重建 Dev，没有更改 Cloud 或 iOS 授权，没有购买、发布或其它真实业务执行。静态资源由标准 Mobile 静态清单提供；新权限接口仍不可达。
