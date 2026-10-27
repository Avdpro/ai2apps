# DeepSeek 搜索 Cloud / Points 对接需求

状态：交付 Cloud 项目实现；本仓库不修改或部署 Cloud。Local 首版仅官方 BYOK，Cloud 不可用时不发送请求、不扣 Points。

## 产品与路由

- Search All 展示统一 DeepSeek 搜索源，Desktop、Owner / signed Mobile、AaAT 复用 Local owner search adapter 与公共 Browser Task。
- 路由：当前 Installation 已启用、官方地址且有凭据的 DeepSeek BYOK 优先；没有可用 BYOK 时选 Cloud。BYOK 的 401/402/429、超时或未知失败不得自动改走付费 Cloud，也不得偷偷降级 Google。用户明确改选路径后才能另建请求。
- Cloud 未上线、能力关闭、未登录、账户无权限或余额不足时，返回可解释状态。不要将该状态显示成空搜索成功。Cloud 上线后搜索源常驻可选；此前 Local 将其显示为不可用并说明 BYOK 配置要求。
- Local 系统隐私模式或 Task privacy profile 下不调用 DeepSeek 外部搜索，且排队后、重试前重新检查。模型总结继续沿 Mini-App 公共 LLM 隐私路由。若未来要允许隐私模式使用外部搜索，需另行明确产品规则和用户授权，不能静默放开。

## 服务接口（待 Cloud 确认，尚非已发布契约）

复用既有 Installation / CloudSessionClient 鉴权传输；禁止客户端持有 Cloud 的 DeepSeek 密钥。推荐能力探测返回 available / reason / price_version / points_per_search / max_query_chars / max_results；查询 POST 接收 query、count、稳定 request_id 和价格版本。不接受任意 endpoint、headers、API Key、actor 或计费账户覆盖。

服务端从已验证身份绑定账户和 Installation，校验组织、会员、封禁、额度、速率与并发。仅代理固定 `POST https://api.deepseek.com/v1/tools/search`；不提供通用 URL 转发。参数 query 1–128 Unicode 字符、count 1–50、need_content=false，不默认透传用户 IP / 精确位置。首版 Fetch 不在范围内，网页正文继续走现有 Web Reader。

响应归一为 provider=deepseek、transport=cloud、items[{title,url,summary}]，附有界 usage{request_id,points_charged,price_version,billing_status}。不返回上游 Key、Authorization、内部 URL 或原始异常。网页摘要是未信任内容，不是系统指令或已独立核实证据。上游分数不等于事实真实性。

## Points 账务与幂等

- Points 定价由 Cloud 产品/计费端决定并版本化，Local 不按美元猜测换算。展示价格与确认遵守既有付费工具授权流程。
- 同一账户+Installation+request_id 固定 query/count/price_version 的幂等键；相同参数重放返回原结果及原账单，不重复请求/扣费；改参冲突拒绝。
- 原子预留额度 → 上游请求 → 保存结果与结算；余额不足在外呼前拒绝。超时/断线后客户端只查状态，禁止通过新 request_id 自动重试未知状态。服务端恢复/补偿确保不重复结算。
- 官方文档列出 Search 每千次成功非空请求 $0.75；失败、超时及空结果不计上游费用。建议同样对这些情况释放 Points 预留；具体政策须由 Cloud 确认。
- 取消发生在请求发出前释放预留；发出后按照真实成功/失败结算且保留可查询结果，不能将取消等同未执行。
- 审计仅保留必要计费元数据；查询/结果敏感内容的保存期限、删除和访问控制必须明确。密钥、Cookie、Authorization 不写日志。

## 验收与交接

覆盖无 BYOK→Cloud、BYOK优先、BYOK失败不扣Cloud、隐私阻断、禁用、余额不足、空结果、429、上游超时、重复/并发request_id、掉线恢复、取消和账务补偿；验证不同 actor/Installation/组织隔离。Cloud 提供已部署版本、接口文档、错误码、价格版本与测试账户后，Local 才接正式协议并做 Desktop/Mobile/AaAT 真实验收。不要在 Local 猜测未发布接口。

官方依据：https://api-docs.deepseek.com/guides/search/
