//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1JDTD3AD10MoreImports*/
/*}#1JDTD3AD10MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?decodeURI(baseURL):baseURL;
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"startUrl":{
			"name":"startUrl","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"goal":{
			"name":"goal","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JDTD3AD10ArgsView*/
	/*}#1JDTD3AD10ArgsView*/
};

/*#{1JDTD3AD10StartDoc*/
/*}#1JDTD3AD10StartDoc*/
//----------------------------------------------------------------------------
let GenWebRpa=async function(session){
	let startUrl,goal;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	
	/*#{1JDTD3AD10LocalVals*/
	/*}#1JDTD3AD10LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			startUrl=input.startUrl;
			goal=input.goal;
		}else{
			startUrl=undefined;
			goal=undefined;
		}
		/*#{1JDTD3AD10ParseArgs*/
		/*}#1JDTD3AD10ParseArgs*/
	}
	
	/*#{1JDTD3AD10PreContext*/
	/*}#1JDTD3AD10PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1JDTD3AD10PostContext*/
	/*}#1JDTD3AD10PostContext*/
	let $agent,agent,segs={};
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"GenWebRpa",
		url:agentURL,
		autoStart:true,
		jaxId:"1JDTD3AD10",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{startUrl,goal}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JDTD3AD10PreEntry*/
			/*}#1JDTD3AD10PreEntry*/
			/*#{1JDTD3AD10PostEntry*/
			/*}#1JDTD3AD10PostEntry*/
			return result;
		},
		/*#{1JDTD3AD10MoreAgentAttrs*/
		/*}#1JDTD3AD10MoreAgentAttrs*/
	};
	/*#{1JDTD3AD10PostAgent*/
	/*}#1JDTD3AD10PostAgent*/
	return agent;
};
/*#{1JDTD3AD10ExCodes*/
/*}#1JDTD3AD10ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JDTD3AD10PostDoc*/
/*}#1JDTD3AD10PostDoc*/


export default GenWebRpa;
export{GenWebRpa};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JDTD3AD10",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JDTD3AD11",
//			"attrs": {
//				"GenWebRpa": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JDTD3AD20",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JDTD3AD21",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1JDTD3AD22",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JDTD3AD23",
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
//			"jaxId": "1JDTD3AD12",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JDTD3AD13",
//			"attrs": {
//				"startUrl": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDTD7IV30",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"goal": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDTD7IV31",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JDTD3AD14",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JDTD3AD15",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JDTD3AD16",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": []
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}