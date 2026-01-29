const flow = {
	id: "compose_file",
	start: "normalizeFiles",
	args: {
		field: {
			type: "string",
			required: true,
			desc: '上传目标字段，仅支持 "image" 或 "video"'
		},
		files: {
			type: "array",
			required: true,
			desc: "要上传的文件路径列表。每项支持：string(路径) 或 {path:string}。"
		}
	},
	steps: [
		{
			id: "normalizeFiles",
			desc: "把 args.files 归一化为 uploadFile 所需的 FileSpec[]（仅 path）",
			action: {
				type: "run_js",
				scope: "agent",
				code: function (files) {
					try {
						const arr = Array.isArray(files) ? files : [];
						const out = [];
						for (let i = 0; i < arr.length; i++) {
							const it = arr[i];

							if (typeof it === "string") {
								const p = it.trim();
								if (p) out.push({ path: p });
								continue;
							}

							if (it && typeof it === "object") {
								const p = (typeof it.path === "string") ? it.path.trim() : "";
								if (p) out.push({ path: p });
							}
						}
						return out;
					} catch (e) {
						return [];
					}
				},
				args: ["${args.files}"],
				cache: false
			},
			saveAs: {
				normFiles: "${result.value}",
				normCount: "${{ return Array.isArray(result.value) ? result.value.length : 0 }}"
			},
			next: {
				done: "routeField",
				failed: "askAssistNormalize"
			}
		},

		{
			id: "routeField",
			desc: "根据 args.field 分流到 image/video 上传入口",
			action: {
				type: "branch",
				cases: [
					{ when: { op: "eq", path: "field", value: "image" }, to: "uploadImages" },
					{ when: { op: "eq", path: "field", value: "video" }, to: "uploadVideos" }
				],
				default: "askAssistBadField"
			}
		},

		{
			id: "uploadImages",
			desc: "上传图片文件（多选）",
			action: {
				type: "uploadFile",
				query:
				"the image upload button or file input for adding photos/images (e.g., 'Add photo', 'Upload image', 'Photos') in the current compose editor",
				files: "${vars.normFiles}"
			},
			next: {
				done: "doneOk",
				failed: "askAssistUpload"
			}
		},

		{
			id: "uploadVideos",
			desc: "上传视频文件（多选）",
			action: {
				type: "uploadFile",
				query:
				"the video upload button or file input for adding videos (e.g., 'Add video', 'Upload video') in the current compose editor",
				files: "${vars.normFiles}"
			},
			next: {
				done: "doneOk",
				failed: "askAssistUpload"
			}
		},

		{
			id: "askAssistBadField",
			desc: "field 非法时请求人工介入",
			action: {
				type: "ask_assist",
				reason: 'compose_file: args.field 仅支持 "image" 或 "video"，请修正参数后重试。'
			},
			next: {
				done: "abortBadField",
				failed: "abortBadField",
				timeout: "abortBadField",
				skipped: "abortBadField"
			}
		},

		{
			id: "askAssistNormalize",
			desc: "无法归一化 files 时请求人工介入",
			action: {
				type: "ask_assist",
				reason:
				"compose_file: 无法解析/归一化 args.files，请确认每项为文件路径 string 或 {path:string}。"
			},
			next: {
				done: "abortNormalize",
				failed: "abortNormalize",
				timeout: "abortNormalize",
				skipped: "abortNormalize"
			}
		},

		{
			id: "askAssistUpload",
			desc: "上传失败时请求人工完成上传",
			action: {
				type: "ask_assist",
				reason:
				"compose_file: 自动上传失败。请在当前编辑器中手动完成附件上传（图片/视频），完成后点继续。"
			},
			next: {
				done: "doneOk",
				failed: "abortUpload",
				timeout: "abortUpload",
				skipped: "abortUpload"
			}
		},

		{
			id: "doneOk",
			desc: "上传完成",
			action: {
				type: "done",
				reason: "files uploaded",
				conclusion: "${{ return `已完成上传：${vars.normCount || 0} 个文件（field=${args.field}）。` }}"
			}
		},

		{
			id: "abortBadField",
			desc: "参数 field 不合法，放弃",
			action: {
				type: "abort",
				reason: 'compose_file: bad args.field (only "image"|"video")'
			}
		},

		{
			id: "abortNormalize",
			desc: "files 归一化失败，放弃",
			action: {
				type: "abort",
				reason: "compose_file: failed to normalize args.files"
			}
		},

		{
			id: "abortUpload",
			desc: "上传失败且未能人工完成，放弃",
			action: {
				type: "abort",
				reason: "compose_file: upload failed"
			}
		}
	],
	vars: {
		normFiles: { type: "array", desc: "归一化后的 FileSpec[]（仅 path）", from: "normalizeFiles.saveAs" },
		normCount: { type: "number", desc: "归一化后的文件数量", from: "normalizeFiles.saveAs" }
	}
};

export default flow;