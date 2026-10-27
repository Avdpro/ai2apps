# Mobile 配对页面文案修正

Cloud 1.76.0 已部署统一 Mobile 授权，但用户手机仍显示旧 Agent 许可文案。

## 已定位

Cloud `src/spaces/mobile-agent-page.ts`：
- 页面 title：批准 Agent 连接
- h1：连接 Desktop Agent
- claim 成功提示：请在 Desktop 上选择是否允许 Agent。

## 要求

- title / h1 统一为「连接 Desktop」。初始页面尚未判定协议，使用中性文案。
- claim 成功： 「请在 Desktop 上确认此次连接。」
- 新协议 awaiting_exchange： 「Desktop 已确认，请返回完成连接。」
- 返回按钮： 「完成连接」。旧协议确实为 Chat-only 或 Agent 的结果说明继续按原状态准确展示。
- 新协议不得出现“选择是否允许 Agent”或单独 Agent 审批承诺。不改变 commitMode、generation、handoff、exchange、安全校验和撤销时序。
- 如此页面已有语言选择机制，同步中英文：Connect to Desktop / Confirm this connection on your Desktop. / Desktop confirmed. Return to finish connecting. / Finish connecting。

## Local 已同步

Desktop 收到成功 decision（含 awaiting_exchange）后立即关窗；仅关闭 UI，不提前激活、不执行 ACK、不撤销客户端。手机仍自行完成 handoff/exchange。确认请求失败保持窗口并显示错误。

## Cloud 验收

新协议扫码后页面没有旧 Agent 选择文案；Desktop 确认关窗后手机可完成连接；在手机完成 exchange 前旧会话继续有效。覆盖旧协议分支以避免误报授权。按 Cloud 正常流程发布，本项目未修改 Cloud 源码。
