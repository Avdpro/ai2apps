# AI2Apps 内部候选收敛与缺口审查（2026-10-25）

状态：0.1.8 / Build 2263 内部签名 App/DMG 已完成基础验收；完整实机验收与正式发布门禁仍未关闭。

用户范围：暂停新增功能，优先完善现有功能链路、排查缺失并验收内部候选；通过后再发布。

## 基线与范围证据

- 匿名生产清单实查：0.1.7 / Build 2262，stable，10000 basis points；与既有生产回执一致。
- 当前 checkout：experiment/moe-cache，HEAD fa377dcb62875d5c82fc8177afd4277cd2357db9。初查381个 tracked 变更、1381个 untracked 文件；该 commit 本身不能复现当前功能。
- 源码产品版本仍为0.1.3，低于生产0.1.7。正式候选必须在范围冻结时统一 App、Host、Release notes 的版本与递增 Build；后续内部候选已统一为0.1.8 / Build2263；正式发布前仍须冻结提交。
- 完整扫描原滚动台账11768行，保存881个NXR段落的原始证据、行号与摘要；295个标题日期晚于2026-10-14。历史状态及后续覆盖记录并存，不能将原始 in_progress/blocked 自动提升 ready。
- 24个内置App声明静态核查：声明式Mobile Gateway引用的模板/资源均存在。部分App明确标为development；这不是全部入口的实机验收，也不能由文件存在推断功能完整。
- 按标准构建脚本真实暂存 ai2apps/，对比2262实际内嵌Host：1361个文件，367新增、212变更、0删除（过滤测试/缓存并忽略符号链接）。这里只是Host源文件差异，不代表Swift、AceFox、oMLX或完整App已通过验收。

## 本轮已完善

1. 情报后台测试真实身份：使用持久AppInstance与Session，恢复实际Session/工作负载授权检查，移除旧的authorize_session空操作；后台执行使用实际unlisted Session。原12个失败的根因是不存在的旧fixture Session。
2. 增加不存在Session、跨用户Session拒绝测试，断言拒绝发生在Browser Task入队之前；不修改生产权限。
3. 通知审批回归使用当前“仅允许这一次”文案，并检查拒绝按钮、旧schema不出现记住工具、仅打开通知不提交任何写请求；原失败为旧文案断言。
4. 标准构建源过滤精确排除三处checkout研究归档：research/deepseek-v41-1017、research/dmoe-cleanup-audit-20261018、research/ssd-cleanup-20261017。真实暂存排除68585291字节（约65.4MiB），10个Research运行模块逐字节保留；没有删除研究源资料或精简cloud Runtime。
5. 清除两处CSS尾部多余空行，修复已有diff门禁噪音。

## 已核实的发布缺口与处理

| 优先级 | 缺口 | 当前结论及关闭条件 |
| --- | --- | --- |
| P0 | 可复现源码与版本基线 | 当前混合工作区及0.1.3版本不可作为可复现正式版；冻结完整范围、提交推送、统一版本，正式构建必须clean。本次内部dirty候选已获明确批准并保存源码快照/摘要；正式发布前仍须冻结提交。 |
| P0 | 版本台账状态不统一 | 保存全量原始证据，逐项结合后续覆盖记录与当前源码决定纳入/延期；881项索引不是881项验收通过。 |
| P1 | 手机授权、重连、撤销 | 实现及回归已存在；仍须当前Cloud协议下真实手机完成扫码、Desktop确认、重启恢复、多客户端互斥/撤销和原业务状态恢复。不能沿用已被后续记录覆盖的cloud_pending描述，也不能自动批准或驱逐现有连接。 |
| P1 | Package发现→安装→能力生效 | 目录与Provider生命周期实现已存在，内部签名/Service夹具已有证据；生产签名App/Service导出配套缺乏端到端实测。需精确已发布目标的干净实例安装、发现/撤销、返回原Chat验收；本轮不把目录描述当作已可调用能力。 |
| P1 | 升级/冷启动/数据保留 | 需完整签名候选、临时升级测试及目标Mac实际升级。验证数据库迁移、Helper接管、原任务/草稿/模型/Package保留与启动资源来源；本轮未替换任何固定实例。 |
| P1 | 真实媒体与通知链路 | 离开Studio后任务继续、共享Output恢复、Mobile播放/TTS、通知点击回原资源，需要区分历史实测、现有fixture和本候选实测；目前不能宣称全链路通过。 |
| P2 | development入口 | Sharing/Environment/Agents/Messager/Bench保留开发标记。是否转正式属于后续产品范围，不以本次收敛为由补一批新功能或掩盖未完成能力。 |

本轮没有根据静态检查确认新的业务功能缺失；已经确认并修复的是打包混入研究资料及两处验收覆盖失效。上述实机证据缺口不等同于已经证实运行时故障。

## 验证记录

- AaAT强制门禁：352 passed，exit0；退出阶段有既有headless Metal警告，不将其隐去或描述为原生GPU验收。
- Swift正常macOS环境：77项Swift Testing与2项XCTest通过，exit0。首轮沙箱构建失败不计通过。
- 情报后台、普通Chat恢复、后台Session：79 passed（含新增2个拒绝案例）。
- 情报混排/手动导入失联恢复/图片查看器：6个Chrome测试通过。
- Chat断线恢复/通知打开/审批呈现/Discover：16个Node/Chrome测试通过（修复旧按钮断言后全文件重跑）。
- Owner/Mobile/Package/通知集成：首轮141项中140 passed、1项被沙箱禁止loopback绑定；自管网络整个11项模块在正常环境重跑全部通过。另一次错误测试目录/缺失测试路径及Node依赖未配置的调用均不算通过。
- 情报编辑/手动导入/增量合并/启动：54 passed。
- 构建脚本zsh语法及实际rsync暂存检查通过；没有据此声称完整App签名/公证/升级通过。

证据目录：ai2apps/.build/release-readiness-20261025/。测试原始日志保留在/private/tmp/ai2apps-release-20261025-*.log；这些临时路径不是长期发布回执。

## 下一阶段准入

先关闭本候选范围与源码来源门禁，再制作隔离内部App。完成上述P1关键链路后，生成新的正式冻结源码与签名/公证候选，执行双源和Cloud交接流程。当前不更新生产清单，不发表独立Package，不修改Cloud代码，不提前将台账标记included。

## 内部候选构建授权（2026-10-25）

用户明确批准基于当前混合工作区制作内部候选，正式发布前再冻结提交。分配候选0.1.8 / Build2263，仅本地内部验收；binary不完全由现有tag复现。使用标准release builder的独立输出目录，保留default/cloud/arm64正式形态以验证升级资格，不替换或启动已安装生产App，不替换固定Dev/App-Dev/Test。保存源输入快照、逐文件摘要、当前commit及差异证据。尚不做公证或上传。

## Build2263 本轮结果

标准脚本完成Developer ID签名App、内部DMG、metadata与公证前预检。内部升级资格eligible；临时目录2262→2263真实Updater替换/备份/health-only/签名验证通过。全新临时目录的候选Local冷启动约3.041秒达到schema95 ready，三个实际HTTP静态资产与候选内嵌源字节一致；后台初始化完成并正常关闭。此数据不代表带模型/Package的既有实例启动性能。

包内1769个源文件精确一致，两份frpc仅签名元数据差异（签名前代码/非签名load commands及payload规范化核对）；未发现丢失源文件。1877个源输入在构建完成前后无漂移。Python3.11编译1076文件通过。源码归档、输入摘要、外部AceFox/Runtime输入摘要、原始测试/构建日志和本地回执已保留。

DMG：268027661字节，SHA-256 `725a6e6b1e49e58a571a5ee9a17b388abb399072e6560ae451a737d45ecaa68f`；metadata明确not_stapled，仅内部候选。路径：`ai2apps/.build/internal-candidate-0.1.8-build2263/`。机器回执：[internal-candidate-build2263-20261025.json](internal-candidate-build2263-20261025.json)。

首轮Updater烟测为/private/tmp与/tmp系统别名混用的夹具失败；统一/tmp重跑通过，没有修改更新器。冷启动首轮日志级别参数大小写错误，改为CLI规定的小写info重跑通过。原失败日志保留，未将失败调用记为通过。

固定Dev/App-Dev/Test和/Applications均未替换或重启，没有公证提交、工件上传、生产清单修改或真实付费模型调用。下一阶段仍是本页P1实机链路验收，不能把基础候选验收等同正式版已发布。
