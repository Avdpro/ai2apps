
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
			let list,i,n,node,wraped,visibleOnly,contextNode,wNode;
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
				if(selector[0]==="("){
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