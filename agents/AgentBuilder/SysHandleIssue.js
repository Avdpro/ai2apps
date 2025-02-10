//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IH66KKV20MoreImports*/
import AATools from "../../agenthub/AATools.mjs";
import AATask from "./Task.js";
import AATaskIssue from "./Issue.js";
/*}#1IH66KKV20MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"issue":{
			"name":"issue","type":"string",
			"defaultValue":"",
			"desc":"要解决的问题描述",
		},
		"issueBrief":{
			"name":"issueBrief","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"问题的简洁描述",
		}
	},
	/*#{1IH66KKV20ArgsView*/
	/*}#1IH66KKV20ArgsView*/
};

/*#{1IH66KKV20StartDoc*/
/*}#1IH66KKV20StartDoc*/
//----------------------------------------------------------------------------
let SysHandleIssue=async function(session){
	let issue,issueBrief;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,InitIssue,AskRag,AskSolution,InitTools,TrySolution,AnalyzeIssue,CheckAnalyze,CheckResult,Finish,RunTool,AskChat,SaveNote,AskHandle,ChatResult,SkipResult,WaitHandle,KeepBash,ManualResult,TrackBash,SumManual,SumGuide,PushManualRAG,RunBash,Chat,FailIssue,ShowSolution,AskTry,EditSolution,TipBash,TipTool,CheckGuide,ShowNewGuide,PushRAG,ShowManualGuide,ShowAgain,PushIssue,JumpToStart,PopIssue,AskResloved,PushUserGuide,AskUser;
	let env=globalContext.env;
	let project=globalContext.project;
	let dirName=project.dirName;
	let dirPath=project.dirPath;
	let tools=null;
	let bashContent="";
	let task=null;
	let guide="";
	let useRagGuide=false;
	let ragGuide="";
	let fixResult="";
	let solution="";
	let issueLogs=null;
	let tryTask=null;
	let orgIssue=null;
	let issueStack=[];
	
	/*#{1IH66KKV20LocalVals*/
	/*}#1IH66KKV20LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			issue=input.issue;
			issueBrief=input.issueBrief;
		}else{
			issue=undefined;
			issueBrief=undefined;
		}
		/*#{1IH66KKV20ParseArgs*/
		/*}#1IH66KKV20ParseArgs*/
	}
	
	/*#{1IH66KKV20PreContext*/
	/*}#1IH66KKV20PreContext*/
	context={};
	/*#{1IH66KKV20PostContext*/
	/*}#1IH66KKV20PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IH77THGP0
		let result=input;
		let missing=false;
		if(issue===undefined || issue==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:InitIssue,result:(result),preSeg:"1IH77THGP0",outlet:"1IH77U7G00"};
	};
	FixArgs.jaxId="1IH77THGP0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["InitIssue"]=InitIssue=async function(input){//:1IHCCSQGV0
		let result=input;
		/*#{1IHCCSQGV0Code*/
		task=new AATaskIssue(session,issue);
		task.setReportCallback((task,content)=>{
			AnalyzeIssue.messages.push({
				progress:content
			});
		});
		orgIssue={issue:issue,brief:issueBrief,logs:task.parentTask.tailLogs(5)};
		issueLogs=orgIssue.logs;
		issueStack.push(orgIssue);
		/*}#1IHCCSQGV0Code*/
		return {seg:AskHandle,result:(result),preSeg:"1IHCCSQGV0",outlet:"1IHCD4HSD0",catchSeg:FailIssue,catchlet:"1IHCD4HSD1"};
	};
	InitIssue.jaxId="1IHCCSQGV0"
	InitIssue.url="InitIssue@"+agentURL
	
	segs["AskRag"]=AskRag=async function(input){//:1IH780CKO0
		let result=input
		/*#{1IH780CKO0Code*/
		//TODO: Ask rag guide
		if(ragGuide){
			guide=ragGuide;
			useRagGuide=true;
		}
		/*}#1IH780CKO0Code*/
		return {seg:InitTools,result:(result),preSeg:"1IH780CKO0",outlet:"1IH78IF790"};
	};
	AskRag.jaxId="1IH780CKO0"
	AskRag.url="AskRag@"+agentURL
	
	segs["AskSolution"]=AskSolution=async function(input){//:1IIBEO7G30
		let tip=((($ln==="CN")?("请输入解决方案"):("Enter the solution")));
		let tipRole=("assistant");
		let placeholder=("");
		let text=("");
		let result="";
		/*#{1IIBEO7G30PreCodes*/
		/*}#1IIBEO7G30PreCodes*/
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		/*#{1IIBEO7G30PostCodes*/
		guide=result;
		useRagGuide=true;
		/*}#1IIBEO7G30PostCodes*/
		return {seg:InitTools,result:(result),preSeg:"1IIBEO7G30",outlet:"1IIBETGBT0"};
	};
	AskSolution.jaxId="1IIBEO7G30"
	AskSolution.url="AskSolution@"+agentURL
	
	segs["InitTools"]=InitTools=async function(input){//:1IH7CTE2O0
		let result=input
		/*#{1IH7CTE2O0Code*/
		tools=new AATools(session,basePath);
		if(!(await tools.load("issue"))){
			tools=null;
		}
		task.report((($ln==="CN")?("开始尝试解决问题"):/*EN*/("Start trying to solve the issue")));
		result="请开始分析问题。";
		/*}#1IH7CTE2O0Code*/
		return {seg:AnalyzeIssue,result:(result),preSeg:"1IH7CTE2O0",outlet:"1IH7CU43Q0"};
	};
	InitTools.jaxId="1IH7CTE2O0"
	InitTools.url="InitTools@"+agentURL
	
	segs["TrySolution"]=TrySolution=async function(input){//:1IH78554O0
		let result;
		let sourcePath=pathLib.join(basePath,"./SysHandleTask.js");
		let arg={"task":`尝试解决问题: ${issueBrief}`,"roleTask":`你是一个根据解决方案尝试解决项目问题的AI。 \n\n你按照指引一步一步的执行，直到解决了当前项目遇到的问题:  \n\n${issue}注意：你只需要解决当前的问题，你可以验证当前问题是否解决。你不要做其他与解决当前问题无关的事情，比如完成整个项目部署，测试项目运行等。`,"prjDesc":"","guide":`当前找到的解决方案:\n\`\`\`markdown\n${input.content}\n\`\`\``,"tools":"fixIssue","handleIssue":false};
		/*#{1IH78554O0Input*/
		task.findSolution(input);
		task.report(`问题: ${issueBrief||issue}\n\n找到了解决方案，尝试执行解决方案。`);
		solution=input.content;
		tryTask=new AATask(session,arg.task,solution);
		arg.task="CURRENT";
		/*}#1IH78554O0Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IH78554O0Output*/
		tryTask.endTask();
		fixResult=result.content;
		/*}#1IH78554O0Output*/
		return {seg:CheckResult,result:(result),preSeg:"1IH78554O0",outlet:"1IH78IF793"};
	};
	TrySolution.jaxId="1IH78554O0"
	TrySolution.url="TrySolution@"+agentURL
	
	segs["AnalyzeIssue"]=AnalyzeIssue=async function(input){//:1IH78614B0
		let prompt;
		let result;
		
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
					"name":"IssueStep",
					"schema":{
						"type":"object",
						"description":"分析问题的步骤/输出",
						"properties":{
							"action":{
								"type":"string",
								"description":"下一步的步骤动作",
								"enum":[
									"Solution","Command","Finish","Abort","Tool","Chat"
								]
							},
							"content":{
								"type":"string",
								"description":"该步骤的内容或说明"
							},
							"commands":{
								"type":"array",
								"description":"这个步骤要执行的命令行指令数组，如果没有要执行的指令，设置为空数组。",
								"items":{
									"type":"string"
								}
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
							}
						},
						"required":[
							"action","content","commands","tool","toolArg"
						],
						"additionalProperties":false
					},
					"strict":true
				}
			}
		};
		let chatMem=AnalyzeIssue.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
---
### 角色与任务：
你是一个针对软件开发、部署遇到的问题，分析原因，查找资料，给出问题解决方案的AI。

---
### 项目环境
当前的系统软硬件环境和系统参数为：
\`\`\`
${JSON.stringify(env,null,"\t")}
\`\`\`

---
### 当前项目
当前的项目是：${project.name}。
${project.dirPath?`当前项目所在的文件路径是: "${project.dirPath}"。`:""}  

当前项目工作进展：  
-${project.progress.join(" \n\n- ")}

${project.conda?`注意：当前已经为工程创建/选择了conda环境：${project.conda}, 正常情况下，不需要创建新的conda环境。`:""}

---
### 问题
在进行工作步骤"${task.parentTask.desc}"时，遇到了问题： 
${issue}。

在遇到问题时的工作日志为：
${JSON.stringify(task.parentTask.tailLogs(5),null,"\t")}

---
### 系统知识库中找到的问题相关参考资料：
${guide?guide:"暂无。"}

${tools?`---\n### 外部工具/智能体: \n分析问题，查找解决方案的时候可能需要调用外部的工具/AI智能体，当前可以调用的工具/AI智能体有:\n\`\`\`\n${JSON.stringify(tools.getScope(),null,"\t")}\n\`\`\`\n`:""}

---
### 对话
你只负责分析问题和生成问题解决方案，而不要试图直接尝试解决问题。生成解决方案后，会有专门的智能体进行尝试，
每一轮对话，你根据当前的步骤执行情况和用户反馈，生成下一个步骤要执行或与用户沟通的内容，并用JSON格式返回。

- 你的解决方案应该包括明确单一方案的操作指南，不要提供多个方案让用户选择。如果找到多个方案需要用户选择，先通过与对话确定使用哪个方案，再生成单一方案的操作指南。

- 如果你找到了解决方案，设置返回JSON的"action"属性为"Solution"，并在"content"属性中包含解决方案的markdown文本。

- 生成解决方案后，系统会进行方案验证，如果成功，则结束当前对话（返回JSON的"action"属性设置为"Finish")。

- 如果系统验证方案不能解决问题，请继续分析，生成新的解决方案。

- 如果你判定当前问题无法解决，例如环境硬件条件不满足，缺少必要的账号等，设置返回JSON的"action"属性为"Abort"，并在"content"属性里说明原因。

---
### 返回的JSON对象属性说明：

- 属性"action": {string}, 下一步的动作。可取值：
	- "Solution": 找到了解决方案，设置"content"属性为解决方案的markdown文本。
	- "Cammand": 通过命令行执行操作，比如用ls查看文件列表，请注意你只能利用这些命令来分析问题和生成解决方案，而不要试图在这里解决问题。
    ${tools?`- "Tool": 调用外部工具完成特定任务，调用的工具名称放在'tool'属性里， 调用的参数/描述放在'toolArg'属性里`:""}
    - "Chat": 需要用户辅助时，与用户对话，提示需要用户手动进行的动作，例如：询问API-Key；登陆环境；提升当前权限(sudo)等，其它时候尽量避免打扰用户。
    - "Finish": 如果你生成的解决方案通过了验证，结束任务，返回总结
    - "Abort": 如果你判定任务无法解决（例如或者当前的硬件环境无法满足项目需求）终止任务。

- 属性"commands": {array<string>}，当"action"为"Command"时，要执行的bash命令数组。
    - 为防止错过纠正问题的机会，一次不要执行太多的命令，
    - 你生成的必须是可以执行的bash命令
    - 你生成的命令只能用来分析问题/生成解决方案，所以不要增加、删除或修改文件

- 属性"content": {string}, 当前步骤的解释描述。例如当"action"为"Abort"时，终止原因的说明；当"action"为"Finish"时，对任务执行情况的完成总结；当"action"为"Solution"时，问题的解决方案。

${tools?`- 属性"tool": 要调用的外部工具名称\n`:""}
${tools?`- 属性"toolArg": 调用的外部工具的参数/自然语言任务描述，例如："将README.md翻译为中文。\n"`:""}




`},
		];
		messages.push(...chatMem);
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		result=await session.callSegLLM("AnalyzeIssue@"+agentURL,opts,messages,true);
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		result=trimJSON(result);
		return {seg:CheckAnalyze,result:(result),preSeg:"1IH78614B0",outlet:"1IH78IF794"};
	};
	AnalyzeIssue.jaxId="1IH78614B0"
	AnalyzeIssue.url="AnalyzeIssue@"+agentURL
	AnalyzeIssue.messages=[];
	
	segs["CheckAnalyze"]=CheckAnalyze=async function(input){//:1IH78A2610
		let result=input;
		if(input.action==="Solution"){
			return {seg:ShowSolution,result:(input),preSeg:"1IH78A2610",outlet:"1IH78CCEV0"};
		}
		if(input.action==="Chat"){
			let output=input.content;
			return {seg:AskUser,result:(output),preSeg:"1IH78A2610",outlet:"1IH78V6J60"};
		}
		if(input.action==="Command"){
			return {seg:TipBash,result:(input),preSeg:"1IH78A2610",outlet:"1IH78NST40"};
		}
		if(input.action==="Tool"){
			return {seg:TipTool,result:(input),preSeg:"1IH78A2610",outlet:"1IH78QMCR0"};
		}
		return {result:result};
	};
	CheckAnalyze.jaxId="1IH78A2610"
	CheckAnalyze.url="CheckAnalyze@"+agentURL
	
	segs["CheckResult"]=CheckResult=async function(input){//:1IH78D7FH0
		let result=input;
		/*#{1IH78D7FH0Start*/
		/*}#1IH78D7FH0Start*/
		if(input.result==="Finish"){
			/*#{1IH78IF7A2Codes*/
			task.report(`问题: ${issueBrief||issue}\n\n尝试解决方案成功: ${input.content}`);
			/*}#1IH78IF7A2Codes*/
			return {seg:AskResloved,result:(input),preSeg:"1IH78D7FH0",outlet:"1IH78IF7A2"};
		}
		if(input.result==="Issue"){
			/*#{1IIHRRGNO0Codes*/
			/*}#1IIHRRGNO0Codes*/
			return {seg:PushIssue,result:(input),preSeg:"1IH78D7FH0",outlet:"1IIHRRGNO0"};
		}
		result=`尝试解决问题没有成功：${input.content}`;
		/*#{1IH78D7FH0Post*/
		task.report(`问题: ${issueBrief||issue}\n\n尝试解决方案不成功: ${input.content}\n\n继续寻找新的解决方案`);
		/*}#1IH78D7FH0Post*/
		return {seg:AnalyzeIssue,result:(result),preSeg:"1IH78D7FH0",outlet:"1IH78IF7A3"};
	};
	CheckResult.jaxId="1IH78D7FH0"
	CheckResult.url="CheckResult@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1IH78HD9N0
		let result=input
		/*#{1IH78HD9N0Code*/
		result={result:"IssueResolved",issue:`${issueBrief||issue}`,content:`问题已解决: ${fixResult}`};
		task.finish(result.content);
		/*}#1IH78HD9N0Code*/
		return {result:result};
	};
	Finish.jaxId="1IH78HD9N0"
	Finish.url="Finish@"+agentURL
	
	segs["RunTool"]=RunTool=async function(input){//:1IH78R6NV0
		let result=input
		/*#{1IH78R6NV0Code*/
		result=await tools.runTool(input.tool,input.toolArg);
		/*}#1IH78R6NV0Code*/
		return {seg:AnalyzeIssue,result:(result),preSeg:"1IH78R6NV0",outlet:"1IH78SBJ85"};
	};
	RunTool.jaxId="1IH78R6NV0"
	RunTool.url="RunTool@"+agentURL
	
	segs["AskChat"]=AskChat=async function(input){//:1IH78VU0G0
		let tip=(input.content);
		let tipRole=("assistant");
		let placeholder=("");
		let text=("");
		let result="";
		/*#{1IH78VU0G0PreCodes*/
		/*}#1IH78VU0G0PreCodes*/
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		/*#{1IH78VU0G0PostCodes*/
		/*}#1IH78VU0G0PostCodes*/
		return {result:result};
	};
	AskChat.jaxId="1IH78VU0G0"
	AskChat.url="AskChat@"+agentURL
	
	segs["SaveNote"]=SaveNote=async function(input){//:1IIBHPL6R0
		let result;
		let sourcePath=pathLib.join(basePath,"./RagPush.js");
		let arg={"address":"","doc":input.content,"desc":`解决问题：${issueBrief}`,"tags":"issue,solution"};
		/*#{1IIBHPL6R0Input*/
		/*}#1IIBHPL6R0Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IIBHPL6R0Output*/
		result=input;
		/*}#1IIBHPL6R0Output*/
		return {seg:TrySolution,result:(result),preSeg:"1IIBHPL6R0",outlet:"1IIBHRHEV0"};
	};
	SaveNote.jaxId="1IIBHPL6R0"
	SaveNote.url="SaveNote@"+agentURL
	
	segs["AskHandle"]=AskHandle=async function(input){//:1IHA3IF990
		let prompt=("是否尝试查询并解决这个问题？您也可以直接输入指导意见。")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/tabos/shared/assets/find.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("查询并尝试解决问题"):("Search and attempt to resolve this issue")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("提供解决方案"):("Provide a solution")),code:1},
			{icon:"/~/tabos/shared/assets/mouse.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("手动解决问题"):("Manually address issue")),code:2},
			{icon:"/~/tabos/shared/assets/moveback.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("忽略这个问题"):("Ignore this issue")),code:3},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:AskRag,result:(result),preSeg:"1IHA3IF990",outlet:"1IHA3IF8H0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:true,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {seg:Chat,result:(result),preSeg:"1IHA3IF990",outlet:"1IHA45QV80"};
		}else if(item.code===0){
			return {seg:AskRag,result:(result),preSeg:"1IHA3IF990",outlet:"1IHA3IF8H0"};
		}else if(item.code===1){
			return {seg:AskSolution,result:(result),preSeg:"1IHA3IF990",outlet:"1IIBETGBR0"};
		}else if(item.code===2){
			return {seg:KeepBash,result:(result),preSeg:"1IHA3IF990",outlet:"1IHA3IF8H2"};
		}else if(item.code===3){
			return {seg:SkipResult,result:(result),preSeg:"1IHA3IF990",outlet:"1IHA3IF8H1"};
		}
		return {seg:Chat,result:(result),preSeg:"1IHA3IF990",outlet:"1IHA45QV80"};
	};
	AskHandle.jaxId="1IHA3IF990"
	AskHandle.url="AskHandle@"+agentURL
	
	segs["ChatResult"]=ChatResult=async function(input){//:1IHA3RMK90
		let result=input
		/*#{1IHA3RMK90Code*/
		result={result:"Finish",conent:(($ln==="CN")?(`用户回复：${input}。`):/*EN*/(`User replied: ${input}.`))};
		task.finish(result.content);
		/*}#1IHA3RMK90Code*/
		return {result:result};
	};
	ChatResult.jaxId="1IHA3RMK90"
	ChatResult.url="ChatResult@"+agentURL
	
	segs["SkipResult"]=SkipResult=async function(input){//:1IHA3SETP0
		let result=input
		/*#{1IHA3SETP0Code*/
		result={result:"IgnoreIssue",issue:issueBrief||issue,content:(($ln==="CN")?(`用户决定忽略这个问题。`):/*EN*/(`The user decides to ignore this issue.`))};
		task.skip(result.content);
		/*}#1IHA3SETP0Code*/
		return {result:result};
	};
	SkipResult.jaxId="1IHA3SETP0"
	SkipResult.url="SkipResult@"+agentURL
	
	segs["WaitHandle"]=WaitHandle=async function(input){//:1IHA3U04V0
		let prompt=((($ln==="CN")?("请在解决问题后请按\"继续\"按钮。"):("Please press the 'continue' button after solving the issue.")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("继续"):("Continue")))||"OK";
		let button2=((($ln==="CN")?("取消"):("Cancel")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:TrackBash,result:(result),preSeg:"1IHA3U04V0",outlet:"1IHA3U04D0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:TrackBash,result:(result),preSeg:"1IHA3U04V0",outlet:"1IHA3U04D0"};
		}
		result=("")||result;
		return {seg:AskHandle,result:(result),preSeg:"1IHA3U04V0",outlet:"1IHA3U04D1"};
	
	};
	WaitHandle.jaxId="1IHA3U04V0"
	WaitHandle.url="WaitHandle@"+agentURL
	
	segs["KeepBash"]=KeepBash=async function(input){//:1IHA4780H0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Content";
		args['commands']="";
		args['options']="";
		/*#{1IHA4780H0PreCodes*/
		task.report((($ln==="CN")?("用户选择手动解决问题"):/*EN*/("User chooses to resolve the issue manually")));
		/*}#1IHA4780H0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IHA4780H0PostCodes*/
		bashContent=result;
		/*}#1IHA4780H0PostCodes*/
		return {seg:WaitHandle,result:(result),preSeg:"1IHA4780H0",outlet:"1IHA4CS5S0"};
	};
	KeepBash.jaxId="1IHA4780H0"
	KeepBash.url="KeepBash@"+agentURL
	
	segs["ManualResult"]=ManualResult=async function(input){//:1IHA4B3890
		let result=input
		/*#{1IHA4B3890Code*/
		result={result:"IssueResolved",issue:`${issueBrief||issue}`,content:`用户手动解决了问题。`};
		task.finish(result.content);
		/*}#1IHA4B3890Code*/
		return {result:result};
	};
	ManualResult.jaxId="1IHA4B3890"
	ManualResult.url="ManualResult@"+agentURL
	
	segs["TrackBash"]=TrackBash=async function(input){//:1IHA4FMOR0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Content";
		args['commands']="";
		args['options']="";
		/*#{1IHA4FMOR0PreCodes*/
		/*}#1IHA4FMOR0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IHA4FMOR0PostCodes*/
		result=`用户解决问题操作记录：${result.substring(bashContent.length)}`;
		/*}#1IHA4FMOR0PostCodes*/
		return {seg:SumManual,result:(result),preSeg:"1IHA4FMOR0",outlet:"1IHA4I7JV0"};
	};
	TrackBash.jaxId="1IHA4FMOR0"
	TrackBash.url="TrackBash@"+agentURL
	
	segs["SumManual"]=SumManual=async function(input){//:1IHA4LPN40
		let prompt;
		let result=null;
		/*#{1IHA4LPN40Input*/
		/*}#1IHA4LPN40Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"$plan",
			maxToken:3912,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=SumManual.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
--- 
### 角色任务
你是软件项目遇到问题解决后，分析用户的操作，总结解决方案的AI

--- 
### 当前环境
当前的系统软硬件环境和系统参数为：
\`\`\`
${JSON.stringify(env,null,"\t")}
\`\`\`

--- 
### 当前的项目
当前的项目是：${project.name}。
${project.dirPath?`当前项目所在的文件路径是: "${project.dirPath}"。`:""}  

--- 
### 遇到的问题
项目工作遇到的问题： 
${issue}


--- 
### 找到的问题相关参考资料  
${ragGuide?ragGuide:"暂无"}

---
### 用户的操记录
${input}

---
### 输出
请用JSON输出解决问题的总结

- 属性 "guide": {string}: 针对问题，参考用户的执行过程，生成解决问题的解决方案文档，markdown格式。

`
},
		];
		/*#{1IHA4LPN40PrePrompt*/
		/*}#1IHA4LPN40PrePrompt*/
		prompt="请生成回复JSON";
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		/*#{1IHA4LPN40PreCall*/
		/*}#1IHA4LPN40PreCall*/
		result=(result===null)?(await session.callSegLLM("SumManual@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IHA4LPN40PostCall*/
		/*}#1IHA4LPN40PostCall*/
		return {seg:ShowManualGuide,result:(result),preSeg:"1IHA4LPN40",outlet:"1IHA4O48F0"};
	};
	SumManual.jaxId="1IHA4LPN40"
	SumManual.url="SumManual@"+agentURL
	
	segs["SumGuide"]=SumGuide=async function(input){//:1IHA4P5370
		let prompt;
		let result;
		
		let opts={
			platform:"",
			mode:"$plan",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=SumGuide.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
--- 
### 角色任务
你是软件项目遇到问题解决后，总结解决方案的AI

--- 
### 当前环境
当前的系统软硬件环境和系统参数为：
\`\`\`
${JSON.stringify(env,null,"\t")}
\`\`\`

--- 
### 当前的项目
当前的项目是：${project.name}。
${project.dirPath?`当前项目所在的文件路径是: "${project.dirPath}"。`:""}  

--- 
### 遇到的问题
项目工作遇到的问题： 
${issue}


--- 
### 找到的问题相关参考资料  
${ragGuide?ragGuide:"暂无"}

---
### 实际执行的解决方案
${solution}

---
### 执行问题解决方案的过程日志：
${JSON.stringify(tryTask.tailLogs(50),null,"\t")}

---
### 输出
请用JSON输出解决问题的总结

- 属性 "refIsOK" {bool}: 参考资料内容是否完全正确，如果没有参考资料，设置为false
- 属性 "guide": {string}: 如果没有参考资料，或者参考资料的内容不完全正确，总结正确的参考资料，markdown格式。

`
},
		];
		prompt="用JSON输出总结";
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		result=await session.callSegLLM("SumGuide@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:CheckGuide,result:(result),preSeg:"1IHA4P5370",outlet:"1IHA4P5381"};
	};
	SumGuide.jaxId="1IHA4P5370"
	SumGuide.url="SumGuide@"+agentURL
	
	segs["PushManualRAG"]=PushManualRAG=async function(input){//:1IHA4RDVD0
		let result;
		let sourcePath=pathLib.join(basePath,"./RagPush.js");
		let arg={"desc":`解决问题：${issueBrief}`,"doc":input.guide,"tags":"issue,solution","env":env};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:ManualResult,result:(result),preSeg:"1IHA4RDVD0",outlet:"1IHA4UBJQ0"};
	};
	PushManualRAG.jaxId="1IHA4RDVD0"
	PushManualRAG.url="PushManualRAG@"+agentURL
	
	segs["RunBash"]=RunBash=async function(input){//:1IHARSDG50
		let result;
		let sourcePath=pathLib.join(basePath,"./ToolBashCommand.js");
		let arg={"commands":input.commands};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:AnalyzeIssue,result:(result),preSeg:"1IHARSDG50",outlet:"1IHARTCCD0"};
	};
	RunBash.jaxId="1IHARSDG50"
	RunBash.url="RunBash@"+agentURL
	
	segs["Chat"]=Chat=async function(input){//:1IHB3PT8G0
		let tip=("");
		let tipRole=("assistant");
		let placeholder=("");
		let text=("");
		let result="";
		/*#{1IHB3PT8G0PreCodes*/
		/*}#1IHB3PT8G0PreCodes*/
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		/*#{1IHB3PT8G0PostCodes*/
		/*}#1IHB3PT8G0PostCodes*/
		return {seg:ChatResult,result:(result),preSeg:"1IHB3PT8G0",outlet:"1IHB3QGHP0"};
	};
	Chat.jaxId="1IHB3PT8G0"
	Chat.url="Chat@"+agentURL
	
	segs["FailIssue"]=FailIssue=async function(input){//:1IHCCTSTT0
		let result=input
		/*#{1IHCCTSTT0Code*/
		task.fail(input);
		result={result:"Failed",issue:issueBrief||issue,content:(($ln==="CN")?(`问题未能解决。尝试解决问题时遇到异常: ${input}。`):/*EN*/(`Resolve issue failed. There is an error excption: ${input}.`))};
		/*}#1IHCCTSTT0Code*/
		return {result:result};
	};
	FailIssue.jaxId="1IHCCTSTT0"
	FailIssue.url="FailIssue@"+agentURL
	
	segs["ShowSolution"]=ShowSolution=async function(input){//:1IHFPSOC20
		let result=input;
		let role="assistant";
		let content=input.content;
		session.addChatText(role,content);
		return {seg:AskTry,result:(result),preSeg:"1IHFPSOC20",outlet:"1IHFQ7LR30"};
	};
	ShowSolution.jaxId="1IHFPSOC20"
	ShowSolution.url="ShowSolution@"+agentURL
	
	segs["AskTry"]=AskTry=async function(input){//:1IHFPUNF80
		let prompt=("是否尝试这个解决方案？您也可以提出对解决方案的修改意见")||input;
		let countdown=undefined;
		let placeholder=((($ln==="CN")?("对解决方案的修改建议"):("Suggestions for modifying the solution")))||null;
		let silent=false;
		let items=[
			{icon:"/~/tabos/shared/assets/run.svg"||"/~/-tabos/shared/assets/dot.svg",text:"执行解决方案",code:0},
			{icon:"/~/tabos/shared/assets/edit.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("手动编辑"):("Manual Edit")),code:1},
			{icon:"/~/tabos/shared/assets/close.svg"||"/~/-tabos/shared/assets/dot.svg",text:"否决，重新寻找解决方案",code:2},
		];
		let result="";
		let item=null;
		
		if(silent){
			result=input;
			return {seg:SaveNote,result:(result),preSeg:"1IHFPUNF80",outlet:"1IHFPUNEM0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:true,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			/*#{1IHFQ7LR31ChatInput*/
			result=`用户对解决方案提出修改意见：${result}`;
			/*}#1IHFQ7LR31ChatInput*/
			return {seg:AnalyzeIssue,result:(result),preSeg:"1IHFPUNF80",outlet:"1IHFQ7LR31"};
		}else if(item.code===0){
			result=(input);
			return {seg:SaveNote,result:(result),preSeg:"1IHFPUNF80",outlet:"1IHFPUNEM0"};
		}else if(item.code===1){
			result=(input);
			return {seg:EditSolution,result:(result),preSeg:"1IHFPUNF80",outlet:"1II1F3H1M0"};
		}else if(item.code===2){
			/*#{1IHFPUNEM1*/
			result=`用户认为解决方案不可行，请重新生成解决方案。`;
			/*}#1IHFPUNEM1*/
			return {seg:AnalyzeIssue,result:(result),preSeg:"1IHFPUNF80",outlet:"1IHFPUNEM1"};
		}
		/*#{1IHFQ7LR31DefaultOutlet*/
		/*}#1IHFQ7LR31DefaultOutlet*/
		return {seg:AnalyzeIssue,result:(result),preSeg:"1IHFPUNF80",outlet:"1IHFQ7LR31"};
	};
	AskTry.jaxId="1IHFPUNF80"
	AskTry.url="AskTry@"+agentURL
	
	segs["EditSolution"]=EditSolution=async function(input){//:1II1EPQMB0
		let result;
		let role="assistant";
		let tip="";
		let showResult=false;
		let dlgVO={title:"编辑解决方案",text:input.content};
		/*#{1II1EPQMB0Pre*/
		/*}#1II1EPQMB0Pre*/
		result= await session.askUserDlg({"dlgPath":"/@editkit/ui/DlgLongText.js","arg":dlgVO,"role":role,tip:tip,showResult:showResult});
		/*#{1II1EPQMB0Codes*/
		if(result===null){
			result=input;
		}else{
			input.content=result;
			result=input;
		}
		/*}#1II1EPQMB0Codes*/
		return {seg:ShowAgain,result:(result),preSeg:"1II1EPQMB0",outlet:"1II1F3H1M1"};
	};
	EditSolution.jaxId="1II1EPQMB0"
	EditSolution.url="EditSolution@"+agentURL
	
	segs["TipBash"]=TipBash=async function(input){//:1IHGC1QM10
		let result=input;
		let role="assistant";
		let content=input;
		session.addChatText(role,content);
		return {seg:RunBash,result:(result),preSeg:"1IHGC1QM10",outlet:"1IHGC47Q10"};
	};
	TipBash.jaxId="1IHGC1QM10"
	TipBash.url="TipBash@"+agentURL
	
	segs["TipTool"]=TipTool=async function(input){//:1IHGC2VAC0
		let result=input;
		let role="assistant";
		let content=input.content;
		session.addChatText(role,content);
		return {seg:RunTool,result:(result),preSeg:"1IHGC2VAC0",outlet:"1IHGC47Q11"};
	};
	TipTool.jaxId="1IHGC2VAC0"
	TipTool.url="TipTool@"+agentURL
	
	segs["CheckGuide"]=CheckGuide=async function(input){//:1IHI8L15I0
		let result=input;
		if(!input.refIsOK){
			let output=input;
			return {seg:ShowNewGuide,result:(output),preSeg:"1IHI8L15I0",outlet:"1IHI8O5MQ0"};
		}
		return {seg:PopIssue,result:(result),preSeg:"1IHI8L15I0",outlet:"1IHI8O5MR0"};
	};
	CheckGuide.jaxId="1IHI8L15I0"
	CheckGuide.url="CheckGuide@"+agentURL
	
	segs["ShowNewGuide"]=ShowNewGuide=async function(input){//:1IHI8M4FL0
		let result=input;
		let role="assistant";
		let content=`这是新生成的问题解决指南：  ${input.guide}`;
		session.addChatText(role,content);
		return {seg:PushRAG,result:(result),preSeg:"1IHI8M4FL0",outlet:"1IHI8O5MR1"};
	};
	ShowNewGuide.jaxId="1IHI8M4FL0"
	ShowNewGuide.url="ShowNewGuide@"+agentURL
	
	segs["PushRAG"]=PushRAG=async function(input){//:1II00TVTU0
		let result;
		let sourcePath=pathLib.join(basePath,"./RagPush.js");
		let arg={"desc":`解决问题：${issueBrief}`,"doc":input.guide,"tags":"issue,solution","env":env};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:PopIssue,result:(result),preSeg:"1II00TVTU0",outlet:"1II0128EH0"};
	};
	PushRAG.jaxId="1II00TVTU0"
	PushRAG.url="PushRAG@"+agentURL
	
	segs["ShowManualGuide"]=ShowManualGuide=async function(input){//:1II03D91U0
		let result=input;
		let role="assistant";
		let content=`这是根据你的操作生成的问题解决指南：  
${input.guide}
`;
		session.addChatText(role,content);
		return {seg:PushManualRAG,result:(result),preSeg:"1II03D91U0",outlet:"1II03FK7E0"};
	};
	ShowManualGuide.jaxId="1II03D91U0"
	ShowManualGuide.url="ShowManualGuide@"+agentURL
	
	segs["ShowAgain"]=ShowAgain=async function(input){//:1II1ESTVS0
		let result=input;
		return {seg:AskHandle,result:result,preSeg:"1II1ESTVS0",outlet:"1II1F3H1M2"};
	
	};
	ShowAgain.jaxId="1II1ESTVS0"
	ShowAgain.url="ShowAgain@"+agentURL
	
	segs["PushIssue"]=PushIssue=async function(input){//:1IIHSCTNV0
		let result=input
		/*#{1IIHSCTNV0Code*/
		let newIssue={
			issue:input.issue,
			brief:input.issueBrief,
			logs:input.logs
		};
		issueStack.push(newIssue);
		issue=newIssue.issue;
		issueBrief=newIssue.brief;
		issueLogs=newIssue.logs;
		AnalyzeIssue.messages.push({role:"user",content:JSON.stringify({result:"NewIssue",content:`遇到新问题: 《${issueBrief}》':\n\n${issue}`})});
		/*}#1IIHSCTNV0Code*/
		return {seg:JumpToStart,result:(result),preSeg:"1IIHSCTNV0",outlet:"1IIHSP1QC0"};
	};
	PushIssue.jaxId="1IIHSCTNV0"
	PushIssue.url="PushIssue@"+agentURL
	
	segs["JumpToStart"]=JumpToStart=async function(input){//:1IIHSEQHQ0
		let result=input;
		return {seg:AskHandle,result:result,preSeg:"1IIHSEQHQ0",outlet:"1IIHSP1QC1"};
	
	};
	JumpToStart.jaxId="1IIHSEQHQ0"
	JumpToStart.url="JumpToStart@"+agentURL
	
	segs["PopIssue"]=PopIssue=async function(input){//:1IIHSL3420
		let result=input;
		/*#{1IIHSL3420Start*/
		let poped=issueStack.pop();
		/*}#1IIHSL3420Start*/
		if(issueStack.length===0){
			return {seg:Finish,result:(input),preSeg:"1IIHSL3420",outlet:"1IIHSP1QC2"};
		}
		/*#{1IIHSL3420Post*/
		let curIssue=issueStack[issueStack.length-1];
		issue=curIssue.issue;
		issueBrief=curIssue.brief;
		AnalyzeIssue.messages.push({role:"user",content:JSON.stringify({result:"IssueResoveld",content:`问题: ${poped.brief}已解决。`})});
		result={result:"BackToIssue",content:`现在回到问题：${issueBrief}上，看看这个问题是否已解决，还需要做什么？`};
		/*}#1IIHSL3420Post*/
		return {seg:AnalyzeIssue,result:(result),preSeg:"1IIHSL3420",outlet:"1IIHSP1QC3"};
	};
	PopIssue.jaxId="1IIHSL3420"
	PopIssue.url="PopIssue@"+agentURL
	
	segs["AskResloved"]=AskResloved=async function(input){//:1IIHST3J20
		let prompt=("请判断当前问题是否真的已经解决，如果你认为还没有解决，请给出建议。")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("是的，问题已解决"):("Yes, the issue has been resolved")),code:0},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:SumGuide,result:(result),preSeg:"1IIHST3J20",outlet:"1IIHST3IE0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:true,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {seg:PushUserGuide,result:(result),preSeg:"1IIHST3J20",outlet:"1IIHT4PT80"};
		}else if(item.code===0){
			return {seg:SumGuide,result:(result),preSeg:"1IIHST3J20",outlet:"1IIHST3IE0"};
		}
		return {seg:PushUserGuide,result:(result),preSeg:"1IIHST3J20",outlet:"1IIHT4PT80"};
	};
	AskResloved.jaxId="1IIHST3J20"
	AskResloved.url="AskResloved@"+agentURL
	
	segs["PushUserGuide"]=PushUserGuide=async function(input){//:1IIHT1MM00
		let result=input
		/*#{1IIHT1MM00Code*/
		/*}#1IIHT1MM00Code*/
		return {seg:AnalyzeIssue,result:(result),preSeg:"1IIHT1MM00",outlet:"1IIHT4PT81"};
	};
	PushUserGuide.jaxId="1IIHT1MM00"
	PushUserGuide.url="PushUserGuide@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1IIUQJUKS0
		let result;
		let sourcePath=pathLib.join(basePath,"./SysAskUser.js");
		let arg=input;
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:AnalyzeIssue,result:(result),preSeg:"1IIUQJUKS0",outlet:"1IIUQKU3R0"};
	};
	AskUser.jaxId="1IIUQJUKS0"
	AskUser.url="AskUser@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"SysHandleIssue",
		url:agentURL,
		autoStart:true,
		jaxId:"1IH66KKV20",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{issue,issueBrief}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IH66KKV20PreEntry*/
			/*}#1IH66KKV20PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IH66KKV20PostEntry*/
			/*}#1IH66KKV20PostEntry*/
			return result;
		},
		/*#{1IH66KKV20MoreAgentAttrs*/
		endChat:function(result){
			task.endTask(result);
			return result;
		}
		/*}#1IH66KKV20MoreAgentAttrs*/
	};
	/*#{1IH66KKV20PostAgent*/
	/*}#1IH66KKV20PostAgent*/
	return agent;
};
/*#{1IH66KKV20ExCodes*/
/*}#1IH66KKV20ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "SysHandleIssue",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				issue:{type:"string",description:"要解决的问题描述"},
				issueBrief:{type:"string",description:"问题的简洁描述"}
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
		name:"SysHandleIssue",showName:"SysHandleIssue",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"issue":{name:"issue",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"issueBrief":{name:"issueBrief",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","issue","issueBrief","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["SysHandleIssue"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['issue']=");this.genAttrStatement(seg.getAttr("issue"));coder.packText(";");coder.newLine();
			coder.packText("args['issueBrief']=");this.genAttrStatement(seg.getAttr("issueBrief"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/SysHandleIssue.js",args,false);`);coder.newLine();
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
/*#{1IH66KKV20PostDoc*/
/*}#1IH66KKV20PostDoc*/


export default SysHandleIssue;
export{SysHandleIssue,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IH66KKV20",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IH66KKV21",
//			"attrs": {
//				"SysHandleIssue": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IH66KKV27",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IH66KKV28",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IH66KKV29",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IH66KKV210",
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
//			"jaxId": "1IH66KKV22",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH66KKV23",
//			"attrs": {
//				"issue": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IH66PRPI0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要解决的问题描述"
//					}
//				},
//				"issueBrief": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHVR4TKC0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "问题的简洁描述",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IH66KKV24",
//			"attrs": {
//				"env": {
//					"type": "auto",
//					"valText": "#globalContext.env"
//				},
//				"project": {
//					"type": "auto",
//					"valText": "#globalContext.project"
//				},
//				"dirName": {
//					"type": "string",
//					"valText": "#project.dirName"
//				},
//				"dirPath": {
//					"type": "auto",
//					"valText": "#project.dirPath"
//				},
//				"tools": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"bashContent": {
//					"type": "string",
//					"valText": ""
//				},
//				"task": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"guide": {
//					"type": "string",
//					"valText": ""
//				},
//				"useRagGuide": {
//					"type": "bool",
//					"valText": "false"
//				},
//				"ragGuide": {
//					"type": "string",
//					"valText": ""
//				},
//				"fixResult": {
//					"type": "string",
//					"valText": ""
//				},
//				"solution": {
//					"type": "string",
//					"valText": ""
//				},
//				"issueLogs": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"tryTask": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"orgIssue": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"issueStack": {
//					"type": "auto",
//					"valText": "[]"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IH66KKV25",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IH66KKV26",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IH77THGP0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "65",
//						"y": "635",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IH77U7G00",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCCSQGV0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IHCCSQGV0",
//					"attrs": {
//						"id": "InitIssue",
//						"viewName": "",
//						"label": "",
//						"x": "270",
//						"y": "635",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHCD4HSJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCD4HSJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHCD4HSD0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHA3IF990"
//						},
//						"catchlet": {
//							"jaxId": "1IHCD4HSD1",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHCCTSTT0"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH780CKO0",
//					"attrs": {
//						"id": "AskRag",
//						"viewName": "",
//						"label": "",
//						"x": "815",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH78IF7H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH78IF7H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH78IF790",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH7CTE2O0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IIBEO7G30",
//					"attrs": {
//						"id": "AskSolution",
//						"viewName": "",
//						"label": "",
//						"x": "815",
//						"y": "405",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIBFN77J0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIBFN77J1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": {
//							"type": "string",
//							"valText": "Enter the solution",
//							"localize": {
//								"EN": "Enter the solution",
//								"CN": "请输入解决方案"
//							},
//							"localizable": true
//						},
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IIBETGBT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH7CTE2O0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH7CTE2O0",
//					"attrs": {
//						"id": "InitTools",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH7CU43V0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH7CU43V1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH7CU43Q0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH78614B0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IH78554O0",
//					"attrs": {
//						"id": "TrySolution",
//						"viewName": "",
//						"label": "",
//						"x": "2560",
//						"y": "95",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH78IF7H6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH78IF7H7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysHandleTask.js",
//						"argument": "{\"task\":\"#`尝试解决问题: ${issueBrief}`\",\"roleTask\":\"#`你是一个根据解决方案尝试解决项目问题的AI。 \\\\n\\\\n你按照指引一步一步的执行，直到解决了当前项目遇到的问题:  \\\\n\\\\n${issue}注意：你只需要解决当前的问题，你可以验证当前问题是否解决。你不要做其他与解决当前问题无关的事情，比如完成整个项目部署，测试项目运行等。`\",\"prjDesc\":\"\",\"guide\":\"#`当前找到的解决方案:\\\\n\\\\`\\\\`\\\\`markdown\\\\n${input.content}\\\\n\\\\`\\\\`\\\\``\",\"tools\":\"fixIssue\",\"handleIssue\":\"#false\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IH78IF793",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH78D7FH0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IH78614B0",
//					"attrs": {
//						"id": "AnalyzeIssue",
//						"viewName": {
//							"type": "string",
//							"valText": "AnalyzeIssue",
//							"localize": {
//								"EN": "AnalyzeIssue",
//								"CN": "分析问题"
//							},
//							"localizable": true
//						},
//						"label": "",
//						"x": "1300",
//						"y": "320",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH78IF7H8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH78IF7H9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "",
//						"mode": "$plan",
//						"system": "#`\n---\n### 角色与任务：\n你是一个针对软件开发、部署遇到的问题，分析原因，查找资料，给出问题解决方案的AI。\n\n---\n### 项目环境\n当前的系统软硬件环境和系统参数为：\n\\`\\`\\`\n${JSON.stringify(env,null,\"\\t\")}\n\\`\\`\\`\n\n---\n### 当前项目\n当前的项目是：${project.name}。\n${project.dirPath?`当前项目所在的文件路径是: \"${project.dirPath}\"。`:\"\"}  \n\n当前项目工作进展：  \n-${project.progress.join(\" \\n\\n- \")}\n\n${project.conda?`注意：当前已经为工程创建/选择了conda环境：${project.conda}, 正常情况下，不需要创建新的conda环境。`:\"\"}\n\n---\n### 问题\n在进行工作步骤\"${task.parentTask.desc}\"时，遇到了问题： \n${issue}。\n\n在遇到问题时的工作日志为：\n${JSON.stringify(task.parentTask.tailLogs(5),null,\"\\t\")}\n\n---\n### 系统知识库中找到的问题相关参考资料：\n${guide?guide:\"暂无。\"}\n\n${tools?`---\\n### 外部工具/智能体: \\n分析问题，查找解决方案的时候可能需要调用外部的工具/AI智能体，当前可以调用的工具/AI智能体有:\\n\\`\\`\\`\\n${JSON.stringify(tools.getScope(),null,\"\\t\")}\\n\\`\\`\\`\\n`:\"\"}\n\n---\n### 对话\n你只负责分析问题和生成问题解决方案，而不要试图直接尝试解决问题。生成解决方案后，会有专门的智能体进行尝试，\n每一轮对话，你根据当前的步骤执行情况和用户反馈，生成下一个步骤要执行或与用户沟通的内容，并用JSON格式返回。\n\n- 你的解决方案应该包括明确单一方案的操作指南，不要提供多个方案让用户选择。如果找到多个方案需要用户选择，先通过与对话确定使用哪个方案，再生成单一方案的操作指南。\n\n- 如果你找到了解决方案，设置返回JSON的\"action\"属性为\"Solution\"，并在\"content\"属性中包含解决方案的markdown文本。\n\n- 生成解决方案后，系统会进行方案验证，如果成功，则结束当前对话（返回JSON的\"action\"属性设置为\"Finish\")。\n\n- 如果系统验证方案不能解决问题，请继续分析，生成新的解决方案。\n\n- 如果你判定当前问题无法解决，例如环境硬件条件不满足，缺少必要的账号等，设置返回JSON的\"action\"属性为\"Abort\"，并在\"content\"属性里说明原因。\n\n---\n### 返回的JSON对象属性说明：\n\n- 属性\"action\": {string}, 下一步的动作。可取值：\n\t- \"Solution\": 找到了解决方案，设置\"content\"属性为解决方案的markdown文本。\n\t- \"Cammand\": 通过命令行执行操作，比如用ls查看文件列表，请注意你只能利用这些命令来分析问题和生成解决方案，而不要试图在这里解决问题。\n    ${tools?`- \"Tool\": 调用外部工具完成特定任务，调用的工具名称放在'tool'属性里， 调用的参数/描述放在'toolArg'属性里`:\"\"}\n    - \"Chat\": 需要用户辅助时，与用户对话，提示需要用户手动进行的动作，例如：询问API-Key；登陆环境；提升当前权限(sudo)等，其它时候尽量避免打扰用户。\n    - \"Finish\": 如果你生成的解决方案通过了验证，结束任务，返回总结\n    - \"Abort\": 如果你判定任务无法解决（例如或者当前的硬件环境无法满足项目需求）终止任务。\n\n- 属性\"commands\": {array<string>}，当\"action\"为\"Command\"时，要执行的bash命令数组。\n    - 为防止错过纠正问题的机会，一次不要执行太多的命令，\n    - 你生成的必须是可以执行的bash命令\n    - 你生成的命令只能用来分析问题/生成解决方案，所以不要增加、删除或修改文件\n\n- 属性\"content\": {string}, 当前步骤的解释描述。例如当\"action\"为\"Abort\"时，终止原因的说明；当\"action\"为\"Finish\"时，对任务执行情况的完成总结；当\"action\"为\"Solution\"时，问题的解决方案。\n\n${tools?`- 属性\"tool\": 要调用的外部工具名称\\n`:\"\"}\n${tools?`- 属性\"toolArg\": 调用的外部工具的参数/自然语言任务描述，例如：\"将README.md翻译为中文。\\n\"`:\"\"}\n\n\n\n\n`",
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
//							"jaxId": "1IH78IF794",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH78A2610"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1IHFRQ5VD0",
//									"attrs": {
//										"prompt": "",
//										"reply": "解决方案：无法找到'Decord'库的版本\n在尝试安装'Decord'库时无法找到可用版本，可能是由以下原因之一导致的：\n\nPyPI 源的问题：默认的 PyPI 源可能没有更新版本的'Decord'库，或者此库尚未上传到 PyPI。\n版本不兼容：可能是当前的 Python 版本与'Decord'库的要求不兼容。\n平台限制：某些库可能只支持特定平台或架构。\n网络问题：网络连接问题可能导致无法正常访问 PyPI。\n解决步骤\n尝试指定源安装：可以尝试从其他源安装'Decord'库，特别是如果它在其他镜像上可用。\n\npip install decord -i https://pypi.tuna.tsinghua.edu.cn/simple\n检查 Python 版本和平台兼容性：确保当前的 Python 版本和平台与'Decord'库兼容。可以查阅'Decord'的官方文档或 GitHub 仓库以确定支持的版本。\n\n从源码安装：如果 PyPI 上没有可用的版本，可以尝试从'Decord'的官方 GitHub 仓库克隆代码并手动安装：\n\ngit clone https://github.com/dmlc/decord.git\ncd decord\npython setup.py install\n检查网络连接：确保网络连接正常，并且能够访问到 PyPI。\n\n请尝试上述解决步骤，看看能否解决该问题。"
//									}
//								}
//							]
//						},
//						"shareChatName": "",
//						"keepChat": "All messages",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"1IHDPJBJ90\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IH78A2610",
//					"attrs": {
//						"id": "CheckAnalyze",
//						"viewName": "",
//						"label": "",
//						"x": "1555",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH78IF7H10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH78IF7H11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH78IF7A1",
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
//									"jaxId": "1IH78CCEV0",
//									"attrs": {
//										"id": "Solution",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH78IF7H12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH78IF7H13",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Solution\""
//									},
//									"linkedSeg": "1IHFPSOC20"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH78V6J60",
//									"attrs": {
//										"id": "Chat",
//										"desc": "输出节点。",
//										"output": "#input.content",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH790RE40",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH790RE41",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Chat\""
//									},
//									"linkedSeg": "1IIUQJUKS0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH78NST40",
//									"attrs": {
//										"id": "Bash",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH78SBJD0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH78SBJD1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Command\""
//									},
//									"linkedSeg": "1IHGC1QM10"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH78QMCR0",
//									"attrs": {
//										"id": "Tool",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH78SBJD2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH78SBJD3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Tool\""
//									},
//									"linkedSeg": "1IHGC2VAC0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IH78D7FH0",
//					"attrs": {
//						"id": "CheckResult",
//						"viewName": "",
//						"label": "",
//						"x": "2795",
//						"y": "95",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH78IF7H20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH78IF7H21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH78IF7A3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": "#`尝试解决问题没有成功：${input.content}`"
//							},
//							"linkedSeg": "1IIHSN3L70"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH78IF7A2",
//									"attrs": {
//										"id": "Adressed",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IH78IF7H22",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH78IF7H23",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result===\"Finish\""
//									},
//									"linkedSeg": "1IIHST3J20"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IIHRRGNO0",
//									"attrs": {
//										"id": "Issue",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IIHSP1QH0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IIHSP1QH1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result===\"Issue\""
//									},
//									"linkedSeg": "1IIHSCTNV0"
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
//					"jaxId": "1IH78HD9N0",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "4515",
//						"y": "95",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IH78IF7H30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH78IF7H31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH78IF7A5",
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
//					"def": "connector",
//					"jaxId": "1IH78LL3G0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1495",
//						"y": "405",
//						"outlet": {
//							"jaxId": "1IH78SBJD13",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH78S3SB0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH78R6NV0",
//					"attrs": {
//						"id": "RunTool",
//						"viewName": "",
//						"label": "",
//						"x": "2065",
//						"y": "395",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH78SBJD17",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH78SBJD18",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH78SBJ85",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH790GSH0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IH78S3SB0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1325",
//						"y": "405",
//						"outlet": {
//							"jaxId": "1IH78SBJD19",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH78614B0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IH78VU0G0",
//					"attrs": {
//						"id": "AskChat",
//						"viewName": "",
//						"label": "",
//						"x": "1785",
//						"y": "655",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH790RE42",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH790RE43",
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
//							"jaxId": "1IH790RE00",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IH790GSH0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2335",
//						"y": "250",
//						"outlet": {
//							"jaxId": "1IH790RE44",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH7DJNSF0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IH7DJNSF0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2360",
//						"y": "470",
//						"outlet": {
//							"jaxId": "1IH7E1CVK4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHA4CBQV0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IIBHPL6R0",
//					"attrs": {
//						"id": "SaveNote",
//						"viewName": "",
//						"label": "",
//						"x": "2335",
//						"y": "95",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIBHRHF70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIBHRHF71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/RagPush.js",
//						"argument": "{\"address\":\"\",\"doc\":\"#input.content\",\"desc\":\"#`解决问题：${issueBrief}`\",\"tags\":\"issue,solution\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IIBHRHEV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH78554O0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IHA3IF990",
//					"attrs": {
//						"id": "AskHandle",
//						"viewName": "",
//						"label": "",
//						"x": "550",
//						"y": "485",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "是否尝试查询并解决这个问题？您也可以直接输入指导意见。",
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1IHA45QV80",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1IHB3PT8G0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHA3IF8H0",
//									"attrs": {
//										"id": "Handle",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Search and attempt to resolve this issue",
//											"localize": {
//												"EN": "Search and attempt to resolve this issue",
//												"CN": "查询并尝试解决问题"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHA45QVE0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHA45QVE1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/find.svg"
//									},
//									"linkedSeg": "1IH780CKO0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IIBETGBR0",
//									"attrs": {
//										"id": "Solution",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Provide a solution",
//											"localize": {
//												"EN": "Provide a solution",
//												"CN": "提供解决方案"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IIBFN77K0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IIBFN77K1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IIBEO7G30"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHA3IF8H2",
//									"attrs": {
//										"id": "Manually",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Manually address issue",
//											"localize": {
//												"EN": "Manually address issue",
//												"CN": "手动解决问题"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHA45QVE2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHA45QVE3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/mouse.svg"
//									},
//									"linkedSeg": "1IHA4780H0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHA3IF8H1",
//									"attrs": {
//										"id": "Skip",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Ignore this issue",
//											"localize": {
//												"EN": "Ignore this issue",
//												"CN": "忽略这个问题"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHA45QVE4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHA45QVE5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/moveback.svg"
//									},
//									"linkedSeg": "1IHA3SETP0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHA3RMK90",
//					"attrs": {
//						"id": "ChatResult",
//						"viewName": "",
//						"label": "",
//						"x": "1015",
//						"y": "655",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHA45QVE6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHA45QVE7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHA45QV81",
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
//					"jaxId": "1IHA3SETP0",
//					"attrs": {
//						"id": "SkipResult",
//						"viewName": "",
//						"label": "",
//						"x": "815",
//						"y": "560",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHA45QVE8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHA45QVE9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHA45QV82",
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
//					"def": "askConfirm",
//					"jaxId": "1IHA3U04V0",
//					"attrs": {
//						"id": "WaitHandle",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "555",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Please press the 'continue' button after solving the issue.",
//							"localize": {
//								"EN": "Please press the 'continue' button after solving the issue.",
//								"CN": "请在解决问题后请按\"继续\"按钮。"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHA3U04D0",
//									"attrs": {
//										"id": "Continue",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Continue",
//											"localize": {
//												"EN": "Continue",
//												"CN": "继续"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHA45QVE10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHA45QVE11",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHA4FMOR0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHA3U04D1",
//									"attrs": {
//										"id": "Cancel",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Cancel",
//											"localize": {
//												"EN": "Cancel",
//												"CN": "取消"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHA45QVE12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHA45QVE13",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHA4AAQA0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IHA4780H0",
//					"attrs": {
//						"id": "KeepBash",
//						"viewName": "",
//						"label": "",
//						"x": "815",
//						"y": "485",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHA4CS610",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHA4CS611",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Content",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IHA4CS5S0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHA3U04V0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHA4AAQA0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1205",
//						"y": "725",
//						"outlet": {
//							"jaxId": "1IHA4CS612",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHA4AGH50"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHA4AGH50",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "585",
//						"y": "725",
//						"outlet": {
//							"jaxId": "1IHA4CS613",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHA3IF990"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHA4B3890",
//					"attrs": {
//						"id": "ManualResult",
//						"viewName": "",
//						"label": "",
//						"x": "2335",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHA4CS614",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHA4CS615",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHA4CS5S1",
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
//					"def": "connector",
//					"jaxId": "1IHA4CBQV0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1680",
//						"y": "470",
//						"outlet": {
//							"jaxId": "1IHA4CS616",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH78LL3G0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IHA4FMOR0",
//					"attrs": {
//						"id": "TrackBash",
//						"viewName": "",
//						"label": "",
//						"x": "1305",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHA4I7K40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHA4I7K41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Content",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IHA4I7JV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHA4LPN40"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IHA4LPN40",
//					"attrs": {
//						"id": "SumManual",
//						"viewName": "",
//						"label": "",
//						"x": "1535",
//						"y": "540",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1IHA4O48K0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHA4O48K1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "$plan",
//						"system": "#`\n--- \n### 角色任务\n你是软件项目遇到问题解决后，分析用户的操作，总结解决方案的AI\n\n--- \n### 当前环境\n当前的系统软硬件环境和系统参数为：\n\\`\\`\\`\n${JSON.stringify(env,null,\"\\t\")}\n\\`\\`\\`\n\n--- \n### 当前的项目\n当前的项目是：${project.name}。\n${project.dirPath?`当前项目所在的文件路径是: \"${project.dirPath}\"。`:\"\"}  \n\n--- \n### 遇到的问题\n项目工作遇到的问题： \n${issue}\n\n\n--- \n### 找到的问题相关参考资料  \n${ragGuide?ragGuide:\"暂无\"}\n\n---\n### 用户的操记录\n${input}\n\n---\n### 输出\n请用JSON输出解决问题的总结\n\n- 属性 \"guide\": {string}: 针对问题，参考用户的执行过程，生成解决问题的解决方案文档，markdown格式。\n\n`\n",
//						"temperature": "0",
//						"maxToken": "3912",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "请生成回复JSON",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IHA4O48F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II03D91U0"
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
//					"def": "callLLM",
//					"jaxId": "1IHA4P5370",
//					"attrs": {
//						"id": "SumGuide",
//						"viewName": "",
//						"label": "",
//						"x": "3305",
//						"y": "25",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1IHA4P5371",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHA4P5380",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "",
//						"mode": "$plan",
//						"system": "#`\n--- \n### 角色任务\n你是软件项目遇到问题解决后，总结解决方案的AI\n\n--- \n### 当前环境\n当前的系统软硬件环境和系统参数为：\n\\`\\`\\`\n${JSON.stringify(env,null,\"\\t\")}\n\\`\\`\\`\n\n--- \n### 当前的项目\n当前的项目是：${project.name}。\n${project.dirPath?`当前项目所在的文件路径是: \"${project.dirPath}\"。`:\"\"}  \n\n--- \n### 遇到的问题\n项目工作遇到的问题： \n${issue}\n\n\n--- \n### 找到的问题相关参考资料  \n${ragGuide?ragGuide:\"暂无\"}\n\n---\n### 实际执行的解决方案\n${solution}\n\n---\n### 执行问题解决方案的过程日志：\n${JSON.stringify(tryTask.tailLogs(50),null,\"\\t\")}\n\n---\n### 输出\n请用JSON输出解决问题的总结\n\n- 属性 \"refIsOK\" {bool}: 参考资料内容是否完全正确，如果没有参考资料，设置为false\n- 属性 \"guide\": {string}: 如果没有参考资料，或者参考资料的内容不完全正确，总结正确的参考资料，markdown格式。\n\n`\n",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "用JSON输出总结",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IHA4P5381",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI8L15I0"
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
//					"def": "aiBot",
//					"jaxId": "1IHA4RDVD0",
//					"attrs": {
//						"id": "PushManualRAG",
//						"viewName": "",
//						"label": "",
//						"x": "2045",
//						"y": "540",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IHA4UBJV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHA4UBJV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/RagPush.js",
//						"argument": "{\"desc\":\"#`解决问题：${issueBrief}`\",\"doc\":\"#input.guide\",\"tags\":\"issue,solution\",\"env\":\"#env\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IHA4UBJQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHA4B3890"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IHARSDG50",
//					"attrs": {
//						"id": "RunBash",
//						"viewName": "",
//						"label": "",
//						"x": "2065",
//						"y": "320",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHARTCCI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHARTCCI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/ToolBashCommand.js",
//						"argument": "{\"commands\":\"#input.commands\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IHARTCCD0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH790GSH0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IHB3PT8G0",
//					"attrs": {
//						"id": "Chat",
//						"viewName": "",
//						"label": "",
//						"x": "815",
//						"y": "655",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHB3QGI40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHB3QGI41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IHB3QGHP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHA3RMK90"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHCCTSTT0",
//					"attrs": {
//						"id": "FailIssue",
//						"viewName": "",
//						"label": "",
//						"x": "550",
//						"y": "825",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHCD4HSJ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHCD4HSJ3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHCD4HSD2",
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
//					"jaxId": "1IHCODNRO0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3810",
//						"y": "110",
//						"outlet": {
//							"jaxId": "1IHCOE6P51",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIHSL3420"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IHFPSOC20",
//					"attrs": {
//						"id": "ShowSolution",
//						"viewName": "",
//						"label": "",
//						"x": "1810",
//						"y": "140",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHFQ7LRB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHFQ7LRB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input.content",
//						"outlet": {
//							"jaxId": "1IHFQ7LR30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHFPUNF80"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IHFPUNF80",
//					"attrs": {
//						"id": "AskTry",
//						"viewName": "",
//						"label": "",
//						"x": "2060",
//						"y": "140",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "是否尝试这个解决方案？您也可以提出对解决方案的修改意见",
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1IHFQ7LR31",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "true"
//							},
//							"linkedSeg": "1IH790GSH0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHFPUNEM0",
//									"attrs": {
//										"id": "Try",
//										"desc": "输出节点。",
//										"text": "执行解决方案",
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHFQ7LRB2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHFQ7LRB3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/run.svg"
//									},
//									"linkedSeg": "1IIBHPL6R0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1II1F3H1M0",
//									"attrs": {
//										"id": "Edit",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Manual Edit",
//											"localize": {
//												"EN": "Manual Edit",
//												"CN": "手动编辑"
//											},
//											"localizable": true
//										},
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1II1F3H1U0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1II1F3H1U1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/edit.svg"
//									},
//									"linkedSeg": "1II1EPQMB0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHFPUNEM1",
//									"attrs": {
//										"id": "Reject",
//										"desc": "输出节点。",
//										"text": "否决，重新寻找解决方案",
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IHFQ7LRB4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHFQ7LRB5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/close.svg"
//									},
//									"linkedSeg": "1IH790GSH0"
//								}
//							]
//						},
//						"silent": "false",
//						"placeholder": {
//							"type": "string",
//							"valText": "Suggestions for modifying the solution",
//							"localize": {
//								"EN": "Suggestions for modifying the solution",
//								"CN": "对解决方案的修改建议"
//							},
//							"localizable": true
//						}
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHFQ7EF10",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2845",
//						"y": "470",
//						"outlet": {
//							"jaxId": "1IHFQ7LRB6",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH7DJNSF0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askUIDlg",
//					"jaxId": "1II1EPQMB0",
//					"attrs": {
//						"id": "EditSolution",
//						"viewName": "",
//						"label": "",
//						"x": "2335",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II1F3H1U2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II1F3H1U3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "/@editkit/ui/DlgLongText.js",
//						"callArg": "#{title:\"编辑解决方案\",text:input.content}",
//						"role": "Assistant",
//						"tip": "",
//						"showResult": "false",
//						"outlet": {
//							"jaxId": "1II1F3H1M1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II1ESTVS0"
//						}
//					},
//					"icon": "idcard.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IHGC1QM10",
//					"attrs": {
//						"id": "TipBash",
//						"viewName": "",
//						"label": "",
//						"x": "1810",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHGC47Q90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHGC47Q91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IHGC47Q10",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHARSDG50"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IHGC2VAC0",
//					"attrs": {
//						"id": "TipTool",
//						"viewName": "",
//						"label": "",
//						"x": "1810",
//						"y": "395",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHGC47Q92",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHGC47Q93",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input.content",
//						"outlet": {
//							"jaxId": "1IHGC47Q11",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH78R6NV0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IHI8L15I0",
//					"attrs": {
//						"id": "CheckGuide",
//						"viewName": "",
//						"label": "",
//						"x": "3545",
//						"y": "25",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHI8O5N10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI8O5N11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI8O5MR0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IHCODNRO0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHI8O5MQ0",
//									"attrs": {
//										"id": "NewGuide",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHI8O5N12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHI8O5N13",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!input.refIsOK"
//									},
//									"linkedSeg": "1IHI8M4FL0"
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
//					"jaxId": "1IHI8M4FL0",
//					"attrs": {
//						"id": "ShowNewGuide",
//						"viewName": "",
//						"label": "",
//						"x": "3800",
//						"y": "10",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHI8O5N14",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI8O5N15",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`这是新生成的问题解决指南：  ${input.guide}`",
//						"outlet": {
//							"jaxId": "1IHI8O5MR1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II00TVTU0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1II00TVTU0",
//					"attrs": {
//						"id": "PushRAG",
//						"viewName": "",
//						"label": "",
//						"x": "4055",
//						"y": "10",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II0128EP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II0128EP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/RagPush.js",
//						"argument": "{\"desc\":\"#`解决问题：${issueBrief}`\",\"doc\":\"#input.guide\",\"tags\":\"issue,solution\",\"env\":\"#env\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1II0128EH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIHSL3420"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1II03D91U0",
//					"attrs": {
//						"id": "ShowManualGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1775",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II03FK7H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II03FK7H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`这是根据你的操作生成的问题解决指南：  \n${input.guide}\n`",
//						"outlet": {
//							"jaxId": "1II03FK7E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHA4RDVD0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1II1ESTVS0",
//					"attrs": {
//						"id": "ShowAgain",
//						"viewName": "",
//						"label": "",
//						"x": "2560",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "AskHandle",
//						"outlet": {
//							"jaxId": "1II1F3H1M2",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IIHSCTNV0",
//					"attrs": {
//						"id": "PushIssue",
//						"viewName": "",
//						"label": "",
//						"x": "3050",
//						"y": "140",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IIHSP1QI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIHSP1QI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIHSP1QC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIHSEQHQ0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IIHSEQHQ0",
//					"attrs": {
//						"id": "JumpToStart",
//						"viewName": "",
//						"label": "",
//						"x": "3305",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "AskHandle",
//						"outlet": {
//							"jaxId": "1IIHSP1QC1",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IIHSL3420",
//					"attrs": {
//						"id": "PopIssue",
//						"viewName": "",
//						"label": "",
//						"x": "4290",
//						"y": "110",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIHSP1QI2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIHSP1QI3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIHSP1QC3",
//							"attrs": {
//								"id": "Issue",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IIHSMOIF0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IIHSP1QC2",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IIHSP1QI4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IIHSP1QI5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#issueStack.length===0"
//									},
//									"linkedSeg": "1IH78HD9N0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IIHSMOIF0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "4420",
//						"y": "310",
//						"outlet": {
//							"jaxId": "1IIHSP1QI6",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIHT3MVP0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IIHSN3L70",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2965",
//						"y": "310",
//						"outlet": {
//							"jaxId": "1IIHSP1QI7",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHFQ7EF10"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IIHST3J20",
//					"attrs": {
//						"id": "AskResloved",
//						"viewName": "",
//						"label": "",
//						"x": "3050",
//						"y": "40",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"prompt": "请判断当前问题是否真的已经解决，如果你认为还没有解决，请给出建议。",
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1IIHT4PT80",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1IIHT1MM00"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IIHST3IE0",
//									"attrs": {
//										"id": "Resovled",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Yes, the issue has been resolved",
//											"localize": {
//												"EN": "Yes, the issue has been resolved",
//												"CN": "是的，问题已解决"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IIHT4PTD0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IIHT4PTD1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHA4P5370"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IIHT1MM00",
//					"attrs": {
//						"id": "PushUserGuide",
//						"viewName": "",
//						"label": "",
//						"x": "3305",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IIHT4PTD2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIHT4PTD3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIHT4PT81",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIHT3MVP0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IIHT3MVP0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3485",
//						"y": "310",
//						"outlet": {
//							"jaxId": "1IIHT4PTD4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIHSN3L70"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IIUQJUKS0",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "1810",
//						"y": "250",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIUQKU410",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIUQKU411",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysAskUser.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IIUQKU3R0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH790GSH0"
//						}
//					},
//					"icon": "agent.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}