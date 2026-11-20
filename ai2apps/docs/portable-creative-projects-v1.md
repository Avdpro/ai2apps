# 创作数据 ZIP 迁移 v1

短漫工坊 0.1.2 支持导出选中系列或全部系列、导入 ZIP。内置角色设计支持导出选中角色（全部形象）、当前单个形象，以及导入角色 ZIP。这些迁移 ZIP 与供 App/Bot 引用的一张定义图加说明的 `.character.json` 用途不同，后者保持原样。

## 包内数据

通用外层为 `ai2apps.portable-project/v1`：`manifest.json` 包含 owner 文档及图片索引，`images/<sha256>` 保存 PNG/JPEG/WebP 原始字节。相同图片只存一份，图片逐一验证大小、格式、尺寸、SHA-256。禁止任意路径、链接、加密、重复条目和清单外文件，不解压至任意文件路径。上限为512 MiB、2000条图片引用、每张20 MiB、元数据8 MiB。

系列文档 `ai2apps.comic-series-backup/v1` 包含系列设定、该系列角色定义图与说明快照、所有已保存分集的脚本和画格、当前草稿。成品可从已有画格重新排版，无需重绘。它不复制共享角色库中未用于该系列的其它形象，不移植源设备 Run/Job 身份。

角色文档 `ai2apps.character-backup/v1` 包含当前身份与别名、各形象设定、各自参考图、定义图、说明和未删除的生成图片；不迁移本机修改历史、删除墓碑或原 Run/Job 身份。导出单个形象时只带这一个形象及其图片。

## 导入行为

先检查全部文件，再预览名称、数量及图片缩略图，用户确认后创建独立副本。同名自动追加数字，不覆盖已有对象。重新分配系列/角色/形象/分集身份并映射图片引用；原设备的访问权限、文件地址和调度不会生效。保留绘图模型 ID，但不自动替换不可用模型。源定时任务不导入，新系列为手动模式。

角色由 Gallery owner 执行检查、素材导入和新角色创建；失败回收本次新建图片，不删除已有去重图片。Package 私有图片按内容寻址，草稿在最终 CAS 保存成功前不会出现半个系列；未绑定的私有去重缓存不会成为 Gallery 用户素材。

## 所有权及交付

Host `image-workflow.archive.export/inspect/import` 只负责有界 JSON/图片 ZIP 传输，并复用现有 live mount、声明和 actor/installation/provider 范围校验。系列语义、选择对象和引用重映射由 Package 的 `web/backup.js` 实现。新接口不增加 AaAT 入口或改变 Bot 结算。

角色设计仍为系统内置 Mini-App（用户已确认），随未来 Desktop 发布；不新增第二个同名 Package 或入口。短漫工坊 Package 已单独发布0.1.2，但 ZIP 功能需要本次新增的 Desktop Host archive bridge。Dev/App-Dev 已加载当前源码，旧生产 Desktop 仅升级 Package 不能获得新宿主接口。
