# 访客 Open-Entry v1

在已签名 App 的 app.yaml 增加：

```yaml
open_entry:
  kind: sandbox
  resource: public/index.html
  capabilities: []
```

资源必须在独立子目录内、进入签名文件索引。该目录内全部资源视为可公开的 App 代码/素材，勿存放私有用户数据。允许 ui/entry.html 作为现有纯静态游戏入口，但发布前应确认 ui 下所有文件均适合向访客提供。

Owner 必须另行在访客空间添加卡片并发布。仅支持已正式安装的签名 App，源码热挂载/本地未签名/宿主 App/带资源 Patch 的 App 不可发布。发布快照锁定 effective digest；升级、停用或卸载后旧卡片拒绝资源，需要重新发布。

访客页面使用 opaque sandbox（只有 allow-scripts），禁止 connect-src、form-action、宿主 Bridge、同源权限和 Owner 数据挂载。相对静态资源 URL 可以使用；游戏不得要求 localStorage 可用。预览只展示 App 卡片，不在 Owner 身份下执行访客应用。

v1 不向游戏提供访客身份、模型调用或文件能力。若需要这些能力，必须等待独立受限 visitor Bridge 的明确能力合同；不能复用 Mobile Owner Bridge。
