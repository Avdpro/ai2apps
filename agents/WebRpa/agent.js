//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1HDBOSUN90MoreImports*/
/*}#1HDBOSUN90MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
/*#{1HDBOSUN90StartDoc*/
let sharedPage=null;
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let agent=async function(session){
	let execInput;
	const $ln=session.language||"EN";let context,globalContext;
	let self;
	let Start,OpenBrwoser,OpenPage,ClickINput,TypeSearch,SharedPage,GotoURL,DoSearch,FlagNavi,WaitNavi,ReadHTML,Output;
	/*#{1HDBOSUN90LocalVals*/
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
	/*}#1HDBOSUN90PreContext*/
	globalContext=session.globalContext;
	context={};
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let agent,segs={};
	segs["Start"]=Start=async function(input){//:1IE2AKSVF0
		let result=true;
		let aiQuery=true;
		try{
			context.webRpa=new WebRpa(session);
			aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1IE2AKSVF0"));
		}catch(err){
			throw err;
		}
		return {seg:OpenBrwoser,result:(result),preSeg:"1IE2AKSVF0",outlet:"1IE2AQ6JS0"};
	};
	Start.jaxId="1IE2AKSVF0"
	Start.url="Start@"+agentURL
	
	segs["OpenBrwoser"]=OpenBrwoser=async function(input){//:1IE2AM2ET0
		let result=true;
		let browser=null;
		let headless=false;
		let devtools=false;
		let dataDir=true;
		let alias="AARPA";
		context.rpaBrowser=browser=await context.webRpa.openBrowser(alias,{headless,devtools,autoDataDir:dataDir});
		context.rpaHostPage=browser.hostPage;
		return {seg:SharedPage,result:(result),preSeg:"1IE2AM2ET0",outlet:"1IE2AQ6JT0"};
	};
	OpenBrwoser.jaxId="1IE2AM2ET0"
	OpenBrwoser.url="OpenBrwoser@"+agentURL
	
	segs["OpenPage"]=OpenPage=async function(input){//:1IE2AN45C0
		let pageVal="aaPage";
		let $url="https://www.google.com";
		let $waitBefore=0;
		let $waitAfter=0;
		let $width=800;
		let $height=600;
		let $userAgent="";
		let page=null;
		$waitBefore && (await sleep($waitBefore));
		/*#{1IE2AN45C0PreCodes*/
		/*}#1IE2AN45C0PreCodes*/
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url);
		$waitAfter && (await sleep($waitAfter));
		/*#{1IE2AN45C0PostCodes*/
		sharedPage=page;
		/*}#1IE2AN45C0PostCodes*/
		return {seg:ClickINput,result:(page),preSeg:"1IE2AN45C0",outlet:"1IE2AQ6JT1"};
	};
	OpenPage.jaxId="1IE2AN45C0"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["ClickINput"]=ClickINput=async function(input){//:1IE7RH1T10
		let result=true;
		let pageVal="aaPage";
		let $query="(//TEXTAREA)";
		let $queryHint="搜索输入框";
		let $x=0;
		let $y=0;
		let $options=undefined;
		let $waitBefore=2000;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1IE7RH1T10")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			await page.click("::-p-xpath"+$query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
		}else{
			await page.mouse.click($x,$y,$options||{});
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:TypeSearch,result:(result),preSeg:"1IE7RH1T10",outlet:"1IE7RKL9E0"};
	};
	ClickINput.jaxId="1IE7RH1T10"
	ClickINput.url="ClickINput@"+agentURL
	
	segs["TypeSearch"]=TypeSearch=async function(input){//:1IE7RJKSH0
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="";
		let $queryHint="";
		let $key="ai2apps";
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1IE7RJKSH0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			await page.type("::-p-xpath"+$query,$key,$options||{});
		}else{
			await page.keyboard.type($key,$options||{});
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:FlagNavi,result:(result),preSeg:"1IE7RJKSH0",outlet:"1IE7RKL9F0"};
	};
	TypeSearch.jaxId="1IE7RJKSH0"
	TypeSearch.url="TypeSearch@"+agentURL
	
	segs["SharedPage"]=SharedPage=async function(input){//:1IE81G5DF0
		let result=input;
		if(sharedPage && (!sharedPage.isClosed())){
			/*#{1IE81IJBV0Codes*/
			context.aaPage=sharedPage;
			/*}#1IE81IJBV0Codes*/
			return {seg:GotoURL,result:(input),preSeg:"1IE81G5DF0",outlet:"1IE81IJBV0"};
		}
		return {seg:OpenPage,result:(result),preSeg:"1IE81G5DF0",outlet:"1IE81IJBV1"};
	};
	SharedPage.jaxId="1IE81G5DF0"
	SharedPage.url="SharedPage@"+agentURL
	
	segs["GotoURL"]=GotoURL=async function(input){//:1IE81OO2Q0
		let result=true;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let url="https://www.google.com";
		let page=context[pageVal];
		let opts={};
		waitBefore && (await sleep(waitBefore));
		await page.goto(url,opts);
		waitAfter && (await sleep(waitAfter))
		return {seg:ClickINput,result:(result),preSeg:"1IE81OO2Q0",outlet:"1IE81QBFV0"};
	};
	GotoURL.jaxId="1IE81OO2Q0"
	GotoURL.url="GotoURL@"+agentURL
	
	segs["DoSearch"]=DoSearch=async function(input){//:1IE822EJB0
		let result=true;
		let pageVal="aaPage";
		let $action="KeyPress";
		let $query="";
		let $queryHint="";
		let $key="Enter";
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		await page.keyboard.press($key,$options||{});
		$waitAfter && (await sleep($waitAfter))
		return {seg:WaitNavi,result:(result),preSeg:"1IE822EJB0",outlet:"1IE826A6H0"};
	};
	DoSearch.jaxId="1IE822EJB0"
	DoSearch.url="DoSearch@"+agentURL
	
	segs["FlagNavi"]=FlagNavi=async function(input){//:1IE823ELI0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $query="";
		let $queryHint="";
		let $waitBefore=0;
		let $waitAfter=0;
		let $options={};
		let page=context[pageVal];
		let $args=[];
		$waitBefore && (await sleep($waitBefore));
		context[$flag]=page.waitForNavigation($options);
		$waitAfter && (await sleep($waitAfter))
		return {seg:DoSearch,result:(result),preSeg:"1IE823ELI0",outlet:"1IE826A6H1"};
	};
	FlagNavi.jaxId="1IE823ELI0"
	FlagNavi.url="FlagNavi@"+agentURL
	
	segs["WaitNavi"]=WaitNavi=async function(input){//:1IE824KA10
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		await context[$flag];
		$waitAfter && (await sleep($waitAfter))
		return {seg:ReadHTML,result:(result),preSeg:"1IE824KA10",outlet:"1IE826A6H2"};
	};
	WaitNavi.jaxId="1IE824KA10"
	WaitNavi.url="WaitNavi@"+agentURL
	
	segs["ReadHTML"]=ReadHTML=async function(input){//:1IE82590O0
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=undefined;
		let $waitBefore=1000;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:true,...$options});
		$waitAfter && (await sleep($waitAfter))
		return {seg:Output,result:(result),preSeg:"1IE82590O0",outlet:"1IE826A6H3"};
	};
	ReadHTML.jaxId="1IE82590O0"
	ReadHTML.url="ReadHTML@"+agentURL
	
	segs["Output"]=Output=async function(input){//:1IE825S5P0
		let result=input;
		let role="assistant";
		let content=input;
		session.addChatText(role,content);
		return {result:result};
	};
	Output.jaxId="1IE825S5P0"
	Output.url="Output@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"agent",
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
			result={seg:Start,"input":input};
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


export default agent;
export{agent};
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
//						"superClass": "",
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
//						"exportType": "UI Data Template"
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1HDBOSUNA1",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IE2AQPU60",
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
//					"def": "WebRpaStart",
//					"jaxId": "1IE2AKSVF0",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "75",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE2AQPU61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE2AQPU62",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IE2AQ6JS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE2AM2ET0"
//						},
//						"catchlet": {
//							"jaxId": "1IE2AQPU63",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1IE2AQPU64",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1IE2AQPU65",
//									"attrs": {
//										"cast": ""
//									}
//								}
//							}
//						},
//						"aiQuery": "true"
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenBrowser",
//					"jaxId": "1IE2AM2ET0",
//					"attrs": {
//						"id": "OpenBrwoser",
//						"viewName": "",
//						"label": "",
//						"x": "285",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE2AQPU66",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE2AQPU67",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"alias": "AARPA",
//						"headless": "false",
//						"devtools": "false",
//						"dataDir": "true",
//						"outlet": {
//							"jaxId": "1IE2AQ6JT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE81G5DF0"
//						},
//						"run": ""
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1IE2AN45C0",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "775",
//						"y": "220",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE2AQPU68",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE2AQPU69",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "https://www.google.com",
//						"vpWidth": "800",
//						"vpHeight": "600",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1IE2AQ6JT1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE7RH1T10"
//						},
//						"run": ""
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1IE7RH1T10",
//					"attrs": {
//						"id": "ClickINput",
//						"viewName": "",
//						"label": "",
//						"x": "1010",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE7RKL9H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE7RKL9H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "(//TEXTAREA)",
//						"queryHint": "搜索输入框",
//						"dx": "0",
//						"dy": "0",
//						"options": "",
//						"waitBefore": "2000",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1IE7RKL9E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE7RJKSH0"
//						},
//						"run": ""
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1IE7RJKSH0",
//					"attrs": {
//						"id": "TypeSearch",
//						"viewName": "",
//						"label": "",
//						"x": "1240",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE7RKL9H2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE7RKL9H3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Type",
//						"query": "",
//						"queryHint": "",
//						"key": "ai2apps",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1IE7RKL9F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE82225M0"
//						},
//						"run": ""
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IE81G5DF0",
//					"attrs": {
//						"id": "SharedPage",
//						"viewName": "",
//						"label": "",
//						"x": "535",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE81IJC30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE81IJC31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IE81IJBV1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IE2AN45C0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IE81IJBV0",
//									"attrs": {
//										"id": "Shared",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IE81IJC32",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IE81IJC33",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#sharedPage && (!sharedPage.isClosed())"
//									},
//									"linkedSeg": "1IE81OO2Q0"
//								}
//							]
//						}
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaPageGoto",
//					"jaxId": "1IE81OO2Q0",
//					"attrs": {
//						"id": "GotoURL",
//						"viewName": "",
//						"label": "",
//						"x": "775",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE81QBG40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE81QBG41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"url": "https://www.google.com",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1IE81QBFV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE7RH1T10"
//						},
//						"run": ""
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IE82225M0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1390",
//						"y": "285",
//						"outlet": {
//							"jaxId": "1IE826A6L0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE8226D00"
//						},
//						"dir": "R2L"
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IE8226D00",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "200",
//						"y": "285",
//						"outlet": {
//							"jaxId": "1IE826A6L1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE823ELI0"
//						},
//						"dir": "R2L"
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1IE822EJB0",
//					"attrs": {
//						"id": "DoSearch",
//						"viewName": "",
//						"label": "",
//						"x": "385",
//						"y": "375",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE826A6L2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE826A6L3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Key Press",
//						"query": "",
//						"queryHint": "",
//						"key": "Enter",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1IE826A6H0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE824KA10"
//						},
//						"run": ""
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1IE823ELI0",
//					"attrs": {
//						"id": "FlagNavi",
//						"viewName": "",
//						"label": "",
//						"x": "175",
//						"y": "375",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE826A6L4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE826A6L5",
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
//							"jaxId": "1IE826A6H1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE822EJB0"
//						}
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1IE824KA10",
//					"attrs": {
//						"id": "WaitNavi",
//						"viewName": "",
//						"label": "",
//						"x": "605",
//						"y": "375",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE826A6L6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE826A6L7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1IE826A6H2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE82590O0"
//						}
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1IE82590O0",
//					"attrs": {
//						"id": "ReadHTML",
//						"viewName": "",
//						"label": "",
//						"x": "820",
//						"y": "375",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE826A6L8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE826A6L9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"target": "CleanHTML",
//						"node": "null",
//						"options": "",
//						"waitBefore": "1000",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1IE826A6H3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IE825S5P0"
//						},
//						"run": ""
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IE825S5P0",
//					"attrs": {
//						"id": "Output",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "375",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IE826A6L10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IE826A6L11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IE826A6H4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					}
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}