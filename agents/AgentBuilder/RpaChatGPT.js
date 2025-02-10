//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHCKTURA0MoreImports*/
/*}#1IHCKTURA0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"question":{
			"name":"question","type":"string",
			"defaultValue":"",
			"desc":"向ChatGPT询问的问题内容",
		},
		"search":{
			"name":"search","type":"bool",
			"required":false,
			"defaultValue":"",
			"desc":"是否启用网页搜索功能",
		}
	},
	/*#{1IHCKTURA0ArgsView*/
	/*}#1IHCKTURA0ArgsView*/
};

/*#{1IHCKTURA0StartDoc*/
/*}#1IHCKTURA0StartDoc*/
//----------------------------------------------------------------------------
let RpaChatGPT=async function(session){
	let question,search;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,InitEnv,AskUser,EndSearch;
	/*#{1IHCKTURA0LocalVals*/
	/*}#1IHCKTURA0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			question=input.question;
			search=input.search;
		}else{
			question=undefined;
			search=undefined;
		}
		/*#{1IHCKTURA0ParseArgs*/
		/*}#1IHCKTURA0ParseArgs*/
	}
	
	/*#{1IHCKTURA0PreContext*/
	/*}#1IHCKTURA0PreContext*/
	context={};
	/*#{1IHCKTURA0PostContext*/
	/*}#1IHCKTURA0PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHCL1I0S0
		let result=input;
		let missing=false;
		if(question===undefined || question==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:InitEnv,result:(result),preSeg:"1IHCL1I0S0",outlet:"1IHCL4L8S0"};
	};
	FixArgs.jaxId="1IHCL1I0S0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["InitEnv"]=InitEnv=async function(input){//:1IHCL1PS80
		let result=input
		/*#{1IHCL1PS80Code*/
		/*}#1IHCL1PS80Code*/
		return {seg:AskUser,result:(result),preSeg:"1IHCL1PS80",outlet:"1IHCL4L8S1"};
	};
	InitEnv.jaxId="1IHCL1PS80"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1IHCL20I50
		let tip=(`请向ChatGPT提问：  \n${question}。（${search?"使用搜索":"不使用搜索。"}）`);
		let tipRole=("assistant");
		let placeholder=("");
		let text=("");
		let result="";
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		return {seg:EndSearch,result:(result),preSeg:"1IHCL20I50",outlet:"1IHCL4L8S2"};
	};
	AskUser.jaxId="1IHCL20I50"
	AskUser.url="AskUser@"+agentURL
	
	segs["EndSearch"]=EndSearch=async function(input){//:1IHCL4OQV0
		let result=input
		/*#{1IHCL4OQV0Code*/
		/*}#1IHCL4OQV0Code*/
		return {result:result};
	};
	EndSearch.jaxId="1IHCL4OQV0"
	EndSearch.url="EndSearch@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"RpaChatGPT",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHCKTURA0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{question,search}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHCKTURA0PreEntry*/
			/*}#1IHCKTURA0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHCKTURA0PostEntry*/
			/*}#1IHCKTURA0PostEntry*/
			return result;
		},
		/*#{1IHCKTURA0MoreAgentAttrs*/
		/*}#1IHCKTURA0MoreAgentAttrs*/
	};
	/*#{1IHCKTURA0PostAgent*/
	/*}#1IHCKTURA0PostAgent*/
	return agent;
};
/*#{1IHCKTURA0ExCodes*/
/*}#1IHCKTURA0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "RpaChatGPT",
		description: "与网页版ChatGPT对话，获取问题答案",
		parameters:{
			type: "object",
			properties:{
				question:{type:"string",description:"向ChatGPT询问的问题内容"},
				search:{type:"bool",description:"是否启用网页搜索功能"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IHCKTURA0PostDoc*/
/*}#1IHCKTURA0PostDoc*/


export default RpaChatGPT;
export{RpaChatGPT,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHCKTURA0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHCKTURA1",
//			"attrs": {
//				"RpaChatGPT": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHCKTURB0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHCKTURB1",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHCKTURB2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHCKTURB3",
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
//			"jaxId": "1IHCKTURA2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHCKTURA3",
//			"attrs": {
//				"question": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHCL1BU00",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "向ChatGPT询问的问题内容"
//					}
//				},
//				"search": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHCL1BU01",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "\"\"",
//						"desc": "是否启用网页搜索功能",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHCKTURA4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IHCKTURA5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHCKTURA6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHCL1I0S0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "50",
//						"y": "230",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHCL4L8S0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCL1PS80"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHCL1PS80",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "240",
//						"y": "230",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCL4L8T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCL4L8T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHCL4L8S1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCL20I50"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IHCL20I50",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "450",
//						"y": "230",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCL4L8T2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCL4L8T3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#`请向ChatGPT提问：  \\n${question}。（${search?\"使用搜索\":\"不使用搜索。\"}）`",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IHCL4L8S2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCL4OQV0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHCL4OQV0",
//					"attrs": {
//						"id": "EndSearch",
//						"viewName": "",
//						"label": "",
//						"x": "660",
//						"y": "230",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCL4S970",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCL4S971",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHCL4S960",
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
//		"desc": "与网页版ChatGPT对话，获取问题答案",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}