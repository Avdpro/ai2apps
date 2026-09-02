# FLUX.2 Klein 4B 双源 Package 发布收据

日期：2026-08-27（Asia/Shanghai）

## 结果

`ai2apps/model-flux2-klein-mlx 0.1.3` 已升级为正式 Checkpoint Distribution 双源下载并
发布到 AI2Apps Cloud 生产 Registry。

本版本只声明已经完成 distribution 的 FLUX.2 Klein 4B；9B checkpoint 没有混入本次
release，避免 Package gate 出现未绑定权重。

| 项目 | 值 |
| --- | --- |
| Package | `ai2apps/model-flux2-klein-mlx` |
| Version | `0.1.3` |
| Distribution | `dist_ai2apps_flux2_klein_4b_e7b7dc27_v1` |
| Artifact SHA-256 | `13eaac8cf187408f7f3d8415f0036b4fb54a0c514f9ea61d33215a9654bc7b6f` |
| Artifact size | `18,999` bytes |
| Submission | `6da75551-1238-489b-9b6e-fabcca6d4133` |
| Review | `1c25b407-fb5a-4484-ae47-6868dd1ed636` |
| Publisher key | `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc` |
| Registry metadata version | `83` |

## 固定来源

- Hugging Face revision：Package 所绑定 distribution envelope 中的不可变 revision；
- ModelScope revision：`2bc2e0f64332317d1315dbc51d536f05b75df847`；
- 下载统一通过 `CheckpointAcquisitionService`，Models App 与 ACPF 不再各自解析 Hub 地址。

## 验证

- Package、checkpoint policy 和 image capability 共 14 项测试通过；
- 正式 production artifact 完成 Ed25519 签名、提交、审核和发布；
- 无 Cookie 公网 artifact 回读为 `18,999` bytes，SHA-256 与发布输入完全一致；
- 无 Cookie 公网 envelope 回读的 package/version、artifact digest/size、Publisher 和 key
  均与本收据一致。

本次读取 dev App scoped Cloud session Cookie 仅用于该 Package 的提交、审核、发布和最终
状态回读；Cookie 值没有输出或复制。最终 artifact/envelope 校验使用无 Cookie 公网路径。
