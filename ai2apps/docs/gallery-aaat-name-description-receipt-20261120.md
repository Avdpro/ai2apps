# Gallery 名称与说明 AaAT 对接回执

日期：2026-11-20。状态：源码已实现、owner 定向测试通过；尚未在运行中的 Dev/App-Dev 激活，未发布 Desktop。全量 AaAT 门禁已启动，结果待确认。

## Bot 调用合同

能力名不变：`gallery.save_material`，Provider version 从 `1` 升至 `2`。

```json
{
  "artifact_id": "当前任务 Session 内真实的 artifact ID",
  "name": "竹林熊猫.png",
  "description": "竹林中戴草帽的熊猫，可用作活动封面。"
}
```

- `artifact_id`：必填，当前拥有的 Session 中的实际产物，最长 256 字符。不可填 Gallery asset ID、URL 或本地路径。
- `name`：可选，1–512 字符，作为文件名；调用方应保留正确扩展名。不传沿用产物名称。Gallery 仍会执行原文件名清理规则，最终以响应为准。
- `description`：可选，最长 4000 字符的纯文本，支持换行，禁止 NUL；新素材不传默认为空字符串。不是提示词或执行指令。
- 旧调用仅传 `artifact_id` 继续可用；未知参数仍拒绝。
- 响应 `asset` 新增 `description`，保留 `id/name/media_type/size_bytes/status`；顶层保留 `status/created/view`。
- 同一 owner、内容和名称命中已有资产时，`created=false`，返回已有资产，不覆盖原说明。改名称会形成不同素材记录，底层内容仍共享。重试请读取真实返回值，不假定传入说明已覆盖旧资产。
- `gallery.search` 的 `query` 同时搜索名称和说明；`gallery.search`、`gallery.get` 均返回 `description`。

## Gallery 与 HTTP API

说明以 Gallery owner 约定的 `metadata.description` 持久保存，API 同时投影为顶层 `description`；旧资产默认空，无数据库迁移。未改内容文件、hash 或原来源元数据。

`PATCH /v1/platform/gallery/assets/{asset_id}` 支持独立或同时提交 `name` 和 `description`；省略/null 保留原值，`description: ""` 清空。现有 artifact/attachment 导入 API 同步接收两字段。图片查看器内“素材说明”折叠面板支持读取、编辑、清空；只读输出查看器不提供编辑入口。

UI 与 AaAT 复用 Gallery 存储/保存服务。所有权、Session、App Access、审批及实际执行检查保持原路径；未在 General Agent 增加业务分支，也不涉及 Cloud 修改或付费模型调用。

## 验证与限制

- `ai2apps/tests/test_material_handoff.py` + `ai2apps/tests/test_bot_gallery_materials.py`：11 passed。真实测试 Runtime/SQLite/Artifact/HTTP/Tool 链路，输入文件为夹具，不是线上 Bot 实测。
- Gallery 既有测试：7 passed，1 failed；失败为页面已有“状态预设”硬编码中文触发 `test_gallery_has_matching_english_and_chinese_translations`，不属于本次新增字段。未削弱测试。
- JavaScript 语法检查通过。
- 已启动 `python ai2apps/tests/run_aaat_boundaries.py`，日志 `/tmp/gallery-aaat-boundaries.log`；未完成时不得声称全量通过。
- 尚未重启用户 Local、验证实时 Provider version 或进行 UI 实机验收。Python/AaAT 改动需待当前任务结束后从对应 Helper 重启 Local，页面刷新；不需要重建 App。
- 激活须遵守固定开发源码合同，核对 App/Helper source-root、运行 Local 导入路径与本 checkout 的实际服务资源；随后 Bot 重新读取 `app.describe` 中该能力的当前 schema/version，不沿用旧声明。

## Bot 联调验收

激活后，使用正常登录账号和原 App Access，在当前任务生成一个小型测试产物，按上述三参数保存；读取 `gallery.get` 核对名称/说明，以说明中的独特词搜索并核对同一 asset ID；重复原调用应返回相同 ID、`created=false`。重启/刷新后再次读取，确认持久化。不得以此回执代替实际联调成功记录。
