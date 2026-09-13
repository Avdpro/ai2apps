# DS4.1F 2048-token Prefill 首次测量与 query 批处理

2026-09-13。用户确认目标：**2048-token Prefill 300 tokens/s、Decode 约 10 tokens/s**。尚未达到。最新已测试入口为 `experiments/dsv41_reference/run_metal_batched_attention.py`，接续全 FP8 Metal 的 `run_metal_cpu_order.py`。

## 本轮最终状态

- 全部普通 FP8 投影使用按 Prefill/GEMV 形状选择 CPU 归约顺序的 Metal 内核，原始量化字节未改变。
- CPU 普通权重缓存限额 12 GiB，实际约 7.94 GiB；已移除末端 CPU FP32 重排缓存。
- 每层 L1=8、LRU L0=24，总专家槽位原始字节约 22.41 GiB。专家读取仍为未修改的 GLM/Qwen C++ `preadv_fused_experts`，4 workers。
- Prefill 按专家合并独立 token/expert 对，恢复每个 token 原有的专家 ID 升序累加。
- 新增 `batched_attention.py`：一次处理 32 个独立 query，保留原 CPU block64 在线 softmax、BF16 probability、FP32 accumulation 和 sink 操作顺序。attention 仍在 CPU；这里是减少 Python/小算子调度，并未声称迁入 GPU。
- CPU router、输出头、非 FP8 算子、部分权重转换、activation quantization、host 路由、普通 FP8 权重上传和 CPU/GPU 往返仍在。尚无 I/O overlap 或 device-only all-hit。

## 实测

同一精确 2048-token raw text、1 次 Decode。prompt/token IDs/SHA-256 位于 `artifacts/dsv41-benchmark2048-prompt.json`。以下计时包括首次缓存填充、forward、读取和全 trace，不包括模型构建；OS 页缓存未清空，不是物理 SSD 冷测，也不是长期稳态服务吞吐。

| 2048-token 路径 | Prefill 秒 | Prefill tokens/s | 一步 Decode 秒 | 峰值 RSS GiB |
|---|---:|---:|---:|---:|
| 全 FP8 Metal，原逐 query CPU attention | 347.298 | 5.897 | 5.812 | 24.101 |
| 新 query 批处理 CPU attention | 266.920 | 7.673 | 4.243 | 26.757 |

Prefill 计时段缩短 **23.14%**。不是重复多轮严格 A/B 的稳定加速比，也不能从一步 Decode 推断长期 TPS。新路径两步合计：CPU sparse attention 32.539 s、专家 GPU 计算 66.004 s、native expert I/O 7.185 s；其余时间包括普通 FP8 投影、其他 CPU 算子、转换、同步和 trace，不能把全部剩余时间归为某一模块。

两版 native 专家逻辑读取均为 **104,418,754,560 bytes**，即约 97.25 GiB，含首次 L1 填充与后续 Decode；并非每次 Prefill 一定访问完整 268.945 GiB 专家存储。prompt 是重复构造的吞吐输入，不能代表所有自然输入的专家工作集。I/O 计时可受 OS 页缓存影响。

最新入口短输入计时：

- France，5-token Prefill 4.430 s，Decode 1.056 / 1.156 / 1.108 s。
- opposite，5-token Prefill 4.502 s，Decode 1.077 / 1.162 s。
- sky，26-token Prefill 7.482 s，Decode 1.106 s。

短 Decode 目前约 **0.9 tokens/s**，与原先约 0.4 tokens/s 相比有进展，但尚未接近 10 TPS；2048-token Prefill 也远未接近 300 TPS。

## 精度范围必须区分

1. 上述三条短输入（5、5、26 tokens）分别与独立 CPU golden 对照，所有保存张量逐位一致，最大有限差 0，共 3,546 张量 / 119,576,738 元素。
2. 2048-token 新旧两条混合路径对照，**416 文件 / 788 张量 / 4,327,663,181 元素**逐位一致，最大有限差 0。这证明 query 批处理在此输入上没有改变原混合路径结果。
3. **2048-token 尚未生成独立 CPU golden，不能将第 2 项称作 CPU 无损验收完成。** 比较器现已根据参考 manifest 区分 hybrid A/B 与 CPU golden，避免因基础 harness 标记 `backend=cpu` 而误报范围。

`test_batched_attention.py` 通过，覆盖 query chunk 边界、非整 block 长度、masked positions 和在线 softmax；`test_metal_cpu_order.py` 四项通过，包括三个保留原 M/N 的真实 FP8 舍入边界。未修改 CPU golden、有效状态或误差阈值；Engram 未使用尾部仍按既有规则规范化。

## 原生 MLX MXFP8 探索

`probe_native_mxfp8.py` 将原始 E4M3 字节打包为 uint32，仅展开原有共享 scale，不重新量化。原生 MXFP8 dequant 与原权重逐位对应。

在已捕获的 `[26,1280] × [32768,1280]` 矩阵上，设备驻留算子热调用：

- MLX 原生 MXFP8：约 0.92 / 1.03 ms。
- 当前严格归约 kernel：约 7.90 / 7.08 ms。

但原生结果转 BF16 后，851,968 个元素中有 **2 个与 CPU 不同**，最大差 `1.52587890625e-05`。这是诊断实验，**未接入无损主路径**。原生结果为 FP32、严格 kernel 输出为 BF16，且归约语义不同；以上不是可直接接受的等价替换加速比。

下一阶段需要真正的矩阵块计算以及可验证的 CPU 舍入兼容方案，不能直接以原生 qmm 的速度替代精度验收。当前逐向量 FP8/FP4 kernel 的长 Prefill 效率是明确的优化方向；GPU attention、专家缓存工作集和 I/O overlap 也仍有工作。

## 复现与产物

分支 `experiment/moe-cache`，HEAD `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`，未提交源码的精确哈希记录在 manifest。仅实验代码/文档变更，未修改官方模型、权重、原生 GLM/Qwen loader 或已发布 runtime。

```sh
.venv/bin/python experiments/dsv41_reference/test_batched_attention.py
.venv/bin/python experiments/dsv41_reference/test_metal_cpu_order.py
.venv/bin/python experiments/dsv41_reference/run_metal_batched_attention.py \
  --expert-store artifacts/dsv41-full-expert-store \
  --output artifacts/my-batched-attention-run --decode 3
```

2048-token 命令通过 JSON 读取 prompt，避免手工复制改变 token 数：

```sh
PYTHONPATH=experiments/dsv41_reference .venv/bin/python - <<'PY'
import json, sys, run_metal_batched_attention
p = json.load(open('artifacts/dsv41-benchmark2048-prompt.json'))
sys.argv = ['run_metal_batched_attention', '--expert-store',
            'artifacts/dsv41-full-expert-store', '--output',
            'artifacts/my-batched-attention-2048', '--prompt', p['prompt'], '--decode', '1']
run_metal_batched_attention.main()
PY
```

GPU 调用需 Metal 权限，新输出目录不可覆盖既有数据。规范化和比较命令沿用 README，2048 的参考选择旧混合路径，仅作为 hybrid A/B。

- 旧 2048：`artifacts/dsv41-metal-cpu-order-prefill2048-20260913/`。
- 新 2048：`artifacts/dsv41-metal-batched-attention-prefill2048-20260913/`，含 `hybrid-parity.json`，每版约 8.07 GiB trace。
- 三组 CPU 对照：`artifacts/dsv41-metal-batched-attention-20260913/`、`dsv41-metal-batched-attention-heldout-20260913/`、`dsv41-metal-batched-attention-prefill26-20260913/`，各自含 `parity.json`。
- 原生 MXFP8 精度/设备计时：`artifacts/dsv41-fp8-audit26-v2-20260913/native-mxfp8-timed.json`，含输入及 probe 源码哈希。
