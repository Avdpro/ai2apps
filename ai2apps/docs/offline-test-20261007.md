# 脱机 Test 验收 · 2026-10-07

用户授权构建固定 Test 并重置其数据。使用现有 Test Helper `instance.reset` 清理 Test 私有数据，保留共享模型缓存；未修改 Dev/App-Dev/default 实例数据。

- 构建：`apps/ai2apps-acefox/scripts/build-test-app.sh`，固定 `.build/AI2Apps-test.app`；原包由脚本归档。
- 身份：`com.ai2apps.desktop.test` / `test` / `cloud` Runtime，非 Development Bundle。
- 校验：`APP=<固定 Test 路径> scripts/verify-release-app.sh` 与 `codesign --verify --deep --strict` 通过。
- 全新原生登录页点击“脱机使用”成功，无帐号注册。首页显示脱机；公网二维码禁用；帐号页说明帐号功能不可用；模型管理的 AI2Apps Cloud 不可用。
- 本机模拟 OpenAI-compatible BYOK 端点完成原生 UI 配置、模型同步、启用、选择和 SSE 对话。端点仅监听 loopback，使用非秘密测试字符串，不涉及真实供应商密钥或付费推理。重建并重启后脱机模式、Provider 配置、模型启用与对话历史保留。测试后移除临时 Provider 并停止模拟服务。
- Test 安装绑定、安装成员、远程设备记录均为 0。
- 首次本地模型安装暴露 Registry 读取被帐号门禁拦截，已修复：仅公开 Registry GET 使用独立匿名传输，去除 Cookie/Authorization；签名、Range 与 SHA 验证不变。禁止缓存 Cloud 默认模型在脱机时被继承。
- 修复后实机仓库 key、metadata、envelope 200，artifact 206；Qwen3.5 包完成 7.9 KB 下载。
- **未通过：真实本地模型推理。** 推荐的 `ai2apps/model-qwen35@0.1.1` 在启动时退出，服务日志为 `ModuleNotFoundError: No module named 'uvicorn'`。此旧 Provider 包没有声明推理 Runtime，推荐方案也没有 Runtime 步骤；需要单独修复/升级该包的 Runtime 合同后继续验收。未修改已签名包、绕过签名或临时安装依赖掩盖问题。
- 回归：脱机 16、Registry 51、Cloud defaults 10、Cloud client 42、Model manager 31，共 **150 passed**。上一轮身份/桌面引导/认证/网关/调度器另有 112 项通过（包含旧版 14 项脱机）。

当前 Test 保持脱机打开，可直接配置自己的 BYOK 继续测试；没有发布 Desktop 或修改 Cloud 后端。本轮不能声称本地推理完整验收通过。


## 后续：Qwen3.8 Checkpoint 403 修复

用户实测 Qwen3.8 27B NVFP4：Runtime 与模型包已完成，权重索引 403。此前“匿名模型包下载通过”仅覆盖 Package，不代表 Checkpoint 全链路通过。

根因是 CheckpointRegistryClient 仍调用帐号通道，触发本地 offline_mode 门禁。已将脱机时 repository-key 与 checkpoint-distributions 的 GET 改为独立匿名通道；写入和帐号请求保持禁用。索引/发行者签名、摘要、有效期和防回滚校验不变。

真实匿名 Qwen3.8 分发清单 `dist_ai2apps_qwen3_8_27b_nvfp4_16b6615a_v1` 已成功读取并验证，摘要 `sha256:17f3284c174cb3de0cc66eacb891cbfeb5d0f53ce8fce1900dd52b91e4041fb6`。45 项脱机/Checkpoint 联合回归通过。固定 Test 已标准重建并通过打包与严格签名校验；保留实例数据，原生 UI 重试后四步全部完成并显示“安装成功”，Qwen3.8 本地模型出现在 Chat 选择器。

真实本地对话已通过：原生 Chat 选择 `(Local) AI2Apps-MLX · Qwen3.8 27B NVFP4`，发送“请只回复：本地模型测试成功。”，返回“本地模型测试成功。”。UI 报告 15.44 秒（含首次加载）、生成 20.9 token/s、Worker 峰值 23.1 GiB。此前旧包阻塞是历史记录；当前 Qwen3.8 的安装、就绪与真实本地推理均已通过。
