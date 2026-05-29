//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1JGP1AAKD0MoreImports*/
import fsp from 'fs/promises';
import yaml from 'js-yaml';
import os from 'os';
import { runAgenticTask } from '../../agenthub/NativeAgenticLoop.mjs';
import { getAllTools } from '../../agenthub/NativeTools.mjs';
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
		},
		"task":{
			"name":"task","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JGP1AAKD0ArgsView*/
	/*}#1JGP1AAKD0ArgsView*/
};

/*#{1JGP1AAKD0StartDoc*/
async function isTextFile(filePath) {
	let fileHandle = null;
	
	try {
		fileHandle = await fsp.open(filePath, 'r');
		const bufferSize = 1024;
		const buffer = Buffer.alloc(bufferSize);
		const result = await fileHandle.read(buffer, 0, bufferSize, 0);
		const content = buffer.slice(0, result.bytesRead);
		if (content.includes(0)) {
			return false;
		}
		return true;
	} catch (err) {
		console.error(`检查文件失败: ${filePath}`, err);
		throw err; 
	} finally {
		if (fileHandle) {
			await fileHandle.close();
		}
	}
}
/*}#1JGP1AAKD0StartDoc*/
//----------------------------------------------------------------------------
let ModelAgentTest=async function(session){
	let model,task;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Welcome,InitBash,Enter,InitBash2,Enter2,Check,Ask,Run;
	/*#{1JGP1AAKD0LocalVals*/
	let query="", config, skill, base_command;
	const KEY = process.env.MODELHUNT_PUBLIC_KEY;
	/*}#1JGP1AAKD0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
			task=input.task;
		}else{
			model=undefined;
			task=undefined;
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
		if(task===undefined || task==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		/*#{1JGP1KHU70PostCodes*/
		const apiUrl = process.env.MODELHUNT_API_URL;
		const modelUsageUrl = `${apiUrl.replace(/\/$/, '')}/api/public/v1/models/${model}/usage`;
		
		try {
			const response = await fetch(modelUsageUrl, {
				method: 'GET',
				headers: {
					'accept': 'application/json',
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${KEY}`
				}
			});
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
			if (config.global_execution.base_command) base_command=config.global_execution.base_command;
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
		result=task;
		/*}#1JGP1TLH70PostCodes*/
		return {seg:Ask,result:(result),preSeg:"1JGP1TLH70",outlet:"1JGP1TRNS0"};
	};
	Welcome.jaxId="1JGP1TLH70"
	Welcome.url="Welcome@"+agentURL
	
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
		globalContext.bash1=result;
		/*}#1JGP3RVH10PostCodes*/
		return {seg:Enter,result:(result),preSeg:"1JGP3RVH10",outlet:"1JGP3SQ0T1"};
	};
	InitBash.jaxId="1JGP3RVH10"
	InitBash.url="InitBash@"+agentURL
	
	segs["Enter"]=Enter=async function(input){//:1JGP4II6C0
		let result,args={};
		args['bashId']=globalContext.bash1;
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
		if(base_command){
			return {seg:InitBash2,result:(input),preSeg:"1JH7SQRPI0",outlet:"1JH7SRM9M0"};
		}
		return {seg:Welcome,result:(result),preSeg:"1JH7SQRPI0",outlet:"1JH7SR6CU0"};
	};
	Check.jaxId="1JH7SQRPI0"
	Check.url="Check@"+agentURL
	
	segs["Ask"]=Ask=async function(input){//:1JPMPHQ890
		let tip=("");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(true)||false;
		let allowEmpty=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		/*#{1JPMPHQ890PreCodes*/
		/*}#1JPMPHQ890PreCodes*/
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
		/*#{1JPMPHQ890PostCodes*/
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
			if($ln==="CN") query = `用户要求：${userRequest}\n上传的文件：\n${fileList.map((f, idx) => `${idx + 1}. ${f}`).join('\n')}`;
			else query = `User Query：${userRequest}\nUploaded Files：\n${fileList.map((f, idx) => `${idx + 1}. ${f}`).join('\n')}`;
		} else if(typeof(result) === 'string') {
			userRequest = result;
			if($ln==="CN") query = `用户要求：${userRequest}`;
			else query = `User Query：${userRequest}`;
		} else if(typeof(result) === 'object') {
			userRequest = result.text || result.prompt || JSON.stringify(result);
			if($ln==="CN") query = `用户要求：${userRequest}`;
			else query = `User Query：${userRequest}`;
		}
		result=query;
		/*}#1JPMPHQ890PostCodes*/
		return {seg:Run,result:(result),preSeg:"1JPMPHQ890",outlet:"1JPMPHQ8A2"};
	};
	Ask.jaxId="1JPMPHQ890"
	Ask.url="Ask@"+agentURL
	
	segs["Run"]=Run=async function(input){//:1JPMPJN5R0
		let result=input
		try{
			/*#{1JPMPJN5R0Code*/
			let userRequest = input;
			let opts = { txtHeader: ($agent.showName || $agent.name || null), channel: "Chat" };
			let language = $ln === 'CN' ? 'zh' : 'en';
			const skillsDoc = config.skills?.map(s => {
				return `### ${s.name}\n- Description: ${s.description}\n- Command: ${s.command_template}\n- Arguments: ${JSON.stringify(s.arguments)}`;
			}).join('\n\n') || "No specific skills.";
			
			const workingDir = config.global_execution?.working_directory || os.homedir();
			const envName = config.global_execution?.env_name || 'base';
			
			const taskContext = language === 'zh'
				? `## 模型使用任务\n用户正在使用模型 "${model}"。当前环境已就绪：\n- 工作目录: ${workingDir}\n- Conda 环境: ${envName} (已激活)\n- 终端 ID: ${globalContext.bash1}\n\n可用技能 (Skills):\n${skillsDoc}\n\n用户的请求: ${userRequest}`
				: `## Model Task\nUser is using model "${model}". Environment is ready:\n- Working dir: ${workingDir}\n- Conda env: ${envName} (activated)\n- Terminal ID: ${globalContext.bash1}\n\nAvailable Skills:\n${skillsDoc}\n\nUser request: ${userRequest}`;
			
			const result = await runAgenticTask(session, {
				sessionKey: 'model_' + model,
				prompt: userRequest,
				systemPrompt: language === 'zh' ? '请用中文回复用户。' : 'Please reply in English.',
				tools: getAllTools(),
				model: 'deepseek/deepseek-v4-flash',
				platform: 'OpenRouter',
				maxTurns: 50,
				temperature: 0.0,
				userContext: {
					model: model,
					workingDirectory: workingDir,
					condaEnv: envName,
					skills: skillsDoc,
				},
				headerOpts: opts,
				cwd: workingDir,
				bashId: globalContext.bash1
			});
			/*}#1JPMPJN5R0Code*/
		}catch(error){
			/*#{1JPMPJN5R0ErrorCode*/
			/*}#1JPMPJN5R0ErrorCode*/
		}
		return {result:result};
	};
	Run.jaxId="1JPMPJN5R0"
	Run.url="Run@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ModelAgentTest",
		url:agentURL,
		autoStart:true,
		jaxId:"1JGP1AAKD0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model,task}*/){
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


export default ModelAgentTest;
export{ModelAgentTest};
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
//				},
//				"task": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JM7FMGHN0",
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
//						"x": "970",
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
//							"linkedSeg": "1JPMPHQ890"
//						}
//					},
//					"icon": "hudtxt.svg"
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
//						"bashId": "#globalContext.bash1",
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
//										"id": "",
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
//										"condition": "#base_command"
//									},
//									"linkedSeg": "1JH7SNN4S0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1JPMPHQ890",
//					"attrs": {
//						"id": "Ask",
//						"viewName": "",
//						"label": "",
//						"x": "1235",
//						"y": "75",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JPMPHQ8A0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JPMPHQ8A1",
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
//							"jaxId": "1JPMPHQ8A2",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JPMPJN5R0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JPMPJN5R0",
//					"attrs": {
//						"id": "Run",
//						"viewName": "",
//						"label": "",
//						"x": "1455",
//						"y": "75",
//						"desc": "This is an AISeg.",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JPMPJQ9C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JPMPJQ9C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JPMPJQ940",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "This is an AI agent.",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}