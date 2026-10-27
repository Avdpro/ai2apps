# AaAT 动态发现与情报中心验收（2026-10-20）

## 实现边界

- AS 仅增加通用 `CapabilityProvider.discovery_context` 观测钩子，按当前用户、Installation、Session 读取；有大小、数量和等待预算，不跨用户缓存。业务数据作为不可信观测进入请求，所选能力仍须读取可信声明并校验权限。
- 情报中心适配器位于 `intelligence/aaat.py`，提供频道、主题、设置及采集更新时间、已有频道新闻查询和经来源确认的临时课题。通用 Agent 没有情报中心名称分支。
- 临时采集复用已安装 Search All / Web Reader 的既有权限和持久工作流，不创建频道或定时订阅。确认绑定完整参数、Provider 版本和同一 Run/Session，取消及改参不能复用旧确认。
- 确认的检索词不再隐式拼接所有来源未统一定义的 `since:` 运算符。回看日期是请求范围；当前不逐条核实发表日期，报告明确说明不能当作严格当日新闻列表。

## 实际 Dev 验证

固定 Dev App / Helper 均绑定当前 checkout；标准 Helper 在无活动任务时重启。最终 Local PID31945，端口59930，导入日志来自当前 checkout。没有重建 App、修改 Cloud 或发布。

1. 腕表自然提问 Run `run_177fea035e3e411981f0d2f98371432f`：模型从动态 Context 发现“腕表”，读取情报中心声明并调用 `intelligence.news`，没有转去通用搜索。后续 Run `run_846c9c46f6774717ae899aa0cd925dac` 验证本地日期/UTC 偏移，结果按本地今天筛选，明确区分入库日期和未核实发表日期。
2. 军事自然提问 Run `run_95f1b2177aee4503a85e350db8d56351`：当前真实数据有“国际新闻”频道，主题包含军事，模型因此调用该频道并披露旧资料及预览限制。没有删除用户频道来伪造无覆盖条件。
3. 临时军事课题 Run `run_702fd28d1e4b46f3a2605b358fc96138`：确认前 durable research tasks 为零；确认 Google、Bing 后展示搜索及阅读进度。前两轮查询结果严重偏题，报告如实披露；模型尝试重开确认并最终遇到现有24步上限，已完成的子报告仍可见。此轮不算有效新闻质量通过。
4. 修复隐式日期改写后，新会话 Run `run_a6b3180ef1c1436280f0fd808779b196`，确认 `Ukraine military news`、最近1天、Google/Bing、每源2条。两路各返回2条，正文实际读到 Reuters 5089字符和 Wikipedia 12000字符；BBC 需要浏览器用户协助，作为阅读失败保留。最终 Completed，报告区分百科背景与新闻，保留日期不一致和未核实限制。最终引用只绑定两个实际读取 URL，Google 跳转解析后的 Reuters 原始文章 URL 进入报告。未声称 BBC 阅读成功，也未声称严格当日覆盖。

## 自动化验证

- `../.venv/bin/python tests/run_aaat_boundaries.py -q --show-capture=no`：最终136项通过（78.62秒），纳入通用动态发现及情报中心行为测试。已有无 Metal 设备退出警告，不影响测试通过。
- 新5项用例通过：任意 Package 风格身份、按用户/Installation隔离、可见性/禁用/版本、超限及取消；已有腕表频道调度；只有腕表频道时军事课题自动选择、确认前零执行、等待期间 Runtime 重启、HTTP 表单确认后仅一次执行、绑定原始引用且不新建频道。
- 上述缺失频道用例为可重复的模型/网络 fixture，不冒充实际网络结果。实际 Dev 的“国际新闻”已有军事主题覆盖。
- 现有 Intelligence 扩展批次20通过，1项旧 `interval_hours=2` 校验预期冲突排除，未放宽规则或改测试来掩盖。

## Package 适用性

同一声明/观测/确认/结果契约适用于 Package 导出；安装和升级适配层须从已验证导出注册 Provider，并通过隔离运行实例的只读协议取得观测，绑定用户、Session、Installation及 Package 版本。禁用或卸载撤销能力。不得执行第三方宿主 Python 或允许 manifest 提供任意回调路径。

当前实现提供通用钩子和契约；完整 Package AaAT 导出与发现 RPC 自动桥接尚未实现。现有 `PackageRuntimeBinder` 仍只自动接入原有 Service Tool manifest，依赖声明不等于能力导出。
