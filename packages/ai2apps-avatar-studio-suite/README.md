# Avatar Studio Suite

独立数字人 Mini-App Package，首个入口“照片说话”挂载在 Video Studio。

## 依赖与选择

Mini-App 必须声明 `video.avatar_generation` 能力。Host ACPF 根据用户选择安装对应模型 Package、兼容 Runtime 和 checkpoint；不会同时强制安装所有模型。

- 默认：FlashHead Lite，最长 60 秒。
- 可选：FlashHead Pro，最长 10 秒；EchoMimic V3。
- Mini-App 根据已安装模型的签名能力读取预设、分辨率和时长限制，不包含模型名称判断。
- `ai2apps.json.dependencies` 为空是有意的：可替换模型通过能力配置解析，模型 Package 自己声明 Runtime 依赖。App Package 不打包模型、Runtime 或权重。

## 工作流

模型菜单中的“安装模型…”启动 ACPF。图片与声音使用素材槽位，可从 Finder、Gallery、图片/声音 Output 拖入，也可点击选择；支持预览、替换和移除。选择模型及其支持的模式后，提交到 Host 持久视频队列。切换或关闭 Mini-App 不会取消已接收的任务；重新打开可恢复状态，支持显式取消和使用冻结输入重试。Local 进程重启中断的推理由队列标记，用户可重试；不承诺从模型中间状态续算。

视频交给 Video Studio 的 Host Runs/Artifacts 与 Preview & Output，Mini-App 不维护独立播放器、下载或输出历史。

## 交付状态

0.1.0 源码开发候选，使用固定 App-Dev 源码挂载。已验证 ACPF 真实安装、冻结输入重试、切换 Mini-App 后后台生成和 Host 成片预览：Lite 两秒输入生成 512×512 / 25 fps / 50 帧视频及音轨。FlashHead 模型 0.1.0 已发布；本 Mini-App 尚未发布。当前依赖本轮新增的 Host 持久任务桥接，正式发布必须先纳入 Desktop Release 并完成签名归档的严格沙箱安装验收。

完整通用数字人接口的 plan、人物准备和实时会话仍为后续设计；当前实现范围是单人照片加音轨的离线生成。
