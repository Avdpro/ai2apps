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

// async inPagePrompt(text,opts)============================================================
// opts:
// - caption: string = "AI2Apps"
// - icon: DataURL|string|null = null
// - okText: string = "OK"
// - cancelText: string = "Cancel"
// - showCancel: boolean = false
// - mask: css-color|string|false = "rgba(0,0,0,0.35)"
// - modal: boolean = true   // NEW: false => show mask visually, but page remains interactive
// - iconSize: number = 88 (px)
// - buttonMinWidth: number = 96 (px)  // NEW: min button width, can grow with text
//
// Menu opts:
// - menu: Array<{ text:string, icon?:string|null, checked?:boolean, enable?:boolean }>
// - multiSelect: boolean = false
// - allowEmpty: boolean = true   // only applies when multiSelect=true
//
// Edit opts:
// - edit: boolean = false
// - editText: string = ""
// - placeHolder: string = ""
//
// Return:
// - If edit==true and NO menu:
//   - OK -> string (user input)
//   - Cancel/Esc (only if showCancel=true) -> null
//
// - If menu present and edit==false:
//   - multiSelect=false -> click item returns that object; Cancel/Esc (only if showCancel=true) -> null
//   - multiSelect=true  -> OK returns Array<menuItem>; Cancel/Esc (only if showCancel=true) -> null
//
// - If menu present and edit==true:
//   - multiSelect=false -> OK returns input string (ONLY when input non-empty); Cancel/Esc (only if showCancel=true) -> null
//   - multiSelect=true  -> OK returns Array (checked items) + (if input non-empty then push input string at end)
//
// - Else (legacy, no menu, edit==false):
//   - showCancel=false  -> Promise<{ok:true, action:string} | {ok:false, reason:string}>
//   - showCancel=true   -> Promise<boolean> (true=OK/Enter, false=Cancel/Esc)
//
// Key rules:
// - hasMenu && showCancel=false : Esc MUST NOT exit
// - hasMenu && showCancel=true  : Esc exits (returns null)
// - edit==true : Enter MUST NOT submit dialog (can insert newline)
const inPagePrompt = function (text, opts = {}) {
	text = (text == null) ? "" : String(text);
	opts = (opts && typeof opts === "object") ? opts : {};
	
	const caption = (opts.caption == null || opts.caption === "") ? "AI2Apps" : String(opts.caption);
	const icon = (opts.icon == null) ? null : String(opts.icon);
	const okText = (opts.okText == null || opts.okText === "") ? "OK" : String(opts.okText);
	const cancelText = (opts.cancelText == null || opts.cancelText === "") ? "Cancel" : String(opts.cancelText);
	const showCancel = !!opts.showCancel;
	
	const mask = (opts.mask === undefined) ? "rgba(0,0,0,0.35)" : opts.mask;
	const modal = (opts.modal === undefined) ? true : !!opts.modal;
	
	const iconSize = Number.isFinite(opts.iconSize) ? Math.max(24, opts.iconSize) : 88;
	const buttonMinWidth = Number.isFinite(opts.buttonMinWidth) ? Math.max(40, opts.buttonMinWidth) : 96;
	
	const hasMenu = Array.isArray(opts.menu);
	const multiSelect = !!opts.multiSelect;
	const allowEmpty = (opts.allowEmpty === undefined) ? true : !!opts.allowEmpty;
	
	const edit = !!opts.edit;
	const editText = (opts.editText == null) ? "" : String(opts.editText);
	const placeHolder = (opts.placeHolder == null) ? "" : String(opts.placeHolder);
	
	// Legacy boolean mode only when no menu and no edit
	const returnBoolean = (!hasMenu) && !edit && showCancel;
	
	// Keep original objects for menu return
	const menu = hasMenu
		? (opts.menu || []).map((it) => (it && typeof it === "object") ? it : ({ text: String(it) }))
		: null;
	
	return new Promise((resolve) => {
		try {
			const doc = document;
			const body = doc.body || doc.documentElement;
			if (!body) return resolve((hasMenu || edit) ? null : (returnBoolean ? false : { ok: false, reason: "no-body" }));
			
			// remove previous
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
			
			// Mask: modal=true blocks; modal=false visual-only
			if (mask !== false) {
				const overlay = doc.createElement("div");
				overlay.style.position = "absolute";
				overlay.style.left = "0";
				overlay.style.top = "0";
				overlay.style.width = "100%";
				overlay.style.height = "100%";
				overlay.style.background =
					(typeof mask === "string" && mask.trim()) ? mask : "rgba(0,0,0,0.35)";
				
				if (modal) {
					overlay.style.pointerEvents = "auto";
					overlay.addEventListener("wheel", (e) => e.preventDefault(), { passive: false });
					overlay.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
				} else {
					overlay.style.pointerEvents = "none";
				}
				root.appendChild(overlay);
			}
			
			const dlg = doc.createElement("div");
			dlg.setAttribute("role", "dialog");
			dlg.setAttribute("aria-modal", modal ? "true" : "false");
			dlg.tabIndex = -1;
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
			
			// Title bar
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
			
			// Content area
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
			
			const rightCol = doc.createElement("div");
			rightCol.style.display = "flex";
			rightCol.style.flexDirection = "column";
			rightCol.style.gap = (hasMenu || edit) ? "10px" : "0";
			rightCol.style.flex = "1 1 auto";
			rightCol.style.minWidth = "0";
			
			const textEl = doc.createElement("div");
			textEl.textContent = text;
			textEl.style.whiteSpace = "pre-wrap";
			textEl.style.lineHeight = "1.35";
			textEl.style.fontSize = "14px";
			textEl.style.fontWeight = "600";
			textEl.style.color = "#111";
			textEl.style.userSelect = "text";
			textEl.style.flex = "0 0 auto";
			rightCol.appendChild(textEl);
			
			// State
			let menuWrap = null;
			let okBtn = null;
			let cancelBtn = null;
			let editBox = null;
			
			// keep references to each menu input for UI sync
			const menuInputEls = []; // index -> <input>
			
			let selected = [];
			const isEnabledItem = (it) => (it && it.enable !== false);
			
			const syncSelectedFromMenu = () => {
				selected = [];
				if (!hasMenu) return;
				for (let i = 0; i < menu.length; i++) {
					if (menu[i] && menu[i].checked === true) selected.push(i);
				}
				if (!multiSelect && selected.length > 1) {
					const keep = selected[0];
					for (let i = 0; i < menu.length; i++) menu[i].checked = (i === keep);
					selected = [keep];
				}
			};
			syncSelectedFromMenu();
			
			const getEditValue = () => editBox ? String(editBox.value || "") : "";
			const hasEditText = () => getEditValue().trim().length > 0;
			
			// NOTE: even when menu+edit+single, we still show OK button (per previous), but now:
			// - Clicking a menu item immediately closes and returns the menu item object.
			const needOk = edit ? true : (hasMenu ? (multiSelect ? true : false) : true);
			
			const computeOkEnabled = () => {
				if (!okBtn) return false;
				
				// edit only
				if (edit && !hasMenu) return true;
				
				// menu + edit
				if (hasMenu && edit) {
					if (!multiSelect) return hasEditText(); // OK only valid when input has text
					if (allowEmpty) return true;
					return (selected.length > 0) || hasEditText();
				}
				
				// menu only
				if (hasMenu && !edit) {
					if (!multiSelect) return true; // OK normally absent
					if (allowEmpty) return true;
					return selected.length > 0;
				}
				
				// legacy
				return true;
			};
			
			const updateOkEnabled = () => {
				if (!okBtn) return;
				const enabled = computeOkEnabled();
				okBtn.disabled = !enabled;
				okBtn.style.opacity = enabled ? "1" : "0.45";
				okBtn.style.cursor = enabled ? "pointer" : "not-allowed";
				okBtn.setAttribute("aria-disabled", enabled ? "false" : "true");
			};
			
			// Key target (B mode)
			const keyTarget = modal ? doc : dlg;
			
			let closed = false;
			const cleanup = (val) => {
				if (closed) return;
				closed = true;
				keyTarget.removeEventListener("keydown", onKeyDown, true);
				if (root && root.parentNode) root.parentNode.removeChild(root);
				resolve(val);
			};
			
			// Menu UI
			const makeMenuRow = (it, idx, groupName) => {
				const row = doc.createElement("div");
				row.setAttribute("role", multiSelect ? "menuitemcheckbox" : "menuitemradio");
				row.tabIndex = (isEnabledItem(it) ? 0 : -1);
				row.style.display = "flex";
				row.style.alignItems = "center";
				row.style.gap = "10px";
				row.style.padding = "10px 10px";
				row.style.borderRadius = "10px";
				row.style.border = thinBorder;
				row.style.background = "#fff";
				row.style.userSelect = "none";
				row.style.outline = "none";
				
				const disabled = !isEnabledItem(it);
				if (disabled) {
					row.style.opacity = "0.45";
					row.style.cursor = "not-allowed";
				} else {
					row.style.cursor = "pointer";
					row.addEventListener("mouseenter", () => (row.style.background = "#f6f6f6"));
					row.addEventListener("mouseleave", () => (row.style.background = "#fff"));
				}
				
				const input = doc.createElement("input");
				input.type = multiSelect ? "checkbox" : "radio";
				input.name = multiSelect ? "" : groupName;
				input.checked = !!it.checked;
				input.disabled = disabled;
				input.style.transform = "scale(1.05)";
				input.style.margin = "0";
				input.style.flex = "0 0 auto";
				
				menuInputEls[idx] = input;
				
				const miIconWrap = doc.createElement("div");
				miIconWrap.style.flex = "0 0 auto";
				miIconWrap.style.width = "22px";
				miIconWrap.style.height = "22px";
				miIconWrap.style.display = it && it.icon ? "flex" : "none";
				miIconWrap.style.alignItems = "center";
				miIconWrap.style.justifyContent = "center";
				
				if (it && it.icon) {
					const im = doc.createElement("img");
					im.alt = "";
					im.src = String(it.icon);
					im.style.width = "22px";
					im.style.height = "22px";
					im.style.objectFit = "contain";
					im.style.borderRadius = "6px";
					im.style.border = "none";
					miIconWrap.appendChild(im);
				}
				
				const label = doc.createElement("div");
				label.textContent = (it && it.text != null) ? String(it.text) : "";
				label.style.flex = "1 1 auto";
				label.style.minWidth = "0";
				label.style.fontSize = "14px";
				label.style.fontWeight = "700";
				label.style.color = "#111";
				label.style.whiteSpace = "pre-wrap";
				label.style.lineHeight = "1.25";
				
				row.appendChild(input);
				row.appendChild(miIconWrap);
				row.appendChild(label);
				
				const setChecked = (checked) => {
					it.checked = !!checked;
					input.checked = !!checked;
				};
				
				const syncRadioUI = (pickedIdx) => {
					for (let i = 0; i < menu.length; i++) {
						const want = (i === pickedIdx);
						if (menu[i]) menu[i].checked = want;
						const el = menuInputEls[i];
						if (el) el.checked = want;
					}
					syncSelectedFromMenu();
				};
				
				const onActivate = () => {
					if (disabled) return null;
					
					if (!multiSelect) {
						syncRadioUI(idx);
						updateOkEnabled();
						
						// ✅ CHANGE: even when menu+edit+single, clicking menu closes and returns menu object
						return { type: "singleDone", value: it };
					}
					
					setChecked(!it.checked);
					syncSelectedFromMenu();
					updateOkEnabled();
					return { type: "toggled" };
				};
				
				row.addEventListener("click", (e) => {
					e.preventDefault();
					e.stopPropagation();
					const r = onActivate();
					if (r && r.type === "singleDone") cleanup(r.value);
				});
				
				row.addEventListener("keydown", (e) => {
					if (!e || disabled) return;
					if (e.key === "Enter" || e.key === " ") {
						e.preventDefault();
						e.stopPropagation();
						const r = onActivate();
						if (r && r.type === "singleDone") cleanup(r.value);
					}
				});
				
				return row;
			};
			
			if (hasMenu) {
				menuWrap = doc.createElement("div");
				menuWrap.setAttribute("role", "menu");
				menuWrap.style.display = "flex";
				menuWrap.style.flexDirection = "column";
				menuWrap.style.gap = "8px";
				menuWrap.style.padding = "0";
				menuWrap.style.margin = "0";
				menuWrap.style.maxHeight = "min(40vh, 300px)";
				menuWrap.style.overflow = "auto";
				menuWrap.style.borderRadius = "12px";
				
				const groupName = "__ai2apps_menu_" + Math.random().toString(16).slice(2);
				
				for (let i = 0; i < menu.length; i++) {
					const it = menu[i];
					if (it.enable === undefined) it.enable = true;
					if (it.checked === undefined) it.checked = false;
					menuWrap.appendChild(makeMenuRow(it, i, groupName));
				}
				
				rightCol.appendChild(menuWrap);
			}
			
			// Edit UI
			if (edit) {
				const wrap = doc.createElement("div");
				wrap.style.display = "flex";
				wrap.style.flexDirection = "column";
				wrap.style.gap = "6px";
				wrap.style.flex = "0 0 auto";
				
				editBox = doc.createElement("textarea");
				editBox.value = editText;
				editBox.placeholder = placeHolder;
				editBox.rows = 1;
				
				editBox.style.width = "100%";
				editBox.style.boxSizing = "border-box";
				editBox.style.resize = "none";
				editBox.style.border = thinBorder;
				editBox.style.borderRadius = "12px";
				editBox.style.padding = "10px 10px";
				editBox.style.fontFamily = font;
				editBox.style.fontSize = "14px";
				editBox.style.fontWeight = "650";
				editBox.style.lineHeight = "1.35";
				editBox.style.outline = "none";
				editBox.style.color = "#111";
				editBox.style.background = "#fff";
				
				const MAX_H = 180;
				const fitHeight = () => {
					editBox.style.height = "auto";
					const h = Math.min(MAX_H, Math.max(44, editBox.scrollHeight || 44));
					editBox.style.height = h + "px";
					editBox.style.overflowY = (editBox.scrollHeight > h) ? "auto" : "hidden";
				};
				editBox.addEventListener("input", () => { fitHeight(); updateOkEnabled(); });
				
				// keep Enter newline; prevent bubbling to dialog key handler
				editBox.addEventListener("keydown", (e) => {
					if (!e) return;
					if (e.key === "Enter" || e.key === "Escape" || e.key === "Esc") e.stopPropagation();
				});
				
				wrap.appendChild(editBox);
				rightCol.appendChild(wrap);
				
				setTimeout(() => { try { fitHeight(); } catch {} }, 0);
			}
			
			content.appendChild(iconWrap);
			content.appendChild(rightCol);
			
			// Footer
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
				btn.style.width = "auto";
				btn.style.whiteSpace = "nowrap";
				btn.style.textAlign = "center";
				btn.style.fontFamily = font;
				btn.style.fontSize = "14px";
				btn.style.fontWeight = "800";
				btn.style.cursor = "pointer";
				if (primary) btn.style.boxShadow = "0 3px 0 rgba(0,0,0,0.16)";
				btn.addEventListener("mouseenter", () => { if (!btn.disabled) btn.style.background = "#f5f5f5"; });
				btn.addEventListener("mouseleave", () => (btn.style.background = "#fff"));
			};
			
			cancelBtn = doc.createElement("button");
			cancelBtn.type = "button";
			cancelBtn.textContent = cancelText;
			baseBtnStyle(cancelBtn, false);
			
			okBtn = doc.createElement("button");
			okBtn.type = "button";
			okBtn.textContent = okText;
			baseBtnStyle(okBtn, true);
			
			let footerHasAnything = false;
			if (showCancel) { footer.appendChild(cancelBtn); footerHasAnything = true; }
			if (needOk) { footer.appendChild(okBtn); footerHasAnything = true; }
			
			dlg.appendChild(titleBar);
			dlg.appendChild(content);
			if (footerHasAnything) dlg.appendChild(footer);
			
			root.appendChild(dlg);
			body.appendChild(root);
			
			// External close hook
			root.__ai2apps_close__ = (reason) => {
				try {
					if (hasMenu || edit) return cleanup(null);
					if (showCancel) return cleanup(false);
					return cleanup({ ok: true, action: (reason == null ? "closed" : String(reason)) });
				} catch {
					try { cleanup(null); } catch {}
				}
			};
			
			// Focus
			if (editBox) editBox.focus({ preventScroll: true });
			else if (hasMenu && menuWrap) {
				const items = Array.from(menuWrap.querySelectorAll('[role="menuitemradio"],[role="menuitemcheckbox"]'));
				const first = items.find((el) => el && el.tabIndex === 0);
				if (first) first.focus({ preventScroll: true });
				else if (needOk && okBtn) okBtn.focus({ preventScroll: true });
				else dlg.focus({ preventScroll: true });
			} else if (needOk && okBtn) {
				okBtn.focus({ preventScroll: true });
			} else {
				dlg.focus({ preventScroll: true });
			}
			
			// OK / Cancel actions
			const closeOkLegacy = () => (returnBoolean ? cleanup(true) : cleanup({ ok: true, action: "ok" }));
			
			const onOk = () => {
				if (!okBtn || okBtn.disabled) return;
				
				// edit only
				if (edit && !hasMenu) return cleanup(getEditValue());
				
				// menu + edit
				if (hasMenu && edit) {
					if (!multiSelect) return cleanup(getEditValue());
					const arr = [];
					for (let i = 0; i < menu.length; i++) if (menu[i] && menu[i].checked === true) arr.push(menu[i]);
					const v = getEditValue();
					if (v.trim().length > 0) arr.push(v);
					return cleanup(arr);
				}
				
				// menu only
				if (hasMenu && !edit) {
					if (!multiSelect) {
						const idx = selected[0];
						return cleanup((idx == null) ? null : menu[idx]);
					}
					const arr = [];
					for (let i = 0; i < menu.length; i++) if (menu[i] && menu[i].checked === true) arr.push(menu[i]);
					return cleanup(arr);
				}
				
				// legacy
				return closeOkLegacy();
			};
			
			const onCancel = () => {
				if (hasMenu || edit) return cleanup(null);
				return cleanup(false);
			};
			
			if (needOk && okBtn) okBtn.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); onOk(); });
			if (showCancel && cancelBtn) cancelBtn.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); onCancel(); });
			
			updateOkEnabled();
			
			// Keydown handler
			const onKeyDown = (e) => {
				if (!e) return;
				const isEsc = (e.key === "Escape" || e.key === "Esc");
				const isEnter = (e.key === "Enter");
				
				if (isEsc) {
					if (edit) {
						if (!showCancel) return;
						e.preventDefault(); e.stopPropagation();
						return cleanup(null);
					}
					if (hasMenu) {
						if (!showCancel) return;
						e.preventDefault(); e.stopPropagation();
						return cleanup(null);
					}
					e.preventDefault(); e.stopPropagation();
					if (showCancel) return cleanup(false);
					return cleanup({ ok: true, action: "esc" });
				}
				
				if (isEnter) {
					if (edit) return; // never submit in edit mode
					if (hasMenu) {
						if (!multiSelect) return; // single-select: handled by row keydown
						e.preventDefault(); e.stopPropagation();
						return onOk();
					}
					e.preventDefault(); e.stopPropagation();
					return closeOkLegacy();
				}
			};
			
			keyTarget.addEventListener("keydown", onKeyDown, true);
			
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
			
			titleBar.addEventListener("pointerdown", (ev) => {
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
			}, true);
			
		} catch (err) {
			resolve((hasMenu || edit) ? null : (returnBoolean ? false : { ok: false, reason: String(err && err.message ? err.message : err) }));
		}
	});
};

//----------------------------------------------------------------------------------
// Close current inPagePrompt dialog (if any)
//
// Usage:
//   ai2appsDismissPrompt();                 // -> true if dismissed
//   ai2appsDismissPrompt("external-close"); // optional reason (used only for legacy object mode)
//
// Behavior:
// - If a prompt is present, it will be removed from DOM.
// - Best-effort to resolve the pending Promise:
//   - If there is an "edit" or "menu" mode (we can't know reliably), we resolve with null.
//   - Else legacy: if it had showCancel=true, resolve false; otherwise resolve {ok:true, action:reason||"closed"}.
// Note: This works with the ai2appsPrompt implementation that stores a resolver on root.dataset / property.
//       If your current ai2appsPrompt doesn't store it yet, this will still remove the DOM, but cannot resolve the Promise.
//
const inPageDismissPrompt = function (reason) {
	try {
		const doc = document;
		const root = doc.getElementById("__ai2apps_prompt_root__");
		if (!root) return false;
		
		// If ai2appsPrompt stored a resolver on root (recommended), call it:
		const closeFn = root.__ai2apps_close__;
		if (typeof closeFn === "function") {
			try { closeFn(reason); } catch {}
			return true;
		}
		
		// Fallback: just remove from DOM (cannot resolve pending Promise)
		root.remove();
		return true;
	} catch {
		return false;
	}
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
//----------------------------------------------------
// inPagePickDomElement - Interactive DOM element picker with hierarchical selection
//
// Creates an interactive overlay that allows users to visually select DOM elements by hovering
// and clicking. Features hierarchical navigation using keyboard controls to select parent/child
// elements in the DOM tree, with real-time visual feedback and detailed element information.
//
// Parameters:
//   opts: object - Configuration options:
//     - promptRootId: string = "__ai2apps_prompt_root__" - ID of prompt dialog to avoid selecting
//     - zIndex: number = 2147483645 - Z-index for picker overlay (below prompt by default)
//     - borderWidth: number = 2 - Width of selection highlight border in pixels (minimum 1px)
//     - preventPageClick: boolean = true - Whether to prevent default click actions on page elements
//     - ignoreSelectors: string[] = [] - Array of CSS selectors for elements to ignore during picking
//     - attr: string|object = null - Attribute to set on picked element:
//       - string: attribute name (value will be "true")
//       - object: {key: string, value: string} for custom attribute name and value
//
// Interactive Controls:
//   - Mouse hover: Highlights elements under cursor
//   - Click: Selects the currently highlighted element
//   - Ctrl key: Navigate up the DOM hierarchy (select parent elements)
//   - Shift+Ctrl: Navigate down the DOM hierarchy (select child elements)
//   - Escape: Cancel selection and exit picker mode
//
// Return Values:
//   Promise<object|null> - Resolves to selection result or null if cancelled:
//     - ok: true - Selection was successful
//     - element: HTMLElement - The selected DOM element
//     - selector: string - Generated CSS selector for the element
//     - rect: object - Bounding rectangle {x, y, width, height, left, top, right, bottom}
//     - tagName: string - Lowercase tag name of the element
//     - id: string - Element's ID attribute (empty string if none)
//     - className: string - Element's class attribute (empty string if none)
//
// Features:
//   - Real-time visual feedback with highlight border and tooltip
//   - Hierarchical element selection using Ctrl/Shift+Ctrl navigation
//   - Detailed element information display (selector, position, dimensions)
//   - Non-blocking overlay that preserves prompt dialog interaction
//   - Automatic CSS selector generation for selected elements
//   - Optional attribute setting on picked elements for marking
//   - Configurable element filtering to avoid system UI components
//   - Responsive tooltip positioning with viewport edge detection
//
// Visual Feedback:
//   - Blue highlight border around hoverable elements
//   - Tooltip showing element selector and position information
//   - Hierarchical level indicator when using keyboard navigation
//   - Mode indicators for Ctrl (parent) and Shift+Ctrl (child) navigation
//
// Error Handling:
//   - Returns null if user cancels with Escape key
//   - Returns null if no valid element can be found at click position
//   - Gracefully handles DOM changes during selection process
//   - Safe attribute setting with try-catch error handling
//
// Cleanup:
//   - Automatically removes overlay and event listeners on completion
//   - Prevents memory leaks by proper cleanup of DOM references
//   - Ensures only one picker instance can be active at a time
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
	
	// normalize opts.attr
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
		return { key: "data-manual-picked", value: "true" };
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
		let shiftDown = false;
		
		// NEW: ladder selection
		// ladder[0] = hovered element; ladder[1] = parent; ladder[2] = grandparent...
		let ladder = [];
		let ladderIdx = 0;
		
		const rebuildLadder = (baseEl) => {
			ladder = [];
			ladderIdx = 0;
			let cur = baseEl;
			while (cur && cur.nodeType === 1) {
				ladder.push(cur);
				cur = cur.parentElement;
			}
		};
		
		const getCurrentLadderEl = () => {
			if (!ladder.length) return null;
			ladderIdx = clamp(ladderIdx, 0, ladder.length - 1);
			return ladder[ladderIdx] || null;
		};
		
		const getEffectiveTarget = (fallbackEl) => {
			return getCurrentLadderEl() || fallbackEl || null;
		};
		
		const updateUI = (rawEl, mouseX, mouseY) => {
			const cand = getEffectiveTarget(rawEl);
			
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
			const mode = shiftDown ? "SHIFT+CTRL→CHILD  " : "CTRL→PARENT  ";
			const modeShown = ctrlDown ? mode : (ladderIdx > 0 ? "LEVEL↑  " : "");
			const levelInfo = ladder.length ? `lvl:${ladderIdx}/${Math.max(0, ladder.length - 1)}  ` : "";
			tip.textContent = `${modeShown}${levelInfo}${sel}  —  x:${rx} y:${ry} w:${rw} h:${rh}`;
			
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
				ladder = [];
				ladderIdx = 0;
				return;
			}
			
			const el = findElementFromPoint(e.clientX, e.clientY);
			
			// If hover target changes, reset ladder to that element
			if (el !== hoveredEl) {
				hoveredEl = el;
				if (hoveredEl) rebuildLadder(hoveredEl);
				else { ladder = []; ladderIdx = 0; }
			}
			
			updateUI(hoveredEl, e.clientX, e.clientY);
		};
		
		const finalizePick = (rawEl) => {
			const el = getEffectiveTarget(rawEl);
			if (!el) return cleanup(null);
			
			// Apply attribute on picked element (best-effort)
			if (pickAttr) {
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
			
			// Determine raw hovered target under cursor
			const raw = hoveredEl
				|| findElementFromPoint(lastMouse.x, lastMouse.y)
				|| (e.target && !shouldIgnoreTarget(e.target) ? e.target : null);
			
			if (preventPageClick) {
				e.preventDefault();
				e.stopPropagation();
				if (e.stopImmediatePropagation) e.stopImmediatePropagation();
			}
			
			// If ladder not built yet, build from raw
			if (!ladder.length && raw) rebuildLadder(raw);
			
			finalizePick(raw);
		};
		
		const onKeyDown = (e) => {
			if (!active || !e) return;
			
			if (e.key === "Escape" || e.key === "Esc") {
				e.preventDefault();
				e.stopPropagation();
				if (e.stopImmediatePropagation) e.stopImmediatePropagation();
				return cleanup(null);
			}
			
			if (e.key === "Shift") {
				if (!shiftDown) {
					shiftDown = true;
					updateUI(hoveredEl, lastMouse.x, lastMouse.y);
				}
				return;
			}
			
			if (e.key === "Control" || e.key === "Ctrl") {
				if (!ctrlDown) {
					ctrlDown = true;
					
					// Ensure ladder exists (if user presses keys before moving mouse)
					if (!ladder.length && hoveredEl) rebuildLadder(hoveredEl);
					
					// Step ladder:
					// - Ctrl: go up (parent)
					// - Shift+Ctrl: go down (child)
					if (ladder.length) {
						if (shiftDown) ladderIdx = Math.max(0, ladderIdx - 1);
						else ladderIdx = Math.min(ladder.length - 1, ladderIdx + 1);
					}
					
					updateUI(hoveredEl, lastMouse.x, lastMouse.y);
				}
			}
		};
		
		const onKeyUp = (e) => {
			if (!active || !e) return;
			
			if (e.key === "Shift") {
				if (shiftDown) {
					shiftDown = false;
					updateUI(hoveredEl, lastMouse.x, lastMouse.y);
				}
				return;
			}
			
			if (e.key === "Control" || e.key === "Ctrl") {
				if (ctrlDown) {
					ctrlDown = false;
					// NOTE: we do NOT reset ladderIdx here; selection stays sticky
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

export {inPagePrompt,inPageDismissPrompt,inPageTip,inPageTipDismiss,inPagePickDomElement,inPageShowSelector,inPageDismissSelector};