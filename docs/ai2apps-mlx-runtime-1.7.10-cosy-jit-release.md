# AI2Apps oMLX Runtime 1.7.10 发布收据

日期：2026-09-22（Asia/Shanghai）

## 发布结果

`ai2apps/runtime-omlx 1.7.10` 已发布，Cloud 源可安装。
源码基线：`61da0fc6a87d4f743d312c8ae1987d1d1b7babb8` 加本次已记录的 Runtime 签名修复工作树变更。

- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- 公钥指纹：`216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- Cloud submission：`a28bc3ec-9d6e-441d-8ef7-031edbada125`
- 最终 releaseStatus：`published`
- Repository metadata：`191`
- Package SHA-256：`a18a4f7128c73eda724fbff9f25eed0e80af6793462a88f02f6de7383ec25d2a`
- Package size：`381986365`
- Apple submission：`dff8a203-8416-4092-80d9-7fc6383fde1c`，`Accepted`
- Staple / Gatekeeper：通过，`Notarized Developer ID`
- 公证 DMG SHA-256：`31b3e22c0862a59f5c88e14a38861addeabed36c77e113048eb4e8f5765d5f20`
- 公证 DMG size：`384690029`

制品保存在 `packages/ai2apps-runtime-omlx/dist/1.7.10/`。

## 修复和验收

修复私有 Python Worker 缺少 LLVM/Numba 可执行内存 entitlement，导致 CosyVoice3
参考音频的 librosa 静音裁剪被 macOS CODESIGNING Invalid Page 终止的问题。
保持 Hardened Runtime/library validation；只给 Python Worker 增加所需权限。
外层签名不再递归覆盖子文件权限，并在最终构建后验证 entitlement。

- 18 项 Runtime 构建/安装回归通过。
- 原 Python LLVM 探针退出 -9；修复签名后退出 0。
- 从标准签名候选 DMG 使用失败请求的同一参考音频，离线真实 CosyVoice3 4-bit 克隆成功输出 24kHz、4.8 秒 WAV。
- 正式 `.ai2service` 安装到隔离临时实例成功；CosyVoice3 0.1.1 Worker 启动成功，依赖锁精确绑定 Runtime 1.7.10 和正式 Package 摘要。
- 无用户会话的 `verify_registry_package_publication.py` 回读成功，`artifactExactBytes=true`、`envelopeExactJson=true`；验证仓库信任、Publisher 签名和完整制品。
- Cloud 匿名完整 SHA-256/大小、首中尾 Range 通过。
- 本次未在另一台 Mac 验证，未替换用户 App-Dev 已安装 Runtime；发布与本地升级分别记录。

## 外部源状态与例外

当前 Cloud 源 active。外部源没有伪报 active：

### GitHub

- 不可变 tag：`package-runtime-omlx-v1.7.10`
- URL：https://github.com/Avdpro/ai2apps/releases/download/package-runtime-omlx-v1.7.10/ai2apps-runtime-omlx-1.7.10-production.ai2service
- Source：`src_cb4f3d96-4050-4a07-925b-f8d4e20fda52`
- Validation：`val_88fd032f-a646-4d79-923d-5407fb147085`
- Validation digest：`288ac34dd82ca46e543dc01b438d9b64536cfc2929ee81aa2c3617c638276383`
- 状态：`pending_approval`；Cloud 预检 `passed`，完整摘要、大小、Range、piece manifest 全部通过（49 次 HTTP 206）。
- Source revision/ETag：`2` / `"sources-2"`
- 待由另一位 reviewer/admin 激活；按发布手册不允许注册者自审自批，未切换身份绕过。

### ModelScope

- Revision：`47a2e08c95dc7b9b97df59fa246185f9f75e1b74`
- URL：https://modelscope.cn/models/ai2apps/desktop-releases/resolve/47a2e08c95dc7b9b97df59fa246185f9f75e1b74/ai2apps-runtime-omlx-1.7.10-production.ai2service
- 完整大小和 SHA-256 与正式包一致。
- Range 检查返回 HTTP 200，虽然有 `Content-Range: bytes 0-1023/381986365` 和 1024 字节响应，但不符合当前发布手册的 HTTP 206 要求。
- 带 no-cache 和 `?download=true` 复查仍为 200；未注册或激活。需要源返回标准 206，或由项目明确更新并验证兼容政策后再接入。

本次暂以 Cloud 单源提供更新，例外是独立源审核尚未完成与 ModelScope Range 状态不符合手册；不影响已发布包通过 Cloud 安装。

## 授权与安全

用户明确授权 Apple 公证及 Dev Cookie 仅用于 Runtime 1.7.10 发布。
使用标准发布脚本 `--browser-live`，Cookie 不落盘、不输出。
发布完成后该 Cookie 授权结束；未修改生产 Cloud 代码或数据库，未重新签署/覆盖已发布版本。
