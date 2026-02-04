// cache_rules.mjs (ESM, ready-to-use instance + factory)
//
// You can either:
//   import CacheAPI from "./cache_rules.mjs";
// or
//   import { createRuleCacheAPI } from "./cache_rules.mjs"; and inject deps yourself.

import crypto from "crypto";
import pathLib from "path";
import { fileURLToPath } from "url";
// ======== CHANGE THESE IMPORT PATHS TO YOUR PROJECT ========
import { urlToJsonName, readJson, saveJson, deepEq, getLan} from "./utils.js";
// ==========================================================

function _esmDirname(metaUrl) {
	const filename = fileURLToPath(metaUrl);
	return pathLib.dirname(filename);
}

export function createRuleCacheAPI(deps = {}) {
	const {
		urlToJsonName,
		readJson,
		saveJson,
		deepEq,
		getLan,
		rulesDir,
	} = deps;

	const baseDir = _esmDirname(import.meta.url);
	const RULES_DIR = rulesDir || pathLib.join(baseDir, "rules");

	function _req(name, fn) {
		if (typeof fn !== "function") throw new Error(`cache_rules.mjs: missing required dependency: ${name}`);
		return fn;
	}
	_req("urlToJsonName", urlToJsonName);
	_req("readJson", readJson);
	_req("saveJson", saveJson);
	_req("deepEq", deepEq);
	_req("getLan", getLan);

	// -------------------------
	// 1) helpers
	// -------------------------
	function _aa_normStr(s, max = 400) {
		return (s == null ? "" : String(s)).replace(/\s+/g, " ").trim().slice(0, max);
	}
	function _aa_normSig(s) { return _aa_normStr(s, 2000); }
	function _aa_getHost(url) { try { return new URL(url).hostname || ""; } catch { return ""; } }

	function _aa_hash16(s) {
		s = _aa_normSig(s);
		if (!s) return "";
		try {
			return crypto.createHash("sha1").update(s, "utf8").digest("hex").slice(0, 16);
		} catch {
			let h = 0x811c9dc5;
			for (let i = 0; i < s.length; i++) {
				h ^= s.charCodeAt(i);
				h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
			}
			return ("00000000" + h.toString(16)).slice(-8) + "00000000";
		}
	}

	function _aa_eidFromSigKey(sigKey, mode = "instance") {
		const sk = _aa_normSig(sigKey);
		if (!sk) return "";
		const m = mode === "class" ? "class" : "instance";
		return "sig:" + _aa_hash16("mode=" + m + "|" + sk);
	}
	function _aa_eidFromPrivateKey(key, query, mode = "instance") {
		const m = mode === "class" ? "class" : "instance";
		return "sig:" + _aa_hash16("mode=" + m + "|key=" + _aa_normStr(key, 300) + "|q=" + _aa_normStr(query, 400));
	}

	function _aa_ensureLanBucket(rules, lan) {
		if (!rules[lan] || typeof rules[lan] !== "object") rules[lan] = {};
		const lanObj = rules[lan];
		lanObj.elements = lanObj.elements && typeof lanObj.elements === "object" ? lanObj.elements : {};
		lanObj.ruleMap  = lanObj.ruleMap  && typeof lanObj.ruleMap  === "object" ? lanObj.ruleMap  : {};
		return lanObj;
	}

	async function _aa_loadRulesFile(page) {
		const url = await page.url();
		const hostname = _aa_getHost(url);
		if (!hostname) return { hostname: "", jsonPath: "", rules: {} };

		let rules = {};
		let jsonPath = "";
		try {
			jsonPath = pathLib.join(RULES_DIR, urlToJsonName(hostname));
			rules = (await readJson(jsonPath)) || {};
		} catch (error) {
			console.log("Read Rules error: ", error);
			rules = {};
		}
		return { hostname, jsonPath, rules };
	}

	function _aa_upsertList(obj, field, item, maxLen) {
		item = _aa_normStr(item, 400);
		if (!item) return false;
		if (!Array.isArray(obj[field])) obj[field] = [];
		const arr = obj[field];
		const idx = arr.findIndex((x) => _aa_normStr(x, 400) === item);
		if (idx === 0) return false;
		if (idx > 0) arr.splice(idx, 1);
		arr.unshift(item);
		if (Number.isFinite(maxLen) && maxLen > 0 && arr.length > maxLen) arr.length = maxLen;
		return true;
	}

	function _aa_removeKeyFromElement(el, key) {
		if (!el || !Array.isArray(el.keys)) return false;
		const k = String(key || "").trim();
		if (!k) return false;
		const idx = el.keys.findIndex((x) => String(x).trim() === k);
		if (idx >= 0) { el.keys.splice(idx, 1); return true; }
		return false;
	}

	function _aa_isEidStillReferenced(ruleMap, eid) {
		for (const k of Object.keys(ruleMap || {})) {
			const r = ruleMap[k];
			if (r && typeof r === "object" && r.eid === eid) return true;
		}
		return false;
	}

	function _aa_deepMerge(dst, patch) {
		if (!patch || typeof patch !== "object") return dst;
		if (!dst || typeof dst !== "object") dst = {};
		for (const k of Object.keys(patch)) {
			const pv = patch[k];
			if (pv && typeof pv === "object" && !Array.isArray(pv)) dst[k] = _aa_deepMerge(dst[k], pv);
			else dst[k] = pv;
		}
		return dst;
	}

	function _aa_normSelectorOne(sel) { return (sel == null ? "" : String(sel).trim()) || ""; }
	function _aa_normSelectors(selOrList) {
		const arr = Array.isArray(selOrList) ? selOrList : [selOrList];
		const out = [];
		for (const x of arr) { const s = _aa_normSelectorOne(x); if (s) out.push(s); }
		return out;
	}

	function _aa_normalizeElement(el) {
		if (!el || typeof el !== "object") return el;
		if (!Array.isArray(el.queries)) {
			if (typeof el.query === "string" && el.query.trim()) el.queries = [_aa_normStr(el.query, 400)];
			else el.queries = [];
			if ("query" in el) delete el.query;
		}
		if (Array.isArray(el.originKeys) && !Array.isArray(el.keys)) {
			el.keys = el.originKeys.map((s) => _aa_normStr(s, 200)).filter(Boolean);
			delete el.originKeys;
		}
		if (el.value != null && !Array.isArray(el.value)) {
			if (typeof el.value === "string" && el.value.trim()) el.value = [el.value.trim()];
		}
		if (Array.isArray(el.value)) el.value = el.value.map(_aa_normSelectorOne).filter(Boolean);
		return el;
	}

	function inferRuleKind(rule) {
		if (!rule || typeof rule !== "object") return "unknown";
		if (rule.status === "done" || rule.status === "failed" || rule.status === "skipped") return "status";
		if (rule.code != null) return "code";
		if (typeof rule.eid === "string" && rule.eid.trim()) return "selector";
		if ("value" in rule) return "value";
		return "unknown";
	}

	function _aa_now() { return Date.now(); }
	function _aa_isExpiredByTtl(time, ttlMs, now) {
		if (!Number.isFinite(ttlMs) || ttlMs <= 0) return false;
		return now - (Number.isFinite(time) ? time : 0) > ttlMs;
	}

	// -------------------------
	// 2) open / flush / gc
	// -------------------------
	async function openRuleCache(session, page, opts = {}) {
		const lan = await page.callFunction(getLan, []);
		const { hostname, jsonPath, rules } = await _aa_loadRulesFile(page);
		if (!hostname) return null;
		const lanObj = _aa_ensureLanBucket(rules, lan);

		const ctx = {
			session, page, hostname, lan, jsonPath, rules, lanObj,
			elements: lanObj.elements, ruleMap: lanObj.ruleMap,
			now: _aa_now(), dirty: false,
		};
		if (opts.gcOnOpen) gcRuleCache(ctx, opts.gcOnOpen === true ? {} : opts.gcOnOpen);
		return ctx;
	}

	async function flushRuleCache(ctx) {
		if (!ctx || !ctx.hostname) return;
		if (!ctx.dirty) return;
		await saveJson(ctx.jsonPath, ctx.rules);
		ctx.dirty = false;
	}

	function gcRuleCache(ctx, opts = {}) {
		if (!ctx || !ctx.lanObj) return { ran: false, removedElements: 0, cleanedRules: 0 };
		const lanObj = ctx.lanObj;
		const elements = lanObj?.elements;
		const ruleMap = lanObj?.ruleMap;
		if (!elements || !ruleMap) return { ran: false, removedElements: 0, cleanedRules: 0 };

		const now = _aa_now();
		const MAX_ELEMENTS = Number.isFinite(opts.maxElements) ? opts.maxElements : 1200;
		const GC_MIN_INTERVAL_MS = Number.isFinite(opts.gcMinIntervalMs) ? opts.gcMinIntervalMs : 6 * 60 * 60 * 1000;
		const PENDING_TTL_MS = Number.isFinite(opts.pendingTtlMs) ? opts.pendingTtlMs : 24 * 60 * 60 * 1000;
		const ORPHAN_TTL_MS = Number.isFinite(opts.orphanTtlMs) ? opts.orphanTtlMs : 90 * 24 * 60 * 60 * 1000;

		const lastGc = Number.isFinite(lanObj._gcTime) ? lanObj._gcTime : 0;
		const elementCount = Object.keys(elements).length;
		if (elementCount <= MAX_ELEMENTS && now - lastGc < GC_MIN_INTERVAL_MS) {
			return { ran: false, removedElements: 0, cleanedRules: 0 };
		}

		let cleanedRules = 0;

		for (const k of Object.keys(ruleMap)) {
			const r = ruleMap[k];
			if (!r || typeof r !== "object") continue;
			const kind = inferRuleKind(r);

			if (kind === "status") {
				if (_aa_isExpiredByTtl(r.time, r.ttlMs, now)) { delete ruleMap[k]; cleanedRules++; }
			} else if (kind === "code") {
				const c = r.code;
				const t = Number.isFinite(c?.time) ? c.time : (Number.isFinite(r.time) ? r.time : 0);
				const ttlMs = c?.ttlMs ?? r.ttlMs;
				if (_aa_isExpiredByTtl(t, ttlMs, now)) { delete r.code; cleanedRules++; if (inferRuleKind(r) === "unknown") delete ruleMap[k]; }
			} else if (kind === "value") {
				const v = r.value;
				if (v && typeof v === "object" && "data" in v) {
					const t = Number.isFinite(v.time) ? v.time : (Number.isFinite(r.time) ? r.time : 0);
					const ttlMs = v.ttlMs ?? r.ttlMs;
					if (_aa_isExpiredByTtl(t, ttlMs, now)) { delete r.value; cleanedRules++; if (inferRuleKind(r) === "unknown") delete ruleMap[k]; }
				} else {
					if (_aa_isExpiredByTtl(r.time, r.ttlMs, now)) { delete ruleMap[k]; cleanedRules++; }
				}
			}
		}

		const active = new Set();
		for (const k of Object.keys(ruleMap)) {
			const r = ruleMap[k];
			if (!r || typeof r !== "object") continue;
			const eid = _aa_normStr(r.eid, 256);
			if (eid) active.add(eid);
		}

		let removed = 0;

		for (const [eid, el] of Object.entries(elements)) {
			if (!el || typeof el !== "object") continue;
			_aa_normalizeElement(el);
			const t = Number.isFinite(el.time) ? el.time : 0;
			const pending = !!el.pending || el.value == null;
			if (pending && now - t > PENDING_TTL_MS) { delete elements[eid]; removed++; }
		}

		for (const [eid, el] of Object.entries(elements)) {
			if (!el || typeof el !== "object") continue;
			if (active.has(eid)) continue;
			const t = Number.isFinite(el.time) ? el.time : 0;
			if (now - t > ORPHAN_TTL_MS) { delete elements[eid]; removed++; }
		}

		const entries = Object.entries(elements)
		.map(([eid, el]) => ({ eid, t: Number.isFinite(el?.time) ? el.time : 0 }))
		.sort((a, b) => b.t - a.t);

		if (entries.length > MAX_ELEMENTS) {
			for (let i = MAX_ELEMENTS; i < entries.length; i++) { delete elements[entries[i].eid]; removed++; }
		}

		lanObj._gcTime = now;
		lanObj._gcRemoved = (lanObj._gcRemoved || 0) + removed;
		if (removed || cleanedRules) ctx.dirty = true;

		return { ran: true, removedElements: removed, cleanedRules };
	}

	// -------------------------
	// 3) resolve + cleanup
	// -------------------------
	function getRule(ctx, key) {
		if (!ctx || !ctx.ruleMap) return null;
		const k = String(key || "").trim();
		if (!k) return null;
		const r = ctx.ruleMap[k];
		return r && typeof r === "object" ? r : null;
	}

	function resolveRule(ctx, keyOrRule, opts = {}) {
		if (!ctx) return null;
		const rule = typeof keyOrRule === "string" ? getRule(ctx, keyOrRule) : keyOrRule;
		if (!rule) return null;
		const kind = inferRuleKind(rule);
		const out = { kind, rule };

		if (kind === "selector") {
			const eid = _aa_normStr(rule.eid, 256);
			const el0 = eid ? (ctx.elements?.[eid] || null) : null;
			const el = el0 ? _aa_normalizeElement(el0) : null;

			out.selector = {
				eid,
				selectors: Array.isArray(el?.value) ? el.value : [],
				sigKey: el?.sigKey ?? null,
				mode: el?.mode === "class" ? "class" : "instance",
				policy: el?.policy === "single" ? "single" : "pool",
				share: typeof el?.share === "boolean" ? el.share : (el?.policy === "pool"),
				ownerKey: el?.ownerKey ?? null,
				maxLen: Number.isFinite(el?.maxLen) ? el.maxLen : 10,
				vision: el?.vision ?? null,
				query: rule.query ?? null,
				time: Number.isFinite(el?.time) ? el.time : (Number.isFinite(rule.time) ? rule.time : null),
				loose: false,
			};
		} else if (kind === "value") {
			const v = rule.value;
			out.value = (v && typeof v === "object" && "data" in v) ? (opts.raw ? v : v.data) : (v ?? null);
		} else if (kind === "code") {
			const c = rule.code;
			out.code = opts.raw ? c : (c && typeof c === "object" ? (c.text ?? null) : (c ?? null));
		} else if (kind === "status") {
			out.status = rule.status;
		}
		return out;
	}

	function _aa_throwConflict(detail) {
		const err = new Error(detail?.message || "CACHE_CONFLICT");
		err.code = "CACHE_CONFLICT";
		err.detail = detail || {};
		throw err;
	}

	function _aa_cleanupOldBinding(ctx, key, oldEid, opts = {}) {
		if (!ctx || !oldEid) return false;
		const elements = ctx.elements;
		const ruleMap = ctx.ruleMap;
		let changed = false;

		const oldEl = elements?.[oldEid] || null;
		if (oldEl) {
			_aa_normalizeElement(oldEl);
			if (_aa_removeKeyFromElement(oldEl, key)) changed = true;
		}

		if (opts.aggressive) {
			const noKeys = !oldEl || !Array.isArray(oldEl.keys) || oldEl.keys.length === 0;
			if (noKeys && !_aa_isEidStillReferenced(ruleMap, oldEid)) { delete elements[oldEid]; changed = true; }
		}
		return changed;
	}

	function deleteRule(ctx, key, opts = {}) {
		if (!ctx || !ctx.ruleMap) return { changed: false };
		const k = String(key || "").trim();
		if (!k) return { changed: false };
		const old = ctx.ruleMap[k];
		if (!old || typeof old !== "object") return { changed: false };
		if (typeof old.eid === "string" && old.eid) _aa_cleanupOldBinding(ctx, k, old.eid, { aggressive: !!opts.aggressive });
		delete ctx.ruleMap[k];
		ctx.dirty = true;
		return { changed: true };
	}

	// -------------------------
	// 4) status/value/code
	// -------------------------
	function setStatus(ctx, key, status, opts = {}) {
		if (!ctx) return { changed: false };
		const k = String(key || "").trim();
		if (!k) return { changed: false };
		const st = (status === "done" || status === "failed" || status === "skipped") ? status : null;
		if (!st) return { changed: false };

		const conflict = opts.conflict || "replace";
		const old = getRule(ctx, k);
		const oldKind = inferRuleKind(old);
		if (old && oldKind !== "status") {
			if (conflict === "throw") _aa_throwConflict({ message: "kind conflict", key: k, oldKind, newKind: "status" });
			if (oldKind === "selector" && old.eid) _aa_cleanupOldBinding(ctx, k, old.eid, { aggressive: !!opts.aggressive });
		}

		const now = _aa_now();
		const q = (typeof opts.query === "string") ? opts.query : (old?.query ?? null);

		ctx.ruleMap[k] = {
			status: st,
			...(opts.reason ? { reason: _aa_normStr(opts.reason, 400) } : null),
			...(Number.isFinite(opts.ttlMs) ? { ttlMs: opts.ttlMs } : null),
			...(opts.runId ? { runId: _aa_normStr(opts.runId, 120) } : null),
			...(q ? { query: q } : null),
			time: now
		};
		ctx.dirty = true;
		return { changed: true };
	}

	function setValue(ctx, key, value, opts = {}) {
		if (!ctx) return { changed: false };
		const k = String(key || "").trim();
		if (!k) return { changed: false };

		const conflict = opts.conflict || "replace";
		const old = getRule(ctx, k);
		const oldKind = inferRuleKind(old);
		if (old && oldKind !== "value") {
			if (conflict === "throw") _aa_throwConflict({ message: "kind conflict", key: k, oldKind, newKind: "value" });
			if (oldKind === "selector" && old.eid) _aa_cleanupOldBinding(ctx, k, old.eid, { aggressive: !!opts.aggressive });
		}

		const now = _aa_now();
		const q = (typeof opts.query === "string") ? opts.query : (old?.query ?? null);
		const vWrap = (value && typeof value === "object" && "data" in value)
		? value
		: { data: value, ...(Number.isFinite(opts.ttlMs) ? { ttlMs: opts.ttlMs } : null), ...(opts.runId ? { runId: _aa_normStr(opts.runId, 120) } : null), time: now };

		ctx.ruleMap[k] = { value: vWrap, ...(q ? { query: q } : null), time: now };
		ctx.dirty = true;
		return { changed: true };
	}

	function setCode(ctx, key, code, opts = {}) {
		if (!ctx) return { changed: false };
		const k = String(key || "").trim();
		if (!k) return { changed: false };

		const conflict = opts.conflict || "replace";
		const old = getRule(ctx, k);
		const oldKind = inferRuleKind(old);
		if (old && oldKind !== "code") {
			if (conflict === "throw") _aa_throwConflict({ message: "kind conflict", key: k, oldKind, newKind: "code" });
			if (oldKind === "selector" && old.eid) _aa_cleanupOldBinding(ctx, k, old.eid, { aggressive: !!opts.aggressive });
		}

		const now = _aa_now();
		const q = (typeof opts.query === "string") ? opts.query : (old?.query ?? null);
		const codeObj = (code && typeof code === "object" && "text" in code)
		? code
		: { text: String(code ?? ""), ...(Number.isFinite(opts.ttlMs) ? { ttlMs: opts.ttlMs } : null), ...(opts.runId ? { runId: _aa_normStr(opts.runId, 120) } : null), time: now };

		if (!codeObj.text) return { changed: false };
		ctx.ruleMap[k] = { code: codeObj, ...(q ? { query: q } : null), time: now };
		ctx.dirty = true;
		return { changed: true };
	}

	// -------------------------
	// 5) selector API
	// -------------------------
	function saveSelector(ctx, key, spec, opts = {}) {
		if (!ctx) return { changed: false, eid: "" };
		const k = String(key || "").trim();
		if (!k) return { changed: false, eid: "" };

		const conflict = opts.conflict || "replace";
		const aggressive = !!opts.aggressive;

		const mode = (spec?.mode === "class") ? "class" : "instance";
		const policy = (spec?.policy === "single") ? "single" : "pool";
		const maxLen = Number.isFinite(spec?.maxLen) ? spec.maxLen : 10;

		const selectors = _aa_normSelectors(spec?.selectors);
		if (!selectors.length) return { changed: false, eid: "" };

		const query = (typeof spec?.query === "string" && spec.query.trim()) ? spec.query : null;
		const sigKey = (typeof spec?.sigKey === "string" && spec.sigKey.trim()) ? spec.sigKey : null;

		const share = (typeof spec?.share === "boolean") ? spec.share : (policy === "pool");
		const ownerKey = share ? (spec?.ownerKey ? String(spec.ownerKey) : null) : (spec?.ownerKey ? String(spec.ownerKey) : k);

		const old = getRule(ctx, k);
		const oldKind = inferRuleKind(old);
		if (old && oldKind !== "selector") {
			if (conflict === "throw") _aa_throwConflict({ message: "kind conflict", key: k, oldKind, newKind: "selector" });
			if (oldKind === "selector" && old.eid) _aa_cleanupOldBinding(ctx, k, old.eid, { aggressive });
		}

		const eid = (sigKey && share) ? _aa_eidFromSigKey(sigKey, mode) : _aa_eidFromPrivateKey(k, query || "", mode);
		if (!eid) return { changed: false, eid: "" };

		const oldEid = (old && typeof old === "object" && typeof old.eid === "string" && old.eid) ? old.eid : null;
		if (oldEid && oldEid !== eid) _aa_cleanupOldBinding(ctx, k, oldEid, { aggressive });

		let el = ctx.elements[eid];
		if (!el || typeof el !== "object") el = ctx.elements[eid] = { value: null, pending: true, time: _aa_now() };
		_aa_normalizeElement(el);

		const now = _aa_now();

		el.mode = mode;
		el.policy = policy;
		el.share = share;
		if (!share) el.ownerKey = ownerKey;
		if (policy === "pool") el.maxLen = Number.isFinite(spec?.maxLen) ? spec.maxLen : (Number.isFinite(el.maxLen) ? el.maxLen : 10);
		if (sigKey && share) el.sigKey = _aa_normSig(sigKey);

		if (!Array.isArray(el.value)) el.value = [];
		if (policy === "single") el.value = [selectors[0]];
		else {
			for (let i = selectors.length - 1; i >= 0; i--) _aa_upsertList(el, "value", selectors[i], el.maxLen || maxLen);
			const cap = Number.isFinite(el.maxLen) ? el.maxLen : maxLen;
			if (Number.isFinite(cap) && cap > 0 && el.value.length > cap) el.value.length = cap;
		}

		if (spec?.visionPatch && typeof spec.visionPatch === "object") el.vision = _aa_deepMerge(el.vision || {}, spec.visionPatch);

		el.pending = false;
		el.time = now;
		if (query) _aa_upsertList(el, "queries", query, 20);
		_aa_upsertList(el, "keys", k, 200);

		ctx.ruleMap[k] = { eid, ...(query ? { query } : null), time: now };
		ctx.dirty = true;
		return { changed: true, eid };
	}

	function resolveSelector(ctx, key) {
		const r = getRule(ctx, key);
		if (!r || !r.eid) return null;
		const eid = _aa_normStr(r.eid, 256);
		const el0 = eid ? (ctx.elements?.[eid] || null) : null;
		if (!el0) return null;
		const el = _aa_normalizeElement(el0);
		return {
			eid,
			selectors: Array.isArray(el.value) ? el.value : [],
			sigKey: el.sigKey ?? null,
			mode: el.mode === "class" ? "class" : "instance",
			policy: el.policy === "single" ? "single" : "pool",
			share: typeof el.share === "boolean" ? el.share : (el.policy === "pool"),
			ownerKey: el.ownerKey ?? null,
			maxLen: Number.isFinite(el.maxLen) ? el.maxLen : 10,
			vision: el.vision ?? null,
			query: r.query ?? null,
			time: Number.isFinite(el.time) ? el.time : (Number.isFinite(r.time) ? r.time : null),
			loose: false
		};
	}

	function unbindSelector(ctx, key, opts = {}) {
		return deleteRule(ctx, key, { aggressive: !!opts.aggressive });
	}

	function findLooseSelector(ctx, args = {}) {
		const key = String(args.key || "").trim();
		const looseQuery = (typeof args.query === "string" && args.query) ? args.query : null;
		if (!key || !looseQuery) return null;

		const cut = key.lastIndexOf("_");
		const prefix = (cut > 0) ? key.slice(0, cut) : null;
		if (!prefix) return null;

		const elements = ctx.elements || {};
		for (const eid in elements) {
			const el0 = elements[eid];
			if (!el0 || typeof el0 !== "object") continue;
			const el = _aa_normalizeElement(el0);

			const qs = el.queries;
			const hasQuery = Array.isArray(qs) ? qs.includes(looseQuery) : (typeof qs === "string" ? qs === looseQuery : (qs && typeof qs === "object" ? (looseQuery in qs) : false));
			if (!hasQuery) continue;

			const ks = el.keys;
			let hasPrefixKey = false;
			if (Array.isArray(ks)) {
				for (const kk of ks) {
					if (typeof kk !== "string") continue;
					const j = kk.lastIndexOf("_");
					if (j > 0 && kk.slice(0, j) === prefix) { hasPrefixKey = true; break; }
				}
			} else if (ks && typeof ks === "object") {
				for (const kk in ks) {
					const j = kk.lastIndexOf("_");
					if (j > 0 && kk.slice(0, j) === prefix) { hasPrefixKey = true; break; }
				}
			}
			if (!hasPrefixKey) continue;

			return { ...resolveSelector({ ...ctx, ruleMap: { [key]: { eid, query: looseQuery, time: _aa_now() } } }, key), loose: true };
		}
		return null;
	}

	function saveRule(ctx, key, payload, opts = {}) {
		const kind = payload?.kind;
		if (kind === "selector") return { changed: saveSelector(ctx, key, payload, opts).changed, rule: getRule(ctx, key) };
		if (kind === "status") return { changed: setStatus(ctx, key, payload.status, { ...payload, ...opts }).changed, rule: getRule(ctx, key) };
		if (kind === "value") return { changed: setValue(ctx, key, payload.value, { ...payload, ...opts }).changed, rule: getRule(ctx, key) };
		if (kind === "code") return { changed: setCode(ctx, key, payload.code, { ...payload, ...opts }).changed, rule: getRule(ctx, key) };
		return { changed: false, rule: getRule(ctx, key) };
	}

	function getRuleElementBySigKey(ctx, sigKey, mode = "instance") {
		const sk = _aa_normSig(sigKey);
		if (!sk) return null;
		const eid = _aa_eidFromSigKey(sk, mode);
		const el0 = ctx.elements?.[eid] || null;
		if (!el0) return null;
		const el = _aa_normalizeElement(el0);
		return { eid, sigKey: el.sigKey ?? sk, value: el.value ?? null, pending: !!el.pending || el.value == null, time: Number.isFinite(el.time) ? el.time : null, queries: Array.isArray(el.queries) ? el.queries : [] };
	}

	return {
		openRuleCache, flushRuleCache, gcRuleCache,
		getRule, deleteRule, inferRuleKind, resolveRule, saveRule,
		setStatus, setValue, setCode,
		saveSelector, resolveSelector, unbindSelector, findLooseSelector,
		getRuleElementBySigKey,
	};
}

// ✅ Ready-to-use default instance:
export const CacheAPI = createRuleCacheAPI({
	urlToJsonName,
	readJson,
	saveJson,
	deepEq,
	getLan,
});

export default CacheAPI;