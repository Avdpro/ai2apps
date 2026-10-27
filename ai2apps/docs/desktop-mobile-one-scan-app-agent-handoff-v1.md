# 一次扫码：普通 App 访问与可选 Agent 授权

2026-10-21；Desktop/Mobile 实现准备协议，Cloud 1.75.0已交付；真实客户端验收进行中。
本仓库不修改 Cloud 代码。对接基线 desktop-mobile-agent-v1 / OpenAPI 1.74.0。

## 用户流程与权限

Desktop 首页“链接二维码”生成新配对。手机扫码、Cloud 登录一次；Desktop 显示绿色
对勾，默认不勾选“允许运行 Agent”。确认始终申请此 Desktop 的普通 App 访问；勾选
时额外批准 Agent，保留现有30秒确认、35秒ACK、单有效连接与generation约束。
Cloud 仍独立验证 Owner/组织/Installation/App 权限。Agent 批准不能替代普通 App 授权。
不勾选不得撤销此前有效 Agent 连接，也不得误恢复另一个连接的Agent身份。

Home 显示同一Desktop上经普通授权、设备Mobile策略启用且有Mobile入口的全部App。
没有手机UI的App不伪造可点卡片。Agent默认发现同一Desktop对当前身份开放且已接入AaAT
的所有App/Mini-App能力，不按Mobile UI目录裁剪，也不另建手机Tool白名单；调用、确认、
资源归属、Provider关闭等继续复用Desktop检查。没有AaAT能力声明不等于自动获得Agent适配。

## 协商（Cloud待实现）

GET /v1/internal/mobile-agent/device 新增可选 appHandoffProtocol：
`desktop-mobile-app-handoff-v1`。Local只在精确协商成功时给POST /pairings增加
`{"appHandoffProtocol":"desktop-mobile-app-handoff-v1"}`；旧Cloud仍发送{}，不误称支持。
Cloud /pairings 返回同字段，整个claim/decision/ACK结果保留此配对的协议版本。
普通App交接只能在decision=chat终态、或decision=agent已ACK active之后签发。
拒绝、过期、撤销、ACK失败均不得签发成功交接。

## 手机返回与交换

Cloud回到注册的精确Device origin（不能收客户端returnUrl）：

- Agent批准：`/mobile/home#agent_connection=<uuid>&apps_connection=<同uuid>&apps_handoff=<oh1一次性handoff>`
- 仅普通App：`/mobile/home#apps_connection=<uuid>&apps_handoff=<oh1一次性handoff>`

片段只在内存消费，立即replaceState去掉；不进收藏、localStorage、日志或Referer。
手机POST既有 `/v1/mobile/member-session/exchange`，JSON：
`{handoff, mobileConnectionId, appHandoffProtocol:"desktop-mobile-app-handoff-v1"}`。
Local Host/Origin检查后，以该设备凭据调用既有
`POST /v1/internal/installations/{id}/member-handoffs/exchange`，传相同字段。
Cloud必须原子消费且校验handoff属于指定连接、Owner、Device、Installation与已批准终态；
错误绑定不能消费另一个有效handoff，不返回Cookie/租约。组合handoff不得省略绑定字段后走旧交换分支；Cloud与Local均拒绝该降级。

Cloud交换返回既有owner-open-home-v1 accessToken/leaseToken/refreshToken/deadlines，
Owner JWT须同时签入 app_handoff_protocol、app_handoff_connection_id、app_handoff_agent（整数0/1），access/member与lease必须一致且续期不得剥离或改变。
组合Device绑定分支mapping_revision=0，表示不走primary映射；只在已验签且完整组合绑定校验下接受此零值。旧入口mapping_revision及其它epoch/revision仍须正整数。
并增加经服务端保存的 `appHandoff` 对象：
`{protocol:"desktop-mobile-app-handoff-v1",connectionId,deviceId,installationId,actorUserId,agent:boolean}`。
Local验证对象与请求连接、已验签Owner租约的Device/Installation/actor完全一致；agent=true
时还验证此Local当前已ACK有效连接相同。交换完成后才设置既有Secure/HttpOnly/Strict
Owner Cookie。Agent私钥与短租约仍独立，不返回Local管理员Cookie/API key。

丢失交换响应不可自动重复消费handoff：当前页面说明交接未完成；用户刷新仅探测普通App
目录/Owner状态，不重新消费，不自动生成新任务或要求用户删除收藏。Cloud可提供
绑定同一客户端的幂等重取，但不得复用旧bearer生成第二份授权。

正常App Cookie与Agent租约分别续期、分别撤销，所有epoch仍逐次校验。重载Home先读
现有Cookie目录并证明当前Agent私钥；普通App授权失败不显示完整App列表，Agent失败
不抹掉有效普通App访问。仅普通App的新配对不授予新的Agent权限，也不撤销此前独立且仍有效的Agent授权。
本地active仅作候选线索；恢复旧Agent必须重新通过原私钥持有证明、Cloud租约与Local
当前generation/connection校验。无active/私钥、已撤销或已被替换的连接不能获得Agent。
旧客户端prefer-agent=false不代表服务端撤销，不得用它遮蔽仍有效的授权。

## 扫码与验收

相同Desktop收藏复用稳定/home URL，新的扫码ticket每次不同；同页hashchange也消费新ticket。
不删除旧收藏、Cookie或私钥；ACK前旧Agent仍按既有协议有效，ACK后旧连接必须拒绝。

必须验收：同一次扫码仅普通App/普通App+Agent；Home全部已授权App且点击正确；无Mobile
入口的App仍可经已注册AaAT调用；关闭/未授权App拒绝；更换Device/actor/installation/
connection、旧handoff重放、Origin错误、ACK失败、过期、撤销均失败关闭；原Chat和Package
动态目录兼容；重载及历史恢复不重新执行任务。Fixture与生产真机证据必须区分。
