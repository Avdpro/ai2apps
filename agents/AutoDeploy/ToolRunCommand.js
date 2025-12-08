//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IUIO756A0MoreImports*/
import axios from 'axios';
/*}#1IUIO756A0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"command":{
			"name":"command","type":"auto",
			"required":true,
			"defaultValue":"",
			"desc":"A bash command",
		},
		"repo":{
			"name":"repo","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IUIO756A0ArgsView*/
	/*}#1IUIO756A0ArgsView*/
};

/*#{1IUIO756A0StartDoc*/
async function fetchLinks(customQuery, maxResults = 5) {
		const options = {
				method: "POST",
				headers: {
						Authorization: "Bearer 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",
						"Content-Type": "application/json"
				},
				body: JSON.stringify({
						query: customQuery,
						max_results: maxResults,
						topic: "general",
						search_depth: "basic",
						include_answer: false,
						include_raw_content: false
				})
		};

		const response = await fetch("https://api.tavily.com/search", options);
		const { results = [] } = await response.json();

		return results
				.filter(r => r.url)
				.map(r => r.url);
}


async function extractArticle(url) {
		try {
				const resp = await fetch("http://8.140.204.249:8000/extract_from_url", {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ url })
				});

				const data = await resp.json();

				if (data.success) {
						// 提取成功
						return `文章链接：${url}\n文章内容：${data.text}`;
				} else {
						// 提取失败
						return `文章链接：${url}\n文章内容：提取失败`;
				}
		} catch (err) {
				console.error("提取请求出错：", err);
				return `文章链接：${url}\n文章内容：请求失败`;
		}
}


async function fetchLinksAndArticles(customQuery, maxResults = 5) {
		const links = await fetchLinks(customQuery, maxResults);

		// 并发提取正文
		const articleStrings = await Promise.all(
				links.map(link => extractArticle(link))
		);

		// 如需一个大字符串，可返回 articleStrings.join("\n---\n");
		return articleStrings.join("\n---\n");
}

async function getSolution(query) {
	const url = "http://ec2-43-199-143-95.ap-east-1.compute.amazonaws.com:222/qa/retrieve";
	let solution = "";

	try {
		const response = await fetch(url, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({
			error_desc: query,
			tags: []
		})
	});

	let result;

	if (response.status === 404) {
		result = [];
	} else if (response.status === 200) {
		result = await response.json();
	} else {
		result = [];
		console.log(`Error: ${response.status} - ${await response.text()}`);
	}

	// Use result here
	if(result !== [] && result.data) {
		for (let item in result.data) {
			let data = result.data[item];
			let metadata = data.metadata;
			let content = data.page_content;
			if (metadata.dense_score > 0.6) {
				solution += '==============================================\n';
				solution += 'Issue: ' + content + '\n';
				solution += 'Solution: ' + metadata.solution + '\n';
			}
		}
	}
		return solution;

	} catch (error) {
		console.error('Request failed:', error);
		return "";
	}
}

async function sendRequest(error_desc, error_solution) {
	const url = "http://ec2-43-199-143-95.ap-east-1.compute.amazonaws.com:222/qa/index";

	try {
		const response = await axios.post(url, {
			error_desc: error_desc,
			error_solution: error_solution
	});

	if (response.status === 201) {
		return response.data;
	} else {
		return {
			error: "Failed to fetch data",
			status_code: response.status,
			response: response.data
			};
		}
	} catch (error) {
		console.error('Request failed:', error);
		return {
			error: "Request failed",
			message: error.message
		};
	}
}

function countTokens(text) {
let chineseChars = 0;

// Count Chinese characters (Unicode range: \u4e00 to \u9fff)
for (let i = 0; i < text.length; i++) {
const char = text[i];
if (char >= '\u4e00' && char <= '\u9fff') {
chineseChars++;
}
}

// Calculate the number of other characters
const otherChars = text.length - chineseChars;

// Return the token count based on the given formula
return Math.floor(chineseChars / 1.5 + otherChars / 4);
}

/*}#1IUIO756A0StartDoc*/
//----------------------------------------------------------------------------
let ToolRunCommand=async function(session){
	let command,repo;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Run,CheckSuccess,Check,Fix,Action,RunCommand,CheckFinish,Fail,GetPath,BackPath,Success,Issues,RunSearch,SearchIssue,CheckNetwork,Network,Retry,ListFiles,Path,ReadFile,FixSuccess,Modify,WriteFile,UpdateSolution;
	/*#{1IUIO756A0LocalVals*/
	let current_output, output, current_path, issue, search_result, bug, current_files, latest_path, all_files, cnt=0;
	let history_summary="";
	/*}#1IUIO756A0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			command=input.command;
			repo=input.repo;
		}else{
			command=undefined;
			repo=undefined;
		}
		/*#{1IUIO756A0ParseArgs*/
		/*}#1IUIO756A0ParseArgs*/
	}
	
	/*#{1IUIO756A0PreContext*/
	function extract(session, sep = '\n<<<###>>>\n') {
		const lines = session.split(/\r?\n/);
		const outputs = [];
		let i = 0;
	
		if (i < lines.length && !/__AGENT_SHELL__>/.test(lines[i])) {
			i++;
			const chunk = [];
			while (i < lines.length && !/__AGENT_SHELL__>/.test(lines[i])) {
			chunk.push(lines[i]);
			i++;
			}
			outputs.push(chunk.join('\n').trim());
		}
		while (i < lines.length) {
			const m = lines[i].match(/__AGENT_SHELL__>\s*(\S.*)$/);
			if (m) {
			i++;
			const chunk = [];
			while (i < lines.length && !/__AGENT_SHELL__>/.test(lines[i])) {
				chunk.push(lines[i]);
				i++;
			}
			outputs.push(chunk.join('\n').trim());
			} else {
			i++;
			}
		}
		return outputs
			.map(o => (o === '' ? ' ' : o))
			.join(sep);
	}
	/*}#1IUIO756A0PreContext*/
	context={};
	/*#{1IUIO756A0PostContext*/
	/*}#1IUIO756A0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IUIO65O30
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(command===undefined || command==="") missing=true;
		if(repo===undefined || repo==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:Run,result:(result),preSeg:"1IUIO65O30",outlet:"1IUIO756A1"};
	};
	FixArgs.jaxId="1IUIO65O30"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Run"]=Run=async function(input){//:1IUIOB71S0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=command;
		args['options']="";
		/*#{1IUIOB71S0PreCodes*/
		/*}#1IUIOB71S0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IUIOB71S0PostCodes*/
		current_output=result;
		output=result;
		issue=result;
		/*}#1IUIOB71S0PostCodes*/
		return {seg:CheckSuccess,result:(result),preSeg:"1IUIOB71S0",outlet:"1IUIOC3B40"};
	};
	Run.jaxId="1IUIOB71S0"
	Run.url="Run@"+agentURL
	
	segs["CheckSuccess"]=CheckSuccess=async function(input){//:1IUIP57LI0
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
			responseFormat:"json_object"
		};
		let chatMem=CheckSuccess.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你是一个终端命令的分析助手。当接收到终端运行的命令和输出时，你需要判断命令是否执行成功。根据命令的输出判断其成功或失败，并以JSON格式输出结果。输出的JSON格式为：{'success': true/false}，其中 'true' 表示命令执行成功，'false' 表示命令执行失败。如果输入是空的，认为执行成功。你只需要根据输出的信息判断命令是否成功，无需进一步的解释。"},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("CheckSuccess@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:Check,result:(result),preSeg:"1IUIP57LI0",outlet:"1IUIP9MVA0"};
	};
	CheckSuccess.jaxId="1IUIP57LI0"
	CheckSuccess.url="CheckSuccess@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1IUIPB1E90
		let result=input;
		if(input.success){
			return {seg:Success,result:(input),preSeg:"1IUIPB1E90",outlet:"1IUIPC0300"};
		}
		return {seg:GetPath,result:(result),preSeg:"1IUIPB1E90",outlet:"1IUIPC0301"};
	};
	Check.jaxId="1IUIPB1E90"
	Check.url="Check@"+agentURL
	
	segs["Fix"]=Fix=async function(input){//:1IUIPQ6810
		let prompt;
		let result=null;
		/*#{1IUIPQ6810Input*/
		cnt += 1;
		/*}#1IUIPQ6810Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=Fix.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`你是一个命令行问题修复专家,具备丰富的Linux/Unix系统管理经验和故障排查能力。

## 当前任务状态
原始目标：${command}
历史操作总结：${history_summary}
项目内包含的所有文件：${all_files}
搜索到的参考方案：${search_result}

## 你的任务
基于历史操作总结，分析当前状态并决定下一步行动。你需要通过自身思考和推理，给出新的命令或解决方案，以json格式输出。

## 可用的操作方式
1. **执行终端命令**：每次只能执行一个命令
   输出格式：{"summary": "<更新后的总结：继承history_summary并补充上一步的操作结果>", "reason": "<基于summary的推理过程，说明为什么要执行这个命令>", "action": "command", "content": "<命令>"}
   注意：如果命令可能不会自动退出，请设置timeout为2分钟

2. **读取文件**：查看特定文件内容来帮助诊断问题
   输出格式：{"summary": "<更新后的总结：继承并补充上一步结果>", "reason": "<推理过程>", "action": "read", "content": "<文件绝对路径>"}

3. **写入新文件**：创建并写入新文件
   输出格式：{"summary": "<更新后的总结：继承并补充上一步结果>", "reason": "<推理过程>", "action": "write", "filePath": "<文件绝对路径>", "content": "<写入内容>"}

4. **修改文件**：修改配置文件或其他文件
   输出格式：{"summary": "<更新后的总结：继承并补充上一步结果>", "reason": "<推理过程>", "action": "modify", "content": "<文件绝对路径>", "guide": "<详细的修改方案>"}

5. **网络搜索**：仅在多次尝试失败后使用
   输出格式：{"summary": "<更新后的总结：继承并补充上一步结果>", "reason": "<推理过程>", "action": "search", "content": "<搜索内容>"}
   警告：只有在尝试自身思考多次无果后才执行搜索

6. **完成任务**：修复成功或确认失败
   - 成功：{"summary": "<完整总结：问题描述+所有步骤+最终方案>", "reason": "<推理过程>", "action": "finish", "content": "success", "commands": ["<命令1>", "<命令2>"]}
   - 失败：{"summary": "<完整总结：问题描述+所有尝试+失败原因>", "reason": "<推理过程>", "action": "finish", "content": "fail"}

## 关键要求：summary字段的生成规则
- **summary只包含已完成的历史操作，不包含本次即将执行的操作**
- **每次输出的summary必须是累积式的完整总结**
- **必须足够详细，包含所有关键信息，避免信息丢失**
- **生成逻辑**：
  1. 从history_summary继承所有历史信息（不要遗漏任何细节）
  2. 补充上一步操作的执行结果（成功/失败/获得了什么信息）
  3. 对于文件读取，必须记录关键内容摘要
  4. 对于命令执行，必须记录完整的输出和错误信息
  5. 更新当前状态
  6. 不要在summary中描述本次即将执行的操作

- **summary必须包含以下结构化内容**：

### 1. 原始需求与意图 (Primary Request and Intent)
- 详细记录用户的原始命令和期望达成的目标
- 包含所有明确的需求和隐含的意图

### 2. 关键技术概念 (Key Technical Concepts)
- 列出所有涉及的技术概念、框架、工具
- 例如：Node.js、npm、端口占用、文件权限等

### 3. 文件与代码操作 (Files and Code Sections)
- **详细记录**所有读取、修改、创建的文件及其路径
- 对于文件读取操作，**必须记录读取到的关键内容**（不能只说"已读取"）
  - 例如：读取了package.json，内容显示start脚本为"node ./bin/www"，依赖包括express@4.16.1, mongodb@3.6.0等
  - 例如：读取了README.md，发现启动说明为"先运行npm run build，再执行npm start"
- 对于代码修改，包含关键代码片段的前后对比
- 说明为什么操作这个文件，达成了什么目的
- 特别关注最近的操作，但保留所有历史文件操作记录

### 4. 问题解决过程 (Problem Solving)
- 记录已解决的问题及解决方案
- 当前正在排查的问题
- 尝试过但失败的方法

### 5. 执行步骤历史 (Execution History)
- **详细记录**按时间顺序的所有执行命令/操作
- 每步必须包含：
  - 执行的完整命令或操作
  - 执行结果（成功/失败/部分成功）
  - **关键输出信息或错误信息**（不能只说"失败"或"成功"）
- 格式示例：
  - 第1步：执行\`npm install\`，报错"EACCES: permission denied"
  - 第2步：执行\`sudo npm install\`，成功安装了25个包，耗时30秒
  - 第3步：执行\`npm start\`，报错"Error: Cannot find module './bin/www'"
  - 第4步：读取package.json，发现start脚本指向缺失的./bin/www文件
  - 第5步：搜索项目目录，确认不存在bin目录，也无app.js或index.js

### 6. 当前状态 (Current Status)
- 问题是否已解决/部分解决/仍在排查
- 下一步计划方向

## 其他要求
- 每次只执行一个操作
- **必须基于history_summary避免重复无效操作**
  - 在reason中明确说明为什么选择这个操作，而不是重复之前的操作
  - 如果某个文件已经读取过，不要再次读取（除非有新的理由）
  - 如果某个命令已经失败过，不要用相同参数再次执行
  - 每次操作都应该是基于已有信息的新尝试
- 在声明失败前必须经过多次不同方向的尝试
- **推理过程中必须参考执行历史**，明确说明：
  - 已经尝试过哪些方法
  - 为什么那些方法失败了
  - 本次操作与之前的区别是什么
  - 为什么本次操作有可能成功 `},
		];
		/*#{1IUIPQ6810PrePrompt*/
		/*}#1IUIPQ6810PrePrompt*/
		prompt=`当前路径是: ${latest_path}，
上一步动作输出是 ${output}`;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IUIPQ6810FilterMessage*/
			/*}#1IUIPQ6810FilterMessage*/
			messages.push(msg);
		}
		/*#{1IUIPQ6810PreCall*/
		/*}#1IUIPQ6810PreCall*/
		result=(result===null)?(await session.callSegLLM("Fix@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IUIPQ6810PostCall*/
		history_summary=result.summary;
		/*}#1IUIPQ6810PostCall*/
		/*#{1IUIPQ6810PreResult*/
		/*}#1IUIPQ6810PreResult*/
		return {seg:Action,result:(result),preSeg:"1IUIPQ6810",outlet:"1IUIPU6VC1"};
	};
	Fix.jaxId="1IUIPQ6810"
	Fix.url="Fix@"+agentURL
	
	segs["Action"]=Action=async function(input){//:1IUIQ6VP90
		let result=input;
		if(input.action==="command"){
			return {seg:RunCommand,result:(input),preSeg:"1IUIQ6VP90",outlet:"1IUIQJ48H0"};
		}
		if(input.action==="search"){
			return {seg:RunSearch,result:(input),preSeg:"1IUIQ6VP90",outlet:"1IUIQ7SC50"};
		}
		if(input.action==="finish"){
			return {seg:CheckFinish,result:(input),preSeg:"1IUIQ6VP90",outlet:"1IUIQO7E60"};
		}
		if(input.action==="read"){
			return {seg:ReadFile,result:(input),preSeg:"1IUIQ6VP90",outlet:"1J0T88DUD0"};
		}
		if(input.action==="modify"){
			return {seg:Modify,result:(input),preSeg:"1IUIQ6VP90",outlet:"1J0T883LJ0"};
		}
		if(input.action==="write"){
			return {seg:WriteFile,result:(input),preSeg:"1IUIQ6VP90",outlet:"1J35TBB4I0"};
		}
		return {result:result};
	};
	Action.jaxId="1IUIQ6VP90"
	Action.url="Action@"+agentURL
	
	segs["RunCommand"]=RunCommand=async function(input){//:1IUIQ96PT0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=input.content;
		args['options']="";
		/*#{1IUIQ96PT0PreCodes*/
		/*}#1IUIQ96PT0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IUIQ96PT0PostCodes*/
		output=result;
		/*}#1IUIQ96PT0PostCodes*/
		return {seg:Path,result:(result),preSeg:"1IUIQ96PT0",outlet:"1IUIQJ48H2"};
	};
	RunCommand.jaxId="1IUIQ96PT0"
	RunCommand.url="RunCommand@"+agentURL
	
	segs["CheckFinish"]=CheckFinish=async function(input){//:1IUIQOIRV0
		let result=input;
		if(input.content==="success"){
			return {seg:BackPath,result:(input),preSeg:"1IUIQOIRV0",outlet:"1IUIQRGDO0"};
		}
		return {seg:Fail,result:(result),preSeg:"1IUIQOIRV0",outlet:"1IUIQRGDO1"};
	};
	CheckFinish.jaxId="1IUIQOIRV0"
	CheckFinish.url="CheckFinish@"+agentURL
	
	segs["Fail"]=Fail=async function(input){//:1IUIQQDFG0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content="无法修复问题";
		/*#{1IUIQQDFG0PreCodes*/
		/*}#1IUIQQDFG0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IUIQQDFG0PostCodes*/
		result="break";
		/*}#1IUIQQDFG0PostCodes*/
		return {result:result};
	};
	Fail.jaxId="1IUIQQDFG0"
	Fail.url="Fail@"+agentURL
	
	segs["GetPath"]=GetPath=async function(input){//:1IVIP6FF50
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="pwd";
		args['options']="";
		/*#{1IVIP6FF50PreCodes*/
		/*}#1IVIP6FF50PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IVIP6FF50PostCodes*/
		current_path=extract(result);
		/*}#1IVIP6FF50PostCodes*/
		return {seg:Issues,result:(result),preSeg:"1IVIP6FF50",outlet:"1IVIP6TOL0"};
	};
	GetPath.jaxId="1IVIP6FF50"
	GetPath.url="GetPath@"+agentURL
	
	segs["BackPath"]=BackPath=async function(input){//:1IVIPCBLH0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`cd "${current_path}"`;
		args['options']="";
		/*#{1IVIPCBLH0PreCodes*/
		/*}#1IVIPCBLH0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IVIPCBLH0PostCodes*/
		result=input;
		/*}#1IVIPCBLH0PostCodes*/
		return {seg:FixSuccess,result:(result),preSeg:"1IVIPCBLH0",outlet:"1IVIPCU1N0"};
	};
	BackPath.jaxId="1IVIPCBLH0"
	BackPath.url="BackPath@"+agentURL
	
	segs["Success"]=Success=async function(input){//:1IVJ1QC600
		let result=input
		/*#{1IVJ1QC600Code*/
		result="";
		/*}#1IVJ1QC600Code*/
		return {result:result};
	};
	Success.jaxId="1IVJ1QC600"
	Success.url="Success@"+agentURL
	
	segs["Issues"]=Issues=async function(input){//:1J08OTLLI0
		let prompt;
		let result=null;
		{
			const $text="An issue occurs, start automatic repair.";
			const $role=(undefined)||"assistant";
			const $roleText=("assistant")||undefined;
			await session.addChatText($role,$text,{"channel":"Process","txtHeader":$roleText});
		}
		/*#{1J08OTLLI0Input*/
		/*}#1J08OTLLI0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=Issues.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`你是一个github项目部署专家，正在部署的项目是 ${repo}，在尝试运行一个命令但遇到了错误，希望在google中查找解决方案，请根据错误给出适合在google里搜索的内容，包含项目名称，以JSON格式返回，如 {"search_content":"github ${repo} huggingface-cli command not found."}。`},
		];
		/*#{1J08OTLLI0PrePrompt*/
		/*}#1J08OTLLI0PrePrompt*/
		prompt=current_output;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1J08OTLLI0FilterMessage*/
			/*}#1J08OTLLI0FilterMessage*/
			messages.push(msg);
		}
		/*#{1J08OTLLI0PreCall*/
		/*}#1J08OTLLI0PreCall*/
		result=(result===null)?(await session.callSegLLM("Issues@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1J08OTLLI0PostCall*/
		bug=result.search_content;
		/*}#1J08OTLLI0PostCall*/
		/*#{1J08OTLLI0PreResult*/
		/*}#1J08OTLLI0PreResult*/
		return {seg:SearchIssue,result:(result),preSeg:"1J08OTLLI0",outlet:"1J08P3QKK0"};
	};
	Issues.jaxId="1J08OTLLI0"
	Issues.url="Issues@"+agentURL
	
	segs["RunSearch"]=RunSearch=async function(input){//:1J0B68RHM0
		let result=input
		/*#{1J0B68RHM0Code*/
		result=fetchLinksAndArticles(input.content);
		output=result;
		/*}#1J0B68RHM0Code*/
		return {seg:Path,result:(result),preSeg:"1J0B68RHM0",outlet:"1J0B69HVV0"};
	};
	RunSearch.jaxId="1J0B68RHM0"
	RunSearch.url="RunSearch@"+agentURL
	
	segs["SearchIssue"]=SearchIssue=async function(input){//:1J0BMLV7G0
		let result=input
		/*#{1J0BMLV7G0Code*/
		result=await getSolution(input.search_content);
		/*}#1J0BMLV7G0Code*/
		return {seg:ListFiles,result:(result),preSeg:"1J0BMLV7G0",outlet:"1J0BMMCDL0"};
	};
	SearchIssue.jaxId="1J0BMLV7G0"
	SearchIssue.url="SearchIssue@"+agentURL
	
	segs["CheckNetwork"]=CheckNetwork=async function(input){//:1J0R3OUU30
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
		let chatMem=CheckNetwork.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你需要根据输入的终端命令输出，判断是否是由于网络不稳定问题导致的错误。请根据以下标准判断：\n\n- 如果输出中有与网络连接、服务器不可达、DNS解析错误、超时、无法连接等相关的错误信息，则可能是由于网络不稳定问题导致的。\n- 如果输出中有与文件、权限、磁盘空间、程序错误、端口未打开等无关的错误，则可能不是网络问题。\n- 请输出结果为一个JSON格式，包含两个字段：\n  - is_network_issue：布尔值，表示是否是网络不稳定问题导致的。\n  - message：一个字符串，描述判断的依据。\n示例： \n{\n\"is_network_issue\": true,\n\"message\": \"Output contains 'Network is unreachable' and 'Connection timed out', indicating a network issue.\"\n}"},
		];
		prompt=current_output;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("CheckNetwork@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:Network,result:(result),preSeg:"1J0R3OUU30",outlet:"1J0R3PIRS0"};
	};
	CheckNetwork.jaxId="1J0R3OUU30"
	CheckNetwork.url="CheckNetwork@"+agentURL
	
	segs["Network"]=Network=async function(input){//:1J0R447KF0
		let result=input;
		if(input.is_network_issue){
			return {result:input};
		}
		return {result:result};
	};
	Network.jaxId="1J0R447KF0"
	Network.url="Network@"+agentURL
	
	segs["Retry"]=Retry=async function(input){//:1J0R4BBI40
		let prompt=("Network Error. Please check your network connection and retry.")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Retry",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Abort",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Run,result:(result),preSeg:"1J0R4BBI40",outlet:"1J0R4BBHH0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Run,result:(result),preSeg:"1J0R4BBI40",outlet:"1J0R4BBHH0"};
		}else if(item.code===1){
			return {result:result};
		}
		return {result:result};
	};
	Retry.jaxId="1J0R4BBI40"
	Retry.url="Retry@"+agentURL
	
	segs["ListFiles"]=ListFiles=async function(input){//:1J0T8KI120
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`find "${decodeURIComponent(basePath)}/projects/${repo.split("/").pop()}" -type f -not -path "*/.git/*" -not -path "*/__pycache__/*" -not -path "*/.pytest_cache/*" -not -path "*/.tox/*" -not -path "*/venv/*" -not -path "*/.venv/*" -not -path "*/env/*" -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" -not -path "*/*.egg-info/*" -not -path "*/.mypy_cache/*" -not -path "*/.coverage/*"`;
		args['options']="";
		/*#{1J0T8KI120PreCodes*/
		/*}#1J0T8KI120PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1J0T8KI120PostCodes*/
		all_files = extract(result);
		/*}#1J0T8KI120PostCodes*/
		return {seg:Path,result:(result),preSeg:"1J0T8KI120",outlet:"1J0T8MNRE0"};
	};
	ListFiles.jaxId="1J0T8KI120"
	ListFiles.url="ListFiles@"+agentURL
	
	segs["Path"]=Path=async function(input){//:1J0T8UJ4S0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="pwd";
		args['options']="";
		/*#{1J0T8UJ4S0PreCodes*/
		/*}#1J0T8UJ4S0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1J0T8UJ4S0PostCodes*/
		latest_path=extract(result);
		/*}#1J0T8UJ4S0PostCodes*/
		return {seg:Fix,result:(result),preSeg:"1J0T8UJ4S0",outlet:"1J0T8V4S40"};
	};
	Path.jaxId="1J0T8UJ4S0"
	Path.url="Path@"+agentURL
	
	segs["ReadFile"]=ReadFile=async function(input){//:1J0TD770P0
		let result;
		let arg=input.content;
		let agentNode=("AgentBuilder")||null;
		let sourcePath="ToolReadFile.js";
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		{
			const $text=`Reading ${input.content}.`;
			const $role=(undefined)||"assistant";
			const $roleText=("assistant")||undefined;
			await session.addChatText($role,$text,{"channel":"Process","txtHeader":$roleText});
		}
		/*#{1J0TD770P0Input*/
		/*}#1J0TD770P0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1J0TD770P0Output*/
		output=result;
		/*}#1J0TD770P0Output*/
		return {seg:Path,result:(result),preSeg:"1J0TD770P0",outlet:"1J0TD770Q0"};
	};
	ReadFile.jaxId="1J0TD770P0"
	ReadFile.url="ReadFile@"+agentURL
	
	segs["FixSuccess"]=FixSuccess=async function(input){//:1J1HQ5UUF0
		let result=input;
		let $channel="Process";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content="Fixed successfully.";
		session.addChatText(role,content,opts);
		return {result:result};
	};
	FixSuccess.jaxId="1J1HQ5UUF0"
	FixSuccess.url="FixSuccess@"+agentURL
	
	segs["Modify"]=Modify=async function(input){//:1J35PLVQ20
		let result;
		let arg={filePath:input.content,guide:input.guide};
		let agentNode=("AgentBuilder")||null;
		let sourcePath="ToolModifyFile.js";
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1J35PLVQ20Input*/
		/*}#1J35PLVQ20Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1J35PLVQ20Output*/
		output="Modify Complete";
		/*}#1J35PLVQ20Output*/
		return {seg:Path,result:(result),preSeg:"1J35PLVQ20",outlet:"1J35POUTJ0"};
	};
	Modify.jaxId="1J35PLVQ20"
	Modify.url="Modify@"+agentURL
	
	segs["WriteFile"]=WriteFile=async function(input){//:1J35TBMGR0
		let result;
		let arg={filePath:input.filePath,content:input.content,append:false};
		let agentNode=("AgentBuilder")||null;
		let sourcePath="ToolWriteFile.js";
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1J35TBMGR0Input*/
		/*}#1J35TBMGR0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1J35TBMGR0Output*/
		output="Write Complete";
		/*}#1J35TBMGR0Output*/
		return {seg:Path,result:(result),preSeg:"1J35TBMGR0",outlet:"1J35TCF2H0"};
	};
	WriteFile.jaxId="1J35TBMGR0"
	WriteFile.url="WriteFile@"+agentURL
	
	segs["UpdateSolution"]=UpdateSolution=async function(input){//:1J3IG34AB0
		let result=input
		/*#{1J3IG34AB0Code*/
		try{
			await sendRequest(bug,input.summary);
		} catch(error){
			console.log("Update Error");
		}
		
		/*}#1J3IG34AB0Code*/
		return {result:result};
	};
	UpdateSolution.jaxId="1J3IG34AB0"
	UpdateSolution.url="UpdateSolution@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolRunCommand",
		url:agentURL,
		autoStart:true,
		jaxId:"1IUIO756A0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{command,repo}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IUIO756A0PreEntry*/
			/*}#1IUIO756A0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IUIO756A0PostEntry*/
			/*}#1IUIO756A0PostEntry*/
			return result;
		},
		/*#{1IUIO756A0MoreAgentAttrs*/
		/*}#1IUIO756A0MoreAgentAttrs*/
	};
	/*#{1IUIO756A0PostAgent*/
	/*}#1IUIO756A0PostAgent*/
	return agent;
};
/*#{1IUIO756A0ExCodes*/
/*}#1IUIO756A0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolRunCommand",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				command:{type:"auto",description:"A bash command"},
				repo:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
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
		name:"ToolRunCommand",showName:"ToolRunCommand",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"command":{name:"command",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"repo":{name:"repo",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","command","repo","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolRunCommand"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['command']=");this.genAttrStatement(seg.getAttr("command"));coder.packText(";");coder.newLine();
			coder.packText("args['repo']=");this.genAttrStatement(seg.getAttr("repo"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AutoDeploy/ai/ToolRunCommand.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
			this.packUpdateContext(coder,seg);
			this.packUpdateGlobal(coder,seg);
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
/*#{1IUIO756A0PostDoc*/
/*}#1IUIO756A0PostDoc*/


export default ToolRunCommand;
export{ToolRunCommand,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IUIO756A0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IUIO756B0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1IUIO5V5O0",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IUIO756B1",
//			"attrs": {
//				"command": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IUIO756B2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "A bash command",
//						"required": "true"
//					}
//				},
//				"repo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J08OD2VG0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IUIO756B3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IUIO756B4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IUIO756B5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IUIO65O30",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "200",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1IUIO756A1",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIOB71S0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IUIOB71S0",
//					"attrs": {
//						"id": "Run",
//						"viewName": "",
//						"label": "",
//						"x": "390",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIOC3B60",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIOC3B61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#command",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IUIOC3B40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIP57LI0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IUIP57LI0",
//					"attrs": {
//						"id": "CheckSuccess",
//						"viewName": "",
//						"label": "",
//						"x": "575",
//						"y": "100",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIP9MVB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIP9MVB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenAI",
//						"mode": "gpt-4.1",
//						"system": "你是一个终端命令的分析助手。当接收到终端运行的命令和输出时，你需要判断命令是否执行成功。根据命令的输出判断其成功或失败，并以JSON格式输出结果。输出的JSON格式为：{'success': true/false}，其中 'true' 表示命令执行成功，'false' 表示命令执行失败。如果输入是空的，认为执行成功。你只需要根据输出的信息判断命令是否成功，无需进一步的解释。",
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
//							"jaxId": "1IUIP9MVA0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIPB1E90"
//						},
//						"stream": "true",
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
//						"formatDef": "\"\"",
//						"outlets": {
//							"attrs": []
//						},
//						"compactContext": {
//							"valText": "200000"
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IUIPB1E90",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "810",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIPC0310",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIPC0311",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IUIPC0301",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IVIP6FF50"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IUIPC0300",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IUIPC0312",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IUIPC0313",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.success"
//									},
//									"linkedSeg": "1IVJ1QC600"
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
//					"jaxId": "1IUIPQ6810",
//					"attrs": {
//						"id": "Fix",
//						"viewName": "",
//						"label": "",
//						"x": "2640",
//						"y": "195",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIQ0KLM2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIQ0KLM3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenAI",
//						"mode": "gpt-4.1",
//						"system": "#`你是一个命令行问题修复专家,具备丰富的Linux/Unix系统管理经验和故障排查能力。\n\n## 当前任务状态\n原始目标：${command}\n历史操作总结：${history_summary}\n项目内包含的所有文件：${all_files}\n搜索到的参考方案：${search_result}\n\n## 你的任务\n基于历史操作总结，分析当前状态并决定下一步行动。你需要通过自身思考和推理，给出新的命令或解决方案，以json格式输出。\n\n## 可用的操作方式\n1. **执行终端命令**：每次只能执行一个命令\n   输出格式：{\"summary\": \"<更新后的总结：继承history_summary并补充上一步的操作结果>\", \"reason\": \"<基于summary的推理过程，说明为什么要执行这个命令>\", \"action\": \"command\", \"content\": \"<命令>\"}\n   注意：如果命令可能不会自动退出，请设置timeout为2分钟\n\n2. **读取文件**：查看特定文件内容来帮助诊断问题\n   输出格式：{\"summary\": \"<更新后的总结：继承并补充上一步结果>\", \"reason\": \"<推理过程>\", \"action\": \"read\", \"content\": \"<文件绝对路径>\"}\n\n3. **写入新文件**：创建并写入新文件\n   输出格式：{\"summary\": \"<更新后的总结：继承并补充上一步结果>\", \"reason\": \"<推理过程>\", \"action\": \"write\", \"filePath\": \"<文件绝对路径>\", \"content\": \"<写入内容>\"}\n\n4. **修改文件**：修改配置文件或其他文件\n   输出格式：{\"summary\": \"<更新后的总结：继承并补充上一步结果>\", \"reason\": \"<推理过程>\", \"action\": \"modify\", \"content\": \"<文件绝对路径>\", \"guide\": \"<详细的修改方案>\"}\n\n5. **网络搜索**：仅在多次尝试失败后使用\n   输出格式：{\"summary\": \"<更新后的总结：继承并补充上一步结果>\", \"reason\": \"<推理过程>\", \"action\": \"search\", \"content\": \"<搜索内容>\"}\n   警告：只有在尝试自身思考多次无果后才执行搜索\n\n6. **完成任务**：修复成功或确认失败\n   - 成功：{\"summary\": \"<完整总结：问题描述+所有步骤+最终方案>\", \"reason\": \"<推理过程>\", \"action\": \"finish\", \"content\": \"success\", \"commands\": [\"<命令1>\", \"<命令2>\"]}\n   - 失败：{\"summary\": \"<完整总结：问题描述+所有尝试+失败原因>\", \"reason\": \"<推理过程>\", \"action\": \"finish\", \"content\": \"fail\"}\n\n## 关键要求：summary字段的生成规则\n- **summary只包含已完成的历史操作，不包含本次即将执行的操作**\n- **每次输出的summary必须是累积式的完整总结**\n- **必须足够详细，包含所有关键信息，避免信息丢失**\n- **生成逻辑**：\n  1. 从history_summary继承所有历史信息（不要遗漏任何细节）\n  2. 补充上一步操作的执行结果（成功/失败/获得了什么信息）\n  3. 对于文件读取，必须记录关键内容摘要\n  4. 对于命令执行，必须记录完整的输出和错误信息\n  5. 更新当前状态\n  6. 不要在summary中描述本次即将执行的操作\n\n- **summary必须包含以下结构化内容**：\n\n### 1. 原始需求与意图 (Primary Request and Intent)\n- 详细记录用户的原始命令和期望达成的目标\n- 包含所有明确的需求和隐含的意图\n\n### 2. 关键技术概念 (Key Technical Concepts)\n- 列出所有涉及的技术概念、框架、工具\n- 例如：Node.js、npm、端口占用、文件权限等\n\n### 3. 文件与代码操作 (Files and Code Sections)\n- **详细记录**所有读取、修改、创建的文件及其路径\n- 对于文件读取操作，**必须记录读取到的关键内容**（不能只说\"已读取\"）\n  - 例如：读取了package.json，内容显示start脚本为\"node ./bin/www\"，依赖包括express@4.16.1, mongodb@3.6.0等\n  - 例如：读取了README.md，发现启动说明为\"先运行npm run build，再执行npm start\"\n- 对于代码修改，包含关键代码片段的前后对比\n- 说明为什么操作这个文件，达成了什么目的\n- 特别关注最近的操作，但保留所有历史文件操作记录\n\n### 4. 问题解决过程 (Problem Solving)\n- 记录已解决的问题及解决方案\n- 当前正在排查的问题\n- 尝试过但失败的方法\n\n### 5. 执行步骤历史 (Execution History)\n- **详细记录**按时间顺序的所有执行命令/操作\n- 每步必须包含：\n  - 执行的完整命令或操作\n  - 执行结果（成功/失败/部分成功）\n  - **关键输出信息或错误信息**（不能只说\"失败\"或\"成功\"）\n- 格式示例：\n  - 第1步：执行\\`npm install\\`，报错\"EACCES: permission denied\"\n  - 第2步：执行\\`sudo npm install\\`，成功安装了25个包，耗时30秒\n  - 第3步：执行\\`npm start\\`，报错\"Error: Cannot find module './bin/www'\"\n  - 第4步：读取package.json，发现start脚本指向缺失的./bin/www文件\n  - 第5步：搜索项目目录，确认不存在bin目录，也无app.js或index.js\n\n### 6. 当前状态 (Current Status)\n- 问题是否已解决/部分解决/仍在排查\n- 下一步计划方向\n\n## 其他要求\n- 每次只执行一个操作\n- **必须基于history_summary避免重复无效操作**\n  - 在reason中明确说明为什么选择这个操作，而不是重复之前的操作\n  - 如果某个文件已经读取过，不要再次读取（除非有新的理由）\n  - 如果某个命令已经失败过，不要用相同参数再次执行\n  - 每次操作都应该是基于已有信息的新尝试\n- 在声明失败前必须经过多次不同方向的尝试\n- **推理过程中必须参考执行历史**，明确说明：\n  - 已经尝试过哪些方法\n  - 为什么那些方法失败了\n  - 本次操作与之前的区别是什么\n  - 为什么本次操作有可能成功 `",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#`当前路径是: ${latest_path}，\n上一步动作输出是 ${output}`",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IUIPU6VC1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIQ6VP90"
//						},
//						"stream": "true",
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
//						"formatDef": "\"\"",
//						"outlets": {
//							"attrs": []
//						},
//						"compactContext": {
//							"valText": "200000"
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IUIQ6VP90",
//					"attrs": {
//						"id": "Action",
//						"viewName": "",
//						"label": "",
//						"x": "2910",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIQJ48L0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIQJ48L1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IUIQJ48H1",
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
//									"jaxId": "1IUIQJ48H0",
//									"attrs": {
//										"id": "Bash",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IUIQJ48L2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IUIQJ48L3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"command\""
//									},
//									"linkedSeg": "1IUIQ96PT0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IUIQ7SC50",
//									"attrs": {
//										"id": "Search",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IUIQJ48L4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IUIQJ48L5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"search\""
//									},
//									"linkedSeg": "1J0B68RHM0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IUIQO7E60",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IUIQO7EA0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IUIQO7EA1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"finish\""
//									},
//									"linkedSeg": "1IUIQOIRV0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J0T88DUD0",
//									"attrs": {
//										"id": "Read",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J0T88DUF0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J0T88DUF1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"read\""
//									},
//									"linkedSeg": "1J0TD770P0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J0T883LJ0",
//									"attrs": {
//										"id": "Modify",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J0T88DUF2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J0T88DUF3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"modify\""
//									},
//									"linkedSeg": "1J35PLVQ20"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J35TBB4I0",
//									"attrs": {
//										"id": "Write",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J35TBB4R0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J35TBB4R1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"write\""
//									},
//									"linkedSeg": "1J35TBMGR0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IUIQ96PT0",
//					"attrs": {
//						"id": "RunCommand",
//						"viewName": "",
//						"label": "",
//						"x": "3120",
//						"y": "85",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIQJ48L6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIQJ48L7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#input.content",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IUIQJ48H2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIQRTBI0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IUIQOIRV0",
//					"attrs": {
//						"id": "CheckFinish",
//						"viewName": "",
//						"label": "",
//						"x": "3120",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIQRGE30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIQRGE31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IUIQRGDO1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IUIQQDFG0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IUIQRGDO0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IUIQRGE32",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IUIQRGE33",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.content===\"success\""
//									},
//									"linkedSeg": "1IVIPCBLH0"
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
//					"jaxId": "1IUIQQDFG0",
//					"attrs": {
//						"id": "Fail",
//						"viewName": "",
//						"label": "",
//						"x": "3355",
//						"y": "315",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIQRGE34",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIQRGE35",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "无法修复问题",
//						"outlet": {
//							"jaxId": "1IUIQRGDO2",
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
//					"def": "connector",
//					"jaxId": "1IUIQRTBI0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3285",
//						"y": "5",
//						"outlet": {
//							"jaxId": "1IUIQTDO70",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIQS6F30"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IUIQS6F30",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2850",
//						"y": "5",
//						"outlet": {
//							"jaxId": "1IUIQTDO71",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0T8LJH00"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IUIR6RV20",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3410",
//						"y": "5",
//						"outlet": {
//							"jaxId": "1IUIR7LC40",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIQRTBI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IUIR79BQ0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3510",
//						"y": "180",
//						"outlet": {
//							"jaxId": "1IUIR7LC41",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIR6RV20"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IVIP6FF50",
//					"attrs": {
//						"id": "GetPath",
//						"viewName": "",
//						"label": "",
//						"x": "1500",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIP8AMJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIP8AMJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "pwd",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IVIP6TOL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J08OTLLI0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IVIPCBLH0",
//					"attrs": {
//						"id": "BackPath",
//						"viewName": "",
//						"label": "",
//						"x": "3355",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIPCU1T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIPCU1T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`cd \"${current_path}\"`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IVIPCU1N0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1HQ5UUF0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IVJ1QC600",
//					"attrs": {
//						"id": "Success",
//						"viewName": "",
//						"label": "",
//						"x": "1010",
//						"y": "0",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVJ1VA3T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVJ1VA3T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IVJ1QQP20",
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
//					"def": "callLLM",
//					"jaxId": "1J08OTLLI0",
//					"attrs": {
//						"id": "Issues",
//						"viewName": "",
//						"label": "",
//						"x": "1725",
//						"y": "195",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J08P3QL00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J08P3QL10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1",
//						"system": "#`你是一个github项目部署专家，正在部署的项目是 ${repo}，在尝试运行一个命令但遇到了错误，希望在google中查找解决方案，请根据错误给出适合在google里搜索的内容，包含项目名称，以JSON格式返回，如 {\"search_content\":\"github ${repo} huggingface-cli command not found.\"}。`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#current_output",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1J08P3QKK0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0BMLV7G0"
//						},
//						"stream": "true",
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
//						"formatDef": "\"\"",
//						"outlets": {
//							"attrs": []
//						},
//						"compactContext": {
//							"valText": "200000"
//						},
//						"process": {
//							"type": "object",
//							"def": "ProcessMsg",
//							"jaxId": "1J1HQ3SDD0",
//							"attrs": {
//								"text": "An issue occurs, start automatic repair.",
//								"role": "Assistant",
//								"codes": "false",
//								"roleText": ""
//							}
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J0B68RHM0",
//					"attrs": {
//						"id": "RunSearch",
//						"viewName": "",
//						"label": "",
//						"x": "3120",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0B6AG4E0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0B6AG4E1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J0B69HVV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIR79BQ0"
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
//					"def": "code",
//					"jaxId": "1J0BMLV7G0",
//					"attrs": {
//						"id": "SearchIssue",
//						"viewName": "",
//						"label": "",
//						"x": "1915",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0BMMCDU0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0BMMCDU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J0BMMCDL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0T8KI120"
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
//					"def": "callLLM",
//					"jaxId": "1J0R3OUU30",
//					"attrs": {
//						"id": "CheckNetwork",
//						"viewName": "",
//						"label": "",
//						"x": "1010",
//						"y": "235",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0R3PIS00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0R3PIS01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "你需要根据输入的终端命令输出，判断是否是由于网络不稳定问题导致的错误。请根据以下标准判断：\n\n- 如果输出中有与网络连接、服务器不可达、DNS解析错误、超时、无法连接等相关的错误信息，则可能是由于网络不稳定问题导致的。\n- 如果输出中有与文件、权限、磁盘空间、程序错误、端口未打开等无关的错误，则可能不是网络问题。\n- 请输出结果为一个JSON格式，包含两个字段：\n  - is_network_issue：布尔值，表示是否是网络不稳定问题导致的。\n  - message：一个字符串，描述判断的依据。\n示例： \n{\n\"is_network_issue\": true,\n\"message\": \"Output contains 'Network is unreachable' and 'Connection timed out', indicating a network issue.\"\n}",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#current_output",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1J0R3PIRS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0R447KF0"
//						},
//						"stream": "true",
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
//						"formatDef": "\"\"",
//						"outlets": {
//							"attrs": []
//						},
//						"compactContext": {
//							"valText": "200000"
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J0R447KF0",
//					"attrs": {
//						"id": "Network",
//						"viewName": "",
//						"label": "",
//						"x": "1255",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0R45CHT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0R45CHT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J0R45CHR1",
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
//									"jaxId": "1J0R45CHR0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J0R45CHT2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J0R45CHT3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.is_network_issue"
//									}
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1J0R4BBI40",
//					"attrs": {
//						"id": "Retry",
//						"viewName": "",
//						"label": "",
//						"x": "1475",
//						"y": "55",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "Network Error. Please check your network connection and retry.",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1J0R4CDTF0",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J0R4BBHH0",
//									"attrs": {
//										"id": "Retry",
//										"desc": "输出节点。",
//										"text": "Retry",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J0R4CDTJ0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J0R4CDTJ1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1J0R4EAFS0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J0R4BBHH1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "Abort",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J0R4CDTJ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J0R4CDTJ3",
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
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J0R4EAFS0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1625",
//						"y": "-95",
//						"outlet": {
//							"jaxId": "1J0R4FK0U0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0R4EGFD0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J0R4EGFD0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "425",
//						"y": "-95",
//						"outlet": {
//							"jaxId": "1J0R4FK0U1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIOB71S0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1J0T8KI120",
//					"attrs": {
//						"id": "ListFiles",
//						"viewName": "",
//						"label": "",
//						"x": "2135",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0T8MNRJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0T8MNRJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`find \"${decodeURIComponent(basePath)}/projects/${repo.split(\"/\").pop()}\" -type f -not -path \"*/.git/*\" -not -path \"*/__pycache__/*\" -not -path \"*/.pytest_cache/*\" -not -path \"*/.tox/*\" -not -path \"*/venv/*\" -not -path \"*/.venv/*\" -not -path \"*/env/*\" -not -path \"*/node_modules/*\" -not -path \"*/dist/*\" -not -path \"*/build/*\" -not -path \"*/*.egg-info/*\" -not -path \"*/.mypy_cache/*\" -not -path \"*/.coverage/*\"`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J0T8MNRE0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0T8UJ4S0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J0T8LJH00",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2380",
//						"y": "5",
//						"outlet": {
//							"jaxId": "1J0T8MNRJ2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0T8UJ4S0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1J0T8UJ4S0",
//					"attrs": {
//						"id": "Path",
//						"viewName": "",
//						"label": "",
//						"x": "2350",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0T8V4SE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0T8V4SE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "pwd",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J0T8V4S40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIPQ6810"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1J0TD770P0",
//					"attrs": {
//						"id": "ReadFile",
//						"viewName": "",
//						"label": "",
//						"x": "3120",
//						"y": "400",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0TD77110",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0TD77111",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ToolReadFile.js",
//						"argument": "#input.content",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1J0TD770Q0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0TDBCHS0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"agentNode": "AgentBuilder",
//						"process": {
//							"type": "object",
//							"def": "ProcessMsg",
//							"jaxId": "1J1HP84TP0",
//							"attrs": {
//								"text": "#`Reading ${input.content}.`",
//								"role": "Assistant",
//								"codes": "false",
//								"roleText": ""
//							}
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J0TDBCHS0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3575",
//						"y": "400",
//						"outlet": {
//							"jaxId": "1J0TDEVAR0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIR79BQ0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J0TDBNOH0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3575",
//						"y": "480",
//						"outlet": {
//							"jaxId": "1J0TDEVAR1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0TDBCHS0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J1HQ5UUF0",
//					"attrs": {
//						"id": "FixSuccess",
//						"viewName": "",
//						"label": "",
//						"x": "3840",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1HQ7D0I0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1HQ7D0I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Process",
//						"text": "Fixed successfully.",
//						"outlet": {
//							"jaxId": "1J1HQ7D0F0",
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
//					"jaxId": "1J35PLVQ20",
//					"attrs": {
//						"id": "Modify",
//						"viewName": "",
//						"label": "",
//						"x": "3125",
//						"y": "480",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J35POUTP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J35POUTP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ToolModifyFile.js",
//						"argument": "#{filePath:input.content,guide:input.guide}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1J35POUTJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0TDBNOH0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"agentNode": "AgentBuilder"
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1J35TBMGR0",
//					"attrs": {
//						"id": "WriteFile",
//						"viewName": "",
//						"label": "",
//						"x": "3120",
//						"y": "570",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J35TCF2N0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J35TCF2N1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ToolWriteFile.js",
//						"argument": "#{filePath:input.filePath,content:input.content,append:false}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1J35TCF2H0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3IGDL5L0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"agentNode": "AgentBuilder"
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J3IG34AB0",
//					"attrs": {
//						"id": "UpdateSolution",
//						"viewName": "",
//						"label": "",
//						"x": "3595",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3IG4GEQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3IG4GEQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J3IG3KCB0",
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
//					"def": "connector",
//					"jaxId": "1J3IGDL5L0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3575",
//						"y": "570",
//						"outlet": {
//							"jaxId": "1J3IGEKFI0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0TDBNOH0"
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
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}