import puppeteer from 'puppeteer';
import startPPT from "./pptstart.mjs";
import setupReadability from './AAEReadability.mjs';
import clipboardy from "clipboardy";
import pathLib from 'path';
import { promises as fs } from 'fs';
import { Buffer } from 'buffer'
import fsp from 'fs/promises'


const AAEE_VERSION="0.0.1";
const AAFarm_Executable=process.env.AAF_EXECUATABLE;
const AAFarm_Entry=process.env.AAF_ENTRY;
const AAFarm_DataDirRoot=process.env.AAF_DATADIR_PATH;
const killBrowserTime=5*60*1000;

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

function getPageId(pageMap,page,create=true){
	let keys,key;
	keys=Array.from(pageMap.keys());
	for(key of keys){
		if(pageMap.get(key)===page){
			return key;
		}
	}
	if(create){
		key=""+(nextPageId++);
		pageMap.set(key,page);
		return key;
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
	let list,page,pageId;
	browser.killTimer=null;
	list=await browser.pages();
	//Clear pages under this browser:
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
	if(alias && AAFarm_DataDirRoot){
		if(opts.autoDataDir){
			dirPath = AAFarm_DataDirRoot;
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
			let dirPath = AAFarm_DataDirRoot;
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
		exePath=AAFarm_Executable;
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
	browser.pageMap=new Map();
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

export default async function(app,router,apiMap) {
	//-------------------------------------------------------------------
	apiMap['aaeeGetVersion'] = async function (req, res, next) {
		let reqVO;
		reqVO = req.body.vo;
		res.json({ code: 200, version: AAEE_VERSION });
	};

	//***********************************************************************
	//Brawser API:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		//-------------------------------------------------------------------
		apiMap['aaeeGetBrowsers'] = async function (req, res, next) {
			let reqVO, opts, browsers, browserId, browser, alias,list,stub,pages,page,pageId,url,title;
			reqVO = req.body.vo;
			browsers=browserAliasMap.values();
			list=[];
			for(browserId of browsers){
				browser=browserMap.get(browserId);
				//browserId=browser.aaeeId;
				alias=browser.aaeeAlias;
				stub={id:browserId,alias:alias};
				pages=await browser.pages();
				stub.pages=[];
				for(page of pages){
					pageId=getPageId(browser.pageMap,page,true);
					url=await page.url();
					title=await page.title();
					stub.pages.push({id:pageId,url:url,title:title});
				}
				list.push(stub);
			}
			res.json({ code: 200, browsers: list});
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeOpenBrowser'] = async function (req, res, next) {
			let reqVO, opts, browserId, browser, alias,dirPath;
			reqVO = req.body.vo;
			opts = reqVO.opts || reqVO.options || {};
			alias=reqVO.alias;
			browser=await openBrowser(alias,opts);
			res.json({ code: 200, browser: browser.aaeBrowserId, alias:alias});
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeGetPageByTitle'] = async function (req, res, next) {
			let reqVO, browserId, browser,title,page;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			title=reqVO.title;
			if(!browserId){
				let browsers=browserMap.values();
				for(browser of browsers){
					let pages=await browser.pages();
					for(page of pages){
						if((await page.title())===title){
							res.json({ code: 200,browser:browser.aaeBrowserId,alias:browser.aaeeAlias,page:getPageId(browser.pageMap,page)});
							return;
						}
					}
				}
				res.json({ code: 200,page:null});
				return;
			}
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			let pages=await browser.pages();
			for(page of pages){
				if((await page.title())===title){
					res.json({ code: 200,page:getPageId(browser.pageMap,page)});
					return;
				}
			}
			res.json({ code: 200,page:null});
		};

		//-------------------------------------------------------------------
		apiMap['aaeeOpenPage'] = async function (req, res, next) {
			let reqVO, browserId, browser, page, pageId, pageMap,time;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			pageMap=browser.pageMap;
			pageId = "" + (nextPageId++);
			page = await browser.newPage();
			pageMap.set(pageId, page);
			page.on('dialog',async (dialog)=>{
				page.aaeDialog=dialog;
			});
			page.on('load',async ()=>{
				page.aaeeCodeTag=null;
			});
			res.json({ code: 200, page: pageId });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeCloseBrowser'] = async function (req, res, next) {
			let reqVO, browserId, browser;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			await browser.close();
			browserMap.delete(browserId);
			res.json({ code: 200 });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeHeartBeat'] = async function (req, res, next) {
			let reqVO, browserId, browser;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			if(browser.killTimer){
				clearTimeout(browser.killTimer);
				browser.killTimer=setTimeout(async ()=>{
					closeBrowser(browser);
				},killBrowserTime);
			}
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeGetBrowserUserAgent'] = async function (req, res, next) {
			let reqVO, browserId, browser, ua;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			ua = await browser.userAgent();
			res.json({ code: 200, userAgent: ua });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeGetPages'] = async function (req, res, next) {
			let reqVO, browserId, browser, list;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			list = await browser.pages();
			list=list.map((item)=>{
				return getPageId(browser.pageMap,item,true);
			})
			res.json({ code: 200, pages: list });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeCreateContext'] = async function (req, res, next) {
			let reqVO, browserId, browser, context,contextId;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			context = await browser.createBrowserContext();
			contextId=""+(nextContextId++);
			contextMap.set(contextId,context);
			res.json({ code: 200, context: contextId });
		};

		//-------------------------------------------------------------------
		apiMap['aaeeCloseContext'] = async function (req, res, next) {
			let reqVO, context,contextId;
			reqVO = req.body.vo;
			contextId = reqVO.context;
			context = contextMap.get(contextId);
			if (!context) {
				res.json({ code: 400, info: "Context not found." });
				return;
			}
			await context.close;
			contextMap.delete(contextId);
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeSaveFile']=async function(req,res,next){
			let reqVO, browserId, browser, zonePath, fileData, fileName;
			let buf;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			fileData = reqVO.data;
			fileName = reqVO.fileName;
			
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			zonePath=browser.aaeZonePath;
			if(!zonePath){
				res.json({ code: 500, info: "Browser don't have AAEZone." });
				return;
			}
			buf = Buffer.from(fileData, "base64");
			await fsp.writeFile(zonePath+"/"+fileName, buf);
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeDeleteFile']=async function(req,res,next){
			let reqVO, browserId, browser, zonePath, fileName;
			let buf;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			fileName = reqVO.fileName;
			
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			zonePath=browser.aaeZonePath;
			if(!zonePath){
				res.json({ code: 500, info: "Browser don't have AAEZone." });
				return;
			}
			deleteFile(zonePath+"/"+fileName);
			res.json({ code: 200});
		};
	}
	
	//***********************************************************************
	//Page API:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		apiMap['aaeeOpenURL'] =apiMap['aaeeGoto'] = async function (req, res, next) {
			let reqVO, browserId, browser, pageId, page, url, pageMap;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			pageMap=browser.pageMap;
			pageId = reqVO.page;
			page = pageMap.get(pageId);
			if (!page) {
				res.json({ code: 400, info: "Page not found." });
				return;
			}
			url=reqVO.url;
			await page.goto(url,reqVO.options||{});
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeGoBack'] = async function (req, res, next) {
			let reqVO, browserId, browser, pageId, page, pageMap;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			pageMap=browser.pageMap;
			pageId = reqVO.page;
			page = pageMap.get(pageId);
			if (!page) {
				res.json({ code: 400, info: "Page not found." });
				return;
			}
			await page.goBack(reqVO.options||{});
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeGoForward'] = async function (req, res, next) {
			let reqVO, browserId, browser, pageId, page, pageMap;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			pageMap=browser.pageMap;
			pageId = reqVO.page;
			page = pageMap.get(pageId);
			if (!page) {
				res.json({ code: 400, info: "Page not found." });
				return;
			}
			await page.goForward(reqVO.options||{});
			res.json({ code: 200});
		};

		//-------------------------------------------------------------------
		apiMap['aaeeClosePage'] = async function (req, res, next) {
			let reqVO, pageId, page;
			reqVO = req.body.vo;
			let browserId = reqVO.browser;
			let browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			let pageMap=browser.pageMap;
			pageId = reqVO.page;
			page = pageMap.get(pageId);
			if (!page) {
				res.json({ code: 400, info: "Page not found." });
				return;
			}
			await page.close();
			pageMap.delete((pageId));
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeBringToFront'] = async function (req, res, next) {
			let reqVO, pageId, page;
			reqVO = req.body.vo;
			let browserId = reqVO.browser;
			let browser = browserMap.get(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			let pageMap=browser.pageMap;
			pageId = reqVO.page;
			page = pageMap.get(pageId);
			if (!page) {
				res.json({ code: 400, info: "Page not found." });
				return;
			}
			await page.bringToFront();
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		//Set/Get page properties: DONE
		//-------------------------------------------------------------------
		{
			//---------------------------------------------------------------
			apiMap['aaeeSetPageViewport'] = async function (req, res, next) {
				let reqVO, pageId, page, viewport;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				viewport=reqVO.viewport;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				await page.setViewport(viewport);
				res.json({ code: 200});
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeSetPageUserAgent'] = async function (req, res, next) {
				let reqVO, pageId, page, ua;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				ua=reqVO.userAgent;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				await page.setUserAgent(ua);
				res.json({ code: 200});
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeGetPageTitle'] = async function (req, res, next) {
				let reqVO, pageId, page, title;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				title = await page.title();
				res.json({ code: 200, title: title });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeGetPageURL'] = async function (req, res, next) {
				let reqVO, pageId, page, url;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				url = await page.url();
				res.json({ code: 200, url: url });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeGetPageViewport'] = async function (req, res, next) {
				let reqVO, pageId, page, viewport;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				viewport = await page.viewport();
				res.json({ code: 200, viewport: { ...viewport } });
			};

			//---------------------------------------------------------------
			apiMap['aaeeGetFrames'] = async function (req, res, next) {
				let reqVO, pageId,page,list,framesMap;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				framesMap=page.aaeeObjsMap;
				if(!framesMap){
					framesMap=page.aaeeObjsMap=new Map();
				}
				list = await page.frames();
				list=list.map((item)=>{
					frameId=getFrameId(framesMap,item,true);
					return frameId;
				})
				res.json({ code: 200, frames: list });
			};
		}
		
		//-------------------------------------------------------------------
		//Actions: Comman API call: Done
		//-------------------------------------------------------------------
		{
			//-------------------------------------------------------------------
			apiMap['aaeePageAPI'] = async function (req, res, next) {
				let reqVO, pageId,page, apiObj,api,i,n,name,result;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				api=reqVO.api;
				apiObj=page;
				if(!Array.isArray(api)){
					api=[api];
				}
				n=api.length;
				if(n>1) {
					for (i = 0; i < n - 1; i++) {
						name = api[i];
						apiObj = apiObj[name];
					}
				}
				api=api[api.length-1];
				result=await apiObj[api](...reqVO.args);
				res.json({ code: 200,result:result});
			};
		}
		
		//-------------------------------------------------------------------
		//Eval related:
		//-------------------------------------------------------------------
		{
			//---------------------------------------------------------------
			apiMap['aaeeAddScriptTag'] = async function (req, res, next) {
				let reqVO, pageId, page, content, path, url, type;
				reqVO = req.body.vo;
				pageId = reqVO.page;
				type = reqVO.type;
				content = reqVO.content;
				path = reqVO.path;
				url = reqVO.url;
				
				page = pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				await page.addScriptTag({ type, content, path, url });
				res.json({ code: 200 });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeAddStyleTag'] = async function (req, res, next) {
				let reqVO, pageId, page, content, path, url, type;
				reqVO = req.body.vo;
				pageId = reqVO.page;
				type = reqVO.type;
				content = reqVO.content;
				path = reqVO.path;
				url = reqVO.url;
				
				page = pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				await page.addStyleTag({ type, content, path, url });
				res.json({ code: 200 });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeGetCodeTag'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.aaeeObjsMap.get(frameId);
				}
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				codeTag=await ensureCodeLib(page);
				res.json({ code: 200, codeTag: codeTag });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeEvaluate'] = async function (req, res, next) {
				let reqVO, pageId, page,code,opts,args,result;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				code = reqVO.code;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				opts = reqVO.opts||{};
				args = reqVO.args||opts.args;
				if(opts.argNames){
					let func=new Function(...opts.argNames,code);
					result = await page.evaluate(func, ...args);
				}else {
					if (args) {
						result = await page.evaluate(code, ...args);
					} else {
						result = await page.evaluate(code);
					}
				}
				res.json({ code: 200,result:result});
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeEvaluateHandle'] = async function (req, res, next) {
				let reqVO, pageId, page,code,params,handle,handleId;
				reqVO = req.body.vo;
				pageId = reqVO.page;
				page = pageMap.get(pageId);
				code = reqVO.code;
				params = reqVO.parmams;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				if(params){
					handle=await page.evaluateHandle(code,...params);
				}else{
					handle=await page.evaluateHandle(code);
				}
				handleId=""+(nextHandleId++);
				handleMap.set(handleId,handle);
				
				res.json({ code: 200,handle:handle});
			};
		}
		
		//-------------------------------------------------------------------
		//Wait functions: DONE
		//-------------------------------------------------------------------
		{
			//---------------------------------------------------------------
			apiMap['aaeeWaitFor'] = async function (req, res, next) {
				let reqVO, pageId,page,action,options;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				options=reqVO.options|| {};
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				action=reqVO.action.toLowerCase();
				switch(action){
					case "navi":
					case "navigation":
						await page.waitForNavigation(options);
						break;
					case "prompt":
					case "deviceprompt":
						await page.waitForDevicePrompt(options);
						break;
					case "filechooser": {
						let dlg=await page.waitForFileChooser(options);
						page.aaeFileDialog=dlg;
						break;
					}
					case "networkidle":
						await page.waitForNetworkIdle(options);
						break;
					case "dialog":{
						let timeout=options.timeout||0;
						let startTime=Date.now();
						let done=false;
						do{
							if(page.aaeDialog){
								res.json({ code: 200});
								return;
							}
							await sleep(200);
							if(timeout>0) {
								if (Date.now() - startTime > timeout) {
									res.json({ code: 500, info: "Timeout." });
									return;
								}
							}
						}while(!done);
						return;
					}
					default:
						res.json({ code: 400, info:`Unknown wait action: ${action}`});
						return;
				}
				res.json({ code: 200});
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeWaitQuery'] = async function (req, res, next) {
				let reqVO, pageId,page,codeTag,options,selector,timeout,node,baseNode,startTime;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				let pageMap=browser.pageMap;
				pageId = reqVO.page;
				page = pageMap.get(pageId);
				selector=reqVO.selector;
				options=reqVO.options||{};
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				baseNode=reqVO.baseNode||null;
				timeout=options?(options.timeout||0):0;
				codeTag=await ensureCodeLib(page);
				startTime=Date.now();
				do{
					node=await page.evaluate((codeTag,aaeId,selector,opts)=>{
						let codeLib=window[codeTag];
						return codeLib.queryNode(aaeId,selector,opts);
					},codeTag,baseNode,selector,options);
					if(node){
						res.json({code:200,node:node});
						return;
					}
					await sleep(200);
					if(timeout>0 && Date.now()-startTime>timeout){
						if(node){
							res.json({code:500,info:"WaitQuery time out."});
							return;
						}
					}
				}while(1);
			};
			
			//TODO: waitForFunction
			//---------------------------------------------------------------
			apiMap['aaeeWaitFunction'] = async function (req, res, next) {
				let reqVO, pageId, page, action, options,code,func;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				options = reqVO.options || {};
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				code=reqVO.code;
				await page.waitForFunction(code,options);
				res.json({ code: 200});
			};
		}
		
		//-------------------------------------------------------------------
		//Read page functions: DONE
		//-------------------------------------------------------------------
		{
			//Inject helper functions into target page:
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
				},codeTag);
				await setupReadability(page,codeTag);
				return codeTag;
			}
			
			//-------------------------------------------------------------------
			apiMap['aaeeReadArticle'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,text;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				codeTag=await ensureCodeLib(page);
				text=await page.evaluate((codeTag)=>{
					let codeLib=window[codeTag];
					return codeLib.readPageArticle();
				},codeTag);
				res.json({ code: 200,text:text});
			};

			//-------------------------------------------------------------------
			apiMap['aaeeGetNodeAttribute'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,opts,aaeId,key,value;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId=reqVO.AAEId||reqVO.aaeId;
				key=reqVO.key;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				codeTag=await ensureCodeLib(page);
				value=await page.evaluate((codeTag,aaeId,key)=>{
					let codeLib=window[codeTag];
					return codeLib.getNodeAttribute(aaeId,key);
				},codeTag,aaeId,key);
				res.json({ code: 200,value:value});
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeSetNodeAttribute'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,opts,aaeId,key,value;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId=reqVO.AAEId||reqVO.aaeId;
				key=reqVO.key;
				value=reqVO.value;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				codeTag=await ensureCodeLib(page);
				await page.evaluate((codeTag,aaeId,key,value)=>{
					let codeLib=window[codeTag];
					return codeLib.setNodeAttribute(aaeId,key,value);
				},codeTag,aaeId,key,value);
				res.json({ code: 200});
			};

			//-------------------------------------------------------------------
			apiMap['aaeeGetNodeAttributes'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,aaeId,attrs;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId=reqVO.AAEId||reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				codeTag=await ensureCodeLib(page);
				attrs=await page.evaluate((codeTag,aaeId)=>{
					let codeLib=window[codeTag];
					return codeLib.getNodeAttributes(aaeId);
				},codeTag,aaeId);
				res.json({ code: 200,attributes:attrs});
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeGetNodeParent'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,aaeId,wraped;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId=reqVO.AAEId||reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				codeTag=await ensureCodeLib(page);
				wraped=await page.evaluate((codeTag,aaeId)=>{
					let codeLib=window[codeTag];
					return codeLib.getNodeParent(aaeId);
				},codeTag,aaeId);
				res.json({ code: 200,node:wraped});
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeGetNodeChildren'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,aaeId,children;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId=reqVO.AAEId||reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				codeTag=await ensureCodeLib(page);
				children=await page.evaluate((codeTag,aaeId)=>{
					let codeLib=window[codeTag];
					return codeLib.getNodeChildren(aaeId);
				},codeTag,aaeId);
				res.json({ code: 200,children:children});
			};

			//-------------------------------------------------------------------
			apiMap['aaeeReadNodeView'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,opts,aaeId,view;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				opts=reqVO.options||reqVO.opts;
				aaeId=reqVO.AAEId||reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				codeTag=await ensureCodeLib(page);
				view=await page.evaluate((codeTag,aaeId,opts)=>{
					let codeLib=window[codeTag];
					return codeLib.readNodeView(aaeId,opts);
				},codeTag,aaeId,opts);
				res.json({ code: 200,view:view});
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeReadNodeText'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,opts,aaeId,text;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				opts=reqVO.opts;
				aaeId=reqVO.AAEId||reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				codeTag=await ensureCodeLib(page);
				text=await page.evaluate((codeTag,aaeId,opts)=>{
					let codeLib=window[codeTag];
					return codeLib.readNodeText(aaeId,opts);
				},codeTag,aaeId,opts);
				res.json({ code: 200,text:text});
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeReadNodeHTML'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,aaeId,text,options;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId=reqVO.AAEId||reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				options=reqVO.options||reqVO.opts;
				codeTag=await ensureCodeLib(page);
				if(options && options.marked) {
					text = await page.evaluate((codeTag, aaeId, opts) => {
						let codeLib = window[codeTag];
						return codeLib.readMarkedHTML(aaeId, true);
					}, codeTag, aaeId, options);
				}else{
					text = await page.evaluate((codeTag, aaeId) => {
						let codeLib = window[codeTag];
						return codeLib.readNodeHTML(aaeId);
					}, codeTag, aaeId);
				}
				res.json({ code: 200,html:text});
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeCapturePage'] = async function (req, res, next) {
				let reqVO, pageId, page,opts,data,imgType;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				opts=reqVO.opts||reqVO.options;
				opts=opts?{...opts,encoding: 'base64'}:{encoding: 'base64',fullPage:true,type:'png'};
				opts.encoding='base64';
				data=await page.screenshot(opts);
				imgType=opts.type||'png';
				switch(imgType){
					case "png":
						data="data:image/png;base64,"+data;
						break;
					case "jpg":
						data="data:image/jpeg;base64,"+data;
						break;
					case "webp":
						data="data:image/webp;base64,"+data;
						break;
				}
				res.json({ code: 200,image:data});
			};

			//-------------------------------------------------------------------
			//Query page node(s):
			apiMap['aaeeQueryNode'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,opts,node,selector,aaeId;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId=reqVO.aaeId||reqVO.AAEId;
				opts=reqVO.options||reqVO.opts;
				selector=reqVO.selector;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				codeTag=await ensureCodeLib(page);
				node=await page.evaluate((codeTag,aaeId,selector,opts)=>{
					let codeLib=window[codeTag];
					return codeLib.queryNode(aaeId,selector,opts);
				},codeTag,aaeId,selector,opts);
				res.json({ code: 200, node:node});
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeQueryNodes'] = async function (req, res, next) {
				let reqVO, pageId, page,codeTag,opts,list,aaeId,selector;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				opts=reqVO.options||reqVO.opts;
				aaeId=reqVO.aaeId||reqVO.AAEId;
				selector=reqVO.selector;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				codeTag=await ensureCodeLib(page);
				list=await page.evaluate((codeTag,aaeId,selector,opts)=>{
					let codeLib=window[codeTag];
					return codeLib.queryNodes(aaeId,selector,opts);
				},codeTag,aaeId,selector,opts);
				res.json({ code: 200, list:list});
			};
		}
		
		//-------------------------------------------------------------------
		//User actions:
		//-------------------------------------------------------------------
		{
			//-------------------------------------------------------------------
			async function moveMouseTo(page,x,y,smooth=false){
				if(smooth){
					//TODO: Code this:
					await page.mouse.move(x,y);
				}else{
					await page.mouse.move(x,y);
				}
			}
			
			//-------------------------------------------------------------------
			async function clickMouse(page){
				await page.mouse.down();
				await page.mouse.up();
			}

			//-------------------------------------------------------------------
			apiMap['aaeeUserAction'] = async function (req, res, next) {
				let reqVO, pageId, page,opts;
				let codeTag,query,action;
				reqVO = req.body.vo;
				pageId = reqVO.page;
				opts=reqVO.opts;
				action=opts.action;
				query=opts.query;
				
				page = pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				switch(action){
					case "click": {
						let node,dx,dy;
						dx=opts.dx||0;
						dy=opts.dy||0;
						codeTag=await ensureCodeLib(page);
						node=await page.evaluate((codeTag,aaeId,selector,opts)=>{
							let codeLib=window[codeTag];
							return codeLib.queryNode(aaeId,selector,opts);
						},codeTag,null,query, {});
						if(node && node.rect){
							let rect=node.rect;
							await moveMouseTo(page,rect.x+rect.width*0.5+dx,rect.y+rect.height*0.5+dx,opts.smooth);
							await clickMouse(page);
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
						codeTag=await ensureCodeLib(page);
						node=await page.evaluate((codeTag,aaeId,selector,opts)=>{
							let codeLib=window[codeTag];
							return codeLib.queryNode(aaeId,selector,opts);
						},codeTag,null,query, {});
						query=`[aaeid="${node.AAEId}"]`;
						await page.type(query, content);
						break;
					}
				}
				res.json({ code: 200});
			};
		}
		
		//-------------------------------------------------------------------
		//Handle Dialogs:
		//-------------------------------------------------------------------
		{
			//---------------------------------------------------------------
			apiMap['aaeeAcceptDialog']=async function (req, res, next) {
				let reqVO, pageId, page;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				
				if(page.aaeDialog){
					await page.aaeDialog.accept(reqVO.value);
					page.aaeDialog=null;
					res.json({ code: 200});
					return;
				}
				if(page.aaeFileDialog){
					//Mapping files' path:
					let zonePath,files;
					zonePath=browser.aaeZonePath;
					if(!zonePath){
						res.json({ code: 500, info: "AcceptFileChooser:Browser don't have AAEZone." });
						return;
					}
					files=reqVO.files;
					if(files) {
						files = files.map((item) => {
							if (item.indexOf("/") >= 0) {
								throw Error("AcceptFileChooser: file path error.");
							}
							return zonePath + "/" + item;
						});
						await page.aaeFileDialog.accept(files);
						page.aaeFileDialog = null;
						res.json({ code: 200 });
						if (reqVO.deleteFile) {
							for (let path of files) {
								deleteFile(path);
							}
						}
					}else{
						res.json({ code: 400, info: "AcceptFileChooser: Missing files for accept FileChooser." });
					}
					return;
				}
				throw Error("No dialog to accept");
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeDismissDialog']=async function (req, res, next) {
				let reqVO, pageId, page;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);

				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}

				if(page.aaeDialog){
					await page.aaeDialog.dismiss();
					page.aaeDialog=null;
					res.json({ code: 200});
					return;
				}
				if(page.aaeFileDialog){
					await page.aaeFileDialog.cancel();
					page.aaeFileDialog=null;
					res.json({ code: 200});
					return;
				}
				throw Error("No dialog to dismiss");
			};
			
			//---------------------------------------------------------------
			apiMap['aaeDialogMessage']=async function (req, res, next) {
				let reqVO, pageId, page,message;
				reqVO = req.body.vo;
				pageId = reqVO.page;
				page = pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				if(page.aaeDialog){
					message=await page.aaeDialog.message();
					res.json({ code: 200,message:message});
					return;
				}
				throw Error("No dialog.");
			};

			//---------------------------------------------------------------
			apiMap['aaeDialogDefaultValue']=async function (req, res, next) {
				let reqVO, pageId, page,value;
				reqVO = req.body.vo;
				pageId = reqVO.page;
				page = pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				if(page.aaeDialog){
					value=await page.aaeDialog.defaultValue();
					res.json({ code: 200,value:value});
					return;
				}
				throw Error("No dialog.");
			};
		}

		//-------------------------------------------------------------------
		//Trace page events
		//-------------------------------------------------------------------
		{
			const MAX_EVENTS=200;
			let startTrace=async function(page,opts){
				let baseTag,codeTag;
				function addTraceEvent(event){
					const list=page.traceEvents;
					event.eventIndex=page.nextTraceEventIndex++;
					list.push(event);
					if(list.length>MAX_EVENTS){
						list.shift();
					}
				}
				
				opts=opts||{network:true,navigation:true};
				codeTag=page.aaeeTraceTag;
				if(codeTag){
					return codeTag;
				}
				codeTag=randomTag(5,true);
				page.aaeeTraceTag=codeTag;
				page.traceEvents=[];
				page.nextTraceEventIndex=0;
				let ensureTrace=async()=> {
					baseTag=await ensureCodeLib(page);
					try {
						await page.exposeFunction(codeTag + "_ReportEvent", function (event) {
							addTraceEvent(event);
						});
					}catch(err){
					}
					await page.evaluate((baseTag, codeTag) => {
						let OnClick, OnDblClick, OnInput, OnKey, OnDocScrollEnd, OnScrollEnd;
						let addEvent = window[codeTag + "_ReportEvent"];
						baseTag = window[baseTag];
						console.log(`baseTag: ${baseTag}, codeTag:${codeTag}`);
						
						OnClick = function (evt) {
							let target = evt.target;
							let evtwraper;
							if (target) {
								target = baseTag.wrapNode(target, null, undefined);
							}
							evtwraper = {
								event: "click", target: target,
								button: evt.button, x: evt.x, y: evt.y,
								pageX: evt.pageX, pageY: evt.pageY,
								offsetX: evt.offseetX, offsetY: evt.offseetY,
								altKey: evt.altKey, ctrlKey: evt.ctrlKey, metaKey: evt.metaKey, shiftKey: evt.shiftKey,
							};
							addEvent(evtwraper);
						};
						
						OnDblClick = function (evt) {
							let target = evt.target;
							let evtwraper;
							if (target) {
								target = baseTag.wrapNode(target, null, undefined);
							}
							evtwraper = {
								event: "dblclick", target: target,
								button: evt.button, x: evt.x, y: evt.y,
								pageX: evt.pageX, pageY: evt.pageY,
								offsetX: evt.offseetX, offsetY: evt.offseetY,
								altKey: evt.altKey, ctrlKey: evt.ctrlKey, metaKey: evt.metaKey, shiftKey: evt.shiftKey,
							};
							addEvent(evtwraper);
						};
						
						OnInput = function (evt) {
							let target = evt.target;
							let evtwraper;
							if (target) {
								target = baseTag.wrapNode(target, null, undefined);
							}
							evtwraper = {
								event: "input", target: target, value: evt.target.value
							};
							addEvent(evtwraper);
						};
						
						OnKey = function (evt) {
							let target = evt.target;
							let evtwraper;
							if (target) {
								target = baseTag.wrapNode(target, null, undefined);
							}
							evtwraper = {
								event: "keydown", target: target,
								key: evt.key, code: evt.key,
								isComposing: evt.isComposing,
								altKey: evt.altKey, ctrlKey: evt.ctrlKey, metaKey: evt.metaKey, shiftKey: evt.shiftKey,
							};
							addEvent(evtwraper);
						};
						
						//Setup mouse / keyboard tracer
						document.body.addEventListener("click", OnClick, true);
						document.body.addEventListener("dblclick", OnDblClick, true);
						document.body.addEventListener("input", OnInput, true);
						document.body.addEventListener("keydown", OnKey, true);
					}, baseTag, codeTag);
				};
				await ensureTrace();
				{
					//Setup navigation events:
					page.on("load",async ()=>{
						let url;
						try {
							url = await page.url();
							let event = {
								event: "load", url: url
							};
							await ensureTrace();
							addTraceEvent(event);
						}catch(err){
						}
					});
				}
				{
					//Setup popup events:
					page.on("popup",async (newPage)=>{
						let event,browser,newPageId;
						try {
							browser = page.browser();
							if (newPage) {
								newPageId = getPageId(browser.pageMap, newPage, true);
								event = {
									event: "popup", page: newPageId
								};
							}
						}catch(err){
						}
					});
				}
				{
					//Setup navigation events:
					//page.setRequestInterception(true);
					page.on('request', ir => {
						let event,url,method,headers,isNavigationRequest,postData;
						try {
							method = ir.method();
							url = ir.url();
							postData = ir.postData();
							headers = ir.headers();
							isNavigationRequest=ir.isNavigationRequest();
							event = {
								event: "request",
								method, url, headers, postData, isNavigationRequest
							};
							addTraceEvent(event);
						}catch(err){
						}
					});
					page.on('response', async (ir) => {
						let event,url,method,headers,text,contentType,status;
						try {
							url=ir.url();
							text=await ir.text();
							headers=ir.headers();
							status=ir.status();
							contentType=headers["content-type"];
							event={
								event:"response",
								method,url,headers,text,status
							};
							if(contentType.indexOf("json")>=0){
								try {
									event.json = await ir.json();
								}catch(err) {
								}
							}
							addTraceEvent(event);
						}catch(err){
						}
					});
				}
			}
			
			//-------------------------------------------------------------------
			apiMap['aaeeTracePage'] = async function (req, res, next) {
				let reqVO, pageId, page,opts;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				opts=reqVO.options||reqVO.opts||{};
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				await startTrace(page,opts);
				res.json({ code: 200});
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeGetTraceEvents'] = async function (req, res, next) {
				let reqVO, pageId, page,events,list,fromIdx,lastIdx,callTime;

				function getEvents(){
					let i,n,list,evt;
					evt=events[events.length-1];
					if(evt){
						if(lastIdx && evt.eventIndex===lastIdx) {
							return null;
						}
						lastIdx = evt.eventIndex;
					}
					n=events.length;
					GetList:{
						for (i = 0; i < n; i++) {
							if(events[i].eventIndex>fromIdx){
								list=events.slice(i);
								break GetList;
							}
						}
						return null;
					}
					return list;
				}
				
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = browserMap.get(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId=reqVO.frame;
				if(frameId){
					page=page.aaeeObjsMap.get(frameId);
				}
				callTime=Date.now();
				lastIdx=0;
				events=page.traceEvents;
				fromIdx=reqVO.fromIndex||0;
				do{
					list = getEvents();
					if(list){
						res.json({ code: 200,events:list});
						return;
					}
					if(Date.now()-callTime>30*1000){
						res.json({ code: 200,events:[]});
						return;
					}
					await sleep(100);
				}while (1);
			};
		}
		
		//-------------------------------------------------------------------
		//Utilities:
		//-------------------------------------------------------------------
		{
			//-------------------------------------------------------------------
			apiMap['aaeeGetClipboard'] = async function (req, res, next) {
				let content = await clipboardy.read();
				res.json({code:200,content:content});
			};
		}
	}
	
	if(AAFarm_Entry){
		let exePath,dataDir,opts;
		opts={headless:false};
		
		//Executable path:
		exePath=AAFarm_Executable;
		if(exePath){
			if (!pathLib.isAbsolute(exePath)) {
				exePath = pathLib.join(app.get("AppHomePath"), exePath);
			}
			opts.executablePath=exePath;
		}

		//UserData path:
		dataDir=AAFarm_DataDirRoot;
		if(dataDir) {
			if (!pathLib.isAbsolute(dataDir)) {
				dataDir = pathLib.join(app.get("AppHomePath"), dataDir);
			}
			opts.userDataDir=pathLib.join(dataDir,"AAHOME");
		}
		opts.defaultViewport=null;
		
		let browserId = "" + (nextBrowserId++);
		//let browser = await puppeteer.launch(opts);
		let browser = await startPPT(opts);
		browser.aaePc=browser.process();
		browser.aaeBrowserId=browserId;
		browserMap.set(browserId, browser);
		browser.pageMap=new Map();
		browserAliasMap.set("AAHOME",browserId);
		browser.aaeeAlias="AAHOME";
		browser.on("disconnected",()=>{
			browserMap.delete(browserId);
			browserAliasMap.delete("AAHOME");
			//Do something about the process:
			try{
				browser.aaePc.kill("SIGKILL");
			}catch(err){
			}
		});
		
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

		let pageMap=browser.pageMap;
		let pageId = "" + (nextPageId++);
		let page = await browser.newPage();
		pageMap.set(pageId, page);
		//await page.setViewport({width:1200,height:900});
		try {
			await page.goto(AAFarm_Entry, {});
		}catch(err){
		}
	}
}
export {browserMap,browserAliasMap,getBrowserId,openBrowser};