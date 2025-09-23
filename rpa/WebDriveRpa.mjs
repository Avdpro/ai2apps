import WebDrive from "./WebDrive.mjs";
import {AIQuery} from "./aiquery.mjs";
import clipboardy from "clipboardy";
import pathLib from 'path'
import { promises as fsp, promises as fs } from 'fs'
import startPPT from './pptstart.mjs';
import {ensureCodeLib} from "./CodeLib.mjs";
import { URL } from 'url'
import html2md from 'html-to-md'

const codeURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const codeDirURL=pathLib.dirname(codeURL);
const codeDirPath=codeDirURL.startsWith("file://")?pathLib.fileURLToPath(codeDirURL):codeDirURL;

const WebRpa_DataDirRoot=process.env.WEBRPA_DATADIR||process.env.AAF_DATADIR;

const aliasPattern = /^[a-zA-Z_][a-zA-Z0-9_]*$/;
const WebRpa_Version='0.0.1';

const browserAliasMap=new Map();
const browserMap=new Map();
let nextBrowserId=0;
let nextTempBrowserId=0;
let nextBrowserPort=9222;

async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}

async function deleteFile(filePath) {
	try {
		await fsp.unlink(filePath);
	} catch (err) {
	}
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

let WebDriveRpaStarted=false;
/**
 * 清理指定目录中以指定前缀开头的所有子目录
 * @param {string} prefix - 前缀（如 'firefox-profile-'）
 * @param {string} [baseDir='/tmp'] - 扫描的根目录，默认 /tmp
 */
async function cleanTmpDirs(prefix, baseDir = '/tmp') {
	try {
		const entries = await fs.readdir(baseDir, { withFileTypes: true });
		
		const targets = entries.filter(entry =>
			entry.isDirectory() && entry.name.startsWith(prefix)
		);
		
		for (const dir of targets) {
			const fullPath = pathLib.join(baseDir, dir.name);
			try {
				await fs.rm(fullPath, { recursive: true, force: true });
				console.log(`✅ 已删除: ${fullPath}`);
			} catch (err) {
				console.warn(`⚠️ 删除失败: ${fullPath}`, err.message);
			}
		}
		
		console.log(`共尝试清理 ${targets.length} 个目录`);
	} catch (err) {
		console.error('读取目录失败：', err.message);
	}
}

async function openBrowser(session,alias,opts){
	let agentNode, browser, browserId,dirPath,sysId,res;
	
	agentNode=session.agentNode;
	if(alias){
		if((!aliasPattern.test(alias)) || alias.startsWith("TMP_")){
			throw Error("Browser alias is invalid.");
		}
		browserId=browserAliasMap.get(alias);
		if(browserId){
			browser=browserMap.get(browserId);
			if(!browser.connected){
				browserMap.delete(browserId);
				browser=null;
			}
			if(browser){
				return browser;
			}
		}
	}

	browserId = "" + (nextBrowserId++);
	browser = new WebDrive();
	browser.aaeBrowserId=browserId;
	browserMap.set(browserId, browser);
	
	if(alias){
		browserAliasMap.set(alias,browserId);
		browser.aaeeAlias=alias;
	}else{
		alias="TMP_"+(nextTempBrowserId++);
		browserAliasMap.set(alias,browserId);
		browser.aaeeAlias=alias;
	}
	
	browser.on("browser.exit",()=>{
		browserAliasMap.delete(alias);
		browserMap.delete(browserId);
	});
	browser.on("browser.willExit",()=>{
		browserAliasMap.delete(alias);
		browserMap.delete(browserId);
	});
	
	sysId=await session.callHub("WebDriveOpenBrowser",{alias:alias,options:opts});
	await browser.start(sysId,alias,agentNode);
	return browser;
}

//***************************************************************************
//WebRpa:
//***************************************************************************
let WebRpa,webRpa;
WebRpa=function(session){
	this.session=session;
	this.agentNode=session.agentNode;
	this.version=WebRpa_Version;
	this.aiQuery=null;
	
	//We only need set this once:
	if(!this.agentNode.WSMsg_WebDriveBrowserClosed){
		//-------------------------------------------------------------------
		this.agentNode.WSMsg_WebDriveBrowserClosed=async function(msgVO){
			let alias,browserId,browser;
			alias=msgVO.alias;
			browserId=browserAliasMap.get(alias);
			if(browserId) {
				browser = browserMap.get(browserId);
				if(browser){
					browser.emit("browser.exit");
				}
			}
		};
		//-------------------------------------------------------------------
		this.agentNode.WSMsg_WebDriveEvent=async function(msgVO){
			let alias,browserId,browser,event;
			alias=msgVO.alias;
			event=msgVO.event;
			browserId=browserAliasMap.get(alias);
			if(browserId && event) {
				browser = browserMap.get(browserId);
				if(browser){
					try {
						browser.handleEvent(event);
					}catch(_){
					}
				}
			}
		};
	}
}
webRpa=WebRpa.prototype={};
WebRpa.version=WebRpa_Version;

//------------------------------------------------------------------------
//TODO: Port this:
webRpa.setupAIQuery=async function(context,agentPath,agentJaxId){
	let aiQuery=this.aiQuery=new AIQuery(this,context,agentPath,agentJaxId);
	await aiQuery.setup();
};//TODO: Port this:

//---------------------------------------------------------------------------
//TODO: Port this:
webRpa.listBrowserAndPages=async function(){
	let browsers, browserId, browser,list,stub,pages,page,url,title;
	browsers=browserAliasMap.values();
	list=[];
	for(browserId of browsers){
		browser=browserMap.get(browserId);
		stub={browser:browser,id:browserId,alias:browser.aaeeAlias};
		pages=await browser.getBrowsingContextTree(0);
		stub.pages=[];
		for(page of pages){
			url=await page.url();
			title=await page.title();
			stub.pages.push({page:page,url:url,title:title});
		}
		list.push(stub);
	}
	return list;
};//TODO: Port this:

//---------------------------------------------------------------------------
webRpa.openBrowser=async function(alias,opts){
	let browser=await openBrowser(this.session,alias,opts);
	if(browser){
		browser.aaeRefcount=browser.aaeRefcount?browser.aaeRefcount+1:1;
	}
	return browser;
};

//---------------------------------------------------------------------------
webRpa.closeBrowser=async function(browser){
	await this.agentNode.callHub("WebDriveCloseBrowser",{alias:browser.alias});
}

//---------------------------------------------------------------------------
webRpa.getPageByTitle=async function(browser,title){
	let page,pages;
	pages=await browser.getPages();
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
webRpa.ensureCodeLib=webRpa.getCodeTag=async function(page){
	return await ensureCodeLib(page);
};

//***************************************************************************
//Access DOM-Tree:
//***************************************************************************
{
	//-----------------------------------------------------------------------
	WebRpa.getNodeAttribute=WebRpa.getNodeAttr=
	webRpa.getNodeAttribute = webRpa.getNodeAttr = async function (pageFrame, node, key) {
		let codeTag;
		codeTag = await ensureCodeLib(pageFrame);
		return await pageFrame.callFunction((codeTag, node, key) => {
			let codeLib = globalThis[codeTag];
			return codeLib.getNodeAttribute(node, key);
		}, [codeTag, node, key]);
	};
	
	//-----------------------------------------------------------------------
	WebRpa.setNodeAttribute=WebRpa.setNodeAttr=
	webRpa.setNodeAttribute=webRpa.setNodeAttr=async function(pageFrame,node,key,value){
		let codeTag;
		codeTag=await ensureCodeLib(pageFrame);
		return await pageFrame.callFunction((codeTag,node,key,value)=>{
			let codeLib=globalThis[codeTag];
			return codeLib.setNodeAttribute(node,key,value);
		},[codeTag,node,key,value]);
	};

	//-----------------------------------------------------------------------
	WebRpa.getNodeAttributes=WebRpa.getNodeAttrs=
	webRpa.getNodeAttributes=webRpa.getNodeAttrs=async function(pageFrame,node){
		let codeTag;
		codeTag=await ensureCodeLib(pageFrame);
		return await pageFrame.callFunction((codeTag,node)=>{
			let codeLib=globalThis[codeTag];
			return codeLib.getNodeAttributes(node);
		},[codeTag,node]);
	};

	//-----------------------------------------------------------------------
	WebRpa.getNodeParent=
	webRpa.getNodeParent=async function(pageFrame,node){
		let codeTag;
		codeTag=await ensureCodeLib(pageFrame);
		return await pageFrame.callFunction((codeTag,node)=>{
			let codeLib=globalThis[codeTag];
			return codeLib.getNodeParent(node);
		},[codeTag,node]);
	};

	//-----------------------------------------------------------------------
	WebRpa.getNodeChildren=
	webRpa.getNodeChildren=async function(pageFrame,node){
		let codeTag;
		codeTag=await ensureCodeLib(pageFrame);
		return await pageFrame.callFunction((codeTag,node)=>{
			let codeLib=globalThis[codeTag];
			return codeLib.getNodeChildren(node);
		},[codeTag,node]);
	};

	//-----------------------------------------------------------------------
	WebRpa.readNodeView=
	webRpa.readNodeView=async function(pageFrame,node,opts){
		let codeTag;
		codeTag=await ensureCodeLib(pageFrame);
		return await pageFrame.callFunction((codeTag,node,opts)=>{
			let codeLib=globalThis[codeTag];
			return codeLib.readNodeView(node,opts);
		},[codeTag,node,opts]);
	};
	
	//-----------------------------------------------------------------------
	WebRpa.readNodeText=
	webRpa.readNodeText=async function(pageFrame,node,opts){
		let codeTag;
		codeTag=await ensureCodeLib(pageFrame);
		return await pageFrame.callFunction((codeTag,node,opts)=>{
			let codeLib=globalThis[codeTag];
			return codeLib.readNodeText(node,opts);
		},[codeTag,node,opts]);
	};

	//-----------------------------------------------------------------------
	WebRpa.readNodeHTML=WebRpa.readInnerHTML=
	webRpa.readNodeHTML=webRpa.readInnerHTML=async function(pageFrame,node,opts){
		let codeTag;
		opts=opts||{mark:true,clean:true};
		codeTag=await ensureCodeLib(pageFrame);
		return await pageFrame.callFunction((codeTag,node,opts) => {
			let codeLib = globalThis[codeTag];
			return codeLib.snapNodeHTML(node, opts);
		}, [codeTag,node,opts]);
	};
	
	//-----------------------------------------------------------------------
	WebRpa.getInnerHTML=
	webRpa.getInnerHTML=async function(pageFrame,node){
			let codeTag;
			codeTag=await ensureCodeLib(pageFrame);
			return await pageFrame.callFunction((codeTag,node) => {
				let codeLib = globalThis[codeTag];
				return codeLib.getInnerHTML(node);
			}, [codeTag,node]);
		};

	//-----------------------------------------------------------------------
	WebRpa.readArticle=
	webRpa.readArticle=async function(pageFrame,baseNode,options){
		let html,md;
		if(baseNode) {
			html = await this.readInnerHTML(pageFrame, baseNode, options);
			md = html2md(html);
			return md;
		}
		return pageFrame.readArticle();
	};
}

//***************************************************************************
//Query/find content:
//***************************************************************************
{
	//-----------------------------------------------------------------------
	//TODO: Maybe use default $() to get node.
	WebRpa.queryNode=
	webRpa.queryNode=async function(pageFrame,node,selector,opts){
		let codeTag;
		codeTag=await ensureCodeLib(pageFrame);
		return await pageFrame.callFunction((codeTag,node,selector,opts)=>{
			let codeLib=globalThis[codeTag];
			return codeLib.queryNode(node,selector,opts);
		},[codeTag,node,selector,opts]);
	};

	//-----------------------------------------------------------------------
	//TODO: Maybe use default $$() to get node
	WebRpa.queryNodes=
	webRpa.queryNodes=async function(pageFrame,node,selector,opts){
		let codeTag;
		codeTag=await ensureCodeLib(pageFrame);
		return await pageFrame.callFunction((codeTag,node,selector,opts)=>{
			let codeLib=globalThis[codeTag];
			return codeLib.queryNodes(node,selector,opts);
		},[codeTag,node,selector,opts]);
	};

	//-----------------------------------------------------------------------
	//TODO: Maybe use default $() to get node.
	webRpa.waitQuery=async function(pageFrame,selector,opts){
		let codeTag,startTime,node,timeout;
		timeout=opts.timeout||0;
		codeTag=await ensureCodeLib(pageFrame);
		node=opts.aaeId||opts.AAEId||opts.root;
		startTime=Date.now();
		do{
			node=await pageFrame.callFunction((codeTag,node,selector,opts)=>{
				let codeLib=globalThis[codeTag];
				return codeLib.queryNode(node,selector,opts);
			},[codeTag,node,selector,opts]);
			if(node){
				return node;
			}
			await sleep(200);
			if(timeout>0 && Date.now()-startTime>timeout){
				return null;
			}
		}while(1);
	}
}

//***************************************************************************
//User actions:
//***************************************************************************
{
	//-----------------------------------------------------------------------
	async function moveMouseTo(page,x,y,smooth=false){
		await page.moveMouse(x,y,{smooth:smooth});
	}

	//-----------------------------------------------------------------------
	async function clickMouse(page){
		await page.mouseClick();
	}

	//-----------------------------------------------------------------------
	webRpa.userAction=async function(pageFrame,opts){
		let action,query,codeTag;
		action=opts.action;
		query=opts.query;
		switch(action){
			case "click": {
				let root,node,dx,dy,selector,offset;
				root=opts.root||null;
				node=opts.node||null;
				selector=opts.query||opts.selector;
				if(selector && !root) {
					await pageFrame.click(selector,opts);
				}else {
					if(!node) {
						if (root && selector) {
							codeTag = await ensureCodeLib(pageFrame);
							node = await pageFrame.callFunction((codeTag, root, selector, opts) => {
								let codeLib = globalThis[codeTag];
								return codeLib.queryNode(root, selector, opts);
							}, [codeTag, root, selector, {}]);
						}
					}
					if (node) {
						let rect = node.rect;
						if(!rect && node.handle) {
							rect=await this.callFunction((item)=>{
								const rect=item.getBoundingClientRect();
								if(!rect){
									return null;
								}
								return {
									x:rect.x, y:rect.y, width:rect.width, height: rect.height
								};
							},[node.handle]);
						}
						if(rect) {
							let tgtX, tgtY;
							if (opts.offset) {
								tgtX = Math.round(rect.x + opts.offset.x);
								tgtY = Math.round(rect.y + opts.offset.y);
							} else {
								tgtX = Math.round(rect.x + rect.width * 0.5);
								tgtY = Math.round(rect.y + rect.height * 0.5);
							}
							await moveMouseTo(pageFrame, tgtX, tgtY, opts.smooth);
							await clickMouse(pageFrame);
						}
					}
				}
				break;
			}
			case "type":{
				let node,content;
				content=opts.content;
				await pageFrame.type(opts.selector||opts.query||null, content);
				break;
			}
			case "paste": {
				let node,content;
				content=opts.content;
				await clipboardy.write('Hello async clipboard!');
				if(!content){
					content=await clipboardy.read();
				}
				await pageFrame.type(opts.selector||opts.query||null, content);
				break;
			}
		}
	};
	
}
export default WebRpa;
export {WebRpa,ensureCodeLib,sleep};