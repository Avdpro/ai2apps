# Qwen + DeepSeek V4 Flesh 三态审校级联

Status: design proposal, not implemented  
Date: 2026-08-09  
Target branch: `experiment/moe-cache`

## 1. 目标

用 Qwen 承担大多数长文生成，用 DeepSeek V4 Flesh（以下简称
DSF）审核答案的正确性和完整性。DSF 根据错误严重程度返回三种决策：

- `PASS`：Qwen 答案可直接交付。
- `REVISE`：主体正确，Qwen 按 DSF 的局部指令修改。
- `REPLACE`：核心结论或求解路线不可用，DSF 接管语义层求解，
  Qwen 只负责把 DSF 的权威要点组织成最终表达。

该设计利用 DSF cache-MoE 路径中 Prefill 相对快、Decode 相对慢的
特征：审核请求一次读入“用户问题 + Qwen 候选答案”，通过时只生成
一个很短的决策；只有必要时才生成修改指令或替换要点。

## 2. 非目标

- 不让 DSF 默认重写每个答案。
- 不把 LLM 审校当作可证明正确的形式验证。
- 不允许 Qwen 在 `REPLACE` 的润色阶段添加新事实、数字或结论。
- 第一版不做无限自我修正循环，也不做多审校模型投票。
- 不为实现该功能破坏现有 Qwen/DSF 引擎、router、attention 或融合
  MoE kernel。

## 3. 状态机

```text
User question
    |
    v
Qwen draft
    |
    v
DSF review #1
    |---------------- PASS ----------------> return draft
    |
    |---------------- REVISE --------------> Qwen constrained revision
    |                                             |
    |                                             v
    |                                        DSF review #2
    |                                             |
    |                                  PASS ------+------ REVISE/REPLACE
    |                                             |              |
    |                                      return revision   fail policy
    |
    `---------------- REPLACE -------------> DSF semantic blueprint
                                                  |
                                                  v
                                            Qwen realization
                                                  |
                                                  v
                                             DSF review #2
                                                  |
                                       PASS ------+------ REVISE/REPLACE
                                                  |              |
                                           return answer     fail policy
```

默认每个请求最多一次 Qwen 返修，随后只进行一次 DSF 复检。复检仍不
通过时不继续自动循环，而是进入显式失败策略。

## 4. 三态判定标准

### PASS

同时满足：

- 核心结论、事实、计算和逻辑正确。
- 用户的显式要求已满足。
- 没有会导致代码不可用或结论失真的实质性问题。
- 剩余差异只是措辞、风格或非必要的扩展。

### REVISE

适用于核心解法正确且可局部修复的答案，例如：

- 遗漏一个明确要求。
- 局部事实、计算、边界条件或代码有错。
- 一个或少量段落需要删除、替换或补充。
- 不需要重新求解，预计修改范围小于答案的约 30%。

### REPLACE

任一条成立即可进入：

- 核心结论错误。
- 推理路线根本不成立，必须重新求解。
- 存在多处相互关联的事实、计算或代码错误。
- 遗漏核心任务目标，局部修补无法交付。
- Qwen 的一次 `REVISE` 仍未解决实质性问题。

`REPLACE` 不应只由“问题看起来很难”触发。审校器应优先根据候选答案的
实际可修复性判断，避免大模型不必要地接管。

## 5. 内部协议

实现层使用结构化对象，不依赖自由文本标题解析：

```json
{
  "decision": "PASS | REVISE | REPLACE",
  "summary": "简短的机器可读原因",
  "instructions": [
    {
      "location": "段落、步骤、代码块或声明的定位",
      "problem": "实质性问题",
      "required_change": "最小可执行修正"
    }
  ],
  "blueprint": {
    "conclusion": "REPLACE 时的核心结论",
    "key_points": ["..."],
    "required_evidence": ["..."],
    "must_preserve": ["数字、公式、代码、限定条件或警告"],
    "must_not_claim": ["..."],
    "recommended_structure": ["..."]
  },
  "risk": "low | medium | high"
}
```

约束：

- `PASS` 必须使用最短输出；`instructions` 和 `blueprint` 为空。
- `REVISE` 最多返回 3 条指令，不输出完整替换答案。
- `REPLACE` 输出语义蓝图，而不是无限长的成品。
- 数学公式、精确数字、引用、API 名和代码块可放入 `must_preserve`，
  Qwen 整理时不得改写。
- 外部 API 不必向用户暴露该对象；它是编排器内部协议。

如果 JSON constrained decoding 的额外 token 成本不可接受，可将 DSF 首个
decision token 约束为 `PASS`/`REVISE`/`REPLACE`：`PASS` 后立即停止，其他两种
再继续生成结构化 payload。不应依赖前端展示文本做路由判断。

## 6. DSF 审校提示词

```text
你是严格的答案审校器。请根据用户问题、约束和候选答案，判断答案是否
可直接交付。

只检查：
1. 事实、计算、逻辑和核心结论；
2. 用户的明确要求是否完整满足；
3. 代码或操作建议是否存在实质性错误；
4. 是否包含危险、虚构或无依据的结论。

不得因个人写作偏好、非必要的扩展或轻微措辞差异要求返修。

决策规则：
- 可直接交付：PASS。
- 核心正确且可局部修复：REVISE，最多给出三条最小、明确、可执行指令。
- 核心结论或求解路线不可用：REPLACE，给出正确语义蓝图。

严格按内部协议输出，不要和候选答案对话，不要在蓝图外重写成品。
```

对第二次复检应使用更严格的精简 prompt，同时提供上一次的审校 payload，
要求 DSF 确认每条修正是否真正落地以及是否引入新错误。

## 7. Qwen 修订与表达约束

### REVISE prompt 要求

- 仅实施 DSF 列出的必需修改。
- 保留其他已通过内容，避免无关重写。
- 不使用修改指令之外的新事实弥补空缺。
- 仍按用户要求的语言、格式和长度输出完整可交付答案。

### REPLACE prompt 要求

```text
你的任务是将审校模型给出的语义蓝图组织成面向用户的答案。
不得新增事实、数字、引用、代码行为或结论。
不得删除蓝图中的限定条件、风险警告和 must_preserve 内容。
你可以调整顺序、添加连接语、改善可读性，但不得改变语义。
```

数学、代码、法律、医疗、财务和精确引用类任务不应让 Qwen 自由重述关键
内容。DSF 应把公式、数字、代码块和安全警告作为不可变片段，Qwen
只补充连接文字。

## 8. 推理和 token 预算

Prefill 只能让 DSF 并行读取问题和候选答案，不能完全替代复杂求解所需的
自回归推理。因此不应把 DSF 永久限制为单 token 判定。

建议初始预算：

| 路径 | DSF 输出预算 | 说明 |
|---|---:|---|
| `PASS` | 决策后立即停止 | 主要成本是 Prefill/TTFT |
| `REVISE` | 最多 128 tokens | 最多三条局部指令 |
| `REPLACE` | 最多 256 tokens | 只生成语义蓝图 |
| 复检 | 优先短判定，上限 128 tokens | 仅报告未修复或新引入问题 |

预算应为配置值，并在评测中根据错误召回率和端到端延迟调整。对复杂
数学、代码或高风险任务可允许更高的 DSF 审校预算；不应为了省 Decode
而伪装审核深度。

## 9. 失败策略

第二次复检不是 `PASS` 时，默认不做第二次 Qwen 自动返修。编排器按
配置选择以下一种：

1. `safe_return`：返回最后候选答案，同时标记“未通过自动复检”。
2. `dsf_complete`：仅对高风险或明确开启的请求，允许 DSF 直接输出最终答案。
3. `error`：内部工作流返回可重试错误，不对用户交付未通过内容。

另外：

- DSF 不可用或超时时，第一版应采用明确的 fail-open/fail-closed 配置，
  默认普通问答 fail-open，高风险模式 fail-closed。
- 协议解析失败可对同一 DSF 输出做一次约束重试，不应重跑 Qwen 初稿。
- 任何路径都必须有总超时和总 token 上限。

## 10. 与 Flesh 引擎的交互

- DSF 审核输入包含完整问题和 Qwen 候选答案，其主要计算落在 Prefill。
- 应使 DSF 常驻，否则模型加载会吞掉级联收益。
- 当前 DSF 实测进程增量约 54.18 GiB；Qwen、DSF、两者 KV cache 和
  MLX allocator cache 必须一起进行峰值内存验证。
- 当前 DSF 冷物理 scope bank 切换约需 3 秒。审校基准必须报告已激活
  scope 和切换时间，不能只报 Prefill TPS。
- Flesh 的物理 expert bank 是模型级可变状态，当前一个 DSF 引擎的推理
  请求会串行。第一版不承诺高并发 judge throughput。
- 首次审核和复检应使用稳定 session ID，但必须遵守现有 scope/
  lossy-policy namespace，不得在不同有效 expert bank 之间复用错误 KV。
- scope probe 对长输入保留少量前缀和主要后缀，候选答案会影响 scope
  判断。基准需检查初审与复检的 scope 稳定性。

## 11. 建议配置

```yaml
review_cascade:
  enabled: true
  generator_model: qwen3.6-35b-a3b-4bit
  reviewer_model: deepseek-v4-flesh
  max_rounds: 2
  revise_max_instructions: 3
  reviewer_revise_max_tokens: 128
  reviewer_replace_max_tokens: 256
  reviewer_recheck_max_tokens: 128
  replacement_realization: qwen
  on_recheck_failure: safe_return
  ordinary_failure_mode: fail_open
  high_risk_failure_mode: fail_closed
```

具体配置形式应遵循 DynaMoe 现有 model settings 和请求配置方式；上述
YAML 仅定义语义，不强制存储格式。

## 12. 可观测性

每个请求至少记录：

- 初审和复检的 decision、risk 和解析是否成功。
- Qwen 初稿、返修及 DSF 各阶段的 prompt/completion tokens。
- 每阶段 TTFT、Prefill TPS、Decode TPS 和总时间。
- DSF scope、scope 切换次数/时间、L3 expert loads、SSD 读取和峰值内存。
- 最终路径：`pass` / `revise_pass` / `replace_pass` / `review_failed` /
  `review_unavailable`。
- 从用户请求到最终答案的端到端 P50/P95 延迟。

生产 telemetry 不应默认记录用户问题、候选答案或 DSF 蓝图原文。评测
模式下如需保存内容，应显式开启并写入隔离的 artifact 目录。

## 13. 评测设计

至少准备以下样本：

- 已知正确的 Qwen 答案，测量 DSF 误杀率。
- 注入单个局部错误的答案，检查 `REVISE` 召回。
- 核心结论错误或推理路线错误的答案，检查 `REPLACE` 召回。
- 只存在文风差异的答案，检查过度修改倾向。
- 数学、代码、常识、长文、中英文及高风险类别。
- 触发 scope 保持和 scope 切换的混合请求序列。

质量指标：

- Qwen 初稿正确率和最终正确率。
- 错误答案召回率，以及正确答案误杀率。
- `PASS`/`REVISE`/`REPLACE` 混淆矩阵。
- `REVISE` 指令完成率。
- `REPLACE` 蓝图组织后的语义保真率，特别是 `must_preserve`
  片段的完全一致率。
- 返修引入新错误的比例。

性能指标：

- 三条路径的端到端延迟、TTFT 和总 tokens。
- DSF 审核 Prefill/Decode 时间占比。
- 冷/热 scope 、冷/热 KV 和顺序/交错请求的 P50/P95。
- Qwen + DSF 同时常驻时的 active/peak memory 和 swap。
- 串行 DSF 审核锁下的排队时间。

## 14. 第一版验收条件

在启用级联作为默认产品路径前，至少满足：

1. 协议解析和三态路由无模糊分支，有单元测试覆盖。
2. `PASS` 路径不修改 Qwen 原文。
3. `REVISE` 和 `REPLACE` 路径都有且只有一次默认返修，没有无界循环。
4. `must_preserve` 片段在 Qwen 表达后完全一致。
5. 超时、模型不可用、格式错误和复检失败均有确定策略。
6. 在固定评测集上，最终正确率明显高于 Qwen-only，且正确答案误杀率在
   预先设定的上限内。
7. 记录相同 prompts 下 Qwen-only、DSF-only 和三态级联的质量、内存、冷/
   热 TTFT 及稳态吞吐。

第 6 项的具体数值应在构建基准集后固化，不应在没有基线数据时伪造
门槛。

## 15. 建议实现顺序

1. 定义内部 decision/payload 类型、严格解析器及三态路由单元测试。
2. 实现无 HTTP 依赖的编排器，以可注入的 Qwen/DSF generate 接口做
   fake-engine 测试。
3. 接入现有 `EnginePool`，保持 Qwen 和 DSF 原有引擎表面不变。
4. 实现决策 token 约束、`PASS` early stop 和可配置 token 预算。
5. 加入 session/KV namespace、超时、取消传播和可观测数据。
6. 先提供显式 opt-in 的 API/模型配置，不默认改变现有 Chat Completions
   行为。
7. 跑固定质量与性能矩阵，再决定默认预算和是否扩大开启范围。

## 16. 待基准确定的问题

- DSF 是否可以在不降低错误召回的前提下，对高置信度 `PASS`
  真正做到决策后立即停止。
- 是否需要利用首决策 token 的 logit margin 将低置信度 `PASS` 升级为
  更深审核，以及该 margin 能否被校准。
- `REPLACE` 蓝图上限 256 tokens 是否足以覆盖数学、代码和长结构任务。
- 是否应根据任务类型选择 `Qwen realization` 或 `DSF complete`。
- 双模型在目标 Apple Silicon 上同时常驻的内存上限和 allocator cache
  管理策略。
- 在 DSF 串行锁和 scope bank 切换存在时，请求排序、按 scope 分组或
  微批审核能否改善 P95，又不伤害单请求延迟。

