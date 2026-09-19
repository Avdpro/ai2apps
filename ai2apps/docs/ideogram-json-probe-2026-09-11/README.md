# Ideogram JSON 实机对照（2026-09-11）

目标：在更新 Package 前验证纯代码 JSON 包装是否解决普通提示词出灰图的问题。
所有测试不调用聊天模型、不调用 Magic Prompt、不修改模型权重或安全逻辑。

环境：App Dev 已安装的 `ai2apps.runtime.omlx` 1.6.2 的 Python 3.11，
Package `ai2apps/model-ideogram4-mlx` 0.1.1 当前源代码，现有原生 Q4 派生缓存。
直接调用 Package pipeline，未启动新的 Managed Service；这些不是签名安装/沙箱验收。
首次尝试开发 `.venv` 因缺少 mflux 在出图前退出，不计为模型测试结果。

统一条件：1024×1024、seed=0。前六项使用官方 `V4_TURBO_12`：
12 步，mu=0.5、std=1.75，CFG 索引顺序 `[3] + [7] * 11`。
第七项使用 `V4_DEFAULT_20`：20 步，mu=0、std=1.75，CFG `[3] * 2 + [7] * 18`。
JSON 为 UTF-8 字符串，紧凑序列化，不转义中文。输入、图片、原始耗时报告与校验结果均在本目录。

| 输入 | 文件前缀 | 实际图片 |
|---|---|---|
| 中文短句最小 JSON | zh_minimal | 灰色安全拒绝画面 |
| 等义英文短句最小 JSON | en_minimal | 灰色安全拒绝画面 |
| 英文完整场景 JSON | en_detailed | 熊猫吃竹子 |
| 中文短句＋固定风格/背景模板 | zh_template | 灰色安全拒绝画面 |
| 英文短句＋同一固定模板 | en_template | 灰色安全拒绝画面 |
| 中文完整场景 JSON | zh_detailed | 熊猫吃竹子 |
| 中文固定模板，20 步 | zh_template20 | 灰色安全拒绝画面 |

最小 JSON 将用户原文放在 high_level_description 与单个 obj.desc 中，background 为空。
固定模板保留原文，加入通用摄影风格，background 为固定前缀加原文，未做语义拆解。
完整中英文场景是测试前准备的静态对照输入，含具体竹林背景和熊猫动作；
它们不是普通短句经已实现的算法自动转换出来的。不能用这两项成功声称短句适配已经实现。

官方 CaptionVerifier 对七份输入均返回空警告列表，见 validation.json。
校验器 SHA-256：e6808c1068cb16937b26a95c1915900c051f35deea9292cb476bffcd3e7ce2b8。
来源：https://raw.githubusercontent.com/ideogram-oss/ideogram4/main/src/ideogram4/caption_verifier.py

当前证据表明：合格 JSON 的构建本身不依赖额外 AI，但格式校验通过不能保证真实出图。
本例中英文的完整场景均有效，不能认定中文必须翻译，也不能认定必须接入 LLM。
最小包装与通用模板未通过真实出图门槛，不能将其作为已修复方案发布。
本轮未执行图生图验收，未构建、更新版本或发布 Package。

已撤回公共平台 `/ideogram-caption` 和聊天模型扩写路径，恢复标准 composed prompt 调用。
Imagine Studio 回归14/14通过，指定文件 diff 检查通过。通过固定 app-dev Helper 重启 Local，
确认固定 App Dev Shell 新端口53496正常启动。未影响其他实例。

原始报告中的 operation 错标为 image_edit 是现有 pipeline 在输出阶段重用 image 变量的
遥测问题；本轮所有调用均未传 image，实际执行文生图。报告按原样保留，不拿此字段冒充图生图验证。

源码 SHA-256：

- pipeline.py: a511d0ed932c712e540c08460b71f655ca61b471d1b5d0f4b8c7af9c3be452b2
- text_encoder.py: 77768688e822bb48a5bb1a3b840ebb47393e612ecf28fca1c8aa42096ef0c51f
- scheduler.py: 05df0675cd329ef9cd704037d5697f11e429b88bca0d3d99a3c3188e50c1b3f7
- worker_adapter.py: 351bd0fbbac32e853a5a8dd0052305a89c6fd6753bc3d42695818f944668aac4

复现：本目录 probe.py、templates.py、followup.py 保存测试脚本原件。
脚本引用本机已安装 Runtime 与模型缓存，并将输出放入 /tmp/ideogram-json-probe。
使用上述 Runtime 的 Python3.11按顺序运行三个脚本；普通开发 .venv 不具备相同依赖。
