# 短漫工坊 · Comic Studio

独立的 Imagine Studio Mini-App 源码 Package。通过标准开发源挂载发现，不需要创建新的 App-Dev 实例。

第一版支持：

- 多系列设定、风格、角色参考和形象确认，保存到当前 Owner 的 Studio 草稿。
- 2～6 格脚本，系列默认画格比例与本集覆盖；不支持的模型尺寸明确报错。
- 使用已配置的任务模型辅助编写一份脚本，参考最近20集摘要；人工检查后再绘制。
- 顺序绘图，角色参考优先、此前最多两格缩小到512像素后作为连续性参考。参考数量受模型能力和通用接口上限约束。
- 对白和旁白独立排字。已有画格可直接重新排版，不再请求绘图模型。
- 最终 PNG 使用统一 Output；角色参考与单格图保存在当前账户、安装和 Package 的私有空间。
- 已提交任务脱离界面继续执行；恢复时只查询原任务，不自动重复不确定的模型调用。
- 成品发布失败时可显式重试导出，复用已有检查点，不再次绘图。

生成方式默认手动。在“生成方式”中可主动启用定时，选择首次时间、固定1～168小时间隔、每次1～5集及可选创作方向。复用系统任务中心，Local需运行；可在那里查看与取消。脚本模型和绘图设置在保存计划时固定，调整后需重新保存。切回手动停止未来触发，保留已生成内容。

明确未包含：新闻采集、多候选审核、单格重绘、跨账户同步、金额硬预算及发布。定时按调用次数限制，最多5次脚本与30张图/批。AI 脚本默认不创建新角色；应先在角色库生成并确认角色，再写入分镜。定时配置目前仅Desktop提供。

## 结构

`web/core.js` 持有漫画语义，`web/automation.js` 编译有界声明式Recipe，`web/comic.js` 持有界面。Host只理解图片序列、模型调用、schema和通用记录，不依赖本Package ID。复杂后台业务适合独立Service；当前Recipe不执行Package代码。

## 验证

从 Git 根目录执行：

```sh
.venv/bin/python -m pytest tests/test_image_workflow.py tests/test_studio_extended_jobs.py tests/test_studio_background_jobs.py -q
node --test tests/comic_core.test.cjs
.venv/bin/python ai2apps/tests/run_aaat_boundaries.py
```

源码挂载验证不等同于签名安装或生产发布验收。
本次面向本机 App-Dev 验收；手机远程访问需要 Cloud 项目补齐新增精确路由，不能据此宣称 Mobile 已验收。

## Multilingual, ASCBot and AaAT

Chinese/English UI and validation prompts follow the host locale. ASCBot saves portable
drawing model, default panel ratio, panel count and previous-reference settings. It does
not copy story text, characters, images, history or schedules; restoring a different panel
count requires a blank episode. No generation starts from restoring settings.

The signed `imagine.create_comic` AaAT capability uses `studio.image-sequence/v1`. Bots
can discover it by comic/storyboard/short-comic tasks in Discover, write 2–6 panel prompts
and captions, resolve finalized characters with `character.list/get/use`, then invoke
directly with actual image artifact IDs. Output uses the host durable queue and shared
Output. This export draws a supplied episode; it does not silently edit a saved series.

The host must provide image.workflow, studio.image-sequence/v1 and the matching ASCBot
state adapter. Older Desktop versions may render the UI without these Agent/shortcut
interfaces; unsupported SDK bindings are unavailable rather than silently substituted.
No model checkpoint dependency is required: choose an available Cloud, BYOK or local
drawing model. News sourcing, multi-candidate script review and per-panel redraw remain
outside this first release. Scheduled generation remains manual by default.

## 0.1.1 Series AaAT

`imagine.comic_series` lists or inspects saved series, including character IDs and
recent 20 stories. The Bot writes a fresh script from this context, then invokes
`imagine.create_series_episode` with exact series and library revisions. It inherits
the model, ratio, style, world and approved character images unless overridden.
A finished episode is appended without replacing the currently edited draft.
Concurrent UI edits use optional versioned draft writes; stale pages must reload
before saving. The matching Desktop project SDK and versioned draft bridge are
required. This release does not add automatic scheduling or new character approval.

## Portable series ZIP (0.1.2)

Export one series or all series with scripts, current drafts, characters' definition images/descriptions and generated panel images. Import previews names/counts and creates new series/character/episode IDs; duplicate names gain a suffix. Source Run IDs and schedules are not reactivated. Missing models remain unavailable until explicitly chosen. This format is distinct from character authoring ZIPs and requires the matching Desktop archive Host bridge.
