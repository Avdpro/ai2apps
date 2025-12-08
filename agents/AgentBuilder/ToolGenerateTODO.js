//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IP197VEV0MoreImports*/
import {tabNT} from "/@tabos";
import {AATools} from "/@tabos/AATools.js";
/*}#1IP197VEV0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"task":{
			"name":"task","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"需要完成的任务",
		}
	},
	/*#{1IP197VEV0ArgsView*/
	/*}#1IP197VEV0ArgsView*/
};

/*#{1IP197VEV0StartDoc*/
/*}#1IP197VEV0StartDoc*/
//----------------------------------------------------------------------------
let ToolGenerateTODO=async function(session){
	let task;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Generate,InitTools,output;
	/*#{1IP197VEV0LocalVals*/
	/*}#1IP197VEV0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			task=input.task;
		}else{
			task=undefined;
		}
		/*#{1IP197VEV0ParseArgs*/
		/*}#1IP197VEV0ParseArgs*/
	}
	
	/*#{1IP197VEV0PreContext*/
	/*}#1IP197VEV0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IP197VEV0PostContext*/
	/*}#1IP197VEV0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IP197P8O0
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(task===undefined || task==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@aichat/ai/CompleteArgs.js",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:InitTools,result:(result),preSeg:"1IP197P8O0",outlet:"1IP197VF00"};
	};
	FixArgs.jaxId="1IP197P8O0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Generate"]=Generate=async function(input){//:1IP198P8G0
		let prompt;
		let result;
		
		let opts={
			platform:"Claude",
			mode:"claude-3-7-sonnet-latest",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=Generate.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`你是一个专业任务规划AI，擅长将复杂任务分解为可执行的步骤。请按照以下要求生成详细的任务清单：
你目前拥有的可用资源
### 本地工具库 (Tools):
${JSON.stringify(context.toolIndex,null,2)}

### 外部节点库 (Nodes):
${JSON.stringify(context.agentNodes,null,2)}

1. 输出格式必须严格遵循：
\`\`\`markdown
# [任务名称] 任务清单

## 阶段1: [阶段名称]
- [ ] [原子级任务描述]
- [ ] [下一个原子级任务]
...

## 阶段2: [阶段名称]
...
\`\`\`

2. 分解原则：
- 保持你示例中的4级结构（总任务>阶段>主任务>子任务）
- 每个子任务必须是可独立执行的最小单元
- 每个任务都可以通过调用可用的工具完成，不需要人工干预
- 每个任务后表明使用的工具

请直接输出markdown，不要输出其他无关内容。
`
},
		];
		prompt=task;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("Generate@"+agentURL,opts,messages,true);
		return {seg:output,result:(result),preSeg:"1IP198P8G0",outlet:"1IP19928O0"};
	};
	Generate.jaxId="1IP198P8G0"
	Generate.url="Generate@"+agentURL
	
	segs["InitTools"]=InitTools=async function(input){//:1IP1A8JDR0
		let result=input
		/*#{1IP1A8JDR0Code*/
		let tools;
		tools=context.aaTools=new AATools();
		await tools.load();
		context.toolIndex=tools.getToolDescIndex();
		context.toolIndex = Object.entries(context.toolIndex).slice(6);
		context.toolIndex.push(["Tool-Bash", "这是一个用于执行命令行命令的工具，可以用于执行允许的命令行命令，如如解压缩，ls，cd，执行代码文件，git，wget，brew下载等等，请提供合法的可以直接在terminal执行的命令。"]);
		context.toolIndex.push(["Tool-Ask", "这是一个调用大语言模型问答或生成内容的工具，请提供需要询问的问题或者需要生成的内容。"]);
		context.toolIndex = Object.fromEntries(context.toolIndex);
		session.debugLog("Tools index:");
		session.debugLog(context.toolIndex);
		console.log("Tools index:");
		console.log(context.toolIndex);
		
		//Build agentNodes info:
		{
			let res,nodes;
			nodes=context.agentNodes={};
			res=await tabNT.makeCall("AhListAgentNodes",{});
			if(res && res.code===200){
				let list,node;
				list=res.nodes;
				for(node of list){
					if(node.chatEntry){
						nodes[node.name]={
							"descritption":node.description,
							"entry":node.chatEntry,
							"workload":node.workload
						}
				}
				}
			}
			session.debugLog("Nodes index:");
			session.debugLog(context.agentNodes);
			console.log("Nodes index:");
			console.log(nodes);
		}
		
		/*}#1IP1A8JDR0Code*/
		return {seg:Generate,result:(result),preSeg:"1IP1A8JDR0",outlet:"1IP1A9GF20"};
	};
	InitTools.jaxId="1IP1A8JDR0"
	InitTools.url="InitTools@"+agentURL
	
	segs["output"]=output=async function(input){//:1IP1CI0SN0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {result:result};
	};
	output.jaxId="1IP1CI0SN0"
	output.url="output@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolGenerateTODO",
		url:agentURL,
		autoStart:true,
		jaxId:"1IP197VEV0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{task}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IP197VEV0PreEntry*/
			/*}#1IP197VEV0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IP197VEV0PostEntry*/
			/*}#1IP197VEV0PostEntry*/
			return result;
		},
		/*#{1IP197VEV0MoreAgentAttrs*/
		/*}#1IP197VEV0MoreAgentAttrs*/
	};
	/*#{1IP197VEV0PostAgent*/
	/*}#1IP197VEV0PostAgent*/
	return agent;
};
/*#{1IP197VEV0ExCodes*/
/*}#1IP197VEV0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IP197VEV0PostDoc*/
/*}#1IP197VEV0PostDoc*/


export default ToolGenerateTODO;
export{ToolGenerateTODO};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IP197VEV0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IP197VF20",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1IP197VF21",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IP197VF22",
//			"attrs": {
//				"task": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IP198ADS0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "需要完成的任务",
//						"required": "true"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IP197VF23",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IP197VF24",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IP197VF25",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IP197P8O0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "-125",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1IP197VF00",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IP1A8JDR0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IP198P8G0",
//					"attrs": {
//						"id": "Generate",
//						"viewName": "",
//						"label": "",
//						"x": "375",
//						"y": "180",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IP19928P0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IP19928P1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "Claude",
//						"mode": "claude-3-7-sonnet-latest",
//						"system": "#`你是一个专业任务规划AI，擅长将复杂任务分解为可执行的步骤。请按照以下要求生成详细的任务清单：\n你目前拥有的可用资源\n### 本地工具库 (Tools):\n${JSON.stringify(context.toolIndex,null,2)}\n\n### 外部节点库 (Nodes):\n${JSON.stringify(context.agentNodes,null,2)}\n\n1. 输出格式必须严格遵循：\n\\`\\`\\`markdown\n# [任务名称] 任务清单\n\n## 阶段1: [阶段名称]\n- [ ] [原子级任务描述]\n- [ ] [下一个原子级任务]\n...\n\n## 阶段2: [阶段名称]\n...\n\\`\\`\\`\n\n2. 分解原则：\n- 保持你示例中的4级结构（总任务>阶段>主任务>子任务）\n- 每个子任务必须是可独立执行的最小单元\n- 每个任务都可以通过调用可用的工具完成，不需要人工干预\n- 每个任务后表明使用的工具\n\n请直接输出markdown，不要输出其他无关内容。\n`\n",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#task",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IP19928O0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IP1CI0SN0"
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
//					"def": "code",
//					"jaxId": "1IP1A8JDR0",
//					"attrs": {
//						"id": "InitTools",
//						"viewName": "",
//						"label": "",
//						"x": "125",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IP1A9GF70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IP1A9GF71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IP1A9GF20",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IP198P8G0"
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
//					"def": "output",
//					"jaxId": "1IP1CI0SN0",
//					"attrs": {
//						"id": "output",
//						"viewName": "",
//						"label": "",
//						"x": "580",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IP1CI3CN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IP1CI3CN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IP1CI3CJ0",
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
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}