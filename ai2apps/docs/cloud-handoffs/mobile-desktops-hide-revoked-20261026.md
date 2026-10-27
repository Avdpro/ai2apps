# 我的 Desktop：隐藏已撤销设备

日期：2026-10-26

## 用户要求

手机“我的 Desktop”列表不显示已撤销设备，包括名为 `Revoked device` 的脱敏记录及仍保留原名称但 `reason=revoked` 的连接。正常离线、远程访问关闭、额度不足、待升级的设备继续显示其原因。

## 已确认的原因

Cloud `src/spaces/owner-home.ts` 的 `mobileDesktops()` 查询当前 Owner 的所有 remoteDevices；`mobileState()` 拒绝后仍将 `reason=revoked` 投影到 items。`src/spaces/mobile-account-page.ts` 遍历这些 items，为其绘制不可点击卡片。

## 实现要求

- `GET /v1/mobile/desktops` 不返回已撤销 Device，也不返回最终判定 `reason=revoked` 的项目；按状态/授权结果过滤，不按名称匹配。
- Cloud 页面可增加 `reason !== 'revoked'` 防御性过滤，避免旧响应显示这些项目。
- 保留数据库撤销记录、审计及 handoff/exchange 拒绝逻辑；隐藏不是删除或恢复授权。
- 全部项目已撤销时展示现有空列表提示。
- 精确选定 Device/Installation 已撤销时提示原选定设备不可用，不渲染卡片、不回退其他 Desktop。
- 保持 no-store、同源登录、Owner 隔离及退出后清理目录。

## 验收

1. 同账户含 active、offline、remote_disabled、quota_exceeded、upgrade_required、revoked 时，仅 revoked 不显示。
2. 脱敏名称及正常名称的 revoked 记录均隐藏；正常设备碰巧名为 Revoked device 仍按真实状态处理。
3. 全撤销目录返回 items:[]；直接访问旧精确入口无法创建交接。
4. 刷新、前后台恢复后撤销卡片消失；不影响其他有效设备与其他账户隔离。
5. 验证生产手机页面，回传去敏化计数和状态；不回传 Cookie 或 handoff。

客户端本轮仅调查并提交要求，未修改 Cloud 源码或部署。
