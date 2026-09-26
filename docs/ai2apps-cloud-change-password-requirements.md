# Account：验证旧密码后修改密码

日期：2026-09-25。客户端已接入；Cloud 项目已完成生产部署，OpenAPI 1.52.0。
本仓库未修改 Cloud 代码。当前剩余工作为固定 App-Dev 可见 UI 联调。
已核对 Cloud 对接合同 `ai2apps-cloud/docs/change-password-v1.md` 与生产回执
`ai2apps-cloud/docs/change-password-production-2026-09-25.md`，以下客户端合同保持兼容。

新增 `POST /v1/auth/password/change`，使用当前浏览器 Cloud 登录会话。
请求：`{"currentPassword":"旧密码","newPassword":"新密码"}`。
目标用户只由登录会话确定，不接受 email/userId 指定别的账户；普通已登录用户均可操作，
不要求管理员身份。确认新密码由客户端比对，不发送、不存储。

Cloud 必须验证当前密码的 Argon2id verifier，新密码使用现有 8–128 UTF-8 字节规则，
禁止与旧密码相同。不裁剪或归一化密码。旧密码错误返回 400/CURRENT_PASSWORD_INVALID，
相同密码返回 400/PASSWORD_UNCHANGED，未登录返回 401/AUTHENTICATION_REQUIRED；
限速返回 429/RATE_LIMITED。失败不修改密码、不吊销会话。

成功以事务方式替换 verifier 并吊销该用户所有登录会话（含当前会话）、管理员二次验证授权
和未消费的密码重置挑战，防止旧授权继续使用；结合现有机制处理竞争更新，避免旧密码并发覆盖。
返回 200 `{"changed":true,"reauthenticationRequired":true}`，清除当前会话 Cookie。
不得删除用户 Device/Installation 绑定或账户数据；凭据类别边界沿用现有密码重置设计并说明。
写无秘密的安全审计；不得记录密码、请求体、凭据或 verifier。按账户及来源限速，复用现有
同源/CSRF 防护。不用登录接口“试旧密码”后调用无授权更新接口。

Local 转发使用当前浏览器 Cloud 会话，成功清除其本地会话缓存；404/405 转为
PASSWORD_CHANGE_UNAVAILABLE，界面提示服务尚未开放。客户端显示三栏：旧密码、新密码、
确认新密码；成功返回登录界面。失败清空字段，校验不一致不提交。

验收：普通用户成功修改，旧密码不能再登录；错误旧密码、未登录、相同密码、UTF-8 边界、
限速、跨账户请求、并发修改、旧会话/旧挑战吊销均覆盖；失败不影响当前登录。
Cloud 部署后，在固定 App-Dev 用专用测试账户进行端到端验收，不修改真实用户密码。
