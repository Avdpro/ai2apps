//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1J4RKIIQO0MoreImports*/
/*}#1J4RKIIQO0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?decodeURI(baseURL):baseURL;
const $ln=VFACT.lanCode||"EN";
/*#{1J4RKIIQO0StartDoc*/
/*}#1J4RKIIQO0StartDoc*/
//----------------------------------------------------------------------------
let TestAPI=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	
	/*#{1J4RKIIQO0LocalVals*/
	/*}#1J4RKIIQO0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1J4RKIIQO0ParseArgs*/
		/*}#1J4RKIIQO0ParseArgs*/
	}
	
	/*#{1J4RKIIQO0PreContext*/
	/*}#1J4RKIIQO0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1J4RKIIQO0PostContext*/
	/*}#1J4RKIIQO0PostContext*/
	let $agent,agent,segs={};
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"TestAPI",
		url:agentURL,
		autoStart:true,
		jaxId:"1J4RKIIQO0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1J4RKIIQO0PreEntry*/
			/*}#1J4RKIIQO0PreEntry*/
			/*#{1J4RKIIQO0PostEntry*/
			/*}#1J4RKIIQO0PostEntry*/
			return result;
		},
		/*#{1J4RKIIQO0MoreAgentAttrs*/
		/*}#1J4RKIIQO0MoreAgentAttrs*/
	};
	/*#{1J4RKIIQO0PostAgent*/
	/*}#1J4RKIIQO0PostAgent*/
	return agent;
};
/*#{1J4RKIIQO0ExCodes*/
/*}#1J4RKIIQO0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1J4RKIIQO0PostDoc*/
/*}#1J4RKIIQO0PostDoc*/


export default TestAPI;
export{TestAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1J4RKIIQO0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1J4RKIK390",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1J4RKIK391",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1J4RKIK392",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1J4RKIK393",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1J4RKIK394",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1J4RKIK395",
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