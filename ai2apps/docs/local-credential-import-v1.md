# 本机实例 API Key 一次性导入

2026年11月20日。入口位于模型设置的“导入 API-Key”。本功能不是共享密钥池，不同步后续修改；来源删除或轮换不会撤销目标副本。

## 使用范围

双方必须是同一macOS用户下运行中的兼容AI2Apps实例，在线登录相同Cloud origin和相同稳定用户ID。仅Desktop核心账号可发起；邮箱相同、本地user字段、旧离线身份或单纯管理员API Key不构成账号证明。各实例通过自身私有Cloud会话调用现有auth/me复核，不传递Cloud会话或Cookie，不修改Cloud API。

可导入用户配置的普通模型API Provider和视频BYOK（MiniMax、火山引擎）。不包含AI2Apps托管Cloud、邮箱密码、OAuth令牌、Cookie、任意Secret条目或登录状态。复制Key和对应Provider名称、HTTPS API地址、协议；不迁移默认模型路由、模型启用清单、余额或计划。新Provider可在导入后使用原“刷新模型”功能查询目录。

## 用户操作

1. 两个实例均升级到支持本功能的Helper与Local并登录同一AI2Apps账号。旧来源实例不显示为可导入，不扫描旧数据目录寻找Key。
2. 在目标模型设置打开“导入 API-Key”，选择来源实例，勾选Provider；需要覆盖时显式勾选替换，使用来源的API地址，不能仅按同名猜目标。
3. 来源实例出现原生确认框，列出来源、目标实例及目标程序路径、用户ID、所选API地址、覆盖与旧Key归属确认。
原生确认框的按钮、说明与验证原因使用发起导入实例当前界面语言；不再中英并列。支持当前九种界面语言。

4. 用户选择继续并完成macOS系统所有者验证（Touch ID或系统支持的密码方式）。取消、失败或不可用时不导出。
取消原生确认或取消系统验证时，目标收到“已取消”回执，不进入导出和写入。认证失败与用户取消分别处理。

5. 目标写入自己的SecretBackend，网页只获得逐项imported/failed/unknown及completed/partial回执。unknown须人工检查配置后再决定，不自动重试。

旧Key没有归属记录时，必须在原生确认中显式认领为当前账号；新保存/导入的Key记录账号归属。已记录属于其他账号的Key不能列出或被导入覆盖。归属绑定Key，不因模型目录刷新变化而认领/丢失归属。

## 实现边界

- `CredentialImportBroker.swift`由每实例Helper发布匿名本机Unix socket；同UID、实际Helper bundle身份和内核audit-token对应的动态代码签名与受信任路径都校验。Developer ID使用既定Team；ad-hoc仅允许同一固定`.build`目录中的固定Dev/App-Dev/Test包，拒绝归档或仅伪造bundle ID。原生确认展示准确目标路径；导入可变源码的Dev意味着用户信任该开发环境。
- 两个Helper通过受保护的本机Unix socket传输；原生Helper与其自身Local复用每启动随机Helper认证通道，内部回调只允许三个准确路径、无Origin且正确Bearer。不向Local HTML开放明文导出接口。
- 账号、安装身份、安全namespace、成员epoch、来源版本、所选Provider和目标前态绑定到180秒的本启动票据。来源offer和目标install均只消费一次；重启后旧票据无效。系统确认后再次验证双方当前状态，不能把旧批准套到新账号/新Key。
- 来源/目标Key版本是实例私有salt的HMAC，不在网页提供可枚举明文摘要。Provider配置和Key变化会使原offer失效。目标变化或已有Key未明确替换时拒绝。
- 明文只短暂存在于可信Local/原生Helper内存及已认证内部通道，不放入公开响应、剪贴板、临时包、日志或模型上下文。Key不经过第三方网络；Cloud仅用于现有身份复核。导入本身不调用付费视频模型。
- 每项持久写入失败尝试恢复原配置/Key；无法证明恢复完成返回unknown。多项批次明确partial，成功项保留，不自动把整个批次重放。

## 验证

Python安全回归见`tests/test_credential_import.py`，覆盖同账号复制、跨账号/Cloud拒绝、来源轮换、目标变化、覆盖、归属隔离、重启/过期、单次消费、视频用户绑定、部分失败、内部接口拒绝浏览器、非秘密响应。它们使用隔离目录、合成Key和身份/Cloud夹具，不代表真人生物识别或真实第三方Key迁移。

原生初始化采用Unix socket，不序列化NSXPCListenerEndpoint；该可选模块初始化失败只记录不可用，不弹框阻断Local启动。隔离原生夹具命令为`apps/ai2apps-acefox/scripts/test-credential-import-native.py`。原生Helper需经标准Swift编译与固定Test构建；Test实机证据、真人系统验证和来源升级状态单独记录到本轮验收收据。完整测试方案中的C33规定端到端及异常步骤；自动测试不能替用户完成系统密码或指纹。
