# WebAgent 通用 Probe 恢复（2026-10-25）

生成和编译：探索上下文可传入最多600个原生或自定义交互控件及覆盖摘要。当前 Probe 显式 ref 由 compiler 校验，拒绝缺失、敏感、禁用或不适合输入的目标；无 Probe 的旧 Source 保持兼容。生成提示明确 DIV/SPAN 与原生控件同等可用，不应凭标签排除。探索成功路径蒸馏也校验其 before Probe。

执行：定位失败先等待稳定、重新观察、重试原定位。实际观察的屏外目标可原生滚动后重新绑定。仍失败才请求当前任务模型选择允许的 ref；不接受模型提供的新操作、参数、代码、坐标或站点。修正规则只作用于本步骤，通过 compiler 和第二次 Probe 身份绑定后再执行，不能自动覆写已发布规则。owner 继续限制实体、数量、渠道等业务范围。

视觉位置：DOM 修正选择默认先用文本 Probe；仍不明确才走图像定位。恢复目标在执行前按任务策略使用标记图复核；执行一次后回读并检查新画面。正常 DOM 定位成功不增加视觉选目标；owner 的 mandatory always 策略仍保持。图片判断不能覆盖 owner 数量回读的反证，也不能批准再点击。

不确定副作用：原生命令回执丢失也先尝试回读，保存已观察数据或具体失败类型，标记 unknown、禁止自动重放。进程恢复只读原绑定上下文；无法观察原页时记录原因，不创建另一页恢复未知操作。原 action journal 的不重放约束继续生效。

Dev 真实诊断发现滚轮路径未像 pointer_to 一样激活原任务页；后台渲染/异步滚动导致后续 Probe 仍拿到旧坐标。SDK 滚动现在复用 activate_for_input、单次零时长原生 wheel，并有界回读实际滚动状态至稳定；仍不稳定时不假称目标可见。此逻辑无站点分支。

跨站点回归使用两个任意域名和 button/SPAN/DIV 夹具，覆盖重新观察免生成、屏外滚动、编译拒绝、目标变更、视觉复核位置、丢失点击回执回读及重启不重放。真实 Dev 验证记录待追加。

## 真实 Dev 验收

最终 Run `run_fd7f94bede3a4988ae25c22a5888b47b`，Task
`btask_93543296f9c6a69b5f8a5fbe84e6a28d890c27e0f92d8aa9f271e3c386a7cb64`。
通过购物达人 UI 在 Default 分身确认仅将 Coca-Cola 16.9fl oz 六瓶装补至4组。
前两轮诊断均在输入前安全停止、数量保持2，随后取消旧轮次并通过标准 Helper 重启 Local。
最终轮自动激活原页、滚动至加号、复核并逐次补齐，item_0 返回 quantity=4、verified=true，report 成功，Run completed。
保留当前隐私任务路由 `cloud/deepseek/deepseek-flash`，未切换模型/分身。
唯一图像摘要对应两次 review 和两次 after；现有 owner 汇总累计证据数组时会重复包含前一次记录，这不是重复输入。只读 BiDi 和原生 AX 独立确认实际数量4；Fresh subtotal 9 items/$42.87。
未结账、付款、清空购物车或改变其他商品。三个验证专用标签页在验收后关闭，未关闭用户原有页面。

此次真实验证覆盖的是 owner 已确定 SPAN 加号后自动滚动、复核、点击、精确回读；AI 重新选择 ref 的通用修正规则分支由跨站点夹具覆盖，不能将夹具写成真实站点验收。

最终 Dev Local 端口64414；App/Helper 源根均为 `/Users/avdpropang/sdk/omlx-moe-cache`。
运行日志确认 background_page、visual_recovery 导入本 checkout，实际 served browser_snapshot.js 与 checkout 字节一致。无需重建 App；App-Dev 未重启。

定向回归：177项 owner/探索/恢复测试通过；最后一次 SDK 核心97项通过；生成/编译13项通过。原生自动集成测试因无测试宿主跳过1项，以上真实 Dev 验证补充覆盖浏览器。强制 AaAT 门禁最终结果见发布台账；前一轮存在一次旧 continuation 测试 SQLite锁竞争，未改变该业务代码或放宽门禁。

最终强制 AaAT 门禁332项全部通过（exit0，退出时有既有 headless Metal 警告）；旧 SQLite锁竞争用例单项复测通过，最终完整门禁也通过。
