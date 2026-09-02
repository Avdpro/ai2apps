(() => {
    'use strict';
    const APP_ID = 'ai2apps.imagine-studio';
    const IMAGE_API = '/v1/images';
    const GALLERY_API = '/v1/platform/gallery';
    const CLOUD_MODELS_API = '/v1/platform/cloud/ai/models';
    const LOCAL_MODELS_API = '/v1/models';
    const HISTORY_API = '/v1/platform/imagine-studio/results';
    const DEFAULT_CLOUD_MODEL = 'openai/gpt-image-2';
    const GOOGLE_FLASH_MODEL = 'google/gemini-3.1-flash-image';
    const LEGACY_SIZE_CAPABILITY = {
        mode: 'fixed', default: '1024x1024', auto: false,
        width: { min: 16, max: 1536, multipleOf: 16 }, height: { min: 16, max: 1536, multipleOf: 16 },
        minPixels: 1048576, maxPixels: 1572864, maxAspectRatio: 1.5, experimentalAbovePixels: Number.MAX_SAFE_INTEGER,
        presets: ['1024x1024', '1536x1024', '1024x1536'],
    };
    const TRANSLATIONS = {
        zh: {
            appName: '创意画坊', appSubtitle: 'Imagine Studio · AI 视觉创作台', cloudGenerate: 'Cloud 生成', localGenerate: '本地生成', configureLocal: '配置本地模型', configuringLocal: '正在配置…', localConfigured: '本地绘图模型已配置', localAlreadyReady: '本地绘图模型已可用', refresh: '刷新', assets: '素材', installed: '已安装', specializedPipeline: '专用 Pipeline', coming: '即将推出', workspaceNav: 'Imagine Studio 工作区导航', pipelineAssets: 'Pipeline 与素材', pipelineList: 'Pipeline 列表', galleryAssets: 'Gallery 素材', pipelineWebUI: '当前 Pipeline WebUI', renderWorkspace: '渲染工作区',
            characterDesign: '角色设计', characterDesignSummary: '角色设定与多视图一致性', productPhoto: '商品摄影', productPhotoSummary: '布景、灯光与品牌模板', comicStoryboard: '漫画分镜', comicStoryboardSummary: '角色连续性与分镜排版', coderNote: '后续可从 Coder App 安装和扩展 Pipeline。',
            openGallery: '打开完整 Gallery', loadingGallery: '正在载入素材库…', retry: '重试', galleryHelp: '将图片拖到中间工作区的指定 Slot。', currentPipeline: 'CURRENT PIPELINE', builtInPipeline: '内置 Pipeline', cloudReady: 'Cloud 就绪', create: 'CREATE', modelReady: '模型就绪',
            referenceAlt: '参考素材', primaryImage: '主图片', referenceImage: '参考图', required: '必选', optional: '可选', cloudDisclosure: '生成时会将提示词和所选图片发送至 AI2Apps Cloud；每次发送图片前都会请求确认。', localDisclosure: '提示词和所选图片只由本机已安装的 AI2Apps 模型处理。', prompt: '提示词', model: '模型', modelHint: '可选择 Cloud 或已安装的本地绘图模型', canvasSize: '画面尺寸', sourceImage: '原图', matchedRatio: '已匹配原图比例', flexibleSize: 'Cloud 灵活尺寸 · 最高 4K', localSize: '本地模型尺寸 · 按模型能力', fixedSize: '固定尺寸 · 1:1 / 3:2 / 2:3', quality: '质量', width: '宽度', height: '高度', multipleOf: 'px · 必须是 {value} 的倍数', swapSize: '交换宽高', experimentalSize: '当前尺寸属于 2K+ 实验性输出，生成更慢且点数消耗可能更高。', advanced: '高级设置', visualStyle: '视觉风格', unspecified: '不指定', photorealistic: '写实摄影', illustration: '精致插画', anime: '动画风格', ink: '水墨画', product: '商业产品图', outputFormat: '输出格式', cloudSubmitHint: '通过 AI2Apps Cloud 生成；完成后可下载或加入 Gallery 当前目录', localSubmitHint: '使用本机模型生成；完成后可下载或加入 Gallery 当前目录', generating: '正在生成…', startGenerate: '开始生成', output: 'OUTPUT', results: '生成结果', clearHistory: '清空生成历史', dragToGallery: '拖到 Gallery', waiting: '等待生成', waitingHint: '生成的图片会显示在这里', addedGallery: '已加入 Gallery', addGallery: '加入 Gallery', download: '下载', generationHistory: '生成记录', resultCount: '{count} 个结果', cloudGenerating: 'Cloud 生成中', localGenerating: '本地生成中', noResults: '还没有结果', noResultsHint: '从左侧选择 Pipeline 开始创作', completed: '已完成', failed: '失败', remove: '移除', deleteHistory: '删除历史', dropIntoSlot: '放入图片 Slot', dropIntoSlotHint: '拖到指定 Slot 可控制素材顺序', autoSize: 'Auto · 根据提示词选择', customSize: '自定义尺寸…',
            textImageName: '文生图', textImageSummary: '从文字生成完整画面', textImageDescription: '文字描述、构图与风格控制', textImageAction: '生成文生图', textImageRun: 'Cloud 图片生成', textImagePlaceholder: '描述主体、环境、构图、光线、色彩与风格，例如：\n雨后的东京小巷，电影感广角镜头，霓虹灯倒映在路面，细腻写实摄影。',
            editName: '图片编辑', editSummary: '按提示修改一张图片', editDescription: '保留原图结构并执行定向修改', editAction: '编辑图片', editRun: 'Cloud 图片编辑', editPlaceholder: '描述需要修改的内容，例如：\n保留人物与构图，将背景改成日落海岸，并统一暖金色光线。',
            referenceName: '参考图创作', referenceSummary: '组合多张图片进行创作', referenceDescription: '使用最多四张参考图控制主体、风格与构图', referenceAction: '基于参考图创作', referenceRun: 'Cloud 参考图生成', referencePlaceholder: '说明每张参考图的用途以及希望生成的画面，例如：\n采用图 1 的人物、图 2 的服装和图 3 的色彩风格，生成正面角色海报。',
            requestFailed: '请求失败 ({status})', cannotRead: '无法读取 {name}', cannotReadDimensions: '无法读取图片尺寸。', resultNotDraggable: '生成结果不是可拖拽的图片数据。', invalidSize: '请输入有效的宽度和高度。', maxEdge: '宽和高均不能超过 {max}px。', alignedSize: '宽和高必须是 {value} 的倍数。', minPixels: '总像素不能少于 {value}。', maxPixels: '总像素不能超过 {value}。', maxAspect: '长短边比例不能超过 {value}:1。', onlyFixed: '当前 Cloud 版本只支持三个固定尺寸。', sourceAspectUnsupported: '原图比例超过 Cloud 支持的 {value}:1，已改用 Auto 尺寸。', invalidSlot: '图片 Slot 只接受 PNG、JPEG 或 WebP。', uploadConfirm: '本次生成会将提示词和 {count} 张所选图片上传到 AI2Apps Cloud 图像模型处理。是否继续？', noCloudImage: 'Cloud 模型没有返回可用图片。', historySaveFailed: '图片已生成，但本地历史保存失败：{error}', missingInstance: '缺少 App Instance，无法保存生成历史。', deleteOneConfirm: '从 Imagine Studio 历史中永久删除这张图片？', clearAllConfirm: '永久清空 Imagine Studio 的全部生成历史？此操作不可恢复。', invalidHistoryUrl: '历史图片地址无效。', dragFailed: '无法拖拽这张图片：{error}', galleryNoAsset: 'Gallery 没有返回资产 ID。', addedToGallery: '已加入 Gallery · {name}', downloadStarted: '下载已开始，请在浏览器下载列表中查看。', miniNoUrl: 'Gallery Mini Entry 未返回可用地址。', miniLoadFailed: '无法载入 Gallery Mini Entry。', currentGalleryOnly: '只接受当前 Gallery 中的图片素材。', readGalleryFailed: '无法读取 Gallery 素材 ({status})', appImageOnly: 'Imagine Studio 的素材 Slot 只接受图片。',
        },
        en: {
            appName: 'Imagine Studio', appSubtitle: 'AI visual creation studio', cloudGenerate: 'Cloud generation', localGenerate: 'Local generation', configureLocal: 'Configure local model', configuringLocal: 'Configuring…', localConfigured: 'Local image model configured', localAlreadyReady: 'A local image model is already ready', refresh: 'Refresh', assets: 'Assets', installed: 'Installed', specializedPipeline: 'Specialized Pipelines', coming: 'COMING SOON', workspaceNav: 'Imagine Studio workspace navigation', pipelineAssets: 'Pipelines and assets', pipelineList: 'Pipeline list', galleryAssets: 'Gallery assets', pipelineWebUI: 'Current Pipeline interface', renderWorkspace: 'Rendering workspace',
            characterDesign: 'Character Design', characterDesignSummary: 'Consistent character sheets and multi-view design', productPhoto: 'Product Photography', productPhotoSummary: 'Sets, lighting, and brand templates', comicStoryboard: 'Comic Storyboards', comicStoryboardSummary: 'Character continuity and panel layouts', coderNote: 'Install and extend Pipelines later from the Coder App.',
            openGallery: 'Open full Gallery', loadingGallery: 'Loading asset library…', retry: 'Retry', galleryHelp: 'Drag an image into a specific Slot in the workspace.', currentPipeline: 'CURRENT PIPELINE', builtInPipeline: 'Built-in Pipeline', cloudReady: 'Cloud ready', create: 'CREATE', modelReady: 'Model ready',
            referenceAlt: 'Reference asset', primaryImage: 'Primary image', referenceImage: 'Reference', required: 'Required', optional: 'Optional', cloudDisclosure: 'Your prompt and selected images are sent to AI2Apps Cloud for generation. You will be asked to confirm before images are uploaded.', localDisclosure: 'Your prompt and selected images are processed only by the installed AI2Apps model on this device.', prompt: 'Prompt', model: 'Model', modelHint: 'Choose an AI2Apps Cloud model or an installed local image model', canvasSize: 'Canvas size', sourceImage: 'Source', matchedRatio: 'source aspect ratio matched', flexibleSize: 'Flexible Cloud sizes · up to 4K', localSize: 'Local model sizes · capability-aware', fixedSize: 'Fixed sizes · 1:1 / 3:2 / 2:3', quality: 'Quality', width: 'Width', height: 'Height', multipleOf: 'px · must be a multiple of {value}', swapSize: 'Swap width and height', experimentalSize: 'This is an experimental 2K+ output. It may generate more slowly and use more points.', advanced: 'Advanced settings', visualStyle: 'Visual style', unspecified: 'Unspecified', photorealistic: 'Photorealistic', illustration: 'Refined illustration', anime: 'Animation', ink: 'Ink wash', product: 'Commercial product', outputFormat: 'Output format', cloudSubmitHint: 'Generate with AI2Apps Cloud, then download or add to the current Gallery folder', localSubmitHint: 'Generate on this device, then download or add to the current Gallery folder', generating: 'Generating…', startGenerate: 'Generate', output: 'OUTPUT', results: 'Results', clearHistory: 'Clear generation history', dragToGallery: 'Drag to Gallery', waiting: 'Ready to create', waitingHint: 'Generated images will appear here', addedGallery: 'Added to Gallery', addGallery: 'Add to Gallery', download: 'Download', generationHistory: 'Generation history', resultCount: '{count} results', cloudGenerating: 'Generating in Cloud', localGenerating: 'Generating locally', noResults: 'No results yet', noResultsHint: 'Choose a Pipeline on the left to start creating', completed: 'Completed', failed: 'Failed', remove: 'Remove', deleteHistory: 'Delete history', dropIntoSlot: 'Drop into an image Slot', dropIntoSlotHint: 'Drop on a specific Slot to control asset order', autoSize: 'Auto · choose from prompt', customSize: 'Custom size…',
            textImageName: 'Text to Image', textImageSummary: 'Create a complete image from text', textImageDescription: 'Prompt, composition, and style controls', textImageAction: 'Create from text', textImageRun: 'Cloud image generation', textImagePlaceholder: 'Describe the subject, setting, composition, lighting, colors, and style. For example:\nA rain-soaked Tokyo alley, cinematic wide-angle view, neon reflections, detailed realistic photography.',
            editName: 'Image Edit', editSummary: 'Modify one image with a prompt', editDescription: 'Preserve the source structure while making targeted changes', editAction: 'Edit image', editRun: 'Cloud image edit', editPlaceholder: 'Describe the changes. For example:\nKeep the person and composition, replace the background with a sunset coast, and use warm golden lighting.',
            referenceName: 'Reference Creation', referenceSummary: 'Create with multiple reference images', referenceDescription: 'Use up to four references to control subject, style, and composition', referenceAction: 'Create from references', referenceRun: 'Cloud reference generation', referencePlaceholder: 'Explain how each reference should be used. For example:\nUse the person from image 1, clothing from image 2, and colors from image 3 to create a front-facing character poster.',
            requestFailed: 'Request failed ({status})', cannotRead: 'Could not read {name}', cannotReadDimensions: 'Could not read the image dimensions.', resultNotDraggable: 'The generated result is not draggable image data.', invalidSize: 'Enter a valid width and height.', maxEdge: 'Width and height cannot exceed {max}px.', alignedSize: 'Width and height must be multiples of {value}.', minPixels: 'Total pixels cannot be less than {value}.', maxPixels: 'Total pixels cannot exceed {value}.', maxAspect: 'The long-to-short edge ratio cannot exceed {value}:1.', onlyFixed: 'This Cloud version supports only three fixed sizes.', sourceAspectUnsupported: 'The source aspect ratio exceeds the Cloud limit of {value}:1. Size was changed to Auto.', invalidSlot: 'Image Slots accept PNG, JPEG, or WebP only.', uploadConfirm: 'This generation will upload the prompt and {count} selected image(s) to the AI2Apps Cloud image model. Continue?', noCloudImage: 'The Cloud model did not return a usable image.', historySaveFailed: 'The image was generated, but local history could not be saved: {error}', missingInstance: 'The App Instance is missing, so generation history cannot be saved.', deleteOneConfirm: 'Permanently delete this image from Imagine Studio history?', clearAllConfirm: 'Permanently clear all Imagine Studio generation history? This cannot be undone.', invalidHistoryUrl: 'The history image URL is invalid.', dragFailed: 'Could not drag this image: {error}', galleryNoAsset: 'Gallery did not return an asset ID.', addedToGallery: 'Added to Gallery · {name}', downloadStarted: 'Download started. Check your browser downloads.', miniNoUrl: 'Gallery Mini Entry did not return a usable URL.', miniLoadFailed: 'Could not load Gallery Mini Entry.', currentGalleryOnly: 'Only images from the current Gallery are accepted.', readGalleryFailed: 'Could not read the Gallery asset ({status})', appImageOnly: 'Imagine Studio Slots accept images only.',
        },
    };
    const PIPELINE_DEFS = [
        { id: 'text-image', mode: 'generate', icon: 'text-cursor-input', needsImages: false, requiresImage: false, maxImages: 0, prefix: 'textImage' },
        { id: 'image-edit', mode: 'edit', icon: 'scan-search', needsImages: true, requiresImage: true, maxImages: 1, prefix: 'edit' },
        { id: 'reference-create', mode: 'reference', icon: 'images', needsImages: true, requiresImage: true, maxImages: 4, prefix: 'reference' },
    ];
    function normalizedLocale(value) { return String(value || '').toLowerCase().startsWith('zh') ? 'zh' : 'en'; }
    function translate(locale, key, values = {}) {
        let text = TRANSLATIONS[normalizedLocale(locale)]?.[key] || TRANSLATIONS.en[key] || key;
        Object.entries(values).forEach(([name, value]) => { text = text.replaceAll(`{${name}}`, String(value)); });
        return text;
    }
    function localizedPipelines(locale) {
        return PIPELINE_DEFS.map(item => ({ ...item, name: translate(locale, `${item.prefix}Name`), summary: translate(locale, `${item.prefix}Summary`), description: translate(locale, `${item.prefix}Description`), actionTitle: translate(locale, `${item.prefix}Action`), runLabel: translate(locale, `${item.prefix}Run`), placeholder: translate(locale, `${item.prefix}Placeholder`) }));
    }
    const STYLE_PROMPTS = {
        photorealistic: 'Use polished photorealistic photography with natural materials and cinematic lighting.',
        illustration: 'Use a refined editorial illustration style with rich detail and controlled color harmony.',
        anime: 'Use a high-quality contemporary animation style with clean linework and expressive lighting.',
        ink: 'Use an elegant Chinese ink-wash style with expressive brushwork and generous negative space.',
        product: 'Use premium commercial product photography, precise studio lighting, and a clean brand-ready composition.',
    };

    async function responsePayload(response) {
        const value = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = value?.error?.message || value?.detail?.error?.message || value?.detail?.message || value?.message || value?.detail;
            const message = typeof detail === 'string' ? detail : (detail?.code ? `${detail.code}${detail.message ? `：${detail.message}` : ''}` : '');
            throw new Error(message || translate(document.documentElement.lang, 'requestFailed', { status: response.status }));
        }
        return value;
    }
    function readDataUrl(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ''));
            reader.onerror = () => reject(new Error(translate(document.documentElement.lang, 'cannotRead', { name: file.name })));
            reader.readAsDataURL(file);
        });
    }
    async function dataUrlFile(dataUrl, name) {
        const response = await fetch(dataUrl);
        const blob = await response.blob();
        return new File([blob], name, { type: blob.type || 'image/png' });
    }
    async function imageDimensions(file) {
        if (typeof createImageBitmap === 'function') {
            const bitmap = await createImageBitmap(file);
            try { return { width: bitmap.width, height: bitmap.height }; }
            finally { bitmap.close(); }
        }
        const url = URL.createObjectURL(file);
        try {
            return await new Promise((resolve, reject) => {
                const image = new Image();
                image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
                image.onerror = () => reject(new Error(translate(document.documentElement.lang, 'cannotReadDimensions')));
                image.src = url;
            });
        } finally { URL.revokeObjectURL(url); }
    }
    function dragFileFromDataUrl(dataUrl, name) {
        const comma = String(dataUrl || '').indexOf(',');
        const header = comma < 0 ? '' : dataUrl.slice(0, comma);
        const match = /^data:(image\/[a-z0-9.+-]+);base64$/i.exec(header);
        if (!match) throw new Error(translate(document.documentElement.lang, 'resultNotDraggable'));
        const binary = atob(dataUrl.slice(comma + 1)); const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
        return new File([bytes], name, { type: match[1] });
    }

    window.imagineStudioApp = function () { return {
        locale: normalizedLocale(document.documentElement.lang), pipelines: localizedPipelines(document.documentElement.lang), pipelineId: PIPELINE_DEFS[0].id, leftView: 'pipelines', prompt: '',
        modelId: DEFAULT_CLOUD_MODEL, models: [], size: '1024x1024', customWidth: 2048, customHeight: 1152,
        sizeCapability: structuredClone(LEGACY_SIZE_CAPABILITY), flexibleSizes: false, pricingVersion: '',
        quality: 'auto', format: 'png', style: '',
        referenceFiles: [], referencePreviews: [], referenceDimensions: [], results: [], selectedResultId: '', generating: false, refreshing: false, configuringLocal: false,
        notice: '', noticeTone: 'error', clientEnvironment: 'browser', galleryMiniUrl: '', galleryMiniMountId: '', galleryMiniLoading: false, galleryMiniError: '', galleryMessageHandler: null, hostContextHandler: null,
        galleryActiveCollectionId: 'recent', galleryActiveCollectionName: 'Recent', galleryDragActive: false, gallerySlotTarget: null,

        get currentPipeline() { return this.pipelines.find(item => item.id === this.pipelineId) || this.pipelines[0]; },
        get requiredOperation() { return this.currentPipeline.mode === 'generate' ? 'image_generation' : 'image_edit'; },
        get compatibleModels() { return this.models.filter(model => model.operations.includes(this.requiredOperation)); },
        get selectedModel() { return this.models.find(model => model.id === this.modelId) || this.compatibleModels[0] || null; },
        get hasLocalModels() { return this.models.some(model => model.source === 'local'); },
        get usingLocalModel() { return this.selectedModel?.source === 'local'; },
        get generationModeLabel() { return this.tr(this.usingLocalModel ? 'localGenerate' : 'cloudGenerate'); },
        get submitHint() { return this.tr(this.usingLocalModel ? 'localSubmitHint' : 'cloudSubmitHint'); },
        get modelSizeHint() { return this.tr(this.usingLocalModel ? 'localSize' : (this.flexibleSizes ? 'flexibleSize' : 'fixedSize')); },
        get formatOptions() { return this.selectedModel?.formats?.length ? this.selectedModel.formats : ['png']; },
        get sizeOptions() {
            const values = [...(this.sizeCapability.presets || [])];
            if (this.sizeCapability.auto) values.unshift('auto');
            if (this.flexibleSizes) values.push('custom');
            return values.map(value => ({ value, label: this.sizeLabel(value) }));
        },
        get requestedSize() { return this.size === 'custom' ? `${Number(this.customWidth)}x${Number(this.customHeight)}` : this.size; },
        get sizeError() { return this.validateSize(this.requestedSize); },
        get experimentalSize() {
            const dimensions = this.parseSize(this.requestedSize); if (!dimensions) return false;
            return dimensions.width * dimensions.height > Number(this.sizeCapability.experimentalAbovePixels || Number.MAX_SAFE_INTEGER);
        },
        get canGenerate() { return Boolean(this.selectedModel) && Boolean(this.prompt.trim()) && !this.sizeError && (!this.currentPipeline.requiresImage || this.referenceFiles.some(Boolean)); },
        get activeResult() { return this.results.find(item => item.id === this.selectedResultId) || this.results.find(item => item.status === 'succeeded') || null; },
        get activeFilename() { return this.activeResult?.filename || 'imagine-studio.png'; },
        get activeDownloadUrl() { return this.activeResult?.galleryAssetId ? `${GALLERY_API}/assets/${encodeURIComponent(this.activeResult.galleryAssetId)}/content?download=true` : (this.activeResult?.imageUrl || '#'); },

        async init() {
            this.clientEnvironment = this.$root?.dataset?.clientEnvironment || 'browser';
            this.galleryMessageHandler = event => this.handleGalleryMessage(event);
            this.hostContextHandler = event => this.setLocale(event.detail?.locale);
            window.addEventListener('message', this.galleryMessageHandler);
            window.addEventListener('ai2apps:host-context', this.hostContextHandler);
            window.addEventListener('beforeunload', () => this.cleanup(), { once: true });
            this.$watch('modelId', () => this.applySelectedModelCapability());
            await this.refresh();
            await this.resumeLocalProvisioning();
        },
        cleanup() { if (this.galleryMessageHandler) window.removeEventListener('message', this.galleryMessageHandler); if (this.hostContextHandler) window.removeEventListener('ai2apps:host-context', this.hostContextHandler); this.referencePreviews.forEach(url => { if (url) URL.revokeObjectURL(url); }); },
        tr(key, values) { return translate(this.locale, key, values); },
        setLocale(value) { const locale = normalizedLocale(value); if (locale === this.locale) return; this.locale = locale; this.pipelines = localizedPipelines(locale); this.results = this.results.map(result => ({ ...result, title: this.pipelines.find(item => item.id === result.pipelineId)?.name || result.title })); document.documentElement.lang = locale; document.title = 'Imagine Studio - AI2Apps'; this.icons(); },
        icons() { this.$nextTick(() => window.lucide?.createIcons()); },
        fail(error) { this.notice = error?.message || String(error); this.noticeTone = 'error'; this.icons(); },
        success(message) { this.notice = message; this.noticeTone = 'success'; this.icons(); },
        appInstanceId() {
            return window.AI2AppsCapabilities?.appInstanceId?.()
                || new URLSearchParams(window.location.hash.slice(1)).get('ai2apps-instance') || '';
        },
        historyHeaders() {
            const instanceId = this.appInstanceId();
            return { Accept: 'application/json', ...(instanceId ? { 'X-AI2Apps-App-Instance': instanceId } : {}) };
        },
        historyResult(record) {
            return {
                id: record.id, historyId: record.id, status: 'succeeded', title: this.pipelines.find(item => item.id === record.pipelineId)?.name || record.title,
                pipelineId: record.pipelineId, prompt: record.prompt, size: record.size,
                modelId: record.modelId, modelLabel: record.modelLabel, imageUrl: record.contentUrl, filename: record.filename,
                error: '', galleryAssetId: '', adding: false, createdAt: record.createdAt,
            };
        },
        async loadHistory() {
            if (!this.appInstanceId()) return;
            const payload = await responsePayload(await fetch(`${HISTORY_API}?limit=20`, { credentials: 'same-origin', headers: this.historyHeaders() }));
            const transient = this.results.filter(item => item.status !== 'succeeded' || !item.historyId);
            this.results = [...transient, ...(payload.items || []).map(item => this.historyResult(item))];
            if (!this.results.some(item => item.id === this.selectedResultId)) this.selectedResultId = this.results[0]?.id || '';
        },
        async refresh() {
            this.refreshing = true;
            try { await Promise.all([this.loadModelCatalog(), this.loadHistory()]); this.icons(); }
            catch (error) { this.fail(error); }
            finally { this.refreshing = false; }
        },
        cloudSizeCapability(model) {
            if (String(model?.id || '').endsWith(GOOGLE_FLASH_MODEL)) return structuredClone(LEGACY_SIZE_CAPABILITY);
            const capability = model?.imageOptions?.size;
            if (capability?.mode !== 'bounded-custom') return structuredClone(LEGACY_SIZE_CAPABILITY);
            return {
                ...structuredClone(LEGACY_SIZE_CAPABILITY), ...capability,
                width: { ...LEGACY_SIZE_CAPABILITY.width, ...(capability.width || {}) },
                height: { ...LEGACY_SIZE_CAPABILITY.height, ...(capability.height || {}) },
                presets: Array.isArray(capability.presets) ? capability.presets.filter(value => !this.validateCatalogSize(value, capability)) : LEGACY_SIZE_CAPABILITY.presets,
            };
        },
        localSizeCapability(capabilities) {
            const geometry = capabilities?.geometry || {}, defaults = capabilities?.defaults || {};
            const minimum = geometry.minimum || { width: 256, height: 256 }, maximum = geometry.maximum || { width: 2048, height: 2048 };
            const multiple = Number(geometry.multiple_of || 1), defaultSize = `${Number(defaults.width || 1024)}x${Number(defaults.height || 1024)}`;
            const ratioValues = (geometry.ratios || ['1:1']).map(value => String(value).split(':').map(Number)).filter(value => value.length === 2 && value.every(Number.isFinite));
            const maxAspectRatio = Math.max(1, ...ratioValues.map(([a, b]) => Math.max(a, b) / Math.min(a, b)));
            const common = ['1024x1024', '1344x768', '768x1344', '1216x832', '832x1216', defaultSize];
            const capability = {
                mode: 'bounded-custom', default: defaultSize, auto: false,
                width: { min: Number(minimum.width), max: Number(maximum.width), multipleOf: multiple },
                height: { min: Number(minimum.height), max: Number(maximum.height), multipleOf: multiple },
                minPixels: Number(minimum.width) * Number(minimum.height), maxPixels: Number(maximum.width) * Number(maximum.height),
                maxAspectRatio, experimentalAbovePixels: Number.MAX_SAFE_INTEGER, presets: [],
            };
            capability.presets = [...new Set(common)].filter(value => !this.validateCatalogSize(value, capability));
            if (!capability.presets.length) capability.presets = [defaultSize];
            return capability;
        },
        async loadModelCatalog() {
            const cloudFallback = { id: DEFAULT_CLOUD_MODEL, label: 'AI2Apps Cloud · GPT Image 2', source: 'cloud', operations: ['image_generation', 'image_edit'], formats: ['png', 'jpeg', 'webp'], sizeCapability: structuredClone(LEGACY_SIZE_CAPABILITY), pricingVersion: '' };
            let cloudModels = [cloudFallback], localModels = [];
            const [cloudResult, localResult] = await Promise.allSettled([
                fetch(CLOUD_MODELS_API, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } }).then(responsePayload),
                fetch(LOCAL_MODELS_API, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } }).then(responsePayload),
            ]);
            if (cloudResult.status === 'fulfilled') {
                cloudModels = (cloudResult.value.items || []).filter(model => model?.capabilities?.imageGeneration).map(model => ({
                    id: model.id, label: `AI2Apps Cloud · ${model.displayName || model.id}`, source: 'cloud',
                    operations: ['image_generation', ...(model.capabilities?.imageEdit ? ['image_edit'] : [])],
                    formats: ['png', 'jpeg', 'webp'], sizeCapability: this.cloudSizeCapability(model), pricingVersion: String(model.pricingVersion || ''),
                }));
                if (!cloudModels.some(model => model.id === DEFAULT_CLOUD_MODEL)) cloudModels.unshift(cloudFallback);
            }
            if (localResult.status === 'fulfilled') {
                localModels = (localResult.value.data || []).filter(model => model?.model_type === 'image_generation' && model?.source_type === 'package' && model?.checkpoint_ready !== false && !model?.is_hidden).map(model => ({
                    id: model.id, label: `AI2Apps Local · ${model.display_name || model.id}`, source: 'local',
                    operations: Array.isArray(model.image_capabilities?.operations) ? model.image_capabilities.operations : (model.capabilities || []).filter(value => ['image_generation', 'image_edit'].includes(value)),
                    formats: model.image_capabilities?.formats?.output || ['png'], sizeCapability: this.localSizeCapability(model.image_capabilities), pricingVersion: '',
                }));
            }
            const preferredModelId = this.modelId;
            this.models = [...cloudModels, ...localModels];
            this.modelId = '';
            await this.$nextTick();
            this.modelId = this.compatibleModels.some(model => model.id === preferredModelId) ? preferredModelId : (this.compatibleModels[0]?.id || '');
            await this.$nextTick();
            this.applySelectedModelCapability();
        },
        reconcileSelectedModel() {
            if (!this.compatibleModels.some(model => model.id === this.modelId)) this.modelId = this.compatibleModels[0]?.id || '';
            this.applySelectedModelCapability();
        },
        applySelectedModelCapability() {
            const model = this.selectedModel; if (!model) return;
            this.sizeCapability = JSON.parse(JSON.stringify(model.sizeCapability || LEGACY_SIZE_CAPABILITY));
            this.flexibleSizes = model.source === 'local' || this.sizeCapability.mode === 'bounded-custom';
            this.pricingVersion = String(model.pricingVersion || '');
            if (!this.sizeOptions.some(option => option.value === this.size)) this.size = String(this.sizeCapability.default || '1024x1024');
            if (!this.formatOptions.includes(this.format)) this.format = this.formatOptions[0] || 'png';
            if (this.currentPipeline.mode === 'edit' && this.referenceDimensions[0]) this.matchEditAspect(this.referenceDimensions[0]);
            this.icons();
        },
        capabilityRequest(actionId) {
            const resumeToken = globalThis.crypto?.randomUUID?.() || `imagine-local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
            return {
                appId: APP_ID, capability: 'image.generation', actionId,
                requirements: { operations: ['image_generation', 'image_edit'], outputFormats: ['png', 'jpeg', 'webp'] },
                intent: { returnTo: `/apps/${APP_ID}`, resumeToken, completionPolicy: 'configure_only' },
            };
        },
        async finishLocalProvisioning(result) {
            await this.refresh();
            if (!this.hasLocalModels) throw new Error('ACPF completed, but no ready local image model was discovered.');
            if (result?.outcome === 'configured' && result.session?.id) await window.AI2AppsCapabilities.acknowledge(result.session.id, { appId: APP_ID });
            this.success(this.tr(result?.outcome === 'configured' ? 'localConfigured' : 'localAlreadyReady'));
        },
        async configureLocalModel() {
            if (this.configuringLocal || !window.AI2AppsCapabilities?.ensure) return;
            this.configuringLocal = true; this.notice = '';
            try { await this.finishLocalProvisioning(await window.AI2AppsCapabilities.ensure(this.capabilityRequest('configure-local-image-model'))); }
            catch (error) { this.fail(error); }
            finally { this.configuringLocal = false; this.icons(); }
        },
        async resumeLocalProvisioning() {
            if (!window.AI2AppsCapabilities?.resume) return;
            try { const result = await window.AI2AppsCapabilities.resume(APP_ID, { capability: 'image.generation' }); if (result) await this.finishLocalProvisioning(result); }
            catch (error) { this.fail(error); }
        },
        parseSize(value) {
            const match = /^([1-9][0-9]{0,4})x([1-9][0-9]{0,4})$/.exec(String(value || ''));
            return match ? { width: Number(match[1]), height: Number(match[2]) } : null;
        },
        validateCatalogSize(value, capability) {
            const dimensions = this.parseSize(value); if (!dimensions) return 'invalid';
            const width = dimensions.width, height = dimensions.height, pixels = width * height;
            if (width > Number(capability.width?.max) || height > Number(capability.height?.max)) return 'edge';
            if (width % Number(capability.width?.multipleOf || 1) || height % Number(capability.height?.multipleOf || 1)) return 'alignment';
            if (pixels < Number(capability.minPixels) || pixels > Number(capability.maxPixels)) return 'pixels';
            if (Math.max(width, height) > Number(capability.maxAspectRatio) * Math.min(width, height)) return 'ratio';
            return '';
        },
        validateSize(value) {
            if (value === 'auto' && this.sizeCapability.auto) return '';
            const dimensions = this.parseSize(value); if (!dimensions) return this.tr('invalidSize');
            const width = dimensions.width, height = dimensions.height, capability = this.sizeCapability, pixels = width * height;
            if (width > capability.width.max || height > capability.height.max) return this.tr('maxEdge', { max: capability.width.max });
            if (width % capability.width.multipleOf || height % capability.height.multipleOf) return this.tr('alignedSize', { value: capability.width.multipleOf });
            if (pixels < capability.minPixels) return this.tr('minPixels', { value: Number(capability.minPixels).toLocaleString(this.locale) });
            if (pixels > capability.maxPixels) return this.tr('maxPixels', { value: Number(capability.maxPixels).toLocaleString(this.locale) });
            if (Math.max(width, height) > capability.maxAspectRatio * Math.min(width, height)) return this.tr('maxAspect', { value: capability.maxAspectRatio });
            if (!this.flexibleSizes && !capability.presets.includes(value)) return this.tr('onlyFixed');
            return '';
        },
        sizeLabel(value) {
            if (value === 'auto') return this.tr('autoSize');
            if (value === 'custom') return this.tr('customSize');
            const dimensions = this.parseSize(value); if (!dimensions) return value;
            const longestEdge = Math.max(dimensions.width, dimensions.height);
            const tier = longestEdge >= 3000 ? '4K' : longestEdge >= 1800 ? '2K' : '1K';
            const divisor = (a, b) => b ? divisor(b, a % b) : a, common = divisor(dimensions.width, dimensions.height);
            return `${dimensions.width}×${dimensions.height} · ${dimensions.width / common}:${dimensions.height / common} · ${tier}`;
        },
        swapCustomSize() { [this.customWidth, this.customHeight] = [this.customHeight, this.customWidth]; this.icons(); },
        referenceSlotStyle(index) {
            const dimensions = this.referenceDimensions[index];
            if (!dimensions?.width || !dimensions?.height || !this.referencePreviews[index]) return '';
            const ratio = dimensions.width / dimensions.height, maxHeight = 360;
            const width = Math.max(1, Math.round(maxHeight * ratio));
            return `width:min(100%,${width}px);height:auto;max-height:${maxHeight}px;aspect-ratio:${dimensions.width}/${dimensions.height};justify-self:center`;
        },
        showLeftView(view) { this.leftView = view === 'assets' ? 'assets' : 'pipelines'; if (this.leftView === 'assets' && !this.galleryMiniUrl) this.mountGalleryMini(); this.icons(); },
        selectPipeline(id) { if (!this.pipelines.some(item => item.id === id)) return; this.pipelineId = id; this.leftView = 'pipelines'; this.trimReferences(); this.reconcileSelectedModel(); if (this.currentPipeline.mode === 'edit' && this.referenceDimensions[0]) this.matchEditAspect(this.referenceDimensions[0]); this.icons(); },
        trimReferences() {
            const limit = this.currentPipeline.maxImages;
            for (let index = limit; index < this.referencePreviews.length; index += 1) if (this.referencePreviews[index]) URL.revokeObjectURL(this.referencePreviews[index]);
            this.referenceFiles = this.referenceFiles.slice(0, limit); this.referencePreviews = this.referencePreviews.slice(0, limit); this.referenceDimensions = this.referenceDimensions.slice(0, limit);
        },
        matchEditAspect(dimensions) {
            const sourceWidth = Number(dimensions?.width), sourceHeight = Number(dimensions?.height);
            if (!sourceWidth || !sourceHeight || this.currentPipeline.mode !== 'edit') return;
            const sourceRatio = sourceWidth / sourceHeight;
            if (!this.flexibleSizes) {
                const preset = [...(this.sizeCapability.presets || [])].sort((left, right) => {
                    const a = this.parseSize(left), b = this.parseSize(right);
                    return Math.abs((a.width / a.height) - sourceRatio) - Math.abs((b.width / b.height) - sourceRatio);
                })[0];
                if (preset) this.size = preset;
                return;
            }
            const capability = this.sizeCapability, widthStep = Number(capability.width.multipleOf || 1), heightStep = Number(capability.height.multipleOf || 1);
            const maxAspect = Number(capability.maxAspectRatio || Number.MAX_SAFE_INTEGER);
            if (Math.max(sourceWidth, sourceHeight) > maxAspect * Math.min(sourceWidth, sourceHeight)) {
                this.size = capability.auto ? 'auto' : capability.default;
                this.fail(new Error(this.tr('sourceAspectUnsupported', { value: maxAspect })));
                return;
            }
            const sourcePixels = sourceWidth * sourceHeight;
            const minScale = Math.max(
                Number(capability.width.min || 1) / sourceWidth,
                Number(capability.height.min || 1) / sourceHeight,
                Math.sqrt(Number(capability.minPixels || 1) / sourcePixels),
            );
            const maxScale = Math.min(
                Number(capability.width.max) / sourceWidth,
                Number(capability.height.max) / sourceHeight,
                Math.sqrt(Number(capability.maxPixels) / sourcePixels),
            );
            const scale = Math.min(maxScale, Math.max(minScale, 1));
            const baseWidth = Math.round(sourceWidth * scale / widthStep) * widthStep;
            const baseHeight = Math.round(sourceHeight * scale / heightStep) * heightStep;
            const targetPixels = sourcePixels * scale * scale; const candidates = [];
            for (let widthOffset = -12; widthOffset <= 12; widthOffset += 1) {
                for (let heightOffset = -12; heightOffset <= 12; heightOffset += 1) {
                    const width = baseWidth + widthOffset * widthStep, height = baseHeight + heightOffset * heightStep;
                    if (this.validateSize(`${width}x${height}`)) continue;
                    const ratioError = Math.abs(Math.log((width / height) / sourceRatio));
                    const pixelError = Math.abs(width * height - targetPixels) / Math.max(1, targetPixels);
                    candidates.push({ width, height, score: ratioError * 1000 + pixelError });
                }
            }
            candidates.sort((left, right) => left.score - right.score);
            if (!candidates.length) { this.size = capability.auto ? 'auto' : capability.default; return; }
            this.customWidth = candidates[0].width; this.customHeight = candidates[0].height; this.size = 'custom';
        },
        async setReference(index, file) {
            if (!file) return;
            if (!String(file.type || '').startsWith('image/')) { this.fail(new Error(this.tr('invalidSlot'))); return; }
            if (this.referencePreviews[index]) URL.revokeObjectURL(this.referencePreviews[index]);
            const files = [...this.referenceFiles], previews = [...this.referencePreviews];
            files[index] = file; previews[index] = URL.createObjectURL(file); this.referenceFiles = files; this.referencePreviews = previews; this.icons();
            try {
                const dimensions = await imageDimensions(file); const values = [...this.referenceDimensions]; values[index] = dimensions; this.referenceDimensions = values;
                if (index === 0) this.matchEditAspect(dimensions);
            } catch (_) {}
        },
        clearReference(index) {
            if (this.referencePreviews[index]) URL.revokeObjectURL(this.referencePreviews[index]);
            const files = [...this.referenceFiles], previews = [...this.referencePreviews];
            const dimensions = [...this.referenceDimensions];
            files[index] = null; previews[index] = ''; dimensions[index] = null; this.referenceFiles = files; this.referencePreviews = previews; this.referenceDimensions = dimensions; this.icons();
        },
        composedPrompt() { return [this.prompt.trim(), STYLE_PROMPTS[this.style] || ''].filter(Boolean).join('\n\n'); },
        extension() { return this.format === 'jpeg' ? 'jpg' : this.format; },
        resultFilename(id) { return `imagine-${this.currentPipeline.id}-${id.slice(-8)}.${this.extension()}`; },

        async generate() {
            if (!this.canGenerate || this.generating) return;
            const references = this.referenceFiles.filter(Boolean);
            const editing = this.currentPipeline.mode !== 'generate';
            const selectedModel = this.selectedModel;
            if (!selectedModel) return;
            if (editing && selectedModel.source === 'cloud' && !window.confirm(this.tr('uploadConfirm', { count: references.length }))) return;
            this.generating = true; this.notice = '';
            const id = globalThis.crypto?.randomUUID?.() || `image-${Date.now()}`;
            const requestedSize = this.requestedSize;
            const item = { id, pipelineId: this.currentPipeline.id, status: 'running', title: this.currentPipeline.name, prompt: this.prompt.trim(), size: requestedSize, modelId: selectedModel.id, modelLabel: selectedModel.label.replace(/^AI2Apps (Cloud|Local) · /, ''), imageUrl: '', filename: this.resultFilename(id), error: '', galleryAssetId: '', adding: false };
            this.results = [item, ...this.results]; this.selectedResultId = id; this.icons();
            try {
                const imageDataUrls = editing ? await Promise.all(references.map(readDataUrl)) : [];
                const result = await responsePayload(await fetch(`${IMAGE_API}/${editing ? 'edits' : 'generations'}`, {
                    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'Idempotency-Key': `imagine-${id}` },
                    body: JSON.stringify({ model: selectedModel.id, prompt: this.composedPrompt(), size: requestedSize, quality: this.quality, outputFormat: this.format, n: 1, ...(editing ? { imageDataUrls } : {}) }),
                }));
                const image = result?.image;
                if (!String(image?.dataUrl || '').startsWith('data:image/')) throw new Error(this.tr('noCloudImage'));
                this.results = this.results.map(entry => entry.id === id ? { ...entry, status: 'succeeded', imageUrl: image.dataUrl, size: image.size || requestedSize } : entry);
                try {
                    const saved = await this.persistResult(this.results.find(entry => entry.id === id));
                    this.results = this.results.map(entry => entry.id === id ? { ...this.historyResult(saved), id } : entry);
                } catch (historyError) {
                    this.notice = this.tr('historySaveFailed', { error: historyError?.message || historyError }); this.noticeTone = 'error';
                }
                try { window.ai2appsShell?.accountChanged?.(); } catch (_) {}
            } catch (error) {
                this.results = this.results.map(entry => entry.id === id ? { ...entry, status: 'failed', error: error?.message || String(error) } : entry);
                this.fail(error);
            }
            finally { this.generating = false; this.icons(); }
        },
        async persistResult(result) {
            if (!result?.imageUrl || !this.appInstanceId()) throw new Error(this.tr('missingInstance'));
            const file = await dataUrlFile(result.imageUrl, result.filename); const form = new FormData();
            form.append('metadata', JSON.stringify({
                pipelineId: result.pipelineId || this.currentPipeline.id, title: result.title, prompt: result.prompt,
                modelId: result.modelId || this.modelId, modelLabel: result.modelLabel, size: result.size,
                quality: this.quality, format: this.format, filename: result.filename,
            }));
            form.append('image', file, file.name);
            return responsePayload(await fetch(HISTORY_API, { method: 'POST', credentials: 'same-origin', headers: this.historyHeaders(), body: form }));
        },
        async removeResult(id) {
            const result = this.results.find(item => item.id === id); if (!result) return;
            if (result.historyId && !window.confirm(this.tr('deleteOneConfirm'))) return;
            try {
                if (result.historyId) {
                    const response = await fetch(`${HISTORY_API}/${encodeURIComponent(result.historyId)}`, { method: 'DELETE', credentials: 'same-origin', headers: this.historyHeaders() });
                    if (!response.ok && response.status !== 404) await responsePayload(response);
                }
                this.results = this.results.filter(item => item.id !== id);
                if (this.selectedResultId === id) this.selectedResultId = this.results[0]?.id || '';
            } catch (error) { this.fail(error); } finally { this.icons(); }
        },
        async clearResults() {
            if (!window.confirm(this.tr('clearAllConfirm'))) return;
            try {
                const response = await fetch(HISTORY_API, { method: 'DELETE', credentials: 'same-origin', headers: this.historyHeaders() });
                if (!response.ok) await responsePayload(response);
                this.results = this.results.filter(item => item.status === 'running'); this.selectedResultId = this.results[0]?.id || '';
            } catch (error) { this.fail(error); } finally { this.icons(); }
        },
        dragGeneratedImage(event, result) {
            if (!event.dataTransfer || result?.status !== 'succeeded' || !result.imageUrl) { event.preventDefault(); return; }
            try {
                event.dataTransfer.effectAllowed = 'copy';
                if (result.imageUrl.startsWith('data:image/')) {
                    const dragFile = dragFileFromDataUrl(result.imageUrl, result.filename);
                    try { event.dataTransfer.items?.add?.(dragFile); } catch (_) {}
                    event.dataTransfer.setData('text/uri-list', result.imageUrl);
                } else {
                    const url = new URL(result.imageUrl, window.location.origin);
                    if (url.origin !== window.location.origin || !url.pathname.startsWith(`${HISTORY_API}/`)) throw new Error(this.tr('invalidHistoryUrl'));
                    event.dataTransfer.setData('text/uri-list', url.href);
                }
                event.dataTransfer.setData('text/plain', result.filename);
                event.dataTransfer.setData('application/x-ai2apps-image-result', JSON.stringify({ name: result.filename, sourceAppId: APP_ID }));
            } catch (error) { event.preventDefault(); this.fail(new Error(this.tr('dragFailed', { error: error?.message || error }))); }
        },
        async addResultToGallery(result) {
            if (!result?.imageUrl || result.adding || result.galleryAssetId) return;
            result.adding = true; this.results = [...this.results];
            try {
                const file = await dataUrlFile(result.imageUrl, result.filename); const form = new FormData(); form.append('file', file, file.name);
                if (this.galleryActiveCollectionId !== 'recent') form.append('collectionId', this.galleryActiveCollectionId);
                form.append('sourceAppId', APP_ID);
                const imported = await responsePayload(await fetch(`${GALLERY_API}/assets/import`, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' }, body: form }));
                result.galleryAssetId = imported.asset?.id || ''; if (!result.galleryAssetId) throw new Error(this.tr('galleryNoAsset'));
                this.$refs.galleryMini?.contentWindow?.postMessage({ type: 'ai2apps.gallery.refresh' }, window.location.origin); this.success(this.tr('addedToGallery', { name: this.galleryActiveCollectionName }));
            } catch (error) { this.fail(error); } finally { result.adding = false; this.results = [...this.results]; this.icons(); }
        },
        downloadResult(event) { if (!this.activeResult?.imageUrl) { event.preventDefault(); return; } if (this.clientEnvironment !== 'desktop') this.success(this.tr('downloadStarted')); },

        async mountGalleryMini(force = false) {
            if (this.galleryMiniLoading || (this.galleryMiniUrl && !force)) return;
            this.galleryMiniLoading = true; this.galleryMiniError = '';
            try {
                const bridge = window.ai2appsShell;
                if (!bridge?.mountMiniEntry) { this.galleryMiniUrl = '/admin/app-content/ai2apps.gallery?surface=mini'; return; }
                const mount = await bridge.mountMiniEntry({ appId: 'ai2apps.gallery', placement: 'sidebar', requestedBy: APP_ID });
                if (!mount?.content_url) throw new Error(this.tr('miniNoUrl')); this.galleryMiniMountId = mount.id || ''; this.galleryMiniUrl = mount.content_url;
            } catch (error) {
                if (String(error?.message || '').includes('Unsupported host mount')) this.galleryMiniUrl = '/admin/app-content/ai2apps.gallery?surface=mini';
                else { this.galleryMiniUrl = ''; this.galleryMiniError = error?.message || this.tr('miniLoadFailed'); }
            } finally { this.galleryMiniLoading = false; this.icons(); }
        },
        openGallery() { if (window.ai2appsShell?.openEntry) window.ai2appsShell.openEntry({ appId: 'ai2apps.gallery' }); else window.open('/apps/ai2apps.gallery', '_blank', 'noopener'); },
        handleGalleryMessage(event) {
            if (event.origin !== window.location.origin || event.source !== this.$refs.galleryMini?.contentWindow || event.data?.type !== 'ai2apps.gallery.collection-changed') return;
            this.galleryActiveCollectionId = String(event.data.collectionId || 'recent'); this.galleryActiveCollectionName = String(event.data.collectionName || 'Recent');
        },
        handleWorkspaceDrag(event) {
            const types = Array.from(event.dataTransfer?.types || []);
            if (types.includes('application/x-ai2apps-image-result')) return;
            event.preventDefault(); this.galleryDragActive = true;
        },
        handleDragLeave(event) { if (!event.currentTarget.contains(event.relatedTarget)) { this.galleryDragActive = false; this.gallerySlotTarget = null; } },
        enterGallerySlot(index) { this.galleryDragActive = false; this.gallerySlotTarget = index; },
        leaveGallerySlot(event, index) { if (this.gallerySlotTarget === index && !event.currentTarget.contains(event.relatedTarget)) this.gallerySlotTarget = null; },
        async handleGalleryDrop(event, imageSlot = null) {
            this.galleryDragActive = false; this.gallerySlotTarget = null;
            try {
                let file = event.dataTransfer?.files?.[0] || null;
                if (!file) {
                    const assetId = event.dataTransfer?.getData('application/x-ai2apps-gallery-asset') || '';
                    const uri = String(event.dataTransfer?.getData('text/uri-list') || '').split('\n').find(line => line && !line.startsWith('#')) || '';
                    if (!assetId || !uri) return;
                    const url = new URL(uri, window.location.origin);
                    if (url.origin !== window.location.origin || !url.pathname.startsWith(`${GALLERY_API}/assets/`) || !url.pathname.endsWith('/content')) throw new Error(this.tr('currentGalleryOnly'));
                    const response = await fetch(url.href, { credentials: 'same-origin' }); if (!response.ok) throw new Error(this.tr('readGalleryFailed', { status: response.status }));
                    const blob = await response.blob(); file = new File([blob], String(event.dataTransfer?.getData('text/plain') || `gallery-${assetId}`).replace(/[\\/]/g, '-'), { type: blob.type });
                }
                if (!String(file.type || '').startsWith('image/')) throw new Error(this.tr('appImageOnly'));
                if (!this.currentPipeline.needsImages) this.pipelineId = 'image-edit';
                const limit = this.currentPipeline.maxImages;
                const empty = Array.from({ length: limit }, (_, index) => index).find(index => !this.referenceFiles[index]);
                const target = imageSlot !== null ? Number(imageSlot) : (empty ?? 0); await this.setReference(Math.min(target, limit - 1), file);
            } catch (error) { this.fail(error); }
        },
    }; };
})();
