# Qwen3.8 Flash Next 4-bit：Checkpoint 上传与 Package 发布交接

日期：2026-08-29  
仓库：`/Users/avdpropang/sdk/omlx-moe-cache`  
分支：`experiment/moe-cache`

## 1. 任务目标

将 Qwen3.8 Flash Next MLX 4-bit checkpoint 建立为 Hugging Face / ModelScope
逐文件字节一致的双源分发，发布对应的 AI2Apps checkpoint distribution，然后构建、
签署、发布并验收以下模型 Package：

- Package ID：`ai2apps/model-qwen38-flash-next-4bit`
- Package version：`0.1.0`
- 模型服务 ID：`ai2apps.model.qwen38-flash-next-4bit`
- 模型 ID：`ai2apps.model.qwen38-flash-next-4bit/qwen3.8-flash-next-mlx-4bit`
- Runtime dependency：`ai2apps/runtime-omlx >=1.5.5 <2.0.0`

本任务的最终完成条件不是“命令执行成功”，而是 distribution 和 Package 都已正式发布、
匿名公网回读成功，并在干净实例完成安装及至少一次真实图文推理。

## 2. 不要重做 Runtime

`ai2apps/runtime-omlx 1.5.5` 已完成构建、公证、staple、发布和匿名验证，且包含本模型所需的
Qwen4-Exp、VLM Worker 与 Direct-L1 支持。本任务直接依赖该正式版本，不重新构建或发布 Runtime。

已验收信息：

- Apple notarization submission：`15a43f0a-5611-49fd-828c-e330127acde8`，Accepted
- Runtime Cloud submission：`cc169ff9-3e1c-4ed6-98ae-dd26efe63327`
- Runtime review：`75a414ea-f432-40b3-8135-57b5cd2fe2e4`
- Runtime DMG SHA-256：`b89ebaa5b95098f915b3277f9310845e881e441763ac749f279ccfb27afb323e`
- Runtime Package SHA-256：`41199ca4570bd4e62c3b9a6a11df592a91aa6c25d95536007eabefe3cb5b7784`
- Runtime Package size：`457169108` bytes
- Registry metadata version：`89`

此前针对 Runtime 的 Cookie 与 Publisher key 使用授权均已随该发布结束而失效，不能用于本任务。

## 3. 当前状态与唯一主要阻塞

### 3.1 已完成

模型 Package 源码已建立：

```text
packages/omlx-model-qwen38-flash-next-4bit/
```

其中已经包含：

- `ai2apps.json`
- `service.yaml`
- `META/sbom.spdx.json`
- `META/checkpoint-distribution.json`
- `release-checkpoints.json`
- `src/worker_adapter.py`
- Qwen4-Exp adapter
- 十类 Scope profile 与 Scope pack
- README、license/source 元数据和 Python package metadata

本地 HF checkpoint 已完整下载：

```text
/Users/avdpropang/.omlx/models/Vontra/Qwen3.8-Flash-Next-MLX-4bit
```

当前 distribution 选中的 33 个文件全部存在，总字节数：

```text
111601662416 bytes
```

本地 Package 相关测试此前通过 29 项，Worker adapter 测试通过 3 项。ModelScope revision
写入及最终构建后必须重新执行测试，不能直接沿用这些结果作为最终验收。

### 3.2 当前阻塞

ModelScope 尚无这个 checkpoint 的逐字节一致镜像。已检查
`Vontra/Qwen3.8-Flash-Next-MLX-4bit`，ModelScope API 返回 404，也未找到其他可验证的精确镜像。

建议创建：

```text
ai2apps/Qwen3.8-Flash-Next-MLX-4bit
```

必须上传 distribution spec 选中的原始 33 个文件，禁止重新量化、重新序列化、改写 JSON、
改变换行、增删 metadata 或对 safetensors 做任何转换。上传后必须取得不可变 ModelScope
revision；不得把 `master` 当成正式 revision。

## 4. 固定的模型与 Distribution 输入

Hugging Face：

- Repo：`Vontra/Qwen3.8-Flash-Next-MLX-4bit`
- Immutable revision：`de597762aa61387c89590a46582222a261ce0387`
- 本地 pinned snapshot：
  `/Users/avdpropang/.omlx/models/Vontra/Qwen3.8-Flash-Next-MLX-4bit`

Checkpoint distribution：

- Distribution ID：`dist_ai2apps_qwen38_flash_next_4bit_de597762_v1`
- Spec：
  `packages/omlx-model-qwen38-flash-next-4bit/META/checkpoint-distribution.json`
- 格式：Safetensors，4-bit
- Shards：22
- 选中文件：33
- 精确总大小：`111601662416` bytes
- Piece size：`8388608` bytes

License：

- Qwen Community License 1.0
- 本地 LICENSE SHA-256：
  `a0dc422560841fd68e06d974907f8b4c709bca44a67daad2b528437bdf676c08`
- License 包含与商业 AI Work Assistant / MaaS 有关的条款；Package 不内嵌模型权重，
  安装流程必须通过 distribution metadata 展示并取得相应许可同意。

Scope profile：

- 源文件：`benchmarks/results/qwen38_next/scope-ten-runtime-top224-v1.json`
- Package 文件：
  `packages/omlx-model-qwen38-flash-next-4bit/src/omlx_model_qwen38_flash_next_4bit/assets/scope-profile.json`
- SHA-256：`690afb37b6b2c1a607091aae4f5c733582a7d25cffa90eabbe928bf6914b9fa0`
- Size：`1218186` bytes
- Profile：48 层、512 experts、capacity 224、10 scopes
- Scopes：`business_finance`、`coding`、`data_ai`、`general`、
  `humanities_social`、`legal_policy`、`math_logic`、`medical_health`、
  `science_engineering`、`writing_creative`

运行策略：

- Family：`qwen4_exp`
- Conversion：`qwen4-exp-affine-q4-gate-up-fused-v1`
- Hot：10
- Lean：Top128，预计约 41 GB
- Balanced：Top160，预计约 44 GB
- Performance：Top224，预计约 50 GB
- 默认 Scope：`general`
- 默认 Boost：关闭，即 natural/full-quality
- 支持：`cached`、`full`
- 模型类型：VLM
- 能力：`work`、`conversation`、`image_recognition`

## 5. 强制遵循的发布边界

开始工作前完整阅读：

- 仓库根目录 `AGENTS.md`
- `docs/ai2apps-package-publication-runbook.md`

仅使用仓库标准发布实现：

- `scripts/build_checkpoint_distribution.py`
- `scripts/publish_checkpoint_distribution.py`
- `scripts/verify_checkpoint_distribution_publication.py`
- `scripts/build_signed_registry_release.py`
- `scripts/publish_signed_registry_artifact.py`

禁止：

- 用浏览器自动化代替标准发布脚本；
- 临时 `curl` Cloud API、直接修改 Cloud 数据库或另写发布实现；
- 将 checkpoint 打入 `.ai2service`；
- 为绕过失败更换 Package ID、版本、Publisher 或 Publisher key；
- 在聊天、文档、命令行或日志中输出 Cookie、Cloud token、私钥内容；
- 扫描或尝试多个 `cookies.sqlite`；
- 已经产生 submission 后重复 submit；
- 清理或重置当前脏工作树中的用户改动；
- 修改 sibling DMoE checkout。

当前工作树有其他未提交改动。只处理本任务范围内文件，不要执行 `git reset --hard`、
`git checkout --` 或批量清理。

## 6. 执行步骤

### 步骤 A：建立 ModelScope 字节一致镜像

1. 读取 distribution spec 的 `includePatterns`，只上传其中 33 个文件。
2. 使用 ModelScope 官方上传机制将这些本地原始文件上传至
   `ai2apps/Qwen3.8-Flash-Next-MLX-4bit`。
3. 上传过程不得对文件做转换或规范化。
4. 发布 ModelScope revision 并记录不可变 revision ID。
5. 从 ModelScope 权威文件清单确认文件集合、逐文件 size 和 SHA-256 均可读取。
6. 如 ModelScope metadata 缺少任一文件 SHA-256，必须准备完整的 pinned MS snapshot，
   后续改用 `full_dual_download`，不能降低验证强度。

### 步骤 B：把 ModelScope 固定 revision 写入 spec

使用 `apply_patch` 在 `sourceRepositories` 中保留现有 HF 项，并新增：

```json
{
  "type": "modelscope",
  "repoId": "ai2apps/Qwen3.8-Flash-Next-MLX-4bit",
  "revision": "<IMMUTABLE_MODELSCOPE_REVISION>",
  "access": "public_anonymous"
}
```

不要修改现有 distribution ID、HF revision、license hash、piece size 或 include patterns，
除非发现有可证明的源数据错误；这种情况应先停止并报告。

### 步骤 C：生成和签署 checkpoint distribution

先从当前 AI2Apps bootstrap 重新发现 `BASE_PATH` 与公开的
`SECURITY_INSTANCE_ID`。不要照抄旧实例 ID。确认没有相同 distribution 的进行中 submission。

现有正式 Publisher 公共身份为：

- Publisher ID：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Cloud 公钥指纹 SHA-256：
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

在读取或使用既有 Publisher secret 前，必须让用户针对本 distribution/Package 重新明确授权。
只先计算公开指纹；只有本机 secret 的公开指纹与上述正式 Cloud 指纹完全相同才可签署。
不得输出或保存私钥。

推荐输出路径：

```text
packages/omlx-model-qwen38-flash-next-4bit/dist/
  dist_ai2apps_qwen38_flash_next_4bit_de597762_v1.envelope.json
  dist_ai2apps_qwen38_flash_next_4bit_de597762_v1.envelope.verification.json
```

ModelScope metadata 含完整 SHA-256 时：

```bash
./.venv/bin/python scripts/build_checkpoint_distribution.py \
  --spec packages/omlx-model-qwen38-flash-next-4bit/META/checkpoint-distribution.json \
  --huggingface-root /Users/avdpropang/.omlx/models/Vontra/Qwen3.8-Flash-Next-MLX-4bit \
  --output packages/omlx-model-qwen38-flash-next-4bit/dist/dist_ai2apps_qwen38_flash_next_4bit_de597762_v1.envelope.json \
  --publisher-id "$PUBLISHER_ID" \
  --publisher-key-id "$PUBLISHER_KEY_ID" \
  --keychain-secret "$PUBLISHER_KEY_SECRET" \
  --keychain-namespace "$KEYCHAIN_NAMESPACE"
```

ModelScope metadata 不完整时，按 runbook 使用：

```bash
./.venv/bin/python scripts/build_checkpoint_distribution.py \
  --verification-mode full_dual_download \
  --spec packages/omlx-model-qwen38-flash-next-4bit/META/checkpoint-distribution.json \
  --huggingface-root /Users/avdpropang/.omlx/models/Vontra/Qwen3.8-Flash-Next-MLX-4bit \
  --modelscope-root /absolute/path/to/pinned-ms-snapshot \
  --output packages/omlx-model-qwen38-flash-next-4bit/dist/dist_ai2apps_qwen38_flash_next_4bit_de597762_v1.envelope.json \
  --publisher-id "$PUBLISHER_ID" \
  --publisher-key-id "$PUBLISHER_KEY_ID" \
  --keychain-secret "$PUBLISHER_KEY_SECRET" \
  --keychain-namespace "$KEYCHAIN_NAMESPACE"
```

检查 verification receipt 至少记录并符合：

- distribution ID 正确；
- 文件数 `33`；
- 总字节数 `111601662416`；
- HF/MS 选中文件集合、size 与逐文件 SHA-256 一致；
- builder ID 正确反映 `metadata_verified` 或 `full_dual_download`；
- manifest digest、piece 数和签名完整。

### 步骤 D：发布并匿名验证 checkpoint distribution

优先使用 Installation Cloud session：

```bash
./.venv/bin/python scripts/publish_checkpoint_distribution.py \
  --base-path "$BASE_PATH" \
  --security-instance-id "$SECURITY_INSTANCE_ID" \
  --envelope packages/omlx-model-qwen38-flash-next-4bit/dist/dist_ai2apps_qwen38_flash_next_4bit_de597762_v1.envelope.json \
  --verification-receipt packages/omlx-model-qwen38-flash-next-4bit/dist/dist_ai2apps_qwen38_flash_next_4bit_de597762_v1.envelope.verification.json \
  --request-review
```

随后严格按脚本 `--help` 和 runbook 使用 `--list-review`、`--submission-id`、
`--decision approved` 与 `--publish` 完成审核和发布。任何阶段失败时保留 submission ID 并恢复，
禁止重新提交同一 envelope。

用不带用户 Cookie 的干净缓存匿名回读：

```bash
VERIFY_CACHE="$(mktemp -d /private/tmp/qwen38-distribution-verify.XXXXXX)"
./.venv/bin/python scripts/verify_checkpoint_distribution_publication.py \
  --distribution-id dist_ai2apps_qwen38_flash_next_4bit_de597762_v1 \
  --envelope packages/omlx-model-qwen38-flash-next-4bit/dist/dist_ai2apps_qwen38_flash_next_4bit_de597762_v1.envelope.json \
  --cache-root "$VERIFY_CACHE"
```

只有公网 distribution endpoint 可读、签名 Index 已包含它且匿名验证通过后，才能进入模型
Package 构建。

### 步骤 E：最终检查与构建模型 Package

重新运行至少以下测试：

```bash
./.venv/bin/python -m pytest -q \
  tests/test_ai2apps_package_contract_v1.py \
  tests/test_inference_runtime_package.py \
  tests/test_ai2apps_scope_pack.py \
  tests/test_checkpoint_package_policy.py
```

再运行与 `packages/omlx-model-qwen38-flash-next-4bit` adapter、Qwen4-Exp、VLM 和图片多轮
对话相关的定向测试。若仓库已有新的专用测试，必须一并执行。

构建：

```bash
./.venv/bin/python scripts/build_signed_registry_release.py \
  --source packages/omlx-model-qwen38-flash-next-4bit \
  --output packages/omlx-model-qwen38-flash-next-4bit/dist/omlx-model-qwen38-flash-next-4bit-0.1.0-production.ai2service \
  --publisher-id "$PUBLISHER_ID" \
  --publisher-key-id "$PUBLISHER_KEY_ID" \
  --keychain-secret "$PUBLISHER_KEY_SECRET" \
  --keychain-namespace "$KEYCHAIN_NAMESPACE"
```

构建后检查：

- `.ai2service` 与 detached envelope 同时存在；
- 记录 artifact SHA-256、size、Package ID 与 version；
- ZIP 内容不含 safetensors、checkpoint snapshot、缓存或其他模型权重；
- `weights.distribution_id` 是已发布的真实 distribution ID；
- Runtime dependency 仍为 `>=1.5.5 <2.0.0`；
- Package 默认不启用 Boost；
- VLM/image recognition 与十个 Scope profile 均在 artifact 中；
- SBOM、license、source revision、平台和 macOS 最低版本正确；
- `git diff --check` 通过。

### 步骤 F：发布模型 Package 0.1.0

先用标准脚本查询 Publisher、key 状态和已有 submission。确认本机既有 Publisher key 的
公开指纹与 Cloud 正式指纹完全一致；不得仅比较 key ID。

如果 Installation Cloud session 足够，则无需读取 Cookie。若标准脚本确认必须使用当前管理员
浏览器会话，先让用户在 **Account → Security → Administrator verification** 中自行完成验证；
Agent 不询问、不读取、不代输管理员密码。随后必须取得本次精确授权：

> 允许读取当前 AI2Apps dev 会话 Cookie，仅用于发布 ai2apps/model-qwen38-flash-next-4bit 0.1.0。

授权后只确认当前实例正在使用的唯一准确 profile，并把该 profile 的 `cookies.sqlite` 路径
传给标准脚本。不得复制、导出、打印 Cookie，不得试探其他 profile。该授权在此 Package 发布
完成后立即失效。

使用：

```bash
./.venv/bin/python scripts/publish_signed_registry_artifact.py \
  --base-path "$BASE_PATH" \
  --security-instance-id "$SECURITY_INSTANCE_ID" \
  --artifact packages/omlx-model-qwen38-flash-next-4bit/dist/omlx-model-qwen38-flash-next-4bit-0.1.0-production.ai2service \
  --envelope packages/omlx-model-qwen38-flash-next-4bit/dist/omlx-model-qwen38-flash-next-4bit-0.1.0-production.ai2service.envelope.json \
  --review-note "Verified Qwen3.8 Flash Next 4-bit Package Contract, checkpoint distribution, signature, tests, and release metadata."
```

只有确实需要且已获得上述授权时才增加：

```text
--browser-cookie-db /absolute/path/to/current/profile/cookies.sqlite
```

若提交后审核或发布失败，先 `--list-only` 查出 Package/version 的现有 submission ID，然后用
`--submission-id` 恢复；不得重新提交 artifact。

### 步骤 G：发布后验收

1. `--list-only` 确认 Package submission 为 published。
2. 匿名公共 catalog 确认 Package latest 为 `0.1.0`，digest/size 与本地 artifact 一致。
3. 确认 distribution 可匿名读取，HF/MS revision 都是不可变 revision。
4. 在干净、受支持的实例安装 Package。
5. 验证 Runtime 1.5.5 dependency 自动解析。
6. 验证用户 license/audit 批准流程。
7. 至少完成一次 ModelScope-only checkpoint 安装：断点续传、piece/file hash、snapshot 激活。
8. 验证 Worker startup、readiness、health、stop、restart、uninstall。
9. 完成一次纯文本推理和一次图片多轮对话推理；默认 Boost 必须为关闭状态。
10. 记录实际内存峰值、Prefill TPS、Decode TPS 和所用 Top/Hot/Scope 配置，作为 Package 0.1.0
    的安装后基线，不要求借发布机会改动已冻结的优化策略。

## 7. 最终发布收据

在 `docs/` 下新增带日期的 release receipt，至少记录：

- source commit 与工作树范围说明；
- HF repo/revision；
- ModelScope repo/revision；
- 33 个文件、总字节数、verification mode；
- distribution ID、manifest digest、piece 数；
- distribution submission/review/publish ID 与匿名验证结果；
- Package ID/version；
- artifact SHA-256/size；
- Publisher ID、Publisher key ID、匹配后的公开指纹；
- Package submission/review/publish ID；
- 公网 catalog 回读结果；
- 干净安装、MS-only 下载、Worker 生命周期、文本与图文推理结果；
- 测试命令与通过数量；
- Cookie 授权已失效的声明。

收据中不得出现 Cookie、token、私钥、管理员密码或 SecretBackend 中的秘密内容。

## 8. 完成判定清单

- [ ] ModelScope 精确镜像存在，并固定不可变 revision
- [ ] HF/MS 33 个选中文件逐文件 SHA-256 和 size 完全一致
- [ ] 精确总大小为 `111601662416` bytes
- [ ] checkpoint distribution 已签署、发布并匿名验证
- [ ] 模型 Package 不含 checkpoint 权重
- [ ] 模型 Package 构建测试和审计通过
- [ ] Runtime dependency 正确解析到已发布的 1.5.5
- [ ] `ai2apps/model-qwen38-flash-next-4bit 0.1.0` 已发布
- [ ] 公共 catalog 的 digest/size 与本地产物一致
- [ ] 干净实例完成 ModelScope-only 安装与断点/哈希验证
- [ ] 文本和图片多轮对话真实推理通过
- [ ] 最终 release receipt 已保存且不含任何秘密

全部项目完成后才可报告本交接任务完成。
