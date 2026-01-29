const rpaKind = {
    kind: 'rpa',

    // semantics:
    // - In find.must/find.prefer, keys mean the agent *has* the capability/arg; they do NOT mean "execute".
    // - By default, all args can also be treated as capabilities for matching/sorting.
    semantics: {
        // 语义约定：find.must / find.prefer 仅表示“具备能力（has-cap）”，不代表本次一定要执行该动作
        findIsHasCapOnly: true,
        // 语义约定：所有 args 默认也可作为 capability key 被 find.must / find.prefer 引用
        argsAreCapsByDefault: true,
    },

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
        //result:
        'blockers.check.result': {
            kind: 'result',
            desc: 'blockers.check 成功时的 value 结构',
            done: {
                value: {
                    blocked: { type: 'boolean', desc: '是否存在阻挡交互的干扰（可见且有效）' },
                    cleared: { type: 'boolean', required: false, desc: '若 blockers.clear=true 且执行了清理，则为 true' },
                }
            }
        },
        
        // login
        'login.check': {
            kind: 'cap',
            desc: '检查当前是否已登录（返回已登录/未登录，或给出原因）'
        },
        'login.ensure': {
            kind: 'arg',
            type:'boolean',
            desc: '确保已登录（先 check；若未登录则引导用户在页面完成登录/验证码等交互流程；不持久化保存任何登录信息/凭据。若通过安全通道注入一次性凭据/会话信息，也必须仅用于本次运行）'
        },
        'login.interactive': {
            kind: 'cap',
            desc: '表示该 Agent 支持在 login.ensure 过程中进行交互式登录引导（例如打开登录入口、提示用户扫码/输入、等待并复检登录状态）。不采集、不保存用户账号密码等敏感信息。'
        },
        'login.meta': {
            kind: 'arg',
            type: 'object',
            deprecated: true,
            privacyRisk: 'sensitive',
            desc: '【不推荐】敏感登录信息占位（如账号/密码/验证码提示等）。当前规范不要求也不建议通过该字段传递敏感凭据；若未来在安全注入场景使用，必须仅限本次运行、不得持久化。'
        },
        'login.cookie': {
            kind: 'arg',
            type: 'string_or_list',
            privacyRisk: 'sensitive',
            transient: true,
            desc: '（可选）用于本次运行的会话 cookie（或其列表/序列化形式）。仅允许安全通道注入，且必须只用于本次运行；不得写入磁盘、不得跨会话复用。用于解决需要额外人机验证/二次确认等场景下的保底策略。'
        },
        //results:
        'login.check.result': {
            kind: 'result',
            desc: 'login.check 成功时的 value 结构',
            done: {
                value: {
                    loggedIn: { type: 'boolean', desc: '是否已登录' },
                    reason: { type: 'string', required: false, desc: '未登录时的原因（best-effort）' },
                }
            }
        },
        'login.ensure.result': {
            kind: 'result',
            desc: 'login.ensure 成功时的 value 结构（确保已登录）',
            done: {
                value: {
                    loggedIn: { type: 'boolean', desc: '最终是否已登录（确保后状态）' },
                    reason: { type: 'string', required: false, desc: '若仍未登录，给出原因（best-effort）' },
                }
            }
        },
        
        // search
        'search': {
            kind: 'cap',
            desc: '支持搜索（返回搜索结果数组）',
        },
        'search.query': {
            kind: 'arg',
            type: 'string',
            desc: '搜索查询语句（关键词/短语/站内高级检索表达式等）'
        },
        'search.target': {
            kind: 'arg',
            type: 'enum',
            values: ['general', 'web', 'image', 'video', 'entity'],
            desc: '搜索目标大类（默认 general）。可用于偏好：网页/图片/视频/实体等。'
        },
        'search.entityType': {
            kind: 'arg',
            type: 'enum',
            values: ['user', 'post', 'product', 'shop'],
            desc: '当 search.target="entity" 时生效，用于细分实体类型（用户/帖子/商品/店铺等）。'
        },
        'search.minResults': {
            kind: 'arg',
            type: 'number',
            desc: '尽量至少返回的结果数量（best-effort）。达到该数量或已无更多结果时停止。'
        },
        //result:
        'search.result': {
            kind: 'result',
            desc: 'search 成功时的 value 结构（SERP 级结果，不要求自动打开）',
            done: {
                value: {
                    urls: { type: 'array<string>', desc: '搜索结果 url 数组（按相关性排序，尽量为绝对 URL）' },
                    items: { type: 'array<object>', required: false, desc: '可选：更丰富的条目（如 title/snippet/siteName），best-effort' },
                    nextCursor: { type: 'string', required: false, desc: '可选：继续拉取更多结果的游标（若实现支持）' },
                }
            }
        },

        // reading
        'read.action': {
            kind: 'arg',
            type: 'enum',
            values: ['article', 'list', 'detail', 'comments', 'reactions', 'profile', 'batch'],
            desc: '指定本次 read 要执行的短任务链（路由）。注意：find.must/find.prefer 仅表示 agent 具备能力，不表示一定执行；执行哪个动作以 read.action 为准。',
            argsByAction: {
                article: { required: [], optional: ['read.fields', 'read.requireFields', 'read.output'] },
                list: { required: [], optional: ['read.target', 'read.minItems', 'read.filter', 'read.sort', 'read.fields', 'read.requireFields', 'read.output'] },
                detail: { required: [], optional: ['read.target', 'read.fields', 'read.requireFields', 'read.output'] },
                comments: { required: [], optional: ['read.target', 'read.minItems', 'read.filter', 'read.sort', 'read.fields', 'read.requireFields', 'read.output'] },
                reactions: { required: [], optional: ['read.target', 'read.fields', 'read.requireFields', 'read.output'] },
                profile: { required: [], optional: ['read.target', 'read.fields', 'read.requireFields', 'read.output'] },
                batch: { required: [], optional: ['read.target', 'read.minItems', 'read.filter', 'read.sort', 'read.fields', 'read.requireFields', 'read.output'] },
            }
        },
        'read.article': {
            kind: 'cap',
            desc: '读取文章内容'
        },
        'read.list': {
            kind: 'cap',
            desc: '读取信息流/文章列表/帖子列表（返回条目 url/title 等）'
        },
        'read.target': {
            kind: 'arg',
            type: 'object',
            desc: '读取目标（可选）。缺省表示“主对象/主内容”。当 action=list 时，target.by/query/selector 应返回列表项集合；target.pick 缺省表示读取全部匹配项，pick=数字表示第 N 个（建议 1-based，-1 表示最后一个），pick=字符串表示选择包含该文本的第一个匹配项。',
            schema: {
                by: 'auto|query|selector',
                query: 'string|object (when by=query)',
                selector: 'string (when by=selector)',
                pick: 'number|string|object (optional)'
            }
        },
        'read.fields': {
            kind: 'arg',
            type: 'array<string>',
            desc: '要读出项目的哪些属性，比如: url, title, summary...'
        },
        'read.requireFields': {
            kind: 'arg',
            type: 'array<string>',
            desc: '必须读出的字段名列表。若无法抽取到这些字段，read 结果应标记为失败或返回 missingFields。'
        },
        'read.minItems': {
            kind: 'arg',
            type: 'number',
            desc: '用于 list/comments/batch：尽量至少返回的条目数量（best-effort）。达到该数量或已无更多结果时停止。'
        },
        'read.filter': {
            kind: 'arg',
            type: 'array<object>',
            desc: '可选。列表过滤条件（默认不过滤）。为通用性，条件字段不强制标准化，agent best-effort 应用。多个条件默认 AND。示例：[{textIncludes:"foo"},{status:"unread"}]'
        },
        'read.sort': {
            kind: 'arg',
            type: 'enum',
            values: ['auto', 'newest', 'oldest', 'relevance'],
            desc: '可选。列表排序偏好。auto=保持页面默认排序（默认）。'
        },
        'read.output': {
            kind: 'arg',
            type: 'enum',
            values: ['raw', 'markdown', 'json'],
            desc: '输出格式偏好。raw=原始字段值；markdown=适合展示；json=结构化输出（字段仍由 read.fields/requireFields 决定）。'
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
        //Result:
        'read.result': {
            kind: 'result',
            desc: 'read 总入口（由 read.action 路由）成功时的 value 结构（简洁统一）',
            done: {
                value: {
                    action: { type: 'string', desc: '本次执行的 read.action' },
                    data: { type: 'object', required: false, desc: '单对象结果（article/detail/profile/reactions 等）' },
                    items: { type: 'array<object>', required: false, desc: '列表结果（list/comments/batch 等）' },
                    nextCursor: { type: 'string', required: false, desc: '可选：继续加载/分页游标（若实现支持）' },
                    missingFields: { type: 'array<string>', required: false, desc: '未能抽取到的必需字段（若 read.requireFields 指定）' },
                }
            }
        },
        
        'read.article.result': {
            kind: 'result',
            desc: 'read.article 成功时的 value 结构',
            done: {
                value: {
                    data: { type: 'object', desc: '文章/主对象字段（由 read.fields / read.output 决定，best-effort）' },
                    missingFields: { type: 'array<string>', required: false, desc: '未能抽取到的必需字段（若 read.requireFields 指定）' },
                }
            }
        },
        'read.list.result': {
            kind: 'result',
            desc: 'read.list 成功时的 value 结构',
            done: {
                value: {
                    items: { type: 'array<object>', desc: '列表条目数组（每项至少建议包含 url/title 等）' },
                    nextCursor: { type: 'string', required: false, desc: '可选：继续加载/分页游标（若实现支持）' },
                    missingFields: { type: 'array<string>', required: false, desc: '未能抽取到的必需字段（若 read.requireFields 指定）' },
                }
            }
        },
        'read.detail.result': {
            kind: 'result',
            desc: 'read.detail 成功时的 value 结构',
            done: {
                value: {
                    data: { type: 'object', desc: '单条详情字段（best-effort）' },
                    missingFields: { type: 'array<string>', required: false, desc: '未能抽取到的必需字段（若 read.requireFields 指定）' },
                }
            }
        },
        'read.comments.result': {
            kind: 'result',
            desc: 'read.comments 成功时的 value 结构',
            done: {
                value: {
                    items: { type: 'array<object>', desc: '评论条目数组（best-effort）' },
                    nextCursor: { type: 'string', required: false, desc: '可选：继续加载评论的游标（若实现支持）' },
                    missingFields: { type: 'array<string>', required: false, desc: '未能抽取到的必需字段（若 read.requireFields 指定）' },
                }
            }
        },
        'read.reactions.result': {
            kind: 'result',
            desc: 'read.reactions 成功时的 value 结构',
            done: {
                value: {
                    data: { type: 'object', desc: '互动数据字段（点赞/收藏/转发/评论数等，best-effort）' },
                    missingFields: { type: 'array<string>', required: false, desc: '未能抽取到的必需字段（若 read.requireFields 指定）' },
                }
            }
        },
        'read.profile.result': {
            kind: 'result',
            desc: 'read.profile 成功时的 value 结构',
            done: {
                value: {
                    data: { type: 'object', desc: '用户/频道资料字段（best-effort）' },
                    missingFields: { type: 'array<string>', required: false, desc: '未能抽取到的必需字段（若 read.requireFields 指定）' },
                }
            }
        },
        'read.batch.result': {
            kind: 'result',
            desc: 'read.batch 成功时的 value 结构',
            done: {
                value: {
                    items: { type: 'array<object>', desc: '批量读取结果数组（每项通常包含 url + data 或 error 信息，best-effort）' },
                    missingFields: { type: 'array<string>', required: false, desc: '未能抽取到的必需字段（若 read.requireFields 指定）' },
                }
            }
        },

        // loadMore
        'loadMore': {
            kind: 'cap',
            desc: '在当前页面加载更多列表内容（自动判断使用下一页/滚动/“加载更多”按钮等方式）'
        },
        'loadMore.target': {
            kind: 'arg',
            type: 'object',
            desc: '可选。用于指定要加载更多的列表/信息流目标（by=query|selector|auto）。缺省表示页面主列表/主内容流。'
        },
        'loadMore.minNewItems': {
            kind: 'arg',
            type: 'number',
            desc: '可选。期望本次至少新增的条目数量（best-effort，默认 1）。用于判断是否“确实加载到了更多”。'
        },
        'loadMore.maxTries': {
            kind: 'arg',
            type: 'number',
            desc: '可选。最多尝试次数（best-effort，默认 3）。用于避免无限加载循环。'
        },
        'loadMore.result': {
            kind: 'result',
            desc: 'loadMore 成功时的 value 结构',
            done: {
                value: {
                    newItems: { type: 'number', desc: '本次新增条目数量（best-effort）' },
                    hasMore: { type: 'boolean', required: false, desc: '是否可能还有更多内容（best-effort）' },
                }
            }
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
            type: 'enum',
            values: ['start','input','file','publish','edit'],
            desc: '撰写的动作（用于路由到对应的原子/短任务链）',
            // action -> 参数约束（required/optional 仅用于校验与生成提示；不影响 must/prefer 的 has-cap 语义）
            argsByAction: {
                start:   { required: [], optional: ['compose.type','compose.visibility'] },
                input:   { required: [], optional: ['compose.field','compose.text','compose.blocks'] },
                file:    { required: ['compose.files'], optional: ['compose.field'] },
                publish: { required: [], optional: ['compose.visibility'] },
                edit:    { required: ['compose.parent'], optional: ['compose.field','compose.text','compose.blocks','compose.files','compose.visibility'] },
            }

        },
        'compose.start':{
            kind: 'cap',
            desc: '具备启动编写内容的能力'
        },
        'compose.input':{
            kind: 'cap',
            desc: '具备填写撰写内容的能力'
        },
        'compose.file':{
            kind: 'cap',
            desc: '具备添加文件附件的能力'
        },
        'compose.publish':{
            kind: 'cap',
            desc: '具备发布能力（可将已撰写内容发布/发送/提交）'
        },
        'compose.edit':{
            kind: 'cap',
            desc: '具备编辑已发布内容的能力'
        },
        'compose.field':{
            kind: 'arg',
            type: 'enum',
            values: ['title','content','tag','subtitle','image','video'],
            desc: '填写的目标，默认为"content"'
        },
        'compose.text':{
            kind: 'arg',
            type: 'string',
            desc: '要填写的内容文本'
        },
        'compose.block':{
            kind: 'arg',
            type: 'object',
            desc: '撰写的内容块对象'
        },
        'compose.blocks':{
            kind: 'arg',
            type: 'array<object>',
            desc: '撰写的内容块数组（用于结构化/富文本输入）'
        },
        'compose.files':{
            kind: 'arg',
            type: 'array<string>',
            desc: '为撰写内容添加文件、图片、视频等附件的本地文件路径数组'
        },
        'compose.visibility':{
            kind: 'arg',
            type: 'string',
            desc: '发布的可见范围, ["public","draft","private","fansOnly","friendsOnly"]'
        },
        //compose results:
        'compose.result': {
            kind: 'result',
            desc: 'compose 成功时的 value 结构（由 compose.action 路由，best-effort）',
            done: {
                value: {
                    action: { type: 'string', desc: '本次执行的 compose.action' },
                    id: { type: 'string', required: false, desc: '发布/对象 id（若可获取）' },
                    url: { type: 'string', required: false, desc: '发布后或编辑对象的 url（若可获取）' },
                }
            }
        },
        'compose.publish.result': {
            kind: 'result',
            desc: 'compose.publish 成功时的 value 结构（发布/发送/提交结果）',
            done: {
                value: {
                    action: { type: 'string', value:"publish", desc: '本次执行的 compose.action' },
                    id: { type: 'string', required: false, desc: '发布对象 id（若可获取）' },
                    url: { type: 'string', required: false, desc: '发布对象 url（若可获取）' },
                }
            }
        },

        // content management
        'delete.post': {
            kind: 'cap',
            risk: 'destructive',
            desc: '删除已有 post'
        },
        //delete results:
        'delete.post.result': {
            kind: 'result',
            desc: 'delete.post 成功时的 value 结构',
            done: { value: { deleted: { type: 'boolean', desc: '是否已删除（best-effort）' } } }
        },
        
        
        // fill
        'fill': {
            kind: 'cap',
            desc: '填写表单/控件（通用）'
        },
        'fill.action': {
            kind: 'arg',
            type: 'enum',
            values: ['text','select','check','upload','submit','clear'],
            desc: '填写动作类型：text=文本输入；select=选项选择；check=勾选/取消勾选；upload=上传文件；submit=提交；clear=清空。执行时由 invoke args 指定 action'
        },
        'fill.target': {
            kind: 'arg',
            type: 'object',
            desc: '必填。定位要操作的控件/入口。复用 by=query|selector 的结构（query/selector 具体格式由实现约定）。upload 时通常定位“上传入口”（按钮/区域/或 <input type="file">）'
        },
        'fill.value': {
            kind: 'arg',
            desc: '按 action 不同语义不同：text 为 string；select 为 string|array<string>；check 为 boolean'
        },
        'fill.files': {
            kind: 'arg',
            type: 'array<string>',
            desc: 'upload 时必填：要上传的本地文件路径数组'
        },
        'fill.uploadMode': {
            kind: 'arg',
            type: 'enum',
            values: ['user','setFiles','auto'],
            desc: 'upload 模式：user=优先 click 触发系统文件对话框并由执行器截获设置文件；setFiles=直接对 <input type="file"> setFiles；auto=优先 user，失败则 fallback setFiles。默认 user'
        },
        'fill.textMode': {
            kind: 'arg',
            type: 'enum',
            values: ['set','append'],
            desc: 'text 模式：set=覆盖输入（默认）；append=追加输入'
        },
        'fill.clear': {
            kind: 'arg',
            type: 'boolean',
            desc: 'text 模式下可用：在输入前先清空（默认 true，仅当 textMode=set 时生效）'
        },
        'fill.selectMode': {
            kind: 'arg',
            type: 'enum',
            values: ['set','add','remove'],
            desc: 'select 模式下可用：set=设为指定值（默认）；add/remove=多选时追加/移除'
        },
        'fill.verify': {
            kind: 'arg',
            type: 'boolean',
            desc: '是否在操作后验证状态已生效（默认 true）'
        },
        'fill.timeoutMs': {
            kind: 'arg',
            type: 'number',
            desc: '可选：等待控件生效/上传完成的超时时间（毫秒）'
        },
        //fill results:
        'fill.result': {
            kind: 'result',
            desc: 'fill 成功时的 value 结构（通用表单填写结果）',
            done: {
                value: {
                    action: { type: 'string', desc: '本次执行的 fill.action' },
                    changed: { type: 'boolean', desc: '是否实际造成了状态变化（best-effort）' },
                }
            }
        },
        
        
        // interaction
        'interact': {
            kind: 'cap',
            desc: '对当前页面的主对象或页面内列表项执行轻量交互（点赞/收藏/关注/分享等）'
        },
        'interact.action': {
            kind: 'arg',
            type: 'enum',
            values: ['like','dislike','bookmark','follow','share','repost','open','expand','collapse', 'select'],
            desc: '交互动作类型（不代表一定执行；find.must/find.prefer 仅表示具备能力；执行时由 invoke args 指定 action）'
        },
        'interact.selectMode': {
            kind: 'arg',
            type: 'enum',
            values: ['replace', 'add', 'toggle'],
            desc: '仅当 action=select 时使用：replace=替换当前选择（默认）；add=追加到当前选择（用于多选）；toggle=反选目标项。'
        },
        'interact.mode': {
            kind: 'arg',
            type: 'enum',
            values: ['set','toggle'],
            desc: '交互模式：set=幂等设置为期望状态；toggle=点击一次切换状态。默认 set'
        },
        'interact.value': {
            kind: 'arg',
            type: 'boolean',
            desc: '当 mode=set 时，期望的最终状态。true=确保已生效（如已点赞/已关注）；false=确保取消。默认 true'
        },
        'interact.target': {
            kind: 'arg',
            type: 'object',
            desc: '可选。用于在当前页面内选择“目标 item 容器”。by/query/selector 应返回 0..N 个 item（数组）；pick 用于从中选出具体一个：number=第N个(建议1-based，可用-1表示最后一个)；string=选择包含该文本的第一个 item；也可扩展为 object（如 {textIncludes,nth}）。省略则表示页面主对象'
        },
        'interact.control': {
            kind: 'arg',
            type: 'object',
            desc: '可选。用于在 target 选中的容器内部再次定位具体可点击控件（按钮/链接）。支持 by=query|selector|auto。省略则根据 interact.action 自动定位。实现时应限制在容器内查找以减少误点'
        },
        //interac result:
        'interact.result': {
            kind: 'result',
            desc: 'interact 成功时的 value 结构（轻量交互结果）',
            done: {
                value: {
                    action: { type: 'string', desc: '本次执行的 interact.action' },
                    state: { type: 'boolean', required: false, desc: '交互后的目标状态（当可判定时）' },
                    changed: { type: 'boolean', required: false, desc: '是否实际发生变化（best-effort）' },
                }
            }
        },
        
        // nav
        'nav': {
            kind: 'cap',
            desc: '站点内导航/进入指定导航目的地（如 Home/Account/Friends/Inbox/Settings 等）。'
        },
        'nav.dest': {
            kind: 'arg',
            type: 'string',
            desc: '导航目的地的规范名/意图名。仅表达“去哪里”，具体如何定位入口由 Agent 实现决定。'
        },
        'nav.result': {
            kind: 'result',
            desc: 'nav 成功时的 value 结构',
            done: {
                value: {
                    dest: { type: 'string', desc: '导航目的地（回显 nav.dest）' },
                    url: { type: 'string', required: false, desc: '导航后页面 url（若可获取）' },
                }
            }
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
        'open.result': {
            kind: 'result',
            desc: 'open 成功时的 value 结构',
            done: {
                value: {
                    pageRef: { type: 'string', required: false, desc: '新页面引用（若有）' },
                    url: { type: 'string', required: false, desc: '打开的 url（若可获取）' },
                }
            }
        },

        // download
        'download': {
            kind: 'cap',
            desc: '下载文件/附件（通过点击触发下载或直接 URL）。'
        },
        'download.action': {
            kind: 'arg',
            type: 'enum',
            values: ['file'],
            desc: '下载动作类型。当前仅支持 file。'
        },
        'download.url': {
            kind: 'arg',
            type: 'string',
            desc: '可选。直接下载的 URL（若提供则优先使用）。'
        },
        'download.target': {
            kind: 'arg',
            type: 'object',
            desc: '可选。通过页面元素触发下载时，用于定位可点击的下载控件。复用 by/query/selector 结构（在当前页面内）。',
            schema: {
                by: 'auto|query|selector',
                query: 'string|object (when by=query)',
                selector: 'string (when by=selector)'
            }
        },
        'download.saveAs': {
            kind: 'arg',
            type: 'string',
            desc: '可选。期望保存的文件名或相对路径（由执行器决定实际落盘位置）。'
        },
        'download.multi': {
            kind: 'arg',
            type: 'boolean',
            desc: '可选。是否允许一次下载多个文件。默认 false。'
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
            desc: '支持 Web IM/聊天（Discord/WhatsApp Web/各类 Web AI Bot 等），以“会话/消息”为中心提供原子/短任务链。'
        },
        'webChat.action':{
            kind: 'arg',
            type: 'enum',
            values: ['getSessions','newSession','enterSession','getMessages','loadMoreMessages','searchMessages','addAsset','input','send','react','markRead','waitReply'],
            desc: 'Web chat 动作（用于路由到对应的原子/短任务链）。',
            
            // argsByAction 仅用于说明/校验；find.must/find.prefer 仍表示 has-cap。
            argsByAction: {
                getSessions: { optional: ['webChat.limit','webChat.fields'] },
                newSession: { required: ['webChat.session'], optional: ['webChat.text','webChat.assets'] },
                enterSession: { required: ['webChat.session'] },
                getMessages: { optional: ['webChat.session','webChat.limit','webChat.cursor','webChat.direction','webChat.minNew','webChat.fields'] },
                loadMoreMessages: { optional: ['webChat.session','webChat.minNew'] },
                searchMessages: { required: ['webChat.query'], optional: ['webChat.session','webChat.limit','webChat.fields'] },
                addAsset: { required: ['webChat.assets'], optional: ['webChat.session'] },
                input: { required: ['webChat.text'], optional: ['webChat.session'] },
                send: { required: ['webChat.text'], optional: ['webChat.session','webChat.replyTo','webChat.mention','webChat.sendMode','webChat.dedupeKey','webChat.assets'] },
                react: { required: ['webChat.reaction'], optional: ['webChat.session','webChat.message'] },
                markRead: { optional: ['webChat.session'] },
                waitReply: { optional: ['webChat.session','webChat.minNew','webChat.cursor'] },
            }
        },
        'webChat.session':{
            kind: 'arg',
            type: 'object',
            desc: '会话/频道/线程 descriptor（用于 enterSession/newSession 等）。兼容：也可传 string 作为 title。',
            schema: {
                kind: 'dm|group|channel|thread (optional)',
                title: 'string (optional)',
                id: 'string (optional)',
                path: 'array<string> (optional, e.g. ["Server","Channel","Thread"])',
                pick: 'number|string (optional, pick from getSessions result; 1-based index or text match)'
            }
        },
        'webChat.limit':{
            kind: 'arg',
            type: 'number',
            desc: '可选。一次最多返回/处理的会话或消息数量（best-effort）。'
        },
        'webChat.cursor':{
            kind: 'arg',
            type: 'string',
            desc: '可选。消息游标（messageId / timestamp / 内部游标），用于增量拉取/继续加载。'
        },
        'webChat.direction':{
            kind: 'arg',
            type: 'enum',
            values: ['newer','older'],
            desc: '可选。消息拉取方向：newer=获取更新消息；older=获取更早历史。默认 newer。'
        },
        'webChat.minNew':{
            kind: 'arg',
            type: 'number',
            desc: '可选。尽量至少获取/等待新增的消息条数（best-effort）。达到或无更多则停止。'
        },
        'webChat.fields':{
            kind: 'arg',
            type: 'array<string>',
            desc: '可选。期望输出/抽取的字段（如 id/ts/author/text/assets/reactions 等），best-effort。'
        },
        'webChat.text':{
            kind: 'arg',
            type: 'string',
            desc: '可选。输入或发送的文本内容。'
        },
        'webChat.assets':{
            kind: 'arg',
            type: 'array<string>',
            desc: '可选。要添加/发送的本地文件路径数组（附件/图片/文件等）。'
        },
        'webChat.replyTo':{
            kind: 'arg',
            type: 'object',
            desc: '可选。回复目标消息 descriptor（用于 send）。',
            schema: {
                id: 'string (optional)',
                textIncludes: 'string (optional)',
                nth: 'number (optional, when multiple matches)'
            }
        },
        'webChat.mention':{
            kind: 'arg',
            type: 'array<string>',
            desc: '可选。@提及的用户/角色（best-effort，具体格式由站点决定）。'
        },
        'webChat.sendMode':{
            kind: 'arg',
            type: 'enum',
            values: ['auto','enter','button'],
            desc: '可选。发送方式偏好：auto=自动判断；enter=回车发送；button=点击发送按钮。默认 auto。'
        },
        'webChat.dedupeKey':{
            kind: 'arg',
            type: 'string',
            desc: '可选。幂等去重键（用于重试时避免重复发送）。'
        },
        'webChat.query':{
            kind: 'arg',
            type: 'string',
            desc: '可选。会话内搜索关键词（用于 searchMessages）。'
        },
        'webChat.reaction':{
            kind: 'arg',
            type: 'string',
            desc: '可选。反应/表情（emoji 或名称），用于 react。'
        },
        'webChat.message':{
            kind: 'arg',
            type: 'string',
            desc: '可选。目标消息 descriptor（messageId 或可唯一定位的文本片段），用于 react 等。'
        },
        //webChat results:
        'webChat.result': {
            kind: 'result',
            desc: 'webChat 成功时的 value 结构（由 webChat.action 路由，best-effort）',
            done: {
                value: {
                    action: { type: 'string', desc: '本次执行的 webChat.action' },
                    session: { type: 'object', required: false, desc: '会话 descriptor（若适用）' },
                    items: { type: 'array<object>', required: false, desc: '会话列表或消息列表（best-effort）' },
                    cursor: { type: 'string', required: false, desc: '游标（用于继续拉取/等待回复，best-effort）' },
                    sent: { type: 'boolean', required: false, desc: 'send 是否已发送成功（best-effort）' },
                }
            }
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

        // ------------------------------------------------------------
        // results (规范 done.value 的结构；保持外层 {status,value,logs,meta} 不变)
        // - kind:'result' 不参与 find.must/find.prefer 的 has-cap 匹配，仅用于约束/文档/校验
        // - 以下返回结构尽量保持简洁，字段均为 best-effort（除非明确 required）
        'showMore.result': {
            kind: 'result',
            desc: 'showMore 成功时的 value 结构',
            done: {
                value: {
                    expanded: { type: 'boolean', desc: '是否已展开更多内容（best-effort）' },
                    newItems: { type: 'number', required: false, desc: '若用于列表扩展，本次新增条目数量（best-effort）' },
                }
            }
        },

        // env/ai capability placeholders（通常仅用于 has-cap；若被调用可返回 supported=true）
        'browser.headless.result': { kind: 'result', desc: 'browser.headless 返回占位', done: { value: { supported: { type: 'boolean', desc: '是否支持（固定 true）' } } } },
        'browser.devtools.result': { kind: 'result', desc: 'browser.devtools 返回占位', done: { value: { supported: { type: 'boolean', desc: '是否支持（固定 true）' } } } },
        'browser.profile.result': { kind: 'result', desc: 'browser.profile 返回占位', done: { value: { supported: { type: 'boolean', desc: '是否支持（固定 true）' } } } },
        'browser.cookies.result': { kind: 'result', desc: 'browser.cookies 返回占位', done: { value: { supported: { type: 'boolean', desc: '是否支持（固定 true）' } } } },
        'ai.query.result': { kind: 'result', desc: 'ai.query 返回占位', done: { value: { data: { type: 'any', desc: 'AI 查询结果（实现自定义）' } } } },
        'ai.extract.result': { kind: 'result', desc: 'ai.extract 返回占位', done: { value: { data: { type: 'any', desc: 'AI 提取结果（实现自定义）' } } } },
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

