/**
 * 解析带有插值语法的字符串或任意值，根据业务参数(args)、环境参数(opts)、流程变量(vars)及上一步执行结果(result)进行安全的插值替换。
 *
 * 支持的插值语法：`${path}`，其中 path 为安全子集(标识符/点/数字索引)。
 * 
 * 主要能力：
 *  - 仅当传入字符串为纯`${path}`格式时，返回原始值(如对象/数字等, 不强转字符串)
 *  - 其它情况：对字符串内容做插值，支持 `\${` 转义为字面量 `${`
 *  - 允许源切换(如`${vars.xxx}`/`${opts.xxx}`/`${result.xxx}`/`${args.xxx}`)，默认从args取值
 *  - 自动拒绝危险属性(__proto__/constructor/prototype) 防止原型污染
 *  - 仅支持安全的路径访问(不支持任意表达式/JS代码)
 *
 * @param {any} val    待处理的值(通常为字符串, 但支持任意类型)
 * @param {object} args  业务参数对象(Flow调用时传入)
 * @param {object} opts  环境/策略参数对象
 * @param {object} vars  局部流程变量对象
 * @param {object} result 上一步执行结果对象
 * @returns {any} 已经插值替换、反转义后的值(类型同输入，不强制转string)
 */
function parseFlowVal(val, args, opts, vars, result, _seen) {
	// cycle guard for objects/arrays
	const seen = _seen || new WeakMap();

	// 1) Arrays: deep-map
	if (Array.isArray(val)) {
		if (seen.has(val)) return seen.get(val);
		const out = [];
		seen.set(val, out);
		for (let i = 0; i < val.length; i++) {
			out[i] = parseFlowVal(val[i], args, opts, vars, result, seen);
		}
		return out;
	}

	// 2) Plain objects: deep-map (skip special objects)
	if (val && typeof val === "object") {
		const proto = Object.getPrototypeOf(val);
		const isPlain = proto === Object.prototype || proto === null;
		if (!isPlain) return val;

		if (seen.has(val)) return seen.get(val);
		const out = proto === null ? Object.create(null) : {};
		seen.set(val, out);

		for (const k of Object.keys(val)) {
			out[k] = parseFlowVal(val[k], args, opts, vars, result, seen);
		}
		return out;
	}

	// 3) Non-string primitive: return as-is
	if (typeof val !== "string") return val;

	const s = val;

	const isDangerKey = (k) => k === "__proto__" || k === "prototype" || k === "constructor";

	function evalJsBlock(code) {
		const js = String(code || "").trim();
		if (!js) return "";

		// If user didn't write "return", treat it as an expression.
		const body = /\breturn\b/.test(js) ? js : `return (${js});`;

		// NOTE: This is powerful by design (Function can access globals).
		// Variables must be explicit: args/opts/vars/result.
		const fn = new Function("args", "opts", "vars", "result", `"use strict";\n${body}`);
		return fn(args, opts, vars, result);
	}

	function resolvePath(rawPath) {
		let path = String(rawPath || "").trim();
		if (!path) return undefined;

		// Support root objects: ${result} / ${vars} / ${opts} / ${args}
		if (path === "args") return args;
		if (path === "opts") return opts;
		if (path === "vars") return vars;
		if (path === "result") return result;

		// Decide source object by prefix (default: args)
		let src = args;
		const pickSource = (obj, cutLen) => {
			src = obj;
			path = path.slice(cutLen);
			if (path.startsWith(".")) path = path.slice(1);
		};

		if (path.startsWith("vars.") || path.startsWith("vars[")) pickSource(vars, 4);
		else if (path.startsWith("opts.") || path.startsWith("opts[")) pickSource(opts, 4);
		else if (path.startsWith("result.") || path.startsWith("result[")) pickSource(result, 6);
		else if (path.startsWith("args.") || path.startsWith("args[")) pickSource(args, 4);
		// else: default args, keep path as-is

		if (src == null) return undefined;
		if (!path) return src;

		// Parse safe path: ident / dot / [number]
		const tokens = [];
		let i = 0;

		const isIdentStart = (c) => /[A-Za-z_$]/.test(c);
		const isIdentChar = (c) => /[A-Za-z0-9_$]/.test(c);

		while (i < path.length) {
			const ch = path[i];

			if (ch === ".") {
				i += 1;
				continue;
			}

			if (ch === "[") {
				// only allow numeric index: [0]
				let j = i + 1;
				let numStr = "";
				while (j < path.length && /[0-9]/.test(path[j])) {
					numStr += path[j];
					j += 1;
				}
				if (!numStr || path[j] !== "]") return undefined;
				tokens.push(Number(numStr));
				i = j + 1;
				continue;
			}

			if (isIdentStart(ch)) {
				let j = i + 1;
				while (j < path.length && isIdentChar(path[j])) j += 1;
				const key = path.slice(i, j);
				if (isDangerKey(key)) return undefined;
				tokens.push(key);
				i = j;
				continue;
			}

			return undefined; // invalid char -> reject
		}

		let cur = src;
		for (const t of tokens) {
			if (cur == null) return undefined;
			if (typeof t === "string") {
				if (isDangerKey(t)) return undefined;
				cur = cur[t];
			} else {
				cur = cur[t];
			}
		}
		return cur;
	}

	function toStrForInterpolation(v) {
		if (v == null) return "";
		if (typeof v === "string") return v;
		if (typeof v === "number" || typeof v === "boolean" || typeof v === "bigint") return String(v);
		try {
			return JSON.stringify(v);
		} catch {
			return String(v);
		}
	}

	// A) Exact JS block form: "${{ ... }}"
	//    - Keep original type (object/array/etc)
	//    - No "default args member" semantics; must use args/opts/vars/result explicitly in JS
	const jsBlock = s.match(/^\$\{\{([\s\S]*)\}\}$/);
	if (jsBlock) {
		try {
			const v = evalJsBlock(jsBlock[1]);
			return v == null ? "" : v;
		} catch (e) {
			// you can choose: throw e;  // if you want hard-fail
			return ""; // soft-fail by default
		}
	}

	// B) Exact single path expression => return typed value (keep original type)
	const sole = s.match(/^\$\{([^}]+)\}$/);
	if (sole) {
		const v = resolvePath(sole[1]);
		return v == null ? "" : v;
	}

	// C) Otherwise: string interpolation + unescape \$ -> $
	let out = "";
	let i = 0;

	while (i < s.length) {
		const ch = s[i];

		// \$
		if (ch === "\\" && i + 1 < s.length && s[i + 1] === "$") {
			out += "$";
			i += 2;
			continue;
		}

		// ${...} (path-only interpolation inside larger strings)
		if (ch === "$" && i + 1 < s.length && s[i + 1] === "{") {
			const end = s.indexOf("}", i + 2);
			if (end === -1) {
				out += "$";
				i += 1;
				continue;
			}
			const expr = s.slice(i + 2, end);
			const v = resolvePath(expr);
			out += toStrForInterpolation(v);
			i = end + 1;
			continue;
		}

		out += ch;
		i += 1;
	}

	return out;
}

/**
 * runBranchAction(action, args, opts, vars, result) -> nextStepId
 *
 * - action: { type:"branch", cases:[{when:Cond,to:string}], default:string }
 * - Cond DSL: exists/truthy/eq/neq/in/contains/match/and/or/not
 * - source 默认 "args"，也可为 "opts"|"vars"|"result"
 * - path 只允许安全子集：ident / dot / [number]
 */
function runBranchAction(action, args, opts, vars, result) {
	if (!action || action.type !== "branch") {
		throw new Error("runBranchAction: action.type must be 'branch'");
	}

	const cases = Array.isArray(action.cases) ? action.cases : [];
	const fallback = action.default;

	for (const c of cases) {
		if (!c || !c.when || typeof c.to !== "string") continue;
		if (evalCond(c.when)) return c.to;
	}
	return fallback;

	// -----------------------
	// Cond evaluation
	// -----------------------
	function evalCond(cond) {
		if (!cond || typeof cond !== "object") return false;

		switch (cond.op) {
			case "exists": {
				const v = readValue(cond);
				return v !== null && v !== undefined;
			}
			case "truthy": {
				const v = readValue(cond);
				return !!v;
			}
			case "eq": {
				const v = readValue(cond);
				return v === cond.value;
			}
			case "neq": {
				const v = readValue(cond);
				return v !== cond.value;
			}
			case "in": {
				const v = readValue(cond);
				const arr = Array.isArray(cond.values) ? cond.values : [];
				return arr.some((x) => x === v);
			}
			case "contains": {
				const v = readValue(cond);
				const needle = cond.value;

				if (typeof v === "string") return v.includes(String(needle));
				if (Array.isArray(v)) return v.some((x) => x === needle);

				// 可选：支持 Set
				if (v && typeof v === "object" && typeof v.has === "function") {
					try { return v.has(needle); } catch { return false; }
				}
				return false;
			}
			case "match": {
				const v = readValue(cond);
				if (v === null || v === undefined) return false;

				let re;
				try {
					re = new RegExp(String(cond.regex ?? ""), String(cond.flags ?? ""));
				} catch {
					return false;
				}
				return re.test(String(v));
			}
			case "and": {
				const items = Array.isArray(cond.items) ? cond.items : [];
				return items.every(evalCond);
			}
			case "or": {
				const items = Array.isArray(cond.items) ? cond.items : [];
				return items.some(evalCond);
			}
			case "not": {
				return !evalCond(cond.item);
			}
			default:
				return false;
		}
	}

	function readValue(cond) {
		const source = cond.source || "args";
		const path = String(cond.path || "");

		let base;
		if (source === "args") base = args;
		else if (source === "opts") base = opts;          // opts 可能为 null
		else if (source === "vars") base = vars;
		else if (source === "result") base = result;
		else base = args;

		return getBySafePath(base, path);
	}

	// -----------------------
	// Safe path resolver
	// -----------------------
	function getBySafePath(base, path) {
		if (base == null) return undefined;
		const p = String(path || "").trim();
		if (!p) return undefined;

		const isDangerKey = (k) => k === "__proto__" || k === "prototype" || k === "constructor";
		const isIdentStart = (c) => /[A-Za-z_$]/.test(c);
		const isIdentChar = (c) => /[A-Za-z0-9_$]/.test(c);

		const tokens = [];
		let i = 0;

		while (i < p.length) {
			const ch = p[i];

			if (ch === ".") { i += 1; continue; }

			if (ch === "[") {
				// only numeric index: [0]
				let j = i + 1;
				let numStr = "";
				while (j < p.length && /[0-9]/.test(p[j])) {
					numStr += p[j];
					j += 1;
				}
				if (!numStr || p[j] !== "]") return undefined;
				tokens.push(Number(numStr));
				i = j + 1;
				continue;
			}

			if (isIdentStart(ch)) {
				let j = i + 1;
				while (j < p.length && isIdentChar(p[j])) j += 1;
				const key = p.slice(i, j);
				if (isDangerKey(key)) return undefined;
				tokens.push(key);
				i = j;
				continue;
			}

			// invalid char
			return undefined;
		}

		let cur = base;
		for (const t of tokens) {
			if (cur == null) return undefined;
			if (typeof t === "string") {
				if (isDangerKey(t)) return undefined;
				cur = cur[t];
			} else {
				cur = cur[t];
			}
		}
		return cur;
	}
}

/**
 * execRunJsAction(action, ctx) -> Promise<StepResult>
 *
 * ctx:
 * - args, opts, vars, result: 当前运行时上下文
 * - parseVal: 你前面实现的 parseVal(val, args, opts, vars, result)
 * - pageEval?: async (codeString, argsArray) => any   // scope:"page" 时必须提供
 * - maxPageArgsBytes?: number                         // 默认 256KB
 * - allowPageDataUrl?: boolean                        // 默认 false
 * - maxDataUrlChars?: number                          // 默认 4096（仅用于 page args 的限制）
 */
async function execRunJsAction(action, ctx) {
	const t0 = Date.now();

	if(!ctx.parseVal){
		ctx.parseVal=parseFlowVal;
	}

	try {
		if (!action || action.type !== "run_js") {
			return {
				status: "failed",
				reason: "run_js: invalid action",
			};
		}

		const scope = (action.scope === "agent") ? "agent" : "page";
		const code = String(action.code || "");

		// spec: code 不做插值，简单粗暴：禁止出现 ${（不区分是否在字符串里）
		/*if (code.includes("${")) {
			return {
				status: "failed",
				reason: "run_js.code must not contain '${' (interpolation is forbidden in code)",
			};
		}*/

		// 解析 action.args（允许插值、且支持对象/数组递归）
		const rawArgs = Array.isArray(action.args) ? action.args : [];
		const parsedArgs = rawArgs.map(v => ctx.parseVal(v, ctx.args, ctx.opts, ctx.vars, ctx.result));

		// 编译：必须“整体就是一个函数”，否则失败
		const compiled = compileSingleFunction(code);
		if (!compiled.ok) {
			return {
				status: "failed",
				reason: `run_js.code invalid: ${compiled.reason}`,
			};
		}

		let value;

		if (scope === "agent") {
			// agent scope：直接在当前环境调用
			if(action.code instanceof Function){
				value = await action.code(...parsedArgs);
			}else {
				value = await compiled.fn(...parsedArgs);
			}
		} else {
			// page scope：交给页面执行器
			if (typeof ctx.pageEval !== "function") {
				return {
					status: "failed",
					reason: 'run_js(scope:"page") requires ctx.pageEval(code, args)',
					meta: { scope },
				};
			}

			// page args 限制（强烈建议）
			const maxBytes = Number.isFinite(ctx.maxPageArgsBytes) ? ctx.maxPageArgsBytes : 256 * 1024;
			const allowDataUrl = !!ctx.allowPageDataUrl;
			const maxDataUrlChars = Number.isFinite(ctx.maxDataUrlChars) ? ctx.maxDataUrlChars : 4096;

			const bytes = approxUtf8BytesSafeJson(parsedArgs);
			if (bytes > maxBytes) {
				return {
					status: "failed",
					reason: `run_js(page) args too large: ~${bytes} bytes (limit ${maxBytes})`,
					meta: { scope, argsBytes: bytes, argsCount: parsedArgs.length },
				};
			}

			if (!allowDataUrl && containsLargeDataUrl(parsedArgs, maxDataUrlChars)) {
				return {
					status: "failed",
					reason: `run_js(page) args contain large DataURL (limit ${maxDataUrlChars} chars)`,
					meta: { scope, argsCount: parsedArgs.length },
				};
			}

			// 让 pageEval 去做：在页面中定义并调用函数，返回结果
			// 传 code 原文（函数代码），由 page 侧 `return (${code})(...args)` 之类执行
			value = await ctx.pageEval(code, parsedArgs);
		}

		return {
			status: "done",
			value: value,
			meta: {
				scope,
				durationMs: Date.now() - t0,
				argsCount: parsedArgs.length,
			},
		};
	} catch (e) {
		return {
			status: "failed",
			reason: "run_js threw an error",
			error: { name: e && e.name, message: e && e.message },
			meta: { durationMs: Date.now() - t0 },
		};
	}

	// -------------------------
	// Helpers
	// -------------------------

	function compileSingleFunction(codeStr) {
		const src = String(codeStr || "").trim();
		if (!src) return { ok: false, reason: "empty code" };

		// 轻量防“自调用/IIFE”顶层：结尾出现 )() 或 }() 这类基本都不符合
		if (/\)\s*\(\s*\)\s*;?\s*$/.test(src) || /\}\s*\(\s*\)\s*;?\s*$/.test(src)) {
			return { ok: false, reason: "top-level invocation (IIFE) is not allowed" };
		}

		let fn;
		try {
			// 关键：要求整体表达式的结果就是 function
			// - "function(a){...}" OK
			// - "(a)=>{...}" OK
			// - "function f(a){...}" OK（在表达式里也成立）
			fn = (new Function('"use strict"; return (' + src + ');'))();
		} catch (e) {
			return { ok: false, reason: "cannot compile to a function" };
		}

		if (typeof fn !== "function") {
			return { ok: false, reason: "code does not evaluate to a function" };
		}

		return { ok: true, fn };
	}

	function approxUtf8BytesSafeJson(x) {
		// 仅用于粗略大小限制；如果不可 JSON 化，退化为 String
		try {
			const s = JSON.stringify(x);
			return utf8ByteLength(s);
		} catch {
			return utf8ByteLength(String(x));
		}
	}

	function utf8ByteLength(str) {
		// 近似 UTF-8 字节数（足够用于限制）
		let bytes = 0;
		for (let i = 0; i < str.length; i++) {
			const c = str.charCodeAt(i);
			if (c <= 0x7f) bytes += 1;
			else if (c <= 0x7ff) bytes += 2;
			else if (c >= 0xd800 && c <= 0xdbff) { // surrogate pair
				bytes += 4;
				i++;
			} else bytes += 3;
		}
		return bytes;
	}

	function containsLargeDataUrl(x, maxChars) {
		// 深度遍历：只要出现 string 以 data: 开头且长度过大就判定 true
		const seen = new WeakSet();

		function walk(v) {
			if (v == null) return false;
			const t = typeof v;

			if (t === "string") {
				if (v.startsWith("data:") && v.length > maxChars) return true;
				return false;
			}
			if (t !== "object") return false;

			if (seen.has(v)) return false;
			seen.add(v);

			if (Array.isArray(v)) {
				for (const it of v) if (walk(it)) return true;
				return false;
			}
			const proto = Object.getPrototypeOf(v);
			const isPlain = proto === Object.prototype || proto === null;
			if (!isPlain) return false;

			for (const k of Object.keys(v)) {
				if (walk(v[k])) return true;
			}
			return false;
		}

		return walk(x);
	}
}
export {parseFlowVal,runBranchAction,execRunJsAction};