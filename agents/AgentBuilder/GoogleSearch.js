//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1HDBOSUN90MoreImports*/
import fs from 'fs';
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
function writeLog(message) {
	// 如果 message 是对象，转成字符串
	const text = typeof message === 'object' ? JSON.stringify(message, null, 2) : message;
	const time = new Date().toLocaleString();
	
	fs.appendFileSync('./my_log.txt', `[${time}] ${text}\n`);
}

// 用法：
// console.log("Starting...");  // 只在控制台
// writeLog("Found url: " + url); // 写入文件

/*}#1HDBOSUN90MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1HDBOSUN90StartDoc*/
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let GoogleSearch=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let OpenPage,Enough,Extract,NextPage,Return,OpenNextPage,ClosePage,ShowRes,CheckNumber,Notify,GoogleTipRes;
	/*#{1HDBOSUN90LocalVals*/
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
	/*}#1HDBOSUN90PreContext*/
	context={};
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let $agent,agent,segs={};
	segs["OpenPage"]=OpenPage=async function(input){//:1IH28P38Q0
		let pageVal="aaPage";
		let $url="https://www.google.com";
		let $waitBefore=0;
		let $waitAfter=500;
		let $width=1200;
		let $height=900;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		/*#{1IH28P38Q0PreCodes*/
		$url = `https://www.google.com.hk/search?client=firefox-b-d&channel=entpr&q=${encodeURIComponent(input.search)}`
		// 【修改1】 初始化全局结果数组
		context.allResults = [];
		// 【修改2】 将初始URL设为下一页URL，以便Enough组件中的循环可以使用
		context.nextPageUrl = $url;
		context.rpaBrowser = globalContext.rpaBrowser;
		context.webRpa = globalContext.webRpa;
		/*}#1IH28P38Q0PreCodes*/
		try{
			context[pageVal]=page=await context.rpaBrowser.newPage();
			($width && $height) && (await page.setViewport({width:$width,height:$height}));
			$userAgent && (await page.setUserAgent($userAgent));
			await page.goto($url,$openOpts);
			$waitAfter && (await sleep($waitAfter));
		}catch(error){
			/*#{1IH28P38Q0ErrorCode*/
			/*}#1IH28P38Q0ErrorCode*/
		}
		/*#{1IH28P38Q0PostCodes*/
		globalContext.aaPage = context[pageVal];
		context.search = input.search;
		context.searchNum = input.searchNum;
		/*}#1IH28P38Q0PostCodes*/
		return {seg:Notify,result:(true),preSeg:"1IH28P38Q0",outlet:"1IH28P9TV0"};
	};
	OpenPage.jaxId="1IH28P38Q0"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["Enough"]=Enough=async function(input){//:1JBEECULO0
		let result=input;
		let list=input;
		let i,n,item,loopR;
		/*#{1JBEECULO0PreLoop*/
		let page=context["aaPage"];
		console.log(`Starting loop. Target: ${context.searchNum}`);
		/* 第一次迭代完成后关闭首页 */
		await page.close();
		n = 10000
		// 制造一个对应的初始化数组
		list = Array.from({length: n}, (_, i) => i);
		/*}#1JBEECULO0PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1JBEECULO0InLoopPre*/
			item = context.nextPageUrl;
			/*}#1JBEECULO0InLoopPre*/
			loopR=await session.runAISeg(agent,OpenNextPage,item,"1JBEECULO0","1JBEEFC5G2")
			if(loopR==="break"){
				break;
			}
			/*#{1JBEECULO0InLoopPost*/
			if (page) {
				if(i===0){
					//await page.close();
				}
			};
			if (context.allResults.length >= context.searchNum) {
				console.log("Collected enough results, breaking loop.");
				break; 
			}
			if (!context.nextPageUrl) {	
				console.log("No next page URL found, breaking loop.");
				break;
			}
			/*}#1JBEECULO0InLoopPost*/
		}
		/*#{1JBEECULO0PostCodes*/
		
		/*}#1JBEECULO0PostCodes*/
		return {seg:Return,result:(result),preSeg:"1JBEECULO0",outlet:"1JBEEFC5F0"};
	};
	Enough.jaxId="1JBEECULO0"
	Enough.url="Enough@"+agentURL
	
	segs["Extract"]=Extract=async function(input){//:1JBEEJKDN0
		let result=input
		try{
			/*#{1JBEEJKDN0Code*/
			try {
				const page = context.aaPage;
				
				// 1. 等待核心元素加载
				// 尝试等待 Google 的结果列表容器
				try {
					console.log("Waiting for selectors...");
					// writeLog("Waiting for selectors (div.g or a[jsname='UWckNb'])...");
					// 假如 aaPage 封装了 waitForSelector，则使用它；否则依靠 sleep
					if (page.waitForSelector) {
						await page.waitForSelector('div.g, a[jsname="UWckNb"]', { timeout: 10000 });
					} else {
						await sleep(1000); // 降级方案
					}
				} catch (waitErr) {
					console.log("Wait timeout (ignoring): " + waitErr.message);
				}
			
				// 2. 使用 callFunction 提取数据
				// 注意：callFunction 第一个参数是函数，第二个参数是参数数组(这里不需要传参，传空数组或不传)
				const currentResults = await page.callFunction(() => {
					let items = [];
					
					// 方案A: 使用你在 Parse 中提供的精确选择器
					const specificLinks = Array.from(document.querySelectorAll('a[jsname="UWckNb"].zReHs'));
					if (specificLinks.length > 0) {
						items = specificLinks.map(link => {
							const h3 = link.querySelector('h3.LC20lb.MBeuO.DKV0Md');
							return {
								title: h3 ? h3.textContent : 'No Title',
								url: link.href,
								platform: 'google'
							};
						});
					}
					return items;
				});
			
				// 记录日志
				const foundCount = currentResults ? currentResults.length : 0;
				const msg = `Extract finished. Found items: ${foundCount}`;
				console.log(msg);
				// writeLog(msg);
			
				// 3. 数据处理 (去重)
				if (foundCount > 0) {
					const newItems = currentResults.filter(newItem => 
						!context.allResults.some(existing => existing.url === newItem.url)
					);
					context.allResults = [...context.allResults, ...newItems];
					// writeLog(`Added ${newItems.length} unique items. Total: ${context.allResults.length}`);
				}
			
				// 4. 【关键】使用 callFunction 滑动到底部
				// 这有助于触发懒加载，确保底部的"下一页"按钮被渲染
				await page.callFunction(() => {
					window.scrollTo(0, document.body.scrollHeight);
				});
				// 滑动后等待一下，给页面反应时间
				await sleep(1000);
			
			} catch (e) {
				console.error("Error in Extract:", e);
				// writeLog("Error in Extract: " + e.message);
			}
			/*}#1JBEEJKDN0Code*/
		}catch(error){
			/*#{1JBEEJKDN0ErrorCode*/
			/*}#1JBEEJKDN0ErrorCode*/
		}
		return {seg:CheckNumber,result:(result),preSeg:"1JBEEJKDN0",outlet:"1JBEEJV3I0"};
	};
	Extract.jaxId="1JBEEJKDN0"
	Extract.url="Extract@"+agentURL
	
	segs["NextPage"]=NextPage=async function(input){//:1JBEEP5DO0
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query="(//a[@id='pnnext'])";
		let $multi=false;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=1000;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1JBEEP5DO0PreCodes*/
		/*}#1JBEEP5DO0PreCodes*/
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			/*#{1JBEEP5DO0CheckItem*/
			/*}#1JBEEP5DO0CheckItem*/
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JBEEP5DO0ErrorCode*/
			/*}#1JBEEP5DO0ErrorCode*/
		}
		/*#{1JBEEP5DO0PostCodes*/
		try {
			// 【修改】不使用 result.evaluate，改用 page.callFunction 直接在页面内获取
			// 因为 queryNode 已经确认元素存在，这里直接 querySelector 获取 href 是安全的
			const nextUrl = await page.callFunction(() => {
				const el = document.querySelector('a#pnnext');
				return el ? el.href : null;
			});
			if (nextUrl) {
				console.log("NextPage URL found:", nextUrl);
				// writeLog("NextPage URL found: " + nextUrl);
				context.nextPageUrl = nextUrl;
			} else {
				// 如果 href 为空，手动抛错进入 catch 处理
				throw new Error("Node found but href is empty");
			}
		} catch (e) {
			console.error("Error extracting next page URL:", e);
			// writeLog("Error extracting next page URL: " + (e.message || e));
			context.nextPageUrl = null;
		}
		/*}#1JBEEP5DO0PostCodes*/
		return {result:result};
	};
	NextPage.jaxId="1JBEEP5DO0"
	NextPage.url="NextPage@"+agentURL
	
	segs["Return"]=Return=async function(input){//:1JBEERSIG0
		let result=input
		try{
			/*#{1JBEERSIG0Code*/
			const finalResults = (context.allResults || []).slice(0, context.searchNum);
			
			const markdown = [
				finalResults.map((d,i)=>`${i+1}. [${d.title}](${d.url})`).join('\n')
			].filter(line => line !== '').join('\n');
			
			result = {
				result: "Finish",
				finds: finalResults,
				markdown,
			};
			
			//result = {
				//result: "Finish",
				//finds: finalResults,
				//type: "post",
				//totalFound: finalResults.length
			//};
			console.log("Agent finished. Returning data.");
			// writeLog("Agent finished. Returning data.");
			// writeLog(JSON.stringify(result));
			/*}#1JBEERSIG0Code*/
		}catch(error){
			/*#{1JBEERSIG0ErrorCode*/
			/*}#1JBEERSIG0ErrorCode*/
		}
		return {seg:GoogleTipRes,result:(result),preSeg:"1JBEERSIG0",outlet:"1JBEES2RE0"};
	};
	Return.jaxId="1JBEERSIG0"
	Return.url="Return@"+agentURL
	
	segs["OpenNextPage"]=OpenNextPage=async function(input){//:1JBEF0OF50
		let pageVal="aaPage";
		let $url=input;
		let $waitBefore=0;
		let $waitAfter=500;
		let $width=1200;
		let $height=900;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		/*#{1JBEF0OF50PreCodes*/
		console.log(`Opening next page: ${$url}`);
		// writeLog(`Opening next page: ${$url}`);
		/*}#1JBEF0OF50PreCodes*/
		try{
			context[pageVal]=page=await context.rpaBrowser.newPage();
			($width && $height) && (await page.setViewport({width:$width,height:$height}));
			$userAgent && (await page.setUserAgent($userAgent));
			await page.goto($url,$openOpts);
			$waitAfter && (await sleep($waitAfter));
		}catch(error){
			/*#{1JBEF0OF50ErrorCode*/
			/*}#1JBEF0OF50ErrorCode*/
		}
		/*#{1JBEF0OF50PostCodes*/
		/*}#1JBEF0OF50PostCodes*/
		return {seg:Extract,result:(true),preSeg:"1JBEF0OF50",outlet:"1JBEF0UOA0"};
	};
	OpenNextPage.jaxId="1JBEF0OF50"
	OpenNextPage.url="OpenNextPage@"+agentURL
	
	segs["ClosePage"]=ClosePage=async function(input){//:1JBERLFKE0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		/*#{1JBERLFKE0PreCodes*/
		/*}#1JBERLFKE0PreCodes*/
		try{
			await page.close();
			context[pageVal]=null;
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JBERLFKE0ErrorCode*/
			/*}#1JBERLFKE0ErrorCode*/
		}
		/*#{1JBERLFKE0PostCodes*/
		/*}#1JBERLFKE0PostCodes*/
		return {result:result};
	};
	ClosePage.jaxId="1JBERLFKE0"
	ClosePage.url="ClosePage@"+agentURL
	
	segs["ShowRes"]=ShowRes=async function(input){//:1JBF2MP1H0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.markdown;
		session.addChatText(role,content,opts);
		return {seg:ClosePage,result:(result),preSeg:"1JBF2MP1H0",outlet:"1JBF2N7VP0"};
	};
	ShowRes.jaxId="1JBF2MP1H0"
	ShowRes.url="ShowRes@"+agentURL
	
	segs["CheckNumber"]=CheckNumber=async function(input){//:1JBF2P8RG0
		let result=input;
		/*#{1JBF2P8RG0Start*/
		console.log(context.allResults.length,"allResults",context.searchNum,"searchNum");
		/*}#1JBF2P8RG0Start*/
		if(context.allResults.length < context.searchNum){
			return {seg:NextPage,result:(input),preSeg:"1JBF2P8RG0",outlet:"1JBF2QK0S0"};
		}
		/*#{1JBF2P8RG0Post*/
		/*}#1JBF2P8RG0Post*/
		return {result:result};
	};
	CheckNumber.jaxId="1JBF2P8RG0"
	CheckNumber.url="CheckNumber@"+agentURL
	
	segs["Notify"]=Notify=async function(input){//:1JBF3FF6S0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("谷歌页面已打开，AI 正在执行联网搜索任务......"):("Google page has been opened, AI is performing online search tasks......"));
		/*#{1JBF3FF6S0PreCodes*/
		/*}#1JBF3FF6S0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JBF3FF6S0PostCodes*/
		/*}#1JBF3FF6S0PostCodes*/
		return {seg:Enough,result:(result),preSeg:"1JBF3FF6S0",outlet:"1JBF3H9150"};
	};
	Notify.jaxId="1JBF3FF6S0"
	Notify.url="Notify@"+agentURL
	
	segs["GoogleTipRes"]=GoogleTipRes=async function(input){//:1JBH3JDHT0
		let result=input;
		let $channel="Process";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JBH3JDHT0PreCodes*/
		//content=`共找到：${input.finds.length}条笔记。`;
		content= ($ln==="CN") ? `共找到：${input.finds.length} 条笔记。` : `Find ${input.finds.length} notes.`;
		/*}#1JBH3JDHT0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JBH3JDHT0PostCodes*/
		/*}#1JBH3JDHT0PostCodes*/
		return {seg:ShowRes,result:(result),preSeg:"1JBH3JDHT0",outlet:"1JBH3JR8C0"};
	};
	GoogleTipRes.jaxId="1JBH3JDHT0"
	GoogleTipRes.url="GoogleTipRes@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"GoogleSearch",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN90PreEntry*/
			/*}#1HDBOSUN90PreEntry*/
			result={seg:OpenPage,"input":input};
			/*#{1HDBOSUN90PostEntry*/
			/*}#1HDBOSUN90PostEntry*/
			return result;
		},
		/*#{1HDBOSUN90MoreAgentAttrs*/
		/*}#1HDBOSUN90MoreAgentAttrs*/
	};
	/*#{1HDBOSUN90PostAgent*/
	/*}#1HDBOSUN90PostAgent*/
	return agent;
};
/*#{1HDBOSUN90ExCodes*/
/*}#1HDBOSUN90ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1HDBOSUN90PostDoc*/
/*}#1HDBOSUN90PostDoc*/


export default GoogleSearch;
export{GoogleSearch};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1HDBOSUN90",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1HDBOSUNA0",
//			"attrs": {
//				"agent": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1HDBOSUNA4",
//					"attrs": {
//						"constructArgs": {
//							"jaxId": "1HDBOSUNB0",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1HDBOSUNB1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1HDBOSUNB2",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportType": "UI Data Template",
//						"exportClass": "false",
//						"superClass": ""
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1HDBOSUNA1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "OpenPage",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH2869AD0",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1HDBOSUNA3",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1HDIJB7SK6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1IH28P38Q0",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "-115",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH28P9U10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH28P9U11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "https://www.google.com",
//						"vpWidth": "1200",
//						"vpHeight": "900",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1IH28P9TV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBF3FF6S0"
//						},
//						"run": "",
//						"errorSeg": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1JBEECULO0",
//					"attrs": {
//						"id": "Enough",
//						"viewName": "",
//						"label": "",
//						"x": "295",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBEEFC5G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBEEFC5G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1JBEEFC5G2",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBEF0OF50"
//						},
//						"catchlet": {
//							"jaxId": "1JBEEFC5F0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBEERSIG0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JBEEJKDN0",
//					"attrs": {
//						"id": "Extract",
//						"viewName": "",
//						"label": "",
//						"x": "735",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBEEJV3L0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBEEJV3L1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JBEEJV3I0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBF2P8RG0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JBEEP5DO0",
//					"attrs": {
//						"id": "NextPage",
//						"viewName": "",
//						"label": "",
//						"x": "1165",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBEEPTHJ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBEEPTHJ3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "(//a[@id='pnnext'])",
//						"queryHint": "",
//						"multi": "false",
//						"options": "",
//						"errorSeg": "",
//						"waitBefore": "0",
//						"waitAfter": "1000",
//						"outlet": {
//							"jaxId": "1JBEEPTHG1",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JBEEP5D60",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									}
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JBEERSIG0",
//					"attrs": {
//						"id": "Return",
//						"viewName": "",
//						"label": "",
//						"x": "505",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBEES2RG0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBEES2RG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JBEES2RE0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBH3JDHT0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1JBEF0OF50",
//					"attrs": {
//						"id": "OpenNextPage",
//						"viewName": "",
//						"label": "",
//						"x": "505",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBEF0UOB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBEF0UOB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "#input",
//						"vpWidth": "1200",
//						"vpHeight": "900",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1JBEF0UOA0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBEEJKDN0"
//						},
//						"run": "",
//						"errorSeg": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1JBERLFKE0",
//					"attrs": {
//						"id": "ClosePage",
//						"viewName": "",
//						"label": "",
//						"x": "1145",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBERLL8G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBERLL8G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JBERLL8D0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JBF2MP1H0",
//					"attrs": {
//						"id": "ShowRes",
//						"viewName": "",
//						"label": "",
//						"x": "945",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBF2N8000",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBF2N8001",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.markdown",
//						"outlet": {
//							"jaxId": "1JBF2N7VP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBERLFKE0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JBF2P8RG0",
//					"attrs": {
//						"id": "CheckNumber",
//						"viewName": "",
//						"label": "",
//						"x": "925",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBF2QK100",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBF2QK110",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JBF2QK0S1",
//							"attrs": {
//								"id": "Down",
//								"desc": "输出节点。",
//								"output": ""
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JBF2QK0S0",
//									"attrs": {
//										"id": "More",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JBF2QK111",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JBF2QK112",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#context.allResults.length < context.searchNum"
//									},
//									"linkedSeg": "1JBEEP5DO0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JBF3FF6S0",
//					"attrs": {
//						"id": "Notify",
//						"viewName": "",
//						"label": "",
//						"x": "100",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBF3H91A0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBF3H91A1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Google page has been opened, AI is performing online search tasks......",
//							"localize": {
//								"EN": "Google page has been opened, AI is performing online search tasks......",
//								"CN": "谷歌页面已打开，AI 正在执行联网搜索任务......"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JBF3H9150",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBEECULO0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JBH3JDHT0",
//					"attrs": {
//						"id": "GoogleTipRes",
//						"viewName": "",
//						"label": "",
//						"x": "705",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBH3JR8D0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBH3JR8D1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Process",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JBH3JR8C0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBF2MP1H0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}