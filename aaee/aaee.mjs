import {WebDriveSys} from "../rpa/WebDriveSys.mjs";
import {WebRpa} from "../rpa/WebRpa.mjs";
import clipboardy from "clipboardy";
import pathLib from 'path';
import { promises as fs } from 'fs';
import { Buffer } from 'buffer'
import fsp from 'fs/promises'


const AAEE_VERSION="0.0.1";

const aliasPattern = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
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
			let reqVO, opts, browsers, browserId, browser, alias, list, stub, pages, page, pageId, url, title;
			reqVO = req.body.vo;
			
			browsers = await WebDriveSys.getBrowsers();
			list = [];
			for (browser of browsers) {
				alias = browser.aaeeAlias;
				stub = { id: browser.browserId, alias: alias };
				pages = await browser.getPages();
				stub.pages = [];
				for (page of pages) {
					pageId = page.context;
					url = await page.url();
					title = await page.title();
					stub.pages.push({ id: pageId, url: url, title: title });
				}
				list.push(stub);
			}
			res.json({ code: 200, browsers: list });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeOpenBrowser'] = async function (req, res, next) {
			let reqVO, opts, browserId, browser, alias, dirPath;
			reqVO = req.body.vo;
			opts = reqVO.opts || reqVO.options || {};
			alias = reqVO.alias;
			browser = await WebDriveSys.openBrowser(alias, opts);
			res.json({ code: 200, browser: browser.browserId, alias: alias });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeGetPageByTitle'] = async function (req, res, next) {
			let reqVO, browserId, browser, title, page;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			title = reqVO.title;
			if (!browserId) {
				let browsers = await WebDriveSys.getBrowsers();
				for (browser of browsers) {
					let pages = await browser.getPages();
					for (page of pages) {
						if ((await page.title()) === title) {
							res.json({
								code: 200,
								browser: browser.browserId,
								alias: browser.aaeeAlias,
								page: getPageId(browser.pageMap, page)
							});
							return;
						}
					}
				}
				res.json({ code: 200, page: null });
				return;
			}
			browser = WebDriveSys.getBrowser(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			let pages = await browser.getPages();
			for (page of pages) {
				if ((await page.title()) === title) {
					res.json({ code: 200, page: getPageId(browser.pageMap, page) });
					return;
				}
			}
			res.json({ code: 200, page: null });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeOpenPage'] = async function (req, res, next) {
			let reqVO, browserId, browser, page, pageId, pageMap, time;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = WebDriveSys.getBrowser(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			page = await browser.newPage();
			res.json({ code: 200, page: page.context });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeCloseBrowser'] = async function (req, res, next) {
			let reqVO, browserId, browser;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = WebDriveSys.getBrowser(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			await browser.close();
			res.json({ code: 200 });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeHeartBeat'] = async function (req, res, next) {
			let reqVO, browserId, browser;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			res.json({ code: 200 });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeGetBrowserUserAgent'] = async function (req, res, next) {
			let reqVO, browserId, browser, ua;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = WebDriveSys.getBrowser(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:130.0) Gecko/20100101 Firefox/130.0";//TODO: Make a real one
			res.json({ code: 200, userAgent: ua });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeGetPages'] = async function (req, res, next) {
			let reqVO, browserId, browser, list;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = WebDriveSys.getBrowser(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			list = await browser.getPages();
			list = list.map((item) => {
				return item.context;
			})
			res.json({ code: 200, pages: list });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeCreateContext'] = async function (req, res, next) {
			res.json({ code: 500, info: "Not supported." });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeCloseContext'] = async function (req, res, next) {
			res.json({ code: 500, info: "Not supported." });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeSaveFile'] = async function (req, res, next) {
			res.json({ code: 500, info: "Not supported." });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeDeleteFile'] = async function (req, res, next) {
			res.json({ code: 500, info: "Not supported." });
		};
	}
	
	//***********************************************************************
	//Page API:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		apiMap['aaeeOpenURL'] = apiMap['aaeeGoto'] = async function (req, res, next) {
			let reqVO, browserId, browser, pageId, page, url, pageMap;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = WebDriveSys.getBrowser(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			pageMap = browser.pageMap;
			pageId = reqVO.page;
			page = pageMap.get(pageId);
			if (!page) {
				res.json({ code: 400, info: "Page not found." });
				return;
			}
			url = reqVO.url;
			await page.goto(url, reqVO.options || {});
			res.json({ code: 200 });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeGoBack'] = async function (req, res, next) {
			let reqVO, browserId, browser, pageId, page, pageMap;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = WebDriveSys.getBrowser(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			pageMap = browser.pageMap;
			pageId = reqVO.page;
			page = pageMap.get(pageId);
			if (!page) {
				res.json({ code: 400, info: "Page not found." });
				return;
			}
			await page.goBack(reqVO.options || {});
			res.json({ code: 200 });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeGoForward'] = async function (req, res, next) {
			let reqVO, browserId, browser, pageId, page, pageMap;
			reqVO = req.body.vo;
			browserId = reqVO.browser;
			browser = WebDriveSys.getBrowser(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			pageMap = browser.pageMap;
			pageId = reqVO.page;
			page = pageMap.get(pageId);
			if (!page) {
				res.json({ code: 400, info: "Page not found." });
				return;
			}
			await page.goForward(reqVO.options || {});
			res.json({ code: 200 });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeClosePage'] = async function (req, res, next) {
			let reqVO, pageId, page;
			reqVO = req.body.vo;
			let browserId = reqVO.browser;
			let browser = WebDriveSys.getBrowser(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			let pageMap = browser.pageMap;
			pageId = reqVO.page;
			page = pageMap.get(pageId);
			if (!page) {
				res.json({ code: 400, info: "Page not found." });
				return;
			}
			await page.close();
			pageMap.delete((pageId));
			res.json({ code: 200 });
		};
		
		//-------------------------------------------------------------------
		apiMap['aaeeBringToFront'] = async function (req, res, next) {
			let reqVO, pageId, page;
			reqVO = req.body.vo;
			let browserId = reqVO.browser;
			let opts = reqVO.options || reqVO.opts || {};
			let browser = WebDriveSys.getBrowser(browserId);
			if (!browser) {
				res.json({ code: 400, info: "Browser not found." });
				return;
			}
			let pageMap = browser.pageMap;
			pageId = reqVO.page;
			page = pageMap.get(pageId);
			if (!page) {
				res.json({ code: 400, info: "Page not found." });
				return;
			}
			await page.bringToFront(opts);
			res.json({ code: 200 });
		};
		
		//-------------------------------------------------------------------
		//Set/Get page properties: DONE
		//-------------------------------------------------------------------
		{
			//---------------------------------------------------------------
			apiMap['aaeeSetPageViewport'] = async function (req, res, next) {
				res.json({ code: 200 });//Not supported:
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeSetPageUserAgent'] = async function (req, res, next) {
				res.json({ code: 200 });//Not supported:
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeGetPageTitle'] = async function (req, res, next) {
				let reqVO, pageId, page, title;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
					page = page.frameMap.get(frameId);
				}
				title = await page.title();
				res.json({ code: 200, title: title });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeGetPageURL'] = async function (req, res, next) {
				let reqVO, pageId, page, url;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
					page = page.frameMap.get(frameId);
				}
				url = await page.url();
				res.json({ code: 200, url: url });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeGetPageViewport'] = async function (req, res, next) {
				let reqVO, pageId, page, viewport;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
				viewport = await page.getViewport();
				res.json({ code: 200, viewport: { ...viewport } });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeGetFrames'] = async function (req, res, next) {
				let reqVO, pageId, page, list, framesMap;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
					page = page.frameMap.get(frameId);
				}
				list = await page.frames();
				list = list.map((item) => {
					return frameId = item.context;
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
				let reqVO, pageId, page, apiObj, api, i, n, name, result;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
					page = page.frameMap.get(frameId);
				}
				api = reqVO.api;
				apiObj = page;
				if (!Array.isArray(api)) {
					api = [api];
				}
				n = api.length;
				if (n > 1) {
					for (i = 0; i < n - 1; i++) {
						name = api[i];
						apiObj = apiObj[name];
					}
				}
				api = api[api.length - 1];
				result = await apiObj[api](...reqVO.args);
				res.json({ code: 200, result: result });
			};
		}
		
		//-------------------------------------------------------------------
		//Eval related:
		//-------------------------------------------------------------------
		{
			//---------------------------------------------------------------
			apiMap['aaeeAddScriptTag'] = async function (req, res, next) {
				res.json({ code: 500, info: "Not supported yet." });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeAddStyleTag'] = async function (req, res, next) {
				res.json({ code: 500, info: "Not supported yet." });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeGetCodeTag'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
					page = page.frameMap.get(frameId);
				}
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				codeTag = await page.ensureCodeLib(page);
				res.json({ code: 200, codeTag: codeTag });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeEvaluate'] = async function (req, res, next) {
				let reqVO, pageId, page, code, opts, args, result;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
					page = page.frameMap.get(frameId);
				}
				code = reqVO.code;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				opts = reqVO.opts || {};
				args = reqVO.args || opts.args;
				if (opts.argNames) {
					let func = new Function(...opts.argNames, code);
					result = await page.evaluate(func, ...args);
				} else {
					if (args) {
						result = await page.evaluate(code, ...args);
					} else {
						result = await page.evaluate(code);
					}
				}
				res.json({ code: 200, result: result });
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeEvaluateHandle'] = async function (req, res, next) {
				let reqVO, pageId, page, code, opts, args, result;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
					page = page.frameMap.get(frameId);
				}
				code = reqVO.code;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				opts = reqVO.opts || {};
				args = reqVO.args || opts.args;
				if (opts.argNames) {
					let func = new Function(...opts.argNames, code);
					result = await page.evaluateHandle(func, ...args);
				} else {
					if (args) {
						result = await page.evaluateHandle(code, ...args);
					} else {
						result = await page.evaluateHandle(code);
					}
				}
				res.json({ code: 200, result: result });
			};
		}
		
		//-------------------------------------------------------------------
		//Wait functions: DONE
		//-------------------------------------------------------------------
		{
			//---------------------------------------------------------------
			apiMap['aaeeWaitFor'] = async function (req, res, next) {
				let reqVO, pageId, page, action, options;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				action = reqVO.action.toLowerCase();
				switch (action) {
					case "navi":
					case "navigation":
						await page.waitForNavigation(options);
						res.json({ code: 200 });
						return;
					case "prompt":
					case "deviceprompt":
						await page.waitForDialog(options);
						res.json({ code: 200 });
						return;
					case "filechooser": {
						let dlg = await page.waitForFileChooser(options);
						res.json({ code: 200 });
						return;
					}
					case "networkidle":
						await page.waitForNetworkIdle(options);
						res.json({ code: 200 });
						return;
					case "dialog": {
						await page.waitForDialog(options);
						res.json({ code: 200 });
						return;
					}
					case "selector":
					case "query": {
						let selector = reqVO.selector || reqVO.query;
						let handle = await page.waitForSelector(selector, options);
						res.json({ code: 200, handle: handle });
						return;
					}
					case "function": {
						let func = reqVO.function || reqVO.code;
						let args = reqVO.args || reqVO.arguments || [];
						let result = await page.waitForFunction(func, options, ...args);
						res.json({ code: 200, result: result });
						return;
					}
					default:
						res.json({ code: 400, info: `Unknown wait action: ${action}` });
						return;
				}
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeWaitQuery'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, options, selector, timeout, node, baseNode, startTime;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				let pageMap = browser.pageMap;
				pageId = reqVO.page;
				page = pageMap.get(pageId);
				selector = reqVO.selector;
				options = reqVO.options || {};
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let handle = await page.waitForSelector(selector, options);
				res.json({ code: 200, handle: handle });
			};
			
			//TODO: waitForFunction
			//---------------------------------------------------------------
			apiMap['aaeeWaitFunction'] = async function (req, res, next) {
				let reqVO, pageId, page, action, options, code, func;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				code = reqVO.code || reqVO.function;
				let args = reqVO.args || reqVO.arguments || [];
				let result = await page.waitForFunction(code, options, ...args);
				res.json({ code: 200, result: result });
			};
		}
		
		//-------------------------------------------------------------------
		//Read page functions: DONE
		//-------------------------------------------------------------------
		{
			//-------------------------------------------------------------------
			apiMap['aaeeReadArticle'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, text;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
					page = page.frameMap.get(frameId);
				}
				text = await page.readArticle();
				res.json({ code: 200, text: text });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeGetNodeAttribute'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, opts, aaeId, key, value;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId = reqVO.AAEId || reqVO.aaeId;
				key = reqVO.key;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				value = await WebRpa.getNodeAttr(aaeId, key);
				res.json({ code: 200, value: value });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeSetNodeAttribute'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, opts, aaeId, key, value;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId = reqVO.AAEId || reqVO.aaeId;
				key = reqVO.key;
				value = reqVO.value;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				await WebRpa.setNodeAttr(aaeId, key, value);
				res.json({ code: 200 });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeGetNodeAttributes'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, aaeId, attrs;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId = reqVO.AAEId || reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				attrs = await WebRpa.getNodeAttrs(page, aaeId);
				res.json({ code: 200, attributes: attrs });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeGetNodeParent'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, aaeId, wraped;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId = reqVO.AAEId || reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				wraped = await WebRpa.getNodeParent(page, aaeId);
				res.json({ code: 200, node: wraped });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeGetNodeChildren'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, aaeId, children;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId = reqVO.AAEId || reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				children = await WebRpa.getNodeChildren(page, aaeId);
				res.json({ code: 200, children: children });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeReadNodeView'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, opts, aaeId, view;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				opts = reqVO.options || reqVO.opts;
				aaeId = reqVO.AAEId || reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				view = await WebRpa.readNodeView(page, aaeId, opts);
				res.json({ code: 200, view: view });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeReadNodeText'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, opts, aaeId, text;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				opts = reqVO.opts;
				aaeId = reqVO.AAEId || reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				text = await WebRpa.readNodeText(page, aaeId, opts);
				res.json({ code: 200, text: text });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeReadNodeHTML'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, aaeId, text, options;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId = reqVO.AAEId || reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				options = reqVO.options || reqVO.opts;
				text = await WebRpa.readNodeHTML(page, aaeId, options);
				res.json({ code: 200, html: text });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeGetNodeHTML'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, aaeId, text;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId = reqVO.AAEId || reqVO.aaeId;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				text = await WebRpa.getInnerHTML(page, aaeId);
				res.json({ code: 200, html: text });
			};

			//-------------------------------------------------------------------
			apiMap['aaeeCapturePage'] = async function (req, res, next) {
				let reqVO, pageId, page, opts, data, imgType;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
				opts = reqVO.opts || reqVO.options;
				opts = opts ? { ...opts, encoding: 'base64' } : { encoding: 'base64', fullPage: true, type: 'png' };
				opts.encoding = 'base64';
				data = await page.screenshot(opts);
				imgType = opts.type || 'png';
				switch (imgType) {
					case "png":
						data = "data:image/png;base64," + data;
						break;
					case "jpg":
						data = "data:image/jpeg;base64," + data;
						break;
					case "webp":
						data = "data:image/webp;base64," + data;
						break;
				}
				res.json({ code: 200, image: data });
			};
			
			//-------------------------------------------------------------------
			//Query page node(s):
			apiMap['aaeeQueryNode'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, opts, node, selector, aaeId;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				aaeId = reqVO.aaeId || reqVO.AAEId;
				opts = reqVO.options || reqVO.opts;
				selector = reqVO.selector;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				node = await WebRpa.queryNode(page, aaeId, selector, opts);
				res.json({ code: 200, node: node });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeQueryNodes'] = async function (req, res, next) {
				let reqVO, pageId, page, codeTag, opts, list, aaeId, selector;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				opts = reqVO.options || reqVO.opts;
				aaeId = reqVO.aaeId || reqVO.AAEId;
				selector = reqVO.selector;
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				list = await WebRpa.queryNodes(page, aaeId, selector, opts);
				res.json({ code: 200, list: list });
			};
		}
		
		//-------------------------------------------------------------------
		//User actions:
		//-------------------------------------------------------------------
		{
			//-------------------------------------------------------------------
			apiMap['aaeeUserAction'] = async function (req, res, next) {
				let reqVO, pageId, page, opts;
				let codeTag, query, action;
				reqVO = req.body.vo;
				pageId = reqVO.page;
				opts = reqVO.opts;
				action = opts.action;
				query = opts.query;
				
				page = pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				switch (action) {
					case "click": {
						let node, dx, dy;
						dx = opts.dx || 0;
						dy = opts.dy || 0;
						codeTag = await ensureCodeLib(page);
						node = await page.evaluate((codeTag, aaeId, selector, opts) => {
							let codeLib = window[codeTag];
							return codeLib.queryNode(aaeId, selector, opts);
						}, codeTag, null, query, {});
						if (node && node.rect) {
							let rect = node.rect;
							await moveMouseTo(page, rect.x + rect.width * 0.5 + dx, rect.y + rect.height * 0.5 + dx, opts.smooth);
							await clickMouse(page);
						}
						break;
					}
					case "type":
					case "paste": {
						let node, content;
						content = opts.content;
						if (!content) {
							content = await clipboardy.read();
						}
						codeTag = await ensureCodeLib(page);
						node = await page.evaluate((codeTag, aaeId, selector, opts) => {
							let codeLib = window[codeTag];
							return codeLib.queryNode(aaeId, selector, opts);
						}, codeTag, null, query, {});
						query = `[aaeid="${node.AAEId}"]`;
						await page.type(query, content);
						break;
					}
				}
				res.json({ code: 200 });
			};
		}
		
		//-------------------------------------------------------------------
		//Handle Dialogs:
		//-------------------------------------------------------------------
		{
			//---------------------------------------------------------------
			apiMap['aaeeAcceptDialog'] = async function (req, res, next) {
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
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.aaeeObjsMap.get(frameId);
				}
				
				if (page.aaeDialog) {
					await page.aaeDialog.accept(reqVO.value);
					page.aaeDialog = null;
					res.json({ code: 200 });
					return;
				}
				if (page.aaeFileDialog) {
					//Mapping files' path:
					let zonePath, files;
					zonePath = browser.aaeZonePath;
					if (!zonePath) {
						res.json({ code: 500, info: "AcceptFileChooser:Browser don't have AAEZone." });
						return;
					}
					files = reqVO.files;
					if (files) {
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
					} else {
						res.json({ code: 400, info: "AcceptFileChooser: Missing files for accept FileChooser." });
					}
					return;
				}
				throw Error("No dialog to accept");
			};
			
			//---------------------------------------------------------------
			apiMap['aaeeDismissDialog'] = async function (req, res, next) {
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
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.aaeeObjsMap.get(frameId);
				}
				
				if (page.aaeDialog) {
					await page.aaeDialog.dismiss();
					page.aaeDialog = null;
					res.json({ code: 200 });
					return;
				}
				if (page.aaeFileDialog) {
					await page.aaeFileDialog.cancel();
					page.aaeFileDialog = null;
					res.json({ code: 200 });
					return;
				}
				throw Error("No dialog to dismiss");
			};
			
			//---------------------------------------------------------------
			apiMap['aaeDialogMessage'] = async function (req, res, next) {
				let reqVO, pageId, page, message;
				reqVO = req.body.vo;
				pageId = reqVO.page;
				page = pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				if (page.aaeDialog) {
					message = await page.aaeDialog.message();
					res.json({ code: 200, message: message });
					return;
				}
				throw Error("No dialog.");
			};
			
			//---------------------------------------------------------------
			apiMap['aaeDialogDefaultValue'] = async function (req, res, next) {
				let reqVO, pageId, page, value;
				reqVO = req.body.vo;
				pageId = reqVO.page;
				page = pageMap.get(pageId);
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				if (page.aaeDialog) {
					value = await page.aaeDialog.defaultValue();
					res.json({ code: 200, value: value });
					return;
				}
				throw Error("No dialog.");
			};
		}
		
		//-------------------------------------------------------------------
		//Trace page events
		//-------------------------------------------------------------------
		{
			const MAX_EVENTS = 200;
			let startTrace = async function (page, opts) {
				let baseTag, codeTag;
				
				function addTraceEvent (event) {
					const list = page.traceEvents;
					event.eventIndex = page.nextTraceEventIndex++;
					list.push(event);
					if (list.length > MAX_EVENTS) {
						list.shift();
					}
				}
				
				opts = opts || { network: true, navigation: true };
				codeTag = page.aaeeTraceTag;
				if (codeTag) {
					return codeTag;
				}
				codeTag = randomTag(5, true);
				page.aaeeTraceTag = codeTag;
				page.traceEvents = [];
				page.nextTraceEventIndex = 0;
				let ensureTrace = async () => {
					baseTag = await ensureCodeLib(page);
					try {
						await page.exposeFunction(codeTag + "_ReportEvent", function (event) {
							addTraceEvent(event);
						});
					} catch (err) {
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
					page.on("load", async () => {
						let url;
						try {
							url = await page.url();
							let event = {
								event: "load", url: url
							};
							await ensureTrace();
							addTraceEvent(event);
						} catch (err) {
						}
					});
				}
				{
					//Setup popup events:
					page.on("popup", async (newPage) => {
						let event, browser, newPageId;
						try {
							browser = page.browser();
							if (newPage) {
								newPageId = getPageId(browser.pageMap, newPage, true);
								event = {
									event: "popup", page: newPageId
								};
							}
						} catch (err) {
						}
					});
				}
				{
					//Setup navigation events:
					//page.setRequestInterception(true);
					page.on('request', ir => {
						let event, url, method, headers, isNavigationRequest, postData;
						try {
							method = ir.method();
							url = ir.url();
							postData = ir.postData();
							headers = ir.headers();
							isNavigationRequest = ir.isNavigationRequest();
							event = {
								event: "request",
								method, url, headers, postData, isNavigationRequest
							};
							addTraceEvent(event);
						} catch (err) {
						}
					});
					page.on('response', async (ir) => {
						let event, url, method, headers, text, contentType, status;
						try {
							url = ir.url();
							text = await ir.text();
							headers = ir.headers();
							status = ir.status();
							contentType = headers["content-type"];
							event = {
								event: "response",
								method, url, headers, text, status
							};
							if (contentType.indexOf("json") >= 0) {
								try {
									event.json = await ir.json();
								} catch (err) {
								}
							}
							addTraceEvent(event);
						} catch (err) {
						}
					});
				}
			}
			
			//-------------------------------------------------------------------
			apiMap['aaeeTracePage'] = async function (req, res, next) {
				let reqVO, pageId, page, opts;
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
				if (!browser) {
					res.json({ code: 400, info: "Browser not found." });
					return;
				}
				pageId = reqVO.page;
				page = browser.pageMap.get(pageId);
				opts = reqVO.options || reqVO.opts || {};
				if (!page) {
					res.json({ code: 400, info: "Page not found." });
					return;
				}
				let frameId = reqVO.frame;
				if (frameId) {
					page = page.frameMap.get(frameId);
				}
				//await startTrace(page, opts);
				res.json({ code: 200 });
			};
			
			//-------------------------------------------------------------------
			apiMap['aaeeGetTraceEvents'] = async function (req, res, next) {
				let reqVO, pageId, page, events, list, fromIdx, lastIdx, callTime;
				
				function getEvents () {
					let i, n, list, evt;
					evt = events[events.length - 1];
					if (evt) {
						if (lastIdx && evt.eventIndex === lastIdx) {
							return null;
						}
						lastIdx = evt.eventIndex;
					}
					n = events.length;
					GetList:{
						for (i = 0; i < n; i++) {
							if (events[i].eventIndex > fromIdx) {
								list = events.slice(i);
								break GetList;
							}
						}
						return null;
					}
					return list;
				}
				
				reqVO = req.body.vo;
				let browserId = reqVO.browser;
				let browser = WebDriveSys.getBrowser(browserId);
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
					page = page.frameMap.get(frameId);
				}
				callTime = Date.now();
				lastIdx = 0;
				events = page.traceEvents;
				fromIdx = reqVO.fromIndex || 0;
				do {
					list = getEvents();
					if (list) {
						res.json({ code: 200, events: list });
						return;
					}
					if (Date.now() - callTime > 30 * 1000) {
						res.json({ code: 200, events: [] });
						return;
					}
					await sleep(100);
				} while (1);
			};
		}
		
		//-------------------------------------------------------------------
		//Utilities:
		//-------------------------------------------------------------------
		{
			//-------------------------------------------------------------------
			apiMap['aaeeGetClipboard'] = async function (req, res, next) {
				let content = await clipboardy.read();
				res.json({ code: 200, content: content });
			};
		}
	}
}
export {};