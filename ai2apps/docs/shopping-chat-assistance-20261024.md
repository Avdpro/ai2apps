# Shopping AaAT 协助链路修复（2026-10-24）

本次 Dev Run 为 `run_94ed5d50153c4057b5575c71c20a4a2d`，原目标可乐为
4 包六瓶装（24 瓶）。实测 DOM 读取数量为 2。原任务后来被系统以
`run_deadline_exceeded` 取消，子任务和原页均已取消/关闭。没有自动重放加购。

## 证据与修复

- Tool invocation progress 已有 `task_progress.state=waiting`、`requires_user=true`、
  wait_reason 和 metrics；主 Run 因等待子任务仍是 running。Mobile 原来只渲染
  status_line.text 和主 Run 状态，丢掉了这些字段；观察器文本又沿用了旧快照。
  现在观察器等待文案覆盖旧值，Mobile 显示实际等待原因与计数。
- Browser Task 使用私有 Session，原 Desktop 控件只允许与 Chat 相同的 Session，
  Mobile 没有协助控制接线。现有 Browser SDK 提供 Run 作用域控制路由：先检查
  原 Run actor 权限，再检查该 Run 持久 invocation progress 的 Task 引用、Task
  所有者及当前待协助 Interaction。只操作原任务；不开放任意 Browser Run。
  页面打开通过原 Profile 和匹配 userContext 的原 browsing context；不新开独立浏览器。
  相同 response_id 的丢回应重试保持幂等。
- 真实 Default 原页只读证据：可乐行 `e155` 为带点击处理的 span 加号，
  坐标 y=-371.95、宽40高31。旧增量提取只认 button/role/input/a-button-text，
  不认实际 span.a-button；视觉 fallback 无可见候选，尚未进入视觉模型决策。
  新提取器认该行的显式加号并绑定 ref；最多三轮原生滚动/等待/重新读取，
  之后再做标记视觉复核及每次点击后的精确数量回读。禁止不确定加购重放。
  修复脚本在原页只读确认得到 increment_ref=e155、数量保持2。
  之后原页随系统任务取消而关闭，因此未完成真实滚动/加购的端到端验证。
- 两张相同购物车表单的中间步骤中，模型重复把 profile 放在顶层和 parameters；
  第一次调用在 prepare 被 invalid_tool_arguments 拒绝，但已占用确认凭据。
  通用凭据机制现在只在持久 prepare 参数拒绝后允许同参数纠正调用复用；
  仍校验 Run、Provider/version、精确值和单次执行声明。execute 失败不释放。
- 购物历史增加页码、订单详情序号/总数、发现订单/商品数及整理阶段计数，
  Desktop/Mobile 都消费同一快照。没有伪造计时百分比。
- Mobile 图标原来通过另一套 Mobile App 目录权限加载，失败后保留两个通用图标。
  现在通过已授权 Agent Run 的只读元数据入口取得可信 App/Mini-App 名称与图标，
  与 Agent 请求共用签名传输。元数据不授予执行权限；共享 AS 没有业务身份分支。

## 验证范围

88 项 Shopping 所有者/控制新回归、27 项视觉与控件回归、11 项 Mobile/Desktop
进度 UI/客户端回归通过。Chrome 390/1100px 为夹具；截图
`/tmp/shopping-mobile-assistance.png` 为夹具渲染，不是真机远程页面。
新控制 API 测试覆盖任意两个能力身份、私有执行 Session、未观察 Task 拒绝、
外来 interaction 拒绝、原请求恢复及丢回应重复提交。真实 Dev 只读检查使用
标准受保护 BiDi SDK，没有读取 Cookie、点击加号、结账或付款。

App-Dev 和 Dev 在无活动 Run 后通过各自标准 Helper 重启；实际资源和导入源路径
核验见本次发布台账。原购物任务已取消，不能声称它已凑满25美元或完成。
