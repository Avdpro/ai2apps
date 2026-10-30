# OXR 本地验证、Runtime 与 Package 接入技术方案

日期：2026-10-30。状态：设计，未实施、未发布。

## 1. 目标与实施顺序

先在隔离的本地实验环境跑通 OXR，再验证 AI2Apps Runtime 候选，随后发布 Runtime、发布依赖该 Runtime 的 OXR Package，最后增强知识库。每阶段通过验收后才能进入下一阶段；本方案不授权现在升级固定开发环境或发布产物。

首期交付为 Apple Silicon 上单张图片的文字/整页识别。复杂 PDF 版面、表格结构和阅读顺序作为后续独立验收范围。OCR 原文与通用视觉模型生成的图片描述分开保存，不能把推测描述当作识别文字。

## 2. 已核实基线与待验证项

- 调研源码 HEAD：`fa377dcb62875d5c82fc8177afd4277cd2357db9`；工作区已有大量其他变更，该 HEAD 不代表完整实验源码。实验须额外记录相关文件差异和依赖锁。
- 根 `pyproject.toml` 通过 uv 固定 mlx-vlm `78b96eb5462141447b9a6b4943ef553891da56dd`；开发 `.venv` 的 direct_url 与此一致，安装目录没有 OXR 模块。开发环境证据不代表已分发 Runtime 内容，后者须另外读取构建清单与安装收据。
- oMLX 已有 VLM 模型发现、图片预处理、图文 embeddings 与语言模型生成路径。`vit_config` 可触发视觉模型兜底发现，但 OXR 尚无明确登记。
- 知识库现有文件落盘、哈希去重和后台导入队列；图片只产生 metadata 占位文本。文档 ParsedBlock 已有类型和页码，尚无统一坐标及识别来源字段。
- mlx-vlm PR #2560 已合入 OXR；不能据此断言 oMLX 的调度、缓存及批处理已兼容。
- 当前工具会话访问 Metal 失败；必须在可访问 GPU 的本机实验进程完成真实验证，禁止用 mock 结果宣布本地跑通。

参考：

- https://github.com/Blaizzy/mlx-vlm/pull/2560
- https://github.com/Blaizzy/mlx-vlm/blob/main/mlx_vlm/models/oxr/README.md
- https://github.com/SoMarkAI/OXR/pull/14 （调研时仍未合并，仅作参考）
- https://github.com/SoMarkAI/OXR/blob/main/LICENSE

## 3. 阶段 A：独立本地实验

在仓库内 `experiments/oxr_mlx/` 建立独立环境、脚本、样本清单和结果收据，不改主依赖锁、现有 `.venv`、固定 Dev/App-Dev、用户数据或已安装 Runtime。模型缓存和输出使用实验专用目录，权重不提交 Git。

1. 固定一个包含 OXR 的 mlx-vlm 精确提交，锁定 Python、MLX、Transformers、Pillow 等依赖；记录权重 revision、文件清单、SHA-256 和许可证。
2. 优先使用原始 OXR 权重及 BF16 做基线，使用上游 processor、任务提示词、temperature=0。记录图片 resize 参数、token 上限和停止原因。
3. 先验证 CLI/Python 独立加载和识别，再测冷启动、暖运行、连续任务、取消、OOM 与模型卸载。
4. 覆盖中文印刷、混合语言、截图、小字、旋转图片、手写、公式、表格、空白与损坏文件。整页识别与专用表格/公式提示分别记录。
5. 确认 BF16 基线后再评估 8-bit；遵守上游视觉 tokenizer/head/embedding 保留精度的策略，不默认全模型 4-bit。

验收证据：机器与系统信息、源码/权重锁、可复现命令、输入哈希、原始输出、人工标注、CER/WER、截断率、冷/暖端到端耗时、峰值进程内存及 MLX 内存。区分加载、视觉预填充和生成耗时。

门槛：所有有效样本有可审阅输出；空白图不生成虚构长文；长输出不能静默截断；损坏输入明确失败；连续至少 20 次请求无持续内存增长；取消后任务结束且可继续使用。质量阈值在首批标注集建立后冻结，不能用单一英文示例宣布中文或表格达标。记录实测支持的设备档位，不预先承诺内存需求和速度。

交付：实验 README、版本锁、评测收据、限制清单及进入阶段 B 的 go/no-go 结论。

## 4. 阶段 B：Runtime 候选兼容

阶段 A 通过后，基于现有 Runtime 构建合同制作隔离候选，先不替换用户运行环境。

- 对比“升级 mlx-vlm 固定提交”与“最小回移植 OXR”的依赖差异、维护成本和回归风险，再选方案。禁止临时安装不固定的 main 作为发布依赖。
- 沿用 VLM 引擎和 Model Worker 生命周期，补模型发现、processor 注册、提示词模板和能力声明；不修改 MoE router、attention 或 fused kernels 来适配 OCR。
- 检查 language_model/layers、get_input_embeddings、prefill、KV cache、流式输出与停止标记、取消、并发和卸载。先限制单请求，批处理作为独立验收项。
- 同一输入对比阶段 A 与 Runtime 候选输出；首选贪心 token 对齐，若无法严格一致则说明原因并审查文本差异。
- 对已有代表性纯文本和视觉模型跑回归，确认现有兼容补丁仍生效；检查候选实际安装内容，而不只看源码依赖。

需要修改嵌入 Runtime 时，按标准 App-Dev builder 重建并在隔离实例验收，遵守 source-root、签名及实例身份合同，不通过旧快照覆盖激活。实施开始即更新根 Desktop next-release ledger；本次只有设计，不创建已实施条目。

## 5. 阶段 C：发布 Runtime，再发布 OXR Package

构建或发布前完整阅读 `docs/ai2apps-package-publication-runbook.md`（Git 根目录），按其中固定签名构建和发布入口执行。本方案不预定新的 Publisher、Package ID 或版本；沿用届时确认的发布上下文。

顺序：Runtime 候选验收 → 签名 Runtime 发布 → 确认 published 及安装验证 → 构建/签名 OXR Package → 发布及安装验证。

Runtime 承担推理依赖和兼容代码；OXR Package 承担固定权重、模型配置、能力元数据、许可/NOTICE 和最低 Runtime 依赖，避免重复携带通用运行环境。字段及 adapter 形态以现有 Model Package 合同为准，不在本方案发明第二套机制。

验证全新安装、旧 Runtime 依赖提示/升级、离线推理、卸载重装及升级失败恢复；哈希、签名、权重精度与实验一致。若已有 submission，查询并续跑，避免重复提交。保留旧 Runtime/模型可恢复路径，但不允许新 Package 在旧 Runtime 下静默失败或运行不受支持的模型。

OXR 不是无附加条件的 Apache 2.0。分发前记录融资/收入门槛、在线署名和托管 API 限制的适用结论；需要授权时先解决。若涉及 Cloud 元数据/API 变更，只编写 Cloud 需求交接文档，不在本仓库改 Cloud 实现。

## 6. 阶段 D：增强知识库

发布安装链路验收后，再实现知识库消费 OCR 能力：

- 文档服务提供 provider 无关的识别接口，输入为有权限的文件引用与识别选项；后端支持本地 OXR 和显式选择的多模态 API。不要把 OCR 业务逻辑放入通用 Agent。
- 结果保存全文、结构块、页码、可选坐标/阅读顺序、模型及版本、输入哈希、提示词版本、截断和错误状态；没有真实坐标时保持为空，不伪造。重识别按版本提交结果，防止旧任务覆盖新版本。
- 复用后台导入基础设施，但将“原图保存成功”与“识别完成”区分。持久化排队/运行/成功/失败/取消状态，支持恢复、重试及明确取消；重试不能重复建条目。
- 原图始终保留；识别完成后原子更新有效文本及索引变更事件，确保全文和语义索引失效/重建。删除与权限撤销后，排队任务和派生数据不能继续暴露内容。
- 界面展示识别状态、原图、识别文字、失败原因及重新识别入口。远端识别按用户配置执行，不能因本地失败而静默把私有图片上传 API。
- 普通照片描述单独标记为模型生成；将 OCR 输出视为不可信资料，不能作为 Agent 指令或授权。

扫描 PDF 后续增加逐页渲染、方向修正、分辨率/页数限制。复杂版式增加独立 layout 后端、区域裁剪、任务提示和阅读顺序合并；评估 CPU/MPS/其他部署方式，不能把识别模型支持 MLX 等同于 layout 已支持 MLX。

知识库验收覆盖图片导入后检索/问答命中、原图引用、重复导入、重新识别、重启恢复、取消、删除、私有/共享边界，以及索引故障恢复。涉及 AaAT 暴露时，先读当前 AaAT 合同和集成指南，由知识库 owner 声明能力并运行根目录 `python ai2apps/tests/run_aaat_boundaries.py` 及 owner 测试。

## 7. 决策与交付清单

当前仅批准方案顺序：A 本地实验 → B Runtime 候选 → C Runtime/OXR Package 发布 → D 知识库。各阶段独立提供结果收据，不能用前阶段成功替代后阶段验收。

尚待实验回答：当前设备峰值内存、中文/小字/手写质量、合理 token 上限、量化损失、与聊天模型共存策略、是否需要第一版就引入 layout。阶段 A 不依赖 Cloud 或正式 Package 发布，可先独立推进。
