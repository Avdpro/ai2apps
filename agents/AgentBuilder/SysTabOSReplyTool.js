//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IOGGDE4T1MoreImports*/
/*}#1IOGGDE4T1MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
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
		},
		"replyTools":{
			"name":"replyTools","type":"auto",
			"defaultValue":"",
			"desc":"在回答问题的时候，可以调用的工具集",
		}
	},
	/*#{1IOGGDE4T1ArgsView*/
	/*}#1IOGGDE4T1ArgsView*/
};

/*#{1IOGGDE4T1StartDoc*/
/*}#1IOGGDE4T1StartDoc*/
//----------------------------------------------------------------------------
let SysTabOSReplyTool=async function(session){
	let agentDesc,orgInput,agentMem,toolAsk,replyTools;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ToolAsk,ToolAskReuslt,ShowAskAiResult,AskUser,ShowAskUserResult,TryTool,CallTool,ToolError,ReplyTool;
	/*#{1IOGGDE4T1LocalVals*/
	/*}#1IOGGDE4T1LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			agentDesc=input.agentDesc;
			orgInput=input.orgInput;
			agentMem=input.agentMem;
			toolAsk=input.toolAsk;
			replyTools=input.replyTools;
		}else{
			agentDesc=undefined;
			orgInput=undefined;
			agentMem=undefined;
			toolAsk=undefined;
			replyTools=undefined;
		}
		/*#{1IOGGDE4T1ParseArgs*/
		/*}#1IOGGDE4T1ParseArgs*/
	}
	
	/*#{1IOGGDE4T1PreContext*/
	/*}#1IOGGDE4T1PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IOGGDE4T1PostContext*/
	/*}#1IOGGDE4T1PostContext*/
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
		if(input.tool){
			return {result:input};
		}
		if(input.reply){
			let output=input.reply;
			return {seg:ShowAskAiResult,result:(output),preSeg:"1IOGGE5V00",outlet:"1IOGGE5V04"};
		}
		/*#{1IOGGE5V00Post*/
		/*}#1IOGGE5V00Post*/
		return {seg:AskUser,result:(result),preSeg:"1IOGGE5V00",outlet:"1IOGGE5V03"};
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
	
	segs["AskUser"]=AskUser=async function(input){//:1IOGGEM2D0
		let result;
		let arg=input.ask;
		let agentNode=(undefined)||null;
		let sourcePath=pathLib.joinTabOSURL(basePath,"./SysTabOSAskUser.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:ShowAskUserResult,result:(result),preSeg:"1IOGGEM2D0",outlet:"1IOGGEM2E0"};
	};
	AskUser.jaxId="1IOGGEM2D0"
	AskUser.url="AskUser@"+agentURL
	
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
	
	segs["TryTool"]=TryTool=async function(input){//:1IQ1L2H7R0
		let result=input;
		/*#{1IQ1L2H7R0Code*/
		false
		/*}#1IQ1L2H7R0Code*/
		return {seg:CallTool,result:(result),preSeg:"1IQ1L2H7R0",outlet:"1IQ1M8SJL1",catchSeg:ToolError,catchlet:"1IQ1M8SJL2"};
	};
	TryTool.jaxId="1IQ1L2H7R0"
	TryTool.url="TryTool@"+agentURL
	
	segs["CallTool"]=CallTool=async function(input){//:1IQ1L30VS0
		let result=input
		let outlets={
			Ask: ReplyTool
		};
		/*#{1IQ1L30VS0Code*/
		/*}#1IQ1L30VS0Code*/
		return {seg:ToolAsk,result:(result),preSeg:"1IQ1L30VS0",outlet:"1IQ1M8SJL3"};
	};
	CallTool.jaxId="1IQ1L30VS0"
	CallTool.url="CallTool@"+agentURL
	
	segs["ToolError"]=ToolError=async function(input){//:1IQ1L4S510
		let result=input
		/*#{1IQ1L4S510Code*/
		result=`执行工具出错：`+input;
		/*}#1IQ1L4S510Code*/
		return {seg:ToolAsk,result:(result),preSeg:"1IQ1L4S510",outlet:"1IQ1M8SJM0"};
	};
	ToolError.jaxId="1IQ1L4S510"
	ToolError.url="ToolError@"+agentURL
	
	segs["ReplyTool"]=ReplyTool=async function(input){//:1IQ1NB6PV0
		let result;
		let arg={"agentDesc":agentDesc,"orgInput":orgInput,"agentMem":agentMem,"toolAsk":input,"replyTools":replyTools};
		let agentNode=(undefined)||null;
		let sourcePath=pathLib.joinTabOSURL(basePath,"./SysTabOSReplyTool.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	ReplyTool.jaxId="1IQ1NB6PV0"
	ReplyTool.url="ReplyTool@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"SysTabOSReplyTool",
		url:agentURL,
		autoStart:true,
		jaxId:"1IOGGDE4T1",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{agentDesc,orgInput,agentMem,toolAsk,replyTools}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IOGGDE4T1PreEntry*/
			/*}#1IOGGDE4T1PreEntry*/
			result={seg:ToolAsk,"input":input};
			/*#{1IOGGDE4T1PostEntry*/
			/*}#1IOGGDE4T1PostEntry*/
			return result;
		},
		/*#{1IOGGDE4T1MoreAgentAttrs*/
		/*}#1IOGGDE4T1MoreAgentAttrs*/
	};
	/*#{1IOGGDE4T1PostAgent*/
	/*}#1IOGGDE4T1PostAgent*/
	return agent;
};
/*#{1IOGGDE4T1ExCodes*/
/*}#1IOGGDE4T1ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "SysTabOSReplyTool",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				agentDesc:{type:"auto",description:"智能体功能描述"},
				orgInput:{type:"auto",description:"智能体要完成的用户任务"},
				agentMem:{type:"auto",description:"对话消息记录"},
				toolAsk:{type:"auto",description:"工具提出的问题"},
				replyTools:{type:"auto",description:"在回答问题的时候，可以调用的工具集"}
			}
		}
	},
	agent: SysTabOSReplyTool
}];
//#CodyExport<<<
/*#{1IOGGDE4T1PostDoc*/
/*}#1IOGGDE4T1PostDoc*/


export default SysTabOSReplyTool;
export{SysTabOSReplyTool};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IOGGDE4T1",
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
//		"inBrowser": "true",
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
//					"jaxId": "1IOGH7FSJ0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "工具提出的问题"
//					}
//				},
//				"replyTools": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IQ1KU0RT0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "在回答问题的时候，可以调用的工具集"
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
//						"x": "100",
//						"y": "325",
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
//						"x": "305",
//						"y": "325",
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
//									"jaxId": "1IQ1M8SJL0",
//									"attrs": {
//										"id": "Tool",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IQ1M8SJO0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IQ1M8SJO1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.tool"
//									}
//								},
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
//						"x": "580",
//						"y": "325",
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
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "580",
//						"y": "400",
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
//						"x": "835",
//						"y": "400",
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
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IQ1L2H7R0",
//					"attrs": {
//						"id": "TryTool",
//						"viewName": "",
//						"label": "",
//						"x": "580",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IQ1M8SJO2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQ1M8SJO3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IQ1M8SJL1",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQ1L30VS0"
//						},
//						"catchlet": {
//							"jaxId": "1IQ1M8SJL2",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQ1L4S510"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IQ1L30VS0",
//					"attrs": {
//						"id": "CallTool",
//						"viewName": "",
//						"label": "",
//						"x": "835",
//						"y": "155",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IQ1M8SJO4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQ1M8SJO5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IQ1M8SJL3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQ1NBOFD0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "CodOutlet",
//									"jaxId": "1IQ1M8SJO6",
//									"attrs": {
//										"id": "Ask",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IQ1M8SJO7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IQ1M8SJO8",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IQ1NB6PV0"
//								}
//							]
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IQ1L4S510",
//					"attrs": {
//						"id": "ToolError",
//						"viewName": "",
//						"label": "",
//						"x": "835",
//						"y": "250",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IQ1M8SJO9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQ1M8SJO10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IQ1M8SJM0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQ1LKNIR0"
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
//					"def": "connector",
//					"jaxId": "1IQ1LJCDF0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1235",
//						"y": "40",
//						"outlet": {
//							"jaxId": "1IQ1M8SJO11",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQ1NBOFD0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IQ1LJKGQ0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "125",
//						"y": "40",
//						"outlet": {
//							"jaxId": "1IQ1M8SJO12",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGGDVMN0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IQ1LKNIR0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1200",
//						"y": "250",
//						"outlet": {
//							"jaxId": "1IQ1M8SJO13",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQ1LJCDF0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IQ1NB6PV0",
//					"attrs": {
//						"id": "ReplyTool",
//						"viewName": "",
//						"label": "",
//						"x": "1040",
//						"y": "170",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IQ1NC4A40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQ1NC4A41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysTabOSReplyTool.js",
//						"argument": "{\"agentDesc\":\"#agentDesc\",\"orgInput\":\"#orgInput\",\"agentMem\":\"#agentMem\",\"toolAsk\":\"#input\",\"replyTools\":\"#replyTools\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IQ1NC49U0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IQ1NBOFD0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "965",
//						"y": "40",
//						"outlet": {
//							"jaxId": "1IQ1NC4A42",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQ1LJKGQ0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}