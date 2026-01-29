//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1J54NE9UK0MoreImports*/
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*}#1J54NE9UK0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1J54NE9UK0StartDoc*/
/*}#1J54NE9UK0StartDoc*/
//----------------------------------------------------------------------------
let rednoteSearch=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ClickSearch,TypeSearch,FlagNavi,WaitNavi,ReadFeeds,ClosePage,CheckNumber,ShowPage,ScrollDown,ReadMore,CheckRounds,Back2App,TipResult,ShowRes;
	let readRounds=0;
	
	/*#{1J54NE9UK0LocalVals*/
	/*}#1J54NE9UK0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1J54NE9UK0ParseArgs*/
		/*}#1J54NE9UK0ParseArgs*/
	}
	
	/*#{1J54NE9UK0PreContext*/
	/*}#1J54NE9UK0PreContext*/
	context={
		finds: [],
		urlMap: new Map(),
		search: "",
		searchNum: 20,
		/*#{1J54NE9UL4ExCtxAttrs*/
		/*}#1J54NE9UL4ExCtxAttrs*/
	};
	/*#{1J54NE9UK0PostContext*/
	/*}#1J54NE9UK0PostContext*/
	let $agent,agent,segs={};
	segs["ClickSearch"]=ClickSearch=async function(input){//:1J54O73FH0
		let result=true;
		let pageVal="aaPage";
		let $query="(//input[@id=\"search-input\"])";
		let $queryHint="";
		let $x=0;
		let $y=0;
		let $options={};
		let $waitBefore=0;
		let $waitAfter=300;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		$waitBefore && (await sleep($waitBefore));
		/*#{1J54O73FH0PreCodes*/
		context.webRpa = page = globalContext.aaPage;
		const browser = globalContext.rpaBrowser;
		const webRpa = globalContext.webRpa;
		context.search = input.search;
		context.searchNum = input.searchNum;
		/*}#1J54O73FH0PreCodes*/
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1J54O73FH0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			$pms=page.click($query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
		}else{
			$pms=page.mouse.click($x,$y,$options||{});
		}
		if($pms && (!$async)){await $pms;}$waitAfter && (await sleep($waitAfter))
		/*#{1J54O73FH0PostCodes*/
		/*}#1J54O73FH0PostCodes*/
		return {seg:FlagNavi,result:(result),preSeg:"1J54O73FH0",outlet:"1J54ORN5V0"};
	};
	ClickSearch.jaxId="1J54O73FH0"
	ClickSearch.url="ClickSearch@"+agentURL
	
	segs["TypeSearch"]=TypeSearch=async function(input){//:1J54OM67N0
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="";
		let $queryHint="";
		let $key=context.search;
		let $options={"delay":50,"coverEnter":0,"postEnter":true};
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		$waitBefore && (await sleep($waitBefore));
		/*#{1J54OM67N0PreCodes*/
		page = globalContext.aaPage;
		/*}#1J54OM67N0PreCodes*/
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1J54OM67N0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			$pms=page.type($query,$key,$options||{});
		}else{
			$pms=page.keyboard.type($key,$options||{});
		}
		if($pms && (!$async)){await $pms;}$waitAfter && (await sleep($waitAfter))
		/*#{1J54OM67N0PostCodes*/
		/*}#1J54OM67N0PostCodes*/
		return {seg:WaitNavi,result:(result),preSeg:"1J54OM67N0",outlet:"1J54ORN5V1"};
	};
	TypeSearch.jaxId="1J54OM67N0"
	TypeSearch.url="TypeSearch@"+agentURL
	
	segs["FlagNavi"]=FlagNavi=async function(input){//:1J54ONSTI0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $query="";
		let $queryHint="";
		let $waitBefore=0;
		let $waitAfter=0;
		let $options={};
		let $timeout=undefined;
		let page=context[pageVal];
		let $args=[];
		
		if($timeout){$options.timeout=$timeout;}
		$waitBefore && (await sleep($waitBefore));
		/*#{1J54ONSTI0PreCodes*/
		page = globalContext.aaPage;
		/*}#1J54ONSTI0PreCodes*/
		context[$flag]=page.waitForNavigation($options);
		$waitAfter && (await sleep($waitAfter))
		/*#{1J54ONSTI0PostCodes*/
		/*}#1J54ONSTI0PostCodes*/
		return {seg:TypeSearch,result:(result),preSeg:"1J54ONSTI0",outlet:"1J54ORN600"};
	};
	FlagNavi.jaxId="1J54ONSTI0"
	FlagNavi.url="FlagNavi@"+agentURL
	
	segs["WaitNavi"]=WaitNavi=async function(input){//:1J54OOCK20
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=2000;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1J54OOCK20PreCodes*/
		page = globalContext.aaPage;
		/*}#1J54OOCK20PreCodes*/
		try{
			result=await context[$flag];
		}catch(error){
			return {result:error};
		}
		$waitAfter && (await sleep($waitAfter))
		/*#{1J54OOCK20PostCodes*/
		/*}#1J54OOCK20PostCodes*/
		return {seg:ReadFeeds,result:(result),preSeg:"1J54OOCK20",outlet:"1J54ORN602"};
	};
	WaitNavi.jaxId="1J54OOCK20"
	WaitNavi.url="WaitNavi@"+agentURL
	
	segs["ReadFeeds"]=ReadFeeds=async function(input){//:1J54OOU3G0
		let result=input
		try{
			/*#{1J54OOU3G0Code*/
			let page = globalContext.aaPage;
			result=await page.callFunction(function(){
				let items,urlSet,cards,card,vo;
				function parseNoteCard(cardEl) {
					if (!cardEl) return null;
					// 笔记的入口链接（带封面图的 a 标签）
					let linkEl = cardEl.querySelector('a.cover.mask.ld');
					let url = linkEl ? linkEl.href : null;
					//console.log("linkEl",linkEl)
					// 封面图
					let coverImg = linkEl ? linkEl.querySelector('img') : null;
					let coverUrl = coverImg ? coverImg.src : null;
					//console.log("coverUrl",coverUrl)
					// 标题
					let titleEl = cardEl.querySelector('a.title span');
					let title = titleEl ? titleEl.innerText.trim() : null;
					// 作者
					let authorEl = cardEl.querySelector('.author .name-time-wrapper .name');
					let author = authorEl ? authorEl.innerText.trim() : null;
					// 发布时间
					let timeEl = cardEl.querySelector('.author .name-time-wrapper .time');
					let time = timeEl ? timeEl.innerText.trim() : null;
					// 点赞数
					let likeEl = cardEl.querySelector('.like-wrapper .count');
					let likes = likeEl ? likeEl.innerText.trim() : null;
			
					return {
						url,        // 直接打开笔记的 URL
						coverUrl,   // 封面图 URL
						title,      // 笔记标题
						author,     // 作者名
						time,       // 发布时间
						likes       // 点赞数
					};
				}
				items=[];urlSet=new Set();
				cards = document.querySelectorAll('section.note-item');
				//console.log("Cards:",cards);
				for(card of cards){
					vo=parseNoteCard(card);
					console.log("Card:",JSON.stringify(vo,null,"\t"));
					if(vo.url && vo.title){
						items.push(vo);
					}
				}
				//console.log("items",JSON.stringify(items,null,"\t"));
				return items;
			},[]);
			console.log("Cards length",result.length);
			{
				let finds,feed,urlMap;
				finds=context.finds;
				urlMap=context.urlMap;
				for(feed of result){
					if(!urlMap.get(feed.url)){
						finds.push(feed);
						urlMap.set(feed.url,feed);
					}
				}
			}
			//console.log("input ===",input);
			const prevResults = Array.isArray(input) ? input : [];                       
			const newPage = result;                     
			const merged = prevResults.concat(newPage);
			context.finds= merged.length ? merged.slice(0,context.searchNum) : [];
			console.log("merged length", merged.length);
			
			result={"result":"Finish",finds: context.finds,type:"Card"};
			/*}#1J54OOU3G0Code*/
		}catch(error){
			/*#{1J54OOU3G0ErrorCode*/
			/*}#1J54OOU3G0ErrorCode*/
		}
		return {seg:CheckNumber,result:(result),preSeg:"1J54OOU3G0",outlet:"1J54ORN603"};
	};
	ReadFeeds.jaxId="1J54OOU3G0"
	ReadFeeds.url="ReadFeeds@"+agentURL
	
	segs["ClosePage"]=ClosePage=async function(input){//:1J59QBN5H0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		/*#{1J59QBN5H0PreCodes*/
		page = globalContext.aaPage;
		/*}#1J59QBN5H0PreCodes*/
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		/*#{1J59QBN5H0PostCodes*/
		result={"result":"Finish",finds:context.finds,type:"Card"};
		/*}#1J59QBN5H0PostCodes*/
		return {result:result};
	};
	ClosePage.jaxId="1J59QBN5H0"
	ClosePage.url="ClosePage@"+agentURL
	
	segs["CheckNumber"]=CheckNumber=async function(input){//:1J5CHAOQV0
		let result=input;
		/*#{1J5CHAOQV0Start*/
		/*}#1J5CHAOQV0Start*/
		if(readRounds===0 && context.finds.length<context.searchNum && readRounds<10){
			/*#{1J5CHFHAM0Codes*/
			/*}#1J5CHFHAM0Codes*/
			return {seg:ShowPage,result:(input),preSeg:"1J5CHAOQV0",outlet:"1J5CHFHAM0"};
		}
		if(context.finds.length<context.searchNum && readRounds<10){
			return {seg:ScrollDown,result:(input),preSeg:"1J5CHAOQV0",outlet:"1J5CHINJB0"};
		}
		/*#{1J5CHAOQV0Post*/
		/*}#1J5CHAOQV0Post*/
		return {seg:CheckRounds,result:(result),preSeg:"1J5CHAOQV0",outlet:"1J5CHFHAM1"};
	};
	CheckNumber.jaxId="1J5CHAOQV0"
	CheckNumber.url="CheckNumber@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1J5CHC3UR0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let $options={"focusBrowser":true};
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		/*#{1J5CHC3UR0PreCodes*/
		page = globalContext.aaPage;
		/*}#1J5CHC3UR0PreCodes*/
		await page.bringToFront($options);
		waitAfter && (await sleep(waitAfter))
		/*#{1J5CHC3UR0PostCodes*/
		/*}#1J5CHC3UR0PostCodes*/
		return {seg:ScrollDown,result:(result),preSeg:"1J5CHC3UR0",outlet:"1J5CHC3UR3"};
	};
	ShowPage.jaxId="1J5CHC3UR0"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["ScrollDown"]=ScrollDown=async function(input){//:1J5CHDJ8Q0
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
		$waitBefore && (await sleep($waitBefore));
		/*#{1J5CHDJ8Q0PreCodes*/
		page = globalContext.aaPage;
		/*}#1J5CHDJ8Q0PreCodes*/
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1J5CHDJ8Q0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			$pms=page.mouseWheel($query,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
		}else{
			$pms=page.mouseWheel(null,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
		}
		if($pms && (!$async)){await $pms;}$waitAfter && (await sleep($waitAfter))
		/*#{1J5CHDJ8Q0PostCodes*/
		result = input?.finds;
		/*}#1J5CHDJ8Q0PostCodes*/
		return {seg:ReadMore,result:(result),preSeg:"1J5CHDJ8Q0",outlet:"1J5CHDJ8Q3"};
	};
	ScrollDown.jaxId="1J5CHDJ8Q0"
	ScrollDown.url="ScrollDown@"+agentURL
	
	segs["ReadMore"]=ReadMore=async function(input){//:1J5CHEP7G0
		let result=input;
		/*#{1J5CHEP7G0PreCodes*/
		readRounds+=1;
		/*}#1J5CHEP7G0PreCodes*/
		return {seg:ReadFeeds,result:result,preSeg:"1J54OOU3G0",outlet:"1J5CHFHAM2"};
	
	};
	ReadMore.jaxId="1J54OOU3G0"
	ReadMore.url="ReadMore@"+agentURL
	
	segs["CheckRounds"]=CheckRounds=async function(input){//:1J5CHOI260
		let result=input;
		if(readRounds===0){
			return {seg:TipResult,result:(input),preSeg:"1J5CHOI260",outlet:"1J5CHT3A40"};
		}
		return {seg:Back2App,result:(result),preSeg:"1J5CHOI260",outlet:"1J5CHT3A41"};
	};
	CheckRounds.jaxId="1J5CHOI260"
	CheckRounds.url="CheckRounds@"+agentURL
	
	segs["Back2App"]=Back2App=async function(input){//:1J5CHRGQ60
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		if(browser){
			await browser.backToApp();
		}
		waitAfter && (await sleep(waitAfter))
		return {seg:TipResult,result:(result),preSeg:"1J5CHRGQ60",outlet:"1J5CHT3A42"};
	};
	Back2App.jaxId="1J5CHRGQ60"
	Back2App.url="Back2App@"+agentURL
	
	segs["TipResult"]=TipResult=async function(input){//:1J5CIBOCU0
		let result=input;
		let $channel="Process";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1J5CIBOCU0PreCodes*/
		content=`共找到：${context.finds.length}条笔记。`;
		/*}#1J5CIBOCU0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1J5CIBOCU0PostCodes*/
		/*}#1J5CIBOCU0PostCodes*/
		return {seg:ShowRes,result:(result),preSeg:"1J5CIBOCU0",outlet:"1J5CIC8CE0"};
	};
	TipResult.jaxId="1J5CIBOCU0"
	TipResult.url="TipResult@"+agentURL
	
	segs["ShowRes"]=ShowRes=async function(input){//:1JAVBDOV00
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JAVBDOV00PreCodes*/
		const markdown = [
			context.finds.map((d,i)=>`${i+1}. [${d.title}](${d.url})`).join('\n')
		].filter(line => line !== '').join('\n');
		content = markdown;
		/*}#1JAVBDOV00PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JAVBDOV00PostCodes*/
		/*}#1JAVBDOV00PostCodes*/
		return {seg:ClosePage,result:(result),preSeg:"1JAVBDOV00",outlet:"1JAVBFRTE0"};
	};
	ShowRes.jaxId="1JAVBDOV00"
	ShowRes.url="ShowRes@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"rednoteSearch",
		url:agentURL,
		autoStart:true,
		jaxId:"1J54NE9UK0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1J54NE9UK0PreEntry*/
			/*}#1J54NE9UK0PreEntry*/
			result={seg:ClickSearch,"input":input};
			/*#{1J54NE9UK0PostEntry*/
			/*}#1J54NE9UK0PostEntry*/
			return result;
		},
		/*#{1J54NE9UK0MoreAgentAttrs*/
		/*}#1J54NE9UK0MoreAgentAttrs*/
	};
	/*#{1J54NE9UK0PostAgent*/
	/*}#1J54NE9UK0PostAgent*/
	return agent;
};
/*#{1J54NE9UK0ExCodes*/
/*}#1J54NE9UK0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "rednoteSearch",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	agentNode: "GlobalSearch",
	agentName: "rednoteSearch.js",
	label: "{\"CN\":\"小红书搜索\",\"EN\":\"RedNote Search\"}",
	isChatApi: true,
	capabilities: ["search"],
	meta: {"source":"www.xiaohongshu.com","icon":"/@GlobalSearch/assets/rednote.svg"},
	icon: "/@GlobalSearch/assets/rednote.svg"
}];
//#CodyExport<<<
/*#{1J54NE9UK0PostDoc*/
/*}#1J54NE9UK0PostDoc*/


export default rednoteSearch;
export{rednoteSearch,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1J54NE9UK0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1J54NE9UL0",
//			"attrs": {
//				"rednote_search": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1J54NE9UL6",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1J54NE9UM0",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1J54NE9UM1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1J54NE9UM2",
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
//			"jaxId": "1J54NE9UL1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "ClickSearch",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1J54NE9UL2",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1J54NE9UL3",
//			"attrs": {
//				"readRounds": {
//					"type": "number",
//					"valText": "0"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1J54NE9UL4",
//			"attrs": {
//				"finds": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J5CGQ58M0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"urlMap": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J5CGR3P60",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "#new Map()",
//						"desc": ""
//					}
//				},
//				"search": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JAVAA0MT0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"searchNum": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JAVAA0MT1",
//					"attrs": {
//						"type": "Number",
//						"mockup": "20",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1J54NE9UL5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1J54O73FH0",
//					"attrs": {
//						"id": "ClickSearch",
//						"viewName": "",
//						"label": "",
//						"x": "50",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J54ORN630",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J54ORN631",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "(//input[@id=\"search-input\"])",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"deltaX": "0",
//						"deltaY": "100",
//						"async": "false",
//						"options": "null",
//						"waitBefore": "0",
//						"waitAfter": "300",
//						"outlet": {
//							"jaxId": "1J54ORN5V0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J54ONSTI0"
//						},
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1J54OM67N0",
//					"attrs": {
//						"id": "TypeSearch",
//						"viewName": "",
//						"label": "",
//						"x": "560",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J54ORN632",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J54ORN633",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Type",
//						"query": "",
//						"queryHint": "",
//						"key": "#context.search",
//						"async": "false",
//						"options": "{\"delay\":50,\"coverEnter\":0,\"postEnter\":true}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J54ORN5V1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J54OOCK20"
//						},
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1J54ONSTI0",
//					"attrs": {
//						"id": "FlagNavi",
//						"viewName": "",
//						"label": "",
//						"x": "310",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J54ORN636",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J54ORN637",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Navigate",
//						"flag": "$WaitFlag",
//						"query": "",
//						"queryHint": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J54ORN600",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J54OM67N0"
//						}
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1J54OOCK20",
//					"attrs": {
//						"id": "WaitNavi",
//						"viewName": "",
//						"label": "",
//						"x": "810",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J54ORN638",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J54ORN639",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "2000",
//						"outlet": {
//							"jaxId": "1J54ORN602",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J54OOU3G0"
//						},
//						"catchlet": {
//							"jaxId": "1J54ORN601",
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
//					"jaxId": "1J54OOU3G0",
//					"attrs": {
//						"id": "ReadFeeds",
//						"viewName": "",
//						"label": "",
//						"x": "1035",
//						"y": "155",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J54ORN6310",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J54ORN6311",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J54ORN603",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J5CHAOQV0"
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
//					"def": "WebRpaClosePage",
//					"jaxId": "1J59QBN5H0",
//					"attrs": {
//						"id": "ClosePage",
//						"viewName": "",
//						"label": "",
//						"x": "2405",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J59QC54E2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J59QC54E3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J59QC5491",
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
//					"def": "brunch",
//					"jaxId": "1J5CHAOQV0",
//					"attrs": {
//						"id": "CheckNumber",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "155",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J5CHFHAS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J5CHFHAS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J5CHFHAM1",
//							"attrs": {
//								"id": "Done",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J5CHOI260"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J5CHFHAM0",
//									"attrs": {
//										"id": "ShowPage",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1J5CHFHAS2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J5CHFHAS3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#readRounds===0 && context.finds.length<context.searchNum && readRounds<10"
//									},
//									"linkedSeg": "1J5CHC3UR0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J5CHINJB0",
//									"attrs": {
//										"id": "More",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J5CHMBOC0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J5CHMBOC1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#context.finds.length<context.searchNum && readRounds<10"
//									},
//									"linkedSeg": "1J5CHDJ8Q0"
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
//					"jaxId": "1J5CHC3UR0",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "1525",
//						"y": "125",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J5CHC3UR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J5CHC3UR2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J5CHC3UR3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J5CHDJ8Q0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1J5CHDJ8Q0",
//					"attrs": {
//						"id": "ScrollDown",
//						"viewName": "",
//						"label": "",
//						"x": "1765",
//						"y": "155",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J5CHDJ8Q1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J5CHDJ8Q2",
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
//							"jaxId": "1J5CHDJ8Q3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J5CHEP7G0"
//						},
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1J5CHEP7G0",
//					"attrs": {
//						"id": "ReadMore",
//						"viewName": "",
//						"label": "",
//						"x": "1995",
//						"y": "155",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1J54OOU3G0",
//						"outlet": {
//							"jaxId": "1J5CHFHAM2",
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
//					"def": "brunch",
//					"jaxId": "1J5CHOI260",
//					"attrs": {
//						"id": "CheckRounds",
//						"viewName": "",
//						"label": "",
//						"x": "1530",
//						"y": "230",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J5CHT3AB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J5CHT3AB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J5CHT3A41",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J5CHRGQ60"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J5CHT3A40",
//									"attrs": {
//										"id": "Zero",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J5CHT3AB2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J5CHT3AB3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#readRounds===0"
//									},
//									"linkedSeg": "1J5CIBOCU0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1J5CHRGQ60",
//					"attrs": {
//						"id": "Back2App",
//						"viewName": "",
//						"label": "",
//						"x": "1765",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J5CHT3AB4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J5CHT3AB5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J5CHT3A42",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J5CIBOCU0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J5CIBOCU0",
//					"attrs": {
//						"id": "TipResult",
//						"viewName": "",
//						"label": "",
//						"x": "1995",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J5CIC8CJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J5CIC8CJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Process",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1J5CIC8CE0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAVBDOV00"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JAVBDOV00",
//					"attrs": {
//						"id": "ShowRes",
//						"viewName": "",
//						"label": "",
//						"x": "2210",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAVBH52B0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAVBH52B1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JAVBFRTE0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J59QBN5H0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"{\\\"CN\\\":\\\"小红书搜索\\\",\\\"EN\\\":\\\"RedNote Search\\\"}\",\"path\":\"\",\"pathInHub\":\"GlobalSearch\",\"chatEntry\":false,\"isChatApi\":0,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"/@GlobalSearch/assets/rednote.svg\",\"catalog\":\"AI Call\",\"capabilities\":[\"search\"],\"meta\":{\"source\":\"www.xiaohongshu.com\",\"icon\":\"/@GlobalSearch/assets/rednote.svg\"}}"
//	}
//}