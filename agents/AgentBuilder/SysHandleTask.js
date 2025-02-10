//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IH8PO9RT0MoreImports*/
import AATools from "../../agenthub/AATools.mjs";
import AATask from "./Task.js";
/*}#1IH8PO9RT0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"task":{
			"name":"task","type":"auto",
			"required":false,
			"defaultValue":"",
			"desc":"指导任务，如不为空，则无需重新创建task",
		},
		"roleTask":{
			"name":"roleTask","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"执行任务的角色设定和任务目标描述",
		},
		"prjDesc":{
			"name":"prjDesc","type":"string",
			"defaultValue":"",
			"desc":"当前项目相关信息的说明",
		},
		"guide":{
			"name":"guide","type":"string",
			"defaultValue":"",
			"desc":"指导完成任务的参考文档。",
		},
		"tools":{
			"name":"tools","type":"auto",
			"required":false,
			"defaultValue":"",
			"desc":"可以调用的Tool的文件路径数组",
		},
		"handleIssue":{
			"name":"handleIssue","type":"bool",
			"required":false,
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IH8PO9RT0ArgsView*/
	/*}#1IH8PO9RT0ArgsView*/
};

/*#{1IH8PO9RT0StartDoc*/
/*}#1IH8PO9RT0StartDoc*/
//----------------------------------------------------------------------------
let SysHandleTask=async function(session){
	let task,roleTask,prjDesc,guide,tools,handleIssue;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let InitTask,InitTools,GenStep,ShowStep,StepAction,RunCommand,HandleIssue,CallTool,FInish,Abort,FailTask,CheckHandle,ReportIssue,AskUser,AskEnd;
	let env=globalContext.env;
	let project=globalContext.project;
	let config=session.agentNode.nodeJSON;
	let ownTask=false;
	let bash=globalContext.getBash(globalContext.bash);
	let curPath="";
	
	/*#{1IH8PO9RT0LocalVals*/
	/*}#1IH8PO9RT0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			task=input.task;
			roleTask=input.roleTask;
			prjDesc=input.prjDesc;
			guide=input.guide;
			tools=input.tools;
			handleIssue=input.handleIssue;
		}else{
			task=undefined;
			roleTask=undefined;
			prjDesc=undefined;
			guide=undefined;
			tools=undefined;
			handleIssue=undefined;
		}
		/*#{1IH8PO9RT0ParseArgs*/
		/*}#1IH8PO9RT0ParseArgs*/
	}
	
	/*#{1IH8PO9RT0PreContext*/
	/*}#1IH8PO9RT0PreContext*/
	context={};
	/*#{1IH8PO9RT0PostContext*/
	/*}#1IH8PO9RT0PostContext*/
	let agent,segs={};
	segs["InitTask"]=InitTask=async function(input){//:1IHCCNP8H0
		let result=input;
		/*#{1IHCCNP8H0Code*/
		if(task==="CURRENT"){
			task=globalContext.curTask;
			ownTask=false;
		}else{
			task=task||"Task";
			if(!(task instanceof AATask)){
				task=new AATask(session,task,guide);
				ownTask=true;
			}
			task.setReportCallback((task,content)=>{
				GenStep.messages.push({
					role:"user",
					content:JSON.stringify({progress:content})
				});
			});
		}
		/*}#1IHCCNP8H0Code*/
		return {seg:InitTools,result:(result),preSeg:"1IHCCNP8H0",outlet:"1IHCCPIKQ0",catchSeg:FailTask,catchlet:"1IHCCPIKQ1"};
	};
	InitTask.jaxId="1IHCCNP8H0"
	InitTask.url="InitTask@"+agentURL
	
	segs["InitTools"]=InitTools=async function(input){//:1IH8QTK050
		let result=input
		/*#{1IH8QTK050Code*/
		if(tools){
			let toolsPath;
			toolsPath=tools;
			tools=new AATools(session,basePath);
			await tools.load(toolsPath);
		}
		result="开始执行";
		/*}#1IH8QTK050Code*/
		return {seg:GenStep,result:(result),preSeg:"1IH8QTK050",outlet:"1IH8QUPFU0"};
	};
	InitTools.jaxId="1IH8QTK050"
	InitTools.url="InitTools@"+agentURL
	
	segs["GenStep"]=GenStep=async function(input){//:1IH8QU7ER0
		let prompt;
		let result=null;
		/*#{1IH8QU7ER0Input*/
		curPath=await bash.cwd();
		/*}#1IH8QU7ER0Input*/
		
		let opts={
			platform:"",
			mode:"$plan",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:{
				"type":"json_schema",
				"json_schema":{
					"name":"TaskStep",
					"schema":{
						"type":"object",
						"description":"执行任务的步骤/输出",
						"properties":{
							"action":{
								"type":"string",
								"description":"下一步的步骤动作",
								"enum":[
									"Command","Tool","Chat","Issue","Finish","Abort"
								]
							},
							"content":{
								"type":"string",
								"description":"该步骤的说明"
							},
							"commands":{
								"type":"array",
								"description":"这个步骤要执行的命令行指令数组，如果没有要执行的指令，设置为空数组。",
								"items":{
									"type":"string"
								}
							},
							"issue":{
								"type":[
									"string","null"
								],
								"description":"当\"action\"属性为\"Issue\"时，对问题的详细描述和查询内容。"
							},
							"issueBrief":{
								"type":[
									"string","null"
								]
							},
							"tool":{
								"type":[
									"string","null"
								],
								"description":"要调用的外部工具/AI智能体名称"
							},
							"toolArg":{
								"type":[
									"string","null"
								],
								"description":"调用的外部工具的参数/自然语言任务描述"
							},
							"assets":{
								"type":"array",
								"description":"如果该步骤包含给用户的附件文件，这个数组里是文件URL/路径列表。如果没有附件，设置为空数组。",
								"items":{
									"type":"string"
								}
							}
						},
						"required":[
							"action","content","commands","issue","issueBrief","tool","toolArg","assets"
						],
						"additionalProperties":false
					},
					"strict":true
				}
			}
		};
		let chatMem=GenStep.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
---
### 角色/任务
${roleTask}

---
### 环境和项目
当前的系统软硬件环境和系统参数为：
\`\`\`
${JSON.stringify(env,null,"\t")}
\`\`\`

用于工作的命令行Terminal的当前路径是：  
${curPath}

当前的项目是：${project.name}。
${prjDesc}
${project.dirPath?`当前项目所在的文件路径是: "${project.dirPath}"。`:""}  

当前项目工作进展：  
-${project.progress.join(" \n\n- ")}

${project.conda?`注意：当前已经为工程创建/选择了conda环境：${project.conda}, 正常情况下，不需要创建新的conda环境。`:""}

---
### 参考资料：
${guide?guide:"暂无。"}

${tools?`---\n### 外部工具/智能体: \n执行任务的时候可能需要调用外部的工具/AI智能体，当前可以调用的工具/AI智能体有:\n\`\`\`\n${JSON.stringify(tools.getScope(),null,"\t")}\n\`\`\`\n`:""}
---
### 对话
每一轮对话，你根据当前的步骤执行情况和用户反馈，生成下一个步骤要执行或与用户沟通的内容，并用JSON格式返回。

---
### 返回的JSON对象属性说明：

- 属性"action": {string}, 下一步的动作。可取值：
	- "Cammand": 通过命令行执行操作，比如用pip安装依赖库，拷贝文件，下载模型等
    ${tools?`- "Tool": 调用外部工具完成特定任务，调用的工具名称放在'tool'属性里， 调用的参数/描述放在'toolArg'属性里`:""}
    - "Chat": 需要用户辅助时，与用户对话，提示需要用户手动进行的动作，例如：询问API-Key；登陆环境；提升当前权限(sudo)等，其它时候尽量避免打扰用户。
    - "Finish": 如果当前任务已完成，结束任务，在"content"属性里设置任务结束总结
    - "Issue": 如果执行步骤遇到问题，针对遇到的问题查询RAG知识库，获取解决方案，解决问题，在"content"属性里表述问题。
    - "Abort": 如果遇到无法解决问题，（例如或者当前的硬件环境无法满足项目需求）终止任务。

- 属性"commands": {array<string>}，当"action"为"Command"时，要执行的bash命令数组。
    - 为防止错过纠正问题的机会，一次不要执行太多的命令，
    - 你生成的必须是可以执行的bash命令
    - 如果要下载AI的模型文件，优先使用huggingface命令行工具，而不是git

- 属性"issueBrief": {string}, 当"action"为"Issue"时，对问题的简短概括描述，相当于是问题的标题
- 属性"issue": {string}, 当"action"为"Issue"时，对问题的详细描述，以及要进行查询的内容

- 属性"content": {string}, 当前步骤的解释描述。例如当"action"为"Abort"时，终止原因的说明；当"action"为"Finish"时，对任务执行情况的完成总结；当"action"为"Issue"时，问题的详细描述。

${tools?`- 属性"tool": 要调用的外部工具名称\n`:""}
${tools?`- 属性"toolArg": 调用的外部工具的参数/自然语言任务描述，例如："将README.md翻译为中文。\n"`:""}
- 属性"assets": {array<url>}, 当前步骤产生的需要告知用户的附加，例如图片，文档等的链接的数组

`},
		];
		messages.push(...chatMem);
		/*#{1IH8QU7ER0PrePrompt*/
		/*}#1IH8QU7ER0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		/*#{1IH8QU7ER0PreCall*/
		/*}#1IH8QU7ER0PreCall*/
		result=(result===null)?(await session.callSegLLM("GenStep@"+agentURL,opts,messages,true)):result;
		/*#{1IH8QU7ER0PostLLM*/
		/*}#1IH8QU7ER0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1IH8QU7ER0PostClear*/
			/*}#1IH8QU7ER0PostClear*/
		}
		result=trimJSON(result);
		/*#{1IH8QU7ER0PostCall*/
		/*}#1IH8QU7ER0PostCall*/
		return {seg:ShowStep,result:(result),preSeg:"1IH8QU7ER0",outlet:"1IH8QUPFU1"};
	};
	GenStep.jaxId="1IH8QU7ER0"
	GenStep.url="GenStep@"+agentURL
	GenStep.messages=[];
	
	segs["ShowStep"]=ShowStep=async function(input){//:1IH8QV5R20
		let result=input;
		let opts={};
		let role="assistant";
		let content=input.content;
		session.addChatText(role,content,opts);
		return {seg:StepAction,result:(result),preSeg:"1IH8QV5R20",outlet:"1IH8QVHH70"};
	};
	ShowStep.jaxId="1IH8QV5R20"
	ShowStep.url="ShowStep@"+agentURL
	
	segs["StepAction"]=StepAction=async function(input){//:1IH8R008S0
		let result=input;
		if(input.action==="Command"){
			let output=input;
			return {seg:RunCommand,result:(output),preSeg:"1IH8R008S0",outlet:"1IH8R008S4"};
		}
		if(input.action==="Tool"){
			return {seg:CallTool,result:(input),preSeg:"1IH8R008S0",outlet:"1IH8R008S10"};
		}
		if(input.action==="Chat"){
			let output=input;
			return {seg:AskUser,result:(output),preSeg:"1IH8R008S0",outlet:"1IH8R008T7"};
		}
		if(input.action==="Issue"){
			return {seg:CheckHandle,result:(input),preSeg:"1IH8R008S0",outlet:"1IH8R008S7"};
		}
		if(input.action==="Finish"){
			return {seg:FInish,result:(input),preSeg:"1IH8R008S0",outlet:"1IH8R008T4"};
		}
		if(input.action==="Abort"){
			return {seg:Abort,result:(input),preSeg:"1IH8R008S0",outlet:"1IH8R008T1"};
		}
		return {result:result};
	};
	StepAction.jaxId="1IH8R008S0"
	StepAction.url="StepAction@"+agentURL
	
	segs["RunCommand"]=RunCommand=async function(input){//:1IH8R0HGL0
		let result;
		let sourcePath=pathLib.join(basePath,"./ToolBashCommand.js");
		let arg={"commands":input.commands};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:GenStep,result:(result),preSeg:"1IH8R0HGL0",outlet:"1IH8R0HGM0"};
	};
	RunCommand.jaxId="1IH8R0HGL0"
	RunCommand.url="RunCommand@"+agentURL
	
	segs["HandleIssue"]=HandleIssue=async function(input){//:1IH8R1AP00
		let result;
		let sourcePath=pathLib.join(basePath,"./SysHandleIssue.js");
		let arg={"issue":input.issue||input.content,"issueBrief":input.issueBrief||""};
		/*#{1IH8R1AP00Input*/
		/*}#1IH8R1AP00Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IH8R1AP00Output*/
		if(result.result==="Finish"){//
			result.result="Resolved"
			result=`问题已解决\n\n解决说明: ${input.content}\n\n请继续执行任务。`;
		}
		/*}#1IH8R1AP00Output*/
		return {seg:GenStep,result:(result),preSeg:"1IH8R1AP00",outlet:"1IH8R1AP03"};
	};
	HandleIssue.jaxId="1IH8R1AP00"
	HandleIssue.url="HandleIssue@"+agentURL
	
	segs["CallTool"]=CallTool=async function(input){//:1IH8R1UKP0
		let result=input
		/*#{1IH8R1UKP0Code*/
		result=await tools.runTool(input.tool,input.toolArg);
		/*}#1IH8R1UKP0Code*/
		return {seg:GenStep,result:(result),preSeg:"1IH8R1UKP0",outlet:"1IH8R68V50"};
	};
	CallTool.jaxId="1IH8R1UKP0"
	CallTool.url="CallTool@"+agentURL
	
	segs["FInish"]=FInish=async function(input){//:1IH8R2SR30
		let result=input
		/*#{1IH8R2SR30Code*/
		result={"result":"Finish",content:input.content};
		if(task){
			task.finish(input.content);
		}
		/*}#1IH8R2SR30Code*/
		return {result:result};
	};
	FInish.jaxId="1IH8R2SR30"
	FInish.url="FInish@"+agentURL
	
	segs["Abort"]=Abort=async function(input){//:1IH8R32N50
		let result=input
		/*#{1IH8R32N50Code*/
		result={"result":"Finish",content:input.content};
		if(task){
			task.abort(input.content);
		}
		/*}#1IH8R32N50Code*/
		return {result:result};
	};
	Abort.jaxId="1IH8R32N50"
	Abort.url="Abort@"+agentURL
	
	segs["FailTask"]=FailTask=async function(input){//:1IHCCP6G60
		let result=input
		/*#{1IHCCP6G60Code*/
		if(task && ownTask){
			task.fail(input);
			result={result:"Failed",error:input,context:`Task error: ${input}`};
		}else{
			throw input;
		}
		/*}#1IHCCP6G60Code*/
		return {seg:AskEnd,result:(result),preSeg:"1IHCCP6G60",outlet:"1IHCCPIKQ2"};
	};
	FailTask.jaxId="1IHCCP6G60"
	FailTask.url="FailTask@"+agentURL
	
	segs["CheckHandle"]=CheckHandle=async function(input){//:1IIC954FA0
		let result=input;
		/*#{1IIC954FA0Start*/
		/*}#1IIC954FA0Start*/
		if(!!handleIssue){
			let output=input;
			return {seg:HandleIssue,result:(output),preSeg:"1IIC954FA0",outlet:"1IIC994SN0"};
		}
		result=input;
		/*#{1IIC954FA0Post*/
		/*}#1IIC954FA0Post*/
		return {seg:ReportIssue,result:(result),preSeg:"1IIC954FA0",outlet:"1IIC994SO0"};
	};
	CheckHandle.jaxId="1IIC954FA0"
	CheckHandle.url="CheckHandle@"+agentURL
	
	segs["ReportIssue"]=ReportIssue=async function(input){//:1IIC97QCR0
		let result=input
		/*#{1IIC97QCR0Code*/
		result={
			result:"Issue",
			content:input.content,
			issue:input.issue,
			issueBrief:input.issueBrief,
			logs:task.tailLogs(5)
		};
		/*}#1IIC97QCR0Code*/
		return {result:result};
	};
	ReportIssue.jaxId="1IIC97QCR0"
	ReportIssue.url="ReportIssue@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1IIUQDKDB0
		let result;
		let sourcePath=pathLib.join(basePath,"./SysAskUser.js");
		let arg=input.content;
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:GenStep,result:(result),preSeg:"1IIUQDKDB0",outlet:"1IIUQFQQI0"};
	};
	AskUser.jaxId="1IIUQDKDB0"
	AskUser.url="AskUser@"+agentURL
	
	segs["AskEnd"]=AskEnd=async function(input){//:1IJKU6STC0
		let prompt=("Please confirm")||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=("OK")||"OK";
		let button2=("Cancel")||"Cancel";
		let button3=("")||"";
		let result="";
		let value=0;
		if(silent){
			result=input;
			return {result:result};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=(input)||result;
			return {result:result};
		}
		if(value===2){
			result=("")||result;
			return {result:result};
		}
		result=(input)||result;
		return {result:result};
	
	};
	AskEnd.jaxId="1IJKU6STC0"
	AskEnd.url="AskEnd@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"SysHandleTask",
		url:agentURL,
		autoStart:true,
		jaxId:"1IH8PO9RT0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{task,roleTask,prjDesc,guide,tools,handleIssue}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IH8PO9RT0PreEntry*/
			/*}#1IH8PO9RT0PreEntry*/
			result={seg:InitTask,"input":input};
			/*#{1IH8PO9RT0PostEntry*/
			/*}#1IH8PO9RT0PostEntry*/
			return result;
		},
		/*#{1IH8PO9RT0MoreAgentAttrs*/
		endChat:async function(result){
			if(task && ownTask && task.endTask){
				task.endTask();
			}
			return result;
		}
		/*}#1IH8PO9RT0MoreAgentAttrs*/
	};
	/*#{1IH8PO9RT0PostAgent*/
	/*}#1IH8PO9RT0PostAgent*/
	return agent;
};
/*#{1IH8PO9RT0ExCodes*/
/*}#1IH8PO9RT0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "SysHandleTask",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				task:{type:"auto",description:"指导任务，如不为空，则无需重新创建task"},
				roleTask:{type:"string",description:"执行任务的角色设定和任务目标描述"},
				prjDesc:{type:"string",description:"当前项目相关信息的说明"},
				guide:{type:"string",description:"指导完成任务的参考文档。"},
				tools:{type:"auto",description:"可以调用的Tool的文件路径数组"},
				handleIssue:{type:"bool",description:""}
			}
		}
	}
}];

//:Export Edit-AddOn:
const DocAIAgentExporter=VFACT?VFACT.classRegs.DocAIAgentExporter:null;
if(DocAIAgentExporter){
	const EditAttr=VFACT.classRegs.EditAttr;
	const EditAISeg=VFACT.classRegs.EditAISeg;
	const EditAISegOutlet=VFACT.classRegs.EditAISegOutlet;
	const SegObjShellAttr=EditAISeg.SegObjShellAttr;
	const SegOutletDef=EditAISegOutlet.SegOutletDef;
	const docAIAgentExporter=DocAIAgentExporter.prototype;
	const packExtraCodes=docAIAgentExporter.packExtraCodes;
	const packResult=docAIAgentExporter.packResult;
	const varNameRegex = /^[a-zA-Z_$][a-zA-Z0-9_$]*$/;
	
	EditAISeg.regDef({
		name:"SysHandleTask",showName:"SysHandleTask",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"task":{name:"task",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"roleTask":{name:"roleTask",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"prjDesc":{name:"prjDesc",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"guide":{name:"guide",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"tools":{name:"tools",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"handleIssue":{name:"handleIssue",showName:undefined,type:"bool",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","task","roleTask","prjDesc","guide","tools","handleIssue","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["SysHandleTask"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['task']=");this.genAttrStatement(seg.getAttr("task"));coder.packText(";");coder.newLine();
			coder.packText("args['roleTask']=");this.genAttrStatement(seg.getAttr("roleTask"));coder.packText(";");coder.newLine();
			coder.packText("args['prjDesc']=");this.genAttrStatement(seg.getAttr("prjDesc"));coder.packText(";");coder.newLine();
			coder.packText("args['guide']=");this.genAttrStatement(seg.getAttr("guide"));coder.packText(";");coder.newLine();
			coder.packText("args['tools']=");this.genAttrStatement(seg.getAttr("tools"));coder.packText(";");coder.newLine();
			coder.packText("args['handleIssue']=");this.genAttrStatement(seg.getAttr("handleIssue"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/SysHandleTask.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
			this.packResult(coder,seg,seg.outlet);
		}
		coder.indentLess();coder.maybeNewLine();
		coder.packText(`};`);coder.newLine();
		if(exportDebug){
			coder.packText(`${segName}.jaxId="${seg.jaxId}"`);coder.newLine();
		}
		coder.packText(`${segName}.url="${segName}@"+agentURL`);coder.newLine();
		coder.newLine();
	};
}
//#CodyExport<<<
/*#{1IH8PO9RT0PostDoc*/
/*}#1IH8PO9RT0PostDoc*/


export default SysHandleTask;
export{SysHandleTask,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IH8PO9RT0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IH8PO9RT1",
//			"attrs": {
//				"SysHandleTask": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IH8PO9RT7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IH8PO9RT8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IH8PO9RT9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IH8PO9RT10",
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
//			"jaxId": "1IH8PO9RT2",
//			"attrs": {}
//		},
//		"entry": "InitTask",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH8PO9RT3",
//			"attrs": {
//				"task": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHCGH4J20",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "指导任务，如不为空，则无需重新创建task",
//						"required": "false"
//					}
//				},
//				"roleTask": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IH8PQQVM0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "执行任务的角色设定和任务目标描述",
//						"label": "",
//						"required": "true"
//					}
//				},
//				"prjDesc": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IH8QL7H00",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "当前项目相关信息的说明",
//						"label": ""
//					}
//				},
//				"guide": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IH8QL7H01",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "指导完成任务的参考文档。"
//					}
//				},
//				"tools": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IH8Q18OU0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "可以调用的Tool的文件路径数组",
//						"required": "false"
//					}
//				},
//				"handleIssue": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IIC9DHLV0",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IH8PO9RT4",
//			"attrs": {
//				"env": {
//					"type": "auto",
//					"valText": "#globalContext.env"
//				},
//				"project": {
//					"type": "auto",
//					"valText": "#globalContext.project"
//				},
//				"config": {
//					"type": "auto",
//					"valText": "#session.agentNode.nodeJSON"
//				},
//				"ownTask": {
//					"type": "bool",
//					"valText": "false"
//				},
//				"bash": {
//					"type": "auto",
//					"valText": "#globalContext.getBash(globalContext.bash)"
//				},
//				"curPath": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IH8PO9RT5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IH8PO9RT6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IHCCNP8H0",
//					"attrs": {
//						"id": "InitTask",
//						"viewName": "",
//						"label": "",
//						"x": "105",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCCPIL00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCCPIL01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHCCPIKQ0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8QTK050"
//						},
//						"catchlet": {
//							"jaxId": "1IHCCPIKQ1",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCCP6G60"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH8QTK050",
//					"attrs": {
//						"id": "InitTools",
//						"viewName": "",
//						"label": "",
//						"x": "315",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH8QUPFV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8QUPFV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH8QUPFU0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8QU7ER0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IH8QU7ER0",
//					"attrs": {
//						"id": "GenStep",
//						"viewName": "",
//						"label": "",
//						"x": "550",
//						"y": "325",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH8QUPFV2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8QUPFV3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "",
//						"mode": "$plan",
//						"system": "#`\n---\n### 角色/任务\n${roleTask}\n\n---\n### 环境和项目\n当前的系统软硬件环境和系统参数为：\n\\`\\`\\`\n${JSON.stringify(env,null,\"\\t\")}\n\\`\\`\\`\n\n用于工作的命令行Terminal的当前路径是：  \n${curPath}\n\n当前的项目是：${project.name}。\n${prjDesc}\n${project.dirPath?`当前项目所在的文件路径是: \"${project.dirPath}\"。`:\"\"}  \n\n当前项目工作进展：  \n-${project.progress.join(\" \\n\\n- \")}\n\n${project.conda?`注意：当前已经为工程创建/选择了conda环境：${project.conda}, 正常情况下，不需要创建新的conda环境。`:\"\"}\n\n---\n### 参考资料：\n${guide?guide:\"暂无。\"}\n\n${tools?`---\\n### 外部工具/智能体: \\n执行任务的时候可能需要调用外部的工具/AI智能体，当前可以调用的工具/AI智能体有:\\n\\`\\`\\`\\n${JSON.stringify(tools.getScope(),null,\"\\t\")}\\n\\`\\`\\`\\n`:\"\"}\n---\n### 对话\n每一轮对话，你根据当前的步骤执行情况和用户反馈，生成下一个步骤要执行或与用户沟通的内容，并用JSON格式返回。\n\n---\n### 返回的JSON对象属性说明：\n\n- 属性\"action\": {string}, 下一步的动作。可取值：\n\t- \"Cammand\": 通过命令行执行操作，比如用pip安装依赖库，拷贝文件，下载模型等\n    ${tools?`- \"Tool\": 调用外部工具完成特定任务，调用的工具名称放在'tool'属性里， 调用的参数/描述放在'toolArg'属性里`:\"\"}\n    - \"Chat\": 需要用户辅助时，与用户对话，提示需要用户手动进行的动作，例如：询问API-Key；登陆环境；提升当前权限(sudo)等，其它时候尽量避免打扰用户。\n    - \"Finish\": 如果当前任务已完成，结束任务，在\"content\"属性里设置任务结束总结\n    - \"Issue\": 如果执行步骤遇到问题，针对遇到的问题查询RAG知识库，获取解决方案，解决问题，在\"content\"属性里表述问题。\n    - \"Abort\": 如果遇到无法解决问题，（例如或者当前的硬件环境无法满足项目需求）终止任务。\n\n- 属性\"commands\": {array<string>}，当\"action\"为\"Command\"时，要执行的bash命令数组。\n    - 为防止错过纠正问题的机会，一次不要执行太多的命令，\n    - 你生成的必须是可以执行的bash命令\n    - 如果要下载AI的模型文件，优先使用huggingface命令行工具，而不是git\n\n- 属性\"issueBrief\": {string}, 当\"action\"为\"Issue\"时，对问题的简短概括描述，相当于是问题的标题\n- 属性\"issue\": {string}, 当\"action\"为\"Issue\"时，对问题的详细描述，以及要进行查询的内容\n\n- 属性\"content\": {string}, 当前步骤的解释描述。例如当\"action\"为\"Abort\"时，终止原因的说明；当\"action\"为\"Finish\"时，对任务执行情况的完成总结；当\"action\"为\"Issue\"时，问题的详细描述。\n\n${tools?`- 属性\"tool\": 要调用的外部工具名称\\n`:\"\"}\n${tools?`- 属性\"toolArg\": 调用的外部工具的参数/自然语言任务描述，例如：\"将README.md翻译为中文。\\n\"`:\"\"}\n- 属性\"assets\": {array<url>}, 当前步骤产生的需要告知用户的附加，例如图片，文档等的链接的数组\n\n`",
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
//							"jaxId": "1IH8QUPFU1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8QV5R20"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "50 messages",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"1IH9Q82MD0\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IH8QV5R20",
//					"attrs": {
//						"id": "ShowStep",
//						"viewName": "",
//						"label": "",
//						"x": "765",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH8QVHH80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8QVHH81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input.content",
//						"outlet": {
//							"jaxId": "1IH8QVHH70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8R008S0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IH8R008S0",
//					"attrs": {
//						"id": "StepAction",
//						"viewName": "",
//						"label": "",
//						"x": "990",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH8R008S1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8R008S2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH8R008S3",
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
//									"jaxId": "1IH8R008S4",
//									"attrs": {
//										"id": "Command",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8R008S5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8R008S6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Command\""
//									},
//									"linkedSeg": "1IH8R0HGL0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH8R008S10",
//									"attrs": {
//										"id": "Tool",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8R008S11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8R008T0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Tool\""
//									},
//									"linkedSeg": "1IH8R1UKP0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH8R008T7",
//									"attrs": {
//										"id": "Chat",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8R008T8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8R008T9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Chat\""
//									},
//									"linkedSeg": "1IIUQDKDB0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH8R008S7",
//									"attrs": {
//										"id": "Issue",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8R008S8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8R008S9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Issue\""
//									},
//									"linkedSeg": "1IIC954FA0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH8R008T4",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8R008T5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8R008T6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Finish\""
//									},
//									"linkedSeg": "1IH8R2SR30"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH8R008T1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH8R008T2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH8R008T3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Abort\""
//									},
//									"linkedSeg": "1IH8R32N50"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IH8R0HGL0",
//					"attrs": {
//						"id": "RunCommand",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "100",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH8R0HGL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8R0HGL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/ToolBashCommand.js",
//						"argument": "{\"commands\":\"#input.commands\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IH8R0HGM0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8R6PTK0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IH8R1AP00",
//					"attrs": {
//						"id": "HandleIssue",
//						"viewName": "",
//						"label": "",
//						"x": "1480",
//						"y": "285",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH8R1AP01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8R1AP02",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysHandleIssue.js",
//						"argument": "{\"issue\":\"#input.issue||input.content\",\"issueBrief\":\"#input.issueBrief||\\\"\\\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IH8R1AP03",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIC94H5O0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH8R1UKP0",
//					"attrs": {
//						"id": "CallTool",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH8R68V70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8R68V71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH8R68V50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8R6PTK0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH8R2SR30",
//					"attrs": {
//						"id": "FInish",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "405",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IH8R68V72",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8R68V73",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH8R68V51",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH8R32N50",
//					"attrs": {
//						"id": "Abort",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "480",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IH8R68V74",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH8R68V75",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH8R68V52",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IH8R6PTK0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1520",
//						"y": "170",
//						"outlet": {
//							"jaxId": "1IH8R8SQO0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIC94H5O0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IH8R7ECT0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1740",
//						"y": "585",
//						"outlet": {
//							"jaxId": "1IH8R8SQO1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8R7RC60"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IH8R7RC60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "815",
//						"y": "585",
//						"outlet": {
//							"jaxId": "1IH8R8SQO2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8R84460"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IH8R84460",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "575",
//						"y": "420",
//						"outlet": {
//							"jaxId": "1IH8R8SQO3",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8QU7ER0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHCCP6G60",
//					"attrs": {
//						"id": "FailTask",
//						"viewName": "",
//						"label": "",
//						"x": "315",
//						"y": "585",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCCPIL02",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCCPIL03",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHCCPIKQ2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJKU6STC0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IIC94H5O0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1720",
//						"y": "285",
//						"outlet": {
//							"jaxId": "1IIC994SS0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8R7ECT0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IIC954FA0",
//					"attrs": {
//						"id": "CheckHandle",
//						"viewName": "",
//						"label": "",
//						"x": "1235",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIC994SS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIC994SS2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIC994SO0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": "#input"
//							},
//							"linkedSeg": "1IIC97QCR0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IIC994SN0",
//									"attrs": {
//										"id": "Handle",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IIC994SS3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IIC994SS4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!handleIssue"
//									},
//									"linkedSeg": "1IH8R1AP00"
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
//					"jaxId": "1IIC97QCR0",
//					"attrs": {
//						"id": "ReportIssue",
//						"viewName": "",
//						"label": "",
//						"x": "1480",
//						"y": "360",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IIC994SS5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIC994SS6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIC994SO1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IIUQDKDB0",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "245",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIUQFQQN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIUQFQQN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysAskUser.js",
//						"argument": "#{}#>input.content",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IIUQFQQI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH8R6PTK0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1IJKU6STC0",
//					"attrs": {
//						"id": "AskEnd",
//						"viewName": "",
//						"label": "",
//						"x": "550",
//						"y": "715",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "Please confirm",
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJKU6SSO0",
//									"attrs": {
//										"id": "Button1",
//										"desc": "输出节点。",
//										"text": "OK",
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJKU7G1U0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJKU7G1U1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									}
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJKU6SSO1",
//									"attrs": {
//										"id": "Button2",
//										"desc": "输出节点。",
//										"text": "Cancel",
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJKU7G1U2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJKU7G1U3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									}
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJKU6SSO2",
//									"attrs": {
//										"id": "Button3",
//										"desc": "输出节点。",
//										"text": "",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJKU7G1U4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJKU7G1U5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									}
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}