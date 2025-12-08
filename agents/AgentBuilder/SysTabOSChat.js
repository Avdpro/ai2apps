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
	let ShowLogo,TipStart,InitTools,StartTip,CheckArg,JumpTool,AskInput,GenAction,CaseAction,CheckCmd,RunCommand,ShowResult,TryNode,TryTool,DoChat,TipFinish,TipAbort,LogError,NodeError,ToolError,ShowNode,ShowTool,CallTool,TipNodeRes,TipToolRes,NextAction,AddChat,AskNext,CallNode,InitBash,Check,RunBash,Generate,LLM,output,ParseJson,NextStep;
	let orgInput=null;
	let cokeEnv=null;
	let cokeTty=null;
	let cmdText="";
	
	/*#{1IKCV9VRJ0LocalVals*/
	let todo="";
	let user_query="";
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
	let $agent,agent,segs={};
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
		let opts={txtHeader:($agent.showName||$agent.name||null)};
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
		context.toolIndex = Object.entries(context.toolIndex);
		context.toolIndex.push(["Tool-Bash", "这是一个用于执行命令行命令的工具，可以用于执行允许的命令行命令，如解压缩，ls，cd，执行代码文件，git，wget，brew下载等等，请提供合法的可以直接在terminal执行的命令。"]);
		//context.toolIndex.push(["Tool-Ask", "这是一个调用大语言模型问答或生成内容的工具，请提供需要询问的问题或者需要生成的内容。"]);
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
		
		//Init cokeEnv&tty
		cokeEnv=await session.WSCall_CreateCokeEnv();
		cokeTty=cokeEnv.tty;
		/*}#1IKCVA57O0Code*/
		return {seg:InitBash,result:(result),preSeg:"1IKCVA57O0",outlet:"1IKCVADJI0"};
	};
	InitTools.jaxId="1IKCVA57O0"
	InitTools.url="InitTools@"+agentURL
	
	segs["StartTip"]=StartTip=async function(input){//:1IKCVAMJC0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="user";
		let content=input.prompt||input;
		/*#{1IKCVAMJC0PreCodes*/
		if(input.assets){
			for (let i = 0; i < input.assets.length; i++) {
			input.assets[i] = await session.getHubPath(input.assets[i]);
			}
		
			content+=(($ln==="CN")?("\n附件: \n"):/*EN*/("\nAttachment: \n"));
			content+=input.assets.join("\n");
		}
		/*}#1IKCVAMJC0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IKCVAMJC0PostCodes*/
		user_query=content;
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
		let askUpward=(false);
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
			mode:"gpt-4.1",
			maxToken:32768,
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
			{role:"system",content:(($ln==="CN")?(`当前的时间是${Date().toString()}。你是一个智能路由AI，负责分析用户请求和严格按照任务规划来动态选择最佳执行方式（本地工具/外部节点/直接响应），并严格遵守决策规则。 ﻿ ## 可用资源 ### 本地工具库 (Tools): ${JSON.stringify(context.toolIndex,null,2)} ﻿ ### 外部节点库 (Nodes): ${JSON.stringify(context.agentNodes,null,2)} ﻿ ## 任务规划 ${todo} ﻿ ## 决策规则 ﻿ ### 1. 请求分类处理 - **简单查询/对话**：直接响应（action=finish） - **需工具处理**：优先本地工具（action=tool） - **需外部能力**：调用节点（action=node） - **信息不足**：发起追问（action=chat） ﻿ ### 2. 响应规范 { "action": "执行类型", // 必选字段根据action类型变化： // tool/node -> 对应工具名+prompt // finish/abort/chat -> content // missingTool -> missingTools数组 "content": "自然语言响应", "tool/node": "具体工具名", "prompt": "工具调用指令", "reason": "使用工具的原因及目的", "missingTools": [{"name":"工具名", "desc":"功能描述"}] } ﻿ ﻿ ### 3. 执行优先级 1. 本地工具（更低延迟） 2. 外部节点（更广能力） 3. 组合调用（需要时链式执行） 4. 严格按照任务规划顺序调用工具 ﻿ ### 4. 特殊处理 - **文件和文件夹操作**： - 创建、写入、修改文件和文件夹必须使用绝对路径 - 未知路径时先调用pwd工具 - 写入文件前请确认文件路径是否存在 - 确保写入的内容完整、详细 - 禁止使用echo和python3 -c - **Python代码**： - 禁止使用echo和python3 -c - 必须先写入文件再执行 - 所有字符串中的换行符 \\n 必须转义为 \\\\n，因为这段代码将通过 Node.js 的 fs.writeFile 执行 保持代码逻辑不变，只对字符串中的特殊字符进行转义处理 最终输出应该是可以直接被 Node.js 执行的字符串形式 - 自动生成合理的文件名（如script_[timestamp].py） ﻿ - **附件处理**： - 所有附件必须显式包含在prompt中（如果以hub://开头必须保留） - 格式："[附件: 文件名.扩展名] 处理要求" ﻿ ### 5. 错误处理流程 1. 参数错误 → 修正后重试 2. 权限问题 → 中止并说明（action=abort） 3. 能力缺失 → 上报需开发的工具（action=missingTool） ﻿ ## 最佳实践示例 1. 文件处理： { "action": "tool", "tool": "FileWriter", "prompt": "保存到/tmp/data_20240408.json：[附件: data.json]", "reason": "我已经得到了数据，现在需要将数据写入文件中" } ﻿ 2. 工具缺失： { "action": "missingTool", "missingTools": [ {"name": "PDF签名工具", "desc": "支持数字签名和手写签名嵌入"}, {"name": "OCR识别引擎", "desc": "支持多语言图片文字提取"} ] } ` ﻿):(`The current time is ${Date(). toString()}. You are an intelligent routing AI responsible for analyzing user requests and dynamically selecting the best execution method (local tools/external nodes/direct response) strictly according to task planning, and strictly following decision rules. ##Available resources ###Local Tools Library: ${JSON.stringify(context.toolIndex,null,2)} ###External Node Library: ${JSON.stringify(context.agentNodes,null,2)} ##Task planning ${todo} ##Decision rules ### 1. Request classification processing -* * Simple Query/Dialogue * *: Direct Response (action=finish) -* * Tool processing required * *: Prioritize local tools (action=tool) -* * External capability required * *: Call node (action=node) -Insufficient information: Initiate follow-up (action=chat) ### 2. Response specifications { "action": Execution type ", //Required fields vary according to action type: //Tool/node ->corresponding tool name+prompt // finish/abort/chat -> content //MissingTools ->missingTools array "content": Natural language response, "tool/node": Specific tool name, "prompt": 'Tool call instruction', "reason": Reasons and purposes for using tools, MissingTools ": [{" name ":" tool name "," desc ":" feature description "}] } ### 3. execution priority 1. Local tools (lower latency) 2. External nodes (with broader capabilities) 3. Combination call (chain execution when needed) 4. Strictly call the tools in the order of task planning ### 4. Special treatment -* * File and folder operations * *: -Creating, writing, and modifying files and folders must use absolute paths -Call the pwd tool first when the path is unknown -Please confirm if the file path exists before writing to the file -Ensure that the written content is complete and detailed -Prohibit the use of echo and python3-c -* * Python code * *: -Prohibit the use of echo and python3-c -Must be written to a file before execution -All line breaks in strings must be escaped as \ \ \ \ n, as this code will be executed through Node.js' fs-writeFile Keep the code logic unchanged and only escape special characters in the string The final output should be in the form of a string that can be directly executed by Node.js -Automatically generate reasonable file names (such as script_ [timestamp]. py) -Attachment processing: -All attachments must be explicitly included in the prompt -Format: [Attachment: File Name. Extension] Processing Requirements ### 5. Error handling process 1. Parameter error ->Fix and retry 2. Permission issue ->Abort and explain (action=abort) 3. Lack of ability ->Report the tool that needs to be developed (action=missingTool) ##Best practice examples 1. File processing: { "action": "tool", "tool": "FileWriter", "prompt": Save to/tmp/data_20240408.json: [Attachment: data.json]", "reason": I have obtained the data, now I need to write it to a file } 2. Missing tools: { "action": "missingTool", "missingTools": [ {"name": "PDF Signature Tool", "desc": "Supports embedding digital and handwritten signatures"}, {"name": "OCR recognition engine", "desc": "Supports multilingual image and text extraction"} ] }  Please use English.`))},
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
		docs.push(`\n---\n## Asset "${url}" text content:\n\n ${docText}\n\n## Asset ${url} end.\n\n---\n`);
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
		let opts={txtHeader:($agent.showName||$agent.name||null)};
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
		return {seg:Check,result:(result),preSeg:"1IKCVNB7A0",outlet:"1IKCVQU3L1",catchSeg:ToolError,catchlet:"1IKCVQU3O5"};
	};
	TryTool.jaxId="1IKCVNB7A0"
	TryTool.url="TryTool@"+agentURL
	
	segs["DoChat"]=DoChat=async function(input){//:1IKCVNLLO0
		let result;
		let arg=input.content;
		let agentNode=("")||null;
		let sourcePath=pathLib.joinTabOSURL(basePath,"./SysTabOSAskUser.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:AddChat,result:(result),preSeg:"1IKCVNLLO0",outlet:"1IKCVQU3L2"};
	};
	DoChat.jaxId="1IKCVNLLO0"
	DoChat.url="DoChat@"+agentURL
	
	segs["TipFinish"]=TipFinish=async function(input){//:1IKCVOA650
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=input.content;
		session.addChatText(role,content,opts);
		return {seg:AskNext,result:(result),preSeg:"1IKCVOA650",outlet:"1IKCVQU3L3"};
	};
	TipFinish.jaxId="1IKCVOA650"
	TipFinish.url="TipFinish@"+agentURL
	
	segs["TipAbort"]=TipAbort=async function(input){//:1IKCVOQ6C0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
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
		let opts={txtHeader:($agent.showName||$agent.name||null)};
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
		let opts={txtHeader:($agent.showName||$agent.name||null)};
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
		if(typeof(prompt)==="string"){
			try{
				prompt=JSON.parse(prompt);
			}catch (e){
				prompt=prompt;
			}
			
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
		let opts={txtHeader:($agent.showName||$agent.name||null)};
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
		let opts={txtHeader:($agent.showName||$agent.name||null)};
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
		return {seg:NextStep,result:result,preSeg:"1IPEEMQF00",outlet:"1IKD0BI2O4"};
	
	};
	NextAction.jaxId="1IPEEMQF00"
	NextAction.url="NextAction@"+agentURL
	
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
		let askUpward=(false);
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
		args['options']="";
		/*#{1IKEN0POL0PreCodes*/
		/*}#1IKEN0POL0PreCodes*/
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		/*#{1IKEN0POL0PostCodes*/
		/*}#1IKEN0POL0PostCodes*/
		return {seg:TipNodeRes,result:(result),preSeg:"1IKEN0POL0",outlet:"1IKEN357K0"};
	};
	CallNode.jaxId="1IKEN0POL0"
	CallNode.url="CallNode@"+agentURL
	
	segs["InitBash"]=InitBash=async function(input){//:1INT3PTSB0
		let result,args={};
		args['nodeName']="builder_new";
		args['callAgent']="Bash.js";
		args['callArg']={action:"Create",options:{client:true,ownBySession:false}};
		args['checkUpdate']=true;
		args['options']="";
		/*#{1INT3PTSB0PreCodes*/
		/*}#1INT3PTSB0PreCodes*/
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		/*#{1INT3PTSB0PostCodes*/
		globalContext.bash = result;
		result=input;
		/*}#1INT3PTSB0PostCodes*/
		return {seg:CheckArg,result:(result),preSeg:"1INT3PTSB0",outlet:"1INT3RMBL0"};
	};
	InitBash.jaxId="1INT3PTSB0"
	InitBash.url="InitBash@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1INT632680
		let result=input;
		if(input.tool === "Tool-Bash"){
			return {seg:RunBash,result:(input),preSeg:"1INT632680",outlet:"1INT63NS20"};
		}
		if(input.tool === "Tool-Ask"){
			return {seg:LLM,result:(input),preSeg:"1INT632680",outlet:"1IP1C7J7B0"};
		}
		return {seg:ShowTool,result:(result),preSeg:"1INT632680",outlet:"1INT63NS21"};
	};
	Check.jaxId="1INT632680"
	Check.url="Check@"+agentURL
	
	segs["RunBash"]=RunBash=async function(input){//:1INT68OMK0
		let result,args={};
		args['nodeName']="builder_new";
		args['callAgent']="Bash.js";
		args['callArg']={bashId:globalContext.bash,action:"Command",commands:input.prompt};
		args['checkUpdate']=true;
		args['options']="";
		/*#{1INT68OMK0PreCodes*/
		if(input.prompt.includes("echo") || input.prompt.includes("python -c") || input.prompt.includes("python3 -c")){
			result="Forbidden command";
			return {seg:NextAction,result:(result),preSeg:"1INT68OMK0",outlet:"1INT6BP5C0"};
		}
		/*}#1INT68OMK0PreCodes*/
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		/*#{1INT68OMK0PostCodes*/
		/*}#1INT68OMK0PostCodes*/
		return {seg:NextAction,result:(result),preSeg:"1INT68OMK0",outlet:"1INT6BP5C0"};
	};
	RunBash.jaxId="1INT68OMK0"
	RunBash.url="RunBash@"+agentURL
	
	segs["Generate"]=Generate=async function(input){//:1IP1BRS1S0
		let prompt;
		let result=null;
		/*#{1IP1BRS1S0Input*/
		/*}#1IP1BRS1S0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1",
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
			{role:"system",content:(($ln==="CN")?(`当前的时间是2025年。你是一个专业任务规划AI，擅长将复杂任务分解为可执行的步骤。请按照以下要求生成详细的任务清单： 你目前拥有的可用资源 ### 本地工具库 (Tools): ${JSON.stringify(context.toolIndex,null,2)} ﻿ ### 外部节点库 (Nodes): ${JSON.stringify(context.agentNodes,null,2)} ﻿ ﻿ 1. 输出格式必须严格遵循： \`\`\`markdown # [任务名称] 任务清单 ﻿ ## 阶段1: [阶段名称] - [ ] [原子级任务描述] - [ ] [下一个原子级任务] ... ﻿ ## 阶段2: [阶段名称] ... \`\`\` ﻿ 2. 分解原则： - 保持你示例中的4级结构（总任务>阶段>主任务>子任务） - 每个子任务必须是可独立执行的最小单元 - 每个任务都可以通过调用可用的工具完成，不需要人工干预 - 每个任务后表明使用的工具 ﻿ 3. 规则  - 如果需要搜索网页，请搜索后将搜索到的结果写入markdown文件，建议每搜索一次写入一个文件 - 创建文件请使用bash - 尽可能通过网页搜索获取外部最新的知识 - 撰写文档时请不要一次性写入过多内容，请依次追加写入内容，分成多个任务 - 读取文件可以一次性全部读入﻿ 直接输出markdown，不要输出其他无关内容。 `):(`The current time is 2025. You are a professional task planning AI, skilled at breaking down complex tasks into executable steps. Please generate a detailed task list according to the following requirements: The available resources you currently have ###Local Tools Library: ${JSON.stringify(context.toolIndex,null,2)} ###External Node Library: ${JSON.stringify(context.agentNodes,null,2)} 1. The output format must strictly follow: \`\`\`markdown #[Task Name] Task List ##Stage 1: [Stage Name] -[] [Atomic level task description] -[] [Next atomic level task] ... ##Stage 2: [Stage Name] ... \`\`\` 2. Decomposition principle: -Maintain the 4-level structure in your example (total task>stage>main task>subtask) -Each subtask must be the smallest unit that can be independently executed -Each task can be completed by calling available tools without the need for manual intervention -Indicate the tools used after each task 3. Rules -If you need to create and output files, please use the pwd command to check the current path in the first step, and then create a working directory (absolute path). Please check if the directory exists first, and if it does, create a new working directory name. -If you need to search for web pages, please write the search results to a markdown file after searching. It is recommended to write a file every time you search -Please use bash to create files -Try to obtain the latest external knowledge through web search as much as possible -When writing a document, please do not write too much content at once. - When reading documents， you can read at the same time instead of iteration. Please add the content in sequence and divide it into multiple tasks Output markdown directly, do not output any irrelevant content.`))},
		];
		/*#{1IP1BRS1S0PrePrompt*/
		/*}#1IP1BRS1S0PrePrompt*/
		prompt=user_query;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IP1BRS1S0FilterMessage*/
			/*}#1IP1BRS1S0FilterMessage*/
			messages.push(msg);
		}
		/*#{1IP1BRS1S0PreCall*/
		/*}#1IP1BRS1S0PreCall*/
		result=(result===null)?(await session.callSegLLM("Generate@"+agentURL,opts,messages,true)):result;
		/*#{1IP1BRS1S0PostCall*/
		todo=result;
		/*}#1IP1BRS1S0PostCall*/
		return {seg:output,result:(result),preSeg:"1IP1BRS1S0",outlet:"1IP1BSSUA0"};
	};
	Generate.jaxId="1IP1BRS1S0"
	Generate.url="Generate@"+agentURL
	
	segs["LLM"]=LLM=async function(input){//:1IP1C8N7Q0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=LLM.messages
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
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("LLM@"+agentURL,opts,messages,true);
		return {seg:NextAction,result:(result),preSeg:"1IP1C8N7Q0",outlet:"1IP1CAF0L0"};
	};
	LLM.jaxId="1IP1C8N7Q0"
	LLM.url="LLM@"+agentURL
	
	segs["output"]=output=async function(input){//:1IP1FIUT30
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=input;
		/*#{1IP1FIUT30PreCodes*/
		/*}#1IP1FIUT30PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IP1FIUT30PostCodes*/
		result=user_query;
		/*}#1IP1FIUT30PostCodes*/
		return {result:result};
	};
	output.jaxId="1IP1FIUT30"
	output.url="output@"+agentURL
	
	segs["ParseJson"]=ParseJson=async function(input){//:1IPE2KORR0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=ParseJson.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你是一个 JSON 转换助手，专门负责将用户输入的可能存在问题的JSON转换为结构化的合法 JSON 格式。请遵循以下规则：\n输出要求：\n- 必须使用双引号包裹所有键名\n- 确保字符串值使用双引号而非单引号\n- 正确处理特殊字符转义(如 \\\", \\\\, \\/, \\b, \\f, \\n, \\r, \\t)\n- 不包含尾随逗号\n- 不包含注释\n- 使用 UTF-8 编码\n\n请直接输出转换后的 JSON，不要包含任何解释或额外文本。现在开始处理用户输入：\n\n"},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("ParseJson@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {result:result};
	};
	ParseJson.jaxId="1IPE2KORR0"
	ParseJson.url="ParseJson@"+agentURL
	
	segs["NextStep"]=NextStep=async function(input){//:1IPEEMQF00
		let result=input
		/*#{1IPEEMQF00Code*/
		/*}#1IPEEMQF00Code*/
		return {seg:GenAction,result:(result),preSeg:"1IPEEMQF00",outlet:"1IPEEMQF20"};
	};
	NextStep.jaxId="1IPEEMQF00"
	NextStep.url="NextStep@"+agentURL
	
	agent=$agent={
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
//		"showName": "",
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
//						"x": "-75",
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
//						"x": "145",
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
//						"x": "330",
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
//							"linkedSeg": "1INT3PTSB0"
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
//						"askUpward": "false",
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
//						"x": "1815",
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
//						"platform": "OpenAI",
//						"mode": "gpt-4.1",
//						"system": {
//							"type": "string",
//							"valText": "#`The current time is ${Date(). toString()}. You are an intelligent routing AI responsible for analyzing user requests and dynamically selecting the best execution method (local tools/external nodes/direct response) strictly according to task planning, and strictly following decision rules. ##Available resources ###Local Tools Library: ${JSON.stringify(context.toolIndex,null,2)} ###External Node Library: ${JSON.stringify(context.agentNodes,null,2)} ##Task planning ${todo} ##Decision rules ### 1. Request classification processing -* * Simple Query/Dialogue * *: Direct Response (action=finish) -* * Tool processing required * *: Prioritize local tools (action=tool) -* * External capability required * *: Call node (action=node) -Insufficient information: Initiate follow-up (action=chat) ### 2. Response specifications { \"action\": Execution type \", //Required fields vary according to action type: //Tool/node ->corresponding tool name+prompt // finish/abort/chat -> content //MissingTools ->missingTools array \"content\": Natural language response, \"tool/node\": Specific tool name, \"prompt\": 'Tool call instruction', \"reason\": Reasons and purposes for using tools, MissingTools \": [{\" name \":\" tool name \",\" desc \":\" feature description \"}] } ### 3. execution priority 1. Local tools (lower latency) 2. External nodes (with broader capabilities) 3. Combination call (chain execution when needed) 4. Strictly call the tools in the order of task planning ### 4. Special treatment -* * File and folder operations * *: -Creating, writing, and modifying files and folders must use absolute paths -Call the pwd tool first when the path is unknown -Please confirm if the file path exists before writing to the file -Ensure that the written content is complete and detailed -Prohibit the use of echo and python3-c -* * Python code * *: -Prohibit the use of echo and python3-c -Must be written to a file before execution -All line breaks in strings must be escaped as \\ \\ \\ \\ n, as this code will be executed through Node.js' fs-writeFile Keep the code logic unchanged and only escape special characters in the string The final output should be in the form of a string that can be directly executed by Node.js -Automatically generate reasonable file names (such as script_ [timestamp]. py) -Attachment processing: -All attachments must be explicitly included in the prompt -Format: [Attachment: File Name. Extension] Processing Requirements ### 5. Error handling process 1. Parameter error ->Fix and retry 2. Permission issue ->Abort and explain (action=abort) 3. Lack of ability ->Report the tool that needs to be developed (action=missingTool) ##Best practice examples 1. File processing: { \"action\": \"tool\", \"tool\": \"FileWriter\", \"prompt\": Save to/tmp/data_20240408.json: [Attachment: data.json]\", \"reason\": I have obtained the data, now I need to write it to a file } 2. Missing tools: { \"action\": \"missingTool\", \"missingTools\": [ {\"name\": \"PDF Signature Tool\", \"desc\": \"Supports embedding digital and handwritten signatures\"}, {\"name\": \"OCR recognition engine\", \"desc\": \"Supports multilingual image and text extraction\"} ] }  Please use English.`",
//							"localize": {
//								"EN": "#`The current time is ${Date(). toString()}. You are an intelligent routing AI responsible for analyzing user requests and dynamically selecting the best execution method (local tools/external nodes/direct response) strictly according to task planning, and strictly following decision rules. ##Available resources ###Local Tools Library: ${JSON.stringify(context.toolIndex,null,2)} ###External Node Library: ${JSON.stringify(context.agentNodes,null,2)} ##Task planning ${todo} ##Decision rules ### 1. Request classification processing -* * Simple Query/Dialogue * *: Direct Response (action=finish) -* * Tool processing required * *: Prioritize local tools (action=tool) -* * External capability required * *: Call node (action=node) -Insufficient information: Initiate follow-up (action=chat) ### 2. Response specifications { \"action\": Execution type \", //Required fields vary according to action type: //Tool/node ->corresponding tool name+prompt // finish/abort/chat -> content //MissingTools ->missingTools array \"content\": Natural language response, \"tool/node\": Specific tool name, \"prompt\": 'Tool call instruction', \"reason\": Reasons and purposes for using tools, MissingTools \": [{\" name \":\" tool name \",\" desc \":\" feature description \"}] } ### 3. execution priority 1. Local tools (lower latency) 2. External nodes (with broader capabilities) 3. Combination call (chain execution when needed) 4. Strictly call the tools in the order of task planning ### 4. Special treatment -* * File and folder operations * *: -Creating, writing, and modifying files and folders must use absolute paths -Call the pwd tool first when the path is unknown -Please confirm if the file path exists before writing to the file -Ensure that the written content is complete and detailed -Prohibit the use of echo and python3-c -* * Python code * *: -Prohibit the use of echo and python3-c -Must be written to a file before execution -All line breaks in strings must be escaped as \\ \\ \\ \\ n, as this code will be executed through Node.js' fs-writeFile Keep the code logic unchanged and only escape special characters in the string The final output should be in the form of a string that can be directly executed by Node.js -Automatically generate reasonable file names (such as script_ [timestamp]. py) -Attachment processing: -All attachments must be explicitly included in the prompt -Format: [Attachment: File Name. Extension] Processing Requirements ### 5. Error handling process 1. Parameter error ->Fix and retry 2. Permission issue ->Abort and explain (action=abort) 3. Lack of ability ->Report the tool that needs to be developed (action=missingTool) ##Best practice examples 1. File processing: { \"action\": \"tool\", \"tool\": \"FileWriter\", \"prompt\": Save to/tmp/data_20240408.json: [Attachment: data.json]\", \"reason\": I have obtained the data, now I need to write it to a file } 2. Missing tools: { \"action\": \"missingTool\", \"missingTools\": [ {\"name\": \"PDF Signature Tool\", \"desc\": \"Supports embedding digital and handwritten signatures\"}, {\"name\": \"OCR recognition engine\", \"desc\": \"Supports multilingual image and text extraction\"} ] }  Please use English.`",
//								"CN": "#`当前的时间是${Date().toString()}。你是一个智能路由AI，负责分析用户请求和严格按照任务规划来动态选择最佳执行方式（本地工具/外部节点/直接响应），并严格遵守决策规则。 ﻿ ## 可用资源 ### 本地工具库 (Tools): ${JSON.stringify(context.toolIndex,null,2)} ﻿ ### 外部节点库 (Nodes): ${JSON.stringify(context.agentNodes,null,2)} ﻿ ## 任务规划 ${todo} ﻿ ## 决策规则 ﻿ ### 1. 请求分类处理 - **简单查询/对话**：直接响应（action=finish） - **需工具处理**：优先本地工具（action=tool） - **需外部能力**：调用节点（action=node） - **信息不足**：发起追问（action=chat） ﻿ ### 2. 响应规范 { \"action\": \"执行类型\", // 必选字段根据action类型变化： // tool/node -> 对应工具名+prompt // finish/abort/chat -> content // missingTool -> missingTools数组 \"content\": \"自然语言响应\", \"tool/node\": \"具体工具名\", \"prompt\": \"工具调用指令\", \"reason\": \"使用工具的原因及目的\", \"missingTools\": [{\"name\":\"工具名\", \"desc\":\"功能描述\"}] } ﻿ ﻿ ### 3. 执行优先级 1. 本地工具（更低延迟） 2. 外部节点（更广能力） 3. 组合调用（需要时链式执行） 4. 严格按照任务规划顺序调用工具 ﻿ ### 4. 特殊处理 - **文件和文件夹操作**： - 创建、写入、修改文件和文件夹必须使用绝对路径 - 未知路径时先调用pwd工具 - 写入文件前请确认文件路径是否存在 - 确保写入的内容完整、详细 - 禁止使用echo和python3 -c - **Python代码**： - 禁止使用echo和python3 -c - 必须先写入文件再执行 - 所有字符串中的换行符 \\\\n 必须转义为 \\\\\\\\n，因为这段代码将通过 Node.js 的 fs.writeFile 执行 保持代码逻辑不变，只对字符串中的特殊字符进行转义处理 最终输出应该是可以直接被 Node.js 执行的字符串形式 - 自动生成合理的文件名（如script_[timestamp].py） ﻿ - **附件处理**： - 所有附件必须显式包含在prompt中（如果以hub://开头必须保留） - 格式：\"[附件: 文件名.扩展名] 处理要求\" ﻿ ### 5. 错误处理流程 1. 参数错误 → 修正后重试 2. 权限问题 → 中止并说明（action=abort） 3. 能力缺失 → 上报需开发的工具（action=missingTool） ﻿ ## 最佳实践示例 1. 文件处理： { \"action\": \"tool\", \"tool\": \"FileWriter\", \"prompt\": \"保存到/tmp/data_20240408.json：[附件: data.json]\", \"reason\": \"我已经得到了数据，现在需要将数据写入文件中\" } ﻿ 2. 工具缺失： { \"action\": \"missingTool\", \"missingTools\": [ {\"name\": \"PDF签名工具\", \"desc\": \"支持数字签名和手写签名嵌入\"}, {\"name\": \"OCR识别引擎\", \"desc\": \"支持多语言图片文字提取\"} ] } ` ﻿"
//							},
//							"localizable": true
//						},
//						"temperature": "0",
//						"maxToken": "32768",
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
//						"x": "2050",
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
//						"x": "1560",
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
//						"x": "1815",
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
//					"jaxId": "1IKCVK9ES0",
//					"attrs": {
//						"id": "ShowResult",
//						"viewName": "",
//						"label": "",
//						"x": "2055",
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
//						"x": "2210",
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
//						"x": "2345",
//						"y": "230",
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
//						"x": "2345",
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
//							"linkedSeg": "1INT632680"
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
//						"x": "2345",
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
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"mcp": {
//							"valText": "false"
//						},
//						"agentNode": ""
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
//						"x": "2345",
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
//						"x": "2345",
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
//						"x": "2720",
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
//						"x": "1590",
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
//						"x": "1560",
//						"y": "635",
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
//						"outlets": {
//							"attrs": []
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
//						"x": "2530",
//						"y": "245",
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
//						"x": "2530",
//						"y": "420",
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
//						"x": "2730",
//						"y": "215",
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
//						"x": "2730",
//						"y": "375",
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
//						"x": "3020",
//						"y": "375",
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
//					"jaxId": "1IKD04TDE0",
//					"attrs": {
//						"id": "TipNodeRes",
//						"viewName": "",
//						"label": "",
//						"x": "3210",
//						"y": "215",
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
//						"x": "3215",
//						"y": "375",
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
//						"x": "3445",
//						"y": "360",
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
//					"jaxId": "1IKDJNI2I0",
//					"attrs": {
//						"id": "AddChat",
//						"viewName": "",
//						"label": "",
//						"x": "2730",
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
//						"outlets": {
//							"attrs": []
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
//						"x": "3320",
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
//						"x": "2595",
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
//						"askUpward": "false",
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
//						"x": "2965",
//						"y": "215",
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
//						"options": "\"\"",
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
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1INT3PTSB0",
//					"attrs": {
//						"id": "InitBash",
//						"viewName": "",
//						"label": "",
//						"x": "515",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INT3RMBR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INT3RMBR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "builder_new",
//						"callAgent": "Bash.js",
//						"callArg": "#{action:\"Create\",options:{client:true,ownBySession:false}}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1INT3RMBL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVBKKB0"
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1INT632680",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "2530",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INT66EV00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INT66EV01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INT63NS21",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IKD03VM90"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INT63NS20",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INT66EV02",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INT66EV03",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.tool === \"Tool-Bash\""
//									},
//									"linkedSeg": "1INT68OMK0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IP1C7J7B0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IP1C83450",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IP1C83451",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.tool === \"Tool-Ask\""
//									},
//									"linkedSeg": "1IP1C8N7Q0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1INT68OMK0",
//					"attrs": {
//						"id": "RunBash",
//						"viewName": "",
//						"label": "",
//						"x": "2730",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INT6BP5I0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INT6BP5I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "builder_new",
//						"callAgent": "Bash.js",
//						"callArg": "#{bashId:globalContext.bash,action:\"Command\",commands:input.prompt}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1INT6BP5C0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INT6GMIR0"
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1INT6GMIR0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3320",
//						"y": "270",
//						"outlet": {
//							"jaxId": "1INT6H1CK0",
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
//					"def": "callLLM",
//					"jaxId": "1IP1BRS1S0",
//					"attrs": {
//						"id": "Generate",
//						"viewName": "",
//						"label": "",
//						"x": "1125",
//						"y": "400",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IP1BSSUK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IP1BSSUL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenAI",
//						"mode": "gpt-4.1",
//						"system": {
//							"type": "string",
//							"valText": "#`The current time is 2025. You are a professional task planning AI, skilled at breaking down complex tasks into executable steps. Please generate a detailed task list according to the following requirements: The available resources you currently have ###Local Tools Library: ${JSON.stringify(context.toolIndex,null,2)} ###External Node Library: ${JSON.stringify(context.agentNodes,null,2)} 1. The output format must strictly follow: \\`\\`\\`markdown #[Task Name] Task List ##Stage 1: [Stage Name] -[] [Atomic level task description] -[] [Next atomic level task] ... ##Stage 2: [Stage Name] ... \\`\\`\\` 2. Decomposition principle: -Maintain the 4-level structure in your example (total task>stage>main task>subtask) -Each subtask must be the smallest unit that can be independently executed -Each task can be completed by calling available tools without the need for manual intervention -Indicate the tools used after each task 3. Rules -If you need to create and output files, please use the pwd command to check the current path in the first step, and then create a working directory (absolute path). Please check if the directory exists first, and if it does, create a new working directory name. -If you need to search for web pages, please write the search results to a markdown file after searching. It is recommended to write a file every time you search -Please use bash to create files -Try to obtain the latest external knowledge through web search as much as possible -When writing a document, please do not write too much content at once. - When reading documents， you can read at the same time instead of iteration. Please add the content in sequence and divide it into multiple tasks Output markdown directly, do not output any irrelevant content.`",
//							"localize": {
//								"EN": "#`The current time is 2025. You are a professional task planning AI, skilled at breaking down complex tasks into executable steps. Please generate a detailed task list according to the following requirements: The available resources you currently have ###Local Tools Library: ${JSON.stringify(context.toolIndex,null,2)} ###External Node Library: ${JSON.stringify(context.agentNodes,null,2)} 1. The output format must strictly follow: \\`\\`\\`markdown #[Task Name] Task List ##Stage 1: [Stage Name] -[] [Atomic level task description] -[] [Next atomic level task] ... ##Stage 2: [Stage Name] ... \\`\\`\\` 2. Decomposition principle: -Maintain the 4-level structure in your example (total task>stage>main task>subtask) -Each subtask must be the smallest unit that can be independently executed -Each task can be completed by calling available tools without the need for manual intervention -Indicate the tools used after each task 3. Rules -If you need to create and output files, please use the pwd command to check the current path in the first step, and then create a working directory (absolute path). Please check if the directory exists first, and if it does, create a new working directory name. -If you need to search for web pages, please write the search results to a markdown file after searching. It is recommended to write a file every time you search -Please use bash to create files -Try to obtain the latest external knowledge through web search as much as possible -When writing a document, please do not write too much content at once. - When reading documents， you can read at the same time instead of iteration. Please add the content in sequence and divide it into multiple tasks Output markdown directly, do not output any irrelevant content.`",
//								"CN": "#`当前的时间是2025年。你是一个专业任务规划AI，擅长将复杂任务分解为可执行的步骤。请按照以下要求生成详细的任务清单： 你目前拥有的可用资源 ### 本地工具库 (Tools): ${JSON.stringify(context.toolIndex,null,2)} ﻿ ### 外部节点库 (Nodes): ${JSON.stringify(context.agentNodes,null,2)} ﻿ ﻿ 1. 输出格式必须严格遵循： \\`\\`\\`markdown # [任务名称] 任务清单 ﻿ ## 阶段1: [阶段名称] - [ ] [原子级任务描述] - [ ] [下一个原子级任务] ... ﻿ ## 阶段2: [阶段名称] ... \\`\\`\\` ﻿ 2. 分解原则： - 保持你示例中的4级结构（总任务>阶段>主任务>子任务） - 每个子任务必须是可独立执行的最小单元 - 每个任务都可以通过调用可用的工具完成，不需要人工干预 - 每个任务后表明使用的工具 ﻿ 3. 规则  - 如果需要搜索网页，请搜索后将搜索到的结果写入markdown文件，建议每搜索一次写入一个文件 - 创建文件请使用bash - 尽可能通过网页搜索获取外部最新的知识 - 撰写文档时请不要一次性写入过多内容，请依次追加写入内容，分成多个任务 - 读取文件可以一次性全部读入﻿ 直接输出markdown，不要输出其他无关内容。 `"
//							},
//							"localizable": true
//						},
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#user_query",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IP1BSSUA0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IP1FIUT30"
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
//					"def": "callLLM",
//					"jaxId": "1IP1C8N7Q0",
//					"attrs": {
//						"id": "LLM",
//						"viewName": "",
//						"label": "",
//						"x": "2730",
//						"y": "320",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IP1CAF0T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IP1CAF0T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1",
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
//							"jaxId": "1IP1CAF0L0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IP1CABF60"
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
//					"def": "connectorL",
//					"jaxId": "1IP1CABF60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3320",
//						"y": "320",
//						"outlet": {
//							"jaxId": "1IP1CAF0T2",
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
//					"def": "output",
//					"jaxId": "1IP1FIUT30",
//					"attrs": {
//						"id": "output",
//						"viewName": "",
//						"label": "",
//						"x": "1340",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IP1FJFN00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IP1FJFN01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IP1FJFMQ0",
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
//					"def": "callLLM",
//					"jaxId": "1IPE2KORR0",
//					"attrs": {
//						"id": "ParseJson",
//						"viewName": "",
//						"label": "",
//						"x": "1820",
//						"y": "560",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IPE2O6R30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IPE2O6R31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "你是一个 JSON 转换助手，专门负责将用户输入的可能存在问题的JSON转换为结构化的合法 JSON 格式。请遵循以下规则：\n输出要求：\n- 必须使用双引号包裹所有键名\n- 确保字符串值使用双引号而非单引号\n- 正确处理特殊字符转义(如 \\\", \\\\, \\/, \\b, \\f, \\n, \\r, \\t)\n- 不包含尾随逗号\n- 不包含注释\n- 使用 UTF-8 编码\n\n请直接输出转换后的 JSON，不要包含任何解释或额外文本。现在开始处理用户输入：\n\n",
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
//							"jaxId": "1IPE2O6QU0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
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
//					"def": "code",
//					"jaxId": "1IPEEMQF00",
//					"attrs": {
//						"id": "NextStep",
//						"viewName": "",
//						"label": "",
//						"x": "1560",
//						"y": "535",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IPEEMQFE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IPEEMQFE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IPEEMQF20",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKCVDIJ50"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}