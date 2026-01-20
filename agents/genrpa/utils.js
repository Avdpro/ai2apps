import pathLib from "path";
import fsp from 'fs/promises';
import {URL,fileURLToPath} from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = pathLib.dirname(__filename);

function urlToJsonName(url) {
	const maxLen = 200; // 防止文件名太长
	let s = String(url)
	.trim()
	.replace(/^https?:\/\//i, '')        // 去掉协议
	.replace(/[^a-zA-Z0-9]+/g, '_')      // 非字母数字统统变成下划线
	.replace(/^_+|_+$/g, '');            // 去掉首尾多余下划线
	if (!s) s = 'url';
	if (s.length > maxLen) s = s.slice(0, maxLen);
	return s + '.json';
}

async function readJson(filePath) {
	try{
		return JSON.parse(await fsp.readFile(filePath, 'utf8'));
	}catch(err){
		return null;
	}
}

async function saveJson(filePath, data) {
	const dir = pathLib.dirname(filePath);
	if (dir && dir !== '.') {
		await fsp.mkdir(dir, { recursive: true });
	}
	const text = JSON.stringify(data, null, "\t");
	await fsp.writeFile(filePath, text, 'utf8');
}

function resolveUrl(currentUrl, targetUrl) {
	if (!targetUrl) return currentUrl;
	try {
		return new URL(targetUrl, currentUrl).toString();
	} catch (err) {
		return targetUrl;
	}
}

function guessMimeFromExt(filePath) {
	const ext = pathLib.extname(filePath).toLowerCase();
	switch (ext) {
		case ".png": return "image/png";
		case ".jpg":
		case ".jpeg": return "image/jpeg";
		case ".gif": return "image/gif";
		case ".webp": return "image/webp";
		case ".svg": return "image/svg+xml";
		case ".ico": return "image/x-icon";
		case ".bmp": return "image/bmp";
		case ".txt": return "text/plain;charset=utf-8";
		case ".html": return "text/html;charset=utf-8";
		case ".css": return "text/css;charset=utf-8";
		case ".js": return "text/javascript;charset=utf-8";
		case ".json": return "application/json;charset=utf-8";
		case ".pdf": return "application/pdf";
		default: return "application/octet-stream";
	}
}

//----------------------------------------------------------------------------
let deepEq,briefJSON,expandDottedKeys;
{
	deepEq=function(a, b, opts) {
		opts = opts || {};
		const o = {
			// 默认“松”：不要求同 prototype；但默认仍要求同内部类型标签（Date/RegExp/Map/Set 等不会和普通对象混淆）
			strictProto: !!opts.strictProto,
			checkTag: opts.checkTag !== false, // default true

			// SameValueZero：NaN==NaN；-0 和 0 视为相等（比 Object.is 更“松”）
			sameValueZero: opts.sameValueZero !== false, // default true

			// key 列表：enumerable(默认) / all(含不可枚举+symbol)
			keys: opts.keys || "enumerable",
			includeSymbols: opts.includeSymbols !== false, // default true

			// Set/Map：不要求顺序
			setOrderless: opts.setOrderless !== false, // default true
			mapOrderless: opts.mapOrderless !== false, // default true

			// Set 元素如何匹配：deep / ref
			setMatch: opts.setMatch || "deep",

			// Map key 如何匹配：deep / ref
			mapKeyMatch: opts.mapKeyMatch || "deep",

			// 是否比较函数内容（默认不比较，只能同引用）
			compareFunctions: !!opts.compareFunctions
		};

		return _eq(a, b, o, new WeakMap());
	}
	function _eq(a, b, o, seen) {
		if (a === b) return true;
		if (o.sameValueZero) {
			// SameValueZero：NaN 相等，-0/0 相等
			if (a !== a && b !== b) return true;
		} else {
			if (Object.is(a, b)) return true;
		}

		if (a == null || b == null) return false;

		const ta = typeof a;
		const tb = typeof b;
		if (ta !== tb) return false;

		if (ta !== "object") {
			if (ta === "function") {
				if (a === b) return true;
				if (!o.compareFunctions) return false;
				return String(a) === String(b);
			}
			return false;
		}

		// Buffer (Node)
		if (typeof Buffer !== "undefined" && Buffer.isBuffer(a) || Buffer.isBuffer(b)) {
			if (!(typeof Buffer !== "undefined" && Buffer.isBuffer(a) && Buffer.isBuffer(b))) return false;
			return a.equals(b);
		}

		// Date / RegExp
		if (a instanceof Date || b instanceof Date) {
			return (a instanceof Date) && (b instanceof Date) && a.getTime() === b.getTime();
		}
		if (a instanceof RegExp || b instanceof RegExp) {
			return (a instanceof RegExp) && (b instanceof RegExp) && a.source === b.source && a.flags === b.flags;
		}

		// ArrayBuffer
		if (a instanceof ArrayBuffer || b instanceof ArrayBuffer) {
			if (!(a instanceof ArrayBuffer && b instanceof ArrayBuffer)) return false;
			if (a.byteLength !== b.byteLength) return false;
			return _bytesEq(new Uint8Array(a), new Uint8Array(b));
		}

		// TypedArray / DataView
		if (ArrayBuffer.isView(a) || ArrayBuffer.isView(b)) {
			if (!(ArrayBuffer.isView(a) && ArrayBuffer.isView(b))) return false;
			if (a.constructor !== b.constructor) return false;
			if (a.byteLength !== b.byteLength) return false;
			return _bytesEq(
				new Uint8Array(a.buffer, a.byteOffset, a.byteLength),
				new Uint8Array(b.buffer, b.byteOffset, b.byteLength)
			);
		}

		// 循环引用：a -> b 的映射
		const prev = seen.get(a);
		if (prev !== undefined) return prev === b;
		seen.set(a, b);

		// Map
		if (a instanceof Map || b instanceof Map) {
			if (!(a instanceof Map && b instanceof Map)) return false;
			if (a.size !== b.size) return false;

			// key 为原始值时可直接 b.has(k)，对象 key 则做 deep/ref 匹配
			const used = o.mapOrderless ? new Set() : null;

			for (const [ka, va] of a) {
				if (_isPrim(ka)) {
					if (!b.has(ka)) return false;
					if (!_eq(va, b.get(ka), o, seen)) return false;
				} else {
					let ok = false;
					let idx = 0;
					for (const [kb, vb] of b) {
						if (used && used.has(idx)) { idx++; continue; }
						if (_matchKey(ka, kb, o, seen) && _eq(va, vb, o, seen)) {
							if (used) used.add(idx);
							ok = true;
							break;
						}
						idx++;
					}
					if (!ok) return false;
				}
			}
			return true;
		}

		// Set
		if (a instanceof Set || b instanceof Set) {
			if (!(a instanceof Set && b instanceof Set)) return false;
			if (a.size !== b.size) return false;

			// 原始值：直接 has；对象：O(n^2) 匹配（默认 deep）
			const arrB = Array.from(b);
			const used = new Array(arrB.length).fill(false);

			for (const va of a) {
				if (_isPrim(va)) {
					if (!b.has(va)) return false;
				} else {
					let ok = false;
					for (let i = 0; i < arrB.length; i++) {
						if (used[i]) continue;
						if (_matchSetVal(va, arrB[i], o, seen)) {
							used[i] = true;
							ok = true;
							break;
						}
					}
					if (!ok) return false;
				}
			}
			return true;
		}

		// prototype / tag
		if (o.strictProto) {
			if (Object.getPrototypeOf(a) !== Object.getPrototypeOf(b)) return false;
		} else if (o.checkTag) {
			if (Object.prototype.toString.call(a) !== Object.prototype.toString.call(b)) return false;
		}

		// 普通对象 / 数组：比较 keys + 递归值
		const ka = _keys(a, o);
		const kb = _keys(b, o);
		if (ka.length !== kb.length) return false;

		for (const k of ka) {
			if (!Object.prototype.hasOwnProperty.call(b, k)) return false;
		}
		for (const k of ka) {
			if (!_eq(a[k], b[k], o, seen)) return false;
		}
		return true;
	}
	function _matchKey(ka, kb, o, seen) {
		if (o.mapKeyMatch === "ref") return ka === kb;
		return _eq(ka, kb, o, seen);
	}
	function _matchSetVal(a, b, o, seen) {
		if (o.setMatch === "ref") return a === b;
		return _eq(a, b, o, seen);
	}
	function _keys(obj, o) {
		if (o.keys === "all") return Reflect.ownKeys(obj);

		// enumerable
		const ks = Object.keys(obj);
		if (!o.includeSymbols) return ks;

		const syms = Object.getOwnPropertySymbols(obj);
		for (const s of syms) {
			const d = Object.getOwnPropertyDescriptor(obj, s);
			if (d && d.enumerable) ks.push(s);
		}
		return ks;
	}
	function _bytesEq(a, b) {
		for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
		return true;
	}
	function _isPrim(x) {
		return x === null || (typeof x !== "object" && typeof x !== "function");
	}


	/**
	 * briefJSON(val, opts) -> string
	 * 生成可读的“缩略 JSON 风格”字符串（不保证严格 JSON 语义）。
	 */
	briefJSON=function(val, opts) {
		opts = opts || {};
		let maxDepth = (opts.maxDepth ?? 4);
		let maxString = (opts.maxString ?? 200);
		let maxElements = (opts.maxElements ?? 20);
		let maxKeys = (opts.maxKeys ?? 50);          // 额外：对象键过多时截断
		let sortKeys = !!opts.sortKeys;              // 额外：是否排序 key
		let pretty = !!opts.pretty;                  // 额外：是否缩进
		let indent = (opts.indent ?? 2);

		let seen = new WeakMap(); // obj -> path string

		function truncStr(s) {
			if (s.length <= maxString) return s;
			return s.slice(0, maxString) + "...more...";
		}

		function tag(s) {
			// 用字符串占位，保持是 JSON-safe 的 string
			return `[${s}]`;
		}

		function isPlainObject(o) {
			if (o === null || typeof o !== "object") return false;
			let p = Object.getPrototypeOf(o);
			return p === Object.prototype || p === null;
		}

		function toJSONSafePrimitive(x) {
			// 把 JSON 不支持的 primitive 做可读占位
			let t = typeof x;
			if (x === undefined) return tag("Undefined");
			if (t === "function") return tag(`Function${x.name ? ":" + x.name : ""}`);
			if (t === "symbol") return tag(`Symbol${x.description ? ":" + x.description : ""}`);
			if (t === "bigint") return tag(`BigInt:${x.toString()}n`);
			if (t === "number") {
				if (Number.isNaN(x)) return tag("NaN");
				if (x === Infinity) return tag("Infinity");
				if (x === -Infinity) return tag("-Infinity");
				return x;
			}
			if (t === "string") return truncStr(x);
			return x; // boolean, null
		}

		function brief(x, depth, path) {
			// primitives
			if (x === null || typeof x !== "object") {
				return toJSONSafePrimitive(x);
			}

			// circular / repeated reference
			let prevPath = seen.get(x);
			if (prevPath) {
				return tag(`Circular~${prevPath}`);
			}
			seen.set(x, path);

			// depth limit
			if (depth >= maxDepth) {
				if (Array.isArray(x)) return tag("...array...");
				return tag("...object...");
			}

			// special objects
			if (x instanceof Date) return tag(`Date:${isNaN(x.getTime()) ? "Invalid" : x.toISOString()}`);
			if (x instanceof RegExp) return tag(`RegExp:${x.toString()}`);
			if (x instanceof Error) return tag(`Error:${x.name}:${truncStr(String(x.message || ""))}`);

			// ArrayBuffer / TypedArray / Buffer (Node)
			if (typeof Buffer !== "undefined" && Buffer.isBuffer?.(x)) {
				return tag(`Buffer:${x.length}b`);
			}
			if (ArrayBuffer.isView(x) && !(x instanceof DataView)) {
				return tag(`${x.constructor?.name || "TypedArray"}:${x.length}`);
			}
			if (x instanceof ArrayBuffer) {
				return tag(`ArrayBuffer:${x.byteLength}b`);
			}

			// Map / Set
			if (x instanceof Map) {
				// 展开成数组形式，但受 maxElements 限制
				let arr = [];
				let i = 0;
				for (let [k, v] of x.entries()) {
					if (i >= maxElements) break;
					arr.push([brief(k, depth + 1, path + `.mapKey${i}`), brief(v, depth + 1, path + `.mapVal${i}`)]);
					i++;
				}
				let more = x.size > maxElements ? tag("...more...") : null;
				// 让输出更像对象：{"$map":[[k,v],...],"$size":N}
				return {
					$map: arr,
					$size: x.size,
					...(more ? { $more: more } : null),
				};
			}

			if (x instanceof Set) {
				let arr = [];
				let i = 0;
				for (let v of x.values()) {
					if (i >= maxElements) break;
					arr.push(brief(v, depth + 1, path + `.set${i}`));
					i++;
				}
				let more = x.size > maxElements ? tag("...more...") : null;
				return {
					$set: arr,
					$size: x.size,
					...(more ? { $more: more } : null),
				};
			}

			// Array
			if (Array.isArray(x)) {
				let n = x.length;
				let take = Math.min(n, maxElements);
				let out = new Array(take);
				for (let i = 0; i < take; i++) {
					out[i] = brief(x[i], depth + 1, path + `[${i}]`);
				}
				if (n > maxElements) out.push(tag("...more..."));
				return out;
			}

			// Object
			// 如果不是 plain object，尽量保留类型信息（否则 class 实例 stringify 可能很奇怪）
			if (!isPlainObject(x)) {
				// 仅展示可枚举属性，但带上类型标签
				let obj = { $type: x.constructor?.name || "Object" };
				// 再把属性按规则摘一些
				let keys = Object.keys(x);
				if (sortKeys) keys.sort();
				let take = Math.min(keys.length, maxKeys);
				for (let i = 0; i < take; i++) {
					let k = keys[i];
					obj[k] = brief(x[k], depth + 1, path + "." + k);
				}
				if (keys.length > maxKeys) obj.$more = tag("...more...");
				return obj;
			}

			let keys = Object.keys(x);
			if (sortKeys) keys.sort();
			let take = Math.min(keys.length, maxKeys);

			let out = {};
			for (let i = 0; i < take; i++) {
				let k = keys[i];
				out[k] = brief(x[k], depth + 1, path + "." + k);
			}
			if (keys.length > maxKeys) out.$more = tag("...more...");
			return out;
		}

		let briefVal = brief(val, 0, "$");
		// 最终 stringify
		// 注意：briefVal 内部已经把不支持的类型转成 string/tag 或结构对象
		return JSON.stringify(briefVal, null, pretty ? indent : 0);
	}
	
	/**
	 * expandDottedKeys(obj, opts) - 扩展带点号的对象键为多层嵌套结构（通常用于配置/表单扁平化后的还原）。
	 *
	 * @param {Object} obj 输入对象（必须为普通对象）
	 * @param {Object} [opts]
	 *   - sep (默认 '.')         : key 分隔符
	 *   - overwrite (默认 false) : 非对象冲突路径时是否强行覆盖为对象（默认安全模式，冲突时报错）
	 *   - keepDotted (默认 false): 是否保留原始带点 key
	 *
	 * @returns {Object} 展开后的嵌套对象
	 * @throws {TypeError|Error} 参数错误或路径冲突时抛异常（除非 overwrite=true）
	 */
	expandDottedKeys=function(obj, opts) {
		// opts:
		// - sep: 分隔符，默认 '.'
		// - overwrite: true 时允许把非对象/数组强行覆盖成对象继续往下写；默认 false（更安全）
		// - keepDotted: true 时保留原始带点号 key；默认 false
		if(!opts) opts = {};
		let sep = (opts.sep !== undefined) ? opts.sep : '.';
		let overwrite = !!opts.overwrite;
		let keepDotted = !!opts.keepDotted;

		if(obj === null || typeof obj !== "object" || Array.isArray(obj)){
			throw new TypeError("expandDottedKeys: obj must be a plain object");
		}

		let out = {};
		let keys = Object.keys(obj);

		for(let i=0;i<keys.length;i++){
			let k = keys[i];
			let v = obj[k];

			if(keepDotted && k.indexOf(sep) >= 0){
				out[k] = v;
			}

			if(k.indexOf(sep) < 0){
				// 普通 key 直接赋值（后面如果出现 dotted key 需要写到 out[k] 里，会进行冲突处理）
				out[k] = v;
				continue;
			}

			let parts = k.split(sep).filter(p => p.length>0);
			if(parts.length === 0){
				out[k] = v;
				continue;
			}

			let cur = out;
			for(let j=0;j<parts.length;j++){
				let p = parts[j];
				let isLeaf = (j === parts.length - 1);

				if(isLeaf){
					cur[p] = v;
				}else{
					let next = cur[p];
					if(next === undefined){
						next = {};
						cur[p] = next;
					}else if(next === null || typeof next !== "object" || Array.isArray(next)){
						// 冲突：例如 out.blocks 原来是 123，但现在需要 out.blocks.xxx
						if(!overwrite){
							// 安全模式：直接跳过或抛错都行；这里选择抛错更明显
							throw new Error("expandDottedKeys: path conflict at '" + parts.slice(0, j+1).join(sep) + "'");
						}
						next = {};
						cur[p] = next;
					}
					cur = next;
				}
			}
		}

		return out;
	}
}

//----------------------------------------------------------------------------
function getLan(){
	const htmlLang = document.documentElement && document.documentElement.lang;
	if (htmlLang && htmlLang.trim()) return htmlLang.trim();
	// <meta http-equiv="content-language" content="en">
	const metaHttp = document.querySelector('meta[http-equiv="content-language" i]');
	const metaHttpLang = metaHttp && metaHttp.getAttribute('content');
	if (metaHttpLang && metaHttpLang.trim()) return metaHttpLang.trim();
	// <meta name="language" content="en">
	const metaName = document.querySelector('meta[name="language" i]');
	const metaNameLang = metaName && metaName.getAttribute('content');
	if (metaNameLang && metaNameLang.trim()) return metaNameLang.trim();
	return "web";
}

//----------------------------------------------------------------------------
let readRule,saveRule;
{
	readRule=async function(session,page,key){
		let url,lan,hostname,rules;
		url=await page.url();
		hostname=(() => { try { return new URL(url).hostname; } catch (e) { return ""; } })();
		lan=await page.callFunction(getLan,[]);
		key=lan+"."+key;
		if(hostname){
			let obj,pts,ptKey;
			try{
				let jsonPath=pathLib.join(__dirname,"rules",urlToJsonName(hostname));
				rules=(await readJson(jsonPath))||{};
			}catch(error){
				console.log("Read Rules error: ",error);
				rules={};
			}
			obj=rules;
			pts=key.split(".");
			for(ptKey of pts){
				obj=obj[ptKey];
				if(!obj){
					return null;
				}
			}
			//TODO: Check system rules:

			if(("value" in obj) && ("time" in obj)){
				return obj.value;
			}
			return obj;
		}
	}

	saveRule=async function(session,page,key,value){
		let url,lan,hostname,rules;
		url=await page.url();
		hostname=(() => { try { return new URL(url).hostname; } catch (e) { return ""; } })();
		lan=await page.callFunction(getLan,[]);
		key=lan+"."+key;
		if(hostname){
			let jsonPath,obj,pObj,pts,ptKey,valKey;
			try{
				jsonPath=pathLib.join(__dirname,"rules",urlToJsonName(hostname));
				rules=(await readJson(jsonPath))||{};
			}catch(error){
				console.log("Read Rules error: ",error);
				rules={};
			}
			obj=rules;
			pts=key.split(".");
			valKey=pts.pop();
			for(ptKey of pts){
				pObj=obj;
				obj=pObj[ptKey];
				if(!obj){
					obj=pObj[ptKey]={};
				}
			}
			if(!obj[valKey] || !deepEq(obj[valKey].value,value)){
				obj[valKey]={value:value,time:Date.now()};
				await saveJson(jsonPath,rules);
			}
			return rules;
		}
		return null;
	}
}

//----------------------------------------------------------------------------
/**
 * Read file as DataURL.
 * @param {string} p Absolute path, or path relative to current file.
 * @param {{ mime?: string }} [opts]
 * @returns {Promise<string>} data:<mime>;base64,<...>
 */
async function readFileAsDataURL(p, opts = {}) {
	if (!p || typeof p !== "string") {
		throw new TypeError("readFileAsDataURL: path must be a non-empty string");
	}
	const resolvedPath = pathLib.isAbsolute(p) ? p : pathLib.resolve(__dirname, p);
	const buf = await fsp.readFile(resolvedPath);
	const mime = (opts.mime && String(opts.mime).trim()) || guessMimeFromExt(resolvedPath);
	const b64 = buf.toString("base64");
	return `data:${mime};base64,${b64}`;
}

//----------------------------------------------------------------------------
let ai2appsPrompt,ai2appsTip,ai2appsTipDismiss;
{
	ai2appsPrompt=function(text, opts = {}) {
		// opts:
		// - caption: string = "AI2Apps"
		// - icon: DataURL|string|null = null
		// - okText: string = "OK"
		// - cancelText: string = "Cancel"
		// - showCancel: boolean = false
		// - mask: css-color|string|false = "rgba(0,0,0,0.35)"
		// - iconSize: number = 88 (px)
		// - buttonMinWidth: number = 96 (px)
		//
		// Return:
		// - showCancel=false  -> Promise<{ok:true, action:string}>
		// - showCancel=true   -> Promise<boolean> (true=OK/Enter, false=Cancel/Esc)

		text = (text == null) ? "" : String(text);
		opts = (opts && typeof opts === "object") ? opts : {};

		const caption = (opts.caption == null || opts.caption === "") ? "AI2Apps" : String(opts.caption);
		const icon = (opts.icon == null) ? null : String(opts.icon);
		const okText = (opts.okText == null || opts.okText === "") ? "OK" : String(opts.okText);
		const cancelText = (opts.cancelText == null || opts.cancelText === "") ? "Cancel" : String(opts.cancelText);
		const showCancel = !!opts.showCancel;
		const mask = (opts.mask === undefined) ? "rgba(0,0,0,0.35)" : opts.mask;

		const iconSize = Number.isFinite(opts.iconSize) ? Math.max(24, opts.iconSize) : 88;
		const buttonMinWidth = Number.isFinite(opts.buttonMinWidth) ? Math.max(40, opts.buttonMinWidth) : 96;

		const returnBoolean = showCancel;

		return new Promise((resolve) => {
			try {
				const doc = document;
				const body = doc.body || doc.documentElement;
				if (!body) return resolve(returnBoolean ? false : { ok: false, reason: "no-body" });

				const prev = doc.getElementById("__ai2apps_prompt_root__");
				if (prev) prev.remove();

				const root = doc.createElement("div");
				root.id = "__ai2apps_prompt_root__";
				root.style.position = "fixed";
				root.style.left = "0";
				root.style.top = "0";
				root.style.width = "100vw";
				root.style.height = "100vh";
				root.style.zIndex = "2147483647";
				root.style.pointerEvents = "none";

				if (mask !== false) {
					const overlay = doc.createElement("div");
					overlay.style.position = "absolute";
					overlay.style.left = "0";
					overlay.style.top = "0";
					overlay.style.width = "100%";
					overlay.style.height = "100%";
					overlay.style.background =
						(typeof mask === "string" && mask.trim()) ? mask : "rgba(0,0,0,0.35)";
					overlay.style.pointerEvents = "auto";
					overlay.addEventListener("wheel", (e) => e.preventDefault(), { passive: false });
					overlay.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
					root.appendChild(overlay);
				}

				const dlg = doc.createElement("div");
				dlg.setAttribute("role", "dialog");
				dlg.setAttribute("aria-modal", "true");
				dlg.style.position = "absolute";
				dlg.style.left = "50%";
				dlg.style.top = "30%";
				dlg.style.transform = "translate(-50%, -50%)";
				dlg.style.maxWidth = "min(760px, calc(100vw - 32px))";
				dlg.style.width = "min(600px, calc(100vw - 32px))";
				dlg.style.background = "#fff";
				dlg.style.color = "#111";
				dlg.style.border = "3px solid #111";
				dlg.style.borderRadius = "12px";
				dlg.style.boxShadow = "0 10px 28px rgba(0,0,0,0.22)";
				dlg.style.pointerEvents = "auto";
				dlg.style.userSelect = "none";

				const font = "system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";
				const thinBorder = "1px solid rgba(0,0,0,0.28)";

				// Title bar (16px)
				const titleBar = doc.createElement("div");
				titleBar.style.display = "flex";
				titleBar.style.alignItems = "center";
				titleBar.style.justifyContent = "flex-start";
				titleBar.style.padding = "10px 12px";
				titleBar.style.borderBottom = thinBorder;
				titleBar.style.cursor = "move";
				titleBar.style.fontFamily = font;
				titleBar.style.fontWeight = "800";
				titleBar.style.fontSize = "16px"; // <- bigger
				titleBar.style.letterSpacing = "0.2px";

				const capEl = doc.createElement("div");
				capEl.textContent = caption;
				capEl.style.whiteSpace = "nowrap";
				capEl.style.overflow = "hidden";
				capEl.style.textOverflow = "ellipsis";
				capEl.style.width = "100%";
				titleBar.appendChild(capEl);

				// Content
				const content = doc.createElement("div");
				content.style.display = "flex";
				content.style.alignItems = "flex-start";
				content.style.gap = "14px";
				content.style.padding = "16px 16px 12px 16px";
				content.style.fontFamily = font;
				content.style.userSelect = "text";

				const iconWrap = doc.createElement("div");
				iconWrap.style.flex = "0 0 auto";
				iconWrap.style.width = `${iconSize}px`;
				iconWrap.style.height = `${iconSize}px`;
				iconWrap.style.marginTop = "2px";
				iconWrap.style.display = icon ? "flex" : "none";
				iconWrap.style.alignItems = "center";
				iconWrap.style.justifyContent = "center";

				if (icon) {
					const img = doc.createElement("img");
					img.alt = "";
					img.src = icon;
					img.style.width = `${iconSize}px`;
					img.style.height = `${iconSize}px`;
					img.style.objectFit = "contain";
					img.style.borderRadius = "12px";
					img.style.border = "none";
					iconWrap.appendChild(img);
				}

				// Text (14px)
				const textEl = doc.createElement("div");
				textEl.textContent = text;
				textEl.style.whiteSpace = "pre-wrap";
				textEl.style.lineHeight = "1.35";
				textEl.style.fontSize = "14px"; // <- set to 14px (slightly larger than previous 14? now explicit)
				textEl.style.fontWeight = "600";
				textEl.style.color = "#111";
				textEl.style.flex = "1 1 auto";
				textEl.style.userSelect = "text";

				content.appendChild(iconWrap);
				content.appendChild(textEl);

				// Footer buttons (reduced vertical padding)
				const footer = doc.createElement("div");
				footer.style.display = "flex";
				footer.style.justifyContent = "flex-end";
				footer.style.gap = "10px";
				footer.style.padding = "0 16px 16px 16px";

				const baseBtnStyle = (btn, primary) => {
					btn.style.border = thinBorder;
					btn.style.background = "#fff";
					btn.style.color = "#111";
					btn.style.borderRadius = "12px";
					btn.style.padding = "6px 14px";      // <- reduced height
					btn.style.minWidth = `${buttonMinWidth}px`;
					btn.style.textAlign = "center";
					btn.style.fontFamily = font;
					btn.style.fontSize = "14px";
					btn.style.fontWeight = "800";
					btn.style.cursor = "pointer";
					if (primary) btn.style.boxShadow = "0 3px 0 rgba(0,0,0,0.16)";
					btn.addEventListener("mouseenter", () => (btn.style.background = "#f5f5f5"));
					btn.addEventListener("mouseleave", () => (btn.style.background = "#fff"));
				};

				const cancelBtn = doc.createElement("button");
				cancelBtn.type = "button";
				cancelBtn.textContent = cancelText;
				baseBtnStyle(cancelBtn, false);

				const okBtn = doc.createElement("button");
				okBtn.type = "button";
				okBtn.textContent = okText;
				baseBtnStyle(okBtn, true);

				if (showCancel) footer.appendChild(cancelBtn);
				footer.appendChild(okBtn);

				dlg.appendChild(titleBar);
				dlg.appendChild(content);
				dlg.appendChild(footer);

				root.appendChild(dlg);
				body.appendChild(root);

				okBtn.focus({ preventScroll: true });

				let closed = false;
				const cleanup = (valOrObj) => {
					if (closed) return;
					closed = true;
					doc.removeEventListener("keydown", onKeyDown, true);
					if (root && root.parentNode) root.parentNode.removeChild(root);
					resolve(valOrObj);
				};

				const closeOk = () => (returnBoolean ? cleanup(true) : cleanup({ ok: true, action: "ok" }));
				const closeCancel = (reason) => (returnBoolean ? cleanup(false) : cleanup({ ok: true, action: reason || "closed" }));

				const onKeyDown = (e) => {
					if (!e) return;
					if (e.key === "Escape" || e.key === "Esc") {
						e.preventDefault();
						e.stopPropagation();
						closeCancel("esc");
						return;
					}
					if (e.key === "Enter") {
						e.preventDefault();
						e.stopPropagation();
						closeOk();
						return;
					}
				};

				okBtn.addEventListener("click", closeOk);
				cancelBtn.addEventListener("click", () => closeCancel("cancel"));
				doc.addEventListener("keydown", onKeyDown, true);

				// Drag behavior
				let dragging = false;
				let startX = 0, startY = 0;
				let startLeft = 0, startTop = 0;

				const px = (v) => (Number.isFinite(v) ? `${v}px` : "0px");
				const getDlgRect = () => dlg.getBoundingClientRect();

				const onPointerMove = (ev) => {
					if (!dragging) return;

					const dx = ev.clientX - startX;
					const dy = ev.clientY - startY;

					const vw = window.innerWidth || doc.documentElement.clientWidth || 0;
					const vh = window.innerHeight || doc.documentElement.clientHeight || 0;

					const rect = getDlgRect();
					const w = rect.width, h = rect.height;

					let newLeft = startLeft + dx;
					let newTop = startTop + dy;

					const margin = 12;
					newLeft = Math.max(margin, Math.min(newLeft, Math.max(margin, vw - w - margin)));
					newTop = Math.max(margin, Math.min(newTop, Math.max(margin, vh - h - margin)));

					dlg.style.left = px(newLeft);
					dlg.style.top = px(newTop);
					dlg.style.transform = "none";
				};

				const onPointerUp = () => {
					if (!dragging) return;
					dragging = false;
					window.removeEventListener("pointermove", onPointerMove, true);
					window.removeEventListener("pointerup", onPointerUp, true);
					titleBar.style.cursor = "move";
				};

				titleBar.addEventListener(
					"pointerdown",
					(ev) => {
						ev.preventDefault();
						ev.stopPropagation();

						const rect = getDlgRect();
						dragging = true;
						startX = ev.clientX;
						startY = ev.clientY;
						startLeft = rect.left;
						startTop = rect.top;

						dlg.style.left = px(startLeft);
						dlg.style.top = px(startTop);
						dlg.style.transform = "none";
						titleBar.style.cursor = "grabbing";

						window.addEventListener("pointermove", onPointerMove, true);
						window.addEventListener("pointerup", onPointerUp, true);
					},
					true
				);

			} catch (err) {
				resolve(returnBoolean ? false : { ok: false, reason: String(err && err.message ? err.message : err) });
			}
		});
	}

	// ai2appsTip(text, opts) / ai2appsTipDismiss(idOrAll)
	// --------------------------------------------------
	// Tip: 顶部/底部悬浮提示，带图标文字；不影响页面操作；不可点击（点击穿透）；可取消；可自动消失；支持多条叠加。
	// 额外功能：鼠标移动到 tip 区域时，tip 变得非常透明（不依赖 hover 事件，仍保持 pointer-events:none）。
	//
	// 使用：
	//   const r = await ai2appsTip("Saved!", { position:"top", timeout: 1800 });
	//   ai2appsTipDismiss(r.id);        // 关闭某条
	//   ai2appsTipDismiss(true);        // 关闭全部 + 移除 root + 卸载事件
	//
	// opts:
	// - id: string|null = null                 // 指定 id（用于更新/覆盖），不传则自动生成并返回
	// - position: "top"|"bottom" = "top"
	// - caption: string|null = null            // 可选小标题
	// - icon: DataURL|string|null = null       // 图标
	// - iconSize: number = 22                  // px
	// - maxWidth: number = 760                 // px
	// - offset: number = 14                    // 距离顶部/底部的边距 px
	// - zIndex: number = 2147483646
	// - timeout: number|0 = 0                  // 自动消失(ms)，0表示不自动消失
	// - theme: "light"|"dark"|"auto" = "auto"
	// - fontSize: number = 13
	// - weight: number = 700
	// - opacity: number = 0.98
	// - lineClamp: number|0 = 3                // 0 不截断，否则多行省略
	// - stack: boolean = true                  // true: 多条叠加；false: 同 position 只保留一个
	// - hoverFade: boolean = true              // 鼠标在 tip 区域时变透明（不拦截点击）
	// - hoverOpacity: number = 0.12            // hoverFade 时的透明度
	//
	// return: Promise<{ ok:true, id:string, action:"shown"|"updated" }>
	ai2appsTip=function(text, opts = {}) {
		function ai2appsTipDismiss(idOrAll) {
			const ROOT_ID = "__ai2apps_tip_root__";
			const TIMERS_KEY = "__ai2apps_tip_timers__";
			const HOVER_KEY = "__ai2apps_tip_hover_fader__";

			const esc = (s) => {
				try {
					return (window.CSS && typeof CSS.escape === "function") ? CSS.escape(s) : String(s).replace(/["\\]/g, "\\$&");
				} catch {
					return String(s).replace(/["\\]/g, "\\$&");
				}
			};

			const uninstallHover = (root) => {
				if (!root) return;
				const h = root[HOVER_KEY];
				if (h && h.onMove) {
					document.removeEventListener("mousemove", h.onMove, true);
					document.removeEventListener("pointermove", h.onMove, true);
				}
				try { delete root[HOVER_KEY]; } catch {}
			};

			const clearAllTimers = (root) => {
				if (!root) return;
				const timers = (root[TIMERS_KEY] && typeof root[TIMERS_KEY] === "object") ? root[TIMERS_KEY] : null;
				if (!timers) return;
				for (const k of Object.keys(timers)) {
					clearTimeout(timers[k]);
					delete timers[k];
				}
			};

			const closeEl = (el) => {
				if (!el) return;
				el.style.transition = "opacity 120ms ease, transform 120ms ease";
				el.style.opacity = "0";
				el.style.transform = "translateY(-6px)";
				setTimeout(() => {
					if (el && el.parentNode) el.parentNode.removeChild(el);
				}, 140);
			};

			try {
				const doc = document;
				const root = doc.getElementById(ROOT_ID);
				if (!root) return { ok: true, action: "none" };

				const timers = (root[TIMERS_KEY] && typeof root[TIMERS_KEY] === "object") ? root[TIMERS_KEY] : null;

				// Dismiss ALL + remove root (explicit)
				if (idOrAll === true) {
					const tips = Array.from(root.querySelectorAll("[data-ai2apps-tip='1']"));
					tips.forEach(closeEl);

					clearAllTimers(root);
					uninstallHover(root);

					setTimeout(() => {
						const r = doc.getElementById(ROOT_ID);
						if (r && r.parentNode) r.parentNode.removeChild(r);
					}, 180);

					return { ok: true, action: "dismissed-all-removed-root" };
				}

				// Dismiss ONE
				if (typeof idOrAll === "string" && idOrAll.trim()) {
					const id = idOrAll.trim();
					const el = root.querySelector(`[data-ai2apps-tip='1'][data-ai2apps-tip-id="${esc(id)}"]`);

					if (timers && timers[id]) {
						clearTimeout(timers[id]);
						delete timers[id];
					}

					closeEl(el);

					// tidy: after removal, if no tips remain -> uninstall + remove root
					setTimeout(() => {
						const r = doc.getElementById(ROOT_ID);
						if (!r) return;
						const stillHas = r.querySelector("[data-ai2apps-tip='1']");
						if (stillHas) return;

						clearAllTimers(r);
						uninstallHover(r);
						if (r.parentNode) r.parentNode.removeChild(r);
					}, 220);

					return { ok: true, action: "dismissed-one", id };
				}

				// Dismiss ALL (default): close all; if empty -> uninstall + remove root
				const tips = Array.from(root.querySelectorAll("[data-ai2apps-tip='1']"));
				tips.forEach(closeEl);
				clearAllTimers(root);

				setTimeout(() => {
					const r = doc.getElementById(ROOT_ID);
					if (!r) return;
					const stillHas = r.querySelector("[data-ai2apps-tip='1']");
					if (stillHas) return;

					uninstallHover(r);
					if (r.parentNode) r.parentNode.removeChild(r);
				}, 220);

				return { ok: true, action: "dismissed-all" };
			} catch (err) {
				return { ok: false, action: "error", reason: String(err && err.message ? err.message : err) };
			}
		}
		text = (text == null) ? "" : String(text);
		opts = (opts && typeof opts === "object") ? opts : {};

		const doc = document;
		const body = doc.body || doc.documentElement;

		const ROOT_ID = "__ai2apps_tip_root__";
		const TIMERS_KEY = "__ai2apps_tip_timers__";
		const HOVER_KEY = "__ai2apps_tip_hover_fader__";

		const position = (opts.position === "bottom") ? "bottom" : "top";
		const maxWidth = Number.isFinite(opts.maxWidth) ? Math.max(240, opts.maxWidth) : 760;
		const offset = Number.isFinite(opts.offset) ? Math.max(0, opts.offset) : 14;
		const zIndex = Number.isFinite(opts.zIndex) ? Math.max(1, opts.zIndex) : 2147483646;
		const timeout = Number.isFinite(opts.timeout) ? Math.max(0, opts.timeout) : 5000;

		const icon = (opts.icon == null || opts.icon === "") ? null : String(opts.icon);
		const iconSize = Number.isFinite(opts.iconSize) ? Math.max(12, opts.iconSize) : 22;
		const caption = (opts.caption == null || opts.caption === "") ? null : String(opts.caption);

		const font = "system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";
		const fontSize = Number.isFinite(opts.fontSize) ? Math.max(10, opts.fontSize) : 13;
		const weight = Number.isFinite(opts.weight) ? Math.max(400, opts.weight) : 700;
		const opacity = Number.isFinite(opts.opacity) ? Math.min(1, Math.max(0.2, opts.opacity)) : 0.98;
		const lineClamp = Number.isFinite(opts.lineClamp) ? Math.max(0, Math.floor(opts.lineClamp)) : 3;

		const theme = (opts.theme === "light" || opts.theme === "dark") ? opts.theme : "auto";
		const stack = (opts.stack === false) ? false : true;

		const hoverFade = (opts.hoverFade === undefined) ? true : !!opts.hoverFade;
		const hoverOpacity = Number.isFinite(opts.hoverOpacity)
		? Math.min(1, Math.max(0.02, opts.hoverOpacity))
		: 0.12;

		const makeId = () => "tip_" + Math.random().toString(36).slice(2, 10);
		const id = (opts.id && String(opts.id).trim()) ? String(opts.id).trim() : makeId();

		const esc = (s) => {
			try {
				return (window.CSS && typeof CSS.escape === "function") ? CSS.escape(s) : String(s).replace(/["\\]/g, "\\$&");
			} catch {
				return String(s).replace(/["\\]/g, "\\$&");
			}
		};

		const prefersDark = (() => {
			try { return !!window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches; } catch { return false; }
		})();
		const isDark = (theme === "dark") ? true : (theme === "light") ? false : prefersDark;

		return new Promise((resolve) => {
			try {
				if (!body) return resolve({ ok: false, id: "", action: "error", reason: "no-body" });

				// root
				let root = doc.getElementById(ROOT_ID);
				if (!root) {
					root = doc.createElement("div");
					root.id = ROOT_ID;
					root.style.position = "fixed";
					root.style.left = "0";
					root.style.top = "0";
					root.style.width = "100vw";
					root.style.height = "100vh";
					root.style.pointerEvents = "none"; // 点击穿透
					root.style.zIndex = String(zIndex);
					body.appendChild(root);
				} else {
					const prevZ = parseInt(root.style.zIndex || "0", 10);
					if (!Number.isFinite(prevZ) || prevZ < zIndex) root.style.zIndex = String(zIndex);
				}

				// timers registry
				const timers = (root[TIMERS_KEY] && typeof root[TIMERS_KEY] === "object")
				? root[TIMERS_KEY]
				: (root[TIMERS_KEY] = Object.create(null));

				// lane for position
				const laneId = "__ai2apps_tip_lane__" + position;
				let lane = doc.getElementById(laneId);
				if (!lane) {
					lane = doc.createElement("div");
					lane.id = laneId;
					lane.style.position = "absolute";
					lane.style.left = "0";
					lane.style.right = "0";
					lane.style.display = "flex";
					lane.style.flexDirection = "column";
					lane.style.alignItems = "center";
					lane.style.gap = "10px";
					lane.style.pointerEvents = "none";
					lane.style.padding = "0";
					lane.style.margin = "0";
					lane.style[position] = `${offset}px`;
					root.appendChild(lane);
				} else {
					lane.style[position] = `${offset}px`;
				}

				if (!stack) {
					Array.from(lane.querySelectorAll("[data-ai2apps-tip='1']")).forEach((el) => el.remove());
				}

				// find existing by id
				let tip = root.querySelector(`[data-ai2apps-tip='1'][data-ai2apps-tip-id="${esc(id)}"]`);
				const isUpdate = !!tip;

				if (!tip) {
					tip = doc.createElement("div");
					tip.setAttribute("data-ai2apps-tip", "1");
					tip.setAttribute("data-ai2apps-tip-id", id);
					tip.style.pointerEvents = "none"; // 自己也穿透
					tip.style.maxWidth = `min(${maxWidth}px, calc(100vw - 24px))`;
					tip.style.width = "fit-content";
					tip.style.boxSizing = "border-box";
					tip.style.minWidth = "min(50vw, calc(100vw - 24px))";
					tip.style.backdropFilter = "blur(6px)";
					tip.style.webkitBackdropFilter = "blur(6px)";
					tip.style.borderRadius = "12px";
					tip.style.boxShadow = "0 10px 26px rgba(0,0,0,0.18)";
					tip.style.padding = caption ? "10px 12px 10px 12px" : "10px 12px";
					tip.style.display = "flex";
					tip.style.alignItems = "flex-start";
					tip.style.gap = "10px";
					tip.style.opacity = "0";
					tip.style.transform = "translateY(-6px)";
					tip.style.transition = "opacity 140ms ease, transform 140ms ease";
					tip.style.userSelect = "none";
					lane.appendChild(tip);
				} else {
					tip.style.transition = "none";
					tip.style.opacity = "0";
					tip.style.transform = "translateY(-6px)";
					void tip.offsetHeight;
					tip.style.transition = "opacity 140ms ease, transform 140ms ease";
				}

				// theme
				const bg = isDark ? "rgba(20,20,20,0.78)" : "rgba(255,255,255,0.86)";
				const fg = isDark ? "#f2f2f2" : "#111";
				const subFg = isDark ? "rgba(242,242,242,0.84)" : "rgba(17,17,17,0.84)";
				const border = isDark ? "1px solid rgba(255,255,255,0.18)" : "1px solid rgba(0,0,0,0.12)";

				tip.style.background = bg;
				tip.style.border = border;
				tip.style.color = fg;

				// store opacity values for hover-fade logic
				tip.setAttribute("data-ai2apps-tip-normal-opacity", String(opacity));
				tip.setAttribute("data-ai2apps-tip-hover-opacity", String(hoverFade ? hoverOpacity : opacity));

				// rebuild content
				tip.innerHTML = "";

				if (icon) {
					const iconWrap = doc.createElement("div");
					iconWrap.style.flex = "0 0 auto";
					iconWrap.style.width = `${iconSize}px`;
					iconWrap.style.height = `${iconSize}px`;
					iconWrap.style.display = "flex";
					iconWrap.style.alignItems = "center";
					iconWrap.style.justifyContent = "center";
					iconWrap.style.marginTop = caption ? "2px" : "1px";

					const img = doc.createElement("img");
					img.alt = "";
					img.src = icon;
					img.style.width = `${iconSize}px`;
					img.style.height = `${iconSize}px`;
					img.style.objectFit = "contain";
					img.style.border = "none";
					img.style.borderRadius = "8px";
					iconWrap.appendChild(img);

					tip.appendChild(iconWrap);
				}

				const textWrap = doc.createElement("div");
				textWrap.style.flex = "1 1 auto";
				textWrap.style.minWidth = "0";
				textWrap.style.fontFamily = font;
				textWrap.style.fontSize = `${fontSize}px`;
				textWrap.style.lineHeight = "1.35";
				textWrap.style.fontWeight = String(weight);

				if (caption) {
					const cap = doc.createElement("div");
					cap.textContent = caption;
					cap.style.fontSize = `${Math.max(11, fontSize)}px`;
					cap.style.fontWeight = "800";
					cap.style.marginBottom = "2px";
					cap.style.color = fg;
					cap.style.letterSpacing = "0.2px";
					textWrap.appendChild(cap);
				}

				const msg = doc.createElement("div");
				msg.textContent = text;
				msg.style.color = caption ? subFg : fg;
				msg.style.fontWeight = caption ? "700" : String(weight);
				msg.style.whiteSpace = "pre-wrap";
				msg.style.wordBreak = "break-word";
				msg.style.userSelect = "none";

				if (lineClamp > 0) {
					msg.style.display = "-webkit-box";
					msg.style.webkitBoxOrient = "vertical";
					msg.style.webkitLineClamp = String(lineClamp);
					msg.style.overflow = "hidden";
				}

				textWrap.appendChild(msg);
				tip.appendChild(textWrap);

				// animate in
				requestAnimationFrame(() => {
					tip.style.opacity = String(opacity);
					tip.style.transform = "translateY(0)";
				});

				// clear previous timer if updating
				if (timers[id]) {
					clearTimeout(timers[id]);
					delete timers[id];
				}

				if (timeout > 0) {
					timers[id] = setTimeout(() => {
						ai2appsTipDismiss(id);
					}, timeout);
				}

				// install hover-fader once (does NOT intercept clicks)
				(function ensureTipHoverFader(rootEl) {
					if (!hoverFade) return;
					if (rootEl[HOVER_KEY]) return;

					let raf = 0;
					let lastX = 0, lastY = 0;

					const apply = () => {
						raf = 0;
						const r = document.getElementById(ROOT_ID);
						if (!r) return;

						const tips = Array.from(r.querySelectorAll("[data-ai2apps-tip='1']"));
						for (const el of tips) {
							const normal = parseFloat(el.getAttribute("data-ai2apps-tip-normal-opacity") || "0");
							const hov = parseFloat(el.getAttribute("data-ai2apps-tip-hover-opacity") || "0");
							if (!normal || !hov) continue;

							const rect = el.getBoundingClientRect();
							const inside = lastX >= rect.left && lastX <= rect.right && lastY >= rect.top && lastY <= rect.bottom;
							el.style.opacity = inside ? String(hov) : String(normal);
						}
					};

					const onMove = (ev) => {
						if (!ev) return;
						lastX = ev.clientX;
						lastY = ev.clientY;
						if (!raf) raf = requestAnimationFrame(apply);
					};

					document.addEventListener("mousemove", onMove, true);
					document.addEventListener("pointermove", onMove, true);

					rootEl[HOVER_KEY] = { onMove };
				})(root);

				resolve({ ok: true, id, action: isUpdate ? "updated" : "shown" });
			} catch (err) {
				resolve({ ok: false, id: "", action: "error", reason: String(err && err.message ? err.message : err) });
			}
		});
	}

	// idOrAll:
	// - string: 关闭指定 id
	// - true: 关闭全部 tip，并移除 root（会卸载 hover 监听）
	// - null/undefined: 关闭全部 tip（若关闭后没有任何 tip，自动卸载监听并移除 root）
	ai2appsTipDismiss=function(idOrAll) {
		const ROOT_ID = "__ai2apps_tip_root__";
		const TIMERS_KEY = "__ai2apps_tip_timers__";
		const HOVER_KEY = "__ai2apps_tip_hover_fader__";

		const esc = (s) => {
			try {
				return (window.CSS && typeof CSS.escape === "function") ? CSS.escape(s) : String(s).replace(/["\\]/g, "\\$&");
			} catch {
				return String(s).replace(/["\\]/g, "\\$&");
			}
		};

		const uninstallHover = (root) => {
			if (!root) return;
			const h = root[HOVER_KEY];
			if (h && h.onMove) {
				document.removeEventListener("mousemove", h.onMove, true);
				document.removeEventListener("pointermove", h.onMove, true);
			}
			try { delete root[HOVER_KEY]; } catch {}
		};

		const clearAllTimers = (root) => {
			if (!root) return;
			const timers = (root[TIMERS_KEY] && typeof root[TIMERS_KEY] === "object") ? root[TIMERS_KEY] : null;
			if (!timers) return;
			for (const k of Object.keys(timers)) {
				clearTimeout(timers[k]);
				delete timers[k];
			}
		};

		const closeEl = (el) => {
			if (!el) return;
			el.style.transition = "opacity 120ms ease, transform 120ms ease";
			el.style.opacity = "0";
			el.style.transform = "translateY(-6px)";
			setTimeout(() => {
				if (el && el.parentNode) el.parentNode.removeChild(el);
			}, 140);
		};

		try {
			const doc = document;
			const root = doc.getElementById(ROOT_ID);
			if (!root) return { ok: true, action: "none" };

			const timers = (root[TIMERS_KEY] && typeof root[TIMERS_KEY] === "object") ? root[TIMERS_KEY] : null;

			// Dismiss ALL + remove root (explicit)
			if (idOrAll === true) {
				const tips = Array.from(root.querySelectorAll("[data-ai2apps-tip='1']"));
				tips.forEach(closeEl);

				clearAllTimers(root);
				uninstallHover(root);

				setTimeout(() => {
					const r = doc.getElementById(ROOT_ID);
					if (r && r.parentNode) r.parentNode.removeChild(r);
				}, 180);

				return { ok: true, action: "dismissed-all-removed-root" };
			}

			// Dismiss ONE
			if (typeof idOrAll === "string" && idOrAll.trim()) {
				const id = idOrAll.trim();
				const el = root.querySelector(`[data-ai2apps-tip='1'][data-ai2apps-tip-id="${esc(id)}"]`);

				if (timers && timers[id]) {
					clearTimeout(timers[id]);
					delete timers[id];
				}

				closeEl(el);

				// tidy: after removal, if no tips remain -> uninstall + remove root
				setTimeout(() => {
					const r = doc.getElementById(ROOT_ID);
					if (!r) return;
					const stillHas = r.querySelector("[data-ai2apps-tip='1']");
					if (stillHas) return;

					clearAllTimers(r);
					uninstallHover(r);
					if (r.parentNode) r.parentNode.removeChild(r);
				}, 220);

				return { ok: true, action: "dismissed-one", id };
			}

			// Dismiss ALL (default): close all; if empty -> uninstall + remove root
			const tips = Array.from(root.querySelectorAll("[data-ai2apps-tip='1']"));
			tips.forEach(closeEl);
			clearAllTimers(root);

			setTimeout(() => {
				const r = doc.getElementById(ROOT_ID);
				if (!r) return;
				const stillHas = r.querySelector("[data-ai2apps-tip='1']");
				if (stillHas) return;

				uninstallHover(r);
				if (r.parentNode) r.parentNode.removeChild(r);
			}, 220);

			return { ok: true, action: "dismissed-all" };
		} catch (err) {
			return { ok: false, action: "error", reason: String(err && err.message ? err.message : err) };
		}
	}
}

//----------------------------------------------------------------------------
/**
 * Build a customized System Prompt for "Decide Next Atomic Action".
 *
 * - goal: embedded into the System Prompt (NOT in user input)
 * - notes: embedded into the System Prompt (optional, NOT in user input)
 * - actions:
 *    - null => enable the "normal" full action set (EXCLUDES "selector" by default)
 *    - array => enable only those listed, plus done/abort always
 *    - NOTE: action "selector" is ONLY enabled when explicitly included in actions array
 *
 * Notes:
 * - "done" and "abort" are always included (even if not in actions).
 * - If actions excludes "run_js"/"uploadFile"/"dialog"/etc, related decision rules are automatically omitted.
 * - removeBlocker stays the highest priority IF it is enabled.
 */
function buildRpaMicroDeciderPrompt(goal, notes = "", actions = null) {
	if (typeof goal !== "string" || !goal.trim()) {
		throw new Error("buildRpaMicroDeciderPrompt(goal, notes, actions): goal must be a non-empty string");
	}
	if (!(typeof notes === "string" || notes === null || notes === undefined)) {
		throw new Error("buildRpaMicroDeciderPrompt(goal, notes, actions): notes must be a string (or null/undefined)");
	}
	if (!(actions === null || Array.isArray(actions))) {
		throw new Error("buildRpaMicroDeciderPrompt(goal, notes, actions): actions must be null or an array of strings");
	}

	// "Normal" full set (selector is intentionally NOT included by default)
	const ALL_DEFAULT = [
		"goto",
		"removeBlocker",
		"click",
		"hover",
		"input",
		"scroll",
		"scroll_show",
		"dialog",
		"uploadFile",
		"run_js",
		"ask_assist",
	];

	// Special action that MUST be explicitly enabled via actions array
	const SPECIAL_EXPLICIT_ONLY = ["selector"];

	const norm = (s) => String(s || "").trim();
	const wantAllDefault = actions === null;

	const allow = new Set(
		(wantAllDefault ? ALL_DEFAULT : actions.map(norm))
		.filter(Boolean)
	);

	// Ensure "selector" is never enabled implicitly
	if (wantAllDefault) {
		allow.delete("selector");
	}

	// done/abort are always present
	allow.add("done");
	allow.add("abort");

	const has = (a) => allow.has(a);

	// Validate action names when user provides a list
	if (!wantAllDefault) {
		const known = new Set([...ALL_DEFAULT, ...SPECIAL_EXPLICIT_ONLY, "done", "abort"]);
		const unknown = (actions || []).map(norm).filter(Boolean).filter((a) => !known.has(a));
		if (unknown.length) {
			throw new Error(`Unknown actions: ${unknown.join(", ")}`);
		}
	}

	// Action union snippet builder
	const actionLines = [];
	if (has("goto")) actionLines.push(`  { type: "goto",  url: string }`);
	if (has("removeBlocker")) actionLines.push(`| { type: "removeBlocker" }      // 专用于解除阻挡层（cookie/consent/modal/overlay/paywall遮罩等），内部自行尝试关闭/同意/移除遮罩`);
	if (has("click")) actionLines.push(`| { type: "click", by: Query, intent?: "open"|"dismiss"|"submit" }`);
	if (has("hover")) actionLines.push(`| { type: "hover", by: Query }`);
	if (has("input")) actionLines.push(`| { type: "input", by: Query, text: string, mode?: "fill"|"type" }`);
	if (has("scroll")) actionLines.push(`| { type: "scroll", x?: number, y?: number, by?: Query }`);
	if (has("scroll_show")) actionLines.push(`| { type: "scroll_show", by?: Query }`);
	if (has("dialog")) {
		actionLines.push(`| { type: "dialog", op: "accept"|"dismiss",`);
		actionLines.push(`    kind?: "alert"|"confirm"|"prompt",`);
		actionLines.push(`    textContains?: string,`);
		actionLines.push(`    value?: string }`);
	}
	if (has("uploadFile")) {
		actionLines.push(`| { type: "uploadFile",`);
		actionLines.push(`    by: Query,               // 点击该元素以打开系统文件选择对话框（或触发<input type=file>）`);
		actionLines.push(`    multi: boolean }         // 是否期望多文件上传（这里表示“本次任务是否需要多选”）`);
	}
	if (has("run_js")) actionLines.push(`| { type: "run_js", code: string }`);
	if (has("ask_assist")) actionLines.push(`| { type: "ask_assist", reason: string, waitUserAction?: boolean}   // reason 显示给用户；需要用户手动操作时 waitUserAction=true`);

	// Special: "selector" (explicit-only)
	if (has("selector")) {
		actionLines.push(`| { type: "selector", by: Query }     // 当目标是“寻找/定位某个HTML元素”时，直接返回该元素的 Query 选择器（不执行点击/输入等操作）`);
	}

	actionLines.push(`| { type: "done", reason: string, conclusion: string}               // conclusion 是对 goal 的回答或成功状态总结`);
	actionLines.push(`| { type: "abort", reason: string }                                 // 当你判断“在当前页面情境下肯定无法实现 goal”，立即放弃`);

	// Optional blocks depending on enabled actions
	const blockerBlock = has("removeBlocker")
	? `
────────────────────────────────────────────────────────
【阻挡层判定（用于决定 removeBlocker）】
若 html/截图显示以下任一情况，视为“有阻挡层”：
- cookie/consent/gdpr/privacy/accept/agree/subscribe/login/paywall/trial/membership/overlay/modal/backdrop 等关键词或明显遮罩结构
- 截图显示覆盖层挡住正文/按钮，导致主内容不可操作
- html 的 class/id 中含 modal/overlay/backdrop/dialog/popup/drawer 等子串并与遮罩结构相符
`.trim()
	: "";

	const abortBlock = `
────────────────────────────────────────────────────────
【abort 判定（必须非常严格，宁可不 abort）】
只有当你能从 url/title/html/截图推断“无论怎么点/滚/填都不可能完成 goal”时才 abort，例如：
- 站点明确显示“404/Not Found/页面已下线/Access Denied 且无继续路径”
- 明确的地区/权限封锁且没有任何替代入口（如必须企业内网、必须订阅但无试用入口且目标需要完整内容）
- goal 与当前站点能力完全不匹配（如 goal 要上传文件但页面无任何上传入口且明显是静态文章页；且也无导航到上传页的入口）
- 明确的人机验证/强制登录且页面无任何可继续浏览的替代信息，同时 goal 必须依赖登录后内容（若仍可能让用户介入则优先 ask_assist，而不是 abort）

abort 的 reason 必须具体（≤200字）：说明“卡死点是什么、为什么无法绕过”。
`.trim();

	// Decision rules (include only those possible)
	const decision = [];

	if (has("dialog")) {
		decision.push(`
0) 系统对话框优先
- 当 LLMContext.dialog 存在时，优先返回 action.type="dialog" 处理。
- 默认：alert → accept；
        confirm → dismiss（仅当文本明确为“继续/允许/同意/接受/关闭提示”等低风险操作才 accept）；
        prompt → 若必须继续且 text 明确要求输入则填写 value，否则 dismiss。
- 可用 textContains 辅助匹配，避免误处理不相关对话框。
`.trim());
	}

	if (has("removeBlocker")) {
		decision.push(`
1) 阻挡层最高优先级（高于 click / upload / scroll / selector）
- 若判定“有阻挡层”，本回合直接返回 {type:"removeBlocker"}。
- 不要尝试用 click 去点“Accept/Close”等；统一交给 removeBlocker 内部处理。
- 只有当你确信没有阻挡层时，才考虑其它动作。
`.trim());
	}

	if (has("selector")) {
		decision.push(`
${has("removeBlocker") ? "2" : "1"}) 选择器输出（仅当 goal 明确要求“寻找/定位特定元素”）
- 当目标是“找某个按钮/输入框/卡片/标题等元素的 selector/Query”，优先返回 {type:"selector", by: <Query> }。
- by 必须是可直接用于后续 click/input/scroll_show 的稳定 Query：优先 [id]/[data-testid]/[aria-*]/[name]/[href*=]/[placeholder*=]，避免脆弱 nth-child。
- 若需要按可见文本定位，优先用 XPath contains(normalize-space(.),"...")。
- 本回合只返回 selector，不要同时 click/scroll/run_js。
`.trim());
	}

	if (has("uploadFile")) {
		decision.push(`
文件上传（当目标明确包含上传意图时优先于普通点击）
- 若任务目标包含“上传/附件/选择文件/导入”等，优先寻找：
  - input[type="file"]（最稳）→ uploadFile(by: "css: input[type='file']", multi: 依据任务是否要多选)
  - 或 “Upload / Choose file / Browse / 添加附件 / 上传” 按钮 → uploadFile(by: 按钮选择器, multi: 同上)
- 若截图显示上传按钮但 html 难定位：用 XPath 按文本匹配作为 by。
- 本回合只做 uploadFile，不要同时 click 再 uploadFile。
`.trim());
	}

	if (has("click")) {
		decision.push(`
列表 → 详情
- 若当前像列表页，选择与目标最匹配的一条标题链接 click.open。
- 选择器优先：a[href] 且标题相关；或带 data-testid/aria-label 的卡片链接。
`.trim());
	}

	if (has("scroll_show")) {
		decision.push(`
需要露出目标元素才可点
- 若目标可能在首屏外，先 scroll_show 到目标附近（本回合只 scroll_show）。
`.trim());
	}

	if (has("hover")) {
		decision.push(`
悬停展开
- 若明显是 hover 才出现菜单/按钮，先 hover 到父元素（本回合只 hover）。
`.trim());
	}

	if (has("scroll") || has("click")) {
		const canLoadMoreClick = has("click");
		const canScroll = has("scroll");
		decision.push(`
加载更多/触发懒加载
- ${canLoadMoreClick ? `优先 click “Load more/More/Next”；` : `若页面有“Load more/More/Next”，但 click 不可用则跳过；`}
  ${canScroll ? `没有按钮再用 scroll（通常 y=1000~2000 或接近底部）。` : `scroll 不可用则跳过。`}
`.trim());
	}

	if (has("run_js")) {
		decision.push(`
run_js 兜底（只在必须时）
- 仅当缺少可靠选择器、需要快速判断页面类型/可见性、或需要从 html 中做轻量查找时使用。
- run_js 必须返回一个在页面中执行的函数代码，禁止包含执行这个函数的代码。
- run_js 代码应短小、可重复、无副作用，优先 querySelector/querySelectorAll 与可见性判断。
`.trim());
	}

	if (has("ask_assist")) {
		decision.push(`
ask_assist（仅在必须用户介入时）
- 若页面明确要求登录/验证码/人机验证/付费订阅且无法继续自动化：
  - 使用 ask_assist，reason 写清“要用户做什么”（如登录/过验证码/关闭系统弹窗）。
  - 需要等待用户手动操作时设 waitUserAction=true。
`.trim());
	}

	decision.push(`
避免重复失败（基于对话历史）
- 如果你从对话上下文判断“刚刚已经对同一 by/目标动作无效”，下一步应换更稳的选择器或改用 scroll_show / run_js 检测遮挡，而不是原样重复。
`.trim());

	const decisionBlock = `
────────────────────────────────────────────────────────
【决策准则（只用 url/title/html + dialog + 截图可视线索；goal/notes 已内置于本 Prompt）】
${decision.join("\n\n")}
`.trim();

	const notesText = norm(notes);
	const notesBlock = notesText
	? `
────────────────────────────────────────────────────────
【重要说明】
${notesText}
`:`
────────────────────────────────────────────────────────
【额外说明】
暂无。
`;

	const prompt = `
Decide Next Atomic Action

你是一个网页 RPA 的微决策器。给定当前环境 LLMContext，你必须基于页面状态返回恰好一个“原子动作”。禁止多步、禁止分支、禁止长解释，严格按指定 JSON 架构输出。

────────────────────────────────────────────────────────
【内置任务（goal）】
${goal.trim()}

${notesBlock}

────────────────────────────────────────────────────────
【输入：LLMContext（极简）】
- url: string
- title: string
- html: string              // 清洗后的完整 HTML（纯文本）
- dialog?: { kind: "alert"|"confirm"|"prompt", text?: string }   // 可选：当前存在的系统对话框信息（若无则为 null/undefined）

【附件（非 JSON）】
- 你可能会收到 0 张或多张“页面截图”作为图片附件（而非 JSON 字段）。
- 若截图与 html 存在矛盾：优先以截图的可视状态判断是否存在阻挡层与关键可见元素；结构化细节仍以 html 为主。
- 你不需要在输出中回传或引用附件；只需据此改进决策。

────────────────────────────────────────────────────────
【你可以返回的动作（只能返回其一）】
Action =
${actionLines.join("\n")}

────────────────────────────────────────────────────────
【元素定位：Query（直接可调用）】
- 两种写法：
  1) CSS（默认/推荐）：  "css: <标准 CSS 选择器>"；若省略前缀则按 CSS 解析
  2) XPath：              "xpath: <XPath 表达式>"
- 建议：
  • CSS 优先，避免脆弱的 :nth-child(...)。
  • 优先使用稳定锚点：[role]、[aria-*]、[data-testid]、[id]、[name]、[placeholder*=]、[href*=]、input[type="file"] 等。
  • 需要按文本匹配时使用 XPath（如：xpath: //button[contains(normalize-space(.),"Accept")]）。

${blockerBlock ? "\n" + blockerBlock + "\n" : ""}
${abortBlock ? "\n" + abortBlock + "\n" : ""}
${decisionBlock}

────────────────────────────────────────────────────────
【判定完成任务】
- 如果操作过程完成了 goal 的目标，或者取得了 goal 需要的数据，设置 action 为 "done"，并填写 conclusion 为对 goal 的回答/总结当前成功状态。

────────────────────────────────────────────────────────
【输出格式（严格 JSON，禁止多余文本/Markdown）】
{
  "action": Action,          // action 必须包含 type，禁止创造不存在的 type
  "reason": string,          // ≤ 200 字，基于 html/截图/dialog 的简短理由
  "summary": string          // ≤ 200 字，对“当前页面 + 本次动作”的简要总结：页面线索；动作；预期短结果
}

【summary 建议写法】
"<页面类型/关键线索>；执行 <动作+目标>；预期 <短结果>；(可选)风险 <遮挡/登录/需要滚动>。"
`.trim();

	return prompt;
}

//----------------------------------------------------------------------------
let findAvailableSelector,findAvailableSelectors;
{
	findAvailableSelector=async function(webRpa,page,selectors){
		let selector,item;
		for(selector of selectors){
			try{
				item=await webRpa.queryNode(page,null,selector,{});
			}catch(err){
				item=null;
			}
			if(item){
				return selector;
			}
		}
		return null;
	}

	//----------------------------------------------------------------------------
	findAvailableSelectors=async function(webRpa,page,selectors){
		let selector,item,list;
		list=[];
		for(selector of selectors){
			try{
				item=await webRpa.queryNode(page,null,selector,{});
			}catch(err){
				item=null;
			}
			if(item){
				list.push(selector);
			}
		}
		return list.length?list:null;
	}
}

//----------------------------------------------------------------------------
let armWaitForScroll,waitForScrollOutcome,extractActionableLinks;
{
	/**
	 * armWaitForScroll(opts)
	 * ----------------------
	 * “武装”一个滚动检测：立即返回一个 token（不等待结果）。
	 * 之后你可以发送 wheel，再调用 waitForScrollOutcome(token) 来 await 结果。
	 *
	 * 说明：
	 * - 单函数自包含：不依赖外部 helper。
	 * - 结果 Promise 会存到 window 上（按 token 索引）。
	 *
	 * opts:
	 *   x, y       : 目标点（通常是 wheel 的坐标），默认视口中心
	 *   deltaY     : wheel deltaY（>0 下滚，<0 上滚，=0 unknown）
	 *   timeoutMs  : 观测窗口，默认 700
	 *   pollMs     : 轮询间隔，默认 50
	 *   storeKey   : 可选，自定义全局存储 key（默认 "__ai2apps_scroll_wait_store__"）
	 *
	 * return:
	 *   { armed:true, token:string }
	 */
	armWaitForScroll=function(opts) {
		opts = opts || {};

		const STORE_KEY = typeof opts.storeKey === "string" && opts.storeKey ? opts.storeKey : "__ai2apps_scroll_wait_store__";
		const root = window;

		// 初始化 store
		let store = root[STORE_KEY];
		if (!store || typeof store !== "object") {
			store = root[STORE_KEY] = { waits: Object.create(null), lastToken: null };
		} else {
			if (!store.waits || typeof store.waits !== "object") store.waits = Object.create(null);
		}

		// 生成 token
		let token = "";
		try {
			token = (crypto && typeof crypto.randomUUID === "function") ? crypto.randomUUID() : "";
		} catch {}
		if (!token) token = `sw_${Date.now()}_${Math.random().toString(16).slice(2)}`;

		const x = Number.isFinite(opts.x) ? opts.x : (window.innerWidth / 2);
		const y = Number.isFinite(opts.y) ? opts.y : (window.innerHeight / 2);
		const deltaY = Number.isFinite(opts.deltaY) ? opts.deltaY : 0;
		const timeoutMs = Number.isFinite(opts.timeoutMs) ? opts.timeoutMs : 700;
		const pollMs = Number.isFinite(opts.pollMs) ? opts.pollMs : 50;

		const direction = deltaY > 0 ? "down" : (deltaY < 0 ? "up" : "unknown");

		// ---- 内部逻辑（自包含）----
		const raf = () => new Promise((resolve) => requestAnimationFrame(resolve));
		const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

		function isScrollable(el) {
			try {
				if (!el) return false;
				if (el === document.body || el === document.documentElement) return false;
				const style = getComputedStyle(el);
				const oy = style.overflowY;
				const ox = style.overflowX;
				const canY =
					  (oy === "auto" || oy === "scroll" || oy === "overlay") &&
					  el.scrollHeight > el.clientHeight + 1;
				const canX =
					  (ox === "auto" || ox === "scroll" || ox === "overlay") &&
					  el.scrollWidth > el.clientWidth + 1;
				return canY || canX;
			} catch {
				return false;
			}
		}

		function makeTarget(where, el, getPos, getMax) {
			const p = getPos();
			const m = getMax();

			const top = Math.round(p.top || 0);
			const left = Math.round(p.left || 0);
			const maxTop = Math.max(0, Math.round(m.maxTop || 0));
			const maxLeft = Math.max(0, Math.round(m.maxLeft || 0));

			const atTop = top <= 0;
			const atBottom = top >= maxTop - 1; // 1px 容错
			const canUp = !atTop;
			const canDown = !atBottom;

			return { where, el, top, left, maxTop, maxLeft, atTop, atBottom, canUp, canDown };
		}

		function getTargetsSnapshot(px, py) {
			// clamp 坐标，避免 elementsFromPoint 异常
			const cx = Math.max(0, Math.min((window.innerWidth || 0) - 1, px));
			const cy = Math.max(0, Math.min((window.innerHeight || 0) - 1, py));

			const docEl = document.documentElement;
			const body = document.body;

			const targets = [];

			// window
			targets.push(
				makeTarget(
					"window",
					null,
					() => ({ top: window.scrollY || 0, left: window.scrollX || 0 }),
					() => {
						const sh = docEl ? docEl.scrollHeight : 0;
						const sw = docEl ? docEl.scrollWidth : 0;
						const maxTop = Math.max(0, sh - (window.innerHeight || 0));
						const maxLeft = Math.max(0, sw - (window.innerWidth || 0));
						return { maxTop, maxLeft };
					}
				)
			);

			// documentElement / body（有些页面用它们滚）
			if (docEl && docEl.scrollHeight > docEl.clientHeight + 1) {
				targets.push(
					makeTarget(
						"documentElement",
						docEl,
						() => ({ top: docEl.scrollTop || 0, left: docEl.scrollLeft || 0 }),
						() => ({
							maxTop: (docEl.scrollHeight - docEl.clientHeight) || 0,
							maxLeft: (docEl.scrollWidth - docEl.clientWidth) || 0,
						})
					)
				);
			}
			if (body && body.scrollHeight > body.clientHeight + 1) {
				targets.push(
					makeTarget(
						"body",
						body,
						() => ({ top: body.scrollTop || 0, left: body.scrollLeft || 0 }),
						() => ({
							maxTop: (body.scrollHeight - body.clientHeight) || 0,
							maxLeft: (body.scrollWidth - body.clientWidth) || 0,
						})
					)
				);
			}

			// 指针下滚动容器（由内到外）
			const els = (document.elementsFromPoint ? document.elementsFromPoint(cx, cy) : [])
			.filter(isScrollable)
			.slice(0, 6);

			for (let i = 0; i < els.length; i++) {
				const el = els[i];
				targets.push(
					makeTarget(
						`element#${i}`,
						el,
						() => ({ top: el.scrollTop || 0, left: el.scrollLeft || 0 }),
						() => ({
							maxTop: (el.scrollHeight - el.clientHeight) || 0,
							maxLeft: (el.scrollWidth - el.clientWidth) || 0,
						})
					)
				);
			}

			// 剔除 DOM 引用（便于序列化）
			const safeTargets = targets.map((t) => {
				// eslint-disable-next-line no-unused-vars
				const { el: _el, ...rest } = t;
				return rest;
			});

			return { at: Date.now(), point: { x: cx, y: cy }, safeTargets };
		}

		function diffTargets(beforeSafe, afterSafe) {
			const mapB = new Map(beforeSafe.map((t) => [t.where, t]));
			const changes = [];

			for (const a of afterSafe) {
				const b = mapB.get(a.where);
				if (!b) continue;
				const dx = (a.left || 0) - (b.left || 0);
				const dy = (a.top || 0) - (b.top || 0);
				if (dx !== 0 || dy !== 0) changes.push({ where: a.where, dx, dy });
			}

			let primary = null;
			if (changes.length) {
				primary = changes.reduce((best, cur) => {
					const score = Math.abs(cur.dy) + Math.abs(cur.dx);
					const bestScore = Math.abs(best.dy) + Math.abs(best.dx);
					return score > bestScore ? cur : best;
				}, changes[0]);
			}

			return { scrolled: changes.length > 0, changes, primary };
		}

		function analyzeScrollability(targetsSafe) {
			const scrollables = targetsSafe.filter((t) => (t.maxTop > 0 || t.maxLeft > 0));
			const hadScrollableTarget = scrollables.length > 0;

			if (direction === "unknown") {
				return { hadScrollableTarget, canScrollInDirection: null, edgeAllTargets: null };
			}

			const wantDown = direction === "down";
			const canAny = scrollables.some((t) => (wantDown ? t.canDown : t.canUp));
			const edgeAll = scrollables.length > 0 && scrollables.every((t) => (wantDown ? !t.canDown : !t.canUp));

			return { hadScrollableTarget, canScrollInDirection: canAny, edgeAllTargets: edgeAll };
		}

		// 在 arm 时就抓 before，避免竞态（wheel 先发生）
		const beforeSnap = getTargetsSnapshot(x, y);
		const beforeSafe = beforeSnap.safeTargets;
		const analysisBefore = analyzeScrollability(beforeSafe);
		const start = Date.now();

		// 创建等待 Promise（不 await）
		const promise = (async () => {
			try {
				while (Date.now() - start < timeoutMs) {
					await raf();
					const afterSnap = getTargetsSnapshot(beforeSnap.point.x, beforeSnap.point.y);
					const afterSafe = afterSnap.safeTargets;

					const diff = diffTargets(beforeSafe, afterSafe);
					if (diff.scrolled) {
						return {
							scrolled: true,
							timedOut: false,
							reason: "scrolled",
							direction,
							primary: diff.primary,
							changes: diff.changes,
							analysis: {
								...analysisBefore,
								durationMs: Date.now() - start,
								point: beforeSnap.point,
								targetsBefore: beforeSafe,
								targetsAfter: afterSafe,
							},
						};
					}

					await sleep(pollMs);
				}

				// timeout 后最终再取一次 after
				const afterSnap = getTargetsSnapshot(beforeSnap.point.x, beforeSnap.point.y);
				const afterSafe = afterSnap.safeTargets;

				// 超时仍没变化：分类原因
				let reason = "no_change_within_timeout";
				if (!analysisBefore.hadScrollableTarget) {
					reason = "no_scrollable_target";
				} else if (direction !== "unknown" && analysisBefore.edgeAllTargets) {
					reason = "at_edge";
				} else if (direction === "unknown") {
					reason = "delta_unknown_no_change";
				} else {
					reason = "no_change_within_timeout";
				}

				return {
					scrolled: false,
					timedOut: true,
					reason,
					direction,
					primary: null,
					changes: [],
					analysis: {
						...analysisBefore,
						durationMs: Date.now() - start,
						point: beforeSnap.point,
						targetsBefore: beforeSafe,
						targetsAfter: afterSafe,
					},
				};
			} catch (e) {
				return {
					scrolled: false,
					timedOut: false,
					reason: "error",
					direction,
					error: String(e && e.stack ? e.stack : e),
				};
			}
		})();
		// 存储
		store.waits[token] = promise;
		store.lastToken = token;
		return { armed: true, token };
	}


	/**
	 * waitForScrollOutcome(token?, opts?)
	 * ---------------------------------
	 * 等待 armWaitForScroll 创建的 Promise 并返回结果。
	 *
	 * - 单函数自包含：不依赖外部 helper。
	 * - token 可省略：省略时用上一次 arm 的 token。
	 *
	 * opts:
	 *   cleanup : boolean（默认 true），拿到结果后是否删除 store 里的 promise
	 *   storeKey: 同 armWaitForScroll，可选，自定义全局存储 key
	 *
	 * return:
	 *   和 arm 里 Promise resolve 的对象一致；若未找到 token，则返回 reason:"not_armed"
	 */
	waitForScrollOutcome=async function(token, opts) {
		// 兼容调用：waitForScrollOutcome(opts)（不传 token）
		if (token && typeof token === "object") {
			opts = token;
			token = undefined;
		}
		opts = opts || {};

		const STORE_KEY = typeof opts.storeKey === "string" && opts.storeKey ? opts.storeKey : "__ai2apps_scroll_wait_store__";
		const cleanup = (typeof opts.cleanup === "boolean") ? opts.cleanup : true;

		const root = window;
		const store = root[STORE_KEY];

		if (!store || typeof store !== "object" || !store.waits || typeof store.waits !== "object") {
			return { scrolled: false, timedOut: false, reason: "not_armed" };
		}

		const useToken = (typeof token === "string" && token) ? token : store.lastToken;
		if (!useToken || !store.waits[useToken]) {
			return { scrolled: false, timedOut: false, reason: "not_armed" };
		}

		try {
			const result = await store.waits[useToken];
			if (cleanup) {
				try { delete store.waits[useToken]; } catch {}
				if (store.lastToken === useToken) store.lastToken = null;
			}
			return result;
		} catch (e) {
			if (cleanup) {
				try { delete store.waits[useToken]; } catch {}
				if (store.lastToken === useToken) store.lastToken = null;
			}
			return {
				scrolled: false,
				timedOut: false,
				reason: "error",
				error: String(e && e.stack ? e.stack : e),
			};
		}
	}

	/**
	 * extractActionableLinks()
	 * ------------------------
	 * 从当前页面提取“可能会形成页面跳转/动作”的链接（排除 css/script/img 等资源型 URL）。
	 *
	 * 返回：Array<{ url: string }>
	 *
	 * 默认覆盖（可点击/可触发动作的）：
	 * - <a href> / <area href>
	 * - <form action>
	 * - <button formaction> / <input formaction>
	 * - [role="link"][href] / [data-href|data-url]
	 * - meta refresh (可选，默认 true)
	 *
	 * 特别处理：
	 * - 相对链接 -> 用 document.baseURI 解析为完整 URL
	 * - protocol-relative //example.com
	 * - mailto:/tel:/data:（data URL 默认会裁剪，避免爆炸）
	 * - 去重（标准化后去重）
	 *
	 * opts:
	 * {
	 *   includeMetaRefresh?: boolean     // default true
	 *   includeFragmentOnly?: boolean    // default true  是否保留 href="#" 或 "#id"（"#" 会被丢弃；"#id" 保留）
	 *   includePseudoLinks?: boolean     // default true
	 *   sameOriginOnly?: boolean         // default false 只保留同源（仅对 http/https 生效）
	 *
	 *   visibleOnly?: boolean            // default true  只保留“可见/可交互”的元素链接（a/area/button/input/role=link）
	 *   requireInViewport?: boolean      // default true  visibleOnly 时要求元素与视口有交集（更像“当前可点”）
	 *
	 *   // DataURL 裁剪（避免爆炸）
	 *   maxDataUrlLength?: number        // default 512
	 *   keepDataUrlPrefix?: boolean      // default true
	 * }
	 */
	extractActionableLinks = function (opts) {
		opts = opts || {};
		const includeMetaRefresh = opts.includeMetaRefresh !== false;
		const includeFragmentOnly = opts.includeFragmentOnly !== false;
		const includePseudoLinks = opts.includePseudoLinks !== false;
		const sameOriginOnly = opts.sameOriginOnly === true;

		const visibleOnly = opts.visibleOnly !== false;
		const requireInViewport = !!opts.requireInViewport;

		const maxDataUrlLength = Number.isFinite(opts.maxDataUrlLength) ? Math.max(32, opts.maxDataUrlLength) : 512;
		const keepDataUrlPrefix = opts.keepDataUrlPrefix !== false;

		const base = document.baseURI || location.href;
		const hereOrigin = (() => {
			try { return new URL(location.href).origin; } catch { return ""; }
		})();

		const out = [];
		const seen = new Set();

		function trimDataUrl(u) {
			const s = String(u);
			if (s.length <= maxDataUrlLength) return s;

			if (!keepDataUrlPrefix) return s.slice(0, maxDataUrlLength) + "...(trimmed)";

			const comma = s.indexOf(",");
			if (comma > 0 && comma < 200) {
				const head = s.slice(0, comma + 1);
				const remain = maxDataUrlLength - head.length;
				if (remain > 16) return head + s.slice(comma + 1, comma + 1 + remain) + "...(trimmed)";
			}
			return s.slice(0, maxDataUrlLength) + "...(trimmed)";
		}

		function normalizeUrl(raw) {
			try {
				if (raw == null) return null;
				let u = String(raw).trim();
				if (!u) return null;

				if (u === "#") return null; // "#" 基本没信息，直接丢弃

				const lower = u.toLowerCase();

				// 明显不会形成跳转/动作的 scheme
				if (lower.startsWith("javascript:") || lower.startsWith("vbscript:") || lower.startsWith("about:")) return null;

				// 动作/导航 scheme
				if (lower.startsWith("mailto:") || lower.startsWith("tel:")) return u;
				if (lower.startsWith("data:")) return trimDataUrl(u);

				// protocol-relative
				if (u.startsWith("//")) u = (location.protocol || "https:") + u;

				// 片段链接：#id
				if (u.startsWith("#")) {
					if (!includeFragmentOnly) return null;
					const full = new URL(u, base).toString();
					return full.endsWith("#") ? null : full;
				}

				// 其余按 URL 解析
				const url = new URL(u, base);

				if (url.protocol !== "http:" && url.protocol !== "https:") return null;
				if (sameOriginOnly && hereOrigin && url.origin !== hereOrigin) return null;

				const s = url.toString();
				return s.endsWith("#") ? s.slice(0, -1) : s;
			} catch {
				return null;
			}
		}

		function isElementVisible(el) {
			if (!el || el.nodeType !== 1) return false;
			if (!(el instanceof Element)) return false;

			// hidden / inert / 祖先 hidden
			if (el.closest("[hidden]")) return false;

			// aria-hidden 更偏“语义不可见”，但在 RPA 里通常也该排除
			if (el.closest('[aria-hidden="true"]')) return false;

			const cs = getComputedStyle(el);
			if (!cs) return false;

			if (cs.display === "none") return false;
			if (cs.visibility === "hidden" || cs.visibility === "collapse") return false;
			if (cs.opacity === "0") return false;
			if (cs.pointerEvents === "none") return false;

			// disabled 的元素一般不可触发（对 a 不适用，但对 button/input 很重要）
			const tag = el.tagName.toLowerCase();
			if ((tag === "button" || tag === "input" || tag === "select" || tag === "textarea") && el.hasAttribute("disabled")) {
				return false;
			}

			// 需要有盒子（注意：<area> 没有 box，这里不处理，交给专门逻辑）
			const rects = el.getClientRects();
			if (!rects || rects.length === 0) return false;

			const r = el.getBoundingClientRect();
			if (r.width <= 0 || r.height <= 0) return false;

			if (!requireInViewport) return true;

			const vw = window.innerWidth || document.documentElement.clientWidth || 0;
			const vh = window.innerHeight || document.documentElement.clientHeight || 0;
			if (vw <= 0 || vh <= 0) return true; // 极端情况放行

			// 与视口有交集
			const inView =
				  r.right > 0 && r.bottom > 0 &&
				  r.left < vw && r.top < vh;

			return inView;
		}

		function isAreaVisible(areaEl) {
			// <area> 没有布局矩形：检查它关联的 <img usemap> 是否可见
			try {
				if (!areaEl || areaEl.tagName.toLowerCase() !== "area") return false;
				const map = areaEl.closest("map");
				if (!map) return false;
				const name = map.getAttribute("name") || map.id || "";
				if (!name) return false;

				// usemap 形如 "#mapname"
				const selector = `img[usemap="#${CSS.escape(name)}"], object[usemap="#${CSS.escape(name)}"]`;
				const host = document.querySelector(selector);
				if (!host) return false;

				return isElementVisible(host);
			} catch {
				return false;
			}
		}

		function pushUrl(raw) {
			const nu = normalizeUrl(raw);
			if (!nu) return;
			const key = nu;
			if (seen.has(key)) return;
			seen.add(key);
			out.push({ url: nu });
		}

		// -------- 1) <a>, <area> --------
		document.querySelectorAll("a[href], area[href]").forEach((el) => {
			const href = el.getAttribute("href");
			if (!href || !String(href).trim()) return;

			if (visibleOnly) {
				const tag = el.tagName.toLowerCase();
				if (tag === "area") {
					if (!isAreaVisible(el)) return;
				} else {
					if (!isElementVisible(el)) return;
				}
			}

			pushUrl(href);
		});

		// -------- 2) 表单动作 --------
		document.querySelectorAll("form[action]").forEach((el) => {
			const action = el.getAttribute("action");
			if (!action) return;

			// form 是否“可见”取决于你用例：这里默认也按可见过滤（更符合“可操作入口”）
			if (visibleOnly && !isElementVisible(el)) return;

			pushUrl(action);
		});

		document.querySelectorAll("button[formaction], input[formaction]").forEach((el) => {
			const fa = el.getAttribute("formaction");
			if (!fa) return;

			if (visibleOnly && !isElementVisible(el)) return;

			pushUrl(fa);
		});

		// -------- 3) 伪链接 --------
		if (includePseudoLinks) {
			document.querySelectorAll('[role="link"], [data-href], [data-url]').forEach((el) => {
				if (!el || !(el instanceof Element)) return;
				if (visibleOnly && !isElementVisible(el)) return;

				if (el.hasAttribute("href") && el.tagName.toLowerCase() !== "a") pushUrl(el.getAttribute("href"));
				if (el.hasAttribute("data-href")) pushUrl(el.getAttribute("data-href"));
				if (el.hasAttribute("data-url")) pushUrl(el.getAttribute("data-url"));
			});
		}

		// -------- 4) meta refresh --------
		if (includeMetaRefresh) {
			document.querySelectorAll('meta[http-equiv="refresh" i][content]').forEach((m) => {
				const content = m.getAttribute("content") || "";
				const mm = /url\s*=\s*(.+)\s*$/i.exec(content);
				if (mm && mm[1]) {
					const u = mm[1].trim().replace(/^["']|["']$/g, "");
					pushUrl(u);
				}
			});
		}

		return out;
	};
}


export {
urlToJsonName,readJson,saveJson,resolveUrl,readFileAsDataURL,
	findAvailableSelector,findAvailableSelectors,armWaitForScroll,waitForScrollOutcome,extractActionableLinks,
	deepEq,getLan,briefJSON,expandDottedKeys,
	readRule,saveRule,
	ai2appsPrompt,ai2appsTip,ai2appsTipDismiss,
	buildRpaMicroDeciderPrompt
};