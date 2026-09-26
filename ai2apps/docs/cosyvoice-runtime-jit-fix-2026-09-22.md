# CosyVoice Runtime JIT 修复验证

## 根因

2026-09-22 19:03，app-dev 的 `/readaloud/training/preview` 返回 502：
`Model provider request failed: Server disconnected without sending a response.`
对应 macOS 崩溃报告 `python3.11-2026-09-22-190302.ips`：
`SIGKILL (Code Signature Invalid)`，`CODESIGNING / Invalid Page`。
调用链包含 `LLVMPY_TryAllocateExecutableMemory`、`llvm::sys::Memory::protectMappedMemory`、`sys_icache_invalidate`。

CosyVoice3 在参考音频预处理阶段调用 `librosa.effects.trim`，触发 Numba/LLVM。
已安装 oMLX Runtime 1.7.9 的 Python 具有 Hardened Runtime 标记，但无可执行内存 entitlement。
原始 Python 执行 `llvmlite.binding.check_jit_execution()` 可独立复现退出码 -9。

## 修复

标准构建器 `scripts/build_omlx_runtime_package.py` 的 `sign_runtime` 仅为
`Contents/Resources/Runtime/Python/cpython-3.11/bin/python3.11` 添加
`com.apple.security.cs.allow-unsigned-executable-memory=true`。
LLVM 当前使用非 MAP_JIT 的内存分配路径，因此单独 allow-jit 并不对应这条路径。
保留 Hardened Runtime 和 library validation；不放宽浏览器或其他原生库权限。

完成子文件签名后，最外层签名取消递归 force-sign，避免覆盖 Python entitlement；
签名完成后检查 entitlement 仍存在，并执行 deep/strict 验证。

Apple 权限说明：https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.allow-unsigned-executable-memory

## 验证

- 同一 Python 的原签名运行 LLVM 检查：退出 -9；修复签名：退出 0。
- librosa.effects.trim 实际执行成功。
- `tests/test_omlx_runtime_builder.py` + `tests/test_inference_runtime_package.py`：18 项通过。
- 标准入口构建 Developer ID 候选 DMG，版本 1.7.10；签名身份 Team ID 84XL5V265N。
- 从只读挂载的候选 DMG 运行真实 CosyVoice3 4-bit，使用失败请求保留的同一参考 WAV、已安装的固定模型和 S3Tokenizer checkpoint；离线生成成功，WAV 24kHz / 115200 frames / 4.8 秒。
- macOS 签名复核：`codesign --verify --deep --strict` 通过，最终 Python entitlement 正确。

候选：`/tmp/ai2apps-cosy-jit-check/AI2Apps-oMLX-Runtime-1.7.10-candidate.dmg`

- size: 384678301
- SHA-256: `9a7dc5721662796360229d590dbe87afa8c31a035182eddb57a918e9d6eaecbc`
- 试听验证输出：`/tmp/ai2apps-cosy-jit-check/cosy-fixed.wav`

## 交付状态

代码与签名候选已验证。候选尚未公证、封装 Publisher 签名、发布或安装。
未修改 app-dev 已安装且摘要寻址的 Runtime 1.7.9，也未修改任何已发布制品。
正式生效需按 Package 发布流程完成新 Runtime 版本发布和 app-dev 升级。

发布更新：Runtime 1.7.10 已完成 Apple 公证和 Cloud 发布。完整收据位于仓库 `docs/ai2apps-mlx-runtime-1.7.10-cosy-jit-release.md`；用户 App-Dev 尚未升级。
