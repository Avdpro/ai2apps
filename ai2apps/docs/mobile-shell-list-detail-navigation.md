# 手机端列表与详情的 Shell 双 iframe 导航方案

更新日期：2026-10-11。参考实现：内置 Todo。用户已在实际使用的 iPhone Safari 上确认返回不再闪动，并确认最终切换体验可接受。本方案尚未形成所有 App 都可调用的通用导航接口。

对于嵌在 Mobile Shell 中、需要列表与详情两级导航的可信 App，采用 **Shell 持有导航历史，列表和详情各用一个 iframe**。列表保留，详情预热复用；点击后先滑入框架，数据就绪后揭开占位层。系统右划由浏览器处理，按钮返回由 Shell 播放退出动画。

## 问题与诊断依据

原实现通过 Todo iframe 内的 `pushState` 创建详情历史，再通过 `popstate` 切换列表和详情的 `hidden`。iPhone 右划返回时，用户看到详情短暂重现，随后才显示列表；App 返回外层 Shell Home 则没有同样现象。

一次时序记录显示：松手后约 17ms 发生 `popstate`，约 2ms 后 DOM 已切为列表；下一次 `requestAnimationFrame` 回调却晚了约 372ms。期间没有外层重新打开 App，也没有详情重新变为可见的 DOM 记录。

这支持“原生导航动画、iframe 画面与 DOM 更新之间交接不一致”的解释，但不等于直接证明 WebKit 使用了哪张快照。DOM 状态、rAF 回调与最终屏幕像素不是同一种证据，不能把 rAF 间隔当成准确的屏幕闪动持续时间。

### 未解决问题的尝试

| 尝试 | 实际结果及教训 |
| --- | --- |
| 去掉列表重复重绘，统一滚动恢复 | 仍闪动。可减少无谓工作，但不是本例根因。 |
| 接管边缘触摸、提前切换、等待两次 rAF | 未消除闪动；不要依赖任意延迟修补系统导航交接。 |
| 滑动过程中隐藏详情内容 | 开始和结束各闪一下，已撤回。不要破坏系统手势期间的当前画面。 |
| 在同一个 iframe 中导航到独立详情 URL | 实测 `pageshow.persisted=false`，返回重新加载；详情加载初期两个视图都隐藏约半秒，还出现重新加载提示。已撤回。不能假定跨文档导航必然命中浏览器往返缓存。 |
| Shell 管理两个保留的 iframe | 用户实机确认返回不闪；后续优化了打开延迟和按钮动画。 |

上述结果来自本应用及本次设备环境，不是所有 Safari 页面行为的普遍结论。

## 最终结构与职责

```text
Mobile Shell                         ← 顶层 history / popstate
  frameHost
    列表 iframe                      ← 保留 DOM、滚动、搜索和折叠状态
    详情 surface 容器                ← Shell 控制显隐与水平动画
      详情 iframe                    ← 预热并复用，编辑及保存业务数据
      placeholder                    ← 加载框架、占位与返回按钮
```

两个 iframe 属于同一 Todo App 实例。当前实现复用已有可信 mount 上下文，为详情 iframe 分配独立的消息校验 token；不额外创建 AppInstance。这个 token 用于识别 frame 消息，不是新授予业务权限。

- **Shell**：创建/保留 frame，管理历史、占位、切换动画、返回防重和来源校验。
- **列表**：保存列表界面状态，提供最新已加载数据快照，接到变更通知后刷新数据。
- **详情**：初始化编辑器、处理保存和 revision 冲突，报告 ready/changed/error，提供离开前检查。
- **服务端**：继续使用原有账号与 App capability 校验；快照传递不改变 API 授权边界。

## 交互流程

### 打开详情

1. 列表首次就绪后发送预热请求，Shell 在后台创建隐藏的详情 iframe，不增加详情历史，也不改变当前画面。
2. 用户点击项目，列表发送项目标识、目录、父项目及已有数据快照。
3. Shell 立即显示占位层、滑入详情 surface，并在顶层 history 增加 `{appId, todoDetail: true}`。
4. 已预热的详情直接收到快照并初始化，避免重复加载文档和请求相同数据。预热尚未结束时，Shell 保存待初始化请求。
5. 详情报告 ready，Shell 仅移除占位层，不再次播放动画。占位层必须遮住上一个项目，不能让旧内容在新项目打开时露出。

框架与内容解耦是流畅度的关键：**点击反馈不等数据完成**。一次优化前测量中，打开约 1043ms，其中新文档约 625ms、数据等待约 413ms、Shell 切换约 2ms；这些是单次样本，不是优化后的性能承诺。

### 返回与前进

- **系统右划**：顶层 Shell 收到 `popstate`，直接隐藏详情 surface 并显示保留的列表。不要叠加自定义退出动画，也不要在 Todo 内拦截系统手势。
- **按钮返回**：先检查未保存内容，发送返回消息；Shell 标记按钮来源并执行一次 `history.back()`。`popstate` 中据此播放滑出动画。
- **加载中返回**：占位框架也提供返回按钮。迟到的 ready 只能移除占位，不得重新打开已经退出的详情。
- **前进**：恢复保留的详情视图，避免重新创建 App。
- **保存后**：详情通知列表刷新。普通返回不重建列表、不重新发起 App focus/open 请求。

当前离开检查由可信同源详情暴露的 `mobileTodoCanLeave()` 完成，处理 busy 和未保存确认。不要把这一直接调用复制到跨源或 sandbox App。

### 动画参数

| 操作 | 时长 | 曲线 | 变换 |
| --- | --- | --- | --- |
| 打开详情 | 240ms | `cubic-bezier(.22,.61,.36,1)` | `translateX(100%)` → `translateX(0)` |
| 按钮返回 | 360ms | `cubic-bezier(.4,0,.2,1)` | `translateX(0)` → `translateX(100%)` |
| 系统右划 | 浏览器管理 | 浏览器管理 | 不增加应用动画 |

使用 Web Animations API 动画化 **surface 容器**，列表在动画期间保留在下层。完成后提交最终显隐并取消动画 fill；被新的导航打断时取消旧动画，避免旧回调覆盖新状态。尊重 `prefers-reduced-motion`，不支持动画时直接切换。

## 当前消息约定与边界

以下名字目前都是 Todo 专用，不是公开稳定 API。

| 消息 | 方向 | 用途 |
| --- | --- | --- |
| `ai2apps.todo.open-detail` | 列表 → Shell | 预热，或打开指定项目 |
| `ai2apps.todo.initialize-detail` | Shell → 详情 | 使用当前列表快照初始化 |
| `ai2apps.todo.detail-ready` | 详情 → Shell | 内容已就绪，移除占位 |
| `ai2apps.todo.detail-back` | 详情 → Shell | 按钮请求返回 |
| `ai2apps.todo.changed` | 详情 → Shell | 保存成功，通知刷新列表 |
| `ai2apps.todo.refresh` | Shell → 列表 | 刷新业务数据 |
| `ai2apps.todo.detail-error` | 详情 → Shell | 显示错误并退出失败的详情 |

Shell 同时验证 `event.origin`、`event.source`、mount token、instance ID 及当前 App；仅接受匹配的可信 Todo frame，拒绝 sandbox 入口。URL 从已授权列表 frame 的地址构造，保留 mount 上下文，不接受消息提供的任意导航 URL。快照仅在匹配的同源 frame 之间传递，不写入诊断日志。

## 日志怎么用

2026-10-11 实机验收后已关闭临时采集。两个入口脚本开头的 `MOBILE_NAV_TRACE_ENABLED` 均为 `false`：不会注册诊断事件、创建观察器或定时器，也不会发送日志请求。以后临时排查时将两处开关改为 `true`，整页刷新后启用；排查结束恢复 `false`。服务端接口保留，已打开的旧页面需整页刷新才停止原有采集。

临时采集器位于两个已有入口脚本开头；经同源 `POST /v1/mobile/todo/navigation-trace` 写入 Local 日志，前缀 `MOBILE_NAV_TRACE`。接口沿用认证和 Todo capability 校验，并验证事件 schema。

按以下字段对齐，而不是按服务器收到日志的时间推断事件顺序：

- `session`：同一 Shell 会话的追踪编号；`document_id`：区分列表、详情和 Shell 文档。
- `surface`：`shell` 或 `todo`；两个 Todo frame 通过文档编号区分。
- `at`：`performance.timeOrigin + performance.now()`；`mono`：文档内相对时间；`seq`：文档内事件顺序。
- `event`：触摸、`popstate`、`pageshow/pagehide`、显隐变更、返回或 pageshow 后两次 rAF。
- `persisted`、`navigation`：缓存恢复标记及导航类型。
- `list/detail/stage/loading/route`：页面或 frame 状态。

`list/detail` 读取的是对应元素自身的 `hidden`，并不是最终像素可见性；祖先容器、占位层和动画可能遮挡它。分析新问题时，必要时补充 surface/placeholder 状态或录像，不要仅凭这两个布尔值断言用户看到的画面。

每批最多 40 条，约 250ms 批量发送；单文档最多 1000 条、采集窗口 30 分钟。网络失败不阻塞交互、不持续重试。日志不记录任务内容、业务 ID、表单、URL 或登录凭据。长期使用前应加显式诊断开关与服务端限流/保留策略；当前属于排障用实现。

排查示例（使用实际运行实例，勿混淆 dev 与 app-dev）：

```sh
rg 'MOBILE_NAV_TRACE' "$HOME/Library/Application Support/AI2Apps/instances/dev/logs/local.log" | tail -30
```

曾有一次新增诊断脚本未进入 Runtime 的 `MOBILE_STATIC_FILES`，`mobile_static()` 在模板渲染阶段直接抛错，使手机入口返回 500。现在代码并入已有允许的脚本；新增静态资源时必须验证真实白名单，不要只用不检查权限的模板 stub。

## 其它 App 接入建议

先复用职责分工，再抽取通用接口，不要复制 Todo 专用分支到多个 App。

1. 保持 App 实例和列表 frame；由 Shell 管理子视图历史，业务 iframe 不另建同一层历史。
2. 详情 frame 预热一次、后续复用，传递已有业务数据；后端仍用 revision 或等价并发检查。
3. 框架立即反馈、占位遮住旧数据；内容 ready 不负责导航，也不能把已返回的用户拉回详情。
4. 通用消息需补充 request/generation ID，过滤过期初始化和重复 ready；定义快速连续点击、关闭 App、切换 App、mount 失效时的取消与回收规则。
5. 明确定义多层详情、刷新后的历史恢复、跨源与 sandbox 边界。当前验证只覆盖可信 Todo 的两层视图，不能直接扩展安全边界。
6. 给冷加载失败设置超时与可恢复界面，制定预热内存预算及隐藏 frame 淘汰规则。当前有限预热和基本错误处理不等于完整通用生命周期管理。

## 验证与实现入口

手机验收至少包含：进入详情、按钮返回、完整右划、右划取消、浏览器前进、未保存拒绝返回、加载中返回、返回后再打开另一项目、保存后列表更新、减少动态效果。重点观察动画两端是否露出旧详情或加载错误页。Node 测试通过不能替代 iPhone 原生手势验收。

当前自动检查：

```sh
# 从 ai2apps/ 目录运行
node --test tests/mobile_todo_shell_frames.test.cjs tests/mobile_navigation.test.cjs tests/mobile_todo_navigation.test.cjs
node --check web/static/js/mobile.js
node --check web/static/js/mobile_todo.js

# 从上级仓库目录运行
.venv/bin/python -m pytest ai2apps/tests/test_mobile_todo_i18n.py ai2apps/tests/test_mobile_todo.py -q
```

- [Shell 导航、动画与诊断](../web/static/js/mobile.js)
- [Todo frame 消息、初始化与保存](../web/static/js/mobile_todo.js)
- [Shell 与占位样式](../web/static/css/mobile.css)
- [诊断接口与 schema](../web/mobile_todo.py)
- [Owner 公网入口边界](../web/owner_home_gateway.py)
- [双 iframe 及动画测试](../tests/mobile_todo_shell_frames.test.cjs)
- [真实静态白名单模板测试](../tests/test_mobile_todo_i18n.py)

前端修改使用浏览器整页刷新，Todo 内“刷新”仅更新业务数据。Python 接口修改需要重启对应 Local；Runtime 白名单等下层变更应按 App-Dev 环境规则处理，不能仅靠页面刷新。
