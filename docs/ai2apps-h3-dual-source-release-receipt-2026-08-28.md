# AI2Apps MiniMax H3 双源 Checkpoint 与 Package 发布收据

日期：2026-08-28  
状态：四个 Checkpoint Distribution 与 `ai2apps/model-minimax-h3 0.8.1` 均已发布并完成匿名公网回读

## Checkpoint Distribution

| 模型 | Distribution ID | Manifest digest | 文件 | 8 MiB pieces | 字节数 | Submission / Review |
| --- | --- | --- | ---: | ---: | ---: | --- |
| FL2VA Q8 | `dist_ai2apps_minimax_h3_fl2va_8bit_64314cde_v1` | `sha256:818a5b5e14283c96449a0395df225b9d117daa83353fd87aba440695d2458efd` | 14 | 8,354 | 70,076,151,074 | `b0cc5452-bd7d-406f-bba2-1eff8164ee1b` / `ae3fb515-4431-4148-9963-16332fa9ec4b` |
| FL2VA Q4 | `dist_ai2apps_minimax_h3_fl2va_4bit_9c927357_v1` | `sha256:2b69def85326591ae982acec40ee55aed706ebf1d354252acb300cb05630ad60` | 14 | 4,901 | 41,108,034,229 | `7fc1294a-3307-4681-b120-2004a9afe7f0` / `d7ee9fd4-e3fd-42fe-8a4e-ff0579115075` |
| Ref2VA Q8 | `dist_ai2apps_minimax_h3_ref2va_8bit_407a9355_v1` | `sha256:03041c64a05869e6b06a777f84f5b9dc2d9978b35e35d17686c9d865714f2ed8` | 13 | 8,261 | 69,296,300,385 | `b5c165b7-70b3-4e00-8ad4-8fcc7efedfd3` / `0de01984-7e27-4e12-86fd-6d6688905b3b` |
| Ref2VA Q4 | `dist_ai2apps_minimax_h3_ref2va_4bit_e038bfbe_v1` | `sha256:6a9b08031557c44f03439229a111775f53346c418551723f0abf87fa9f03842a` | 13 | 4,886 | 40,984,387,696 | `5609b329-1769-47fa-a45a-c614eda17648` / `449ba68d-42bc-404a-8d15-253108541971` |

四份 envelope 均由 `ai2apps-local/checkpoint-metadata-verified-v1` 构建：从本地已有的固定 Hugging Face 等价快照计算逐文件 SHA-256 和全局 piece hashes，再与以下 ModelScope 固定 commit 的完整文件元数据核对，不重复下载第二份权重：

- FL2VA Q8：`7b409aac5b5f00e64eeb48799ca80d4c6943ba69`
- FL2VA Q4：`3c042201396f296a52ec4b8c7a9e660239706233`
- Ref2VA Q8：`a63db4762ec4252788a9138d226850edc1744872`
- Ref2VA Q4：`f9d384f9b78788c72b79b812f975f00157fc1b75`

许可策略为 `conditional`，P2P 禁用。下载前必须展示 MiniMax H3 Community License 条款和 URL，并要求用户确认其位于许可定义的 Applicable Territory 且接受条款，或已经取得 MiniMax 的单独书面许可。许可文件与 NOTICE 均属于校验清单。

最终 Checkpoint Index 版本为 `33`。四份 distribution 的匿名公网回读均返回 `envelopeExactJson: true`。

## Package 0.8.1

- Package：`ai2apps/model-minimax-h3`
- Version：`0.8.1`
- Artifact：`/Users/avdpropang/sdk/minimaxh3/ai2apps-package/dist/ai2apps-model-minimax-h3-0.8.1-production.ai2service`
- Artifact SHA-256：`17de861817401e75011b1139ac670acaadf7f268a8664699bdd80b4b22591889`
- Artifact size：`108326` bytes
- Submission ID：`d847f1e6-c122-4dc4-b37a-8885bcdd8165`
- Review ID：`f1472ad0-815d-431a-860f-8ac4f75b5c96`
- Repository Metadata version：`86`

Package 保留四个已验证的 Q8/Q4 FL2VA/Ref2VA 模型，全部绑定已发布 distribution。仍存在 MLX 推理问题且没有双源 distribution 的 BF16 条目在 0.8.1 中暂时移除；Worker 默认模型调整为 FL2VA Q4。BF16 修复并完成双源后才能在后续版本恢复。

Package archive 不含 checkpoint、旧 `dist/` 内容或私钥。公网 catalog 的 latest version 为 `0.8.1` 且状态为 `published`；公网 artifact 与本地 artifact 逐字节一致，公网 envelope 与本地 envelope 的 canonical JSON 完全一致。

## 验证

- H3 Worker 与 Checkpoint Package Policy：`15 passed`
- YAML/JSON 解析：通过
- 四个 Package 模型均声明真实、已发布的 `weights.distribution_id`
- Archive checkpoint/private-key 审计：0 项
- 匿名公网 Checkpoint Index、四份 distribution、Package catalog、artifact 与 envelope 回读：通过

scoped Cloud Cookie 仅用于本次四个 H3 distribution 与 `ai2apps/model-minimax-h3 0.8.1` 的提交、审核和发布；最终验证使用匿名公网路径。
