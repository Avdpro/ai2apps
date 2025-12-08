//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1JAV99S3I0MoreImports*/
/*}#1JAV99S3I0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1JAV99S3I0StartDoc*/
/*}#1JAV99S3I0StartDoc*/
//----------------------------------------------------------------------------
let CheckEnvironment=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let InitBash,CheckHuggingface,output,CheckPip;
	/*#{1JAV99S3I0LocalVals*/
	let hf_mirror = false, pip_mirror = false, conda_mirror = false;
	/*}#1JAV99S3I0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1JAV99S3I0ParseArgs*/
		/*}#1JAV99S3I0ParseArgs*/
	}
	
	/*#{1JAV99S3I0PreContext*/
	/*}#1JAV99S3I0PreContext*/
	context={};
	/*#{1JAV99S3I0PostContext*/
	/*}#1JAV99S3I0PostContext*/
	let $agent,agent,segs={};
	segs["InitBash"]=InitBash=async function(input){//:1JAV99LPT0
		let result,args={};
		args['bashId']=undefined;
		args['action']="Create";
		args['commands']="";
		args['options']={client:true};
		/*#{1JAV99LPT0PreCodes*/
		/*}#1JAV99LPT0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JAV99LPT0PostCodes*/
		globalContext.bash=result;
		/*}#1JAV99LPT0PostCodes*/
		return {seg:CheckHuggingface,result:(result),preSeg:"1JAV99LPT0",outlet:"1JAV99S3I1"};
	};
	InitBash.jaxId="1JAV99LPT0"
	InitBash.url="InitBash@"+agentURL
	
	segs["CheckHuggingface"]=CheckHuggingface=async function(input){//:1JAV9CQ770
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="ping huggingface.co -c 5";
		args['options']="";
		/*#{1JAV9CQ770PreCodes*/
		/*}#1JAV9CQ770PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JAV9CQ770PostCodes*/
		if(result.split("Request timeout").length - 1 > 2) hf_mirror=true;
		/*}#1JAV9CQ770PostCodes*/
		return {seg:CheckPip,result:(result),preSeg:"1JAV9CQ770",outlet:"1JAV9D4I60"};
	};
	CheckHuggingface.jaxId="1JAV9CQ770"
	CheckHuggingface.url="CheckHuggingface@"+agentURL
	
	segs["output"]=output=async function(input){//:1JAVA673K0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {result:result};
	};
	output.jaxId="1JAVA673K0"
	output.url="output@"+agentURL
	
	segs["CheckPip"]=CheckPip=async function(input){//:1JAVAB6JV0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="ping pypi.org -c 5";
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {result:result};
	};
	CheckPip.jaxId="1JAVAB6JV0"
	CheckPip.url="CheckPip@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CheckEnvironment",
		url:agentURL,
		autoStart:true,
		jaxId:"1JAV99S3I0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1JAV99S3I0PreEntry*/
			/*}#1JAV99S3I0PreEntry*/
			result={seg:InitBash,"input":input};
			/*#{1JAV99S3I0PostEntry*/
			/*}#1JAV99S3I0PostEntry*/
			return result;
		},
		/*#{1JAV99S3I0MoreAgentAttrs*/
		/*}#1JAV99S3I0MoreAgentAttrs*/
	};
	/*#{1JAV99S3I0PostAgent*/
	/*}#1JAV99S3I0PostAgent*/
	return agent;
};
/*#{1JAV99S3I0ExCodes*/
/*}#1JAV99S3I0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JAV99S3I0PostDoc*/
/*}#1JAV99S3I0PostDoc*/


export default CheckEnvironment;
export{CheckEnvironment};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JAV99S3I0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JAV99S3K0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JAV99S3K1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JAV99S3K2",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1JAV99S3K3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JAV99S3K4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JAV99S3K5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JAV99LPT0",
//					"attrs": {
//						"id": "InitBash",
//						"viewName": "",
//						"label": "",
//						"x": "195",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAV99S3L0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAV99S3L1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client:true}",
//						"outlet": {
//							"jaxId": "1JAV99S3I1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAV9CQ770"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JAV9CQ770",
//					"attrs": {
//						"id": "CheckHuggingface",
//						"viewName": "",
//						"label": "",
//						"x": "425",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAV9E2PV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAV9E2PV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "ping huggingface.co -c 5",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JAV9D4I60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JAVAB6JV0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JAVA673K0",
//					"attrs": {
//						"id": "output",
//						"viewName": "",
//						"label": "",
//						"x": "950",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAVA69J80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAVA69J81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JAVA69J50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JAVAB6JV0",
//					"attrs": {
//						"id": "CheckPip",
//						"viewName": "",
//						"label": "",
//						"x": "700",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JAVAFPHP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JAVAFPHP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "ping pypi.org -c 5",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JAVABFP30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "terminal.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}