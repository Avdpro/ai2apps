// kinds/code.mjs
// KindDef: code (v0.6.1)
//
// code covers: code generation, refactor, review, debugging, test generation,
// patch/diff output, multi-file planning, and repo-aware tasks.
//
// Conventions:
// - caps: key -> { kind:"cap"|"arg", desc, type?, values?, allowWildcard? }
// - ranks: key -> { desc, order:"asc"|"desc", valueFrom, type:"number", missing, defaultValue? }
// - defaultRanks: used when FindVO.rank is omitted

const codeKind = {
	kind: 'code',
	
	caps: {
		// ----------------------------
		// CAP: capability switches
		// ----------------------------
		'gen.code': {
			kind: 'cap',
			desc: '支持生成新代码（从需求到实现）',
		},
		'edit.refactor': {
			kind: 'cap',
			desc: '支持重构/整理代码（保持语义，改善结构/可读性）',
		},
		'edit.patch': {
			kind: 'cap',
			desc: '支持以 patch/diff 形式输出修改（unified diff 或等价格式）',
		},
		'review': {
			kind: 'cap',
			desc: '支持代码审查（指出问题、风险、风格建议）',
		},
		'debug': {
			kind: 'cap',
			desc: '支持调试/排错（定位原因、提出修复）',
		},
		'tests.unit': {
			kind: 'cap',
			desc: '支持生成单元测试（unit tests）',
		},
		'tests.integration': {
			kind: 'cap',
			desc: '支持生成集成测试（integration tests）',
		},
		'docs.api': {
			kind: 'cap',
			desc: '支持生成 API 文档/注释（docstring/jsdoc）',
		},
		'repo.multiFile': {
			kind: 'cap',
			desc: '支持多文件/多模块任务（能输出文件列表与修改计划）',
		},
		'build.fix': {
			kind: 'cap',
			desc: '支持修复构建/CI 错误（根据日志定位问题）',
		},
		'security.scan': {
			kind: 'cap',
			desc: '支持安全审查（依赖风险、注入、权限等）',
		},
		
		// ----------------------------
		// ARG: supported input/output args
		// ----------------------------
		'lang': {
			kind: 'arg',
			type: 'enum_or_list',
			values: ['js', 'ts', 'python', 'go', 'java', 'rust', 'cpp', 'csharp', 'php', 'ruby'],
			desc: '目标编程语言（或语言列表）',
		},
		'framework': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '框架/生态（例如: react/electron/node/nextjs/django）',
		},
		
		'input.code': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '输入代码（片段/文件内容；可为数组）',
		},
		'input.diff': {
			kind: 'arg',
			type: 'string',
			desc: '输入 diff/patch（用于继续修改或审查）',
		},
		'input.errorLog': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '错误日志/堆栈（build/test/runtime）',
		},
		
		'output.format': {
			kind: 'arg',
			type: 'enum',
			values: ['code', 'diff', 'markdown', 'json'],
			desc: '输出格式（纯代码/差异补丁/说明文档/结构化 JSON）',
		},
		'output.style': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '风格约束（例如: eslint/prettier/pep8/compact functions）',
		},
		'output.files': {
			kind: 'arg',
			type: 'string_or_list',
			desc: '期望输出/修改的文件路径列表（用于多文件任务）',
		},
		
		// constraints / quality
		'constraints.noWeb': {
			kind: 'arg',
			type: 'enum',
			values: ['true', 'false'],
			desc: '是否禁止联网/外部依赖（string enum；也可未来扩展 boolean）',
		},
		'constraints.maxChanges': {
			kind: 'arg',
			type: 'number_or_range',
			desc: '修改范围/变更量上限（由 agent 自己解释）',
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

export default codeKind
export { codeKind }
