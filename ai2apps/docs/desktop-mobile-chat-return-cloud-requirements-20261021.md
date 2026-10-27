# Desktop/Mobile 配对：Chat结果回到普通入口

日期：2026-10-21。仅为Cloud项目交接要求，本仓库没有改Cloud代码。

Desktop首页二维码复用desktop-mobile-agent-v1。手机扫码后Desktop显示绿色对勾，
启用默认未选中的“允许运行Agent”；用户确认勾选时decision=agent，未勾选时
decision=chat。Agent继续现有ACK与连接私钥证明。

发现Cloud mobile-agent-page.ts在chat终态停止轮询并显示说明，但没有返回Desktop
按钮。请在chat终态提供明确的“进入普通Chat”导航，目标由服务端保存的精确
Desktop Device/Installation绑定决定，不接受前端returnUrl，不改连主要设备。
复用既有Owner登录/Owner Home普通Chat恢复机制，不签发agent:invoke租约，
不把connectionId或chat决策当Agent授权。若既有Owner访问未就绪，请走现有
账户登录/选择流程，不新建同权代理。denied/expired/revoked不显示Agent入口。

验收：未勾选确认后手机能够明确返回同一Desktop普通Chat；Agent接口继续拒绝；
旧有效Agent连接不因chat决策失效。Agent分支、旧Chat API和通知OAuth权限不变。

## 2026-10-21 普通App与Agent连接衔接补充

真机确认仅Agent批准返回/mobile/home时，没有普通Owner App会话，普通App列表返回拒绝。
Desktop Local不能把agent:invoke租约转换为Owner App权限。本地已给出独立“连接其他App”
入口，经/mobile导航到既有Cloud普通授权页，Agent收藏及私钥保留。
请Cloud明确配对结果中普通App授权的独立handoff/续接协议：同一Owner、Device、原点绑定，
单次短时消费；普通权限仍按既有Owner规则决定，Agent批准不是授权替代。
扫码同一Desktop不应要求删除旧收藏；新配对应有新ticket/connection，在Desktop ACK前旧连接
仍按现有generation有效，ACK后单一active切换。重复claim的幂等/已消费提示需区分新扫码。
另公网附加CSP会与Local CSP共同生效：目前Local使用有权限的字节解码绘制，不要求Cloud
放宽策略；若后续采用blob图片节点，需双方统一明确img-src并保留其他限制。


正式一次扫码协议已整理为 [desktop-mobile-one-scan-app-agent-handoff-v1.md](desktop-mobile-one-scan-app-agent-handoff-v1.md)。
请以该文的能力协商、片段字段、绑定交换响应与拒绝降级规则作为实现/联调接口，
不要只加导航按钮后把普通App与Agent当成同一个权限。Local/Mobile端已实现等待Cloud协商。
