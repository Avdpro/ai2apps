//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHCHS17T0MoreImports*/
/*}#1IHCHS17T0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"search":{
			"name":"search","type":"string",
			"defaultValue":"",
			"desc":"要搜索的内容",
		}
	},
	/*#{1IHCHS17T0ArgsView*/
	/*}#1IHCHS17T0ArgsView*/
};

/*#{1IHCHS17T0StartDoc*/
/*}#1IHCHS17T0StartDoc*/
//----------------------------------------------------------------------------
let RpaWebSearch=async function(session){
	let search;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,InitEnv,AskUser,EndSearch;
	/*#{1IHCHS17T0LocalVals*/
	/*}#1IHCHS17T0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			search=input.search;
		}else{
			search=undefined;
		}
		/*#{1IHCHS17T0ParseArgs*/
		/*}#1IHCHS17T0ParseArgs*/
	}
	
	/*#{1IHCHS17T0PreContext*/
	/*}#1IHCHS17T0PreContext*/
	context={};
	/*#{1IHCHS17T0PostContext*/
	/*}#1IHCHS17T0PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHCKI9BO0
		let result=input;
		let missing=false;
		if(search===undefined || search==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:InitEnv,result:(result),preSeg:"1IHCKI9BO0",outlet:"1IHCKJ60E0"};
	};
	FixArgs.jaxId="1IHCKI9BO0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["InitEnv"]=InitEnv=async function(input){//:1IHCHSA4D0
		let result=input
		/*#{1IHCHSA4D0Code*/
		/*}#1IHCHSA4D0Code*/
		return {seg:AskUser,result:(result),preSeg:"1IHCHSA4D0",outlet:"1IHCHTPKO0"};
	};
	InitEnv.jaxId="1IHCHSA4D0"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1IHCHSO060
		let tip=(`请在Google上搜索： \n${search}.`);
		let tipRole=("assistant");
		let placeholder=("");
		let text=("");
		let result="";
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		return {seg:EndSearch,result:(result),preSeg:"1IHCHSO060",outlet:"1IHCHTPKO1"};
	};
	AskUser.jaxId="1IHCHSO060"
	AskUser.url="AskUser@"+agentURL
	
	segs["EndSearch"]=EndSearch=async function(input){//:1IHCHT2PG0
		let result=input
		/*#{1IHCHT2PG0Code*/
		/*}#1IHCHT2PG0Code*/
		return {result:result};
	};
	EndSearch.jaxId="1IHCHT2PG0"
	EndSearch.url="EndSearch@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"RpaWebSearch",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHCHS17T0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{search}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHCHS17T0PreEntry*/
			/*}#1IHCHS17T0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHCHS17T0PostEntry*/
			/*}#1IHCHS17T0PostEntry*/
			return result;
		},
		/*#{1IHCHS17T0MoreAgentAttrs*/
		/*}#1IHCHS17T0MoreAgentAttrs*/
	};
	/*#{1IHCHS17T0PostAgent*/
	/*}#1IHCHS17T0PostAgent*/
	return agent;
};
/*#{1IHCHS17T0ExCodes*/
/*}#1IHCHS17T0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "RpaWebSearch",
		description: "使用Google进行网页搜索并返回总结后的搜索结果。",
		parameters:{
			type: "object",
			properties:{
				search:{type:"string",description:"要搜索的内容"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IHCHS17T0PostDoc*/
/*}#1IHCHS17T0PostDoc*/


export default RpaWebSearch;
export{RpaWebSearch,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHCHS17T0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHCHS17T1",
//			"attrs": {
//				"RpaWebSearch": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHCHS17U0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHCHS17U1",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHCHS17U2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHCHS17U3",
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
//			"jaxId": "1IHCHS17T2",
//			"attrs": {}
//		},
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHCHS17T3",
//			"attrs": {
//				"search": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHCKJ60G0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要搜索的内容"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHCHS17T4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IHCHS17T5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHCHS17T6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHCKI9BO0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "70",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHCKJ60E0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCHSA4D0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHCHSA4D0",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "285",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCHTPKQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCHTPKQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHCHTPKO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCHSO060"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IHCHSO060",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "495",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCHTPKQ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCHTPKQ3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#`请在Google上搜索： \\n${search}.`",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IHCHTPKO1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCHT2PG0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHCHT2PG0",
//					"attrs": {
//						"id": "EndSearch",
//						"viewName": "",
//						"label": "",
//						"x": "715",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCHTPKQ4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCHTPKQ5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHCHTPKP0",
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
//		"desc": "使用Google进行网页搜索并返回总结后的搜索结果。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}