//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IOGGDE4T0MoreImports*/
/*}#1IOGGDE4T0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"agentDesc":{
			"name":"agentDesc","type":"auto",
			"defaultValue":"",
			"desc":"智能体功能描述",
		},
		"orgInput":{
			"name":"orgInput","type":"auto",
			"defaultValue":"",
			"desc":"智能体要完成的用户任务",
		},
		"agentMem":{
			"name":"agentMem","type":"auto",
			"defaultValue":"",
			"desc":"对话消息记录",
		},
		"toolAsk":{
			"name":"toolAsk","type":"auto",
			"defaultValue":"",
			"desc":"工具提出的问题",
		}
	},
	/*#{1IOGGDE4T0ArgsView*/
	/*}#1IOGGDE4T0ArgsView*/
};

/*#{1IOGGDE4T0StartDoc*/
/*}#1IOGGDE4T0StartDoc*/
//----------------------------------------------------------------------------
let SysReplyTool=async function(session){
	let agentDesc,orgInput,agentMem,toolAsk;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ToolAsk,ToolAskReuslt,ShowAskAiResult,ToolAskUser,ShowAskUserResult;
	/*#{1IOGGDE4T0LocalVals*/
	/*}#1IOGGDE4T0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			agentDesc=input.agentDesc;
			orgInput=input.orgInput;
			agentMem=input.agentMem;
			toolAsk=input.toolAsk;
		}else{
			agentDesc=undefined;
			orgInput=undefined;
			agentMem=undefined;
			toolAsk=undefined;
		}
		/*#{1IOGGDE4T0ParseArgs*/
		/*}#1IOGGDE4T0ParseArgs*/
	}
	
	/*#{1IOGGDE4T0PreContext*/
	/*}#1IOGGDE4T0PreContext*/
	context={};
	/*#{1IOGGDE4T0PostContext*/
	/*}#1IOGGDE4T0PostContext*/
	let $agent,agent,segs={};
	segs["ToolAsk"]=ToolAsk=async function(input){//:1IOGGDVMN0
		let prompt;
		let result=null;
		/*#{1IOGGDVMN0Input*/
		let mem;
		let ua=$agent.upperAgent;
		if(ua){
			$agent.showName=ua.showName||ua.name;
		}
		mem=[];
		{
			let i,n,chat,content,line,sub;
			agentMem=agentMem.slice(-9);
			n=agentMem.length;
			for(i=0;i<n-1;i++){
				chat=agentMem[i];
				content=chat.content;
				if(Array.isArray(content)){
					line=""+JSON.stringify(content);
				}else{
					line=""+JSON.stringify(content);
				}
				if(line.length>256){
					line=line.substring(0,256)+"...";
				}
				mem.push({role:chat.role,content:line});
			}
			mem.push(agentMem[n-1]);//Don't compress the last round.
		}
		/*}#1IOGGDVMN0Input*/
		
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
		let chatMem=ToolAsk.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
### 角色
你负责帮助当前智能体，回答其调用的工具提出的问题

### 当前智能体
${agentDesc}

### 当前智能体正在执行的用户任务:
${orgInput.prompt||orgInput}

### 当前智能体调用工具情况
当前智能体的执行过程以及工具的调用情况，经过化简后如下：
\`\`\`
${JSON.stringify(mem,null,"\t")}
\`\`\`

### 对话
用户的输入是正在执行的工具提出的问题，你根据当前智能体的信息，用JSON回复
- 回复的时候请总结当前任务，当前工具执行目的，根据工具的提问以及当前智能体的对话过程，分析答案，并把思考过程写在回复JSON的"think"属性内。
- 如果根据当前的信息，你可以回答问题，请把你的回答放在回复JSON的"reply"属性中。例如：
	\`\`\`
		{
        	"think": "用户任务是查询股票信息并绘制图表。当前调用工具查询股票几个信息。工具询问文件输出格式，应该是为了下一步绘制收集数据。通常在智能体之间交换数据使用csv或者json多一些。这里虽然也可以使用json格式，但使用csv格式最为通用。"
			"reply":"请用.csv格式输出数据。"
		}
	\`\`\`

- 如果根据当前的信息，你无法做出明确回答，请把回复智能体的"reply"属性设置为null。例如：
	\`\`\`
		{
        	"think": "用户任务是查询股票信息并绘制图表。当前调用工具查询股价信息。工具询问查询股价的API-Key。从当前智能体执行情况来看，我不知道可以有使用的API-Key，无法做出回答"
			"reply":null
		}
	\`\`\`


- 为了减少打扰用户，请尽量做出回答。

### 回复JSON参数
- "think" {string}: 你的思考过程
- "reply" {string}: 你的回答，如果无法回答，设置为null
`},
		];
		/*#{1IOGGDVMN0PrePrompt*/
		/*}#1IOGGDVMN0PrePrompt*/
		prompt=toolAsk;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IOGGDVMN0FilterMessage*/
			/*}#1IOGGDVMN0FilterMessage*/
			messages.push(msg);
		}
		/*#{1IOGGDVMN0PreCall*/
		/*}#1IOGGDVMN0PreCall*/
		result=(result===null)?(await session.callSegLLM("ToolAsk@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IOGGDVMN0PostCall*/
		result.ask=toolAsk;
		/*}#1IOGGDVMN0PostCall*/
		return {seg:ToolAskReuslt,result:(result),preSeg:"1IOGGDVMN0",outlet:"1IOGGDVMO2"};
	};
	ToolAsk.jaxId="1IOGGDVMN0"
	ToolAsk.url="ToolAsk@"+agentURL
	
	segs["ToolAskReuslt"]=ToolAskReuslt=async function(input){//:1IOGGE5V00
		let result=input;
		/*#{1IOGGE5V00Start*/
		/*}#1IOGGE5V00Start*/
		if(input.reply){
			let output=input.reply;
			return {seg:ShowAskAiResult,result:(output),preSeg:"1IOGGE5V00",outlet:"1IOGGE5V04"};
		}
		/*#{1IOGGE5V00Post*/
		/*}#1IOGGE5V00Post*/
		return {seg:ToolAskUser,result:(result),preSeg:"1IOGGE5V00",outlet:"1IOGGE5V03"};
	};
	ToolAskReuslt.jaxId="1IOGGE5V00"
	ToolAskReuslt.url="ToolAskReuslt@"+agentURL
	
	segs["ShowAskAiResult"]=ShowAskAiResult=async function(input){//:1IOGGEDD20
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=input;
		/*#{1IOGGEDD20PreCodes*/
		opts.icon="/~/-tabos/shared/assets/arrowright.svg";
		opts.txtHeader+=(($ln==="CN")?(" 答复:"):/*EN*/(" reply:"));
		opts.iconSize=24;
		opts.fontSize=12;
		/*}#1IOGGEDD20PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IOGGEDD20PostCodes*/
		/*}#1IOGGEDD20PostCodes*/
		return {result:result};
	};
	ShowAskAiResult.jaxId="1IOGGEDD20"
	ShowAskAiResult.url="ShowAskAiResult@"+agentURL
	
	segs["ToolAskUser"]=ToolAskUser=async function(input){//:1IOGGEM2D0
		let result;
		let arg=input.ask;
		let agentNode=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./SysTabOSAskUser.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:ShowAskUserResult,result:(result),preSeg:"1IOGGEM2D0",outlet:"1IOGGEM2E0"};
	};
	ToolAskUser.jaxId="1IOGGEM2D0"
	ToolAskUser.url="ToolAskUser@"+agentURL
	
	segs["ShowAskUserResult"]=ShowAskUserResult=async function(input){//:1IOGGF7O00
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=input;
		/*#{1IOGGF7O00PreCodes*/
		opts.icon="/~/-tabos/shared/assets/arrowright.svg";
		opts.txtHeader+=(($ln==="CN")?(" 答复:"):/*EN*/(" reply:"));
		opts.iconSize=24;
		opts.fontSize=12;
		/*}#1IOGGF7O00PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IOGGF7O00PostCodes*/
		/*}#1IOGGF7O00PostCodes*/
		return {result:result};
	};
	ShowAskUserResult.jaxId="1IOGGF7O00"
	ShowAskUserResult.url="ShowAskUserResult@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"SysReplyTool",
		url:agentURL,
		autoStart:true,
		jaxId:"1IOGGDE4T0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{agentDesc,orgInput,agentMem,toolAsk}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IOGGDE4T0PreEntry*/
			/*}#1IOGGDE4T0PreEntry*/
			result={seg:ToolAsk,"input":input};
			/*#{1IOGGDE4T0PostEntry*/
			/*}#1IOGGDE4T0PostEntry*/
			return result;
		},
		/*#{1IOGGDE4T0MoreAgentAttrs*/
		/*}#1IOGGDE4T0MoreAgentAttrs*/
	};
	/*#{1IOGGDE4T0PostAgent*/
	/*}#1IOGGDE4T0PostAgent*/
	return agent;
};
/*#{1IOGGDE4T0ExCodes*/
/*}#1IOGGDE4T0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "SysReplyTool",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				agentDesc:{type:"auto",description:"智能体功能描述"},
				orgInput:{type:"auto",description:"智能体要完成的用户任务"},
				agentMem:{type:"auto",description:"对话消息记录"},
				toolAsk:{type:"auto",description:"工具提出的问题"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IOGGDE4T0PostDoc*/
/*}#1IOGGDE4T0PostDoc*/


export default SysReplyTool;
export{SysReplyTool,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IOGGDE4T0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IOGGDE4T1",
//			"attrs": {
//				"SysReplyTool": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IOGGDE4T7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IOGGDE4T8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IOGGDE4T9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IOGGDE4T10",
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
//			"jaxId": "1IOGGDE4T2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IOGGDE4T3",
//			"attrs": {
//				"agentDesc": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOGGHL440",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "智能体功能描述"
//					}
//				},
//				"orgInput": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOGGHL441",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "智能体要完成的用户任务"
//					}
//				},
//				"agentMem": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOGGHL442",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "对话消息记录"
//					}
//				},
//				"toolAsk": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOGHRB2A0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "工具提出的问题"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IOGGDE4T4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IOGGDE4T5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IOGGDE4T6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IOGGDVMN0",
//					"attrs": {
//						"id": "ToolAsk",
//						"viewName": "",
//						"label": "",
//						"x": "115",
//						"y": "185",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IOGGDVMO0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGGDVMO1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`\n### 角色\n你负责帮助当前智能体，回答其调用的工具提出的问题\n\n### 当前智能体\n${agentDesc}\n\n### 当前智能体正在执行的用户任务:\n${orgInput.prompt||orgInput}\n\n### 当前智能体调用工具情况\n当前智能体的执行过程以及工具的调用情况，经过化简后如下：\n\\`\\`\\`\n${JSON.stringify(mem,null,\"\\t\")}\n\\`\\`\\`\n\n### 对话\n用户的输入是正在执行的工具提出的问题，你根据当前智能体的信息，用JSON回复\n- 回复的时候请总结当前任务，当前工具执行目的，根据工具的提问以及当前智能体的对话过程，分析答案，并把思考过程写在回复JSON的\"think\"属性内。\n- 如果根据当前的信息，你可以回答问题，请把你的回答放在回复JSON的\"reply\"属性中。例如：\n\t\\`\\`\\`\n\t\t{\n        \t\"think\": \"用户任务是查询股票信息并绘制图表。当前调用工具查询股票几个信息。工具询问文件输出格式，应该是为了下一步绘制收集数据。通常在智能体之间交换数据使用csv或者json多一些。这里虽然也可以使用json格式，但使用csv格式最为通用。\"\n\t\t\t\"reply\":\"请用.csv格式输出数据。\"\n\t\t}\n\t\\`\\`\\`\n\n- 如果根据当前的信息，你无法做出明确回答，请把回复智能体的\"reply\"属性设置为null。例如：\n\t\\`\\`\\`\n\t\t{\n        \t\"think\": \"用户任务是查询股票信息并绘制图表。当前调用工具查询股价信息。工具询问查询股价的API-Key。从当前智能体执行情况来看，我不知道可以有使用的API-Key，无法做出回答\"\n\t\t\t\"reply\":null\n\t\t}\n\t\\`\\`\\`\n\n\n- 为了减少打扰用户，请尽量做出回答。\n\n### 回复JSON参数\n- \"think\" {string}: 你的思考过程\n- \"reply\" {string}: 你的回答，如果无法回答，设置为null\n`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#toolAsk",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IOGGDVMO2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGGE5V00"
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
//					"jaxId": "1IOGGE5V00",
//					"attrs": {
//						"id": "ToolAskReuslt",
//						"viewName": "",
//						"label": "",
//						"x": "335",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGGE5V01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGGE5V02",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOGGE5V03",
//							"attrs": {
//								"id": "AskUser",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IOGGEM2D0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IOGGE5V04",
//									"attrs": {
//										"id": "Reply",
//										"desc": "输出节点。",
//										"output": "#input.reply",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOGGE5V05",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOGGE5V06",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.reply"
//									},
//									"linkedSeg": "1IOGGEDD20"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IOGGEDD20",
//					"attrs": {
//						"id": "ShowAskAiResult",
//						"viewName": "",
//						"label": "",
//						"x": "600",
//						"y": "130",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGGEDD30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGGEDD31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IOGGEDD32",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IOGGEM2D0",
//					"attrs": {
//						"id": "ToolAskUser",
//						"viewName": "",
//						"label": "",
//						"x": "600",
//						"y": "235",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGGEM2D1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGGEM2D2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysTabOSAskUser.js",
//						"argument": "#{}#>input.ask",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IOGGEM2E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGGF7O00"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IOGGF7O00",
//					"attrs": {
//						"id": "ShowAskUserResult",
//						"viewName": "",
//						"label": "",
//						"x": "840",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGGF7O01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGGF7O02",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IOGGF7O03",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}