//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IIFF7BU70MoreImports*/
import {appCfg} from "../cfg/appCfg.js";
/*}#1IIFF7BU70MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1IIFF7BU70StartDoc*/
const xtermMeta={
	type:"app",
	name:"AgentTerminal",
	caption:"Agent Terminal",
	icon:appCfg.sharedAssets+"/terminal.svg",iconPad:12,
	appFrame:{
		main:pathLib.join(basePath,"../xterm.html"),
		group:"AgentTerminal",caption:(($ln==="CN")?("智能体终端"):("Agent Terminal")),
		openApp:true,
		width:640,height:380,
		icon:appCfg.sharedAssets+"/terminal.svg",iconPad:2,
		sizeable:false
	}
};
async function createXTerm(message){
	let app,appFrame,sessionId;
	sessionId=message.session||message.sessionId;
	app=VFACT.app;
	if(app.uiTerminal){
		app.uiTerminal.connectBash(sessionId);
	}else{
		appFrame=app.appFrame;
		if(app.openAppMeta){
			app.openAppMeta(xtermMeta,`session=${sessionId}`);
		}else{
			window.open(pathLib.join(basePath,"../xterm.html")+`?session=${sessionId}`);
		}
	}
};
/*}#1IIFF7BU70StartDoc*/
//----------------------------------------------------------------------------
let TestEntry=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ShowStart,CallTest,ShowEnd;
	/*#{1IIFF7BU70LocalVals*/
	session.WSCall_CreateXTerm=createXTerm;
	session.WSCall_BashNotify=async function(message){
		session.addChatText("system",message.info);
	}
	/*}#1IIFF7BU70LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IIFF7BU70ParseArgs*/
		/*}#1IIFF7BU70ParseArgs*/
	}
	
	/*#{1IIFF7BU70PreContext*/
	/*}#1IIFF7BU70PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IIFF7BU70PostContext*/
	/*}#1IIFF7BU70PostContext*/
	let agent,segs={};
	segs["ShowStart"]=ShowStart=async function(input){//:1IIFF9RTL0
		let result=input;
		let role="assistant";
		let content="Start test...";
		session.addChatText(role,content);
		return {seg:CallTest,result:(result),preSeg:"1IIFF9RTL0",outlet:"1IIFFB7BV0"};
	};
	ShowStart.jaxId="1IIFF9RTL0"
	ShowStart.url="ShowStart@"+agentURL
	
	segs["CallTest"]=CallTest=async function(input){//:1IIFFAJVA0
		let result,args={};
		args['nodeName']="AgentBuilder";
		args['callAgent']="TestGround.js";
		args['callArg']=undefined;
		args['checkUpdate']=true;
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {seg:ShowEnd,result:(result),preSeg:"1IIFFAJVA0",outlet:"1IIFFB7BV1"};
	};
	CallTest.jaxId="1IIFFAJVA0"
	CallTest.url="CallTest@"+agentURL
	
	segs["ShowEnd"]=ShowEnd=async function(input){//:1IIFFBP1R0
		let result=input;
		let role="assistant";
		let content="Test end.";
		session.addChatText(role,content);
		return {result:result};
	};
	ShowEnd.jaxId="1IIFFBP1R0"
	ShowEnd.url="ShowEnd@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"TestEntry",
		url:agentURL,
		autoStart:true,
		jaxId:"1IIFF7BU70",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IIFF7BU70PreEntry*/
			/*}#1IIFF7BU70PreEntry*/
			result={seg:ShowStart,"input":input};
			/*#{1IIFF7BU70PostEntry*/
			/*}#1IIFF7BU70PostEntry*/
			return result;
		},
		/*#{1IIFF7BU70MoreAgentAttrs*/
		/*}#1IIFF7BU70MoreAgentAttrs*/
	};
	/*#{1IIFF7BU70PostAgent*/
	/*}#1IIFF7BU70PostAgent*/
	return agent;
};
/*#{1IIFF7BU70ExCodes*/
/*}#1IIFF7BU70ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IIFF7BU70PostDoc*/
/*}#1IIFF7BU70PostDoc*/


export default TestEntry;
export{TestEntry};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IIFF7BU70",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IIFF7BU71",
//			"attrs": {
//				"TestEntry": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IIFF7BU77",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IIFF7BU78",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IIFF7BU79",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IIFF7BU710",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportClass": "false"
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1IIFF7BU72",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IIFF7BU73",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IIFF7BU74",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IIFF7BU75",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IIFF7BU76",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IIFF9RTL0",
//					"attrs": {
//						"id": "ShowStart",
//						"viewName": "",
//						"label": "",
//						"x": "115",
//						"y": "150",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIFFB7C10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIFFB7C11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "Start test...",
//						"outlet": {
//							"jaxId": "1IIFFB7BV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIFFAJVA0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1IIFFAJVA0",
//					"attrs": {
//						"id": "CallTest",
//						"viewName": "",
//						"label": "",
//						"x": "350",
//						"y": "150",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIFFB7C12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIFFB7C13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AgentBuilder",
//						"callAgent": "TestGround.js",
//						"callArg": "",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1IIFFB7BV1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIFFBP1R0"
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IIFFBP1R0",
//					"attrs": {
//						"id": "ShowEnd",
//						"viewName": "",
//						"label": "",
//						"x": "575",
//						"y": "150",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIFFC5V70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIFFC5V71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "Test end.",
//						"outlet": {
//							"jaxId": "1IIFFC5V40",
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
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}