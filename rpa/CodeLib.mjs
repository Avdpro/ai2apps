
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
		"computeSigKey":function(el) {
			try {
				if (!el || el.nodeType !== 1) return null;
				
				// ---------- helpers ----------
				const norm = (s, max = 80) =>
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
				
				const getTestId = (node) => {
					const keys = ["data-testid", "data-test", "data-qa", "data-cy"];
					for (const k of keys) {
						const v = norm(getAttr(node, k));
						if (v) return v;
					}
					return "";
				};
				
				const getRole = (node) => norm(getAttr(node, "role")) || "";
				const getType = (node) => norm(getAttr(node, "type")) || "";
				const getName = (node) => norm(getAttr(node, "name")) || "";
				const getId = (node) => norm(node.id) || "";
				const getAriaLabel = (node) => norm(getAttr(node, "aria-label")) || "";
				const getPlaceholder = (node) => norm(getAttr(node, "placeholder")) || "";
				
				const getLabelledByText = (node) => {
					const ids = norm(getAttr(node, "aria-labelledby"), 120);
					if (!ids) return "";
					const parts = ids.split(/\s+/).filter(Boolean);
					const texts = [];
					for (const id of parts) {
						const target = document.getElementById(id);
						if (!target) continue;
						const t = norm(target.innerText || target.textContent || "", 80);
						if (t) texts.push(t);
						if (texts.join(" ").length > 120) break;
					}
					return norm(texts.join(" "), 120);
				};
				
				const isEditable = (node) => {
					const tag = (node.tagName || "").toLowerCase();
					if (tag === "input" || tag === "textarea") return true;
					const ce = getAttr(node, "contenteditable");
					return ce === "" || String(ce).toLowerCase() === "true";
				};
				
				const getVisibleText = (node) => {
					// visible-ish text
					return norm(node.innerText || node.textContent || "", 80);
				};
				
				const kindOf = (node) => {
					const tag = (node.tagName || "").toLowerCase();
					const role = getRole(node);
					const type = getType(node);
					const editable = isEditable(node);
					
					if (editable) {
						if (tag === "textarea") return "textbox|textarea";
						if (tag === "input") return "textbox|input:" + (type || "text");
						return "textbox|editable";
					}
					
					const isButtonish = tag === "button" || role === "button" || type === "submit";
					if (isButtonish) {
						return "button|" + (type ? type : (role ? "role=" + role : "plain"));
					}
					
					if (tag === "a") return "link|" + (role ? "role=" + role : "a");
					
					return tag || "element";
				};
				
				const findContainer = (node) => {
					const selectors = [
						"[role='dialog']",
						"dialog",
						"form",
						"main",
						"section",
						"nav",
						"header",
						"footer",
						"aside",
					];
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
				
				const chainPart = (node, container) => {
					const items = [];
					let cur = node;
					let guard = 0;
					
					while (cur && cur !== container && guard++ < 50) {
						cur = cur.parentElement;
						if (!cur || cur === container) break;
						
						const id = getId(cur);
						const testid = getTestId(cur);
						const role = getRole(cur);
						
						// only keep ancestors with some stable identity
						if (!id && !testid && !role) continue;
						
						const tag = (cur.tagName || "").toLowerCase();
						let frag = tag;
						if (testid) frag += "[testid=" + testid + "]";
						if (id) frag += "#" + id;
						if (role) frag += "[role=" + role + "]";
						items.push(frag);
						
						if (items.length >= 3) break;
					}
					
					return items.length ? ("chain=" + items.reverse().join(">")) : "chain=none";
				};
				
				// ---------- build parts ----------
				const kind = kindOf(el);
				
				// ids: include multiple strong IDs (if present)
				const ids = [];
				const id = getId(el);
				const testid = getTestId(el);
				const name = getName(el);
				if (id) ids.push("id=" + id);
				if (testid) ids.push("testid=" + testid);
				if (name) ids.push("name=" + name);
				const idsPart = "ids:" + (ids.length ? ids.join(";") : "none");
				
				// a11y/text: include multiple semantic labels (if present)
				const a11y = [];
				const alby = getLabelledByText(el);
				const aria = getAriaLabel(el);
				const ph = getPlaceholder(el);
				const txt = getVisibleText(el);
				
				if (alby) a11y.push("alby=" + alby);
				if (aria) a11y.push("aria=" + aria);
				if (ph) a11y.push("ph=" + ph);
				
				// Only include text for button-ish / link-ish (text on huge divs is noisy)
				if (kind.startsWith("button|") || kind.startsWith("link|")) {
					if (txt) a11y.push("txt=" + txt);
				}
				
				const a11yPart = "a11y:" + (a11y.length ? a11y.join(";") : "none");
				
				// anchor
				const c = findContainer(el);
				const anchorPart = "anchor:" + containerPart(c) + "|" + chainPart(el, c);
				
				// cap total length (safety)
				let key = "v2|" + kind + "|" + idsPart + "|" + a11yPart + "|" + anchorPart;
				if (key.length > 600) key = key.slice(0, 600);
				
				return key;
			} catch (e) {
				return null;
			}
		},
		"computeSigKeyForSelector":function(selector,opts){
			console.log("computeSigKeyForSelector> selector:"+selector);
			opts = (opts && typeof opts === "object") ? opts : {};
			const mode = (opts.mode === "all") ? "all" : "first";
			
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
			if (!sel)
				return null;
			const sigOf = (el) => {
				try {
					return el ? this.computeSigKey(el) : null;
				} catch {
					return null;
				}
			};
			
			try {
				if (scheme === "css") {
					if (mode === "all") {
						const list = Array.from(document.querySelectorAll(sel));
						const sigKeys = list.map(sigOf).filter(Boolean);
						return sigKeys;
					} else {
						const el = document.querySelector(sel);
						console.log("computeSigKeyForSelector> el:",el);
						if(!el) {
							return null;
						}
						const sigKey = sigOf(el);
						console.log("computeSigKeyForSelector> sigKey:",sigKey);
						return sigKey;
					}
				}
				
				// xpath
				const doc = document;
				const ctxNode = doc; // you can change to doc.documentElement if you prefer
				const type = (mode === "all")
					? XPathResult.ORDERED_NODE_SNAPSHOT_TYPE
					: XPathResult.FIRST_ORDERED_NODE_TYPE;
				
				const res = doc.evaluate(sel, ctxNode, null, type, null);
				
				if (mode === "all") {
					const sigKeys = [];
					const n = res.snapshotLength || 0;
					for (let i = 0; i < n; i++) {
						const node = res.snapshotItem(i);
						if (node && node.nodeType === 1) {
							const sk = sigOf(node);
							if (sk) sigKeys.push(sk);
						}
					}
					return sigKeys;
				} else {
					const node = res.singleNodeValue;
					const el = (node && node.nodeType === 1) ? node : null;
					if(!el){
						return null;
					}
					const sigKey = sigOf(el);
					return sigKey;
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