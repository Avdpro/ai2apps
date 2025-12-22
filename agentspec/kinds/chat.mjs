// kinds/chat.mjs
// KindDef: chat (v0.6.1)
//
// chat covers: general dialog, reasoning, planning, tool orchestration, structured output.
// This KindDef defines capability keys (cap) and supported args (arg).
//
// Conventions:
// - caps: key -> { kind:"cap"|"arg", desc, type?, values?, allowWildcard? }
// - ranks: key -> { desc, order:"asc"|"desc", valueFrom, type:"number", missing, defaultValue? }
// - defaultRanks: used when FindVO.rank is omitted

const chatKind = {
	kind: 'chat',
	
	caps: {
		// ----------------------------
		// CAP: capability switches
		// ----------------------------
		'streaming': {
			kind: 'cap',
			desc: '支持流式输出（逐 token / chunk 输出）',
		},
		'tool.call': {
			kind: 'cap',
			desc: '支持工具/函数调用（function calling / tool use）',
		},
		'tool.parallel': {
			kind: 'cap',
			desc: '支持并行工具调用（同一轮可触发多个 tool call）',
		},
		'output.json': {
			kind: 'cap',
			desc: '支持严格 JSON 输出（可用于结构化结果）',
		},
		'output.jsonSchema': {
			kind: 'cap',
			desc: '支持按 JSON Schema 约束输出（或等价的结构约束能力）',
		},
		'output.markdown': {
			kind: 'cap',
			desc: '支持 Markdown 输出（含标题/列表/代码块等格式）',
		},
		'vision.input': {
			kind: 'cap',
			desc: '支持输入图片进行理解（多模态视觉输入）',
		},
		'vision.output': {
			kind: 'cap',
			desc: '支持生成/编辑图片输出（若你的系统把它也归为 chat）',
		},
		'longContext': {
			kind: 'cap',
			desc: '支持长上下文（较大上下文窗口或等价能力）',
		},
		'planning': {
			kind: 'cap',
			desc: '支持计划/分解任务（planner 风格输出或内置规划）',
		},
		'code': {
			kind: 'cap',
			desc: '擅长代码生成/改写/审查（code-oriented chat）',
		},
		'citations': {
			kind: 'cap',
			desc: '支持带引用/来源标注的输出（若 agent 能提供）',
		},
		
		// ----------------------------
		// ARG: supported input/output args
		// ----------------------------
		'lang': {
			kind: 'arg',
			type: 'enum_or_list',
			values: ['zh', 'en', 'ja', 'ko', 'fr', 'de', 'es'],
			desc: '输出语言（或语言列表；用于多语言频道/多语言回答）',
		},
		
		'persona': {
			kind: 'arg',
			type: 'string',
			desc: '人设/角色（例如: assistant/devops tutor/法律助理；由 agent 自己解释）',
		},
		'tone': {
			kind: 'arg',
			type: 'enum',
			values: ['neutral', 'friendly', 'formal', 'playful', 'serious'],
			desc: '语气风格（粗粒度）',
		},
		'verbosity': {
			kind: 'arg',
			type: 'enum',
			values: ['short', 'medium', 'long'],
			desc: '输出详略程度（粗粒度）',
		},
		
		// structured output controls
		'response.format': {
			kind: 'arg',
			type: 'enum_or_list',
			values: ['text', 'json', 'markdown'],
			desc: '响应格式偏好（text/json/markdown）',
		},
		'response.jsonSchema': {
			kind: 'arg',
			type: 'string',
			desc: 'JSON Schema（建议传 JSON 字符串；由 agent 解析）',
		},
		
		// tool calling constraints
		'tools.allow': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '允许使用的工具名列表（或单个工具名）',
		},
		'tools.deny': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '禁止使用的工具名列表（或单个工具名）',
		},
		
		// model sampling hints (LLM-like)
		'sampling.temperature': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '采样温度（0-2 常见；范围由引擎解释）',
		},
		'sampling.topP': {
			kind: 'arg',
			type: 'number_or_range',
			desc: 'top_p（0-1 常见；范围由引擎解释）',
		},
		'sampling.maxTokens': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '最大输出 token 数（或 {min,max}）',
		},
		
		// safety / policy hints (non-binding; agent may ignore or map to its own policy)
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

export default chatKind
export { chatKind }
