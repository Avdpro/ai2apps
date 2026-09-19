(() => {
    'use strict';
    const APP_ID = 'ai2apps.imagine-studio';
    const IMAGE_API = '/v1/images';
    const GALLERY_API = '/v1/platform/gallery';
    const CLOUD_MODELS_API = '/v1/platform/cloud/ai/models';
    const LOCAL_MODELS_API = '/v1/platform/imagine-studio/models';
    const HISTORY_API = '/v1/platform/imagine-studio/results';
    const STUDIO_API = '/v1/platform/imagine-studio';
    const LAYOUT_KEY = 'ai2apps.imagine-studio.layout.v1';
    const DISCOVERY_KEY = 'ai2apps.imagine-studio.discovery.v1';
    const STYLE_KEY = 'ai2apps.imagine-studio.image-style.v1';
    const ADJUSTMENT_PRESETS_KEY = 'ai2apps.imagine-studio.adjustment-presets.v1';
    const ADJUSTMENT_LOCK_KEY = 'ai2apps.imagine-studio.adjustment-lock.v1';
    const ADJUSTMENT_SELECTED_PRESET_KEY = 'ai2apps.imagine-studio.adjustment-selected-preset.v1';
    const GALLERY_MINI_FALLBACK_URL = '/admin/app-content/ai2apps.gallery?surface=mini';
    const DEFAULT_CLOUD_MODEL = 'cloud/ai2apps/openai/gpt-image-2';
    const STYLE_TRANSFER_INSTRUCTION = 'Restyle the source image in the selected visual style. Preserve the main subject, identity, pose, composition, geometry, and important content unless the additional instructions explicitly request a change. Change the visual rendering, materials, lighting, color treatment, and texture to match the target style.';
    const GROUP_PHOTO_INSTRUCTION = 'Create one natural, coherent group photograph containing every person from the person reference images exactly once. Preserve each person\'s recognizable identity, facial features, apparent age, skin tone, hairstyle, and body characteristics. Keep the people distinct: do not merge identities, duplicate anyone, omit anyone, or introduce extra people. Use the final reference image only as the background when a background image is supplied. Make lighting, scale, perspective, shadows, eye lines, anatomy, and contact between people physically consistent.';
    const GOOGLE_FLASH_MODEL = 'google/gemini-3.1-flash-image';
    const GOOGLE_SIZE_LABELS = {
        '1024x1024': { size: '1024×1024', ratio: '1:1' },
        '1536x1024': { size: '1264×848', ratio: '3:2' },
        '1024x1536': { size: '848×1264', ratio: '2:3' },
    };
    const LEGACY_SIZE_CAPABILITY = {
        mode: 'fixed', default: '1024x1024', auto: false,
        width: { min: 16, max: 1536, multipleOf: 16 }, height: { min: 16, max: 1536, multipleOf: 16 },
        minPixels: 1048576, maxPixels: 1572864, maxAspectRatio: 1.5, experimentalAbovePixels: Number.MAX_SAFE_INTEGER,
        presets: ['1024x1024', '1536x1024', '1024x1536'],
    };
    const TRANSLATIONS = {
        zh: {
            samplingSteps: '采样步数', redrawStrength: '重绘强度', zImageHint: 'Z-Image Turbo 默认 8 步。图生图是重绘而非指令编辑；请描述目标画面。强度越高，原图变化越大。', localEditRun: '本地图片编辑', localGenerateRun: '本地图片生成',
            refreshRunsHint: '刷新任务状态和生成结果，不会重新生成图片或额外扣费。',
            appName: '创意画坊', appSubtitle: 'Imagine Studio · AI 视觉创作台', cloudGenerate: 'Cloud 生成', localGenerate: '本地生成', configureLocal: '配置本地模型', installMoreModels: '安装更多模型', noModelsAvailable: '暂无可用模型', configuringLocal: '正在配置…', localConfigured: '本地绘图模型已配置', localAlreadyReady: '本地绘图模型已可用', refresh: '刷新', assets: '素材', installed: '已安装', specializedPipeline: '规划中的 Mini-Apps', coming: '即将推出', workspaceNav: 'Imagine Studio 工作区导航', pipelineAssets: 'Mini-Apps 与素材', pipelineList: 'Mini-App 列表', galleryAssets: 'Gallery 素材', pipelineWebUI: '当前 Mini-App 创作界面', renderWorkspace: '渲染工作区',
            characterDesign: '角色设计', characterDesignSummary: '角色设定与多视图一致性', productPhoto: '商品摄影', productPhotoSummary: '布景、灯光与品牌模板', comicStoryboard: '漫画分镜', comicStoryboardSummary: '角色连续性与分镜排版', coderNote: '可在 Coder 中创建和扩展 Mini-App。',
            openGallery: '打开完整 Gallery', loadingGallery: '正在载入素材库…', retry: '重试', galleryHelp: '将图片拖到中间工作区的指定 Slot。', currentPipeline: 'CURRENT MINI-APP', builtInPipeline: 'AI2Apps 官方 Mini-App', cloudReady: 'Cloud 就绪', create: 'CREATE', modelReady: '模型就绪',
            referenceAlt: '参考素材', primaryImage: '主图片', referenceImage: '参考图', required: '必选', optional: '可选', cloudDisclosure: '生成时会将提示词和所选图片发送至 AI2Apps Cloud；每次发送图片前都会请求确认。', localDisclosure: '提示词和所选图片只由本机已安装的 AI2Apps 模型处理。', prompt: '提示词', model: '模型', modelHint: '可选择 Cloud 或已安装的本地绘图模型', canvasSize: '画面尺寸', sourceImage: '原图', matchedRatio: '已匹配原图比例', flexibleSize: 'Cloud 灵活尺寸 · 最高 4K', localSize: '本地模型尺寸 · 按模型能力', fixedSize: '固定尺寸 · 1:1 / 3:2 / 2:3', googleFixedSize: 'Google 当前真实 1K 输出尺寸', quality: '质量', width: '宽度', height: '高度', multipleOf: 'px · 必须是 {value} 的倍数', swapSize: '交换宽高', experimentalSize: '当前尺寸属于 2K+ 实验性输出，生成更慢且点数消耗可能更高。', advanced: '高级设置', visualStyle: '视觉风格', unspecified: '不指定', photorealistic: '写实摄影', illustration: '精致插画', anime: '动画风格', ink: '水墨画', product: '商业产品图', outputFormat: '输出格式', cloudSubmitHint: '通过 AI2Apps Cloud 生成；完成后可下载或加入 Gallery 当前目录', localSubmitHint: '使用本机模型生成；完成后可下载或加入 Gallery 当前目录', generating: '正在生成…', startGenerate: '开始生成', output: 'OUTPUT', results: '生成结果', clearHistory: '清空生成历史', dragToGallery: '拖到 Gallery', waiting: '等待生成', waitingHint: '生成的图片会显示在这里', addedGallery: '已加入 Gallery', addGallery: '加入 Gallery', download: '下载', generationHistory: '生成记录', resultCount: '{count} 个结果', cloudGenerating: 'Cloud 生成中', localGenerating: '本地生成中', noResults: '还没有结果', noResultsHint: '从左侧选择 Pipeline 开始创作', completed: '已完成', failed: '失败', remove: '移除', deleteHistory: '删除历史', dropIntoSlot: '放入图片 Slot', dropIntoSlotHint: '拖到指定 Slot 可控制素材顺序', autoSize: 'Auto · 根据提示词选择', customSize: '自定义尺寸…',
            textImageName: '文生图', textImageSummary: '从文字生成完整画面', textImageDescription: '文字描述、构图与风格控制', textImageAction: '生成文生图', textImageRun: 'Cloud 图片生成', textImagePlaceholder: '描述主体、环境、构图、光线、色彩与风格，例如：\n雨后的东京小巷，电影感广角镜头，霓虹灯倒映在路面，细腻写实摄影。',
            editName: '图片编辑', editSummary: '按提示修改一张图片', editDescription: '保留原图结构并执行定向修改', editAction: '编辑图片', editRun: 'Cloud 图片编辑', editPlaceholder: '描述需要修改的内容，例如：\n保留人物与构图，将背景改成日落海岸，并统一暖金色光线。',
            styleTransferName: '更换图片风格', styleTransferSummary: '将一张图片转换为另一种视觉风格', styleTransferDescription: '优先使用 OpenAI，在保留主体与构图的同时重绘视觉风格', styleTransferAction: '更换图片风格', styleTransferRun: 'Cloud 图片风格转换', styleTransferPlaceholder: '可选：补充需要保留或改变的细节，例如：\n保留人物面部和服装轮廓，背景可以更具绘画感。',
            referenceName: '参考图创作', referenceSummary: '组合多张图片进行创作', referenceDescription: '使用最多四张参考图控制主体、风格与构图', referenceAction: '基于参考图创作', referenceRun: 'Cloud 参考图生成', referencePlaceholder: '说明每张参考图的用途以及希望生成的画面，例如：\n采用图 1 的人物、图 2 的服装和图 3 的色彩风格，生成正面角色海报。',
            groupPhotoName: '合影', groupPhotoSummary: '把多张人物照片合成为自然合影', groupPhotoDescription: '提供 2–3 张人物图与背景图或描述，控制合影的气氛和姿势', groupPhotoAction: '生成合影', groupPhotoRun: 'Cloud 合影生成', groupPhotoPlaceholder: '可选：补充服装、镜头、构图或必须保留的细节。',
            groupPhotoPerson: '人物 {number}', groupPhotoBackgroundImage: '背景图', groupPhotoBackground: '背景描述', groupPhotoBackgroundPlaceholder: '没有背景图时必填，例如：傍晚的海边草坪，远处有暖色灯串。', groupPhotoAtmosphere: '气氛', groupPhotoAtmospherePlaceholder: '例如：温暖、亲密、自然抓拍、轻松欢乐。', groupPhotoPose: '姿势与互动', groupPhotoPosePlaceholder: '例如：三人并肩站立，中间人物挽着两侧人物，大家看向镜头。', groupPhotoRequirements: '至少添加 2 张人物图；背景图与背景描述任选其一。最多支持 3 人。', groupPhotoNeedPeople: '请至少添加 2 张人物图片。', groupPhotoNeedBackground: '请添加背景图，或填写背景描述。',
            requestFailed: '请求失败 ({status})', cannotRead: '无法读取 {name}', cannotReadDimensions: '无法读取图片尺寸。', resultNotDraggable: '生成结果不是可拖拽的图片数据。', invalidSize: '请输入有效的宽度和高度。', maxEdge: '宽和高均不能超过 {max}px。', alignedSize: '宽和高必须是 {value} 的倍数。', minPixels: '总像素不能少于 {value}。', maxPixels: '总像素不能超过 {value}。', maxAspect: '长短边比例不能超过 {value}:1。', onlyFixed: '当前 Cloud 版本只支持三个固定尺寸。', sourceAspectUnsupported: '原图比例超过 Cloud 支持的 {value}:1，已改用 Auto 尺寸。', invalidSlot: '图片 Slot 只接受 PNG、JPEG 或 WebP。', uploadConfirm: '本次生成会将提示词和 {count} 张所选图片上传到 AI2Apps Cloud 图像模型处理。是否继续？', noCloudImage: 'Cloud 模型没有返回可用图片。', historySaveFailed: '图片已生成，但本地历史保存失败：{error}', missingInstance: '缺少 App Instance，无法保存生成历史。', deleteOneConfirm: '从 Imagine Studio 历史中永久删除这张图片？', clearAllConfirm: '永久清空 Imagine Studio 的全部生成历史？此操作不可恢复。', invalidHistoryUrl: '历史图片地址无效。', dragFailed: '无法拖拽这张图片：{error}', galleryNoAsset: 'Gallery 没有返回资产 ID。', addedToGallery: '已加入 Gallery · {name}', downloadStarted: '下载已开始，请在浏览器下载列表中查看。', miniNoUrl: 'Gallery Mini Entry 未返回可用地址。', miniLoadFailed: '无法载入 Gallery Mini Entry。', currentGalleryOnly: '只接受当前 Gallery 中的图片素材。', readGalleryFailed: '无法读取 Gallery 素材 ({status})', appImageOnly: 'Imagine Studio 的素材 Slot 只接受图片。',
        },
        en: {
            samplingSteps: 'Sampling steps', redrawStrength: 'Redraw strength', zImageHint: 'Z-Image Turbo defaults to 8 steps. Img2Img redraws rather than follows edit instructions: describe the desired image. Higher strength changes more of the source.', localEditRun: 'Local image edit', localGenerateRun: 'Local image generation',
            refreshRunsHint: 'Refresh task status and results. Does not regenerate images or incur additional charges.',
            appName: 'Imagine Studio', appSubtitle: 'AI visual creation studio', cloudGenerate: 'Cloud generation', localGenerate: 'Local generation', configureLocal: 'Configure local model', installMoreModels: 'Install more models', noModelsAvailable: 'No available models', configuringLocal: 'Configuring…', localConfigured: 'Local image model configured', localAlreadyReady: 'A local image model is already ready', refresh: 'Refresh', assets: 'Assets', installed: 'Installed', specializedPipeline: 'Planned Mini-Apps', coming: 'COMING SOON', workspaceNav: 'Imagine Studio workspace navigation', pipelineAssets: 'Mini-Apps and assets', pipelineList: 'Mini-App list', galleryAssets: 'Gallery assets', pipelineWebUI: 'Current Mini-App workspace', renderWorkspace: 'Render workspace',
            characterDesign: 'Character Design', characterDesignSummary: 'Consistent character sheets and multi-view design', productPhoto: 'Product Photography', productPhotoSummary: 'Sets, lighting, and brand templates', comicStoryboard: 'Comic Storyboards', comicStoryboardSummary: 'Character continuity and panel layouts', coderNote: 'Create and extend Mini-Apps in Coder.',
            openGallery: 'Open full Gallery', loadingGallery: 'Loading asset library…', retry: 'Retry', galleryHelp: 'Drag an image into a specific Slot in the workspace.', currentPipeline: 'CURRENT MINI-APP', builtInPipeline: 'Official AI2Apps Mini-App', cloudReady: 'Cloud ready', create: 'CREATE', modelReady: 'Model ready',
            referenceAlt: 'Reference asset', primaryImage: 'Primary image', referenceImage: 'Reference', required: 'Required', optional: 'Optional', cloudDisclosure: 'Your prompt and selected images are sent to AI2Apps Cloud for generation. You will be asked to confirm before images are uploaded.', localDisclosure: 'Your prompt and selected images are processed only by the installed AI2Apps model on this device.', prompt: 'Prompt', model: 'Model', modelHint: 'Choose an AI2Apps Cloud model or an installed local image model', canvasSize: 'Canvas size', sourceImage: 'Source', matchedRatio: 'source aspect ratio matched', flexibleSize: 'Flexible Cloud sizes · up to 4K', localSize: 'Local model sizes · capability-aware', fixedSize: 'Fixed sizes · 1:1 / 3:2 / 2:3', googleFixedSize: 'Current Google 1K output dimensions', quality: 'Quality', width: 'Width', height: 'Height', multipleOf: 'px · must be a multiple of {value}', swapSize: 'Swap width and height', experimentalSize: 'This is an experimental 2K+ output. It may generate more slowly and use more points.', advanced: 'Advanced settings', visualStyle: 'Visual style', unspecified: 'Unspecified', photorealistic: 'Photorealistic', illustration: 'Refined illustration', anime: 'Animation', ink: 'Ink wash', product: 'Commercial product', outputFormat: 'Output format', cloudSubmitHint: 'Generate with AI2Apps Cloud, then download or add to the current Gallery folder', localSubmitHint: 'Generate on this device, then download or add to the current Gallery folder', generating: 'Generating…', startGenerate: 'Generate', output: 'OUTPUT', results: 'Results', clearHistory: 'Clear generation history', dragToGallery: 'Drag to Gallery', waiting: 'Ready to create', waitingHint: 'Generated images will appear here', addedGallery: 'Added to Gallery', addGallery: 'Add to Gallery', download: 'Download', generationHistory: 'Generation history', resultCount: '{count} results', cloudGenerating: 'Generating in Cloud', localGenerating: 'Generating locally', noResults: 'No results yet', noResultsHint: 'Choose a Mini-App to start creating', completed: 'Completed', failed: 'Failed', remove: 'Remove', deleteHistory: 'Delete history', dropIntoSlot: 'Drop into an image Slot', dropIntoSlotHint: 'Drop on a specific Slot to control asset order', autoSize: 'Auto · choose from prompt', customSize: 'Custom size…',
            textImageName: 'Text to Image', textImageSummary: 'Create a complete image from text', textImageDescription: 'Prompt, composition, and style controls', textImageAction: 'Create from text', textImageRun: 'Cloud image generation', textImagePlaceholder: 'Describe the subject, setting, composition, lighting, colors, and style. For example:\nA rain-soaked Tokyo alley, cinematic wide-angle view, neon reflections, detailed realistic photography.',
            editName: 'Image Edit', editSummary: 'Modify one image with a prompt', editDescription: 'Preserve the source structure while making targeted changes', editAction: 'Edit image', editRun: 'Cloud image edit', editPlaceholder: 'Describe the changes. For example:\nKeep the person and composition, replace the background with a sunset coast, and use warm golden lighting.',
            styleTransferName: 'Change Image Style', styleTransferSummary: 'Transform one image into another visual style', styleTransferDescription: 'Prefer OpenAI and restyle the image while preserving its subject and composition', styleTransferAction: 'Change image style', styleTransferRun: 'Cloud image style transfer', styleTransferPlaceholder: 'Optional: describe details to preserve or change. For example:\nKeep the face and clothing silhouette; make the background more painterly.',
            referenceName: 'Reference Creation', referenceSummary: 'Create with multiple reference images', referenceDescription: 'Use up to four references to control subject, style, and composition', referenceAction: 'Create from references', referenceRun: 'Cloud reference generation', referencePlaceholder: 'Explain how each reference should be used. For example:\nUse the person from image 1, clothing from image 2, and colors from image 3 to create a front-facing character poster.',
            groupPhotoName: 'Group Photo', groupPhotoSummary: 'Compose several people into one natural photo', groupPhotoDescription: 'Use 2–3 person images plus a background image or description, with atmosphere and pose controls', groupPhotoAction: 'Create group photo', groupPhotoRun: 'Cloud group photo', groupPhotoPlaceholder: 'Optional: add wardrobe, camera, composition, or preservation details.',
            groupPhotoPerson: 'Person {number}', groupPhotoBackgroundImage: 'Background image', groupPhotoBackground: 'Background description', groupPhotoBackgroundPlaceholder: 'Required without a background image, for example: a seaside lawn at dusk with warm string lights.', groupPhotoAtmosphere: 'Atmosphere', groupPhotoAtmospherePlaceholder: 'For example: warm, intimate, candid, relaxed, and joyful.', groupPhotoPose: 'Poses and interaction', groupPhotoPosePlaceholder: 'For example: three people stand shoulder to shoulder, the middle person links arms, everyone looks at camera.', groupPhotoRequirements: 'Add at least 2 person images and either a background image or description. Up to 3 people are supported.', groupPhotoNeedPeople: 'Add at least 2 person images.', groupPhotoNeedBackground: 'Add a background image or enter a background description.',
            requestFailed: 'Request failed ({status})', cannotRead: 'Could not read {name}', cannotReadDimensions: 'Could not read the image dimensions.', resultNotDraggable: 'The generated result is not draggable image data.', invalidSize: 'Enter a valid width and height.', maxEdge: 'Width and height cannot exceed {max}px.', alignedSize: 'Width and height must be multiples of {value}.', minPixels: 'Total pixels cannot be less than {value}.', maxPixels: 'Total pixels cannot exceed {value}.', maxAspect: 'The long-to-short edge ratio cannot exceed {value}:1.', onlyFixed: 'This Cloud version supports only three fixed sizes.', sourceAspectUnsupported: 'The source aspect ratio exceeds the Cloud limit of {value}:1. Size was changed to Auto.', invalidSlot: 'Image Slots accept PNG, JPEG, or WebP only.', uploadConfirm: 'This generation will upload the prompt and {count} selected image(s) to the AI2Apps Cloud image model. Continue?', noCloudImage: 'The Cloud model did not return a usable image.', historySaveFailed: 'The image was generated, but local history could not be saved: {error}', missingInstance: 'The App Instance is missing, so generation history cannot be saved.', deleteOneConfirm: 'Permanently delete this image from Imagine Studio history?', clearAllConfirm: 'Permanently clear all Imagine Studio generation history? This cannot be undone.', invalidHistoryUrl: 'The history image URL is invalid.', dragFailed: 'Could not drag this image: {error}', galleryNoAsset: 'Gallery did not return an asset ID.', addedToGallery: 'Added to Gallery · {name}', downloadStarted: 'Download started. Check your browser downloads.', miniNoUrl: 'Gallery Mini Entry did not return a usable URL.', miniLoadFailed: 'Could not load Gallery Mini Entry.', currentGalleryOnly: 'Only images from the current Gallery are accepted.', readGalleryFailed: 'Could not read the Gallery asset ({status})', appImageOnly: 'Imagine Studio Slots accept images only.',
        },
    };
    Object.assign(TRANSLATIONS.zh, {
        miniApps: 'Mini-Apps', miniAppsAssets: 'Mini-Apps 与素材', miniAppList: 'Mini-App 列表', miniAppWebUI: '当前 Mini-App 创作界面', currentMiniApp: 'CURRENT MINI-APP', officialMiniApp: 'AI2Apps 官方 Mini-App', specializedPipeline: '规划中的 Mini-Apps', coderNote: '可在 Coder 中创建和扩展 Mini-App。', searchMiniApps: '搜索 Mini-App', filterMiniApps: '筛选 Mini-App', all: '全部', favorites: '收藏', favorite: '收藏 Mini-App', recent: '最近', noMiniApps: '没有匹配的 Mini-App', createInCoder: '在 Coder 中创建', ready: 'Ready', unavailable: 'Unavailable', broken: 'Broken', needsSetup: 'Needs setup', renderWorkspace: '渲染工作区', refreshRuns: '刷新 Run', runHistory: 'Run 历史', runCount: '{count} 个 Run', placement: '挂载位置', started: '开始时间', steps: 'Steps', artifacts: 'Artifacts', queued: '排队中', running: '运行中', waiting_input: '等待继续', succeeded: '已完成', cancelled: '已取消', expired: '已过期', pending: '等待中', skipped: '已跳过', cancel: '取消', toggleMiniApps: '折叠或展开 Mini-Apps', toggleOutput: '折叠或展开输出', dismiss: '关闭提示', mobileNav: 'Imagine Studio 页面', noResultsHint: '选择 Mini-App 开始创作',
        characterDesignName: '角色设计', characterDesignDescription: '角色、风格和多视图一致性项目', characterDesignAction: '设计角色', characterDesignRun: '角色设计', characterDesignPlaceholder: '描述角色、服装、表情和需要的视图。', productPhotoName: '商品摄影', productPhotoDescription: '商品布景、灯光和品牌版式项目', productPhotoAction: '制作商品海报', productPhotoRun: '商品海报', productPhotoPlaceholder: '描述商品、布景、灯光和品牌风格。', comicStoryboardName: '漫画分镜', comicStoryboardDescription: '漫画与分镜的连续性项目', comicStoryboardAction: '创建漫画分镜', comicStoryboardRun: '漫画分镜', comicStoryboardPlaceholder: '描述角色、场景和镜头顺序。',
        chooseStyle: '选择风格', changeStyle: '更换风格', noStyle: '无风格', noStyleHint: '仅使用提示词，不附加风格描述', styleDialogTitle: '选择视觉风格', styleDialogHint: '这是所有图片 Mini-App 共用的核心设置；选中的风格提示词会随生成或编辑请求一起发送。', styleCategories: '风格分类', styleCount: '{count} 种风格', applyStyle: '应用风格', selectedStyle: '已选风格',
        styleRequired: '请选择目标风格（必选）', additionalInstructions: '补充说明（可选）', openAIPreferred: '此工作流优先使用 OpenAI 图片模型',
        adjustName: '调整图片', adjustSummary: '裁剪、旋转与精细调色', adjustDescription: '像照片 App 一样在本机调整构图、光线、颜色和细节', adjustAction: '调整图片', adjustRun: '本地图片调整', adjustPlaceholder: '', localAdjustments: '本机调整', adjustmentReady: '调整工具就绪', chooseAdjustmentImage: '选择要调整的图片', replaceImage: '更换图片', crop: '裁剪', rotateLeft: '向左旋转', rotateRight: '向右旋转', flipHorizontal: '水平翻转', flipVertical: '垂直翻转', undo: '撤销', redo: '重做', resetAdjustments: '复原', adjustmentControls: '调整', exportAdjustment: '完成并保存', exportingAdjustment: '正在保存…', adjustmentSubmitHint: '在本机按原始分辨率渲染，并保存为可下载、可加入 Gallery 的 Artifact', adjustOriginal: '原始比例', adjustFree: '自由', adjustExposure: '曝光', adjustBrilliance: '鲜明度', adjustHighlights: '高光', adjustShadows: '阴影', adjustContrast: '对比度', adjustBrightness: '亮度', adjustSaturation: '饱和度', adjustVibrance: '自然饱和度', adjustBlackPoint: '黑点', adjustColorBalance: '颜色平衡', adjustWarmth: '色温', adjustTint: '色调', adjustSharpness: '锐度', adjustDefinition: '清晰度', adjustNoiseReduction: '噪点消除', adjustVignette: '晕影', adjustmentMissingImage: '请先选择一张要调整的图片。', adjustmentFailed: '图片调整失败', adjustmentPreset: '调整方案', newPreset: '新方案', presetName: '方案名称', savePreset: '保存方案', updatePreset: '更新方案', managePresets: '管理方案', noSavedPresets: '还没有保存的调整方案', presetNameRequired: '请先输入方案名称。', presetSaved: '调整方案已保存。', presetUpdated: '调整方案已更新。', renamePreset: '改名', deletePreset: '删除', renamePresetPrompt: '输入新的方案名称', deletePresetConfirm: '删除调整方案“{name}”？', lockAdjustment: '锁定调整', lockAdjustmentHint: '拖入新图时沿用当前参数', batchProcess: '批量处理', batchTitle: '批量调整图片', batchHint: '把当前调整方案应用到一组图片。处理在本机完成。', batchInput: '输入来源', batchFiles: '多个文件', batchFolder: '本地目录', batchGallery: 'Gallery', chooseFiles: '选择多个文件', chooseFolder: '选择目录', batchFileCount: '已选择 {count} 张图片', batchGallerySummary: '当前 Gallery：{name}', batchOutput: '输出方式', overwrite: '覆盖原图', saveAs: '另存为', chooseOutputFolder: '选择存储目录', batchOutputFolderNeedsFile: '请选择一个至少包含一个文件的目录；系统会把它作为输出目录。', batchChooseInput: '请先选择要处理的图片。', batchChooseOutput: '请选择另存位置。', batchOverwriteConfirm: '覆盖会替换原文件或 Gallery 资产，且无法撤销。继续吗？', batchNoImages: '所选来源中没有可处理的图片。', batchNativePathUnavailable: '无法取得“{name}”的本地路径，请在 AI2Apps App 中重新选择。', batchCompleted: '已完成 {count} 张图片的批量调整。', batchProgress: '已完成 {done}/{total}', startBatch: '开始批量处理', batchProcessing: '处理中…',
    });
    Object.assign(TRANSLATIONS.en, {
        miniApps: 'Mini-Apps', miniAppsAssets: 'Mini-Apps and assets', miniAppList: 'Mini-App list', miniAppWebUI: 'Current Mini-App workspace', currentMiniApp: 'CURRENT MINI-APP', officialMiniApp: 'Official AI2Apps Mini-App', specializedPipeline: 'Planned Mini-Apps', coderNote: 'Create and extend Mini-Apps in Coder.', searchMiniApps: 'Search Mini-Apps', filterMiniApps: 'Filter Mini-Apps', all: 'All', favorites: 'Favorites', favorite: 'Favorite Mini-App', recent: 'Recent', noMiniApps: 'No matching Mini-Apps', createInCoder: 'Create in Coder', ready: 'Ready', unavailable: 'Unavailable', broken: 'Broken', needsSetup: 'Needs setup', renderWorkspace: 'Render workspace', refreshRuns: 'Refresh Runs', runHistory: 'Run history', runCount: '{count} Runs', placement: 'Placement', started: 'Started', steps: 'Steps', artifacts: 'Artifacts', queued: 'Queued', running: 'Running', waiting_input: 'Waiting to continue', succeeded: 'Succeeded', cancelled: 'Cancelled', expired: 'Expired', pending: 'Pending', skipped: 'Skipped', cancel: 'Cancel', toggleMiniApps: 'Collapse or expand Mini-Apps', toggleOutput: 'Collapse or expand output', dismiss: 'Dismiss message', mobileNav: 'Imagine Studio pages', noResultsHint: 'Choose a Mini-App to start creating',
        characterDesignName: 'Character Design', characterDesignDescription: 'A character, style, and multi-view consistency project', characterDesignAction: 'Design a character', characterDesignRun: 'Character design', characterDesignPlaceholder: 'Describe the character, wardrobe, expressions, and required views.', productPhotoName: 'Product Photography', productPhotoDescription: 'A product staging, lighting, and brand layout project', productPhotoAction: 'Create a product poster', productPhotoRun: 'Product poster', productPhotoPlaceholder: 'Describe the product, set, lighting, and brand style.', comicStoryboardName: 'Comic Storyboards', comicStoryboardDescription: 'A comic and storyboard continuity project', comicStoryboardAction: 'Create a storyboard', comicStoryboardRun: 'Comic storyboard', comicStoryboardPlaceholder: 'Describe the characters, scenes, and shot sequence.',
        chooseStyle: 'Choose style', changeStyle: 'Change style', noStyle: 'No style', noStyleHint: 'Use only your prompt without an added style description', styleDialogTitle: 'Choose a visual style', styleDialogHint: 'This is a core setting shared by every image Mini-App. Its style prompt is included with generation and edit requests.', styleCategories: 'Style categories', styleCount: '{count} styles', applyStyle: 'Apply style', selectedStyle: 'Selected style',
        styleRequired: 'Choose a target style (required)', additionalInstructions: 'Additional instructions (optional)', openAIPreferred: 'This workflow prefers an OpenAI image model',
        adjustName: 'Adjust Image', adjustSummary: 'Crop, rotate, and fine-tune color', adjustDescription: 'Adjust composition, light, color, and detail locally, like a photo app', adjustAction: 'Adjust image', adjustRun: 'Local image adjustment', adjustPlaceholder: '', localAdjustments: 'On-device adjustments', adjustmentReady: 'Adjustment tools ready', chooseAdjustmentImage: 'Choose an image to adjust', replaceImage: 'Replace image', crop: 'Crop', rotateLeft: 'Rotate left', rotateRight: 'Rotate right', flipHorizontal: 'Flip horizontally', flipVertical: 'Flip vertically', undo: 'Undo', redo: 'Redo', resetAdjustments: 'Reset', adjustmentControls: 'Adjust', exportAdjustment: 'Done and save', exportingAdjustment: 'Saving…', adjustmentSubmitHint: 'Render locally at the cropped source resolution and save a downloadable, Gallery-ready Artifact', adjustOriginal: 'Original', adjustFree: 'Free', adjustExposure: 'Exposure', adjustBrilliance: 'Brilliance', adjustHighlights: 'Highlights', adjustShadows: 'Shadows', adjustContrast: 'Contrast', adjustBrightness: 'Brightness', adjustSaturation: 'Saturation', adjustVibrance: 'Vibrance', adjustBlackPoint: 'Black Point', adjustColorBalance: 'Color Balance', adjustWarmth: 'Warmth', adjustTint: 'Tint', adjustSharpness: 'Sharpness', adjustDefinition: 'Definition', adjustNoiseReduction: 'Noise Reduction', adjustVignette: 'Vignette', adjustmentMissingImage: 'Choose an image to adjust first.', adjustmentFailed: 'Image adjustment failed', adjustmentPreset: 'Adjustment preset', newPreset: 'New preset', presetName: 'Preset name', savePreset: 'Save preset', updatePreset: 'Update preset', managePresets: 'Manage presets', noSavedPresets: 'No saved adjustment presets yet', presetNameRequired: 'Enter a preset name first.', presetSaved: 'Adjustment preset saved.', presetUpdated: 'Adjustment preset updated.', renamePreset: 'Rename', deletePreset: 'Delete', renamePresetPrompt: 'Enter a new preset name', deletePresetConfirm: 'Delete adjustment preset “{name}”?', lockAdjustment: 'Lock adjustment', lockAdjustmentHint: 'Keep current settings for new images', batchProcess: 'Batch process', batchTitle: 'Batch adjust images', batchHint: 'Apply the current adjustments to a group of images. Processing stays on this device.', batchInput: 'Input source', batchFiles: 'Multiple files', batchFolder: 'Local folder', batchGallery: 'Gallery', chooseFiles: 'Choose files', chooseFolder: 'Choose folder', batchFileCount: '{count} image(s) selected', batchGallerySummary: 'Current Gallery: {name}', batchOutput: 'Output mode', overwrite: 'Overwrite originals', saveAs: 'Save as', chooseOutputFolder: 'Choose output folder', batchOutputFolderNeedsFile: 'Choose a folder containing at least one file; the App will use it as the output folder.', batchChooseInput: 'Choose images to process first.', batchChooseOutput: 'Choose an output location.', batchOverwriteConfirm: 'Overwrite will replace the original files or Gallery assets and cannot be undone. Continue?', batchNoImages: 'The selected source contains no supported images.', batchNativePathUnavailable: 'The local path for “{name}” is unavailable. Select it again in the AI2Apps App.', batchCompleted: 'Batch adjustment completed for {count} image(s).', batchProgress: '{done}/{total} completed', startBatch: 'Start batch', batchProcessing: 'Processing…',
    });
    const MINI_APP_DEFS = [
        { id: 'ai2apps.imagine.text-to-image', legacyId: 'text-image', adapter: 'text-to-image', version: '1.0.0', status: 'ready', source: 'official', category: 'quick', mode: 'generate', icon: 'text-cursor-input', needsImages: false, requiresImage: false, maxImages: 0, prefix: 'textImage' },
        { id: 'ai2apps.imagine.image-edit', legacyId: 'image-edit', adapter: 'image-edit', version: '1.0.0', status: 'ready', source: 'official', category: 'edit', mode: 'edit', icon: 'scan-search', needsImages: true, requiresImage: true, maxImages: 1, prefix: 'edit' },
        { id: 'ai2apps.imagine.style-transfer', legacyId: 'style-transfer', adapter: 'style-transfer', version: '1.0.0', status: 'ready', source: 'official', category: 'edit', mode: 'style-transfer', icon: 'wand-sparkles', needsImages: true, requiresImage: true, maxImages: 1, prefix: 'styleTransfer' },
        { id: 'ai2apps.imagine.reference-creation', legacyId: 'reference-create', adapter: 'reference-creation', version: '1.0.0', status: 'ready', source: 'official', category: 'create', mode: 'reference', icon: 'images', needsImages: true, requiresImage: true, maxImages: 4, prefix: 'reference' },
        { id: 'ai2apps.imagine.group-photo', legacyId: 'group-photo', adapter: 'group-photo', version: '1.0.0', status: 'ready', source: 'official', category: 'create', mode: 'group-photo', icon: 'users-round', needsImages: true, requiresImage: true, maxImages: 4, personSlots: 3, backgroundSlot: 3, prefix: 'groupPhoto' },
        { id: 'ai2apps.imagine.adjust-image', legacyId: 'adjust-image', adapter: 'adjust-image', version: '1.0.0', status: 'ready', source: 'official', category: 'edit', mode: 'adjust', icon: 'sliders-horizontal', needsImages: true, requiresImage: true, maxImages: 1, prefix: 'adjust' },
        { id: 'ai2apps.imagine.character-design', adapter: 'character-design', version: 'Planned', status: 'unavailable', source: 'official', category: 'project', mode: 'project', icon: 'user-round-cog', needsImages: true, requiresImage: false, maxImages: 4, prefix: 'characterDesign' },
        { id: 'ai2apps.imagine.product-poster', adapter: 'product-poster', version: 'Planned', status: 'unavailable', source: 'official', category: 'project', mode: 'project', icon: 'shopping-bag', needsImages: true, requiresImage: true, maxImages: 4, prefix: 'productPhoto' },
        { id: 'ai2apps.imagine.comic-storyboard', adapter: 'comic-storyboard', version: 'Planned', status: 'unavailable', source: 'official', category: 'project', mode: 'project', icon: 'panels-top-left', needsImages: true, requiresImage: false, maxImages: 4, prefix: 'comicStoryboard' },
    ];
    function normalizedLocale(value) { return String(value || '').toLowerCase().startsWith('zh') ? 'zh' : 'en'; }
    function translate(locale, key, values = {}) {
        let text = TRANSLATIONS[normalizedLocale(locale)]?.[key] || TRANSLATIONS.en[key] || key;
        Object.entries(values).forEach(([name, value]) => { text = text.replaceAll(`{${name}}`, String(value)); });
        return text;
    }
    function managedCloudModelId(value) {
        const modelId = String(value || '').trim();
        if (!modelId || modelId.startsWith('cloud/')) return modelId;
        return `cloud/ai2apps/${modelId}`;
    }
    function galleryHostUnavailable(error) {
        return /AI2Apps Host did not respond|Unsupported host mount/i.test(String(error?.message || error || ''));
    }
    function localizedMiniApps(locale) {
        return MINI_APP_DEFS.map(item => ({ ...item, name: translate(locale, `${item.prefix}Name`) || item.id, summary: translate(locale, `${item.prefix}Summary`), description: translate(locale, `${item.prefix}Description`) || translate(locale, `${item.prefix}Summary`), actionTitle: translate(locale, `${item.prefix}Action`) || translate(locale, `${item.prefix}Name`), runLabel: translate(locale, `${item.prefix}Run`) || translate(locale, `${item.prefix}Name`), placeholder: translate(locale, `${item.prefix}Placeholder`) }));
    }
    const LEGACY_STYLE_IDS = { illustration: 'digital-painting', ink: 'ink-wash', product: 'photorealistic' };

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
        const match = /^data:([^;,]+)?(;base64)?,(.*)$/s.exec(String(dataUrl || ''));
        if (!match) throw new Error(translate(document.documentElement.lang, 'noCloudImage'));
        const mediaType = match[1] || 'image/png';
        const decoded = match[2] ? atob(match[3]) : decodeURIComponent(match[3]);
        const bytes = new Uint8Array(decoded.length);
        for (let index = 0; index < decoded.length; index += 1) bytes[index] = decoded.charCodeAt(index);
        return new File([bytes], name, { type: mediaType });
    }
    function canvasFile(canvas, name, mediaType = 'image/png') {
        return new Promise((resolve, reject) => {
            canvas.toBlob(blob => {
                if (!blob) { reject(new Error(translate(document.documentElement.lang, 'adjustmentFailed'))); return; }
                resolve(new File([blob], name, { type: blob.type || mediaType }));
            }, mediaType);
        });
    }
    function base64Bytes(bytes) {
        let binary = '';
        for (let offset = 0; offset < bytes.length; offset += 0x8000) {
            binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
        }
        return btoa(binary);
    }
    function nativeFilePath(file) {
        try { return String(file?.mozAI2AppsFullPath || ''); }
        catch (_) { return ''; }
    }
    function selectedDirectory(files) {
        const file = Array.from(files || [])[0];
        const fullPath = nativeFilePath(file), relativePath = String(file?.webkitRelativePath || '');
        if (!fullPath || !relativePath || !fullPath.endsWith(relativePath)) return '';
        return fullPath.slice(0, -relativePath.length).replace(/\/$/, '');
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
    async function loadRenderableImage(file) {
        if (typeof createImageBitmap === 'function') return createImageBitmap(file);
        const url = URL.createObjectURL(file);
        return new Promise((resolve, reject) => {
            const image = new Image(); image.onload = () => { image._objectUrl = url; resolve(image); };
            image.onerror = () => { URL.revokeObjectURL(url); reject(new Error(translate(document.documentElement.lang, 'cannotReadDimensions'))); };
            image.src = url;
        });
    }
    function disposeRenderableImage(image) { if (image?.close) image.close(); if (image?._objectUrl) URL.revokeObjectURL(image._objectUrl); }
    function packageMiniApp(item, locale) {
        const placement = (item.placements || []).find(value => value?.studio === APP_ID) || {};
        return {
            ...item, source: 'package', status: 'ready', mode: `package:${item.id}`, adapter: `package:${item.id}`,
            category: placement.category || 'installed', icon: item.icon || 'blocks', needsImages: false, requiresImage: false, maxImages: 0,
            name: item.name || item.title || item.id, summary: item.summary || item.description || item.provider?.name || 'Installed Package',
            description: item.description || item.summary || item.provider?.name || '', actionTitle: item.name || item.title || item.id,
            locale,
        };
    }
    window.imagineStudioApp = function () { return {
        locale: normalizedLocale(document.documentElement.lang), miniApps: localizedMiniApps(document.documentElement.lang), miniAppId: MINI_APP_DEFS[0].id, leftView: 'mini-apps', prompt: '',
        groupBackgroundDescription: '', groupAtmosphere: '', groupPose: '',
        modelId: DEFAULT_CLOUD_MODEL, models: [], size: '1024x1024', customWidth: 2048, customHeight: 1152,
        sizeCapability: structuredClone(LEGACY_SIZE_CAPABILITY), flexibleSizes: false, pricingVersion: '',
        quality: 'auto', format: 'png', style: '', pendingStyle: '', styleDialogOpen: false, styleCategoryId: '', stylePreferenceLoaded: false,
        adjustState: window.ImagineAdjustEngine?.state?.() || { values: {}, rotation: 0, flipX: false, flipY: false, cropRatio: 'original' }, adjustHistory: [], adjustHistoryIndex: -1, adjustBitmap: null, adjustRenderFrame: 0, adjustmentExporting: false,
        adjustmentLocked: false, adjustmentPresets: [], selectedAdjustmentPresetId: '', adjustmentPresetName: '', adjustmentPresetDialogOpen: false,
        adjustmentBatchOpen: false, adjustmentBatchSource: 'files', adjustmentBatchFiles: [], adjustmentBatchOutputMode: 'save-as', adjustmentBatchOutputDirectory: '', adjustmentBatchBusy: false, adjustmentBatchDone: 0, adjustmentBatchTotal: 0,
        referenceFiles: [], referencePreviews: [], referenceDimensions: [], referenceAssets: [], runs: [], selectedRunId: '', selectedArtifactId: '', generating: false, refreshing: false, configuringLocal: false, currentRunController: null,
        notice: '', noticeTone: 'error', noticeTimer: null, clientEnvironment: 'browser', galleryMiniUrl: '', galleryMiniMountId: '', galleryMiniLoading: false, galleryMiniError: '', galleryMessageHandler: null, hostContextHandler: null,
        chatController: null, chatMiniUrl: '', packageChatBridge: null,
        galleryActiveCollectionId: 'recent', galleryActiveCollectionName: 'Recent', galleryDragActive: false, gallerySlotTarget: null,
        favoriteMiniApps: [], recentMiniApps: [], leftCollapsed: false, rightCollapsed: false, mobileSurface: 'create', draftTimer: null,
        packageMiniAppId: '', packageMiniAppUrl: '', packageMiniAppMountId: '', packageMiniAppLoading: false, packageMiniAppError: '', packageMiniAppReadiness: {}, packageMiniAppSetupBusy: false,

        get currentMiniApp() { return this.miniApps.find(item => item.id === this.miniAppId) || this.miniApps[0]; },
        get currentMiniAppReady() { return this.currentMiniApp?.source !== 'package' || this.packageMiniAppReadiness[this.currentMiniApp.id] === true; },
        get miniAppChatEnabled() { return Boolean(window.AI2AppsMiniAppChat && this.currentMiniApp && (this.currentMiniApp.source !== 'package' || this.currentMiniApp.chat?.enabled === true)); },
        get isAdjustMode() { return this.currentMiniApp.mode === 'adjust'; },
        get isStyleTransferMode() { return this.currentMiniApp.mode === 'style-transfer'; },
        get isGroupPhotoMode() { return this.currentMiniApp.mode === 'group-photo'; },
        get prefersOpenAIModel() { return this.isStyleTransferMode || this.isGroupPhotoMode; },
        get groupPersonFiles() { return this.referenceFiles.slice(0, this.currentMiniApp.personSlots || 0).filter(Boolean); },
        get groupBackgroundFile() { return this.referenceFiles[this.currentMiniApp.backgroundSlot] || null; },
        get groupPhotoReady() { return this.groupPersonFiles.length >= 2 && Boolean(this.groupBackgroundFile || this.groupBackgroundDescription.trim()); },
        get filteredMiniApps() {
            return [...this.miniApps].sort((a, b) => (a.status === 'ready' ? 0 : 1) - (b.status === 'ready' ? 0 : 1));
        },
        get requiredOperation() { return this.currentMiniApp.mode === 'generate' ? 'image_generation' : 'image_edit'; },
        get compatibleModels() {
            const minimum = this.isGroupPhotoMode ? 2 : 1;
            const models = this.models.filter(model => model.operations.includes(this.requiredOperation) && (this.requiredOperation !== 'image_edit' || (model.referenceLimits?.maximum ?? 4) >= minimum));
            if (!this.prefersOpenAIModel) return models;
            return [...models].sort((left, right) => Number(!this.isOpenAIModel(left)) - Number(!this.isOpenAIModel(right)));
        },
        get selectedModel() { return this.models.find(model => model.id === this.modelId) || this.compatibleModels[0] || null; },
        get hasLocalModels() { return this.models.some(model => model.source === 'local'); },
        get usingLocalModel() { return this.selectedModel?.source === 'local'; },
        zImageSteps: 8, zImageRedraw: 75,
        zImageBaseSteps: 30, zImageBaseGuidance: 4, zImageBaseNegativePrompt: '',
        get usingZImageBase() { return this.usingLocalModel && /z-image-base-mlx/.test(this.selectedModel?.id || ''); },
        localEditParameters(model, editing) {
            // Reference KV caching changes Klein edit conditioning, not just speed.
            // Fixed-seed A/B on 2026-09-11 preserved source geometry only without it.
            return editing && model?.source === 'local' && /flux2-klein/i.test(model.id || '')
                ? { use_kv_cache: false } : {};
        },
        get usingZImage() { return this.usingLocalModel && /z[-_]?image/i.test(this.selectedModel?.id || '') && !/z-image-base-mlx/.test(this.selectedModel?.id || ''); },
        zImageParameters() {
            if (this.usingZImageBase) return {
                num_inference_steps: Math.max(1, Math.min(50, Math.round(Number(this.zImageBaseSteps) || 30))),
                guidance: Math.max(1, Math.min(10, Number(this.zImageBaseGuidance) || 4)),
                negative_prompt: this.zImageBaseNegativePrompt.slice(0, 8192),
            };
            if (!this.usingZImage) return {};
            const steps = Math.max(2, Math.min(50, Math.round(Number(this.zImageSteps) || 8)));
            const redraw = Math.max(10, Math.min(90, Number(this.zImageRedraw) || 75));
            // mflux image_strength is the START fraction, not denoising strength.
            return { num_inference_steps: steps, ...(this.currentMiniApp.mode !== 'generate' ? { strength: 1 - redraw / 100 } : {}) };
        },
        get generationModeLabel() { return this.tr(this.isAdjustMode ? 'localAdjustments' : (this.usingLocalModel ? 'localGenerate' : 'cloudGenerate')); },
        get submitHint() { return this.tr(this.isAdjustMode ? 'adjustmentSubmitHint' : (this.usingLocalModel ? 'localSubmitHint' : 'cloudSubmitHint')); },
        get usingGoogleImageModel() { return String(this.selectedModel?.id || '').endsWith(GOOGLE_FLASH_MODEL); },
        get modelSizeHint() { return this.tr(this.usingLocalModel ? 'localSize' : (this.flexibleSizes ? 'flexibleSize' : (this.usingGoogleImageModel ? 'googleFixedSize' : 'fixedSize'))); },
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
        get canGenerate() { const hasInstruction = this.isStyleTransferMode ? Boolean(this.selectedStyle) : (this.isGroupPhotoMode ? this.groupPhotoReady : Boolean(this.prompt.trim())); return this.currentMiniApp.status === 'ready' && Boolean(this.selectedModel) && hasInstruction && !this.sizeError && (!this.currentMiniApp.requiresImage || this.referenceFiles.some(Boolean)); },
        get selectedRun() { return this.runs.find(item => item.id === this.selectedRunId) || this.runs[0] || null; },
        get activeArtifact() { const items = this.selectedRun?.artifacts || []; return items.find(item => item.id === this.selectedArtifactId) || items.find(item => item.final) || items[0] || null; },
        get qualityOptions() { return this.selectedModel?.qualities?.length ? this.selectedModel.qualities : ['auto']; },
        get adjustmentControls() { return window.ImagineAdjustEngine?.controls || []; },
        get adjustmentCropRatios() { return window.ImagineAdjustEngine?.cropRatios || []; },
        get canUndoAdjustment() { return this.adjustHistoryIndex > 0; },
        get canRedoAdjustment() { return this.adjustHistoryIndex >= 0 && this.adjustHistoryIndex < this.adjustHistory.length - 1; },
        get canExportAdjustment() { return Boolean(this.adjustBitmap && this.referenceFiles[0]) && !this.adjustmentExporting; },
        get selectedAdjustmentPreset() { return this.adjustmentPresets.find(item => item.id === this.selectedAdjustmentPresetId) || null; },
        get preservesAdjustmentsForNewImage() { return this.adjustmentLocked || Boolean(this.selectedAdjustmentPresetId); },
        get adjustmentBatchSummary() {
            if (this.adjustmentBatchSource === 'gallery') return this.tr('batchGallerySummary', { name: this.galleryActiveCollectionName });
            return this.tr('batchFileCount', { count: this.adjustmentBatchFiles.length });
        },
        get styleCategories() { return Array.isArray(window.IMAGINE_STYLE_CATALOG) ? window.IMAGINE_STYLE_CATALOG : []; },
        get activeStyleCategory() { return this.styleCategories.find(category => category.id === this.styleCategoryId) || this.styleCategories[0] || { styles: [] }; },
        get allStyles() { return this.styleCategories.flatMap(category => category.styles); },
        get selectedStyle() { return this.allStyles.find(item => item.id === this.style) || null; },
        get pendingSelectedStyle() { return this.allStyles.find(item => item.id === this.pendingStyle) || null; },
        get promptFieldLabel() { return this.tr((this.isStyleTransferMode || this.isGroupPhotoMode) ? 'additionalInstructions' : 'prompt'); },
        get styleSelectionHint() { return this.selectedStyle ? this.localizedName(this.selectedStyle) : this.tr(this.isStyleTransferMode ? 'styleRequired' : 'noStyleHint'); },

        async init() {
            this.clientEnvironment = this.$root?.dataset?.clientEnvironment || 'browser';
            await this.refreshPackageMiniApps();
            this.restorePreferences();
            const pendingPackageMiniAppId = window.AI2AppsStudioMiniApps?.pendingSetup(APP_ID)?.miniAppId;
            if (this.miniApps.some(item => item.source === 'package' && item.id === pendingPackageMiniAppId)) this.miniAppId = pendingPackageMiniAppId;
            if (this.currentMiniApp?.source === 'package') await this.mountPackageMiniApp(this.currentMiniApp);
            this.setupMiniAppChat();
            this.galleryMessageHandler = event => this.handleGalleryMessage(event);
            this.hostContextHandler = event => this.setLocale(event.detail?.locale);
            window.addEventListener('message', this.galleryMessageHandler);
            window.addEventListener('ai2apps:host-context', this.hostContextHandler);
            window.addEventListener('beforeunload', () => this.cleanup(), { once: true });
            this.$watch('modelId', () => this.applySelectedModelCapability());
            await this.refresh();
            const draft = this.packageMiniAppId ? {} : await this.loadDraft(this.miniAppId);
            if (this.prefersOpenAIModel && !draft?.modelId) { this.preferOpenAIEditingModel(); this.applySelectedModelCapability(); }
            if (this.selectedAdjustmentPresetId) this.selectAdjustmentPreset();
            this.monitorActiveRun();
            try {
                const packageMiniApps = this.miniApps.filter(item => item.source === 'package');
                const resumed = await window.AI2AppsStudioMiniApps?.resumeSetup(APP_ID, packageMiniApps);
                if (resumed?.status === 'ready') {
                    const item = packageMiniApps.find(value => value.id === (resumed.miniAppId || this.packageMiniAppId));
                    if (item && item.id !== this.packageMiniAppId) { this.miniAppId = item.id; await this.mountPackageMiniApp(item); }
                    else if (item) await this.refreshPackageMiniAppReadiness(item);
                    await this.refreshAllPackageMiniAppReadiness();
                    await this.refresh(); this.success('Dependencies ready');
                }
            } catch (error) { this.fail(error); }
            await this.resumeLocalProvisioning();
            if (this.leftView === 'assets') this.mountGalleryMini();
            if (this.leftView === 'chat') this.mountMiniAppChat();
        },
        cleanup() { if (this.draftTimer) clearTimeout(this.draftTimer); if (this.noticeTimer) clearTimeout(this.noticeTimer); if (this.adjustRenderFrame) cancelAnimationFrame(this.adjustRenderFrame); this.chatController?.dispose(); this.packageChatBridge?.dispose(); disposeRenderableImage(this.adjustBitmap); if (this.galleryMessageHandler) window.removeEventListener('message', this.galleryMessageHandler); if (this.hostContextHandler) window.removeEventListener('ai2apps:host-context', this.hostContextHandler); this.referencePreviews.forEach(url => { if (url) URL.revokeObjectURL(url); }); },
        tr(key, values) { return translate(this.locale, key, values); },
        localizedName(item) { return item?.name?.[this.locale === 'zh' ? 'CN' : 'EN'] || item?.name?.EN || ''; },
        openStyleDialog() {
            this.pendingStyle = this.style;
            const selectedCategory = this.styleCategories.find(category => category.styles.some(item => item.id === this.style));
            this.styleCategoryId = selectedCategory?.id || this.styleCategories[0]?.id || '';
            this.styleDialogOpen = true; this.icons();
        },
        closeStyleDialog() { this.styleDialogOpen = false; this.pendingStyle = this.style; this.icons(); },
        chooseStyle(styleId) { if (this.isStyleTransferMode && !styleId) return; this.pendingStyle = styleId; this.icons(); },
        applyStyle() { if (this.isStyleTransferMode && !this.pendingStyle) return; this.style = this.pendingStyle; this.styleDialogOpen = false; this.persistStylePreference(); this.scheduleDraftSave(); this.icons(); },
        persistAdjustmentPreferences() {
            localStorage.setItem(ADJUSTMENT_PRESETS_KEY, JSON.stringify(this.adjustmentPresets));
            localStorage.setItem(ADJUSTMENT_LOCK_KEY, this.adjustmentLocked ? '1' : '0');
            localStorage.setItem(ADJUSTMENT_SELECTED_PRESET_KEY, this.selectedAdjustmentPresetId);
            this.saveDraft().catch(error => this.fail(error));
        },
        toggleAdjustmentLock() { this.adjustmentLocked = !this.adjustmentLocked; this.persistAdjustmentPreferences(); },
        selectAdjustmentPreset() {
            const preset = this.selectedAdjustmentPreset;
            if (!preset) { this.adjustmentPresetName = ''; this.persistAdjustmentPreferences(); return; }
            this.adjustmentPresetName = preset.name;
            this.adjustState = window.ImagineAdjustEngine.clone(preset.state);
            this.adjustHistory = [window.ImagineAdjustEngine.clone(this.adjustState)]; this.adjustHistoryIndex = 0;
            this.persistAdjustmentPreferences(); this.scheduleAdjustmentRender(); this.scheduleDraftSave(); this.icons();
        },
        saveAdjustmentPreset() {
            const name = this.adjustmentPresetName.trim();
            if (!name) { this.fail(new Error(this.tr('presetNameRequired'))); return; }
            const now = new Date().toISOString(), state = window.ImagineAdjustEngine.clone(this.adjustState);
            const existing = this.selectedAdjustmentPreset;
            if (existing) {
                this.adjustmentPresets = this.adjustmentPresets.map(item => item.id === existing.id ? { ...item, name, state, updatedAt: now } : item);
            } else {
                const id = globalThis.crypto?.randomUUID?.() || `preset-${Date.now()}`;
                this.adjustmentPresets = [...this.adjustmentPresets, { id, name, state, createdAt: now, updatedAt: now }];
                this.selectedAdjustmentPresetId = id;
            }
            this.persistAdjustmentPreferences(); this.success(this.tr(existing ? 'presetUpdated' : 'presetSaved')); this.icons();
        },
        renameAdjustmentPreset(preset) {
            const name = window.prompt(this.tr('renamePresetPrompt'), preset.name)?.trim();
            if (!name) return;
            this.adjustmentPresets = this.adjustmentPresets.map(item => item.id === preset.id ? { ...item, name, updatedAt: new Date().toISOString() } : item);
            if (this.selectedAdjustmentPresetId === preset.id) this.adjustmentPresetName = name;
            this.persistAdjustmentPreferences(); this.icons();
        },
        deleteAdjustmentPreset(preset) {
            if (!window.confirm(this.tr('deletePresetConfirm', { name: preset.name }))) return;
            this.adjustmentPresets = this.adjustmentPresets.filter(item => item.id !== preset.id);
            if (this.selectedAdjustmentPresetId === preset.id) { this.selectedAdjustmentPresetId = ''; this.adjustmentPresetName = ''; }
            this.persistAdjustmentPreferences(); this.icons();
        },
        openAdjustmentBatch() {
            this.adjustmentBatchOpen = true; this.adjustmentBatchDone = 0; this.adjustmentBatchTotal = 0; this.icons();
        },
        closeAdjustmentBatch() { if (!this.adjustmentBatchBusy) this.adjustmentBatchOpen = false; },
        chooseBatchFiles() { this.$refs.adjustmentBatchFiles?.click(); },
        chooseBatchFolder() { this.$refs.adjustmentBatchFolder?.click(); },
        chooseBatchOutputFolder() { this.$refs.adjustmentBatchOutputFolder?.click(); },
        setAdjustmentBatchFiles(files, source) {
            this.adjustmentBatchSource = source;
            this.adjustmentBatchFiles = Array.from(files || []).filter(file => String(file.type || '').startsWith('image/'));
            this.adjustmentBatchOutputDirectory = '';
        },
        setAdjustmentBatchOutputDirectory(files) {
            this.adjustmentBatchOutputDirectory = selectedDirectory(files);
            if (!this.adjustmentBatchOutputDirectory) this.fail(new Error(this.tr('batchOutputFolderNeedsFile')));
        },
        async galleryBatchFiles() {
            const query = new URLSearchParams({ collectionId: this.galleryActiveCollectionId, kind: 'image', limit: '200' });
            const payload = await responsePayload(await fetch(`${GALLERY_API}/assets?${query}`, { credentials: 'same-origin', cache: 'no-store' }));
            const assets = payload.items || [];
            return Promise.all(assets.map(async asset => {
                const handle = await responsePayload(await fetch(`${GALLERY_API}/assets/${encodeURIComponent(asset.id)}/resource-handles`, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ consumerAppId: APP_ID, appInstanceId: this.appInstanceId() }) }));
                const handleId = String(handle.resourceHandle || '').replace(/^resource:\/\//, '');
                const handleUrl = `${GALLERY_API}/resource-handles/${encodeURIComponent(handleId)}/content?appInstanceId=${encodeURIComponent(this.appInstanceId())}&consumerAppId=${encodeURIComponent(APP_ID)}`;
                const response = await fetch(handleUrl, { credentials: 'same-origin' });
                if (!response.ok) throw new Error(this.tr('readGalleryFailed', { status: response.status }));
                const blob = await response.blob(); return { file: new File([blob], asset.name, { type: asset.media_type || blob.type }), asset };
            }));
        },
        async uploadBatchOutput(file, target) {
            const bytes = new Uint8Array(await file.arrayBuffer()), chunkSize = 192 * 1024, total = Math.ceil(bytes.length / chunkSize);
            const uploadId = globalThis.crypto?.randomUUID?.() || `batch-${Date.now()}`; let result = null;
            for (let index = 0; index < total; index += 1) {
                result = await responsePayload(await fetch(`${STUDIO_API}/batch-output/chunks`, { method: 'POST', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ uploadId, index, total, target, data: base64Bytes(bytes.subarray(index * chunkSize, Math.min(bytes.length, (index + 1) * chunkSize))) }) }));
            }
            return result;
        },
        async runAdjustmentBatch() {
            if (this.adjustmentBatchBusy) return;
            if (this.adjustmentBatchSource !== 'gallery' && !this.adjustmentBatchFiles.length) { this.fail(new Error(this.tr('batchChooseInput'))); return; }
            if (this.adjustmentBatchSource !== 'gallery' && this.adjustmentBatchOutputMode === 'save-as' && !this.adjustmentBatchOutputDirectory) { this.fail(new Error(this.tr('batchChooseOutput'))); return; }
            if (this.adjustmentBatchOutputMode === 'overwrite' && !window.confirm(this.tr('batchOverwriteConfirm'))) return;
            this.adjustmentBatchBusy = true; this.adjustmentBatchDone = 0; this.dismissNotice();
            try {
                const items = this.adjustmentBatchSource === 'gallery' ? await this.galleryBatchFiles() : this.adjustmentBatchFiles.map(file => ({ file, asset: null }));
                this.adjustmentBatchTotal = items.length;
                if (!items.length) throw new Error(this.tr('batchNoImages'));
                for (const item of items) {
                    const bitmap = await loadRenderableImage(item.file);
                    try {
                        const canvas = document.createElement('canvas'); window.ImagineAdjustEngine.render(bitmap, canvas, this.adjustState, 0);
                        const sourceType = ['image/jpeg', 'image/webp'].includes(item.file.type) ? item.file.type : 'image/png';
                        const output = await canvasFile(canvas, item.file.name, sourceType);
                        if (this.adjustmentBatchSource === 'gallery') {
                            await this.uploadBatchOutput(output, { kind: 'gallery', overwrite: this.adjustmentBatchOutputMode === 'overwrite', assetId: item.asset.id, collectionId: this.galleryActiveCollectionId === 'recent' ? null : this.galleryActiveCollectionId, name: item.file.name, mediaType: output.type });
                        } else {
                            const sourcePath = nativeFilePath(item.file);
                            if (!sourcePath) throw new Error(this.tr('batchNativePathUnavailable', { name: item.file.name }));
                            const relative = this.adjustmentBatchSource === 'folder' ? String(item.file.webkitRelativePath || item.file.name) : item.file.name;
                            await this.uploadBatchOutput(output, { kind: 'local', overwrite: this.adjustmentBatchOutputMode === 'overwrite', sourcePath, outputRoot: this.adjustmentBatchOutputDirectory || null, relativePath: relative, name: item.file.name, mediaType: output.type });
                        }
                    } finally { disposeRenderableImage(bitmap); }
                    this.adjustmentBatchDone += 1;
                }
                this.success(this.tr('batchCompleted', { count: this.adjustmentBatchDone })); this.adjustmentBatchOpen = false;
                this.$refs.galleryMini?.contentWindow?.postMessage({ type: 'ai2apps.gallery.refresh' }, window.location.origin);
            } catch (error) { this.fail(error); }
            finally { this.adjustmentBatchBusy = false; this.icons(); }
        },
        resetAdjustments(record = true) {
            this.adjustState = window.ImagineAdjustEngine.state();
            if (record) { this.adjustHistory = [window.ImagineAdjustEngine.clone(this.adjustState)]; this.adjustHistoryIndex = 0; this.scheduleDraftSave(); }
            this.scheduleAdjustmentRender(); this.icons();
        },
        commitAdjustment() {
            const snapshot = window.ImagineAdjustEngine.clone(this.adjustState);
            this.adjustHistory = [...this.adjustHistory.slice(0, this.adjustHistoryIndex + 1), snapshot].slice(-60);
            this.adjustHistoryIndex = this.adjustHistory.length - 1; this.scheduleDraftSave(); this.scheduleAdjustmentRender(); this.icons();
        },
        transformAdjustment(action) {
            if (action === 'rotate-left') this.adjustState.rotation = (this.adjustState.rotation - 90) % 360;
            if (action === 'rotate-right') this.adjustState.rotation = (this.adjustState.rotation + 90) % 360;
            if (action === 'flip-x') this.adjustState.flipX = !this.adjustState.flipX;
            if (action === 'flip-y') this.adjustState.flipY = !this.adjustState.flipY;
            this.commitAdjustment();
        },
        undoAdjustment() { if (!this.canUndoAdjustment) return; this.adjustHistoryIndex -= 1; this.adjustState = window.ImagineAdjustEngine.clone(this.adjustHistory[this.adjustHistoryIndex]); this.scheduleAdjustmentRender(); this.scheduleDraftSave(); this.icons(); },
        redoAdjustment() { if (!this.canRedoAdjustment) return; this.adjustHistoryIndex += 1; this.adjustState = window.ImagineAdjustEngine.clone(this.adjustHistory[this.adjustHistoryIndex]); this.scheduleAdjustmentRender(); this.scheduleDraftSave(); this.icons(); },
        scheduleAdjustmentRender() { if (this.adjustRenderFrame) cancelAnimationFrame(this.adjustRenderFrame); this.adjustRenderFrame = requestAnimationFrame(() => { this.adjustRenderFrame = 0; this.renderAdjustment(); }); },
        renderAdjustment() { if (!this.adjustBitmap || !this.$refs.adjustCanvas) return; window.ImagineAdjustEngine.render(this.adjustBitmap, this.$refs.adjustCanvas, this.adjustState, 1400); },
        async exportAdjustment(retryOf = null) {
            if (!this.canExportAdjustment) { this.fail(new Error(this.tr('adjustmentMissingImage'))); return; }
            this.adjustmentExporting = true; this.dismissNotice(); let run = null; let stage = 'Preparing adjustment';
            const id = globalThis.crypto?.randomUUID?.() || `adjust-${Date.now()}`;
            const input = { ...this.draftPayload(), prompt: '', sourceName: this.referenceFiles[0]?.name || '', adjustmentState: window.ImagineAdjustEngine.clone(this.adjustState) };
            try {
                await this.saveDraft(); run = await this.createRun(input, retryOf); this.runs = [run, ...this.runs]; this.selectRun(run);
                run = await this.updateRun(run.id, 'running', 20, this.tr('localAdjustments')); this.runs = this.runs.map(item => item.id === run.id ? run : item);
                await new Promise(resolve => requestAnimationFrame(resolve));
                stage = 'Rendering full-resolution image';
                const canvas = document.createElement('canvas'); const rendered = window.ImagineAdjustEngine.render(this.adjustBitmap, canvas, this.adjustState, 0);
                const filename = `imagine-adjust-${id.slice(-8)}.png`;
                stage = 'Encoding PNG';
                const imageFile = await canvasFile(canvas, filename);
                stage = 'Saving image artifact';
                await this.persistResult({ runId: run.id, miniAppId: this.miniAppId, pipelineId: 'adjust-image', title: this.currentMiniApp.name, prompt: '', size: `${rendered.naturalWidth}x${rendered.naturalHeight}`, modelId: 'local/image-adjustments', modelLabel: this.tr('localAdjustments'), quality: 'lossless', format: 'png', imageFile, filename });
                await this.updateRun(run.id, 'succeeded', 100, this.tr('completed')); await this.refreshRuns(); this.selectRun(this.runs.find(item => item.id === run.id)); this.success(this.tr('completed'));
            } catch (error) {
                const failure = new Error(`${stage}: ${error?.message || String(error)}`);
                if (run) { try { await this.updateRun(run.id, 'failed', 100, this.tr('failed'), { code: 'image_adjustment_failed', message: failure.message }); } catch (_) {} }
                this.fail(failure); await this.refreshRuns().catch(() => {});
            } finally { this.adjustmentExporting = false; this.icons(); }
        },
        setLocale(value) { const locale = normalizedLocale(value); if (locale === this.locale) return; const installed = this.miniApps.filter(item => item.source === 'package').map(item => packageMiniApp(item, locale)); this.locale = locale; this.miniApps = [...localizedMiniApps(locale), ...installed]; document.documentElement.lang = locale; document.title = 'Imagine Studio - AI2Apps'; this.icons(); },
        icons() { this.$nextTick(() => window.lucide?.createIcons()); },
        dismissNotice() { if (this.noticeTimer) clearTimeout(this.noticeTimer); this.noticeTimer = null; this.notice = ''; },
        showNotice(message, tone = 'error', timeoutMs = null) {
            this.dismissNotice(); this.notice = String(message || ''); this.noticeTone = tone;
            const delay = Number(timeoutMs ?? (tone === 'error' ? 8000 : 4500));
            if (this.notice && delay > 0) this.noticeTimer = setTimeout(() => { this.notice = ''; this.noticeTimer = null; }, delay);
            this.icons();
        },
        fail(error) { const message = error?.message || String(error); const cancelled = /cancelled|canceled|已取消|取消能力配置/i.test(message); this.showNotice(message, cancelled ? 'neutral' : 'error', cancelled ? 4000 : 8000); },
        success(message) { this.showNotice(message, 'success', 4500); },
        setupMiniAppChat() {
            if (!window.AI2AppsMiniAppChat) return;
            this.chatController = window.AI2AppsMiniAppChat.createStudioController({ describe: () => this.describeMiniAppChat(), invoke: (name, args) => this.invokeMiniAppChatTool(name, args), help: () => this.readMiniAppHelp() });
            this.chatMiniUrl = this.chatController.url();
        },
        mountMiniAppChat() {
            if (!this.chatController) this.setupMiniAppChat();
            return new Promise(resolve => this.$nextTick(() => { this.chatController?.bind(this.$refs.miniAppChat); resolve(); }));
        },
        async describeMiniAppChat() {
            const miniApp = this.currentMiniApp;
            if (miniApp.source === 'package') {
                if (!this.packageChatBridge) throw new Error('Package Mini-App Chat provider is not ready');
                return this.packageChatBridge.describe({ id: miniApp.id, name: miniApp.name, version: miniApp.version, studioId: APP_ID });
            }
            return {
                schema: window.AI2AppsMiniAppChat.SCHEMA, enabled: true,
                miniApp: { id: miniApp.id, name: miniApp.name, version: miniApp.version, studioId: APP_ID },
                systemPrompt: `You are the conversational controller for ${miniApp.name} in Imagine Studio. Help compose the image brief and configure only the visible draft. Do not claim an image exists until the Tool reports a successful run.`,
                help: { available: true, format: 'markdown', maxBytes: 32 * 1024 },
                context: {
                    mode: miniApp.mode, prompt: this.prompt, modelId: this.modelId, model: this.selectedModel?.label || null,
                    size: this.requestedSize, quality: this.quality, format: this.format, style: this.selectedStyle ? this.localizedName(this.selectedStyle) : null,
                    referenceImages: this.referenceFiles.map(file => file?.name || null),
                    groupPhoto: this.isGroupPhotoMode ? { background: this.groupBackgroundDescription, atmosphere: this.groupAtmosphere, pose: this.groupPose, ready: this.groupPhotoReady } : null,
                    ready: this.currentMiniApp.status === 'ready', canRun: this.canGenerate,
                },
                tools: [
                    { name: 'update_current_draft', title: 'Update image draft', description: 'Update the prompt and supported generation settings for the current Mini-App.', inputSchema: { type: 'object', properties: {
                        prompt: { type: 'string', maxLength: 32000 }, modelId: { type: 'string' }, size: { type: 'string' }, quality: { type: 'string' }, format: { type: 'string' }, styleId: { type: 'string' },
                        background: { type: 'string', maxLength: 4000 }, atmosphere: { type: 'string', maxLength: 2000 }, pose: { type: 'string', maxLength: 4000 },
                    }, additionalProperties: false } },
                    { name: 'run_current', title: this.isAdjustMode ? 'Export adjusted image' : 'Generate image', description: 'Run the current Mini-App using the visible draft and selected references.', inputSchema: { type: 'object', properties: {}, additionalProperties: false }, confirmation: 'always' },
                ],
            };
        },
        async readMiniAppHelp() {
            if (this.currentMiniApp.source === 'package') {
                if (!this.packageChatBridge) throw new Error('Package Mini-App Chat provider is not ready');
                return this.packageChatBridge.help();
            }
            return window.AI2AppsMiniAppChat.loadBuiltinHelp(this.currentMiniApp);
        },
        async invokeMiniAppChatTool(name, args) {
            if (this.currentMiniApp.source === 'package') {
                if (!this.packageChatBridge) throw new Error('Package Mini-App Chat provider is not ready');
                return this.packageChatBridge.invoke(name, args);
            }
            if (name === 'update_current_draft') {
                if (typeof args.prompt === 'string') this.prompt = args.prompt.slice(0, 32000);
                if (typeof args.modelId === 'string' && this.models.some(item => item.id === args.modelId)) this.modelId = args.modelId;
                if (typeof args.size === 'string' && this.sizeOptions.some(item => item.value === args.size)) this.size = args.size;
                if (typeof args.quality === 'string' && this.qualityOptions.includes(args.quality)) this.quality = args.quality;
                if (typeof args.format === 'string' && this.formatOptions.includes(args.format)) this.format = args.format;
                if (typeof args.styleId === 'string' && (!args.styleId || this.allStyles.some(item => item.id === args.styleId))) { this.style = args.styleId; this.persistStylePreference(); }
                if (this.isGroupPhotoMode) {
                    if (typeof args.background === 'string') this.groupBackgroundDescription = args.background.slice(0, 4000);
                    if (typeof args.atmosphere === 'string') this.groupAtmosphere = args.atmosphere.slice(0, 2000);
                    if (typeof args.pose === 'string') this.groupPose = args.pose.slice(0, 4000);
                }
                this.scheduleDraftSave(); this.persistPreferences(); this.icons();
                return { updated: true, state: (await this.describeMiniAppChat()).context };
            }
            if (name === 'run_current') {
                if (this.isAdjustMode) { if (!this.canExportAdjustment) throw new Error('Choose an image before exporting adjustments'); await this.exportAdjustment(); }
                else { if (!this.canGenerate) throw new Error('The current Mini-App is missing required input or configuration'); await this.generate(); }
                return { started: true, miniAppId: this.miniAppId };
            }
            throw new Error('Unknown Mini-App Tool');
        },
        appInstanceId() {
            return window.AI2AppsCapabilities?.appInstanceId?.()
                || new URLSearchParams(window.location.hash.slice(1)).get('ai2apps-instance') || '';
        },
        historyHeaders() {
            const instanceId = this.appInstanceId();
            return { Accept: 'application/json', ...(instanceId ? { 'X-AI2Apps-App-Instance': instanceId } : {}) };
        },
        restorePreferences() {
            try {
                const layout = JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}');
                const discovery = JSON.parse(localStorage.getItem(DISCOVERY_KEY) || '{}');
                this.leftView = ['assets', 'chat'].includes(layout.leftView) ? layout.leftView : 'mini-apps';
                this.leftCollapsed = Boolean(layout.leftCollapsed); this.rightCollapsed = Boolean(layout.rightCollapsed);
                if (this.miniApps.some(item => item.id === layout.miniAppId && item.status === 'ready')) this.miniAppId = layout.miniAppId;
                this.favoriteMiniApps = Array.isArray(discovery.favorites) ? discovery.favorites : [];
                this.recentMiniApps = Array.isArray(discovery.recent) ? discovery.recent.slice(0, 8) : [];
                const savedStyle = localStorage.getItem(STYLE_KEY);
                if (savedStyle !== null) { this.style = LEGACY_STYLE_IDS[savedStyle] || savedStyle; this.stylePreferenceLoaded = true; }
                const presets = JSON.parse(localStorage.getItem(ADJUSTMENT_PRESETS_KEY) || '[]');
                this.adjustmentPresets = Array.isArray(presets) ? presets.filter(item => item?.id && item?.name && item?.state) : [];
                this.adjustmentLocked = localStorage.getItem(ADJUSTMENT_LOCK_KEY) === '1';
                const selectedPresetId = localStorage.getItem(ADJUSTMENT_SELECTED_PRESET_KEY) || '';
                this.selectedAdjustmentPresetId = this.adjustmentPresets.some(item => item.id === selectedPresetId) ? selectedPresetId : '';
            } catch (_) {}
        },
        persistStylePreference() { localStorage.setItem(STYLE_KEY, this.style); this.stylePreferenceLoaded = true; },
        persistPreferences() {
            localStorage.setItem(LAYOUT_KEY, JSON.stringify({ leftView: this.leftView, leftCollapsed: this.leftCollapsed, rightCollapsed: this.rightCollapsed, miniAppId: this.miniAppId }));
            localStorage.setItem(DISCOVERY_KEY, JSON.stringify({ favorites: this.favoriteMiniApps, recent: this.recentMiniApps.slice(0, 8) }));
        },
        toggleColumn(column) { if (column === 'left') this.leftCollapsed = !this.leftCollapsed; else this.rightCollapsed = !this.rightCollapsed; this.persistPreferences(); this.icons(); },
        mobileVisible(surface) { return window.innerWidth > 760 || this.mobileSurface === surface; },
        isFavorite(id) { return this.favoriteMiniApps.includes(id); },
        toggleFavorite(id) { this.favoriteMiniApps = this.isFavorite(id) ? this.favoriteMiniApps.filter(value => value !== id) : [id, ...this.favoriteMiniApps]; this.persistPreferences(); this.icons(); },
        miniAppName(id) { return this.miniApps.find(item => item.id === id)?.name || id || '' },
        formatTime(value) { if (!value) return '—'; try { return new Intl.DateTimeFormat(this.locale, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)); } catch (_) { return value; } },
        isActiveRun(run) { return ['queued', 'running'].includes(run?.status); },
        canRetryRun(run) { return ['failed', 'cancelled', 'expired', 'waiting_input'].includes(run?.status); },
        selectRun(run) { this.selectedRunId = run?.id || ''; this.selectedArtifactId = run?.artifacts?.[0]?.id || ''; this.icons(); },
        selectArtifact(artifact) { this.selectedArtifactId = artifact?.id || ''; this.icons(); },
        draftPayload() { return { zImageBaseSteps: this.zImageBaseSteps, zImageBaseGuidance: this.zImageBaseGuidance, zImageBaseNegativePrompt: this.zImageBaseNegativePrompt, zImageSteps: this.zImageSteps, zImageRedraw: this.zImageRedraw, prompt: this.prompt, groupBackgroundDescription: this.groupBackgroundDescription, groupAtmosphere: this.groupAtmosphere, groupPose: this.groupPose, modelId: this.modelId, size: this.size, customWidth: this.customWidth, customHeight: this.customHeight, quality: this.quality, format: this.format, style: this.style, adjustmentState: window.ImagineAdjustEngine?.clone?.(this.adjustState), adjustmentLocked: this.adjustmentLocked, adjustmentPresets: this.adjustmentPresets, selectedAdjustmentPresetId: this.selectedAdjustmentPresetId, assetReferences: this.referenceAssets.slice(0, this.currentMiniApp.maxImages) }; },
        applyDraft(draft, restoreStyle = false) { if (!draft || typeof draft !== 'object') return; this.zImageBaseSteps = Number(draft.zImageBaseSteps) || 30; this.zImageBaseGuidance = Number(draft.zImageBaseGuidance) || 4; this.zImageBaseNegativePrompt = String(draft.zImageBaseNegativePrompt || '').slice(0, 8192); this.zImageSteps = Number(draft.zImageSteps) || 8; this.zImageRedraw = Number(draft.zImageRedraw) || 75; this.prompt = String(draft.prompt || ''); this.groupBackgroundDescription = String(draft.groupBackgroundDescription || ''); this.groupAtmosphere = String(draft.groupAtmosphere || ''); this.groupPose = String(draft.groupPose || ''); const savedModelId = String(draft.modelId || this.modelId); const managedModelId = managedCloudModelId(savedModelId); this.modelId = this.models.some(model => model.source === 'cloud' && model.id === managedModelId) ? managedModelId : savedModelId; this.size = String(draft.size || this.size); this.customWidth = Number(draft.customWidth || this.customWidth); this.customHeight = Number(draft.customHeight || this.customHeight); this.quality = String(draft.quality || 'auto'); this.format = String(draft.format || 'png'); if (restoreStyle || !this.stylePreferenceLoaded) { const savedStyle = String(draft.style || ''); this.style = LEGACY_STYLE_IDS[savedStyle] || savedStyle; this.persistStylePreference(); } if (draft.adjustmentState && window.ImagineAdjustEngine) { this.adjustState = window.ImagineAdjustEngine.clone(draft.adjustmentState); this.adjustHistory = [window.ImagineAdjustEngine.clone(this.adjustState)]; this.adjustHistoryIndex = 0; } if (Array.isArray(draft.adjustmentPresets)) this.adjustmentPresets = draft.adjustmentPresets.filter(item => item?.id && item?.name && item?.state); if (typeof draft.adjustmentLocked === 'boolean') this.adjustmentLocked = draft.adjustmentLocked; if (typeof draft.selectedAdjustmentPresetId === 'string') this.selectedAdjustmentPresetId = this.adjustmentPresets.some(item => item.id === draft.selectedAdjustmentPresetId) ? draft.selectedAdjustmentPresetId : ''; this.referenceAssets = Array.isArray(draft.assetReferences) ? draft.assetReferences : []; this.reconcileSelectedModel(); },
        scheduleDraftSave() { if (this.draftTimer) clearTimeout(this.draftTimer); this.draftTimer = setTimeout(() => this.saveDraft().catch(error => this.fail(error)), 500); },
        async saveDraft() { if (!this.appInstanceId() || this.currentMiniApp.status !== 'ready') return; await responsePayload(await fetch(`${STUDIO_API}/drafts/${encodeURIComponent(this.miniAppId)}`, { method: 'PUT', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ draft: this.draftPayload() }) })); },
        async loadDraft(miniAppId) { if (!this.appInstanceId()) return {}; const payload = await responsePayload(await fetch(`${STUDIO_API}/drafts/${encodeURIComponent(miniAppId)}`, { credentials: 'same-origin', headers: this.historyHeaders() })); const draft = payload.draft || {}; this.applyDraft(draft); await this.restoreAssetReferences(); return draft; },
        async materializeAssetReference(assetReference, index, preserveAdjustments = false) {
            const assetId = String(assetReference?.assetId || ''); if (!assetId) return;
            const refreshed = await responsePayload(await fetch(`${GALLERY_API}/assets/${encodeURIComponent(assetId)}/resource-handles`, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ consumerAppId: APP_ID, appInstanceId: this.appInstanceId() }) }));
            const handleId = String(refreshed.resourceHandle || '').replace(/^resource:\/\//, '');
            const handleUrl = `${GALLERY_API}/resource-handles/${encodeURIComponent(handleId)}/content?appInstanceId=${encodeURIComponent(this.appInstanceId())}&consumerAppId=${encodeURIComponent(APP_ID)}`;
            const response = await fetch(handleUrl, { credentials: 'same-origin' }); if (!response.ok) throw new Error(this.tr('readGalleryFailed', { status: response.status }));
            const blob = await response.blob(); const file = new File([blob], refreshed.name || `gallery-${assetId}`, { type: refreshed.mediaType || blob.type });
            await this.setReference(index, file, refreshed, preserveAdjustments);
        },
        async restoreAssetReferences() { const values = [...this.referenceAssets]; for (let index = 0; index < values.length; index += 1) { if (!values[index]?.assetId) continue; try { await this.materializeAssetReference(values[index], index, true); } catch (_) { const stale = [...this.referenceAssets]; stale[index] = null; this.referenceAssets = stale; } } },
        async refreshRuns() { if (!this.appInstanceId()) return; const payload = await responsePayload(await fetch(`${STUDIO_API}/runs?limit=50`, { credentials: 'same-origin', headers: this.historyHeaders(), cache: 'no-store' })); this.runs = payload.items || []; if (!this.runs.some(item => item.id === this.selectedRunId)) this.selectRun(this.runs[0] || null); },
        async waitForRun(runId) {
            while (true) {
                await new Promise(resolve => setTimeout(resolve, 1000));
                await this.refreshRuns();
                const run = this.runs.find(item => item.id === runId);
                if (!run || this.isActiveRun(run)) continue;
                this.selectRun(run);
                if (run.status === 'succeeded' || run.status === 'cancelled') return run;
                throw new Error(run.error?.message || this.tr('failed'));
            }
        },
        async monitorActiveRun() {
            const run = this.runs.find(item => this.isActiveRun(item));
            if (!run || this.generating) return;
            this.generating = true; this.selectRun(run); this.icons();
            try { await this.waitForRun(run.id); }
            catch (error) { this.fail(error); }
            finally { this.generating = false; this.icons(); }
        },
        async createRun(input, retryOf = null) { return responsePayload(await fetch(`${STUDIO_API}/runs`, { method: 'POST', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ miniAppId: this.miniAppId, title: this.usingLocalModel && !this.isAdjustMode ? this.tr(this.currentMiniApp.mode === 'generate' ? 'localGenerateRun' : 'localEditRun') : this.currentMiniApp.runLabel, input, retryOf }) })); },
        async updateRun(runId, status, progress, detail = '', error = null) { return responsePayload(await fetch(`${STUDIO_API}/runs/${encodeURIComponent(runId)}`, { method: 'PATCH', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ status, progress, detail, error }) })); },
        async executeCloudRun(runId, request) { return responsePayload(await fetch(`${STUDIO_API}/runs/${encodeURIComponent(runId)}/execute`, { method: 'POST', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify(request) })); },
        async cancelRun(run) { if (!this.isActiveRun(run)) return; if (run.id === this.selectedRunId) this.currentRunController?.abort(); try { await this.updateRun(run.id, 'cancelled', run.progress, this.tr('cancelled')); await this.refreshRuns(); } catch (error) { this.fail(error); } },
        async retryRun(run) { this.miniAppId = run.miniAppId; this.applyDraft(run.input, true); this.mobileSurface = 'create'; if (this.isAdjustMode) await this.exportAdjustment(run.id); else await this.generate(run.id); },
        async refresh() {
            this.refreshing = true;
            try { await Promise.all([this.loadModelCatalog(), this.refreshRuns()]); this.icons(); }
            catch (error) { this.fail(error); }
            finally { this.refreshing = false; }
        },
        cloudSizeCapability(model) {
            const capability = model?.imageOptions?.size;
            if (!['fixed', 'bounded-custom'].includes(capability?.mode)) return structuredClone(LEGACY_SIZE_CAPABILITY);
            return {
                ...structuredClone(LEGACY_SIZE_CAPABILITY), ...capability,
                width: { ...LEGACY_SIZE_CAPABILITY.width, ...(capability.width || {}) },
                height: { ...LEGACY_SIZE_CAPABILITY.height, ...(capability.height || {}) },
                presets: Array.isArray(capability.presets) ? capability.presets.filter(value => this.parseSize(value)) : LEGACY_SIZE_CAPABILITY.presets,
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
        async loadModelCatalog({ requireLocal = false } = {}) {
            const cloudFallback = { id: DEFAULT_CLOUD_MODEL, label: '(Cloud) OpenAI · GPT Image 2', source: 'cloud', operations: ['image_generation', 'image_edit'], formats: ['png', 'jpeg', 'webp'], qualities: ['auto', 'low', 'medium', 'high'], sizeCapability: structuredClone(LEGACY_SIZE_CAPABILITY), pricingVersion: '' };
            let cloudModels = [cloudFallback], localModels = [];
            const [cloudResult, localResult] = await Promise.allSettled([
                fetch(CLOUD_MODELS_API, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } }).then(responsePayload),
                fetch(LOCAL_MODELS_API, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } }).then(responsePayload),
            ]);
            if (cloudResult.status === 'fulfilled') {
                cloudModels = (cloudResult.value.items || []).filter(model => model?.capabilities?.imageGeneration).map(model => ({
                    id: managedCloudModelId(model.id), label: model.identity?.displayName || model.displayName || model.id, source: 'cloud',
                    operations: ['image_generation', ...(model.capabilities?.imageEdit ? ['image_edit'] : [])],
                    formats: Array.isArray(model.imageOptions?.outputFormat) && model.imageOptions.outputFormat.length ? model.imageOptions.outputFormat : ['png', 'jpeg', 'webp'],
                    qualities: Array.isArray(model.imageOptions?.quality) && model.imageOptions.quality.length ? model.imageOptions.quality : ['auto'],
                    sizeCapability: this.cloudSizeCapability(model), pricingVersion: String(model.pricingVersion || ''),
                }));
                if (!cloudModels.some(model => model.id === DEFAULT_CLOUD_MODEL)) cloudModels.unshift(cloudFallback);
            }
            if (requireLocal && localResult.status === 'rejected') throw localResult.reason;
            if (localResult.status === 'fulfilled') {
                localModels = (localResult.value.data || []).filter(model => model?.model_type === 'image_generation' && model?.source_type === 'package' && model?.checkpoint_ready !== false && !model?.is_hidden).map(model => ({
                    id: model.id, label: model.identity?.displayName || model.display_name || model.id, source: 'local',
                    operations: Array.isArray(model.image_capabilities?.operations) ? model.image_capabilities.operations : (model.capabilities || []).filter(value => ['image_generation', 'image_edit'].includes(value)),
                    referenceLimits: model.image_capabilities?.inputs?.reference_images || { minimum: 1, maximum: 1 },
                    formats: model.image_capabilities?.formats?.output || ['png'], qualities: ['auto', 'low', 'medium', 'high'], sizeCapability: this.localSizeCapability(model.image_capabilities), pricingVersion: '',
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
        isOpenAIModel(model) { return /(^|\/)openai\//.test(String(model?.id || '')); },
        preferOpenAIEditingModel() { if (!this.prefersOpenAIModel) return; const preferred = this.compatibleModels.find(model => this.isOpenAIModel(model)); if (preferred) this.modelId = preferred.id; },
        preferOpenAIStyleModel() { this.preferOpenAIEditingModel(); },
        applySelectedModelCapability() {
            const model = this.selectedModel; if (!model) return;
            this.sizeCapability = JSON.parse(JSON.stringify(model.sizeCapability || LEGACY_SIZE_CAPABILITY));
            this.flexibleSizes = model.source === 'local' || this.sizeCapability.mode === 'bounded-custom';
            this.pricingVersion = String(model.pricingVersion || '');
            if (!this.sizeOptions.some(option => option.value === this.size)) this.size = String(this.sizeCapability.default || '1024x1024');
            if (!this.formatOptions.includes(this.format)) this.format = this.formatOptions[0] || 'png';
            if (!this.qualityOptions.includes(this.quality)) this.quality = this.qualityOptions[0] || 'auto';
            if (['edit', 'style-transfer', 'group-photo'].includes(this.currentMiniApp.mode) && this.referenceDimensions[0]) this.matchEditAspect(this.referenceDimensions[0]);
            this.icons();
        },
        capabilityRequest(actionId) {
            const resumeToken = globalThis.crypto?.randomUUID?.() || `imagine-local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
            return {
                appId: APP_ID, capability: this.requiredOperation === 'image_edit' ? 'image.edit' : 'image.generation', actionId,
                requirements: { operations: [this.requiredOperation], outputFormats: ['png', 'jpeg', 'webp'] },
                intent: { returnTo: `/apps/${APP_ID}`, resumeToken, completionPolicy: 'configure_only' },
            };
        },
        async finishLocalProvisioning(result) {
            await this.loadModelCatalog({ requireLocal: true });
            if (!this.hasLocalModels) throw new Error('ACPF completed, but no ready local image model was discovered.');
            if (result?.outcome === 'configured' && result.session?.id) await window.AI2AppsCapabilities.acknowledge(result.session.id, { appId: APP_ID });
            this.success(this.tr(result?.outcome === 'configured' ? 'localConfigured' : 'localAlreadyReady'));
        },
        onModelSelect(select) {
            if (select.value === '__install_more__') {
                select.value = this.modelId || '';
                void this.configureLocalModel(true);
                return;
            }
            this.modelId = select.value;
            this.scheduleDraftSave();
        },
        async configureLocalModel(installMore = false) {
            if (this.configuringLocal || !window.AI2AppsCapabilities?.ensure) return;
            this.configuringLocal = true; this.dismissNotice();
            try { await this.finishLocalProvisioning(await window.AI2AppsCapabilities.ensure(this.capabilityRequest(installMore ? 'install-more-image-models' : 'configure-local-image-model'), { installMore })); }
            catch (error) { this.fail(error); }
            finally { this.configuringLocal = false; this.icons(); }
        },
        async resumeLocalProvisioning() {
            if (!window.AI2AppsCapabilities?.resume) return;
            try { const result = await window.AI2AppsCapabilities.resume(APP_ID); if (result) await this.finishLocalProvisioning(result); }
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
            if (this.usingGoogleImageModel && GOOGLE_SIZE_LABELS[value]) {
                const actual = GOOGLE_SIZE_LABELS[value];
                return `${actual.size} · ${actual.ratio} · 1K`;
            }
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
        referenceSlotLabel(index) {
            if (!this.isGroupPhotoMode) return index === 0 ? this.tr('primaryImage') : `${this.tr('referenceImage')} ${index + 1}`;
            if (index === this.currentMiniApp.backgroundSlot) return this.tr('groupPhotoBackgroundImage');
            return this.tr('groupPhotoPerson', { number: index + 1 });
        },
        referenceSlotRequirement(index) {
            if (!this.isGroupPhotoMode) return index === 0 && this.currentMiniApp.requiresImage ? this.tr('required') : this.tr('optional');
            return index < 2 ? this.tr('required') : this.tr('optional');
        },
        showLeftView(view) { this.leftView = view === 'assets' ? 'assets' : (view === 'chat' && this.miniAppChatEnabled ? 'chat' : 'mini-apps'); if (this.leftView === 'assets' && !this.galleryMiniUrl) this.mountGalleryMini(); if (this.leftView === 'chat') this.mountMiniAppChat(); this.persistPreferences(); this.icons(); },
        async selectMiniApp(id) { const selected = this.miniApps.find(item => item.id === id); if (!selected || selected.status !== 'ready') return; if (!this.packageMiniAppId) await this.saveDraft().catch(() => {}); disposeRenderableImage(this.adjustBitmap); this.adjustBitmap = null; this.miniAppId = id; if (this.leftView !== 'chat') this.leftView = 'mini-apps'; this.recentMiniApps = [id, ...this.recentMiniApps.filter(value => value !== id)].slice(0, 8); if (selected.source === 'package') { await this.mountPackageMiniApp(selected); if (!this.miniAppChatEnabled && this.leftView === 'chat') this.leftView = 'mini-apps'; this.persistPreferences(); this.mobileSurface = 'create'; return; } this.packageChatBridge?.dispose(); this.packageChatBridge = null; this.packageMiniAppId = ''; this.packageMiniAppUrl = ''; this.packageMiniAppError = ''; this.referenceFiles = []; this.referencePreviews.forEach(url => { if (url) URL.revokeObjectURL(url); }); this.referencePreviews = []; this.referenceDimensions = []; this.referenceAssets = []; const draft = await this.loadDraft(id); this.trimReferences(); this.reconcileSelectedModel(); if (this.prefersOpenAIModel && !draft?.modelId) { this.preferOpenAIEditingModel(); this.applySelectedModelCapability(); } if (['edit', 'style-transfer', 'group-photo'].includes(this.currentMiniApp.mode) && this.referenceDimensions[0]) this.matchEditAspect(this.referenceDimensions[0]); this.chatController?.changed(); this.persistPreferences(); this.mobileSurface = 'create'; this.icons(); },
        async refreshPackageMiniApps() {
            try {
                const catalog = await window.AI2AppsStudioMiniApps?.list(APP_ID);
                this.miniApps = [...this.miniApps, ...(catalog?.items || []).filter(item => item.source === 'package').map(item => packageMiniApp(item, this.locale))];
                await this.refreshAllPackageMiniAppReadiness();
            } catch (_) { /* Built-in catalog remains available. */ }
        },
        miniAppReady(item) { return item?.source !== 'package' || this.packageMiniAppReadiness[item.id] === true; },
        async refreshAllPackageMiniAppReadiness() {
            try { this.packageMiniAppReadiness = await window.AI2AppsStudioMiniApps?.readiness(APP_ID) || {}; }
            catch (_) { /* Keep the most recent readiness snapshot during reconnects. */ }
            this.icons();
            return this.packageMiniAppReadiness;
        },
        async refreshPackageMiniAppReadiness(item, mountId = this.packageMiniAppMountId) {
            if (!item?.id || !mountId) return false;
            try {
                const probe = await window.AI2AppsStudioMiniApps.probe(APP_ID, mountId);
                const capabilities = Array.isArray(probe?.items) ? probe.items : [];
                const required = capabilities.filter(value => value?.required !== false);
                const ready = required.length > 0 && required.every(value => value?.implemented === true && value?.ready === true);
                this.packageMiniAppReadiness = { ...this.packageMiniAppReadiness, [item.id]: ready };
                return ready;
            } catch (_) {
                this.packageMiniAppReadiness = { ...this.packageMiniAppReadiness, [item.id]: false };
                return false;
            }
        },
        async setupCurrentMiniApp() {
            const item = this.currentMiniApp;
            if (!item || item.source !== 'package' || this.currentMiniAppReady || this.packageMiniAppSetupBusy) return;
            this.packageMiniAppSetupBusy = true; this.dismissNotice();
            try {
                await window.AI2AppsStudioMiniApps.setup(APP_ID, item);
                const readiness = await this.refreshAllPackageMiniAppReadiness();
                const ready = readiness[item.id] === true;
                if (ready) this.success('Dependencies ready');
            } catch (error) { this.fail(error); }
            finally { this.packageMiniAppSetupBusy = false; this.icons(); }
        },
        async mountPackageMiniApp(item) {
            if (!item?.id || this.packageMiniAppLoading) return;
            this.packageMiniAppId = item.id; this.packageMiniAppUrl = ''; this.packageMiniAppError = ''; this.packageMiniAppLoading = true;
            this.packageMiniAppReadiness = { ...this.packageMiniAppReadiness, [item.id]: false };
            try {
                const mount = await window.AI2AppsStudioMiniApps.mount(APP_ID, item.id, { placement: 'inline' });
                this.packageMiniAppMountId = mount.id || ''; this.packageMiniAppUrl = mount.content_url || '';
                if (!this.packageMiniAppUrl) throw new Error('Mini-App content URL is unavailable');
                await this.refreshPackageMiniAppReadiness(item, this.packageMiniAppMountId);
                if (item.chat?.enabled === true) await new Promise(resolve => this.$nextTick(() => {
                    this.packageChatBridge?.dispose();
                    this.packageChatBridge = window.AI2AppsMiniAppChat.createPackageBridge(() => this.$refs.packageMiniApp, item.chat);
                    resolve();
                }));
            } catch (error) { this.packageMiniAppError = error?.message || String(error); }
            finally { this.packageMiniAppLoading = false; this.chatController?.changed(); this.icons(); }
        },
        openCoder() { if (window.ai2appsShell?.openEntry) window.ai2appsShell.openEntry({ appId: 'ai2apps.coder', query: { template: 'mini-app', placement: APP_ID } }); else window.open('/apps/ai2apps.coder?template=mini-app&placement='+encodeURIComponent(APP_ID), '_blank', 'noopener'); },
        trimReferences() {
            const limit = this.currentMiniApp.maxImages;
            for (let index = limit; index < this.referencePreviews.length; index += 1) if (this.referencePreviews[index]) URL.revokeObjectURL(this.referencePreviews[index]);
            this.referenceFiles = this.referenceFiles.slice(0, limit); this.referencePreviews = this.referencePreviews.slice(0, limit); this.referenceDimensions = this.referenceDimensions.slice(0, limit);
        },
        matchEditAspect(dimensions) {
            const sourceWidth = Number(dimensions?.width), sourceHeight = Number(dimensions?.height);
            if (!sourceWidth || !sourceHeight || !['edit', 'style-transfer', 'group-photo'].includes(this.currentMiniApp.mode)) return;
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
        async setReference(index, file, assetReference = null, preserveAdjustments = false) {
            if (!file) return;
            if (!String(file.type || '').startsWith('image/')) { this.fail(new Error(this.tr('invalidSlot'))); return; }
            if (this.referencePreviews[index]) URL.revokeObjectURL(this.referencePreviews[index]);
            const files = [...this.referenceFiles], previews = [...this.referencePreviews];
            files[index] = file; previews[index] = URL.createObjectURL(file); this.referenceFiles = files; this.referencePreviews = previews;
            const assets = [...this.referenceAssets]; assets[index] = assetReference; this.referenceAssets = assets; this.scheduleDraftSave(); this.icons();
            try {
                const dimensions = await imageDimensions(file); const values = [...this.referenceDimensions]; values[index] = dimensions; this.referenceDimensions = values;
                if (index === 0 && this.isAdjustMode) { disposeRenderableImage(this.adjustBitmap); this.adjustBitmap = await loadRenderableImage(file); if (preserveAdjustments || this.preservesAdjustmentsForNewImage) { this.adjustHistory = [window.ImagineAdjustEngine.clone(this.adjustState)]; this.adjustHistoryIndex = 0; } else this.resetAdjustments(); this.$nextTick(() => this.scheduleAdjustmentRender()); }
                else if (index === 0) this.matchEditAspect(dimensions);
            } catch (_) {}
        },
        clearReference(index) {
            if (this.referencePreviews[index]) URL.revokeObjectURL(this.referencePreviews[index]);
            const files = [...this.referenceFiles], previews = [...this.referencePreviews];
            const dimensions = [...this.referenceDimensions];
            const assets = [...this.referenceAssets]; assets[index] = null;
            files[index] = null; previews[index] = ''; dimensions[index] = null; this.referenceFiles = files; this.referencePreviews = previews; this.referenceDimensions = dimensions; this.referenceAssets = assets; this.scheduleDraftSave(); this.icons();
            if (index === 0 && this.isAdjustMode) { disposeRenderableImage(this.adjustBitmap); this.adjustBitmap = null; this.resetAdjustments(false); }
        },
        composedPrompt() {
            if (!this.isGroupPhotoMode) return [this.isStyleTransferMode ? STYLE_TRANSFER_INSTRUCTION : '', this.selectedStyle?.prompt || '', this.prompt.trim()].filter(Boolean).join('\n\n');
            const personCount = this.groupPersonFiles.length;
            const background = this.groupBackgroundFile
                ? `The last input image is the background reference. Place the people naturally into that setting; do not treat it as a person reference.${this.groupBackgroundDescription.trim() ? ` Background direction: ${this.groupBackgroundDescription.trim()}.` : ''}`
                : `Background: ${this.groupBackgroundDescription.trim()}.`;
            return [
                GROUP_PHOTO_INSTRUCTION,
                `The first ${personCount} input images are distinct person references, one person per image.`,
                background,
                `Atmosphere: ${this.groupAtmosphere.trim() || 'natural, cohesive, warm, and believable'}.`,
                `Poses and interaction: ${this.groupPose.trim() || 'natural, anatomically plausible group-photo poses with comfortable spacing and interaction'}.`,
                this.selectedStyle?.prompt || '',
                this.prompt.trim(),
            ].filter(Boolean).join('\n\n');
        },
        extension() { return this.format === 'jpeg' ? 'jpg' : this.format; },
        resultFilename(id) { return `imagine-${this.currentMiniApp.adapter}-${id.slice(-8)}.${this.extension()}`; },

        async generate(retryOf = null) {
            if (!this.canGenerate || this.generating) return;
            const references = this.referenceFiles.filter(Boolean);
            const editing = this.currentMiniApp.mode !== 'generate';
            const selectedModel = this.selectedModel;
            if (!selectedModel) return;
            if (editing && selectedModel.referenceLimits && (references.length < selectedModel.referenceLimits.minimum || references.length > selectedModel.referenceLimits.maximum)) {
                this.fail(new Error(`This model requires ${selectedModel.referenceLimits.minimum}–${selectedModel.referenceLimits.maximum} reference images.`));
                return;
            }
            if (editing && selectedModel.source === 'cloud' && !window.confirm(this.tr('uploadConfirm', { count: references.length }))) return;
            this.generating = true; this.dismissNotice();
            const id = globalThis.crypto?.randomUUID?.() || `image-${Date.now()}`;
            const requestedSize = this.requestedSize;
            const input = { ...this.draftPayload(), prompt: this.prompt.trim(), size: requestedSize, modelLabel: selectedModel.label, assetReferences: this.referenceAssets.slice(0, this.currentMiniApp.maxImages) };
            let run = null;
            let serverManaged = false;
            try {
                await this.saveDraft();
                run = await this.createRun(input, retryOf);
                this.runs = [run, ...this.runs]; this.selectRun(run);
                const imageDataUrls = editing ? await Promise.all(references.map(readDataUrl)) : [];
                if (selectedModel.source === 'cloud') {
                    await this.executeCloudRun(run.id, { model: selectedModel.id, prompt: this.composedPrompt(), size: requestedSize, quality: this.quality, outputFormat: this.format, ...(editing ? { imageDataUrls } : {}) });
                    serverManaged = true;
                    await this.waitForRun(run.id);
                    try { window.ai2appsShell?.accountChanged?.(); } catch (_) {}
                    return;
                }
                run = await this.updateRun(run.id, 'running', 10, this.tr('running'));
                this.runs = this.runs.map(item => item.id === run.id ? run : item);
                this.currentRunController = new AbortController();
                const result = await responsePayload(await fetch(`${IMAGE_API}/${editing ? 'edits' : 'generations'}`, {
                    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'Idempotency-Key': `imagine-${id}` },
                    body: JSON.stringify({ model: selectedModel.id, prompt: this.composedPrompt(), size: requestedSize, quality: this.quality, outputFormat: this.format, n: 1, ...this.zImageParameters(), ...this.localEditParameters(selectedModel, editing), ...(editing ? { imageDataUrls } : {}) }),
                    signal: this.currentRunController.signal,
                }));
                const image = result?.image;
                if (!String(image?.dataUrl || '').startsWith('data:image/')) throw new Error(this.tr('noCloudImage'));
                const saved = await this.persistResult({ runId: run.id, miniAppId: this.miniAppId, pipelineId: this.currentMiniApp.legacyId, title: this.currentMiniApp.name, prompt: this.prompt.trim(), size: image.size || requestedSize, modelId: selectedModel.id, modelLabel: selectedModel.label.replace(/^AI2Apps (Cloud|Local) · /, ''), imageUrl: image.dataUrl, filename: this.resultFilename(id) });
                await this.updateRun(run.id, 'succeeded', 100, this.tr('completed'));
                await this.refreshRuns(); this.selectRun(this.runs.find(item => item.id === run.id));
                try { window.ai2appsShell?.accountChanged?.(); } catch (_) {}
            } catch (error) {
                if (run && !serverManaged && error?.name !== 'AbortError') {
                    try { await this.updateRun(run.id, 'failed', 100, this.tr('failed'), { code: 'image_generation_failed', message: error?.message || String(error) }); } catch (_) {}
                }
                if (error?.name !== 'AbortError') this.fail(error);
                await this.refreshRuns().catch(() => {});
            }
            finally { this.currentRunController = null; this.generating = false; this.icons(); }
        },
        async persistResult(result) {
            if ((!result?.imageFile && !result?.imageUrl) || !this.appInstanceId()) throw new Error(this.tr('missingInstance'));
            const metadata = {
                pipelineId: result.pipelineId || this.currentMiniApp.legacyId, miniAppId: result.miniAppId || this.miniAppId, runId: result.runId, title: result.title, prompt: result.prompt,
                modelId: result.modelId || this.modelId, modelLabel: result.modelLabel, size: result.size,
                quality: result.quality || this.quality, format: result.format || this.format, filename: result.filename,
            };
            if (result.imageFile) {
                let uploadStage = 'Reading rendered PNG';
                try {
                const bytes = new Uint8Array(await result.imageFile.arrayBuffer());
                const chunkSize = 192 * 1024; const total = Math.ceil(bytes.length / chunkSize);
                const uploadId = globalThis.crypto?.randomUUID?.() || `upload-${Date.now()}`; let saved = null;
                for (let index = 0; index < total; index += 1) {
                    uploadStage = `Uploading image chunk ${index + 1}/${total}`;
                    saved = await responsePayload(await fetch(`${HISTORY_API}/chunks`, {
                        method: 'POST', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' },
                        body: JSON.stringify({ uploadId, index, total, metadata, data: base64Bytes(bytes.subarray(index * chunkSize, Math.min(bytes.length, (index + 1) * chunkSize))) }),
                    }));
                }
                return saved;
                } catch (error) { throw new Error(`${uploadStage}: ${error?.message || String(error)}`); }
            }
            const file = await dataUrlFile(result.imageUrl, result.filename); const form = new FormData();
            form.append('metadata', JSON.stringify(metadata));
            form.append('image', file, file.name);
            return responsePayload(await fetch(HISTORY_API, { method: 'POST', credentials: 'same-origin', headers: this.historyHeaders(), body: form }));
        },
        async addArtifactToGallery(artifact) {
            if (!artifact?.id || artifact.adding || artifact.galleryAssetId) return;
            artifact.adding = true; this.runs = [...this.runs];
            try {
                const imported = await responsePayload(await fetch(`${STUDIO_API}/artifacts/${encodeURIComponent(artifact.id)}/gallery`, { method: 'POST', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ collectionId: this.galleryActiveCollectionId === 'recent' ? null : this.galleryActiveCollectionId }) }));
                artifact.galleryAssetId = imported.asset?.id || ''; if (!artifact.galleryAssetId) throw new Error(this.tr('galleryNoAsset'));
                this.$refs.galleryMini?.contentWindow?.postMessage({ type: 'ai2apps.gallery.refresh' }, window.location.origin); this.success(this.tr('addedToGallery', { name: this.galleryActiveCollectionName }));
            } catch (error) { this.fail(error); } finally { artifact.adding = false; this.runs = [...this.runs]; this.icons(); }
        },
        downloadArtifact(event, url) { if (!url) { event.preventDefault(); this.fail(new Error(this.tr('invalidHistoryUrl'))); return; } if (this.clientEnvironment !== 'desktop') this.success(this.tr('downloadStarted')); },

        async mountGalleryMini(force = false) {
            if (this.galleryMiniLoading || (this.galleryMiniUrl && !force)) return;
            this.galleryMiniLoading = true; this.galleryMiniError = '';
            if (force) { this.galleryMiniUrl = ''; this.galleryMiniMountId = ''; }
            try {
                const bridge = window.ai2appsShell;
                if (!bridge?.mountMiniEntry) { this.galleryMiniUrl = GALLERY_MINI_FALLBACK_URL; return; }
                const mount = await bridge.mountMiniEntry({ appId: 'ai2apps.gallery', placement: 'sidebar', requestedBy: APP_ID });
                if (!mount?.content_url) throw new Error(this.tr('miniNoUrl')); this.galleryMiniMountId = mount.id || ''; this.galleryMiniUrl = mount.content_url;
            } catch (error) {
                // A restored inner App frame can briefly retain an obsolete Shell
                // mount token. Keep the first-party Gallery usable while a later
                // Shell refresh establishes a new instance-bound bridge.
                if (galleryHostUnavailable(error)) this.galleryMiniUrl = GALLERY_MINI_FALLBACK_URL;
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
                let assetReference = null;
                if (!file) {
                    const assetId = event.dataTransfer?.getData('application/x-ai2apps-gallery-asset') || '';
                    if (!assetId || !this.appInstanceId()) return;
                    const target = imageSlot !== null ? Number(imageSlot) : (Array.from({ length: this.currentMiniApp.needsImages ? this.currentMiniApp.maxImages : 1 }, (_, index) => index).find(index => !this.referenceFiles[index]) ?? 0);
                    if (!this.currentMiniApp.needsImages) this.miniAppId = 'ai2apps.imagine.image-edit';
                    await this.materializeAssetReference({ assetId }, Math.min(target, this.currentMiniApp.maxImages - 1)); this.persistPreferences(); return;
                }
                if (!String(file.type || '').startsWith('image/')) throw new Error(this.tr('appImageOnly'));
                if (!this.currentMiniApp.needsImages) { this.miniAppId = 'ai2apps.imagine.image-edit'; this.recentMiniApps = [this.miniAppId, ...this.recentMiniApps.filter(value => value !== this.miniAppId)].slice(0, 8); }
                const limit = this.currentMiniApp.maxImages;
                const empty = Array.from({ length: limit }, (_, index) => index).find(index => !this.referenceFiles[index]);
                const target = imageSlot !== null ? Number(imageSlot) : (empty ?? 0); await this.setReference(Math.min(target, limit - 1), file, assetReference); this.persistPreferences();
            } catch (error) { this.fail(error); }
        },
    }; };
})();
