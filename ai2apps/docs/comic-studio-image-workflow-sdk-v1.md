# Bounded image workflow SDK v1

`image.workflow` 是可声明的 Studio 通用能力。Package 编译有界的图片序列，Host 不理解系列、漫画、角色、脚本审核或调度规则。

挂载桥接操作：

| 操作 | 参数 / 结果 |
| --- | --- |
| `image-workflow.models` | 当前身份的现有绘图目录与编辑参考上限，仍由绘图服务校验 |
| `image-workflow.import` | `file: Blob`，最大20 MiB；返回私有 `id` |
| `image-workflow.read` | `assetId`；返回 Blob。素材编号不得覆盖消息协议的 `id` |
| `image-workflow.reference` | Host 已支持的 Gallery / Output 引用；受原有所有权校验 |
| `image-workflow.submit` | `plan: ai2apps.image-sequence/v1`；返回持久任务 |
| `image-workflow.lookup` | `key`；只查询原提交，不执行 |
| `image-workflow.status` / `cancel` | `jobId`；只能访问本身份、本 Studio 实例、本 Mini-App 的图片工作流任务 |
| `image-workflow.retry-publication` | 只允许已保存最终检查点的 `publish_failed`；不重做推理 |

HTTP 前缀为 `/v1/platform/studios/{studio_id}/mini-app-mounts/{mount_id}/image-workflow`。

计划包含1～6个步骤；每步为提示词绘制或已接受私有图片复用，可附最多4张必要参考图和此前最多2步缩略图。必要参考优先，剩余配额分配给此前画面。输入在提交时快照，后续草稿修改不影响已接受计划。最终成品为独立标题、图片格与图外说明文字组成的 PNG。现有图片保持比例，不进行拉伸。

图片资产按 actor、installation、provider 隔离。私有步骤不创建共享 Output Run；最终输出沿已有 Studio 发布路径。成功后的输入快照清除，私有接受图片保留以供角色复用及重新排版。推理中断不自动重放；不确定提交提供只读查询。

本 SDK 不替代任意 Service Package 业务代码。当前支持下述有界声明式配方；复杂业务决策、独立业务数据库或多候选审核等逻辑仍适合独立工作流Service。

## 有界声明式定时计划（2026-10-31）

新增可选能力 `image.workflow.schedule`。Package可以提供一份纯数据Recipe：提示词、记录JSON schema、已确认参考图白名单、模型/尺寸、1～6步和1～5次迭代，以及自身草稿中的只读上下文路径。Host不加载Package脚本，不理解漫画角色或笑点；只验证声明、调用模型、验证结果、提交原有图片任务并保存通用记录。因此这种有界配方可直接承载当前自动编剧加绘制；复杂业务代码、任意循环或候选评审仍不属于该接口，后续可采用隔离Service。

- `image-workflow.schedule.get/set` 映射GET/PUT `/schedules/{resource}`；默认关闭，明确保存启用后才创建有效计划。
- 系列路径、数据schema与提示词由Package编译。数据仅在actor/installation/studio/mini-app/provider自己的空间内读取；不接受文件路径、外部回调或可执行代码。
- 复用SystemTaskService，未增加时钟或第二条调度循环。不可变Recipe版本与时钟行通过统一事务写入原系统计划表；注册的通用处理器绑定Studio，重新核验Package摘要、声明和实例访问权。
- 当前只支持桌面配置、固定1～168小时间隔、首次运行时间与每批1～5次；UI同时显示最大脚本/图片调用次数。模型选择固定到保存时的具体ID，变化需再次保存。
- 结果记录独立于前端草稿保存，不会因旧页面自动保存而丢失。Package读取回执合入分集历史，保留用户正在编辑的草稿。每次脚本生成合并最近20条记忆。
- 同资源自动任务生效期间，新的手动绘图提交被拒绝；自动任务遇到已接受的手动绘图先等待。取消只影响本任务拥有的下游任务。
- 从已保存脚本、图片任务ID和输出回执恢复；文字提交结果不确定或图片被标记interrupted时不自动重放。禁止用重试换Provider。漏过周期仍由系统合并。
- “手动”只停用未来触发；正在执行的任务由统一任务中心取消。验收后没有遗留启用的漫画计划。
