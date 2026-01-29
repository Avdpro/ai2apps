const flow={
	"id": "compose_input",
	"start": "routeField",
	"steps": [
		{
			"id": "routeField",
			"desc": "根据 args.field 路由到不同输入目标（默认 content）",
			"action": {
				"type": "branch",
				"cases": [
					{ "when": { "op": "eq", "path": "field", "value": "title" }, "to": "clickTitle" },
					{ "when": { "op": "eq", "path": "field", "value": "subtitle" }, "to": "clickSubtitle" },
					{ "when": { "op": "eq", "path": "field", "value": "tag" }, "to": "clickTag" },
					{ "when": { "op": "eq", "path": "field", "value": "content" }, "to": "clickContent" }
				],
				"default": "clickContent"
			}
		},

		{
			"id": "clickTitle",
			"desc": "尝试聚焦标题输入框",
			"action": {
				"type": "click",
				"query": "标题输入框（Title input）。优先：placeholder/aria-label/name 含 title/标题；常见为 input 或 textarea，位于编辑器顶部"
			},
			"next": { "done": "inputTitle", "failed": "prepareTitleFallback", "skipped": "prepareTitleFallback", "timeout": "prepareTitleFallback" }
		},
		{
			"id": "inputTitle",
			"desc": "在标题框清空并输入 title 文本",
			"action": { "type": "input", "text": "${text}", "mode": "fill" },
			"next": { "done": "doneOk", "failed": "prepareTitleFallback", "skipped": "prepareTitleFallback", "timeout": "prepareTitleFallback" }
		},
		{
			"id": "prepareTitleFallback",
			"desc": "构造标题退化到正文时的文本（含分割行）",
			"action": {
				"type": "run_js",
				"scope": "agent",
				"code": "function(t){ t = (t==null?\"\":String(t)); if(!t.trim()) return \"\"; return \"========\\n\" + t + \"\\n========\\n\"; }",
				"args": ["${text}"]
			},
			"saveAs": "fallbackText",
			"next": { "done": "clickContentForTitleFallback", "failed": "askAssist", "skipped": "askAssist", "timeout": "askAssist" }
		},

		{
			"id": "clickSubtitle",
			"desc": "尝试聚焦副标题输入框",
			"action": {
				"type": "click",
				"query": "副标题输入框（Subtitle input）。优先：placeholder/aria-label/name 含 subtitle/副标题；常见为 input 或 textarea，通常在标题附近"
			},
			"next": { "done": "inputSubtitle", "failed": "prepareSubtitleFallback", "skipped": "prepareSubtitleFallback", "timeout": "prepareSubtitleFallback" }
		},
		{
			"id": "inputSubtitle",
			"desc": "在副标题框清空并输入 subtitle 文本",
			"action": { "type": "input", "text": "${text}", "mode": "fill" },
			"next": { "done": "doneOk", "failed": "prepareSubtitleFallback", "skipped": "prepareSubtitleFallback", "timeout": "prepareSubtitleFallback" }
		},
		{
			"id": "prepareSubtitleFallback",
			"desc": "构造副标题退化到正文时的文本",
			"action": {
				"type": "run_js",
				"scope": "agent",
				"code": "function(t){ t = (t==null?\"\":String(t)); if(!t.trim()) return \"\"; return \"\\n<\" + t + \">\\n\"; }",
				"args": ["${text}"]
			},
			"saveAs": "fallbackText",
			"next": { "done": "clickContentForFallback", "failed": "askAssist", "skipped": "askAssist", "timeout": "askAssist" }
		},

		{
			"id": "clickTag",
			"desc": "尝试聚焦标签输入框",
			"action": {
				"type": "click",
				"query": "标签输入框（Tags input）。优先：placeholder/aria-label/name 含 tag/tags/标签；或在“标签/Tags”区域内的输入框"
			},
			"next": { "done": "inputTag", "failed": "prepareTagFallback", "skipped": "prepareTagFallback", "timeout": "prepareTagFallback" }
		},
		{
			"id": "inputTag",
			"desc": "在标签框清空并输入 tag 文本",
			"action": { "type": "input", "text": "${text}", "mode": "fill" },
			"next": { "done": "doneOk", "failed": "prepareTagFallback", "skipped": "prepareTagFallback", "timeout": "prepareTagFallback" }
		},
		{
			"id": "prepareTagFallback",
			"desc": "构造标签退化到正文时的文本（原样追加）",
			"action": {
				"type": "run_js",
				"scope": "agent",
				"code": "function(t){ t = (t==null?\"\":String(t)); if(!t.trim()) return \"\"; return \"\\n\\n\" + t; }",
				"args": ["${text}"]
			},
			"saveAs": "fallbackText",
			"next": { "done": "clickContentForFallback", "failed": "askAssist", "skipped": "askAssist", "timeout": "askAssist" }
		},

		{
			"id": "clickContentForFallback",
			"desc": "退化路径：聚焦正文编辑器输入区域",
			"action": {
				"type": "click",
				"query": "正文/内容编辑器输入区域（Post body editor）。优先：contenteditable=true 的编辑区或主要 textarea，通常是页面最大输入区"
			},
			"next": { "done": "inputFallbackText", "failed": "askAssist", "skipped": "askAssist", "timeout": "askAssist" }
		},
		{
			"id": "inputFallbackText",
			"desc": "退化路径：把 fallbackText 粘贴到正文（不清空正文）",
			"action": { "type": "input", "text": "${vars.fallbackText}", "mode": "paste" },
			"next": { "done": "doneOk", "failed": "askAssist", "skipped": "askAssist", "timeout": "askAssist" }
		},
		{
			"id": "clickContentForTitleFallback",
			"desc": "标题退化路径：聚焦正文编辑器输入区域（准备清空后写入标题）",
			"action": {
				"type": "click",
				"query": "正文/内容编辑器输入区域（Post body editor）。优先：contenteditable=true 的编辑区或主要 textarea，通常是页面最大输入区"
			},
			"next": { "done": "inputFallbackTitleText", "failed": "askAssist", "skipped": "askAssist", "timeout": "askAssist" }
		},

		{
			"id": "inputFallbackTitleText",
			"desc": "标题退化路径：清空正文并粘贴 fallbackText（标题专用）",
			"action": { "type": "input", "text": "${vars.fallbackText}", "mode": "paste", "clear": true },
			"next": { "done": "doneOk", "failed": "askAssist", "skipped": "askAssist", "timeout": "askAssist" }
		},
		{
			"id": "clickContent",
			"desc": "聚焦正文编辑器输入区域",
			"action": {
				"type": "click",
				"query": "正文/内容编辑器输入区域（Post body editor）。优先：contenteditable=true 的编辑区或主要 textarea，通常是页面最大输入区"
			},
			"next": { "done": "inputContent", "failed": "askAssist", "skipped": "askAssist", "timeout": "askAssist" }
		},
		{
			"id": "inputContent",
			"desc": "向正文粘贴输入（长文本友好）",
			"action": { "type": "input", "text": "${text}", "mode": "paste" },
			"next": { "done": "doneOk", "failed": "askAssist", "skipped": "askAssist", "timeout": "askAssist" }
		},

		{
			"id": "askAssist",
			"desc": "无法自动定位输入框，请用户介入定位后继续",
			"action": {
				"type": "ask_assist",
				"reason": "我没能可靠定位到要输入的区域（field=${field}）。请你手动点击正确的输入框（标题/副标题/标签/正文任一你希望的目标），然后继续。我会把内容以“粘贴”方式输入到当前焦点。"
			},
			"next": { "done": "buildFinalTextAfterAssist", "failed": "abortCannotInput", "skipped": "abortCannotInput", "timeout": "abortCannotInput" }
		},
		{
			"id": "buildFinalTextAfterAssist",
			"desc": "人工介入后：决定要输入的最终文本（优先 fallbackText，否则 text）",
			"action": {
				"type": "run_js",
				"scope": "agent",
				"code": "function(text,fallback){ fallback = (fallback==null?\"\":String(fallback)); text = (text==null?\"\":String(text)); return fallback.trim()? fallback : text; }",
				"args": ["${text}", "${vars.fallbackText}"]
			},
			"saveAs": "finalText",
			"next": { "done": "inputFinalTextAfterAssist", "failed": "abortCannotInput", "skipped": "abortCannotInput", "timeout": "abortCannotInput" }
		},
		{
			"id": "inputFinalTextAfterAssist",
			"desc": "人工介入后：向当前焦点粘贴输入最终文本",
			"action": { "type": "input", "text": "${vars.finalText}", "mode": "paste" },
			"next": { "done": "doneOk", "failed": "abortCannotInput", "skipped": "abortCannotInput", "timeout": "abortCannotInput" }
		},

		{
			"id": "abortCannotInput",
			"desc": "仍无法完成输入则放弃",
			"action": {
				"type": "abort",
				"reason": "多次尝试后仍无法定位或写入目标输入框；且用户介入后仍未能完成输入。"
			}
		},
		{
			"id": "doneOk",
			"desc": "完成 compose.input",
			"action": {
				"type": "done",
				"reason": "已将文本写入目标输入区域（或按规则退化到正文输入）。",
				"conclusion": "compose.input 完成"
			}
		}
	],
	"args": {
		"field": { "type": "string", "required": false, "desc": "输入目标：title/content/tag/subtitle，默认 content" },
		"text": { "type": "string", "required": true, "desc": "要输入的文本内容" }
	},
	"vars": {
		"fallbackText": { "type": "string", "desc": "当 title/subtitle/tag 无法定位时，退化为写入正文的文本（title 含分割行）" },
		"finalText": { "type": "string", "desc": "用户介入后要粘贴到焦点的最终文本（优先 fallbackText）" }
	}
};

export default flow;
