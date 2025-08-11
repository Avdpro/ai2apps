import puppeteer from 'puppeteer';
import startPPT from "./pptstart.mjs";
import clipboardy from "clipboardy";
import pathLib from 'path';
import { promises as fs, promises as fsp } from 'fs'
import { Buffer } from 'buffer'
import setupReadability from '../aaee/AAEReadability.mjs';
import {AIQuery} from "./aiquery.mjs";
import html2md from 'html-to-md';

const WebRpa_Version="0.0.1";
const WebRpa_Executable=process.env.WEBRPA_EXECUATABLE||process.env.AAF_EXECUATABLE;
const WebRpa_Entry=process.env.WEBRPA_ENTRY||process.env.AAF_ENTRY;
const WebRpa_DataDirRoot=process.env.WEBRPA_DATADIR||process.env.AAF_DATADIR;
const killBrowserTime=50*60*1000;

const browserAliasMap=new Map();
const browserMap=new Map();
const contextMap=new Map();
const handleMap=new Map();
let nextBrowserId=0;
let nextPageId=0;
let nextContextId=0;
let nextHandleId=0;
let ensureCodeLib=null;

let nextTempBrowserId=1;

const aliasPattern = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}

function getBrowserId(browser){
	let keys,key;
	keys=Array.from(browserMap.keys());
	for(key of keys){
		if(browserMap.get(key)===browser){
			return key;
		}
	}
	return null;
}

function getHandleId(handle){
	let keys,key;
	keys=Array.from(handleMap.keys());
	for(key of keys){
		if(handleMap.get(key)===handle){
			return key;
		}
	}
	return null;
}

function getFrameId(frameMap,frame,create=true){
	let keys,key;
	keys=Array.from(frameMap.keys());
	for(key of keys){
		if(frameMap.get(key)===frame){
			return key;
		}
	}
	if(create){
		key=""+(nextPageId++);
		frameMap.set(key,frame);
		return key;
	}
	return null;
}

function randomTag(digit=6,time=true){
	const characters = 'abcdefghijklmnopqrstuvwxyz0123456789';
	let result = '';
	const charactersLength = characters.length;
	if(time){
		time=""+Date.now();
		time=time.substring(time.length-6);
	}
	for (let i = 0; i < digit; i++) {
		result += characters.charAt(Math.floor(Math.random() * charactersLength));
	}
	return "$"+result+time;
}

async function deleteFile(filePath) {
	try {
		await fsp.unlink(filePath);
	} catch (err) {
	}
}

//-------------------------------------------------------------------
async function closeBrowser(browser){
	let list,page;
	browser.killTimer=null;
	list=await browser.pages();
	await browser.close();
}

async function openBrowser(alias,opts,keepAlive){
	let browserId, browser, dirPath;
	if(alias){
		if((!aliasPattern.test(alias)) || alias.startsWith("TMP_")){
			throw Error("Browser alias is invalid.");
		}
		browserId=browserAliasMap.get(alias);
		if(browserId){
			browser=browserMap.get(browserId);
			if(browser){
				return browser;
			}
		}
	}
	dirPath=null;
	//Check auto data dir
	if(alias && WebRpa_DataDirRoot){
		if(opts.autoDataDir){
			dirPath = WebRpa_DataDirRoot;
			if (dirPath[0] !== "/") {
				//make it full path
				dirPath = pathLib.join(app.get("AppHomePath"), dirPath);
			}
			dirPath = pathLib.join(dirPath, alias);
			try{
				await fs.access(dirPath);
				opts.userDataDir = dirPath;
			}catch(err){
				try {
					await fs.mkdir(dirPath, { recursive: true });
					opts.userDataDir = dirPath;
				}catch(err){
					//Do not use data-dir.
				}
			}
		}else{
			//Check dir for alias
			let dirPath = WebRpa_DataDirRoot;
			if (dirPath[0] !== "/") {
				//make it full path
				dirPath = pathLib.join(app.get("AppHomePath"), dirPath);
			}
			dirPath = pathLib.join(dirPath, alias);
			try{
				await fs.access(dirPath);
				opts.userDataDir = dirPath;
			}catch(err){
				//Do not use data-dir.
			}
		}
	}
	
	//check if use executable path:
	if(!opts.executablePath){
		let exePath;
		exePath=WebRpa_Executable;
		if(exePath){
			if (exePath[0] !== "/" && (exePath[1]===":" && exePath[2]===":")) {
				exePath = pathLib.join(app.get("AppHomePath"), exePath);
			}
			opts.executablePath=exePath;
		}
	}
	browserId = "" + (nextBrowserId++);
	browser = await startPPT(opts);
	browser.aaeBrowserId=browserId;
	browserMap.set(browserId, browser);
	if(opts.userDataDir){
		let zonePath=pathLib.join(opts.userDataDir,"AAEZone");
		try{
			await fs.access(zonePath);
			browser.aaeZonePath=zonePath;
		}catch(err){
			try {
				await fs.mkdir(zonePath, { recursive: true });
				browser.aaeZonePath=zonePath;
			}catch(err){
				//Do not use data-dir.
			}
		}
	}
	
	if(alias){
		browserAliasMap.set(alias,browserId);
		browser.aaeeAlias=alias;
	}else{
		alias="TMP_"+(nextTempBrowserId++);
		browserAliasMap.set(alias,browserId);
		browser.aaeeAlias=alias;
	}
	if(!keepAlive) {
		browser.killTimer = setTimeout(async () => {
			closeBrowser(browser);
		}, killBrowserTime);
	}
	
	browser.aaePc=browser.process();
	
	browser.on("disconnected", () => {
		browserMap.delete(browserId);
		if(alias) {
			browserAliasMap.delete(alias);
		}
		//Do something about the process:
		try{
			browser.aaePc.kill("SIGKILL");
		}catch(err){
		}
	});
	return browser;
}

ensureCodeLib=async function (page){
	let codeTag;
	codeTag=page.aaeeCodeTag;
	if(codeTag){
		let hasTag;
		//ensure codeTag is ok:
		hasTag=await page.evaluate((codeTag)=>{
			return !!window[codeTag];
		},codeTag);
		if(hasTag) {
			return codeTag;
		}
	}
	codeTag=randomTag(5,true);
	page.aaeeCodeTag=codeTag;
	await page.evaluate((codeTag)=>{
		const stdExcludes=new Set(["SCRIPPT","STYLE"]);
		let nextAAEId=0;
		const allowedAttributes=new Set([
			"aaeid","class","contenteditable","class","hidden","id","style","title",
			"aria-label","role",
			"name","value","placeholder","required","disabled","readonly","type",
			"href","alt","src"
		]);
		window[codeTag]={
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
			
			"readMarkedHTML":function(aaeId,clean=true){
				let node,html;
				if(aaeId){
					node=document.querySelector(`[aaeid="${aaeId}"]`);
				}else{
					node=document.body;
				}
				this.markNodeTree(node);
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
				try{
					throw "Break";
				}catch(err){
				}
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
							wraped.push(wNode);
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
	},codeTag);
	await setupReadability(page,codeTag);
	return codeTag;
}

//***************************************************************************
//WebRpa:
//***************************************************************************
let WebRpa,webRpa;
WebRpa=function(session){
	this.session=session;
	this.version=WebRpa_Version;
	this.aiQuery=null;
}
webRpa=WebRpa.prototype={};
WebRpa.version=WebRpa_Version;

//------------------------------------------------------------------------
webRpa.setupAIQuery=async function(context,agentPath,agentJaxId){
	let aiQuery=this.aiQuery=new AIQuery(this,context,agentPath,agentJaxId);
	await aiQuery.setup();
};

//---------------------------------------------------------------------------
webRpa.listBrowserAndPages=async function(){
	let browsers, browserId, browser, alias,list,stub,pages,page,pageId,url,title;
	browsers=browserAliasMap.values();
	list=[];
	for(browserId of browsers){
		browser=browserMap.get(browserId);
		alias=browser.aaeeAlias;
		stub={browser:browser,id:browserId,alias:alias};
		pages=await browser.pages();
		stub.pages=[];
		for(page of pages){
			url=await page.url();
			title=await page.title();
			stub.pages.push({page:page,url:url,title:title});
		}
		list.push(stub);
	}
	return list;
};

//---------------------------------------------------------------------------
webRpa.openBrowser=async function(alias,opts){
	let browser=await openBrowser(alias,opts);
	if(browser){
		browser.aaeRefcount=browser.aaeRefcount?browser.aaeRefcount+1:1;
	}
	return browser;
};

//---------------------------------------------------------------------------
webRpa.closeBrowser=async function(browser){
	let browserId;
	browserId=browser.aaeBrowserId;
	if(browser && browser.aaeRefcount>0){
		browser.aaeRefcount-=1;
		if(!browser.aaeRefcount){
			await browser.close();
			browserMap.delete(browserId);
		}
	}else {
		await browser.close();
		browserMap.delete(browserId);
	}
};

//---------------------------------------------------------------------------
webRpa.getPageByTitle=async function(browser,title){
	let page;
	if(!browser){
		let browsers=browserMap.values();
		for(browser of browsers){
			let pages=await browser.pages();
			for(page of pages){
				if((await page.title())===title){
					return page;
				}
			}
		}
		return null;
	}
	let pages=await browser.pages();
	for(page of pages){
		if((await page.title())===title){
			return page;
		}
	}
	return null;
};

//---------------------------------------------------------------------------
webRpa.openPage=async function(browser){
	let page;
	page = await browser.newPage();
	page.on('dialog',async (dialog)=>{
		page.aaeDialog=dialog;
	});
	page.on('load',async ()=>{
		page.aaeeCodeTag=null;
	});
	return page;
};

//---------------------------------------------------------------------------
webRpa.closePage=async function(page){
	await page.close();
};

//---------------------------------------------------------------------------
webRpa.saveFile=async function(browser,fileName,data){
	let zonePath;
	zonePath=browser.aaeZonePath;
	if(!zonePath){
		return false;
	}
	await fsp.writeFile(zonePath+"/"+fileName, data);
	return true;
};

//---------------------------------------------------------------------------
webRpa.deleteFile=async function(browser,fileName){
	let zonePath;
	zonePath=browser.aaeZonePath;
	if(!zonePath){
		return false;
	}
	await deleteFile(zonePath+"/"+fileName);
	return true;
};

//---------------------------------------------------------------------------
webRpa.ensureCodeLib=webRpa.getCodeTag=async function(pageFrame){
	return await ensureCodeLib(pageFrame);
};

//---------------------------------------------------------------------------
webRpa.getNodeAttribute=webRpa.getNodeAttr=async function(pageFrame,aaeId,key){
	let codeTag;
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag)=>{
		let codeLib=window[codeTag];
		return codeLib.getNodeAttribute(aaeId,key);
	},codeTag);
};

//---------------------------------------------------------------------------
webRpa.setNodeAttribute=webRpa.setNodeAttr=async function(pageFrame,aaeId,key,value){
	let codeTag;
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag)=>{
		let codeLib=window[codeTag];
		return codeLib.setNodeAttribute(aaeId,key,value);
	},codeTag);
};

//---------------------------------------------------------------------------
webRpa.getNodeAttributes=webRpa.getNodeAttrs=async function(pageFrame,aaeId){
	let codeTag;
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag)=>{
		let codeLib=window[codeTag];
		return codeLib.getNodeAttributes(aaeId);
	},codeTag);
};

//---------------------------------------------------------------------------
webRpa.getNodeParent=async function(pageFrame,aaeId){
	let codeTag;
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag)=>{
		let codeLib=window[codeTag];
		return codeLib.getNodeParent(aaeId);
	},codeTag);
};

//---------------------------------------------------------------------------
webRpa.getNodeChildren=async function(pageFrame,aaeId){
	let codeTag;
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag)=>{
		let codeLib=window[codeTag];
		return codeLib.getNodeChildren(aaeId);
	},codeTag);
};

//---------------------------------------------------------------------------
webRpa.readNodeView=async function(pageFrame,aaeId,opts){
	let codeTag;
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag)=>{
		let codeLib=window[codeTag];
		return codeLib.readNodeView(aaeId,opts);
	},codeTag);
};

//---------------------------------------------------------------------------
webRpa.readNodeText=async function(pageFrame,aaeId,opts){
	let codeTag;
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag)=>{
		let codeLib=window[codeTag];
		return codeLib.readNodeText(aaeId,opts);
	},codeTag);
};

//---------------------------------------------------------------------------
webRpa.readNodeHTML=async function(pageFrame,aaeId,opts){
	let codeTag;
	opts=opts||{mark:true};
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag) => {
		let codeLib = window[codeTag];
		return codeLib.readMarkedHTML(aaeId, true);
	}, codeTag,aaeId,opts);
};

//---------------------------------------------------------------------------
webRpa.queryNode=async function(pageFrame,aaeId,selector,opts){
	let codeTag;
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag,aaeId,selector,opts)=>{
		let codeLib=window[codeTag];
		return codeLib.queryNode(aaeId,selector,opts);
	},codeTag,aaeId,selector,opts);
};

//---------------------------------------------------------------------------
webRpa.queryNodes=async function(pageFrame,aaeId,selector,opts){
	let codeTag;
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag,aaeId,selector,opts)=>{
		let codeLib=window[codeTag];
		return codeLib.queryNodes(aaeId,selector,opts);
	},codeTag,aaeId,selector,opts);
};

//---------------------------------------------------------------------------
webRpa.waitQuery=async function(pageFrame,selector,opts){
	let codeTag,startTime,node,timeout,aaeId;
	timeout=opts.timeout||0;
	codeTag=await ensureCodeLib(pageFrame);
	startTime=Date.now();
	aaeId=opts.aaeId||opts.AAEId||opts.baseNode;
	do{
		node=await pageFrame.evaluate((codeTag,aaeId,selector,opts)=>{
			let codeLib=window[codeTag];
			return codeLib.queryNode(aaeId,selector,opts);
		},codeTag,aaeId,selector,opts);
		if(node){
			return node;
		}
		await sleep(200);
		if(timeout>0 && Date.now()-startTime>timeout){
			throw Error("Timeout");
			//return null;
		}
	}while(1);
}

async function moveMouseTo(page,x,y,smooth=false){
	if(smooth){
		//TODO: Code this:
		await page.mouse.move(x,y);
	}else{
		await page.mouse.move(x,y);
	}
}

//---------------------------------------------------------------------------
async function clickMouse(page){
	await page.mouse.down();
	await page.mouse.up();
}

//---------------------------------------------------------------------------
webRpa.userAction=async function(pageFrame,opts){
	let action,query,codeTag;
	action=opts.action;
	query=opts.query;
	switch(action){
		case "click": {
			let node,dx,dy;
			dx=opts.dx||0;
			dy=opts.dy||0;
			codeTag=await ensureCodeLib(pageFrame);
			node=await pageFrame.evaluate((codeTag,aaeId,selector,opts)=>{
				let codeLib=window[codeTag];
				return codeLib.queryNode(aaeId,selector,opts);
			},codeTag,null,query, {});
			if(node && node.rect){
				let rect=node.rect;
				await moveMouseTo(pageFrame,rect.x+rect.width*0.5+dx,rect.y+rect.height*0.5+dx,opts.smooth);
				await clickMouse(pageFrame);
			}
			break;
		}
		case "type":
		case "paste": {
			let node,content;
			content=opts.content;
			if(!content){
				content=await clipboardy.read();
			}
			codeTag=await ensureCodeLib(pageFrame);
			node=await page.evaluate((codeTag,aaeId,selector,opts)=>{
				let codeLib=window[codeTag];
				return codeLib.queryNode(aaeId,selector,opts);
			},codeTag,null,query, {});
			query=`[aaeid="${node.AAEId}"]`;
			await page.type(query, content);
			break;
		}
	}
};

//---------------------------------------------------------------------------
webRpa.acceptDialog=async function(pageFrame,opts){
	let browser;
	browser=pageFrame.browser();
	if(pageFrame.aaeDialog){
		let value=opts.value;
		await pageFrame.aaeDialog.accept(value);
		pageFrame.aaeDialog=null;
		return true;
	}
	if(pageFrame.aaeFileDialog){
		//Mapping files' path:
		let zonePath,files;
		zonePath=browser.aaeZonePath;
		if(!zonePath){
			return false;
		}
		files=opts.files;
		if(files) {
			files = files.map((item) => {
				if (item.indexOf("/") >= 0) {
					throw Error("AcceptFileChooser: file path error.");
				}
				return zonePath + "/" + item;
			});
			await pageFrame.aaeFileDialog.accept(files);
			pageFrame.aaeFileDialog = null;
			if (opts.deleteFile) {
				for (let path of files) {
					await deleteFile(path);
				}
			}
			return true;
		}
	}
	return false;
};

//---------------------------------------------------------------------------
webRpa.dismissDialog=async function(pageFrame){
	if(pageFrame.aaeDialog){
		await pageFrame.aaeDialog.dismiss();
		pageFrame.aaeDialog=null;
		return true;
	}
	if(pageFrame.aaeFileDialog){
		await pageFrame.aaeFileDialog.cancel();
		pageFrame.aaeFileDialog=null;
		return true;
	}
	return false;
};

//---------------------------------------------------------------------------
webRpa.dialogMessage=async function(pageFrame) {
	if(pageFrame.aaeDialog){
		return await pageFrame.aaeDialog.message();
	}
	return null;
};

//---------------------------------------------------------------------------
webRpa.dialogDefaultValue=async function(pageFrame) {
	if(pageFrame.aaeDialog){
		return await pageFrame.aaeDialog.defaultValue();
	}
	return null;
};

//---------------------------------------------------------------------------
webRpa.confirmQuery=async function(pageFrame,query,queryHint,segId){
	let aiQuery;
	aiQuery=this.aiQuery;
	if(!aiQuery){
		return query;
	}
	return await aiQuery.getQuery(pageFrame,query,queryHint,segId);
};

//---------------------------------------------------------------------------
webRpa.readInnerHTML=async function(pageFrame,baseNode,options){
	let codeTag,text;
	codeTag=await ensureCodeLib(pageFrame);
	baseNode=baseNode?(baseNode.AAEId||baseNode):null;
	options=options||{};
	text = await pageFrame.evaluate((codeTag, aaeId, opts) => {
		let codeLib = window[codeTag];
		return codeLib.snapNodeHTML(aaeId, opts);
	}, codeTag, baseNode, options);
	return text;
};

//---------------------------------------------------------------------------
webRpa._readArticle=async function(pageFrame){
	let codeTag;
	codeTag=await ensureCodeLib(pageFrame);
	return await pageFrame.evaluate((codeTag)=>{
		let codeLib=window[codeTag];
		return codeLib.readPageArticle();
	},codeTag);
};

//---------------------------------------------------------------------------
webRpa.readArticle=async function(pageFrame,baseNode,options){
	let html,md;
	html=await this.readInnerHTML(pageFrame,baseNode,options);
	md=html2md(html);
	return md;
};

//---------------------------------------------------------------------------
webRpa.startTrace=async function(){
	//TODO: Code this:
	return null;
};
export {WebRpa,ensureCodeLib,sleep};
