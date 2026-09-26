# AI2Apps oMLX Runtime 1.7.12 发布收据

状态：Cloud 已发布；Cloud、GitHub、ModelScope 三源均已激活，匿名完整下载、Repository Snapshot 与 Publisher 签名验证通过。

- Package：`ai2apps/runtime-omlx 1.7.12`
- 修复：DeepSeek V4 Flash 2-bit DQ Direct Prefill 九段 bias store 安全回退。
- 内部 DMG：`packages/ai2apps-runtime-omlx/dist/1.7.12/AI2Apps-oMLX-Runtime-1.7.12-internal.dmg`
- 大小：384,542,702 bytes
- SHA-256：`aade49e5e185980a33255c81861b1e4d24aea279be2f1da315432fd30c0bbc5e`
- Developer ID Team：`84XL5V265N`
- Apple 公证：`c5c26f26-b75d-4bde-ba18-818692b16cb8`，`Accepted`。
- 正式 DMG：384,554,430 bytes，SHA-256
  `92fddc5e05a986cbb117bfb8f258f00066f938396295a115d40985a053878132`。
- 正式 Package：381,892,948 bytes，SHA-256
  `1ad9dafbf39fca32ed6c1625a91cc6bd38ff06f562bf01cff514443fce89df87`。

## 实现

Direct Prefill 预取标记仅由 Direct Prefill 已开启、原生 Direct-L1 可用且 store 为
canonical 六段布局的请求产生。带 `gate/down/up_proj.biases` 的九段 2-bit DQ store
使用既有异步 Legacy Prefill。陈旧 Direct 标记会在 layer/expert IDs 校验后同步读取完整
records，不再抛出 `direct Prefill marker reached legacy path`。

## 验证

- Direct-L1 10 项通过。
- DeepSeek Prefill、patch、Scope warmup/runtime 132 项通过。
- Model Worker、2-bit adapter、Runtime contract 39 项通过。
- Runtime 版本提升后的 Direct-L1、Worker、adapter、contract、builder 51 项通过。
- Ruff、compileall、diff check 通过。
- 内部 DMG 深层签名通过，版本为 1.7.12；候选内修复文件与工作树 SHA-256 均为
  `6f2d8d2ad59416e9bf57456f1271a0370b8334e194a1e69755a48bfa2bbc60e8`。
- 候选 CPython 3.11 成功加载 MLX、`preadv_fused_experts` 和其他原生符号。
- 直接从候选 DMG 运行真实 2-bit DQ `hi`：非空 4 token，TTFT 0.893 秒，Decode
  15.43 token/s，2/2 异步 Prefill 预取命中，0 Direct load，峰值 31.27 GiB。
- 相同 Runtime ABI 的 `20+20=?` 48-token A/B：两路均明确输出 40，Direct Prefill
  开/关输出 SHA-256 均为
  `a1364ed8dc05609f8cf0ccf81b9bf6c6e51fa7fb5028131d4878dfb121d027b3`；开启路径
  40/40 异步 Prefill 预取命中、0 Direct load，峰值 31.45 GiB。
- 正式签名 Package 在全新隔离 Platform 根目录安装成功；Demucs 0.1.0 的依赖锁精确绑定
  Runtime 1.7.12 及上述摘要，managed Worker 状态为 `running`。
- staple、Gatekeeper、Publisher 公钥指纹和 Package Contract 验证通过。

## 已知验收边界

当前 Test 缓存的 4-bit `DeepSeek-V4-Flash-SSD` 专家段顺序是旧的
`scales, weight`，不满足 canonical Direct loader 的 `weight, scales` 顺序，因此真实
4-bit 运行只验证了正常生成，没有命中 Direct Prefill。canonical 六段 Direct 标记、
无 staging 和 `_direct_load_slots()` 调用由回归测试覆盖。完成真实 4-bit Direct 门禁需要
compute-ready checkpoint。

## Registry 与三源发布

- Cloud submission：`56e0d3c1-d751-4367-aa70-9f3dfb1f18e7`，`published`。
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`；Key：
  `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`；公钥指纹与既有正式发布一致。
- GitHub tag：`package-runtime-omlx-v1.7.12`；Source
  `src_b5055efa-47d2-4099-b329-3bc2fee7a745`，validation
  `val_a13baa12-2a85-403e-b393-b05e31787bc1`，digest
  `8ca831be9d87be7914723b1739036f19cff91a45b6e4f14966d8084e2a52d8aa`。
- ModelScope revision：`6213e1642251f68e17c145b10f77c27de8fd86a8`；Source
  `src_c1cdf4fe-bb51-4e93-aa85-84899f1d2bad`，validation
  `val_26f866a8-f088-44c7-ab30-ad966ca71402`，digest
  `6b08f3b220ebdef3d5810287afd2603d934b073117278e01df1ba136bb171ddf`。
- 两个外部源均完成匿名全量下载，大小和 SHA-256 与正式 Package 完全一致。首、中、尾
  Range 字节匹配；GitHub 返回标准 HTTP 206，ModelScope 返回严格 HTTP 200 加精确
  `Content-Range`。
- Cloud 对两个外部源各执行 49 次 Range、完整 SHA/size 和 46-piece manifest 校验。
  GitHub 使用 `http-206`；ModelScope 使用 `package-single-range-v2` 的
  `http-200-content-range` 兼容模式。
- 最终 Source revision / ETag：6 / `"sources-6"`；Repository metadata：202；
  Snapshot digest：`fd4504d911fec1fca13e3591c362af9c5da162fc4ce35cadf64a0bcf0adb2cf4`。
- 全新匿名缓存完成 Repository Snapshot、三源下载、Package 字节和 Publisher envelope
  验证；`artifactExactBytes=true`、`envelopeExactJson=true`。

## 实例跟进

正式发布不会直接替换 App-Dev 或 Test 当前运行的 Worker。实例升级到 Runtime 1.7.12 后，
应重跑 2-bit DQ 的 `hi`、`20+20=?`、首 token、结束事件以及 Prefill/Decode/Duration
telemetry。模型代码、checkpoint 与 checkpoint distribution 不需要升级。现有模型 Package
0.3.5 的依赖范围是 `>=1.7.5,<2.0.0`，因此实例需要显式升级 Runtime 1.7.12；若要由 ACPF
自动修复已经安装 1.7.11 的实例，需要另发一个将最低 Runtime 提高到 1.7.12 的模型 Package
修订版。

本次 Dev Cookie 只通过标准发布脚本的 live 路径在进程内使用；三源发布完成后授权失效。
