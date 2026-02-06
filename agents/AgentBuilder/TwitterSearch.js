//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1HDBOSUN90MoreImports*/
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*}#1HDBOSUN90MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1HDBOSUN90StartDoc*/
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let TwitterSearch=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ClosePage,WaitFlag,TypeKeyword,ReadRes,CheckNumber,ReadMore,Back2App,TipResult,ShowRes,ShowPage,ScrollDown,CheckRounds;
	let readRounds=0;
	
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
	segs["ClosePage"]=ClosePage=async function(input){//:1J9PBM8TH0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		try{
			await page.close();
			context[pageVal]=null;
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1J9PBM8TH0ErrorCode*/
			/*}#1J9PBM8TH0ErrorCode*/
		}
		return {result:result};
	};
	ClosePage.jaxId="1J9PBM8TH0"
	ClosePage.url="ClosePage@"+agentURL
	
	segs["WaitFlag"]=WaitFlag=async function(input){//:1JBHHCNF50
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=200;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1JBHHCNF50PreCodes*/
		page = globalContext.aaPage;
		context[pageVal] = page;
		context.webRpa = globalContext.webRpa;
		context.search = input.search;
		context.searchNum = input.searchNum;
		context.comments = input.comments;
		console.log("input.comments",input.comments);
		/*}#1JBHHCNF50PreCodes*/
		try{
			result=$flag?(await context[$flag]):input;
		}catch(error){
			return {result:error};
		}
		$waitAfter && (await sleep($waitAfter))
		/*#{1JBHHCNF50PostCodes*/
		/*}#1JBHHCNF50PostCodes*/
		return {seg:TypeKeyword,result:(result),preSeg:"1JBHHCNF50",outlet:"1JBHHD4CE1"};
	};
	WaitFlag.jaxId="1JBHHCNF50"
	WaitFlag.url="WaitFlag@"+agentURL
	
	segs["TypeKeyword"]=TypeKeyword=async function(input){//:1JB45QRSC0
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="(//input[@data-testid='SearchBox_Search_Input'])";
		let $queryHint="";
		let $key=context.search;
		let $options={};
		let $waitBefore=200;
		let $waitAfter=500;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		/*#{1JB45QRSC0PreCodes*/
		//page = globalContext.aaPage;
		//context[pageVal] = page;
		//context.webRpa = globalContext.webRpa;
		//context.search = input.search;
		//context.searchNum = input.searchNum;
		/*}#1JB45QRSC0PreCodes*/
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JB45QRSC0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.type($query,$key,$options||{});
			}else{
				$pms=page.keyboard.type($key,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JB45QRSC0ErrorCode*/
			/*}#1JB45QRSC0ErrorCode*/
		}
		/*#{1JB45QRSC0PostCodes*/
		await page.keyboard.press('Enter');
		/*}#1JB45QRSC0PostCodes*/
		return {seg:ReadRes,result:(result),preSeg:"1JB45QRSC0",outlet:"1JB45TP9I0"};
	};
	TypeKeyword.jaxId="1JB45QRSC0"
	TypeKeyword.url="TypeKeyword@"+agentURL
	
	segs["ReadRes"]=ReadRes=async function(input){//:1JB47O9T70
		let result=input
		try{
			/*#{1JB47O9T70Code*/
			let page = context['aaPage'];
			//const timeline = await page.waitForSelector('div[aria-label="Timeline: Search timeline"]');
			const searchResults = await page.callFunction((searchNumber) => {
				const elements = document.querySelectorAll('div[data-testid="cellInnerDiv"]');
				console.log(elements,"elements");
				const results = [];
				
				if(elements){
					for (let el of elements) {
					const title = el.querySelector('div[data-testid="tweetText"]') ? el.querySelector('div[data-testid="tweetText"]').textContent.trim() : '';
					
					const author = el.querySelector('div[data-testid="User-Name"] a') ? el.querySelector('div[data-testid="User-Name"] a').textContent.trim() : '';
					
					const timeElements = el.querySelector('time');
					const time = timeElements ? timeElements.textContent.trim() : '';
					
					const urlElements = el.querySelector('a[href*="/status/"]');
					const url = urlElements ? 'https://twitter.com' + urlElements.getAttribute('href') : '';
					
					const replyElements = el.querySelector('span[data-testid="app-text-transition-container"]');
					const reply = replyElements ? replyElements.textContent.trim() : '';
					
					const allNumElements = el.querySelector('[aria-label*="replies,"]'); 
					const label = allNumElements ? allNumElements.getAttribute('aria-label') : ''; // "19 replies, 7 reposts, 68 likes, 18 bookmarks, 37236 views"
					const obj = {};
					if(label){
						label.match(/(\d+)\s+(\w+)/g).forEach(pair => {
							const [num, key] = pair.split(' '); 
							obj[key] = Number(num);
						});
					};
					
					const user = url.match(/^https?:\/\/twitter\.com\/([^\/]+)/)?.[1];
					const avatarImg =  document.querySelector(`a[href="/${user}"] img[src*="profile_images"]`);
					const avatarUrl = avatarImg ? avatarImg.src : '';
						
					console.log("obj ReadRes",obj)
					
					if(title && url){
						results.push({
							title,
							author,
							time,
							url,
							replies:obj.replies,
							reposts:obj.reposts,
							likes:obj.likes,
							bookmarks:obj.bookmarks,
							views:obj.views,
							avatarUrl,
						});
					};
				}
				}
				return results;
			},[context.searchNum]);
			console.log("searchResults",searchResults);
			//console.log("input",input);
			const prevResults = Array.isArray(input) ? input : [];                       
			const newPage = searchResults;                     
			const merged = prevResults.concat(newPage);
			context.finds= merged.length ? merged.slice(0,context.searchNum) : [];
			console.log("merged length", merged.length);
			result = context.finds;
			/*}#1JB47O9T70Code*/
		}catch(error){
			/*#{1JB47O9T70ErrorCode*/
			/*}#1JB47O9T70ErrorCode*/
		}
		return {seg:CheckNumber,result:(result),preSeg:"1JB47O9T70",outlet:"1JB47P5OF0"};
	};
	ReadRes.jaxId="1JB47O9T70"
	ReadRes.url="ReadRes@"+agentURL
	
	segs["CheckNumber"]=CheckNumber=async function(input){//:1JB4GD74L0
		let result=input;
		if(readRounds===0 && context.finds.length<context.searchNum && readRounds<10){
			return {seg:ShowPage,result:(input),preSeg:"1JB4GD74L0",outlet:"1JCFTQH2N0"};
		}
		if(context.finds.length<context.searchNum && readRounds<10){
			return {seg:ScrollDown,result:(input),preSeg:"1JB4GD74L0",outlet:"1JCIGU4JL0"};
		}
		return {seg:CheckRounds,result:(result),preSeg:"1JB4GD74L0",outlet:"1JB4GFCSK1"};
	};
	CheckNumber.jaxId="1JB4GD74L0"
	CheckNumber.url="CheckNumber@"+agentURL
	
	segs["ReadMore"]=ReadMore=async function(input){//:1JB4GJ65S0
		let result=input;
		/*#{1JB4GJ65S0PreCodes*/
		readRounds+=1;
		/*}#1JB4GJ65S0PreCodes*/
		return {seg:ReadRes,result:result,preSeg:"1JB47O9T70",outlet:"1JB4GKJ220"};
	
	};
	ReadMore.jaxId="1JB47O9T70"
	ReadMore.url="ReadMore@"+agentURL
	
	segs["Back2App"]=Back2App=async function(input){//:1JB4GL3J30
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		/*#{1JB4GL3J30PreCodes*/
		/*}#1JB4GL3J30PreCodes*/
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JB4GL3J30ErrorCode*/
			/*}#1JB4GL3J30ErrorCode*/
		}
		/*#{1JB4GL3J30PostCodes*/
		context.finds = result;
		/*}#1JB4GL3J30PostCodes*/
		return {seg:TipResult,result:(result),preSeg:"1JB4GL3J30",outlet:"1JB4GLKHG0"};
	};
	Back2App.jaxId="1JB4GL3J30"
	Back2App.url="Back2App@"+agentURL
	
	segs["TipResult"]=TipResult=async function(input){//:1JB4JA1RS0
		let result=input;
		let $channel="Process";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JB4JA1RS0PreCodes*/
		//content=`共找到：${context.finds.length}条笔记。`;
		content= ($ln==="CN") ? `共找到：${context.finds.length} 条笔记。` : `Find ${context.finds.length} notes.`;
		/*}#1JB4JA1RS0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JB4JA1RS0PostCodes*/
		const markdown = context.finds
		.map((d, i) => `${i + 1}. [${d.title.slice(0, 20)}${d.title.length > 20 ? '…' : ''}](${d.url})`)
		.filter(line => line !== '')   
		.join('\n');
		
		result = {
			markdown,
			finds: context.finds
		};
		/*}#1JB4JA1RS0PostCodes*/
		return {seg:ShowRes,result:(result),preSeg:"1JB4JA1RS0",outlet:"1JB4JB1AP0"};
	};
	TipResult.jaxId="1JB4JA1RS0"
	TipResult.url="TipResult@"+agentURL
	
	segs["ShowRes"]=ShowRes=async function(input){//:1JB4JCSAK0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?(input.markdown ? input.markdown : '未搜索到数据'):(input.markdown ? input.markdown : 'No data found'));
		/*#{1JB4JCSAK0PreCodes*/
		/*}#1JB4JCSAK0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JB4JCSAK0PostCodes*/
		result = {
			...input,
			comments: context.comments
		}
		/*}#1JB4JCSAK0PostCodes*/
		return {seg:ClosePage,result:(result),preSeg:"1JB4JCSAK0",outlet:"1JB4JE3VI0"};
	};
	ShowRes.jaxId="1JB4JCSAK0"
	ShowRes.url="ShowRes@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1JCIH72IO0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let $options={"focusBrowser":true};
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		/*#{1JCIH72IO0PreCodes*/
		/*}#1JCIH72IO0PreCodes*/
		try{
			await page.bringToFront($options);
			waitAfter && (await sleep(waitAfter))
			if($options.focusBrowser && $options.switchBack){
				let $browser=context.rpaBrowser;
				if($browser){
					await $browser.backToApp();
				}
			}
		}catch(error){
			/*#{1JCIH72IO0ErrorCode*/
			/*}#1JCIH72IO0ErrorCode*/
		}
		/*#{1JCIH72IO0PostCodes*/
		/*}#1JCIH72IO0PostCodes*/
		return {seg:ScrollDown,result:(result),preSeg:"1JCIH72IO0",outlet:"1JCIHAK0V0"};
	};
	ShowPage.jaxId="1JCIH72IO0"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["ScrollDown"]=ScrollDown=async function(input){//:1JCIH8BBJ0
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint="";
		let $deltaX=0;
		let $deltaY=500;
		let $options={"steps":10};
		let $waitBefore=500;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JCIH8BBJ0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.mouseWheel($query,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
			}else{
				$pms=page.mouseWheel(null,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JCIH8BBJ0ErrorCode*/
			/*}#1JCIH8BBJ0ErrorCode*/
		}
		return {seg:ReadMore,result:(result),preSeg:"1JCIH8BBJ0",outlet:"1JCIHAK100"};
	};
	ScrollDown.jaxId="1JCIH8BBJ0"
	ScrollDown.url="ScrollDown@"+agentURL
	
	segs["CheckRounds"]=CheckRounds=async function(input){//:1JCIHD9RO0
		let result=input;
		if(readRounds===0){
			return {seg:TipResult,result:(input),preSeg:"1JCIHD9RO0",outlet:"1JCIHFEGP0"};
		}
		return {seg:Back2App,result:(result),preSeg:"1JCIHD9RO0",outlet:"1JCIHFEGP1"};
	};
	CheckRounds.jaxId="1JCIHD9RO0"
	CheckRounds.url="CheckRounds@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"TwitterSearch",
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
			result={seg:WaitFlag,"input":input};
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


export default TwitterSearch;
export{TwitterSearch};
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
//		"entry": "WaitFlag",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH2869AD0",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {
//				"readRounds": {
//					"type": "number",
//					"valText": "0"
//				}
//			}
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
//					"def": "WebRpaClosePage",
//					"jaxId": "1J9PBM8TH0",
//					"attrs": {
//						"id": "ClosePage",
//						"viewName": "",
//						"label": "",
//						"x": "1905",
//						"y": "175",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9PBMF3R0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9PBMF3R1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J9PBMF3Q0",
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
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JBHHCNF50",
//					"attrs": {
//						"id": "WaitFlag",
//						"viewName": "",
//						"label": "",
//						"x": "80",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBHHD4CM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBHHD4CM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "200",
//						"outlet": {
//							"jaxId": "1JBHHD4CE1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB45QRSC0"
//						},
//						"catchlet": {
//							"jaxId": "1JBHHD4CE0",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1JB45QRSC0",
//					"attrs": {
//						"id": "TypeKeyword",
//						"viewName": "",
//						"label": "",
//						"x": "300",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB45TP9O0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB45TP9O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Type",
//						"query": "(//input[@data-testid='SearchBox_Search_Input'])",
//						"queryHint": "",
//						"key": "#context.search",
//						"async": "false",
//						"options": "null",
//						"waitBefore": "200",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1JB45TP9I0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB47O9T70"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JB47O9T70",
//					"attrs": {
//						"id": "ReadRes",
//						"viewName": "",
//						"label": "",
//						"x": "530",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB47P5ON0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB47P5ON1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JB47P5OF0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB4GD74L0"
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
//					"def": "brunch",
//					"jaxId": "1JB4GD74L0",
//					"attrs": {
//						"id": "CheckNumber",
//						"viewName": "",
//						"label": "",
//						"x": "745",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB4GFCSS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB4GFCSS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JB4GFCSK1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JCIHD9RO0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JCFTQH2N0",
//									"attrs": {
//										"id": "ShowPage",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JCFTRRRV0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JCFTRRRV1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#readRounds===0 && context.finds.length<context.searchNum && readRounds<10"
//									},
//									"linkedSeg": "1JCIH72IO0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JCIGU4JL0",
//									"attrs": {
//										"id": "More",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JCIGU4JR0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JCIGU4JR1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#context.finds.length<context.searchNum && readRounds<10"
//									},
//									"linkedSeg": "1JCIH8BBJ0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JB4GJ65S0",
//					"attrs": {
//						"id": "ReadMore",
//						"viewName": "",
//						"label": "",
//						"x": "1465",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JB47O9T70",
//						"outlet": {
//							"jaxId": "1JB4GKJ220",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JB4GL3J30",
//					"attrs": {
//						"id": "Back2App",
//						"viewName": "",
//						"label": "",
//						"x": "1245",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB4GLKHN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB4GLKHN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JB4GLKHG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB4JA1RS0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JB4JA1RS0",
//					"attrs": {
//						"id": "TipResult",
//						"viewName": "",
//						"label": "",
//						"x": "1465",
//						"y": "175",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB4JCN3H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB4JCN3H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Process",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JB4JB1AP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB4JCSAK0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JB4JCSAK0",
//					"attrs": {
//						"id": "ShowRes",
//						"viewName": "",
//						"label": "",
//						"x": "1685",
//						"y": "175",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB4JGA8V0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB4JGA8V1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "#input.markdown ? input.markdown : 'No data found'",
//							"localize": {
//								"EN": "#input.markdown ? input.markdown : 'No data found'",
//								"CN": "#input.markdown ? input.markdown : '未搜索到数据'"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JB4JE3VI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9PBM8TH0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaActivePage",
//					"jaxId": "1JCIH72IO0",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "1010",
//						"y": "70",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIHAK1C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIHAK1C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JCIHAK0V0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCIH8BBJ0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JCIH8BBJ0",
//					"attrs": {
//						"id": "ScrollDown",
//						"viewName": "",
//						"label": "",
//						"x": "1240",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIHAK1C2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIHAK1C3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Mouse Wheel",
//						"query": "",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"deltaX": "0",
//						"deltaY": "500",
//						"async": "false",
//						"options": "{\"steps\":10}",
//						"waitBefore": "500",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JCIHAK100",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB4GJ65S0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JCIHD9RO0",
//					"attrs": {
//						"id": "CheckRounds",
//						"viewName": "",
//						"label": "",
//						"x": "1010",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIHFEGV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIHFEGV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JCIHFEGP1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JB4GL3J30"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JCIHFEGP0",
//									"attrs": {
//										"id": "Zero",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JCIHFEGV2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JCIHFEGV3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#readRounds===0"
//									},
//									"linkedSeg": "1JB4JA1RS0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}