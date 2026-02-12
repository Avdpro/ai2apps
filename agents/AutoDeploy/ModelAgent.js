//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1JGP1AAKD0MoreImports*/
import fsp from 'fs/promises';
import yaml from 'js-yaml';
import os from 'os';
/*}#1JGP1AAKD0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JGP1AAKD0ArgsView*/
	/*}#1JGP1AAKD0ArgsView*/
};

/*#{1JGP1AAKD0StartDoc*/
/*}#1JGP1AAKD0StartDoc*/
//----------------------------------------------------------------------------
let ModelAgent=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Welcome,Ask,Output,Agent,Action,AskUser,Run,InitBash,Respond,Enter,Show,Again,Execute,InitBash2,Enter2,Check;
	/*#{1JGP1AAKD0LocalVals*/
	let query="", config, skill, base_command;
	/*}#1JGP1AAKD0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
		}else{
			model=undefined;
		}
		/*#{1JGP1AAKD0ParseArgs*/
		/*}#1JGP1AAKD0ParseArgs*/
	}
	
	/*#{1JGP1AAKD0PreContext*/
	/*}#1JGP1AAKD0PreContext*/
	context={};
	/*#{1JGP1AAKD0PostContext*/
	
	/*}#1JGP1AAKD0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1JGP1KHU70
		let result=input;
		let missing=false;
		let smartAsk=false;
		/*#{1JGP1KHU70PreCodes*/
		/*}#1JGP1KHU70PreCodes*/
		if(model===undefined || model==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		/*#{1JGP1KHU70PostCodes*/
		const apiUrl = process.env.MODELHUNT_API_URL;
		const modelUsageUrl = `${apiUrl.replace(/\/$/, '')}/api/v1/models/${model}/usage`;
		
		try {
			const response = await fetch(modelUsageUrl);
			if (!response.ok) {
				throw new Error(`Failed to fetch model config: ${response.status} ${response.statusText}`);
			}
			const yamlContent = await response.text();
			config = yaml.load(yamlContent);
		
			if (config.global_execution && config.global_execution.working_directory) {
				let wd = config.global_execution.working_directory;
				if (wd.startsWith('~')) {
					wd = pathLib.join(os.homedir(), wd.slice(1));
				}
				config.global_execution.working_directory = pathLib.resolve(wd);
			}
			if (config.base_command) base_command=config.base_command;
		} catch (error) {
			throw new Error(`Failed to load model config for "${model}": ${error.message}`);
		}
		/*}#1JGP1KHU70PostCodes*/
		return {seg:InitBash,result:(result),preSeg:"1JGP1KHU70",outlet:"1JGP1KHU71"};
	};
	FixArgs.jaxId="1JGP1KHU70"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Welcome"]=Welcome=async function(input){//:1JGP1TLH70
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JGP1TLH70PreCodes*/
		const language = $ln === 'CN' ? 'zh' : 'en';
		if (config?.interface?.languages?.[language]?.greeting) {
			content = config.interface.languages[language].greeting;
		}
		/*}#1JGP1TLH70PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JGP1TLH70PostCodes*/
		/*}#1JGP1TLH70PostCodes*/
		return {seg:Ask,result:(result),preSeg:"1JGP1TLH70",outlet:"1JGP1TRNS0"};
	};
	Welcome.jaxId="1JGP1TLH70"
	Welcome.url="Welcome@"+agentURL
	
	segs["Ask"]=Ask=async function(input){//:1JGP2DSRR0
		let tip=("");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(true)||false;
		let allowEmpty=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		/*#{1JGP2DSRR0PreCodes*/
		/*}#1JGP2DSRR0PreCodes*/
		if(askUpward && tip){
			result=await session.askUpward($agent,tip);
		}else{
			if(tip){
				session.addChatText(tipRole,tip);
			}
			result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile,allowEmpty:allowEmpty});
		}
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		/*#{1JGP2DSRR0PostCodes*/
		let userRequest = "";
		let fileList = [];
		
		if(typeof(result) === 'object' && result.assets && result.assets.length > 0) {
			userRequest = result.prompt || result.text || "";
			const filelibPath = pathLib.join(pathLib.dirname(pathLib.dirname(basePath)), 'filelib');
			for(let i = 0; i < result.assets.length; i++) {
				let assetPath = result.assets[i];
				if(assetPath.startsWith('hub://')) {
					assetPath = assetPath.substring(6);
				}
				const absolutePath = pathLib.join(filelibPath, assetPath);
				fileList.push(absolutePath);
			}
			query = `用户要求：${userRequest}\n上传的文件：\n${fileList.map((f, idx) => `${idx + 1}. ${f}`).join('\n')}`;
		} else if(typeof(result) === 'string') {
			userRequest = result;
			query = `用户要求：${userRequest}`;
		} else if(typeof(result) === 'object') {
			userRequest = result.text || result.prompt || JSON.stringify(result);
			query = `用户要求：${userRequest}`;
		}
		/*}#1JGP2DSRR0PostCodes*/
		return {seg:Agent,result:(result),preSeg:"1JGP2DSRR0",outlet:"1JGP2E32A0"};
	};
	Ask.jaxId="1JGP2DSRR0"
	Ask.url="Ask@"+agentURL
	
	segs["Output"]=Output=async function(input){//:1JGP381J70
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.message;
		session.addChatText(role,content,opts);
		return {seg:Again,result:(result),preSeg:"1JGP381J70",outlet:"1JGP389H50"};
	};
	Output.jaxId="1JGP381J70"
	Output.url="Output@"+agentURL
	
	segs["Agent"]=Agent=async function(input){//:1JGP3LBMP0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-4.1";
		let $agent;
		let result=null;
		/*#{1JGP3LBMP0Input*/
		/*}#1JGP3LBMP0Input*/
		
		let opts={
			platform:$platform,
			mode:$model,
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=Agent.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		messages.push(...chatMem);
		/*#{1JGP3LBMP0PrePrompt*/
		const allSkillsDoc = config.skills?.map(s => {
					return `
		### Function Name: ${s.name}
		- Description: ${s.description}
		- Arguments Definition: ${JSON.stringify(s.arguments)}
		- Command Template: ${s.command_template}
		`;
		}).join('\n') || "No specific skills configured.";
		
		const language = $ln === 'CN' ? 'zh' : 'en';
		
		const systemPrompt = language === 'zh'
		? `你是一个全能的任务执行助手。你的目标是根据用户的请求，从可用功能列表中选择合适的功能并执行。
		
		**当前运行状态 (非常重要)**：
		1. 系统 **已自动切换** 到工作目录：${config.global_execution?.working_directory || '未指定'}
		2. 系统 **已自动激活** Conda 环境：${config.global_execution?.env_name || '未指定'}
		❌ **禁止** 在生成的命令中包含 \`cd\` 或 \`conda activate\`。
		❗ **绝对路径规则**：在 Finish 动作中返回的 \`filePath\` **必须** 是绝对路径（例如 \`/home/user/workspace/data.csv\`），**严禁** 使用相对路径。
		
		**可用功能列表 (Skills)**：
		${allSkillsDoc}
		
		**可用动作 (Actions)** - 请返回 JSON，每次仅一个动作：
		
		1. **Bash** (执行任务)
		- 场景：找到匹配功能且参数齐全。
		- 格式：{"action": "Bash", "command": "完整命令", "message": "简短告知用户正在执行什么操作", "reasoning": "..."}
		
		2. **Ask** (追问参数)
		- 场景：匹配到功能但缺少参数。
		- 格式：{"action": "Ask", "question": "问题", "reasoning": "..."}
		
		3. **Finish** (任务成功)
		- 场景：命令执行成功，任务已完成。
		- 格式：{
		"action": "Finish", 
		"type": "text" | "image" | "audio" | "video" | "file", 
		"message": "结束语(纯文本结果写在这里)", 
		"filePath": "单个文件的绝对路径 (String) 或 多个文件的绝对路径列表 (Array<String>)。注意：必须是绝对路径！", 
		"reasoning": "..."
		}
		
		4. **Chitchat** (闲聊)
		- 场景：用户打招呼、闲聊。
		- 格式：{"action": "Chitchat", "message": "回复内容", "reasoning": "..."}
		
		5. **Reject** (无法处理)
		- 场景：请求超出能力范围。
		- 格式：{"action": "Reject", "message": "拒绝理由及能力介绍", "reasoning": "..."}
		
		**执行流程**：
		1. 分析请求 -> 2. 分类 (Chitchat/Reject/Task) -> 3. 匹配 Skills -> 4. 检查参数 (Ask/Bash) -> 5. 执行结果 (Finish)
		`
		: `You are a versatile task execution assistant.
		
		**Current Execution State (CRITICAL)**:
		1. Working directory is SET: ${config.global_execution?.working_directory || 'N/A'}
		2. Conda environment is ACTIVATED: ${config.global_execution?.env_name || 'N/A'}
		❌ **DO NOT** include \`cd\` or \`conda activate\` in commands.
		❗ **ABSOLUTE PATH RULE**: The \`filePath\` returned in Finish action **MUST** be an ABSOLUTE path (e.g., \`/home/user/workspace/output.png\`). Relative paths are **FORBIDDEN**.
		
		**Available Skills**:
		${allSkillsDoc}
		
		**Available Actions**:
		Return JSON output:
		
		1. **Bash** (Execute Command)
		- Format: {"action": "Bash", "command": "command", "message": "status update", "reasoning": "reasoning"}
		
		2. **Ask** (Ask User)
		- Format: {"action": "Ask", "question": "question", "reasoning": "reasoning"}
		
		3. **Finish** (Task Success)
		- Format: {
		"action": "Finish", 
		"type": "text" | "image" | "audio" | "video" | "file", 
		"message": "closing message or text result", 
		"filePath": "Single absolute path (String) OR List of absolute paths (Array<String>). NOTE: MUST use Absolute Path.", 
		"reasoning": "reasoning"
		}
		
		4. **Chitchat** (Casual Conversation)
		- Format: {"action": "Chitchat", "message": "response", "reasoning": "reasoning"}
		
		5. **Reject** (Cannot Handle)
		- Format: {"action": "Reject", "message": "response", "reasoning": "reasoning"}
		
		**Execution Flow**:
		1. Analyze -> 2. Classify -> 3. Match Skill -> 4. Check Args (Ask/Bash) -> 5. Result (Finish)`;
		
		messages[0].content = systemPrompt;
						/*}#1JGP3LBMP0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JGP3LBMP0FilterMessage*/
			/*}#1JGP3LBMP0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JGP3LBMP0PreCall*/
		/*}#1JGP3LBMP0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("Agent@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JGP3LBMP0PostLLM*/
		/*}#1JGP3LBMP0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		result=trimJSON(result);
		/*#{1JGP3LBMP0PostCall*/
		/*}#1JGP3LBMP0PostCall*/
		/*#{1JGP3LBMP0PreResult*/
		/*}#1JGP3LBMP0PreResult*/
		return {seg:Action,result:(result),preSeg:"1JGP3LBMP0",outlet:"1JGP3LT3M0"};
	};
	Agent.jaxId="1JGP3LBMP0"
	Agent.url="Agent@"+agentURL
	Agent.messages=[];
	
	segs["Action"]=Action=async function(input){//:1JGP3NVPQ0
		let result=input;
		if(input.action==="Ask"){
			return {seg:AskUser,result:(input),preSeg:"1JGP3NVPQ0",outlet:"1JGP3PR1S0"};
		}
		if(input.action==="Bash"){
			return {seg:Execute,result:(input),preSeg:"1JGP3NVPQ0",outlet:"1JGP3OP2U0"};
		}
		if(input.action==="Reject"){
			return {seg:Output,result:(input),preSeg:"1JGP3NVPQ0",outlet:"1JGPPCJ030"};
		}
		if(input.action==="ChitChat"){
			return {seg:Output,result:(input),preSeg:"1JGP3NVPQ0",outlet:"1JGPQPU9E0"};
		}
		return {seg:Show,result:(result),preSeg:"1JGP3NVPQ0",outlet:"1JGP3PR1S1"};
	};
	Action.jaxId="1JGP3NVPQ0"
	Action.url="Action@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1JGP3QVB70
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.question;
		session.addChatText(role,content,opts);
		return {seg:Respond,result:(result),preSeg:"1JGP3QVB70",outlet:"1JGP3SQ0S0"};
	};
	AskUser.jaxId="1JGP3QVB70"
	AskUser.url="AskUser@"+agentURL
	
	segs["Run"]=Run=async function(input){//:1JGP3RICD0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=input.command;
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:Agent,result:(result),preSeg:"1JGP3RICD0",outlet:"1JGP3SQ0T0"};
	};
	Run.jaxId="1JGP3RICD0"
	Run.url="Run@"+agentURL
	
	segs["InitBash"]=InitBash=async function(input){//:1JGP3RVH10
		let result,args={};
		args['bashId']="";
		args['action']="Create";
		args['commands']="";
		args['options']={client:true};
		/*#{1JGP3RVH10PreCodes*/
		/*}#1JGP3RVH10PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JGP3RVH10PostCodes*/
		globalContext.bash=result;
		/*}#1JGP3RVH10PostCodes*/
		return {seg:Enter,result:(result),preSeg:"1JGP3RVH10",outlet:"1JGP3SQ0T1"};
	};
	InitBash.jaxId="1JGP3RVH10"
	InitBash.url="InitBash@"+agentURL
	
	segs["Respond"]=Respond=async function(input){//:1JGP4CTCI0
		let tip=("");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let allowEmpty=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		/*#{1JGP4CTCI0PreCodes*/
		/*}#1JGP4CTCI0PreCodes*/
		if(askUpward && tip){
			result=await session.askUpward($agent,tip);
		}else{
			if(tip){
				session.addChatText(tipRole,tip);
			}
			result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile,allowEmpty:allowEmpty});
		}
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		/*#{1JGP4CTCI0PostCodes*/
		if(typeof(result) === 'object' && result.assets && result.assets.length > 0) {
			let userResponse = result.prompt || result.text || "";
			const filelibPath = pathLib.join(pathLib.dirname(pathLib.dirname(basePath)), 'filelib');
			let fileList = [];
			
			for(let i = 0; i < result.assets.length; i++) {
				let assetPath = result.assets[i];
				if(assetPath.startsWith('hub://')) {
					assetPath = assetPath.substring(6);
				}
				const absolutePath = pathLib.join(filelibPath, assetPath);
				fileList.push(absolutePath);
			}
			result = `${userResponse}\n上传的文件：\n${fileList.map((f, idx) => `${idx + 1}. ${f}`).join('\n')}`;
		} else if(typeof(result) === 'object') {
			result = result.text || result.prompt || JSON.stringify(result);
		}
		/*}#1JGP4CTCI0PostCodes*/
		return {seg:Agent,result:(result),preSeg:"1JGP4CTCI0",outlet:"1JGP4D2120"};
	};
	Respond.jaxId="1JGP4CTCI0"
	Respond.url="Respond@"+agentURL
	
	segs["Enter"]=Enter=async function(input){//:1JGP4II6C0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="";
		args['options']="";
		/*#{1JGP4II6C0PreCodes*/
		args['commands']=[`cd "${config.global_execution?.working_directory}"`, `conda activate ${config.global_execution?.env_name} || source activate ${config.global_execution?.env_name}`];
		/*}#1JGP4II6C0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JGP4II6C0PostCodes*/
		/*}#1JGP4II6C0PostCodes*/
		return {seg:Check,result:(result),preSeg:"1JGP4II6C0",outlet:"1JGP4IUBI0"};
	};
	Enter.jaxId="1JGP4II6C0"
	Enter.url="Enter@"+agentURL
	
	segs["Show"]=Show=async function(input){//:1JGPM3RLV0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.message;
		/*#{1JGPM3RLV0PreCodes*/
		let filePaths = [];
		if (input.filePath) {
			if (Array.isArray(input.filePath)) {
				filePaths = input.filePath;
			} else {
				if (input.filePath) filePaths = [input.filePath];
			}
		}
		if (input.type !== 'text' && filePaths.length > 0) {
			for (let i = 0; i < filePaths.length; i++) {
				let fp = filePaths[i];
				let fileOpts = { channel: $channel }; 
				let fileContent = ""; 
				
				try {
					let originalName = pathLib.basename(fp);
					let ext = pathLib.extname(fp);
					if (!ext) ext = ".bin";
					let data = await fsp.readFile(fp);
					let saveName = `output_${Date.now()}_${i}_${originalName}`;
					let savedHubName = await session.saveHubFile(saveName, data);
					let hubUrl = "hub://" + savedHubName;
					if (input.type === 'image') {
						fileOpts.image = hubUrl;
						fileContent = `Image ${i+1}: ${originalName}`;
					} else if (input.type === 'audio') {
						fileOpts.audio = hubUrl;
						fileContent = `Audio ${i+1}: ${originalName}`;
					} else if (input.type === 'video') {
						fileOpts.video = hubUrl;
						fileContent = `Video ${i+1}: ${originalName}`;
					} else {
						fileOpts.file = hubUrl;
						fileContent = `File ${i+1}: ${originalName}`;
						if ($ln === 'CN') {
							fileContent += " (可在右侧文件面板下载)";
						} else {
							fileContent += " (Download in Files panel)";
						}
					}
					session.addChatText(role, fileContent, fileOpts);
					
				} catch (e) {
					session.addChatText(role, `[Error processing file ${pathLib.basename(fp)}: ${e.message}]`, {channel:$channel});
				}
			}
		}
		/*}#1JGPM3RLV0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JGPM3RLV0PostCodes*/
		/*}#1JGPM3RLV0PostCodes*/
		return {seg:Again,result:(result),preSeg:"1JGPM3RLV0",outlet:"1JGPM44AH0"};
	};
	Show.jaxId="1JGPM3RLV0"
	Show.url="Show@"+agentURL
	
	segs["Again"]=Again=async function(input){//:1JGPN2B3H0
		let result=input;
		return {seg:Ask,result:result,preSeg:"1JGP2DSRR0",outlet:"1JGPN38BL0"};
	
	};
	Again.jaxId="1JGP2DSRR0"
	Again.url="Again@"+agentURL
	
	segs["Execute"]=Execute=async function(input){//:1JGPPV87R0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.message;
		session.addChatText(role,content,opts);
		return {seg:Run,result:(result),preSeg:"1JGPPV87R0",outlet:"1JGPQ089F0"};
	};
	Execute.jaxId="1JGPPV87R0"
	Execute.url="Execute@"+agentURL
	
	segs["InitBash2"]=InitBash2=async function(input){//:1JH7SNN4S0
		let result,args={};
		args['bashId']="";
		args['action']="Create";
		args['commands']="";
		args['options']={client:true};
		/*#{1JH7SNN4S0PreCodes*/
		/*}#1JH7SNN4S0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JH7SNN4S0PostCodes*/
		globalContext.backend=result;
		/*}#1JH7SNN4S0PostCodes*/
		return {seg:Enter2,result:(result),preSeg:"1JH7SNN4S0",outlet:"1JH7SNN4T2"};
	};
	InitBash2.jaxId="1JH7SNN4S0"
	InitBash2.url="InitBash2@"+agentURL
	
	segs["Enter2"]=Enter2=async function(input){//:1JH7SOU1E0
		let result,args={};
		args['bashId']=globalContext.backend;
		args['action']="Command";
		args['commands']="";
		args['options']="";
		/*#{1JH7SOU1E0PreCodes*/
		args['commands']=[`cd "${config.global_execution?.working_directory}"`, `conda activate ${config.global_execution?.env_name} || source activate ${config.global_execution?.env_name}`, base_command];
		/*}#1JH7SOU1E0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JH7SOU1E0PostCodes*/
		/*}#1JH7SOU1E0PostCodes*/
		return {seg:Welcome,result:(result),preSeg:"1JH7SOU1E0",outlet:"1JH7SOU1E3"};
	};
	Enter2.jaxId="1JH7SOU1E0"
	Enter2.url="Enter2@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1JH7SQRPI0
		let result=input;
		if(input==="undefined"){
			return {seg:InitBash2,result:(input),preSeg:"1JH7SQRPI0",outlet:"1JH7SRM9M0"};
		}
		return {seg:Welcome,result:(result),preSeg:"1JH7SQRPI0",outlet:"1JH7SR6CU0"};
	};
	Check.jaxId="1JH7SQRPI0"
	Check.url="Check@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ModelAgent",
		url:agentURL,
		autoStart:true,
		jaxId:"1JGP1AAKD0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JGP1AAKD0PreEntry*/
			/*}#1JGP1AAKD0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1JGP1AAKD0PostEntry*/
			/*}#1JGP1AAKD0PostEntry*/
			return result;
		},
		/*#{1JGP1AAKD0MoreAgentAttrs*/
		/*}#1JGP1AAKD0MoreAgentAttrs*/
	};
	/*#{1JGP1AAKD0PostAgent*/
	/*}#1JGP1AAKD0PostAgent*/
	return agent;
};
/*#{1JGP1AAKD0ExCodes*/
/*}#1JGP1AAKD0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JGP1AAKD0PostDoc*/
/*}#1JGP1AAKD0PostDoc*/


export default ModelAgent;
export{ModelAgent};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JGP1AAKD0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JGP1FIQ80",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JGP1F6R10",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JGP1FIQ81",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGP1FIQ82",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JGP1FIQ83",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JGP1FIQ84",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JGP1FIQ85",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1JGP1KHU70",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "-190",
//						"y": "60",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1JGP1KHU71",
//							"attrs": {
//								"id": "Next",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP3RVH10"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JGP1TLH70",
//					"attrs": {
//						"id": "Welcome",
//						"viewName": "",
//						"label": "",
//						"x": "695",
//						"y": "75",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGP1TUEB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGP1TUEB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JGP1TRNS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP2DSRR0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1JGP2DSRR0",
//					"attrs": {
//						"id": "Ask",
//						"viewName": "",
//						"label": "",
//						"x": "970",
//						"y": "70",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGP2E32B0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGP2E32B1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "true",
//						"allowEmpty": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1JGP2E32A0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP3KRLK0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JGP381J70",
//					"attrs": {
//						"id": "Output",
//						"viewName": "",
//						"label": "",
//						"x": "525",
//						"y": "590",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGP38PRR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGP38PRR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.message",
//						"outlet": {
//							"jaxId": "1JGP389H50",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGPN2B3H0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JGP3KRLK0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1095",
//						"y": "295",
//						"outlet": {
//							"jaxId": "1JGP3LT3U0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP3L6890"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JGP3L6890",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "-150",
//						"y": "295",
//						"outlet": {
//							"jaxId": "1JGP3LT3U1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP3LBMP0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JGP3LBMP0",
//					"attrs": {
//						"id": "Agent",
//						"viewName": "",
//						"label": "",
//						"x": "-185",
//						"y": "535",
//						"desc": "Excute a LLM call.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGP3LT3U2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGP3LT3U3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenAI",
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
//							"jaxId": "1JGP3LT3M0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP3NVPQ0"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "All messages",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"\"",
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JGP3NVPQ0",
//					"attrs": {
//						"id": "Action",
//						"viewName": "",
//						"label": "",
//						"x": "275",
//						"y": "535",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGP3PR230",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGP3PR231",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JGP3PR1S1",
//							"attrs": {
//								"id": "Finish",
//								"desc": "Outlet.",
//								"output": ""
//							},
//							"linkedSeg": "1JGPM3RLV0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JGP3PR1S0",
//									"attrs": {
//										"id": "Ask",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGP3PR232",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGP3PR233",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Ask\""
//									},
//									"linkedSeg": "1JGP3QVB70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JGP3OP2U0",
//									"attrs": {
//										"id": "Bash",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGP3PR236",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGP3PR237",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Bash\""
//									},
//									"linkedSeg": "1JGPPV87R0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JGPPCJ030",
//									"attrs": {
//										"id": "Reject",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGPPCJ0H0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGPPCJ0H1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Reject\""
//									},
//									"linkedSeg": "1JGP381J70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JGPQPU9E0",
//									"attrs": {
//										"id": "Chat",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGPQRSH00",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGPQRSH01",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"ChitChat\""
//									},
//									"linkedSeg": "1JGP381J70"
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
//					"jaxId": "1JGP3QVB70",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "525",
//						"y": "445",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGP3SQ140",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGP3SQ141",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.question",
//						"outlet": {
//							"jaxId": "1JGP3SQ0S0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP4CTCI0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JGP3RICD0",
//					"attrs": {
//						"id": "Run",
//						"viewName": "",
//						"label": "",
//						"x": "740",
//						"y": "520",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGP3SQ142",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGP3SQ143",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#input.command",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JGP3SQ0T0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGPKDRUP0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JGP3RVH10",
//					"attrs": {
//						"id": "InitBash",
//						"viewName": "",
//						"label": "",
//						"x": "5",
//						"y": "60",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGP3SQ144",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGP3SQ145",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "\"\"",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client:true}",
//						"outlet": {
//							"jaxId": "1JGP3SQ0T1",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP4II6C0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1JGP4CTCI0",
//					"attrs": {
//						"id": "Respond",
//						"viewName": "",
//						"label": "",
//						"x": "740",
//						"y": "445",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGP4D21A0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGP4D21A1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"allowEmpty": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1JGP4D2120",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGPKF6O30"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JGP4II6C0",
//					"attrs": {
//						"id": "Enter",
//						"viewName": "",
//						"label": "",
//						"x": "205",
//						"y": "60",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGP4IUBQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGP4IUBQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JGP4IUBI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH7SQRPI0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JGPKDRUP0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "940",
//						"y": "520",
//						"outlet": {
//							"jaxId": "1JGPKESVE0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP3KRLK0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JGPKF6O30",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "940",
//						"y": "445",
//						"outlet": {
//							"jaxId": "1JGPKGOQ10",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP3KRLK0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JGPM3RLV0",
//					"attrs": {
//						"id": "Show",
//						"viewName": "",
//						"label": "",
//						"x": "525",
//						"y": "695",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGPM4RSI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGPM4RSI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.message",
//						"outlet": {
//							"jaxId": "1JGPM44AH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGPN2B3H0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JGPN2B3H0",
//					"attrs": {
//						"id": "Again",
//						"viewName": "",
//						"label": "",
//						"x": "740",
//						"y": "590",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JGP2DSRR0",
//						"outlet": {
//							"jaxId": "1JGPN38BL0",
//							"attrs": {
//								"id": "Next",
//								"desc": "Outlet."
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JGPPV87R0",
//					"attrs": {
//						"id": "Execute",
//						"viewName": "",
//						"label": "",
//						"x": "525",
//						"y": "520",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGPQ089P0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGPQ089P1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.message",
//						"outlet": {
//							"jaxId": "1JGPQ089F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP3RICD0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JH7SNN4S0",
//					"attrs": {
//						"id": "InitBash2",
//						"viewName": "",
//						"label": "",
//						"x": "595",
//						"y": "-55",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH7SNN4T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH7SNN4T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "\"\"",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client:true}",
//						"outlet": {
//							"jaxId": "1JH7SNN4T2",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH7SOU1E0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JH7SOU1E0",
//					"attrs": {
//						"id": "Enter2",
//						"viewName": "",
//						"label": "",
//						"x": "835",
//						"y": "-55",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH7SOU1E1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH7SOU1E2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.backend",
//						"action": "Command",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JH7SOU1E3",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGP1TLH70"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JH7SQRPI0",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "385",
//						"y": "60",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH7SRCTG0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH7SRCTG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH7SR6CU0",
//							"attrs": {
//								"id": "Default",
//								"desc": "Outlet.",
//								"output": ""
//							},
//							"linkedSeg": "1JGP1TLH70"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JH7SRM9M0",
//									"attrs": {
//										"id": "#base_command",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JH7SRM9S0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JH7SRM9S1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JH7SNN4S0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				}
//			]
//		},
//		"desc": "This is an AI agent.",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}