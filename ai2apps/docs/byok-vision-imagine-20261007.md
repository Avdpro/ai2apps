# BYOK 视觉与绘图模型目录修复

## 原因与修改

- 默认模型路由的视觉型号提示仅包含 GPT-4/5，遗漏 GPT-6。提取共享能力归一化，增加 GPT-6，并兼容 capabilities 列表及 image_input 别名；图像生成模型仍不等同于图像识别模型。
- Imagine Studio 以前只加载 AI2Apps Cloud 与本地 Package。现由已认证的本机目录端点返回已配置、启用且使用 OpenAI-compatible 协议的 BYOK 图像模型。返回字段使用白名单，不包含 Key/凭据引用。
- 保留 `cloud/openai/<model>` BYOK ID，生成与编辑进入现有服务器后台执行/结果保存流程，再由 Gateway 直连供应商；不改写为 `cloud/ai2apps/...`。
- 移除目录失败时虚构的 Cloud 默认模型，脱机也能从独立本机目录取得 BYOK。现有缓存模型不要求重新输入 Key 或同步。

## 验证

- Python 共 67 passed（图像相关 31、模型管理 36），涵盖新视觉识别、两款 Image 2.5 目录和模拟生成、现有图像目录/历史/网关。
- 另有 1 项既有移动端模板检查失败：`test_imagine_studio_uses_studio_shell_with_builtin_mini_apps` 要求模板含 `is-mobile-nav`，该模板本轮未修改。
- 新增 Node 目录测试覆盖 Cloud 403 下 BYOK 可选、ID/选择保留、后台执行路由和空目录不补虚假 Cloud；现有 11 个 Imagine Node 脚本全部通过。
- 真实收费生成未执行；API 请求通过模拟供应商验证。Test 原生 UI 已验证图像识别下拉包含 GPT-6.1 Sol、GPT-6 Luna、GPT-6 Astra；绘图下拉包含 GPT Image 2.5 Sunburst、Sunburst 2026-09-08、Flare。BYOK Key 未读取/修改；默认路由未代为设置。另修正 BYOK 提示与上传确认，明确直连所选供应商。

能力依据：[OpenAI Images and vision](https://developers.openai.com/api/docs/guides/images-vision)、[Images API](https://developers.openai.com/api/reference/resources/images/methods/generate)。没有修改 Cloud 后端。

最终固定 Test 已重建、严格签名与打包验证通过，嵌入 JS 与源码一致；当前原生界面显示 BYOK Sunburst 和“使用你的 API Key 直连供应商”提示，保留用户数据。
