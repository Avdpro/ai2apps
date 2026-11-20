# Mobile 首页、Dock 和 Messager 列表布局

2026-11-19 按用户反馈调整：

- 首页 App：Messager 放首位，Chat 紧跟 Todo，其余保持相对顺序。
- Dock：保留 Home；Home 后首个固定 App 为 Messenger，Chat 不固定。最近使用项排除 Messenger，普通与签名内联 Chat 均在打开后参与最近项排序。
- Bot 列表：隐藏 Shell 的「AI2Apps / Messenger」顶栏，保留底部 Dock。进入对话/详情/创建时沿用隐藏 Dock 的现有方式，返回列表恢复 Dock，但不恢复 Shell 顶栏。
- 保留 App 自身标题和 iOS 原生「我的 Desktop」导航。

可见性继续由受 mountToken / instanceId 约束的既有 Shell 消息控制，初次加载、重新激活及历史返回使用一致设置。无新增接口、资源白名单、Runtime 或原生 iOS 改动。更新 HTML / JS 后重新进入 Mobile 页面即可。

验收证据：`acceptance/mobile-messager-dock-header-20261119/receipt.json`。Chrome 媒体和服务为夹具；实际手机视觉效果仍待用户刷新确认。

## Bot详情依赖修正

Mobile统计和任务用量共用messager_usage.js中的formatMessagerUsage；该脚本此前未登记到App挂载资源清单，导致详情异步统计报函数未定义。现补齐该脚本及分组对话框所需的text_input_dialog.js、system_dialog.css。回归改用实际App资源声明处理器，并在浏览器里展开统计区确认Tokens内容可见、无错误提示；不再用无限制静态夹具掩盖资源缺失。8项Mobile检查和1项完整Chrome回归通过，Dev已通过自身Helper在无活动任务/语音时重启更新manifest；手机重进页面即可。证据acceptance/mobile-bot-sidebar-assets-20261119/receipt.json。

## 进入Desktop时的稳定加载页

入口HTML首屏即为统一加载状态，连接、授权交接、App目录及挂载恢复期间不显示半成品首页、Shell标题和Dock。重定向保留加载；重复connection-ready事件单飞合并，在最后一次启动完成后只揭示一次稳定页面。失败转明确错误，普通/mobile或/mobile/home可手动重试读取入口，不重放Bot业务请求；交接令牌仍沿用原一次性处理。成功重试恢复连接文案及活动卡片。

加载页遵循减少动态效果偏好并提供aria-busy/status状态；390px截图已检查。Chrome慢速分阶段响应、重复事件、失败/重试2项和原签名/Owner回归2项通过；生产模板19项及8种入口首屏验证通过。运行Dev已提供当前JS/CSS字节，HTML热更新；不需重启Local、重建手机或修改Cloud。真机体验仍待用户重新进入Desktop确认。证据acceptance/mobile-stable-entry-20261119/receipt.json。

## 精简Bot列表标题

Mobile不再显示Bots/Inbox切换和Inbox视图。顶部使用50px“我的 Bots / My Bots”标题栏，右侧保留44px新建按钮。分组、未读/协助状态与Bot对话入口保留；Desktop与通知后端不变。8项Mobile owner/真实资源检查及1项完整Chrome回归通过，并检查390px截图。Dev已热更新，不需重启或重装；证据acceptance/mobile-bots-compact-list-20261119/receipt.json。

## 页头按钮视觉统一

Mobile Bot列表、聊天和详情页头参照情报中心改成透明无外框按钮；返回使用28px圆角SVG、3.5描边，新建/详情图标为24px。保留44px点击区域和键盘焦点描边，输入区按钮不变。完整Mobile导航回归通过，390px截图已查看，运行Dev样式与源码匹配；HTML/CSS刷新生效。证据acceptance/mobile-bot-header-icons-20261119/receipt.json。
