# Shopping Pro AaAT 补货与购物车契约

Shopping Pro 拥有 history → recommend（或 refresh_list 一次刷新并推荐）→ prepare_cart 的业务流程。
主 Agent 不根据历史记录自行估算周期或日期分档。App 与 AaAT 使用同一 Browser Task 和购物服务。

后端以当前本地日历日、非未来的不同购买日期和正间隔中位数计算周期（不足整天向上取整），
预计补货日为最近购买日加周期。互斥分档：overdue（小于0天）、due_today（0天）、
next_3_days（1至3天，包含第3天）、later（大于3天）、unknown（不足两次不同日期）。
未知日期不能当成今日到期；用户修改选择不改变日期事实。购买周期仅为历史估计，不代表实际库存。

购物车入口只接受同用户、同分身、已完成的观察任务和已观察商品。Chat 参数表单显示
商品及数量，实际执行必须绑定本Run、当前Provider版本、完全一致的用户确认及单次调用凭证。
取消、改参、跨Run复用均不能执行。维持现有不确定点击不重试、渠道验证和购物车回读；
只准备购物车，禁止结账、付款或订阅。AaAT 不另建调度或进度通道。

页面读取必须区分空白未就绪与实际布局变化；有限重新观察仅用于只读步骤。Fresh 按钮若由透明input与aria-hidden文字构成，只采用可见且含真实submit控件的包装层，并仍从附近明确卖场标识验证渠道，不以URL参数或商品品牌代替渠道证据。

用户要求先出清单时，应完成清单展示并等待后续购物车请求。购物车失败或需协助必须保留实际状态，不能被先前成功的补货报告覆盖。

## 加购参数与确认表格

prepare_cart使用source_tasks、selected:[{id,quantity}]及profile，不直接接受推荐报告
的items字段。Shopping Pro自己的prepare_values将无冲突的旧items草稿迁移为selected，
保持每个商品ID与数量；两字段冲突拒绝，不删除其它未知字段来绕过schema。
确认前从同用户同分身的观察任务取商品名称和允许ID，声明通用records编辑表格，
用户看到具体商品及目标数量。缺失/未知商品与非法数量仍不能提交。确认只生成原有
Run/Provider/版本绑定回执，实际购物车操作仍须原校验且回读核实；不生成订单或付款。

### Actionable assistance (2026-10-21)

Shopping owns human-readable assistance messages: identify the observed product,
target and read quantity, ask for inspection in the same browser/store, and warn
against repeating unverified adds or checkout/payment. Login instructions require
an actual blocked-page observation. Shared browser execution only transports the
owner message into the durable interaction; AS has no Shopping reason-code map.
Fresh visible quantity controls take precedence over stale hidden select/dataset
values; conflicting visible quantities remain unknown rather than authorizing an
increment. Existing pending interactions retain their original durable prompt.
