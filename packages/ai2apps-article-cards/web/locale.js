(() => {
  'use strict';
  const english = {
  "文章卡片": "Article Cards",
  "文章与模板": "Article and template",
  "文章正文": "Article text",
  "粘贴文章，保留原来的段落和空行": "Paste the article, including paragraph breaks",
  "画幅": "Aspect ratio",
  "自动分页": "Paginate",
  "封面设置": "Cover settings",
  "封面": "Cover",
  "不加封面": "No cover",
  "模板大标题": "Template title",
  "AI 生成封面": "AI cover",
  "封面标题": "Cover title",
  "输入要在封面上显示的标题": "Enter a title for the cover",
  "画面风格": "Visual style",
  "例如：暖色手账、留白、纸张纹理": "For example, warm colors, whitespace, paper texture",
  "参考图片（可选）": "Reference images (optional)",
  "生图模型": "Image model",
  "生成 AI 封面": "Generate AI cover",
  "取消生成": "Cancel generation",
  "查询生成结果": "Check generation status",
  "图片模板": "Card template",
  "编辑模板": "Edit template",
  "底色": "Background color",
  "边框色": "Border color",
  "文字色": "Text color",
  "字号": "Font size",
  "文字区左边距 (%)": "Left text margin (%)",
  "文字区右边距 (%)": "Right text margin (%)",
  "文字区上边距 (%)": "Top text margin (%)",
  "文字区下边距 (%)": "Bottom text margin (%)",
  "贴纸 X (%)": "Sticker X (%)",
  "贴纸 Y (%)": "Sticker Y (%)",
  "页码 X (%)": "Page number X (%)",
  "页码 Y (%)": "Page number Y (%)",
  "显示页码": "Show page numbers",
  "显示贴纸": "Show stickers",
  "底图排版": "Background layout",
  "整页底图（适合固定画幅）": "Full-page background (fixed aspect ratio)",
  "九宫格底图（适合跨画幅）": "Nine-slice background (multiple aspect ratios)",
  "AI 生成底图": "AI background",
  "画面风格（可选）": "Visual style (optional)",
  "留空沿用当前模板配色": "Leave blank to use the current template colors",
  "生成并预览": "Generate preview",
  "恢复上一张底图": "Restore previous background",
  "上传底图（PNG / JPEG / WebP）": "Upload background (PNG / JPEG / WebP)",
  "左切片 (%)": "Left slice (%)",
  "右切片 (%)": "Right slice (%)",
  "上切片 (%)": "Top slice (%)",
  "下切片 (%)": "Bottom slice (%)",
  "边框宽度 (%)": "Border width (%)",
  "预览辅助线": "Show guides",
  "恢复纯色底图": "Reset to solid background",
  "模板名称": "Template name",
  "给模板起个名字": "Enter a template name",
  "保存模板": "Save template",
  "分页预览和编辑": "Page preview and editing",
  "上一页": "Previous page",
  "页面": "Page",
  "选择页面": "Select page",
  "下一页": "Next page",
  "文章卡片预览": "Article card preview",
  "本页正文": "Text on this page",
  "本页贴纸": "Sticker on this page",
  "在正文光标处拆页": "Split at the text cursor",
  "在光标处拆页": "Split at cursor",
  "与下一页合并": "Merge with next page",
  "导出当前页 PNG": "Export current page as PNG",
  "导出整篇 ZIP": "Export all pages as ZIP",
  "请在 Doc Studio 或 Imagine Studio 中打开「文章卡片」。": "Open Article Cards in Doc Studio or Imagine Studio.",
  "导出等待超时。请先检查 Studio 输出区。": "Export timed out. Check the Studio output panel.",
  "Studio 请求超时，请检查状态后再试。": "Studio request timed out. Check its status before retrying.",
  "封面标题超出文字区。请缩短标题或扩大文字区。": "The cover title does not fit. Shorten it or enlarge the text area.",
  "填写封面标题。使用 AI 封面时，请先生成画面。": "Enter a cover title. For an AI cover, generate the image first.",
  "封面会放在图片包的第一张，正文页码从 01 开始。": "The cover comes first. Body pages are numbered from 01.",
  "原文已修改。请重新分页后再导出。": "The article changed. Paginate again before exporting.",
  "无法读取已保存的底图。": "Could not load the saved background.",
  "请先输入文章。": "Enter an article first.",
  "重新分页会用原文替换逐页编辑。继续吗？": "Repaginating replaces page edits with the article text. Continue?",
  "含封面的图片包最多 30 张。请缩短正文或调整字号。": "A bundle can contain up to 30 images, including the cover. Shorten the article or adjust the font size.",
  "生成的底图超过 12 MiB 或格式不受支持。": "The generated background exceeds 12 MiB or has an unsupported format.",
  "请上传 12 MiB 以内的 PNG、JPEG 或 WebP。": "Upload a PNG, JPEG, or WebP under 12 MiB.",
  "底图宽高至少需要 32 像素。": "The background must be at least 32 pixels wide and high.",
  "底图纹理较复杂，请缩小图片或压缩后重试。": "Reduce the background size or compress it and try again.",
  "无法读取保存的模板库。": "Could not load saved templates.",
  "请填写模板名称。": "Enter a template name.",
  "图片包超过 8 MiB。请简化底图或分批处理文章。": "The bundle exceeds 8 MiB. Simplify the background or split the article.",
  "Studio 未返回成品，请检查 Output。": "Check the Studio output panel for the export.",
  "已在当前 Studio 的输出区生成当前页 PNG。": "The current page PNG is in Studio Output.",
  "暂无支持此底图尺寸的已配置生图模型。": "No configured image model supports this size.",
  "参考图会发送给所选模型。生成后仍可编辑标题。": "Reference images go to the selected model. The title remains editable.",
  "生成正方形底图，四角保留装饰，边缘可拉伸。": "Generate a square background with decorated corners and stretchable edges.",
  "底图": "Background",
  "生图任务没有返回图片。": "The generation task returned no image.",
  "封面已生成。可以修改标题，预览后再导出。": "Cover ready. Edit the title and preview before exporting.",
  "底图已套用。满意后可保存模板。": "Background applied. Save the template to keep it.",
  "模板已切换，底图未覆盖。": "The template changed, so its background was preserved.",
  "模板或底图已更改，生成结果未覆盖当前底图。": "The template or background changed. The current background was preserved.",
  "已取消生成。": "Generation canceled.",
  "文章模板底图": "Article template background",
  "请填写标题，并选择可用的生图模型。": "Enter a title and select an available image model.",
  "请选择可用的生图模型。": "Select an available image model.",
  "参考图须为 20 MiB 以内的 PNG、JPEG 或 WebP。": "Reference images must be PNG, JPEG, or WebP under 20 MiB.",
  "正在准备参考图…": "Preparing reference images…",
  "正在提交生图任务…": "Submitting image generation…",
  "已恢复上一张底图。": "Previous background restored.",
  "已请求取消生成。": "Cancellation requested.",
  "未找到已受理的生成任务，可以重新生成。": "No accepted generation task was found. You can try again.",
  "请把光标放在两段正文之间。": "Place the cursor between two passages.",
  "文章卡片有改动或正在处理。": "Article Cards changed or is busy.",
  "文章卡片设置无效。": "Invalid Article Cards settings.",
  "无贴纸": "No sticker",
  "奶油手账": "Cream notebook",
  "鼠尾草": "Sage",
  "夜读": "Night reading"
};
  const originals = new WeakMap();
  let zh = true;
  const t = (text, alternative = english[text] || text) => zh ? text : alternative;
  function setLocale(locale) {
    zh = /^zh/i.test(locale || '');
    document.documentElement.lang = zh ? 'zh-CN' : 'en';
    const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        return node.parentElement?.closest('script, style, textarea, [role="status"]') ?
          NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      }
    });
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const original = originals.get(node) || node.nodeValue;
      const key = original.trim();
      if (!Object.hasOwn(english, key)) continue;
      originals.set(node, original);
      node.nodeValue = original.replace(key, t(key));
    }
    for (const element of document.querySelectorAll('[aria-label], [placeholder], [title]')) {
      const values = originals.get(element) || {};
      for (const attribute of ['aria-label', 'placeholder', 'title']) {
        const original = values[attribute] || element.getAttribute(attribute);
        if (!Object.hasOwn(english, original)) continue;
        values[attribute] = original;
        element.setAttribute(attribute, t(original));
      }
      originals.set(element, values);
    }
  }
  window.ArticleCardsLocale = {t, setLocale};
  setLocale(new URLSearchParams(location.search).get('locale') || navigator.language || 'en');
})();
