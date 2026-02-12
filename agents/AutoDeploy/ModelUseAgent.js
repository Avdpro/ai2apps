//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1JH054SQN0MoreImports*/
/*}#1JH054SQN0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?decodeURI(baseURL):baseURL;
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JH054SQN0ArgsView*/
	/*}#1JH054SQN0ArgsView*/
};

/*#{1JH054SQN0StartDoc*/
/*}#1JH054SQN0StartDoc*/
//----------------------------------------------------------------------------
let ModelUseAgent=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Run;
	/*#{1JH054SQN0LocalVals*/
	/*}#1JH054SQN0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
		}else{
			model=undefined;
		}
		/*#{1JH054SQN0ParseArgs*/
		/*}#1JH054SQN0ParseArgs*/
	}
	
	/*#{1JH054SQN0PreContext*/
	/*}#1JH054SQN0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1JH054SQN0PostContext*/
	/*}#1JH054SQN0PostContext*/
	let $agent,agent,segs={};
	segs["Run"]=Run=async function(input){//:1JH056C1R0
		let result,args={};
		args['nodeName']="AutoDeploy";
		args['callAgent']="ModelUse.js";
		args['callArg']={model:model};
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	Run.jaxId="1JH056C1R0"
	Run.url="Run@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ModelUseAgent",
		url:agentURL,
		autoStart:true,
		jaxId:"1JH054SQN0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JH054SQN0PreEntry*/
			/*}#1JH054SQN0PreEntry*/
			result={seg:Run,"input":input};
			/*#{1JH054SQN0PostEntry*/
			/*}#1JH054SQN0PostEntry*/
			return result;
		},
		/*#{1JH054SQN0MoreAgentAttrs*/
		/*}#1JH054SQN0MoreAgentAttrs*/
	};
	/*#{1JH054SQN0PostAgent*/
	/*}#1JH054SQN0PostAgent*/
	return agent;
};
/*#{1JH054SQN0ExCodes*/
/*}#1JH054SQN0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JH054SQN0PostDoc*/
/*}#1JH054SQN0PostDoc*/


export default ModelUseAgent;
export{ModelUseAgent};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JH054SQN0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JH056FAM0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JH056FAM1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JH056FAM2",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JH056JQE0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JH056FAM3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JH056FAM4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JH056FAM5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1JH056C1R0",
//					"attrs": {
//						"id": "Run",
//						"viewName": "",
//						"label": "",
//						"x": "750",
//						"y": "240",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH056FAM6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH056FAM7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AutoDeploy",
//						"callAgent": "ModelUse.js",
//						"callArg": "#{model:model}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JH056FAL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							}
//						}
//					},
//					"icon": "cloudact.svg"
//				}
//			]
//		},
//		"desc": "This is an AI agent.",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}