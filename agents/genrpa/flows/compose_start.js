const flow={
	"id": "compose_start_generic",
	"start": "clearBlockers",
	"args": {
		"composeTypeHint": {
			"type": "string",
			"required": false,
			"desc": "可选提示：post/article/email/message 等，仅用于让 query 更贴近当前目标（不影响通用性）"
		}
	},
	"steps": [
		{
			"id": "clearBlockers",
			"desc": "清理可能阻挡操作的弹窗/遮罩/插屏等（第一步）",
			"action": {
				"type": "invoke",
				"find": {
					"kind": "rpa",
					"must": ["blockers.clear"],
					"prefer": ["blockers.check"],
					"filter": [
						{ "key": "domain", "value": "*" }
					],
					"rank": "cost"
				},
				"args": {
					"blockers.clear": true
				},
				"timeoutMs": 15000,
				"onError": "return"
			},
			"next": "ensureLogin"
		},
		{
			"id": "ensureLogin",
			"desc": "确保已登录（未登录则执行登录流程/需要用户介入）",
			"action": {
				"type": "invoke",
				"find": {
					"kind": "rpa",
					"must": ["login.ensure"],
					"prefer": ["login.check", "login.cookie", "login.interactive"],
					"filter": [
						{ "key": "domain", "value": "*" }
					],
					"rank": "cost"
				},
				"args": {
					"login.ensure": true
				},
				"timeoutMs": 60000
			},
			"next": {
				"done": "checkComposeReady",
				"failed": "assistLogin",
				"timeout": "assistLogin"
			}
		},
		{
			"id": "assistLogin",
			"desc": "需要用户完成登录/验证码/人机验证后再继续",
			"action": {
				"type": "askAssist",
				"reason": "请在当前站点完成登录（如输入账号密码/验证码/扫码/人机验证），完成后回到页面并继续。",
				"waitUserAction": true
			},
			"next": "checkComposeReady"
		},
		{
			"id": "checkComposeReady",
			"desc": "探测：当前是否已经处于可直接发布的撰写界面（无需点击“新建/撰写”入口）",
			"action": {
				"type": "selector",
				"state": "visible",
				"scope": "current",
				"query": "可见的撰写编辑器/输入区（用于发布内容），通常是 textarea 或 contenteditable 区域，并且附近常出现“发布/发送/下一步/Submit/Post/Publish/Send”等按钮；优先匹配主要编辑区域而非搜索框"
			},
			"next": {
				"done": "doneAlreadyReady",
				"failed": "clickComposeEntry"
			}
		},
		{
			"id": "clickComposeEntry",
			"desc": "若未在撰写界面：尝试点击“新建/撰写/发帖/写文章/Compose/Write”入口打开编辑器",
			"action": {
				"type": "click",
				"intent": "open",
				"query": "用于开始撰写/新建内容的入口按钮或链接（例如：发帖/写点什么/新建/撰写/写文章/Compose/New post/New message/创建/发布；避免点击“发布/发送”最终提交按钮）"
			},
			"next": {
				"done": "waitComposeEditor",
				"failed": "assistOpenCompose",
				"timeout": "assistOpenCompose"
			}
		},
		{
			"id": "waitComposeEditor",
			"desc": "等待撰写编辑器/输入区出现（compose 已启动即可，不要求填写内容）",
			"action": {
				"type": "wait",
				"state": "visible",
				"scope": "current",
				"timeoutMs": 5000,
				"pollMs": 150,
				"query": "可见的撰写编辑器/输入区（textarea 或 contenteditable），用于输入正文；通常与“发布/发送/下一步”按钮同处一个面板/弹窗/页面"
			},
			"next": {
				"done": "doneOpened",
				"failed": "assistOpenCompose",
				"timeout": "assistOpenCompose"
			}
		},
		{
			"id": "assistOpenCompose",
			"desc": "无法自动打开撰写界面时请求用户介入",
			"action": {
				"type": "askAssist",
				"reason": "我没能自动打开撰写界面。请你手动点击站点的“新建/撰写/发帖/Compose/Write”等入口打开编辑器（不要发布），打开后继续。",
				"waitUserAction": true
			},
			"next": "checkComposeReady"
		},
		{
			"id": "doneAlreadyReady",
			"desc": "已在撰写界面（可直接发布），无需点击入口",
			"action": {
				"type": "done",
				"reason": "检测到当前页面已经处于撰写/编辑状态。",
				"conclusion": "compose 已启动（已在编辑器界面）。"
			}
		},
		{
			"id": "doneOpened",
			"desc": "已成功打开撰写界面",
			"action": {
				"type": "done",
				"reason": "已打开撰写编辑器/输入区。",
				"conclusion": "compose 已启动（编辑器已打开）。"
			}
		}
	]
}

export default flow;