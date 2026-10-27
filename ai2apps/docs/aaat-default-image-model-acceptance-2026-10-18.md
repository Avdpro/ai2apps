# 默认绘图模型选择修复验收（2026-10-18）

## 行为

- GPT Image 模型族补足 image_edit；显式 imageEdit=false 等声明优先。
- 默认模型不在当前操作候选列表或未就绪时，不再取列表中第一个模型，也不再伪造兼容模型。
- General Agent 通过 Provider 参数声明打开持久化模型选择表单，保留参考素材及已有参数。提交才继续原 Tool，取消则停止。
- 旧 Cloud ID 仅可按现有网关规则匹配同一模型的账户 Cloud ID，已配置 BYOK 不得因此转到账户 Cloud。
- 没有修改默认模型设置，没有修改 ACPF 安装或 Runtime 重启恢复实现。

## 回归

45 项通过：test_provider_parameters（8）、test_imagine_reference_tools（2）、test_image_capability_providers（4）、test_parameter_forms（6）、test_ai2apps_tool_recovery（25）。包括默认模型不在列表、精确默认模型优先于列表顺序、旧 Cloud ID 同模型映射及 BYOK 隔离、表单等待期间重启调度器后恢复、能力审批后只执行一次。

## App-Dev 激活与真实任务

- App/Helper 的 AI2AppsDevelopmentSourceRoot 均为 /Users/avdpropang/sdk/omlx-moe-cache。
- Helper 重启 Local；16:01:57 启动日志确认当前 checkout 的 ai2apps/storage/database.py。端口 52923。
- 保留旧的等待输入转写 Run run_d3049bef26854196b1bef1fc61fc90bc，没有终止或提交该表单。
- 通过真实 Chat 界面发起合影，Run：run_27c22ce9b283429291743f9529c31597。
- Tool：image.group_photo；Studio job：stjob_8e6a5be17151451d915f24f01ffc4287。
- Agent 未指定 model，job 实际使用默认 cloud/openai/gpt-image-2.5-flare，source=cloud。
- 两张最初上传的参考图 art_68dcaedf1d7a4a7781839e39041ce4a9、art_83eff05513d94974a5226e7ae0cd1a11 均传入；原始字节数分别为 2567922、1248206，任务中解码后的 SHA-256 与素材 content_hash 一致。
- 生成成功，Studio job 08:03:09–08:04:05 UTC（约 56 秒），Agent completed。返回模型仍为 cloud/openai/gpt-image-2.5-flare，Provider 为 ai2apps.imagine.group-photo。
- 输出 art_d9a7a1145b144c2da199827c1199b6f6，PNG，1024×1024，1709534 字节；已读取实际产物检查画面。Chat AX 显示 Completed、新素材 ID、默认模型名称及两张原始参考 ID。
- 自动化覆盖表单等待期间调度器重启恢复；未执行实际 Runtime 安装升级。
