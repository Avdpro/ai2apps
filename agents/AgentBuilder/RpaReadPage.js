//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHCKTECK0MoreImports*/
/*}#1IHCKTECK0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"url":{
			"name":"url","type":"string",
			"defaultValue":"",
			"desc":"要读取的页面URL",
		},
		"info":{
			"name":"info","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"要从页面中获得的信息",
		}
	},
	/*#{1IHCKTECK0ArgsView*/
	/*}#1IHCKTECK0ArgsView*/
};

/*#{1IHCKTECK0StartDoc*/
/*}#1IHCKTECK0StartDoc*/
//----------------------------------------------------------------------------
let RpaReadPage=async function(session){
	let url,info;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,InitEnv,AskUser,EndRead;
	/*#{1IHCKTECK0LocalVals*/
	/*}#1IHCKTECK0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			url=input.url;
			info=input.info;
		}else{
			url=undefined;
			info=undefined;
		}
		/*#{1IHCKTECK0ParseArgs*/
		/*}#1IHCKTECK0ParseArgs*/
	}
	
	/*#{1IHCKTECK0PreContext*/
	/*}#1IHCKTECK0PreContext*/
	context={};
	/*#{1IHCKTECK0PostContext*/
	/*}#1IHCKTECK0PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHG4F0UN0
		let result=input;
		let missing=false;
		if(url===undefined || url==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:InitEnv,result:(result),preSeg:"1IHG4F0UN0",outlet:"1IHG4F0UN1"};
	};
	FixArgs.jaxId="1IHG4F0UN0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["InitEnv"]=InitEnv=async function(input){//:1IHG4F75V0
		let result=input
		/*#{1IHG4F75V0Code*/
		/*}#1IHG4F75V0Code*/
		return {seg:AskUser,result:(result),preSeg:"1IHG4F75V0",outlet:"1IHG4F7602"};
	};
	InitEnv.jaxId="1IHG4F75V0"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1IHG4FH5K0
		let tip=(`请访问：${url}，${info?`找到与：${info}相关的信息`:"总结页面内容"}。`);
		let tipRole=("assistant");
		let placeholder=("");
		let text=("");
		let result="";
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		return {seg:EndRead,result:(result),preSeg:"1IHG4FH5K0",outlet:"1IHG4FH5K3"};
	};
	AskUser.jaxId="1IHG4FH5K0"
	AskUser.url="AskUser@"+agentURL
	
	segs["EndRead"]=EndRead=async function(input){//:1IHG4FS8N0
		let result=input
		/*#{1IHG4FS8N0Code*/
		/*}#1IHG4FS8N0Code*/
		return {result:result};
	};
	EndRead.jaxId="1IHG4FS8N0"
	EndRead.url="EndRead@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"RpaReadPage",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHCKTECK0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{url,info}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHCKTECK0PreEntry*/
			/*}#1IHCKTECK0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHCKTECK0PostEntry*/
			/*}#1IHCKTECK0PostEntry*/
			return result;
		},
		/*#{1IHCKTECK0MoreAgentAttrs*/
		/*}#1IHCKTECK0MoreAgentAttrs*/
	};
	/*#{1IHCKTECK0PostAgent*/
	/*}#1IHCKTECK0PostAgent*/
	return agent;
};
/*#{1IHCKTECK0ExCodes*/
/*}#1IHCKTECK0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "RpaReadPage",
		description: "这是一个读取Web页面内容的工具/AI智能体。给出一个页面URL和想要提取的信息（例如：获取页面的InnerHTML，页面文章详细内容，针对页面内容的问题等），本工具会读取页面内容并回答。\n仅用于读取互联网上页面内容，请不要使用本工具读取本地磁盘上的文件内容。",
		parameters:{
			type: "object",
			properties:{
				url:{type:"string",description:"要读取的页面URL"},
				info:{type:"string",description:"要从页面中获得的信息"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IHCKTECK0PostDoc*/
/*}#1IHCKTECK0PostDoc*/


export default RpaReadPage;
export{RpaReadPage,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHCKTECK0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHCKTECK1",
//			"attrs": {
//				"RpaReadPage": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHCKTECL2",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHCKTECL3",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHCKTECL4",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHCKTECL5",
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
//			"jaxId": "1IHCKTECK2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHCKTECK3",
//			"attrs": {
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHG4ELHI0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要读取的页面URL"
//					}
//				},
//				"info": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHG4ELHJ0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要从页面中获得的信息",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHCKTECK4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IHCKTECL0",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHCKTECL1",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHG4F0UN0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "60",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHG4F0UN1",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHG4F75V0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHG4F75V0",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "265",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHG4F7600",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHG4F7601",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHG4F7602",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHG4FH5K0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IHG4FH5K0",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "480",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHG4FH5K1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHG4FH5K2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#`请访问：${url}，${info?`找到与：${info}相关的信息`:\"总结页面内容\"}。`",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IHG4FH5K3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHG4FS8N0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHG4FS8N0",
//					"attrs": {
//						"id": "EndRead",
//						"viewName": "",
//						"label": "",
//						"x": "690",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHG4FS8N1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHG4FS8N2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHG4FS8N3",
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
//		"desc": "这是一个读取Web页面内容的工具/AI智能体。给出一个页面URL和想要提取的信息（例如：获取页面的InnerHTML，页面文章详细内容，针对页面内容的问题等），本工具会读取页面内容并回答。\n仅用于读取互联网上页面内容，请不要使用本工具读取本地磁盘上的文件内容。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}