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
async function getInputModalityOutputTokens(modelName) {
	try {
		const response = await fetch('https://openrouter.ai/api/v1/models', {
			headers: {
				'Authorization': 'Bearer EMPTY',
				'Content-Type': 'application/json'
			}
		});

		if (!response.ok) {
			throw new Error(`HTTP error! status: ${response.status}`);
		}

		const data = await response.json();

		// Find the model by ID
		const model = data.data.find(m => m.id === modelName);

		if (!model) {
			throw new Error(`Model "${modelName}" not found`);
		}

		// Get input_modalities from architecture
		const inputModalities = model.architecture?.input_modalities || [];
		const max_tokens = model.top_provider?.max_completion_tokens || 2048;
		return {modalities: inputModalities, max_tokens: max_tokens};
	} catch (error) {
		console.error('Error fetching model data:', error.message);
		throw error;
	}
}
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let agent=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,GetInputModality,Welcome,AskInput,Generate2,Output2;
	/*#{1HDBOSUN90LocalVals*/
	let model_list, input_modality, max_tokens;
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
		return {seg:GetInputModality,result:(result),preSeg:"1J9OR4L7L0",outlet:"1J9OR4L7L1"};
	};
	FixArgs.jaxId="1J9OR4L7L0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["GetInputModality"]=GetInputModality=async function(input){//:1JGJH0L600
		let result=input
		try{
			/*#{1JGJH0L600Code*/
			let response = await getInputModalityOutputTokens(model);
			input_modality = response.modalities;
			max_tokens = response.max_tokens;
			/*}#1JGJH0L600Code*/
		}catch(error){
			/*#{1JGJH0L600ErrorCode*/
			/*}#1JGJH0L600ErrorCode*/
		}
		return {seg:Welcome,result:(result),preSeg:"1JGJH0L600",outlet:"1JGJH0R9I0"};
	};
	GetInputModality.jaxId="1JGJH0L600"
	GetInputModality.url="GetInputModality@"+agentURL
	
	segs["Welcome"]=Welcome=async function(input){//:1JGJH42JR0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JGJH42JR0PreCodes*/
		let modalityText = "";
		if(input_modality && input_modality.length > 0) {
			const modalityIcons = {
				'text': '📝',
				'image': '🖼️',
				'video': '🎬',
				'audio': '🎵',
				'file': '📎'
			};
			const modalityNamesCN = {
				'text': '文本',
				'image': '图片',
				'video': '视频',
				'audio': '音频',
				'file': '文件'
			};
		
			let modalityList;
			if($ln === "CN") {
				modalityList = input_modality.map(m => `${modalityIcons[m] || '•'} ${modalityNamesCN[m] || m}`).join('、');
				modalityText = `\n\n**支持的输入模态:** ${modalityList}`;
			} else {
				modalityList = input_modality.map(m => `${modalityIcons[m] || '•'} ${m}`).join(', ');
				modalityText = `\n\n**Supported Input Modalities:** ${modalityList}`;
			}
		}
		
		if($ln === "CN") {
			content = `👋 欢迎使用 AI 助手！\n\n**当前模型:** ${model}${modalityText}\n\n我已准备就绪，请问有什么可以帮助您的吗？`;
		} else {
			content = `👋 Welcome to AI Assistant!\n\n**Current Model:** ${model}${modalityText}\n\nI'm ready to help. How can I assist you today?`;
		}
		/*}#1JGJH42JR0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JGJH42JR0PostCodes*/
		/*}#1JGJH42JR0PostCodes*/
		return {seg:AskInput,result:(result),preSeg:"1JGJH42JR0",outlet:"1JGJH48410"};
	};
	Welcome.jaxId="1JGJH42JR0"
	Welcome.url="Welcome@"+agentURL
	
	segs["AskInput"]=AskInput=async function(input){//:1JGJHEJD10
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
		return {seg:Generate2,result:(result),preSeg:"1JGJHEJD10",outlet:"1JGJHETJR0"};
	};
	AskInput.jaxId="1JGJHEJD10"
	AskInput.url="AskInput@"+agentURL
	
	segs["Generate2"]=Generate2=async function(input){//:1JGJHQV9K0
		let prompt;
		let $platform="OpenRouter";
		let $model=model;
		let $agent;
		let result=null;
		/*#{1JGJHQV9K0Input*/
		/*}#1JGJHQV9K0Input*/
		
		let opts={
			platform:$platform,
			mode:$model,
			maxToken:max_tokens,
			temperature:1,
			topP:0.0001,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=Generate2.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		messages.push(...chatMem);
		/*#{1JGJHQV9K0PrePrompt*/
		let content = [];
		if(typeof(input) === 'object' && input.assets && input.assets.length > 0) {
			prompt = input.prompt || input.text || "";
		
			// Add text content first
			if(prompt) {
				content.push({
					type: "text",
					text: prompt
				});
			}
		
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
					// Read file as base64
					const fileBuffer = await fsp.readFile(absolutePath);
					const base64Data = fileBuffer.toString('base64');
					const fileName = pathLib.basename(absolutePath);
					const ext = pathLib.extname(fileName).toLowerCase();
		
					// Determine file type based on extension
					if(['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(ext)) {
						// Image file - check if model supports images
						if(input_modality && input_modality.includes('image')) {
							const mimeType = ext === '.jpg' || ext === '.jpeg' ? 'image/jpeg' :
											ext === '.png' ? 'image/png' :
											ext === '.gif' ? 'image/gif' : 'image/webp';
							content.push({
								type: "image_url",
								image_url: {
									url: `data:${mimeType};base64,${base64Data}`
								}
							});
						}
					} else if(['.mp4', '.mpeg', '.mov', '.webm'].includes(ext)) {
						// Video file
						if(input_modality && input_modality.includes('video')) {
							const mimeType = ext === '.mp4' ? 'video/mp4' :
											ext === '.mpeg' ? 'video/mpeg' :
											ext === '.mov' ? 'video/mov' : 'video/webm';
							content.push({
								type: "video_url",
								video_url: {
									url: `data:${mimeType};base64,${base64Data}`
								}
							});
						}
					} else if(['.wav', '.mp3', '.aiff', '.aac', '.ogg', '.flac', '.m4a'].includes(ext)) {
						// Audio file
						if(input_modality && input_modality.includes('audio')) {
							const format = ext.substring(1); // Remove the dot
							content.push({
								type: "input_audio",
								input_audio: {
									data: base64Data,
									format: format
								}
							});
						}
					} else if(ext === '.pdf') {
						// PDF file
						if(input_modality && input_modality.includes('file')) {
							content.push({
								type: "file",
								file: {
									filename: fileName,
									file_data: `data:application/pdf;base64,${base64Data}`
								}
							});
						}
					}
				} catch(error) {
					console.error(`Failed to read file: ${absolutePath}`, error);
				}
			}
		} else {
			// Simple text prompt
			prompt = input;
		}
		if(content.length > 0){
			input=content;
		}
		/*}#1JGJHQV9K0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JGJHQV9K0FilterMessage*/
			if(content.length > 0)prompt=JSON.parse(prompt);
			msg={role:"user",content:prompt};
			/*}#1JGJHQV9K0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JGJHQV9K0PreCall*/
		/*}#1JGJHQV9K0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("Generate2@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JGJHQV9K0PostLLM*/
		/*}#1JGJHQV9K0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		/*#{1JGJHQV9K0PostCall*/
		/*}#1JGJHQV9K0PostCall*/
		/*#{1JGJHQV9K0PreResult*/
		/*}#1JGJHQV9K0PreResult*/
		return {seg:Output2,result:(result),preSeg:"1JGJHQV9K0",outlet:"1JGJHR6V90"};
	};
	Generate2.jaxId="1JGJHQV9K0"
	Generate2.url="Generate2@"+agentURL
	Generate2.messages=[];
	
	segs["Output2"]=Output2=async function(input){//:1JGJI4MHM0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:AskInput,result:(result),preSeg:"1JGJI4MHM0",outlet:"1JGJI500E0"};
	};
	Output2.jaxId="1JGJI4MHM0"
	Output2.url="Output2@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"agent",
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


export default agent;
export{agent};
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
//						"x": "-115",
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
//							"linkedSeg": "1JGJH0L600"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JGJH0L600",
//					"attrs": {
//						"id": "GetInputModality",
//						"viewName": "",
//						"label": "",
//						"x": "120",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGJH0R9N0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGJH0R9N1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JGJH0R9I0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJH42JR0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JGJH42JR0",
//					"attrs": {
//						"id": "Welcome",
//						"viewName": "",
//						"label": "",
//						"x": "395",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGJH48450",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGJH48451",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JGJH48410",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJHEJD10"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1JGJHEJD10",
//					"attrs": {
//						"id": "AskInput",
//						"viewName": "",
//						"label": "",
//						"x": "625",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGJHETK10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGJHETK11",
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
//							"jaxId": "1JGJHETJR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJHQV9K0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JGJHQV9K0",
//					"attrs": {
//						"id": "Generate2",
//						"viewName": "",
//						"label": "",
//						"x": "860",
//						"y": "320",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGJHR6VF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGJHR6VF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenRouter",
//						"mode": "#model",
//						"system": "You are a smart assistant.",
//						"temperature": "1",
//						"maxToken": "#max_tokens",
//						"topP": "0.0001",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1JGJHR6V90",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJI4MHM0"
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
//						"responseFormat": "text",
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
//					"def": "output",
//					"jaxId": "1JGJI4MHM0",
//					"attrs": {
//						"id": "Output2",
//						"viewName": "",
//						"label": "",
//						"x": "1100",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGJI500M0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGJI500M1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JGJI500E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJI5SCF0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JGJI5SCF0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1225",
//						"y": "125",
//						"outlet": {
//							"jaxId": "1JGJI6E350",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJI60TJ0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JGJI60TJ0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "655",
//						"y": "125",
//						"outlet": {
//							"jaxId": "1JGJI6E351",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJHEJD10"
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