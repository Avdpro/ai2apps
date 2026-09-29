# AI2Apps oMLX Runtime 1.8.4 DeepSeek V4.1 SSD 遥测修正

状态：已由 Runtime 1.8.5 候选取代。1.8.4 的 DeepSeek V4.1 修正和真实 Worker
验证保留为中间证据；1.8.5 在此基础上覆盖全部已发布 Cached-MoE 引擎，并修正 Host
内存口径。1.8.4 未进行 Developer ID 签名、Apple 公证或生产发布。

## 问题

Runtime 1.8.3 已把 `ssd_recent_10_tokens` 与 `ssd_turn_average` 接入 Worker SSE，
但实时接口只实现在旧 DeepSeek V4 的 `DeepseekV4FleshEngine`。AI2Apps 的 DeepSeek
V4.1 Package 实际创建独立的 `DeepseekV41Engine`，因此累计 token 与 Token Gen 可以
更新，SSD pressure 字段始终缺失，Chat 正确显示 `— / —`。

## 修正

DeepSeek V4.1 专用引擎现在：

- 在 Prefill 完成并释放 Prefill executor 后建立 Decode SSD 基线；
- 在每个完成 token 的既有安全边界更新最近 10 token 与整轮累计窗口；
- 从每层 resident bank 的已完成 `bytes` 和 `record_bytes` 精确换算专家读取次数；
- 以全部 routed layer 的精确 Top-6 字节作为 pressure 分母；
- 按 Session 导出 `get_live_metrics()`，并在 `get_stats()["flesh"]` 中提供空闲状态投影。

这些字段均由已有纯 Python 计数构成，不执行 MLX array 求值，不增加 Metal readback 或
GPU→CPU 同步。首个由 Prefill logits 采样的 token 不计入 Decode 步数或分母，避免短回复
低报 SSD pressure。

## 验证

- DeepSeek V4.1 窗口数学、Session 映射、Worker SSE、Cache-MoE Worker、Model Worker、
  Worker 管理、Runtime Package 与 builder 定向回归：79 passed。
- Ruff、CPython compileall 与 `git diff --check`：通过。
- 受限沙箱中的大套件导入 MLX 时没有 Metal 设备；改在具备 Metal 权限的本机测试环境
  运行 Runtime/Worker 61 项并通过。
- ad-hoc Package：369,730,125 bytes，SHA-256
  `ef08f8b6c835cf106be5543a6b4d92e15d99ceab092e837a093057c4bc932686`；挂载后的
  Runtime 包含 V4.1 实时接口与完成 Decode 步计数。
- 使用本机已有 475GB 共享 checkpoint 运行候选中的真实 V4.1 engine 和隔离 Model
  Worker。请求完成 1 个 Decode 步，实际读取 62 个专家、1,165,639,680 bytes；滚动窗口
  与整轮平均均为 25.833333%，`critical`。Worker SSE 与完成后的 `/v1/status` 数值完全
  一致，流以 `[DONE]` 正常结束。

待完成：构建 Developer ID 正式候选，进行 Apple 公证、Package 发布、三源激活和
App-Dev UI 复验。模型 Package 与 checkpoint 不需要升级。
