# DS4.1F MLX视觉接入与footprint

2026-09-13。单序列、单图/双图纯MLX实验，原始权重，Main40/Hot8、动态L1、
完整Top6、Prefill双缓冲64，沿用65十进制GB峰值约束。无生产Runtime集成。

## 结构与实现

官方视觉编码器是稠密ViT，不是MoE：32层、dim1024、16头、MLP inter2816、
14×14 patch，图内全双向attention和2D RoPE。3×3 channel-major unfold后由
两层aligner投影到LLM dim5120。权重直接驻留，不使用SSD专家换入换出。

| 视觉权重部分 | 原始字节 |
| --- | ---: |
| ViT | 823,685,120 |
| Aligner | 146,821,120 |
| 三个image分隔符embedding | 30,720 |
| 合计 | **970,536,960** |

均保留checkpoint dtype（视觉部分BF16）；主干40层新增VL router bias共61,440字节。
图像token进入主干后仍然使用MoE，以原`bias_vl`选专家；不能将视觉塔稠密误解成
整个视觉推理没有MoE。每token的原Top6 unbiased权重归一化规则不变。

新增 `experiments/dsv41_mlx/vision.py`：官方resize/grid规划、RGB归一化/patch排列、
MLX ViT、aligner。图片前处理用PIL读取/缩放，数值前向在MLX。runner从原checkpoint
的encoding/encoding.py构造chat提示，每张图展开start/image/newline/end span并覆盖
输入embedding，之后再展开mHC。多张图共享同一套视觉权重。

Engram额外处理：图片位置置DEAD，遇到图片后更早的n-gram来源用PAD屏蔽，图片
自身的Engram gate置零；后续Decode沿用已屏蔽的历史。此处不能只改embedding。

## 内存实测

每例固定继续32步Decode；其余参数相同。单图等长度文本对照使用457-token普通
文本，控制长度但内容/路由不同，不能声称所有workspace完全相同。

| 输入 | 总prompt tokens | 图像span tokens | 峰值GB |
| --- | ---: | ---: | ---: |
| 等长度纯文本 | 457 | 0 | **57.043** |
| 胡萝卜，cap256 | 243 | 230 | **58.114** |
| 胡萝卜，cap1024 | 457 | 444 | **58.249** |
| 胡萝卜＋玉米，各cap1024 | 653 | 444＋189 | **58.290** |

高预算单图相对等长度文本峰值增加 **1.206GB**。视觉权重原始payload约0.971GB，
首个样本单独加载权重阶段的进程footprint由0.219升到1.403GB，增加约**1.184GB**；
allocator等开销使footprint不等于原始权重字节。图像编码完成时约1.796GB，随后
主干权重及专家bank加载决定整个模型峰值。视觉权重保持驻留，未卸载以压低结果。

图像样本Prefill完成、释放scratch后约56.89GB，32步结束约56.85～56.86GB。
双图没有复制视觉塔，因此不会简单增加另一份0.971GB权重。所有测量无Torch、
输出有限且峰值低于65GB。cap1024是上限，本组图片并未达到1024图像token；
不能将58.29GB当作任意高分辨率、多图、视频或长上下文的峰值承诺。

本轮Prefill step计时不含预先显式加载视觉权重及图像前处理，不用于宣称视觉
端到端速度。footprint采样覆盖视觉权重加载和模型推理，且保留各阶段current/peak。

## 验证

- 官方示例胡萝卜图，在cap256/1024均正确识别为胡萝卜。
- 双图正确回答“第一张图是胡萝卜，第二张图是玉米”。
- 固定步数benchmark忽略EOS，EOS后可能出现重复/无意义文字；质量检查只读首个EOS前回答。
- 官方image_processor与MLX前处理在胡萝卜cap256的patch tensor逐值一致。
- 独立官方CPU ViT+aligner参考，使用原权重、6×7 patch grid（含aligner padding）：
  最终6×5120特征max_abs=0.00097656，RMSE=0.00014746，参考RMS=0.0283493，
  cosine=0.99998651。这是BF16近似一致，不宣称逐位一致或完整VL CPU真值验证。
- 图像n-gram边界与后续Decode的hash和独立整数公式逐值一致。
- 纯文本2048+32回归的33份logits与接入前Hot-direct版本逐值一致。

初版仅支持local image路径、单序列、一次Prefill包含所有图片。图像场景Burst
目前显式拒绝，等待独立质量验收。没有视频编码、多轮图像缓存、会话恢复、
取消/并发或AI2Apps Runtime服务化验收。

## 使用与证据

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --image artifacts/dsv41-download/DeepSeek-V4.1-Flash/inference/examples/images/carrots.jpeg \
  --prompt '请简短说明图片里是什么食材。' --vision-max-tokens 1024 \
  --prefill-slots 64 --decode 32 --output <fresh-output>
# 双图：再添加一次 --image <second-path>
```

- `bench_vision.py`：高预算单图、双图、等长度文本及2048文本回归。
- `vision_cpu_reference.py` / `test_vision_mlx.py`：独立官方CPU视觉参考与MLX比较。
- `vision_processor_reference.py`：官方前处理fixture；`test_vision_masks.py`：Engram边界验证。
- `summarize_vision.py`：验证trace哈希并汇总内存与首段回答。
- `artifacts/dsv41-vision-{carrots256,carrots1024,two1024,matched-text,text-regression}-20260913`。
- 汇总：`artifacts/dsv41-vision-summary-20260913.json`。

manifest保存原图SHA256、ViT网格、image span、视觉权重字节、阶段footprint与源码
哈希。初次视觉run的通用scope字符串仍写有旧no-vision字样；实际执行以images、
config、image_inputs和vision_stages为准，汇总已说明，后续runner该字段已修正。
所有旧产物及v2 Tag保留。
