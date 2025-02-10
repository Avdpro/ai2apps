//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1HDBOSUN90MoreImports*/
import{appCfg} from "../cfg/appCfg.js";
import {RemoteSession} from "/@aichat/remotesession.js";
/*}#1HDBOSUN90MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"prjURL":{
			"name":"prjURL","type":"string",
			"defaultValue":"",
			"desc":"项目的GitHub地址",
		},
		"dirPath":{
			"name":"dirPath","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"当前项目工程所在的本地目录路径",
		}
	},
	/*#{1HDBOSUN90ArgsView*/
	/*}#1HDBOSUN90ArgsView*/
};

/*#{1HDBOSUN90StartDoc*/
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
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let agent=async function(session){
	let prjURL,dirPath;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let CallBuilder,SEG1IH77BG110;
	/*#{1HDBOSUN90LocalVals*/
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			prjURL=input.prjURL;
			dirPath=input.dirPath;
		}else{
			prjURL=undefined;
			dirPath=undefined;
		}
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
	/*}#1HDBOSUN90PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let agent,segs={};
	segs["CallBuilder"]=CallBuilder=async function(input){//:1IGTUQTDL0
		let result=input
		/*#{1IGTUQTDL0Code*/
		session.WSCall_CreateXTerm=createXTerm;
		//result=await RemoteSession.exec(session,"AgentBuilder","PrjSetupPrj.js",{prjURL:prjURL,dirPath:dirPath},{checkUpdate:true});
		result=await RemoteSession.exec(session,"AgentBuilder","TestHandleIssue.js",{},{checkUpdate:true});
		/*}#1IGTUQTDL0Code*/
		return {result:result};
	};
	CallBuilder.jaxId="1IGTUQTDL0"
	CallBuilder.url="CallBuilder@"+agentURL
	
	segs["SEG1IH77BG110"]=SEG1IH77BG110=async function(input){//:1IH77BG110
		let result=input;
		let missing=false;
		if(prjURL===undefined || prjURL==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@aichat/ai/CompleteArgs.js",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:CallBuilder,result:(result),preSeg:"1IH77BG110",outlet:"1IH77BREJ0"};
	};
	SEG1IH77BG110.jaxId="1IH77BG110"
	SEG1IH77BG110.url="SEG1IH77BG110@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"agent",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{prjURL,dirPath}*/){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN90PreEntry*/
			/*}#1HDBOSUN90PreEntry*/
			result={seg:SEG1IH77BG110,"input":input};
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
//		"entry": " FixArgs",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IG0KG6PO0",
//			"attrs": {
//				"prjURL": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IGT6HB8K0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "项目的GitHub地址"
//					}
//				},
//				"dirPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IGT6HB8K1",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "当前项目工程所在的本地目录路径",
//						"required": "false"
//					}
//				}
//			}
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
//					"def": "code",
//					"jaxId": "1IGTUQTDL0",
//					"attrs": {
//						"id": "CallBuilder",
//						"viewName": "",
//						"label": "",
//						"x": "275",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGTURQNJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGTURQNJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGTURQND0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IH77BG110",
//					"attrs": {
//						"id": " FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "85",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IH77BREJ0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGTUQTDL0"
//						}
//					},
//					"icon": "args.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}