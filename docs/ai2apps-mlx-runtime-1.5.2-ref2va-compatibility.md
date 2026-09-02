# MLX Runtime 1.5.2 与 1.4.1 Ref2VA 兼容性审计

日期：2026-08-26

## 结论

当前 MLX Runtime 1.5.2 对正式发布的 1.4.1 Ref2VA 能力完全向后兼容。1.5.2 保留了 1.4.1 的全部非签名载荷文件和 Model Worker 协议，同时扩大了 Host、能力校验和任务编排层的多参考输入容量。审计未发现需要从 1.4.1 回迁的代码，因此没有为兼容性修改 Runtime 源码。

本结论覆盖代码、打包载荷、依赖解析、Model Worker 启动及 12 个参考媒体部件的端到端传输边界。它不代表 1.5.2 已完成生产签名或正式发布；当前 1.5.2 仍是 development 构建候选。

## 对照基准

- 正式 1.4.1 服务包：`packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.4.1-production.ai2service`
  - SHA-256：`ef1eea6a648f99b1d1bf51677f900e18d0c9109147241b465e78cfb4d6f0db26`
- 正式 1.4.1 DMG：`packages/ai2apps-runtime-omlx/dist/AI2AppsOmlxRuntime-1.4.1.dmg`
  - SHA-256：`9bc745ccd3e3dd8eef9a3f870255d79aa34d5cdcfaaffd6fbdb8ddf5bbdba200`
- 1.5.2 development 服务包规范载荷摘要：`sha256:fd4cfd828fba9c2efbf1e5cc40c6a44cdb48a50649e27ffec9348ccff9a1602f`
- 1.5.2 内层 DMG SHA-256：`34c1219e2de8581697df05ae1262d928d63f5ef04844bf93cd9f75cd251d92ee`
- Ref2VA 模型包：MiniMax H3 0.8.0，Runtime 依赖范围 `>=1.4.1,<2.0.0`

1.4.1 production 服务包采用 Cloud 生产发布封装，不包含本地开发归档使用的 `META/files.json`。因此载荷对照通过只读挂载正式 DMG 完成；这只是服务包封装格式差异，不影响 Runtime 或 Model Worker 协议。

## 审计结果

### 文件载荷

忽略代码签名目录和 `Info.plist` 后，对两个实际 DMG 做逐文件校验：

- 1.4.1 中存在而 1.5.2 缺失的文件：0
- 1.5.2 新增或内容不同的文件：1,340

因此 1.5.2 是 1.4.1 载荷的文件级严格超集。重建和重新签名会使部分二进制哈希变化，所以兼容性判断不要求所有二进制逐字节相同。

### Ref2VA 协议与限制

- `ai2apps/model_worker/protocol.py` 两版 SHA-256 相同：`62d24091048fb6b4f00452cf1f93fd2d6f28c62d2f544015752e0fe6cb7b5d7d`。
- Model Worker 的 `MAX_MULTIPART_PARTS` 两版均为 12。
- 1.4.1 Host 解析上限为 8 个文件；1.5.2 提升为 16 个文件、32 个字段，能够容纳 12 个参考媒体部件及 JSON 元数据。
- 视频能力校验的单角色上限由 8 提升到 12。
- 1.5.2 支持重复 reference role、稳定顺序的 `reference_XX_kind` 部件命名和 `reference_parts` 清单。
- 图片、视频和音频参考的合计上限保持为 12，并增加媒体时长和视频策略校验。

这些变化保持 1.4.1 请求语义，同时补齐了 H3 0.8.0 Ref2VA 声明所需的完整 12-reference 路径。

## 验证

### 自动化测试

联合运行 MiniMax H3 0.8.0 与当前 Runtime 的 Worker adapter、Ref2VA packing、scheduler、Model Worker、video task 和 Runtime video 测试：

- 结果：41/41 通过
- Metal packing 用例在允许 Metal 的宿主环境中单独复跑并通过

### 干净安装与传输 smoke

在全新隔离实例中安装 1.5.2 Runtime 和 H3 0.8.0：

- 依赖锁将 H3 0.8.0 正确解析到 Runtime 1.5.2。
- H3 Model Worker 成功启动并进入 `running` 状态。
- 包含 12 个媒体部件的 multipart 请求成功穿过 Host、任务编排和 Model Worker 边界。
- 请求最终返回预期的 `503 model_unavailable`，原因是隔离实例未安装真实 checkpoint；并非 multipart、能力校验或协议错误。
- smoke 记录：`{"parts":12,"adapter_error":"model_unavailable","status":503}`。

## 发布建议

1.5.2 可以作为下一批图像模型接入和优化的共同开发基线。正式发布前仍需执行标准 production 签名、公证、服务包发布与真实 H3 checkpoint 回归，但无需再进行 Ref2VA 兼容性代码合并。
