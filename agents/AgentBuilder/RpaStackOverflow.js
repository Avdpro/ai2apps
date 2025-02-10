//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHCKLKEB0MoreImports*/
/*}#1IHCKLKEB0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"search":{
			"name":"search","type":"string",
			"defaultValue":"",
			"desc":"要查询的代码问题",
		}
	},
	/*#{1IHCKLKEB0ArgsView*/
	/*}#1IHCKLKEB0ArgsView*/
};

/*#{1IHCKLKEB0StartDoc*/
/*}#1IHCKLKEB0StartDoc*/
//----------------------------------------------------------------------------
let RpaStackOverflow=async function(session){
	let search;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,InitEnv,AskUser,EndSearch;
	/*#{1IHCKLKEB0LocalVals*/
	/*}#1IHCKLKEB0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			search=input.search;
		}else{
			search=undefined;
		}
		/*#{1IHCKLKEB0ParseArgs*/
		/*}#1IHCKLKEB0ParseArgs*/
	}
	
	/*#{1IHCKLKEB0PreContext*/
	/*}#1IHCKLKEB0PreContext*/
	context={};
	/*#{1IHCKLKEB0PostContext*/
	/*}#1IHCKLKEB0PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHCKO1OQ0
		let result=input;
		let missing=false;
		if(search===undefined || search==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:InitEnv,result:(result),preSeg:"1IHCKO1OQ0",outlet:"1IHCKQOH30"};
	};
	FixArgs.jaxId="1IHCKO1OQ0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["InitEnv"]=InitEnv=async function(input){//:1IHCKO97P0
		let result=input
		/*#{1IHCKO97P0Code*/
		/*}#1IHCKO97P0Code*/
		return {seg:AskUser,result:(result),preSeg:"1IHCKO97P0",outlet:"1IHCKQOH31"};
	};
	InitEnv.jaxId="1IHCKO97P0"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1IHCKOMTU0
		let tip=(`请在https://stackoverflow.com网站搜索:  \n\n${search}`);
		let tipRole=("assistant");
		let placeholder=("");
		let text=("");
		let result="";
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		return {seg:EndSearch,result:(result),preSeg:"1IHCKOMTU0",outlet:"1IHCKQOH40"};
	};
	AskUser.jaxId="1IHCKOMTU0"
	AskUser.url="AskUser@"+agentURL
	
	segs["EndSearch"]=EndSearch=async function(input){//:1IHCKQTR80
		let result=input
		/*#{1IHCKQTR80Code*/
		/*}#1IHCKQTR80Code*/
		return {result:result};
	};
	EndSearch.jaxId="1IHCKQTR80"
	EndSearch.url="EndSearch@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"RpaStackOverflow",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHCKLKEB0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{search}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHCKLKEB0PreEntry*/
			/*}#1IHCKLKEB0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHCKLKEB0PostEntry*/
			/*}#1IHCKLKEB0PostEntry*/
			return result;
		},
		/*#{1IHCKLKEB0MoreAgentAttrs*/
		/*}#1IHCKLKEB0MoreAgentAttrs*/
	};
	/*#{1IHCKLKEB0PostAgent*/
	/*}#1IHCKLKEB0PostAgent*/
	return agent;
};
/*#{1IHCKLKEB0ExCodes*/
/*}#1IHCKLKEB0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "RpaStackOverflow",
		description: "使用stackoverflow.com网站查询代码相关的问题。",
		parameters:{
			type: "object",
			properties:{
				search:{type:"string",description:"要查询的代码问题"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IHCKLKEB0PostDoc*/
/*}#1IHCKLKEB0PostDoc*/


export default RpaStackOverflow;
export{RpaStackOverflow,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHCKLKEB0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHCKLKEB1",
//			"attrs": {
//				"RpaStackOverflow": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHCKLKEB7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHCKLKEB8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHCKLKEB9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHCKLKEB10",
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
//			"jaxId": "1IHCKLKEB2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHCKLKEB3",
//			"attrs": {
//				"search": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHCKNTI80",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要查询的代码问题"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHCKLKEB4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IHCKLKEB5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHCKLKEB6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHCKO1OQ0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "75",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHCKQOH30",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCKO97P0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHCKO97P0",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "280",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCKQOH41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCKQOH42",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHCKQOH31",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCKOMTU0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IHCKOMTU0",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "485",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCKQOH43",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCKQOH44",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#`请在https://stackoverflow.com网站搜索:  \\n\\n${search}`",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IHCKQOH40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCKQTR80"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHCKQTR80",
//					"attrs": {
//						"id": "EndSearch",
//						"viewName": "",
//						"label": "",
//						"x": "700",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCKR4F50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCKR4F51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHCKR4F40",
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
//		"desc": "使用stackoverflow.com网站查询代码相关的问题。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}