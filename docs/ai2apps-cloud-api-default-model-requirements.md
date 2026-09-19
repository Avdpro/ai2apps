# Cloud API Default 模型配置需求

日期：2026-09-09。状态：客户端按本合同完成接入，等待 Cloud 项目实现、部署与联调。
本任务没有修改 Cloud 源码、配置或生产状态。

## 产品行为

Cloud 管理全局 API Default，初始选择现有目录 ID `deepseek/deepseek-v4-flash`
（DeepSeek V4 Flash）。不得仅根据显示名重新创建模型记录。
新 Device/Local 的 Work complexity 三档 simple、standard、complex 未显式指定模型时，
动态继承此默认值。用户手动选择优先；清空选择恢复继承。
默认模型变更无需再次升级已支持本协议的客户端，也不写进用户显式 routes。
本次只覆盖 Work complexity，不能给图像、音频、视频专用槽位填入文本模型。

## 新增读取合同

`GET /v1/ai/defaults`，HTTPS，公开的非敏感全局配置；全新客户端登录前即可读取。
不返回上游 Key、Cookie、安装凭据或内部服务地址；推理仍按既有授权和 Points 结算。

```json
{
  "schema": "ai2apps.ai-defaults/v1",
  "revision": "1",
  "apiDefault": {
    "modelId": "deepseek/deepseek-v4-flash",
    "displayName": "DeepSeek · DeepSeek V4 Flash"
  }
}
```

`revision` 为非空字符串（最长 128 字符），每次修改生成新版本，支持回滚。
`modelId` 是 Cloud 推理接口接受的 provider/model ID，不带 Local 的 cloud/ai2apps/ 前缀。
`displayName` 为非空、无控制字符字符串（最长 256 字符）。
主动停用时返回 200 且 `apiDefault: null`，revision 仍必填；不能用 404 表示停用。
未知字段可添加；不兼容变更必须换 schema 并与客户端协调。

## Cloud 配置与验证

通过 Cloud 项目既有受保护管理配置机制维护单一全局模型选择，持久化且可审计、回滚；
不得要求客户端升级来调整选择。管理入口具体实现由 Cloud 项目负责。
配置写入时校验目录模型存在、启用、可通过 Points 调用，支持文本对话及当前
Agent/浏览器规划使用的工具调用与结构化输出能力；用真实小型请求验收初始模型。
模型禁用或下架时同步切换有效默认值或发布 null。目录改动与默认配置保持一致。
公开配置不代表调用权限，不改变用户等级、余额不足、额度、并发限制及现有扣费规则。

## 已实现的 Local 行为

- 启动加载时拉取配置，最多等待 3 秒，之后每 300 秒刷新；登录前后均可获取。
- 显式 routes 与 Cloud 缓存分开存储；只有空的 work_simple/work_standard/work_complex 继承。
- 使用 `cloud/ai2apps/<modelId>`，确保 Cloud Points 路由；同厂商个人 Key 不拦截该显式路由。
- 缓存绑定 Cloud origin，原子保存，有效期 24 小时；成功读取的新配置立即替换旧配置。
- 404、网络故障、非 200 或非法响应保留有效缓存，超期停止继承；无缓存时保留未配置状态，
  不猜测模型或选择目录第一项。200/null 立即清除继承值。
- Models 页面加载时通过 Local `/v1/platform/cloud/ai/defaults` 读取已缓存策略，
  在 Use API Default 后显示模型名称，保存时仍保留空字符串表示跟随。

## 联调与上线验收

1. 未登录、零配置的新 Local 启动即可读到策略；完成邮箱验证、登录后用 Points 完成标准任务。
2. 三个空槽位均解析到上述 Cloud 模型；非 work 专用槽位不受影响。
3. 手选本地/BYOK/Cloud 后不覆盖；清空后恢复继承。
4. Cloud 改为另一个有效模型后，客户端启动或下次刷新采用新值，不升级客户端。
5. 老 Cloud 404、断网、坏 JSON、缓存过期和 null 停用符合上述行为。
6. 已配置同厂商个人 Key 时，继承的 Cloud 默认仍走 Points；验证权限与余额不足错误不绕过。
7. 发布记录中记录策略 revision、实际模型 ID、部署版本及端到端任务结果。

Cloud 侧完成后交回实际响应和部署信息；当前客户端不能标记为生产端到端已验收。
