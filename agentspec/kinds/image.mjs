// kinds/image.mjs
// KindDef: image (v0.6.1)
//
// image covers: image generation, editing, inpainting/outpainting, upscaling, background removal,
// style transfer, and related 2D visual tasks.
//
// Conventions:
// - caps: key -> { kind:"cap"|"arg", desc, type?, values?, allowWildcard? }
// - ranks: key -> { desc, order:"asc"|"desc", valueFrom, type:"number", missing, defaultValue? }
// - defaultRanks: used when FindVO.rank is omitted

const imageKind = {
	kind: 'image',
	
	caps: {
		// ----------------------------
		// CAP: capability switches
		// ----------------------------
		'gen.text2img': {
			kind: 'cap',
			desc: '支持文本生成图片（text-to-image）',
		},
		'gen.img2img': {
			kind: 'cap',
			desc: '支持参考图生成/风格迁移（image-to-image）',
		},
		'transform':{
			kind:'cap',
			desc:'支持放缩、裁剪、旋转、镜像等与尺寸相关的操作',
		},
		'adjust':{
			kind:'cap',
			desc:'支持调整亮度、对比度、饱和度，放缩、裁剪、旋转、镜像等与尺寸相关的操作',
		},
		'compose':{
			kind:'cap',
			desc:'拼合图片。',
		},
		'gen.drawText': {
			kind: 'cap',
			desc: '支持参考图生成/风格迁移（image-to-image）',
		},
		'edit.inpaint': {
			kind: 'cap',
			desc: '支持局部重绘/修补（inpainting）',
		},
		'edit.outpaint': {
			kind: 'cap',
			desc: '支持扩图/外延（outpainting）',
		},
		'edit.removeObject': {
			kind: 'cap',
			desc: '支持移除对象（remove object / cleanup）',
		},
		'edit.replaceObject': {
			kind: 'cap',
			desc: '支持替换对象（replace object）',
		},
		'edit.backgroundRemove': {
			kind: 'cap',
			desc: '支持抠图/去背景（alpha matte / background removal）',
		},
		'edit.backgroundReplace': {
			kind: 'cap',
			desc: '支持换背景（背景合成/替换）',
		},
		'edit.face': {
			kind: 'cap',
			desc: '支持人脸相关编辑（修复/换脸/表情等；具体能力以 agent 为准）',
		},
		'edit.styleTransfer': {
			kind: 'cap',
			desc: '支持风格迁移（style transfer）',
		},
		'enhance.upscale': {
			kind: 'cap',
			desc: '支持超分辨率/放大增强（upscale/super-resolution）',
		},
		'enhance.denoise': {
			kind: 'cap',
			desc: '支持降噪/去压缩伪影（denoise/deblock）',
		},
		'control.pose': {
			kind: 'cap',
			desc: '支持姿态/骨架控制（pose control）',
		},
		'control.depth': {
			kind: 'cap',
			desc: '支持深度图控制（depth control）',
		},
		'control.edge': {
			kind: 'cap',
			desc: '支持边缘/线稿控制（canny/lineart control）',
		},
		'control.seg': {
			kind: 'cap',
			desc: '支持语义分割控制（segmentation control）',
		},
		'seed': {
			kind: 'cap',
			desc: '支持 seed 控制（复现同一随机结果）',
		},
		'batch': {
			kind: 'cap',
			desc: '支持批量生成（一次请求生成多张）',
		},
		
		// ----------------------------
		// ARG: supported input/output args
		// ----------------------------
		//--------------------------------------------------------------------
		'prompt': {
			kind: 'arg',
			type: 'string',
			desc: {"EN":'Main prompt (text description)',"CN":'主提示词（文本描述）'},
		},
		'prompt.negative': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '负面提示词（或列表）',
		},
		
		//--------------------------------------------------------------------
		'input.image': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '输入参考图（URL/base64/path 等，由 agent 自己解释；可为列表）',
		},
		'input.mask': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '遮罩（mask）（URL/base64/path 等；可为列表）',
		},
		'input.controlImage': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '控制图（pose/depth/edge/seg 等；由 agent 解释）',
		},
		
		//--------------------------------------------------------------------
		'transform.operation':{
			kind: 'arg',
			type: 'string',
			values: ['scale', 'resize', 'slice', 'mirror', 'rotate', 'dedrift'],
			desc: '操作。',
		},
		'transform.scale':{
			kind: 'arg',
			type: 'number',
			desc: '设置图片的放缩比例，使用放缩比例时，保持横总比。',
		},
		'transform.maxSize':{
			kind: 'arg',
			type: 'number',
			desc: '设置图片的最大尺寸，保持横总比，输出图片的最大宽/高均不超过maxSize指定的尺寸。',
		},
		'transform.width':{
			kind: 'arg',
			type: 'number',
			desc: '设置放缩图片的宽度，如果没有指定 height，则保持横总比。',
		},
		'transform.height':{
			kind: 'arg',
			type: 'number',
			desc: '设置放缩图片的高度，如果没有指定 width，则保持横总比。',
		},
		'transform.coverAlign':{
			kind: 'arg',
			type: 'string',
			desc: '当使用cover方式改变图片尺寸的时候，截取内容的对齐方式。横纵向都有三个值可以选："start", "center", "end"。可以是一个值同时指定横纵向，也可以是用逗号隔开的两个值分别指定横纵向',
		},
		'transform.coverWidth':{
			kind: 'arg',
			type: 'number',
			desc: '设置cover剪裁模式输出的图片的最大遮挡宽度，如果没有指定 coverHeight，则保持横总比，输出的图片最大宽度为coverWidth。',
		},
		'transform.coverHeight':{
			kind: 'arg',
			type: 'number',
			desc: '设置cover剪裁模式输出的图片的最大遮挡高度，如果没有指定 coverWidth，则保持横总比，输出的图片最大高度为coverHeight。',
		},
		'transform.containWidth':{
			kind: 'arg',
			type: 'number',
			desc: '设置contain剪裁模式输出的图片的最大包含宽度，如果没有指定 containHeight，则保持横总比，输出的图片最大宽度为containWidth。',
		},
		'transform.containHeight':{
			kind: 'arg',
			type: 'number',
			desc: '设置contain剪裁模式输出的图片的最大包含高度，如果没有指定 containWidth，则保持横总比，输出的图片最大高度为containHeight。',
		},
		'transform.rotate':{
			kind: 'arg',
			type: 'string',
			desc: '图片的旋转角度，只能取："0"、"90"、:180"、"270"',
		},
		'transform.mirror':{
			kind: 'arg',
			type: 'string',
			desc: '图片镜像的轴，取值为："x"，"y"，"xy"',
		},
		'transform.sliceX':{
			kind: 'arg',
			type: 'number/string',
			desc: '剪裁图片区域的起始横坐标，数值或者字符串 "center"(代表剪裁居中) 如果没有指定默认为center。',
		},
		'transform.sliceY':{
			kind: 'arg',
			type: 'number/string',
			desc: '剪裁图片区域的起始纵坐标，数值或者字符串 "center"(代表剪裁居中) 如果没有指定默认为center。',
		},
		'transform.sliceWidth':{
			kind: 'arg',
			type: 'number',
			desc: '剪裁图片区域的宽度，如果没有指定sliceHeight，则保持横纵比。',
		},
		'transform.sliceHeight':{
			kind: 'arg',
			type: 'number',
			desc: '剪裁图片区域的高度，如果没有指定sliceWidth，则保持横纵比。',
		},
		
		//--------------------------------------------------------------------
		'adjust.operation':{
			kind: 'arg',
			type: 'string',
			values: ['auto', 'light', 'contrast', 'saturation', 'hue','colorBalance','grayscale','denoise','enhance', 'blur', 'clear'],
			desc: '操作。',
		},
		'adjust.value':{
			kind: 'arg',
			type: 'number',
			desc: '调整数值',
		},
		'adjust.color':{
			kind: 'arg',
			type: 'number',
			desc: '调整颜色',
		},
		
		//--------------------------------------------------------------------
		'compose.operation':{
			kind: 'arg',
			type: 'string',
			values: ['fillSlot', 'fillSlots'],
			desc: '拼合动作',
		},
		'compose.template':{
			kind: 'arg',
			type: 'json',
			desc: '拼合模版',
		},
		'compose.base':{
			kind: 'arg',
			type: 'string',
			desc: '拼合模版底图的DataURL',
		},
		'compose.slot':{
			kind: 'arg',
			type: 'int',
			desc: '要填充的槽id',
		},
		'compose.image':{
			kind: 'arg',
			type: 'string',
			desc: '图片DataURL',
		},
		'compose.text':{
			kind: 'arg',
			type: 'string',
			desc: '槽文本',
		},
		
		//--------------------------------------------------------------------
		'output.format': {
			kind: 'arg',
			type: 'enum_or_list',
			values: ['png', 'jpg', 'jpeg', 'webp'],
			desc: '输出格式',
		},
		'output.count': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '输出张数（或 {min,max}）',
		},
		'output.resolution': {
			kind: 'arg',
			type: 'string',
			desc: '输出像素分辨率，取值为: 1K, 2K, 4K',
		},
		'output.maxSize': {
			kind: 'arg',
			type: 'string',
			desc: '输出像素分辨率，取值为: 1K, 2K, 4K',
		},
		'output.width': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '输出宽度（像素）',
		},
		'output.height': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '输出高度（像素）',
		},
		'output.aspectRatio': {
			kind: 'arg',
			type: 'enum',
			values: ['1:1', '4:3', '3:4', '16:9', '9:16', '2:3', '3:2'],
			desc: '输出长宽比（粗粒度；若提供则可由 agent 决定 width/height）',
		},
		'output.transparent': {
			kind: 'arg',
			type: 'enum',
			values: ['true', 'false'],
			desc: '是否输出透明背景（string enum 便于 JSON/表单；你也可改成 boolean 类型扩展）',
		},
		
		'style.preset': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '风格预设/模型风格名（例如: photoreal/anime/oil painting）',
		},
		'quality': {
			kind: 'arg',
			type: 'enum',
			values: ['draft', 'normal', 'high'],
			desc: '质量档位（影响步数/采样/分辨率等，由 agent 映射）',
		},
		
		'sampling.steps': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '采样步数（或 {min,max}）',
		},
		'sampling.cfgScale': {
			kind: 'arg',
			type: 'number_or_range',
			desc: 'CFG scale / guidance scale（或范围）',
		},
		'sampling.seed': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '随机 seed（或范围；用于多样性/网格搜索）',
		},
		
		// misc hints
		'safety.level': {
			kind: 'arg',
			type: 'enum',
			values: ['low', 'medium', 'high'],
			desc: '安全/保守程度（越高越谨慎；由 agent 自己解释）',
		},
	}
}

export default imageKind
export { imageKind }
