# AI2Apps Cloud Site Agent Discovery 扩展需求

状态：客户端 P4.0 已就绪，Cloud 精确索引增强待 Cloud 项目实现  
日期：2026-08-29

## 1. 边界

客户端已经能够通过现有 `GET /v1/registry/search?type=agent&q=...` 查询并安装标准签名
`.ai2agent`。为获得无需全文搜索猜测的精确 Site Agent Discovery，Cloud Registry 需要从已审核
Agent Source 提取下列不可执行索引字段。Cloud 不编译、不运行 Publisher Hint。

P4.0 客户端已经发送 `agent_kind`、`origin`、`path`、`capability` 和 `output_schema`；Cloud 在上线
精确索引前可以忽略新增参数并继续使用 `q` 兼容搜索。

## 2. Registry 索引字段

```json
{
  "agentKind": "site-agent",
  "webAgentSchema": "ai2apps.web-agent-package/v1",
  "siteScopes": [
    {"origin": "https://example.com", "pathPatterns": ["/**"]}
  ],
  "capabilities": [
    {"name": "web.article_feed", "outputSchema": "ArticleList/v1"}
  ],
  "permissions": ["browser.read"],
  "testSummary": {"passed": 12, "failed": 0},
  "compatibility": {"webdriverBidi": ">=1"}
}
```

索引内容必须来自已签名、审核通过的 Artifact；不能接受 Publisher 另外提交的未签名搜索元数据。

## 3. 搜索接口

扩展现有接口，不增加第二套 Registry：

```http
GET /v1/registry/search?type=agent&agent_kind=site-agent
    &origin=https%3A%2F%2Fexample.com
    &path=%2Fnews
    &capability=web.article_feed
    &output_schema=ArticleList%2Fv1
```

结果增加：

- `siteScopes`、`capabilities`、`permissions`；
- Publisher、版本、签名/审核状态；
- 测试摘要、最近匿名兼容性健康度；
- AI2Apps、Runtime 和 BiDi 兼容范围；
- 安装用既有 package/version/artifact/envelope 字段。

## 4. 排序

固定排序因素：已安装兼容版本、origin 精确度、path 具体度、capability/schema 匹配、最近测试、
用户固定版本、Publisher 信任和匿名健康度。不得为了推荐 Site Agent 隐式调用模型。

## 5. 健康反馈

新增可选、批量、匿名端点。只接受：Package ID/version/digest、Capability、客户端兼容版本、
成功/失败类别、结构指纹的不可逆摘要和时间桶。禁止上传 URL query、页面正文、截图、表单、
Cookie、账号标识或模型 Prompt。

Cloud 应执行限流、最小样本阈值和抗投毒聚合；单设备反馈不得直接改变公开健康状态。

## 6. 审核要求

- 审核 Source、权限、Fixture、Validator 和 JS 静态扫描结果；
- 外层 Contract 权限必须覆盖内层 `web_agent.permissions`；
- Publisher Hint 不作为正确性或安全证据；
- Scope/权限扩大必须作为显著版本变化展示；
- 同 Package/version 保持不可变。

无需数据库迁移方案由客户端仓库决定；具体 Cloud schema、migration 和部署由 Cloud 项目实现。
