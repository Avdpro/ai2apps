# AI2Apps Core 设备管理：Cloud 补充工作

状态：Cloud 已完成，Local 已接入设备列表、改名和撤销
日期：2026-08-16

## 已复用的 Cloud 能力

- `GET /v1/remote/devices`：列出当前 Core 账户拥有的全部设备；
- `GET /v1/installations`：把 `cloudDeviceId` 映射到 `installationId`；
- `POST /v1/owner-reauth/grants`：签发 `installation.revoke` 一次性授权；
- `POST /v1/remote/devices/{deviceId}/revoke`：永久撤销设备并释放 Core 设备名额。

Local Account App 不保存 Owner 密码或一次性 grant。撤销当前设备后，Local 会立即停止
远程连接、撤销本地成员登录 Session，并把 Installation 标记为 `revoked`。

## CLOUD-012：设备改名（已完成）

Cloud 已提供：

```http
PATCH /v1/remote/devices/{deviceId}
Content-Type: application/json

{"displayName":"Living Room Mac"}
```

已核对的契约：

- 只有设备所属 Core 账户可以修改；
- `displayName` 去除首尾空白后长度为 1～120；
- 只修改展示名称，不改变 Installation、credential、access epoch、URL 或容量占用；
- 返回更新后的完整 `RemoteDevice`；
- 写入不含密码、credential 和旧名称正文之外秘密的审计事件；
- 稳定错误至少包括 `REMOTE_DEVICE_NOT_FOUND`、`INVALID_REQUEST`；
- 更新 OpenAPI、客户端对接文档和 IDOR 测试。

Local 已在 Core devices 表格中加入内联改名，并直接使用成功响应替换 Cloud 投影，不保存
本地名称副本。
