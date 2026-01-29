const flow={
	"id": "compose_publish",
	"start": "routeVisibility",
	"args": {
		"visibility": {
			"type": "string",
			"required": false,
			"desc": "发布可见范围（public/draft/private/fansOnly/friendsOnly）。可选；若设置失败仍继续发布。"
		}
	},
	"steps": [
		{
			"id": "routeVisibility",
			"desc": "若提供 visibility，则尝试调用子能力设置可见性（失败也继续发布）",
			"action": {
				"type": "branch",
				"cases": [
					{ "when": { "op": "exists", "path": "visibility" }, "to": "invokeSetVisibility" }
				],
				"default": "clickPublish"
			}
		},
		{
			"id": "invokeSetVisibility",
			"desc": "调用子能力尝试设置可见性（失败忽略，继续发布）",
			"action": {
				"type": "invoke",
				"find": {
					"kind": "rpa",
					"must": ["fill", "fill.action", "fill.target", "fill.value"],
					"filter": [{ "key": "domain", "value": "*" }]
				},
				"args": {
					"fill.action": "select",
					"fill.target": {
						"by": "query",
						"query": "可见范围/隐私/受众(Audience)/Visibility 的选择控件（下拉/菜单/弹层入口）"
					},
					"fill.value": "${visibility}"
				},
				"onError": "return",
				"returnTo": "caller",
				"timeoutMs": 12000
			},
			"next": {
				"done": "clickPublish",
				"failed": "clickPublish",
				"timeout": "clickPublish",
				"skipped": "clickPublish"
			}
		},

		{
			"id": "clickPublish",
			"desc": "点击发布/发送/提交按钮",
			"action": {
				"type": "click",
				"intent": "submit",
				"query": "发布/发送/提交（Post/Publish/Send/Submit）按钮：用于把当前已编辑好的内容发布出去"
			},
			"next": {
				"done": "clickConfirmIfAny",
				"failed": "routePublishManual",
				"timeout": "routePublishManual",
				"skipped": "routePublishManual"
			}
		},
		{
			"id": "routePublishManual",
			"desc": "若没点到发布按钮且允许人工参与，则提示用户手动点击发布",
			"action": {
				"type": "branch",
				"cases": [
					{ "when": { "op": "truthy", "source": "opts", "path": "allowManual" }, "to": "askUserClickPublish" }
				],
				"default": "abortCannotClickPublish"
			}
		},
		{
			"id": "askUserClickPublish",
			"desc": "请求用户手动点击发布",
			"action": {
				"type": "ask_assist",
				"reason": "我没有成功定位到“发布/发送/提交”按钮。请你手动点击一次发布/发送/提交，然后继续。",
				"waitUserAction": true
			},
			"next": "clickConfirmIfAny"
		},
		{
			"id": "abortCannotClickPublish",
			"desc": "无法点击发布且不允许人工参与",
			"action": {
				"type": "abort",
				"reason": "无法定位或点击“发布/发送/提交”按钮，且 opts.allowManual 未开启。"
			}
		},

		{
			"id": "clickConfirmIfAny",
			"desc": "若出现页面内二次确认按钮，则点击确认（找不到也继续）",
			"action": {
				"type": "click",
				"intent": "submit",
				"query": "二次确认发布/发送的按钮（确认/确定/发布/发送/Confirm/OK）；如果没有则忽略"
			},
			"next": {
				"done": "acceptDialogIfAny",
				"failed": "acceptDialogIfAny",
				"timeout": "acceptDialogIfAny",
				"skipped": "acceptDialogIfAny"
			}
		},
		{
			"id": "acceptDialogIfAny",
			"desc": "处理系统对话框（confirm/alert/prompt），尽量接受（没有则忽略）",
			"action": {
				"type": "dialog",
				"op": "accept"
			},
			"next": "waitPublishSuccess"
		},

		{
			"id": "waitPublishSuccess",
			"desc": "等待发布成功的提示（最简单路径：等成功提示）",
			"action": {
				"type": "wait",
				"query": "发布成功/已发送/已提交/Published/Sent/Success 的提示（toast/横幅/弹窗提示文本）",
				"state": "visible",
				"scope": "any",
				"timeoutMs": 12000,
				"pollMs": 180
			},
			"next": {
				"done": "readResultPageInfo",
				"failed": "routeOutcomeManual",
				"timeout": "routeOutcomeManual",
				"skipped": "routeOutcomeManual"
			}
		},
		{
			"id": "routeOutcomeManual",
			"desc": "未能确认成功提示：若允许人工参与则让用户确认已发布，否则放弃",
			"action": {
				"type": "branch",
				"cases": [
					{ "when": { "op": "truthy", "source": "opts", "path": "allowManual" }, "to": "askUserConfirmPublished" }
				],
				"default": "abortPublishNotConfirmed"
			}
		},
		{
			"id": "askUserConfirmPublished",
			"desc": "请求用户确认是否已发布，并完成必要的人机验证",
			"action": {
				"type": "ask_assist",
				"reason": "我没看到明确的“发布成功”提示。请你确认页面是否已发布（必要时完成验证码/风控提示/再次确认），完成后继续。",
				"waitUserAction": true
			},
			"next": "readResultPageInfo"
		},
		{
			"id": "abortPublishNotConfirmed",
			"desc": "无法确认发布成功且不允许人工参与",
			"action": {
				"type": "abort",
				"reason": "未能在超时内确认发布成功提示，且 opts.allowManual 未开启。"
			}
		},

		{
			"id": "readResultPageInfo",
			"desc": "读取当前页面 URL/标题（用于回填发布结果）",
			"action": {
				"type": "readPage",
				"field": { "url": true, "title": true }
			},
			"saveAs": "pageInfo",
			"next": "buildPublishResult"
		},
		{
			"id": "buildPublishResult",
			"desc": "基于当前 URL 构造 compose.publish.result（best-effort 提取 id）",
			"action": {
				"type": "run_js",
				"scope": "agent",
				"args": ["${vars.pageInfo}"],
				"cache": false,
				"code": "function buildPublishResult(pageInfo){\n  const url = (pageInfo && typeof pageInfo.url === 'string' && pageInfo.url.trim()) ? pageInfo.url.trim() : null;\n  let id = null;\n  if (url) {\n    // best-effort：从 URL 中提取较长数字/短码作为 id（不保证所有站点适用）\n    const m1 = url.match(/(?:\\/|=)([0-9]{5,})(?:\\b|$)/);\n    if (m1) id = m1[1];\n    if (!id) {\n      const m2 = url.match(/\\/([A-Za-z0-9_-]{8,})(?:\\b|$)/);\n      if (m2) id = m2[1];\n    }\n  }\n  const out = { action: 'publish' };\n  if (id) out.id = id;\n  if (url) out.url = url;\n  return out;\n}"
			},
			"saveAs": "publishResult",
			"next": "doneOk"
		},

		{
			"id": "doneOk",
			"desc": "完成发布",
			"action": {
				"type": "done",
				"reason": "compose.publish done",
				"conclusion": "已完成发布（best-effort）。",
				"value": "${vars.publishResult}"
			}
		}
	],
	"vars": {
		"pageInfo": { "type": "object", "desc": "readPage 获取的 url/title", "from": "readResultPageInfo.saveAs" },
		"publishResult": { "type": "object", "desc": "compose.publish.result value（action/url/id）", "from": "buildPublishResult.saveAs" }
	}
}
export default flow;