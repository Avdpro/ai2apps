import {deepEq,getLan,briefJSON,expandDottedKeys,readRule,saveRule,readRuleElements,getRuleElementBySigKey,getRuleElementById} from "./utils.js";

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

	if (!ctx.parseVal) {
		ctx.parseVal = parseFlowVal;
	}

	// -------------------------
	// Logs (always included in meta)
	// -------------------------
	const logs = [];
	const logsLimit = Number.isFinite(ctx.maxRunJsLogs) ? ctx.maxRunJsLogs : 200;
	let logsTruncated = false;

	function pushLog(level, args) {
		if (logsTruncated) return;
		if (logs.length >= logsLimit) {
			logsTruncated = true;
			logs.push({ t: Date.now(), level: "internal", args: safeBrief(["logs truncated", { limit: logsLimit }]) });
			return;
		}
		logs.push({ t: Date.now(), level, args: safeBrief(args) });
	}

	function safeBrief(val) {
		try {
			// 你已有的 briefJSON：限制 JSON 长度、处理递归嵌套
			return briefJSON(val);
		} catch (e) {
			// briefJSON 自己炸了也不能影响主流程
			try {
				return { __brief_failed: true, message: e && e.message };
			} catch {
				return "__brief_failed__";
			}
		}
	}

	function normArgs(args) {
		// 把 Error 稳定化，便于 briefJSON & 上报
		return Array.isArray(args) ? args.map(a => {
			if (a instanceof Error) {
				return { __type: "Error", name: a.name, message: a.message, stack: a.stack };
			}
			return a;
		}) : args;
	}

	function hookConsole() {
		const orig = {
			log: console.log,
			info: console.info,
			warn: console.warn,
			error: console.error,
			debug: console.debug,
		};

		console.log = function(...args) {
			pushLog("log", normArgs(args));
			orig.log.apply(console, args);
		};
		console.info = function(...args) {
			pushLog("info", normArgs(args));
			orig.info.apply(console, args);
		};
		console.warn = function(...args) {
			pushLog("warn", normArgs(args));
			orig.warn.apply(console, args);
		};
		console.error = function(...args) {
			pushLog("error", normArgs(args));
			orig.error.apply(console, args);
		};
		console.debug = function(...args) {
			pushLog("debug", normArgs(args));
			orig.debug.apply(console, args);
		};

		return function restoreConsole() {
			console.log = orig.log;
			console.info = orig.info;
			console.warn = orig.warn;
			console.error = orig.error;
			console.debug = orig.debug;
		};
	}

	try {
		if (!action || action.type !== "run_js") {
			return {
				status: "failed",
				reason: "run_js: invalid action",
				meta: { durationMs: Date.now() - t0, logs, logsTruncated, logsLimit },
			};
		}

		const scope = (action.scope === "agent") ? "agent" : "page";
		const code = String(action.code || "");

		// 解析 action.args（允许插值、且支持对象/数组递归）
		const rawArgs = Array.isArray(action.args) ? action.args : [];
		const parsedArgs = rawArgs.map(v => ctx.parseVal(v, ctx.args, ctx.opts, ctx.vars, ctx.result));

		// 编译：必须“整体就是一个函数”，否则失败
		const compiled = compileSingleFunction(code);
		if (!compiled.ok) {
			return {
				status: "failed",
				reason: `run_js.code invalid: ${compiled.reason}`,
				meta: { scope, durationMs: Date.now() - t0, argsCount: parsedArgs.length, logs, logsTruncated, logsLimit },
			};
		}

		let value;

		if (scope === "agent") {
			// agent scope：直接在当前环境调用（期间捕获 console）
			const restore = hookConsole();
			try {
				if (action.code instanceof Function) {
					value = await action.code(...parsedArgs);
				} else {
					value = await compiled.fn(...parsedArgs);
				}
			} catch (e) {
				// 记录 throw（同时不吞掉错误，交给外层 catch 返回 failed）
				pushLog("throw", [{ __type: "Error", name: e && e.name, message: e && e.message, stack: e && e.stack }]);
				throw e;
			} finally {
				restore();
			}
		} else {
			// page scope：交给页面执行器（在页面内部捕获 console）
			if (typeof ctx.pageEval !== "function") {
				return {
					status: "failed",
					reason: 'run_js(scope:"page") requires ctx.pageEval(code, args)',
					meta: { scope, durationMs: Date.now() - t0, argsCount: parsedArgs.length, logs, logsTruncated, logsLimit },
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
					meta: { scope, durationMs: Date.now() - t0, argsBytes: bytes, argsCount: parsedArgs.length, logs, logsTruncated, logsLimit },
				};
			}

			if (!allowDataUrl && containsLargeDataUrl(parsedArgs, maxDataUrlChars)) {
				return {
					status: "failed",
					reason: `run_js(page) args contain large DataURL (limit ${maxDataUrlChars} chars)`,
					meta: { scope, durationMs: Date.now() - t0, argsCount: parsedArgs.length, logs, logsTruncated, logsLimit },
				};
			}

			// page wrapper：第一个参数传 userCode 字符串，后面是原 args
			const wrapperCode = PAGE_WRAPPER_CODE;
			const ret = await ctx.pageEval(wrapperCode, [code, ...parsedArgs]);

			// ret 约定：{ ok, value?, error?, logs? }
			if (!ret || typeof ret !== "object") {
				return {
					status: "failed",
					reason: "run_js(page) returned non-object result",
					meta: { scope, durationMs: Date.now() - t0, argsCount: parsedArgs.length, logs, logsTruncated, logsLimit },
				};
			}

			// 这里以 page logs 为准（不混 Node 内部 logs；Node 内部基本不会产生日志）
			const pageLogs = Array.isArray(ret.logs) ? ret.logs : [];
			logs.length = 0;
			for (let i = 0; i < pageLogs.length; i++) logs.push(pageLogs[i]);

			if (ret.ok) {
				value = ret.value;
			} else {
				return {
					status: "failed",
					reason: "run_js(page) threw an error",
					error: ret.error || { name: "Error", message: "unknown error" },
					meta: { scope, durationMs: Date.now() - t0, argsCount: parsedArgs.length, logs, logsTruncated: !!ret.logsTruncated, logsLimit: ret.logsLimit || logsLimit },
				};
			}
		}

		return {
			status: "done",
			value: value,
			meta: {
				scope,
				durationMs: Date.now() - t0,
				argsCount: parsedArgs.length,
				logs,
				logsTruncated,
				logsLimit,
			},
		};
	} catch (e) {
		return {
			status: "failed",
			reason: "run_js threw an error",
			error: { name: e && e.name, message: e && e.message },
			meta: { durationMs: Date.now() - t0, logs, logsTruncated, logsLimit },
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
		try {
			const s = JSON.stringify(x);
			return utf8ByteLength(s);
		} catch {
			return utf8ByteLength(String(x));
		}
	}

	function utf8ByteLength(str) {
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

// -------------------------
// Page wrapper (function source string)
// - args: (userCodeStr, ...args)
// - returns: { ok, value?, error?, logs, logsTruncated, logsLimit }
// -------------------------
const PAGE_WRAPPER_CODE = String(function (userCodeStr, ...args) {
	// ---- minimal brief (cycle-safe, depth/len-limited) ----
	const logs = [];
	const logsLimit = 200; // page side default; you can pass from ctx by embedding, or keep fixed
	let logsTruncated = false;

	function __brief(val) {
		const seen = new WeakSet();
		const maxDepth = 4;
		const maxStr = 500;
		const maxKeys = 50;
		const maxArr = 50;

		function cutStr(s) {
			s = String(s);
			return (s.length > maxStr) ? (s.slice(0, maxStr) + "…") : s;
		}

		function enc(v, d) {
			if (v == null) return v;
			const t = typeof v;

			if (t === "string") return cutStr(v);
			if (t === "number" || t === "boolean") return v;
			if (t === "bigint") return String(v);
			if (t === "symbol") return String(v);
			if (t === "function") return "[Function]";
			if (v instanceof Error) return { __type: "Error", name: v.name, message: v.message, stack: cutStr(v.stack || "") };

			if (d >= maxDepth) return "[MaxDepth]";

			if (t === "object") {
				if (seen.has(v)) return "[Circular]";
				seen.add(v);

				if (Array.isArray(v)) {
					const out = [];
					const n = Math.min(v.length, maxArr);
					for (let i = 0; i < n; i++) out.push(enc(v[i], d + 1));
					if (v.length > n) out.push(`[+${v.length - n} more]`);
					return out;
				}

				const proto = Object.getPrototypeOf(v);
				const isPlain = proto === Object.prototype || proto === null;
				if (!isPlain) return `[${(v && v.constructor && v.constructor.name) || "Object"}]`;

				const out = proto === null ? Object.create(null) : {};
				const ks = Object.keys(v);
				const n = Math.min(ks.length, maxKeys);
				for (let i = 0; i < n; i++) {
					const k = ks[i];
					out[k] = enc(v[k], d + 1);
				}
				if (ks.length > n) out.__moreKeys = ks.length - n;
				return out;
			}

			return String(v);
		}

		return enc(val, 0);
	}

	function push(level, rawArgs) {
		if (logsTruncated) return;
		if (logs.length >= logsLimit) {
			logsTruncated = true;
			logs.push({ t: Date.now(), level: "internal", args: __brief(["logs truncated", { limit: logsLimit }]) });
			return;
		}
		logs.push({ t: Date.now(), level, args: __brief(rawArgs) });
	}

	const orig = {
		log: console.log,
		info: console.info,
		warn: console.warn,
		error: console.error,
		debug: console.debug,
	};

	console.log = function(...a) { push("log", a); orig.log.apply(console, a); };
	console.info = function(...a) { push("info", a); orig.info.apply(console, a); };
	console.warn = function(...a) { push("warn", a); orig.warn.apply(console, a); };
	console.error = function(...a) { push("error", a); orig.error.apply(console, a); };
	console.debug = function(...a) { push("debug", a); orig.debug.apply(console, a); };

	function restore() {
		console.log = orig.log;
		console.info = orig.info;
		console.warn = orig.warn;
		console.error = orig.error;
		console.debug = orig.debug;
	}

	try {
		// compile from string to function in page
		const fn = (0, eval)("(" + String(userCodeStr || "") + ")");
		if (typeof fn !== "function") {
			restore();
			return { ok: false, error: { name: "TypeError", message: "code does not evaluate to a function" }, logs, logsTruncated, logsLimit };
		}

		return Promise.resolve(fn(...args)).then(
			(v) => { restore(); return { ok: true, value: v, logs, logsTruncated, logsLimit }; },
			(e) => {
				push("throw", [e instanceof Error ? { __type: "Error", name: e.name, message: e.message, stack: e.stack } : e]);
				restore();
				return { ok: false, error: { name: e && e.name, message: e && e.message, stack: e && e.stack }, logs, logsTruncated, logsLimit };
			}
		);
	} catch (e) {
		push("throw", [e instanceof Error ? { __type: "Error", name: e.name, message: e.message, stack: e.stack } : e]);
		restore();
		return { ok: false, error: { name: e && e.name, message: e && e.message, stack: e && e.stack }, logs, logsTruncated, logsLimit };
	}
});


/**
 * buildRpaMicroDeciderPromptV40
 * -----------------------------------------
 * Micro-decider prompt builder aligned with rpa-flow-spec v0.40 (no branch).
 *
 * Outputs a prompt that forces the model to return exactly ONE atomic action as strict JSON.
 *
 * Project-level (stricter-than-spec) policies baked into the prompt:
 * - QuerySpec MUST be an object (not a plain string) whenever query is used.
 * - Element-targeting actions MUST include both query + by.
 * - run_js is READ-ONLY (v0.40): extract/compute/generate/locate/validate only; no page state changes.
 * - run_js MUST output scope and cache (even if spec marks them optional).
 * - args/vars/opts/result are READ-ONLY; persistence ONLY via top-level saveAs into vars.
 * - FlowVal path roots are strictly limited to: args / vars / opts / result.
 *
 * Assumption:
 * - Host injects trimmed rpa.mjs (allowed invoke capabilities + arg schema) via extra user messages.
 *
 * Dependency:
 * - briefJSON(val, opts) must exist (your existing function).
 *
 * Call signature:
 *   buildRpaMicroDeciderPromptV40(goal, notes?, actions?, opts?)
 *
 * Parameters:
 * - goal: string (required)
 * - notes: string|null (optional)
 * - actions: null | string[] (optional). null => allow all actions in v0.40 set (except branch).
 * - opts: object (optional)
 *     - env?: { args?:any, vars?:any, opts?:any, result?:any }   // will be briefJSON-compressed into prompt
 *     - usedStepIds?: string[]
 *     - history?: Array<{ id:string, action?:object, result?:object }>
 *     - envBriefOpts?: briefJSON options
 *     - historyBriefOpts?: briefJSON options
 */
function buildRpaStepDeciderPrompt(goal, notes = "", actions = null, opts = null) {
	if (typeof goal !== "string" || !goal.trim()) {
		throw new Error("buildRpaMicroDeciderPromptV40(goal,...): goal must be a non-empty string");
	}
	if (!(typeof notes === "string" || notes == null)) {
		throw new Error("buildRpaMicroDeciderPromptV40(goal,...): notes must be a string (or null/undefined)");
	}
	if (!(actions === null || Array.isArray(actions))) {
		throw new Error("buildRpaMicroDeciderPromptV40(goal,...): actions must be null or an array of strings");
	}

	opts = (opts && typeof opts === "object") ? opts : {};
	const norm = (s) => String(s || "").trim();

	// ---- v0.40 action set (micro-decider: no "branch") ----
	const ALL_V40 = [
		"goto",
		"click",
		"hover",
		"input",
		"press_key",
		"scroll",
		"scroll_show",
		"readPage",
		"readElement",
		"setChecked",
		"setSelect",
		"dialog",
		"uploadFile",
		"run_js",
		"run_ai",
		"ask_assist",
		"selector",
		"wait",
		"invoke",
		"done",
		"abort",
	];

	const wantAll = actions === null;
	const allow = new Set((wantAll ? ALL_V40 : actions.map(norm)).filter(Boolean));
	allow.add("done");
	allow.add("abort");

	if (!wantAll) {
		const known = new Set(ALL_V40);
		const unknown = (actions || []).map(norm).filter(Boolean).filter((a) => !known.has(a));
		if (unknown.length) throw new Error(`Unknown actions: ${unknown.join(", ")}`);
	}

	const has = (a) => allow.has(a);

	// ---- Optional env & history injection via briefJSON ----
	const env = (opts.env && typeof opts.env === "object") ? opts.env : null;
	const history = Array.isArray(opts.history) ? opts.history : null;
	const usedStepIds = Array.isArray(opts.usedStepIds) ? opts.usedStepIds : null;

	const envBriefOpts = (opts.envBriefOpts && typeof opts.envBriefOpts === "object")
	? opts.envBriefOpts
	: { maxDepth: 4, maxString: 200, maxElements: 20, maxKeys: 50 };

	const historyBriefOpts = (opts.historyBriefOpts && typeof opts.historyBriefOpts === "object")
	? opts.historyBriefOpts
	: { maxDepth: 4, maxString: 180, maxElements: 30, maxKeys: 80 };

	const envBlock = env
	? `
────────────────────────────────────────────────────────
【可选：运行上下文（已提供，已压缩）】
说明：
- 仅用于：决定下一步策略、构造 action.args/text、决定 saveAs、或避免重复失败。
- 严禁在任何 action（尤其 run_js / run_ai）中修改这些对象；它们是只读的。
（压缩后 JSON）
${briefJSON(env, envBriefOpts)}
`.trim()
	: `
────────────────────────────────────────────────────────
【可选：运行上下文（本次未提供）】
- args?: object
- vars?: object
- opts?: object
- result?: object
说明：这些对象即便提供，也一律只读；持久化只能通过 saveAs 写入 vars。
`.trim();

	const historyObj = (history || usedStepIds) ? { usedStepIds: usedStepIds || [], history: history || [] } : null;
	const historyBlock = historyObj
	? `
────────────────────────────────────────────────────────
【已执行步骤历史（已提供，已压缩）】
用途：
- 避免重复失败：若某 type+by 刚失败，下一步必须换策略（wait/scroll_show/readElement/run_js/invoke 等）
- 纠错：history.result 可能包含失败 reason/logs，可据此修正下一步
- id 不重复：本次输出 id 不得与 usedStepIds 冲突
（压缩后 JSON）
${briefJSON(historyObj, historyBriefOpts)}
`.trim()
	: `
────────────────────────────────────────────────────────
【已执行步骤历史（本次未提供）】
建议宿主提供（可压缩）：
- usedStepIds?: string[]
- history?: Array<{ id?:string, action?:object, result?:object }>
其中 result 建议包含 status/by/reason/value/logs（越有利于纠错越好）
`.trim();

	// ---- QuerySpec (force OBJECT) ----
	const querySpecBlock = `
────────────────────────────────────────────────────────
【QuerySpec（强制使用对象，不允许纯字符串）】
QuerySpec = {
  text: string,                    // 自然语言意图描述（不要复制大段 html）
  kind?: "selector"|"status"|"code"|"value",
  mode?: "instance"|"class",
  policy?: "single"|"pool",
  maxLen?: number,
  share?: boolean,
  allowVision?: boolean,
  stabilityHint?: "high"|"medium"|"low",
  tags?: string[]
}
QueryOrTuple = QuerySpec | QuerySpec[]
ByOrTuple = string | string[]
`.trim();

	// ---- FlowVal + path rules (explicit) ----
	const flowValBlock = `
────────────────────────────────────────────────────────
【FlowVal 与 \${path}（用于 args / saveAs 等字段；run_js.code 禁止）】

FlowVal 支持两种形式：
1) 字符串插值： "xxx \${path} yyy"
   - 仅替换 \${path} 片段为对应值（转为字符串拼接）。
2) 整串表达式： "\${{ <js expression> }}"
   - 必须整串以 "\${{" 开头、"}}" 结尾；执行表达式并返回“原类型”（string/number/object/array...）。

path 语法（白名单根对象）：
- 允许的根：args / vars / opts / result
- 示例：
  - \${args.field}
  - \${vars.selectors.publishBtn}
  - \${opts.allowManual}
  - \${result.status}
  - \${result.by}
  - \${result.value}
  - \${result.value.items[0].url}

禁止：
- 任何未定义根对象：\${ctx...} / \${env...} / \${page...} / \${call...}
- 在 run_js.code 内出现任何 \${...}
`.trim();

	// ---- Read-only + persistence rules ----
	const readOnlyPersistenceBlock = `
────────────────────────────────────────────────────────
【只读与持久化规则（必须遵守）】
- 你在任何 action（尤其 run_js / run_ai）中都不得“修改”或“依赖修改”以下对象：
  - args / vars / opts / result（以及它们的子对象）
- 这些对象在决策时视为只读；即便你在 JS 里写了赋值，也会被视为违规/不可靠（执行器可能冻结/拷贝/丢弃）。
- 唯一允许的持久化方式：在本次输出 JSON 顶层使用 saveAs，把值写入 vars：
  - saveAs: "a.b.c"              // 写入 result.value
  - saveAs: { "a.b": FlowVal, ... }  // 写入表达式结果
`.trim();

	// ---- query+by enforcement ----
	const mustQueryBy = [
		"click",
		"hover",
		"scroll",       // if element-targeting
		"scroll_show",
		"readElement",
		"setChecked",
		"setSelect",
		"uploadFile",
		"selector",
		"wait",
	];

	const queryByRulesBlock = `
────────────────────────────────────────────────────────
【query + by 强制要求（微决策器策略，比 spec 更严格）】
对以下动作：${mustQueryBy.filter(has).join(", ") || "(本次允许动作集中无此类动作)"}
- 你必须同时输出：
  - query：QuerySpec 对象（不允许纯字符串）
  - by：可直接执行的选择器字符串（"css: ..." 或 "xpath: ..."）
- query.text 写自然语言意图，不要复制大段 html。
- by 优先稳定锚点：id/data-testid/aria-*/name/placeholder/href*=，避免脆弱 nth-child。
- 需要文本匹配时用 XPath：contains(normalize-space(.),"...")。
`.trim();

	// ---- Action union snippet builder ----
	const actionLines = [];

	if (has("goto")) actionLines.push(`  { type: "goto", url: string }`);

	if (has("click")) actionLines.push(`| { type: "click", query: QueryOrTuple, by: ByOrTuple, intent?: "open"|"dismiss"|"submit" }`);
	if (has("hover")) actionLines.push(`| { type: "hover", query: QueryOrTuple, by: ByOrTuple }`);

	if (has("input")) actionLines.push(`| { type: "input", text: string, mode?: "fill"|"type"|"paste", clear?: boolean, pressEnter?: boolean }`);
	if (has("press_key")) actionLines.push(`| { type: "press_key", key: string, modifiers?: ("Shift"|"Alt"|"Control"|"Meta")[], times?: number }`);

	if (has("scroll")) actionLines.push(`| { type: "scroll", x?: number, y?: number, query?: QueryOrTuple, by?: ByOrTuple }`);
	if (has("scroll_show")) actionLines.push(`| { type: "scroll_show", query?: QueryOrTuple, by?: ByOrTuple }`);

	if (has("readPage")) {
		actionLines.push(`| { type: "readPage", field: "html"|"url"|"title"|"article"|"screenshot"|{url?:boolean,title?:boolean,html?:boolean,article?:boolean,screenshot?:boolean} }`);
	}

	if (has("readElement")) {
		actionLines.push(`| { type: "readElement", query: QueryOrTuple, by: ByOrTuple, pick: "text"|"value"|"rect"|"html"|"html:inner"|("attr:" + string), multi?: boolean }`);
	}

	if (has("setChecked")) actionLines.push(`| { type: "setChecked", query: QueryOrTuple, by: ByOrTuple, checked: boolean, multi?: boolean }`);
	if (has("setSelect")) {
		actionLines.push(`| { type: "setSelect", query: QueryOrTuple, by: ByOrTuple, choice: { by:"value", value:string } | { by:"label", label:string } | { by:"index", index:number } }`);
	}

	if (has("dialog")) {
		actionLines.push(`| { type: "dialog", op: "accept"|"dismiss", kind?: "alert"|"confirm"|"prompt", textContains?: string, value?: string }`);
	}

	if (has("uploadFile")) {
		actionLines.push(`| { type: "uploadFile", query: QueryOrTuple, by: ByOrTuple, files: Array<{ path?: string, filename?: string, data?: string }> }`);
	}

	if (has("run_js")) {
		// spec: scope optional, cache optional; micro-decider: REQUIRE both (stricter).
		// args are FlowVal[] (not any[]) so the model uses ${path} there (and never in code).
		actionLines.push(`| { type: "run_js", scope: "page"|"agent", cache: boolean, code?: string, query?: QuerySpec, args?: FlowVal[] }`);
	}

	if (has("run_ai")) {
		actionLines.push(`| { type: "run_ai", prompt: string, input?: any, schema?: object, page?: {url?:boolean,html?:boolean,screenshot?:boolean,article?:boolean}, model?: "fast"|"balanced"|"quality"|"vision"|"free" }`);
	}

	if (has("ask_assist")) actionLines.push(`| { type: "ask_assist", reason: string, waitUserAction?: boolean }`);

	if (has("selector")) {
		actionLines.push(`| { type: "selector", query: QueryOrTuple, by: ByOrTuple, state?: "present"|"visible", scope?: "current"|"newest"|"any", autoSwitch?: boolean, multi?: boolean }`);
	}

	if (has("wait")) {
		actionLines.push(`| { type: "wait", query: QueryOrTuple, by: ByOrTuple, state?: "visible"|"present"|"hidden"|"gone", scope?: "current"|"newest"|"any", autoSwitch?: boolean, timeoutMs?: number, pollMs?: number }`);
	}

	if (has("invoke")) {
		actionLines.push(`| { type: "invoke", target?: string, find?: FindSpec, args?: Record<string, any>, timeoutMs?: number, onError?: "fail"|"return", returnTo?: "caller"|"keep" }`);
	}

	actionLines.push(`| { type: "done", reason: string, conclusion: string }`);
	actionLines.push(`| { type: "abort", reason: string }`);

	// ---- invoke find ref (short) ----
	const invokeFindRefBlock = has("invoke")
	? `
────────────────────────────────────────────────────────
【invoke.find 参考（短版，必须遵守）】
FindSpec = {
  kind: "rpa",
  must?: string[],    // 必须满足的 capability key（禁止杜撰）
  can?: string[],     // 可选能力
  filter?: Array<{ key: string, op?: "eq"|"ne"|"in"|"contains"|"exists", value?: any }>,
  rank?: string[]     // 排序规则（如需）
}

强规则：
- invoke.find.must/can 中的 capability key 只能来自“对话中额外注入的（裁剪后的）rpa.mjs 能力定义/清单”，禁止编造不存在的 key。
- 若你不确定存在某个能力：不要 invoke，改用 click/selector/readPage/ask_assist。
- invoke.args 必须符合该能力的 arg schema；不确定字段就省略，不要猜复杂结构。
`.trim()
	: "";

	// ---- run_js constraints (v0.40) + scope + args calling format + cache ----
	const runJsBlock = has("run_js")
	? `
────────────────────────────────────────────────────────
【run_js 强约束（v0.40，必须遵守）】

A) 调用与传参（与 spec 一致）
- action.args（若提供）按 FlowVal 规则解析/插值（其中 string 允许 \${path} / 整串 "\${{...}}"），得到 finalArgs 数组。
- 执行器以 fn(...finalArgs) 的方式调用函数。
- 你要传入的动态数据必须放在 action.args 里，而不是写进 code 文本里。
- scope:"page" 时 args 必须可序列化（JSON/结构化克隆友好），不要传大对象/大 DataURL。

B) code 形态
- code 必须且只能是一段“函数定义”代码（允许形参）；不得包含顶层执行语句/立即调用。
- code 不做插值：禁止出现 \${...}（包括 JS 模板字符串里的 \${...}）。

C) scope 选择（必须显式写出 scope；默认 page）
- scope:"page"（默认/优先）：用于 DOM 提取/定位/可见性判断/页面状态校验（读取 document/window/元素属性等）。
- scope:"agent"（少用）：仅用于“纯计算/格式化/归一化/小型打分”等不依赖 DOM 的逻辑；可读取宿主提供的只读上下文（args/vars/result/opts）。
- 任意 scope 都必须遵守下面的“只读约束”，禁止副作用；且不得修改传入的 args 对象内容（只读）。

D) 只读约束（最重要；任何 scope 都禁止副作用）
run_js 仅允许：提取、计算、生成内容（作为返回值）、定位元素（只返回 selector/by）、校验页面状态（如是否登录）。
禁止包括但不限于：
1) 导航/历史：location.assign/replace/reload、history.pushState/replaceState/go/back/forward、window.open
2) 触发交互：el.click/focus/blur、form.submit、dispatchEvent(...)
3) DOM 写入：innerHTML/outerHTML/insertAdjacentHTML/appendChild/removeChild、setAttribute/removeAttribute、classList.add/remove/toggle、style.*=、el.value=
4) 网络/外部副作用：fetch/XMLHttpRequest/WebSocket/sendBeacon
5) 存储写入：localStorage/sessionStorage/indexedDB 写入
6) 计时器/等待：setTimeout/setInterval/requestAnimationFrame、忙等循环
7) 弹窗：alert/confirm/prompt（交给 dialog action）

E) cache（必须输出）
- 当 action.type="run_js" 时，你必须输出 cache:boolean。
- cache=true：脚本是通用的只读探测/提取/定位/校验逻辑；仅通过 args 接收少量参数；对同类页面可重复使用。
- cache=false：脚本明显是一次性修补/强依赖本页瞬时 DOM/文本/错误上下文；或预计下次很可能无效。

F) 何时用 run_js
- 仅当缺少可靠 by、需要轻量判断/提取/可见性检测、或需要从 html 中快速做只读筛选时使用。
- 若仅提供 query（不提供 code），表示“让系统用 AI 生成 code”；cache 仅在脚本可复用时才 true。
`.trim()
	: "";

	// ---- saveAs rules ----
	const saveAsBlock = `
────────────────────────────────────────────────────────
【saveAs（可选，用于写入 vars；由宿主映射到 Step.saveAs）】
- 形式A：saveAs: "a.b.c"
  含义：把本次 action 的 result.value 写入 vars.a.b.c
- 形式B：saveAs: { "a.b": FlowVal, "x": FlowVal, ... }
  含义：逐项写入；FlowVal 支持 \${result.by} / \${result.value} / \${vars...} / \${args...} / \${opts...} / \${{ ... }}

重要：selector 的 saveAs 只能保存最终选择器（\${result.by}），不要保存 result.value.page/matchedPage。
建议写法：saveAs: { "selectors.xxx": "\${result.by}" }
`.trim();

	// ---- step id rules ----
	const idRulesBlock = `
────────────────────────────────────────────────────────
【输出必须包含 step id（强制）】
你输出的 JSON 顶层必须包含 "id"（string），用于宿主生成 step.id。
规则：
1) id 只能包含 [a-z0-9_]+；长度 ≤ 48。
2) 若已提供 usedStepIds：本次 id 必须不与其重复。
3) id 应反映动作语义：<type>_<target>，例如：
   - invoke_blockers_clear
   - dialog_dismiss
   - selector_publish_button
   - click_publish
   - wait_editor_visible
   - readElement_title_value
4) 若候选 id 已被占用：追加后缀 _2 / _3 递增直到不冲突。
`.trim();

	const abortBlock = `
────────────────────────────────────────────────────────
【abort 判定（必须非常严格，宁可不 abort）】
只有当你能从 url/title/html/截图推断“无论怎么做都不可能完成 goal”时才 abort，例如：
- 明确 404/Not Found/页面已下线/Access Denied 且无继续路径
- 明确地区/权限封锁且无替代入口且 goal 必须依赖被封锁内容
- 明确人机验证/强制登录且自动化无法继续：优先 ask_assist(waitUserAction=true)；只有用户介入也不可能完成时才 abort
abort.reason 必须具体（≤200字）：卡死点是什么、为什么无法绕过。
`.trim();

	// ---- decision rules ----
	const decision = [];

	decision.push(`
截图与 HTML 的使用原则
- 若提供了页面截图：遮挡层/可点击性/是否在首屏等“可视状态”以截图为准；选择器结构与属性以 html 为主。
- 若未提供截图：不要臆测可视状态，只基于 html/dialog/url/title 推断。
`.trim());

	if (has("dialog")) {
		decision.push(`
系统对话框优先
- LLMContext.dialog 存在时优先返回 dialog。
- 默认：alert→accept；confirm→dismiss（低风险继续/关闭才 accept）；prompt→仅必须输入才 accept+value。
`.trim());
	}

	if (has("invoke")) {
		decision.push(`
invoke（能力调用）使用规则
- 仅当“对话中已注入的裁剪版 rpa.mjs”明确提供了对应能力 key 与 args schema，才可 invoke。
- 遇到遮罩/弹窗/同意条款：优先 invoke 相关清理能力（若存在）；不要用 click 去赌“Accept/Close”。
`.trim());
	}

	if (has("ask_assist")) {
		decision.push(`
需要用户介入（登录/验证码/人机验证/订阅墙）
- 自动化无法继续：ask_assist；reason 写清用户要做什么；需要等待则 waitUserAction=true。
`.trim());
	}

	if (has("selector")) {
		decision.push(`
selector（不等待）
- 用于“确认元素存在/可见”或“拿到稳定 by 以复用”。
- 复用 selector：用 saveAs:{ "selectors.xxx":"\${result.by}" } 保存最终 by（不要保存 result.value）。
`.trim());
	}

	if (has("wait")) {
		decision.push(`
wait（会等待）
- 点击/提交后需要等变化：用 wait，比重复 click 更稳。
- 默认 state=visible scope=current；timeoutMs 建议 1200–2500；pollMs 100–250。
`.trim());
	}

	if (has("scroll_show")) {
		decision.push(`
scroll_show
- 目标可能在首屏外：先 scroll_show 露出（本回合只露出，不点不输）。
`.trim());
	}

	if (has("click")) {
		decision.push(`
click
- 列表→详情：点最匹配标题链接（intent:"open"）。
- 提交/发布/发送：intent:"submit"。
- 关闭/取消：intent:"dismiss"（确认不破坏目标）。
`.trim());
	}

	if (has("hover")) {
		decision.push(`
hover
- 明显 hover 才出现菜单/按钮：先 hover 父元素（本回合只 hover）。
`.trim());
	}

	if (has("input")) {
		decision.push(`
input（不定位）
- 必须先 click 获得焦点再 input。
- 长文本优先 paste；覆盖输入 clear:true；需要回车触发 pressEnter:true。
`.trim());
	}

	if (has("readElement")) {
		decision.push(`
readElement
- 需要知道输入框是否已有内容/读取提示：readElement pick:"value"/"text"。
`.trim());
	}

	if (has("setChecked")) {
		decision.push(`
setChecked（幂等）
- 需要把开关/checkbox 设为确定状态：用 setChecked，比 click 更稳。
`.trim());
	}

	if (has("setSelect")) {
		decision.push(`
setSelect（幂等）
- 设置 <select>/下拉项：用 setSelect（choice by value/label/index）。
`.trim());
	}

	if (has("uploadFile")) {
		decision.push(`
uploadFile
- goal 含“上传/附件/选择文件/导入”：优先 uploadFile。
- by 优先 input[type=file]；否则用“上传/选择文件/添加附件”按钮的稳定选择器或 XPath 文本匹配。
- files 数组就是本次上传集合。
`.trim());
	}

	if (has("readPage")) {
		decision.push(`
readPage
- 需要补充页面材料（html/article/screenshot）再决策：用 readPage（按需请求，避免过大）。
`.trim());
	}

	if (has("run_ai")) {
		decision.push(`
run_ai
- 需要总结/分类/结构化输出：用 run_ai。
- 产出必须是 JSON envelope（例如 {status:"ok",result} / {status:"error",reason}），不得夹杂多余文本。
- 同样不得修改 args/vars/opts/result；持久化只能通过 saveAs 写入 vars。
`.trim());
	}

	if (has("run_js")) {
		decision.push(`
run_js（只读兜底，v0.40）
- 必须显式写 scope 与 cache；默认 scope=page；agent 仅纯计算。
- 动态数据用 args（FlowVal）；禁止把动态值写进 code 文本。
- 仅做提取/计算/生成/定位/状态校验；严禁任何页面状态变化（见 run_js 强约束）。
- 优先用 selector/readElement 等声明式 action；run_js 仅在缺少可靠 by 或需轻量判断时使用。
`.trim());
	}

	decision.push(`
避免重复失败（基于 history）
- 若 history 显示同一 type+by 刚失败：下一步必须换策略或换 by；优先利用 history.result.reason/logs 来定位失败原因。
`.trim());

	const decisionBlock = `
────────────────────────────────────────────────────────
【决策准则（只用 url/title/html + dialog + 截图线索；goal/notes 已内置）】
${decision.join("\n\n")}
`.trim();

	const notesText = norm(notes);
	const notesBlock = notesText
	? `
────────────────────────────────────────────────────────
【重要说明】
${notesText}
`.trim()
	: `
────────────────────────────────────────────────────────
【额外说明】
暂无。
`.trim();

	// ---- Final prompt ----
	const prompt = `
Decide Next Atomic Action (RPA micro-decider, spec v0.40)

你是网页 RPA 的微决策器。给定当前环境 LLMContext，你必须返回恰好一个“原子动作”。
禁止多步、禁止规划多 step；严格按指定 JSON 输出，禁止额外文本/Markdown。

────────────────────────────────────────────────────────
【内置任务（goal）】
${goal.trim()}

${notesBlock}

${envBlock}

${historyBlock}

────────────────────────────────────────────────────────
【输入：LLMContext（极简）】
- url: string
- title: string
- html: string
- dialog?: { kind: "alert"|"confirm"|"prompt", text?: string }

【附件（非 JSON）】
- 可能有页面截图；若截图与 html 矛盾：遮挡层/可点性以截图为准；选择器细节以 html 为主。

${querySpecBlock}

${flowValBlock}

${readOnlyPersistenceBlock}

${queryByRulesBlock}

${has("invoke") ? "\n" + invokeFindRefBlock + "\n" : ""}
${abortBlock ? "\n" + abortBlock + "\n" : ""}
${has("run_js") ? "\n" + runJsBlock + "\n" : ""}
${saveAsBlock}

${idRulesBlock}

────────────────────────────────────────────────────────
【你可以返回的动作（只能返回其一）】
Action =
${actionLines.join("\n")}

${decisionBlock}

────────────────────────────────────────────────────────
【判定完成任务】
- 若你已完成 goal 或已取得 goal 需要的数据：返回 action.type="done"，conclusion 写出答案/成功状态总结。

────────────────────────────────────────────────────────
【输出格式（严格 JSON，禁止多余文本）】
{
  "id": string,                    // 必填：不重复 step id（见规则）
  "action": Action,                // 必填：只能是上面 Union 之一
  "saveAs": string | object | null,// 可选：写 vars（selector 建议保存 \${result.by}）
  "reason": string,                // ≤200字
  "summary": string                // ≤200字
}
`.trim();

	return prompt;
}
export {parseFlowVal,runBranchAction,execRunJsAction,briefJSON,buildRpaStepDeciderPrompt};