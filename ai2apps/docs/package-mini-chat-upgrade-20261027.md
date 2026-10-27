# Package AaAT / Mini-Chat 升级（代码与回归完成，待标准发布）

范围：8个 Package、15个 Mini-App。补齐音乐/音效/歌曲、照片说话与静止时间 AaAT；显式多宿主导出分离、转写、视频换声。新增执行使用原 Studio 队列与共享输出；静止时间要求实际 UI 相机帧计划，不编造默认轨迹。输入归属、模型就绪、可选能力、调用幂等与不确定准入禁止重放在 owner adapter 内处理。AS 无业务身份分支。

Package UI 桥接统一为 canonical package_mini_chat.js：只读声明字段与有界模型/素材元数据，仅可修改闭合 schema 中的草稿字段；禁止运行按钮、未知字段、禁用控件、未知模型选项、凭据和许可确认字段。先验证整份 patch，再修改并调用原草稿保存。只读 context 在慢启动时限时重试，写操作不自动重试。素材元数据不冒充可执行资源引用；缺少引用仍需选择有效材料。

AI Browser 接入同一 App Chat Session/Run/system Task，能力限于当前 Mini-App，普通作用域调用不重复确认；购物车等 owner 业务确认保留。Package 声明带中英文 capabilityCatalog，但这只是签名目录说明，不授予执行权限；宿主必须实际实现相应注册。

通用修复：开发源码加载沿标准构建器从 app.yaml 派生 Mini-App 索引，避免重复维护；并发参数批准凭证写入预先取得 SQLite 写锁，避免多个读事务升级失败。后者为无业务身份的原有并发测试稳定暴露的问题。

候选版本：audio-generation-suite / media-voice-studio-suite 0.2.3；avatar-studio-suite 0.1.4；frozen-time 0.1.2；search-all / shopping-pro / trip-planner / web-reader 0.1.1。

最终回归：448项 AaAT gate通过（184.13s）；39项新增/相关 Package 检查、70项现有 Avatar/媒体/Frozen 集成检查通过；6项新 UI adapter、16项既有 UI 检查及2项真实 Chrome 检查通过。8个候选 Package 的标准构建与 Registry 兼容预检通过。未签名预检工件不用于发布。

App-Dev 真实验证：DeepSeek读取/修改音效草稿并持久保存；Stable Audio MLX实际生成进入 Voice唯一共享输出；第二轮提交后立即关闭页面，原任务在 Local完成，重开后同一会话和输出恢复。两次成功 Run均0额外确认交互。一搜到底Package Chat也能读取/修改实际搜索草稿，未触发搜索。其余生成流程为夹具回归，不声称真实数字人/静止时间/歌曲/音乐推理验收。

账户处于登录状态；此前会话失效的判断不准确。标准发布CLI所需的Installation会话与账户UI登录是两个问题；未读取浏览器Cookie、未签署或发布。候选版本依赖本次Desktop宿主改动，发布前须协调宿主版本；之后严格走标准签名、安装/升级验收与发布流程。详见 [验收记录](acceptance/package-mini-chat-20261027/README.md)。
