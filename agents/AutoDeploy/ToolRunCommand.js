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


/*}#1IUIO756A0StartDoc*/
//----------------------------------------------------------------------------
let ToolRunCommand=async function(session){
	let command,repo;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Run,CheckSuccess,Check,Fix,Action,RunCommand,CheckFinish,Fail,GetPath,BackPath,Success,Issues,RunSearch,SearchIssue,CheckNetwork,Network,Retry,ListFiles,Path,ReadFile,FixSuccess,Modify,WriteFile,UpdateSolution,CheckTimes,Failed;
	/*#{1IUIO756A0LocalVals*/
	let current_output, output, current_path, issue, search_result, bug, current_files, latest_path, all_files, cnt=0;
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
		return {seg:CheckNetwork,result:(result),preSeg:"1IUIPB1E90",outlet:"1IUIPC0301"};
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
			{role:"system",content:`你是一个命令行问题修复专家，具备丰富的Linux/Unix系统管理经验和故障排查能力。你正在尝试运行一个命令但遇到了错误，具体是 ${current_output}。输入是当前执行的终端命令及其输出或者是通过上网搜索得出的结果，你需要根据错误信息分析问题并尝试修复。
项目内包含的所有文件：${all_files}
你根据相关报错内容查找到相关的问题和解决方案作为参考
如下：${search_result}
你需要通过自身思考，分析错误原因并推理，尝试给出新的命令或解决方案，以json格式输出
你可以通过以下几种方式进行修复：
1. 如果需要执行终端命令，注意每次只能执行一个命令，输出格式为 {"reason": "<推理过程>", "action": "command", "content": "<命令>"}。如果运行一个可能不会自动退出或者停止的命令时，请设置timeout为2分钟。
2. 如果你无法通过思考解决问题，可以执行其他命令来获取更多的上下文信息，如阅读相关的文件或日志。
3. 如果需要查看特定文件内容来帮助诊断问题，可以读取文件，输出格式为 {"reason": "<推理过程>", "action": "read", "content": "<文件绝对路径>"}。
4. 如果需要创建并写入新文件，可以写入文件，输出格式为 {"reason": "<推理过程>", "action": "write", "filePath": "<文件绝对路径>", "content": "<写入内容>"}。
5. 如果需要修改配置文件或其他文件来解决问题，可以修改文件，输出格式为 {"reason": "<推理过程>", "action": "modify", "content": "<文件绝对路径>", "guide": "<详细的修改方案>"}。
6. 如果多次尝试失败且仍无法解决问题，你可以通过上网搜索寻找解决方案，搜索内容要符合搜索的风格，输出格式为 {"reason": "<推理过程>", "action": "search", "content": "<搜索内容>"}，但是请注意，只有在尝试自身思考多次无果后才执行搜索。
请注意，每次尝试之后，你必须基于新的信息继续思考或修复，确保你在执行搜索之前已经尽力排查和解决问题。每次只能执行一次命令或一次搜索。
7. 如果修复成功，输出所有有效解决问题的终端命令 {"reason": "<推理过程>", "action": "finish", "content": "success", "commands":["<命令1>","命令2",...], "summary": "<执行的命令以及错误，解决方案的描述和总结，需要包含每一条执行的命令以及执行它的原因>"}。
8. 如果多次尝试之后仍然失败，无法完成初始命令的目标，请输出 {"reason": "<推理过程>", "action": "finish", "content": "fail"}，注意一定要经过多次尝试后均失败才算失败。`},
		];
		messages.push(...chatMem);
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
		/*#{1IUIPQ6810PostLLM*/
		/*}#1IUIPQ6810PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1IUIPQ6810PostClear*/
			/*}#1IUIPQ6810PostClear*/
		}
		result=trimJSON(result);
		/*#{1IUIPQ6810PostCall*/
		/*}#1IUIPQ6810PostCall*/
		return {seg:Action,result:(result),preSeg:"1IUIPQ6810",outlet:"1IUIPU6VC1"};
	};
	Fix.jaxId="1IUIPQ6810"
	Fix.url="Fix@"+agentURL
	Fix.messages=[];
	
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
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
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
		return {seg:UpdateSolution,result:(result),preSeg:"1IVIPCBLH0",outlet:"1IVIPCU1N0"};
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
			{role:"system",content:"你需要根据输入的终端命令输出，判断是否是由于网络问题导致的错误。请根据以下标准判断：\n\n- 如果输出中有与网络连接、服务器不可达、DNS解析错误、超时、无法连接等相关的错误信息，则可能是由于网络问题导致的。\n- 如果输出中有与文件、权限、磁盘空间、程序错误等无关的错误，则可能不是网络问题。\n- 请输出结果为一个JSON格式，包含两个字段：\n  - is_network_issue：布尔值，表示是否是网络问题导致的。\n  - message：一个字符串，描述判断的依据。\n示例： \n{\n\"is_network_issue\": true,\n\"message\": \"Output contains 'Network is unreachable' and 'Connection timed out', indicating a network issue.\"\n}"},
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
			return {seg:Retry,result:(input),preSeg:"1J0R447KF0",outlet:"1J0R45CHR0"};
		}
		return {seg:GetPath,result:(result),preSeg:"1J0R447KF0",outlet:"1J0R45CHR1"};
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
		return {seg:CheckTimes,result:(result),preSeg:"1J0T8UJ4S0",outlet:"1J0T8V4S40"};
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
		let channel="Process";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
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
		return {seg:FixSuccess,result:(result),preSeg:"1J3IG34AB0",outlet:"1J3IG3KCB0"};
	};
	UpdateSolution.jaxId="1J3IG34AB0"
	UpdateSolution.url="UpdateSolution@"+agentURL
	
	segs["CheckTimes"]=CheckTimes=async function(input){//:1J3IGL3440
		let result=input;
		if(cnt<=10){
			return {seg:Fix,result:(input),preSeg:"1J3IGL3440",outlet:"1J3IGOELM0"};
		}
		return {seg:Failed,result:(result),preSeg:"1J3IGL3440",outlet:"1J3IGLH770"};
	};
	CheckTimes.jaxId="1J3IGL3440"
	CheckTimes.url="CheckTimes@"+agentURL
	
	segs["Failed"]=Failed=async function(input){//:1J3IGV6IP0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=无法修复问题;
		/*#{1J3IGV6IP0PreCodes*/
		/*}#1J3IGV6IP0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1J3IGV6IP0PostCodes*/
		result="break";
		/*}#1J3IGV6IP0PostCodes*/
		return {result:result};
	};
	Failed.jaxId="1J3IGV6IP0"
	Failed.url="Failed@"+agentURL
	
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
//						"platform": "\"OpenAI\"",
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
//							"linkedSeg": "1J0R3OUU30"
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
//						"x": "2755",
//						"y": "180",
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
//						"system": "#`你是一个命令行问题修复专家，具备丰富的Linux/Unix系统管理经验和故障排查能力。你正在尝试运行一个命令但遇到了错误，具体是 ${current_output}。输入是当前执行的终端命令及其输出或者是通过上网搜索得出的结果，你需要根据错误信息分析问题并尝试修复。\n项目内包含的所有文件：${all_files}\n你根据相关报错内容查找到相关的问题和解决方案作为参考\n如下：${search_result}\n你需要通过自身思考，分析错误原因并推理，尝试给出新的命令或解决方案，以json格式输出\n你可以通过以下几种方式进行修复：\n1. 如果需要执行终端命令，注意每次只能执行一个命令，输出格式为 {\"reason\": \"<推理过程>\", \"action\": \"command\", \"content\": \"<命令>\"}。如果运行一个可能不会自动退出或者停止的命令时，请设置timeout为2分钟。\n2. 如果你无法通过思考解决问题，可以执行其他命令来获取更多的上下文信息，如阅读相关的文件或日志。\n3. 如果需要查看特定文件内容来帮助诊断问题，可以读取文件，输出格式为 {\"reason\": \"<推理过程>\", \"action\": \"read\", \"content\": \"<文件绝对路径>\"}。\n4. 如果需要创建并写入新文件，可以写入文件，输出格式为 {\"reason\": \"<推理过程>\", \"action\": \"write\", \"filePath\": \"<文件绝对路径>\", \"content\": \"<写入内容>\"}。\n5. 如果需要修改配置文件或其他文件来解决问题，可以修改文件，输出格式为 {\"reason\": \"<推理过程>\", \"action\": \"modify\", \"content\": \"<文件绝对路径>\", \"guide\": \"<详细的修改方案>\"}。\n6. 如果多次尝试失败且仍无法解决问题，你可以通过上网搜索寻找解决方案，搜索内容要符合搜索的风格，输出格式为 {\"reason\": \"<推理过程>\", \"action\": \"search\", \"content\": \"<搜索内容>\"}，但是请注意，只有在尝试自身思考多次无果后才执行搜索。\n请注意，每次尝试之后，你必须基于新的信息继续思考或修复，确保你在执行搜索之前已经尽力排查和解决问题。每次只能执行一次命令或一次搜索。\n7. 如果修复成功，输出所有有效解决问题的终端命令 {\"reason\": \"<推理过程>\", \"action\": \"finish\", \"content\": \"success\", \"commands\":[\"<命令1>\",\"命令2\",...], \"summary\": \"<执行的命令以及错误，解决方案的描述和总结，需要包含每一条执行的命令以及执行它的原因>\"}。\n8. 如果多次尝试之后仍然失败，无法完成初始命令的目标，请输出 {\"reason\": \"<推理过程>\", \"action\": \"finish\", \"content\": \"fail\"}，注意一定要经过多次尝试后均失败才算失败。`",
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
//					"jaxId": "1IUIQ6VP90",
//					"attrs": {
//						"id": "Action",
//						"viewName": "",
//						"label": "",
//						"x": "2920",
//						"y": "180",
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
//						"x": "3130",
//						"y": "70",
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
//						"x": "3130",
//						"y": "260",
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
//						"x": "3365",
//						"y": "300",
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
//						"x": "3295",
//						"y": "-10",
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
//						"x": "2860",
//						"y": "-10",
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
//						"x": "3420",
//						"y": "-10",
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
//						"x": "3520",
//						"y": "165",
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
//						"x": "3365",
//						"y": "220",
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
//							"linkedSeg": "1J3IG34AB0"
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
//						"process": {
//							"type": "object",
//							"def": "ProcessMsg",
//							"jaxId": "1J1HQ3SDD0",
//							"attrs": {
//								"text": "An issue occurs, start automatic repair.",
//								"role": "Assistant",
//								"roleText": "",
//								"codes": "false"
//							}
//						}
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J0B68RHM0",
//					"attrs": {
//						"id": "RunSearch",
//						"viewName": "",
//						"label": "",
//						"x": "3130",
//						"y": "165",
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
//						"y": "180",
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
//						"system": "你需要根据输入的终端命令输出，判断是否是由于网络问题导致的错误。请根据以下标准判断：\n\n- 如果输出中有与网络连接、服务器不可达、DNS解析错误、超时、无法连接等相关的错误信息，则可能是由于网络问题导致的。\n- 如果输出中有与文件、权限、磁盘空间、程序错误等无关的错误，则可能不是网络问题。\n- 请输出结果为一个JSON格式，包含两个字段：\n  - is_network_issue：布尔值，表示是否是网络问题导致的。\n  - message：一个字符串，描述判断的依据。\n示例： \n{\n\"is_network_issue\": true,\n\"message\": \"Output contains 'Network is unreachable' and 'Connection timed out', indicating a network issue.\"\n}",
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
//					"jaxId": "1J0R447KF0",
//					"attrs": {
//						"id": "Network",
//						"viewName": "",
//						"label": "",
//						"x": "1245",
//						"y": "180",
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
//							},
//							"linkedSeg": "1IVIP6FF50"
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
//									},
//									"linkedSeg": "1J0R4BBI40"
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
//						"y": "-10",
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
//							"linkedSeg": "1J3IGL3440"
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
//						"x": "3130",
//						"y": "385",
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
//								"roleText": "",
//								"codes": "false"
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
//						"x": "3585",
//						"y": "385",
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
//						"x": "3585",
//						"y": "465",
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
//						"x": "3850",
//						"y": "220",
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
//						"x": "3135",
//						"y": "465",
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
//						"x": "3130",
//						"y": "555",
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
//						"x": "3580",
//						"y": "220",
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
//							},
//							"linkedSeg": "1J1HQ5UUF0"
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
//						"x": "3585",
//						"y": "555",
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
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J3IGL3440",
//					"attrs": {
//						"id": "CheckTimes",
//						"viewName": "",
//						"label": "",
//						"x": "2530",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3IGM2QJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3IGM2QJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J3IGLH770",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J3IGV6IP0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J3IGOELM0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J3IGPF360",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J3IGPF361",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#cnt<=10"
//									},
//									"linkedSeg": "1IUIPQ6810"
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
//					"jaxId": "1J3IGV6IP0",
//					"attrs": {
//						"id": "Failed",
//						"viewName": "",
//						"label": "",
//						"x": "2755",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3IGVTEO0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3IGVTEO1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#无法修复问题",
//						"outlet": {
//							"jaxId": "1J3IGVTEK0",
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
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}