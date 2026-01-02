// kinds/image.mjs
// KindDef: image (v0.7.0)
//
// image covers: image generation, editing, inpainting/outpainting, upscaling, background removal,
// style transfer, and related 2D visual tasks.
//
// Conventions:
// - caps: key -> { kind:"cap"|"arg", desc:{EN,CN}, type?, values?, allowWildcard? }
// - NOTE: filter 只能约束 arg key；arg 必须声明 type（用于 filter 校验）
//
// Type set (recommended):
// - enum | enum_or_list | number | number_or_range | domain_list | string | string_or_list

const imageKind = {
	kind: 'image',
	
	caps: {
		// ----------------------------
		// CAP: capability switches
		// ----------------------------
		'gen.text2img': {
			kind: 'cap',
			desc: { EN: 'Text-to-image generation', CN: '支持文本生成图片（text-to-image）' },
		},
		'gen.img2img': {
			kind: 'cap',
			desc: { EN: 'Image-to-image / reference-based generation (incl. style transfer)', CN: '支持参考图生成/风格迁移（image-to-image）' },
		},
		'gen.drawText': {
			kind: 'cap',
			desc: { EN: 'Draw/overlay text on an image (captions, watermark, etc.)', CN: '支持在图片上绘制文字/字幕/水印等' },
		},
		'edit.inpaint': {
			kind: 'cap',
			desc: { EN: 'Inpainting (local repaint/repair)', CN: '支持局部重绘/修补（inpainting）' },
		},
		'edit.outpaint': {
			kind: 'cap',
			desc: { EN: 'Outpainting (extend canvas)', CN: '支持扩图/外延（outpainting）' },
		},
		'edit.removeObject': {
			kind: 'cap',
			desc: { EN: 'Remove object / cleanup', CN: '支持移除对象（remove object / cleanup）' },
		},
		'edit.replaceObject': {
			kind: 'cap',
			desc: { EN: 'Replace object', CN: '支持替换对象（replace object）' },
		},
		'edit.backgroundRemove': {
			kind: 'cap',
			desc: { EN: 'Background removal (alpha matte)', CN: '支持抠图/去背景（alpha matte / background removal）' },
		},
		'edit.backgroundReplace': {
			kind: 'cap',
			desc: { EN: 'Background replacement / compositing', CN: '支持换背景（背景合成/替换）' },
		},
		'edit.face': {
			kind: 'cap',
			desc: { EN: 'Face-related edits (restore/swap/expression, agent-defined)', CN: '支持人脸相关编辑（修复/换脸/表情等；具体能力以 agent 为准）' },
		},
		'edit.styleTransfer': {
			kind: 'cap',
			desc: { EN: 'Style transfer', CN: '支持风格迁移（style transfer）' },
		},
		
		'enhance.upscale': {
			kind: 'cap',
			desc: { EN: 'Upscale / super-resolution', CN: '支持超分辨率/放大增强（upscale/super-resolution）' },
		},
		'enhance.denoise': {
			kind: 'cap',
			desc: { EN: 'Denoise / deblock', CN: '支持降噪/去压缩伪影（denoise/deblock）' },
		},
		
		'control.pose': {
			kind: 'cap',
			desc: { EN: 'Pose/skeleton control', CN: '支持姿态/骨架控制（pose control）' },
		},
		'control.depth': {
			kind: 'cap',
			desc: { EN: 'Depth-map control', CN: '支持深度图控制（depth control）' },
		},
		'control.edge': {
			kind: 'cap',
			desc: { EN: 'Edge/line-art control (canny/lineart)', CN: '支持边缘/线稿控制（canny/lineart control）' },
		},
		'control.seg': {
			kind: 'cap',
			desc: { EN: 'Segmentation control', CN: '支持语义分割控制（segmentation control）' },
		},
		
		'seed': {
			kind: 'cap',
			desc: { EN: 'Seed control (reproducibility)', CN: '支持 seed 控制（复现同一随机结果）' },
		},
		'batch': {
			kind: 'cap',
			desc: { EN: 'Batch generation (multiple outputs per request)', CN: '支持批量生成（一次请求生成多张）' },
		},
		
		// ----------------------------
		// ARG: supported input/output args
		// ----------------------------
		// prompt
		'prompt': {
			kind: 'arg',
			type: 'string',
			desc: { EN: 'Main prompt (text description)', CN: '主提示词（文本描述）' },
		},
		'prompt.natural': {
			kind: 'cap',
			desc: {
				EN: 'Accepts natural-language prompts (free-form sentences/paragraphs), not only keyword tags or strict syntax',
				CN: '支持自然语言 Prompt（可用句子/段落自由描述），而不仅限于关键词标签或严格语法'
			},
		},
		'negativePrompt': {
			kind: 'arg',
			type: 'string_or_list',
			desc: { EN: 'Negative prompt (or list)', CN: '负面提示词（或列表）' },
		},
		// input images
		'image': {
			kind: 'arg',
			type: 'string_or_list',
			desc: { EN: 'Reference input image(s) (URL/base64/path, agent-defined)', CN: '输入参考图（URL/base64/path 等，由 agent 自己解释；可为列表）' },
		},
		'maskImage': {
			kind: 'arg',
			type: 'string_or_list',
			desc: { EN: 'Mask image(s) (URL/base64/path, agent-defined)', CN: '遮罩（mask）（URL/base64/path 等；可为列表）' },
		},
		'controlImage': {
			kind: 'arg',
			type: 'string_or_list',
			desc: { EN: 'Control image(s) (pose/depth/edge/seg, agent-defined)', CN: '控制图（pose/depth/edge/seg 等；由 agent 解释）' },
		},
		
		// ----------------------------
		// transform args
		// ----------------------------
		'transform': {
			kind: 'cap',
			desc: { EN: 'Geometric transforms: scale/resize, crop, rotate, mirror, etc.', CN: '支持放缩、裁剪、旋转、镜像等几何/尺寸相关操作' },
		},
		'transform.operation': {
			kind: 'arg',
			type: 'enum',
			values: ['scale', 'fit', 'crop', 'mirror', 'rotate', 'dedrift'],
			desc: { EN: 'Transform operation', CN: '变换操作类型' },
		},
		
		// scale / resize
		'transform.scale': {
			kind: 'arg',
			type: 'number',
			desc: { EN: 'Scale factor (keeps aspect ratio)', CN: '放缩比例（保持长宽比）' },
		},
		'transform.width': {
			kind: 'arg',
			type: 'number',
			desc: { EN: 'Target width in pixels (if height omitted, keep aspect ratio)', CN: '目标宽度（像素）；若未指定 height 则保持长宽比' },
		},
		'transform.height': {
			kind: 'arg',
			type: 'number',
			desc: { EN: 'Target height in pixels (if width omitted, keep aspect ratio)', CN: '目标高度（像素）；若未指定 width 则保持长宽比' },
		},
		
		// fit modes
		'transform.fit': {
			kind: 'arg',
			type: 'enum',
			values: ['max', 'aspect', 'cover', 'contain'],
			desc: { EN: 'Fit mode', CN: 'fit 操作模式' },
		},
		'transform.fitMaxSize': {
			kind: 'arg',
			type: 'number',
			desc: { EN: 'Max size for fit=max (longer edge capped, keeps aspect ratio)', CN: 'fit=max 时的最大尺寸（保持长宽比；输出宽/高不超过该值）' },
		},
		'transform.fitAspect': {
			kind: 'arg',
			type: 'number',
			desc: { EN: 'Aspect ratio for fit=aspect (crop to largest area matching ratio)', CN: 'fit=aspect 时的目标比例（从图中截取最大面积匹配该比例）' },
		},
		'transform.align': {
			kind: 'arg',
			type: 'string',
			desc: { EN: 'Alignment for cover/contain cropping: "start|center|end" or "x,y"', CN: 'cover/contain 时的对齐方式："start|center|end"，可单值或用逗号分隔的 "x,y"' },
		},
		
		// rotate / mirror / crop
		'transform.rotate': {
			kind: 'arg',
			type: 'enum',
			values: ['0', '90', '180', '270'],
			desc: { EN: 'Rotate angle (degrees, limited set)', CN: '旋转角度（仅允许 0/90/180/270）' },
		},
		'transform.mirror': {
			kind: 'arg',
			type: 'enum',
			values: ['x', 'y', 'xy'],
			desc: { EN: 'Mirror axis', CN: '镜像轴：x / y / xy' },
		},
		'transform.crop': {
			kind: 'cap',
			desc: { EN: 'Crop part of image', CN: '剪裁图片的一部分为新图片' },
		},
		'transform.cropX': {
			kind: 'arg',
			type: 'string',
			desc: { EN: 'Crop start X (number as string, or "center")', CN: '剪裁起始 X（数值或 "center"；未指定默认 center）' },
		},
		'transform.cropY': {
			kind: 'arg',
			type: 'string',
			desc: { EN: 'Crop start Y (number as string, or "center")', CN: '剪裁起始 Y（数值或 "center"；未指定默认 center）' },
		},
		'transform.dedrift': {
			kind: 'cap',
			desc: { EN: 'Remove image pixels drift from another image.)', CN: '移除图片像素相对于另一张图片的像素位移' },
		},
		
		// ----------------------------
		// adjust args
		// ----------------------------
		'adjust': {
			kind: 'cap',
			desc: { EN: 'Image adjustments: brightness/contrast/saturation, denoise, blur, etc.', CN: '支持亮度/对比度/饱和度等调色与滤镜（降噪/模糊/增强等）' },
		},
		'adjust.operation': {
			kind: 'arg',
			type: 'enum',
			values: ['auto', 'light', 'contrast', 'saturation', 'hue', 'colorBalance', 'temperature','denoise', 'enhance', 'blur'],
			desc: { EN: 'Adjustment operation', CN: '调整/滤镜操作类型' },
		},
		'adjust.value': {
			kind: 'arg',
			type: 'number',
			desc: { EN: 'Adjustment value (meaning depends on operation)', CN: '调整数值（含义由 operation 决定）' },
		},
		'adjust.color': {
			kind: 'arg',
			type: 'number',
			desc: { EN: 'Color parameter (meaning depends on operation)', CN: '颜色参数（含义由 operation 决定）' },
		},
		'adjust.light': {
			kind: 'cap',
			desc: { EN: 'Adjust brightness of image.)', CN: '调整图片亮度' },
		},
		'adjust.contrast': {
			kind: 'cap',
			desc: { EN: 'Adjust contrast of image.)', CN: '调整图片对比度' },
		},
		'adjust.saturation': {
			kind: 'cap',
			desc: { EN: 'Adjust saturation of image.)', CN: '调整图片饱和度' },
		},
		'adjust.hue': {
			kind: 'cap',
			desc: { EN: 'Adjust hue of image.)', CN: '调整图片色轮' },
		},
		'adjust.colorBalance': {
			kind: 'cap',
			desc: { EN: 'Adjust colorBalance of image.)', CN: '调整图片颜色平衡' },
		},
		'adjust.temperature': {
			kind: 'cap',
			desc: { EN: 'Adjust temperature of image.)', CN: '调整图片色温度' },
		},
		'adjust.denoise': {
			kind: 'cap',
			desc: { EN: 'Reduce noise rate of image.)', CN: '降低图片噪声' },
		},
		'adjust.enhance': {
			kind: 'cap',
			desc: { EN: 'Enhance image content.)', CN: '增强图片内容' },
		},
		'adjust.sharpen': {
			kind: 'cap',
			desc: { EN: 'Sharpen image content.)', CN: '锐化图片内容' },
		},
		'adjust.blur': {
			kind: 'cap',
			desc: { EN: 'Blur image content.)', CN: '模糊图片内容' },
		},
		
		// ----------------------------
		// compose args
		// ----------------------------
		'compose': {
			kind: 'cap',
			desc: { EN: 'Compositing / templated multi-layer collage', CN: '支持拼合/合成图片（模板填充、拼贴等）' },
		},
		'compose.operation': {
			kind: 'arg',
			type: 'enum',
			values: ['fillSlot', 'fillSlots'],
			desc: { EN: 'Compose action', CN: '拼合动作' },
		},
		'compose.template': {
			kind: 'arg',
			type: 'string',
			desc: { EN: 'Compose template (JSON string, agent-defined schema)', CN: '拼合模板（JSON 字符串；结构由 agent 定义）' },
		},
		'compose.base': {
			kind: 'arg',
			type: 'string',
			desc: { EN: 'Base image DataURL for the template', CN: '模板底图 DataURL' },
		},
		'compose.slot': {
			kind: 'arg',
			type: 'number',
			desc: { EN: 'Slot id to fill', CN: '要填充的槽位 id' },
		},
		'compose.image': {
			kind: 'arg',
			type: 'string',
			desc: { EN: 'Slot image DataURL', CN: '槽位图片 DataURL' },
		},
		'compose.text': {
			kind: 'arg',
			type: 'string',
			desc: { EN: 'Slot text', CN: '槽位文本' },
		},
		
		// ----------------------------
		// output & quality args
		// ----------------------------
		'output.format': {
			kind: 'arg',
			type: 'enum_or_list',
			values: ['png', 'jpg', 'jpeg', 'webp'],
			desc: { EN: 'Output format(s)', CN: '输出格式' },
		},
		'output.count': {
			kind: 'arg',
			type: 'number_or_range',
			desc: { EN: 'Number of outputs (or {min,max})', CN: '输出张数（或 {min,max}）' },
		},
		'output.resolution': {
			kind: 'arg',
			type: 'string',
			desc: { EN: 'Resolution preset (e.g., 1K/2K/4K, agent-defined mapping)', CN: '分辨率档位（如 1K/2K/4K；由 agent 映射）' },
		},
		'output.width': {
			kind: 'arg',
			type: 'number_or_range',
			desc: { EN: 'Output width (px) or {min,max}', CN: '输出宽度（像素；或 {min,max}）' },
		},
		'output.height': {
			kind: 'arg',
			type: 'number_or_range',
			desc: { EN: 'Output height (px) or {min,max}', CN: '输出高度（像素；或 {min,max}）' },
		},
		'output.aspectRatio': {
			kind: 'arg',
			type: 'enum',
			values: ['1:1', '4:3', '3:4', '16:9', '9:16', '2:3', '3:2','4:5','5:4','21:10'],
			desc: { EN: 'Aspect ratio preset (agent may derive width/height)', CN: '长宽比预设（可由 agent 推导 width/height）' },
		},
		'output.transparent': {
			kind: 'arg',
			type: 'enum',
			values: ['true', 'false'],
			desc: { EN: 'Transparent background output (string enum for forms/JSON)', CN: '是否输出透明背景（用 string enum 便于表单/JSON）' },
		},
		
		'style.preset': {
			kind: 'arg',
			type: 'string_or_list',
			desc: { EN: 'Style preset(s) / style name(s)', CN: '风格预设/模型风格名（例如 photoreal/anime/oil painting）' },
		},
		'quality': {
			kind: 'arg',
			type: 'enum',
			values: ['draft', 'normal', 'high'],
			desc: { EN: 'Quality level (agent maps to steps/resolution/etc.)', CN: '质量档位（影响步数/采样/分辨率等，由 agent 映射）' },
		},
		
		'sampling.steps': {
			kind: 'arg',
			type: 'number_or_range',
			desc: { EN: 'Sampling steps (or {min,max})', CN: '采样步数（或 {min,max}）' },
		},
		'sampling.cfgScale': {
			kind: 'arg',
			type: 'number_or_range',
			desc: { EN: 'CFG / guidance scale (or range)', CN: 'CFG scale / guidance scale（或范围）' },
		},
		'sampling.seed': {
			kind: 'arg',
			type: 'number_or_range',
			desc: { EN: 'Random seed (or range for exploration)', CN: '随机 seed（或范围；用于多样性/网格搜索）' },
		},
		
		// misc hints
		'safety.level': {
			kind: 'arg',
			type: 'enum',
			values: ['low', 'medium', 'high'],
			desc: { EN: 'Safety/conservativeness level (agent-defined)', CN: '安全/保守程度（越高越谨慎；由 agent 自己解释）' },
		},
	},
}

export default imageKind
export { imageKind }