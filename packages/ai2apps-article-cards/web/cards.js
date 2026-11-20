'use strict';

(() => {
  const cards = window.ArticleCards;
  const {t, setLocale} = window.ArticleCardsLocale;
  const $ = id => document.getElementById(id);
  const preview = $('preview');
  const miniApp = 'ai2apps.imagine.article-cards';
  const schema = 'ai2apps.mini-app-draft/v1';
  const maxExportBytes = 8 * 1024 * 1024;
  const maxBackgroundBytes = 650000;
  const maxTemplates = 5;
  const sizes = {'3:4': [960, 1280], '9:16': [720, 1280]};
  const fields = ['paper', 'border', 'ink', 'font', 'left', 'right', 'top', 'bottom',
    'stickerX', 'stickerY', 'numberX', 'numberY', 'number', 'stickers',
    'sliceLeft', 'sliceRight', 'sliceTop', 'sliceBottom', 'frame'];
  const library = Object.entries(cards.themes).map(([id]) => ({id, ...cards.defaults(id)}));
  let template = {...library[0]};
  let custom = [];
  let pages = [];
  let selected = 0;
  let generatedFrom = '';
  let pageEdited = false;
  let busy = false;
  let loadingBackground = false;
  let background = null;
  let backgroundVersion = 0;
  let coverImage = null;
  let imageModels = null;
  let imageJob = null;
  let generatingImage = false;
  let previousBackground = null;

  const hasCover = () => $('cover-mode').value !== 'none';
  const cover = () => ({
    title: $('cover-title').value,
    image: $('cover-mode').value === 'ai' ? coverImage : null,
  });

  function status(message, error = false) {
    $('status').textContent = message;
    $('status').classList.toggle('error', error);
  }

  let studioOrigin;
  const connection = new Promise((resolve, reject) => {
    function receive(event) {
      if (event.source !== parent || event.data?.type !== 'ai2apps:studio-connected'
          || event.data.version !== 1 || !event.ports[0]) return;
      clearTimeout(timer);
      window.removeEventListener('message', receive);
      const port = event.ports[0];
      studioOrigin = event.origin;
      function updateLocale(locale) {
        setLocale(locale);
        refreshTemplates();
        syncPages();
        $('sticker').options[0].textContent = t('无贴纸');
      }
      if (event.data.locale) updateLocale(event.data.locale);
      port.addEventListener('message', ({data}) => {
        if (data?.type === 'ai2apps:studio-locale') updateLocale(data.locale);
      });
      port.start();
      resolve(port);
    }
    const timer = setTimeout(() => {
      window.removeEventListener('message', receive);
      reject(Error(t("请在 Doc Studio 或 Imagine Studio 中打开「文章卡片」。")));
    }, 8000);
    window.addEventListener('message', receive);
    window.addEventListener('load', () => setTimeout(() => {
      parent.postMessage({type: 'ai2apps:studio-connect', version: 1}, '*');
    }, 0), {once: true});
  });

  let stateRevision = 0;
  for (const type of ['input', 'change']) document.addEventListener(type, () => { stateRevision++; });
  window.addEventListener('message', async event => {
    const data = event.data;
    if (event.source !== parent || event.origin !== studioOrigin ||
        data?.type !== 'ai2apps:article-cards-state/v1' || !event.ports[0]) return;
    const port = event.ports[0];
    try {
      if (data.action === 'apply') {
        if (busy || loadingBackground || generatingImage || data.revision !== stateRevision)
          throw Error(t('文章卡片有改动或正在处理。'));
        const values = data.values;
        if (!values || Object.keys(values).some(key => !['article', 'ratio', 'theme'].includes(key)) ||
            ('article' in values && (typeof values.article !== 'string' || values.article.length > 30000)) ||
            ('ratio' in values && !Object.hasOwn(sizes, values.ratio)) ||
            ('theme' in values && !Object.hasOwn(cards.themes, values.theme))) throw Error(t('文章卡片设置无效。'));
        if ('article' in values) $('article').value = values.article;
        if ('ratio' in values) $('ratio').value = values.ratio;
        if ('theme' in values && template.id !== values.theme) {
          $('template').value = values.theme;
          await selectTemplate(values.theme);
        }
        stateRevision++;
        draw();
      } else if (data.action !== 'read') throw Error('Unknown editor action');
      const theme = Object.hasOwn(cards.themes, template.id) ? template.id : null;
      const ratio = $('ratio').value;
      port.postMessage({state:{revision:stateRevision, settings:theme ? {ratio, theme} : null,
        draft:{article:$('article').value, ratio, theme, pageCount:pages.length}}});
    } catch (error) { port.postMessage({error:error.message}); }
    finally { port.close(); }
  });

  let requestId = 0;
  let requestQueue = Promise.resolve();
  function request(operation, fields, timeout = 10000) {
    const result = requestQueue.then(() => send(operation, fields, timeout));
    requestQueue = result.catch(() => {});
    return result;
  }
  async function send(operation, fields, timeout) {
    const port = await connection;
    return new Promise((resolve, reject) => {
      const id = ++requestId;
      function receive(event) {
        if (event.data?.id !== id) return;
        clearTimeout(timer);
        port.removeEventListener('message', receive);
        if (event.data.error) reject(Error(event.data.error));
        else resolve(event.data.value);
      }
      const timer = setTimeout(() => {
        port.removeEventListener('message', receive);
        reject(Error(operation === 'invoke' ? t("导出等待超时。请先检查 Studio 输出区。") : t("Studio 请求超时，请检查状态后再试。")));
      }, timeout);
      port.addEventListener('message', receive);
      port.start();
      port.postMessage({id, operation, ...fields});
    });
  }

  function decodeImage(src) {
    const image = new Image();
    image.src = src;
    return image.decode().then(() => image);
  }

  function refreshTemplates() {
    $('template').replaceChildren(...[...library, ...custom].map(item => new Option(library.some(theme => theme.id === item.id) ? t(item.name) : item.name, item.id)));
    $('template').value = template.id;
    $('save').disabled = busy || loadingBackground;
  }

  function fillTemplateFields() {
    for (const name of fields) {
      const input = $(name);
      if (input.type === 'checkbox') input.checked = template[name];
      else input.value = template[name];
    }
    $('background-mode').value = template.backgroundMode || 'slice';
    $('name').value = library.some(item => item.id === template.id) ? '' : template.name;
  }

  function syncPages() {
    const options = pages.map((_, index) => new Option(t(`第 ${index + 1} 页`, `Page ${index + 1}`), index));
    if (hasCover()) options.unshift(new Option(t("封面"), -1));
    $('page').replaceChildren(...options);
    $('page').value = String(selected);
    $('edit').hidden = selected < 0 || !pages.length;
    $('page-text').value = pages[selected]?.text || '';
    $('sticker').value = pages[selected]?.sticker || '';
    draw();
  }

  function draw() {
    const [width, height] = sizes[$('ratio').value];
    if (preview.width !== width || preview.height !== height) {
      preview.width = width;
      preview.height = height;
    }
    const page = pages[selected];
    const onCover = selected === -1;
    const currentCover = cover();
    const overflow = onCover
      ? cards.renderCover(preview, template, background, currentCover, $('guides').checked)
      : cards.render(preview, template, background, page, selected, pages.length, $('guides').checked);
    const coverReady = Boolean(currentCover.title.trim() && ($('cover-mode').value !== 'ai' || currentCover.image));
    const stale = $('article').value !== generatedFrom;
    $('prev').disabled = busy || selected <= (hasCover() ? -1 : 0);
    $('next').disabled = busy || selected >= pages.length - 1;
    $('page').disabled = busy || (!pages.length && !hasCover());
    $('merge').disabled = busy || onCover || selected >= pages.length - 1;
    $('split').disabled = busy || !page || pages.length + Number(hasCover()) >= cards.maxPages;
    $('png').disabled = busy || loadingBackground || Boolean(overflow)
      || (onCover ? !coverReady : !page?.text.trim() || stale);
    $('zip').disabled = busy || loadingBackground || !pages.length || stale || (hasCover() && !coverReady);
    $('cover-options').hidden = !hasCover();
    $('cover-ai').hidden = $('cover-mode').value !== 'ai';
    $('paginate').disabled = busy;
    $('save').disabled = busy || loadingBackground;
    $('slice-fields').hidden = template.backgroundMode === 'fixed';
    $('background-undo').hidden = !previousBackground;
    for (const kind of ['cover', 'background']) {
      $(kind + '-generate').disabled = busy || generatingImage || Boolean(imageJob)
        || !$(kind + '-model').value || (kind === 'background' && loadingBackground);
      $(kind + '-cancel').hidden = imageJob?.kind !== kind || !imageJob.id;
      $(kind + '-recover').hidden = generatingImage || imageJob?.kind !== kind;
    }
    if (!busy && onCover && overflow) status(t("封面标题超出文字区。请缩短标题或扩大文字区。"), true);
    else if (!busy && onCover && !coverReady) status(t("填写封面标题。使用 AI 封面时，请先生成画面。"));
    else if (!busy && onCover) status(t("封面会放在图片包的第一张，正文页码从 01 开始。"));
    else if (!busy && stale && pages.length) status(t("原文已修改。请重新分页后再导出。"));
    else if (!busy && page && overflow) status(t(`本页多出 ${overflow} 行。可拆页、缩小字号或扩大文字区。`, `This page overflows by ${overflow} lines. Split the page, reduce the font size, or enlarge the text area.`), true);
    else if (!busy && page) status(t(`共 ${pages.length} 页。可逐页修改正文与贴纸，再导出。`, `${pages.length} pages. Edit text and stickers before exporting.`));
    else if (!busy) status('');
  }

  async function selectTemplate(id) {
    const item = [...library, ...custom].find(row => row.id === id);
    if (!item) return;
    const version = ++backgroundVersion;
    template = {...item, backgroundMode: item.backgroundMode || 'slice'};
    previousBackground = null;
    background = null;
    loadingBackground = Boolean(template.background);
    fillTemplateFields();
    draw();
    if (!loadingBackground) return;
    try {
      const image = await decodeImage(template.background);
      if (version === backgroundVersion) background = image;
    } catch {
      if (version === backgroundVersion) {
        template.background = '';
        status(t("无法读取已保存的底图。"), true);
      }
    } finally {
      if (version === backgroundVersion) {
        loadingBackground = false;
        draw();
      }
    }
  }

  function updateFields(event) {
    const input = event.target;
    if (input.type === 'number') {
      if (!input.value || !input.validity.valid) return;
      template[input.id] = Number(input.value);
    } else {
      template[input.id] = input.type === 'checkbox' ? input.checked : input.value;
    }
    draw();
  }

  function paginate() {
    const text = $('article').value;
    if (!text.trim()) return status(t("请先输入文章。"), true);
    if (pageEdited && !window.confirm(t("重新分页会用原文替换逐页编辑。继续吗？"))) return;
    try {
      const next = cards.paginate(preview.getContext('2d'), text, template, ...sizes[$('ratio').value]);
      if (next.length + Number(hasCover()) > cards.maxPages) throw Error(t("含封面的图片包最多 30 张。请缩短正文或调整字号。"));
      pages = next;
      generatedFrom = text;
      pageEdited = false;
      selected = hasCover() ? -1 : 0;
      syncPages();
    } catch (error) {
      const limit = /^排版超过 (\d+) 页。/.exec(error.message);
      status(limit ? t(error.message, `Layout exceeds ${limit[1]} pages. Reduce the font size, enlarge the text area, or shorten the article.`) : error.message, true);
    }
  }

  async function uploadBackground(file, generated) {
    if (!file) return;
    if (file.size > 12 * 1024 * 1024 || !['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      if (generated) throw Error(t("生成的底图超过 12 MiB 或格式不受支持。"));
      status(t("请上传 12 MiB 以内的 PNG、JPEG 或 WebP。"), true);
      return;
    }
    const prior = {image: background, data: template.background, mode: template.backgroundMode,
      slices: Object.fromEntries(['sliceLeft', 'sliceRight', 'sliceTop', 'sliceBottom'].map(name => [name, template[name]]))};
    const version = ++backgroundVersion;
    loadingBackground = true;
    draw();
    const url = URL.createObjectURL(file);
    let message = '';
    try {
      const source = await decodeImage(url);
      if (Math.min(source.naturalWidth, source.naturalHeight) < 32) throw Error(t("底图宽高至少需要 32 像素。"));
      const canvas = document.createElement('canvas');
      const scale = Math.min(1, 1200 / Math.max(source.naturalWidth, source.naturalHeight));
      canvas.width = Math.max(32, Math.round(source.naturalWidth * scale));
      canvas.height = Math.max(32, Math.round(source.naturalHeight * scale));
      canvas.getContext('2d').drawImage(source, 0, 0, canvas.width, canvas.height);
      const encoded = canvas.toDataURL('image/webp', .86);
      if (encoded.length > maxBackgroundBytes) throw Error(t("底图纹理较复杂，请缩小图片或压缩后重试。"));
      const image = await decodeImage(encoded);
      if (version !== backgroundVersion) return;
      background = image;
      template.background = encoded;
      previousBackground = generated ? prior : null;
      if (generated?.mode === 'slice') {
        for (const name of ['sliceLeft', 'sliceRight', 'sliceTop', 'sliceBottom']) {
          template[name] = 25;
          $(name).value = 25;
        }
      }
      $('guides').checked = true;
      return true;
    } catch (error) {
      message = error.message;
      if (generated) throw error;
    } finally {
      URL.revokeObjectURL(url);
      if (version === backgroundVersion) {
        loadingBackground = false;
        draw();
        if (message) status(message, true);
      }
    }
  }

  function validTemplate(item) {
    if (!item || !/^custom-\d+$/.test(item.id) || typeof item.name !== 'string' || !item.name || item.name.length > 32
        || typeof item.background !== 'string' || item.background.length > maxBackgroundBytes
        || (item.background && !/^data:image\/(png|webp);base64,[a-z0-9+/=]+$/i.test(item.background))) return false;
    if (item.backgroundMode !== undefined && !['fixed', 'slice'].includes(item.backgroundMode)) return false;
    return fields.every(name => {
      const input = $(name);
      if (input.type === 'checkbox') return typeof item[name] === 'boolean';
      if (input.type === 'color') return /^#[\da-f]{6}$/i.test(item[name]);
      return Number.isInteger(item[name]) && item[name] >= Number(input.min) && item[name] <= Number(input.max);
    });
  }

  let libraryReady;
  async function loadTemplates() {
    const raw = await request('draft.get', {});
    if (raw === null) return;
    const draft = JSON.parse(raw);
    if (draft?.schema !== schema || draft.miniApp !== miniApp || !Array.isArray(draft.templates)) {
      throw Error(t("无法读取保存的模板库。"));
    }
    custom = draft.templates.filter(validTemplate).slice(0, maxTemplates);
    refreshTemplates();
  }

  async function saveTemplate() {
    const name = $('name').value.trim();
    if (!name) return status(t("请填写模板名称。"), true);
    const current = template;
    const snapshot = {...current};
    busy = true;
    draw();
    try {
      await libraryReady;
      const existing = custom.find(item => item.name === name);
      if (!existing && custom.length >= maxTemplates) throw Error(t(`最多保存 ${maxTemplates} 个模板。可用已有名称更新模板。`, `Save up to ${maxTemplates} templates. Reuse an existing name to update it.`));
      const saved = {...snapshot, name, id: existing?.id || `custom-${Date.now()}`};
      const next = [...custom.filter(item => item.id !== saved.id), saved];
      await request('draft.set', {value: JSON.stringify({schema, miniApp, templates: next})});
      custom = next;
      if (template === current) template = {...current, id: saved.id, name};
      refreshTemplates();
      busy = false;
      draw();
      status(t(`已保存模板「${name}」。`, `Saved template “${name}”.`));
    } catch (error) {
      busy = false;
      draw();
      status(error.message, true);
    }
  }

  async function publish(format) {
    const current = selected;
    const output = format === 'png' ? [current] : [
      ...(hasCover() ? [-1] : []), ...pages.map((_, index) => index),
    ];
    const snapshots = pages.map(page => ({...page}));
    const front = cover();
    const total = pages.length;
    const snapshot = {...template};
    const backdrop = background;
    const canvas = document.createElement('canvas');
    [canvas.width, canvas.height] = sizes[$('ratio').value];
    busy = true;
    draw();
    try {
      const frames = [];
      let encodedBytes = 64;
      if (output.length > cards.maxPages) throw Error(t("含封面的图片包最多 30 张。请缩短正文或调整字号。"));
      for (const pageIndex of output) {
        const isCover = pageIndex === -1;
        const label = isCover ? t("封面") : t(`第 ${pageIndex + 1} 页`, `Page ${pageIndex + 1}`);
        const page = snapshots[pageIndex];
        status(t(`正在生成${label}…`, `Generating ${label}…`));
        if (!isCover && !page?.text.trim()) throw Error(t(`${label}没有正文。`, `${label} has no text.`));
        const overflow = isCover ? cards.renderCover(canvas, snapshot, backdrop, front)
          : cards.render(canvas, snapshot, backdrop, page, pageIndex, total);
        if (overflow) throw Error(t(`${label}文字超出排版区域，请修改后再导出。`, `Text on ${label} does not fit. Edit it before exporting.`));
        const data = canvas.toDataURL('image/png').slice('data:image/png;base64,'.length);
        encodedBytes += data.length + 3;
        if (encodedBytes > maxExportBytes) throw Error(t("图片包超过 8 MiB。请简化底图或分批处理文章。"));
        frames.push(data);
        await new Promise(resolve => setTimeout(resolve, 0));
      }
      const file = new File([JSON.stringify({format, seconds: 1, frames})], 'article-pages.json', {type: 'application/json'});
      const result = await request('invoke', {capability: 'media.visual_sequence.export', fields: [['file', file]]}, 120000);
      if (!result?.headers?.['x-ai2apps-download-url']) {
        const detail = result?.body instanceof Blob ? await result.body.text() : result?.body;
        const response = typeof detail === 'string' ? JSON.parse(detail || '{}') : detail;
        throw Error(response?.detail || t("Studio 未返回成品，请检查 Output。"));
      }
      busy = false;
      draw();
      status(format === 'zip' ? t(`已在当前 Studio 的输出区生成 ${output.length} 张 PNG 图片包。`, `A ZIP of ${output.length} PNGs is in Studio Output.`) : t("已在当前 Studio 的输出区生成当前页 PNG。"));
    } catch (error) {
      busy = false;
      draw();
      status(error.message, true);
    }
  }

  function modelSize(model, kind) {
    const square = kind === 'background' && template.backgroundMode === 'slice';
    const [width, height] = square ? [1024, 1024] : sizes[$('ratio').value];
    const limits = model.size || {};
    const candidates = limits.mode === 'fixed' ? limits.presets || [] : [
      `${width}x${height}`, '768x1024', '576x1024', '832x1216', '1024x1536', '1024x1024', '768x768', '512x512', '1536x1536',
    ];
    return candidates.filter(value => {
      if (!/^\d+x\d+$/.test(value)) return false;
      const [w, h] = value.split('x').map(Number);
      if (square && w !== h) return false;
      if (Math.min(w, h) < 256 || Math.max(w, h) > 2048) return false;
      if (limits.mode === 'fixed') return true;
      const fits = (n, axis) => n >= (axis?.min || 1) && n <= (axis?.max || 2048) && n % (axis?.multipleOf || 1) === 0;
      return fits(w, limits.width) && fits(h, limits.height)
        && w * h >= (limits.minPixels || 1) && w * h <= (limits.maxPixels || 4194304)
        && Math.max(w / h, h / w) <= (limits.maxAspectRatio || Infinity);
    }).sort((a, b) => {
      const distance = value => {
        const [w, h] = value.split('x').map(Number);
        return Math.abs(Math.log((w / h) / (width / height)));
      };
      return distance(a) - distance(b);
    })[0];
  }

  const imageStatus = (kind, text) => { $(kind + '-status').textContent = text; };

  async function loadImageModels(kind) {
    const select = $(kind + '-model');
    try {
      if (!imageModels) {
        const result = await request('image-workflow.models', {});
        imageModels = (result.items || []).filter(model => model.ready && model.formats?.includes('png') && model.qualities?.length);
      }
      const selectedModel = select.value;
      const options = imageModels.filter(model => modelSize(model, kind));
      select.replaceChildren(...options.map(model => new Option(model.label, model.id)));
      const preferred = selectedModel || $(kind === 'cover' ? 'background-model' : 'cover-model').value;
      if (options.some(item => item.id === preferred)) select.value = preferred;
      if (!options.length) imageStatus(kind, t("暂无支持此底图尺寸的已配置生图模型。"));
      else if (!imageJob && kind === 'cover' && !coverImage)
        imageStatus(kind, t("参考图会发送给所选模型。生成后仍可编辑标题。"));
      else if (!imageJob && kind === 'background' && !previousBackground)
        imageStatus(kind, template.backgroundMode === 'slice'
          ? t("生成正方形底图，四角保留装饰，边缘可拉伸。")
          : t(`按当前 ${$('ratio').value} 画幅生成，必要时居中裁切。`, `Generate at ${$('ratio').value} and center-crop if needed.`));
    } catch (error) { imageStatus(kind, error.message); }
    draw();
  }

  async function readImageJob(job) {
    const task = imageJob;
    const {kind} = task;
    const label = kind === 'cover' ? t("封面") : t("底图");
    task.id = job.id;
    draw();
    for (let attempt = 0; attempt < 150; attempt++) {
      if (job.status === 'succeeded') {
        const assetId = job.result?.assetIds?.[0];
        if (!assetId) throw Error(t("生图任务没有返回图片。"));
        const blob = await request('image-workflow.read', {assetId}, 30000);
        if (kind === 'cover') {
          const url = URL.createObjectURL(blob);
          try { coverImage = await decodeImage(url); }
          finally { URL.revokeObjectURL(url); }
          imageStatus(kind, t("封面已生成。可以修改标题，预览后再导出。"));
        } else if (task.version === backgroundVersion && task.mode === template.backgroundMode) {
          const applied = await uploadBackground(blob, task);
          imageStatus(kind, applied ? t("底图已套用。满意后可保存模板。") : t("模板已切换，底图未覆盖。"));
        } else {
          imageStatus(kind, t("模板或底图已更改，生成结果未覆盖当前底图。"));
        }
        imageJob = null;
        return;
      }
      if (['failed', 'cancelled', 'interrupted', 'publish_failed'].includes(job.status)) {
        imageJob = null;
        throw Error(job.error?.message || (job.status === 'cancelled' ? t("已取消生成。") : t(`${label}生成未完成。`, `${label} generation did not finish.`)));
      }
      imageStatus(kind, job.status === 'queued' ? t(`${label}已排队…`, `${label} is queued…`) : t(`正在生成${label}…`, `Generating ${label}…`));
      await new Promise(resolve => setTimeout(resolve, 2000));
      job = await request('image-workflow.status', {jobId: job.id});
    }
    throw Error(t(`${label}仍在生成，可以稍后查询结果。`, `${label} is still generating. Check again later.`));
  }

  function imagePrompt(kind, title, style, mode) {
    if (kind === 'cover') return `为文章《${title}》绘制竖版封面背景。风格：${style || '简洁的杂志封面，柔和色彩'}。
把视觉主体安排在边缘或上下方，中央留出大片低对比度留白，便于后期排印标题。
参考图用于构图、配色或材质。图片中不要出现标题、文字、标志或水印。`;
    const colors = `底色 ${template.paper}，边框色 ${template.border}。`;
    const composition = mode === 'slice'
      ? '正方形九宫格可拉伸边框。四周各 25% 为边框区，四角装饰完全落在角区内。上下边的中段沿水平方向保持连续均匀，左右边的中段沿垂直方向保持连续均匀，避免在这些边段放置具体图案。中央区域为纯净均匀的底色。不要画出九宫格线。'
      : `用于 ${$('ratio').value} 竖版文章卡片的整页底图。只在边缘或角落放少量装饰，中央至少 75% 的区域保持浅淡、均匀、低纹理，便于大段正文排版。`;
    return `${composition} ${colors} 风格：${style || '简洁手账，细边框，少量点缀'}。
输出平面底图，不要添加任何文字、数字、占位符、水印、投影或展示样机。`;
  }

  async function generateImage(kind) {
    if (imageJob || generatingImage) return;
    const title = kind === 'cover' ? $('cover-title').value.trim() : t("文章模板底图");
    const model = imageModels?.find(item => item.id === $(kind + '-model').value);
    const size = model && modelSize(model, kind);
    const style = $(kind + '-style').value.trim();
    const files = kind === 'cover' ? Array.from($('cover-references').files) : [];
    if (!title || !size) return imageStatus(kind, kind === 'cover'
      ? t("请填写标题，并选择可用的生图模型。") : t("请选择可用的生图模型。"));
    if (files.length > Math.min(4, model.referenceLimit || 0))
      return imageStatus(kind, t(`此模型最多支持 ${model.referenceLimit || 0} 张参考图。`, `This model supports up to ${model.referenceLimit || 0} reference images.`));
    if (files.some(file => !file.size || file.size > 20 * 1024 * 1024
        || !['image/png', 'image/jpeg', 'image/webp'].includes(file.type)))
      return imageStatus(kind, t("参考图须为 20 MiB 以内的 PNG、JPEG 或 WebP。"));
    const mode = template.backgroundMode;
    const version = backgroundVersion;
    const prompt = imagePrompt(kind, title, style, mode);
    generatingImage = true;
    draw();
    try {
      imageStatus(kind, files.length ? t("正在准备参考图…") : t("正在提交生图任务…"));
      const references = [];
      for (const file of files) references.push((await request('image-workflow.import', {file}, 30000)).id);
      const key = Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
      const plan = {key, title, model: model.id, size, quality: model.qualities.includes('auto') ? 'auto' : model.qualities[0],
        columns: 1, reference_limit: references.length, publish: false, steps: [{references, previous: 0, prompt}]};
      imageJob = {key, kind, mode, version};
      await readImageJob(await request('image-workflow.submit', {plan}, 30000));
    } catch (error) { imageStatus(kind, error.message); }
    finally {
      generatingImage = false;
      draw();
    }
  }

  $('cover-mode').addEventListener('change', () => {
    selected = hasCover() ? -1 : 0;
    syncPages();
    if ($('cover-mode').value === 'ai') void loadImageModels('cover');
  });
  $('cover-title').addEventListener('input', draw);
  $('ai-background').addEventListener('toggle', () => {
    if ($('ai-background').open) void loadImageModels('background');
  });
  $('background-mode').addEventListener('change', () => {
    template.backgroundMode = $('background-mode').value;
    draw();
    if ($('ai-background').open) void loadImageModels('background');
  });
  $('background-undo').addEventListener('click', () => {
    if (!previousBackground) return;
    backgroundVersion++;
    loadingBackground = false;
    background = previousBackground.image;
    Object.assign(template, previousBackground.slices, {
      background: previousBackground.data, backgroundMode: previousBackground.mode,
    });
    previousBackground = null;
    $('background-mode').value = template.backgroundMode;
    for (const name of ['sliceLeft', 'sliceRight', 'sliceTop', 'sliceBottom']) $(name).value = template[name];
    draw();
    void loadImageModels('background').then(() => imageStatus('background', t("已恢复上一张底图。")));
  });
  for (const kind of ['cover', 'background']) {
    $(kind + '-model').addEventListener('change', draw);
    $(kind + '-generate').addEventListener('click', () => generateImage(kind));
    $(kind + '-cancel').addEventListener('click', async () => {
      if (!imageJob?.id) return;
      try {
        await request('image-workflow.cancel', {jobId: imageJob.id});
        imageStatus(kind, t("已请求取消生成。"));
      } catch (error) { imageStatus(kind, error.message); }
    });
    $(kind + '-recover').addEventListener('click', async () => {
      if (!imageJob || generatingImage) return;
      generatingImage = true;
      draw();
      try {
        const job = imageJob.id
          ? await request('image-workflow.status', {jobId: imageJob.id})
          : await request('image-workflow.lookup', {key: imageJob.key});
        if (!job) {
          imageJob = null;
          throw Error(t("未找到已受理的生成任务，可以重新生成。"));
        }
        await readImageJob(job);
      } catch (error) { imageStatus(kind, error.message); }
      finally {
        generatingImage = false;
        draw();
      }
    });
  }

  $('template').addEventListener('change', async event => {
    await selectTemplate(event.target.value);
    if ($('ai-background').open) void loadImageModels('background');
  });
  for (const name of fields) $(name).addEventListener('input', updateFields);
  $('ratio').addEventListener('change', () => {
    if ($('cover-mode').value === 'ai') void loadImageModels('cover');
    if ($('ai-background').open) void loadImageModels('background');
  });
  for (const name of ['ratio', 'article', 'guides']) $(name).addEventListener('input', draw);
  $('background').addEventListener('change', event => {
    uploadBackground(event.target.files[0]);
    event.target.value = '';
  });
  $('remove-background').addEventListener('click', () => {
    backgroundVersion++;
    loadingBackground = false;
    background = null;
    template.background = '';
    previousBackground = null;
    draw();
  });
  $('save').addEventListener('click', saveTemplate);
  $('paginate').addEventListener('click', paginate);
  $('page').addEventListener('change', event => { selected = Number(event.target.value); syncPages(); });
  $('prev').addEventListener('click', () => { selected--; syncPages(); });
  $('next').addEventListener('click', () => { selected++; syncPages(); });
  $('page-text').addEventListener('input', event => {
    pages[selected].text = event.target.value;
    pageEdited = true;
    draw();
  });
  $('sticker').addEventListener('change', event => {
    pages[selected].sticker = event.target.value;
    pageEdited = true;
    draw();
  });
  $('split').addEventListener('click', () => {
    const cursor = $('page-text').selectionStart;
    const page = pages[selected];
    const head = page.text.slice(0, cursor);
    const tail = page.text.slice(cursor);
    if (!head.trim() || !tail.trim()) return status(t("请把光标放在两段正文之间。"), true);
    page.text = head;
    pages.splice(selected + 1, 0, {text: tail, sticker: cards.stickerFor(tail, selected + 1)});
    pageEdited = true;
    syncPages();
  });
  $('merge').addEventListener('click', () => {
    pages[selected].text += pages[selected + 1].text;
    pages.splice(selected + 1, 1);
    pageEdited = true;
    syncPages();
  });
  $('png').addEventListener('click', () => publish('png'));
  $('zip').addEventListener('click', () => publish('zip'));
  $('sticker').replaceChildren(...cards.stickers.map(value => new Option(value || t("无贴纸"), value)));
  refreshTemplates();
  fillTemplateFields();
  draw();
  libraryReady = loadTemplates();
  libraryReady.catch(() => {});
})();
