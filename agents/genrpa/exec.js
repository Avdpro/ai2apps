//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IH29DAPT0MoreImports*/
import{appCfg} from "../cfg/appCfg.js";
import {RemoteSession} from "/@aichat/remotesession.js";
/*}#1IH29DAPT0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1IH29DAPT0StartDoc*/
/*}#1IH29DAPT0StartDoc*/
//----------------------------------------------------------------------------
let exec=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Exec,Start;
	let prjName=pathLib.basename(pathLib.join(basePath,"../"));
	
	/*#{1IH29DAPT0LocalVals*/
	/*}#1IH29DAPT0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IH29DAPT0ParseArgs*/
		/*}#1IH29DAPT0ParseArgs*/
	}
	
	/*#{1IH29DAPT0PreContext*/
	/*}#1IH29DAPT0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IH29DAPT0PostContext*/
	/*}#1IH29DAPT0PostContext*/
	let agent,segs={};
	segs["Exec"]=Exec=async function(input){//:1IH29T89N0
		let result=input
		/*#{1IH29T89N0Code*/
		result=await RemoteSession.exec(session,prjName,"agent.js",null,{checkUpdate:true});
		/*}#1IH29T89N0Code*/
		return {result:result};
	};
	Exec.jaxId="1IH29T89N0"
	Exec.url="Exec@"+agentURL
	
	segs["Start"]=Start=async function(input){//:1IH2BHEM00
		let result=input;
		let role="assistant";
		let content="Start Web-RPA...";
		session.addChatText(role,content);
		return {seg:Exec,result:(result),preSeg:"1IH2BHEM00",outlet:"1IH2BI4HR0"};
	};
	Start.jaxId="1IH2BHEM00"
	Start.url="Start@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"exec",
		url:agentURL,
		autoStart:true,
		jaxId:"1IH29DAPT0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IH29DAPT0PreEntry*/
			/*}#1IH29DAPT0PreEntry*/
			result={seg:Start,"input":input};
			/*#{1IH29DAPT0PostEntry*/
			/*}#1IH29DAPT0PostEntry*/
			return result;
		},
		/*#{1IH29DAPT0MoreAgentAttrs*/
		/*}#1IH29DAPT0MoreAgentAttrs*/
	};
	/*#{1IH29DAPT0PostAgent*/
	/*}#1IH29DAPT0PostAgent*/
	return agent;
};
/*#{1IH29DAPT0ExCodes*/
/*}#1IH29DAPT0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IH29DAPT0PostDoc*/
/*}#1IH29DAPT0PostDoc*/


export default exec;
export{exec};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IH29DAPT0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IH29DAPT1",
//			"attrs": {
//				"exec": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IH29DAPT7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IH29DAPU0",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IH29DAPU1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IH29DAPU2",
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
//			"jaxId": "1IH29DAPT2",
//			"attrs": {}
//		},
//		"entry": "Start",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH29DAPT3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IH29DAPT4",
//			"attrs": {
//				"prjName": {
//					"type": "string",
//					"valText": "#pathLib.basename(pathLib.join(basePath,\"../\"))"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IH29DAPT5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IH29DAPT6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH29T89N0",
//					"attrs": {
//						"id": "Exec",
//						"viewName": "",
//						"label": "",
//						"x": "270",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH29TG1C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH29TG1C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH29TG190",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IH2BHEM00",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "85",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH2BI4I00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH2BI4I01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "Start Web-RPA...",
//						"outlet": {
//							"jaxId": "1IH2BI4HR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH29T89N0"
//						}
//					}
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}