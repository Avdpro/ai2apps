# AI2Apps oMLX Runtime 1.8.1 / Ornith 0.1.5 发布收据

状态：两个 Package 已按依赖顺序发布。Runtime 1.8.1 已完成 Apple 公证以及
Cloud、GitHub、ModelScope 三源激活；Ornith 0.1.5 已在 Runtime 发布后完成 Cloud
发布。正式签名制品的安装、依赖解析、Worker 启动和匿名回读通过。

本收据记录 Package 发布事实。发布 handoff 要求的六种真实 checkpoint 的
Natural/Blast 全矩阵尚未全部在最终签名 Runtime 上重跑，因此不把该项写成已完成；原
handoff 保留为验收清单。

## Runtime 1.8.1

- Package：`ai2apps/runtime-omlx 1.8.1`。
- 源码基线：`de405d2371d61f85fda19da583b5d9fa1000849a`，发布内容来自该提交上的
  working tree。
- Apple 公证：`6c737fc9-409f-4050-b900-81c3f2625b28`，状态 `Accepted`；staple、
  `stapler validate` 与 Gatekeeper 通过。
- 正式 DMG：388,289,270 bytes，SHA-256
  `3a4ec4a659788c15d26ab6b9054ec5b0b8c604764593c9c74b6fdc0d70e76a39`。
- 正式 Package：385,593,065 bytes，SHA-256
  `d42c0fc17235714b25b694bafb7741658bf89217b7a4f564cbf4dab3b4fc8cac`。
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`；key
  `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`。
- Cloud submission：`ffa0d8d0-2bc1-4c6a-9dee-26d1064fe005`，状态
  `published`。

Runtime 包含统一 Engine Boost 会话控制：DeepSeek V4.1、DeepSeek V4、Qwen3.6
文本/VLM、Ornith、Qwen3.8 Flash Next 与 GLM-5.3 都通过对应的运行时策略入口；Prefill
保持精确，Decode 的 Natural/Turbo/Blast 按各模型策略执行。Worker usage 与状态端点返回
实际 Boost 模式和引擎统计。DeepSeek V4.1 的结束清理沿用已有同步边界，没有为了统计增加
每 token Metal 同步。

## Ornith 0.1.5

- Package：`ai2apps/model-ornith15-35b-a3b-4bit-vision 0.1.5`。
- 正式 Package：184,600 bytes，SHA-256
  `6aaafb653228b80f269ef255a2e70b5c6fa57f5918f49465263401de2c2448a2`。
- Cloud submission：`5a78c32e-d521-46fe-862b-5828f1660bd2`；review
  `81aa9599-4394-4250-8f5b-e20222d5603c`；状态 `published`。
- 依赖下限为 `ai2apps/runtime-omlx >=1.8.1,<2.0.0`。隔离安装实际解析并锁定
  Runtime 1.8.1 的上述精确 SHA-256，Worker 状态为 `running`。
- Package 使用 Runtime 的 `Qwen36DynamicVLMEngine`；归档审计确认没有 checkpoint
  权重、Mach-O、`.dylib` 或 `.so`。
- Checkpoint distribution 沿用
  `dist_ai2apps_ornith1_5_35b_a3b_mlx_4bit_vision_ssd_114f31e6_v1`，没有重传权重。

## Registry 与 Runtime 多源

- GitHub tag：`package-runtime-omlx-v1.8.1`；Source
  `src_f3921860-7a17-4a26-9ef7-341889c4ebaa`，validation
  `val_1ddbf8f3-62a5-4429-be24-41da14d3478a`，digest
  `507b253664dce1aba3b19e7e8f965a6c53d0db0e9823297ca128805c4bfcc07a`。
- ModelScope immutable revision：`b2621c1734a5e8d702ca32d2dec44152377b9fe0`；Source
  `src_5ede1ba3-080b-40b6-ac67-fddcdbabedcb`，validation
  `val_c3df718d-2aaf-4a74-b1da-1b2c234f75c7`，digest
  `2993f247edc1c563af7b20a439ef7962f2ea1eefe11097ea206f98bc11eb5fed`。
- Cloud 对两个外部源均完成完整 SHA-256、size、46-piece manifest 与 49 次 Range
  校验。GitHub 为 HTTP 206；ModelScope 为严格 HTTP 200 加精确
  `Content-Range`。两个 Source 和 Cloud Source 均为 `active`。
- 最终 Source revision / ETag：6 / `"sources-6"`；Repository metadata：214；
  Snapshot digest：
  `94968b59aba11024d3e39893f1ce6f7cae94f629445777a8aa4a6e5c21560ef8`。
- 匿名完整下载的 GitHub 与 ModelScope 制品均与本地正式 Package 的长度、SHA-256 和
  原始字节一致；Registry 匿名回读确认 Package 与签名 envelope 精确一致。

## 验证记录

- Boost 专项矩阵 85 项通过；Engine Pool/Worker 154 项通过；Package、Provider、Adapter
  与资源兼容套件 131 项通过；最终 Runtime/Worker/Ornith 收口套件 52 项通过。各套件有
  重叠，不能相加为唯一测试数。
- Runtime 精确签名 Package 在独立 Platform 根目录安装成功；CPython 3.11.10、MLX
  0.32.0、Metal 和 `preadv_fused_experts` 原生符号通过。DeepSeek V4.1 Worker 启动为
  `running`，依赖锁精确指向 Runtime 1.8.1。
- Ornith 精确签名 Package 在另一个独立 Platform 根目录安装成功；Resolver 选择
  Runtime 1.8.1，Worker 启动为 `running`。
- `git diff --check` 通过。

## 验收边界

源码阶段的真实 DeepSeek V4.1 对照已经证明 Blast 为 `protected_top=2`、
`omitted_tail_routes=220`、`executed_routes=500`，Natural 为
`protected_top=6`、`omitted_tail_routes=0`。这项结果不是最终签名 1.8.1 Package 的
六后端全矩阵替代品。

最终签名 Runtime 尚未逐一完成 DeepSeek V4、DeepSeek V4.1、Qwen3.6 文本、Ornith
VLM、Qwen3.8 Flash Next 和 GLM-5.3 的真实 Natural/Blast 推理，也没有在现有 Dev/Test
实例执行全部兼容模型依赖锁迁移。发布制品、Registry、多源与精确安装已经完成；上述项目
保留为发布后的模型验收，不在本收据中宣称通过。
