// kinds/tts.mjs
// KindDef: tts (v0.6.1)
// Notes:
// - caps: key -> { kind:"cap"|"arg", desc, type?, values?, allowWildcard? }
// - ranks: key -> { desc, order:"asc"|"desc", valueFrom, type:"number", missing, defaultValue? }
// - defaultRanks: used when FindVO.rank is omitted

const ttsKind = {
	kind: 'tts',
	
	caps: {
		// ----------------------------
		// CAP: capability switches
		// ----------------------------
		'ssml': {
			kind: 'cap',
			desc: '支持 SSML（或等价标记语言）输入',
		},
		'prosody.pauseControl': {
			kind: 'cap',
			desc: '支持停顿/断句控制（SSML break 或等价能力）',
		},
		'prosody.pitch': {
			kind: 'cap',
			desc: '支持音高（pitch）控制',
		},
		'prosody.volume': {
			kind: 'cap',
			desc: '支持音量（volume）控制',
		},
		'voice.clone': {
			kind: 'cap',
			desc: '支持音色克隆/声音复刻',
		},
		'voice.multispeaker': {
			kind: 'cap',
			desc: '支持多说话人/多角色输出（同一请求可含多个 voice）',
		},
		'timestamps.word': {
			kind: 'cap',
			desc: '支持输出逐词/逐字时间戳（word/char timestamps）',
		},
		'timestamps.sentence': {
			kind: 'cap',
			desc: '支持输出句级时间戳（sentence timestamps）',
		},
		'streaming': {
			kind: 'cap',
			desc: '支持流式输出（边合成边输出音频）',
		},
		
		// ----------------------------
		// ARG: supported input/output args
		// ----------------------------
		'lang': {
			kind: 'arg',
			type: 'enum_or_list',
			values: ['zh', 'en', 'ja', 'ko', 'fr', 'de', 'es'],
			desc: '语言（或语言列表）',
		},
		
		'voice.id': {
			kind: 'arg',
			type: 'string',
			desc: '指定 voice ID/预设音色名（引擎内部映射）',
		},
		'voice.gender': {
			kind: 'arg',
			type: 'enum',
			values: ['female', 'male', 'neutral'],
			desc: '期望音色性别（若引擎支持）',
		},
		'voice.age': {
			kind: 'arg',
			type: 'enum',
			values: ['child', 'young', 'adult', 'senior'],
			desc: '期望音色年龄段（若引擎支持）',
		},
		
		'prosody.speed': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '语速（1.0 为正常语速；可用 number 或 {min,max}）',
		},
		'prosody.emotion': {
			kind: 'arg',
			type: 'enum',
			values: ['neutral', 'calm', 'happy', 'sad', 'angry', 'serious', 'excited'],
			desc: '情绪/语气',
		},
		'prosody.style': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '风格/场景预设（如 narration/customer_service）',
		},
		'prosody.pitchLevel': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '音高级别（单位由引擎解释；可用 number 或 {min,max}）',
		},
		'prosody.volumeLevel': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '音量级别（单位由引擎解释；可用 number 或 {min,max}）',
		},
		
		'output.format': {
			kind: 'arg',
			type: 'enum_or_list',
			values: ['wav', 'mp3', 'aac', 'ogg', 'flac'],
			desc: '输出音频格式',
		},
		'output.sampleRate': {
			kind: 'arg',
			type: 'number',
			desc: '输出采样率（如 24000/48000）',
		},
		'output.bitRateKbps': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '输出码率（kbps，适用于压缩格式）',
		},
		'output.channels': {
			kind: 'arg',
			type: 'enum',
			values: ['mono', 'stereo'],
			desc: '输出声道数',
		},
		
		// execution hints (still args)
		'stream.chunkMs': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '流式输出的 chunk 时长（毫秒）',
		},
	},
	
	ranks: {
		// NOTE: these are just definitions; actual values come from Agent.metrics.*
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
	
	// When FindVO.rank is omitted
	defaultRanks: ['successRate', 'latency', 'size'],
}

export default ttsKind
export { ttsKind }
