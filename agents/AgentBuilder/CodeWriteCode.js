//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHI4J5VQ0MoreImports*/
/*}#1IHI4J5VQ0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"filePath":{
			"name":"filePath","type":"string",
			"defaultValue":"",
			"desc":"代码文件路径",
		},
		"orgCode":{
			"name":"orgCode","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"文件的代码，如果未设置，会自动读取文件。",
		},
		"prompt":{
			"name":"prompt","type":"string",
			"defaultValue":"",
			"desc":"如何编写/改写代码的提示。",
		}
	},
	/*#{1IHI4J5VQ0ArgsView*/
	/*}#1IHI4J5VQ0ArgsView*/
};

/*#{1IHI4J5VQ0StartDoc*/
/*}#1IHI4J5VQ0StartDoc*/
//----------------------------------------------------------------------------
let CodeWriteCode=async function(session){
	let filePath,orgCode,prompt;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,HasCode,ReadCode,PlanCode,PlanAction,RunTool,InitTools,WriteCode,DoChat,SaveCode;
	/*#{1IHI4J5VQ0LocalVals*/
	/*}#1IHI4J5VQ0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			filePath=input.filePath;
			orgCode=input.orgCode;
			prompt=input.prompt;
		}else{
			filePath=undefined;
			orgCode=undefined;
			prompt=undefined;
		}
		/*#{1IHI4J5VQ0ParseArgs*/
		/*}#1IHI4J5VQ0ParseArgs*/
	}
	
	/*#{1IHI4J5VQ0PreContext*/
	/*}#1IHI4J5VQ0PreContext*/
	context={};
	/*#{1IHI4J5VQ0PostContext*/
	/*}#1IHI4J5VQ0PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHI4RLDH0
		let result=input;
		let missing=false;
		if(filePath===undefined || filePath==="") missing=true;
		if(prompt===undefined || prompt==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:HasCode,result:(result),preSeg:"1IHI4RLDH0",outlet:"1IHI53A710"};
	};
	FixArgs.jaxId="1IHI4RLDH0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["HasCode"]=HasCode=async function(input){//:1IHI4S0VJ0
		let result=input;
		if(!orgCode){
			return {seg:ReadCode,result:(input),preSeg:"1IHI4S0VJ0",outlet:"1IHI53A711"};
		}
		return {seg:InitTools,result:(result),preSeg:"1IHI4S0VJ0",outlet:"1IHI53A712"};
	};
	HasCode.jaxId="1IHI4S0VJ0"
	HasCode.url="HasCode@"+agentURL
	
	segs["ReadCode"]=ReadCode=async function(input){//:1IHI4SSJ60
		let result=input
		/*#{1IHI4SSJ60Code*/
		/*}#1IHI4SSJ60Code*/
		return {seg:InitTools,result:(result),preSeg:"1IHI4SSJ60",outlet:"1IHI53A720"};
	};
	ReadCode.jaxId="1IHI4SSJ60"
	ReadCode.url="ReadCode@"+agentURL
	
	segs["PlanCode"]=PlanCode=async function(input){//:1IHI4TMKM0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"$plan",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=PlanCode.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		result=await session.callSegLLM("PlanCode@"+agentURL,opts,messages,true);
		return {seg:PlanAction,result:(result),preSeg:"1IHI4TMKM0",outlet:"1IHI53A721"};
	};
	PlanCode.jaxId="1IHI4TMKM0"
	PlanCode.url="PlanCode@"+agentURL
	
	segs["PlanAction"]=PlanAction=async function(input){//:1IHI4VP2O0
		let result=input;
		if(input==="Write"){
			return {seg:WriteCode,result:(input),preSeg:"1IHI4VP2O0",outlet:"1IHI53A722"};
		}
		if(input==="Chat"){
			return {seg:DoChat,result:(input),preSeg:"1IHI4VP2O0",outlet:"1IHI51H6D0"};
		}
		if(input==="Tool"){
			return {seg:RunTool,result:(input),preSeg:"1IHI4VP2O0",outlet:"1IHI517210"};
		}
		return {result:result};
	};
	PlanAction.jaxId="1IHI4VP2O0"
	PlanAction.url="PlanAction@"+agentURL
	
	segs["RunTool"]=RunTool=async function(input){//:1IHI522JM0
		let result=input
		/*#{1IHI522JM0Code*/
		/*}#1IHI522JM0Code*/
		return {seg:PlanCode,result:(result),preSeg:"1IHI522JM0",outlet:"1IHI53A724"};
	};
	RunTool.jaxId="1IHI522JM0"
	RunTool.url="RunTool@"+agentURL
	
	segs["InitTools"]=InitTools=async function(input){//:1IHI52S3R0
		let result=input
		/*#{1IHI52S3R0Code*/
		/*}#1IHI52S3R0Code*/
		return {seg:PlanCode,result:(result),preSeg:"1IHI52S3R0",outlet:"1IHI53A725"};
	};
	InitTools.jaxId="1IHI52S3R0"
	InitTools.url="InitTools@"+agentURL
	
	segs["WriteCode"]=WriteCode=async function(input){//:1IHI53UDT0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"$code",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=WriteCode.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		result=await session.callSegLLM("WriteCode@"+agentURL,opts,messages,true);
		return {seg:SaveCode,result:(result),preSeg:"1IHI53UDT0",outlet:"1IHI57QVC0"};
	};
	WriteCode.jaxId="1IHI53UDT0"
	WriteCode.url="WriteCode@"+agentURL
	
	segs["DoChat"]=DoChat=async function(input){//:1IHI5483D0
		let tip=(input.content);
		let tipRole=("assistant");
		let placeholder=("");
		let text=("");
		let result="";
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		return {seg:PlanCode,result:(result),preSeg:"1IHI5483D0",outlet:"1IHI57QVC1"};
	};
	DoChat.jaxId="1IHI5483D0"
	DoChat.url="DoChat@"+agentURL
	
	segs["SaveCode"]=SaveCode=async function(input){//:1IHI57KAQ0
		let result=input
		/*#{1IHI57KAQ0Code*/
		/*}#1IHI57KAQ0Code*/
		return {result:result};
	};
	SaveCode.jaxId="1IHI57KAQ0"
	SaveCode.url="SaveCode@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"CodeWriteCode",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHI4J5VQ0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{filePath,orgCode,prompt}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHI4J5VQ0PreEntry*/
			/*}#1IHI4J5VQ0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHI4J5VQ0PostEntry*/
			/*}#1IHI4J5VQ0PostEntry*/
			return result;
		},
		/*#{1IHI4J5VQ0MoreAgentAttrs*/
		/*}#1IHI4J5VQ0MoreAgentAttrs*/
	};
	/*#{1IHI4J5VQ0PostAgent*/
	/*}#1IHI4J5VQ0PostAgent*/
	return agent;
};
/*#{1IHI4J5VQ0ExCodes*/
/*}#1IHI4J5VQ0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CodeWriteCode",
		description: "根据用户提示编写/改写程序的工具智能体，需要编程的时候调用。",
		parameters:{
			type: "object",
			properties:{
				filePath:{type:"string",description:"代码文件路径"},
				orgCode:{type:"string",description:"文件的代码，如果未设置，会自动读取文件。"},
				prompt:{type:"string",description:"如何编写/改写代码的提示。"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IHI4J5VQ0PostDoc*/
/*}#1IHI4J5VQ0PostDoc*/


export default CodeWriteCode;
export{CodeWriteCode,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHI4J5VQ0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHI4J5VQ1",
//			"attrs": {
//				"CodeWriteCode": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHI4J5VQ7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHI4J5VQ8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHI4J5VQ9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHI4J5VQ10",
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
//			"jaxId": "1IHI4J5VQ2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHI4J5VQ3",
//			"attrs": {
//				"filePath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHI4PFEM0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "代码文件路径"
//					}
//				},
//				"orgCode": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHI4PFEM1",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "文件的代码，如果未设置，会自动读取文件。",
//						"required": "false"
//					}
//				},
//				"prompt": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHI4PFEN0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "如何编写/改写代码的提示。"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHI4J5VQ4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IHI4J5VQ5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHI4J5VQ6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHI4RLDH0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "85",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHI53A710",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI4S0VJ0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IHI4S0VJ0",
//					"attrs": {
//						"id": "HasCode",
//						"viewName": "",
//						"label": "",
//						"x": "290",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1IHI53A730",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI53A731",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI53A712",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IHI52S3R0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHI53A711",
//									"attrs": {
//										"id": "NoCode",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHI53A732",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHI53A733",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!orgCode"
//									},
//									"linkedSeg": "1IHI4SSJ60"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHI4SSJ60",
//					"attrs": {
//						"id": "ReadCode",
//						"viewName": "",
//						"label": "",
//						"x": "515",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI53A734",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI53A735",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI53A720",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI52S3R0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IHI4TMKM0",
//					"attrs": {
//						"id": "PlanCode",
//						"viewName": "",
//						"label": "",
//						"x": "945",
//						"y": "315",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI53A736",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI53A737",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "$plan",
//						"system": "You are a smart assistant.",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IHI53A721",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI4VP2O0"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "No",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "text",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IHI4VP2O0",
//					"attrs": {
//						"id": "PlanAction",
//						"viewName": "",
//						"label": "",
//						"x": "1175",
//						"y": "315",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI53A740",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI53A741",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI53A723",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHI53A722",
//									"attrs": {
//										"id": "Write",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHI53A742",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHI53A743",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1IHI53UDT0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHI51H6D0",
//									"attrs": {
//										"id": "Chat",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHI53A744",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHI53A745",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1IHI5483D0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHI517210",
//									"attrs": {
//										"id": "Tool",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHI53A746",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHI53A747",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1IHI522JM0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHI522JM0",
//					"attrs": {
//						"id": "RunTool",
//						"viewName": "",
//						"label": "",
//						"x": "1410",
//						"y": "375",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI53A748",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI53A749",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI53A724",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI557UP0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHI52S3R0",
//					"attrs": {
//						"id": "InitTools",
//						"viewName": "",
//						"label": "",
//						"x": "720",
//						"y": "315",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI53A7410",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI53A7411",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI53A725",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI4TMKM0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IHI53UDT0",
//					"attrs": {
//						"id": "WriteCode",
//						"viewName": "",
//						"label": "",
//						"x": "1410",
//						"y": "215",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI57QVE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI57QVE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "$code",
//						"system": "You are a smart assistant.",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IHI57QVC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI57KAQ0"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "No",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "text",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IHI5483D0",
//					"attrs": {
//						"id": "DoChat",
//						"viewName": "",
//						"label": "",
//						"x": "1410",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI57QVE2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI57QVE3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#input.content",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IHI57QVC1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI557UP0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHI557UP0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1535",
//						"y": "460",
//						"outlet": {
//							"jaxId": "1IHI57QVE4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI55DF60"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHI55DF60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "975",
//						"y": "460",
//						"outlet": {
//							"jaxId": "1IHI57QVE5",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI4TMKM0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHI57KAQ0",
//					"attrs": {
//						"id": "SaveCode",
//						"viewName": "",
//						"label": "",
//						"x": "1640",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI57QVE6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI57QVE7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI57QVC2",
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
//		"desc": "根据用户提示编写/改写程序的工具智能体，需要编程的时候调用。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}