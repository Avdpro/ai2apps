const rpaKind = {
    kind: 'rpa',

    caps: {
        // blockers
        'blockers.check': {
            kind: 'cap',
            desc: '检查当前页面是否包含阻挡操作的干扰（Cookie 同意/订阅弹窗/模态对话框/遮罩层/插屏等）'
        },
        'blockers.clear': {
            kind: 'arg',
            type: 'boolean',
            desc: '自动清理阻挡操作的干扰（Cookie 同意/订阅弹窗/模态对话框/遮罩层/插屏等），以恢复可点击/可滚动状态'
        },
        
        // login
        'login.check': {
            kind: 'cap',
            desc: '检查当前是否已登录（返回已登录/未登录，或给出原因）'
        },
        'login.ensure': {
            kind: 'arg',
            type:'boolean',
            desc: '确保已登录（若未登录可执行登录流程；可能需要 authMode + 凭据/cookie 由系统注入或者用户介入）'
        },
        'login.interactive': {
            kind: 'cap',
            type:'boolean',
            desc: '支持交互式登录（需要用户手动输入账号密码或扫码）'
        },
        'login.meta': {
            kind: 'arg',
            type: 'object',
            desc: '登录所需要的信息，比如email，password等。'
        },
        'login.cookie': {
            kind: 'cap',
            desc: '支持通过 cookie 自动登录'
        },
        
        // search
        'search.keyword': {
            kind: 'cap',
            desc: '支持关键词搜索（返回搜索结果列表）'
        },
        'search.account': {
            kind: 'cap',
            desc: '支持账号/用户搜索（查找特定账号的内容）'
        },
        'search.pagination': {
            kind: 'cap',
            desc: '支持搜索结果分页/翻页'
        },
        'search.scroll': {
            kind: 'cap',
            desc: '支持无限滚动加载更多搜索结果'
        },

        // reading
        'read.article': {
            kind: 'cap',
            desc: '读取文章内容'
        },
        'read.list': {
            kind: 'cap',
            desc: '读取信息流/文章列表/帖子列表（返回条目 url/title 等）'
        },
        'read.listTarget': {
            kind: 'arg',
            type: 'string',
            desc: '要读取的列表项目的类型[search_result,article,email]'
        },
        'read.fields': {
            kind: 'arg',
            type: 'array>string>',
            desc: '要读出项目的哪些属性，比如: url, title, summary...'
        },
        'read.detail': {
            kind: 'arg',
            type: 'boolean',
            desc: '读取单个 post/article 的详情内容（正文、作者、时间等）'
        },
        'read.batch': {
            kind: 'cap',
            desc: '批量读取多个文章/帖子的详情（并发处理）'
        },
        'read.comments': {
            kind: 'cap',
            desc: '读取评论列表（含分页/排序由 agent 支持情况决定）'
        },
        'read.reactions': {
            kind: 'cap',
            desc: '读取 post 的互动数据（赞/踩/收藏/转发/评论数等，字段由 outFields 指定）'
        },
        'read.profile': {
            kind: 'cap',
            desc: '读取用户/频道/页面资料信息（关注数、简介、头像等）'
        },
        
        // compose
        'compose':{
            kind: 'cap',
            desc: '编写内容'
        },
        'compose.type':{
            kind: 'arg',
            type: 'string',
            desc: '编写内容类型：article, post, thread, comment, reply'
        },
        'compose.parent':{
            kind: 'arg',
            type: 'string',
            desc: '如果是评论或者回复，上一级的描述对象/selector'
        },
        'compose.action':{
            kind: 'arg',
            type: 'string ["start","title","content","block","asset","tag","publish"]',
            desc: '撰写的动作'
            
        },
        'compose.text':{
            kind: 'arg',
            type: 'string',
            desc: '撰写的内容文本'
        },
        'compose.block':{
            kind: 'arg',
            type: 'object',
            desc: '撰写的内容块对象'
        },
        'compose.file':{
            kind: 'arg',
            type: 'string',
            desc: '为撰写内容添加文件、图片、视频等附件的DataURL或文件路径'
        },
        'compose.visibility':{
            kind: 'arg',
            type: 'string',
            desc: '发布的可见范围, ["public","draft","private","fansOnly","friendsOnly]"'
        },

        // content management
        'edit.post': {
            kind: 'cap',
            desc: '编辑已有 post'
        },
        'delete.post': {
            kind: 'cap',
            desc: '删除已有 post'
        },

        // interaction
        'interact.like': {
            kind: 'cap',
            desc: '对 post 点赞（或等价 reaction）'
        },
        'interact.dislike': {
            kind: 'cap',
            desc: '对 post 点踩（若平台支持）'
        },
        'interact.bookmark': {
            kind: 'cap',
            desc: '收藏/保存 post（若平台支持）'
        },
        'interact.follow': {
            kind: 'cap',
            desc: '关注用户/频道（若平台支持）'
        },
        'interact.share': {
            kind: 'cap',
            desc: '分享/转发 post（若平台支持）'
        },
        
        //open
        'open': {
            kind: 'cap',
            desc: '支持打开浏览器/页面'
        },
        'open.focus': {
            kind: 'arg',
            type: 'boolean',
            desc: '是否聚焦打开的页面，默认为true'
        },
        'open.focusBack': {
            kind: 'arg',
            type: 'boolean',
            desc: '聚焦打开的页面后，是否切回来，默认为true'
        },

        //browser
        'browser.headless': {
            kind: 'cap',
            desc: '支持无头浏览器模式（headless mode）'
        },
        'browser.devtools': {
            kind: 'cap',
            desc: '支持开发者工具模式（devtools mode）'
        },
        'browser.profile': {
            kind: 'cap',
            desc: '支持多浏览器配置文件（profile）隔离'
        },
        'browser.cookies': {
            kind: 'cap',
            desc: '支持 cookie 管理和持久化'
        },

        // ai related
        'ai.query': {
            kind: 'cap',
            desc: '支持 AI 辅助查询和解析（使用 LLM 理解页面结构）'
        },
        'ai.extract': {
            kind: 'cap',
            desc: '支持 AI 智能提取内容（从复杂 HTML 中提取结构化数据）'
        },
        
        // web chat
        'webChat':{
            kind: 'cap',
            desc: '支持 Web 页面内的聊天，例如与AI对话'
        },
        
        'webChat.action':{
            kind: 'arg',
            type: 'string',
            desc: 'Web chat 动作： "getSessions",“newSession”,"enterSession","getMessages",“addAsset”,"input","send","waitReply"'
        },
        'webChat.session':{
            kind: 'arg',
            type: 'string',
            desc: 'session descriptor, for "enterSession", "deleteSession"'
        },
        
        //arg
        'platform': {
            kind: 'arg',
            type: 'enum_or_list',
            values: [
                'google', 'baidu', 'bilibili', 'rednote', 'xiaohongshu',
                'twitter', 'x', 'weibo', 'zhihu', 'linkedin',
                'nytimes', 'cnn', 'generic'
            ],
            desc: '目标平台标识',
        },
        'domain': {
            kind: 'arg',
            type: 'domain_list',
            allowWildcard: true,
            desc: '目标站点域名（支持 [\'a.com\',\'*\'] 降级）',
        },
        'url': {
            kind: 'arg',
            type: 'string',
            desc: '目标 URL（单条详情/列表入口/操作页）',
        },
        'profile': {
            kind: 'arg',
            type: 'string_or_list',
            desc: '浏览器 profile 标识（用于多账号/多会话隔离）',
        },
        'lang': {
            kind: 'arg',
            type: 'enum_or_list',
            values: ['zh', 'en', 'ja', 'ko', 'fr', 'de', 'es'],
            desc: '目标页面/内容语言（用于选择解析策略/输出语言）',
        },

        //auth
        'authMode': {
            kind: 'arg',
            type: 'enum',
            values: ['none', 'cookie', 'password', 'oauth', 'interactive'],
            desc: '认证模式（none/cookie/password/oauth/interactive）',
        },
        'username': {
            kind: 'arg',
            type: 'string',
            desc: '登录用户名（authMode=password 时使用）',
        },
        'password': {
            kind: 'arg',
            type: 'string',
            desc: '登录密码（authMode=password 时使用）',
        },

        // search
        'search': {
            kind: 'arg',
            type: 'string',
            desc: '搜索关键词或查询字符串',
        },
        'searchNum': {
            kind: 'arg',
            type: 'number_or_range',
            desc: '期望搜索结果数量（或 {min,max}）',
        },
        'account': {
            kind: 'arg',
            type: 'string',
            desc: '目标账号名（用于账号搜索或内容抓取）',
        },

        // crawler
        'maxPages': {
            kind: 'arg',
            type: 'number_or_range',
            desc: '最大翻页/加载页数（或 {min,max}）',
        },
        'minItems': {
            kind: 'arg',
            type: 'number_or_range',
            desc: '最少（如果有）抓取条目数（或 {min,max}）',
        },
        'maxItems': {
            kind: 'arg',
            type: 'number_or_range',
            desc: '最大抓取条目数（或 {min,max}）',
        },
        'scrollRounds': {
            kind: 'arg',
            type: 'number_or_range',
            desc: '滚动加载轮数（用于无限滚动场景）',
        },
        
        //post
        'publish.post': {
            kind: 'cap',
            desc: '发表 post（可能包含文本/图片/链接等）'
        },
        'post.addImage':{
            kind: 'cap',
            desc: '专门支持添加图片的Agent',
        },
        'post.addVideo':{
            kind: 'cap',
            desc: '专门支持添加视频的Agent',
        },
        'post.title':{
            kind: 'arg',
            type: 'string',
            desc: '发帖子的标题',
        },
        'post.text':{
            kind: 'arg',
            type: 'string',
            desc: '发帖子的文本内容',
        },
        'post.topic':{
            kind: 'arg',
            type: 'string-or-list',
            desc: '发帖子的标签',
        },
        'post.image':{
            kind: 'arg',
            type: 'string-or-list',
            desc: '发帖子的图片',
        },
        'post.video':{
            kind: 'arg',
            type: 'string-or-list',
            desc: '发帖子的视频',
        },
        'post.contentBlocks':{
            kind: 'arg',
            type: 'list',
            desc: '帖子的标题图文内容块数组，用于复杂文章的发布',
        },

        //comment & reaction
        'publish.comment': {
            kind: 'cap',
            desc: '发布评论/回复'
        },
        'comment.text': {
            kind: 'arg',
            type: 'string',
            desc: '要发布的评论文本内容',
        },
        'comment.image': {
            kind: 'arg',
            type: 'string-or-list',
            desc: '要发布的评论图片',
        },
        'comments': {
            kind: 'arg',
            type: 'number_or_range',
            desc: '抓取评论数量（或 {min,max}）',
        },
        'commentsNum': {
            kind: 'arg',
            type: 'number_or_range',
            desc: '评论数量（或 {min,max}，与 comments 同义）',
        },
        'finds': {
            kind: 'arg',
            type: 'array',
            desc: '待处理的 URL/文章列表（用于批量读取）',
        },

        //output & format
        'outFields': {
            kind: 'arg',
            type: 'string_or_list',
            desc: '期望输出字段列表（例如 title/author/content/time/likes/comments/views）',
        },
        'outFormat': {
            kind: 'arg',
            type: 'enum_or_list',
            values: ['json', 'markdown', 'text', 'html'],
            desc: '输出格式偏好',
        },

        // browser
        'headless': {
            kind: 'arg',
            type: 'boolean',
            desc: '是否使用无头模式（默认 false）',
        },
        'devtools': {
            kind: 'arg',
            type: 'boolean',
            desc: '是否开启开发者工具（默认 false）',
        },
        'viewport.width': {
            kind: 'arg',
            type: 'number',
            desc: '浏览器视口宽度（默认 1200）',
        },
        'viewport.height': {
            kind: 'arg',
            type: 'number',
            desc: '浏览器视口高度（默认 900）',
        },
        'userAgent': {
            kind: 'arg',
            type: 'string',
            desc: '自定义 User-Agent',
        },

        // timing
        'waitMs': {
            kind: 'arg',
            type: 'number_or_range',
            desc: '进入页面后的等待时间（ms；用于 lazy-load/异步渲染）',
        },
        'waitBefore': {
            kind: 'arg',
            type: 'number',
            desc: '操作前等待时间（ms）',
        },
        'waitAfter': {
            kind: 'arg',
            type: 'number',
            desc: '操作后等待时间（ms）',
        },
        'waitFor': {
            kind: 'arg',
            type: 'string_or_list',
            desc: '等待某个 selector/xpath/事件名可用（由 agent 解释）',
        },
        'timeout': {
            kind: 'arg',
            type: 'number',
            desc: '操作超时时间（ms；默认 30000）',
        },
        
        //concurrency
        'concurrency': {
            kind: 'arg',
            type: 'number',
            desc: '并发处理数量（用于批量操作）',
        },
        'retryCount': {
            kind: 'arg',
            type: 'number',
            desc: '失败重试次数（默认 0）',
        },

        // others
        'xpath': {
            kind: 'arg',
            type: 'string',
            desc: '自定义 XPath 查询表达式',
        },
        'selector': {
            kind: 'arg',
            type: 'string',
            desc: '自定义 CSS Selector',
        },
        'customScript': {
            kind: 'arg',
            type: 'string',
            desc: '自定义 JavaScript 脚本（在页面上下文中执行）',
        },
        'extractRule': {
            kind: 'arg',
            type: 'object',
            desc: '自定义提取规则（JSON 对象，定义字段提取逻辑）',
        },
        'showMore':{
            kind: 'cap',
            desc: '显示更多内容',
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
        reliability: {
            desc: '可靠性评分（越高越优先）',
            order: 'desc',
            valueFrom: 'metrics.reliability',
            type: 'number',
            missing: 'last',
        },
        speed: {
            desc: '执行速度（越快越优先）',
            order: 'asc',
            valueFrom: 'metrics.avgExecutionTime',
            type: 'number',
            missing: 'last',
        },
    },

    defaultRanks: ['successRate', 'latency', 'size'],
}

export default rpaKind
export {rpaKind}

