//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IKCV9VRJ0MoreImports*/
import {tabNT} from "/@tabos";
/*}#1IKCV9VRJ0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1IKCV9VRJ0StartDoc*/
import {AATools} from "/@tabos/AATools.js";
/*}#1IKCV9VRJ0StartDoc*/
//----------------------------------------------------------------------------
let SysTabOSChat=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ShowLogo,TipStart,InitTools,StartTip,CheckArg,JumpTool,AskInput,GenAction,CaseAction,CheckCmd,RunCommand,ShowResult,TryNode,TryTool,DoChat,TipFinish,TipAbort,LogError,NodeError,ToolError,ShowNode,ShowTool,CallTool,TipNodeRes,TipToolRes,NextAction,NextStep,AddChat,AskNext,CallNode;
	let orgInput=null;
	let cokeEnv=null;
	let cokeTty=null;
	let cmdText="";
	
	/*#{1IKCV9VRJ0LocalVals*/
	/*}#1IKCV9VRJ0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IKCV9VRJ0ParseArgs*/
		/*}#1IKCV9VRJ0ParseArgs*/
	}
	
	/*#{1IKCV9VRJ0PreContext*/
	/*}#1IKCV9VRJ0PreContext*/
	context={
		aaTools: "",
		toolIndex: "",
		curTool: "",
		agentNodes: "",
		curNode: "",
		/*#{1IKCV9VRJ5ExCtxAttrs*/
		/*}#1IKCV9VRJ5ExCtxAttrs*/
	};
	context=VFACT.flexState(context);
	/*#{1IKCV9VRJ0PostContext*/
	/*}#1IKCV9VRJ0PostContext*/
	let agent,segs={};
	segs["ShowLogo"]=ShowLogo=async function(input){//:1IKE6TS810
		let result=input;
		let role="assistant";
		let content=" ";
		/*#{1IKE6TS810PreCodes*/
		/*}#1IKE6TS810PreCodes*/
		let vo={image:"/~/tabos/shared/assets/aalogo.svg"};
		/*#{1IKE6TS810Options*/
		vo.button=false;
		vo.icon=false;
		/*}#1IKE6TS810Options*/
		session.addChatText(role,content,vo);
		/*#{1IKE6TS810PostCodes*/
		/*}#1IKE6TS810PostCodes*/
		return {seg:TipStart,result:(result),preSeg:"1IKE6TS810",outlet:"1IKE6TS820"};
	};
	ShowLogo.jaxId="1IKE6TS810"
	ShowLogo.url="ShowLogo@"+agentURL
	
	segs["TipStart"]=TipStart=async function(input){//:1IKE6V3JM0
		let result=input;
		let opts={};
		let role="assistant";
		let content=(($ln==="CN")?("欢迎使用AI2Apps系统对话."):("Welcome to the AI2Apps System Chat."));
		session.addChatText(role,content,opts);
		return {seg:InitTools,result:(result),preSeg:"1IKE6V3JM0",outlet:"1IKE74LT70"};
	};
	TipStart.jaxId="1IKE6V3JM0"
	TipStart.url="TipStart@"+agentURL
	
	segs["InitTools"]=InitTools=async function(input){//:1IKCVA57O0
		let result=input
		/*#{1IKCVA57O0Code*/
		let tools;
		tools=context.aaTools=new AATools();
		await tools.load();
		context.toolIndex=tools.getToolDescIndex();
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
		
		//Init cokeEnv&tty
		cokeEnv=await session.WSCall_CreateCokeEnv();
		cokeTty=cokeEnv.tty;
		/*}#1IKCVA57O0Code*/
		return {seg:CheckArg,result:(result),preSeg:"1IKCVA57O0",outlet:"1IKCVADJI0"};
	};
	InitTools.jaxId="1IKCVA57O0"
	InitTools.url="InitTools@"+agentURL
	
	segs["StartTip"]=StartTip=async function(input){//:1IKCVAMJC0
		let result=input;
		let opts={};
		let role="user";
		let content=input.prompt||input;
		/*#{1IKCVAMJC0PreCodes*/
		if(input.assets){
			content+=(($ln==="CN")?("\n附件: \n"):/*EN*/("\nAttachment: \n"));
			content+=input.assets.join("\n");
		}
		/*}#1IKCVAMJC0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IKCVAMJC0PostCodes*/
		/*}#1IKCVAMJC0PostCodes*/
		return {seg:CheckCmd,result:(result),preSeg:"1IKCVAMJC0",outlet:"1IKCVDSRP0"};
	};
	StartTip.jaxId="1IKCVAMJC0"
	StartTip.url="StartTip@"+agentURL
	
	segs["CheckArg"]=CheckArg=async function(input){//:1IKCVBKKB0
		let result=input;
		/*#{1IKCVBKKB0Start*/
		session.debugLog("orgInput: "+orgInput);
		/*}#1IKCVBKKB0Start*/
		if(!orgInput){
			return {seg:AskInput,result:(input),preSeg:"1IKCVBKKB0",outlet:"1IKCVDSRP1"};
		}
		if(orgInput.tool){
			let output=orgInput;
			return {seg:JumpTool,result:(output),preSeg:"1IKCVBKKB0",outlet:"1IMRPT4F10"};
		}
		/*#{1IKCVBKKB0Post*/
		/*}#1IKCVBKKB0Post*/
		return {seg:StartTip,result:(result),preSeg:"1IKCVBKKB0",outlet:"1IKCVDSRP2"};
	};
	CheckArg.jaxId="1IKCVBKKB0"
	CheckArg.url="CheckArg@"+agentURL
	
	segs["JumpTool"]=JumpTool=async function(input){//:1IMRL8FIK0
		let result=input;
		/*#{1IMRL8FIK0PreCodes*/
		let chatMem;
		let assets,list,url,ext,toolPath,tools,i,n,tool,toolId;
		let content,opts;
		toolPath=input.tool;//.filePath;
		tools=context.aaTools.getTools();
		n=tools.length;
		FindTool:{
			for(i=0;i<n;i++){
				tool=tools[i];
				if(tool.filePath===toolPath){
					toolId="Tool-"+i;
					context.curTool=tool;
					break;
				}
			}
			toolId="Tool-??";
		}
		assets=list=input.assets;
		let prompt=input.prompt;
		if(assets){
			prompt=input.prompt;
			prompt+=`\n- - -\n\n# Assets URLs: \n\n[\n\n`
			for(url of assets){
				prompt+=`\t${url}, \n\n`
			}
			prompt+=`]\n- - -\n\n`
		}
		chatMem=GenAction.messages;
		chatMem.push({role:"user",content:prompt});
		result={
			action:"tool",
			tool:toolId,
			prompt:prompt
		};
		chatMem.push({role:"assistant",content:JSON.stringify(result)});
		content=(($ln==="CN")?(`### 调用智能体: \n- 智能体：${context.curTool.getNameText()} \n- 调用提示：${input.prompt}`):/*EN*/(`### Call agent: \n- Agent: ${context.curTool.getNameText()} \n- Prompt: ${input.prompt}`))
		opts={icon:"/~/-tabos/shared/assets/gas_e.svg"};
		session.addChatText("assistant",content,opts);
		/*}#1IMRL8FIK0PreCodes*/
		return {seg:CallTool,result:result,preSeg:"1IKD04LRQ0",outlet:"1IMRPT4F20"};
	
	};
	JumpTool.jaxId="1IKD04LRQ0"
	JumpTool.url="JumpTool@"+agentURL
	
	segs["AskInput"]=AskInput=async function(input){//:1IKCVCHC90
		let tip=("");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(true)||false;
		let text=("");
		let result="";
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		return {seg:CheckCmd,result:(result),preSeg:"1IKCVCHC90",outlet:"1IKCVDSRP3"};
	};
	AskInput.jaxId="1IKCVCHC90"
	AskInput.url="AskInput@"+agentURL
	
	segs["GenAction"]=GenAction=async function(input){//:1IKCVDIJ50
		let prompt;
		let result=null;
		/*#{1IKCVDIJ50Input*/
		/*}#1IKCVDIJ50Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"$expert",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=GenAction.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
你是一个根据用户输入，选择适合的Tool(本地智能体)或Node(外部智能体节点)运行，与用户对话，完成任务的AI。

当前的Tools（本地智能体工具）有:
${JSON.stringify(context.toolIndex,null,"\t")}

当前的Nodes（外部智能体节点）有:
${JSON.stringify(context.agentNodes,null,"\t")}

- - -

- 第一轮对话时，用户输入的是要完成的任务也可能是简单的对话。你根据用户的输入，选择合适的Tool执行任务，或者与用户对话。

- 每一回合对话，跟根据当前对话/任务执行的情况，回复一个JSON对象。
- 如果需要执行一个Tool，设置回复JSON中的"action"属性为"tool"；设置"tool"属性是下一步要执行的Tool(智能体)的名称; 回复JSON中的prompt属性是调用这个Tool的输入指令。例如：
{
	"action":"tool",
	"tool":"Tool-3",
    "prompt":"Search for: Who is the winner of 2024 F1?"
}
注意: 如果输入包含附件，生成的调用tool的prompt属性的文本里，应该包含全部的附件。

- 如果需要执行一个Node，设置回复JSON中的"action"属性为"node"；回复JSON中的"node"属性是下一步要执行的Node（外部智能体）的名称; 回复JSON中的prompt属性是调用这个Tool的输入指令。例如：
{
	"action":"node",
	"node":"DrawNode",
    "prompt":"Draw picture of a cute fat cat."
}

- 执行Tool或Node的结果会在对话中告知。你根据任务目标以及当前的执行情况，可能需要继续选择新的Tool/Node进一步执行。

- 如果同时有Tool和Node可以执行当前的任务需求，优先使用Tool，如果Tool执行失败或无法完成任务再尝试Node。

- 如果回答用户的输入不需要使用任何tool，回复将JSON中的"action"属性设置为"finish"，用回复JSON中的"content"属性回答用户。例如：当用户询问："西瓜是一种水果么？"，你的回复：
{
	"action":"finish",
	"content":"是的，西瓜是一种水果。"
}

- 如果成功的完成了用户提出的任务，回复将JSON中的"action"属性设置为"finish"，并通过"content"属性总结汇报执行情况。例如
{
	"action":"finish",
    "content":"论坛帖子已经成功发布。"
}

- 如果执行Tool出现错误，请分析错误原因，如果是参数问题或者需要提供更多的参数，请使用修正后的调用prompt重新调用Tool

- 如果执行Tool出现错误，分析原因后，你认为无法完成用户的任务，设置回复JSON中的"action"属性为"abort"，并在"content"属性中说明原因。例如:
{
	"action":"abort",
    "content":"没有登录脸书账号，无法发布新的内容。"
}

- 如果没有Tool或Node可以完成用户的要求，设置回复JSON中的"action"属性为"missingTool"，请设计一个或多个用来完成用户需求的Tool，在回复JSON中用"missingTools"数组属性里描述缺失的Tool。例如：
{
	"action":"missingTool",
	"missingTools":[
    	"检查脸书账号登录状态",
        "发布脸书动态"
    ]
}

- 如果执行任务需要用户提供更多的信息，设置回复JSON中的"action"属性为"chat"，要询问用户的内容放在"content"属性里。例如，需要用户提供邮箱地址：
{
	"action":"chat",
	"content":"请告诉我你的电子邮箱地址"
}
`},
		];
		messages.push(...chatMem);
		/*#{1IKCVDIJ50PrePrompt*/
		let assets,images,docs,audios;
		if(input.prompt){
			let list,url,ext;
			assets=list=input.assets;
			if(list){
				docs=[];
				images=[];
				for(url of list){
					if(url.startsWith("hub://")){
						ext=pathLib.extname(url).toLowerCase();
						if(ext===".jpeg" || ext===".png" || ext===".jpg"){
							images.push(await session.normURL(url));
						}else if(ext===".md" || ext===".htm" || ext===".html"|| ext===".txt"
								|| ext===".js" || ext===".py" || ext===".mjs" || ext===".css" 
								|| ext===".c" || ext===".cpp" || ext===".sh"  || ext===".java"){
							let buf,docText;
							buf=await session.loadHubFile(url);
							buf=Base64.decodeBytes(buf);
							docText=new TextDecoder().decode(buf);
							docs.push(`\n---\n## Asset "${url}" text conent:\n\n ${docText}\n\n## Asset ${url} end.\n\n---\n`);
						}
					}
				}
				images=images.length?images:null;
				docs=docs.length?docs:null;
			}else{
				input=input.prompt;
			}
		}
		/*}#1IKCVDIJ50PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IKCVDIJ50FilterMessage*/
			let embedAssets=false;
			if(assets){
				let url
				prompt=input.prompt;
				prompt+=`\n- - -\n\n# Assets URLs:\n\n[\n\n`
				for(url of assets){
					prompt+=`\t${url}, \n\n`
				}
				prompt+=`]\n- - -\n\n`
				if(embedAssets && docs){
					let chatText,docText;
					chatText=prompt+"- - -\n\n# Text Asset file contents:\n\n";
					for(docText of docs){
						chatText+=docText;
					}
					prompt=chatText;
				}
				if(embedAssets && images){
					let content=[{type:"text",text:prompt}];
					for(let url of images){
						content.push({type:"image_url","image_url":{"url":url}});
					}
					msg={role:"user",content:content};
					prompt=msg.content;
				}else{
					msg={role:"user",content:prompt};
					prompt=msg.content;
				}
			}
			/*}#1IKCVDIJ50FilterMessage*/
			messages.push(msg);
		}
		/*#{1IKCVDIJ50PreCall*/
		/*}#1IKCVDIJ50PreCall*/
		result=(result===null)?(await session.callSegLLM("GenAction@"+agentURL,opts,messages,true)):result;
		/*#{1IKCVDIJ50PostLLM*/
		/*}#1IKCVDIJ50PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1IKCVDIJ50PostClear*/
			/*}#1IKCVDIJ50PostClear*/
		}
		result=trimJSON(result);
		/*#{1IKCVDIJ50PostCall*/
		/*}#1IKCVDIJ50PostCall*/
		return {seg:CaseAction,result:(result),preSeg:"1IKCVDIJ50",outlet:"1IKCVDSRP4"};
	};
	GenAction.jaxId="1IKCVDIJ50"
	GenAction.url="GenAction@"+agentURL
	GenAction.messages=[];
	
	segs["CaseAction"]=CaseAction=async function(input){//:1IKCVE61A0
		let result=input;
		if(input.action==="node"){
			let output=input;
			return {seg:TryNode,result:(output),preSeg:"1IKCVE61A0",outlet:"1IKCVL5P90"};
		}
		if(input.action==="tool"){
			let output=input;
			return {seg:TryTool,result:(output),preSeg:"1IKCVE61A0",outlet:"1IKCVFA8O0"};
		}
		if(input.action==="chat"){
			let output=input;
			return {seg:DoChat,result:(output),preSeg:"1IKCVE61A0",outlet:"1IKCVHF4K0"};
		}
		if(input.action==="finish"){
			let output=input;
			return {seg:TipFinish,result:(output),preSeg:"1IKCVE61A0",outlet:"1IKCVHK4J0"};
		}
		if(input.action==="abort"){
			let output=input;
			return {seg:TipAbort,result:(output),preSeg:"1IKCVE61A0",outlet:"1IKCVHPS90"};
		}
		result=input;
		return {result:result};
	};
	CaseAction.jaxId="1IKCVE61A0"
	CaseAction.url="CaseAction@"+agentURL
	
	segs["CheckCmd"]=CheckCmd=async function(input){//:1IKCVIQND0
		let result=input;
		/*#{1IKCVIQND0Start*/
		let isCommand=false;
		if(typeof(input)==="string" && input[0]==="/"){
			let cmd;
			input=input.substring(1);
			cmd=input.split(" ")[0];
			if(cmd){
				cmd=await cokeEnv.getCmdFunc(cmd,input);
				if(cmd){
					isCommand=true;
				}
			}
		}
		/*}#1IKCVIQND0Start*/
		if(isCommand){
			/*#{1IKCVL5P92Codes*/
			/*}#1IKCVL5P92Codes*/
			return {seg:RunCommand,result:(input),preSeg:"1IKCVIQND0",outlet:"1IKCVL5P92"};
		}
		/*#{1IKCVIQND0Post*/
		/*}#1IKCVIQND0Post*/
		return {seg:GenAction,result:(result),preSeg:"1IKCVIQND0",outlet:"1IKCVL5P93"};
	};
	CheckCmd.jaxId="1IKCVIQND0"
	CheckCmd.url="CheckCmd@"+agentURL
	
	segs["RunCommand"]=RunCommand=async function(input){//:1IKCVJFTJ0
		let result=input
		/*#{1IKCVJFTJ0Code*/
		let orgContentLen,content;
		cmdText=input;
		orgContentLen=cokeTty.getContent().length;
		await cokeEnv.execCmd(input);
		content=cokeTty.getContent();
		result=content.substring(orgContentLen);
		/*}#1IKCVJFTJ0Code*/
		return {seg:ShowResult,result:(result),preSeg:"1IKCVJFTJ0",outlet:"1IKCVL5P94"};
	};
	RunCommand.jaxId="1IKCVJFTJ0"
	RunCommand.url="RunCommand@"+agentURL
	
	segs["ShowResult"]=ShowResult=async function(input){//:1IKCVK9ES0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		/*#{1IKCVK9ES0PreCodes*/
		content=`#### Command:\n\`\`\`\n${input}\n\`\`\`\n`;
		opts.icon="/~/-tabos/shared/assets/terminal.svg";
		/*}#1IKCVK9ES0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IKCVK9ES0PostCodes*/
		result=`---\nExcute command:  \n\n${cmdText}\n---\n $Command excute result:  \n\n${input}`;
		/*}#1IKCVK9ES0PostCodes*/
		return {seg:AskInput,result:(result),preSeg:"1IKCVK9ES0",outlet:"1IKCVL5PA0"};
	};
	ShowResult.jaxId="1IKCVK9ES0"
	ShowResult.url="ShowResult@"+agentURL
	
	segs["TryNode"]=TryNode=async function(input){//:1IKCVMUAG0
		let result=input;
		/*#{1IKCVMUAG0Code*/
		false
		/*}#1IKCVMUAG0Code*/
		return {seg:ShowNode,result:(result),preSeg:"1IKCVMUAG0",outlet:"1IKCVQU3L0",catchSeg:NodeError,catchlet:"1IKCVQU3O2"};
	};
	TryNode.jaxId="1IKCVMUAG0"
	TryNode.url="TryNode@"+agentURL
	
	segs["TryTool"]=TryTool=async function(input){//:1IKCVNB7A0
		let result=input;
		/*#{1IKCVNB7A0Code*/
		false
		/*}#1IKCVNB7A0Code*/
		return {seg:ShowTool,result:(result),preSeg:"1IKCVNB7A0",outlet:"1IKCVQU3L1",catchSeg:ToolError,catchlet:"1IKCVQU3O5"};
	};
	TryTool.jaxId="1IKCVNB7A0"
	TryTool.url="TryTool@"+agentURL
	
	segs["DoChat"]=DoChat=async function(input){//:1IKCVNLLO0
		let result;
		let arg=input.content;
		let sourcePath=pathLib.joinTabOSURL(basePath,"./SysTabOSAskUser.js");
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:AddChat,result:(result),preSeg:"1IKCVNLLO0",outlet:"1IKCVQU3L2"};
	};
	DoChat.jaxId="1IKCVNLLO0"
	DoChat.url="DoChat@"+agentURL
	
	segs["TipFinish"]=TipFinish=async function(input){//:1IKCVOA650
		let result=input;
		let opts={};
		let role="assistant";
		let content=input.content;
		session.addChatText(role,content,opts);
		return {seg:AskNext,result:(result),preSeg:"1IKCVOA650",outlet:"1IKCVQU3L3"};
	};
	TipFinish.jaxId="1IKCVOA650"
	TipFinish.url="TipFinish@"+agentURL
	
	segs["TipAbort"]=TipAbort=async function(input){//:1IKCVOQ6C0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input.content;
		session.addChatText(role,content,opts);
		return {seg:AskNext,result:(result),preSeg:"1IKCVOQ6C0",outlet:"1IKCVQU3L4"};
	};
	TipAbort.jaxId="1IKCVOQ6C0"
	TipAbort.url="TipAbort@"+agentURL
	
	segs["LogError"]=LogError=async function(input){//:1IKCVU57C0
		let result=input
		/*#{1IKCVU57C0Code*/
		session.addChatText("error",""+input);
		/*}#1IKCVU57C0Code*/
		return {seg:GenAction,result:(result),preSeg:"1IKCVU57C0",outlet:"1IKD025ML0"};
	};
	LogError.jaxId="1IKCVU57C0"
	LogError.url="LogError@"+agentURL
	
	segs["NodeError"]=NodeError=async function(input){//:1IKD005D30
		let result=input;
		return {seg:LogError,result:result,preSeg:"1IKCVU57C0",outlet:"1IKD025ML1"};
	
	};
	NodeError.jaxId="1IKCVU57C0"
	NodeError.url="NodeError@"+agentURL
	
	segs["ToolError"]=ToolError=async function(input){//:1IKD00IP70
		let result=input;
		return {seg:LogError,result:result,preSeg:"1IKCVU57C0",outlet:"1IKD025ML2"};
	
	};
	ToolError.jaxId="1IKCVU57C0"
	ToolError.url="ToolError@"+agentURL
	
	segs["ShowNode"]=ShowNode=async function(input){//:1IKD03BL10
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		/*#{1IKD03BL10PreCodes*/
		/*}#1IKD03BL10PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IKD03BL10PostCodes*/
		let node;
		node=context.curNode=context.agentNodes[input.node];
		if(!node){
			throw `AgentNode "${input.node}" not found. Are you confusing Node and Tool?`;
		}
		context.curNode={...node,name:input.node,prompt:input.prompt};
		/*}#1IKD03BL10PostCodes*/
		return {seg:CallNode,result:(result),preSeg:"1IKD03BL10",outlet:"1IKD046QG0"};
	};
	ShowNode.jaxId="1IKD03BL10"
	ShowNode.url="ShowNode@"+agentURL
	
	segs["ShowTool"]=ShowTool=async function(input){//:1IKD03VM90
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		/*#{1IKD03VM90PreCodes*/
		let toolId=input.tool;
		toolId=parseInt(toolId.substring("Tool-".length));
		let tool=context.aaTools.getTools()[toolId];
		if(!tool){
			throw `Tool "${input.tool}" not found. Are you confusing Node and Tool? Choose tool or agent node.`;
		}
		context.curTool=tool;
		content=(($ln==="CN")?(`### 调用工具: \n- 工具：${context.curTool.getNameText()} \n- 调用提示：${input.prompt}`):/*EN*/(`### Call tool: \n- Tool: ${context.curTool.getNameText()} \n- Prompt: ${input.prompt}`))
		opts.icon="/~/-tabos/shared/assets/gas_e.svg";
		/*}#1IKD03VM90PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IKD03VM90PostCodes*/
		/*}#1IKD03VM90PostCodes*/
		return {seg:CallTool,result:(result),preSeg:"1IKD03VM90",outlet:"1IKD046QG1"};
	};
	ShowTool.jaxId="1IKD03VM90"
	ShowTool.url="ShowTool@"+agentURL
	
	segs["CallTool"]=CallTool=async function(input){//:1IKD04LRQ0
		let result=input
		/*#{1IKD04LRQ0Code*/
		let tools=context.aaTools;
		let tool=context.curTool;
		let toolPath=tool.filePath;
		let prompt=input.prompt;
		if(typeof(prompt)!=="string"){
			prompt=JSON.stringify(prompt);
		}
		session.debugLog({type:"CallTool",tool:toolPath,prompt:prompt});
		result=await tools.execTool(VFACT.app,tool,prompt,session);
		session.debugLog({type:"ToolResult",tool:toolPath,result:result});
		/*}#1IKD04LRQ0Code*/
		return {seg:TipToolRes,result:(result),preSeg:"1IKD04LRQ0",outlet:"1IKD0BI2O1"};
	};
	CallTool.jaxId="1IKD04LRQ0"
	CallTool.url="CallTool@"+agentURL
	
	segs["TipNodeRes"]=TipNodeRes=async function(input){//:1IKD04TDE0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		/*#{1IKD04TDE0PreCodes*/
		content=content.content||content;
		opts.txtHeader=context.curTool.name+(($ln==="CN")?(" 返回:"):/*EN*/(" result:"));
		/*}#1IKD04TDE0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IKD04TDE0PostCodes*/
		result=`Call agent node result: ${JSON.stringify(input)}`;
		/*}#1IKD04TDE0PostCodes*/
		return {seg:NextAction,result:(result),preSeg:"1IKD04TDE0",outlet:"1IKD0BI2O2"};
	};
	TipNodeRes.jaxId="1IKD04TDE0"
	TipNodeRes.url="TipNodeRes@"+agentURL
	
	segs["TipToolRes"]=TipToolRes=async function(input){//:1IKD0580Q0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		/*#{1IKD0580Q0PreCodes*/
		content=content?(content.content||content):{result:"Unkonwn",content:"无执行结果"};
		opts.txtHeader=context.curTool.getNameText()+(($ln==="CN")?(" 返回:"):/*EN*/(" result:"));
		opts.icon="/~/-tabos/shared/assets/arrowleft.svg";
		/*}#1IKD0580Q0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IKD0580Q0PostCodes*/
		result=`Call tool result: ${JSON.stringify(input)}`;
		/*}#1IKD0580Q0PostCodes*/
		return {seg:NextAction,result:(result),preSeg:"1IKD0580Q0",outlet:"1IKD0BI2O3"};
	};
	TipToolRes.jaxId="1IKD0580Q0"
	TipToolRes.url="TipToolRes@"+agentURL
	
	segs["NextAction"]=NextAction=async function(input){//:1IKD09MJ10
		let result=input;
		return {seg:NextStep,result:result,preSeg:"1IKD0ABJJ0",outlet:"1IKD0BI2O4"};
	
	};
	NextAction.jaxId="1IKD0ABJJ0"
	NextAction.url="NextAction@"+agentURL
	
	segs["NextStep"]=NextStep=async function(input){//:1IKD0ABJJ0
		let result=input
		/*#{1IKD0ABJJ0Code*/
		/*}#1IKD0ABJJ0Code*/
		return {seg:GenAction,result:(result),preSeg:"1IKD0ABJJ0",outlet:"1IKD0BI2O5"};
	};
	NextStep.jaxId="1IKD0ABJJ0"
	NextStep.url="NextStep@"+agentURL
	
	segs["AddChat"]=AddChat=async function(input){//:1IKDJNI2I0
		let result=input
		/*#{1IKDJNI2I0Code*/
		/*}#1IKDJNI2I0Code*/
		return {seg:NextAction,result:(result),preSeg:"1IKDJNI2I0",outlet:"1IKDJOFUD0"};
	};
	AddChat.jaxId="1IKDJNI2I0"
	AddChat.url="AddChat@"+agentURL
	
	segs["AskNext"]=AskNext=async function(input){//:1IKE77PS40
		let tip=("");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(true)||false;
		let text=("");
		let result="";
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		return {seg:CheckCmd,result:(result),preSeg:"1IKE77PS40",outlet:"1IKE789LQ0"};
	};
	AskNext.jaxId="1IKE77PS40"
	AskNext.url="AskNext@"+agentURL
	
	segs["CallNode"]=CallNode=async function(input){//:1IKEN0POL0
		let result,args={};
		args['nodeName']=context.curNode.name;
		args['callAgent']=context.curNode.entry;
		args['callArg']=context.curNode.prompt;
		args['checkUpdate']=true;
		/*#{1IKEN0POL0PreCodes*/
		/*}#1IKEN0POL0PreCodes*/
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		/*#{1IKEN0POL0PostCodes*/
		/*}#1IKEN0POL0PostCodes*/
		return {seg:TipNodeRes,result:(result),preSeg:"1IKEN0POL0",outlet:"1IKEN357K0"};
	};
	CallNode.jaxId="1IKEN0POL0"
	CallNode.url="CallNode@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"SysTabOSChat",
		url:agentURL,
		autoStart:true,
		jaxId:"1IKCV9VRJ0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IKCV9VRJ0PreEntry*/
			orgInput=input;
			/*}#1IKCV9VRJ0PreEntry*/
			result={seg:ShowLogo,"input":input};
			/*#{1IKCV9VRJ0PostEntry*/
			/*}#1IKCV9VRJ0PostEntry*/
			return result;
		},
		/*#{1IKCV9VRJ0MoreAgentAttrs*/
		/*}#1IKCV9VRJ0MoreAgentAttrs*/
	};
	/*#{1IKCV9VRJ0PostAgent*/
	/*}#1IKCV9VRJ0PostAgent*/
	return agent;
};
/*#{1IKCV9VRJ0ExCodes*/
/*}#1IKCV9VRJ0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IKCV9VRJ0PostDoc*/
/*}#1IKCV9VRJ0PostDoc*/


export default SysTabOSChat;
export{SysTabOSChat};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IKCV9VRJ0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IKCV9VRJ1",
//			"attrs": {
//				"SysTabOSChat": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IKCV9VRJ7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IKCV9VRK0",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IKCV9VRK1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IKCV9VRK2",
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
//			"jaxId": "1IKCV9VRJ2",
//			"attrs": {}
//		},
//		"entry": "ShowLogo",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IKCV9VRJ3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IKCV9VRJ4",
//			"attrs": {
//				"orgInput": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"cokeEnv": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"cokeTty": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"cmdText": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IKCV9VRJ5",
//			"attrs": {
//				"aaTools": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IKD11ON80",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"toolIndex": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IKD11ON81",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"curTool": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IKD11ON84",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"agentNodes": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IKD11ON82",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"curNode": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IKD12IIT0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1IKCV9VRJ6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "image",
//					"jaxId": "1IKE6TS810",
//					"attrs": {
//						"id": "ShowLogo",
//						"viewName": "",
//						"label": "",
//						"x": "30",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKE6TS811",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKE6TS812",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"text": " ",
//						"image": "#\"/~/tabos/shared/assets/aalogo.svg\"",
//						"role": "Assistant",
//						"sizeLimit": "",
//						"format": "JEPG",
//						"outlet": {
//							"jaxId": "1IKE6TS820",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKE6V3JM0"
//						}
//					},
//					"icon": "hudimg.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKE6V3JM0",
//					"attrs": {
//						"id": "TipStart",
//						"viewName": "",
//						"label": "",
//						"x": "265",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKE74LTG0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKE74LTG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "Welcome to the AI2Apps System Chat.",
//							"localize": {
//								"EN": "Welcome to the AI2Apps System Chat.",
//								"CN": "欢迎使用AI2Apps系统对话."
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IKE74LT70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVA57O0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IKCVA57O0",
//					"attrs": {
//						"id": "InitTools",
//						"viewName": "",
//						"label": "",
//						"x": "495",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVADJL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVADJL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKCVADJI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVBKKB0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKCVAMJC0",
//					"attrs": {
//						"id": "StartTip",
//						"viewName": "",
//						"label": "",
//						"x": "935",
//						"y": "475",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVDSRQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVDSRQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "User",
//						"text": "#input.prompt||input",
//						"outlet": {
//							"jaxId": "1IKCVDSRP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVIQND0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IKCVBKKB0",
//					"attrs": {
//						"id": "CheckArg",
//						"viewName": "",
//						"label": "",
//						"x": "715",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVDSRQ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVDSRQ3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKCVDSRP2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IKCVAMJC0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKCVDSRP1",
//									"attrs": {
//										"id": "NoArgs",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKCVDSRQ4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKCVDSRQ5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!orgInput"
//									},
//									"linkedSeg": "1IKCVCHC90"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IMRPT4F10",
//									"attrs": {
//										"id": "EntryTool",
//										"desc": "输出节点。",
//										"output": "#orgInput",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMRQJ5O40",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMRQJ5O41",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#orgInput.tool"
//									},
//									"linkedSeg": "1IMRL8FIK0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IMRL8FIK0",
//					"attrs": {
//						"id": "JumpTool",
//						"viewName": "",
//						"label": "",
//						"x": "935",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1IKD04LRQ0",
//						"outlet": {
//							"jaxId": "1IMRPT4F20",
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
//					"def": "askChat",
//					"jaxId": "1IKCVCHC90",
//					"attrs": {
//						"id": "AskInput",
//						"viewName": "",
//						"label": "",
//						"x": "935",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVDSRQ6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVDSRQ7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "true",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IKCVDSRP3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVIQND0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IKCVDIJ50",
//					"attrs": {
//						"id": "GenAction",
//						"viewName": "",
//						"label": "",
//						"x": "1450",
//						"y": "465",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVDSRQ8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVDSRQ9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "$expert",
//						"system": "#`\n你是一个根据用户输入，选择适合的Tool(本地智能体)或Node(外部智能体节点)运行，与用户对话，完成任务的AI。\n\n当前的Tools（本地智能体工具）有:\n${JSON.stringify(context.toolIndex,null,\"\\t\")}\n\n当前的Nodes（外部智能体节点）有:\n${JSON.stringify(context.agentNodes,null,\"\\t\")}\n\n- - -\n\n- 第一轮对话时，用户输入的是要完成的任务也可能是简单的对话。你根据用户的输入，选择合适的Tool执行任务，或者与用户对话。\n\n- 每一回合对话，跟根据当前对话/任务执行的情况，回复一个JSON对象。\n- 如果需要执行一个Tool，设置回复JSON中的\"action\"属性为\"tool\"；设置\"tool\"属性是下一步要执行的Tool(智能体)的名称; 回复JSON中的prompt属性是调用这个Tool的输入指令。例如：\n{\n\t\"action\":\"tool\",\n\t\"tool\":\"Tool-3\",\n    \"prompt\":\"Search for: Who is the winner of 2024 F1?\"\n}\n注意: 如果输入包含附件，生成的调用tool的prompt属性的文本里，应该包含全部的附件。\n\n- 如果需要执行一个Node，设置回复JSON中的\"action\"属性为\"node\"；回复JSON中的\"node\"属性是下一步要执行的Node（外部智能体）的名称; 回复JSON中的prompt属性是调用这个Tool的输入指令。例如：\n{\n\t\"action\":\"node\",\n\t\"node\":\"DrawNode\",\n    \"prompt\":\"Draw picture of a cute fat cat.\"\n}\n\n- 执行Tool或Node的结果会在对话中告知。你根据任务目标以及当前的执行情况，可能需要继续选择新的Tool/Node进一步执行。\n\n- 如果同时有Tool和Node可以执行当前的任务需求，优先使用Tool，如果Tool执行失败或无法完成任务再尝试Node。\n\n- 如果回答用户的输入不需要使用任何tool，回复将JSON中的\"action\"属性设置为\"finish\"，用回复JSON中的\"content\"属性回答用户。例如：当用户询问：\"西瓜是一种水果么？\"，你的回复：\n{\n\t\"action\":\"finish\",\n\t\"content\":\"是的，西瓜是一种水果。\"\n}\n\n- 如果成功的完成了用户提出的任务，回复将JSON中的\"action\"属性设置为\"finish\"，并通过\"content\"属性总结汇报执行情况。例如\n{\n\t\"action\":\"finish\",\n    \"content\":\"论坛帖子已经成功发布。\"\n}\n\n- 如果执行Tool出现错误，请分析错误原因，如果是参数问题或者需要提供更多的参数，请使用修正后的调用prompt重新调用Tool\n\n- 如果执行Tool出现错误，分析原因后，你认为无法完成用户的任务，设置回复JSON中的\"action\"属性为\"abort\"，并在\"content\"属性中说明原因。例如:\n{\n\t\"action\":\"abort\",\n    \"content\":\"没有登录脸书账号，无法发布新的内容。\"\n}\n\n- 如果没有Tool或Node可以完成用户的要求，设置回复JSON中的\"action\"属性为\"missingTool\"，请设计一个或多个用来完成用户需求的Tool，在回复JSON中用\"missingTools\"数组属性里描述缺失的Tool。例如：\n{\n\t\"action\":\"missingTool\",\n\t\"missingTools\":[\n    \t\"检查脸书账号登录状态\",\n        \"发布脸书动态\"\n    ]\n}\n\n- 如果执行任务需要用户提供更多的信息，设置回复JSON中的\"action\"属性为\"chat\"，要询问用户的内容放在\"content\"属性里。例如，需要用户提供邮箱地址：\n{\n\t\"action\":\"chat\",\n\t\"content\":\"请告诉我你的电子邮箱地址\"\n}\n`",
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
//							"jaxId": "1IKCVDSRP4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVE61A0"
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IKCVE61A0",
//					"attrs": {
//						"id": "CaseAction",
//						"viewName": "",
//						"label": "",
//						"x": "1685",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVL5PC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVL5PC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKCVL5P91",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": "#input"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKCVL5P90",
//									"attrs": {
//										"id": "CallNode",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKCVL5PC2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKCVL5PC3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"node\""
//									},
//									"linkedSeg": "1IKCVMUAG0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKCVFA8O0",
//									"attrs": {
//										"id": "CallTool",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKCVL5PC4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKCVL5PC5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"tool\""
//									},
//									"linkedSeg": "1IKCVNB7A0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKCVHF4K0",
//									"attrs": {
//										"id": "Chat",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKCVL5PC6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKCVL5PC7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"chat\""
//									},
//									"linkedSeg": "1IKCVNLLO0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKCVHK4J0",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKCVL5PC8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKCVL5PC9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"finish\""
//									},
//									"linkedSeg": "1IKCVOA650"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKCVHPS90",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKCVL5PC10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKCVL5PC11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"abort\""
//									},
//									"linkedSeg": "1IKCVOQ6C0"
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
//					"jaxId": "1IKCVIQND0",
//					"attrs": {
//						"id": "CheckCmd",
//						"viewName": "",
//						"label": "",
//						"x": "1195",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVL5PC12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVL5PC13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKCVL5P93",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IKCVDIJ50"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKCVL5P92",
//									"attrs": {
//										"id": "Command",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IKCVL5PC14",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKCVL5PC15",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#isCommand"
//									},
//									"linkedSeg": "1IKCVJFTJ0"
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
//					"jaxId": "1IKCVJFTJ0",
//					"attrs": {
//						"id": "RunCommand",
//						"viewName": "",
//						"label": "",
//						"x": "1450",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVL5PC16",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVL5PC17",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKCVL5P94",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVK9ES0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKCVK9ES0",
//					"attrs": {
//						"id": "ShowResult",
//						"viewName": "",
//						"label": "",
//						"x": "1690",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVL5PC18",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVL5PC19",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IKCVL5PA0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVKJP90"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IKCVKJP90",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1845",
//						"y": "215",
//						"outlet": {
//							"jaxId": "1IKCVL5PC20",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVKPI60"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IKCVKPI60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "965",
//						"y": "215",
//						"outlet": {
//							"jaxId": "1IKCVL5PC21",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVCHC90"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IKCVMUAG0",
//					"attrs": {
//						"id": "TryNode",
//						"viewName": "",
//						"label": "",
//						"x": "1980",
//						"y": "260",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVQU3O0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVQU3O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKCVQU3L0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKD03BL10"
//						},
//						"catchlet": {
//							"jaxId": "1IKCVQU3O2",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKD005D30"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IKCVNB7A0",
//					"attrs": {
//						"id": "TryTool",
//						"viewName": "",
//						"label": "",
//						"x": "1980",
//						"y": "360",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVQU3O3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVQU3O4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKCVQU3L1",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKD03VM90"
//						},
//						"catchlet": {
//							"jaxId": "1IKCVQU3O5",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKD00IP70"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IKCVNLLO0",
//					"attrs": {
//						"id": "DoChat",
//						"viewName": "",
//						"label": "",
//						"x": "1980",
//						"y": "450",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVQU3O6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVQU3O7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysTabOSAskUser.js",
//						"argument": "#{}#>input.content",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IKCVQU3L2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKDJNI2I0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKCVOA650",
//					"attrs": {
//						"id": "TipFinish",
//						"viewName": "",
//						"label": "",
//						"x": "1980",
//						"y": "530",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVQU3O8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVQU3O9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input.content",
//						"outlet": {
//							"jaxId": "1IKCVQU3L3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKE77PS40"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKCVOQ6C0",
//					"attrs": {
//						"id": "TipAbort",
//						"viewName": "",
//						"label": "",
//						"x": "1980",
//						"y": "620",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKCVQU3O10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKCVQU3O11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input.content",
//						"outlet": {
//							"jaxId": "1IKCVQU3L4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKE77PS40"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IKCVR1VM0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2355",
//						"y": "705",
//						"outlet": {
//							"jaxId": "1IKD025MN0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVS8430"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IKCVS8430",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1225",
//						"y": "705",
//						"outlet": {
//							"jaxId": "1IKD025MN2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVIQND0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IKCVU57C0",
//					"attrs": {
//						"id": "LogError",
//						"viewName": "",
//						"label": "",
//						"x": "1195",
//						"y": "570",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "link.svg",
//						"context": {
//							"jaxId": "1IKD025MN3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKD025MN4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKD025ML0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVDIJ50"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IKD005D30",
//					"attrs": {
//						"id": "NodeError",
//						"viewName": "",
//						"label": "",
//						"x": "2165",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "LogError",
//						"outlet": {
//							"jaxId": "1IKD025ML1",
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
//					"def": "jumper",
//					"jaxId": "1IKD00IP70",
//					"attrs": {
//						"id": "ToolError",
//						"viewName": "",
//						"label": "",
//						"x": "2165",
//						"y": "390",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "LogError",
//						"outlet": {
//							"jaxId": "1IKD025ML2",
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
//					"def": "output",
//					"jaxId": "1IKD03BL10",
//					"attrs": {
//						"id": "ShowNode",
//						"viewName": "",
//						"label": "",
//						"x": "2365",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKD046QJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKD046QJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IKD046QG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKEN0POL0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKD03VM90",
//					"attrs": {
//						"id": "ShowTool",
//						"viewName": "",
//						"label": "",
//						"x": "2365",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKD046QJ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKD046QJ3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IKD046QG1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKD04LRQ0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IKD04LRQ0",
//					"attrs": {
//						"id": "CallTool",
//						"viewName": "",
//						"label": "",
//						"x": "2600",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKD0BI2S2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKD0BI2S3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKD0BI2O1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKD0580Q0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKD04TDE0",
//					"attrs": {
//						"id": "TipNodeRes",
//						"viewName": "",
//						"label": "",
//						"x": "2840",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKD0BI2S4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKD0BI2S5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IKD0BI2O2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKD09MJ10"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKD0580Q0",
//					"attrs": {
//						"id": "TipToolRes",
//						"viewName": "",
//						"label": "",
//						"x": "2840",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKD0BI2S6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKD0BI2S7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IKD0BI2O3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKD09MJ10"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IKD09MJ10",
//					"attrs": {
//						"id": "NextAction",
//						"viewName": "",
//						"label": "",
//						"x": "3080",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "NextStep",
//						"outlet": {
//							"jaxId": "1IKD0BI2O4",
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
//					"jaxId": "1IKD0ABJJ0",
//					"attrs": {
//						"id": "NextStep",
//						"viewName": "",
//						"label": "",
//						"x": "1195",
//						"y": "490",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "link.svg",
//						"context": {
//							"jaxId": "1IKD0BI2T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKD0BI2T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKD0BI2O5",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVDIJ50"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IKDJNI2I0",
//					"attrs": {
//						"id": "AddChat",
//						"viewName": "",
//						"label": "",
//						"x": "2365",
//						"y": "450",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKDJOFUI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKDJOFUI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKDJOFUD0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKDJOVRA0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IKDJOVRA0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2955",
//						"y": "450",
//						"outlet": {
//							"jaxId": "1IKDJP5CM0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKD09MJ10"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IKE77PS40",
//					"attrs": {
//						"id": "AskNext",
//						"viewName": "",
//						"label": "",
//						"x": "2230",
//						"y": "575",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKE789M20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKE789M21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "true",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IKE789LQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVR1VM0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1IKEN0POL0",
//					"attrs": {
//						"id": "CallNode",
//						"viewName": "",
//						"label": "",
//						"x": "2600",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKEN6ELP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKEN6ELP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "#context.curNode.name",
//						"callAgent": "#context.curNode.entry",
//						"callArg": "#context.curNode.prompt",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1IKEN357K0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKD04TDE0"
//						}
//					},
//					"icon": "cloudact.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}