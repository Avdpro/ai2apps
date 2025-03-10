//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1ILSNBFKR0MoreImports*/
/*}#1ILSNBFKR0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1ILSNBFKR0StartDoc*/
/*}#1ILSNBFKR0StartDoc*/
//----------------------------------------------------------------------------
let ToolTabOSReadPage=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let CallAgent;
	/*#{1ILSNBFKR0LocalVals*/
	/*}#1ILSNBFKR0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1ILSNBFKR0ParseArgs*/
		/*}#1ILSNBFKR0ParseArgs*/
	}
	
	/*#{1ILSNBFKR0PreContext*/
	/*}#1ILSNBFKR0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1ILSNBFKR0PostContext*/
	/*}#1ILSNBFKR0PostContext*/
	let agent,segs={};
	segs["CallAgent"]=CallAgent=async function(input){//:1ILSNBPSH0
		let result,args={};
		args['nodeName']="AgentBuilder";
		args['callAgent']="RpaReadPage.js";
		args['callArg']=input;
		args['checkUpdate']=true;
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	CallAgent.jaxId="1ILSNBPSH0"
	CallAgent.url="CallAgent@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolTabOSReadPage",
		url:agentURL,
		autoStart:true,
		jaxId:"1ILSNBFKR0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1ILSNBFKR0PreEntry*/
			/*}#1ILSNBFKR0PreEntry*/
			result={seg:CallAgent,"input":input};
			/*#{1ILSNBFKR0PostEntry*/
			/*}#1ILSNBFKR0PostEntry*/
			return result;
		},
		/*#{1ILSNBFKR0MoreAgentAttrs*/
		/*}#1ILSNBFKR0MoreAgentAttrs*/
	};
	/*#{1ILSNBFKR0PostAgent*/
	/*}#1ILSNBFKR0PostAgent*/
	return agent;
};
/*#{1ILSNBFKR0ExCodes*/
/*}#1ILSNBFKR0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1ILSNBFKR0PostDoc*/
/*}#1ILSNBFKR0PostDoc*/


export default ToolTabOSReadPage;
export{ToolTabOSReadPage};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1ILSNBFKR0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1ILSNBFKR1",
//			"attrs": {
//				"ToolTabOSReadPage": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1ILSNBFKS0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1ILSNBFKS1",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1ILSNBFKS2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1ILSNBFKS3",
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
//			"jaxId": "1ILSNBFKR2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1ILSNBFKR3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1ILSNBFKR4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1ILSNBFKR5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1ILSNBFKR6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1ILSNBPSH0",
//					"attrs": {
//						"id": "CallAgent",
//						"viewName": "",
//						"label": "",
//						"x": "170",
//						"y": "220",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSND5EH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSND5EH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AgentBuilder",
//						"callAgent": "RpaReadPage.js",
//						"callArg": "#input",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1ILSND5EG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "cloudact.svg"
//				}
//			]
//		},
//		"desc": "这是一个读取Web页面内容的工具/AI智能体。给出一个页面URL和想要提取的信息（例如：获取页面的InnerHTML，页面文章详细内容，针对页面内容的问题等），本工具会读取页面内容并回答。\n仅用于读取互联网上页面内容，请不要使用本工具读取本地磁盘上的文件内容。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}