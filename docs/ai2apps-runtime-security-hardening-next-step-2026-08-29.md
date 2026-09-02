# AI2Apps Runtime 安全性增强：下一阶段决策

状态：已讨论、待实现  
日期：2026-08-29  
范围：AI2Apps Local、OpenAI-compatible API、可安装 Service/Model Worker Package、oMLX Runtime

## 1. 结论

当前 Runtime 已经把可安装 Model Worker/Service Package 放到 AI2Apps Host 进程之外，并具备签名校验、不可变 Package/Runtime dependency lock、Worker 临时认证、精确 checkpoint 只读授权、默认禁网、Local Session 和 Tool capability 检查等基础边界。

下一阶段不追求一次性完成最强隔离，而集中解决三个更直接、工程收益更高的风险：

1. 生产模式不得存在无认证的 OpenAI-compatible API；
2. 第三方 Model Worker 不得直接联网；
3. 第三方 Package 不得借 external、subprocess 或未审核 native library 绕过 Managed Service Sandbox。

当前安全定位是：

> AI2Apps 可以安全运行经过审核、签名且遵循最小权限约束的模型 Package；当前边界不承诺安全执行任意敌意 native code。

## 2. 当前已有的安全基础

### 2.1 Host 与 Package 进程隔离

- 可安装 Package 禁止使用 `in_process`/`embedded` 进入 AI2Apps Host。
- Model Worker 的 Python、启动命令、端口、认证 token 和 framework 路径由 Host 生成。
- 旧 `omlx.model_adapters` Host 导入路径在生产环境默认关闭，仅保留显式危险开发开关。
- Package Runtime dependency 固定到已安装、已验证的不可变 digest。

### 2.2 Worker 资源边界

- Package payload 只读；Package data/tmp 独立。
- Model Worker 只读取 Host 根据固定 repository/revision/distribution 解析出的 checkpoint repository，而不是整个用户目录。
- checkpoint 路径必须位于授权 repository 内，越界 symlink 和不完整 snapshot 会被拒绝。
- 模型 Package 默认声明 `network.outbound: false`。
- Worker 使用每次启动独立生成的高熵 Bearer token，App 不直接获得该 token。

### 2.3 Local Web、Package 和 Tool 边界

- AI2Apps Shell 使用 Installation-scoped、HttpOnly Local Session，不需要把主 API key 放入页面 JavaScript。
- Cookie 写请求检查精确 scheme/host/port Origin。
- Package 安装要求 Publisher/signature 校验、静态/AI audit 和必要的显式审核批准。
- Tool Gateway 校验 provider identity、活动 Session、input schema 和 capability，并记录调用审计。
- main/sub API key 只能访问 inference API，不能因此获得 Package、Secret、Trust 或 Platform 管理权限。

## 3. 已识别但本阶段暂缓的方向

本阶段明确不推进以下工作：

1. 使用签名 XPC Runner + App Sandbox 取代 `sandbox-exec`。
2. Worker 按 Package+用户隔离，或按 Session 创建和销毁独立 Worker。
3. 新增完整磁盘、RSS、统一内存、请求时长和并发配额体系。
4. 将网页内容统一标记为不可信输入，并对已经授权的高风险 Tool 做逐次确认。
5. 在 Trust Center 展示模型可见的 Prompt/图片、联网状态和数据保留时间。

这些方向不是被否定，而是暂不作为下一阶段交付门槛。

其中 XPC/App Sandbox 曾因大模型 checkpoint 共享、HF snapshot/blob 链接、MLX path-based loader、Metal mmap 和 Direct Decode 性能等工程问题搁置。未来若恢复，应优先验证“Host 打开不可变 checkpoint 文件并通过 XPC 传递只读 FD，Runner 直接 mmap”的方案，而不是复制 checkpoint 或通过 RPC 传输模型字节。

## 4. 优先事项一：生产模式强制认证并收紧 CORS

### 4.1 目标

生产模式下，OpenAI-compatible inference API 不得因为未配置 main API key 或启用 `skip_api_key_verification` 而变成匿名 API。普通网页即使可以访问本机 loopback，也不能无凭据调用推理、读取结果或消耗大量本地资源。

### 4.2 生产认证规则

生产模式固定采用以下规则：

- 删除“`api_key is None` 时自动允许请求”的行为；
- `skip_api_key_verification=true` 在生产模式下启动失败或被强制忽略并记录安全错误；
- AI2Apps Shell 的同源请求继续使用有效 Local Session Cookie；
- 非 Shell/非 Cookie 客户端必须提供有效的外部 inference client key；
- inference key 不得访问 Platform 管理、Package、Secret、Trust Center 或设备管理 API；
- 不因没有配置外部 client key 而自动生成并暴露一个全局万能 key；没有 client key 时，外部请求返回 `401`。

“生产模式强制 API key”的准确含义是：

> 每个 inference 请求必须由 Local Session 或明确创建的 inference client credential 认证；不存在匿名 fallback。

### 4.3 凭据分层

| 调用者 | 凭据 | 生命周期 | 存储/传递 |
|---|---|---:|---|
| AI2Apps Shell | HttpOnly Local Session | 可跨 Local 进程重启，按 expiry/epoch 刷新 | Cookie；页面 JS 不可读 |
| App instance | 后续可引入短期 capability token；当前由 Host Session/Gateway 代理 | 短期 | 不写 URL/localStorage/Package |
| Model Worker/Managed Service | 每次启动独立 token | 随进程失效 | 当前由 Host 注入；App 不可见 |
| 外部 CLI/SDK | 用户显式创建的 client key | 持久、可撤销 | 只显示一次；服务端保存 hash |
| Host 内部 | Boot secret | 每次 Local 启动重新生成 | 仅内存，不进入 Keychain |

Boot secret 不写 macOS Keychain。Keychain 只保存每个 Installation 数量稳定的长期 root/credential；频繁重启不会创建 Keychain item 或产生垃圾。

当前 main/sub-key 仅做等价字符串匹配，sub-key 仍缺少 scope、audience、expiry 和 quota。目标实现应逐步迁移为：

- 每个外部客户端独立 key；
- 高熵 secret 只在创建时返回一次；
- 服务端保存 key ID、hash、名称、创建者、scope、模型 allowlist、expiry、revoke epoch 和最近使用记录；
- 不在 settings、前端状态、日志或诊断中保存/返回 key 明文；
- main key 最终退化为兼容迁移项，而不是 Shell/App 共用凭据。

### 4.4 CORS 规则

OpenAI-compatible API 的生产默认值从 `cors_origins: ["*"]` 改为默认无跨 Origin 浏览器访问：

- 默认只接受非浏览器 API 客户端和同源 AI2Apps Shell；
- 禁止生产配置中的 wildcard `*`；
- 如用户确需浏览器客户端，必须配置精确 `scheme://host:port` allowlist；
- 不把 Cookie credential 暴露给跨 Origin inference 请求；
- Preflight 只允许实际需要的方法和 Header；
- `Origin: null` 不作为可信来源；
- 远程网页不能借 localhost、CORS 或无 key fallback 调用本机推理。

### 4.5 验收标准

- 生产配置无 API key时，非 Local Session inference 请求稳定返回 `401`。
- 生产配置开启 `skip_api_key_verification` 时启动失败或配置被拒绝，不能静默降级。
- `Origin: https://evil.example` 的浏览器请求不能通过 CORS读取响应。
- 精确允许的 Origin 加有效 client key时可以调用。
- Shell 不接收、显示或保存 main/client key，仍可通过 Local Session正常推理。
- inference key无法访问任一 Platform管理 API。
- Local重启后所有 Boot/Worker临时 token失效；持久外部 client key按其 policy继续有效。

## 5. 优先事项二：第三方 Model Worker 强制禁网

### 5.1 目标

第三方 Model Worker即使能看到发送给它的 Prompt、图片和输出，也不能直接把数据发送到 Internet、局域网或任意 localhost服务。

### 5.2 强制规则

- 第三方 Model Worker必须声明且实际执行 `network.outbound: false`；
- 第三方 Package声明 `network.outbound: true` 时，生产安装直接拒绝，而不是仅提示用户批准；
- checkpoint、tokenizer、processor 和转换资源由可信 Host downloader根据签名 distribution和固定 revision下载；
- Worker不能自行调用 Hugging Face、ModelScope或其他下载 API；
- Worker不能连接任意 localhost端口；Worker和Host之间只使用系统分配且认证的内部 transport；
- Package manifest中的 URL只是资源请求描述，不构成网络授权。

第三方的判定至少绑定 Publisher identity/trust policy，而不能由 Package自行声称“first-party”。AI2Apps正式 Publisher签名的受信任系统 Package可按单独策略审核，但模型 Package仍应默认禁网。

### 5.3 Host Network Broker

确有联网需求时，只允许通过 Host Broker完成最小、受审计的请求：

- 权限绑定 Installation、Package ID、Package digest、操作和 expiry；
- 只允许精确 HTTPS origin，不接受默认 wildcard；
- 校验 scheme、hostname、IDN、port和重定向目标；
- 防止 DNS rebinding到 loopback、link-local、private、multicast和metadata地址；
- 限制 HTTP method、Header、请求/响应大小、超时和并发；
- 不自动附加 Host Cookie、API key或其他 credential；
- 日志只记录脱敏元数据，不记录 Prompt、响应正文或 Secret。

Broker完成之前，第三方 Worker联网请求一律 fail closed。

### 5.4 验收标准

- 第三方 Package的 `network.outbound: true` 安装测试失败并返回稳定错误码。
- 已安装第三方 Worker不能访问 Internet、LAN和其他 localhost服务。
- 禁网 Worker仍可接受Host请求并使用Metal和精确checkpoint授权。
- 缺少checkpoint时由Host触发下载/准备，Worker自身不发生网络请求。
- Broker未来启用后，未授权origin、重定向到私网和DNS rebinding测试全部失败。

## 6. 优先事项三：禁止第三方 Package绕过执行边界

### 6.1 禁止第三方 external模式

`runtime.mode: external` 表示 AI2Apps不启动该进程，只连接一个已经存在的loopback HTTP endpoint。该进程：

- 不受AI2Apps Sandbox控制；
- 不受Package digest和Publisher签名覆盖；
- 可能拥有完整Home、网络、Keychain或子进程权限；
- 可能被另一个进程抢占相同端口；
- 无法由AI2Apps可靠停止、重启、升级或卸载；
- 可能被恶意Package用于访问本机无认证HTTP服务，形成localhost SSRF/confused-deputy路径；
- 可能被多个Installation共享，破坏数据和会话隔离。

因此生产策略为：

- Registry/Discover安装的第三方Package禁止声明`external`；
- Model Package和Runtime Provider禁止使用`external`；
- External功能只保留为Core用户显式创建的本地高级集成；
- UI必须明确说明该服务不受AI2Apps Sandbox；
- External integration不接收Secret Broker注入值；
- 后续如增强，应绑定独立认证token、PID/UID、executable digest、Apple code signature/Team ID和process start time，优先使用权限为`0600`的Unix socket。

### 6.2 禁止任意subprocess

第三方 Managed Service/Model Worker不得依赖或创建任意子进程：

- Package审计检测`subprocess`、`os.system`、`popen`、fork/exec包装和等价native调用；
- 检测结果对第三方Package不是普通warning，而是安装拒绝或必须存在正式review attestation；
- Sandbox profile应在不破坏Python/MLX/Metal初始化的前提下拒绝Worker内部fork/exec；
- Metal compiler、系统GPU服务等通过受限Mach/IOKit能力访问，不等同于允许任意Package子进程；
- 不允许Package通过shell、脚本解释器或PATH查找启动未签名工具；
- 如果某项能力确实需要独立进程，应建成独立、签名、声明依赖的Managed Service，而不是隐藏child process。

静态扫描不能单独形成安全边界；最终必须由OS sandbox和进程监督共同执行。

### 6.3 禁止未审核native library

第三方模型Package默认只允许数据文件和受支持的Python adapter代码，不得携带未审核：

- Mach-O executable；
- `.dylib`、`.so`、native Python extension；
- 可执行脚本/二进制工具；
- 动态下载或生成后加载的native payload；
- 通过`ctypes`、`cffi`等加载的Package自带native代码。

模型所需MLX、oMLX、Metal kernel和正式native extension应来自已签名、已公证、版本/digest锁定的Runtime Provider。

确需第三方native library时必须有独立review attestation，至少绑定：

- Package ID/version/digest；
- 每个native文件的digest；
- architecture和minimum macOS；
- Apple code signature、Team ID和Hardened Runtime结果；
- SBOM/license；
- 禁网和文件访问测试；
- 已审核的加载路径和调用目的。

Package升级或任一native digest变化后，旧批准自动失效。

### 6.4 验收标准

- 第三方`external` Package在inspect/install阶段被稳定拒绝。
- Core手工配置的本地external integration仍可作为明确的非Sandbox高级功能存在。
- 第三方Package携带Mach-O、`.dylib`、`.so`或可执行文件且无attestation时被拒绝。
- 第三方Worker尝试fork/exec/subprocess时被OS边界拒绝并产生不含敏感内容的审计事件。
- 正式模型Package仍可使用Runtime Provider内已审核的MLX/oMLX/native组件。
- Package不能从data/tmp下载、生成并动态加载新的native代码。

## 7. Trust与Package分类

实现上述策略需要一个由Host决定的Package分类，而不是依赖manifest自报：

| 类别 | 典型来源 | 允许范围 |
|---|---|---|
| Built-in | 随AI2Apps App构建 | Host内部代码，走发布安全流程 |
| Trusted Runtime/System Package | AI2Apps正式Publisher、固定Package ID | 已审核native payload和系统能力 |
| Reviewed Model Package | 正式Publisher或明确review attestation | 默认禁网；只使用锁定Runtime native组件 |
| Third-party Package | 其他Publisher | 禁止external、任意subprocess、未审核native library；默认禁网 |
| Local development Package | Core用户显式开发模式 | 可放宽，但必须醒目标记且不能混入生产策略 |

Publisher签名只证明来源和完整性，不等同于安全审核。分类还必须检查Package ID、Publisher/key、review attestation、digest和当前Trust policy。

## 8. 建议实现顺序

1. 引入明确的production/development security profile。
2. 让production profile拒绝无认证inference和`skip_api_key_verification`。
3. 将OpenAI API CORS默认值改为空并拒绝production wildcard。
4. 定义外部client key的新记录格式和迁移策略；先保证不向WebUI返回明文。
5. 增加Host判定的Package trust class。
6. 在Package inspect/install阶段拒绝第三方`external`和`network.outbound: true`。
7. 增加native payload扫描与review attestation验证。
8. 收紧macOS/Linux sandbox中的fork/exec策略，并对现有模型做兼容回归。
9. 增加Host Network Broker；Broker完成前保持第三方Worker完全禁网。
10. 将上述负向测试加入release gate，并在Runtime/Package发布前强制执行。

## 9. 发布门槛

完成本阶段后，Runtime/AI2Apps生产发布至少需要证明：

- 生产OpenAI API不存在匿名路径；
- Shell不持有或暴露全局API key；
- 外部client key不能获得Platform管理权限；
- 第三方Worker无直接网络访问；
- 第三方Package不能使用external；
- 第三方Package不能启动任意subprocess；
- 未审核native payload不能安装或加载；
- 现有DeepSeek、GLM、Qwen、Ornith等正式Model Worker仍可加载checkpoint、使用Metal并保持现有推理正确性和性能基线；
- 所有拒绝行为都有稳定错误码和脱敏审计记录；
- development escape hatch不能在production profile静默生效。

## 10. 本阶段明确不作出的安全承诺

即使完成以上增强，本阶段仍不承诺：

- 抵抗所有macOS/Metal/MLX/kernel级漏洞；
- 对任意恶意native代码提供完整隔离；
- 完整GPU/统一内存DoS防护；
- 同一Model Worker内部的跨Session内存隔离；
- 对已经授权的Agent Tool消除所有Prompt Injection风险；
- 通过App Sandbox实现OS级checkpoint capability隔离。

这些限制应作为后续安全架构输入，但不阻塞本阶段三个高优先级增强。
