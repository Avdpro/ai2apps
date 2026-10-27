# Mini-Chat：会话与按钮扩展 v1.2

2026-10-24，统一 SDK 1.2.0。适用于内置 App 的受信任宿主接入。
规范边界见 [AaAT 声明与 Context](aaat-declaration-context-v1.md)。

## 兼容性与职责

新增 schema `ai2apps.app-chat/v1`，不替换旧 `ai2apps.mini-app-chat/v1`。
旧 createStudioController、createPackageBridge、registerPackageProvider、Tools、help、
begin/end、URL 查询与 fragment、事件名称和响应结构不变。既有 Browser/Studio/Todo
保持原执行协议；只有 app_chat=1 的入口启用 owner transport 协议。所有路径的 UI 均由 createConversationSurface 生成，不自动迁移旧历史或改变模型选择。

只载入 mini_app_chat.js；独立页面随后载入 chat_mini.js。独立 app_chat_entry.js 已删除。能力检测使用
AI2AppsMiniAppChat.getAppChatCapabilities()；缺少新 SDK 时不要把新请求发给旧协议。

Chat 拥有真正 Mini-Entry 页面中的消息、输入、按钮、表单、Markdown 安全显示、状态和
草稿；App 拥有身份、会话/对象绑定、上下文按需读取、执行、预算、证据、权限、确认和
持久历史。共享层不识别 App、Tool 或站点名字，不新增模型/工具执行器。

标准 Chat/Agent 执行可以由受信任 send 适配器委托现有宿主执行入口；专用问答则调用
所属 API。新 SDK 不提供跳过现有模型、AaAT 或业务入口校验的调用通道。

## 创建控制器

```js
const controller = AI2AppsMiniAppChat.createController({
  identity: {appId: 'example.notes', providerId: 'example.notes.chat', version: '1'},
  describe: async () => ({
    binding: {sessionId: thread.id, contextId: note.id, revision: note.contextVersion},
    title: 'Notes', subtitle: note.title,
    messages: await owner.readMessages(thread.id),
    suggestions: ['Explain the main argument'], suggestionsVisible: true,
    busy: false, status: '',
    actions: [{id: 'save', disabled: false}],
  }),
  send: ctx => owner.answer({
    session: ctx.binding.sessionId, object: ctx.binding.contextId,
    question: ctx.text, requestId: ctx.requestId, signal: ctx.signal,
    onProgress: ctx.changed,
  }),
  actions: [{id:'save', hook:'save', label:{zh:'保存',en:'Save'},
             tip:{zh:'保存此消息',en:'Save this message'},
             icon:'bookmark', placement:'message', order:0}],
  hooks: {save: ctx => owner.saveMessage(ctx.binding, ctx.messageId, ctx.requestId)},
  cancel: ctx => owner.requestCancellation(ctx.binding, ctx.targetRequestId),
  openReference: ctx => owner.openReference(ctx.binding, ctx.reference),
});
```

describe 必须返回宿主已授权的当前快照，而不是模型生成的声明。
identity 在控制器生命周期内固定。binding 三个字段均为非空字符串，最多 200 字符；
revision 是上下文/声明版本，不应每个消息 token 都改变。切换对象、线程或失效的上下文
版本应改变 binding，调用 changed()。旧绑定发起的新调用被拒绝；执行中 hook 始终收到
开始时的绑定，不能重新从全局 selectedObject 选择操作对象。

消息格式为 `{id, role, content, format?, references?}`；role 为 user/assistant/system，
format 为 text（默认）或 markdown。message ID 在快照内唯一且跨更新保持稳定。
引用为 `{id,title,label?,url?}`；HTTP(S) URL 可打开，其余由注册的 openReference 处理。
引用 id 必须来自该消息当前已保存的引用集合，不能传任意对象调用引用 hook。

### AI 回复展示（2026-10-24）

共享 surface 统一输出无气泡的 assistant 正文、Thinking details 及正文下的复制/朗读
按钮。可选消息字段 `thinking` 为字符串，`thinking_tokens` 为非负安全整数，仍计入
原 1 MiB 快照上限；没有数据时不伪造 Thinking 或 token 数。owner 的 send/历史服务
负责提供并持久化这些字段，UI 不为补齐历史而重新调用模型。
旧浏览器/Tools 流式入口消费 `delta.reasoning_content`/`reasoning` 及明确的
`<think>...</think>` 标签，保留跨 chunk 分隔；不按自然语言猜测思考内容。
正文 Markdown 沿用原净化，用户消息、错误和思考均按纯文本呈现。

复制只复制答复源正文，不混入思考、状态、引用按钮或工具栏。朗读只读取已渲染正文，
排除代码块和思考，经 Desktop 既有 `/v1/models` 和 `/v1/audio/speech` 授权入口执行，
不会使用设备系统语音；优先选现有 Chat 的可用 TTS 模型偏好，否则使用就绪候选及其
首个声明音色。复杂音色/克隆设置仍需在完整版配置，本 surface 不宣称完整复刻其音色
偏好。无可用模型或配置失败明确提示去 Desktop 安装/配置。生成分段有界，停止、
切换会话、隐藏页面或移除视图释放播放/请求；不声称能撤销已提交的模型计算。

旧 Tools 路径显示真实已请求的工具名及返回状态；返回不等于业务成功。App owner
自有消息动作、引用和表单保持原 hook、绑定及确认守卫。此更新没有新增通用 Agent
开关，没有发现/调用额外 AaAT，也未将 v1 的前端执行迁成持久后台 Run。
开放讨论见 [Mini-Chat Agent 边界](mini-chat-agent-scope-20261024.md)。

Markdown 使用已有 marked 与 DOMPurify，禁止非 HTTP(S) 链接，移除远程图片以避免
意外联网；缺少这两个渲染库时安全显示纯文本，不执行 HTML。

## 挂载

同页挂载与 Mini-Entry iframe 使用同一契约、控制器和 UI：

```js
const entry = AI2AppsMiniAppChat.mount({root, transport:controller,
  labels:{placeholder:'Ask a question',send:'Send',stop:'Stop'}});
// 或使用 Chat 实际 Mini-Entry 页面：
controller.bind(iframe); // 必须先绑定真实 iframe
iframe.src = controller.url();
```

iframe 的事件同时校验 channel、精确 contentWindow 和同源 origin，不能依靠第一个
发消息的窗口自动认领。页面重新加载仍使用当前 iframe WindowProxy。新 iframe 控制器
URL 的查询参数与 fragment 同时携带新 channel，防止只改 fragment 保留旧执行器。
本版不开放新 App-Chat 给任意跨源/沙箱 Package Frame；现有 Package v1 桥接保留。

## 按钮与 hook

最多 32 个注册动作，支持 header、composer、message、content 四个位置；
label/tip 可为文字或语言字典；icon 为 Lucide 图标名，order 控制同位置排序。
describe 的 actions 只能按已注册 id 更新 visible/disabled，不能注入 hook 或新增动作。
message 位置收到 messageId；所有动作收到 draft、requestId、identity、binding、signal
和 changed()。参数是数据，不允许执行消息中的脚本、函数名或模型提供的回调。

默认忙碌时禁用动作。可信注册可以为重置、关闭等显式声明 allowWhileBusy；这不授予
任何后端权限。Hook 可以调用所属标准表单/确认流程；点击本身不替代业务确认。

异步 hook 可执行所属 API/Task，更新所属状态并调用 ctx.changed()，UI 即读取新快照。
支持可选 cancel hook；停止请求绑定原执行 ID，取消成功后通知原 AbortSignal。
取消不声称撤销已保存结果，未实现 cancel 不展示停止按钮。dispose 中止本地观察信号，
不会自动提交后端取消或重放操作。

## 建议与表单

suggestions 为字符串数组或 `{id,text}` 数组，点击只填写输入，不自动发送。
App 通过 suggestionsVisible 控制其生命周期。首次推荐、发送收起、追问重现及重置策略
属于所属 App；核心不判断“文章”“项目”等业务状态。

可选 interaction：

```js
{actionId:'confirm', fields:[
  {id:'query',type:'text',label:'Query',value:'...',required:true,maxLength:1024},
  {id:'source',type:'select',label:'Source',value:'one',
   options:[{value:'one',label:'Source one'}]}
]}
```

支持 text、textarea、select；actionId 必须是已注册动作。提交传 values 到该 hook，
隐藏原位置同一动作按钮以避免无参数提交。字段和授权必须由所属后端再次校验；
interaction 是 UI，不能冒充现有持久化确认凭证。复杂工作流继续用已有标准交互服务。

## 会话、重复请求和故障

会话历史由 App 后端持久保存并校验 actor/App/Session/object/version。前端仅保存当前
挂载生命周期的最多 128 个绑定草稿，切换恢复；不承诺跨页面重建恢复未保存输入。
切换后旧结果标记 stale，不追加到新对象，也不清空新对象草稿。

同一控制器最多保存 256 个 requestId 的执行 Promise；相同 ID/精确输入共用执行，
改变输入复用 ID 拒绝。成功、失败和不确定结果都不自动重试。达到上限明确报错，不淘汰
旧结果来偷偷重放；重建后需依赖所属后端的持久 requestId 幂等与状态查询，不是 exactly-once。
iframe RPC 超时为 300 秒且不重发；超时不等于后端未执行。原有 v1 超时保持不变。

状态快照最多 1 MiB、200 条消息、12 个建议、每条消息 64 个引用和 12 个交互字段。大历史应由 owner 做窗口/分页，相关资料按需提供给
所属模型，不把全部资料或函数放入消息。按钮状态仅为 UI；Owner API 才是权限边界。

## 首个接入与验收

情报文章对话已作为 owner adapter 迁移，复用其现有线程、Task、证据、有限联网确认与
API，没有在通用执行器中加入情报规则。频道旧共享 surface 和 Todo/Studio v1 均继续兼容。
测试区分：任意 provider 的控制器/iframe 测试为夹具；开发实例的真实页面另行记录。

## 单一 Mini-Chat 实现与兼容边界（2026-10-23）

输入、消息渲染、用户气泡、待响应消息与错误都由原有 Mini-Chat 的共享 surface 提供。旧 Tools 模式及新的 owner transport 只是执行适配器；都用同一个 `beginTurn` 立即加入用户消息和等待消息，不维护第二套聊天 UI。owner transport 不执行模型或业务 Tool，只调用注册的 send/action/cancel/reference hook。按钮可注入 header/composer/message/content，业务语义与授权仍归 owner。

`AI2AppsMiniAppChat.createController/mount` 为当前入口。`createAppChatController/mountAppChat` 以及旧 `AI2AppsAppChat` 名称仅为相同函数的兼容别名，没有独立脚本或实现。既有 app_chat 查询参数、iframe 消息协议与 schema 保留作为传输兼容，不表示另一种聊天产品。

发送即显示 prompt 并清空输入；等待与错误在消息流内展示。失败保留 prompt 并恢复草稿，不自动重发；收到持久消息后去重替换。上下文切换丢弃原视图的临时状态，旧请求仍绑定原上下文。原请求幂等、取消、注册 hook、同源绑定及不确定结果保护保持不变。

验收需覆盖：只加载一个 SDK 的新/旧 iframe、慢请求中的即时消息、进度变化、失败恢复、相同文字的再次发送、上下文切换和跨 owner 隔离；fixture 不能替代真机/生产网络验收。


## 统一组件界面（1.2.0）

iframe 旧入口先通过 hydrateEntry 保留旧 DOM ID 与上下文插槽，再调用与内嵌 owner 入口相同的 createConversationSurface；不再维护两种可见布局。模型、重置同一顶部工具栏，输入区与消息区使用同一 CSS；发送为带 aria-label/Tip 的箭头图标。Mobile 通过共享响应式样式适配，App 不得覆盖组件内部按钮/输入/消息样式。容器高度与所在侧栏由 App 排版。

owner describe 可返回 `models: [{id,name}], model`；可选 `selectModel(ctx)` 只接收模型列表里存在的 ID。model 的实际授权、适用性及执行仍由 owner API 验证；共享 UI 不代替执行权限。可选 `reset(ctx)` 在当前 binding 下执行，或者继续注册旧 `id=reset` 的 action（原 composer/header placement 仍兼容，但统一呈现在模型旁边）。没有 reset hook 的旧 owner 显示不可用按钮，不伪造清空持久上下文的成功。旧 Studio/浏览器入口清空其本身拥有的对话历史；忙碌中不执行本地重置。

新增 action placement `toolbar` 向后兼容旧 placements。旧方法名、事件、schema、AppChat 别名、工具调用、begin/end 和 Package bridge 保留；UI 统一不将旧前端执行器冒充持久 Agent。

## v2 执行迁移（2026-10-27）

[持久执行标准](app-chat-durable-v2.md) 是新 App/Mini-App Chat 的统一执行接入。
Todo 首先改用 `AI2AppsAppChat.create`，继续复用本文件的 controller/surface。
其他尚未迁移的旧入口保持上述 v1 行为，不宣称其已具备后台持续执行。
