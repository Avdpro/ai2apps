//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1HDBOSUN90MoreImports*/
import fsp from 'fs/promises';
/*}#1HDBOSUN90MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1HDBOSUN90ArgsView*/
	/*}#1HDBOSUN90ArgsView*/
};

/*#{1HDBOSUN90StartDoc*/
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let OllamaAgent=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,InitBash,ListModels,CheckInstall,Pull,Greet,Ask,Generate,Output,Download,CheckPull,Fail,Retry,CheckRun,Start;
	/*#{1HDBOSUN90LocalVals*/
	let model_list, input_modality;
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
		}else{
			model=undefined;
		}
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
	/*}#1HDBOSUN90PreContext*/
	context={};
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1J9OR4L7L0
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(model===undefined || model==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:InitBash,result:(result),preSeg:"1J9OR4L7L0",outlet:"1J9OR4L7L1"};
	};
	FixArgs.jaxId="1J9OR4L7L0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["InitBash"]=InitBash=async function(input){//:1J9OR88QE0
		let result,args={};
		args['bashId']="";
		args['action']="Create";
		args['commands']="";
		args['options']={client:true};
		/*#{1J9OR88QE0PreCodes*/
		/*}#1J9OR88QE0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1J9OR88QE0PostCodes*/
		globalContext.bash=result;
		/*}#1J9OR88QE0PostCodes*/
		return {seg:ListModels,result:(result),preSeg:"1J9OR88QE0",outlet:"1J9OR99650"};
	};
	InitBash.jaxId="1J9OR88QE0"
	InitBash.url="InitBash@"+agentURL
	
	segs["ListModels"]=ListModels=async function(input){//:1J9ORDF050
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="ollama list";
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:CheckRun,result:(result),preSeg:"1J9ORDF050",outlet:"1J9OREIEF0"};
	};
	ListModels.jaxId="1J9ORDF050"
	ListModels.url="ListModels@"+agentURL
	
	segs["CheckInstall"]=CheckInstall=async function(input){//:1J9ORU8NT0
		let result=input;
		if(input.includes(model)){
			return {seg:Greet,result:(input),preSeg:"1J9ORU8NT0",outlet:"1J9ORUUF20"};
		}
		return {seg:Download,result:(result),preSeg:"1J9ORU8NT0",outlet:"1J9ORUUF21"};
	};
	CheckInstall.jaxId="1J9ORU8NT0"
	CheckInstall.url="CheckInstall@"+agentURL
	
	segs["Pull"]=Pull=async function(input){//:1J9OS17JC0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`ollama pull ${model}`;
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:CheckPull,result:(result),preSeg:"1J9OS17JC0",outlet:"1J9OS3S740"};
	};
	Pull.jaxId="1J9OS17JC0"
	Pull.url="Pull@"+agentURL
	
	segs["Greet"]=Greet=async function(input){//:1J9OS5E6P0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("你好，需要什么帮助吗？"):("Hello, how can I help you?"));
		session.addChatText(role,content,opts);
		return {seg:Ask,result:(result),preSeg:"1J9OS5E6P0",outlet:"1J9OS72MR0"};
	};
	Greet.jaxId="1J9OS5E6P0"
	Greet.url="Greet@"+agentURL
	
	segs["Ask"]=Ask=async function(input){//:1J9OS7BA20
		let tip=("");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(true)||false;
		let allowEmpty=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
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
		return {seg:Generate,result:(result),preSeg:"1J9OS7BA20",outlet:"1J9OS7F5H0"};
	};
	Ask.jaxId="1J9OS7BA20"
	Ask.url="Ask@"+agentURL
	
	segs["Generate"]=Generate=async function(input){//:1J9OS7UUK0
		let prompt;
		let $platform="Ollama";
		let $model=model;
		let $agent;
		let result=null;
		/*#{1J9OS7UUK0Input*/
		/*}#1J9OS7UUK0Input*/
		
		let opts={
			platform:$platform,
			mode:$model,
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
			{role:"system",content:"You are a smart assistant."},
		];
		messages.push(...chatMem);
		/*#{1J9OS7UUK0PrePrompt*/
		// Handle input with images
		let images = [];
		if(typeof(input) === 'object' && input.assets && input.assets.length > 0) {
			prompt = input.prompt || "";
		
			// Convert hub:// paths to absolute @filelib/ paths and read as base64
			const filelibPath = pathLib.join(pathLib.dirname(pathLib.dirname(basePath)), 'filelib');
			for(let i = 0; i < input.assets.length; i++) {
				let assetPath = input.assets[i];
				// Remove hub:// prefix if present
				if(assetPath.startsWith('hub://')) {
					assetPath = assetPath.substring(6);
				}
				const absolutePath = pathLib.join(filelibPath, assetPath);
		
				try {
					// Read image file as base64
					const imageBuffer = await fsp.readFile(absolutePath);
					const base64Image = imageBuffer.toString('base64');
					images.push(base64Image);
				} catch(error) {
					console.error(`Failed to read image: ${absolutePath}`, error);
				}
			}
		} else {
			prompt = input;
		}
		/*}#1J9OS7UUK0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1J9OS7UUK0FilterMessage*/
			if(images.length > 0) {
				msg.images = images;
			}
			/*}#1J9OS7UUK0FilterMessage*/
			messages.push(msg);
		}
		/*#{1J9OS7UUK0PreCall*/
		
		/*}#1J9OS7UUK0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("Generate@"+agentURL,opts,messages,true)):result;
		}
		/*#{1J9OS7UUK0PostLLM*/
		/*}#1J9OS7UUK0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1J9OS7UUK0PostClear*/
			/*}#1J9OS7UUK0PostClear*/
		}
		/*#{1J9OS7UUK0PostCall*/
		/*}#1J9OS7UUK0PostCall*/
		/*#{1J9OS7UUK0PreResult*/
		/*}#1J9OS7UUK0PreResult*/
		return {seg:Output,result:(result),preSeg:"1J9OS7UUK0",outlet:"1J9OS84KO0"};
	};
	Generate.jaxId="1J9OS7UUK0"
	Generate.url="Generate@"+agentURL
	Generate.messages=[];
	
	segs["Output"]=Output=async function(input){//:1J9OSCN8T0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:Ask,result:(result),preSeg:"1J9OSCN8T0",outlet:"1J9OSCUJ00"};
	};
	Output.jaxId="1J9OSCN8T0"
	Output.url="Output@"+agentURL
	
	segs["Download"]=Download=async function(input){//:1J9P1OS850
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("正在下载模型，请稍等"):("Downloading model, please wait"));
		session.addChatText(role,content,opts);
		return {seg:Pull,result:(result),preSeg:"1J9P1OS850",outlet:"1J9P1PQFR0"};
	};
	Download.jaxId="1J9P1OS850"
	Download.url="Download@"+agentURL
	
	segs["CheckPull"]=CheckPull=async function(input){//:1J9P1R2GP0
		let result=input;
		if(input.includes("success")){
			return {seg:Greet,result:(input),preSeg:"1J9P1R2GP0",outlet:"1J9P1S6VB0"};
		}
		return {seg:Fail,result:(result),preSeg:"1J9P1R2GP0",outlet:"1J9P1S6VB1"};
	};
	CheckPull.jaxId="1J9P1R2GP0"
	CheckPull.url="CheckPull@"+agentURL
	
	segs["Fail"]=Fail=async function(input){//:1J9P1SBLP0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("模型下载失败，是否重试"):("Model download failed, would you like to retry?"));
		session.addChatText(role,content,opts);
		return {seg:Retry,result:(result),preSeg:"1J9P1SBLP0",outlet:"1J9P1U64F0"};
	};
	Fail.jaxId="1J9P1SBLP0"
	Fail.url="Fail@"+agentURL
	
	segs["Retry"]=Retry=async function(input){//:1J9P1ULAT0
		let prompt=("Please confirm")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("重试"):("Retry")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("中止"):("Abort")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Pull,result:(result),preSeg:"1J9P1ULAT0",outlet:"1J9P1ULA70"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Pull,result:(result),preSeg:"1J9P1ULAT0",outlet:"1J9P1ULA70"};
		}else if(item.code===1){
			return {result:result};
		}
		return {result:result};
	};
	Retry.jaxId="1J9P1ULAT0"
	Retry.url="Retry@"+agentURL
	
	segs["CheckRun"]=CheckRun=async function(input){//:1J9R9TNTS0
		let result=input;
		if(input.includes("ollama server not responding")){
			return {seg:Start,result:(input),preSeg:"1J9R9TNTS0",outlet:"1J9R9VV390"};
		}
		return {seg:CheckInstall,result:(result),preSeg:"1J9R9TNTS0",outlet:"1J9R9VV391"};
	};
	CheckRun.jaxId="1J9R9TNTS0"
	CheckRun.url="CheckRun@"+agentURL
	
	segs["Start"]=Start=async function(input){//:1J9R9V1S90
		let result,args={};
		args['bashId']=globalContext.backend;
		args['action']="Command";
		args['commands']="brew services start ollama";
		args['options']={ownBySession:true};
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:ListModels,result:(result),preSeg:"1J9R9V1S90",outlet:"1J9R9VV392"};
	};
	Start.jaxId="1J9R9V1S90"
	Start.url="Start@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"OllamaAgent",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model}*/){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN90PreEntry*/
			/*}#1HDBOSUN90PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1HDBOSUN90PostEntry*/
			/*}#1HDBOSUN90PostEntry*/
			return result;
		},
		/*#{1HDBOSUN90MoreAgentAttrs*/
		/*}#1HDBOSUN90MoreAgentAttrs*/
	};
	/*#{1HDBOSUN90PostAgent*/
	/*}#1HDBOSUN90PostAgent*/
	return agent;
};
/*#{1HDBOSUN90ExCodes*/
/*}#1HDBOSUN90ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1HDBOSUN90PostDoc*/
/*}#1HDBOSUN90PostDoc*/


export default OllamaAgent;
export{OllamaAgent};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1HDBOSUN90",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1HDBOSUNA0",
//			"attrs": {
//				"agent": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1HDBOSUNA4",
//					"attrs": {
//						"constructArgs": {
//							"jaxId": "1HDBOSUNB0",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1HDBOSUNB1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1HDBOSUNB2",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportType": "UI Data Template",
//						"exportClass": "false",
//						"superClass": ""
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1HDBOSUNA1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1J9OR4L7O0",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J9OR50UK0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"required": "true",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1HDBOSUNA3",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1HDIJB7SK6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1J9OR4L7L0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "-160",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1J9OR4L7L1",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9OR88QE0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1J9OR88QE0",
//					"attrs": {
//						"id": "InitBash",
//						"viewName": "",
//						"label": "",
//						"x": "80",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9OR99660",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9OR99661",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "\"\"",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client:true}",
//						"outlet": {
//							"jaxId": "1J9OR99650",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9ORDF050"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1J9ORDF050",
//					"attrs": {
//						"id": "ListModels",
//						"viewName": "",
//						"label": "",
//						"x": "340",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9OREIEK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9OREIEK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "ollama list",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J9OREIEF0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9R9TNTS0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J9ORU8NT0",
//					"attrs": {
//						"id": "CheckInstall",
//						"viewName": "",
//						"label": "",
//						"x": "945",
//						"y": "335",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9OS3S7D0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9OS3S7D1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J9ORUUF21",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J9P1OS850"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J9ORUUF20",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J9OS3S7D2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J9OS3S7D3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.includes(model)"
//									},
//									"linkedSeg": "1J9OS5E6P0"
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
//					"jaxId": "1J9OS17JC0",
//					"attrs": {
//						"id": "Pull",
//						"viewName": "",
//						"label": "",
//						"x": "1380",
//						"y": "450",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9OS3S7D4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9OS3S7D5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`ollama pull ${model}`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J9OS3S740",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9P1R2GP0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J9OS5E6P0",
//					"attrs": {
//						"id": "Greet",
//						"viewName": "",
//						"label": "",
//						"x": "1225",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9OS72N00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9OS72N01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Hello, how can I help you?",
//							"localize": {
//								"EN": "Hello, how can I help you?",
//								"CN": "你好，需要什么帮助吗？"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J9OS72MR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9OS7BA20"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1J9OS7BA20",
//					"attrs": {
//						"id": "Ask",
//						"viewName": "",
//						"label": "",
//						"x": "1455",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9OS7F5M0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9OS7F5M1",
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
//							"jaxId": "1J9OS7F5H0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9OS7UUK0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1J9OS7UUK0",
//					"attrs": {
//						"id": "Generate",
//						"viewName": "",
//						"label": "",
//						"x": "1680",
//						"y": "320",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9OS84KQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9OS84KQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "Ollama",
//						"mode": "#model",
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
//							"jaxId": "1J9OS84KO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9OSCN8T0"
//						},
//						"stream": "true",
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
//						"responseFormat": "text",
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
//					"def": "output",
//					"jaxId": "1J9OSCN8T0",
//					"attrs": {
//						"id": "Output",
//						"viewName": "",
//						"label": "",
//						"x": "1915",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9OSCUJ20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9OSCUJ21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1J9OSCUJ00",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9OSDAFI0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J9OSDAFI0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2045",
//						"y": "180",
//						"outlet": {
//							"jaxId": "1J9OSDOEK0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9OSDHBN0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J9OSDHBN0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1480",
//						"y": "180",
//						"outlet": {
//							"jaxId": "1J9OSDOEK1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9OS7BA20"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J9P1OS850",
//					"attrs": {
//						"id": "Download",
//						"viewName": "",
//						"label": "",
//						"x": "1150",
//						"y": "450",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9P1PQFT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9P1PQFT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Downloading model, please wait",
//							"localize": {
//								"EN": "Downloading model, please wait",
//								"CN": "正在下载模型，请稍等"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J9P1PQFR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9OS17JC0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J9P1R2GP0",
//					"attrs": {
//						"id": "CheckPull",
//						"viewName": "",
//						"label": "",
//						"x": "1575",
//						"y": "450",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9P1S6VB2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9P1S6VB3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J9P1S6VB1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J9P1SBLP0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J9P1S6VB0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J9P1S6VC0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J9P1S6VC1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.includes(\"success\")"
//									},
//									"linkedSeg": "1J9P1SGL50"
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
//					"jaxId": "1J9P1SBLP0",
//					"attrs": {
//						"id": "Fail",
//						"viewName": "",
//						"label": "",
//						"x": "1795",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9P1U64H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9P1U64H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Model download failed, would you like to retry?",
//							"localize": {
//								"EN": "Model download failed, would you like to retry?",
//								"CN": "模型下载失败，是否重试"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J9P1U64F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9P1ULAT0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J9P1SGL50",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1720",
//						"y": "370",
//						"outlet": {
//							"jaxId": "1J9P1U64H2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9P1SMNV0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J9P1SMNV0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1250",
//						"y": "370",
//						"outlet": {
//							"jaxId": "1J9P1U64H3",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9OS5E6P0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1J9P1ULAT0",
//					"attrs": {
//						"id": "Retry",
//						"viewName": "",
//						"label": "",
//						"x": "1975",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "Please confirm",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1J9P2080K0",
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
//									"jaxId": "1J9P1ULA70",
//									"attrs": {
//										"id": "Retry",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Retry",
//											"localize": {
//												"EN": "Retry",
//												"CN": "重试"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J9P2080M0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J9P2080M1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1J9P20IMQ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J9P1ULA71",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Abort",
//											"localize": {
//												"EN": "Abort",
//												"CN": "中止"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J9P2080M2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J9P2080M3",
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
//					"jaxId": "1J9P20IMQ0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2100",
//						"y": "700",
//						"outlet": {
//							"jaxId": "1J9P214TJ0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9P20NUH0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J9P20NUH0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1415",
//						"y": "700",
//						"outlet": {
//							"jaxId": "1J9P214TJ1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9OS17JC0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J9R9TNTS0",
//					"attrs": {
//						"id": "CheckRun",
//						"viewName": "",
//						"label": "",
//						"x": "605",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9R9VV3F0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9R9VV3F1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J9R9VV391",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J9ORU8NT0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J9R9VV390",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J9R9VV3F2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J9R9VV3F3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.includes(\"ollama server not responding\")"
//									},
//									"linkedSeg": "1J9R9V1S90"
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
//					"jaxId": "1J9R9V1S90",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "835",
//						"y": "220",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9R9VV3F4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9R9VV3F5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.backend",
//						"action": "Command",
//						"commands": "brew services start ollama",
//						"options": "#{ownBySession:true}",
//						"outlet": {
//							"jaxId": "1J9R9VV392",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9RA07C00"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J9RA07C00",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "960",
//						"y": "145",
//						"outlet": {
//							"jaxId": "1J9RA0HV70",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9RA0BR60"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J9RA0BR60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "375",
//						"y": "145",
//						"outlet": {
//							"jaxId": "1J9RA0HV71",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9ORDF050"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":false,\"isChatApi\":1,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\",\"kind\":\"chat\",\"capabilities\":[],\"filters\":[],\"metrics\":{\"quality\":\"\",\"costPerCall\":\"\",\"costPer1M\":\"\",\"speed\":\"\",\"size\":\"\"},\"meta\":\"\"}"
//	}
//}