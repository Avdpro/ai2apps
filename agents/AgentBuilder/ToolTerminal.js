//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1INO3K4QR0MoreImports*/
/*}#1INO3K4QR0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"task":{
			"name":"task","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"用户的任务要求",
		}
	},
	/*#{1INO3K4QR0ArgsView*/
	/*}#1INO3K4QR0ArgsView*/
};

/*#{1INO3K4QR0StartDoc*/
/*}#1INO3K4QR0StartDoc*/
//----------------------------------------------------------------------------
let ToolTerminal=async function(session){
	let task;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let InitBash,Loop,LLM,Run,output,FixArgs,Check,Read,Error,Finish,Summary,Write,Ask,Summ,Search;
	/*#{1INO3K4QR0LocalVals*/
	let previous_result = [], current_step;
	/*}#1INO3K4QR0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			task=input.task;
		}else{
			task=undefined;
		}
		/*#{1INO3K4QR0ParseArgs*/
		/*}#1INO3K4QR0ParseArgs*/
	}
	
	/*#{1INO3K4QR0PreContext*/
	/*}#1INO3K4QR0PreContext*/
	context={};
	/*#{1INO3K4QR0PostContext*/
	/*}#1INO3K4QR0PostContext*/
	let agent,segs={};
	segs["InitBash"]=InitBash=async function(input){//:1INO3NBBG0
		let result,args={};
		args['bashId']="";
		args['action']="Create";
		args['commands']="";
		args['options']={client:true};
		/*#{1INO3NBBG0PreCodes*/
		/*}#1INO3NBBG0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1INO3NBBG0PostCodes*/
		globalContext.bash = result;
		/*}#1INO3NBBG0PostCodes*/
		return {seg:Loop,result:(result),preSeg:"1INO3NBBG0",outlet:"1INO3NPJJ0"};
	};
	InitBash.jaxId="1INO3NBBG0"
	InitBash.url="InitBash@"+agentURL
	
	segs["Loop"]=Loop=async function(input){//:1INO5FHK90
		let result=input;
		let list=input;
		let i,n,item,loopR;
		/*#{1INO5FHK90PreLoop*/
		list = new Array(1000).fill(0);
		/*}#1INO5FHK90PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1INO5FHK90InLoopPre*/
			/*}#1INO5FHK90InLoopPre*/
			loopR=await session.runAISeg(agent,LLM,item,"1INO5FHK90","1INO5GDAL0")
			if(loopR==="break"){
				break;
			}
			/*#{1INO5FHK90InLoopPost*/
			/*}#1INO5FHK90InLoopPost*/
		}
		/*#{1INO5FHK90PostCodes*/
		/*}#1INO5FHK90PostCodes*/
		return {result:result};
	};
	Loop.jaxId="1INO5FHK90"
	Loop.url="Loop@"+agentURL
	
	segs["LLM"]=LLM=async function(input){//:1INO5G4SU0
		let prompt;
		let result=null;
		/*#{1INO5G4SU0Input*/
		/*}#1INO5G4SU0Input*/
		
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
		let chatMem=LLM.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你是一个命令行助手，你的职责是根据任务描述和之前的命令运行结果，生成下一步需要执行的操作。你的回答必须严格遵循以下要求：\n1. 输出格式必须为 JSON，对象中包含两个必需键：\n   - \"Tool\": 表示使用的工具，必须是以下值之一：[\"bash\", \"readFile\", \"writeFile\", \"askUser\", \"search\"]\n   - \"Parameters\": 包含具体操作参数的字典，其结构根据工具类型而定：\n     * 当 Tool=\"bash\" 时，Parameters 必须包含 \"command\" 键，其值为要执行的终端命令\n     * 当 Tool=\"readFile\" 时，Parameters 必须包含 \"filePath\" 键，其值为要读取的文件路径，支持pdf，doc，docx以及其他文本文档。\n     * 当 Tool=\"writeFile\" 时，Parameters 必须包含 \"filePath\" 和 \"content\" 键，分别表示文件路径和要写入的内容\n     * 当 Tool=\"askUser\" 时，Parameters 必须包含 \"content\" 参数表示问用户的问题\n     * 当 Tool=\"search\" 时，Parameters 必须包含 \"content\" 参数表示需要上网搜索的内容。\n2. 如果任务失败或者不可能继续完成任务时，请在返回的 JSON 对象中添加一个键 \"Error\"，其值为失败或者无法决策的原因。\n3. 如果任务已经完成，请在返回的 JSON 对象中添加一个键 \"Finished\"，其值为\"Yes\"。\n4. 不要输出任何额外的解释、提示或说明，确保返回结果可以直接被程序解析执行。\n4. 请确保生成的操作能够有效地推进任务，并符合任务要求。\n5. 请确保所有的filePath为绝对路径，如果不知道当前路径，可以使用pwd命令查看，并且路径中文件夹或者文件名含有空格时请用引号。\n6. 读取文件readFile前请先用命令确保文件路径存在。\n7. 如果你有任何不了解的问题时，可以调用search工具。\n请仅返回符合要求的 JSON 格式响应。"},
		];
		/*#{1INO5G4SU0PrePrompt*/
		/*}#1INO5G4SU0PrePrompt*/
		prompt=`你的任务是 ${task}。
之前的运行命令及结果如下：
${JSON.stringify(previous_result)}。

请分析当前任务状态，并以严格JSON格式提供下一步操作，包含：
- "Tool"（必填）："bash"|"readFile"|"writeFile"|"askUser"|"search"
- "Parameters"（必填）：根据工具类型包含对应参数
若任务失败或者不可能继续完成任务则添加"Error"键,值表示原因。
若任务已经完成则添加"Finished"键,值为"Yes"。
输出示例：
{"Tool":"bash","Parameters":{"command":"ls -l"}}
{"Tool":"readFile","Parameters":{"filePath":"/path/to/file"}}
{"Tool":"writeFile","Parameters":{"content":"hello world","filePath":"/path/to/file"}}
{"Tool":"askUser","Parameters":{"content":"Which type of file do you want to save to, pdf, ppt or md?"}}
{"Tool":"search","Parameters":{"content":"Recent news on AI"}}
{"Error":"失败原因"}
{"Finished":"Yes"}

必须严格输出纯JSON，无任何额外文本。
注意：如果不存在无法解决的问题，请不要添加Error，尽量尝试解决。
5. 请确保所有的filePath为绝对路径，如果不知道当前路径，可以使用pwd命令查看，并且路径中文件夹或者文件名含有空格时请用引号。`;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1INO5G4SU0FilterMessage*/
			/*}#1INO5G4SU0FilterMessage*/
			messages.push(msg);
		}
		/*#{1INO5G4SU0PreCall*/
		/*}#1INO5G4SU0PreCall*/
		result=(result===null)?(await session.callSegLLM("LLM@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1INO5G4SU0PostCall*/
		/*}#1INO5G4SU0PostCall*/
		return {seg:Check,result:(result),preSeg:"1INO5G4SU0",outlet:"1INO5GDAM1"};
	};
	LLM.jaxId="1INO5G4SU0"
	LLM.url="LLM@"+agentURL
	
	segs["Run"]=Run=async function(input){//:1INO5R1SK0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=input.Parameters.command;
		args['options']="";
		/*#{1INO5R1SK0PreCodes*/
		
				/*}#1INO5R1SK0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1INO5R1SK0PostCodes*/
		current_step = {
		Tool: input.Tool,
		Parameters: JSON.stringify(input.Parameters),
		Result: result
		};
		previous_result.push({
		Tool: input.Tool,
		Parameters: JSON.stringify(input.Parameters),
		Result: result
		});
		/*}#1INO5R1SK0PostCodes*/
		return {seg:output,result:(result),preSeg:"1INO5R1SK0",outlet:"1INO5RMJ90"};
	};
	Run.jaxId="1INO5R1SK0"
	Run.url="Run@"+agentURL
	
	segs["output"]=output=async function(input){//:1INO5REUS0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {result:result};
	};
	output.jaxId="1INO5REUS0"
	output.url="output@"+agentURL
	
	segs["FixArgs"]=FixArgs=async function(input){//:1INO5SFIV0
		let result=input;
		let missing=false;
		if(task===undefined || task==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:InitBash,result:(result),preSeg:"1INO5SFIV0",outlet:"1INO5UVKN0"};
	};
	FixArgs.jaxId="1INO5SFIV0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1INQN0FVG0
		let result=input;
		if(input.Tool === "bash"){
			return {seg:Run,result:(input),preSeg:"1INQN0FVG0",outlet:"1INQN65O70"};
		}
		if(input.Tool === "readFile"){
			return {seg:Read,result:(input),preSeg:"1INQN0FVG0",outlet:"1INQN0M8P0"};
		}
		if(input.Tool === "writeFile"){
			return {seg:Write,result:(input),preSeg:"1INQN0FVG0",outlet:"1INQN0NFA0"};
		}
		if(input.Finished === "Yes"){
			return {seg:Summary,result:(input),preSeg:"1INQN0FVG0",outlet:"1INQP1OOT0"};
		}
		if(input.Tool === "askUser"){
			return {seg:Ask,result:(input),preSeg:"1INQN0FVG0",outlet:"1INSPDKMD0"};
		}
		if(input.Tool === "search"){
			return {seg:Search,result:(input),preSeg:"1INQN0FVG0",outlet:"1INSRFIT00"};
		}
		return {seg:Error,result:(result),preSeg:"1INQN0FVG0",outlet:"1INQN65O80"};
	};
	Check.jaxId="1INQN0FVG0"
	Check.url="Check@"+agentURL
	
	segs["Read"]=Read=async function(input){//:1INQN3QAG0
		let result,args={};
		args['nodeName']="builder_new";
		args['callAgent']="ToolReadFile.js";
		args['callArg']={filePath:input.Parameters.filePath};
		args['checkUpdate']=true;
		/*#{1INQN3QAG0PreCodes*/
		/*}#1INQN3QAG0PreCodes*/
		result= await session.pipeChat("/@tabos/RemoteChat.mjs",args,false);
		/*#{1INQN3QAG0PostCodes*/
		current_step = {
		Tool: input.Tool,
		Parameters: JSON.stringify(input.Parameters),
		Result: result
		};
		previous_result.push({
		Tool: input.Tool,
		Parameters: JSON.stringify(input.Parameters),
		Result: result
		});
		/*}#1INQN3QAG0PostCodes*/
		return {seg:output,result:(result),preSeg:"1INQN3QAG0",outlet:"1INQN65O81"};
	};
	Read.jaxId="1INQN3QAG0"
	Read.url="Read@"+agentURL
	
	segs["Error"]=Error=async function(input){//:1INQNAOKR0
		let result=input;
		let opts={};
		let role="assistant";
		let content=`错误：${input.Error}`;
		/*#{1INQNAOKR0PreCodes*/
		/*}#1INQNAOKR0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1INQNAOKR0PostCodes*/
		result="break";
		/*}#1INQNAOKR0PostCodes*/
		return {result:result};
	};
	Error.jaxId="1INQNAOKR0"
	Error.url="Error@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1INQP36U90
		let result=input;
		let opts={};
		let role="assistant";
		let content=`任务已经完成\n ${input}`;
		/*#{1INQP36U90PreCodes*/
		/*}#1INQP36U90PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1INQP36U90PostCodes*/
		result="break";
		/*}#1INQP36U90PostCodes*/
		return {result:result};
	};
	Finish.jaxId="1INQP36U90"
	Finish.url="Finish@"+agentURL
	
	segs["Summary"]=Summary=async function(input){//:1INQP69PI0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=Summary.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		prompt=`你的任务是 ${task}。
之前的运行命令及结果如下：
${JSON.stringify(previous_result)}。
请总结一下任务的结果，以markdown格式呈现。`;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("Summary@"+agentURL,opts,messages,true);
		return {seg:Finish,result:(result),preSeg:"1INQP69PI0",outlet:"1INQP8VP90"};
	};
	Summary.jaxId="1INQP69PI0"
	Summary.url="Summary@"+agentURL
	
	segs["Write"]=Write=async function(input){//:1INQRPVAI0
		let result,args={};
		args['nodeName']="builder_new";
		args['callAgent']="ToolWriteFile.js";
		args['callArg']={content:input.Parameters.content,filePath:input.Parameters.filePath};
		args['checkUpdate']=true;
		/*#{1INQRPVAI0PreCodes*/
		/*}#1INQRPVAI0PreCodes*/
		result= await session.pipeChat("/@tabos/RemoteChat.mjs",args,false);
		/*#{1INQRPVAI0PostCodes*/
		previous_result.push({
		Tool: input.Tool,
		Parameters: JSON.stringify(input.Parameters),
		Result: "Success"
		});
		/*}#1INQRPVAI0PostCodes*/
		return {result:result};
	};
	Write.jaxId="1INQRPVAI0"
	Write.url="Write@"+agentURL
	
	segs["Ask"]=Ask=async function(input){//:1INSPC1DG0
		let result,args={};
		args['nodeName']="builder_new";
		args['callAgent']="SysTabOSAskUser.js";
		args['callArg']=input.Parameters.content;
		args['checkUpdate']=true;
		/*#{1INSPC1DG0PreCodes*/
		/*}#1INSPC1DG0PreCodes*/
		result= await session.pipeChat("/@tabos/RemoteChat.mjs",args,false);
		/*#{1INSPC1DG0PostCodes*/
		previous_result.push({
		Tool: input.Tool,
		Parameters: JSON.stringify(input.Parameters),
		Result: result
		});
		/*}#1INSPC1DG0PostCodes*/
		return {result:result};
	};
	Ask.jaxId="1INSPC1DG0"
	Ask.url="Ask@"+agentURL
	
	segs["Summ"]=Summ=async function(input){//:1INSPHI340
		let prompt;
		let result=null;
		/*#{1INSPHI340Input*/
		/*}#1INSPHI340Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=Summ.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`你的任务是 ${task}。当前步骤是 ${JSON.stringify(current_step)}，请总结和任务相关以及工具使用结果相关的内容替换Result，要求尽可能简洁清晰，必须包含所有相关内容，直接输出总结后的内容。
如果是当前步骤使用命令行，并且命令只与成功或失败有关，直接输出Success或者Failed。
`},
		];
		/*#{1INSPHI340PrePrompt*/
		/*}#1INSPHI340PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1INSPHI340FilterMessage*/
			/*}#1INSPHI340FilterMessage*/
			messages.push(msg);
		}
		/*#{1INSPHI340PreCall*/
		/*}#1INSPHI340PreCall*/
		result=(result===null)?(await session.callSegLLM("Summ@"+agentURL,opts,messages,true)):result;
		/*#{1INSPHI340PostCall*/
		current_step.Result = result;
		previous_result.push(current_step);
		/*}#1INSPHI340PostCall*/
		return {result:result};
	};
	Summ.jaxId="1INSPHI340"
	Summ.url="Summ@"+agentURL
	
	segs["Search"]=Search=async function(input){//:1INSRGNO80
		let result,args={};
		args['nodeName']="builder_new";
		args['callAgent']="RpaWebSearch.js";
		args['callArg']={search:input.Parameters.content,top_k:3};
		args['checkUpdate']=true;
		/*#{1INSRGNO80PreCodes*/
		/*}#1INSRGNO80PreCodes*/
		result= await session.pipeChat("/@tabos/RemoteChat.mjs",args,false);
		/*#{1INSRGNO80PostCodes*/
		previous_result.push({
		Tool: input.Tool,
		Parameters: JSON.stringify(input.Parameters),
		Result: result
		});
		/*}#1INSRGNO80PostCodes*/
		return {result:result};
	};
	Search.jaxId="1INSRGNO80"
	Search.url="Search@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolTerminal",
		url:agentURL,
		autoStart:true,
		jaxId:"1INO3K4QR0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{task}*/){
			let result;
			parseAgentArgs(input);
			/*#{1INO3K4QR0PreEntry*/
			/*}#1INO3K4QR0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1INO3K4QR0PostEntry*/
			/*}#1INO3K4QR0PostEntry*/
			return result;
		},
		/*#{1INO3K4QR0MoreAgentAttrs*/
		/*}#1INO3K4QR0MoreAgentAttrs*/
	};
	/*#{1INO3K4QR0PostAgent*/
	/*}#1INO3K4QR0PostAgent*/
	return agent;
};
/*#{1INO3K4QR0ExCodes*/
/*}#1INO3K4QR0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1INO3K4QR0PostDoc*/
/*}#1INO3K4QR0PostDoc*/


export default ToolTerminal;
export{ToolTerminal};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1INO3K4QR0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1INO3K4QT0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1INO3K4QT1",
//			"attrs": {}
//		},
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1INO3K4QT2",
//			"attrs": {
//				"task": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1INO5UVKS0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "用户的任务要求",
//						"required": "true"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1INO3K4QT3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1INO3K4QT4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1INO3K4QT5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1INO3NBBG0",
//					"attrs": {
//						"id": "InitBash",
//						"viewName": "",
//						"label": "",
//						"x": "200",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INO3NPJK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INO3NPJK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "\"\"",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client:true}",
//						"outlet": {
//							"jaxId": "1INO3NPJJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INO5FHK90"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1INO5FHK90",
//					"attrs": {
//						"id": "Loop",
//						"viewName": "",
//						"label": "",
//						"x": "440",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INO5GDAN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INO5GDAN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1INO5GDAL0",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INO5G4SU0"
//						},
//						"catchlet": {
//							"jaxId": "1INO5GDAM0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1INO5G4SU0",
//					"attrs": {
//						"id": "LLM",
//						"viewName": "",
//						"label": "",
//						"x": "635",
//						"y": "85",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INO5GDAN2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INO5GDAN3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "你是一个命令行助手，你的职责是根据任务描述和之前的命令运行结果，生成下一步需要执行的操作。你的回答必须严格遵循以下要求：\n1. 输出格式必须为 JSON，对象中包含两个必需键：\n   - \"Tool\": 表示使用的工具，必须是以下值之一：[\"bash\", \"readFile\", \"writeFile\", \"askUser\", \"search\"]\n   - \"Parameters\": 包含具体操作参数的字典，其结构根据工具类型而定：\n     * 当 Tool=\"bash\" 时，Parameters 必须包含 \"command\" 键，其值为要执行的终端命令\n     * 当 Tool=\"readFile\" 时，Parameters 必须包含 \"filePath\" 键，其值为要读取的文件路径，支持pdf，doc，docx以及其他文本文档。\n     * 当 Tool=\"writeFile\" 时，Parameters 必须包含 \"filePath\" 和 \"content\" 键，分别表示文件路径和要写入的内容\n     * 当 Tool=\"askUser\" 时，Parameters 必须包含 \"content\" 参数表示问用户的问题\n     * 当 Tool=\"search\" 时，Parameters 必须包含 \"content\" 参数表示需要上网搜索的内容。\n2. 如果任务失败或者不可能继续完成任务时，请在返回的 JSON 对象中添加一个键 \"Error\"，其值为失败或者无法决策的原因。\n3. 如果任务已经完成，请在返回的 JSON 对象中添加一个键 \"Finished\"，其值为\"Yes\"。\n4. 不要输出任何额外的解释、提示或说明，确保返回结果可以直接被程序解析执行。\n4. 请确保生成的操作能够有效地推进任务，并符合任务要求。\n5. 请确保所有的filePath为绝对路径，如果不知道当前路径，可以使用pwd命令查看，并且路径中文件夹或者文件名含有空格时请用引号。\n6. 读取文件readFile前请先用命令确保文件路径存在。\n7. 如果你有任何不了解的问题时，可以调用search工具。\n请仅返回符合要求的 JSON 格式响应。",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#`你的任务是 ${task}。\n之前的运行命令及结果如下：\n${JSON.stringify(previous_result)}。\n\n请分析当前任务状态，并以严格JSON格式提供下一步操作，包含：\n- \"Tool\"（必填）：\"bash\"|\"readFile\"|\"writeFile\"|\"askUser\"|\"search\"\n- \"Parameters\"（必填）：根据工具类型包含对应参数\n若任务失败或者不可能继续完成任务则添加\"Error\"键,值表示原因。\n若任务已经完成则添加\"Finished\"键,值为\"Yes\"。\n输出示例：\n{\"Tool\":\"bash\",\"Parameters\":{\"command\":\"ls -l\"}}\n{\"Tool\":\"readFile\",\"Parameters\":{\"filePath\":\"/path/to/file\"}}\n{\"Tool\":\"writeFile\",\"Parameters\":{\"content\":\"hello world\",\"filePath\":\"/path/to/file\"}}\n{\"Tool\":\"askUser\",\"Parameters\":{\"content\":\"Which type of file do you want to save to, pdf, ppt or md?\"}}\n{\"Tool\":\"search\",\"Parameters\":{\"content\":\"Recent news on AI\"}}\n{\"Error\":\"失败原因\"}\n{\"Finished\":\"Yes\"}\n\n必须严格输出纯JSON，无任何额外文本。\n注意：如果不存在无法解决的问题，请不要添加Error，尽量尝试解决。\n5. 请确保所有的filePath为绝对路径，如果不知道当前路径，可以使用pwd命令查看，并且路径中文件夹或者文件名含有空格时请用引号。`",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1INO5GDAM1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INQN0FVG0"
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
//					"def": "Bash",
//					"jaxId": "1INO5R1SK0",
//					"attrs": {
//						"id": "Run",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "-70",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INO5RMJE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INO5RMJE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#input.Parameters.command",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1INO5RMJ90",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INO5REUS0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1INO5REUS0",
//					"attrs": {
//						"id": "output",
//						"viewName": "",
//						"label": "",
//						"x": "1415",
//						"y": "-70",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INO5RMJE2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INO5RMJE3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1INO5RMJ91",
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
//					"def": "fixArgs",
//					"jaxId": "1INO5SFIV0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "-10",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1INO5UVKN0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INO3NBBG0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1INQN0FVG0",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "810",
//						"y": "85",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQN9SD70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQN9SD71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INQN65O80",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INQNAOKR0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INQN65O70",
//									"attrs": {
//										"id": "Bash",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INQN9SD72",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INQN9SD73",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.Tool === \"bash\""
//									},
//									"linkedSeg": "1INO5R1SK0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INQN0M8P0",
//									"attrs": {
//										"id": "ReadFile",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INQN9SD74",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INQN9SD75",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.Tool === \"readFile\""
//									},
//									"linkedSeg": "1INQN3QAG0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INQN0NFA0",
//									"attrs": {
//										"id": "writeFile",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INQN9SD76",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INQN9SD77",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.Tool === \"writeFile\""
//									},
//									"linkedSeg": "1INQRPVAI0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INQP1OOT0",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INQP5N4H0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INQP5N4H1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.Finished === \"Yes\""
//									},
//									"linkedSeg": "1INQP69PI0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INSPDKMD0",
//									"attrs": {
//										"id": "AskUser",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INSPEQE10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INSPEQE11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.Tool === \"askUser\""
//									},
//									"linkedSeg": "1INSPC1DG0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INSRFIT00",
//									"attrs": {
//										"id": "Search",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INSRFIT80",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INSRFIT81",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.Tool === \"search\""
//									},
//									"linkedSeg": "1INSRGNO80"
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
//					"jaxId": "1INQN3QAG0",
//					"attrs": {
//						"id": "Read",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "10",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQN9SD78",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQN9SD79",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "builder_new",
//						"callAgent": "ToolReadFile.js",
//						"callArg": "#{filePath:input.Parameters.filePath}",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1INQN65O81",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INO5REUS0"
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1INQNAOKR0",
//					"attrs": {
//						"id": "Error",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQNBI890",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQNBI891",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`错误：${input.Error}`",
//						"outlet": {
//							"jaxId": "1INQNBI820",
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
//					"def": "output",
//					"jaxId": "1INQP36U90",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQP5N4H2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQP5N4H3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`任务已经完成\\n ${input}`",
//						"outlet": {
//							"jaxId": "1INQP4BLN0",
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
//					"jaxId": "1INQP69PI0",
//					"attrs": {
//						"id": "Summary",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "160",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQP8VPI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQP8VPI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "You are a smart assistant.",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#`你的任务是 ${task}。\n之前的运行命令及结果如下：\n${JSON.stringify(previous_result)}。\n请总结一下任务的结果，以markdown格式呈现。`",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1INQP8VP90",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INQP36U90"
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
//					"def": "RemoteChat",
//					"jaxId": "1INQRPVAI0",
//					"attrs": {
//						"id": "Write",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "85",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INQS48GH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INQS48GH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "builder_new",
//						"callAgent": "ToolWriteFile.js",
//						"callArg": "#{content:input.Parameters.content,filePath:input.Parameters.filePath}",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1INQS48GC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1INSPC1DG0",
//					"attrs": {
//						"id": "Ask",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INSPEQE12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INSPEQE13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "builder_new",
//						"callAgent": "SysTabOSAskUser.js",
//						"callArg": "#input.Parameters.content",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1INSPDKMD1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1INSPHI340",
//					"attrs": {
//						"id": "Summ",
//						"viewName": "",
//						"label": "",
//						"x": "1240",
//						"y": "-310",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INSQ1NDQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INSQ1NDQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`你的任务是 ${task}。当前步骤是 ${JSON.stringify(current_step)}，请总结和任务相关以及工具使用结果相关的内容替换Result，要求尽可能简洁清晰，必须包含所有相关内容，直接输出总结后的内容。\n如果是当前步骤使用命令行，并且命令只与成功或失败有关，直接输出Success或者Failed。\n`",
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
//							"jaxId": "1INSPO5DP0",
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
//						"responseFormat": "text",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1INSRGNO80",
//					"attrs": {
//						"id": "Search",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INSRK9Q00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INSRK9Q01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "builder_new",
//						"callAgent": "RpaWebSearch.js",
//						"callArg": "#{search:input.Parameters.content,top_k:3}",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1INSRK9PN0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
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