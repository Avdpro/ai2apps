/**
 * 返回“合并公共字段后的”某个 item 类型 schema（JSON）。
 *
 * @param {string} type  item 类型；若不存在则默认使用 "article"
 * @param {null | string[]} fields  若提供，则这些字段 required=true，其它字段 required=false（覆盖默认 required）
 * @returns {{code:string,text:string,desc:string,fields:Object<string,{type:string,required:boolean,desc:string}>}}
 */
function getMergedItemSchema(type = "article", fields = null) {
	const BASE_FIELDS = {
		id: { type: "string", required: false, desc: "站内唯一标识（有就填，没有可空）" },
		url: { type: "url", required: false, desc: "条目详情页/跳转链接（尽量绝对链接）" },
		title: { type: "string", required: true, desc: "条目主标题/主文本（优先取可点击标题）" },
		summary: { type: "string", required: false, desc: "摘要/预览文本（列表页能看到的那部分）" },
		source: { type: "string", required: false, desc: "来源站点/栏目/频道（可选）" },
		author: { type: "string", required: false, desc: "作者/发布者/发件人等（按类型语义）" },
		publishedAt: { type: "datetime", required: false, desc: "发布时间（ISO8601，如可见）" },
		updatedAt: { type: "datetime", required: false, desc: "更新时间（ISO8601，如可见）" },
		position: { type: "number", required: false, desc: "在列表中的顺序，从1开始（如可推断）" },
		badges: { type: "list<string>", required: false, desc: "标签/角标，如置顶/广告/已读/精选" }
	};

	const ITEM_TYPES = {
		search_result: {
			code: "search_result",
			text: "搜索结果",
			desc: "搜索引擎或站内搜索的结果条目列表，通常包含标题、摘要、来源与跳转链接。",
			fields: {
				displayUrl: { type: "string", required: false, desc: "展示用的短链接/域名路径（不要求绝对URL）" },
				cardImageUrl: { type: "url", required: false, desc: "搜索结果卡片图/缩略图的链接（如有）" },
				siteName: { type: "string", required: false, desc: "站点名称（如有）" },
				faviconUrl: { type: "url", required: false, desc: "站点 favicon 链接（如可见）" },
				sitelinks: { type: "list<object>", required: false, desc: "子链接列表（如“站点链接/相关链接”）" },
				resultRank: { type: "number", required: false, desc: "搜索结果排名（如页面直接标注/可推断）" }
			}
		},

		article: {
			code: "article",
			text: "文章",
			desc: "内容型条目列表，如资讯、博客、专栏等。news 可视为 article 的一种形态。",
			fields: {
				articleKind: { type: "string", required: false, desc: "文章形态（news/blog/column/press 等）" },
				category: { type: "string", required: false, desc: "分类/栏目（如科技/财经/专栏名）" },
				coverImageUrl: { type: "url", required: false, desc: "封面图链接（列表卡片常见）" },
				readingTimeMin: { type: "number", required: false, desc: "预计阅读时长（分钟）" },
				isBreaking: { type: "boolean", required: false, desc: "是否“突发/快讯”（新闻常见）" },
				region: { type: "string", required: false, desc: "地区标签（如中国/全球/东南亚）" }
			}
		},

		post: {
			code: "post",
			text: "帖子",
			desc: "论坛/社区/社交平台的内容条目，可能是主题帖或动态更新，通常含作者、时间与互动数据。",
			fields: {
				postKind: { type: "string", required: false, desc: "帖子形态（social/forum/announcement 等）" },
				content: { type: "string", required: false, desc: "正文/摘要（社交动态常有；论坛主题可能只有标题）" },
				likeCount: { type: "number", required: false, desc: "点赞数（如有）" },
				commentCount: { type: "number", required: false, desc: "评论数（如有）" },
				replyCount: { type: "number", required: false, desc: "回复数（论坛主题常见）" },
				shareCount: { type: "number", required: false, desc: "分享/转发数（如有）" },
				viewCount: { type: "number", required: false, desc: "浏览/阅读量（如有）" },
				lastReplyAt: { type: "datetime", required: false, desc: "最后回复时间（论坛常见）" },
				lastReplier: { type: "string", required: false, desc: "最后回复者（论坛常见）" },
				isPinned: { type: "boolean", required: false, desc: "是否置顶" },
				isRepost: { type: "boolean", required: false, desc: "是否转发/引用他人内容" },
				originalUrl: { type: "url", required: false, desc: "原帖链接（转发/引用时）" },
				media: { type: "list<object>", required: false, desc: "媒体附件（图片/视频等，如有）" }
			}
		},

		comment: {
			code: "comment",
			text: "评论",
			desc: "评论列表项，可能存在楼中楼/线程结构，通常包含评论者、内容、时间与点赞数。",
			fields: {
				content: { type: "string", required: true, desc: "评论正文（核心字段）" },
				parentId: { type: "string", required: false, desc: "父评论ID/所属楼层ID（楼中楼时）" },
				likeCount: { type: "number", required: false, desc: "点赞数" },
				replyCount: { type: "number", required: false, desc: "回复数" },
				depth: { type: "number", required: false, desc: "层级深度（按你的约定：主评论=0或1）" },
				floorNo: { type: "number", required: false, desc: "楼层号（如“#23”）" }
			}
		},

		qa_item: {
			code: "qa_item",
			text: "问答条目",
			desc: "问答网站的问题或回答条目。通过 qaKind 区分 question/answer。",
			fields: {
				qaKind: { type: "string", required: true, desc: "类型（question/answer）" },
				content: { type: "string", required: false, desc: "内容摘要（answer 常见；question 也可能有描述）" },
				tags: { type: "list<string>", required: false, desc: "标签（问题常见）" },
				answerCount: { type: "number", required: false, desc: "回答数（问题常见）" },
				followerCount: { type: "number", required: false, desc: "关注/收藏数（问题常见）" },
				voteCount: { type: "number", required: false, desc: "赞同/投票数（回答常见）" },
				commentCount: { type: "number", required: false, desc: "评论数（回答常见）" },
				isAccepted: { type: "boolean", required: false, desc: "是否被采纳（回答常见）" },
				questionId: { type: "string", required: false, desc: "所属问题ID（回答时如可获得）" },
				status: { type: "string", required: false, desc: "状态（如已解决/悬赏中/关闭）" }
			}
		},

		message: {
			code: "message",
			text: "消息",
			desc: "站内信/聊天/邮件相关列表项。通过 messageKind 区分 email/thread/chat_message。",
			fields: {
				messageKind: { type: "string", required: true, desc: "类型（email/thread/chat_message）" },
				from: { type: "string", required: false, desc: "发件人/发送者（email/chat_message 常见）" },
				to: { type: "list<string>", required: false, desc: "收件人（email 常见，列表页可能缺失）" },
				cc: { type: "list<string>", required: false, desc: "抄送（email 有则抓）" },
				subject: { type: "string", required: false, desc: "主题（email 常见）" },
				snippet: { type: "string", required: false, desc: "摘要/预览（email/thread 常见）" },
				participants: { type: "list<string>", required: false, desc: "参与者列表（thread 常见）" },
				lastMessage: { type: "string", required: false, desc: "最后一条消息摘要（thread 常见）" },
				unreadCount: { type: "number", required: false, desc: "未读数（thread 常见）" },
				isUnread: { type: "boolean", required: false, desc: "是否未读（email 常见）" },
				sentAt: { type: "datetime", required: false, desc: "发送时间（chat_message 常见）" },
				threadId: { type: "string", required: false, desc: "会话/线程ID（email/thread 常见）" },
				hasAttachment: { type: "boolean", required: false, desc: "是否含附件（email 常见）" },
				attachments: { type: "list<object>", required: false, desc: "附件列表（chat_message 常见）" },
				folder: { type: "string", required: false, desc: "所在文件夹/标签（email 常见：收件箱/已发送等）" }
			}
		},

		product: {
			code: "product",
			text: "商品",
			desc: "电商商品列表项，通常包含价格、促销、评价与库存等信息。",
			fields: {
				price: { type: "currency", required: false, desc: "当前价" },
				listPrice: { type: "currency", required: false, desc: "原价/划线价（如有）" },
				currency: { type: "string", required: false, desc: "币种（CNY/THB/USD 等）" },
				discountText: { type: "string", required: false, desc: "促销文案（如“满200减50”/“限时折扣”）" },
				rating: { type: "number", required: false, desc: "评分（如 4.8）" },
				reviewCount: { type: "number", required: false, desc: "评价数" },
				stockStatus: { type: "string", required: false, desc: "库存/售卖状态（有货/无货/预售）" },
				seller: { type: "string", required: false, desc: "商家/店铺名称（如可见）" },
				shippingInfo: { type: "string", required: false, desc: "配送信息（包邮/到货时间等）" },
				sku: { type: "string", required: false, desc: "SKU/商品编号（如可见）" },
				thumbnailUrl: { type: "url", required: false, desc: "缩略图链接（如可见）" }
			}
		},

		place: {
			code: "place",
			text: "地点",
			desc: "地点/POI 列表项（地图结果、导览点等），通常包含地址、评分、距离与营业状态。",
			fields: {
				category: { type: "string", required: false, desc: "类别（餐厅/景点/商场等）" },
				address: { type: "string", required: false, desc: "地址" },
				distanceKm: { type: "number", required: false, desc: "距离（公里，如可见）" },
				rating: { type: "number", required: false, desc: "评分" },
				reviewCount: { type: "number", required: false, desc: "评价数" },
				openNow: { type: "boolean", required: false, desc: "是否营业/开放中" },
				openHoursText: { type: "string", required: false, desc: "营业时间展示文本（如“10:00-22:00”）" },
				phone: { type: "string", required: false, desc: "电话（如可见）" },
				geo: { type: "object", required: false, desc: "坐标（如 {lat, lon}）" },
				priceLevel: { type: "string", required: false, desc: "价格水平（如 $$/人均）" }
			}
		},

		event: {
			code: "event",
			text: "活动",
			desc: "活动/会议/演出等列表项，通常包含时间、地点、主办方与报名/票务状态。",
			fields: {
				startAt: { type: "datetime", required: true, desc: "开始时间（核心字段）" },
				endAt: { type: "datetime", required: false, desc: "结束时间（如有）" },
				location: { type: "string", required: false, desc: "地点/线上方式描述" },
				organizer: { type: "string", required: false, desc: "主办方/组织者（如可见）" },
				price: { type: "currency", required: false, desc: "票价/报名费（如有）" },
				currency: { type: "string", required: false, desc: "币种" },
				status: { type: "string", required: false, desc: "状态（报名中/已满/已结束/取消）" },
				onlineUrl: { type: "url", required: false, desc: "线上入口链接（如可见）" }
			}
		},

		task: {
			code: "task",
			text: "任务",
			desc: "任务/待办列表项，通常包含状态、优先级、负责人、截止时间与标签/项目归属。",
			fields: {
				status: { type: "string", required: false, desc: "状态（未开始/进行中/已完成/阻塞等）" },
				isDone: { type: "boolean", required: false, desc: "是否完成（轻量待办常见）" },
				priority: { type: "string", required: false, desc: "优先级（高/中/低等）" },
				dueAt: { type: "datetime", required: false, desc: "截止时间" },
				assignee: { type: "string", required: false, desc: "负责人/指派对象" },
				project: { type: "string", required: false, desc: "所属项目/看板/清单" },
				tags: { type: "list<string>", required: false, desc: "标签" }
			}
		},

		transaction: {
			code: "transaction",
			text: "交易与单据",
			desc: "交易流水/账单/发票/订单/物流等可追踪条目。通过 txnKind 区分子类型。",
			fields: {
				txnKind: { type: "string", required: true, desc: "子类型（transaction/bill/invoice/order/shipment）" },
				refNo: { type: "string", required: false, desc: "通用编号（交易号/账单号/发票号/订单号/运单号等）" },
				amount: { type: "currency", required: false, desc: "金额（适用于 transaction/bill/invoice/order）" },
				currency: { type: "string", required: false, desc: "币种" },
				direction: { type: "string", required: false, desc: "方向（收入/支出，交易流水常见）" },
				counterparty: { type: "string", required: false, desc: "对方（商户/个人/供应商等）" },
				status: { type: "string", required: false, desc: "状态（成功/失败/处理中；或 已付/未付；或 待发/已完成；或 派送中/已签收）" },
				method: { type: "string", required: false, desc: "方式（卡/转账/钱包；或 配送方式等）" },
				period: { type: "string", required: false, desc: "账期（账单常见，如 2025-12）" },
				dueDate: { type: "datetime", required: false, desc: "到期/截止时间（账单/发票常见）" },
				paidAt: { type: "datetime", required: false, desc: "支付时间（已付时）" },
				carrier: { type: "string", required: false, desc: "承运商/快递公司（shipment 常见）" },
				estimatedDeliveryAt: { type: "datetime", required: false, desc: "预计送达时间（shipment 常见）" },
				lastEvent: { type: "string", required: false, desc: "最新节点描述（shipment 常见）" },
				lastEventAt: { type: "datetime", required: false, desc: "最新节点时间（shipment 常见）" }
			}
		},

		case: {
			code: "case",
			text: "事项与工单",
			desc: "可跟踪事项（客服工单/支持案件/Issue/Bug 等）。通过 caseKind 区分子类型。",
			fields: {
				caseKind: { type: "string", required: true, desc: "子类型（support/complaint/issue/bug）" },
				caseNo: { type: "string", required: false, desc: "编号（如 #123 / TKT-9）" },
				state: { type: "string", required: false, desc: "状态（open/closed；或 新建/处理中/已解决等）" },
				priority: { type: "string", required: false, desc: "优先级（高/中/低等）" },
				severity: { type: "string", required: false, desc: "严重程度（缺陷常见：S1/S2/高/中/低）" },
				assignee: { type: "string", required: false, desc: "负责人/处理人" },
				labels: { type: "list<string>", required: false, desc: "标签" },
				milestone: { type: "string", required: false, desc: "里程碑（如有）" },
				commentCount: { type: "number", required: false, desc: "评论/回复数（如有）" },
				channel: { type: "string", required: false, desc: "渠道（电话/邮件/在线/门店等，支持案件常见）" },
				lastReplyAt: { type: "datetime", required: false, desc: "最近回复/更新动作时间（如可见）" }
			}
		},

		asset: {
			code: "asset",
			text: "文件与文档",
			desc: "文件/文档/知识库页面等资源条目。通过 assetKind 区分 file/document/page 等。",
			fields: {
				assetKind: { type: "string", required: true, desc: "子类型（file/document/page/pdf/sheet 等）" },
				fileType: { type: "string", required: false, desc: "文件类型/扩展名（如 pdf/png/docx）" },
				docType: { type: "string", required: false, desc: "文档类型（页面/表格/演示等）" },
				sizeBytes: { type: "number", required: false, desc: "大小（字节，如可得）" },
				sizeText: { type: "string", required: false, desc: "展示大小（如“1.2 MB”）" },
				downloadUrl: { type: "url", required: false, desc: "下载链接（如列表可直接下载）" },
				path: { type: "string", required: false, desc: "路径/层级（如知识库目录/网盘目录）" },
				pageCount: { type: "number", required: false, desc: "页数（PDF/文档可见时）" },
				owner: { type: "string", required: false, desc: "所有者/共享者（如可见）" },
				thumbnailUrl: { type: "url", required: false, desc: "缩略图/预览图链接（如有）" }
			}
		},

		changelog: {
			code: "changelog",
			text: "更新记录",
			desc: "版本更新/变更记录条目，通常包含版本号、日期与变更要点。",
			fields: {
				productName: { type: "string", required: false, desc: "产品/项目名称（如页面包含）" },
				version: { type: "string", required: false, desc: "版本号（如 v1.2.3）" },
				changeType: { type: "string", required: false, desc: "变更类型（新增/修复/优化/破坏性变更）" },
				changes: { type: "list<string>", required: false, desc: "变更要点列表（列表页可见则提取）" },
				impact: { type: "string", required: false, desc: "影响说明（如需要迁移/Breaking Changes）" }
			}
		}
	};

	const clone = (obj) => JSON.parse(JSON.stringify(obj));

	const pickedType = ITEM_TYPES[type] || ITEM_TYPES.article;

	// 合并 fields：公共字段 + 类型独有字段（独有字段同名会覆盖公共字段）
	const mergedFields = { ...clone(BASE_FIELDS), ...clone(pickedType.fields || {}) };

	// 若指定 fields，则：指定的 required=true，其它 required=false（覆盖默认 required）
	if (Array.isArray(fields)) {
		const set = new Set(fields);
		for (const k of Object.keys(mergedFields)) {
			mergedFields[k].required = set.has(k);
		}

		// 若用户指定了未声明字段：补一个兜底定义，避免丢字段
		for (const k of set) {
			if (!(k in mergedFields)) {
				mergedFields[k] = {
					type: "string",
					required: true,
					desc: "用户指定字段（原类型未声明，已用 string 兜底）"
				};
			}
		}
	}

	return {
		code: pickedType.code,
		text: pickedType.text,
		desc: pickedType.desc,
		fields: mergedFields
	};
}

/**
 * 基于“若干关键字段”的模糊比较，判断两个 item 是否可能重复。
 * - 会自动排除一些不适合作为去重依据的字段（可通过 opts.ignoreFields 覆盖/追加）
 * - 优先使用强唯一字段：id/refNo/hash/...、再用 url、最后用文本相似度 + 辅助字段（作者/时间/金额）
 *
 * @param {object} a
 * @param {object} b
 * @param {object} [opts]
 * @param {string[]} [opts.ignoreFields]       额外忽略字段
 * @param {string[]} [opts.idFields]           强唯一字段名列表（任意一个相等即可判重）
 * @param {string}   [opts.urlField]           URL 字段名
 * @param {string[]} [opts.primaryTextFields]  主文本字段（用于主要相似度：title/subject/content）
 * @param {string[]} [opts.secondaryTextFields]辅助文本字段（作者/来源/对方）
 * @param {string[]} [opts.dateFields]         时间字段（用于近似）
 * @param {number}   [opts.dateToleranceMs]    时间容忍度（默认 36 小时）
 * @param {number}   [opts.threshold]          判重阈值（默认 0.86）
 * @returns {boolean}
 */
function isDuplicateItem(a, b, opts = {}) {
	if (!a || !b || typeof a !== "object" || typeof b !== "object") return false;

	const DEFAULT_IGNORE = new Set([
		// UI/排序/装饰类
		"position",
		"badges",
		// 列表预览类通常噪声很大（你也可以改成不忽略）
		"summary",
		"snippet",
		"lastMessage",
		// 图片/附件/站点链接等（弱证据，且容易变化）
		"media",
		"attachments",
		"sitelinks",
		"faviconUrl",
		"cardImageUrl",
		"thumbnailUrl",
		// 更新字段易变（可保留 publishedAt）
		"updatedAt"
	]);

	const ignoreFields = new Set([
		...DEFAULT_IGNORE,
		...(Array.isArray(opts.ignoreFields) ? opts.ignoreFields : [])
	]);

	const idFields = Array.isArray(opts.idFields)
	? opts.idFields
	: [
		"id",
		"refNo",
		"caseNo",
		"orderNo",
		"invoiceNo",
		"trackingNo",
		"txnId",
		"hash",
		"threadId",
		"version"
	];

	const urlField = opts.urlField || "url";

	const primaryTextFields = Array.isArray(opts.primaryTextFields)
	? opts.primaryTextFields
	: ["title", "subject", "content"];

	const secondaryTextFields = Array.isArray(opts.secondaryTextFields)
	? opts.secondaryTextFields
	: ["author", "from", "counterparty", "siteName", "source", "organizer", "seller"];

	const dateFields = Array.isArray(opts.dateFields)
	? opts.dateFields
	: ["publishedAt", "sentAt", "startAt", "occurredAt", "createdAt"];

	const dateToleranceMs =
		  typeof opts.dateToleranceMs === "number" ? opts.dateToleranceMs : 36 * 60 * 60 * 1000;

	const threshold = typeof opts.threshold === "number" ? opts.threshold : 0.86;

	// ---------- helpers ----------
	const isNonEmpty = (v) => v !== null && v !== undefined && String(v).trim() !== "";

	const pickFirst = (obj, keys) => {
		for (const k of keys) {
			const v = obj?.[k];
			if (typeof v === "string" && v.trim()) return v;
		}
		return "";
	};

	const normalizeText = (s) =>
	String(s || "")
	.toLowerCase()
	.replace(/[\u200B-\u200D\uFEFF]/g, "") // zero-width
	.replace(/https?:\/\/\S+/g, " ") // 去掉 URL 噪声
	.replace(/[^\p{L}\p{N}]+/gu, " ") // 非字母数字 -> 空格（含中文）
	.replace(/\s+/g, " ")
	.trim();

	// Dice coefficient over bigrams（对短文本比 token-jaccard 更稳）
	const diceSim = (s1, s2) => {
		const a = normalizeText(s1);
		const b = normalizeText(s2);
		if (!a || !b) return 0;
		if (a === b) return 1;
		if (a.length < 2 || b.length < 2) return a === b ? 1 : 0;

		const bigrams = (s) => {
			const m = new Map();
			for (let i = 0; i < s.length - 1; i++) {
				const bg = s.slice(i, i + 2);
				m.set(bg, (m.get(bg) || 0) + 1);
			}
			return m;
		};

		const A = bigrams(a);
		const B = bigrams(b);
		let inter = 0;
		let sizeA = 0;
		let sizeB = 0;

		for (const [, c] of A) sizeA += c;
		for (const [, c] of B) sizeB += c;

		for (const [bg, cA] of A) {
			const cB = B.get(bg) || 0;
			inter += Math.min(cA, cB);
		}
		return (2 * inter) / (sizeA + sizeB);
	};

	const normalizeUrl = (u) => {
		try {
			const url = new URL(String(u));
			url.hash = "";

			// 去常见追踪参数
			const drop = new Set([
				"utm_source",
				"utm_medium",
				"utm_campaign",
				"utm_term",
				"utm_content",
				"utm_id",
				"gclid",
				"fbclid",
				"yclid",
				"mc_cid",
				"mc_eid"
			]);
			for (const k of [...url.searchParams.keys()]) {
				if (drop.has(k) || k.startsWith("utm_")) url.searchParams.delete(k);
			}

			// 统一 pathname 尾部 /
			url.pathname = url.pathname.replace(/\/+$/, "");
			// 默认端口去掉
			if ((url.protocol === "http:" && url.port === "80") || (url.protocol === "https:" && url.port === "443")) {
				url.port = "";
			}
			return url.toString();
		} catch {
			return "";
		}
	};

	const parseDate = (v) => {
		if (!isNonEmpty(v)) return null;
		const d = new Date(String(v));
		return Number.isFinite(d.getTime()) ? d : null;
	};

	// ---------- 1) 强唯一字段：任一命中直接判重 ----------
	for (const k of idFields) {
		if (ignoreFields.has(k)) continue;
		const va = a[k];
		const vb = b[k];
		if (isNonEmpty(va) && isNonEmpty(vb) && String(va).trim() === String(vb).trim()) {
			return true;
		}
	}

	// ---------- 2) URL：规范化后相同直接判重 ----------
	const ua = a[urlField];
	const ub = b[urlField];
	if (isNonEmpty(ua) && isNonEmpty(ub)) {
		const nua = normalizeUrl(ua);
		const nub = normalizeUrl(ub);
		if (nua && nub && nua === nub) return true;
	}

	// ---------- 3) 模糊相似度：主文本 + 辅助文本 + 时间 + 金额 ----------
	const primaryA = pickFirst(a, primaryTextFields);
	const primaryB = pickFirst(b, primaryTextFields);
	const primarySim = diceSim(primaryA, primaryB);

	const secondaryA = pickFirst(a, secondaryTextFields);
	const secondaryB = pickFirst(b, secondaryTextFields);
	const secondarySim = secondaryA && secondaryB ? diceSim(secondaryA, secondaryB) : 0;

	// 时间：找任意一个同时存在的时间字段做对比
	let dateSim = 0;
	for (const k of dateFields) {
		if (ignoreFields.has(k)) continue;
		const da = parseDate(a[k]);
		const db = parseDate(b[k]);
		if (da && db) {
			const diff = Math.abs(da.getTime() - db.getTime());
			dateSim = Math.max(0, 1 - diff / dateToleranceMs);
			break;
		}
	}

	// 金额：若两边都有 amount/currency（或 price），可提供额外证据
	const amountKeys = ["amount", "price"];
	const getNumber = (v) => {
		if (typeof v === "number" && Number.isFinite(v)) return v;
		if (typeof v === "string") {
			const n = Number(v.replace(/[, ]+/g, "").replace(/[^\d.\-]/g, ""));
			return Number.isFinite(n) ? n : null;
		}
		return null;
	};
	let amountSim = 0;
	for (const k of amountKeys) {
		if (ignoreFields.has(k)) continue;
		const na = getNumber(a[k]);
		const nb = getNumber(b[k]);
		if (na !== null && nb !== null) {
			if (na === nb) amountSim = 1;
			else {
				const denom = Math.max(1, Math.abs(na), Math.abs(nb));
				const rel = Math.abs(na - nb) / denom;
				amountSim = rel <= 0.01 ? 0.95 : rel <= 0.03 ? 0.85 : 0;
			}
			break;
		}
	}

	// 动态权重：主文本最重要；其它只在存在时参与
	const parts = [];
	parts.push({ w: 0.68, v: primarySim });

	if (secondaryA && secondaryB) parts.push({ w: 0.12, v: secondarySim });
	if (dateSim > 0) parts.push({ w: 0.10, v: dateSim });
	if (amountSim > 0) parts.push({ w: 0.10, v: amountSim });

	// 归一化权重（避免缺字段时分数过低）
	const wSum = parts.reduce((s, p) => s + p.w, 0);
	const score = wSum > 0 ? parts.reduce((s, p) => s + p.w * p.v, 0) / wSum : 0;

	// 额外硬规则：主文本非常像，并且（作者像 or 时间接近）也判重
	const hard =
		  primarySim >= 0.93 && ((secondaryA && secondaryB && secondarySim >= 0.70) || dateSim >= 0.85);

	return hard || score >= threshold;
}

/**
 * 把 arrB 中的元素“去重后”合并进 arrA（原地修改 arrA），并返回 arrA。
 * - 去重依据：isDuplicateItem（你上条已有）
 * - 默认：只要在 arrA 中找到任意一个重复项，就不加入
 *
 * @template T extends object
 * @param {T[]} arrA
 * @param {T[]} arrB
 * @param {object} [opts]
 * @param {(a:T,b:T,opts?:any)=>boolean} [opts.isDup]  自定义判重函数（默认 isDuplicateItem）
 * @param {any} [opts.dupOpts]                         传给判重函数的 opts
 * @param {boolean} [opts.mutateA]                     是否原地修改 arrA（默认 true）
 * @returns {T[]}
 */
function mergeItemsDedup(arrA, arrB, opts = {}) {
	const isDup = typeof opts.isDup === "function" ? opts.isDup : isDuplicateItem;
	const dupOpts = opts.dupOpts || {};
	const mutateA = opts.mutateA !== false;

	const base = Array.isArray(arrA) ? (mutateA ? arrA : arrA.slice()) : [];
	const add = Array.isArray(arrB) ? arrB : [];

	if (add.length === 0) return base;
	if (base.length === 0) {
		// 直接拷贝/追加
		for (const it of add) base.push(it);
		return base;
	}

	outer: for (const itemB of add) {
		if (!itemB || typeof itemB !== "object") continue;

		for (let i = 0; i < base.length; i++) {
			const itemA = base[i];
			if (!itemA || typeof itemA !== "object") continue;

			if (isDup(itemA, itemB, dupOpts)) {
				continue outer; // 找到重复：不加入
			}
		}

		base.push(itemB); // 未找到重复：加入
	}

	return base;
}

export default getMergedItemSchema;
export {getMergedItemSchema,isDuplicateItem,mergeItemsDedup};


