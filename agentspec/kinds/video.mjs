// kinds/video.mjs
// KindDef: video (v0.6.1)
//
// video covers: text-to-video, image-to-video, video editing (trim/concat/overlay),
// generation of short clips, and simple post-processing pipelines.
//
// Conventions:
// - caps: key -> { kind:"cap"|"arg", desc, type?, values?, allowWildcard? }
// - ranks: key -> { desc, order:"asc"|"desc", valueFrom, type:"number", missing, defaultValue? }
// - defaultRanks: used when FindVO.rank is omitted

const videoKind = {
	kind: 'video',
	caps: {
		// ----------------------------
		// CAP: capability switches
		// ----------------------------
		'gen.text2video': {
			kind: 'cap',
			desc: '支持文本生成视频（text-to-video）',
		},
		'gen.img2video': {
			kind: 'cap',
			desc: '支持图片生成视频/动效（image-to-video）',
		},
		'edit.trim': {
			kind: 'cap',
			desc: '支持剪切/裁剪时段（trim）',
		},
		'edit.concat': {
			kind: 'cap',
			desc: '支持拼接/合并片段（concat/merge）',
		},
		'edit.overlay': {
			kind: 'cap',
			desc: '支持叠加元素（字幕/贴纸/Logo/水印等 overlay）',
		},
		'edit.subtitles': {
			kind: 'cap',
			desc: '支持字幕生成/嵌入（burn-in 或外挂字幕）',
		},
		'edit.style': {
			kind: 'cap',
			desc: '支持风格化/滤镜（stylize/color grade）',
		},
		'edit.motion': {
			kind: 'cap',
			desc: '支持基础镜头运动/动效（pan/zoom/ken burns 等）',
		},
		'audio.mix': {
			kind: 'cap',
			desc: '支持音频混合/配乐（bgm/voice mix）',
		},
		'seed': {
			kind: 'cap',
			desc: '支持 seed 控制（复现同一随机结果）',
		},
		'batch': {
			kind: 'cap',
			desc: '支持批量生成（一次请求生成多个视频）',
		},
		
		// ----------------------------
		// ARG: supported input/output args
		// ----------------------------
		'prompt': {
			kind: 'arg',
			type: 'string',
			desc: '主提示词（文本描述）',
		},
		'prompt.negative': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '负面提示词（或列表）',
		},
		
		'input.image': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '输入参考图（URL/base64/path 等；可为列表）',
		},
		'input.video': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '输入视频（用于编辑/续写；URL/path 等；可为列表）',
		},
		'input.audio': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '输入音频（配乐/旁白；URL/path 等；可为列表）',
		},
		
		'output.format': {
			kind: 'arg',
			type: 'enum_or_list',
			values: ['mp4', 'mov', 'webm', 'gif'],
			desc: '输出格式',
		},
		'output.durationSec': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '输出时长（秒；或 {min,max}）',
		},
		'output.fps': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '帧率（fps；或 {min,max}）',
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
		
		'quality': {
			kind: 'arg',
			type: 'enum',
			values: ['draft', 'normal', 'high'],
			desc: '质量档位（影响分辨率/步数/码率等，由 agent 映射）',
		},
		'sampling.steps': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '采样步数（生成类模型；或 {min,max}）',
		},
		'sampling.seed': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '随机 seed（或范围）',
		},
		
		// subtitles
		'subtitles.text': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '字幕内容（单段或多段；格式由 agent 解释）',
		},
		'subtitles.format': {
			kind: 'arg',
			type: 'enum',
			values: ['srt', 'vtt', 'burnin'],
			desc: '字幕格式（外挂 srt/vtt 或 burn-in）',
		},
		
		// safety / policy hints
		'safety.level': {
			kind: 'arg',
			type: 'enum',
			values: ['low', 'medium', 'high'],
			desc: '安全/保守程度（越高越谨慎；由 agent 自己解释）',
		},
	},
	
	ranks: {
		size: {
			desc: '模型/Agent 体积（越小越优先）',
			order: 'asc',
			valueFrom: 'metrics.size',
			type: 'number',
			missing: 'last',
		},
		successRate: {
			desc: '成功率（越高越优先）',
			order: 'desc',
			valueFrom: 'metrics.successRate',
			type: 'number',
			missing: 'last',
		},
		latency: {
			desc: '延迟 P95（越低越优先）',
			order: 'asc',
			valueFrom: 'metrics.latencyMsP95',
			type: 'number',
			missing: 'last',
		},
		cost: {
			desc: '成本（越低越优先）',
			order: 'asc',
			valueFrom: 'metrics.costPer1k',
			type: 'number',
			missing: 'last',
		},
	},
	
	defaultRanks: ['successRate', 'latency', 'size'],
}

export default videoKind
export { videoKind }
