# 短漫工坊 Mobile 路由需求（待 Cloud 项目处理）

本仓库只实施 Local 和源码 Package，不修改或部署 Cloud。

手机远程挂载需要在现有 Owner / Installation / mount 权限边界内，将以下精确路由转发到当前 Local。沿用既有 Studio 草稿和挂载路由，不开放任意路径代理，不以 Edge HTML 404 代替 Local JSON 权限响应。

前缀：`/v1/platform/studios/{studio_id}/mini-app-mounts/{mount_id}/image-workflow`

| 方法 | 后缀 | 请求 |
| --- | --- | --- |
| GET | `/models` | 绘制模型目录 |
| POST | `/assets` | multipart image，最大20 MiB |
| GET | `/assets/{asset_id}` | 私有图片；保留 no-store |
| POST | `/jobs` | 有界图片序列 JSON；不可因响应丢失自动重放 |
| GET | `/jobs/{job_id}` | 原任务状态 |
| DELETE | `/jobs/{job_id}` | 取消原任务 |
| GET | `/submissions/{key}` | 只读确认原提交 |
| POST | `/jobs/{job_id}/retry-publication` | 显式重试既有成品发布 |
| GET | `/schedules/{resource}` | 计划状态及当前Provider私有回执 |
| PUT | `/schedules/{resource}` | 明确启用/停用有界计划；当前Local要求Desktop身份，不能通过Cloud路由扩大为Mobile授权 |

验收应覆盖：未授权 JSON 403、错 Owner / Installation / mount 拒绝、上传尺寸、图片流、幂等 key 冲突、移动端素材选择和预览、重开草稿、断网后查询原任务及实际 iPhone 滚动。现有 Local 端已经执行身份和能力检查；Cloud 路由不能扩大授权。
