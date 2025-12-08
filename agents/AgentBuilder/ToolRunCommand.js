//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IUIO756A0MoreImports*/
import { Octokit } from 'octokit';
/*}#1IUIO756A0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"command":{
			"name":"command","type":"string",
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
const octokit = new Octokit({
	auth: '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' // 替换为你的token
});
async function searchBugIssues(bugDescription, repo, issueCount = 5) {
	try {
		let query = `is:issue "${bugDescription}"`;
		if (repo) query += ` repo:${repo}`;

		const response = await octokit.request('GET /search/issues', {
			headers: { 'X-GitHub-Api-Version': '2022-11-28' },
			q: query,
			sort: 'relevance',
			order: 'desc',
			per_page: issueCount,
			page: 1
		});

		const issues = response.data.items.slice(0, issueCount);
		const pieces = [];

		for (const issue of issues) {
			const [owner, repoName] = issue.html_url
				.split('/')
				.slice(-4, -2);

			let section = `Issue 标题：${issue.title}\n`;

			if (issue.comments > 0) {
				const commentsResp = await octokit.request(
					'GET /repos/{owner}/{repo}/issues/{issue_number}/comments',
					{
						owner,
						repo: repoName,
						issue_number: issue.number,
						headers: { 'X-GitHub-Api-Version': '2022-11-28' }
					}
				);
				const bodies = commentsResp.data.map((c, i) => `${i + 1}. ${c.body}`);
				section += '评论：\n' + bodies.join('\n') + '\n';
			} else {
				section += '暂无评论\n';
			}

			pieces.push(section);
			// 防止触发 API 限制
			await new Promise(r => setTimeout(r, 500));
		}

		// 把所有 section 用两行空行隔开，拼成一个大字符串
		return pieces.join('\n\n');

	} catch (error) {
		throw new Error(`搜索失败: ${error.message}`);
	}
}
/*}#1IUIO756A0StartDoc*/
//----------------------------------------------------------------------------
let ToolRunCommand=async function(session){
	let command,repo;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Run,CheckSuccess,Check,Fix,Action,RunCommand,RunSearch,CheckFinish,Fail,GetPath,BackPath,Success,Issues,SearchIssues,Search;
	/*#{1IUIO756A0LocalVals*/
	let current_output, output, current_path, issue, search_result;
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
			{role:"system",content:"你是一个终端命令的分析助手。当接收到终端运行的命令和输出时，你需要判断命令是否执行成功。根据命令的输出判断其成功或失败，并以JSON格式输出结果。输出的JSON格式为：{'success': true/false}，其中 'true' 表示命令执行成功，'false' 表示命令执行失败。你只需要根据输出的信息判断命令是否成功，无需进一步的解释。"},
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
		let chatMem=Fix.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`你是一个命令行问题修复专家。你正在尝试运行一个命令但遇到了错误，具体是 ${current_output}。输入是当前执行的终端命令及其输出或者是通过上网搜索得出的结果，你需要根据错误信息分析问题并尝试修复。
你在google中查找到了相关报错内容，相关的问题和解决方案
如下：${search_result}
你可以通过以下几种方式进行修复：\n\n1. 通过自身思考，分析错误原因并尝试给出新的命令或解决方案，以json格式输出。每次只能执行一个命令，输出格式为 {\"action\": \"command\", \"content\": \"<命令>\"}。你允许读取、写入、修改文件内容。\n2. 如果你无法通过思考解决问题，可以执行其他命令来获取更多的上下文信息，如阅读相关的文件或日志。\n3. 如果多次尝试失败且仍无法解决问题，你可以通过上网搜索寻找解决方案，搜索内容要符合搜索的风格，输出格式为 {\"action\": \"search\", \"content\": \"<搜索内容>\"}，但是请注意，只有在尝试自身思考多次无果后才执行搜索。\n\n请注意，每次尝试之后，你必须基于新的信息继续思考或修复，确保你在执行搜索之前已经尽力排查和解决问题。每次只能执行一次命令或一次搜索。\n4. 如果修复成功，输出 {\"action\": \"finish\", \"content\": \success\", \"summary\": \"<所有用于有效修复问题的命令>\"}。\n5. 如果多次尝试之后仍然失败，无法完成初始命令的目标，请输出 {\"action\": \"finish\", \"content\": \fail\"}，注意一定要经过多次尝试后均失败才算失败。。`

},
		];
		messages.push(...chatMem);
		prompt=output;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("Fix@"+agentURL,opts,messages,true);
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
		}
		result=trimJSON(result);
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
		return {seg:Fix,result:(result),preSeg:"1IUIQ96PT0",outlet:"1IUIQJ48H2"};
	};
	RunCommand.jaxId="1IUIQ96PT0"
	RunCommand.url="RunCommand@"+agentURL
	
	segs["RunSearch"]=RunSearch=async function(input){//:1IUIQA1360
		let result,args={};
		args['nodeName']="DeepSearch";
		args['callAgent']="agent.js";
		args['callArg']={question:input.content, save:false};
		args['checkUpdate']=true;
		args['options']="";
		/*#{1IUIQA1360PreCodes*/
		/*}#1IUIQA1360PreCodes*/
		result= await session.pipeChat("/@tabos/RemoteChat.mjs",args,false);
		/*#{1IUIQA1360PostCodes*/
		output=result;
		/*}#1IUIQA1360PostCodes*/
		return {seg:Fix,result:(result),preSeg:"1IUIQA1360",outlet:"1IUIQJ48H3"};
	};
	RunSearch.jaxId="1IUIQA1360"
	RunSearch.url="RunSearch@"+agentURL
	
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
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="无法修复问题";
		session.addChatText(role,content,opts);
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
		result=`执行 ${command} 失败，错误为 ${issue}，修复流程：${input.summary}`;
		/*}#1IVIPCBLH0PostCodes*/
		return {result:result};
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
		let chatMem=Issues.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`你是一个github项目部署专家，正在部署的项目是 ${repo}，在尝试运行一个命令但遇到了错误，希望在google中查找解决方案，请根据错误给出适合在google里搜索的内容，包含项目名称，以JSON格式返回，如 {"search_content":"github ${repo} huggingface-cli command not found."}。`},
		];
		prompt=current_output;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("Issues@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:Search,result:(result),preSeg:"1J08OTLLI0",outlet:"1J08P3QKK0"};
	};
	Issues.jaxId="1J08OTLLI0"
	Issues.url="Issues@"+agentURL
	
	segs["SearchIssues"]=SearchIssues=async function(input){//:1J08P4F0T0
		let result=input
		/*#{1J08P4F0T0Code*/
		result=await searchBugIssues(input.search_content, repo);
		/*}#1J08P4F0T0Code*/
		return {result:result};
	};
	SearchIssues.jaxId="1J08P4F0T0"
	SearchIssues.url="SearchIssues@"+agentURL
	
	segs["Search"]=Search=async function(input){//:1J08RJJUS0
		let result,args={};
		args['nodeName']="DeepSearch";
		args['callAgent']="agent.js";
		args['callArg']={question:input.search_content, save:false};
		args['checkUpdate']=true;
		args['options']="";
		/*#{1J08RJJUS0PreCodes*/
		/*}#1J08RJJUS0PreCodes*/
		result= await session.pipeChat("/@tabos/RemoteChat.mjs",args,false);
		/*#{1J08RJJUS0PostCodes*/
		search_result=result;
		/*}#1J08RJJUS0PostCodes*/
		return {seg:Fix,result:(result),preSeg:"1J08RJJUS0",outlet:"1J08RKAV40"};
	};
	Search.jaxId="1J08RJJUS0"
	Search.url="Search@"+agentURL
	
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
				command:{type:"string",description:"A bash command"},
				repo:{type:"auto",description:""}
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
		name:"ToolRunCommand",showName:"ToolRunCommand",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"command":{name:"command",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
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
			coder.packText(`result= await session.pipeChat("/~/builder_new/ai/ToolRunCommand.js",args,false);`);coder.newLine();
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
//						"type": "String",
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
//						"system": "你是一个终端命令的分析助手。当接收到终端运行的命令和输出时，你需要判断命令是否执行成功。根据命令的输出判断其成功或失败，并以JSON格式输出结果。输出的JSON格式为：{'success': true/false}，其中 'true' 表示命令执行成功，'false' 表示命令执行失败。你只需要根据输出的信息判断命令是否成功，无需进一步的解释。",
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
//						"x": "1680",
//						"y": "175",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
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
//						"system": "#`你是一个命令行问题修复专家。你正在尝试运行一个命令但遇到了错误，具体是 ${current_output}。输入是当前执行的终端命令及其输出或者是通过上网搜索得出的结果，你需要根据错误信息分析问题并尝试修复。\n你在google中查找到了相关报错内容，相关的问题和解决方案\n如下：${search_result}\n你可以通过以下几种方式进行修复：\\n\\n1. 通过自身思考，分析错误原因并尝试给出新的命令或解决方案，以json格式输出。每次只能执行一个命令，输出格式为 {\\\"action\\\": \\\"command\\\", \\\"content\\\": \\\"<命令>\\\"}。你允许读取、写入、修改文件内容。\\n2. 如果你无法通过思考解决问题，可以执行其他命令来获取更多的上下文信息，如阅读相关的文件或日志。\\n3. 如果多次尝试失败且仍无法解决问题，你可以通过上网搜索寻找解决方案，搜索内容要符合搜索的风格，输出格式为 {\\\"action\\\": \\\"search\\\", \\\"content\\\": \\\"<搜索内容>\\\"}，但是请注意，只有在尝试自身思考多次无果后才执行搜索。\\n\\n请注意，每次尝试之后，你必须基于新的信息继续思考或修复，确保你在执行搜索之前已经尽力排查和解决问题。每次只能执行一次命令或一次搜索。\\n4. 如果修复成功，输出 {\\\"action\\\": \\\"finish\\\", \\\"content\\\": \\success\\\", \\\"summary\\\": \\\"<所有用于有效修复问题的命令>\\\"}。\\n5. 如果多次尝试之后仍然失败，无法完成初始命令的目标，请输出 {\\\"action\\\": \\\"finish\\\", \\\"content\\\": \\fail\\\"}，注意一定要经过多次尝试后均失败才算失败。。`\n\n",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#output",
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
//						"x": "1880",
//						"y": "175",
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
//									"linkedSeg": "1IUIQA1360"
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
//						"x": "2085",
//						"y": "65",
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
//					"def": "RemoteChat",
//					"jaxId": "1IUIQA1360",
//					"attrs": {
//						"id": "RunSearch",
//						"viewName": "",
//						"label": "",
//						"x": "2085",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIQJ48L8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIQJ48L9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "DeepSearch",
//						"callAgent": "agent.js",
//						"callArg": "#{question:input.content, save:false}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IUIQJ48H3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIR79BQ0"
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IUIQOIRV0",
//					"attrs": {
//						"id": "CheckFinish",
//						"viewName": "",
//						"label": "",
//						"x": "2085",
//						"y": "280",
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
//						"x": "2325",
//						"y": "295",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
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
//						"x": "2255",
//						"y": "-15",
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
//						"x": "1820",
//						"y": "-15",
//						"outlet": {
//							"jaxId": "1IUIQTDO71",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIPQ6810"
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
//						"x": "2380",
//						"y": "-15",
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
//						"x": "2470",
//						"y": "160",
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
//						"x": "1010",
//						"y": "175",
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
//						"x": "2325",
//						"y": "215",
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
//							}
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
//						"y": "5",
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
//						"x": "1215",
//						"y": "175",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
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
//							"linkedSeg": "1J08RJJUS0"
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
//					"jaxId": "1J08P4F0T0",
//					"attrs": {
//						"id": "SearchIssues",
//						"viewName": "",
//						"label": "",
//						"x": "1405",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J08P5MTU0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J08P5MTU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J08P4NRS0",
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
//					"def": "RemoteChat",
//					"jaxId": "1J08RJJUS0",
//					"attrs": {
//						"id": "Search",
//						"viewName": "",
//						"label": "",
//						"x": "1425",
//						"y": "175",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J08RKAV80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J08RKAV81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "DeepSearch",
//						"callAgent": "agent.js",
//						"callArg": "#{question:input.search_content, save:false}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J08RKAV40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IUIPQ6810"
//						}
//					},
//					"icon": "cloudact.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}