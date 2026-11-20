# Sticker Workshop / 表情包工坊

上传一张清晰的照片或角色设定图，选择 24 种表情或状态之一，再设置半身或全身、正面或朝画面左／右。可以另选视觉风格。快捷整组按开心、比心、震惊、委屈依次生成四张，沿用同一参考图和构图。Cloud 按张计费。停止整组后，已完成的图仍在右侧输出。

展开「角色表情包」，用当前参考图、角色名和可选的设定创建表情包。创建时可再加三张照片或设定图。选择已有表情包后，可加载主参考图，也可把右侧选中的贴纸加入包中。表情包会出现在 Gallery 的「表情包」分类。

在拥有表情包工坊权限的 Bot 中，可以说「给这张海报加一张马斯克晕眩的贴纸」。Bot 会先查已有的角色贴纸，匹配时可将原图用于下游创作。缺图时，可以按现有角色参考图补绘并存回原包。绘制需要支持参考图编辑的模型。

Upload a photo or character sheet, choose from 24 expressions, and set framing and facing. The four-sticker shortcut draws Happy, Heart gesture, Shocked and Pleading with the same reference and composition. Cloud charges per image.

Open Character sticker packs to save a name, a description and up to four references. Select a pack to load its primary reference or add the selected Output sticker. A Bot with Sticker Workshop access can reuse a matching sticker or draw a missing variant and save it to the pack.

The standard sticker prompt requests a white background. Identity consistency depends on the selected image model.

背景可选择白底（默认）或透明。透明贴纸需要模型明确支持原生透明背景，使用 PNG 或 WebP；返回图片会检查真实透明通道。角色表情包中的白底和透明版本分别保存、匹配。Bot 可通过 `sticker.lookup` 和 `sticker.generate` 的 `background=transparent` 请求透明贴纸。模型不支持时会提示，不自动更换模型。
