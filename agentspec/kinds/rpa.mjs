// kinds/rpa.mjs
// KindDef: rpa (v0.6.1)
// Flattened cap/arg keys (prefer top-level names).
//
// Rule of thumb:
// - cap: concrete task ability (boolean support)
// - arg: parameters usable in FindVO.filter (typed)
//
// Conventions:
// - caps: key -> { kind:"cap"|"arg", desc, type?, values?, allowWildcard? }
// - ranks: key -> { desc, order:"asc"|"desc", valueFrom, type:"number", missing, defaultValue? }
// - defaultRanks: used when FindVO.rank is omitted

const rpaKind = {
	kind: 'rpa',
	
	caps: {
		// ----------------------------
		// CAP: task capabilities (business-level)
		// ----------------------------
		checkLogin: { kind: 'cap', desc: '检查当前是否已登录（返回已登录/未登录，或给出原因）' },
		ensureLogin: {
			kind: 'cap',
			desc: '确保已登录（若未登录可执行登录流程；可能需要 authMode + 凭据/cookie 由系统注入）'
		},
		
		readList: { kind: 'cap', desc: '读取信息流/文章列表/帖子列表（返回条目 url/title 等）' },
		readNextPage: { kind: 'cap', desc: '在列表/信息流上翻页或加载下一页（用于分页/无限滚动）' },
		
		readDetail: { kind: 'cap', desc: '读取单个 post/article 的详情内容（正文、作者、时间等）' },
		readReactions: { kind: 'cap', desc: '读取 post 的互动数据（赞/踩/收藏/转发/评论数等，字段由 outFields 指定）' },
		
		publishPost: { kind: 'cap', desc: '发表 post（可能包含文本/图片/链接等）' },
		editPost: { kind: 'cap', desc: '编辑已有 post' },
		deletePost: { kind: 'cap', desc: '删除已有 post' },
		
		readComments: { kind: 'cap', desc: '读取评论列表（含分页/排序由 agent 支持情况决定）' },
		publishComment: { kind: 'cap', desc: '发布评论/回复' },
		
		readProfile: { kind: 'cap', desc: '读取用户/频道/页面资料信息（关注数、简介、头像等）' },
		
		likePost: { kind: 'cap', desc: '对 post 点赞（或等价 reaction）' },
		dislikePost: { kind: 'cap', desc: '对 post 点踩（若平台支持）' },
		bookmarkPost: { kind: 'cap', desc: '收藏/保存 post（若平台支持）' },
		
		// ----------------------------
		// ARG: scope / target / strategy / output
		// ----------------------------
		
		// scope
		domain: {
			kind: 'arg',
			type: 'domain_list',
			allowWildcard: true,
			desc: '目标站点域名（支持 [\'a.com\',\'*\'] 降级）',
		},
		profile: {
			kind: 'arg',
			type: 'string_or_list',
			desc: '浏览器 profile 标识（用于多账号/多会话隔离）',
		},
		lang: {
			kind: 'arg',
			type: 'enum_or_list',
			values: ['zh', 'en', 'ja', 'ko', 'fr', 'de', 'es'],
			desc: '目标页面/内容语言（用于选择解析策略/输出语言）',
		},
		
		// target
		url: {
			kind: 'arg',
			type: 'string',
			desc: '目标 URL（单条详情/列表入口/操作页）',
		},
		// auth strategy
		authMode: {
			kind: 'arg',
			type: 'enum',
			values: ['none', 'cookie', 'password', 'oauth'],
			desc: '认证模式（none/cookie/password/oauth）',
		},
		
		// crawling / pagination
		maxPages: {
			kind: 'arg',
			type: 'number_or_range',
			desc: '最大翻页/加载页数（或 {min,max}）',
		},
		maxItems: {
			kind: 'arg',
			type: 'number_or_range',
			desc: '最大抓取条目数（或 {min,max}）',
		},
		
		// output
		outFields: {
			kind: 'arg',
			type: 'string_or_list',
			desc: '期望输出字段列表（例如 likes/dislikes/comments/views）',
		},
		outFormat: {
			kind: 'arg',
			type: 'enum_or_list',
			values: ['json', 'markdown', 'text'],
			desc: '输出格式偏好',
		},
		
		// execution hints
		waitMs: {
			kind: 'arg',
			type: 'number_or_range',
			desc: '进入页面后的等待时间（ms；用于 lazy-load/异步渲染）',
		},
		waitFor: {
			kind: 'arg',
			type: 'string_or_list',
			desc: '等待某个 selector/xpath/事件名可用（由 agent 解释）',
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
	},
	
	defaultRanks: ['successRate', 'latency', 'size'],
}

export default rpaKind
export { rpaKind }
