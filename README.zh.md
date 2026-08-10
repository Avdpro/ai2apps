# AI2Apps

端侧超模生态系统——面向 Apple Silicon 的本地优先 Fusion 与 Cache-MoE 推理平台。

AI2Apps 是一个独立项目，基于开源项目
[oMLX](https://github.com/jundot/omlx) 的推理运行时构建。它面向 DeepSeek
V4 Flesh 等超大 MoE 模型，增加了 scope 选择、路由专家缓存、SSD 专家存储、
可选有损加速、session 安全的 KV 复用，以及 AI2Apps 专属可观测能力。

> AI2Apps 与 oMLX 项目及其维护者不存在隶属、合作、赞助、认证或背书关系。
> oMLX 名称仅用于说明运行时来源，完整归属见 [NOTICE](NOTICE)。

[English](README.md) · [架构](docs/architecture.md) ·
[Flesh 引擎](docs/deepseek-v4-flesh-engine.md) ·
[Benchmark 记录](docs/moe-cache-benchmark-2026-08-08.md)

## AI2Apps 增加了什么

- 可配置的扁平或树形 scope catalog。
- 仅通过主干与 shared expert 完成 scope probe，默认 16 层，可配置到 43 层。
- 每个 scope 独立的静态专家 bank，并保持 Top-K 路由在设备端执行。
- `exact`、`conservative`、`tail1`、`tail2`、`head2` 五档策略。
- expert-major SSD 格式及 cache-aware fallback 加载。
- 多轮 session 与按 scope 隔离的 KV-cache 复用。
- OpenAI 兼容 API、AI2Apps CLI、聊天界面与实时 scope/cache 状态。
- Prefill、decode、miss 捕获、I/O 和 scope 的可复现实验工具。

继承自 oMLX 的运行时继续提供模型加载、attention、融合 MoE kernel、连续批处理、
分页 KV cache、音频/VLM 引擎、MCP 集成及原有的后台管理能力。

## 目录边界

```text
ai2apps/                 AI2Apps 产品包和公共 CLI
omlx/                    内嵌并经过修改的 oMLX runtime
  engine/flesh.py        DeepSeek V4 Flesh 请求编排
  cache/                 KV 与 MoE 专家存储
  patches/deepseek_v4/   scope 路由、专家 bank、策略和 kernel
  admin/                 由 runtime 托管的 AI2Apps WebUI
configs/                 scope catalog 与 profile
scripts/                 转换、profile 和 benchmark 工具
docs/                    架构及实验记录
artifacts/               本地实验输出
```

为避免破坏已经验证的 runtime，Python 的 `omlx` import namespace 和
`OMLX_*` 环境变量暂时保留。新应用应使用 `ai2apps` 命令，并从
`ai2apps.runtime` 导入产品引擎。运行数据也暂时保留在 `~/.omlx`，避免升级时
丢失已有模型、配置和 KV cache。

## 安装

需要 Apple Silicon Mac、Python 3.11–3.13 及支持 Metal 的 macOS。

```bash
brew install uv
uv sync --dev
source .venv/bin/activate

ai2apps --version
ai2apps info
```

也可以自行创建 Python 3.11–3.13 虚拟环境，再运行
`python -m pip install -e '.[dev]'`。

## 启动与 API

```bash
ai2apps serve --model-dir ~/models --port 8000
```

- 聊天界面：<http://127.0.0.1:8000/admin/chat>
- 管理后台：<http://127.0.0.1:8000/admin/dashboard>
- OpenAI Base URL：<http://127.0.0.1:8000/v1>
- 对话：`POST /v1/chat/completions`
- 模型列表：`GET /v1/models`

旧的 `omlx` 命令暂时作为兼容别名保留；新文档和集成统一使用 `ai2apps`。

## 配置 DeepSeek V4 Flesh

通过 AI2Apps 下载源安装的模型会自动使用版本包内置、经过校验的 Scope Pack。
只有手工研究环境需要通过公共环境变量覆盖 expert store 和 scope profile：

```bash
export AI2APPS_DEEPSEEK_V4_EXPERT_STORE=/path/to/expert-store
export AI2APPS_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/scope-profile.json
export AI2APPS_DEEPSEEK_V4_SCOPE_NAME=general
export AI2APPS_DEEPSEEK_V4_SCOPE_PROBE_DEPTH=16
export AI2APPS_DEEPSEEK_V4_SCOPE_LOSSY_MODE=exact

ai2apps serve --model-dir /path/to/models
```

`ai2apps` 入口会把 `AI2APPS_*` 变量转换到保留的 `OMLX_*` runtime 接口，
因此旧部署配置仍可继续使用。AI2Apps 准备的模型不需要设置 profile 覆盖变量。
有损模式必须显式开启。质量敏感场景使用 `exact`；部署 `conservative`、
`tail1`、`tail2` 或 `head2` 前，应使用真实 prompt 做质量和速度评估。管理后台会
展示当前 scope、probe 层数、有损模式、scope 切换次数和 fallback 次数，并且
读取这些状态不会引入新的 GPU 同步。

## 开发与性能门槛

实验分支为 `experiment/moe-cache`。除 AI2Apps 功能需要的局部改动外，应保留
oMLX 原有的模型、attention、router 和融合 MoE kernel。所有性能对比必须使用
相同 prompt 与生成 token，并记录内存、cold TPS 和 steady TPS。

```bash
pytest -q
python scripts/bench_scope_once.py --help
python scripts/bench_moe_expert_store.py --help
```

动态替换进入生产阶段前，静态 oracle bank 必须满足：Top-10 完全一致、运行期
零 miss、常驻内存下降，且 steady-state TPS 至少保留 full-resident 的 85%。

## 来源、许可证和品牌声明

AI2Apps 基于 oMLX commit
[`49ec271`](https://github.com/jundot/omlx/commit/49ec271676ba9c14bbebb75da1912e3fcb5fb0f4)
开发，并保留上游版权与归属信息。AI2Apps 的修改由文件内容和 Git 历史标识。

本项目采用 [Apache License 2.0](LICENSE)：Copyright 2025 oMLX
contributors；Copyright 2026 AI2Apps contributors。Apache-2.0 不授予对上游
商品名或标识的广泛使用权，因此 AI2Apps 不使用 oMLX 名称或 Logo 作为产品
标识，也不声称获得 oMLX 项目或维护者的合作、认证或背书。
