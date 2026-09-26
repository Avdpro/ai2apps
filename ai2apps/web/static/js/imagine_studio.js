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
            productStudioName: '商品摄影棚', productStudioSummary: '为商品打造布景、灯光与展示构图', productStudioDescription: '以商品照片为参考生成展示图；Logo、标签与外形需人工核对，不保证像素级保真。', productStudioAction: '拍摄商品图', productStudioRun: '商品摄影', productStudioPlaceholder: '可选：需要保留的细节、道具或禁止出现的元素。',
            stickerName: '表情包工坊', stickerSummary: '把人物或宠物变成专属表情贴纸', stickerDescription: '上传参考照片，选择表情，生成独立白底贴纸。支持整组生成与单张重做。', stickerAction: '制作表情', stickerRun: '表情贴纸', stickerPlaceholder: '可选：希望保留的配饰、服装或其他细节。',
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
            productStudioName: 'Product Photo Studio', productStudioSummary: 'Stage, light and compose product photographs', productStudioDescription: 'Generate product scenes from a photo. Review logos, labels and geometry; pixel-exact preservation is not guaranteed.', productStudioAction: 'Create product photo', productStudioRun: 'Product photography', productStudioPlaceholder: 'Optional: details to preserve, props or elements to avoid.',
            stickerName: 'Sticker Workshop', stickerSummary: 'Personal stickers from people or pets', stickerDescription: 'Create separate white-background stickers from a reference photo, one at a time or as a set.', stickerAction: 'Create sticker', stickerRun: 'Sticker', stickerPlaceholder: 'Optional: accessories, clothing or details to preserve.',
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
        { id: 'ai2apps.imagine.adjust-image', legacyId: 'adjust-image', adapter: 'adjust-image', version: '1.0.0', status: 'ready', source: 'official', category: 'edit', mode: 'adjust', icon: 'sliders-horizontal', needsImages: true, requiresImage: true, maxImages: 1, prefix: 'adjust' },
        { id: 'ai2apps.imagine.style-transfer', legacyId: 'style-transfer', adapter: 'style-transfer', version: '1.0.0', status: 'ready', source: 'official', category: 'edit', mode: 'style-transfer', icon: 'wand-sparkles', needsImages: true, requiresImage: true, maxImages: 1, prefix: 'styleTransfer' },
        { id: 'ai2apps.imagine.reference-creation', legacyId: 'reference-create', adapter: 'reference-creation', version: '1.0.0', status: 'ready', source: 'official', category: 'create', mode: 'reference', icon: 'images', needsImages: true, requiresImage: true, maxImages: 4, prefix: 'reference' },
        { id: 'ai2apps.imagine.sticker-workshop', legacyId: 'sticker-workshop', adapter: 'sticker-workshop', version: '1.0.0', status: 'ready', source: 'official', category: 'create', mode: 'sticker', icon: 'smile', needsImages: true, requiresImage: true, maxImages: 1, prefix: 'sticker' },
        { id: 'ai2apps.imagine.group-photo', legacyId: 'group-photo', adapter: 'group-photo', version: '1.0.0', status: 'ready', source: 'official', category: 'create', mode: 'group-photo', icon: 'users-round', needsImages: true, requiresImage: true, maxImages: 4, personSlots: 3, backgroundSlot: 3, prefix: 'groupPhoto' },
        { id: 'ai2apps.imagine.product-poster', legacyId: 'product-poster', adapter: 'product-poster', version: '1.0.0', status: 'ready', source: 'official', category: 'create', mode: 'product-photo', icon: 'shopping-bag', needsImages: true, requiresImage: true, maxImages: 1, prefix: 'productStudio' },
        { id: 'ai2apps.imagine.character-design', adapter: 'character-design', version: 'Planned', status: 'unavailable', source: 'official', category: 'project', mode: 'project', icon: 'user-round-cog', needsImages: true, requiresImage: false, maxImages: 4, prefix: 'characterDesign' },
        { id: 'ai2apps.imagine.comic-storyboard', adapter: 'comic-storyboard', version: 'Planned', status: 'unavailable', source: 'official', category: 'project', mode: 'project', icon: 'panels-top-left', needsImages: true, requiresImage: false, maxImages: 4, prefix: 'comicStoryboard' },
    ];
    // Shared UI strings: keep workflow instructions separate from display text.
    Object.assign(TRANSLATIONS.zh, {
        "stickerProgress": "整组进度：{done}/{total}",
        "stickerStop": "完成当前张后停止",
        "stickerIntro": "上传一张人物或宠物照片，再选择表情。每次生成一张独立白底贴纸，不是四格拼图；可使用下方视觉风格。",
        "stickerSet": "生成整组 · 4 张",
        "stickerSetHint": "整组将执行 4 次生成；Cloud 按每张计费。中途失败会停止，已完成结果保留在右侧。",
        "stickerSetConfirm": "将依次生成 4 张独立表情。Cloud 模型会上传参考图并分别计费；是否继续？",
        "productIntro": "上传清晰商品照，选择布景与光线。生成结果可能改变细节，请核对 Logo、标签文字和商品结构后再用于展示。",
        "productScenesLabel": "布景预设",
        "productLighting": "光线",
        "productCompositionLabel": "构图与留白",
        "productSceneRequired": "场景描述（必填）",
        "productSceneOptional": "场景补充（可选）",
        "productScenePlaceholder": "例如：米色背景，亚麻桌布，少量绿植，不要遮挡商品。",
        "productApplyStyle": "将下方视觉风格用于布景（默认不使用）",
        "chat": "聊天",
        "openingMiniApp": "正在打开 Mini-App…",
        "dependenciesReady": "依赖已就绪",
        "setupRequired": "需要配置",
        "planned": "规划中",
        "negativePrompt": "负面提示词",
        "outputTitle": "输出",
        "qualityAuto": "自动",
        "qualityLow": "低",
        "qualityMedium": "中",
        "qualityHigh": "高",
        "qualityXhigh": "超高",
        "qualityMax": "最高",
        "chatUnavailable": "Mini-App 聊天服务尚未就绪",
        "waitGeneration": "请等待生成完成后再修改输入",
        "inputMissing": "当前 Mini-App 缺少必需的输入或配置",
        "unknownTool": "未知的 Mini-App 工具",
        "localModelMissing": "ACPF 已完成，但未发现就绪的本地绘图模型。",
        "miniAppUrlMissing": "Mini-App 内容地址不可用",
        "readingPng": "正在读取渲染后的 PNG",
        "uploadChunk": "正在上传图片分块 {number}/{total}"
    });
    Object.assign(TRANSLATIONS.en, {
        "stickerProgress": "Set progress: {done}/{total}",
        "stickerStop": "Stop after current image",
        "stickerIntro": "Upload a person or pet photo and choose an emotion. Each result is a separate white-background sticker, not a collage. Choose a visual style below.",
        "stickerSet": "Generate set · 4 images",
        "stickerSetHint": "A set makes 4 generation requests; Cloud charges per image. Stops on failure and preserves completed results in Output.",
        "stickerSetConfirm": "Generate 4 separate stickers? Cloud models upload the reference and charge for each image.",
        "productIntro": "Upload a clear product photo and choose a scene and lighting. Review generated logos, label text and product geometry before use.",
        "productScenesLabel": "Scene presets",
        "productLighting": "Lighting",
        "productCompositionLabel": "Composition and copy space",
        "productSceneRequired": "Scene description (required)",
        "productSceneOptional": "Scene details (optional)",
        "productScenePlaceholder": "For example: beige backdrop, linen tabletop, subtle greenery; no props obscuring the product.",
        "productApplyStyle": "Apply the visual style below to the setting (off by default)",
        "chat": "Chat",
        "openingMiniApp": "Opening Mini-App…",
        "dependenciesReady": "Dependencies ready",
        "setupRequired": "Setup required",
        "planned": "Planned",
        "negativePrompt": "Negative prompt",
        "outputTitle": "Output",
        "qualityAuto": "Auto",
        "qualityLow": "Low",
        "qualityMedium": "Medium",
        "qualityHigh": "High",
        "qualityXhigh": "Extra high",
        "qualityMax": "Max",
        "chatUnavailable": "Package Mini-App Chat provider is not ready",
        "waitGeneration": "Wait for generation to finish before changing inputs",
        "inputMissing": "The current Mini-App is missing required input or configuration",
        "unknownTool": "Unknown Mini-App Tool",
        "localModelMissing": "ACPF completed, but no ready local image model was discovered.",
        "miniAppUrlMissing": "Mini-App content URL is unavailable",
        "readingPng": "Reading rendered PNG",
        "uploadChunk": "Uploading image chunk {number}/{total}"
    });
    Object.assign(TRANSLATIONS.zh, {
        "productSceneWhite": "纯白棚拍",
        "productSceneStone": "石材展台",
        "productSceneLifestyle": "生活桌面",
        "productSceneOutdoors": "自然户外",
        "productSceneGift": "节日礼赠",
        "productSceneCustom": "自定义场景",
        "productLightSoftbox": "柔光棚拍",
        "productLightWindow": "自然窗光",
        "productLightRim": "轮廓光",
        "productCompositionCenter": "居中展示",
        "productCompositionLeft": "商品居左 · 右侧留白",
        "productCompositionRight": "商品居右 · 左侧留白",
        "stickerHappy": "开心",
        "stickerLove": "比心",
        "stickerSurprised": "震惊",
        "stickerPleading": "委屈"
    });
    Object.assign(TRANSLATIONS.en, {
        "productSceneWhite": "White studio",
        "productSceneStone": "Stone podium",
        "productSceneLifestyle": "Lifestyle tabletop",
        "productSceneOutdoors": "Outdoors",
        "productSceneGift": "Gift setting",
        "productSceneCustom": "Custom scene",
        "productLightSoftbox": "Softbox",
        "productLightWindow": "Window light",
        "productLightRim": "Rim light",
        "productCompositionCenter": "Centered",
        "productCompositionLeft": "Product left / copy space right",
        "productCompositionRight": "Product right / copy space left",
        "stickerHappy": "Happy",
        "stickerLove": "Love",
        "stickerSurprised": "Surprised",
        "stickerPleading": "Pleading"
    });
    Object.assign(TRANSLATIONS.zh, {
        "preparingAdjustment": "正在准备调整",
        "renderingFullImage": "正在渲染全分辨率图片",
        "encodingPng": "正在编码 PNG",
        "savingArtifact": "正在保存图片成果",
        "updateDraftTitle": "更新图片草稿",
        "updateDraftDescription": "更新当前 Mini-App 的提示词和生成设置。",
        "runDraftDescription": "使用当前草稿和参考图片运行 Mini-App。"
    });
    Object.assign(TRANSLATIONS.en, {
        "preparingAdjustment": "Preparing adjustment",
        "renderingFullImage": "Rendering full-resolution image",
        "encodingPng": "Encoding PNG",
        "savingArtifact": "Saving image artifact",
        "updateDraftTitle": "Update image draft",
        "updateDraftDescription": "Update the prompt and supported generation settings for the current Mini-App.",
        "runDraftDescription": "Run the current Mini-App using the visible draft and selected references."
    });
    Object.assign(TRANSLATIONS.zh, {
        portraitName: '人像摄影棚', portraitSummary: '证件照、杂志封面与生活写真', portraitDescription: '以单人照片为参考，选择拍摄模式、服装与场景。', portraitAction: '生成人像', portraitRun: '人像生成', portraitPlaceholder: '可选：希望保留的细节或其他拍摄要求。',
        portraitIntro: '上传一张清晰的单人照片。Custom 衣着可另加服装参考图；第二张图片只用于衣着，不用于人物身份。', portraitMode: '拍摄模式', portraitId: '证件照', portraitCover: '杂志封面', portraitLifestyle: '生活写真', portraitClothing: '衣着', portraitKeep: '保留原衣着', portraitSuit: '商务西装', portraitShirt: '简洁衬衫', portraitCasual: '休闲服装', portraitCustom: '自定义 · Custom', portraitPerson: '人物参考照', portraitOutfit: '服装参考图', portraitCustomHint: '选择 Custom 后必须上传服装参考图。请提供清晰的服装照片。',
        portraitBackground: '背景颜色', portraitWhite: '白色', portraitBlue: '蓝色', portraitRed: '红色', portraitGray: '浅灰色', portraitFraming: '取景', portraitHead: '头肩照', portraitHalf: '半身照', portraitFull: '全身照', portraitRatio: '画面比例 / 尺寸', portraitIdNotice: '仅生成证件照风格图片，不保证符合护照、签证或官方证件要求；使用前请核对尺寸及规定。证件照模式不应用视觉风格。',
        portraitCoverTitle: '封面刊名（可选）', portraitCoverTitleHint: '留空时仅生成封面人像与排版留白，不生成文字。', portraitCoverMood: '封面风格', portraitMinimal: '极简时尚', portraitBold: '大胆色彩', portraitClassic: '经典黑白', portraitCoverNotice: 'AI 生成的刊名文字可能不准确，请核对；也可留空后自行排版。', portraitScene: '生活场景', portraitCafe: '街角咖啡馆', portraitPark: '户外公园', portraitHome: '温馨室内', portraitBeach: '海边', portraitLight: '光线', portraitDaylight: '柔和自然光', portraitGolden: '日落金色光', portraitStudioLight: '柔光棚灯', portraitPose: '姿势与气氛（可选）', portraitPoseHint: '例如：自然微笑，轻松站姿，视线看向镜头。',
    });
    Object.assign(TRANSLATIONS.en, {
        portraitName: 'Portrait', portraitSummary: 'Photo-ID, magazine covers and lifestyle portraits', portraitDescription: 'Create a solo portrait from a photo with mode, outfit and scene controls.', portraitAction: 'Create portrait', portraitRun: 'Portrait generation', portraitPlaceholder: 'Optional: details to preserve or additional photography instructions.',
        portraitIntro: 'Upload a clear photo of one person. Custom clothing accepts an extra outfit reference; image 2 is used for clothing only, not identity.', portraitMode: 'Portrait mode', portraitId: 'Photo-ID', portraitCover: 'Magazine cover', portraitLifestyle: 'Lifestyle', portraitClothing: 'Clothing', portraitKeep: 'Keep original outfit', portraitSuit: 'Business suit', portraitShirt: 'Simple shirt', portraitCasual: 'Casual wear', portraitCustom: 'Custom', portraitPerson: 'Person reference', portraitOutfit: 'Clothing reference', portraitCustomHint: 'Custom requires a clothing reference image. Use a clear photo of the outfit.',
        portraitBackground: 'Background color', portraitWhite: 'White', portraitBlue: 'Blue', portraitRed: 'Red', portraitGray: 'Light gray', portraitFraming: 'Framing', portraitHead: 'Head and shoulders', portraitHalf: 'Half body', portraitFull: 'Full body', portraitRatio: 'Aspect ratio / size', portraitIdNotice: 'Photo-ID styling only; compliance with passport, visa or official ID rules is not guaranteed. Check dimensions and requirements before use. Visual style is not applied in this mode.',
        portraitCoverTitle: 'Cover title (optional)', portraitCoverTitleHint: 'Leave blank for a cover portrait with copy space and no text.', portraitCoverMood: 'Cover style', portraitMinimal: 'Minimal fashion', portraitBold: 'Bold color', portraitClassic: 'Classic monochrome', portraitCoverNotice: 'AI-generated title text may be inaccurate. Review it, or leave blank and add typography later.', portraitScene: 'Lifestyle scene', portraitCafe: 'Street café', portraitPark: 'Outdoor park', portraitHome: 'Cozy interior', portraitBeach: 'Beach', portraitLight: 'Lighting', portraitDaylight: 'Soft daylight', portraitGolden: 'Golden hour', portraitStudioLight: 'Soft studio lighting', portraitPose: 'Pose and mood (optional)', portraitPoseHint: 'For example: a natural smile, relaxed standing pose, looking at the camera.',
    });
    MINI_APP_DEFS.splice(MINI_APP_DEFS.findIndex(item => item.prefix === 'groupPhoto'), 0, {
        id: 'ai2apps.imagine.portrait', legacyId: 'portrait', adapter: 'portrait', version: '1.0.0', status: 'ready', source: 'official', category: 'create', mode: 'portrait', icon: 'contact-round', needsImages: true, requiresImage: true, maxImages: 2, prefix: 'portrait',
    });
    Object.assign(TRANSLATIONS.zh, { submittedPrompt: '实际提交的 Prompt', submittedPromptHint: '显示实际发送给模型的完整文本，可直接编辑。修改上方参数后会重新生成并替换手动修改；图片、尺寸等另行提交。', resetSubmittedPrompt: '恢复自动 Prompt', promptEdited: '已手动编辑', promptAutomatic: '自动生成', submittedPromptInvalid: '提交的 Prompt 不能为空，且不能超过 32000 个字符。' });
    Object.assign(TRANSLATIONS.en, { submittedPrompt: 'Prompt sent to model', submittedPromptHint: 'The complete text sent to the model. Edit it directly; changing the settings above regenerates it and replaces manual edits. Images, size and other parameters are sent separately.', resetSubmittedPrompt: 'Restore automatic prompt', promptEdited: 'Manually edited', promptAutomatic: 'Automatic', submittedPromptInvalid: 'The submitted prompt must contain 1–32000 characters.' });
    Object.assign(TRANSLATIONS.zh, { extractName:'提取物品', extractSummary:'从照片提取衣着或指定物品参考图', extractDescription:'选择物品或输入描述，生成独立白底参考图。', extractAction:'提取物品', extractRun:'物品提取', extractPlaceholder:'可选：物品位置、颜色或需要保留的细节。', extractTarget:'提取目标', extractOutfit:'整套穿着', extractClothes:'衣服', extractTop:'上衣', extractPants:'裤子', extractSkirt:'裙子', extractDress:'连衣裙', extractShoes:'鞋子', extractBag:'包', extractCustom:'自定义', extractCustomLabel:'物品描述（必填）', extractCustomHint:'例如：左侧人物穿的黑色夹克，或桌上的红色杯子。', extractIntro:'上传原照片，选择要提取的物品；有多个相似物品时，请在补充说明中指明位置。输出为独立白底物品参考图，不包含人物。', extractNotice:'这是 AI 重建参考图，不是精确抠图；遮挡部分可能被补全，图案、标签和细节请人工核对。不保证透明背景；不应用全局视觉风格。' });
    Object.assign(TRANSLATIONS.en, { extractName:'Extract Items', extractSummary:'Extract clothing or objects as reference images', extractDescription:'Choose an item or describe it to create an isolated white-background reference.', extractAction:'Extract item', extractRun:'Item extraction', extractPlaceholder:'Optional: item location, color or details to preserve.', extractTarget:'Extraction target', extractOutfit:'Complete outfit', extractClothes:'Clothing', extractTop:'Top', extractPants:'Pants', extractSkirt:'Skirt', extractDress:'Dress', extractShoes:'Shoes', extractBag:'Bag', extractCustom:'Custom', extractCustomLabel:'Item description (required)', extractCustomHint:'For example: the black jacket worn by the person on the left, or the red mug on the table.', extractIntro:'Upload a photo and choose the item. If several similar items are present, specify its location in the additional instructions. The result is an isolated item reference on white, without people.', extractNotice:'AI reconstruction, not pixel-exact cutout. Occluded parts may be inferred; review patterns, labels and details. Transparency is not guaranteed. Shared visual style is not applied.' });
    MINI_APP_DEFS.splice(MINI_APP_DEFS.findIndex(item => item.prefix === 'portrait') + 1, 0, { id:'ai2apps.imagine.extract-items', legacyId:'extract-items', adapter:'extract-items', version:'1.0.0', status:'ready', source:'official', category:'create', mode:'extract-items', icon:'scissors', needsImages:true, requiresImage:true, maxImages:1, prefix:'extract' });
    Object.assign(TRANSLATIONS.zh, {tryOnName:'试穿试用',tryOnSummary:'让人物试穿、使用或手持参考物品',tryOnDescription:'人物与物品双参考，选择动作、姿势和背景。',tryOnAction:'生成试穿试用图',tryOnRun:'试穿试用',tryOnPlaceholder:'可选：穿戴方式、物品位置或需要保留的细节。',tryOnIntro:'第一张为人物，第二张为物品。支持衣服、配饰和其他物品；物品图中的人物不会作为身份参考。',tryOnItem:'物品参考图',tryOnActionLabel:'互动方式',tryOnWear:'试穿 / 佩戴',tryOnUse:'使用物品',tryOnHold:'手持物品',tryOnPose:'姿势',tryOnKeepPose:'保留原姿势',tryOnStand:'自然站立',tryOnSit:'自然坐姿',tryOnWalk:'行走展示',tryOnCustom:'自定义',tryOnPoseDetails:'姿势描述（必填）',tryOnPoseHint:'例如：侧身站立，右手拿包，左手自然下垂。',tryOnBackground:'背景',tryOnKeepBackground:'保留原背景',tryOnWhite:'白色摄影棚',tryOnStreet:'城市街景',tryOnPark:'户外公园',tryOnRoom:'室内生活场景',tryOnBackgroundDetails:'背景描述（必填）',tryOnBackgroundHint:'例如：明亮的咖啡馆，木质桌面，柔和窗光。',tryOnNotice:'AI 效果预览，不代表真实尺码或合身度。请核对人物相似度、物品细节及手部接触关系；为保留原貌，不应用全局视觉风格。'});
    Object.assign(TRANSLATIONS.en, {tryOnName:'Try On',tryOnSummary:'Wear, use or hold an item from a reference',tryOnDescription:'Person and item references with action, pose and background controls.',tryOnAction:'Create try-on image',tryOnRun:'Try on',tryOnPlaceholder:'Optional: how to wear or use the item, placement or details to preserve.',tryOnIntro:'Image 1 is the person; image 2 is the item. Supports clothing, accessories and other objects. People in the item photo are not identity references.',tryOnItem:'Item reference',tryOnActionLabel:'Interaction',tryOnWear:'Wear',tryOnUse:'Use',tryOnHold:'Hold',tryOnPose:'Pose',tryOnKeepPose:'Keep original pose',tryOnStand:'Relaxed standing',tryOnSit:'Natural sitting',tryOnWalk:'Walking',tryOnCustom:'Custom',tryOnPoseDetails:'Pose description (required)',tryOnPoseHint:'For example: stand sideways, hold the bag in the right hand, left arm relaxed.',tryOnBackground:'Background',tryOnKeepBackground:'Keep original background',tryOnWhite:'White studio',tryOnStreet:'City street',tryOnPark:'Outdoor park',tryOnRoom:'Lifestyle interior',tryOnBackgroundDetails:'Background description (required)',tryOnBackgroundHint:'For example: a bright café, wooden table and soft window light.',tryOnNotice:'AI preview, not a guarantee of actual sizing or fit. Review identity, item details and hand/object contact. Shared visual style is not applied to preserve the references.'});
    MINI_APP_DEFS.splice(MINI_APP_DEFS.findIndex(item=>item.prefix==='extract')+1,0,{id:'ai2apps.imagine.try-on',legacyId:'try-on',adapter:'try-on',version:'1.0.0',status:'ready',source:'official',category:'create',mode:'try-on',icon:'shirt',needsImages:true,requiresImage:true,maxImages:2,prefix:'tryOn'});
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
        locale: normalizedLocale(document.documentElement.lang), miniApps: localizedMiniApps(document.documentElement.lang), miniAppId: 'ai2apps.imagine.text-to-image', leftView: 'mini-apps', prompt: '',
        groupBackgroundDescription: '', groupAtmosphere: '', groupPose: '',
        productScene: 'white', productLight: 'soft', productComposition: 'center', productSceneDescription: '', productUseStyle: false,
        get isProductPhotoMode() { return this.currentMiniApp.mode === 'product-photo'; },
        portraitMode: 'id', portraitClothing: 'keep', portraitBackground: 'white', portraitFraming: 'head', portraitCoverMood: 'minimal', portraitCoverTitle: '', portraitScene: 'cafe', portraitLight: 'daylight', portraitPose: '',
        get isPortraitMode() { return this.currentMiniApp.mode === 'portrait'; },
        extractTarget:'outfit', extractCustom:'',
        get isExtractMode() { return this.currentMiniApp.mode === 'extract-items'; },
        tryOnInteraction:'wear', tryOnPose:'keep', tryOnBackground:'keep', tryOnPoseText:'', tryOnBackgroundText:'',
        get isTryOnMode() { return this.currentMiniApp.mode === 'try-on'; },
        get tryOnOptions() { return {
            tryOnInteraction:[['wear','tryOnWear'],['use','tryOnUse'],['hold','tryOnHold']],
            tryOnPose:[['keep','tryOnKeepPose'],['stand','tryOnStand'],['sit','tryOnSit'],['walk','tryOnWalk'],['custom','tryOnCustom']],
            tryOnBackground:[['keep','tryOnKeepBackground'],['white','tryOnWhite'],['street','tryOnStreet'],['park','tryOnPark'],['room','tryOnRoom'],['custom','tryOnCustom']],
        }; },
        get tryOnReady() { return Boolean(this.referenceFiles[0] && this.referenceFiles[1]) && (this.tryOnPose!=='custom'||Boolean(this.tryOnPoseText.trim())) && (this.tryOnBackground!=='custom'||Boolean(this.tryOnBackgroundText.trim())); },
        tryOnDraft() { return Object.fromEntries([...Object.keys(this.tryOnOptions),'tryOnPoseText','tryOnBackgroundText'].map(key=>[key,this[key]])); },
        restoreTryOnDraft(draft) {
            for(const [key,options] of Object.entries(this.tryOnOptions)) this[key]=options.some(([id])=>id===draft[key])?draft[key]:options[0][0];
            this.tryOnPoseText=String(draft.tryOnPoseText||'').slice(0,2000);this.tryOnBackgroundText=String(draft.tryOnBackgroundText||'').slice(0,2000);
        },
        tryOnPrompt() {
            const action={wear:'Dress or accessorize the person with the referenced item in its appropriate wearing position. Replace only the corresponding original garment or accessory; preserve unrelated clothing.',use:'Show the person naturally using the referenced object according to its ordinary function, with physically plausible interaction.',hold:'Show the person holding the referenced object naturally, with anatomically correct hands and believable grip. Do not turn the object into clothing.'}[this.tryOnInteraction];
            const pose=this.tryOnPose==='custom'?this.tryOnPoseText.trim():{keep:'Preserve the original pose as closely as possible; make only the minimal limb changes required for the requested interaction.',stand:'Relaxed natural standing pose.',sit:'Natural seated pose.',walk:'Natural walking pose suitable for showing the item.'}[this.tryOnPose];
            const background=this.tryOnBackground==='custom'?this.tryOnBackgroundText.trim():{keep:'Preserve the background and camera perspective of image 1.',white:'A clean white photography studio.',street:'A realistic city street.',park:'A green outdoor park.',room:'A tasteful lived-in interior.'}[this.tryOnBackground];
            return ['Create ONE realistic image of exactly the person from image 1 interacting with the item from image 2. Image 1 is the ONLY identity reference: preserve recognizable face, apparent age, skin tone, hair and natural body proportions. Image 2 is ITEM ONLY: do not copy its model, face, body, pose or background. Preserve the item design, color, shape, material, pattern and existing markings; do not invent a substitute or duplicate it. Preserve unrelated details. Match scale, perspective, lighting, shadows, contact and occlusion; no extra people, limbs, fingers, captions or watermarks.',action,'Pose: '+pose,'Background: '+background,this.prompt.trim()].filter(Boolean).join('\n\n');
        },
        get extractOptions() { return [['outfit','extractOutfit','the complete worn outfit, including clothing, shoes and worn accessories, arranged together as separate items'],['clothes','extractClothes','all clothing, excluding shoes and accessories'],['top','extractTop','the upper-body garment'],['pants','extractPants','the pants or trousers'],['skirt','extractSkirt','the skirt'],['dress','extractDress','the dress'],['shoes','extractShoes','the shoes as a matching pair when visible'],['bag','extractBag','the bag'],['custom','extractCustom','']]; },
        get extractReady() { return Boolean(this.referenceFiles[0]) && (this.extractTarget !== 'custom' || Boolean(this.extractCustom.trim())); },
        restoreExtractDraft(draft) { this.extractTarget = this.extractOptions.some(([id]) => id === draft.extractTarget) ? draft.extractTarget : 'outfit'; this.extractCustom = String(draft.extractCustom || '').slice(0,2000); },
        extractPrompt() {
            const target = this.extractTarget === 'custom' ? this.extractCustom.trim() : this.extractOptions.find(([id]) => id === this.extractTarget)?.[2];
            return ['Create ONE clean object-reference image by extracting the specified target from input image 1.', 'Target: '+target+'.', 'Use the source as the authoritative reference. Preserve the visible item design, silhouette, proportions, colors, material, seams, patterns and existing markings as closely as possible. Remove the wearer, face, body, hands, mannequin and original background. Show the complete item unobstructed on a seamless pure white background, centered with generous margins, realistic lighting and only a subtle contact shadow. For multiple requested garments, use a neat flat-lay arrangement in a single image, no duplicates or panel grid. Do not add props, labels, captions or watermarks. Do not invent a different product or substitute an unrelated object. If reconstruction of hidden parts is necessary, keep it minimal and consistent with visible evidence.', this.prompt.trim()].filter(Boolean).join('\n\n');
        },
        get referenceSlotCount() { return this.isPortraitMode ? (this.portraitClothing === 'custom' ? 2 : 1) : this.currentMiniApp.maxImages; },
        get portraitReady() { return Boolean(this.referenceFiles[0]) && (this.portraitClothing !== 'custom' || Boolean(this.referenceFiles[1])); },
        get portraitOptions() { return {
            portraitMode: [['id','portraitId'],['cover','portraitCover'],['lifestyle','portraitLifestyle']],
            portraitClothing: [['keep','portraitKeep'],['suit','portraitSuit'],['shirt','portraitShirt'],['casual','portraitCasual'],['custom','portraitCustom']],
            portraitBackground: [['white','portraitWhite'],['blue','portraitBlue'],['red','portraitRed'],['gray','portraitGray']],
            portraitFraming: [['head','portraitHead'],['half','portraitHalf'],['full','portraitFull']],
            portraitCoverMood: [['minimal','portraitMinimal'],['bold','portraitBold'],['classic','portraitClassic']],
            portraitScene: [['cafe','portraitCafe'],['park','portraitPark'],['home','portraitHome'],['beach','portraitBeach']],
            portraitLight: [['daylight','portraitDaylight'],['golden','portraitGolden'],['studio','portraitStudioLight']],
        }; },
        restorePortraitDraft(draft) {
            for (const [field, choices] of Object.entries(this.portraitOptions)) this[field] = choices.some(([id]) => id === draft[field]) ? draft[field] : choices[0][0];
            this.portraitCoverTitle = String(draft.portraitCoverTitle || '').slice(0, 100);
            this.portraitPose = String(draft.portraitPose || '').slice(0, 2000);
        },
        portraitDraft() { return Object.fromEntries([...Object.keys(this.portraitOptions), 'portraitCoverTitle', 'portraitPose'].map(key => [key, this[key]])); },
        portraitClothingChanged() {
            if (this.portraitClothing !== 'custom') this.clearReference(1);
            this.reconcileSelectedModel(); this.scheduleDraftSave();
        },
        portraitPrompt() {
            const clothing = {
                keep: 'Preserve the original outfit from image 1.', suit: 'Dress the subject in a well-fitted neutral business suit.', shirt: 'Dress the subject in a simple neat collared shirt.', casual: 'Dress the subject in tasteful casual clothing.',
                custom: 'Image 2 is CLOTHING ONLY: transfer its outfit design, color, fabric and fit to the person in image 1. Never copy the face, body identity, background or pose of any person in image 2.',
            }[this.portraitClothing];
            const framing = {head:'head-and-shoulders', half:'half-body', full:'full-body'}[this.portraitFraming];
            let mode;
            if (this.portraitMode === 'id') mode = `Create a realistic Photo-ID-style head-and-shoulders portrait, facing straight at the camera, centered, upright, eyes visible, neutral expression, even lighting and a flat solid ${this.portraitBackground} background. Preserve natural facial proportions and skin texture; no beautification that changes identity. No text, logos, props or decorations.`;
            else if (this.portraitMode === 'cover') mode = `Create a professional magazine cover portrait, ${framing} framing, ${ {minimal:'minimal fashion editorial',bold:'bold colorful editorial',classic:'classic black-and-white editorial'}[this.portraitCoverMood] }. Leave clear typography space without covering the face. ${this.portraitCoverTitle.trim() ? 'Use this cover title only: '+JSON.stringify(this.portraitCoverTitle.trim())+'. No other text.' : 'Do not render any text, letters, brands or watermarks.'}`;
            else mode = `Create a natural lifestyle photograph, ${framing} framing, in a ${ {cafe:'street café',park:'green outdoor park',home:'cozy home interior',beach:'seaside beach'}[this.portraitScene] }, with ${ {daylight:'soft natural daylight',golden:'warm golden-hour light',studio:'soft studio-style lighting'}[this.portraitLight] }. ${this.portraitPose.trim() || 'Relaxed natural pose and expression.'}`;
            return ['Create ONE solo portrait of exactly the person in input image 1. Preserve their recognizable facial identity, apparent age, skin tone and distinctive features. No extra people, no duplicated faces, no collage. Clothing changes must not alter identity.', mode, clothing,
                this.portraitMode !== 'id' ? this.selectedStyle?.prompt || '' : '', this.prompt.trim()].filter(Boolean).join('\n\n');
        },
        get productScenes() { return [
            {id:'white', labelKey: 'productSceneWhite', prompt:'Seamless pure white studio background, subtle natural contact shadow.'},
            {id:'stone', labelKey: 'productSceneStone', prompt:'Minimal neutral stone podium with a refined studio backdrop.'},
            {id:'desk', labelKey: 'productSceneLifestyle', prompt:'Tasteful natural wood tabletop in a clean interior, restrained supporting props.'},
            {id:'nature', labelKey: 'productSceneOutdoors', prompt:'Natural outdoor setting with soft greenery in the distance and realistic scale.'},
            {id:'festival', labelKey: 'productSceneGift', prompt:'Elegant gift-giving scene with subtle ribbons and warm festive accents, no text.'},
            {id:'custom', labelKey: 'productSceneCustom', prompt:''},
        ]; },
        get productLights() { return [
            {id:'soft', labelKey: 'productLightSoftbox', prompt:'Large softbox lighting, controlled reflections and soft shadows.'},
            {id:'window', labelKey: 'productLightWindow', prompt:'Natural diffused window light and realistic gentle shadows.'},
            {id:'dramatic', labelKey: 'productLightRim', prompt:'Dramatic but readable rim lighting, preserve accurate product colors and material.'},
        ]; },
        get productCompositions() { return [
            {id:'center', labelKey: 'productCompositionCenter', prompt:'Center the entire product with generous margins; preserve its original viewing angle.'},
            {id:'left', labelKey: 'productCompositionLeft', prompt:'Place the entire product on the left, leave uncluttered negative space on the right for later typesetting.'},
            {id:'right', labelKey: 'productCompositionRight', prompt:'Place the entire product on the right, leave uncluttered negative space on the left for later typesetting.'},
        ]; },
        get productPhotoReady() { return this.productScene !== 'custom' || Boolean(this.productSceneDescription.trim()); },
        restoreProductDraft(draft) {
            for (const [field, choices] of [['productScene',this.productScenes],['productLight',this.productLights],['productComposition',this.productCompositions]]) {
                this[field] = choices.some(item => item.id === draft[field]) ? draft[field] : choices[0].id;
            }
            this.productSceneDescription = String(draft.productSceneDescription || '').slice(0,2000);
            this.productUseStyle = draft.productUseStyle === true;
        },
        productPhotoPrompt() {
            const choose = (items, id) => (items.find(item => item.id === id) || items[0]).prompt;
            return ['Create ONE professional product photograph using the supplied image as the authoritative product reference. Preserve the exact product identity, silhouette, proportions, visible parts, packaging, original colors, material, logos and existing readable label text. Keep the original product viewing angle; do not invent hidden surfaces or new branding. Do not add people, duplicate products, prices, slogans or watermarks. Change the setting and lighting, not the product design. Maintain realistic contact shadows, perspective, reflections and scale.',
                choose(this.productScenes,this.productScene), this.productSceneDescription.trim(), choose(this.productLights,this.productLight), choose(this.productCompositions,this.productComposition),
                this.productUseStyle && this.selectedStyle ? 'Apply the following style only to the setting, not the product: '+this.selectedStyle.prompt : '', this.prompt.trim()
            ].filter(Boolean).join('\n\n');
        },
        stickerEmotion: 'happy', stickerBatchBusy: false, stickerBatchStop: false, stickerBatchDone: 0,
        get isStickerMode() { return this.currentMiniApp.mode === 'sticker'; },
        get stickerEmotions() { return [
            { id: 'happy', icon: '😄', labelKey: 'stickerHappy', instruction: 'Laughing joyfully, cheerful expressive eyes.' },
            { id: 'love', icon: '🥰', labelKey: 'stickerLove', instruction: 'Express affection with hearts, a warm loving expression.' },
            { id: 'wow', icon: '😮', labelKey: 'stickerSurprised', instruction: 'Amazed and surprised, wide eyes and open mouth.' },
            { id: 'sad', icon: '🥺', labelKey: 'stickerPleading', instruction: 'An adorable pleading expression with teary eyes.' },
        ]; },
        stickerLabel(item) { return this.tr(item.labelKey); },
        stickerPrompt() {
            const emotion = this.stickerEmotions.find(item => item.id === this.stickerEmotion) || this.stickerEmotions[0];
            return ['Create ONE expressive die-cut chat sticker of the main person or pet in the reference image. Preserve recognizable identity, hairstyle or fur markings and distinctive accessories. Only one subject, not a grid or collage. Cute clean illustration, bold contours, white sticker border, plain pure white background, generous margins, entire subject within the canvas. No letters, words, watermark or captions.', emotion.instruction, this.selectedStyle?.prompt || '', this.prompt.trim()].filter(Boolean).join('\n\n');
        },
        async generateStickerSet() {
            if (!this.isStickerMode || !this.canGenerate || this.generating || this.stickerBatchBusy) return;
            const message = this.tr('stickerSetConfirm');
            if (!window.confirm(message)) return;
            this.stickerBatchBusy = true; this.stickerBatchStop = false; this.stickerBatchDone = 0;
            try {
                for (const emotion of this.stickerEmotions) {
                    if (this.stickerBatchStop) break;
                    this.stickerEmotion = emotion.id;
                    const result = await this.generate(null, { stickerBatch: true });
                    if (!result || result.status !== 'succeeded') break;
                    this.stickerBatchDone += 1;
                }
            } catch (error) { this.fail(error); }
            finally { this.stickerBatchBusy = false; this.scheduleDraftSave(); }
        },
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
        get prefersOpenAIModel() { return this.isStyleTransferMode || this.isGroupPhotoMode || this.isStickerMode || this.isProductPhotoMode || this.isPortraitMode || this.isExtractMode || this.isTryOnMode; },
        get groupPersonFiles() { return this.referenceFiles.slice(0, this.currentMiniApp.personSlots || 0).filter(Boolean); },
        get groupBackgroundFile() { return this.referenceFiles[this.currentMiniApp.backgroundSlot] || null; },
        get groupPhotoReady() { return this.groupPersonFiles.length >= 2 && Boolean(this.groupBackgroundFile || this.groupBackgroundDescription.trim()); },
        get filteredMiniApps() {
            return [...this.miniApps].sort((a, b) => (a.status === 'ready' ? 0 : 1) - (b.status === 'ready' ? 0 : 1));
        },
        get requiredOperation() { return this.currentMiniApp.mode === 'generate' ? 'image_generation' : 'image_edit'; },
        get compatibleModels() {
            const minimum = this.isTryOnMode || this.isGroupPhotoMode || (this.isPortraitMode && this.portraitClothing === 'custom') ? 2 : 1;
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
        get canGenerate() { const hasInstruction = this.isTryOnMode ? this.tryOnReady : this.isExtractMode ? this.extractReady : this.isStyleTransferMode ? Boolean(this.selectedStyle) : (this.isGroupPhotoMode ? this.groupPhotoReady : (this.isPortraitMode ? this.portraitReady : (this.isStickerMode || (this.isProductPhotoMode ? this.productPhotoReady : Boolean(this.submissionPrompt.trim()))))); return this.currentMiniApp.status === 'ready' && Boolean(this.selectedModel) && hasInstruction && this.submissionPromptValid && !this.sizeError && (!this.currentMiniApp.requiresImage || this.referenceFiles.some(Boolean)); },
        get selectedRun() { return this.runs.find(item => item.id === this.selectedRunId) || this.runs[0] || null; },
        get activeArtifact() { const items = this.selectedRun?.artifacts || []; return items.find(item => item.id === this.selectedArtifactId) || items.find(item => item.final) || items[0] || null; },
        get qualityOptions() { return this.selectedModel?.qualities?.length ? this.selectedModel.qualities : ['auto']; },
        qualityLabel(value) { const key = 'quality' + value.charAt(0).toUpperCase() + value.slice(1); return this.tr(key) === key ? value : this.tr(key); },
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
        get promptFieldLabel() { return this.tr((this.isStyleTransferMode || this.isGroupPhotoMode || this.isProductPhotoMode || this.isPortraitMode || this.isExtractMode || this.isTryOnMode) ? 'additionalInstructions' : 'prompt'); },
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
                    await this.refresh(); this.success(this.tr('dependenciesReady'));
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
            this.adjustmentExporting = true; this.dismissNotice(); let run = null; let stage = this.tr('preparingAdjustment');
            const id = globalThis.crypto?.randomUUID?.() || `adjust-${Date.now()}`;
            const input = { ...this.draftPayload(), prompt: '', sourceName: this.referenceFiles[0]?.name || '', adjustmentState: window.ImagineAdjustEngine.clone(this.adjustState) };
            try {
                await this.saveDraft(); run = await this.createRun(input, retryOf); this.runs = [run, ...this.runs]; this.selectRun(run);
                run = await this.updateRun(run.id, 'running', 20, this.tr('localAdjustments')); this.runs = this.runs.map(item => item.id === run.id ? run : item);
                await new Promise(resolve => requestAnimationFrame(resolve));
                stage = this.tr('renderingFullImage');
                const canvas = document.createElement('canvas'); const rendered = window.ImagineAdjustEngine.render(this.adjustBitmap, canvas, this.adjustState, 0);
                const filename = `imagine-adjust-${id.slice(-8)}.png`;
                stage = this.tr('encodingPng');
                const imageFile = await canvasFile(canvas, filename);
                stage = this.tr('savingArtifact');
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
                if (!this.packageChatBridge) throw new Error(this.tr('chatUnavailable'));
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
                    { name: 'update_current_draft', title: this.tr('updateDraftTitle'), description: this.tr('updateDraftDescription'), inputSchema: { type: 'object', properties: {
                        prompt: { type: 'string', maxLength: 32000 }, modelId: { type: 'string' }, size: { type: 'string' }, quality: { type: 'string' }, format: { type: 'string' }, styleId: { type: 'string' },
                        background: { type: 'string', maxLength: 4000 }, atmosphere: { type: 'string', maxLength: 2000 }, pose: { type: 'string', maxLength: 4000 },
                    }, additionalProperties: false } },
                    { name: 'run_current', title: this.tr(this.isAdjustMode ? 'exportAdjustment' : 'startGenerate'), description: this.tr('runDraftDescription'), inputSchema: { type: 'object', properties: {}, additionalProperties: false }, confirmation: 'always' },
                ],
            };
        },
        async readMiniAppHelp() {
            if (this.currentMiniApp.source === 'package') {
                if (!this.packageChatBridge) throw new Error(this.tr('chatUnavailable'));
                return this.packageChatBridge.help();
            }
            return window.AI2AppsMiniAppChat.loadBuiltinHelp(this.currentMiniApp);
        },
        async invokeMiniAppChatTool(name, args) {
            if (this.currentMiniApp.source === 'package') {
                if (!this.packageChatBridge) throw new Error(this.tr('chatUnavailable'));
                return this.packageChatBridge.invoke(name, args);
            }
            if (name === 'update_current_draft') {
                if (this.generating || this.stickerBatchBusy) throw new Error(this.tr('waitGeneration'));
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
                if (this.isAdjustMode) { if (!this.canExportAdjustment) throw new Error(this.tr('adjustmentMissingImage')); await this.exportAdjustment(); }
                else { if (!this.canGenerate) throw new Error(this.tr('inputMissing')); await this.generate(); }
                return { started: true, miniAppId: this.miniAppId };
            }
            throw new Error(this.tr('unknownTool'));
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
        runTaskMenu(event,run) { window.AI2AppsStudioTaskMenu.open(event,{disabled:!['draft','succeeded','failed','cancelled','expired'].includes(run.status),onDelete:()=>this.deleteHistoryRun(run)}); },
        async deleteHistoryRun(run) {
            try {
                await responsePayload(await fetch(`${STUDIO_API}/runs/${encodeURIComponent(run.id)}`,{method:'DELETE',credentials:'same-origin',headers:this.historyHeaders()}));
                const selected=this.selectedRunId===run.id;
                await this.refreshRuns();
                if(selected)this.selectRun(this.runs[0]);
            }catch(error){this.fail(error);}
        },
        selectRun(run) { this.selectedRunId = run?.id || ''; this.selectedArtifactId = run?.artifacts?.[0]?.id || ''; this.icons(); },
        selectArtifact(artifact) { this.selectedArtifactId = artifact?.id || ''; this.icons(); },
        draftPayload() { return { ...this.tryOnDraft(), extractTarget: this.extractTarget, extractCustom: this.extractCustom, promptOverride: this.promptIsEdited ? this.promptOverride : null, ...this.portraitDraft(), productScene: this.productScene, productLight: this.productLight, productComposition: this.productComposition, productSceneDescription: this.productSceneDescription, productUseStyle: this.productUseStyle, stickerEmotion: this.stickerEmotion, zImageBaseSteps: this.zImageBaseSteps, zImageBaseGuidance: this.zImageBaseGuidance, zImageBaseNegativePrompt: this.zImageBaseNegativePrompt, zImageSteps: this.zImageSteps, zImageRedraw: this.zImageRedraw, prompt: this.prompt, groupBackgroundDescription: this.groupBackgroundDescription, groupAtmosphere: this.groupAtmosphere, groupPose: this.groupPose, modelId: this.modelId, size: this.size, customWidth: this.customWidth, customHeight: this.customHeight, quality: this.quality, format: this.format, style: this.style, adjustmentState: window.ImagineAdjustEngine?.clone?.(this.adjustState), adjustmentLocked: this.adjustmentLocked, adjustmentPresets: this.adjustmentPresets, selectedAdjustmentPresetId: this.selectedAdjustmentPresetId, assetReferences: this.referenceAssets.slice(0, this.currentMiniApp.maxImages) }; },
        applyDraft(draft, restoreStyle = false) { if (!draft || typeof draft !== 'object') return; this.promptOverride = draft.promptOverride && typeof draft.promptOverride.key === 'string' && typeof draft.promptOverride.text === 'string' ? { key: draft.promptOverride.key, text: draft.promptOverride.text.slice(0, 32000) } : null; this.restoreTryOnDraft(draft); this.restoreExtractDraft(draft); this.restoreProductDraft(draft); this.restorePortraitDraft(draft); this.stickerEmotion = this.stickerEmotions.some(item => item.id === draft.stickerEmotion) ? draft.stickerEmotion : 'happy'; this.zImageBaseSteps = Number(draft.zImageBaseSteps) || 30; this.zImageBaseGuidance = Number(draft.zImageBaseGuidance) || 4; this.zImageBaseNegativePrompt = String(draft.zImageBaseNegativePrompt || '').slice(0, 8192); this.zImageSteps = Number(draft.zImageSteps) || 8; this.zImageRedraw = Number(draft.zImageRedraw) || 75; this.prompt = String(draft.prompt || ''); this.groupBackgroundDescription = String(draft.groupBackgroundDescription || ''); this.groupAtmosphere = String(draft.groupAtmosphere || ''); this.groupPose = String(draft.groupPose || ''); const savedModelId = String(draft.modelId || this.modelId); const managedModelId = managedCloudModelId(savedModelId); this.modelId = this.models.some(model => model.source === 'cloud' && model.id === managedModelId) ? managedModelId : savedModelId; this.size = String(draft.size || this.size); this.customWidth = Number(draft.customWidth || this.customWidth); this.customHeight = Number(draft.customHeight || this.customHeight); this.quality = String(draft.quality || 'auto'); this.format = String(draft.format || 'png'); if (restoreStyle || !this.stylePreferenceLoaded) { const savedStyle = String(draft.style || ''); this.style = LEGACY_STYLE_IDS[savedStyle] || savedStyle; this.persistStylePreference(); } if (draft.adjustmentState && window.ImagineAdjustEngine) { this.adjustState = window.ImagineAdjustEngine.clone(draft.adjustmentState); this.adjustHistory = [window.ImagineAdjustEngine.clone(this.adjustState)]; this.adjustHistoryIndex = 0; } if (Array.isArray(draft.adjustmentPresets)) this.adjustmentPresets = draft.adjustmentPresets.filter(item => item?.id && item?.name && item?.state); if (typeof draft.adjustmentLocked === 'boolean') this.adjustmentLocked = draft.adjustmentLocked; if (typeof draft.selectedAdjustmentPresetId === 'string') this.selectedAdjustmentPresetId = this.adjustmentPresets.some(item => item.id === draft.selectedAdjustmentPresetId) ? draft.selectedAdjustmentPresetId : ''; this.referenceAssets = Array.isArray(draft.assetReferences) ? draft.assetReferences : []; this.reconcileSelectedModel(); },
        scheduleDraftSave() { if (this.draftTimer) clearTimeout(this.draftTimer); this.draftTimer = setTimeout(() => this.saveDraft().catch(error => this.fail(error)), 500); },
        async saveDraft() { if (!this.appInstanceId() || this.currentMiniApp.status !== 'ready') return; await responsePayload(await fetch(`${STUDIO_API}/drafts/${encodeURIComponent(this.miniAppId)}`, { method: 'PUT', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ draft: this.draftPayload() }) })); },
        async loadDraft(miniAppId) {
            if (!this.appInstanceId()) return {};
            this.restoringPrompt = true;
            try {
                const payload = await responsePayload(await fetch(`${STUDIO_API}/drafts/${encodeURIComponent(miniAppId)}`, { credentials: 'same-origin', headers: this.historyHeaders() }));
                const draft = payload.draft || {}; this.applyDraft(draft);
                await this.restoreAssetReferences(); return draft;
            } finally { this.restoringPrompt = false; this.syncSubmissionPrompt(); }
        },
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
        async createRun(input, retryOf = null) { return responsePayload(await fetch(`${STUDIO_API}/runs`, { method: 'POST', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ miniAppId: this.miniAppId, title: this.isStickerMode ? this.currentMiniApp.name + ' · ' + this.stickerLabel(this.stickerEmotions.find(item => item.id === this.stickerEmotion) || this.stickerEmotions[0]) : this.usingLocalModel && !this.isAdjustMode ? this.tr(this.currentMiniApp.mode === 'generate' ? 'localGenerateRun' : 'localEditRun') : this.currentMiniApp.runLabel, input, retryOf }) })); },
        async updateRun(runId, status, progress, detail = '', error = null) { return responsePayload(await fetch(`${STUDIO_API}/runs/${encodeURIComponent(runId)}`, { method: 'PATCH', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ status, progress, detail, error }) })); },
        async executeCloudRun(runId, request) { return responsePayload(await fetch(`${STUDIO_API}/runs/${encodeURIComponent(runId)}/execute`, { method: 'POST', credentials: 'same-origin', headers: { ...this.historyHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify(request) })); },
        async cancelRun(run) { if (!this.isActiveRun(run)) return; if (run.id === this.selectedRunId) this.currentRunController?.abort(); try { await this.updateRun(run.id, 'cancelled', run.progress, this.tr('cancelled')); await this.refreshRuns(); } catch (error) { this.fail(error); } },
        async retryRun(run) { if (this.generating || this.stickerBatchBusy) return; this.miniAppId = run.miniAppId; this.applyDraft(run.input, true); this.mobileSurface = 'create'; if (this.isAdjustMode) await this.exportAdjustment(run.id); else await this.generate(run.id); },
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
            if (!this.hasLocalModels) throw new Error(this.tr('localModelMissing'));
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
            if (this.isTryOnMode) return this.tr(index===0?'portraitPerson':'tryOnItem');
            if (this.isPortraitMode) return this.tr(index === 0 ? 'portraitPerson' : 'portraitOutfit');
            if (!this.isGroupPhotoMode) return index === 0 ? this.tr('primaryImage') : `${this.tr('referenceImage')} ${index + 1}`;
            if (index === this.currentMiniApp.backgroundSlot) return this.tr('groupPhotoBackgroundImage');
            return this.tr('groupPhotoPerson', { number: index + 1 });
        },
        referenceSlotRequirement(index) {
            if (this.isTryOnMode) return this.tr('required');
            if (this.isPortraitMode) return this.tr('required');
            if (!this.isGroupPhotoMode) return index === 0 && this.currentMiniApp.requiresImage ? this.tr('required') : this.tr('optional');
            return index < 2 ? this.tr('required') : this.tr('optional');
        },
        showLeftView(view) { this.leftView = view === 'assets' ? 'assets' : (view === 'chat' && this.miniAppChatEnabled ? 'chat' : 'mini-apps'); if (this.leftView === 'assets' && !this.galleryMiniUrl) this.mountGalleryMini(); if (this.leftView === 'chat') this.mountMiniAppChat(); this.persistPreferences(); this.icons(); },
        async selectMiniApp(id) { if (this.generating || this.stickerBatchBusy) return; const selected = this.miniApps.find(item => item.id === id); if (!selected || selected.status !== 'ready') return; if (!this.packageMiniAppId) await this.saveDraft().catch(() => {}); disposeRenderableImage(this.adjustBitmap); this.adjustBitmap = null; this.miniAppId = id; if (this.leftView !== 'chat') this.leftView = 'mini-apps'; this.recentMiniApps = [id, ...this.recentMiniApps.filter(value => value !== id)].slice(0, 8); if (selected.source === 'package') { await this.mountPackageMiniApp(selected); if (!this.miniAppChatEnabled && this.leftView === 'chat') this.leftView = 'mini-apps'; this.persistPreferences(); this.mobileSurface = 'create'; return; } this.packageChatBridge?.dispose(); this.packageChatBridge = null; this.packageMiniAppId = ''; this.packageMiniAppUrl = ''; this.packageMiniAppError = ''; this.referenceFiles = []; this.referencePreviews.forEach(url => { if (url) URL.revokeObjectURL(url); }); this.referencePreviews = []; this.referenceDimensions = []; this.referenceAssets = []; const draft = await this.loadDraft(id); this.trimReferences(); this.reconcileSelectedModel(); if (this.prefersOpenAIModel && !draft?.modelId) { this.preferOpenAIEditingModel(); this.applySelectedModelCapability(); } if (['edit', 'style-transfer', 'group-photo'].includes(this.currentMiniApp.mode) && this.referenceDimensions[0]) this.matchEditAspect(this.referenceDimensions[0]); this.chatController?.changed(); this.persistPreferences(); this.mobileSurface = 'create'; this.icons(); },
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
                if (ready) this.success(this.tr('dependenciesReady'));
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
                if (!this.packageMiniAppUrl) throw new Error(this.tr('miniAppUrlMissing'));
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
            const limit = this.referenceSlotCount;
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
            if ((this.isStickerMode || this.isProductPhotoMode || this.isPortraitMode || this.isExtractMode || this.isTryOnMode) && (this.generating || this.stickerBatchBusy)) return;
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
            if ((this.isStickerMode || this.isProductPhotoMode || this.isPortraitMode || this.isExtractMode || this.isTryOnMode) && (this.generating || this.stickerBatchBusy)) return;
            if (this.referencePreviews[index]) URL.revokeObjectURL(this.referencePreviews[index]);
            const files = [...this.referenceFiles], previews = [...this.referencePreviews];
            const dimensions = [...this.referenceDimensions];
            const assets = [...this.referenceAssets]; assets[index] = null;
            files[index] = null; previews[index] = ''; dimensions[index] = null; this.referenceFiles = files; this.referencePreviews = previews; this.referenceDimensions = dimensions; this.referenceAssets = assets; this.scheduleDraftSave(); this.icons();
            if (index === 0 && this.isAdjustMode) { disposeRenderableImage(this.adjustBitmap); this.adjustBitmap = null; this.resetAdjustments(false); }
        },
        promptOverride: null, restoringPrompt: false,
        get promptCompositionKey() { return JSON.stringify([this.miniAppId, this.composedPrompt(), this.modelId, this.requestedSize, this.quality, this.format]); },
        get promptIsEdited() { return this.promptOverride?.key === this.promptCompositionKey; },
        get submissionPrompt() { return this.promptIsEdited ? this.promptOverride.text : this.composedPrompt(); },
        get submissionPromptValid() { return Boolean(this.submissionPrompt.trim()) && this.submissionPrompt.length <= 32000; },
        editSubmissionPrompt(text) { this.promptOverride = { key: this.promptCompositionKey, text: String(text) }; this.scheduleDraftSave(); },
        resetSubmissionPrompt() { this.promptOverride = null; this.scheduleDraftSave(); },
        syncSubmissionPrompt() { if (!this.restoringPrompt && this.promptOverride && !this.promptIsEdited) this.resetSubmissionPrompt(); },
        composedPrompt() {
            if (this.isTryOnMode) return this.tryOnPrompt();
            if (this.isExtractMode) return this.extractPrompt();
            if (this.isPortraitMode) return this.portraitPrompt();
            if (this.isProductPhotoMode) return this.productPhotoPrompt();
            if (this.isStickerMode) return this.stickerPrompt();
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

        async generate(retryOf = null, options = {}) {
            if (this.stickerBatchBusy && !options.stickerBatch) return;
            if (!this.canGenerate || this.generating) return;
            const references = this.referenceFiles.slice(0, this.referenceSlotCount).filter(Boolean);
            const editing = this.currentMiniApp.mode !== 'generate';
            const selectedModel = this.selectedModel;
            if (!selectedModel) return;
            if (editing && selectedModel.referenceLimits && (references.length < selectedModel.referenceLimits.minimum || references.length > selectedModel.referenceLimits.maximum)) {
                this.fail(new Error(`This model requires ${selectedModel.referenceLimits.minimum}–${selectedModel.referenceLimits.maximum} reference images.`));
                return;
            }
            if (editing && selectedModel.source === 'cloud' && !(options.stickerBatch && this.stickerBatchBusy) && !window.confirm(this.tr('uploadConfirm', { count: references.length }))) return;
            this.generating = true; this.dismissNotice();
            const id = globalThis.crypto?.randomUUID?.() || `image-${Date.now()}`;
            const requestedSize = this.requestedSize;
            const submittedPrompt = this.submissionPrompt;
            const input = { ...this.draftPayload(), submittedPrompt, prompt: this.prompt.trim(), size: requestedSize, modelLabel: selectedModel.label, assetReferences: this.referenceAssets.slice(0, this.currentMiniApp.maxImages) };
            let run = null;
            let serverManaged = false;
            try {
                await this.saveDraft();
                run = await this.createRun(input, retryOf);
                this.runs = [run, ...this.runs]; this.selectRun(run);
                const imageDataUrls = editing ? await Promise.all(references.map(readDataUrl)) : [];
                if (selectedModel.source === 'cloud') {
                    await this.executeCloudRun(run.id, { model: selectedModel.id, prompt: submittedPrompt, size: requestedSize, quality: this.quality, outputFormat: this.format, ...(editing ? { imageDataUrls } : {}) });
                    serverManaged = true;
                    const completedRun = await this.waitForRun(run.id);
                    try { window.ai2appsShell?.accountChanged?.(); } catch (_) {}
                    return completedRun;
                }
                run = await this.updateRun(run.id, 'running', 10, this.tr('running'));
                this.runs = this.runs.map(item => item.id === run.id ? run : item);
                this.currentRunController = new AbortController();
                const result = await responsePayload(await fetch(`${IMAGE_API}/${editing ? 'edits' : 'generations'}`, {
                    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'Idempotency-Key': `imagine-${id}` },
                    body: JSON.stringify({ model: selectedModel.id, prompt: submittedPrompt, size: requestedSize, quality: this.quality, outputFormat: this.format, n: 1, ...this.zImageParameters(), ...this.localEditParameters(selectedModel, editing), ...(editing ? { imageDataUrls } : {}) }),
                    signal: this.currentRunController.signal,
                }));
                const image = result?.image;
                if (!String(image?.dataUrl || '').startsWith('data:image/')) throw new Error(this.tr('noCloudImage'));
                const saved = await this.persistResult({ runId: run.id, miniAppId: this.miniAppId, pipelineId: this.currentMiniApp.legacyId, title: this.currentMiniApp.name, prompt: this.prompt.trim(), size: image.size || requestedSize, modelId: selectedModel.id, modelLabel: selectedModel.label.replace(/^AI2Apps (Cloud|Local) · /, ''), imageUrl: image.dataUrl, filename: this.resultFilename(id) });
                await this.updateRun(run.id, 'succeeded', 100, this.tr('completed'));
                await this.refreshRuns(); this.selectRun(this.runs.find(item => item.id === run.id));
                try { window.ai2appsShell?.accountChanged?.(); } catch (_) {}
                return this.runs.find(item => item.id === run.id);
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
                let uploadStage = this.tr('readingPng');
                try {
                const bytes = new Uint8Array(await result.imageFile.arrayBuffer());
                const chunkSize = 192 * 1024; const total = Math.ceil(bytes.length / chunkSize);
                const uploadId = globalThis.crypto?.randomUUID?.() || `upload-${Date.now()}`; let saved = null;
                for (let index = 0; index < total; index += 1) {
                    uploadStage = this.tr('uploadChunk', { number: index + 1, total });
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
        dragOutputImage(event, artifact) {
            if (!artifact?.id || !event.dataTransfer) { event.preventDefault(); return; }
            event.dataTransfer.effectAllowed = 'copy';
            event.dataTransfer.setData('application/x-ai2apps-image-result', JSON.stringify({artifactId: artifact.id, appInstanceId: this.appInstanceId()}));
            // Keep the native URL format for Gallery and external drop targets.
            event.dataTransfer.setData('text/uri-list', new URL(artifact.previewUrl, window.location.origin).href);
            event.dataTransfer.setData('text/plain', new URL(artifact.previewUrl, window.location.origin).href);
        },
        async droppedOutputFile(transfer) {
            const raw = transfer?.getData('application/x-ai2apps-image-result');
            if (!raw) return null;
            const ref = JSON.parse(raw);
            if (!this.appInstanceId() || ref.appInstanceId !== this.appInstanceId()) throw new Error(this.tr('currentGalleryOnly'));
            const artifact = this.runs.flatMap(run => run.artifacts || []).find(item => item.id === ref.artifactId);
            if (!artifact) throw new Error(this.tr('invalidHistoryUrl'));
            const url = new URL(artifact.previewUrl, window.location.origin);
            if (url.origin !== window.location.origin || !/^\/v1\/platform\/imagine-studio\/results\/isr_[0-9a-f]{32}\/content$/.test(url.pathname) || url.searchParams.get('appInstanceId') !== this.appInstanceId()) throw new Error(this.tr('invalidHistoryUrl'));
            const response = await fetch(url.href, {credentials: 'same-origin'});
            if (!response.ok) throw new Error(this.tr('readGalleryFailed', {status: response.status}));
            const blob = await response.blob();
            if (!['image/png','image/jpeg','image/webp'].includes(blob.type)) throw new Error(this.tr('invalidSlot'));
            return new File([blob], artifact.name || 'output.png', {type: blob.type});
        },
        handleWorkspaceDrag(event) {
            event.preventDefault(); this.galleryDragActive = true;
        },
        handleDragLeave(event) { if (!event.currentTarget.contains(event.relatedTarget)) { this.galleryDragActive = false; this.gallerySlotTarget = null; } },
        enterGallerySlot(index) { this.galleryDragActive = false; this.gallerySlotTarget = index; },
        leaveGallerySlot(event, index) { if (this.gallerySlotTarget === index && !event.currentTarget.contains(event.relatedTarget)) this.gallerySlotTarget = null; },
        async handleGalleryDrop(event, imageSlot = null) {
            this.galleryDragActive = false; this.gallerySlotTarget = null;
            if (this.generating || this.stickerBatchBusy || this.adjustmentExporting) return;
            try {
                let file = await this.droppedOutputFile(event.dataTransfer) || event.dataTransfer?.files?.[0] || null;
                let assetReference = null;
                if (!file) {
                    const assetId = event.dataTransfer?.getData('application/x-ai2apps-gallery-asset') || '';
                    if (!assetId || !this.appInstanceId()) return;
                    const target = imageSlot !== null ? Number(imageSlot) : (Array.from({ length: this.currentMiniApp.needsImages ? this.referenceSlotCount : 1 }, (_, index) => index).find(index => !this.referenceFiles[index]) ?? 0);
                    if (!this.currentMiniApp.needsImages) this.miniAppId = 'ai2apps.imagine.image-edit';
                    await this.materializeAssetReference({ assetId }, Math.min(target, this.referenceSlotCount - 1)); this.persistPreferences(); return;
                }
                if (!String(file.type || '').startsWith('image/')) throw new Error(this.tr('appImageOnly'));
                if (!this.currentMiniApp.needsImages) { this.miniAppId = 'ai2apps.imagine.image-edit'; this.recentMiniApps = [this.miniAppId, ...this.recentMiniApps.filter(value => value !== this.miniAppId)].slice(0, 8); }
                const limit = this.referenceSlotCount;
                const empty = Array.from({ length: limit }, (_, index) => index).find(index => !this.referenceFiles[index]);
                const target = imageSlot !== null ? Number(imageSlot) : (empty ?? 0); await this.setReference(Math.min(target, limit - 1), file, assetReference); this.persistPreferences();
            } catch (error) { this.fail(error); }
        },
    }; };
})();
