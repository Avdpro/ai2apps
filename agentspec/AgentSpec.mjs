// AgentSpec.mjs
// v0.6.1-compatible KindSpec registry (ONLY kinds: load/register/list/lookup/validate)
// - API exposed as AgentSpecs object
// - No Agent registry, no Find/Route logic
// - Supports dynamic init() that scans kinds directory and imports modules
//
// Expected file layout:
//   /agent-spec/AgentSpec.mjs
//   /agent-spec/kinds/*.mjs
//
// Each kind module should export either:
//   - default export: KindDef object
//   - OR named export containing a KindDef object (e.g., export const ttsKind = {...})
// A KindDef must at least have: { kind, caps, ranks }.

import fsp from 'fs/promises'
import path from 'path'
import { pathToFileURL,fileURLToPath } from 'url'

export const AgentSpecs = {
// internal store: kind -> KindDef (frozen)
	_kinds: new Map(),
	_loaded: [], // [{file, kind}]

// ---------- lifecycle ----------
// init() can be called multiple times to refresh.
// It will clear previously loaded kinds by default (clear=true).
//
// options:
// - rootDir: base dir for resolving kindsDir (default: dirname of this file)
// - kindsDir: relative/absolute path to kinds directory (default: "./kinds")
// - exts: file extensions to load (default: [".mjs",".js"])
// - match: optional RegExp to filter filenames
// - clear: whether to clear existing kinds before reloading (default: true)
// - override: whether init can override existing kind (default: true when clear=true)
// - bustCache: append query to import url to bypass module cache (default: true)
	async init (opts = {}) {
		const rootDir = opts.rootDir || path.dirname(_selfPath())
		const kindsDir = opts.kindsDir || './kinds'
		const exts = Array.isArray(opts.exts) && opts.exts.length ? opts.exts : ['.mjs', '.js']
		const match = opts.match instanceof RegExp ? opts.match : null
		const clear = opts.clear !== false
		const bustCache = opts.bustCache !== false
		
		if (clear) this.clear()
		
		const dirAbs = path.isAbsolute(kindsDir) ? kindsDir : path.resolve(rootDir, kindsDir)
		const ents = await fsp.readdir(dirAbs, { withFileTypes: true })
		
		const files = ents
			.filter(d => d.isFile())
			.map(d => d.name)
			.filter(name => exts.includes(path.extname(name)))
			.filter(name => (match ? match.test(name) : true))
			.sort()
		
		const loaded = []
		for (const name of files) {
			const fileAbs = path.join(dirAbs, name)
			const mod = await _dynImport(fileAbs, bustCache)
			const kindDefs = _extractKindDefs(mod, fileAbs)
			
			for (const kd of kindDefs) {
				const reg = this.registerKind(kd, { override: true, fromFile: fileAbs })
				loaded.push(reg)
			}
		}
		
		this._loaded = loaded
		return { kinds: this.listKinds(), loaded }
	},
	
	clear () {
		this._kinds.clear()
		this._loaded = []
		return this
	},
	// ---------- basic operations ----------
	registerKind (kindDef, opts = {}) {
		const override = !!opts.override
		const fromFile = opts.fromFile || null
		
		const kd = _normalizeKindDef(kindDef)
		const kind = kd.kind
		
		if (this._kinds.has(kind) && !override) {
			throw new Error(`Kind already registered: ${kind}`)
		}
		
		// freeze shallowly (caller can deep-freeze if desired)
		const frozen = Object.freeze(kd)
		this._kinds.set(kind, frozen)
		
		return { kind, fromFile }
	},
	
	unregisterKind (kind) {
		kind = (kind || '').trim()
		if (!kind) return false
		return this._kinds.delete(kind)
	},
	
	getKind (kind) {
		kind = (kind || '').trim()
		return kind ? (this._kinds.get(kind) || null) : null
	},
	
	getSpecs () {
		return Array.from(this._kinds.values()).sort((a,b)=>{return a.kind>=b.kind?1:-1;});
	},
	
	listKinds () {
		return Array.from(this._kinds.keys()).sort()
	},
	
	listCaps (kind) {
		const kd = this.getKind(kind)
		return kd && kd.caps ? Object.keys(kd.caps) : []
	},
	
	capMeta (kind, key) {
		const kd = this.getKind(kind)
		if (!kd || !kd.caps) return null
		return kd.caps[key] || null
	},
	
	isArg (kind, key) {
		const m = this.capMeta(kind, key)
		return !!m && m.kind === 'arg'
	},
	
	isCap (kind, key) {
		const m = this.capMeta(kind, key)
		return !!m && m.kind === 'cap'
	},

// ---------- validation ----------
// validate all registered kinds (or one kind if provided)
// returns array of {code,msg}
	validate (kind = null, opts = {}) {
		const strict = opts.strict !== false // default true
		const errs = []
		
		if (kind) {
			const kd = this.getKind(kind)
			if (!kd) return [{ code: 'kind_not_found', msg: `kind not found: ${kind}` }]
			errs.push(..._validateKindDef(kd, strict))
			return errs
		}
		
		for (const kd of this._kinds.values()) {
			errs.push(..._validateKindDef(kd, strict))
		}
		return errs
	},

// for debugging/inspection
	loadedFiles () {
		return this._loaded.slice()
	},
}

// ---------------- internal helpers ----------------

function _normalizeKindDef (kd) {
	if (!kd || typeof kd !== 'object') throw new Error('Invalid KindDef: not an object')
	const kind = (kd.kind || '').trim()
	if (!kind) throw new Error('Invalid KindDef: kind required')

// keep fields as-is, only ensure object shapes exist
	const caps = kd.caps && typeof kd.caps === 'object' ? kd.caps : {}
	const ranks = kd.ranks && typeof kd.ranks === 'object' ? kd.ranks : {}
	
	const out = {
		...kd,
		kind,
		caps,
		ranks,
	}

// normalize defaultRank/defaultRanks
	if (typeof out.defaultRank === 'string') out.defaultRank = out.defaultRank.trim()
	if (Array.isArray(out.defaultRanks)) out.defaultRanks = out.defaultRanks.map(s => ('' + s).trim()).filter(Boolean)
	
	return out
}

// Extract KindDef object(s) from a module.
// - If module.default looks like KindDef => use it
// - Else, scan named exports and pick any object that looks like KindDef
function _extractKindDefs (mod, fileAbs) {
	const out = []
	
	if (mod && mod.default && _looksLikeKindDef(mod.default)) out.push(mod.default)
	
	if (mod && typeof mod === 'object') {
		for (const k of Object.keys(mod)) {
			const v = mod[k]
			if (_looksLikeKindDef(v)) out.push(v)
		}
	}

// de-dup by kind (last one wins inside the module)
	const byKind = new Map()
	for (const kd of out) byKind.set((kd.kind || '').trim(), kd)
	const arr = Array.from(byKind.values()).filter(Boolean)
	
	if (!arr.length) {
		// not fatal: allow non-kind modules in kinds/ if you ever want
		return []
	}

// attach provenance (non-enumerable to avoid persisting)
	for (const kd of arr) {
		try {
			Object.defineProperty(kd, '__fromFile', { value: fileAbs, enumerable: false })
		} catch {}
	}
	return arr
}

function _looksLikeKindDef (v) {
	return !!v
		&& typeof v === 'object'
		&& typeof v.kind === 'string'
		&& v.kind.trim().length > 0
		&& v.caps && typeof v.caps === 'object'
}

async function _dynImport (fileAbs, bustCache) {
	const url = pathToFileURL(fileAbs)
	if (bustCache) {
		// cache-bust to allow init() refresh
		url.searchParams.set('v', String(Date.now()) + '_' + String(Math.random()).slice(2))
	}
	return import(url.href)
}

// obtain current module path robustly in Node ESM
function _selfPath () {
// import.meta.url is the canonical source; convert to local path
	const u = new URL(import.meta.url)
	return u.protocol === 'file:' ? fileURLToPath(u) : ''
}

function _validateKindDef (kd, strict) {
	const errs = []
	const kind = kd && ('' + kd.kind).trim()
	if (!kind) return [{ code: 'kind_invalid', msg: 'KindDef.kind required' }]

// caps
	if (!kd.caps || typeof kd.caps !== 'object') {
		errs.push({ code: 'caps_invalid', msg: `${kind}: caps must be object` })
	} else {
		for (const key of Object.keys(kd.caps)) {
			const m = kd.caps[key]
			if (!m || typeof m !== 'object') {
				errs.push({
					code: 'cap_meta_invalid',
					msg: `${kind}.${key}: meta invalid`
				})
				continue
			}
			if (!m.desc) errs.push({ code: 'cap_desc_missing', msg: `${kind}.${key}: desc required` })
			if (m.kind !== 'cap' && m.kind !== 'arg') errs.push({
				code: 'cap_kind_invalid',
				msg: `${kind}.${key}: kind must be cap|arg`
			})
			if (m.kind === 'arg' && !m.type) errs.push({
				code: 'arg_type_missing',
				msg: `${kind}.${key}: arg.type required`
			})
			if (m.kind === 'arg' && strict && typeof m.type !== 'string') errs.push({
				code: 'arg_type_invalid',
				msg: `${kind}.${key}: arg.type must be string`
			})
		}
	}

// ranks
	if (!kd.ranks || typeof kd.ranks !== 'object') {
		errs.push({ code: 'ranks_invalid', msg: `${kind}: ranks must be object` })
	} else {
		for (const rk of Object.keys(kd.ranks)) {
			const m = kd.ranks[rk]
			if (!m || typeof m !== 'object') {
				errs.push({
					code: 'rank_meta_invalid',
					msg: `${kind}.ranks.${rk}: meta invalid`
				})
				continue
			}
			if (!m.desc) errs.push({ code: 'rank_desc_missing', msg: `${kind}.ranks.${rk}: desc required` })
			if (m.order !== 'asc' && m.order !== 'desc') errs.push({
				code: 'rank_order_invalid',
				msg: `${kind}.ranks.${rk}: order must be asc|desc`
			})
			if (!m.valueFrom) errs.push({
				code: 'rank_valueFrom_missing',
				msg: `${kind}.ranks.${rk}: valueFrom required`
			})
			if (!m.missing) errs.push({ code: 'rank_missing_missing', msg: `${kind}.ranks.${rk}: missing required` })
			if (m.missing === 'default' && m.defaultValue === undefined) errs.push({
				code: 'rank_defaultValue_missing',
				msg: `${kind}.ranks.${rk}: defaultValue required when missing=default`
			})
			if (strict && m.type && m.type !== 'number') errs.push({
				code: 'rank_type_invalid',
				msg: `${kind}.ranks.${rk}: only type=number supported in v0.6.1`
			})
		}
	}

// defaultRank(s) should reference existing ranks
	const hasRank = (rk) => !!rk && kd.ranks && kd.ranks[rk]
	
	if (Array.isArray(kd.defaultRanks)) {
		for (const rk of kd.defaultRanks) if (!hasRank(rk)) errs.push({
			code: 'defaultRanks_invalid',
			msg: `${kind}: defaultRanks contains unknown rank: ${rk}`
		})
	} else if (kd.defaultRanks != null) {
		errs.push({ code: 'defaultRanks_invalid', msg: `${kind}: defaultRanks must be array` })
	}
	
	if (typeof kd.defaultRank === 'string' && kd.defaultRank.trim()) {
		if (!hasRank(kd.defaultRank.trim())) errs.push({
			code: 'defaultRank_invalid',
			msg: `${kind}: defaultRank unknown: ${kd.defaultRank}`
		})
	} else if (kd.defaultRank != null && typeof kd.defaultRank !== 'string') {
		errs.push({ code: 'defaultRank_invalid', msg: `${kind}: defaultRank must be string` })
	}
	
	return errs
}
