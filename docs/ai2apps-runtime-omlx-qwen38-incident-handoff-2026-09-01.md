# AI2Apps oMLX Runtime 1.5.6 / Qwen3.8 Cached-MoE 故障与升级交接

日期：2026-09-01  
仓库：`/Users/avdpropang/sdk/omlx-moe-cache`  
目标负责人：AI2Apps oMLX Runtime 构建、签名与发布维护者  
受影响 Runtime：`ai2apps/runtime-omlx 1.5.6`  
建议修复版本：`1.5.7`（不得覆盖已经发布的 `1.5.6`）

## 1. 结论与负责人需要完成的工作

`ai2apps/runtime-omlx 1.5.6` 需要重新构建为新版本，完成 Developer ID 签名、
Apple notarization、staple、AI2Apps Publisher 签名和 Registry 发布。

这不是 checkpoint 损坏，也不是 Hugging Face / ModelScope 下载方式差异导致的问题。
同一份合法 checkpoint 在 Runtime 中连续暴露了两个独立缺陷：

1. Runtime 对 safetensors 符号链接执行 `Path.resolve()`，导致 Qwen4 checkpoint
   sanitize 没有生效，模型拒绝 672 个参数；
2. Runtime 内置 Python 3.11，却打包了 `_ext.cpython-313-darwin.so`。Direct-L1
   原生扩展无法导入，Cached-MoE 在首次 decode Scope prime 时失败。

当前开发机上的已安装 Runtime 已做现场热修复并通过真实 Chat 推理，但该热修复不是可发布物，
重新安装、清缓存或升级 Runtime 后可能被覆盖。负责人必须从修复后的源码重新生成不可变的新版本。

完成条件：在干净实例安装新 Runtime 后，Qwen3.8 4-bit 模型无需改写 checkpoint 即可在
Chat App 的全新对话中返回正确正文，并且服务日志中不存在本文列出的两类错误。

## 2. 用户可见现象

模型 Package 和 checkpoint 在 Model App 中均显示 Ready，Chat App 也可以选中模型，但推理依次出现：

### 2.1 初始错误：checkpoint 未准备

```text
Error: Checkpoint must be prepared before Qwen4 Cached-MoE execution
```

该阶段涉及模型准备目录选择和 prepared manifest；完成准备与 Worker 路径修复后进入下一错误。

### 2.2 模型加载错误：672 个未识别参数

```text
Error: Unable to load Vontra/Qwen3.8-Flash-Next-MLX-4bit:
Received 672 parameters not in model:
language_model.model.layers.0.mlp.switch_mlp.gate_proj.biases,
language_model.model.layers.0.mlp.switch_mlp.gate_proj.scales,
language_model.model.layers.0.mlp.switch_mlp.gate_proj.weight,
...
language_model.model.layers.1.ple.ple_embedding.ngram_embedding.shard_0.weight,
...
```

错误集合主要包括：

- 48 层 `switch_mlp.gate_proj` / `switch_mlp.up_proj` 的 weight、scales、biases；
- PLE ngram embedding 的 128 个 shard 参数。

### 2.3 加载错误消失后，Chat 返回空白正文

修复 672 参数错误后，Chat 请求耗时约 28 秒，HTTP 上游记录为 `200 OK`，但 UI 中助手正文为空，
统计为 0 prompt token / 0 generated token，只显示了无关的 Knowledge citations。

本地数据库记录确认并非模型生成了空字符串：Worker 已开始 SSE 响应并发送 HTTP 200，随后推理线程抛出异常；
Chat 的流式调用没有把该后置异常转换成可见错误，最终把空正文保存为 completed。

Worker 的真实错误是：

```text
RuntimeError: Qwen4 Scope prime requires Direct L1
```

同时服务启动日志包含：

```text
omlx.custom_kernels.glm_moe_dsa.fast: native extension is present but failed to load;
falling back to the slow path: cannot import name '_ext' from partially initialized module
'omlx.custom_kernels.glm_moe_dsa'
```

## 3. 验证环境与不受影响的数据

现场环境：

- Apple Silicon Mac；
- AI2Apps development instance：`dev`；
- Local 验收端口：`55191`（动态端口，仅用于本次记录）；
- 已安装 Runtime：`ai2apps.runtime.omlx 1.5.6`；
- Runtime 安装 digest：
  `a757d5a6ea59f37150861ead9c7d8768645a280946703d52a1aedf8f01f38c25`；
- Runtime Python：`cpython-3.11/bin/python3.11`，版本 3.11.10；
- 模型：`Vontra/Qwen3.8-Flash-Next-MLX-4bit`；
- HF immutable revision：`de597762aa61387c89590a46582222a261ce0387`；
- 模型大小约 111.6 GB；
- prepared Cached-MoE：48/48 层，Qwen4 affine-Q4 fused expert-major store；
- Chat 模型 ID：
  `ai2apps.model.qwen38-flash-next-4bit/qwen3.8-flash-next-mlx-4bit`。

以下内容没有被修改：

- 原始 checkpoint safetensors 字节；
- HF immutable revision；
- checkpoint distribution；
- 量化内容。

现场操作只创建/使用 AI2Apps 模型缓存、prepared expert store，并修复 Runtime 代码和原生扩展。

## 4. 根因一：safetensors 符号链接被错误解析

相关文件：

```text
omlx/patches/qwen38_next_cache/runtime.py
```

prepared model 目录中的普通模型文件是指向 Hugging Face blob cache 的符号链接。旧实现：

```python
path = Path(filename).resolve()
if path.parent == target_dir and path.suffix == ".safetensors":
    ...
```

`resolve()` 会把：

```text
<prepared-model>/model-00001-of-00022.safetensors
```

解析成：

```text
<huggingface-cache>/blobs/<sha256>
```

解析后的 parent 不再等于 prepared model 目录，且 blob 文件名也不再带 `.safetensors` 后缀。
因此 Runtime 没有移除 safetensors metadata 中的 `format=mlx`。mlx-vlm 随后跳过
Qwen4 专用 sanitize/fuse 路径，原始 gate/up/PLE 参数直接进入紧凑 Cached-MoE 模型，最终出现
`Received 672 parameters not in model`。

### 4.1 源码修复

新增 `_is_checkpoint_safetensor()`，使用 lexical absolute path，不解析符号链接：

```python
path = Path(os.path.abspath(os.path.expanduser(os.fspath(filename))))
return path.parent == target_dir and path.suffix == ".safetensors"
```

修复原则：

- 路径必须规范为绝对路径；
- 允许 `~`；
- 不得调用 `resolve()`；
- 判断的是模型视图中的文件名和 parent，不是 blob 实体路径。

回归测试位于：

```text
tests/test_qwen38_ple_mode.py
```

测试必须覆盖“prepared model shard 是指向 Hub blob 的 symlink”这一实际布局。

## 5. 根因二：原生扩展 Python ABI 与 Runtime 不一致

Runtime 实际解释器：

```text
Contents/Resources/Runtime/Python/cpython-3.11/bin/python3.11
```

`1.5.6` 中 GLM/Direct-L1 扩展却是：

```text
omlx/custom_kernels/glm_moe_dsa/_ext.cpython-313-darwin.so
```

Python 3.11 不会把 CPython 3.13 专用扩展当作可导入的当前 ABI 模块。`fast.py` 因此进入 slow path，
`native_symbols()` 中不存在 `preadv_fused_experts`。Qwen4 Cached-MoE 的 Scope prime 要把固定 Scope
专家直接读入最终 MLX L1 slot，该路径要求 Direct-L1；原生符号缺失时抛出：

```text
RuntimeError: Qwen4 Scope prime requires Direct L1
```

### 5.1 为什么原构建检查没有发现

相关脚本：

```text
apps/omlx-mac/Scripts/build.sh
```

旧 `_build_custom_kernels()` 使用宿主 `$PYTHON_BIN` 执行：

```bash
"$PYTHON_BIN" setup.py build_ext --inplace --force --with-custom-kernel
```

本次宿主开发环境是 Python 3.13，所以生成 cp313 扩展。构建后的 ABI 检查仍使用同一个宿主 Python 3.13，
扩展在检查环境中可以导入，形成假阳性；最终 Runtime bundle 却嵌入 Python 3.11。

### 5.2 永久构建修复

`build.sh` 已修改为：

1. 固定使用 donor layers 中即将随 Runtime 发布的解释器：

   ```text
   $DONOR_LAYERS/cpython-3.11/bin/python3.11
   ```

2. 从宿主 Python 环境只借用 pure-Python `nanobind==2.13.0` build package；
3. `PYTHONPATH` 首项使用 donor 的 `framework-mlx-base/lib/python3.11/site-packages`；
4. build、nanobind version check、MLX `abi_probe()` 全部使用 bundled Python 3.11；
5. 产物必须是 `_ext.cpython-311-darwin.so`，不得接受 cp313；
6. `abi_probe(mx.zeros((1,)))` 必须使用随 Runtime 发布的 MLX wheel 执行。

对应回归测试：

```text
tests/test_app_bundle_cli_wrapper.py::test_custom_kernels_build_with_the_bundled_python_abi
```

## 6. 本次现场修复过程

以下步骤用于确认根因和恢复当前开发实例，不应代替正式发布：

1. 将 HF checkpoint 以链接方式纳入 AI2Apps 实例模型缓存；
2. 生成 48 层 Qwen4 expert-major prepared store 和 `ai2apps-model.json`；
3. 修复 Worker 模型路径选择，使 Cached-MoE 使用 prepared model 目录；
4. 修复 safetensors symlink 判断并同步到已安装 Runtime；
5. 停止 Qwen Worker，使其重新导入 Runtime；
6. 发现并读取 `service_logs` 中隐藏的 `Direct L1` 异常；
7. 使用 Runtime 自带 Python 3.11、Runtime 自带 MLX 和 pinned nanobind 重新编译：

   ```text
   _ext.cpython-311-darwin.so
   libomlx_glm_kernel_ops.dylib
   ```

8. 使用与 Runtime 相同的 Developer ID Team `84XL5V265N` 签名新 Mach-O；
9. 用 Runtime Python 3.11 执行 ABI 检查，结果：

   ```text
   native extension available: True
   preadv_fused_experts present: True
   import_error: None
   ```

10. 把 cp311 扩展部署到当前已安装 Runtime，重启 Qwen Worker；
11. 在 Chat App 创建全新对话并执行真实推理。

现场 Runtime 路径中的手工修改是诊断性热修复。不得直接把安装缓存归档后发布，也不得把
`1.5.6` 用不同字节重新上传。

## 7. 已完成的验收证据

### 7.1 自动测试

执行：

```bash
bash -n apps/omlx-mac/Scripts/build.sh

./.venv/bin/pytest -q \
  tests/test_app_bundle_cli_wrapper.py \
  tests/test_qwen38_ple_mode.py \
  tests/test_ai2apps_model_worker.py \
  -k 'custom_kernels or qwen4'

git diff --check
```

结果：

```text
4 passed, 17 deselected
git diff --check: passed
```

MLX 测试需要实际 Metal 访问；在受限沙箱中 MLX 初始化可能 abort，应在允许 Metal 的构建环境执行。

### 7.2 真实 Chat 推理

在全新对话发送：

```text
计算 246 + 135，只回复数字。
```

模型回复：

```text
381
```

UI 记录：

- total：33.18s；
- thinking：约 6s；
- 正文非空；
- 无 `672 parameters`；
- 无 `Qwen4 Scope prime requires Direct L1`。

验收后已停止 Qwen Worker 释放约 40–50GB resident memory；Local 保持运行，下一请求会按需重新启动 Worker。

## 8. Runtime 1.5.7 构建要求

发布前先将以下 Runtime metadata 同步升为同一新版本，例如 `1.5.7`：

```text
packages/ai2apps-runtime-omlx/service.yaml
packages/ai2apps-runtime-omlx/ai2apps.json
packages/ai2apps-runtime-omlx/META/runtime-manifest.json
packages/ai2apps-runtime-omlx/META/sbom.spdx.json
```

不得覆盖 `1.5.6`；AI2Apps Package 的 `package ID + version` 是不可变字节身份。

### 8.1 重新导出 layers 并构建原生扩展

从仓库根目录执行。实际发布时以 `docs/ai2apps-package-publication-runbook.md` 为准：

```bash
cd /Users/avdpropang/sdk/omlx-moe-cache

./.venv/bin/python packaging/build.py --venvstacks-only

PYTHON_BIN="$PWD/.venv/bin/python" \
  apps/omlx-mac/Scripts/build.sh release --with-custom-kernel
```

关键检查：

```bash
find omlx/custom_kernels -name '_ext*.so' -print
```

所有会复制进 Runtime 的扩展都必须匹配 bundled CPython 3.11；至少确认：

```text
omlx/custom_kernels/glm_moe_dsa/_ext.cpython-311-darwin.so
```

以下情况必须中止发布：

- 只存在 `_ext.cpython-313-darwin.so`；
- `fast.is_native_available()` 为 false；
- `preadv_fused_experts` 不在 native symbols；
- `abi_probe()` 拒绝 bundled MLX array；
- extension/dylib 的最低 macOS 版本与 Package metadata 不一致。

### 8.2 构建 Developer ID Runtime DMG

```bash
RUNTIME_SOURCE="$PWD/packages/ai2apps-runtime-omlx"
RUNTIME_LAYERS="$PWD/packaging/_export"
RUNTIME_VERSION='1.5.7'
INTERNAL_DMG="/absolute/release/path/AI2Apps-oMLX-Runtime-${RUNTIME_VERSION}-internal.dmg"
FINAL_DMG="/absolute/release/path/AI2Apps-oMLX-Runtime-${RUNTIME_VERSION}.dmg"
SIGN_IDENTITY='Developer ID Application: Avdpro Pang (84XL5V265N)'

./.venv/bin/python scripts/build_omlx_runtime_dmg.py \
  --layers "$RUNTIME_LAYERS" \
  --output "$INTERNAL_DMG" \
  --version "$RUNTIME_VERSION" \
  --sign-identity "$SIGN_IDENTITY"
```

构建器会对嵌套 Mach-O 重新执行 Developer ID + Hardened Runtime 签名。不要手工从当前安装缓存复制文件。

### 8.3 Apple notarization 与 staple

使用已经配置的 Keychain profile；如果尚未配置，只能让用户通过交互输入 App 专用密码：

```bash
cp "$INTERNAL_DMG" "$FINAL_DMG"

xcrun notarytool submit "$FINAL_DMG" \
  --keychain-profile ai2apps-notary \
  --wait

xcrun stapler staple "$FINAL_DMG"
xcrun stapler validate "$FINAL_DMG"
spctl --assess --type open --context context:primary-signature -v "$FINAL_DMG"
```

不得把 Apple App 专用密码写入命令行、文档或日志。

### 8.4 封装并签署外层 AI2Apps Package

按 runbook 使用既有正式 Publisher 和 registered Publisher key；不要创建新 Publisher/key 绕过失败：

```bash
ARTIFACT="/absolute/release/path/ai2apps-runtime-omlx-${RUNTIME_VERSION}.ai2service"

./.venv/bin/python scripts/build_omlx_runtime_package.py \
  --source "$RUNTIME_SOURCE" \
  --layers "$RUNTIME_LAYERS" \
  --output "$ARTIFACT" \
  --prepared-dmg "$FINAL_DMG" \
  --prepared-signing developer-id \
  --team-id 84XL5V265N \
  --keychain-secret "$PUBLISHER_KEY_SECRET" \
  --keychain-namespace "$KEYCHAIN_NAMESPACE" \
  --publisher-id "$PUBLISHER_ID" \
  --key-id "$PUBLISHER_KEY_ID"
```

### 8.5 发布

只使用：

```text
scripts/publish_signed_registry_artifact.py
```

先查询 Publisher、key fingerprint 和相同 Package/version 的现有 submission。若已经 submit，必须用
`--submission-id` 恢复，禁止重复提交。需要管理员浏览器会话时，按 runbook 重新获得本次
`ai2apps/runtime-omlx 1.5.7` 专项 Cookie 访问授权；旧任务授权不继承。

## 9. 新版本发布验收清单

- [ ] Runtime metadata 四处版本完全一致且高于 `1.5.6`；
- [ ] Runtime bundle 使用 CPython 3.11；
- [ ] GLM Direct-L1 扩展为 cp311，不包含误打包的 cp313-only 扩展；
- [ ] `preadv_fused_experts` 在 bundled Runtime 中可用；
- [ ] bundled Python + bundled MLX 的 `abi_probe()` 通过；
- [ ] safetensors symlink 回归测试通过；
- [ ] 自定义 kernel build ABI 回归测试通过；
- [ ] 内嵌 `.so`、`.dylib`、Python、bundle、DMG 的 codesign 校验通过；
- [ ] Apple notarization Accepted；
- [ ] staple validate 通过；
- [ ] Gatekeeper `spctl` 通过；
- [ ] 外层 `.ai2service` Publisher envelope 校验通过；
- [ ] Registry submission 已 published；
- [ ] 干净实例可以解析并安装 `ai2apps/runtime-omlx 1.5.7`；
- [ ] Qwen 模型 Package 自动解析到兼容新 Runtime；
- [ ] HF 安装路径真实推理通过；
- [ ] ModelScope 安装路径真实推理通过；
- [ ] Worker startup/readiness/health/stop/restart/uninstall 通过；
- [ ] 全新 Chat 对话得到非空且正确的模型回复；
- [ ] 服务日志无本文两类错误；
- [ ] 保存 commit、artifact SHA-256/size、Publisher key ID、submission ID、notary ID 和发布时间。

## 10. 模型 Package 是否需要重新发布

当前 Qwen 模型 Package 对 Runtime 的依赖范围是：

```text
ai2apps/runtime-omlx >=1.5.5 <2.0.0
```

因此发布 `1.5.7` 后，依赖解析应能直接选择新 Runtime，通常不需要为了本故障重新发布 checkpoint
或模型 Package。仍必须在干净实例验证升级解析行为；如果 Registry 的已安装版本锁定策略不会自动替换
`1.5.6`，应通过正常 Runtime upgrade 流程解决，而不是改变 checkpoint。

## 11. 额外改进建议

本次 Direct-L1 异常发生在 SSE 响应开始、HTTP 200 已发送之后，Chat 最终保存为空白 completed 消息。
建议另开问题修复流式错误传播：

- Worker 在 SSE 中输出结构化 error event；
- Local/Fusion adapter 把 stream error 映射为失败消息；
- Chat 不应把零 token、无 finish payload 且流异常的响应标记为 completed；
- `_recentStats.total_tokens == 0` 且 generation 为 null 时保留真实 Worker error；
- 增加“stream headers 已发送后 engine exception”的集成测试。

该改进不阻塞 Runtime 1.5.7 的根因修复发布，但可以避免未来运行时错误被误判为模型空回复。

## 12. 相关文件

```text
omlx/patches/qwen38_next_cache/runtime.py
tests/test_qwen38_ple_mode.py
apps/omlx-mac/Scripts/build.sh
tests/test_app_bundle_cli_wrapper.py
ai2apps/model_worker/cache_moe.py
ai2apps/model_worker/omlx_chat.py
scripts/build_omlx_runtime_dmg.py
scripts/build_omlx_runtime_package.py
scripts/publish_signed_registry_artifact.py
packages/ai2apps-runtime-omlx/
docs/ai2apps-package-publication-runbook.md
```

## 13. 交接状态

已完成：

- 两个根因定位；
- 源码修复；
- 回归测试；
- 当前开发实例热修复；
- bundled Python 3.11 原生扩展 ABI 验证；
- 真实 Qwen Chat 推理验收。

待 Runtime 负责人完成：

- 决定并写入新 Runtime 版本（建议 `1.5.7`）；
- 从干净 build inputs 重新构建；
- 完整签名、公证、staple；
- 生成并签署外层 Package；
- 发布到 Registry；
- 在干净实例和另一台受支持 Mac 上完成发布后验收；
- 保存正式发布收据。
