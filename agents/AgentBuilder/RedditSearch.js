//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1JC5LFDLN0MoreImports*/
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*}#1JC5LFDLN0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1JC5LFDLN0StartDoc*/
/*}#1JC5LFDLN0StartDoc*/
//----------------------------------------------------------------------------
let redditSearch=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let OpenRedditPage,Notify,WaitNavi,ReadFeeds,CheckNumber,ShowPage,ScrollDown,CheckRounds,ReadMore,Back2App,TipResult,ClosePage,ShowRes;
	let readRounds=0;
	
	/*#{1JC5LFDLN0LocalVals*/
	/*}#1JC5LFDLN0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1JC5LFDLN0ParseArgs*/
		/*}#1JC5LFDLN0ParseArgs*/
	}
	
	/*#{1JC5LFDLN0PreContext*/
	/*}#1JC5LFDLN0PreContext*/
	context={
		search: "",
		searchNum: "",
		finds: [],
		urlMap: new Map(),
		/*#{1JC5LFDLN5ExCtxAttrs*/
		/*}#1JC5LFDLN5ExCtxAttrs*/
	};
	/*#{1JC5LFDLN0PostContext*/
	/*}#1JC5LFDLN0PostContext*/
	let $agent,agent,segs={};
	segs["OpenRedditPage"]=OpenRedditPage=async function(input){//:1JC5LGFA60
		let pageVal="aaPage";
		let $url=`https://www.reddit.com/search/?q=${input.search}&type=posts`;
		let $waitBefore=0;
		let $waitAfter=500;
		let $width=1200;
		let $height=900;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		/*#{1JC5LGFA60PreCodes*/
		context.rpaBrowser = globalContext.rpaBrowser;
		context.webRpa = globalContext.webRpa;
		/*}#1JC5LGFA60PreCodes*/
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url,$openOpts);
		$waitAfter && (await sleep($waitAfter));
		/*#{1JC5LGFA60PostCodes*/
		globalContext.aaPage = context[pageVal];
		context.search = input.search;
		context.searchNum = input.searchNum;
		/*}#1JC5LGFA60PostCodes*/
		return {seg:Notify,result:(true),preSeg:"1JC5LGFA60",outlet:"1JC5LHGQ40"};
	};
	OpenRedditPage.jaxId="1JC5LGFA60"
	OpenRedditPage.url="OpenRedditPage@"+agentURL
	
	segs["Notify"]=Notify=async function(input){//:1JC5MC9GH0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("Reddit已打开。"):("Reddit has been opened."));
		session.addChatText(role,content,opts);
		return {seg:WaitNavi,result:(result),preSeg:"1JC5MC9GH0",outlet:"1JC5MDT7N0"};
	};
	Notify.jaxId="1JC5MC9GH0"
	Notify.url="Notify@"+agentURL
	
	segs["WaitNavi"]=WaitNavi=async function(input){//:1JC5MF6430
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=1000;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			result=await context[$flag];
		}catch(error){
			return {result:error};
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:ReadFeeds,result:(result),preSeg:"1JC5MF6430",outlet:"1JC5MFNTM1"};
	};
	WaitNavi.jaxId="1JC5MF6430"
	WaitNavi.url="WaitNavi@"+agentURL
	
	segs["ReadFeeds"]=ReadFeeds=async function(input){//:1JC5MGV4S0
		let result=input
		try{
			/*#{1JC5MGV4S0Code*/
			let page=context["aaPage"];
			let data =await page.callFunction(function(){
				let items=[];
				const mainContainer = document.querySelector('main[id="main-content"]');
				if (!mainContainer) return [];
				const box1 =  mainContainer.querySelectorAll('div[data-testid="search-post-with-content-preview"]');
				const box2 = mainContainer.querySelectorAll('div[data-testid="search-post-unit"]')
				const postItems = (box1 && box1.length)? box1 : box2;
				//console.log("postItems",postItems);
				postItems.forEach(o => {
					//const titleEl = o.querySelector('a[data-testid="post-title-text"], a[data-testid="post-title"]');
					const titleEl = o.querySelector('a[data-testid="post-title"]');
					const title = titleEl ? titleEl.textContent.trim() : null;
					const url = titleEl ? titleEl.href : null;
					const author = o.querySelector('span[class="truncate"]') ? o.querySelector('span[class="truncate"]').innerText.trim(): null;
					const time = o.querySelector('time') ? o.querySelector('time').innerText.trim() : null;
					const num = o.querySelector('div[data-testid="search-counter-row"]');
					const votes  = num ? num.querySelector('span:nth-of-type(1)').textContent.trim() : null;
					const comments  = num ? num.querySelector('span:nth-of-type(3)').textContent.trim() : null;
					let vo = {
						title,
						url,
						author,
						time,
						votes,
						comments,
						platform: 'reddit',
					};
					if(vo.title && vo.url){
						items.push(vo);
					}
				});
				return items;
			},[]);
			//console.log(data,'ReadFeeds');
			{
				let finds,feed,urlMap;
				finds=context.finds;
				urlMap=context.urlMap;
				for(feed of data){
					if(!urlMap.get(feed.url)){
						finds.push(feed);
						urlMap.set(feed.url,feed);
					}
				}
			}
			console.log(context.finds,'ReadFeeds',context.finds.length,'===');
			result={ result: "Finish", finds: data, type: "Card" };
			/*}#1JC5MGV4S0Code*/
		}catch(error){
			/*#{1JC5MGV4S0ErrorCode*/
			/*}#1JC5MGV4S0ErrorCode*/
		}
		return {seg:CheckNumber,result:(result),preSeg:"1JC5MGV4S0",outlet:"1JC5MHCF40"};
	};
	ReadFeeds.jaxId="1JC5MGV4S0"
	ReadFeeds.url="ReadFeeds@"+agentURL
	
	segs["CheckNumber"]=CheckNumber=async function(input){//:1JC5V8IQC0
		let result=input;
		/*#{1JC5V8IQC0Start*/
		/*}#1JC5V8IQC0Start*/
		if(readRounds===0 && context.finds.length < context.searchNum && readRounds<10){
			/*#{1JC5V9VDV0Codes*/
			/*}#1JC5V9VDV0Codes*/
			return {seg:ShowPage,result:(input),preSeg:"1JC5V8IQC0",outlet:"1JC5V9VDV0"};
		}
		if(context.finds.length < context.searchNum && readRounds<10){
			return {seg:ScrollDown,result:(input),preSeg:"1JC5V8IQC0",outlet:"1JC5V95OI0"};
		}
		/*#{1JC5V8IQC0Post*/
		/*}#1JC5V8IQC0Post*/
		return {seg:CheckRounds,result:(result),preSeg:"1JC5V8IQC0",outlet:"1JC5V9VDV1"};
	};
	CheckNumber.jaxId="1JC5V8IQC0"
	CheckNumber.url="CheckNumber@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1JC5VDAK40
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let $options={"focusBrowser":true};
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.bringToFront($options);
		waitAfter && (await sleep(waitAfter))
		return {seg:ScrollDown,result:(result),preSeg:"1JC5VDAK40",outlet:"1JC5VDU2B0"};
	};
	ShowPage.jaxId="1JC5VDAK40"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["ScrollDown"]=ScrollDown=async function(input){//:1JC5VE4PG0
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint="";
		let $deltaX=0;
		let $deltaY=500;
		let $options=null;
		let $waitBefore=500;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JC5VE4PG0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			$pms=page.mouseWheel($query,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
		}else{
			$pms=page.mouseWheel(null,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
		}
		if($pms && (!$async)){await $pms;}$waitAfter && (await sleep($waitAfter))
		return {seg:ReadMore,result:(result),preSeg:"1JC5VE4PG0",outlet:"1JC5VF60S0"};
	};
	ScrollDown.jaxId="1JC5VE4PG0"
	ScrollDown.url="ScrollDown@"+agentURL
	
	segs["CheckRounds"]=CheckRounds=async function(input){//:1JC5VG5780
		let result=input;
		if(readRounds===0){
			return {seg:TipResult,result:(input),preSeg:"1JC5VG5780",outlet:"1JC5VK6050"};
		}
		return {seg:Back2App,result:(result),preSeg:"1JC5VG5780",outlet:"1JC5VK6051"};
	};
	CheckRounds.jaxId="1JC5VG5780"
	CheckRounds.url="CheckRounds@"+agentURL
	
	segs["ReadMore"]=ReadMore=async function(input){//:1JC5VJ9RK0
		let result=input;
		/*#{1JC5VJ9RK0PreCodes*/
		readRounds+=1;
		/*}#1JC5VJ9RK0PreCodes*/
		return {seg:ReadFeeds,result:result,preSeg:"1JC5MGV4S0",outlet:"1JC5VK6052"};
	
	};
	ReadMore.jaxId="1JC5MGV4S0"
	ReadMore.url="ReadMore@"+agentURL
	
	segs["Back2App"]=Back2App=async function(input){//:1JC5VKK5A0
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		if(browser){
			await browser.backToApp();
		}
		waitAfter && (await sleep(waitAfter))
		return {seg:TipResult,result:(result),preSeg:"1JC5VKK5A0",outlet:"1JC5VMTAS0"};
	};
	Back2App.jaxId="1JC5VKK5A0"
	Back2App.url="Back2App@"+agentURL
	
	segs["TipResult"]=TipResult=async function(input){//:1JC5VLB8F0
		let result=input;
		let $channel="Process";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JC5VLB8F0PreCodes*/
		//content=`共找到：${context.finds.length}条笔记。`;
		let data = (context.finds && context.finds.length) ? context.finds.slice(0,context.searchNum) : [];
		const markdown = [
			data.map((d,i)=>`${i+1}. [${d.title}](${d.url})`).join('\n')
		].filter(line => line !== '').join('\n');
		content=`共找到：${data.length}条笔记。`;
		/*}#1JC5VLB8F0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JC5VLB8F0PostCodes*/
		result = { ...input, finds: data, markdown};
		/*}#1JC5VLB8F0PostCodes*/
		return {seg:ShowRes,result:(result),preSeg:"1JC5VLB8F0",outlet:"1JC5VMTAS1"};
	};
	TipResult.jaxId="1JC5VLB8F0"
	TipResult.url="TipResult@"+agentURL
	
	segs["ClosePage"]=ClosePage=async function(input){//:1JC5VNG7G0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		/*#{1JC5VNG7G0PreCodes*/
		/*}#1JC5VNG7G0PreCodes*/
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		/*#{1JC5VNG7G0PostCodes*/
		/*}#1JC5VNG7G0PostCodes*/
		return {result:result};
	};
	ClosePage.jaxId="1JC5VNG7G0"
	ClosePage.url="ClosePage@"+agentURL
	
	segs["ShowRes"]=ShowRes=async function(input){//:1JC602I1U0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.markdown ? input.markdown : 'no data';
		/*#{1JC602I1U0PreCodes*/
		/*}#1JC602I1U0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JC602I1U0PostCodes*/
		/*}#1JC602I1U0PostCodes*/
		return {seg:ClosePage,result:(result),preSeg:"1JC602I1U0",outlet:"1JC6030PG0"};
	};
	ShowRes.jaxId="1JC602I1U0"
	ShowRes.url="ShowRes@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"redditSearch",
		url:agentURL,
		autoStart:true,
		jaxId:"1JC5LFDLN0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1JC5LFDLN0PreEntry*/
			/*}#1JC5LFDLN0PreEntry*/
			result={seg:OpenRedditPage,"input":input};
			/*#{1JC5LFDLN0PostEntry*/
			/*}#1JC5LFDLN0PostEntry*/
			return result;
		},
		/*#{1JC5LFDLN0MoreAgentAttrs*/
		/*}#1JC5LFDLN0MoreAgentAttrs*/
	};
	/*#{1JC5LFDLN0PostAgent*/
	/*}#1JC5LFDLN0PostAgent*/
	return agent;
};
/*#{1JC5LFDLN0ExCodes*/
/*}#1JC5LFDLN0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JC5LFDLN0PostDoc*/
/*}#1JC5LFDLN0PostDoc*/


export default redditSearch;
export{redditSearch};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JC5LFDLN0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JC5LFDLN1",
//			"attrs": {
//				"redditSearch": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JC5LFDLO0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JC5LFDLO1",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JC5LFDLO2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JC5LFDLO3",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportClass": "false",
//						"superClass": ""
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1JC5LFDLN2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "OpenRedditPage",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JC5LFDLN3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1JC5LFDLN4",
//			"attrs": {
//				"readRounds": {
//					"type": "number",
//					"valText": "0"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JC5LFDLN5",
//			"attrs": {
//				"search": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC5MAJNT0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"searchNum": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC5MAJNT1",
//					"attrs": {
//						"type": "Number",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"finds": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC5UH6OT0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"urlMap": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC5UH6OT1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "#new Map()",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1JC5LFDLN6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1JC5LGFA60",
//					"attrs": {
//						"id": "OpenRedditPage",
//						"viewName": "",
//						"label": "",
//						"x": "40",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5LHGQ70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5LHGQ71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "#`https://www.reddit.com/search/?q=${input.search}&type=posts`",
//						"vpWidth": "1200",
//						"vpHeight": "900",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1JC5LHGQ40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC5MC9GH0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JC5MC9GH0",
//					"attrs": {
//						"id": "Notify",
//						"viewName": "",
//						"label": "",
//						"x": "275",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5MDT7R0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5MDT7R1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Reddit has been opened.",
//							"localize": {
//								"EN": "Reddit has been opened.",
//								"CN": "Reddit已打开。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JC5MDT7N0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC5MF6430"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JC5MF6430",
//					"attrs": {
//						"id": "WaitNavi",
//						"viewName": "",
//						"label": "",
//						"x": "455",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5MFNTP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5MFNTP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "1000",
//						"outlet": {
//							"jaxId": "1JC5MFNTM1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC5MGV4S0"
//						},
//						"catchlet": {
//							"jaxId": "1JC5MFNTM0",
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
//					"def": "code",
//					"jaxId": "1JC5MGV4S0",
//					"attrs": {
//						"id": "ReadFeeds",
//						"viewName": "",
//						"label": "",
//						"x": "660",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5MHCF70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5MHCF71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JC5MHCF40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC5V8IQC0"
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
//					"jaxId": "1JC5V8IQC0",
//					"attrs": {
//						"id": "CheckNumber",
//						"viewName": "",
//						"label": "",
//						"x": "880",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5V9VE50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5V9VE51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JC5V9VDV1",
//							"attrs": {
//								"id": "Down",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JC5VG5780"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JC5V9VDV0",
//									"attrs": {
//										"id": "ShowPage",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JC5V9VE52",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC5V9VE53",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#readRounds===0 && context.finds.length < context.searchNum && readRounds<10"
//									},
//									"linkedSeg": "1JC5VDAK40"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JC5V95OI0",
//									"attrs": {
//										"id": "More",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JC5V9VE54",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC5V9VE55",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#context.finds.length < context.searchNum && readRounds<10"
//									},
//									"linkedSeg": "1JC5VE4PG0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaActivePage",
//					"jaxId": "1JC5VDAK40",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "1145",
//						"y": "90",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5VDU2M0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5VDU2M1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JC5VDU2B0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC5VE4PG0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JC5VE4PG0",
//					"attrs": {
//						"id": "ScrollDown",
//						"viewName": "",
//						"label": "",
//						"x": "1395",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5VF60V0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5VF60V1",
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
//						"options": "",
//						"waitBefore": "500",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JC5VF60S0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC5VJ9RK0"
//						},
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JC5VG5780",
//					"attrs": {
//						"id": "CheckRounds",
//						"viewName": "",
//						"label": "",
//						"x": "1150",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5VK9DE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5VK9DE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JC5VK6051",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JC5VKK5A0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JC5VK6050",
//									"attrs": {
//										"id": "Zero",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JC5VK9DE2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC5VK9DE3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#readRounds===0"
//									},
//									"linkedSeg": "1JC5VLB8F0"
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
//					"jaxId": "1JC5VJ9RK0",
//					"attrs": {
//						"id": "ReadMore",
//						"viewName": "",
//						"label": "",
//						"x": "1610",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JC5MGV4S0",
//						"outlet": {
//							"jaxId": "1JC5VK6052",
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
//					"jaxId": "1JC5VKK5A0",
//					"attrs": {
//						"id": "Back2App",
//						"viewName": "",
//						"label": "",
//						"x": "1395",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5VN16M0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5VN16M1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JC5VMTAS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC5VLB8F0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JC5VLB8F0",
//					"attrs": {
//						"id": "TipResult",
//						"viewName": "",
//						"label": "",
//						"x": "1650",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5VN16M2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5VN16M3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Process",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JC5VMTAS1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC602I1U0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1JC5VNG7G0",
//					"attrs": {
//						"id": "ClosePage",
//						"viewName": "",
//						"label": "",
//						"x": "2045",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5VP2RM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5VP2RM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JC5VOIGD0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JC602I1U0",
//					"attrs": {
//						"id": "ShowRes",
//						"viewName": "",
//						"label": "",
//						"x": "1850",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC6030PJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC6030PJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.markdown ? input.markdown : 'no data'",
//						"outlet": {
//							"jaxId": "1JC6030PG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC5VNG7G0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}