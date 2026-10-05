# 独立上下文引擎 Python 移植

来源：DeepSeek Harness 固定提交 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`。
核心：`ai2apps/context_engine/`；宿主桥接：`ai2apps/agents/context_engine_adapter.py`、`session_memory.py`；模型计量通过 Runtime 的可选 `bind_context_provider` 注入。

## 边界与升级合同

核心仅依赖 Python 标准库，不导入 AI2Apps、MLX、模型 SDK、数据库或 Web 框架。
可将整个目录作为 `context_engine` 独立复制/安装，使用相同 API 运行。
Node 使用不可变 JSON 字符串快照；Surface 是带 Session 标识的有序节点，节点顺序而非数值 ID 决定区间。

核心四个宿主接口是：

- Surface/Route：宿主提供可见上下文和实际 provider/model、容量、输出预留与计量单位。
- Meter：宿主按同一模型计量消息节点和 envelope（包括工具 schema/请求 framing）；禁止混用 token 与字节。
- Summarizer：异步接收冻结来源及输出上限，返回完整的非权限级摘要节点。
- Store：持久 begin/commit/fail，提交必须原子完成来源/路由比较、可见上下文替换、来源记录与事务结束；重启须处理未关闭的 begin。

工具、审批、身份、模型调用、文件和业务服务不进入核心。升级核心先运行隔离合同测试，再运行宿主桥接及检查点恢复测试。API 改动应只影响该桥接层；不能在核心增加对宿主数据库结构的依赖。

## 当前移植范围

已移植：按窗口/输出预留/headroom 的压力预算、比例/绝对保留预算、精确 provider/model 策略选择、按可见顺序选区、完整工具配对、手动/压力/超限三种触发、冻结来源、区间变化拒绝、允许无关尾部追加、摘要实际缩减校验、事务取消/失败、有限压缩和有进展才重试超限。
工具配对比参考代码的数量平衡额外检查 call ID，属于本地加强。

源码对照：

| Python 合同 | 上游源码/行为测试入口 |
| --- | --- |
| Policy.budgets / Policies.resolve | compaction-basic/src/config.ts；配置默认值、路由覆盖、输出预留与保留冲突测试 |
| prepare / prepare_range / balanced_cuts | compaction-basic/src/region.ts、compaction/src/tool-pairing.ts；保留尾部、不可拆工具配对、非单调 surface 顺序 |
| replacement / compact | region.ts；来源稳定、摘要缩减、取消、持久开始/结束、无关追加 |
| with_overflow_recovery | compaction-basic/src/index.ts；仅窗口超限、有界次数、恢复后必须有进展 |

保留 DeepSeek MIT 许可和来源说明。这是行为与接口移植，不是整个 TypeScript/Cordis 运行时搬迁；未宣称完整上游测试逐项等价。

## 隔离验收

命令：

```sh
.venv/bin/python scripts/test_context_engine_isolated.py --receipt docs/context-engine-isolated-acceptance-2026-10-05.json
```

脚本只复制核心、MIT 文本和独立测试到新临时目录，建立无 system-site-packages 的新 venv，用 Python `-I` 执行，并断言没有导入 AI2Apps。不使用 Local 实例、真实用户数据库或模型缓存。测试结束删除临时环境；回执保存源码 SHA-256。测试 JournalStore 是测试适配器，不作为第二套生产存储。

首次独立验收 31 项通过后，才接入宿主代码。策略选择和摘要替换校验由独立核心执行；现有 RunStep 持久摘要调用、用户原文覆盖与状态投影保留在宿主层。宿主不需要更改各个业务工具。

## Session 宿主接入与验收

SessionMemory 以原 Messages 和 Events 为原始存储，用不可变 message/step ID 建立可见 Surface。读取不限于原 200/1000 条边界；旧 Run 已完成且配对完整的工具轨迹也进入 Surface，未完成/uncertain 工具不会投影为可执行调用。摘要步骤从普通决策转录中排除，继续消耗原 Run 的步数、时间与 token 预算。

摘要先冻结来源并记录 started，随后作为正常持久 ModelCallAction 执行；下一轮核对来源、结构与实际缩减，原子写入 committed/ended。不同 Run 同时压缩会显式拒绝；终止 Run 和 abandoned 模型步骤的未关闭事务可回收。同一来源无有效进展不会循环付费摘要，每 Run 最多 8 次尝试。原始消息/RunStep 不删除；摘要合并仍保留用户原文，包括此前检查点的原文侧记录。

`agent.read_session_memory` 允许当前授权 Run 分页读取同 Session 的冻结来源；跨 Session 拒绝。模型实际调用别名写入来源提示，回读页不递归裁剪。手动入口 `POST /v1/platform/sessions/{session_id}/memory/compact` 沿用 Session ownership，创建幂等 maintenance Run，tools=[]，不生成任务答案；一次提交即完成。

Session 摘要沿用 system、完整历史消息和工具 schema 的前缀，末尾追加摘要指令，通过既有 actor-owned cache namespace 调用模型。保留 schema 不授予摘要工具执行权，任何 tool-call/截断/非法格式响应都拒绝提交。当前 Run 的旧版检查点仍使用结构化来源提示；不宣称其请求有相同的缓存命中收益。

旧 Run 的大工具结果先通过独立 `pruning.py` 的无模型投影转为显式 head/tail/hash/原文引用，按事务持久化，最多一轮处理 8 条；原 RunStep 原文保留。投影保留 role/tool_call_id 和配对关系，回读页不重复裁剪。原文变更使投影失效。摘要模型中断的 failed/cancelled 尝试可回收并重新开始，已完成但非法的同来源摘要不会循环重试。

图片投影在独立 `images.py` 中实现。provider 确认超限时可省略最旧的一个非 pinned 输入图，记录独立事务并保留原图。模型收到明确省略通知、part index、hash 和回读来源；assistant 输出图及当前输入不省略。索引按 OpenAI content part，而上游按 image occurrence，这是有意的协议适配。

本地文本模型计量复用实际 serving tokenizer、系统消息转换、reasoning/template 参数与工具 schema，记录真实解析 model ID，保留输出空间。默认未指定输出上限时限定为 min(2048, capacity/4, serving default)，并明确写入实际模型请求；显式输出上限不偷偷缩小。小窗口的 host headroom 为 min(65536, capacity/8)，独立核心仍保留上游默认公式。计量在检查点回放后以及最终发出前执行；token 压力可在字节压力很低时触发压缩。

HTTP 或流内明确的 context_length_exceeded/context_window_exceeded，以及本地明确的 Prompt too long 错误才触发恢复；权限、网络、模板错误不触发。普通 General Run 最多一次模型超限重试，必须有可验证的请求变化；摘要自身超限停止，不重放业务工具。其他 executor 未实现恢复时明确失败。

本轮独立 35 项、宿主相关 78 个不同用例通过。宿主包含 Agent 回归 34、checkpoint 12、adapter 2、result reader 7、control 3、reliability 6、Session memory 12、serving meter seam 2。后者以抽取生产函数并注入假 engine 验证，不是实际 MLX/tokenizer 测试。初版发现局部变量名错误和手动维护重复压缩，修复后复测；两个旧问答恢复测试和纠错测试使用合理等待窗口复测，未改变成功条件。

## 明确的兼容与验收边界

远程、未知路由、custom extractor 和多模态计量返回 None，使用明确 UTF-8 字节回退及 provider-confirmed overflow；不声称准确视觉 token 计量或远程 token 计量。摘要来源分批仍按字节 admission 选区；最终 token gate 保证支持的本地文本路由不会带着超出窗口的受保护内容发出。无法有效压缩时保留原文并明确失败，不静默丢历史。

本地结构校验和用户原文侧记录不能保证所有 assistant 技术事实在摘要文本中语义无遗漏；原始证据可回读。这是 Python 行为移植加宿主适配，保留既有持久 Run 机制，不引入第二套 Cordis/Session 运行时。上游完整 Vitest 逐项等价、真实模型长任务成功率/耗时/token/缓存命中对照、故障进程实测以及 App-Dev 界面验收尚未完成。没有重启 App-Dev、重建 bundle 或生产发布；本次 omlx/server.py 是 embedded Runtime 改动，实际采用必须遵守固定 App-Dev builder 的重建流程。

最终验收回执：`docs/context-memory-host-acceptance-2026-10-05.json`，包括独立/宿主测试结果、准确源文件 SHA-256、未做真实模型验收/未激活/未发布标志。最终宿主合跑 78 passed，168.80 秒。

2026-10-05 后续实例激活：用户授权通过固定 builder 重建/启动 Dev、App-Dev、Test，三实例 healthy、memory API 与 reader 已注册，App-Dev/Test 嵌入关键源码一致，签名及适用完整 verifier 通过。回执 `docs/context-memory-instance-activation-2026-10-05.json`；这更新了前述“未激活”的历史状态，不构成真实模型效果或生产发布验收。Test Shell 当前停在登录页。
