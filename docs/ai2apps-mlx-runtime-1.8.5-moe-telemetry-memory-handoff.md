# AI2Apps oMLX Runtime 1.8.5 MoE 遥测与内存口径交接

状态：实现与交接阶段完成，正式 `ai2apps/runtime-omlx 1.8.5` 已完成 Developer ID
构建、Apple 公证、隔离安装、Cloud 发布和 GitHub/ModelScope 三源激活。本文保留实现
与 development 验证背景；正式制品、来源和发布标识见
`docs/ai2apps-mlx-runtime-1.8.5-moe-telemetry-memory-release.md`。

## 结果

Runtime 1.8.5 将 SSD pressure 的实时 SSE 数据补齐到全部已发布 Cached-MoE 对话模型，
同时将 Chat 的 Worker memory 主口径从 RSS 改为 macOS `phys_footprint`。采集只读取既有
纯 Python SSD 计数，并复用每个引擎已经存在的 Decode 完成边界，不新增 MLX 求值、
Metal readback 或 GPU→CPU 同步。

| 模型 Package | 执行引擎 | 1.8.5 状态 |
| --- | --- | --- |
| DeepSeek V4 Flash | `DeepseekV4FleshEngine` | 保留既有 rolling/turn SSE |
| DeepSeek V4 Flash 2-bit | `DeepseekV4FleshEngine` | 保留既有 rolling/turn SSE |
| DeepSeek V4.1 Flash | `DeepseekV41Engine` | 专用 resident-bank 计数已接入 |
| GLM-5.3 Flash | `Glm5DynamicVLMEngine` | 动态缓存计数已接入 |
| Qwen3.6 Cached-MoE | `Qwen36TieredEngine` | tiered 与 fallback SSD 计数合并 |
| Ornith 1.5 35B Vision | `Qwen36DynamicVLMEngine` | VLM 动态缓存计数已接入 |
| Qwen3.8 Flash Next | `Qwen4DynamicVLMEngine` | Qwen4 动态缓存计数已接入 |

Qwen3.8 27B NVFP4 等全驻留模型不是 Cached-MoE；它们继续明确显示无 SSD pressure
样本，而不是伪造 `0%`。

## SSD pressure 实现

共享 `SsdPressureTelemetry` 接收三个已经物化的累计值：专家读取次数、SSD 读取字节和
每 token 理论路由专家字节。Prefill 结束时重设基线，Prefill logits 产生的第一个 token
不计入 Decode 分母；以后在既有 scheduler callback 更新最近 10 个 Decode token 和整轮
累计窗口。数据按 Session 保存，并由 `get_live_metrics(session_id)` 进入既有
`ai2apps_metrics` SSE 扩展帧；`get_stats()["flesh"]` 提供完成态和 Host 空闲投影。

动态引擎的 callback 继续先执行原 Boost/adaptive 控制器，再采样 SSD 计数。测试验证原
callback 没有被替换或跳过。GLM/Qwen4 直接读取共享动态缓存的 `experts_loaded`、
`bytes_loaded` 以及每层 store 的 `record_bytes × top_k`；Qwen3.6/Ornith 合并 tiered cache
与 fallback loader 的计数，并按每层真实 expert record 大小建立分母。

## V4.1 内存差异

原 Host 仅使用 `psutil.Process(pid).memory_info().rss`。Apple Silicon 的 Metal/IOAccelerator
统一内存并不完整计入 RSS，而系统活动监视器使用接近 `phys_footprint` 的 ledger 口径，
因此 V4.1 的大规模 Metal 常驻区使 UI 明显低报；其它模型 Metal footprint 较小时差异不
突出。

Host 现在通过 `proc_pid_rusage(RUSAGE_INFO_V4)` 同时导出：

- `residentMemoryBytes`：保留的 RSS 诊断值；
- `physicalFootprintBytes`：macOS physical footprint；
- `memoryMetric`：`phys_footprint`，不可用时为 `rss`。

Chat 当前值和整轮 250ms 采样峰值优先使用 `physicalFootprintBytes`，并显示
`FOOTPRINT`；非 macOS 或系统调用失败时安全回退 RSS。该 Host/UI 修改属于 Desktop/App
交付内容，单独安装 Runtime Package 不会改变旧 Desktop 的内存卡片。

使用本机共享 DeepSeek V4.1 SSD checkpoint 的同一次真实短推理测得：

- peak RSS：43.4923 GiB；
- peak `phys_footprint`：51.6140 GiB；
- 差值：8.1218 GiB。

这解释了旧 UI 与系统工具的主要差异。修正后的主值仍只统计选中 Model Worker 进程，
不会把 AI2Apps Host、Shell 或其它 Worker 合并进来；若系统工具查看的是全系统内存压力，
两者仍不应被理解为同一指标。

## 验证

- 共享 SSD 数学和四个新增引擎接线：9 passed。
- Runtime、Worker、Package、Engine、Adapter 与 Chat 联合定向套件：237 passed。
- Desktop Product、Shell、Package 和 Chat UI 收口套件：198 passed。
- Ruff、CPython `compileall`、`git diff --check`：通过。
- development Runtime Package 挂载检查确认包含共享 telemetry helper、GLM、Qwen4、
  Qwen3.6 text/VLM 与 DeepSeek V4/V4.1 的实时接口。
- 真实 DeepSeek V4.1 短推理生成 2 token，其中 1 个完整 Decode 步读取 83 个专家、
  1,560,453,120 bytes，pressure 34.583333%，recent 与 turn window 一致；推理正常结束。

本机没有同时驻留可安全运行的 GLM/Ornith/Qwen3.6 checkpoint；这些后端以真实缓存接口
形状、callback 保留和 SSE 合同测试验收。Qwen3.8 Flash Next checkpoint 存在，但在
V4.1 Worker 已占用大量统一内存时没有额外加载 41+ GiB 引擎，避免改变用户正在使用的
App 实例状态。正式发布前可在隔离机器各补一个 2-token smoke，预期不需要代码变更。

## Development 制品

- Package：`/private/tmp/ai2apps-runtime-omlx-1.8.5-development.ai2service`
- 大小：369,813,519 bytes
- SHA-256：`92fd5e0eebbd799ba8561025ff184abb93e4f90331b08b1898210fd319260742`
- package digest：`sha256:5d2e2cf76ff5fc2917504f6b9cc246ec9865e4a5611c2347a0819c7ecc791d14`
- V4.1 回执：`/private/tmp/dsv41-runtime-1.8.5-memory-smoke.json`

该制品使用临时 development Publisher，只用于本地审查。正式发布需按 Package runbook
重新执行 Developer ID 构建、公证与 staple，再用已有正式 AI2Apps Publisher key 构建
并发布 1.8.5；不得复用临时 Publisher envelope。

## 发布边界

1. Runtime 1.8.5 提供所有 Cached-MoE 引擎的 SSD SSE 数据，不要求模型 Package 或
   checkpoint 升版。
2. 正确的 `phys_footprint` 展示位于 Host/UI，必须随下一版 Desktop/App 源码纳入；无需
   把 Host 模块复制进 Runtime DMG。
3. 发布人员需对正式签名制品重复 Runtime 合同、挂载内容、隔离 Worker 和至少 V4.1
   真实 SSE smoke；条件允许时追加 GLM、Qwen3.6/Ornith、Qwen3.8 Next 各 2 token。
4. 后续发布任务已获得用户授权并完成公证、Cloud publication 与双外部源激活；模型
   Package 和 checkpoint 仍无需升版。
