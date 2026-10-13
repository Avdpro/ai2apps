# H3 数字人 Package 0.10.0 验收与发布回执

日期：2026-10-05 验收，2026-10-06 正式发布。状态：**已正式发布，匿名完整下载与签名验证通过**。

## 可交付文件

- Package：`artifacts/h3-avatar-20261005/release/accepted/ai2apps-model-minimax-h3-0.10.0.ai2service`
- detached envelope：同名 `.envelope.json`。
- SHA-256：`5d87670df8f672497f6129c4c400428688dbed97447f74e56877255206cc05d9`
- 大小：215,634 字节。只含模型适配源码及说明，不含 Runtime 或 checkpoint。
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`；key：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`。
- Host 基线 commit：`fa377dcb62875d5c82fc8177afd4277cd2357db9`，有本次未提交改动；H3 源码位于 `/Users/avdpropang/sdk/minimaxh3/ai2apps-package`（非 Git checkout），由最终 Package 文件索引和签名固定。

## 功能与验证

新增 `avatar-lightx2v-4step-4bit`（1–60 秒）和 `avatar-base-4bit`（1–8 秒）。512²/24 fps 内部生成，Host 通用接口处理任意原图尺寸的裁剪回贴。推荐至少 64 GiB 内存，复用 Runtime >=1.8.8 <2，无需新 Runtime。Mini-App 源码无需模型专用修改；实际安装后通用发现和 source-canvas 规划通过。两个 ACPF 新安装入口已加入 Host 源码，Runtime >=1.8.8、Package >=0.10.0、最低 64 GiB；23 项 Host 回归通过。该 Host 配置随后续 Desktop 更新分发，本次未发布或重建 Desktop。现有 Mini-App 安装本模型 Package 后可通过通用模型发现使用两个入口。

H3 动作底片使用 latent 续接、原图末帧软约束与五帧解码 holdback；随后纯 MLX YuNet/BiSeNet 自动定位嘴部，MuseTalk 精修，保留原音轨。原生英文 H3 口型未达标，因此不会返回未经精修的中间底片。

- 60 秒 1440 帧：H3 1569.60 秒，精修 144.33 秒，合计 28.57 分钟；M5 Max/128 GiB，MLX peak 29.980 GB。视频与音轨 60.0 秒，PTS 误差零，四处 SyncNet offset -1 评估帧（40 ms）。末段亮度稳定。
- 最终签名归档真实安装：Base50 一秒音轨输出 24 帧，耗时 300.97 秒；Turbo 2.796 秒音轨输出 68 帧，耗时 78.42 秒。这是运行记录，Turbo 接在 Base50 后运行，不作为独立冷启动比较。
- Turbo 最终视频与此前精确测量的安装输出逐字节相同：SHA `90737b7dac7caf3ce7dba6c93c5566a1f250702a67245f533275c35aa408e643`，SyncNet -1 帧，confidence 5.526。
- 最终制品启动、health、两个模型实际推理、停止/重启/卸载、Mini-App 通用模型发现均通过。98 项定向回归通过。
- 仍有限制：正面无遮挡单人；嘴部可能柔化；静音段不保证完全闭嘴；尚不支持显式视线/情绪控制。

## 权重双源

HF `Avdpro/H3-Portrait-Refiner-MLX@b19653717a136186461fd1fa9ae7a6af000090a3`；ModelScope `ai2apps/H3-Portrait-Refiner-MLX@861f0228351bfd7a2ded792e791b25030f4f8710`。20 文件、184 pieces、1,536,290,232 字节双端完整回下载一致。

两个模型使用相同权重字节，但 Registry 要求模型身份各自绑定：

- Turbo Distribution `dist_ai2apps_h3_portrait_refiner_b1965371_v1`；submission `8426579e-27d0-438a-8ee2-140ffe09abd4`。
- Base50 Distribution `dist_ai2apps_h3_portrait_refiner_base_b1965371_v1`；submission `7f6f4c0c-b814-45ba-a150-4c9a49d56ff8`。

两者均已正式发布、匿名签名 Index 回读通过。全部十个模型的 model ID/repo/revision 对公开签名声明核验通过。H3 原有权重及其用户许可确认流程保持原约束。

## 已解除的 Cloud 发布阻塞（历史记录）

初版候选把 Base50 指向 Turbo 的 Distribution。Cloud 在 publish 阶段正确拒绝模型身份不匹配。已在本地修正，并重新构建/完整安装推理验收。旧提交 `32a6d1c0-acdc-44f5-bf09-54865f251a5b` 仍为 approved，**未发布**，旧 SHA 为 `4dd4d3cceacd410b6d1e5099c1422c0cbce28630198b91d77f90f2c7107e59f3`，不能恢复发布此旧制品。

标准脚本拒绝旧提交时，Cloud 返回 `only a review-pending release can receive a decision`。修正版使用原 Package ID/version/Publisher 提交，两次均返回 `An internal error occurred`。每次失败后查询列表，未出现修正版摘要的 submission。不能从笼统错误确定是同版本状态约束、存储还是其它服务端故障。

本次 Dev Cookie 读取已有明确授权，仅通过标准 `--browser-live` 使用，没有输出或保存 Cookie。尚未完成发布，不能标为 Discover 可安装。见 Cloud 交接文档。


## 2026-10-06 正式生产回执

Cloud OpenAPI 1.57.0 提供受保护撤回流程后，通过已授权 Dev 的标准发布脚本撤回旧候选并发布原始 accepted 字节，没有重建、换版本或重新签名。

- 新 submission：`1701c811-203a-469b-9227-b1a56f19b90e`，最终列表状态 `published`。
- 旧 submission：`32a6d1c0-acdc-44f5-bf09-54865f251a5b`，撤回成功，列表状态 `rejected`，保留历史。
- Repository Snapshot：**255**。匿名 `RegistryPackageManager.download_verified` 完整下载、仓库信任指纹、Publisher 签名、SHA-256、215634 字节全部匹配。
- Discover catalog 匿名回读已保存，与同一次验签回执一起归档。
- 正式制品和安装验收制品逐字节一致，因此沿用此前真实双入口推理、生命周期和 60 秒质量证据，本轮未重复运行模型推理。
- Package 为约 216 KB 的 Cloud 制品；大型 checkpoint 保持 Hugging Face / ModelScope 固定双源。Runtime 仍为独立依赖，无需专用数字人 Runtime。
- Host 两个 ACPF 选项已接入源码，23 项回归和 scoped diff check 通过；不声称旧版 Desktop 已含新增 ACPF 配置。
- 发布材料：`artifacts/h3-avatar-20261005/release/accepted/h3-withdrawal.json`、`h3-production-publication.json`、`h3-production-final-list.json`、`public-verification.json`。

本次发布完成，Cookie 读取授权随之结束。
