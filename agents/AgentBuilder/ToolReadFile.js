//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHHLMCC50MoreImports*/
import fsp from 'fs/promises';
/*}#1IHHLMCC50MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"filePath":{
			"name":"filePath","type":"string",
			"defaultValue":"",
			"desc":"要读取的文件路径，请提供完整的绝对路径",
		}
	},
	/*#{1IHHLMCC50ArgsView*/
	/*}#1IHHLMCC50ArgsView*/
};

/*#{1IHHLMCC50StartDoc*/
/*}#1IHHLMCC50StartDoc*/
//----------------------------------------------------------------------------
let ToolReadFile=async function(session){
	let filePath;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,ReadFile;
	/*#{1IHHLMCC50LocalVals*/
	/*}#1IHHLMCC50LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			filePath=input.filePath;
		}else{
			filePath=undefined;
		}
		/*#{1IHHLMCC50ParseArgs*/
		/*}#1IHHLMCC50ParseArgs*/
	}
	
	/*#{1IHHLMCC50PreContext*/
	/*}#1IHHLMCC50PreContext*/
	context={};
	/*#{1IHHLMCC50PostContext*/
	/*}#1IHHLMCC50PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHHLN9J60
		let result=input;
		let missing=false;
		if(filePath===undefined || filePath==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:ReadFile,result:(result),preSeg:"1IHHLN9J60",outlet:"1IHHLO8ID0"};
	};
	FixArgs.jaxId="1IHHLN9J60"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["ReadFile"]=ReadFile=async function(input){//:1IHHLO2SF0
		let result=input
		/*#{1IHHLO2SF0Code*/
		try{
			let content
			content=await fsp.readFile(filePath,"utf8");
			result={result:"Finish",content:content};
		}catch(err){
			if(filePath[0]!="/"){
				result={result:"Fail",content:`文件路径错误，需要"/"开头的完整路径，而不是相对路径。`};
			}else{
				result={result:"Fail",content:`读取文件内容失败: ${""+err}`};
			}
		}
		/*}#1IHHLO2SF0Code*/
		return {result:result};
	};
	ReadFile.jaxId="1IHHLO2SF0"
	ReadFile.url="ReadFile@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolReadFile",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHHLMCC50",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{filePath}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHHLMCC50PreEntry*/
			/*}#1IHHLMCC50PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHHLMCC50PostEntry*/
			/*}#1IHHLMCC50PostEntry*/
			return result;
		},
		/*#{1IHHLMCC50MoreAgentAttrs*/
		/*}#1IHHLMCC50MoreAgentAttrs*/
	};
	/*#{1IHHLMCC50PostAgent*/
	/*}#1IHHLMCC50PostAgent*/
	return agent;
};
/*#{1IHHLMCC50ExCodes*/
/*}#1IHHLMCC50ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolReadFile",
		description: "这是读取文件内容的工具。如果需要读取文件的文本内容，请调用本工具。\n请提供要读取的文件的完整路径，不要提供相对路径。",
		parameters:{
			type: "object",
			properties:{
				filePath:{type:"string",description:"要读取的文件路径，请提供完整的绝对路径"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IHHLMCC50PostDoc*/
/*}#1IHHLMCC50PostDoc*/


export default ToolReadFile;
export{ToolReadFile,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHHLMCC50",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHHLMCC51",
//			"attrs": {
//				"ToolReadFile": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHHLMCC57",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHHLMCC60",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHHLMCC61",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHHLMCC62",
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
//			"jaxId": "1IHHLMCC52",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHHLMCC53",
//			"attrs": {
//				"filePath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHHLN1VR0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要读取的文件路径，请提供完整的绝对路径"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHHLMCC54",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IHHLMCC55",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHHLMCC56",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHHLN9J60",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "120",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHHLO8ID0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHLO2SF0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHHLO2SF0",
//					"attrs": {
//						"id": "ReadFile",
//						"viewName": "",
//						"label": "",
//						"x": "325",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHHLOHQ70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHLOHQ71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHHLO8IE0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是读取文件内容的工具。如果需要读取文件的文本内容，请调用本工具。\n请提供要读取的文件的完整路径，不要提供相对路径。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}