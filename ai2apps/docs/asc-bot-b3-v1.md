# ASC-Bot B3：App-State 快捷入口

实施日期：2026-11-05。B3 首批实现已加载固定 App-Dev；不涉及 Cloud 发布。

## 用户流程

在已接入 App-State 的 App/Mini-App 中调整设置，打开「状态预设 → 创建快捷 Bot」，填写名称、预设头像和颜色。保存的是 owner 声明允许的参数，不包括当前 Prompt、图片、会话、凭据或权限。

在 Messager 点击 ASC-Bot，宿主直接打开对应 App/Mini-App，再由原 App-State binding 恢复设置；不创建对话或 Agent Task，不自动提交生成。用户继续在目标 UI 中提供素材并执行。Desktop 右键快捷 Bot 可打开管理视图，修改名称/头像及通过原恢复机制删除；Mobile 首批支持创建和点击打开，尚无独立快捷 Bot 管理面板。

同一 Local 安装的 Desktop/Mobile 使用同一 Bot 目录。Mobile 目标须已启用且有对应 UI。跨独立安装同步、Package 自定义声明、任意脚本和自动生成不在本阶段开放范围。

## 一套状态恢复机制

ASC 是 App-State 的消费者，复用 export、版本/合同校验、owner 原子恢复、冲突确认和应用回执。Agent-Chat「在 App 内继续」仍负责自己的任务归属、私有素材和结果回传；参数恢复与 ASC 使用同一 binding，不维护第二个参数执行器。

SDK binding 只增加可选 activate 和 configureDependencies，注册完成发出 ai2apps:app-state-registered。ASC 消费器等待宿主上下文和实际 owner 就绪，先选择目标 Mini-App，再调用原 restore。

## 持久化与授权边界

BotDefinition 的 app_shortcut 配置仅保存经过校验的 App-State packet。创建要求真实 source principal 和 source instance，经原 Bot 创建事务提交身份、定义、头像和幂等回执。不能通过普通创建接口提交未经源实例校验的快捷定义，ASC 不接收 App Access 或模型执行权限。

点击生成独立的 UI launch intent，绑定 actor、installation、Bot 定义摘要和最终 AppInstance，15 分钟到期，过期超过 24 小时的记录在后续创建时清理。同一 request_id 重试不得改变 Bot 或定义；已绑定的 intent 不能被另一个实例抢占。删除/修改 Bot 后旧 intent 失效。

Desktop/Mobile 宿主从服务端读取目标，不相信调用方传来的 App ID。消息仍校验当前可信 frame、origin、mount 和 instance；响应回到原调用 frame。目标 Mobile App 需通过 enabled 检查。浏览器重载可重送同一 intent，恢复沿用 App-State 幂等/冲突守卫；UI intent 的 claimed 状态不代表任务或生成完成。

ASC 在 Bot owner 层拒绝伪造的对话 scope、提交和 Agent 执行请求。未给通用 Agent 添加业务分支。

## 缺失依赖和失败

模型缺失/不可用由 owner 返回 dependency_unavailable，界面说明具体模型，允许打开既有 ACPF。配置时关闭原生阻塞弹窗，完成后由用户明确「继续快捷入口」，重新校验原模型；不替换成其它模型，不自动生成。账号/云模型配置仍由目标 App 的既有流程处理，ACPF 不保证能解决所有云端配置问题。

其它错误提供明确原因和重试恢复入口，不显示无关的安装建议。API 请求有 15 秒超时。重复点击宿主上下文不重复应用；创建遇到响应丢失保留原快照和 request_id，防止重复 Bot。当前不提供修改已保存参数的编辑器，需要重新从目标 UI 捕获。

## 验证和已知边界

后端类型/创建/Flash/ASC 合同 41 项、相关 owner/App-State/AaAT 架构 97 项、相关 JavaScript 44 项通过。浏览器 Desktop/Mobile 尺寸夹具覆盖创建响应丢失后重试、目标恢复、重复上下文、缺失模型与 ACPF 显式回接；原 Standard/Flash 创建夹具同时通过。最后仅重复 ASC 五项检查最终 claim 状态调整。

本轮没有修改共享 Agentic/AaAT 执行、路由声明、交互和结果策略，使用对应 owner 和架构检查；完整 AaAT gate 已在前序整合执行，本轮不重复全量运行。

原生 App-Dev 实际创建「Dev 验收：ASC 吉卜力」，从消息列表点击后打开创意画坊「更换图片风格」，显示吉卜力、(BYOK) OpenAI gpt-image-2.5-sunburst、1024×1024、自动质量。验收未触发生成或后台 Task，Bot 保留供用户检查。真实手机的端到端人工验收尚未执行，不能用 viewport 夹具代替。

标准 App-Dev 构建、verify-release 和 codesign 检查通过；App/Helper 源根、实际 Local 导入路径、Desktop/Mobile served 资源与当前 checkout 字节一致。详见 [验收记录](acceptance/asc-bot-b3-20261105/acceptance.md)。
