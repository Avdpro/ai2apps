//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JDTDIACF0MoreImports*/
/*}#1JDTDIACF0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"url":{
			"name":"url","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"profile":{
			"name":"profile","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"headless":{
			"name":"headless","type":"bool",
			"defaultValue":false,
			"desc":"",
		},
		"waitAfter":{
			"name":"waitAfter","type":"integer",
			"defaultValue":"",
			"desc":"",
		},
		"open":{
			"name":"open","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JDTDIACF0ArgsView*/
	/*}#1JDTDIACF0ArgsView*/
};

/*#{1JDTDIACF0StartDoc*/
/*}#1JDTDIACF0StartDoc*/
//----------------------------------------------------------------------------
let CaRpa_OpenBrowser=async function(session){
	let url,profile,headless,waitAfter,open;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,Finish,Failed,CheckFocus,CheckFocusBack,FocusPage,FocusBack,WaitAfter;
	/*#{1JDTDIACF0LocalVals*/
	/*}#1JDTDIACF0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			url=input.url;
			profile=input.profile;
			headless=input.headless;
			waitAfter=input.waitAfter;
			open=input.open;
		}else{
			url=undefined;
			profile=undefined;
			headless=undefined;
			waitAfter=undefined;
			open=undefined;
		}
		/*#{1JDTDIACF0ParseArgs*/
		/*}#1JDTDIACF0ParseArgs*/
	}
	
	/*#{1JDTDIACF0PreContext*/
	/*}#1JDTDIACF0PreContext*/
	context={};
	/*#{1JDTDIACF0PostContext*/
	/*}#1JDTDIACF0PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JDTDK5BH0
		let result=true;
		let aiQuery=true;
		let $alias=profile||"RPAHOME";
		let $url=url;
		let $ref=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let $webRpa=null;
		try{
			if($ref){
				let $page,$browser;
				let $pageVal="aaPage";
				$page=WebRpa.getPageByRef($ref);
				context.rpaBrowser=$browser=$page.webDrive;
				context.webRpa=$webRpa=$browser.aaWebRpa;
				Object.defineProperty(context, $pageVal, {enumerable:true,get(){return $webRpa.currentPage},set(v){$webRpa.setCurrentPage(v)}});
				context[$pageVal]=$page;
			}else{
				let $pageVal="aaPage";
				context.webRpa=$webRpa=session.webRpa || new WebRpa(session);
				session.webRpa=$webRpa;
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JDTDK5BH0"));
				if($alias){
					let $headless=headless||false;
					let $devtools=false;
					let options={$headless:false,$devtools:false,autoDataDir:false};
					let $browser=null;
					context.rpaBrowser=$browser=await context.webRpa.openBrowser($alias,options);
					context.rpaHostPage=$browser.hostPage;
					Object.defineProperty(context, $pageVal, {enumerable:true,get(){return $webRpa.currentPage},set(v){$webRpa.setCurrentPage(v)}});
					if($url){
						let $page=null;
						let $opts={};
						context[$pageVal]=$page=await $browser.newPage();
						await $page.goto($url,{});
					}
				}
			}
			$waitAfter && (await sleep($waitAfter));
		}catch(error){
			return {seg:Failed,result:(error),preSeg:"1JDTDK5BH0",outlet:"1JDTDKT742",catchSeg:Failed,catchlet:"1JDTDKT742"};
		}
		return {seg:CheckFocus,result:(result),preSeg:"1JDTDK5BH0",outlet:"1JDTDKT730"};
	};
	StartRpa.jaxId="1JDTDK5BH0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1JDTDSC5Q0
		let result=input
		try{
			/*#{1JDTDSC5Q0Code*/
			result={status:"Done",result:"Finish",pageRef:context.aaPage.pageRef};
			/*}#1JDTDSC5Q0Code*/
		}catch(error){
			/*#{1JDTDSC5Q0ErrorCode*/
			/*}#1JDTDSC5Q0ErrorCode*/
		}
		return {seg:WaitAfter,result:(result),preSeg:"1JDTDSC5Q0",outlet:"1JDTDSQ0I0"};
	};
	Finish.jaxId="1JDTDSC5Q0"
	Finish.url="Finish@"+agentURL
	
	segs["Failed"]=Failed=async function(input){//:1JDTDSJ1T0
		let result=input
		try{
			/*#{1JDTDSJ1T0Code*/
			result={status:"Failed",result:"Failed",reason:""+input};
			/*}#1JDTDSJ1T0Code*/
		}catch(error){
			/*#{1JDTDSJ1T0ErrorCode*/
			/*}#1JDTDSJ1T0ErrorCode*/
		}
		return {result:result};
	};
	Failed.jaxId="1JDTDSJ1T0"
	Failed.url="Failed@"+agentURL
	
	segs["CheckFocus"]=CheckFocus=async function(input){//:1JDVNDU730
		let result=input;
		if((!open) ||(open.focus!==false)){
			return {seg:FocusPage,result:(input),preSeg:"1JDVNDU730",outlet:"1JDVNKETG0"};
		}
		return {seg:Finish,result:(result),preSeg:"1JDVNDU730",outlet:"1JDVNKETG1"};
	};
	CheckFocus.jaxId="1JDVNDU730"
	CheckFocus.url="CheckFocus@"+agentURL
	
	segs["CheckFocusBack"]=CheckFocusBack=async function(input){//:1JDVNFS090
		let result=input;
		if((!open) ||(open.focusBack!==false)){
			return {seg:FocusBack,result:(input),preSeg:"1JDVNFS090",outlet:"1JDVNKETG2"};
		}
		return {seg:Finish,result:(result),preSeg:"1JDVNFS090",outlet:"1JDVNKETH0"};
	};
	CheckFocusBack.jaxId="1JDVNFS090"
	CheckFocusBack.url="CheckFocusBack@"+agentURL
	
	segs["FocusPage"]=FocusPage=async function(input){//:1JDVNG6RU0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=1000;
		let $options={"focusBrowser":true,"switchBack":0};
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
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
			/*#{1JDVNG6RU0ErrorCode*/
			/*}#1JDVNG6RU0ErrorCode*/
		}
		return {seg:CheckFocusBack,result:(result),preSeg:"1JDVNG6RU0",outlet:"1JDVNKETH1"};
	};
	FocusPage.jaxId="1JDVNG6RU0"
	FocusPage.url="FocusPage@"+agentURL
	
	segs["FocusBack"]=FocusBack=async function(input){//:1JDVNIAC20
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JDVNIAC20ErrorCode*/
			/*}#1JDVNIAC20ErrorCode*/
		}
		return {seg:Finish,result:(result),preSeg:"1JDVNIAC20",outlet:"1JDVNKETH2"};
	};
	FocusBack.jaxId="1JDVNIAC20"
	FocusBack.url="FocusBack@"+agentURL
	
	segs["WaitAfter"]=WaitAfter=async function(input){//:1JE441R2T0
		let result=true;
		let pageVal="aaPage";
		let $flag="";
		let $waitBefore=0;
		let $waitAfter=waitAfter||0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			result=$flag?(await context[$flag]):input;
		}catch(error){
			return {result:error};
		}
		$waitAfter && (await sleep($waitAfter))
		return {result:result};
	};
	WaitAfter.jaxId="1JE441R2T0"
	WaitAfter.url="WaitAfter@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CaRpa_OpenBrowser",
		url:agentURL,
		autoStart:true,
		jaxId:"1JDTDIACF0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{url,profile,headless,waitAfter,open}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JDTDIACF0PreEntry*/
			/*}#1JDTDIACF0PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JDTDIACF0PostEntry*/
			/*}#1JDTDIACF0PostEntry*/
			return result;
		},
		/*#{1JDTDIACF0MoreAgentAttrs*/
		/*}#1JDTDIACF0MoreAgentAttrs*/
	};
	/*#{1JDTDIACF0PostAgent*/
	/*}#1JDTDIACF0PostAgent*/
	return agent;
};
/*#{1JDTDIACF0ExCodes*/
/*}#1JDTDIACF0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CaRpa_OpenBrowser",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				url:{type:"auto",description:""},
				profile:{type:"auto",description:""},
				headless:{type:"bool",description:""},
				waitAfter:{type:"integer",description:""},
				open:{type:"auto",description:""}
			}
		}
	},
	agentNode: "genrpa",
	agentName: "CaRpa_OpenBrowser.js",
	isChatApi: true,
	kind: "rpa",
	capabilities: ["open","url","profile","waitAfter"],
	filters: [],
	metrics: {"quality":"","costPerCall":"","costPer1M":"","speed":"","size":""}
}];
//#CodyExport<<<
/*#{1JDTDIACF0PostDoc*/
/*}#1JDTDIACF0PostDoc*/


export default CaRpa_OpenBrowser;
export{CaRpa_OpenBrowser,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JDTDIACF0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JDTDIACF1",
//			"attrs": {
//				"CaRpa_OpenBrowser": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JDTDIACG0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JDTDIACG1",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JDTDIACG2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JDTDIACG3",
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
//			"jaxId": "1JDTDIACF2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JDTDIACF3",
//			"attrs": {
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDTDJQ9M1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"profile": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDTDJQ9M0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"headless": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDTDMJB50",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "false",
//						"desc": ""
//					}
//				},
//				"waitAfter": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDVJ457F0",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"open": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDVNKETJ0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JDTDIACF4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JDTDIACF5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JDTDIACF6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JDTDK5BH0",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "125",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDTDKT740",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDTDKT741",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"browser": "#profile||\"RPAHOME\"",
//						"headless": "#headless||false",
//						"devtools": "false",
//						"url": "#url",
//						"valName": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JDTDKT730",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDVNDU730"
//						},
//						"catchlet": {
//							"jaxId": "1JDTDKT742",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JDTDKT743",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JDTDKT744",
//									"attrs": {
//										"cast": ""
//									}
//								}
//							},
//							"linkedSeg": "1JDTDSJ1T0"
//						},
//						"aiQuery": "true",
//						"autoCurrentPage": "true"
//					},
//					"icon": "start.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JDTDSC5Q0",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "1365",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDTDSQ0M0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDTDSQ0M1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDTDSQ0I0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE441R2T0"
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
//					"def": "code",
//					"jaxId": "1JDTDSJ1T0",
//					"attrs": {
//						"id": "Failed",
//						"viewName": "",
//						"label": "",
//						"x": "350",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDTDSQ0M2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDTDSQ0M3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDTDSQ0I1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
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
//					"jaxId": "1JDVNDU730",
//					"attrs": {
//						"id": "CheckFocus",
//						"viewName": "",
//						"label": "",
//						"x": "350",
//						"y": "130",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDVNKETJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDVNKETJ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDVNKETG1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JDVNJLGH0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JDVNKETG0",
//									"attrs": {
//										"id": "Focus",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JDVNKETJ3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JDVNKETJ4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#(!open) ||(open.focus!==false)"
//									},
//									"linkedSeg": "1JDVNG6RU0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JDVNFS090",
//					"attrs": {
//						"id": "CheckFocusBack",
//						"viewName": "",
//						"label": "",
//						"x": "855",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDVNKETJ5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDVNKETJ6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDVNKETH0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JDVNJTB00"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JDVNKETG2",
//									"attrs": {
//										"id": "Back",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JDVNKETJ7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JDVNKETJ8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#(!open) ||(open.focusBack!==false)"
//									},
//									"linkedSeg": "1JDVNIAC20"
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
//					"jaxId": "1JDVNG6RU0",
//					"attrs": {
//						"id": "FocusPage",
//						"viewName": "",
//						"label": "",
//						"x": "615",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDVNKETJ9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDVNKETJ10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true,\"switchBack\":0}",
//						"waitBefore": "0",
//						"waitAfter": "1000",
//						"outlet": {
//							"jaxId": "1JDVNKETH1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDVNFS090"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JDVNIAC20",
//					"attrs": {
//						"id": "FocusBack",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDVNKETJ11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDVNKETJ12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JDVNKETH2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDTDSC5Q0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JDVNJLGH0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "610",
//						"y": "210",
//						"outlet": {
//							"jaxId": "1JDVNKETJ13",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDVNJTB00"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JDVNJTB00",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1135",
//						"y": "210",
//						"outlet": {
//							"jaxId": "1JDVNKETJ14",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDTDSC5Q0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JE441R2T0",
//					"attrs": {
//						"id": "WaitAfter",
//						"viewName": "",
//						"label": "",
//						"x": "1585",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE442A9I0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE442A9I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "",
//						"waitBefore": "0",
//						"waitAfter": "#waitAfter||0",
//						"outlet": {
//							"jaxId": "1JE442A9H1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"catchlet": {
//							"jaxId": "1JE442A9H0",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"genrpa\",\"chatEntry\":false,\"isChatApi\":1,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\",\"kind\":\"rpa\",\"capabilities\":[\"open\",\"url\",\"profile\",\"waitAfter\"],\"filters\":[],\"metrics\":{\"quality\":\"\",\"costPerCall\":\"\",\"costPer1M\":\"\",\"speed\":\"\",\"size\":\"\"},\"meta\":\"\"}"
//	}
//}