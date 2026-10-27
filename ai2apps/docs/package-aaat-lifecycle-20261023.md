# Package AaAT 生命周期与安装续接

## 所有权与执行协议

Discover/Package 层负责目录选择、签名安装、能力绑定和安装回执；原业务由其 App/Mini-App
负责。General Agent 不增加业务分支。复用 CapabilityRouter、Tool Gateway、持久参数表单及
App continuation。没有新增任意 Python、URL、命令或模型提供的回调执行入口。

Cloud capabilityCatalog 仍只是发布者签名的发现摘要。要自动注册，App 的已索引、验哈希、
签名的 app.yaml 还须提供 `aaat.schema: ai2apps.app-service-exports/v1` 和 exports 数组。
每项必须且只包含以下字段：

```yaml
aaat:
  schema: ai2apps.app-service-exports/v1
  exports:
    - kind: app
      identity: main
      name: example.transform
      interfaceVersion: 1.0.0
      servicePackage: publisher/example-service
      serviceTool: example.service.transform
      inputSchema:
        type: object
        x-ai2apps-interface-version: 1.0.0
        properties:
          text: {type: string}
        required: [text]
        additionalProperties: false
      agentContext:
        schema: ai2apps.aaat-declaration/v1
        instructions: ["Explain the owner's supported scope and validation here."]
```

`kind/identity/name/interfaceVersion` 必须与 capabilityCatalog 的 AaAT 导出一致。
Service Package 必须是 root manifest 中非 optional 的明确依赖，已安装、active、隔离运行，
其实际验签 envelope artifact 摘要必须与安装记录一致。Tool 名须属于该 Service，inputSchema
必须与实际 Tool 描述完全一致，并由 Service 自己声明 `x-ai2apps-interface-version`。
不把 requirements 推导成 exports，不把目录里的普通描述当作指令。当前协议是隔离 Service
Tool 桥接；纯前端 Mini-App 必须提供此适配器或维持 UI-only，不能自动变成可调用能力。

运行时适配器使用真实 Tool 的 effects、required capabilities 与网关校验，保留当前 actor、
Installation、Session 和 Run，调用前核验 App 访问权和 Session 所有权。Service 请求通过
已有运行实例 endpoint，Host 自己发送身份及 invocation headers；参数 JSON 不能覆盖身份。
Package 代码不进入宿主 Python 进程。当前桥接不声称 Service 内部业务已完成；结果仍经
原 Tool/Provider 结果与错误策略处理。

## 注册与撤销

启动、Registry 安装状态提交、App 激活/禁用/回滚、Service 绑定/启停/升级/卸载触发重对账。
仅已验证可连接的导出进入 Provider 注册表和参数表单。撤销时移除 Provider 和其自有表单，
最后一个 Provider 消失时禁用对应 Gateway Tool；不覆盖其他 owner 的同名 Tool。
版本绑定 App 版本/双摘要、运行声明、Service artifact 和实际 Tool revision/接口/权限描述。
旧版本表单凭证不能用于新接口。每次准备和执行前再次对账，旧 callback 不能绕过撤销。
跨 App 访问、版本变化和缺失运行实例都拒绝，不通过换 Provider 绕过取消/权限。

## Chat 安装续接

Discover 的只读搜索向模型说明：选定后通过 app.collect_parameters 的 discover.install
表单交接。目标必须是同一 Run 已完成 discover.packages 返回的 candidates，精确绑定
Package/version/manifestSha256/artifactSha256；excluded 不构成候选。

原 Run、输入、引用素材及参数留在既有持久交互中。用户选择“在 App 中继续”后，Discover
按持久记录打开精确卡片，仍走原审核和签名安装操作。用户可核验安装并继续、稍后返回、
取消交接。刷新、断开客户端、重启调度器后从服务器交互恢复；不靠客户端成功布尔值。
核验时重新检查实际已安装 release、App 访问及真实 Provider。缺少声明/运行适配器可返回
installed-but-not-callable，不声称原业务成功。原 Agent 继续审阅新 Provider 声明和业务参数，
安装许可不自动授权业务。重复完成读取同一回执；取消不会转成完成。

安装过程中业务任务尚未提交。既有 Registry install operation 的任意进程崩溃重放没有改为
自动重试；原 Chat handoff 仍保留，安装后可按实际精确安装状态核验。受控依赖重启继续
使用原 pinned continuation。不会因未知安装状态自动安装其他版本。

## 验收范围

组合回归 97 项通过，Discover JS 4 项通过；AaAT 边界门禁最终记录见下。生产目录目前无新版 signed App/Service 导出组合，
真实生产 Package 的安装后调用尚不能据此宣称通过；正向执行使用明确标注的隔离 Service
夹具，Host Router/Gateway、SQLite、交互 API 和调度器使用生产代码。


### App-Dev 实际验收

固定 App-Dev 的真实 Cloud 模型执行 Run `run_7de630f339ee4d10ab997ef246cbe594`：
搜索 avatar，选择 Talking Portrait 0.1.3，打开 discover.install 表单；点击“在 App 中继续”
后到 Discover 的精确 0.1.3 详情，保留完整双摘要绑定，并显示核验继续、稍后返回、取消
交接三个入口。稍后返回能回到同一原 Run；再次“回到 App”仍恢复同一精确版本；取消
交接后原 Agent 读到 cancelled，终态 completed，未安装/接受许可/生成业务输出。

“核验安装并继续原任务”按钮被自动审批拦截，原因是本次真实 Agent 的验收输入明确
限定只准备交接，按钮会推进续接。没有绕过拦截、没有把夹具说成真实安装验收。
安装后继续的正向闭环由真实签名临时 App 构建/验包、Registry App 激活、状态提交、
真实 Router/Gateway/SQLite/HTTP 交互和调度器恢复测试验证，只有隔离 Service 的业务
handler 和外部目录为夹具。特别覆盖 artifact 的 sha256: 存储表示、Service 验证记录的
signature/envelope 层次和最终卸载撤销，避免仅测试手写观测对象。

上线使用仍需要发布者按新协议发布带导出的 App 与隔离 Service。此次没有生产发布，
不宣称现有未声明的 Talking Portrait 已可由 Agent 执行业务。

### 最终验证记录

- 97 项组合 Python 回归通过（13 项新增生命周期/权限/签名激活/续接/transport 用例）。
- 268 项 AaAT 边界与行为回归通过；4 项 Discover JS 回归通过。
- 固定 App-Dev 最终端口 63291，App/Helper 源码根均为当前 Git checkout；实际
  builtin_apps 与 app_exports 模块导入日志来自当前 checkout，discover.js 与
  agent_parameter_forms.js 服务字节和源码完全一致；原生窗口标题为
  `AI2Apps-App-Dev: App-Dev 127.0.0.1:63291`。
- 未构建/发布生产 App 或 Package，未改写 Cloud 代码，未接受真实许可，未触发媒体生成。
