# AI2Apps Checkpoint Distribution 与 Package 批量升级记录（二）

日期：2026-08-27  
状态：**18 个 Checkpoint Distribution 与 12 个升级 Package 均已发布并完成公网回读**

## Checkpoint Distribution 结果

本批次发布以下 18 个不可变、逐文件和 8 MiB piece 校验的双源 distribution：

- `dist_ai2apps_punctuation_restorer_5cccf43a_v1`
- `dist_ai2apps_multilingual_e5_small_5030c762_v1`
- `dist_ai2apps_qwen3_asr_0_6b_4bit_313d8501_v1`
- `dist_ai2apps_vibevoice_realtime_0_5b_4bit_550877a1_v1`
- `dist_ai2apps_qwen2_5_0_5b_instruct_c89bee90_v1`
- `dist_ai2apps_qwen3_asr_0_6b_bf16_e8cb6ff5_v1`
- `dist_ai2apps_qwen3_vl_2b_instruct_89644892_v1`
- `dist_ai2apps_cosyvoice3_0_5b_4bit_55a6713d_v1`
- `dist_ai2apps_cosyvoice3_0_5b_8bit_177baf27_v1`
- `dist_ai2apps_s3tokenizer_v3_b143914b_v1`
- `dist_ai2apps_qwen3_tts_1_7b_custom_voice_8bit_41d3337e_v1`
- `dist_ai2apps_qwen3_tts_1_7b_base_5bit_18103d58_v1`
- `dist_ai2apps_qwen3_tts_1_7b_voice_design_5bit_6e936cfb_v1`
- `dist_ai2apps_qwen3_6_35b_a3b_4bit_38740b84_v1`
- `dist_ai2apps_z_image_turbo_f332072a_v1`
- `dist_ai2apps_flux2_klein_4b_e7b7dc27_v1`
- `dist_ai2apps_qwen3_5_2b_4bit_674aaa72_v1`
- `dist_ai2apps_qwen3_5_0_8b_4bit_da28692b_v1`

最终 Checkpoint Index 为版本 26。18 个 submission 均为 `published`，无 Cookie
公网验证全部返回 `envelopeExactJson: true`。用于 distribution 提交、审核、发布和
最终回读的 scoped Cloud Cookie 授权已在回读完成后失效。

## Package 构建收据

| Package | 版本 | Artifact SHA-256 | 字节数 |
| --- | --- | --- | ---: |
| `ai2apps/punctuation-restorer` | `0.1.1` | `efd5ee1e89159ad0b8829f945f1a68879e42b7339a292542df918a2fa84b2188` | 6,832 |
| `ai2apps/model-multilingual-e5-small` | `0.1.3` | `753b9c6c0154f956f0855cb81551b989127282aa747baebd8bee1a05a12932cd` | 8,180 |
| `ai2apps/model-qwen3-asr-06b` | `0.1.1` | `8cb8b226d06382cf7fe48de177b0c3d827ce632519e5ea05f4d2572d49bc6112` | 5,538 |
| `ai2apps/model-vibevoice-05b` | `0.1.1` | `74c020bdddbf9fa5476f25c96da0677b5164ca926774fee6b1582246d884bdbc` | 5,669 |
| `ai2apps/model-qwen25-0-5b-cuda` | `0.1.1` | `1f92c1d8af90c01a1fecfb0e346c3b4faac58dcf44ee498c67d5d9d1527820d5` | 6,810 |
| `ai2apps/model-qwen3-asr-0-6b-cuda` | `0.1.3` | `e76d1278822bdb84a0f7bc3a5a87e8128367e571c5a80ed6be55804d59aa4657` | 6,515 |
| `ai2apps/model-qwen3-vl-2b-cuda` | `0.1.1` | `c9ed8aa3be031f42e7ded7e1145fdc3bc40e7c3447c311c32c933d3822e3141a` | 6,496 |
| `ai2apps/model-cosyvoice3-05b` | `0.1.1` | `493223d9d79f32bee89e5c9413b87d54ace8e1e0605af99f78dffb5fd98eecbf` | 8,200 |
| `ai2apps/model-qwen3-tts-17b` | `0.1.1` | `f95c0f5701f3174bf64797f07033907c5a7b243102510d9d5d5db9c19f764a53` | 8,022 |
| `ai2apps/model-qwen36-35b` | `0.3.2` | `6c6561a6ec25ac2415d8dfe6b0ed0ea0ea212fc7f6d0fea24ce2f1b0e4b32c60` | 178,916 |
| `ai2apps/model-z-image-mlx` | `0.1.2` | `0976cbd864807cae3b855df2def7b24fd0e356a343235f8537fca3890fb9f518` | 17,093 |
| `ai2apps/model-qwen35` | `0.1.1` | `d3bb7dc555d3b01450e6999651426730e3621fa958702e3f5a1df3338693048b` | 8,121 |

制品目录：`/private/tmp/ai2apps-package-batch-2026-08-27-2/`。12 个 artifact
及其 detached envelope 已使用生产 Publisher key 完成密码学验证；archive 中没有
`.safetensors`、`.gguf`、`.onnx`、`.ckpt`、`.pt`、`.pth`、DMG 或 tar 权重载荷。

E5 和 Qwen35 已从旧式 service-only 源迁移为标准 Contract v1。Qwen35 的服务 ID
仍为 `ai2apps.qwen35`，标准 Registry Package ID 为 `ai2apps/model-qwen35`。

3 个 CUDA Package 的 Ubuntu 最低版本由发行版常用写法 `24.04` 规范化为 Contract
与 Cloud schema 接受的等价数字版本 `24.4`。首次提交在创建 submission 前即被 schema
拒绝；重新构建和签名后发布成功，没有残留 candidate。

## Cloud Package 发布收据

| Package / version | Submission ID | Review ID |
| --- | --- | --- |
| `ai2apps/punctuation-restorer 0.1.1` | `61651ea9-9641-415e-9a23-2717e8b53229` | `acfecdfb-0f08-48b2-a4e9-9640566f13ea` |
| `ai2apps/model-multilingual-e5-small 0.1.3` | `b43ec8d5-3698-4401-ad66-cadbd35c8d12` | `a9ec19a8-15fa-413a-be91-1694f8e04267` |
| `ai2apps/model-qwen3-asr-06b 0.1.1` | `eb63f677-c9cb-42a6-aa25-f45b7362446c` | `64df4a3a-eb21-4fae-843c-c3518669d7dc` |
| `ai2apps/model-vibevoice-05b 0.1.1` | `349a9ec9-5cc9-4093-ae00-426e9fed8354` | `bbf7ce6a-49c1-47a9-80b4-cd4e736d0104` |
| `ai2apps/model-qwen25-0-5b-cuda 0.1.1` | `5db9c5fe-004d-4add-a728-4ed14203d4cc` | `76e7c2d4-59b1-4734-bcb7-0fac9d67c9e4` |
| `ai2apps/model-qwen3-asr-0-6b-cuda 0.1.3` | `da10e3f4-92a2-4588-9a9a-31ad08c247ac` | `26872758-07a6-4566-a69c-4cc040ff3e12` |
| `ai2apps/model-qwen3-vl-2b-cuda 0.1.1` | `2684484a-b3f0-450f-b411-26f4df613f2e` | `b1fa93d6-b410-4c21-8c2e-7d36aebadfe2` |
| `ai2apps/model-cosyvoice3-05b 0.1.1` | `9802fa32-69d4-485a-b1dd-41cea55d94f4` | `e5e93b82-ca61-4540-add9-cc35bfbd7162` |
| `ai2apps/model-qwen3-tts-17b 0.1.1` | `e3593358-6f81-4e9b-ab68-f8329d60443a` | `cf538f5b-fd34-4ac1-8679-3c03052ecd82` |
| `ai2apps/model-qwen36-35b 0.3.2` | `1fefc818-54bb-436b-b82a-9144c45a0c5e` | `6347f9ec-771b-458f-8068-d27c6e8ae9d6` |
| `ai2apps/model-z-image-mlx 0.1.2` | `2f95dda7-dd49-41ee-91f0-c89e933f6c85` | `e79a30e1-e64a-4b95-9e38-9245b4f7765a` |
| `ai2apps/model-qwen35 0.1.1` | `24eb33e0-e3a0-407d-9bcd-7446848a7cab` | `e5dd82c4-718f-46cc-9d51-bb15b1d21d9e` |

最终 scoped Cookie 回读确认 12/12 为 `published`，artifact digest、Publisher
`229d6350-cd0e-408a-9905-41367385ae5c` 和 Publisher key
`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc` 全部精确匹配。回读完成后该次 Cookie 授权
立即失效。

无 Cookie 公网路径重新获取并验证了固定 Repository public key 和签名 Metadata；
最终 Repository Metadata 版本为 80，以上 12 个 release 全部可见且状态、digest、
Publisher 与 key 精确匹配。

## 暂不升级的 Package

- FLUX.2 Klein Package 同时包含 4B 与 9B 模型。4B distribution 已发布，但 9B
  运行内容为 52,888,738,257 字节，超过 50 GB 自动下载授权，因此整个 Package
  暂不绑定，避免产生同一 Package 内一半新机制、一半旧机制的状态。
- Fish S2 Pro 与 Ideogram 4 的运行文件已完成校验，但许可属于条件式再分发；Cloud
  当前只支持 `allowed`/`forbidden`，不能把条件式许可错误降级为无条件允许。Cloud
  需求见 `docs/ai2apps-conditional-checkpoint-redistribution-cloud-requirements-v1.md`。
- EchoMimic V3 当前没有可用的 ModelScope 镜像。

## 本地验证

- 最终组合回归：127 项通过；
- Ruff：通过；
- `git diff --check`：通过；
- 12 个 Package 签名 envelope：全部密码学验证通过；
- Package 内嵌模型权重审计：0 项。
