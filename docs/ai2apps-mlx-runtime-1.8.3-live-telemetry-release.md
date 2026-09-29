# AI2Apps oMLX Runtime 1.8.3 实时遥测发布收据

状态：`ai2apps/runtime-omlx 1.8.3` 已正式发布。Developer ID 签名、Apple 公证、
staple、Gatekeeper、隔离安装、Cloud 发布、GitHub/ModelScope 三源激活和匿名 Registry
回读均通过。模型 Package 与 checkpoint 没有变化。

## 变更

Runtime 1.8.3 补齐 1.8.2 整轮遥测的生成中传输链路。DeepSeek V4 Flesh engine 新增
`get_live_metrics(session_id)`，把已经在安全 Decode 边界物化的
`ssd_recent_10_tokens` 和 `ssd_turn_average` 作为纯 Python 数据返回。Worker 在既有
`ai2apps_metrics` SSE 扩展帧中携带这些字段，因此 Chat 可以在请求仍在生成时更新最近
10 token 的 SSD pressure，并在完成后保留整轮平均。

流式帧继续提供累计 completion token。若后端没有原生 token 时间戳，客户端可用本地
单调接收时间计算滚动 Decode 速度。该回退只影响展示统计，不改变模型调度、路由或生成
结果。新增接口不读取 MLX array，没有增加 Metal readback 或 GPU→CPU 同步。

## 发布后勘误（2026-09-29）

实机复验发现 DeepSeek V4.1 使用独立的 `DeepseekV41Engine`，不经过上述
`DeepseekV4FleshEngine`。因此 1.8.3 的 Worker 传输与 Chat 展示有效，但 V4.1 专用引擎
没有提供 `get_live_metrics()`，界面只能显示 `— / —`。1.8.3 的签名制品与发布事实保持
不变；该遗漏最初在 1.8.4 候选中修正，随后并入覆盖全部 Cached-MoE 引擎和正确 macOS
内存口径的 Runtime 1.8.5 候选。未把 1.8.3 的 Worker 启动检查误记为真实 V4.1 SSD
数值验收。

## 正式制品

- 源码基线：`de405d2371d61f85fda19da583b5d9fa1000849a` 上的 working tree。
- Apple 公证 submission：`2ff308b2-e760-4ca7-b66a-1642f134a2ec`，状态
  `Accepted`；staple、`stapler validate` 与 Gatekeeper 通过。
- DMG：384,481,076 bytes，SHA-256
  `61af0ab76eea9329995ab4d682503fb75f2b16cc3fbc2b0c7ed1d312bdf07320`。
- Package：381,811,781 bytes，SHA-256
  `972bbe2498f9a5d7543b206cc6c6d5026e42e728c282c8b515d39523c9cd95ee`。
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`；key
  `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`。
- Cloud submission：`0e6cf1da-fd08-4b73-9b08-b0da8d722098`；review
  `82b6eaa3-6b00-42d5-b35b-60b24c73214f`；状态 `published`。

## 三源发布

- Cloud Source 保持 active。
- GitHub tag：`package-runtime-omlx-v1.8.3`；Source
  `src_a2c7e8ba-c9a4-4684-8815-e0966af0922a`；validation
  `val_72bd00bd-c9f2-4814-9e94-eaf34a704dc4`；digest
  `52c20416832afe6b694fa9bcf2ce28f54d2224b1da685d2e517b61650ccecd0b`。
- ModelScope immutable revision：`490e5831b651d5856ed9995e77ca10dfb45d10cf`；
  Source `src_368033fe-2939-4c09-ba3e-24e157c73754`；validation
  `val_ca916ccf-e5a7-4342-9bf4-00fb3e86f38d`；digest
  `f0ee2210933d4af75e05f38e1afbe994cc5de021ed23cb1150074e6120d5dd3e`。
- 两个外部源分别完成匿名完整下载，长度、SHA-256 和原始字节均与正式 Package 一致。
  首段、中段、尾段与单字节 Range 也逐字节匹配。GitHub 返回标准 HTTP 206；
  ModelScope 返回兼容的 HTTP 200 加精确 `Content-Range`。
- Cloud 对每个外部源重复验证完整 SHA-256、46-piece manifest 和 49 次 Range 请求。
  最终 Source revision / ETag 为 6 / `"sources-6"`；Repository metadata 为 221；
  Snapshot digest 为
  `6b43293218897aff48c7e8388ed42ab581dec789ef154a97f6528ad294114f5e`。
- 匿名 Registry 回读确认正式 Package 字节和 Publisher envelope 均与本地签名制品精确
  一致。

## 验证

- 遥测数学、Worker SSE、Runtime、Package、Product、Chat 与 Engine Pool 定向回归共
  254 项通过；`git diff --check` 与 CPython 3.11 `compileall` 通过。
- 正式签名 Package 在独立 Platform 根目录安装成功；CPython 3.11.10、MLX 0.32.0、
  Metal 和原生 `preadv_fused_experts` 通过。已安装代码包含 `get_live_metrics` 及对应
  Worker SSE 接线。
- DeepSeek V4.1 0.1.0 Worker 在隔离环境中启动为 `running`，依赖锁精确指向 Runtime
  1.8.3 的上述 SHA-256。

本轮验证覆盖统计传输、Runtime 制品、依赖解析和 Worker 启动，没有重复下载 475 GB
checkpoint 或执行新的真实生成吞吐测试，因此不据此改变既有 TPS 结论。
