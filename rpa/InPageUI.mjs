//// InPageUI.mjs - In-page dialog and notification utilities
//
// This module provides lightweight, non-intrusive UI components that can be injected
// into any web page without external dependencies. All components use pointer-events:none
// where appropriate to avoid interfering with page interactions.
//
// Components:
// - inPagePrompt: Modal dialog with optional icon, draggable, keyboard support
// - inPageTip: Non-blocking toast notifications with hover fade and stacking
// - inPageTipDismiss: Utility to close tip notifications
//
// Features:
// - No external dependencies (pure DOM manipulation)
// - Responsive design with viewport constraints
// - Dark/light theme support with auto-detection
// - Keyboard navigation and accessibility attributes
// - Click-through where appropriate for notifications
// - Proper cleanup and memory management

//----------------------------------------------------
// inPagePrompt - Modal dialog with customizable appearance and behavior
//
// Creates a modal dialog that can be displayed over any web page with full customization
// options for styling, behavior, and interaction. Supports both modal and non-modal modes.
//
// Parameters:
//   text: string - The main message text to display
//   opts: object - Configuration options:
//     - caption: string = "AI2Apps" - Dialog title bar text
//     - icon: DataURL|string|null = null - Icon to display (image URL or data URL)
//     - okText: string = "OK" - Text for the OK button
//     - cancelText: string = "Cancel" - Text for the Cancel button
//     - showCancel: boolean = false - Whether to show the Cancel button
//     - mask: css-color|string|false = "rgba(0,0,0,0.35)" - Background overlay color
//     - modal: boolean = true - Whether dialog blocks page interaction
//     - iconSize: number = 88 - Icon size in pixels (minimum 24px)
//     - buttonMinWidth: number = 96 - Minimum button width in pixels (minimum 40px)
//
// Return Values:
//   When showCancel = false: Promise<{ok: boolean, action: string, reason?: string}>
//     - action can be: "ok", "esc", "cancel", "closed"
//   When showCancel = true: Promise<boolean>
//     - true for OK/Enter, false for Cancel/Escape
//
// Features:
//   - Draggable by title bar with viewport constraints
//   - Keyboard navigation (Enter=OK, Escape=Cancel)
//   - Responsive design with max-width constraints
//   - Auto-focus on OK button for accessibility
//   - Modal mode blocks page interaction, non-modal allows click-through
//   - Customizable overlay background or transparent
//   - Prevents multiple instances (replaces existing dialog)
//
// Usage Examples:
//   // Simple confirmation
//   const result = await inPagePrompt("Are you sure?", { showCancel: true });
//   if (result) console.log("User confirmed");
//
//   // Custom styled dialog
//   const response = await inPagePrompt("Operation completed!", {
//     caption: "Success",
//     icon: "data:image/svg+xml;base64,...",
//     okText: "Continue",
//     mask: "rgba(0,100,0,0.2)"
//   });
//
//   // Non-modal notification
//   await inPagePrompt("Background task running...", {
//     modal: false,
//     mask: false,
//     okText: "Dismiss"
//   });
const inPagePrompt = function (text, opts = {}) {
	text = (text == null) ? "" : String(text);
	opts = (opts && typeof opts === "object") ? opts : {};
	
	const caption = (opts.caption == null || opts.caption === "") ? "AI2Apps" : String(opts.caption);
	const icon = (opts.icon == null) ? null : String(opts.icon);
	const okText = (opts.okText == null || opts.okText === "") ? "OK" : String(opts.okText);
	const cancelText = (opts.cancelText == null || opts.cancelText === "") ? "Cancel" : String(opts.cancelText);
	const showCancel = !!opts.showCancel;
	
	const modal = (opts.modal === undefined) ? true : !!opts.modal; // <--- NEW
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
			
			// NEW:
			// - modal=true  => root eats events (no click-through)
			// - modal=false => root does NOT eat events (click-through everywhere except dialog)
			root.style.pointerEvents = modal ? "auto" : "none";
			
			// Overlay only when modal=true AND mask !== false
			if (modal && mask !== false) {
				const overlay = doc.createElement("div");
				overlay.style.position = "absolute";
				overlay.style.left = "0";
				overlay.style.top = "0";
				overlay.style.width = "100%";
				overlay.style.height = "100%";
				overlay.style.background =
					(typeof mask === "string" && mask.trim()) ? mask : "rgba(0,0,0,0.35)";
				overlay.style.pointerEvents = "auto";
				
				// Still block scroll only in modal mode
				overlay.addEventListener("wheel", (e) => e.preventDefault(), { passive: false });
				overlay.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
				
				root.appendChild(overlay);
			}
			
			const dlg = doc.createElement("div");
			dlg.setAttribute("role", "dialog");
			dlg.setAttribute("aria-modal", modal ? "true" : "false"); // NEW
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
			titleBar.style.fontSize = "16px";
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
			textEl.style.fontSize = "14px";
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
				btn.style.padding = "6px 14px";
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
};

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
const inPageTip=function(text, opts = {}) {
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
	const iconSize = Number.isFinite(opts.iconSize) ? Math.max(12, opts.iconSize) : 32;
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

// --------------------------------------------------
// idOrAll:
// - string: 关闭指定 id
// - true: 关闭全部 tip，并移除 root（会卸载 hover 监听）
// - null/undefined: 关闭全部 tip（若关闭后没有任何 tip，自动卸载监听并移除 root）
const inPageTipDismiss=function(idOrAll) {
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


// --------------------------------------------------
/**
 * pickDomElement - DevTools-like element picker that plays nicely with inPagePrompt({modal:false})
 *
 * Usage:
 *   const picked = await pickDomElement();
 *   if (picked) console.log(picked.element, picked.selector, picked.rect);
 *
 * Behavior:
 * - Hover highlights element with a box and shows a tooltip near cursor.
 * - Click selects element (prevents default page action), returns info object.
 * - Hold Ctrl to pick parent of current hovered element.
 * - Esc cancels (returns null).
 * - Overlay z-index is below inPagePrompt root, and never blocks pointer events.
 */
const inPagePickDomElement = function pickDomElement(opts = {}) {
	opts = (opts && typeof opts === "object") ? opts : {};
	
	const PROMPT_ROOT_ID = (opts.promptRootId == null || opts.promptRootId === "")
		? "__ai2apps_prompt_root__"
		: String(opts.promptRootId);
	
	const zIndex = Number.isFinite(opts.zIndex) ? opts.zIndex : 2147483645; // prompt is 2147483647, tip is 2147483646
	const borderWidth = Number.isFinite(opts.borderWidth) ? Math.max(1, opts.borderWidth) : 2;
	
	// If true, we will prevent the clicked element's default action (recommended)
	const preventPageClick = (opts.preventPageClick === undefined) ? true : !!opts.preventPageClick;
	
	// If provided, array of selectors to ignore (besides prompt root)
	const extraIgnore = Array.isArray(opts.ignoreSelectors) ? opts.ignoreSelectors.map(String) : [];
	
	// NEW: normalize opts.attr
	// - string => {key: string, value: "true"}
	// - {key,value} => {key,value}
	const normalizeAttr = (a) => {
		if (!a) return null;
		if (typeof a === "string") {
			const k = a.trim();
			if (!k) return null;
			return { key: k, value: "true" };
		}
		if (typeof a === "object") {
			const k = (a.key == null) ? "" : String(a.key).trim();
			if (!k) return null;
			const v = (a.value == null) ? "" : String(a.value);
			return { key: k, value: v };
		}
		return {key:"data-manual-picked",value:"true"};
	};
	const pickAttr = normalizeAttr(opts.attr);
	
	// Simple CSS selector generator (best-effort)
	const cssEscape = (s) => {
		try {
			if (window.CSS && CSS.escape) return CSS.escape(String(s));
		} catch (_) {}
		return String(s).replace(/([^\w-])/g, "\\$1");
	};
	
	const getSimpleSelector = (el) => {
		if (!el || el.nodeType !== 1) return "";
		const tag = el.tagName.toLowerCase();
		const id = el.id ? `#${cssEscape(el.id)}` : "";
		let cls = "";
		if (el.classList && el.classList.length) {
			// Keep it short to avoid massive selectors
			const kept = Array.from(el.classList).slice(0, 3).map(cssEscape);
			if (kept.length) cls = "." + kept.join(".");
		}
		return `${tag}${id}${cls}`;
	};
	
	const getRect = (el) => {
		const r = el.getBoundingClientRect();
		return {
			x: Math.round(r.left),
			y: Math.round(r.top),
			width: Math.round(r.width),
			height: Math.round(r.height),
			left: Math.round(r.left),
			top: Math.round(r.top),
			right: Math.round(r.right),
			bottom: Math.round(r.bottom),
		};
	};
	
	const inPrompt = (node) => {
		try {
			const root = document.getElementById(PROMPT_ROOT_ID);
			return !!(root && node && root.contains(node));
		} catch (_) {
			return false;
		}
	};
	
	const inExtraIgnored = (node) => {
		if (!node || node.nodeType !== 1) return false;
		for (const sel of extraIgnore) {
			try {
				if (sel && node.closest && node.closest(sel)) return true;
			} catch (_) {}
		}
		return false;
	};
	
	const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
	
	return new Promise((resolve) => {
		const doc = document;
		const body = doc.body || doc.documentElement;
		if (!body) return resolve(null);
		
		// Ensure only one picker at a time
		const prev = doc.getElementById("__ai2apps_picker_root__");
		if (prev) prev.remove();
		
		// Root overlay (NON-BLOCKING)
		const root = doc.createElement("div");
		root.id = "__ai2apps_picker_root__";
		root.style.position = "fixed";
		root.style.left = "0";
		root.style.top = "0";
		root.style.width = "100vw";
		root.style.height = "100vh";
		root.style.zIndex = String(zIndex);
		root.style.pointerEvents = "none"; // never block clicks (prompt remains clickable)
		
		// Highlight box
		const box = doc.createElement("div");
		box.style.position = "fixed";
		box.style.left = "0";
		box.style.top = "0";
		box.style.width = "0";
		box.style.height = "0";
		box.style.border = `${borderWidth}px solid rgba(0, 120, 255, 0.95)`;
		box.style.background = "rgba(0, 120, 255, 0.10)";
		box.style.boxSizing = "border-box";
		box.style.borderRadius = "6px";
		box.style.pointerEvents = "none";
		
		// Tooltip
		const tip = doc.createElement("div");
		tip.style.position = "fixed";
		tip.style.left = "0";
		tip.style.top = "0";
		tip.style.maxWidth = "min(520px, calc(100vw - 24px))";
		tip.style.padding = "6px 8px";
		tip.style.border = "1px solid rgba(0,0,0,0.25)";
		tip.style.borderRadius = "8px";
		tip.style.background = "rgba(255,255,255,0.96)";
		tip.style.color = "#111";
		tip.style.font = "12px/1.2 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";
		tip.style.fontWeight = "700";
		tip.style.boxShadow = "0 6px 16px rgba(0,0,0,0.18)";
		tip.style.pointerEvents = "none";
		tip.style.whiteSpace = "nowrap";
		tip.style.overflow = "hidden";
		tip.style.textOverflow = "ellipsis";
		
		root.appendChild(box);
		root.appendChild(tip);
		body.appendChild(root);
		
		let active = true;
		let hoveredEl = null;
		let lastMouse = { x: 0, y: 0 };
		let ctrlDown = false;
		
		const pickCandidate = (el) => {
			if (!el || el.nodeType !== 1) return null;
			if (ctrlDown && el.parentElement) return el.parentElement;
			return el;
		};
		
		const updateUI = (el, mouseX, mouseY) => {
			const cand = pickCandidate(el);
			
			if (!cand) {
				box.style.width = "0";
				box.style.height = "0";
				tip.textContent = "";
				return;
			}
			
			const r = cand.getBoundingClientRect();
			
			// Box
			box.style.left = `${Math.round(r.left)}px`;
			box.style.top = `${Math.round(r.top)}px`;
			box.style.width = `${Math.round(r.width)}px`;
			box.style.height = `${Math.round(r.height)}px`;
			
			// Tooltip text
			const sel = getSimpleSelector(cand);
			const rx = Math.round(r.left), ry = Math.round(r.top), rw = Math.round(r.width), rh = Math.round(r.height);
			tip.textContent = `${ctrlDown ? "CTRL→PARENT  " : ""}${sel}  —  x:${rx} y:${ry} w:${rw} h:${rh}`;
			
			// Tooltip position near cursor, clamped
			const pad = 12;
			const vw = window.innerWidth || doc.documentElement.clientWidth || 0;
			const vh = window.innerHeight || doc.documentElement.clientHeight || 0;
			
			// Temporarily place then measure
			tip.style.left = "0px";
			tip.style.top = "0px";
			const tr = tip.getBoundingClientRect();
			const tw = tr.width, th = tr.height;
			
			let tx = mouseX + 14;
			let ty = mouseY + 14;
			
			if (tx + tw + pad > vw) tx = mouseX - tw - 14;
			if (ty + th + pad > vh) ty = mouseY - th - 14;
			
			tx = clamp(tx, pad, Math.max(pad, vw - tw - pad));
			ty = clamp(ty, pad, Math.max(pad, vh - th - pad));
			
			tip.style.left = `${Math.round(tx)}px`;
			tip.style.top = `${Math.round(ty)}px`;
		};
		
		const cleanup = (val) => {
			if (!active) return;
			active = false;
			doc.removeEventListener("mousemove", onMouseMove, true);
			doc.removeEventListener("mousedown", onMouseDown, true);
			doc.removeEventListener("click", onClick, true);
			doc.removeEventListener("keydown", onKeyDown, true);
			doc.removeEventListener("keyup", onKeyUp, true);
			if (root && root.parentNode) root.parentNode.removeChild(root);
			resolve(val);
		};
		
		const shouldIgnoreTarget = (t) => {
			// Ignore prompt UI and our own picker overlay
			if (!t) return true;
			if (t === root || root.contains(t)) return true;
			if (inPrompt(t)) return true;
			if (inExtraIgnored(t)) return true;
			return false;
		};
		
		const findElementFromPoint = (x, y) => {
			// elementFromPoint gives the topmost element at point
			let el = doc.elementFromPoint(x, y);
			if (!el) return null;
			if (shouldIgnoreTarget(el)) return null;
			return el;
		};
		
		const onMouseMove = (e) => {
			if (!active || !e) return;
			lastMouse = { x: e.clientX, y: e.clientY };
			
			// If hovering over prompt, hide highlight (so it doesn't look weird)
			const under = doc.elementFromPoint(e.clientX, e.clientY);
			if (under && (inPrompt(under) || (under === root || root.contains(under)))) {
				updateUI(null, e.clientX, e.clientY);
				hoveredEl = null;
				return;
			}
			
			const el = findElementFromPoint(e.clientX, e.clientY);
			hoveredEl = el;
			updateUI(el, e.clientX, e.clientY);
		};
		
		const finalizePick = (rawEl) => {
			const el = pickCandidate(rawEl);
			if (!el) return cleanup(null);
			
			// NEW: apply attribute on picked element (best-effort)
			if (pickAttr) {
				console.log("Will set picked attr at:",el);
				try {
					el.setAttribute(pickAttr.key, pickAttr.value);
				} catch (_) {}
			}
			
			const rect = getRect(el);
			const selector = getSimpleSelector(el);
			
			cleanup({
				ok: true,
				element: el,
				selector,
				rect,
				tagName: el.tagName.toLowerCase(),
				id: el.id || "",
				className: (el.className && typeof el.className === "string") ? el.className : "",
			});
		};
		
		// We block page action only when click is outside prompt.
		const onMouseDown = (e) => {
			if (!active || !e) return;
			
			// If user is clicking the prompt, don't interfere.
			if (e.target && inPrompt(e.target)) return;
			
			if (preventPageClick) {
				// Stop most "press" behaviors early (drag, focus, etc.)
				e.preventDefault();
				e.stopPropagation();
				if (e.stopImmediatePropagation) e.stopImmediatePropagation();
			}
		};
		
		const onClick = (e) => {
			if (!active || !e) return;
			
			// If user is clicking the prompt, don't interfere.
			if (e.target && inPrompt(e.target)) return;
			
			// Determine target under cursor
			const el = hoveredEl || findElementFromPoint(lastMouse.x, lastMouse.y) || (e.target && !shouldIgnoreTarget(e.target) ? e.target : null);
			
			if (preventPageClick) {
				e.preventDefault();
				e.stopPropagation();
				if (e.stopImmediatePropagation) e.stopImmediatePropagation();
			}
			
			finalizePick(el);
		};
		
		const onKeyDown = (e) => {
			if (!active || !e) return;
			
			if (e.key === "Escape" || e.key === "Esc") {
				e.preventDefault();
				e.stopPropagation();
				if (e.stopImmediatePropagation) e.stopImmediatePropagation();
				return cleanup(null);
			}
			
			if (e.key === "Control" || e.key === "Ctrl") {
				if (!ctrlDown) {
					ctrlDown = true;
					updateUI(hoveredEl, lastMouse.x, lastMouse.y);
				}
			}
		};
		
		const onKeyUp = (e) => {
			if (!active || !e) return;
			if (e.key === "Control" || e.key === "Ctrl") {
				if (ctrlDown) {
					ctrlDown = false;
					updateUI(hoveredEl, lastMouse.x, lastMouse.y);
				}
			}
		};
		
		doc.addEventListener("mousemove", onMouseMove, true);
		doc.addEventListener("mousedown", onMouseDown, true);
		doc.addEventListener("click", onClick, true);
		doc.addEventListener("keydown", onKeyDown, true);
		doc.addEventListener("keyup", onKeyUp, true);
		
		// Prime UI immediately
		updateUI(null, 12, 12);
	});
};

//----------------------------------------------------
// inPageShowSelector - Highlight elements matching a CSS selector with animated boxes
//
// Creates visual highlight overlays on all elements matching the given CSS selector.
// Each matched element gets a pulsing border box that follows the element's position
// and size, with automatic viewport tracking and scroll-to-view behavior.
//
// Parameters:
//   selector: string - CSS selector to match elements (e.g., ".my-class", "#my-id", "div[data-attr]")
//   opts: object - Configuration options:
//     - zIndex: number = 2147483645 - Z-index for highlight overlays (below prompt by default)
//     - borderWidth: number = 2 - Width of highlight border in pixels (minimum 1px)
//     - pulse: boolean = true - Whether to animate with pulsing effect
//     - pulseSeconds: number = 1.2 - Duration of pulse animation cycle (minimum 0.25s)
//
// Return Values:
//   number - Count of elements that were highlighted (0 if none found or selector invalid)
//
// Features:
//   - Real-time position tracking with requestAnimationFrame for smooth updates
//   - Automatic scroll-to-view: if no highlighted elements are in viewport, scrolls to first match
//   - Responsive to window resize and scroll events
//   - Non-blocking overlay (pointer-events: none)
//   - Automatic cleanup when dismissed or replaced
//   - Staggered pulse animation timing for multiple elements
//   - Handles dynamic DOM changes and element repositioning
//   - Viewport constraint handling and boundary clamping
//
// Usage Examples:
//   // Highlight all buttons
//   const count = inPageShowSelector("button");
//   console.log(`Highlighted ${count} buttons`);
//
//   // Highlight specific element with custom styling
//   inPageShowSelector("#my-target", {
//     borderWidth: 4,
//     pulse: false,
//     zIndex: 1000000
//   });
//
//   // Highlight form inputs with slow pulse
//   inPageShowSelector("input, textarea, select", {
//     pulseSeconds: 2.5
//   });
//
// Cleanup:
//   Use inPageDismissSelector() to remove all highlights, or call the function again
//   with a new selector to replace the current highlights.
//
//----------------------------------------------------
// inPageDismissSelector - Remove all selector highlights
//
// Removes all active highlight overlays created by inPageShowSelector() and cleans up
// associated event listeners and animation frames.
//
// Parameters: None
//
// Return Values:
//   boolean - true if highlights were actively dismissed, false if none were present
//
// Features:
//   - Stops all animation frames and removes event listeners
//   - Cleans up DOM elements and global state
//   - Safe to call multiple times or when no highlights are active
//
// Usage:
//   const wasDismissed = inPageDismissSelector();
//   if (wasDismissed) console.log("Highlights removed");
//
const inPageShowSelector = function(selector, opts = {}) {
	opts = (opts && typeof opts === "object") ? opts : {};
	selector = (selector == null) ? "" : String(selector);
	
	const stateKey = "__ai2apps_selector_highlight__";
	const PROMPT_Z = 2147483645;
	const zIndex = Number.isFinite(opts.zIndex) ? opts.zIndex : (PROMPT_Z - 1);
	const borderWidth = Number.isFinite(opts.borderWidth) ? Math.max(1, opts.borderWidth) : 2;
	
	const pulse = (opts.pulse === undefined) ? true : !!opts.pulse;
	const pulseSeconds = Number.isFinite(opts.pulseSeconds) ? Math.max(0.25, opts.pulseSeconds) : 1.2;
	
	const doc = document;
	const body = doc.body || doc.documentElement;
	if (!body) return 0;
	
	// 先关掉旧的
	if (window[stateKey] && window[stateKey].dismiss) {
		try { window[stateKey].dismiss(); } catch (_) {}
	}
	
	// 解析 selector：支持 css/xpath
	const raw = selector;
	const s = raw.trim();
	const detectMode = (str) => {
		if (!str) return { mode: "css", expr: "" };
		if (/^css:/i.test(str)) return { mode: "css", expr: str.replace(/^css:/i, "").trim() };
		if (/^xpath:/i.test(str)) return { mode: "xpath", expr: str.replace(/^xpath:/i, "").trim() };
		if (str[0] === "(") return { mode: "xpath", expr: str }; // 以括号开头认为是 XPath
		return { mode: "css", expr: str };
	};
	
	const getElementsBySelector = (input) => {
		const { mode, expr } = detectMode(input);
		if (!expr) return [];
		
		if (mode === "css") {
			return Array.from(doc.querySelectorAll(expr));
		}
		
		// XPath
		const out = [];
		const seen = new Set();
		// resolver: 处理 SVG 等命名空间（尽量兼容，不强制）
		const resolver = doc.createNSResolver
			? doc.createNSResolver(doc.documentElement || doc)
			: null;
		
		const result = doc.evaluate(
			expr,
			doc,
			resolver,
			XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
			null
		);
		
		for (let i = 0; i < result.snapshotLength; i++) {
			const n = result.snapshotItem(i);
			if (n && n.nodeType === 1 && !seen.has(n)) {
				seen.add(n);
				out.push(n);
			}
		}
		return out;
	};
	
	// 创建 root
	const root = doc.createElement("div");
	root.id = "__ai2apps_selector_root__";
	root.style.position = "fixed";
	root.style.left = "0";
	root.style.top = "0";
	root.style.width = "100vw";
	root.style.height = "100vh";
	root.style.zIndex = String(zIndex);
	root.style.pointerEvents = "none";
	
	// 注入动画 CSS（仅一次）
	const styleId = "__ai2apps_selector_style__";
	let styleEl = doc.getElementById(styleId);
	if (!styleEl) {
		styleEl = doc.createElement("style");
		styleEl.id = styleId;
		styleEl.type = "text/css";
		styleEl.textContent = `
@keyframes __ai2apps_pulse__ {
  0%   { box-shadow: 0 0 0 rgba(0,120,255,0.0); background: rgba(0,120,255,0.08); }
  50%  { box-shadow: 0 0 0 6px rgba(0,120,255,0.18); background: rgba(0,120,255,0.16); }
  100% { box-shadow: 0 0 0 rgba(0,120,255,0.0); background: rgba(0,120,255,0.08); }
}`;
		(doc.head || body).appendChild(styleEl);
	}
	
	// 工具函数
	const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
	const rectArea = (r) => Math.max(0, r.width) * Math.max(0, r.height);
	const intersectsViewport = (r, vw, vh) => !(r.right <= 0 || r.bottom <= 0 || r.left >= vw || r.top >= vh);
	
	let els = [];
	try {
		els = getElementsBySelector(selector);
	} catch (e) {
		return 0;
	}
	
	const count = els.length;
	if (count === 0) return 0;
	
	// Boxes
	const boxes = els.map(() => {
		const box = doc.createElement("div");
		box.style.position = "fixed";
		box.style.left = "0";
		box.style.top = "0";
		box.style.width = "0";
		box.style.height = "0";
		box.style.boxSizing = "border-box";
		box.style.border = `${borderWidth}px solid rgba(0, 120, 255, 0.95)`;
		box.style.background = "rgba(0, 120, 255, 0.10)";
		box.style.borderRadius = "6px";
		box.style.pointerEvents = "none";
		
		if (pulse) {
			box.style.animation = `__ai2apps_pulse__ ${pulseSeconds}s ease-in-out infinite`;
			box.style.animationDelay = `${(Math.random() * pulseSeconds * 0.6).toFixed(3)}s`;
		}
		
		root.appendChild(box);
		return box;
	});
	
	body.appendChild(root);
	
	let raf = 0;
	let alive = true;
	let dirty = true;
	
	const markDirty = () => { dirty = true; };
	
	const layoutOnce = () => {
		if (!alive) return;
		
		for (let i = 0; i < els.length; i++) {
			const el = els[i];
			const box = boxes[i];
			if (!el || !box || el.nodeType !== 1) continue;
			
			const r = el.getBoundingClientRect();
			if (!r || !Number.isFinite(r.left) || rectArea(r) <= 0) {
				box.style.width = "0px";
				box.style.height = "0px";
				continue;
			}
			
			const left = clamp(Math.round(r.left), -10000, 10000);
			const top = clamp(Math.round(r.top), -10000, 10000);
			const width = clamp(Math.round(r.width), 0, 20000);
			const height = clamp(Math.round(r.height), 0, 20000);
			
			box.style.left = `${left}px`;
			box.style.top = `${top}px`;
			box.style.width = `${width}px`;
			box.style.height = `${height}px`;
		}
		
		dirty = false;
		
		// 确保至少一个在视野里（只做一次）
		if (window[stateKey] && window[stateKey]._didEnsure !== true) {
			window[stateKey]._didEnsure = true;
			
			const vw = window.innerWidth || doc.documentElement.clientWidth || 0;
			const vh = window.innerHeight || doc.documentElement.clientHeight || 0;
			
			let anyInView = false;
			let firstGoodEl = null;
			
			for (const el of els) {
				if (!el || el.nodeType !== 1) continue;
				const rr = el.getBoundingClientRect();
				if (!rr || rectArea(rr) <= 0) continue;
				if (!firstGoodEl) firstGoodEl = el;
				if (intersectsViewport(rr, vw, vh)) { anyInView = true; break; }
			}
			
			if (!anyInView && firstGoodEl) {
				try {
					firstGoodEl.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" });
				} catch (_) {
					try { firstGoodEl.scrollIntoView(true); } catch (_) {}
				}
				dirty = true;
			}
		}
	};
	
	const tick = () => {
		if (!alive) return;
		if (dirty) layoutOnce();
		raf = window.requestAnimationFrame(tick);
	};
	raf = window.requestAnimationFrame(tick);
	
	const dismiss = () => {
		if (!alive) return;
		alive = false;
		try { window.cancelAnimationFrame(raf); } catch (_) {}
		window.removeEventListener("scroll", markDirty, true);
		window.removeEventListener("resize", markDirty, true);
		if (root && root.parentNode) root.parentNode.removeChild(root);
		if (window[stateKey]) delete window[stateKey];
	};
	
	window.addEventListener("scroll", markDirty, true);
	window.addEventListener("resize", markDirty, true);
	
	window[stateKey] = { dismiss, root, els, boxes, _didEnsure: false };
	
	// 立即布局一次
	dirty = true;
	layoutOnce();
	
	return count;
};

//----------------------------------------------------
// inPageShowSelector - Highlight elements matching a CSS selector with animated boxes
//
// Creates visual highlight overlays on all elements matching the given CSS selector.
// Each matched element gets a pulsing border box that follows the element's position
// and size, with automatic viewport tracking and scroll-to-view behavior.
//
// Parameters:
//   selector: string - CSS selector to match elements (e.g., ".my-class", "#my-id", "div[data-attr]")
//   opts: object - Configuration options:
//     - zIndex: number = 2147483645 - Z-index for highlight overlays (below prompt by default)
//     - borderWidth: number = 2 - Width of highlight border in pixels (minimum 1px)
//     - pulse: boolean = true - Whether to animate with pulsing effect
//     - pulseSeconds: number = 1.2 - Duration of pulse animation cycle (minimum 0.25s)
//
// Return Values:
//   number - Count of elements that were highlighted (0 if none found or selector invalid)
//
// Features:
//   - Real-time position tracking with requestAnimationFrame for smooth updates
//   - Automatic scroll-to-view: if no highlighted elements are in viewport, scrolls to first match
//   - Responsive to window resize and scroll events
//   - Non-blocking overlay (pointer-events: none)
//   - Automatic cleanup when dismissed or replaced
//   - Staggered pulse animation timing for multiple elements
//   - Handles dynamic DOM changes and element repositioning
//   - Viewport constraint handling and boundary clamping
//
// Usage Examples:
//   // Highlight all buttons
//   const count = inPageShowSelector("button");
//   console.log(`Highlighted ${count} buttons`);
//
//   // Highlight specific element with custom styling
//   inPageShowSelector("#my-target", {
//     borderWidth: 4,
//     pulse: false,
//     zIndex: 1000000
//   });
//
//   // Highlight form inputs with slow pulse
//   inPageShowSelector("input, textarea, select", {
//     pulseSeconds: 2.5
//   });
//
// Cleanup:
//   Use inPageDismissSelector() to remove all highlights, or call the function again
//   with a new selector to replace the current highlights.
//
//----------------------------------------------------
// inPageDismissSelector - Remove all selector highlights
//
// Removes all active highlight overlays created by inPageShowSelector() and cleans up
// associated event listeners and animation frames.
//
// Parameters: None
//
// Return Values:
//   boolean - true if highlights were actively dismissed, false if none were present
//
// Features:
//   - Stops all animation frames and removes event listeners
//   - Cleans up DOM elements and global state
//   - Safe to call multiple times or when no highlights are active
//
// Usage:
//   const wasDismissed = inPageDismissSelector();
//   if (wasDismissed) console.log("Highlights removed");
//
const inPageDismissSelector = function() {
	const stateKey = "__ai2apps_selector_highlight__";
	const st = window[stateKey];
	if (st && st.dismiss) {
		try { st.dismiss(); return true; } catch (_) {}
	}
	try {
		const el = document.getElementById("__ai2apps_selector_root__");
		if (el) el.remove();
	} catch (_) {}
	try { delete window[stateKey]; } catch (_) {}
	return false;
};

export {inPagePrompt,inPageTip,inPageTipDismiss,inPagePickDomElement,inPageShowSelector,inPageDismissSelector};