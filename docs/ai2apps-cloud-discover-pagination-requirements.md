# AI2Apps Cloud：Discover 游标分页要求

## 目标

为 Desktop Discover 的 `All / Apps / Mini-Apps / Agents / Models / Services` 目录提供稳定、可扩展的游标分页。Desktop 当前首屏请求 24 条，用户通过“加载更多”继续读取；现有不返回游标的 Cloud 版本由 Desktop 最多预取 100 条并进行本地分页，以免升级过渡期隐藏既有 Package。页大小属于客户端展示策略，Cloud 不应把 24 固化为协议上限。

## API 合同

适用于：

- `GET /packages/catalog/recommendations`
- `GET /packages/catalog/search`

请求继续使用现有 `limit` 与 `cursor`。响应必须保持现有条目数组字段，并返回：

```json
{
  "items": [],
  "nextCursor": "opaque-value-or-null"
}
```

要求：

1. `nextCursor` 是不透明字符串；没有下一页时为 `null`。Desktop 不解析、拼接或修改游标。
2. 游标必须绑定完整查询：搜索词、排序、Package type、content kind、模型分类/任务、Mini-App 分类、兼容性与可见性上下文。查询改变后旧游标必须拒绝或失效，不能静默用于另一查询。
3. 同一查询和目录快照内排序稳定；翻页不得重复或遗漏条目。发布状态变化时允许 Cloud 使旧游标过期并返回明确的可重试错误。
4. `All` 使用一个由 Cloud 生成的混合排序和单一游标，不能让 Desktop 分别请求每种类型再拼页。
5. `limit` 表示响应目录卡片数，而不是过滤前候选数；必须支持 Desktop 当前使用的 `limit=24`。

## 原生过滤要求

Cloud 必须在生成游标前执行以下过滤，而不是让 Local 从一个固定大小的 Cloud 页面中二次截取：

- `content=model|service`
- `model_category=<canonical category>`
- `model_task=<canonical task>`
- Mini-App Catalog 分类

这可保证当前每页最多 24 张有效卡片，并避免 Local 过滤后页面过短或跨页遗漏。

## Mini-App 索引

Cloud 接受并验证 Package 签名清单中的 `miniApps` 投影后，应建立组件级 Discover 索引。Mini-App 查询的分页单位是组件卡片，稳定主键为 `packageId#componentId`；安装、升级和卸载目标仍是所属 App Package。不得把 Mini-App 伪装成独立 Package。

兼容阶段允许 Cloud 仍按 App Package 分页，由 Desktop 展开组件；这种模式只作为迁移兜底，不保证每页组件卡片数量固定。

## 错误与安全

- 游标必须带签名或由服务端存储，不能信任客户端可编辑的排序位置、租户或可见性字段。
- 过期、损坏或查询不匹配的游标返回结构化 `invalid_cursor`/`cursor_expired` 错误和可重试提示。
- 游标不得泄露内部数据库键、账号、审核状态或未发布 Package 信息。
- 匿名与登录态查询都必须在每一页重新执行相同的可见性和发布状态检查。

## 验收

1. 六个一级目录分别以 `limit=24` 连续翻页，合并结果无重复、无遗漏，末页 `nextCursor=null`。
2. 搜索、排序和任一分类改变后从第一页开始；旧游标用于新查询会被拒绝。
3. Models 的 category/task 过滤与 Services 排除模型在 Cloud 原生完成。
4. Mini-App 按组件分页，`packageId#componentId` 唯一，生命周期目标保持所属 Package。
5. 并发发布、下架和权限变化不会暴露不可见条目；过期游标返回明确错误。
6. 不返回 `nextCursor` 的旧响应仍可被当前 Desktop 当作单页结果读取。
