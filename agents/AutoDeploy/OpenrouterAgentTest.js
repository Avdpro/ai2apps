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
		},
		"task":{
			"name":"task","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1HDBOSUN90ArgsView*/
	/*}#1HDBOSUN90ArgsView*/
};

/*#{1HDBOSUN90StartDoc*/
async function fetchWithRetry(url, options = {}, retries = 3, delay = 1000) {
	let lastError;

	for (let attempt = 0; attempt <= retries; attempt++) {
		try {
			const response = await fetch(url, options);

			// 对 429 和 5xx 进行重试
			if (!response.ok) {
				if ((response.status === 429 || response.status >= 500) && attempt < retries) {
					const waitTime = delay * Math.pow(2, attempt); // 指数退避
					await new Promise(resolve => setTimeout(resolve, waitTime));
					continue;
				}

				throw new Error(`HTTP error! status: ${response.status}`);
			}

			return response;
		} catch (error) {
			lastError = error;

			// 网络错误时重试
			if (attempt < retries) {
				const waitTime = delay * Math.pow(2, attempt); // 指数退避
				await new Promise(resolve => setTimeout(resolve, waitTime));
				continue;
			}
		}
	}

	throw lastError;
}

async function getInputModalityOutputTokens(modelName) {
	try {
		const response = await fetchWithRetry(
			'https://openrouter.ai/api/v1/models?output_modalities=all',
			{
				headers: {
					'Authorization': 'Bearer EMPTY',
					'Content-Type': 'application/json'
				}
			},
			3,     // 最多重试 3 次
			1000   // 初始延迟 1 秒
		);

		const data = await response.json();

		// Find the model by ID
		const model = data.data.find(m => m.id === modelName);
		if (!model) {
			throw new Error(`Model "${modelName}" not found`);
		}

		// Get input_modalities from architecture
		const inputModalities = model.architecture?.input_modalities || [];
		const outputModalities = model.architecture?.output_modalities || [];
		const max_tokens = model.top_provider?.max_completion_tokens || 2048;
		const thinking = model.supported_parameters?.includes("reasoning") || false;

		return {
			modalities: inputModalities,
			max_tokens,
			output: outputModalities,
			thinking
		};
	} catch (error) {
		console.error('Error fetching model data:', error.message);
		throw error;
	}
}
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let OpenrouterAgentTest=async function(session){
	let model,task;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,GetInfo,Welcome,Generate2,Output2,Check,Generate1,Reasoning,Type,GenerateImage,OutputImage,GenerateAudio,OutputAudio,EnableThinking,Output;
	/*#{1HDBOSUN90LocalVals*/
	let model_list, input_modality, max_tokens, last_generated_image, flag=false, output_modality, support_thinking=false, enable_thinking=false;
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
			task=input.task;
		}else{
			model=undefined;
			task=undefined;
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
		if(task===undefined || task==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:GetInfo,result:(result),preSeg:"1J9OR4L7L0",outlet:"1J9OR4L7L1"};
	};
	FixArgs.jaxId="1J9OR4L7L0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["GetInfo"]=GetInfo=async function(input){//:1JGJH0L600
		let result=input
		try{
			/*#{1JGJH0L600Code*/
			let response = await getInputModalityOutputTokens(model);
			input_modality = response.modalities;
			output_modality = response.output;
			max_tokens = Math.floor(response.max_tokens / 2);
			support_thinking=response.thinking;
			/*}#1JGJH0L600Code*/
		}catch(error){
			/*#{1JGJH0L600ErrorCode*/
			/*}#1JGJH0L600ErrorCode*/
		}
		return {seg:Welcome,result:(result),preSeg:"1JGJH0L600",outlet:"1JGJH0R9I0"};
	};
	GetInfo.jaxId="1JGJH0L600"
	GetInfo.url="GetInfo@"+agentURL
	
	segs["Welcome"]=Welcome=async function(input){//:1JGJH42JR0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JGJH42JR0PreCodes*/
		opts.txtHeader=model;
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
		return {seg:Type,result:(result),preSeg:"1JGJH42JR0",outlet:"1JGJH48410"};
	};
	Welcome.jaxId="1JGJH42JR0"
	Welcome.url="Welcome@"+agentURL
	
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
			enable_thinking:true,
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
		input=task;
		opts.enable_thinking=enable_thinking;
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
			content.push({
				type: "text",
				text: input
			});
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
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat,enable_thinking:opts.enable_thinking})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("Generate2@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JGJHQV9K0PostLLM*/
		/*}#1JGJHQV9K0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>10){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1JGJHQV9K0PostClear*/
			/*}#1JGJHQV9K0PostClear*/
		}
		/*#{1JGJHQV9K0PostCall*/
		if (result && typeof result === 'object') {
			let lastMsg = chatMem[chatMem.length - 1];
			if (result.images && result.images.length > 0) {
				lastMsg.content = result.content || "（图片已生成）";
				let imageContent = [];
				for (let i = 0; i < result.images.length; i++) {
					imageContent.push(result.images[i]);
				}
				chatMem.push({ role: "user", content: imageContent });
			} else {
				lastMsg.content = result.content || JSON.stringify(result);
			}
		}
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
		/*#{1JGJI4MHM0PreCodes*/
		opts.txtHeader=model;
		if(typeof(input) === 'object' && input.images && input.images.length > 0){
			content=input.content;
			if(input.content && input.content.length>0) session.addChatText(role,content,opts);
			const images = input.images;
			let fileOpts = { channel: $channel }; 
			for(let i = 0; i < images.length; i ++){
				let image = images[i];
				if(image.type==="image_url"){
					const regex = /^data:image\/(\w+);base64,/;
					const data = image.image_url.url;
					if(data){
						last_generated_image=data;
						flag=true;
						const matches = data.match(regex);
						if (matches && matches.length === 2) {
							let saveName = `output_${Date.now()}_${i}.${matches[1]}`;
							let savedHubName = await session.saveHubFile(saveName, data);
							let hubUrl = "hub://" + savedHubName;
							fileOpts.image = hubUrl;
							session.addChatText(role, " ", fileOpts);
							result=await session.getHubPath(hubUrl);
						}
					}
				}
			}
		}
		else{
			session.addChatText(role,content,opts);
		}
		return {seg:Output,result:(result),preSeg:"1JGJI4MHM0",outlet:"1JGJI500E0"};
		/*}#1JGJI4MHM0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JGJI4MHM0PostCodes*/
		/*}#1JGJI4MHM0PostCodes*/
		return {seg:Output,result:(result),preSeg:"1JGJI4MHM0",outlet:"1JGJI500E0"};
	};
	Output2.jaxId="1JGJI4MHM0"
	Output2.url="Output2@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1JIP30I8E0
		let result=input;
		if(output_modality.includes("image")){
			return {seg:Generate1,result:(input),preSeg:"1JIP30I8E0",outlet:"1JIP31KNA0"};
		}
		return {seg:Generate2,result:(result),preSeg:"1JIP30I8E0",outlet:"1JIP31KNA1"};
	};
	Check.jaxId="1JIP30I8E0"
	Check.url="Check@"+agentURL
	
	segs["Generate1"]=Generate1=async function(input){//:1JIP319SH0
		let prompt;
		let $platform="OpenRouter";
		let $model=model;
		let $agent;
		let result=null;
		/*#{1JIP319SH0Input*/
		/*}#1JIP319SH0Input*/
		
		let opts={
			platform:$platform,
			mode:$model,
			enable_thinking:true,
			maxToken:max_tokens,
			temperature:1,
			topP:0.0001,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=Generate1.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		messages.push(...chatMem);
		/*#{1JIP319SH0PrePrompt*/
		input=task;
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
			content.push({
				type: "text",
				text: input
			});
		}
		
		if(content.length > 0){
			input=content;
		}
		/*}#1JIP319SH0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JIP319SH0FilterMessage*/
			if(content.length > 0)prompt=JSON.parse(prompt);
			msg={role:"user",content:prompt};
			/*}#1JIP319SH0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JIP319SH0PreCall*/
		/*}#1JIP319SH0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat,enable_thinking:opts.enable_thinking})):result;
		}else{
			result=(result===null)?(await session.makeAICall("Generate1@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JIP319SH0PostLLM*/
		/*}#1JIP319SH0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>10){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1JIP319SH0PostClear*/
			/*}#1JIP319SH0PostClear*/
		}
		/*#{1JIP319SH0PostCall*/
		if (result && typeof result === 'object') {
			let lastMsg = chatMem[chatMem.length - 1];
			if (result.images && result.images.length > 0) {
				lastMsg.content = result.content || "（图片已生成）";
				let imageContent = [];
				for (let i = 0; i < result.images.length; i++) {
					imageContent.push(result.images[i]);
				}
				chatMem.push({ role: "user", content: imageContent });
			} else {
				lastMsg.content = result.content || JSON.stringify(result);
			}
		}
		/*}#1JIP319SH0PostCall*/
		/*#{1JIP319SH0PreResult*/
		/*}#1JIP319SH0PreResult*/
		return {seg:Output2,result:(result),preSeg:"1JIP319SH0",outlet:"1JIP319SI0"};
	};
	Generate1.jaxId="1JIP319SH0"
	Generate1.url="Generate1@"+agentURL
	Generate1.messages=[];
	
	segs["Reasoning"]=Reasoning=async function(input){//:1JK2KQG040
		let result=input;
		if(support_thinking){
			return {seg:EnableThinking,result:(input),preSeg:"1JK2KQG040",outlet:"1JK2KRN3E0"};
		}
		return {seg:Check,result:(result),preSeg:"1JK2KQG040",outlet:"1JK2KRN3E1"};
	};
	Reasoning.jaxId="1JK2KQG040"
	Reasoning.url="Reasoning@"+agentURL
	
	segs["Type"]=Type=async function(input){//:1JL11NDNJ0
		let result=input;
		if(output_modality.length===1&&output_modality.includes("image")){
			return {seg:GenerateImage,result:(input),preSeg:"1JL11NDNJ0",outlet:"1JL12945V0"};
		}
		if(output_modality.includes("audio")){
			return {seg:GenerateAudio,result:(input),preSeg:"1JL11NDNJ0",outlet:"1JL11NHSU0"};
		}
		return {seg:Reasoning,result:(result),preSeg:"1JL11NDNJ0",outlet:"1JL12945V1"};
	};
	Type.jaxId="1JL11NDNJ0"
	Type.url="Type@"+agentURL
	
	segs["GenerateImage"]=GenerateImage=async function(input){//:1JL12Q63D0
		let prompt;
		let $platform="OpenRouter";
		let $model=model;
		let $agent;
		let result=null;
		/*#{1JL12Q63D0Input*/
		/*}#1JL12Q63D0Input*/
		
		let opts={
			platform:$platform,
			mode:$model,
			enable_thinking:true,
			maxToken:max_tokens,
			temperature:1,
			topP:0.0001,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=GenerateImage.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		/*#{1JL12Q63D0PrePrompt*/
		input=task;
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
			content.push({
				type: "text",
				text: input
			});
		}
		
		if(content.length > 0){
			input=content;
		}
		/*}#1JL12Q63D0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JL12Q63D0FilterMessage*/
			if(content.length > 0)prompt=JSON.parse(prompt);
			msg={role:"user",content:prompt};
			/*}#1JL12Q63D0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JL12Q63D0PreCall*/
		/*}#1JL12Q63D0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat,enable_thinking:opts.enable_thinking})):result;
		}else{
			result=(result===null)?(await session.makeAICall("GenerateImage@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JL12Q63D0PostCall*/
		/*}#1JL12Q63D0PostCall*/
		/*#{1JL12Q63D0PreResult*/
		/*}#1JL12Q63D0PreResult*/
		return {seg:OutputImage,result:(result),preSeg:"1JL12Q63D0",outlet:"1JL12Q63F0"};
	};
	GenerateImage.jaxId="1JL12Q63D0"
	GenerateImage.url="GenerateImage@"+agentURL
	
	segs["OutputImage"]=OutputImage=async function(input){//:1JL12ST4U0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JL12ST4U0PreCodes*/
		opts.txtHeader=model;
		if(typeof(input) === 'object' && input.images && input.images.length > 0){
		content=input.content;
		if(input.content && input.content.length>0) session.addChatText(role,content,opts);
		const images = input.images;
		let fileOpts = { channel: $channel }; 
		for(let i = 0; i < images.length; i ++){
		let image = images[i];
		if(image.type==="image_url"){
			const regex = /^data:image\/(\w+);base64,/;
			const data = image.image_url.url;
			if(data){
				last_generated_image=data;
				flag=true;
				const matches = data.match(regex);
				if (matches && matches.length === 2) {
					let saveName = `output_${Date.now()}_${i}.${matches[1]}`;
					let savedHubName = await session.saveHubFile(saveName, data);
					let hubUrl = "hub://" + savedHubName;
					fileOpts.image = hubUrl;
					session.addChatText(role, " ", fileOpts);
					result=await session.getHubPath(hubUrl);
				}
			}
		}
		}
		}
		else{
		session.addChatText(role,content,opts);
		}
		return {seg:Output,result:(result),preSeg:"1JGJI4MHM0",outlet:"1JGJI500E0"};
		/*}#1JL12ST4U0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JL12ST4U0PostCodes*/
		/*}#1JL12ST4U0PostCodes*/
		return {seg:Output,result:(result),preSeg:"1JL12ST4U0",outlet:"1JL12ST4V0"};
	};
	OutputImage.jaxId="1JL12ST4U0"
	OutputImage.url="OutputImage@"+agentURL
	
	segs["GenerateAudio"]=GenerateAudio=async function(input){//:1JL16ANFB0
		let prompt;
		let $platform="OpenRouter";
		let $model=model;
		let $agent;
		let result=null;
		/*#{1JL16ANFB0Input*/
		/*}#1JL16ANFB0Input*/
		
		let opts={
			platform:$platform,
			mode:$model,
			enable_thinking:true,
			maxToken:max_tokens,
			temperature:1,
			topP:0.0001,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=GenerateAudio.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		/*#{1JL16ANFB0PrePrompt*/
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
			content.push({
				type: "text",
				text: input
			});
		}
		
		if(content.length > 0){
			input=content;
		}
		/*}#1JL16ANFB0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JL16ANFB0FilterMessage*/
			if(content.length > 0)prompt=JSON.parse(prompt);
			msg={role:"user",content:prompt};
			/*}#1JL16ANFB0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JL16ANFB0PreCall*/
		/*}#1JL16ANFB0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat,enable_thinking:opts.enable_thinking})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("GenerateAudio@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JL16ANFB0PostCall*/
		/*}#1JL16ANFB0PostCall*/
		/*#{1JL16ANFB0PreResult*/
		/*}#1JL16ANFB0PreResult*/
		return {seg:OutputAudio,result:(result),preSeg:"1JL16ANFB0",outlet:"1JL16ANFC0"};
	};
	GenerateAudio.jaxId="1JL16ANFB0"
	GenerateAudio.url="GenerateAudio@"+agentURL
	
	segs["OutputAudio"]=OutputAudio=async function(input){//:1JL16CCPS0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JL16CCPS0PreCodes*/
		opts.txtHeader=model;
		if(typeof(input) === 'object'){
			content = input.content || "";
			// 显示 transcript 文本
			if(content && content.length > 0){
				session.addChatText(role, content, opts);
			}
			// 处理音频 dataURL
			if(input.audio && input.audio.startsWith("data:audio/")){
				let fileOpts = { channel: $channel };
				const regex = /^data:audio\/(\w+);base64,/;
				const matches = input.audio.match(regex);
				if(matches && matches.length === 2){
					let ext = matches[1] === 'mpeg' ? 'mp3' : matches[1];
					let saveName = `output_${Date.now()}.${ext}`;
					let savedHubName = await session.saveHubFile(saveName, input.audio);
					let hubUrl = "hub://" + savedHubName;
					fileOpts.audio = hubUrl;
					session.addChatText(role, " ", fileOpts);
					result=await session.getHubPath(hubUrl);
				}
			}
		} else {
			session.addChatText(role, content, opts);
		}
		return {seg:Output,result:(result),preSeg:"1JGJI4MHM0",outlet:"1JGJI500E0"};
		/*}#1JL16CCPS0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JL16CCPS0PostCodes*/
		/*}#1JL16CCPS0PostCodes*/
		return {seg:Output,result:(result),preSeg:"1JL16CCPS0",outlet:"1JL16CP6S0"};
	};
	OutputAudio.jaxId="1JL16CCPS0"
	OutputAudio.url="OutputAudio@"+agentURL
	
	segs["EnableThinking"]=EnableThinking=async function(input){//:1JM7GH26I0
		let result=input
		try{
			/*#{1JM7GH26I0Code*/
			enable_thinking=true;
			/*}#1JM7GH26I0Code*/
		}catch(error){
			/*#{1JM7GH26I0ErrorCode*/
			/*}#1JM7GH26I0ErrorCode*/
		}
		return {seg:Check,result:(result),preSeg:"1JM7GH26I0",outlet:"1JM7GH7RP0"};
	};
	EnableThinking.jaxId="1JM7GH26I0"
	EnableThinking.url="EnableThinking@"+agentURL
	
	segs["Output"]=Output=async function(input){//:1JMAOVCP80
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {result:result};
	};
	Output.jaxId="1JMAOVCP80"
	Output.url="Output@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"OpenrouterAgentTest",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model,task}*/){
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


export default OpenrouterAgentTest;
export{OpenrouterAgentTest};
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
//				},
//				"task": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JM7GBRNB0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
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
//						"x": "-945",
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
//						"id": "GetInfo",
//						"viewName": "",
//						"label": "",
//						"x": "-740",
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
//						"x": "-500",
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
//							"linkedSeg": "1JL11NDNJ0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JGJHQV9K0",
//					"attrs": {
//						"id": "Generate2",
//						"viewName": "",
//						"label": "",
//						"x": "650",
//						"y": "680",
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
//						"enable_thinking": "true",
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
//						"keepChat": "10 messages",
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
//						"x": "925",
//						"y": "680",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
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
//							"linkedSeg": "1JMAOVCP80"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JIP30I8E0",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "415",
//						"y": "665",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIP31KNM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIP31KNM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JIP31KNA1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JGJHQV9K0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JIP31KNA0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JIP31KNM2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JIP31KNM3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#output_modality.includes(\"image\")"
//									},
//									"linkedSeg": "1JIP319SH0"
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
//					"jaxId": "1JIP319SH0",
//					"attrs": {
//						"id": "Generate1",
//						"viewName": "",
//						"label": "",
//						"x": "650",
//						"y": "580",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIP319SH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIP319SH2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenRouter",
//						"mode": "#model",
//						"system": "You are a smart assistant.",
//						"enable_thinking": "true",
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
//							"jaxId": "1JIP319SI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJI4MHM0"
//						},
//						"stream": "false",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "10 messages",
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
//					"def": "brunch",
//					"jaxId": "1JK2KQG040",
//					"attrs": {
//						"id": "Reasoning",
//						"viewName": "",
//						"label": "",
//						"x": "-55",
//						"y": "650",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JK2KRN3P0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JK2KRN3P1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JK2KRN3E1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JIP30I8E0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JK2KRN3E0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JK2KRN3P2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JK2KRN3P3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#support_thinking"
//									},
//									"linkedSeg": "1JM7GH26I0"
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
//					"jaxId": "1JL11NDNJ0",
//					"attrs": {
//						"id": "Type",
//						"viewName": "",
//						"label": "",
//						"x": "-270",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "#output_modality",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JL12946R0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JL12946R1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JL12945V1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JK2KQG040"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JL12945V0",
//									"attrs": {
//										"id": "Draw",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JL12946R2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JL12946R3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#output_modality.length===1&&output_modality.includes(\"image\")"
//									},
//									"linkedSeg": "1JL12Q63D0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JL11NHSU0",
//									"attrs": {
//										"id": "Audio",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JL12946R4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JL12946R5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#output_modality.includes(\"audio\")"
//									},
//									"linkedSeg": "1JL16ANFB0"
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
//					"jaxId": "1JL12Q63D0",
//					"attrs": {
//						"id": "GenerateImage",
//						"viewName": "",
//						"label": "",
//						"x": "-65",
//						"y": "115",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JL12Q63E0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JL12Q63E1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenRouter",
//						"mode": "#model",
//						"system": "You are a smart assistant.",
//						"enable_thinking": "true",
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
//							"jaxId": "1JL12Q63F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JL12ST4U0"
//						},
//						"stream": "false",
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
//					"jaxId": "1JL12ST4U0",
//					"attrs": {
//						"id": "OutputImage",
//						"viewName": "",
//						"label": "",
//						"x": "215",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JL12ST4U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JL12ST4U2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JL12ST4V0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JMAOVCP80"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JL16ANFB0",
//					"attrs": {
//						"id": "GenerateAudio",
//						"viewName": "",
//						"label": "",
//						"x": "-60",
//						"y": "320",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JL16ANFB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JL16ANFB2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenRouter",
//						"mode": "#model",
//						"system": "You are a smart assistant.",
//						"enable_thinking": "true",
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
//							"jaxId": "1JL16ANFC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JL16CCPS0"
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
//					"jaxId": "1JL16CCPS0",
//					"attrs": {
//						"id": "OutputAudio",
//						"viewName": "",
//						"label": "",
//						"x": "215",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JL16CP7B0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JL16CP7B1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JL16CP6S0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JMAOVCP80"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JM7GH26I0",
//					"attrs": {
//						"id": "EnableThinking",
//						"viewName": "",
//						"label": "",
//						"x": "165",
//						"y": "510",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JM7GH7S80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JM7GH7S81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JM7GH7RP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIP30I8E0"
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
//					"jaxId": "1JMAOVCP80",
//					"attrs": {
//						"id": "Output",
//						"viewName": "",
//						"label": "",
//						"x": "585",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JMAOVN3G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JMAOVN3G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JMAOVN300",
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
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":false,\"isChatApi\":1,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\",\"kind\":\"chat\",\"capabilities\":[],\"filters\":[],\"metrics\":{\"quality\":\"\",\"costPerCall\":\"\",\"costPer1M\":\"\",\"speed\":\"\",\"size\":\"\"},\"meta\":\"\"}"
//	}
//}