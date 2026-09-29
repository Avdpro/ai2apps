# AI2Apps oMLX Runtime 1.7.13 发布收据

状态：Cloud 已发布；Cloud、GitHub、ModelScope 三源均已激活，匿名完整下载、Repository
Snapshot 与 Publisher 签名验证通过。

- Package：`ai2apps/runtime-omlx 1.7.13`
- 修复：DeepSeek V4.1 Flash 长 Decode 的 Metal lazy graph 资源无界累积，以及 Model Worker
  流式异常/取消被误记为成功。
- Apple 公证：`d050cb53-f97c-4deb-b307-35fe3ee63526`，`Accepted`。
- 正式 DMG：383,545,630 bytes，SHA-256
  `7b76285b30d8aa5acfe26aa81e21b3feb89ed4b22e2ffe208dcf6592efe2223c`。
- 正式 Package：380,848,221 bytes，SHA-256
  `ffc0718fc7c65c47f74b4a933d4b995b1a98489521cad40fce02224be3aca7ac`。

## 实现与验证

DeepSeek V4.1 resident bank 在既有 token logits materialization 边界一并 materialize cache
counters/ages，并清除已经完成的专家输出引用。该边界没有增加 GPU→CPU 同步次数或 router
readback。Model Worker 只在生成流完整消费后标记成功；异常和取消分别传播为 `failed` 与
`cancelled`，DeepSeek V4.1 达到 token 上限时报告 `finish_reason=length`。

- 149 项 Runtime、DeepSeek V4.1、Worker、Cached-MoE 与 Package 定向测试通过。
- 真实共享 SSD checkpoint 完成 12,000 token 强制 Decode，10.365 token/s；Metal active
  仅增加 3,100,812 bytes，pending output 始终为 0，随后第二次短请求正常完成。
- 480,000 次 layer decision 中 89.788% all-hit；修复保持原有 L0/L1 与 router 路径。
- 正式签名 Package 在全新隔离 Platform 根目录安装成功，DeepSeek V4.1 模型 Package
  0.1.0 精确锁定 Runtime 1.7.13，managed Worker 状态为 `running`。
- DMG 深层签名、staple、Gatekeeper、CPython 3.11、MLX 0.32.0 和原生
  `preadv_fused_experts` 探针通过。

## Registry 与多源

- Cloud submission：`480c75c6-a842-4b7a-a09c-864388bd123a`，`published`。
- GitHub tag：`package-runtime-omlx-v1.7.13`；Source
  `src_fc36830d-0682-48a1-bd2c-340746989050`，validation
  `val_5b01ccae-ac0c-4d52-9ce8-3f6b3dae12b5`，digest
  `2024c297c8afb60406dfac6735d6d706ce7194c7ff9207bc47486b71909a18ad`。
- ModelScope revision：`f3c677dabb73dfc0c00b3fb6ec1f3a8631e1bd27`；Source
  `src_093bfaf8-b24d-4571-bb0a-4982ed447a6d`，validation
  `val_b7358c9f-1271-4139-9ddb-2c25cd6c8a8b`，digest
  `8782ceeb10015e766e5a80cc65dd2ca4d39b891a691fce10428e6c0803c91552`。
- Cloud 对两个外部源分别完成完整 SHA/size、46-piece manifest 与 49 次 Range 校验。
  GitHub 使用标准 HTTP 206；ModelScope 使用严格 HTTP 200 加精确 `Content-Range`。
- 最终 Source revision / ETag：6 / `"sources-6"`；Repository metadata：208；Snapshot
  digest：`5d5039fb63ff3e7de23e5676ea5828ff1f2fef0d4cab43de78f8a061c66bc8c6`。
- 全新匿名缓存验证得到 `artifactExactBytes=true`、`envelopeExactJson=true`。

## 发布边界

checkpoint、DeepSeek V4.1 模型权重和模型 Package 均未改变。现有模型 Package 依赖范围允许
安装 Runtime 1.7.13，但已经固定在旧 Runtime 的设备不会仅因本次 Runtime 发布自动升级；
如需 ACPF 主动修复既有安装，后续应发布仅提高最低 Runtime 到 1.7.13 的模型 Package。
Chat 对异常 EOF 的 UI 防御属于 Desktop 静态前端，仍由下一版 Desktop Release 纳入。
