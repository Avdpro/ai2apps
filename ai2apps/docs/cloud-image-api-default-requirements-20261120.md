# Cloud 绘图 API-Default 改动需求

日期：2026-11-20。Cloud 项目负责实现、部署和生产验收；本仓库只修改 Local/客户端，不直接改 Cloud。

## 目标

绘图与对话分别由 Cloud 指定 API-Default。调整绘图默认模型无需发布客户端。用户显式指定的模型、本机系统默认值及会话模型偏好保留优先级；已提交任务固定原模型，不因策略更新而切换或重新提交。

## 接口扩展

在现有 `GET /v1/ai/defaults` 的 `ai2apps.ai-defaults/v1` 响应中增加可选字段 `imageApiDefault`，复用已有身份、缓存和响应机制。示例中的模型 ID 仅为格式示意，由 Cloud 管理员选择真实可用模型：

```json
{
  "schema": "ai2apps.ai-defaults/v1",
  "revision": "new-immutable-revision",
  "apiDefault": {"modelId": "provider/chat-model", "displayName": "Chat model"},
  "imageApiDefault": {"modelId": "provider/image-model", "displayName": "Drawing model"}
}
```

- `apiDefault` 含义不变，不能将对话默认误用于绘图。
- `imageApiDefault: null` 明确表示当前不提供绘图默认；旧服务完全省略该字段也合法，新客户端此时要求手动选择，不恢复写死模型或自动挑选首个 BYOK 模型。
- 两种默认均允许独立为 null；一项为空不能丢失另一项。
- `modelId` 必须是 `/v1/ai/models` 中的原始 `provider/model` ID，不带 `cloud/`、`gateway/` 或 `ai2apps/` 路由前缀；Local 构造 `cloud/ai2apps/{modelId}`，仍走账户 Cloud 路由，不能因个人 API Key 存在而改走 BYOK。
- `displayName` 为非空可展示名称。ID/名称长度、字符约束沿用现有对话 API-Default 校验。
- 每次实际配置变更必须更新 revision；无效配置不得发布。所有字段均为数据，不是提示词或授权。

## 配置与就绪校验

复用现有管理员配置/审计机制，新增独立的绘图默认选择。发布前检查目标模型已启用并支持 `imageGeneration`，提供实际尺寸、格式、质量及计费信息。建议默认模型同时支持 `imageEdit`，供编辑、参考图、合影等入口使用；若不支持，客户端必须要求另选，不隐式切换其他模型。

账户不可用、地区/组织限制、下架、熔断等仍由模型目录和执行入口校验。设置默认不授予调用权限、上传同意或付费授权，也不能绕过限额。返回的默认策略不得包含凭据。

## 缓存与兼容

- 客户端启动拉取，之后每 300 秒刷新；最近有效缓存最多使用 86400 秒，并绑定 Cloud origin。
- 网络失败、旧接口 404、无效响应不得覆盖最近有效缓存。有效的显式 null 应立即清除相应默认；成功返回的旧策略缺少 imageApiDefault 时，新客户端不应沿用旧的绘图默认。
- 超期、离线模式、无绘图默认时，仅保留有效的明确选择；否则展示模型选择，不猜测其他付费模型。
- 策略只提供默认引用，不替代当前模型目录、参数与就绪验证。更新默认不修改客户端保存的显式默认配置文件。
- 建议先部署此可选字段，再发布客户端。旧客户端继续只消费 apiDefault；新客户端在旧 Cloud 上允许用户手动选择绘图模型。

## 验收清单

1. 保留旧响应兼容性；对话默认 A、绘图默认 B，分别返回并生效。
2. 绘图默认从 B 改 C、revision 更新；客户端刷新后新任务继承 C，显式选择及已提交 B 任务不变。
3. apiDefault=null 但 imageApiDefault 有值，及反向情况均正确。
4. imageApiDefault 缺失/null、非法 ID、无绘图能力、下架模型和账户不可用；不回退到写死/首个模型，不误走 BYOK。
5. 模拟超时、503、404、非法 JSON，验证缓存保护；有效 null、缓存过期、origin 变化、离线模式均验证。
6. Studio 文生图、图片编辑、Bot/AaAT 及采用宿主默认解析的 Mini-App 共用默认解析；能力不匹配进入已有参数选择流程。
7. 提供生产响应（脱敏）、revision、目录能力校验和 B→C 切换回执；不要仅以接口 200 判定业务成功。

## 客户端对应改动

Local 保留/校验 imageApiDefault；Model Manager 的 image_generation 继承该字段；Image Service 删除具体模型及名称猜测兜底。Imagine Studio 使用 Local 返回的 preferred，保存“继承默认/明确选择”状态；旧草稿保留原模型，新草稿继承 Cloud 更新。放大模型仍按独立放大能力选择，不套用绘图 API-Default。

本需求不代表 Cloud 已部署。本地测试使用策略及模型目录夹具，不调用真实付费绘图。


## 客户端完成记录（2026-11-20）

客户端源码已完成，并在固定 Dev 加载。验证包括：49 项默认策略/路由测试；最终字段刷新与离线保护专项 9 项；相关 AaAT 门禁 79 项；Studio Python 回归 14 项、Node 界面行为 14 项；Mini-App 图像工作流/Skill 执行 17 项。各组有重叠，不将其相加声称独立测试总数。模型目录、Cloud 响应和绘图调用均使用夹具，未进行付费绘图。

Dev 在任务队列清空后通过标准 Helper 重启，PID 11718、端口 52888、健康检查 200。App/Helper source-root 均指向当前 checkout；运行模块日志和实际返回的 Studio JS SHA-256 与当前源码一致。Studio JS 的缓存版本已更新。App-Dev 未重启，未发布 Desktop/Package。

Cloud 字段部署、真实账户模型目录可用性和生产 B→C 切换联调仍由 Cloud 项目完成；本文的客户端通过记录不替代这些生产回执。
