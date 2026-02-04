
const codeLib=(codeTag)=>{
	const stdExcludes=new Set(["SCRIPPT","STYLE"]);
	let nextAAEId=0;
	const allowedAttributes=new Set([
		"aaeid","class","contenteditable","class","hidden","id","style","title",
		"aria-label","role",
		"name","value","placeholder","required","disabled","readonly","type",
		"href","alt","src"
	]);
	if(globalThis[codeTag]){
		return;
	}
	globalThis[codeTag]={
		//Wrap a node to AAE-Obj:
		"markNode":function(node){
			let aaeId,rect,handlers;
			if(node.nodeType===3){
				return;
			}
			if(node.getAttribute){
				let names,name,attrs;
				aaeId=node.getAttribute("AAEId");
				if(!aaeId){
					aaeId=""+(nextAAEId++);
					node.setAttribute("aaeid",aaeId);
				}
			}
			if(node.getBoundingClientRect && ((node.offsetWidth>0 && node.offsetHeight) || node===document.body)){
				rect=node.getBoundingClientRect();
				if(rect){
					node.setAttribute("aaerect",`${rect.x},${rect.y},${rect.width},${rect.height}`);
					let styles,wrapedStyle;
					styles = window.getComputedStyle(node);
					wrapedStyle={
						"display":styles.display,
						"position":styles.position,
						"overflow":styles.overflow,
						"opacity":styles.opacity,
						"visibility":styles.visibility,
					};
					if(styles.pointerEvents!=="none" && rect.width>0 && rect.height>0){
						wrapedStyle.touchable=true;
					}
					if(styles.fontWeight!=="400"){
						wrapedStyle.fontWeight=styles.fontWeight;
					}
					wrapedStyle.offsetParent=!!node.offsetParent;
					node.setAttribute("aaestyle",JSON.stringify(wrapedStyle));
				}
				if(window.getEventListeners){
					handlers=window.getEventListeners(node);
					if(handlers){
						handlers=Object.keys(handlers);
						node.setAttribute("aaehandlers",JSON.stringify(handlers));
					}
				}
			}
		},
		
		"cleanNode":function(node){
			if(node.removeAttribute){
				node.removeAttribute("aaerect");
				node.removeAttribute("aaestyle");
				node.removeAttribute("aaehandlers");
			}
		},
		
		"wrapNode":function(node,sizeInfo,opts){
			let wraped,aaeId,rect,handlers;
			let filterAttrs;
			opts=opts||{filterAttrs:true};
			filterAttrs=opts.filterAttrs;
			if(node.nodeType===3){
				return {
					nodeType:node.nodeType,
					tagName:node.tagName,
					text:node.textContent
				};
			}
			if(!sizeInfo){
				sizeInfo=document.body.getBoundingClientRect();
			}
			wraped={
				nodeType:node.nodeType,
				tagName:node.tagName,
			};
			if(node.getAttribute){
				let value,names,name,attrs,pts;
				aaeId=node.getAttribute("AAEId");
				if(!aaeId){
					aaeId=""+(nextAAEId++);
					node.setAttribute("AAEId",aaeId);
				}
				wraped.AAEId=aaeId;
				wraped.id=node.getAttribute("id");
				wraped.class=node.getAttribute("class");
				attrs=wraped.attrs={};
				names=node.getAttributeNames();
				for(name of names){
					if(filterAttrs){
						if(allowedAttributes.has(name)){
							if(name==="class"){
								value=node.getAttribute(name);
								pts=value.split(" ");
								if(pts.length>3){
									pts.splice(3);
								}
								attrs[name]=pts.join(" ");
							}else{
								attrs[name]=node.getAttribute(name);
							}
						}
					}else{
						attrs[name]=node.getAttribute(name);
					}
				}
			}
			if(!node.childNodes || !node.childNodes.length){
				wraped.text=node.innerText||node.textContent;
			}
			wraped.touchable=false;
			if(node.getBoundingClientRect && ((node.offsetWidth>0 || node.offsetHeight>0) || node===document.body)){
				rect=node.getBoundingClientRect();
				if(rect){
					let styles;
					wraped.rect={x:rect.x,y:rect.y,width:rect.width,height:rect.height};
					wraped.rect.x=rect.x;
					wraped.rect.y=rect.y;
					wraped.rect.cx=wraped.rect.x+wraped.rect.width*0.5;
					wraped.rect.cy=wraped.rect.y+wraped.rect.height*0.5;
					wraped.rect.right=(rect.x+rect.width)-sizeInfo.right;
					wraped.rect.bottom=(rect.y+rect.height)-sizeInfo.bottom;
					wraped.rect.scx=wraped.rect.cx/sizeInfo.width;
					wraped.rect.scy=wraped.rect.cy/sizeInfo.height;
					styles = window.getComputedStyle(node);
					if(styles.pointerEvents!=="none" && rect.width>0 && rect.height>0){
						wraped.touchable=true;
					}
					wraped.style={
						"display":styles.display,
						"position":styles.position,
						"overflow":styles.overflow,
						"opacity":styles.opacity,
						"visibility":styles.visibility,
					};
					if(styles.fontWeight!=="400"){
						wraped.style.fontWeight=styles.fontWeight;
					}
				}
			}
			if(window.getEventListeners){
				handlers=window.getEventListeners(node);
				if(handlers){
					handlers=Object.keys(handlers);
					wraped.handleEvents=handlers;
				}
			}
			return wraped;
		},
		
		"markNodeTree":function(node){
			let list,i,n,sub;
			this.markNode(node);
			list=node.childNodes;
			n=list.length;
			for(i=0;i<n;i++) {
				sub = list[i];
				this.markNodeTree(sub);
			}
		},
		
		"cleanNodeTree":function(node){
			let list,i,n,sub;
			this.cleanNode(node);
			list=node.childNodes;
			n=list.length;
			for(i=0;i<n;i++) {
				sub = list[i];
				this.cleanNode(sub);
			}
		},
		
		"readMarkedHTML":function(aaeId,mark=true,clean=true){
			let node,html;
			if(aaeId){
				if(typeof(aaeId)==="string") {
					node = document.querySelector(`[aaeid="${aaeId}"]`);
				}else if (aaeId instanceof HTMLElement){
					node=aaeId;
				}else{
					node=document.body;
				}
			}else{
				node=document.body;
			}
			if(mark) {
				this.markNodeTree(node);
			}
			html=node.innerHTML;
			if(clean){
				this.cleanNodeTree(node);
			}
			return html;
		},
		
		"genNodeView":function(node,opts){
			let sizeInfo,includes,excludes;
			let json,tagName,list,sub,i,n,children,rect,subJson,compactTree,style,subStyle;
			opts=opts||{};
			sizeInfo=opts.sizeInfo||null;
			includes=opts.includes||null;
			excludes=(opts.excludes===undefined)?stdExcludes:null;
			compactTree=opts.compactTree===true;
			if(!sizeInfo){
				sizeInfo=document.body.getBoundingClientRect();
			}
			json=this.wrapNode(node,sizeInfo);
			rect=json.rect;
			if(json && rect){
				children=[];
				list=node.childNodes;
				n=list.length;
				style=json.style||getComputedStyle(node);
				if(rect.width<=1 || rect.height<=1){
					if(style.overflow==="hidden"||style.overflow==="clip"){
						n=0;
					}
				}
				if(style.opacity==="0"){
					return null;
				}
				for(i=0;i<n;i++){
					sub=list[i];
					
					if(sub.nodeType===1){
						tagName=sub.tagName;
						subStyle=window.getComputedStyle(sub);
						if(subStyle.position==="fixed"){
							if(!(sub.offsetWidth>0) || !(sub.offsetHeight>0)){
								continue;
							}
						}else if(!sub.offsetParent || !sub.getBoundingClientRect){
							continue;
						}
						if(includes && !includes.has(tagName)){
							continue;
						}
						if(excludes && excludes.has(tagName)){
							continue;
						}
					}
					try{
						opts.sizeInfo=sizeInfo;
						subJson=this.genNodeView(sub,opts);
						if(subJson){
							if(compactTree && subJson.tagName==="DIV"){
								let subSubs;
								subSubs=subJson.children;
								if(subSubs && subSubs.length===1 && subSubs[0].rect){
									subSubs[0].rect=subJson.rect;
									children.push(subSubs[0]);
								}else{
									children.push(subJson);
								}
							}else{
								children.push(subJson);
							}
						}
					}catch(err){
					}
				}
				if(children.length>0){
					json.children=children;
				}else{
					if(style.visibility==="hidden" || style.visibility==="collapse"){
						return null;
					}
				}
			}
			if(json.nodeType===3){
				if(!json.text.trim()){
					return null;
				}
			}else if(!json.children){
				if(rect.width<=1 || rect.height<=1){
					return null;
				}
			}
			return json;
		},
		
		//---------------------------------------------------------------
		//截取一个节点，根据opts里的设置裁剪
		"snapNode":function(orgNode,opts,parentNode){
			let snappedNode,nodeType,excludeNodeTags,excludeTags,aaeId;
			let cmpStyle,nodeTag,clientRect,nullSized;
			if(typeof(orgNode)==="string"){
				orgNode = document.querySelector(`[aaeid="${orgNode}"]`);
			}
			orgNode=orgNode||document.body;
			nodeType=orgNode.nodeType;
			excludeTags=(opts.excludeTags===undefined)?stdExcludes:(opts.excludeTags||null);
			if(!("removeHidden" in opts)){
				opts.removeHidden=true;
			}
			if(nodeType!==3 && nodeType!==1 && nodeType!==9){
				//Only snap DOCUMENT, ELEMENT_NODE and TEXT_NODE
				return null;
			}
			switch(nodeType){
				case 3:{//Text node
					if(orgNode.nodeValue==="跳至主內容"){
						nodeType=3;
					}
					if(opts.removeHidden && parentNode) {
						if (parentNode.$nullSized) {
							return null;
						}
						if (parentNode.$cmpStyle.opacity === "0") {
							return null;
						}
						if (parentNode.$cmpStyle.visibility === "none") {
							return null;
						}
					}
					snappedNode=orgNode.cloneNode(false);
					break;
				}
				case 9:{
					snappedNode=orgNode.cloneNode(false);
					break;
				}
				case 1:{//Elements, check if we should exclude this node for exporting:
					cmpStyle=getComputedStyle(orgNode);
					snappedNode=orgNode.cloneNode(false);
					nullSized=false;
					snappedNode.$nullSized=false;
					
					nodeTag=orgNode.nodeName;
					clientRect=orgNode.getBoundingClientRect();
					
					//Filter out none-visible elements that not depends on their children:
					{
						if(excludeTags.has(nodeTag)) {
							return null;
						}
						if(opts.removeHidden) {//Result should not include hidden elements:
							if (cmpStyle.display === "none") {
								return null;
							}
							if (cmpStyle.visibility === "hidden") {
								return null;
							}
						}
					}
					
					//Check if this element is null-sized?
					{
						if (parentNode && parentNode.$nullSized && cmpStyle.position !== "fixed") {
							nullSized = true;
							snappedNode.$nullSized = true;
						}else if ((clientRect.width <= 1 && clientRect.height <= 1)|| clientRect.width<1 || clientRect.height<1) {//Too small to see?
							let overflow;
							nullSized = true;
							overflow = cmpStyle.overflow;
							if (overflow === "scroll" || "hidden") {//Parent is nullSized, and this node will apply parent
								snappedNode.$nullSized = true;
							}
						}
					}
					
					//Generate child nodes:
					if(snappedNode){
						let snappedChildren=[];
						try {
							snappedNode.$orgNode = orgNode;
							snappedNode.$cmpStyle = cmpStyle;
							snappedNode.$clientRect = clientRect;
							
							//Snap children:
							orgNode.childNodes.forEach(child => {
								let subNode;
								subNode=this.snapNode(child,opts,snappedNode);
								if(subNode){
									snappedChildren.push(subNode);
								}
							});
							if (snappedChildren.length) {
								snappedChildren.forEach(child=>{
									snappedNode.appendChild(child);
								})
							}else if(opts.removeHidden){//Filter out no-children-none-visible elements and
								if (nullSized) {
									return null;
								}
								if (cmpStyle.visibility === "hidden") {
									return null;
								}
								if (cmpStyle.opacity === "0") {
									return null;
								}
							}
							
						}catch (err){
							return null;
						}finally {
							//Do something?
						}
						if(snappedNode.style.visibility!==cmpStyle.visibility) snappedNode.style.visibility=cmpStyle.visibility;
						if(snappedNode.style.display!==cmpStyle.display) snappedNode.style.display=cmpStyle.display;
						if(snappedNode.style.opacity!==cmpStyle.opacity) snappedNode.style.opacity=cmpStyle.opacity;
					}
				}
			}
			if(opts.mark) {//Add aae-marks
				aaeId = orgNode.getAttribute("AAEId");
				if (!aaeId) {
					aaeId = "" + (nextAAEId++);
					orgNode.setAttribute("AAEId", aaeId);
				}
				snappedNode.setAttribute("AAEId", aaeId);
				
				if(clientRect) {
					snappedNode.setAttribute("aaerect", `${clientRect.x},${clientRect.y},${clientRect.width},${clientRect.height}`);
					if(cmpStyle){
						let wrappedStyle={
							"display":cmpStyle.display,
							"position":cmpStyle.position,
							"overflow":cmpStyle.overflow,
							"opacity":cmpStyle.opacity,
							"visibility":cmpStyle.visibility,
						};
						if(cmpStyle.pointerEvents!=="none" && clientRect.width>0 && clientRect.height>0){
							wrappedStyle.touchable=true;
						}
						if(cmpStyle.fontWeight!=="400"){
							wrappedStyle.fontWeight=styles.fontWeight;
						}
						wrappedStyle.offsetParent=!!orgNode.offsetParent;
						snappedNode.setAttribute("aaestyle",JSON.stringify(wrappedStyle));
					}
				}
			}
			return snappedNode;
		},
		
		//---------------------------------------------------------------
		"snapNodeHTML":function(orgNode,opts){
			let snappedNode;
			console.log(`Will read HTML.`);
			snappedNode=this.snapNode(orgNode,opts,null);
			if(!snappedNode){
				return ""
			}
			if(snappedNode.nodeType===9){//document:
				return snappedNode.documentElement.outerHTML;
			}
			return snappedNode.outerHTML;
		},
		
		//---------------------------------------------------------------
		"readNodeView":function(aaeId,opts){
			let node;
			if(aaeId){
				node=document.querySelector(`[aaeid="${aaeId}"]`);
			}else{
				node=document.body;
			}
			if(node){
				return this.genNodeView(node,opts);
			}
			return null;
		},
		
		//---------------------------------------------------------------
		"readNodeText":function(aaeId){
			let node;
			if(aaeId){
				node=document.querySelector(`[aaeid="${aaeId}"]`);
			}else{
				node=document.body;
			}
			if(node){
				return node.innerText;
			}
			return null;
		},
		
		//---------------------------------------------------------------
		"readNodeHTML":function(aaeId){
			let node;
			if(aaeId){
				node=document.querySelector(`[aaeid="${aaeId}"]`);
			}else{
				node=document.body;
			}
			if(node){
				return node.innerHTML;
			}
			return null;
		},
		
		//---------------------------------------------------------------
		"getInnerHTML":function(aaeId){
			let node;
			if(aaeId){
				node=document.querySelector(`[aaeid="${aaeId}"]`);
			}else{
				node=document.body;
			}
			if(node){
				return node.innerHTML;
			}
			return null;
		},
		
		"readPageHTML":function(){
			return document.body.innerHTML;
		},
		
		"getNodeAttribute":function(aaeId,key){
			let node;
			node=document.querySelector(`[aaeid="${aaeId}"]`);
			if(node && node.getAttributeNames){
				return node.getAttribute(key);
			}
			return null;
		},
		
		"setNodeAttribute":function(aaeId,key,value){
			let node;
			node=document.querySelector(`[aaeid="${aaeId}"]`);
			if(node && node.getAttributeNames){
				node.setAttribute(key,value);
				return true;
			}
			return false;
		},
		
		"getNodeAttributes":function(aaeId){
			let node;
			node=document.querySelector(`[aaeid="${aaeId}"]`);
			if(node && node.getAttributeNames){
				let names,name,attrs;
				attrs={};
				names=node.getAttributeNames();
				for(name of names){
					attrs[name]=node.getAttribute(name);
				}
				return attrs;
			}
			return null;
		},
		
		"getNodeParent":function(aaeId){
			let node;
			node=document.querySelector(`[aaeid="${aaeId}"]`);
			if(node){
				node=node.parentNode;
				if(node && node!==document){
					return this.wrapNode(node);
				}
			}
			return null;
		},
		
		"getNodeChildren":function(aaeId){
			let node,tagName;
			node=document.querySelector(`[aaeid="${aaeId}"]`);
			if(node){
				let list,i,n,subs,sub;
				list=node.childNodes;
				if(list){
					subs=[];
					n=list.length;
					for(i=0;i<n;i++){
						sub=list[i];
						if(sub.nodeType!==3){
							tagName=sub.tagName;
							if(!sub.offsetParent || !sub.getBoundingClientRect){
								continue;
							}
							if(stdExcludes.has(tagName)){
								continue;
							}
						}
						sub=this.wrapNode(sub);
						if(sub){
							subs.push(sub);
						}
					}
					return subs;
				}
			}
		},
		
		"queryNodes":function(aaeId,selector,opts){
			let list,i,n,node,wraped,visibleOnly,contextNode,wNode,isXPath;
			wraped=[];
			visibleOnly=opts?(opts.filterVisible===false?false:true):true;
			try{
				if(aaeId){
					node = document.querySelector(`[aaeid="${aaeId}"]`);
					if(!node){
						return null;
					}
					contextNode=node;
				}else{
					contextNode=document;
				}
				if (selector.startsWith('::-p-xpath')) {//pup-style XPath
					isXPath=true;
					selector=selector.substring('::-p-xpath'.length).trim();
				}else if(selector.startsWith("xpath:")){
					isXPath=true;
					selector=selector.substring('xpath:'.length).trim();
				}else if (selector.startsWith('(')) {
					isXPath=true;
				}else if (selector.startsWith('css:')) {//CSS selector
					isXPath=false;
					selector=selector.substring('css:'.length).trim();
				}else{
					isXPath=false;
				}
				if(isXPath){
					let result;
					//This is a XPath querry:
					result = document.evaluate(selector, contextNode, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
					n=result.snapshotLength;
					for(i=0;i<n;i++){
						node = result.snapshotItem(i);
						wNode=this.wrapNode(node,null,undefined,opts);
						if(visibleOnly){
							let rect;
							rect=wNode.rect;
							if(!rect) {
								continue;
							}
							if(rect.width<=1 || rect.height<=1){
								let style=wNode.style;
								if(style.overflow==="hidden"||style.overflow==="clip"){
									continue;
								}
							}
						}
						wraped.push(wNode);
					}
				}else{
					//This is a normal node querry:
					list=contextNode.querySelectorAll(selector);
					n=list.length;
					for(i=0;i<n;i++){
						node=list[i];
						wNode=this.wrapNode(node,null,undefined,opts);
						if(visibleOnly){
							let rect;
							rect=wNode.rect;
							if(!rect) {
								continue;
							}
							if(rect.width<=1 || rect.height<=1){
								let style=wNode.style;
								if(style.overflow==="hidden"||style.overflow==="clip"){
									continue;
								}
							}
						}
						wraped.push(node);
					}
				}
			}catch(err){
				console.log("QueryNodes error:");
				console.log(err);
			}
			return wraped;
		},
		
		"queryNode":function(aaeId,selector,opts){
			let list;
			list=this.queryNodes(aaeId,selector,opts);
			if(list){
				return list[0];
			}
			return null;
		},
		
		/**
		 * computeSigKey(el)
		 * -------------------
		 * Stronger sigKey that includes MULTIPLE strong attributes (not just one),
		 * while remaining stable across minor UI changes.
		 *
		 * Designed so that:
		 * - Different "Send" buttons in different dialogs/forms tend to have different keys (anchor helps).
		 * - List items of the same type may share the same key (acceptable for multi-select workflows).
		 */
		"computeSigKey":function(el,opts)
		{
			opts = (opts && typeof opts === "object") ? opts : {};
			const allowMulti = (opts.allowMulti === true);
			const debug = !!opts.debug;
			const noOrd = !!opts._noOrd; // internal: prevent ord recursion
			
			// v3.10: "instance" (default) vs "class"
			// - instance: precise identity (buttons etc), may include txt/icon/ord
			// - class: generic "type" signature (post cards/list items), avoids content text and ord
			const sigMode = (opts.sigMode === "class") ? "class" : "instance";
			
			const maxKeyLen = Number.isFinite(opts.maxKeyLen) ? opts.maxKeyLen : 900;
			const maxLiftScan = Number.isFinite(opts.maxLiftScan) ? opts.maxLiftScan : 300;
			const maxScanNodes = Number.isFinite(opts.maxScanNodes) ? opts.maxScanNodes : 6000;
			const maxTextLen = Number.isFinite(opts.maxTextLen) ? opts.maxTextLen : 160;
			
			// editable label fallback cap (avoid user-typed content changing sig)
			const editableFallbackTextMax = Number.isFinite(opts.editableFallbackTextMax)
				? opts.editableFallbackTextMax
				: 20;
			
			// v3.10: for class mode, cap any fallback label even more (avoid content)
			const classFallbackTextMax = Number.isFinite(opts.classFallbackTextMax)
				? opts.classFallbackTextMax
				: 0; // default 0 == disable rendered-text fallback for non-clickable blocks
			
			try {
				if (!el || el.nodeType !== 1) return null;
				
				// ---------------- helpers ----------------
				const norm = (s, max = maxTextLen) =>
					(s == null ? "" : String(s))
						.replace(/\s+/g, " ")
						.trim()
						.slice(0, max);
				
				const getAttr = (node, name) => {
					try {
						const v = node.getAttribute(name);
						return v == null ? "" : String(v);
					} catch {
						return "";
					}
				};
				
				const tinyHash = (s) => {
					s = String(s || "");
					let h = 2166136261;
					for (let i = 0; i < s.length; i++) {
						h ^= s.charCodeAt(i);
						h = Math.imul(h, 16777619);
					}
					return (h >>> 0).toString(36);
				};
				
				const sampledHash = (data, head = 512, tail = 512) => {
					data = String(data || "");
					const len = data.length;
					if (len <= head + tail) return tinyHash(data);
					return tinyHash(data.slice(0, head) + "|" + data.slice(len - tail));
				};
				
				const parseDataUrl = (url) => {
					url = String(url || "");
					if (!url.startsWith("data:")) return null;
					const comma = url.indexOf(",");
					if (comma < 0) return null;
					const meta = url.slice(5, comma);
					const data = url.slice(comma + 1);
					const mime = (meta.split(";")[0] || "").trim().toLowerCase() || "text/plain";
					const isBase64 = /;\s*base64\s*$/i.test(meta);
					return { mime, isBase64, data };
				};
				
				const dataUrlSig = (url) => {
					const p = parseDataUrl(url);
					if (!p) return "";
					const len = p.data.length;
					const h = sampledHash(p.data, 256, 256);
					return `data:${p.mime}|b64=${p.isBase64 ? 1 : 0}|len=${len}|h=${h}`;
				};
				
				const shortUrl = (u, max = 140) => {
					u = (u == null) ? "" : String(u).trim();
					if (!u) return "";
					if (/^data:/i.test(u)) return dataUrlSig(u);
					if (/^(blob:|about:)/i.test(u)) return u.slice(0, 40);
					const hashPos = u.indexOf("#");
					if (hashPos >= 0) u = u.slice(0, hashPos);
					const qPos = u.indexOf("?");
					if (qPos >= 0) u = u.slice(0, qPos);
					if (u.length > max) u = u.slice(-max);
					return u;
				};
				
				const getTestId = (node) => {
					const keys = ["data-testid", "data-test", "data-qa", "data-cy"];
					for (const k of keys) {
						const v = norm(getAttr(node, k), 80);
						if (v) return v;
					}
					return "";
				};
				
				const getRole = (node) => norm(getAttr(node, "role"), 60) || "";
				const getType = (node) => norm(getAttr(node, "type"), 40) || "";
				const getName = (node) => norm(getAttr(node, "name"), 80) || "";
				const getId = (node) => norm(node.id, 80) || "";
				const getAriaLabel = (node) => norm(getAttr(node, "aria-label"), 200) || "";
				const getPlaceholder = (node) => norm(getAttr(node, "placeholder"), 200) || "";
				
				const getLabelledByText = (node) => {
					const ids = norm(getAttr(node, "aria-labelledby"), 240);
					if (!ids) return "";
					const parts = ids.split(/\s+/).filter(Boolean);
					const texts = [];
					for (const id of parts) {
						const target = document.getElementById(id);
						if (!target) continue;
						const t = norm(target.textContent || "", 200);
						if (t) texts.push(t);
						if (texts.join(" ").length > 240) break;
					}
					return norm(texts.join(" "), 240);
				};
				
				const isEditable = (node) => {
					const tag = (node.tagName || "").toLowerCase();
					// never treat real controls as editable
					if (tag === "button" || tag === "a") return false;
					if (tag === "input" || tag === "textarea") return true;
					const ce = getAttr(node, "contenteditable");
					return ce === "" || String(ce).toLowerCase() === "true";
				};
				
				const hasInteractiveAria = (node) =>
					!!(getAttr(node, "aria-pressed") || getAttr(node, "aria-expanded") || getAttr(node, "aria-haspopup"));
				
				const isClickableLike = (node) => {
					try {
						const tag = (node.tagName || "").toLowerCase();
						const role = getRole(node);
						const type = getType(node);
						
						if (tag === "button") return true;
						if (tag === "a" && (getAttr(node, "href") || "").trim()) return true;
						if (role === "button" || role === "link") return true;
						if (type === "submit" || type === "button") return true;
						
						if (getTestId(node)) return true;
						
						const tabindex = getAttr(node, "tabindex");
						if (tabindex !== "" && !Number.isNaN(Number(tabindex)) && Number(tabindex) >= 0) return true;
						
						if (getAttr(node, "onclick")) return true;
						if (hasInteractiveAria(node)) return true;
						
						try {
							const cs = window.getComputedStyle(node);
							if (cs && cs.cursor === "pointer") return true;
						} catch {}
						
						return false;
					} catch {
						return false;
					}
				};
				
				const kindOf = (node) => {
					const tag = (node.tagName || "").toLowerCase();
					const role = getRole(node);
					const type = getType(node);
					
					if (isEditable(node)) {
						if (tag === "textarea") return "textbox|textarea";
						if (tag === "input") return "textbox|input:" + (type || "text");
						return "textbox|editable";
					}
					
					const buttonish = (tag === "button" || role === "button" || type === "submit" || isClickableLike(node));
					if (buttonish) return "button|" + (type ? type : (role ? "role=" + role : "clickable"));
					
					if (tag === "a") return "link|" + (role ? "role=" + role : "a");
					
					return tag || "element";
				};
				
				const getPseudoText = (node) => {
					try {
						const clean = (c) => {
							c = String(c || "").trim();
							if (!c || c === "none" || c === "normal") return "";
							c = c.replace(/^["']|["']$/g, "");
							return norm(c, 120);
						};
						const b = clean(window.getComputedStyle(node, "::before")?.content || "");
						const a = clean(window.getComputedStyle(node, "::after")?.content || "");
						return norm([b, a].filter(Boolean).join(" "), 160);
					} catch {
						return "";
					}
				};
				
				const getRenderedText = (node) => {
					try {
						if (!node || node.nodeType !== 1) return "";
						const it = norm(node.innerText || "", 200);
						if (it) return it;
						const tc = norm(node.textContent || "", 200);
						return tc;
					} catch {
						return "";
					}
				};
				
				// v3.10: label extraction modes
				// - clickable: allow rendered text (buttons)
				// - editable: stable attrs, very short fallback
				// - stableOnly: only stable attrs (aria/title/placeholder/name), no rendered text
				// - any: allow rendered text (but class mode will usually avoid using this)
				const getNodeLabel = (node, mode) => {
					if (!node || node.nodeType !== 1) return "";
					
					const aria = getAriaLabel(node);
					if (aria) return aria;
					
					const alby = getLabelledByText(node);
					if (alby) return alby;
					
					const title = norm(getAttr(node, "title"), 200);
					if (title) return title;
					
					const ph = getPlaceholder(node);
					if (ph && (mode === "editable" || mode === "stableOnly")) return ph;
					if (ph && mode === "any") return ph;
					
					const nm = getName(node);
					if (nm && (mode === "editable" || mode === "stableOnly")) return nm;
					
					if (mode === "stableOnly") return "";
					
					if (mode === "editable") {
						const t = norm(getRenderedText(node), editableFallbackTextMax);
						if (t) return t;
						const p = getPseudoText(node);
						if (p) return norm(p, editableFallbackTextMax);
						return "";
					}
					
					// clickable / any
					const t = getRenderedText(node);
					if (t) return t;
					
					const p = getPseudoText(node);
					if (p) return p;
					
					if (node.querySelectorAll) {
						const all = Array.from(node.querySelectorAll("*")).slice(0, 80);
						for (const c of all) {
							const tc = getRenderedText(c);
							if (tc) return tc;
							const pc = getPseudoText(c);
							if (pc) return pc;
						}
					}
					return "";
				};
				
				// -------- icon signature (img/svg/bg/mask) --------
				const canonicalizeSvgMarkup = (markup) => {
					markup = String(markup || "");
					if (!markup) return "";
					markup = markup.replace(/<!--[\s\S]*?-->/g, "");
					markup = markup
						.replace(/\s(?:id|class|style)=(".*?"|'.*?')/gi, "")
						.replace(/\sdata-[\w-]+=(".*?"|'.*?')/gi, "")
						.replace(/\saria-[\w-]+=(".*?"|'.*?')/gi, "")
						.replace(/\son\w+=(".*?"|'.*?')/gi, "");
					markup = markup.replace(/'/g, '"');
					markup = markup.replace(/\s+/g, " ").trim();
					return markup;
				};
				
				const svgSig = (svgEl) => {
					try {
						if (!svgEl || svgEl.nodeType !== 1) return "";
						if ((svgEl.tagName || "").toLowerCase() !== "svg") return "";
						const use = svgEl.querySelector && svgEl.querySelector("use");
						if (use) {
							const href = use.getAttribute("href") || use.getAttribute("xlink:href") || "";
							if (href) return `svg:use=${href.slice(0, 80)}`;
						}
						const raw = svgEl.outerHTML || "";
						const canon = canonicalizeSvgMarkup(raw);
						if (!canon) return "svg:empty";
						return `svg:len=${canon.length}|h=${sampledHash(canon, 512, 512)}`;
					} catch {
						return "";
					}
				};
				
				const cssUrlFrom = (node, prop) => {
					try {
						const cs = window.getComputedStyle(node);
						const v = cs ? (cs[prop] || "") : "";
						const m = /url\((["']?)(.+?)\1\)/i.exec(v);
						if (!m) return "";
						return shortUrl(m[2]);
					} catch {
						return "";
					}
				};
				
				// v3.10: icon scan budget depends on sigMode
				// - instance: scan more (buttons)
				// - class: scan shallow (avoid content images inside posts)
				const getIconSig = (root, mode) => {
					try {
						if (!root || root.nodeType !== 1) return "";
						const isClass = (mode === "class");
						
						// shallow scan first: direct children and a few descendants
						const nodes = [root];
						const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null);
						const limit = isClass ? 12 : 80;
						let n = 0;
						while (walker.nextNode() && n++ < limit) nodes.push(walker.currentNode);
						
						// For class mode, prefer direct child icons first
						const pickOrder = isClass
							? nodes.sort((a, b) => (a.parentElement === root ? -1 : 0) - (b.parentElement === root ? -1 : 0))
							: nodes;
						
						for (const node of pickOrder) {
							if ((node.tagName || "").toLowerCase() === "img") {
								const src = shortUrl(node.currentSrc || node.src || "");
								const alt = norm(getAttr(node, "alt"), 60);
								const w = node.naturalWidth || node.width || 0;
								const h = node.naturalHeight || node.height || 0;
								return src ? `img:${src}|alt=${alt}|${w}x${h}` : `img:alt=${alt}|${w}x${h}`;
							}
						}
						
						for (const node of pickOrder) {
							if ((node.tagName || "").toLowerCase() === "svg") {
								const s = svgSig(node);
								if (s) return s;
							}
						}
						
						// background/mask: in class mode only check root itself
						const bgNodes = isClass ? [root] : pickOrder.slice(0, 30);
						
						for (const node of bgNodes) {
							const u = cssUrlFrom(node, "backgroundImage");
							if (u) return `bg:${u}`;
						}
						
						for (const node of bgNodes) {
							const u = cssUrlFrom(node, "maskImage") || cssUrlFrom(node, "webkitMaskImage");
							if (u) return `mask:${u}`;
						}
						
						return "";
					} catch {
						return "";
					}
				};
				
				// v3.10 lift: for instance mode, still lift to actionable; for class mode, DON'T lift unless wrapper is obviously a pure shell
				const liftToActionable = (node) => {
					try {
						if (!node || node.nodeType !== 1) return node;
						
						const strongSel =
							"button,a[href],input[type='submit'],input[type='button'],[role='button'],[role='link']";
						
						if (sigMode === "instance") {
							// same as v3.9: prefer clickable descendant
							if (node.closest) {
								const anc = node.closest(strongSel);
								if (anc && anc.nodeType === 1) return anc;
							}
							const strong = node.querySelector ? node.querySelector(strongSel) : null;
							if (strong && strong.nodeType === 1) return strong;
							
							if (node.querySelectorAll) {
								const all = Array.from(node.querySelectorAll("*")).slice(0, maxLiftScan);
								let best = null, bestScore = -1;
								
								const score = (c) => {
									if (!c || c.nodeType !== 1) return -1;
									if (!isClickableLike(c)) return -1;
									const tag = (c.tagName || "").toLowerCase();
									let s = 0;
									if (tag === "button") s += 100;
									if (tag === "a") s += 80;
									if (getRole(c) === "button") s += 70;
									if (getTestId(c)) s += 40;
									const lab = getNodeLabel(c, "clickable");
									if (lab) s += 30;
									return s;
								};
								
								for (const c of all) {
									const sc = score(c);
									if (sc > bestScore) {
										bestScore = sc;
										best = c;
										if (bestScore >= 120) break;
									}
								}
								if (best && bestScore >= 0) return best;
							}
							return node;
						}
						
						// class mode:
						// If wrapper is a pure shell that contains exactly one strong actionable control and has no own identity,
						// lift to that control. Otherwise keep wrapper to represent the "block".
						const ownId = getId(node);
						const ownTestId = getTestId(node);
						const ownRole = getRole(node);
						const ownClickable = isClickableLike(node);
						const ownEditable = isEditable(node);
						
						// has stable identity => keep wrapper
						if (ownId || ownTestId || ownRole || ownClickable || ownEditable) return node;
						
						// If exactly one strong actionable descendant exists, lift
						const list = node.querySelectorAll ? Array.from(node.querySelectorAll(strongSel)).slice(0, 3) : [];
						if (list.length === 1) return list[0];
						
						return node;
					} catch {
						return node;
					}
				};
				
				const findContainer = (node) => {
					const selectors = ["[role='dialog']", "dialog", "form", "main", "section", "nav", "header", "footer", "aside"];
					for (const sel of selectors) {
						const c = node.closest ? node.closest(sel) : null;
						if (c) return c;
					}
					return null;
				};
				
				const containerPart = (c) => {
					if (!c) return "c=none";
					const tag = (c.tagName || "").toLowerCase();
					const role = getRole(c);
					const id = getId(c);
					const testid = getTestId(c);
					let p = "c=" + (role ? ("role:" + role) : tag);
					if (testid) p += ":testid=" + testid;
					if (id) p += ":id=" + id;
					return p;
				};
				
				// v3.10: chain depth in class mode is smaller to reduce miss on layout changes
				const chainPart = (node, container) => {
					const items = [];
					const limit = (sigMode === "class") ? 1 : 3;
					
					let cur = node, guard = 0;
					while (cur && cur !== container && guard++ < 50) {
						cur = cur.parentElement;
						if (!cur || cur === container) break;
						const id = getId(cur);
						const testid = getTestId(cur);
						const role = getRole(cur);
						if (!id && !testid && !role) continue;
						const tag = (cur.tagName || "").toLowerCase();
						let frag = tag;
						if (testid) frag += "[testid=" + testid + "]";
						if (id) frag += "#" + id;
						if (role) frag += "[role=" + role + "]";
						items.push(frag);
						if (items.length >= limit) break;
					}
					return items.length ? ("chain=" + items.reverse().join(">")) : "chain=none";
				};
				
				// ---------------- normalize target ----------------
				const wrapper = el;
				const action = liftToActionable(el);
				
				const kind = kindOf(action);
				const editable = kind.startsWith("textbox|");
				const clickable = kind.startsWith("button|") || kind.startsWith("link|") || isClickableLike(action);
				
				// v3.10: label policy by sigMode
				const labelModeForAction =
					clickable ? "clickable" :
						(editable ? "editable" : (sigMode === "class" ? "stableOnly" : "any"));
				
				const labelAction = getNodeLabel(action, labelModeForAction);
				
				// class mode: avoid wrapper label fallback (prevents post content from entering)
				const labelWrapper =
					(wrapper === action) ? "" : getNodeLabel(wrapper, (sigMode === "class") ? "stableOnly" : labelModeForAction);
				
				const label =
					labelAction ||
					((sigMode === "instance" && !clickable) ? labelWrapper : "");
				
				// ids
				const ids = [];
				const id = getId(action);
				const testid = getTestId(action);
				const name = getName(action);
				if (id) ids.push("id=" + id);
				if (testid) ids.push("testid=" + testid);
				if (name) ids.push("name=" + name);
				const idsPart = "ids:" + (ids.length ? ids.join(";") : "none");
				
				// a11y
				const a11y = [];
				const alby = getLabelledByText(action);
				const aria = getAriaLabel(action);
				const ph = getPlaceholder(action);
				if (alby) a11y.push("alby=" + alby);
				if (aria) a11y.push("aria=" + aria);
				if (ph) a11y.push("ph=" + ph);
				
				let hasTxt = false;
				let hasIcon = false;
				
				if (clickable) {
					if (label && sigMode === "instance") {
						a11y.push("txt=" + norm(label, 160));
						hasTxt = true;
					} else if (label && sigMode === "class") {
						// class mode: only keep stable label (aria/title), never rendered content text
						a11y.push("lab=" + norm(label, 80));
					} else {
						const icon = getIconSig(action, sigMode);
						if (icon) {
							a11y.push("icon=" + icon);
							hasIcon = true;
						}
					}
				} else if (editable) {
					if (label) a11y.push("lab=" + norm(label, 160));
				} else {
					// non-clickable block
					if (sigMode === "instance") {
						// instance mode: allow short label fallback if user really wants (rare)
						if (classFallbackTextMax > 0) {
							const t = norm(getRenderedText(action), classFallbackTextMax);
							if (t) a11y.push("txt=" + t);
						}
					} else {
						// class mode: keep generic; optionally add a shallow icon if present
						const icon = getIconSig(action, sigMode);
						if (icon) {
							a11y.push("icon=" + icon);
							hasIcon = true;
						}
					}
				}
				
				if (wrapper !== action) a11y.push("lift=" + ((wrapper.tagName || "").toLowerCase()));
				
				const a11yPart = "a11y:" + (a11y.length ? a11y.join(";") : "none");
				const c = findContainer(action);
				const anchorPart = "anchor:" + containerPart(c) + "|" + chainPart(action, c);
				
				let key = "v3.10|" + kind + "|" + idsPart + "|" + a11yPart + "|" + anchorPart;
				if (key.length > maxKeyLen) key = key.slice(0, maxKeyLen);
				
				if (debug) {
					console.log("computeSigKey v3.10> sigMode:", sigMode);
					console.log("computeSigKey v3.10> wrapper:", wrapper);
					console.log("computeSigKey v3.10> action:", action);
					console.log("kind:", kind, "clickable:", clickable, "editable:", editable);
					console.log("labelAction:", labelAction, "labelWrapper:", labelWrapper, "picked:", label);
					console.log("hasTxt:", hasTxt, "hasIcon:", hasIcon, "allowMulti:", allowMulti, "noOrd:", noOrd);
					console.log("key:", key);
				}
				
				// ---------------- ord disambiguation ----------------
				// Only when: instance mode, allowMulti=false, clickable, no txt/icon, not internal call.
				const DISAMBIGUATE =
					(!noOrd) &&
					(sigMode === "instance") &&
					(!allowMulti) &&
					clickable &&
					(!hasTxt) &&
					(!hasIcon);
				
				if (DISAMBIGUATE) {
					try {
						const baseKey = key; // before ord/n
						const scope = (c && c.nodeType === 1) ? c : (document.body || document.documentElement || document);
						
						const computeBaseKeyFor = (node) => {
							try {
								if (!node || node.nodeType !== 1) return "";
								return computeSigKey(node, { ...opts, allowMulti: true, debug: false, _noOrd: true, sigMode }) || "";
							} catch {
								return "";
							}
						};
						
						const walker = document.createTreeWalker(scope, NodeFilter.SHOW_ELEMENT, null);
						
						let total = 0;
						let nSame = 0;
						let ord = 0;
						
						while (walker.nextNode()) {
							const cur = walker.currentNode;
							total++;
							if (total > maxScanNodes) break;
							
							const k2 = computeBaseKeyFor(cur);
							if (!k2) continue;
							
							if (k2 === baseKey) {
								nSame++;
								if (cur === wrapper) ord = nSame;
							}
						}
						
						if (nSame > 1 && ord > 0) {
							key += `|ord=${ord}|n=${nSame}`;
							if (key.length > maxKeyLen) key = key.slice(0, maxKeyLen);
						}
					} catch {
						// ignore
					}
				}
				
				return key;
			} catch {
				return null;
			}
		},
		"computeSigKeyForSelector": function(selector, opts) {
			console.log("computeSigKeyForSelector> selector:", selector);
			opts = (opts && typeof opts === "object") ? opts : {};
			
			// mode: "auto"(default) | "first" | "all"
			const mode = (opts.mode === "all") ? "all" : (opts.mode === "first" ? "first" : "auto");
			
			let sel = (selector == null) ? "" : String(selector).trim();
			if (!sel) return null;
			
			// default scheme: css
			let scheme = "css";
			const lower = sel.toLowerCase();
			if (lower.startsWith("css:")) {
				scheme = "css";
				sel = sel.slice(4).trim();
			} else if (lower.startsWith("xpath:")) {
				scheme = "xpath";
				sel = sel.slice(6).trim();
			}
			if (!sel) return null;
			
			// helpers
			const mergeSigOpts = (baseOpts, inferred) => {
				// user explicitly set => keep
				const out = { ...(baseOpts || {}) };
				
				if (out.allowMulti === undefined) out.allowMulti = inferred.allowMulti;
				if (out.sigMode === undefined) out.sigMode = inferred.sigMode;
				
				// pass-through debug if user wants
				if (baseOpts && baseOpts.debug !== undefined) out.debug = baseOpts.debug;
				
				return out;
			};
			
			const sigOf = (el, sigOpts) => {
				try {
					return el ? this.computeSigKey(el, sigOpts) : null;
				} catch {
					return null;
				}
			};
			
			try {
				// 1) Collect matches as list (always)
				let list = [];
				
				if (scheme === "css") {
					// always queryAll for counting + auto
					list = Array.from(document.querySelectorAll(sel));
				} else {
					// xpath -> snapshot list
					const doc = document;
					const ctxNode = doc;
					const res = doc.evaluate(sel, ctxNode, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
					const n = res.snapshotLength || 0;
					for (let i = 0; i < n; i++) {
						const node = res.snapshotItem(i);
						if (node && node.nodeType === 1) list.push(node);
					}
				}
				
				const n = list.length;
				
				if (mode === "first") {
					const el0 = list[0] || null;
					if (!el0) return null;
					// first implies single-target precision unless user overrides
					const inferred = { allowMulti: false, sigMode: "instance" };
					const sigOpts = mergeSigOpts(opts, inferred);
					console.log("computeSigKeyForSelector> el:", el0);
					const sigKey = sigOf(el0, sigOpts);
					console.log("computeSigKeyForSelector> sigKey:", sigKey);
					return sigKey;
				}
				
				if (mode === "all") {
					if (!n) return [];
					// all implies group/class unless user overrides
					const inferred = { allowMulti: true, sigMode: "class" };
					const sigOpts = mergeSigOpts(opts, inferred);
					const sigKeys = list.map(el => sigOf(el, sigOpts)).filter(Boolean);
					return sigKeys;
				}
				
				// mode === "auto"
				if (!n) return null;
				
				if (n === 1) {
					const el0 = list[0];
					// auto single: precise
					const inferred = { allowMulti: false, sigMode: "instance" };
					const sigOpts = mergeSigOpts(opts, inferred);
					console.log("computeSigKeyForSelector> auto n=1 el:", el0);
					const sigKey = sigOf(el0, sigOpts);
					console.log("computeSigKeyForSelector> auto n=1 sigKey:", sigKey);
					return sigKey;
				} else {
					// auto multi: class/group
					const inferred = { allowMulti: true, sigMode: "class" };
					const sigOpts = mergeSigOpts(opts, inferred);
					console.log("computeSigKeyForSelector> auto n=", n, " -> class sig");
					const sigKeys = list.map(el => sigOf(el, sigOpts)).filter(Boolean);
					return sigKeys;
				}
			} catch (e) {
				return null;
			}
		}
	};
	console.log("AI2Apps WebRPALib engaged.");
};

//---------------------------------------------------------------------------
async function ensureCodeLib(page,codeTag){
	codeTag=codeTag||"$codeLib";
	if(await page.evaluate(`!!globalThis["${codeTag}"]`)){
		return codeTag;
	}
	await page.callFunction(codeLib,[codeTag],{sandbox:"AASandBox"});
	return codeTag;
}

export {ensureCodeLib};