# WebAgent 验证后修正规则缓存

`browser/repair_cache.py` 提供 owner 本地 SQLite 缓存。键隔离 actor/Profile/caller/program/step/URL，版本绑定 Source digest、generation、完整操作参数及目标说明、compiler/policy、站点及当前验证策略。修复提示记录结构和唯一目标的 SHA-256，不保存原 DOM ref、坐标、页面正文或操作回执。容量2048条，按最近验证时间淘汰。

Probe 给每个控件增加最多32层 composed DOM 路径（标签、role、同类兄弟位置），覆盖 Shadow DOM；完整控件集合、语义及允许候选共同建立结构指纹。位置/ref 变化可以重新绑定；控件结构、语义、范围变化或 Probe 截断则失效。过深结构不参与缓存。缓存命中也重新编译、fresh Probe、标记复核和 native hit-test；动作及参数不可被修复改变。

第一次只有生成和执行前复核还不会保存。正常命令返回后，owner verified=true 或视觉事后确认且 owner 无明确反证，才提交。未知副作用、回读反证和缓存目标的视觉拒绝会清除提示，不重放动作。原 exactly-once action journal 保持。

默认顺利命中原规则、且没有缓存时不增加模型调用；已有缓存可跳过失效的原定位，校验后使用。缓存命中省去 repair/select 模型调用，但保留声明要求的 review/after。没有足够事后验证的恢复不推广为缓存。共享 AS 不包含业务分支。

验证记录待追加。Dev 验收是明确的本机受控悬停页，使用真实 Dev Local、Default/native BiDi 和当前 DeepSeek；不把该页描述成外部购物网站测试。

## 回归与 Dev 真实执行

20项 owner 缓存回归覆盖两个任意站点、SPAN/DIV、新文档 ref/坐标变化后复用、结构/语义/允许范围/Source/generation/操作参数变化失效、actor/Profile/URL隔离、截断拒绝、视觉拒绝、缓存命中后的丢回执不重放及缓存写入失败不掩盖成功。117项缓存/原恢复/原生执行核心回归通过；9项 Node/真实 Chrome DOM SDK回归通过，含32层路径界限及共享 Probe加载版本。

真实 Dev 受控页 `http://127.0.0.1:58743/`，当前 DeepSeek `cloud/deepseek/deepseek-flash`，Default原生 userContext。通过标准 Builder Repository 创建可归档任务，再由原生 Sidebar 的“试运行全部”实际派发到 Dev Local；没有用模型替身，也没有修改执行/授权守卫。页面只有安全的 Preview report 悬停操作。

- `run_c5f434a1392c4126b704a843f0025383` completed/success：miss → repair → rule_validated → review → after → saved；3次模型调用。
- `run_f728db79307e45d49851d99db47d5af6` completed/success：hit → rule_validated(generated=false) → review → after → saved；2次模型调用，无 repair/select。
- 两轮 generation 均 `agen_7770b95a6010438396ac3c9016b63579`，Source digest均 `sha256:398ca16ed21ccc47c6be5e23e3f117e319b1ac876fb8379a2eb5bf27a2bc6b57`；SQLite实存1条、hits=1。完整计数摘录 `/tmp/repair-cache-live-evidence.json`。

早期诊断任务说明误写为 description，Source DSL实际读取 desc，第二轮虽hit仍被视觉复核拒绝且没有操作；旧轮次已取消。受控任务修正说明并产生新generation后，上述最终两轮通过。缓存命中从不保证跳过视觉或owner验证。

最终门禁及 Dev 收尾源码绑定/清理结果见发布台账。外站跨站点恢复用夹具验证；本次真实验收是 Dev 原生浏览器运行受控任务，不是购物车变更或外部站点验证。

最终强制门禁352项全部通过（exit0，既有 headless Metal退出警告）。其他 Dev 情报任务结束后，通过标准 Helper 重启加载最终保护，Local端口63169；App/Helper源根、background_page/visual_recovery实际导入路径及served Probe/客户端SDK字节均核验匹配本checkout。重启后SQLite仍为1条/hits1。专用draft已归档，已知ID的唯一验收标签页关闭，本机服务停止。App-Dev未重启；未构建、发布或修改Cloud。
