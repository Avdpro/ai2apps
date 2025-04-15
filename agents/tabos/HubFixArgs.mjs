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
		},
		"smartAsk":{
			"name":"smartAsk","type":"bool",
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
	let argsTemplate,command,smartAsk;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let CheckCommand,GenArgs,HasMissing,InputArgs,Done,CheckSmart,SmartCheck,SmartMissing,AskUpward;
	/*#{1IH730PV10LocalVals*/
	/*}#1IH730PV10LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			argsTemplate=input.argsTemplate;
			command=input.command;
			smartAsk=input.smartAsk;
		}else{
			argsTemplate=undefined;
			command=undefined;
			smartAsk=undefined;
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
	let $agent,agent,segs={};
	segs["CheckCommand"]=CheckCommand=async function(input){//:1IH73317D0
		let result=input;
		/*#{1IH73317D0Start*/
		let ua=$agent.upperAgent;
		if(ua){
			$agent.showName=ua.showName||ua.name;
		}
		/*}#1IH73317D0Start*/
		if(!!command){
			return {seg:CheckSmart,result:(input),preSeg:"1IH73317D0",outlet:"1IH73317D4"};
		}
		/*#{1IH73317D0Post*/
		/*}#1IH73317D0Post*/
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
${typeof(command)==="string"?("自然语言指令："+command):"指令JSON表达："+JSON.stringify(command)}
`;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IH73EH360FilterMessage*/
			/*}#1IH73EH360FilterMessage*/
			messages.push(msg);
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
	
	segs["CheckSmart"]=CheckSmart=async function(input){//:1IOCA6NNO0
		let result=input;
		if(!!smartAsk){
			let output="请分析并用JSON给出函数调用参数或给出提问内容。";
			return {seg:SmartCheck,result:(output),preSeg:"1IOCA6NNO0",outlet:"1IOCAC6N80"};
		}
		return {seg:GenArgs,result:(result),preSeg:"1IOCA6NNO0",outlet:"1IOCAC6N90"};
	};
	CheckSmart.jaxId="1IOCA6NNO0"
	CheckSmart.url="CheckSmart@"+agentURL
	
	segs["SmartCheck"]=SmartCheck=async function(input){//:1IOCAJ6EI0
		let prompt;
		let result;
		
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
		let chatMem=SmartCheck.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
### 角色
你是一个解析自然语言命令，生成函数调用参数的AI
- 用户会输入要调用的函数的参数描述以及自然语言命令。

### 函数参数
- 当前函数参数的JSON定义是：
\`\`\`
${JSON.stringify(argsTemplate.properties,null,"\t")}
\`\`\`

${typeof(command)==="string"?("### 用户初始输入的自然语言的调用指令\n"+command):"### 调用指令的JSON表达："+JSON.stringify(command)}

### 对话
- 在每一轮对话中，请分析根据输入的调用指令以及当前对话过程，是否可以给出符合要求的完整函数调用参数

- 你必须用JSON格式做出回复

- 如果当前信息可以给出完整的函数调用参数，请在返回JSON中的"arguments"属性中给出当前函数参数。例如：
\`\`\`
{
	"arguments":{
		"name":"Alex",
    	"gender":"Male"
    }
}
\`\`\`

- 如果当前信息无法给出完整的函数调用参数，请在返回JSON中的"ask"属性中给出向用户提问补全信息的问题。你的问题应该明确详细，包括缺失参数的简单说明，请用用户容易理解的自然语言提问。例如：
\`\`\`
{
	"ask":"请提供要查询的用户的电子邮箱地址，用户的性别，以及用户的年龄范围。"
}
\`\`\`

- 提问后收到用户回复后，根据当前对话信息，如果不足以返回完整的调用参数，请继续向用户提问，直到返回完整函数调用信息为止。

### 返回JSON属性
- "arguments" optional, {object}: 完整的函数调用参数列表，其中每一项属性的名称是对应的参数名称，内容是参数的值。
- "ask" optional, {string}: 向用户提问的内容。
`},
		];
		messages.push(...chatMem);
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("SmartCheck@"+agentURL,opts,messages,true);
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>20){
			let removedMsgs=chatMem.splice(0,2);
		}
		result=trimJSON(result);
		return {seg:SmartMissing,result:(result),preSeg:"1IOCAJ6EI0",outlet:"1IOCAL79L0"};
	};
	SmartCheck.jaxId="1IOCAJ6EI0"
	SmartCheck.url="SmartCheck@"+agentURL
	SmartCheck.messages=[];
	
	segs["SmartMissing"]=SmartMissing=async function(input){//:1IOCAK22S0
		let result=input;
		/*#{1IOCAK22S0Start*/
		/*}#1IOCAK22S0Start*/
		if(!!input.ask){
			let output=input.ask;
			return {seg:AskUpward,result:(output),preSeg:"1IOCAK22S0",outlet:"1IOCAL79L1"};
		}
		/*#{1IOCAK22S0Post*/
		result=input.arguments;
		/*}#1IOCAK22S0Post*/
		return {seg:Done,result:(result),preSeg:"1IOCAK22S0",outlet:"1IOCAL79L2"};
	};
	SmartMissing.jaxId="1IOCAK22S0"
	SmartMissing.url="SmartMissing@"+agentURL
	
	segs["AskUpward"]=AskUpward=async function(input){//:1IOCALSVS0
		let tip=(input);
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let askUpward=(true);
		let text=("");
		let result="";
		if(askUpward && tip){
			result=await session.askUpward($agent,tip);
		}else{
			if(tip){
				session.addChatText(tipRole,tip);
			}
			result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		}
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		return {seg:SmartCheck,result:(result),preSeg:"1IOCALSVS0",outlet:"1IOCAMJIN0"};
	};
	AskUpward.jaxId="1IOCALSVS0"
	AskUpward.url="AskUpward@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"HubFixArgs",
		url:agentURL,
		autoStart:true,
		jaxId:"1IH730PV10",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{argsTemplate,command,smartAsk}*/){
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
//		"showName": "",
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
//				},
//				"smartAsk": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOCA5BNS0",
//					"attrs": {
//						"type": "Boolean",
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
//						"x": "95",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
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
//									"linkedSeg": "1IOCA6NNO0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IH73EH360",
//					"attrs": {
//						"id": "GenArgs",
//						"viewName": "",
//						"label": "New AI Seg",
//						"x": "610",
//						"y": "300",
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
//						"prompt": "#`\n函数参数JSON：\n${JSON.stringify(argsTemplate.properties,null,\"\\t\")}\n${typeof(command)===\"string\"?(\"自然语言指令：\"+command):\"指令JSON表达：\"+JSON.stringify(command)}\n`",
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
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IH73GIC20",
//					"attrs": {
//						"id": "HasMissing",
//						"viewName": "",
//						"label": "New AI Seg",
//						"x": "855",
//						"y": "300",
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
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askEditObj",
//					"jaxId": "1IH73KQVI0",
//					"attrs": {
//						"id": "InputArgs",
//						"viewName": "",
//						"label": "",
//						"x": "1120",
//						"y": "400",
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
//					},
//					"icon": "rename.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH73K4870",
//					"attrs": {
//						"id": "Done",
//						"viewName": "",
//						"label": "New AI Seg",
//						"x": "1120",
//						"y": "285",
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
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IOCA6NNO0",
//					"attrs": {
//						"id": "CheckSmart",
//						"viewName": "",
//						"label": "",
//						"x": "360",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOCAC6NA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOCAC6NA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOCAC6N90",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IH73EH360"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IOCAC6N80",
//									"attrs": {
//										"id": "Smart",
//										"desc": "输出节点。",
//										"output": "请分析并用JSON给出函数调用参数或给出提问内容。",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOCAC6NA2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOCAC6NA3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!smartAsk"
//									},
//									"linkedSeg": "1IOCAJ6EI0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IOCAJ6EI0",
//					"attrs": {
//						"id": "SmartCheck",
//						"viewName": "",
//						"label": "",
//						"x": "610",
//						"y": "185",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOCAL79O0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOCAL79O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`\n### 角色\n你是一个解析自然语言命令，生成函数调用参数的AI\n- 用户会输入要调用的函数的参数描述以及自然语言命令。\n\n### 函数参数\n- 当前函数参数的JSON定义是：\n\\`\\`\\`\n${JSON.stringify(argsTemplate.properties,null,\"\\t\")}\n\\`\\`\\`\n\n${typeof(command)===\"string\"?(\"### 用户初始输入的自然语言的调用指令\\n\"+command):\"### 调用指令的JSON表达：\"+JSON.stringify(command)}\n\n### 对话\n- 在每一轮对话中，请分析根据输入的调用指令以及当前对话过程，是否可以给出符合要求的完整函数调用参数\n\n- 你必须用JSON格式做出回复\n\n- 如果当前信息可以给出完整的函数调用参数，请在返回JSON中的\"arguments\"属性中给出当前函数参数。例如：\n\\`\\`\\`\n{\n\t\"arguments\":{\n\t\t\"name\":\"Alex\",\n    \t\"gender\":\"Male\"\n    }\n}\n\\`\\`\\`\n\n- 如果当前信息无法给出完整的函数调用参数，请在返回JSON中的\"ask\"属性中给出向用户提问补全信息的问题。你的问题应该明确详细，包括缺失参数的简单说明，请用用户容易理解的自然语言提问。例如：\n\\`\\`\\`\n{\n\t\"ask\":\"请提供要查询的用户的电子邮箱地址，用户的性别，以及用户的年龄范围。\"\n}\n\\`\\`\\`\n\n- 提问后收到用户回复后，根据当前对话信息，如果不足以返回完整的调用参数，请继续向用户提问，直到返回完整函数调用信息为止。\n\n### 返回JSON属性\n- \"arguments\" optional, {object}: 完整的函数调用参数列表，其中每一项属性的名称是对应的参数名称，内容是参数的值。\n- \"ask\" optional, {string}: 向用户提问的内容。\n`",
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
//							"jaxId": "1IOCAL79L0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOCAK22S0"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "20 messages",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IOCAK22S0",
//					"attrs": {
//						"id": "SmartMissing",
//						"viewName": "",
//						"label": "",
//						"x": "855",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOCAL79O2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOCAL79O3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOCAL79L2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IH73K4870"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IOCAL79L1",
//									"attrs": {
//										"id": "Ask",
//										"desc": "输出节点。",
//										"output": "#input.ask",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOCAL79O4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOCAL79O5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!input.ask"
//									},
//									"linkedSeg": "1IOCALSVS0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IOCALSVS0",
//					"attrs": {
//						"id": "AskUpward",
//						"viewName": "",
//						"label": "",
//						"x": "1120",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOCAMJIQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOCAMJIQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#input",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "true",
//						"outlet": {
//							"jaxId": "1IOCAMJIN0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOCAMUM00"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IOCAMUM00",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1265",
//						"y": "75",
//						"outlet": {
//							"jaxId": "1IOCANA2G0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOCAN2R70"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IOCAN2R70",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "640",
//						"y": "75",
//						"outlet": {
//							"jaxId": "1IOCANA2G1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOCAJ6EI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}