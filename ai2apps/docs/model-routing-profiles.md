# 普通与隐私模型配置

系统模型路由有 `normal`（普通）和 `privacy`（隐私）两个独立配置，每个包含高中低强度对话/任务模型、图像识别（多模态）、绘图、语音识别/生成、音频处理和视频生成模型。

## 设置与兼容

模型 App 的默认用途页面选择普通或隐私，再选择各用途模型并保存。普通沿用 `default-models.json` 和既有 Cloud 默认策略，无需迁移旧文件。隐私保存在同目录 `privacy-models.json`，不复制普通设置、不使用 Cloud 默认策略、不接受 fallback。用户可明确选择可信的本机、私有服务或云端模型。此配置是路由选择，不是匿名化、数据删除或服务隐私认证。

受 `APP_SYSTEM_MANAGE` 保护的 Local API：GET `/v1/platform/model-profiles` 返回两组配置；PUT `/v1/platform/model-profiles/privacy` 使用既有 live 模型目录及兼容性验证保存隐私配置。普通继续使用既有管理接口。无需 Cloud 修改。

## WebAgent 与 Mini-App

WebAgent Source 可声明 `"model_profile": "privacy"`。Package Mini-App 在 `web_agent` 声明同字段作为应用默认，或在能力声明中指定。购物达人、电子邮箱 Package 应声明隐私默认；不要依靠页面勾选或根据目标文字猜测场景。

```json
{
  "web_agent": {
    "schema": "ai2apps.web-agent-mini-app/v1",
    "model_profile": "privacy",
    "capabilities": [{"id": "organize", "source": {"agent_type": "web"}}]
  }
}
```

上例仅演示字段位置，完整 Source 仍须有网站范围、参数和有效步骤。模型配置与浏览器登录 Profile 是两个不同概念。

Mini-App 前端不能通过提交参数改写模型配置。服务端将声明选定的配置写入公用后台 Task，创建 AgentRun 时解析并记录三档模型路由；已创建的 Run 使用其记录的路由。子 Agent 调用继承路由，隐私 Source 不可被普通调用上下文降级。已选择隐私的父 Browser Task 的子 Browser Task 继承隐私。缺少所需模型时 AI 步骤明确失败，不转到普通模型；纯编译读取步骤无需强制调用 AI。

既有未声明配置的 Agent 使用普通，情报中心既有调用保持兼容。其他业务调用多模态/绘图模型时使用 `resolve_default_model(purpose, profile="privacy")`；返回 None 时提示用户配置，不另行指定普通 fallback。购物达人 `ai2apps.shopping-pro` 已声明隐私配置并在后台核验，补货建议与对话修改使用标准任务模型；订单只读和购物车固定动作无需调用 AI。未来邮箱 Mini-App 必须接入同一契约。

## 验证

测试覆盖独立持久化、普通 Cloud 默认兼容、隐私不回退、live 目录校验、Package 声明与队列选择、Source 编译验证及 Run 路由固定。不得通过真实私人邮件或购物记录进行配置测试。
