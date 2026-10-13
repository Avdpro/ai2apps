# H3 0.10.0 Cloud 发布状态恢复要求（已解除）

**2026-10-06 已解除**：旧候选经标准受保护流程撤回，accepted 原始字节正式发布；新 submission `1701c811-203a-469b-9227-b1a56f19b90e`，Snapshot 255，匿名下载验签通过。以下保留历史问题与恢复要求。

本仓库不修改 Cloud 代码。请 Cloud 项目定位并修复标准 Package 发布流程的错误恢复路径。

## 请求与证据

2026-10-05，Package `ai2apps/model-minimax-h3` / `0.10.0`，Publisher `229d6350-cd0e-408a-9905-41367385ae5c`，key `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`。

1. 旧 submission `32a6d1c0-acdc-44f5-bf09-54865f251a5b` 已审核 approved，publish 因 Base50 绑定 Turbo Distribution 而拒绝。错误已在修正版修复；旧制品禁止发布。
2. 标准 `--reject-submission` 返回 `only a review-pending release can receive a decision`，无法结束该未发布候选。
3. 修正版 SHA `5d87670df8f672497f6129c4c400428688dbed97447f74e56877255206cc05d9`，215634 bytes，签名、十模型 identity preflight、Runtime 1.8.8 真实安装/两个入口推理/重启/卸载/Mini-App 发现全部通过。
4. 标准 `scripts/publish_signed_registry_artifact.py` 提交修正版两次均返回 `An internal error occurred`；每次查询后均无此新摘要的提交。未改版本、Publisher、key，没有直写 Cloud 数据。

## Cloud 处理要求

- 按日期、Publisher、Package/version 和两份 SHA 关联服务日志，确认上传/唯一性约束/发布状态流转的实际失败点；不要把未知根因直接归为 Cookie 或管理员验证。
- 核查是否存在列表之外的部分提交或上传对象；有则提供可恢复的真实 submission ID。
- 提供受权限和审计保护的未发布候选撤回/替换或重新审核路径，保留旧提交历史；不得修改已发布版本的不可变性，不放宽模型身份校验，不直接改生产库绕过工作流。
- 修正版仍使用 `ai2apps/model-minimax-h3 0.10.0`，通过标准客户端入口重新提交/审核/发布。若需要新增 Local 脚本参数，提供正式 API 契约后在现有标准脚本中实现。
- 无法提交时返回明确可诊断的错误码、状态和 request ID，不能把常规状态冲突包装成笼统 internal_error。
- 加入回归：approved 候选 publish 校验失败 → 撤回/修正 → 同一未发布目标版本成功提交审核发布；已发布版本仍拒绝不同字节覆盖。

## 恢复验收

先查询列表。如有修正版 SHA 的 submission，使用它的 `--submission-id` 恢复；**不要恢复旧 SHA 的提交**。没有修正版提交时，使用已保存的 accepted 制品/envelope，不能重建换字节。发布后匿名 `RegistryPackageManager.download_verified` 验证 Repository Snapshot、Publisher 签名、完整 SHA/size，再启用 Host 的两个 H3 ACPF 入口。

精确本地制品、安装与查询回执位于 `artifacts/h3-avatar-20261005/release/accepted/`；完整回执见 `docs/ai2apps-h3-avatar-package-0.10.0-release.md`。不需要 Cookie/token 或私钥作为 Cloud 诊断材料。
