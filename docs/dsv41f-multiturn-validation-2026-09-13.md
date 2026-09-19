# DS4.1F 多轮文本与图像对话验证

2026-09-13。完整Top6、Main40/Hot8、动态L1、Prefill双缓冲64、Hot直接交接，
图像cap256，65十进制GB峰值约束。新CLI支持`--messages-json`传入完整消息历史，
通过官方chat编码按时间顺序展开历史图像；`--stop-at-eos`为本测试提前停止，
既有固定步benchmark默认行为未改变。manifest的decode_forwards记录实际步数，
requested_decode_forwards记录请求上限。

## 全历史重放：9轮通过

每轮独立启动模型，传入真实前轮assistant回答及全部历史消息；不是每轮单独
问一个互不相关的问题。历史图片保留在早先user消息中，不要求最新消息重传。
每轮重编码和重算历史图像/主干，不宣称复用了旧KV或视觉features。

| 用例 | 输入tokens演进 | 验证结果 | 本组最高峰值GB |
| --- | --- | --- | ---: |
| 纯文本3轮 | 24 → 46 → 67 | 记住青松、团子，正确回答周六上午九点 | 55.957 |
| 跨128窗口的文本2轮 | 210 → 239 | 保留林舟、成都；用新时间周日下午三点替换旧时间 | 56.856 |
| 图像4轮 | 247 → 302 → 517 → 538 | A为胡萝卜；无新图追问仍记住；追加B玉米后顺序正确；最后回答玉米是B | 58.266 |

图像1/2轮历史各含1张图，3/4轮各含2张图。所有9轮正常EOS结束，没有把EOS后
的无意义固定步续写当作回答。示例末轮：

- 文本：“你的代号是青松，猫的名字是团子，体检时间是周六上午九点。”
- 长文本更新：“你的名字是林舟，目的地是成都，最新出发时间是周日下午三点。”
- 图片顺序：“胡萝卜、玉米”；最后无图追问回答“B”。

纯文本第3轮、视觉第4轮分别再次独立重放，全部logits逐值一致。图像SHA256、
输入tokens及输出trace哈希已核验。所有运行无Torch、输出有限、峰值低于65GB。
这些是有限样本的语义/数值验收，不是通用多轮质量基准。

## KV增量续接：Top1一致，但不是逐值等价

另外做4段独立诊断：text1→3、text-long1→2、vision1→2、vision3→4。
段首正常Prefill，其后保留同一模型状态；把新消息前缀逐token送入，并固定喂入
完整重放参考中的assistant token。每轮比较末位Prefill和最多后续8个Decode
位置。先验证下一轮官方编码前缀与已消费token完全一致，防止错误复用。

| 诊断段 | 检查位置 | Top1一致 | 最大KL |
| --- | ---: | ---: | ---: |
| 文本1→3 | 13 | 13 | **0.103755** |
| 长文本1→2 | 11 | 11 | 0.000139253 |
| 图像1→2 | 11 | 11 | 4.33e-10 |
| 图像3→4 | 6 | 6 | 2.16e-9 |

合计41/41 Top1一致，其中段首检查属于完整Prefill控制，不应全部描述为新增
上下文检查。后续续接并非logit逐值一致：总体最大绝对差约4.531，文本某位置
KL达到0.104。不能仅凭Top1一致判定无损KV复用通过，也不能未经定位就将它
全部归因于BF16舍入。该诊断使用teacher forcing，不代表完整自由生成续接
在所有位置都会与重放相同。

现阶段没有把增量KV诊断变成默认多轮执行器。模型只支持非零offset的单token
forward，不支持多token增量Prefill；新增图像也不能逐token当作普通文本追加。
视觉第3轮加入新图时明确重新完整Prefill，诊断分段从第3轮重新开始；第4轮
没有新图，才测试复用含两张图的状态。不存在已实现的增量新图路径。

## 当前建议与待办

- 当前可用且本次通过的多轮方式：每轮完整历史重放，原图路径和消息顺序保持。
- 文本/旧图追问的KV续接仍为诊断，需定位与整块Prefill之间的数值差异，再扩展评估。
- 新图追加暂采用完整重放；后续需实现带offset图像embedding/掩码及相应状态续接。
- 尚无多会话隔离、并发、取消、session序列化、生产API及Runtime集成验收。
- 未开启Burst，不把本轮结果外推到有损多轮。

## 使用与证据

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --messages-json <history.json> --stop-at-eos --decode 64 \
  --prefill-slots 64 --vision-max-tokens 256 --output <fresh-output>
```

history.json为官方支持的messages列表，保留user/assistant历史。图片使用
`{"type":"image_url","image_url":{"url":"/local/path.jpg"}}`内容块。当前只接收本地路径。
`--messages-json`不能与`--image`或`--prompt-json`混用。

脚本：`bench_multiturn.py`、`bench_multiturn_long.py`、`audit_multiturn_kv.py`、
`summarize_multiturn.py`，均位于experiments/dsv41_analysis。
证据目录 `artifacts/dsv41-multiturn-20260913/` 包含逐轮messages/transcript、
manifest、完整logits、KV诊断和repeat比较。总报告为该目录的summary.json。
所有旧Tag和测试产物保留，无生产Runtime改动。
