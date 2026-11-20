# Harness 连续执行增强

本轮范围：稳定 AI 审核、持久任务事实与产物清单、只读执行前检查、失败后的证据与续做、所属能力的完成验收、后台任务查询等待取消、图像及文档视觉检查、有界独立读取并行、环境查询与受限 PTY。

实现边界：共享 Agent 仅处理通用审批与执行协议。文件、进程、文档和任务证据由 Harness owner 提供；不按业务 App 名称分支。任务笔记、预检及结果正文不授予任何权限。取消和结果未知不自动重放。后台命令继续使用已有进程管理与持久状态，不能另建不受管控的 shell。

## 已实现的接口与行为

| 范围 | 实现 |
| --- | --- |
| AI 审核 | 标准 reasoning_effort=none、2048 token；截断/过滤及无效 JSON 不批准操作，用量仍记入原 Run |
| 持久事实 | task.checkpoint 使用版本检查保存笔记、待办和产物 ID；task.resume 从实际 RunStep 恢复证据，不把模型笔记当授权 |
| 前置检查 | task.preflight 返回当前可见 Provider 版本及 owner 的参数/依赖契约；不执行、不授予 Access 或许可证 |
| 失败续做 | 恢复具体步骤及文件保存回执、保留部分成功；结果未知/取消不自动重放，沿用已有 Runtime 守卫 |
| 完成验收 | task.verify 验证文件存在、长度和 SHA-256；失败回执通过 owner 完成策略阻止虚报完成 |
| 后台命令 | process.start wait_ms=0 立即返回；process.jobs/status/logs/wait/cancel 复用同一套持久进程；等待到期返回仍运行，不算命令失败 |
| 视觉检查 | document.render_pages 渲染最多 4 页 PDF；artifact.inspect_image 支持裁切，检查当前路由的显式视觉能力后把预览交给普通模型回合 |
| 独立读取 | workspace.read_batch 最多 8 项、3 路并发，全部先校验；保留顺序和逐项失败，不允许写入或绕过子 Provider 可见性 |
| 环境/终端 | environment.info 查询版本与可用性，不返回秘密；process.start pty=true、write_stdin、resize、interrupt 复用相同沙箱、进程组、限额和取消机制 |

## 范围说明

- 持久笔记属于当前 Session，进程控制保持当前 Run 归属；恢复不扩大权限。
- 后台能力是 Harness 命令的统一生命周期。模型/导出等 App 自有任务继续使用原 owner 的持久工作流，不在 Harness 内跨 App 直接取消或重放。
- 文件校验不等于语义正确；图片检查使用当前选择且明确支持视觉输入的模型。PDF 渲染依赖已有 pypdfium2，缺失时准确返回配置提示。
- 当前未增加自动安装 Python 包、任意联网 shell 或默认并行写入。

## 验证记录

- 初轮相关 AaAT 门禁 144 项通过；新增两组不同 Provider 的真实 General/Router 视觉投影循环通过（模型回复使用夹具）。
- 最终相关 AaAT 门禁：148 passed / 1401 deselected（只选择本轮 Harness、审批、路由、参数、架构与不同 owner 行为，未运行全量 App 回归）。最后的审核协议指纹/按所选模型预检调整后，30 项专项及 1 项精确预检再次通过。
- 原有进程与图片输入兼容回归：14 passed、2 skipped。首次并行运行时旧取消进程组测试的 1 秒启动等待未读到子进程 ID；单独复测及整组复测均通过，未修改测试来掩盖。
- 真实本地文件、SQLite、PDF 页面渲染、PTY 输入/尺寸/中断/归属均测试；模型决策和视觉能力声明使用夹具，未进行真实付费推理或真实 Bot 对话验收。
- Dev 已通过标准 Helper 重启：PID 18123、端口 52888，健康 200；App 与 Helper source-root 均指向 /Users/avdpropang/sdk/omlx-moe-cache。运行日志确认加载当前 General/Harness 源码，11 个新增工具、PTY/wait_ms 和预检 values schema 已在 live DB 注册。
- 当前 Harness 48 项 Provider。本轮未发布 Package 或 Desktop。
