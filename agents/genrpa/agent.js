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
const VFACT=null;
/*#{1HDBOSUN90StartDoc*/
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let agent=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,OpenBrowser,OpenPage,Notify;
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
	let agent,segs={};
	segs["Start"]=Start=async function(input){//:1IH28H5RP0
		let result=true;
		let aiQuery=true;
		try{
			context.webRpa=new WebRpa(session);
			aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1IH28H5RP0"));
		}catch(err){
			throw err;
		}
		return {seg:OpenBrowser,result:(result),preSeg:"1IH28H5RP0",outlet:"1IH28I25B0"};
	};
	Start.jaxId="1IH28H5RP0"
	Start.url="Start@"+agentURL
	
	segs["OpenBrowser"]=OpenBrowser=async function(input){//:1IH28HPRB0
		let result=true;
		let browser=null;
		let headless=false;
		let devtools=false;
		let dataDir=false;
		let alias="RPAHOME";
		context.rpaBrowser=browser=await context.webRpa.openBrowser(alias,{headless,devtools,autoDataDir:dataDir});
		context.rpaHostPage=browser.hostPage;
		return {seg:OpenPage,result:(result),preSeg:"1IH28HPRB0",outlet:"1IH28I25B1"};
	};
	OpenBrowser.jaxId="1IH28HPRB0"
	OpenBrowser.url="OpenBrowser@"+agentURL
	
	segs["OpenPage"]=OpenPage=async function(input){//:1IH28P38Q0
		let pageVal="rpaPage";
		let $url="https://www.google.com";
		let $waitBefore=0;
		let $waitAfter=0;
		let $width=800;
		let $height=600;
		let $userAgent="";
		let page=null;
		$waitBefore && (await sleep($waitBefore));
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url);
		$waitAfter && (await sleep($waitAfter));
		return {seg:Notify,result:(page),preSeg:"1IH28P38Q0",outlet:"1IH28P9TV0"};
	};
	OpenPage.jaxId="1IH28P38Q0"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["Notify"]=Notify=async function(input){//:1IH28Q6DB0
		let result=input;
		let opts={};
		let role="assistant";
		let content="Page opened.";
		session.addChatText(role,content,opts);
		return {result:result};
	};
	Notify.jaxId="1IH28Q6DB0"
	Notify.url="Notify@"+agentURL
	
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
//						"exportType": "UI Data Template",
//						"exportClass": "false"
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
//					"def": "WebRpaStart",
//					"jaxId": "1IH28H5RP0",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "95",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH28I25C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH28I25C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH28I25B0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH28HPRB0"
//						},
//						"catchlet": {
//							"jaxId": "1IH28I25C2",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1IH28I25C3",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1IH28I25C4",
//									"attrs": {
//										"cast": ""
//									}
//								}
//							}
//						},
//						"aiQuery": "true"
//					},
//					"icon": "start.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenBrowser",
//					"jaxId": "1IH28HPRB0",
//					"attrs": {
//						"id": "OpenBrowser",
//						"viewName": "",
//						"label": "",
//						"x": "300",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH28I25C5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH28I25C6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"alias": "RPAHOME",
//						"headless": "false",
//						"devtools": "false",
//						"dataDir": "false",
//						"outlet": {
//							"jaxId": "1IH28I25B1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH28P38Q0"
//						},
//						"run": ""
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1IH28P38Q0",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "535",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
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
//						"valName": "rpaPage",
//						"url": "https://www.google.com",
//						"vpWidth": "800",
//						"vpHeight": "600",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1IH28P9TV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH28Q6DB0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IH28Q6DB0",
//					"attrs": {
//						"id": "Notify",
//						"viewName": "",
//						"label": "",
//						"x": "760",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH28R1BC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH28R1BC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "Page opened.",
//						"outlet": {
//							"jaxId": "1IH28R1BB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
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