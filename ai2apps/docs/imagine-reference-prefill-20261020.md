# Imagine 已生成素材预填修复（2026-10-20）

## 诊断

App-Dev Session `ses_d8546b9dcaf7498c9c1260ce370bc447` 中，生成 Run `run_c5f86375e9704026866f2cbb4df2bd0c` 成功返回熊猫图片 `art_c8e4880ff1cb40e1a410a7d8716d0d3c`。图片实际保存在该 Session，后续两次 General 模型请求均含该真实 ID；不是生成失败、图片未保存或 Session 素材被裁剪丢失。

后续 Run `run_13ab6388ba1f45638eeae36572c53799` 与 `run_caaaceb544fc4083b5fde091b9713243` 的 app.collect_parameters 只传了文字 prompt、背景、姿势及尺寸，遗漏 person_artifact_ids，所以表单正确显示0张已选素材。描述“相同熊猫”不能代替传入素材 ID。

## 修复边界

- `images/mini_parameters.py` 提供 Imagine 所有的 AaAT 声明，注册给现有图像 Provider，包括生成、修图、合影、风格转换和参考创作。声明要求复用用户指向的真实素材 ID；打开表单时带入已知引用，即使素材数未达最小数量也保留，继续收集缺失照片。
- 合影的主体包括人、动物和角色；熊猫必须作为主体引用，而不是只有背景文字。未知的“我”仍需用户本人照片，不复制熊猫 ID 来凑数量，也不自动猜用户身份。用户主动删除素材优先。
- AS 仍只执行现有选定声明复核，未添加 image/group-photo/App 名分支。测试同时发现“只开放表单 Tool 时，路由目标声明被去重漏掉”的通用缺口：现在只有已经实际投影的 Provider 才去重，表单路径保留 Provider 版本。任意新 Provider 的回归验证该机制，不识别图像业务。
- Schema 的最少素材数、素材归属、最终校验、模型选择和计费入口保持原约束。部分预填不等于可以直接提交生成。

## 回归

新增两项 owner 测试：Provider/Form 共享声明；真实 Session 素材引用经过历史投影、声明复核、持久化参数表单和 API 可见，并保留“缺用户照片”的校验。移除预填素材后不会自动重加，未创建生成 Job。

新增任意 Provider 的 form-only 声明/版本/禁用回归。已有 Provider 模型夹具适配声明复核的额外规划轮；模拟构造的 executor 补足 router 属性，发现调用使用有效 ToolCallContext，不放宽产品守卫。

首次较宽回归出现一次既有 SQLite handoff 读转写锁竞争；未据此修改本轮业务或降低并发守卫。之后完整127项组合通过；最终包含取消恢复补充的统一门禁128项通过，72.42秒，退出码0。测试结束仍有既有 Metal 不可用 atexit 警告；没有 GPU 推理验收。


## 声明更新期间的交互恢复

第一次激活后，旧表单的取消先遇到新增所有者声明复核，使真实取消结果尚未返回模型就触发重新规划。已修复通用顺序：已提交控制交互的读取不提交新业务，先消费真实完成/取消结果，保留原请求与权限/版本校验。新增任意 Provider 热更新声明期间取消表单的调度/API测试，确认只保留一次交互、不重开、不执行业务。不是按图像 App 或合影能力特判。


## 最终实机验收

通过标准 Helper、空闲检查后激活最终 Local PID3234 / 端口56743。固定 App/Helper 的 app-dev 身份及源码根指向当前 checkout；启动日志中的 Todo/Service 组合路径仍来自该根，原生标题与端口一致。只改 Python，没有 App 重建或静态资源变更。

在原 Session 使用已配置 DeepSeek V4.1 Flash 提交：`打开合影表单，我要和刚刚生成的熊猫合影，16:9。`。未手工选素材、未在输入中提供 artifact ID。

新 Run **run_9828738a743c40f185911fe514fa98f0** 停在 waiting_input，interaction **int_6b092eb01c344557a09b51c7895566b4** pending。持久记录显示首轮不加载完整声明；选中后经过 tool_declaration_required，第二轮模型请求包含 Imagine 合影声明，实际表单 values.person_artifact_ids 为 `["art_c8e4880ff1cb40e1a410a7d8716d0d3c"]`，与原生成产物完全相同。

原生 Chat 显示素材槽“1/3，至少2个”和原熊猫文件预览，等待补充本人照片；没有把背景文字当作素材，没有补造第二张图。验收 Run 创建后没有新增 Studio 生成 Job，未提交图像生成。当前表单保持打开，1792×1024 的既有不支持提示仍保留，需要用户重选模型支持的尺寸；本轮没有静默改写尺寸。

初次激活后旧交互曾因声明更新而多规划一个表单的现象，与最终新 Run 的成功记录分开；该通用顺序已修复并回归，不将旧交互的重开当作最终新流程验收。

## Current-change routing (2026-10-29)

The Imagine owner distinguishes image content/action/object/local edits from visual
style conversion in both compact Tool summaries and trusted AaAT declarations.
`image.edit` preserves unrequested properties, including an existing visual style;
`image.style_transfer` is selected when the current request asks to change that
style, not merely because it produced the source. Sequential work uses the actual
latest selected artifact ID. No host-side prompt keyword classifier or tool retry
is introduced; actual invocation still follows normal scope, version and approval
checks. Live-model routing evidence is recorded separately from fixed-rendering
reference validation.
