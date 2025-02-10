//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IH730PV10MoreImports*/
/*}#1IH730PV10MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"argsTemplate":{
			"name":"argsTemplate","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"command":{
			"name":"command","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IH730PV10ArgsView*/
	/*}#1IH730PV10ArgsView*/
};

/*#{1IH730PV10StartDoc*/
/*}#1IH730PV10StartDoc*/
//----------------------------------------------------------------------------
let HubFixArgs=async function(session){
	let argsTemplate,command;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let CheckCommand,GenArgs,HasMissing,InputArgs,Done;
	/*#{1IH730PV10LocalVals*/
	/*}#1IH730PV10LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			argsTemplate=input.argsTemplate;
			command=input.command;
		}else{
			argsTemplate=undefined;
			command=undefined;
		}
		/*#{1IH730PV10ParseArgs*/
		/*}#1IH730PV10ParseArgs*/
	}
	
	/*#{1IH730PV10PreContext*/
	/*}#1IH730PV10PreContext*/
	context={
		args: "",
		/*#{1IH730PV15ExCtxAttrs*/
		/*}#1IH730PV15ExCtxAttrs*/
	};
	/*#{1IH730PV10PostContext*/
	/*}#1IH730PV10PostContext*/
	let agent,segs={};
	segs["CheckCommand"]=CheckCommand=async function(input){//:1IH73317D0
		let result=input;
		if(!!command){
			return {seg:GenArgs,result:(input),preSeg:"1IH73317D0",outlet:"1IH73317D4"};
		}
		return {seg:InputArgs,result:(result),preSeg:"1IH73317D0",outlet:"1IH73317D3"};
	};
	CheckCommand.jaxId="1IH73317D0"
	CheckCommand.url="CheckCommand@"+agentURL
	
	segs["GenArgs"]=GenArgs=async function(input){//:1IH73EH360
		let prompt;
		let result=null;
		/*#{1IH73EH360Input*/
		/*}#1IH73EH360Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=GenArgs.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
你是一个解析自然语言命令，生成函数调用参数的AI
- 用户会输入要调用的函数的参数描述以及自然语言命令。

- 函数参数描述是以JSON形式提供，例如
{
	"name":{
		"name":"name","type":"string",
		"defaultValue":"",
		"desc":"User name used in this site."
	},
	"gender":{
		"name":"gender","type":"string",
		"defaultValue":"Male",
		"desc":"User gender."
	}
}

- 请根据函数参数JSON，分析用户的自然语言指令，生成调用函数的参数VO，用JSON回答。例如：
{
	"name":"Alex",
    "gender":"Male"
}

- 如果你无法确定某些参数的内容，请用字符串"$$MISSING"作为参数值.例如，如果你不能确定gender属性：：
{
	"name":"Alex",
    "gender":"$$MISSING"
}
`},
		];
		/*#{1IH73EH360PrePrompt*/
		/*}#1IH73EH360PrePrompt*/
		prompt=`
函数参数JSON：
${JSON.stringify(argsTemplate.properties,null,"\t")}
自然语言指令：${command}
`;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		/*#{1IH73EH360PreCall*/
		/*}#1IH73EH360PreCall*/
		result=(result===null)?(await session.callSegLLM("GenArgs@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IH73EH360PostCall*/
		context.args=result;
		/*}#1IH73EH360PostCall*/
		return {seg:HasMissing,result:(result),preSeg:"1IH73EH360",outlet:"1IH73EH363"};
	};
	GenArgs.jaxId="1IH73EH360"
	GenArgs.url="GenArgs@"+agentURL
	
	segs["HasMissing"]=HasMissing=async function(input){//:1IH73GIC20
		let result=input;
		/*#{1IH73GIC20Start*/
		let hasMissing=false;
		let pptDefs=argsTemplate.properties;
		{
			let key,value;
			for(key in input){
				value=input[key];
				if(value==="$$MISSING"){
					delete input[key];
					if(pptDefs[key].required!==false){
						hasMissing=true;
					}
				}
			}
		}
		/*}#1IH73GIC20Start*/
		if(!hasMissing){
			return {seg:Done,result:(input),preSeg:"1IH73GIC20",outlet:"1IH73GIC30"};
		}
		/*#{1IH73GIC20Post*/
		/*}#1IH73GIC20Post*/
		return {seg:InputArgs,result:(result),preSeg:"1IH73GIC20",outlet:"1IH73GIC23"};
	};
	HasMissing.jaxId="1IH73GIC20"
	HasMissing.url="HasMissing@"+agentURL
	
	segs["InputArgs"]=InputArgs=async function(input){//:1IH73KQVI0
		let result,resultText;
		let role="assistant";
		let text=(($ln==="CN")?("完善智能体调用参数:"):("Complete agent arguments:"));
		let template=argsTemplate;
		let data=context.args;
		let edit=true;
		if(typeof(template)==="string"){
			template=VFACT.getEditUITemplate(template)||VFACT.getUITemplate(template);
		}
		let inputVO={template:template,data:data,options:{edit:edit}};
		/*#{1IH73KQVI0Pre*/
		/*}#1IH73KQVI0Pre*/
		[resultText,result]=await session.askUserRaw({type:"object",text:text,data:data,template:template,role:role,edit:edit});
		/*#{1IH73KQVI0Codes*/
		/*}#1IH73KQVI0Codes*/
		return {result:result};
	};
	InputArgs.jaxId="1IH73KQVI0"
	InputArgs.url="InputArgs@"+agentURL
	
	segs["Done"]=Done=async function(input){//:1IH73K4870
		let result=input
		/*#{1IH73K4870Code*/
		/*}#1IH73K4870Code*/
		return {result:result};
	};
	Done.jaxId="1IH73K4870"
	Done.url="Done@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"HubFixArgs",
		url:agentURL,
		autoStart:true,
		jaxId:"1IH730PV10",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{argsTemplate,command}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IH730PV10PreEntry*/
			/*}#1IH730PV10PreEntry*/
			result={seg:CheckCommand,"input":input};
			/*#{1IH730PV10PostEntry*/
			/*}#1IH730PV10PostEntry*/
			return result;
		},
		/*#{1IH730PV10MoreAgentAttrs*/
		/*}#1IH730PV10MoreAgentAttrs*/
	};
	/*#{1IH730PV10PostAgent*/
	/*}#1IH730PV10PostAgent*/
	return agent;
};
/*#{1IH730PV10ExCodes*/
/*}#1IH730PV10ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IH730PV10PostDoc*/
/*}#1IH730PV10PostDoc*/


export default HubFixArgs;
export{HubFixArgs};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IH730PV10",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IH730PV11",
//			"attrs": {
//				"HubFixArgs": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IH730PV20",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IH730PV21",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IH730PV22",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IH730PV23",
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
//			"jaxId": "1IH730PV12",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH730PV13",
//			"attrs": {
//				"argsTemplate": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IH7327JK0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"command": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IH7327JK1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IH730PV14",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IH730PV15",
//			"attrs": {
//				"args": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IH732SAH0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1IH730PV16",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IH73317D0",
//					"attrs": {
//						"id": "CheckCommand",
//						"viewName": "",
//						"label": "New AI Seg",
//						"x": "115",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH73317D1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH73317D2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH73317D3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IH73KQVI0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH73317D4",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH73317D5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH73317D6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "!!command"
//									},
//									"linkedSeg": "1IH73EH360"
//								}
//							]
//						}
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IH73EH360",
//					"attrs": {
//						"id": "GenArgs",
//						"viewName": "",
//						"label": "New AI Seg",
//						"x": "380",
//						"y": "120",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IH73EH361",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH73EH362",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`\n你是一个解析自然语言命令，生成函数调用参数的AI\n- 用户会输入要调用的函数的参数描述以及自然语言命令。\n\n- 函数参数描述是以JSON形式提供，例如\n{\n\t\"name\":{\n\t\t\"name\":\"name\",\"type\":\"string\",\n\t\t\"defaultValue\":\"\",\n\t\t\"desc\":\"User name used in this site.\"\n\t},\n\t\"gender\":{\n\t\t\"name\":\"gender\",\"type\":\"string\",\n\t\t\"defaultValue\":\"Male\",\n\t\t\"desc\":\"User gender.\"\n\t}\n}\n\n- 请根据函数参数JSON，分析用户的自然语言指令，生成调用函数的参数VO，用JSON回答。例如：\n{\n\t\"name\":\"Alex\",\n    \"gender\":\"Male\"\n}\n\n- 如果你无法确定某些参数的内容，请用字符串\"$$MISSING\"作为参数值.例如，如果你不能确定gender属性：：\n{\n\t\"name\":\"Alex\",\n    \"gender\":\"$$MISSING\"\n}\n`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#`\n函数参数JSON：\n${JSON.stringify(argsTemplate.properties,null,\"\\t\")}\n自然语言指令：${command}\n`",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IH73EH363",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH73GIC20"
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
//						"responseFormat": "json_object",
//						"formatDef": "\"\""
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IH73GIC20",
//					"attrs": {
//						"id": "HasMissing",
//						"viewName": "",
//						"label": "New AI Seg",
//						"x": "600",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH73GIC21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH73GIC22",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH73GIC23",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IH73KQVI0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH73GIC30",
//									"attrs": {
//										"id": "NoMissing",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH73GIC31",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH73GIC32",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!hasMissing"
//									},
//									"linkedSeg": "1IH73K4870"
//								}
//							]
//						}
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "askEditObj",
//					"jaxId": "1IH73KQVI0",
//					"attrs": {
//						"id": "InputArgs",
//						"viewName": "",
//						"label": "",
//						"x": "865",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH73KQVI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH73KQVJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"text": {
//							"type": "string",
//							"valText": "Complete agent arguments:",
//							"localize": {
//								"EN": "Complete agent arguments:",
//								"CN": "完善智能体调用参数:"
//							},
//							"localizable": true
//						},
//						"role": "Assistant",
//						"data": "#context.args",
//						"template": "#argsTemplate",
//						"editData": "true",
//						"outlet": {
//							"jaxId": "1IH73KQVJ1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH73K4870",
//					"attrs": {
//						"id": "Done",
//						"viewName": "",
//						"label": "New AI Seg",
//						"x": "865",
//						"y": "105",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IH73K4871",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH73K4872",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH73K4873",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					}
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}