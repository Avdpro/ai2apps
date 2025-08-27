import { promises as fsp } from 'fs';
import pathLib from "path";
import sharp from "sharp";
import OpenAI from "openai";
import {pathToFileURL} from 'url';
import RemoteSession from '../agents/tabos/remotesession.mjs';
import * as Os from 'os'
async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}

let openAI = null;

// *****************************************************************************
function setupOpenAI(session) {
	if (openAI) return openAI;
	
	const key = session.agentNode.hubJSON?.key_OpenAI;
	if (key) {
		openAI = new OpenAI({
			apiKey:key,
		});
		return openAI;
	}
	return null;
}

// *****************************************************************************
function trimJSON(inputString) {
	try {
		let value;
		let startIdx = inputString.indexOf("{");
		if (startIdx === -1) return null;
		let endIdx=inputString.lastIndexOf("}");
		while (endIdx > 0) {
			try {
				value = JSON.parse(inputString.substring(startIdx,endIdx+1));
				return value;
			} catch {
				endIdx = inputString.indexOf("}", endIdx - 1);
			}
		}
	} catch {
		return null;
	}
	return null;
}

// *****************************************************************************
async function importModuleFromFile(filePath) {
	if (process.platform=== "win32" && pathLib.isAbsolute(filePath)){
		filePath = pathToFileURL(filePath).href;
		const module = await import(filePath);
		return module;
	}
	const module = await import(pathLib.resolve(filePath));
	return module;
}

// *****************************************************************************
function getErrorLocation(e) {
	if(e && e.stack) {
		const trace = e.stack.split("\n");
		return trace[trace.length - 1];
	}
	return "NA";
}

let frameSeqId=0;

class ChatSession {
	static agentDict = {};
	
	constructor(basePath, node = null, sessionId = null, options = {}) {
		this.basePath = basePath;
		this.curPath = null;
		this.agentNode = node;
		this.curAgent = null;
		this.curAISeg=null;
		this.sessionId = sessionId;
		this.nextCallId = 0;
		this.callMap = new Map();
		this.version = "0.0.2";
		this.options = options || {};
		this.language = this.options.language || "CN";
		this.globalContext={};
		{
			let gc;
			gc=node.hubJSON?node.hubJSON.globalContext:null;
			if(gc){
				Object.assign(this.globalContext,gc);
			}
			gc=node.nodeJSON.globalContext;
			if(gc){
				Object.assign(this.globalContext,gc);
			}
			gc=options?options.globalContext:null;
			if(gc){
				Object.assign(this.globalContext,gc);
			}
		}
		this.termMap=new Map();
		
		this.debugStarted=false;
		this.debugConnected=false;
		
		this.callClientFromAgent=null;
		this.callClientAskSeg=null;
	}
	
	// -------------------------------------------------------------------------
	// Show version:
	showVersion() {
		console.log("ChatSession 0.02");
	}
	
	//--------------------------------------------------------------------------
	async startDebug(agentURL,entryDef){
		this.debugStarted=true;
		try{
			await this.callClient("ConnectAgentDebug",{address:this.agentNode.address,port:this.agentNode.debugPort,entryURL:agentURL,entryAgent:entryDef});
		}catch(err){
			return;
		}
		this.debugConnected=true;
	};
	
	// -------------------------------------------------------------------------
	async sendToClient(msg, vo) {
		const message = JSON.stringify({
			msg: "MessageToClient",
			sessionId: this.sessionId,
			message: {
				msg,
				vo,
			},
		});
		await this.agentNode.websocket.send(message);
	}
	
	// ----------------------------------------------------------------------
	async callClient(msg, vo) {
		const callId = String(this.nextCallId++);
		const pms = new Promise((resolve, reject) => {
			this.callMap.set(callId,{ resolve, reject });
		});
		
		const message = JSON.stringify({
			msg: "CallClient",
			sessionId: this.sessionId,
			callId,
			message: { msg, vo },
		});
		await this.agentNode.websocket.send(message);
		return pms;
	}
	
	// ----------------------------------------------------------------------
	async clientCallResult(callId, result) {
		const stub = this.callMap.get(callId);
		if (!stub) return;
		this.callMap.delete(callId);
		stub.resolve(result);
	}
	
	// ----------------------------------------------------------------------
	async clientCallError(callId, error) {
		const stub = this.callMap.get(callId);
		if (!stub) return;
		this.callMap.delete(callId);
		stub.reject(new Error(error));
	}
	
	//-----------------------------------------------------------------------
	async handleMessage(msg,vo){
		let handler;
		handler=this["WSMsg_"+msg];
		if(!handler){
			throw Error(`Session message handler for "${msg}" not found.`);
		}
		return await handler(vo);
	}
	
	//-----------------------------------------------------------------------
	async indentMore(){
		await this.callClient("IndentMore",{});
	}
	
	//-----------------------------------------------------------------------
	async indentLess(){
		await this.callClient("IndentLess",{});
	}
	
	//-----------------------------------------------------------------------
	async handleCall(msg,vo){
		let handler;
		handler=this["WSCall_"+msg];
		switch(msg) {
			case "AskUpward": {
				let fromAgent, askSeg, fakeAgent;
				fromAgent = this.callClientFromAgent;
				askSeg = this.callClientAskSeg;
				fakeAgent = {
					upperAgent: fromAgent,
					askUpwardSeg: askSeg
				};
				return await this.askUpward(fakeAgent,vo.prompt);
			}
		}
		if(!handler){
			throw Error(`Session call handler for "${msg}" not found.`);
		}
		return await handler(vo);
	}
	
	//-----------------------------------------------------------------------
	async loadAgent(fromAgent, path) {
		let agent = null;
		const agentDict=ChatSession.agentDict;
		//if (!path.startsWith("/")) {
		if (!pathLib.isAbsolute(path)) {
			if (!fromAgent) {
				path = pathLib.join(this.basePath, path);
			} else {
				path = pathLib.join(fromAgent.baseDir || this.basePath, path);
			}
			path = pathLib.resolve(path);
		}
		agent = agentDict[path];
		if (agent){
			return agent;
		}
		
		let entryPath = path;
		if (entryPath.startsWith("/@")) {
			entryPath = "../" + entryPath.slice(2);
		}
		// if(entryPath[0]!=="/") {
		if(!pathLib.isAbsolute(entryPath)) {
			if (!fromAgent) {
				entryPath = pathLib.join(this.basePath, entryPath);
			} else {
				entryPath = pathLib.join(fromAgent.baseDir || this.basePath, entryPath);
			}
			entryPath = pathLib.resolve(entryPath);
		}
		try {
			const module = await importModuleFromFile(entryPath);
			agent = module.default;
			agentDict[path] = agent;
			try{
				let code,pos,mark;
				code=await fsp.readFile(entryPath,"utf8");
				mark="/*Cody Project Doc*/";
				pos=code.indexOf(mark);
				if(pos>0){
					code=code.substring(pos+mark.length);
					code=code.replaceAll("\n//","\n");
					agent.sourceDef=JSON.parse(code);
				}
			}catch(e){
				//do nothing;
				agent.sourceDef=null;
			}
			return agent;
		} catch (e) {
			console.error(`Failed to load agent from ${path}: ${e.message}`);
			throw e;
		}
	}
	
	//-----------------------------------------------------------------------
	async runSeg(agent, segVO) {
		let result = null;
		let catchSeg = null;
		let input = segVO.input || segVO.result || "";
		let seg = segVO.seg;
		let oldSeg=this.curAISeg;
		
		if ("catchSeg" in segVO) {
			catchSeg = segVO.catchSeg;
		}
		
		try {
			while (seg) {
				const segAct = await this.logSegStart(agent, result || segVO);
				this.curAISeg=seg;
				if(seg instanceof Function){
					result = await seg(input);
				}else {
					result = await seg.exec(input);
				}
				this.curAISeg=oldSeg;
				await this.logSegEnd(agent, segAct, result);
				
				if (typeof(result)==="object" && "result" in result) {
					input = result.result;
				}
				
				if (result.seg) {
					seg = result.seg;
				} else {
					seg = null;
					result = input;
				}
				
				if (seg && result.catchSeg) {
					return await this.runSeg(agent, result);
				}
			}
		} catch (e) {
			console.error(`Caught error: [${e.name}]: ${e.message}`);
			console.error("Traceback (most recent call last):", e.stack);
			
			const info = `Caught error: ${e} at ${getErrorLocation(e)}`;
			if (catchSeg) {
				await this.logCatchError(agent,""+e);
				const catchSegVO = { input: info, seg: catchSeg ,preSeg:segVO.preSeg,outlet:segVO.catchlet};
				result = await this.runSeg(agent, catchSegVO);
			} else {
				throw e;
			}
		} finally {
			this.curAISeg=oldSeg;
		}
		return result;
	}
	
	//-----------------------------------------------------------------------
	async execAgent(agentPath, input, opts) {
		const fromAgent = this.curAgent;
		opts=opts||{};
		let agent,sourceDef;
		if (typeof agentPath === "function") {
			agent = agentPath;
		} else {
			agent = await this.loadAgent(fromAgent, agentPath);
		}
		sourceDef=agent.sourceDef;
		agent = await agent(this);
		agent.sourceDef=sourceDef;
		agent.agentFrameId=frameSeqId++;
		agent.upperAgent=opts.fromAgent||opts.upperAgent||fromAgent;
		agent.askUpwardSeg=opts.askUpwardSeg||null;
		
		this.curAgent=agent;
		
		if(!this.debugStarted){
			await this.startDebug(agent.url,sourceDef);
		}
		
		await this.logAgentStart(agent,input);
		const entry = await agent.execChat(input);
		let result = await this.runSeg(agent, entry);
		await this.logAgentEnd(agent,result);
		if(agent.endChat){
			result=await agent.endChat(result)||result;
		}
		this.curAgent = fromAgent; // Restore the previous agent
		return result;
	}
	
	//-----------------------------------------------------------------------
	//TODO: Never called?
	async execAISeg(agent, seg, input,fromSeg,fromOutlet) {
		const execVO = {
			seg:seg,
			input:input,
			preSeg:fromSeg,
			outlet:fromOutlet
		};
		return await this.runSeg(agent, execVO);
	}
	
	//-----------------------------------------------------------------------
	async runAISeg(agent, seg, input,fromSeg,fromOutlet) {
		const execVO = {
			seg:seg,
			input:input,
			preSeg:fromSeg,
			outlet:fromOutlet
		};
		return await this.runSeg(agent, execVO);
	}
	
	//-----------------------------------------------------------------------
	async askUpward(agent,prompt){
		let askAgent,askUpwardSeg,result;
		askAgent=agent;
		if(agent.name){
			let opts;
			opts={txtHeader:agent.showName||agent.name,icon:"/~/-tabos/shared/assets/ask.svg",iconSize:24,fontSize:12};
			await this.addChatText("assistant",prompt,opts);
		}
		while(askAgent){
			askUpwardSeg=askAgent.askUpwardSeg;
			askAgent=askAgent.upperAgent;
			if(askAgent && askUpwardSeg){
				break;
			}
		}
		if(askAgent && askUpwardSeg){
			if(askAgent==="$client"){
				//Call client to ask upward...
				result=await this.callClient("AskUpward",{prompt:prompt});
			}else{
				//Call response upper agent
				result=await this.runAISeg(askAgent,askUpwardSeg,prompt);
			}
		}else{
			//Can't find responsalbe upper agent,
			result=await this.askChatInput({type:"input",text:"",allowFile:true});
			if(typeof(result)==="string"){
				await this.addChatText("user",result);
			}else if(result.assets && result.prompt){
				await this.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
			}else{
				await this.addChatText("user",result.text||result.prompt||result);
			}
		}
		if(typeof(result)!=="string"){
			result=JSON.stringify(result);
		}
		return result;
	}
	
	//-----------------------------------------------------------------------
	async debugLog(log){
		console.log(log);
		await this.logSegLog(log,this.curAgent,this.curAISeg);
	}
	
	//-----------------------------------------------------------------------
	async logAgentStart(agent,input) {
		if (!this.agentNode) return;
		
		const log = {
			type: "StartAgent",
			agent: agent.jaxId,
			name:agent.name,
			url:agent.url,
			input:input,
			sourceDef:agent.sourceDef,
			frameId:agent.agentFrameId
		};
		if(await this.agentNode.sendDebugLog(log)){
			return;
		}
		//await this.sendToClient("DebugLog", log);
	}
	
	//-----------------------------------------------------------------------
	async logAgentEnd(agent,result) {
		if (!this.agentNode) return;
		const log = {
			type: "EndAgent",
			agent: agent.jaxId,
			name:agent.name,
			url:agent.url,
			frameId:agent.agentFrameId,
			result:result,
		};
		if(await this.agentNode.sendDebugLog(log)){
			return;
		}
		//await this.sendToClient("DebugLog", log);
	}
	
	//-----------------------------------------------------------------------
	async logSegStart(agent, segVO) {
		let agentNode=this.agentNode;
		if (!agentNode)
			return;
		
		const seg = segVO.seg || null;
		if (!seg)
			return;
		
		const segAct = {
			agent: agent.jaxId,
			name: seg.name || "seg",
			url: seg.url || "",
			jaxId: seg.jaxId || "",
			input: segVO.input || segVO.result,
			fromSeg: segVO.preSeg || null,
			fromOutlet: segVO.outlet || null,
			id: Symbol(), // 使用 Symbol 生成唯一 ID
		};
		
		const log = {
			type: "StartSeg",
			session: this.sessionId,
			seg: segAct,
		};
		if(await agentNode.sendDebugLog(log)){
			if(agentNode.slowMo){
				await sleep(500);
			}
			return segAct;
		}
		//await this.sendToClient("DebugLog", log);
		if(agentNode.slowMo){
			await sleep(500);
		}
		return segAct;
	}
	
	//-----------------------------------------------------------------------
	async logSegEnd(agent, segAct, result) {
		if (!this.agentNode) return;
		
		segAct["result"] = result||null;
		const log = {
			type: "EndSeg",
			session: this.sessionId,
			seg: segAct,
		};
		if(await this.agentNode.sendDebugLog(log)){
			return;
		}
		//await this.sendToClient("DebugLog", log);
	}
	
	async logCatchError(agent,error){
		if (!this.agentNode) return;
		const log = {
			type: "CatchError",
			agent: agent.jaxId,
			url:agent.url,
			frameId:agent.agentFrameId,
			error:""+error,
		};
		await this.agentNode.sendDebugLog(log);
	}
	
	//-----------------------------------------------------------------------
	async logLlmCall(codeURL,opts,messages,fromSeg,agent,seg){
		if(!this.agentNode){
			return;
		}
		let log={
			"type":"LlmCall",
			"session":this.sessionId,
			"code":codeURL,
			"options":opts,
			"messages":messages
		};
		if(agent && agent.jaxId){
			log.agent=agent.jaxId;
		}
		if(seg && seg.jaxId){
			log.seg={
				name:seg.name,
				url:seg.url,
				jaxId:seg.jaxId
			};
		}
		if(await this.agentNode.sendDebugLog(log)){
			return;
		}
		//await this.sendToClient("DebugLog", log);
	}
	
	//-----------------------------------------------------------------------
	async logLlmResult(codeURL,opts,messages,result,agent,seg){
		if(!this.agentNode){
			return;
		}
		let log={
			"type":"LlmResult",
			"session":this.sessionId,
			"code":codeURL,
			"options":opts,
			"messages":messages,
			"result":result
		};
		if(agent && agent.jaxId){
			log.agent=agent.jaxId;
		}
		if(seg && seg.jaxId){
			log.seg={
				name:seg.name,
				url:seg.url,
				jaxId:seg.jaxId
			};
		}
		if(await this.agentNode.sendDebugLog(log)){
			return;
		}
		//await this.sendToClient("DebugLog", log);
	}
	
	//-----------------------------------------------------------------------
	async logSegLog(message,agent,seg){
		if(!this.agentNode){
			return;
		}
		let log={
			"type":"DebugLog",
			"session":this.sessionId,
			"agent":agent?agent.jaxId:null,
			"seg":seg?seg.jaxId:null,
			"log":message
		};
		if(await this.agentNode.sendDebugLog(log)){
			return;
		}
		//await this.sendToClient("DebugLog", log);
	}
	
	//-----------------------------------------------------------------------
	async importFile(filePath) {
		const name = pathLib.basename(filePath).replace(/\.js$/, "");
		const module = await import(pathLib.resolve(filePath));
		return module.default || module;
	}
	
	//-----------------------------------------------------------------------
	async loadAPIFromFile(filePath) {
		if (!filePath.startsWith("/")) {
			filePath = pathLib.join(this.basePath, filePath);
			filePath = pathLib.resolve(filePath);
		}
		try {
			const module = await importFile(filePath);
			const apis = module.ChatAPI;
			return apis;
		} catch (e) {
			console.error(`Failed to load API from ${filePath}: ${e.message}`);
			return null;
		}
	}
	
	//-----------------------------------------------------------------------
	async loadAISegAPIs(list) {
		const allApis = [];
		for (const path of list) {
			console.log(`---loadAPI: ${path}`);
			const sub = await loadAPIFromFile(path);
			if (sub) {
				allApis.push(...sub);
			}
		}
		return allApis;
	}
	
	//-----------------------------------------------------------------------
	async readFile(path, outputFormat) {
		if (!path.startsWith("/")) {
			path = pathLib.join(this.basePath, path);
			path = pathLib.resolve(path);
		}
		const content = await fsp.readFile(path, outputFormat === "text" ? "utf8" : null);
		return content;
	}
	
	//-----------------------------------------------------------------------
	async writeFile(path, content, outputFormat) {
		if (!path.startsWith("/")) {
			path = pathLib.join(this.basePath, path);
			path = pathLib.resolve(path);
		}
		await fsp.writeFile(path, content, outputFormat === "text" ? "utf8" : null);
	}
	
	//-----------------------------------------------------------------------
	async saveHubTextFile(fileName, text) {
		const content = Buffer.from(text, "utf-8").toString("base64");
		return await this.saveHubFile(fileName, content);
	}
	
	//-----------------------------------------------------------------------
	async saveHubFile(fileName, content) {
		if (typeof content === "string") {
			if (content.startsWith("data:")) {
				const pos = content.indexOf(",");
				content = content.slice(pos + 1); // Extract base64 content after the comma
			}
		} else if (Buffer.isBuffer(content)) {
			content = content.toString("base64");
		} else {
			try {
				content = JSON.stringify(content);
			} catch {
				content = String(content);
			}
			content = Buffer.from(content, "utf-8").toString("base64");
		}
		
		const res = await this.callHub("AhFileSave", { fileName, data: content });
		if (res && res.code === 200) {
			await this.callClient("NewHubFile",res.fileName);
			return res.fileName;
		}
		const errorInfo = res ? `${res.code}: ${res.info}` : "Unknown error";
		throw new Error(`Save hub file ${fileName} failed: ${errorInfo}`);
	}
	
	//-----------------------------------------------------------------------
	async loadHubFile(fileName, outputFormat = "utf-8") {
		outputFormat = outputFormat.toLowerCase();
		const res = await this.callHub("AhFileLoad", { fileName });
		if (!res || res.code !== 200) {
			const errorInfo = res ? `${res.code}: ${res.info}` : "Unknown error";
			throw new Error(`Load hub file ${fileName} failed: ${errorInfo}`);
		}
		
		const decodedBytes = Buffer.from(res.data, "base64");
		switch (outputFormat) {
			case "utf-8":
			case "text":
			case "utf8":
				return decodedBytes.toString("utf-8");
			case "json":
				return JSON.parse(decodedBytes.toString("utf-8"));
			case "data":
			case "bytes":
				return decodedBytes;
			case "dataurl":
				const ext = pathLib.extname(fileName).toLowerCase();
				const mimeType = {
					".json": "application/json",
					".jpg": "image/jpeg",
					".jpeg": "image/jpeg",
					".png": "image/png",
					".txt": "text/plain",
				}[ext] || "application/octet-stream";
				return `data:${mimeType};base64,${res.data}`;
			default:
				return res.data;
		}
	}
	
	//-----------------------------------------------------------------------
	async getHubPath(fileName){
		if(fileName.startsWith("hub://")){
			fileName=fileName.substring("hub://".length);
		}
		const res = await this.callHub("AhFilePath", { fileName });
		if (!res || res.code !== 200) {
			const errorInfo = res ? `${res.code}: ${res.info}` : "Unknown error";
			throw new Error(`Load hub file ${fileName} failed: ${errorInfo}`);
		}
		return res.path;
	}
	
	//-----------------------------------------------------------------------
	async normURL(url) {
		if (url.startsWith("hub://")) {
			const fileName = url.slice("hub://".length);
			return await this.loadHubFile(fileName, "dataurl");
		}
		return url;
	}
	
	//-----------------------------------------------------------------------
	async addChatText(role, content, opts = {}) {
		if (this.agentNode) {
			const blockVO = {
				role,
				text: content,
				txtHeader:opts?.txtHeader,
				channel:opts?.channel,
			};
			if(!blockVO.txtHeader) {
				if (role !== "user" && role !== "log") {
					blockVO.txtHeader = this.agentNode.name;
				}
			}
			if (opts.image) blockVO.image = opts.image;
			if (opts.audio) blockVO.audio = opts.audio;
			await this.sendToClient("ChatBlock", blockVO);
		}
	}
	
	//-----------------------------------------------------------------------
	async resizeImage(dataURL, maxSize, imgFormat = "jpeg") {
		const imageData = Buffer.from(dataURL.split(",")[1], "base64");
		const metadata = await sharp(imageData).metadata();
		
		let { width: orgW, height: orgH } = metadata;
		let newW = orgW;
		let newH = orgH;
		
		if (orgW > maxSize) {
			newH = Math.floor((orgH * maxSize) / orgW);
			newW = maxSize;
		}
		if (newH > maxSize) {
			newW = Math.floor((newW * maxSize) / newH);
			newH = maxSize;
		}
		
		if (orgW <= maxSize && orgH <= maxSize) {
			return dataURL;
		}
		
		const resizedBuffer = await sharp(imageData)
			.resize(newW, newH)
			.toFormat(imgFormat.toLowerCase())
			.toBuffer();
		
		const resizedBase64 = resizedBuffer.toString("base64");
		return `data:image/${imgFormat.toLowerCase()};base64,${resizedBase64}`;
	}
	
	//-----------------------------------------------------------------------
	async askChatInput(vo) {
		const askVO = {
			...vo,
			role: vo.role || "assistant",
			prompt: vo.prompt || "Please input",
			initText: vo.initText || "",
			placeholder:vo.placeholder||"",
		};
		return await this.callClient("AskChatInput", askVO);
	}
	
	//-----------------------------------------------------------------------
	async callHub(msg, vo) {
		return await this.agentNode.callHub(msg, vo, this);
	}
	
	//-----------------------------------------------------------------------
	async callHubAI(opts, messages, waitBlk) {
		let res;
		const callVO = {
			platform: opts.platform || "OpenAI",
			model: opts.model||opts.mode || "gpt-4o-mini",
			temperature: opts.temperature || 0,
			max_tokens: opts.maxToken || 4096,
			messages,
			top_p: opts.topP || 1,
			presence_penalty: opts.prcP || 0,
			frequency_penalty: opts.fqcP || 0,
			response_format: opts.responseFormat || "text",
		};
		{
			let models=this.globalContext.models||{};
			let name=callVO.model;
			if(name[0]==="$"){
				name=name.substring(1);
				let vo=models[name];
				if(!vo){
					throw Error(`Can't find platform shortcut: ${name}`);
				}
				callVO.platform=vo.platform;
				callVO.model=vo.model;
			}
		}
		const seed = opts.seed;
		if (seed) {
			callVO.seed = seed;
		}
		
		const apis = opts.apis;
		if (apis) {
			callVO.functions = apis.functions;
			if (opts.parallelFunction) {
				callVO.parallelFunction = true;
			}
		}
		console.log(`Call AI: ${JSON.stringify(callVO)}`);
		console.log(callVO);
		res = await this.callHub("AICall", callVO);
		if (res.code !== 200) {
			throw new Error(`AIStreamCall failed: ${res.code}:${res.info}`);
		}
		return res.message;
	}

	//-----------------------------------------------------------------------
	async callHubLLM(opts, messages, waitBlk) {
		let res;
		const callVO = {
			platform: opts.platform || "OpenAI",
			model: opts.model||opts.mode || "gpt-4o-mini",
			temperature: opts.temperature || 0,
			max_tokens: opts.maxToken || 4096,
			messages,
			top_p: opts.topP || 1,
			presence_penalty: opts.prcP || 0,
			frequency_penalty: opts.fqcP || 0,
			response_format: opts.responseFormat || "text",
		};
		{
			let models=this.globalContext.models||{};
			let name=callVO.model;
			if(name[0]==="$"){
				name=name.substring(1);
				let vo=models[name];
				if(!vo){
					throw Error(`Can't find platform shortcut: ${name}`);
				}
				callVO.platform=vo.platform;
				callVO.model=vo.model;
			}
		}
		const seed = opts.seed;
		if (seed) {
			callVO.seed = seed;
		}
		
		const apis = opts.apis;
		if (apis) {
			callVO.functions = apis.functions;
			if (opts.parallelFunction) {
				callVO.parallelFunction = true;
			}
		}
		console.log(`Call LLM: ${JSON.stringify(callVO)}`);
		console.log(callVO);
		res = await this.callHub("AICallStream", callVO);
		if (res.code !== 200) {
			throw new Error(`AIStreamCall failed: ${res.code}:${res.info}`);
		}
		
		const streamId = res.streamId;
		const streamObj = {};
		while (!res.closed) {
			res = await this.callHub("readAIChatStream", { streamId });
			if (res.code !== 200) {
				break;
			}
			const content = res.message || "";
			streamObj.content = content;
			
			if (res.functionCall) {
				streamObj.functionCall = res.functionCall;
			}
			if (res.toolCalls) {
				streamObj.toolCalls = res.toolCalls;
			}
			if (res.inputTokens >= 0) {
				streamObj.inputTokens = res.inputTokens;
			}
			if (res.outputTokens >= 0) {
				streamObj.outputTokens = res.outputTokens;
			}
			
			await this.sendToClient("SetWaitBlockText", { block: waitBlk, text: content });
		}
		
		const content = streamObj.content;
		const functionCall = streamObj.functionCall;
		const toolCalls = streamObj.toolCalls;
		
		if (functionCall) {
			const name = functionCall.name;
			const stub = opts.apis.stubs[name];
			if (!stub) {
				throw new Error(`API Function: ${name} not found.`);
			}
			const func = stub.func;
			const args = functionCall.arguments;
			if (func) {
				const params = Object.keys(func);
				const filteredArgs = params.reduce((acc, key) => {
					if (key in args) acc[key] = args[key];
					return acc;
				}, {});
				const callResult = await func({ session: this, ...filteredArgs });
				messages.push({ role: "assistant", content: "", function_call: functionCall });
				messages.push({ role: "function", name, content: callResult });
				return await this.callHubLLM(opts, messages);
			} else {
				throw new Error(`Can't find function ${name}`);
			}
		} else if (toolCalls) {
			for (const toolCall of toolCalls) {
				const functionCall = toolCall.function;
				const name = functionCall.name;
				const stub = opts.apis.stubs[name];
				if (!stub) {
					throw new Error(`API Function: ${name} not found.`);
				}
				const func = stub.func;
				if (func) {
					const args = functionCall.arguments;
					const params = Object.keys(func);
					const filteredArgs = params.reduce((acc, key) => {
						if (key in args) acc[key] = args[key];
						return acc;
					}, {});
					const callResult = await func({ session: this, ...filteredArgs });
					messages.push({
						tool_call_id: toolCall.id,
						role: "tool",
						name,
						content: callResult,
					});
				} else {
					messages.push({
						tool_call_id: toolCall.id,
						role: "tool",
						name,
						content: "Can't find function",
					});
				}
			}
			return await this.callHubLLM(opts, messages);
		}
		return content;
	}
	
	//-----------------------------------------------------------------------
	async makeAICall(codeURL,opts,messages,fromSeg=false){
		const model2Platform = {
			"gpt-4o": "OpenAI",
			"gpt-4o-mini": "OpenAI",
			"gpt-3.5-turbo": "OpenAI",
			"gpt-3.5-turbo-16k": "OpenAI",
			"gpt-3.5-turbo-1106": "OpenAI",
			"gpt-4": "OpenAI",
			"gpt-4-32k": "OpenAI",
			"gpt-4-1106-preview": "OpenAI",
		};
		let model = opts.model || opts.mode || "gpt-4o-mini";
		let platform;
		{
			let models=this.globalContext.models||{};
			if(model[0]==="$"){
				model=model.substring(1);
				let vo=models[model];
				if(!vo){
					throw Error(`Can't find platform shortcut: ${name}`);
				}
				platform=vo.platform;
				model=vo.model;
			}else{
				platform= model2Platform[model] || opts.platform;
			}
		}
		await this.logLlmCall(codeURL,opts,messages,fromSeg,this.curAgent,this.curAISeg);
		let result=await this.callHubAI(opts, messages);
		await this.logLlmResult(codeURL,opts,messages,result,this.curAgent,this.curAISeg);
		return result;
	}
	
	//-----------------------------------------------------------------------
	async callSegLLM(codeURL, opts, messages, fromSeg) {
		const model2Platform = {
			"gpt-4o": "OpenAI",
			"gpt-4o-mini": "OpenAI",
			"gpt-3.5-turbo": "OpenAI",
			"gpt-3.5-turbo-16k": "OpenAI",
			"gpt-3.5-turbo-1106": "OpenAI",
			"gpt-4": "OpenAI",
			"gpt-4-32k": "OpenAI",
			"gpt-4-1106-preview": "OpenAI",
		};

		await this.logLlmCall(codeURL,opts,messages,fromSeg,this.curAgent,this.curAISeg);
		
		let model = opts.model || opts.mode || "gpt-4o-mini";
		let platform;
		{
			let models=this.globalContext.models||{};
			if(model[0]==="$"){
				model=model.substring(1);
				let vo=models[model];
				if(!vo){
					throw Error(`Can't find platform shortcut: ${name}`);
				}
				platform=vo.platform;
				model=vo.model;
			}else{
				platform= model2Platform[model] || opts.platform;
			}
		}
		
		let waitBlk = 0;
		if (this.agentNode) {
			waitBlk = await this.callClient("AddWaitBlock", { text: "..." });
		}
		
		try {
			if (platform === "OpenAI") {
				const openAI = setupOpenAI(this);
				if (!openAI) {
					let result;
					result=await this.callHubLLM(opts, messages, waitBlk);
					await this.logLlmResult(codeURL,opts,messages,result,this.curAgent,this.curAISeg);
					return result;
				}
				
				const useStream = opts.stream !== false;
				const temperature = opts.temperature || 1;

				let resFormat=opts.responseFormat;
				if(typeof(resFormat)!=="object"){
					resFormat=resFormat === "json_object" ? "json_object" : "text";
				}
				
				let completion;
				if (opts.apis) {
					const apis = opts.apis;
					const apiHash = {};
					const tools = apis.map((stub) => {
						apiHash[stub.def.name] = stub;
						return { type: "function", function: stub.def };
					});
					
					completion = await openAI.createChatCompletion({
						model,
						temperature,
						messages,
						tools,
						tool_choice: "auto",
						response_format:resFormat,
						stream: useStream,
					});
				} else {
					completion = await openAI.createChatCompletion({
						model,
						temperature,
						messages,
						response_format: resFormat,
						stream: useStream,
					});
				}
				
				if (useStream) {
					const content = [];
					const toolCalls=[];
					let refusal="";
					for await (const chunk of completion) {
						const delta = chunk.choices[0].delta;
						if (delta.content) content.push(delta.content);
						if (delta.tool_calls) {
							let srcList, tgtList, i, n, idx, srcStub, tgtStub, srcFunc, tgtFunc;
							srcList = delta.tool_calls;
							tgtList = toolCalls;
							n = srcList.length;
							for (i = 0; i < n; i++) {
								srcStub = srcList[i];
								idx = srcStub.index >= 0 ? srcStub.index : i;
								tgtStub = tgtList[idx];
								if (!tgtStub) {
									tgtStub = tgtList[idx] = {
										index: idx, id: "", type: "function",
										function: {
											name: "", arguments: ""
										}
									};
								}
								if ("index" in srcStub) {
									tgtStub.index = srcStub.index;
								}
								if ("id" in srcStub) {
									tgtStub.id += srcStub.id;
								}
								if ("type" in srcStub) {
									tgtStub.type = "function";//srcStub.type;
								}
								srcFunc = srcStub.function;
								tgtFunc = tgtStub.function;
								if (srcFunc) {
									tgtFunc.name += srcFunc.name || "";
									tgtFunc["arguments"] += srcFunc["arguments"] || "";
								}
							}
						}
						if(delta.refusal){
							refusal+=delta.refusal;
						}
						if (this.agentNode) {
							await this.sendToClient("SetWaitBlockText", {
								block: waitBlk,
								text: delta.content || "...",
							});
						}
					}
					let result=content.join("");
					if(refusal){
						throw Error(`AI refusal: ${refusal}`);
					}
					await this.logLlmResult(codeURL,opts,messages,result,this.curAgent,this.curAISeg);
					return result;
				} else {
					let refusal=completion.choices[0].message.refusal;
					if(refusal){
						throw Error(`AI refusal: ${refusal}`);
					}
					let result=completion.choices[0].message.content;
					await this.logLlmResult(codeURL,opts,messages,result,this.curAgent,this.curAISeg);
					return result;
				}
			} else {
				let result=await this.callHubLLM(opts, messages, waitBlk);
				await this.logLlmResult(codeURL,opts,messages,result,this.curAgent,this.curAISeg);
				return result;
			}
		} finally {
			if (this.agentNode) {
				await this.sendToClient("RemoveWaitBlock", { block: waitBlk });
			}
		}
	}
	
	
	//-----------------------------------------------------------------------
	async callAgent(agentNode,path,input,opts){
		if(agentNode) {//This is a remote chat
			if(agentNode==="$client"){
				let oldFromAgent,oldAskSeg,result;
				oldFromAgent=this.callClientFromAgent;
				oldAskSeg=this.callClientAskSeg;
				this.callClientFromAgent=opts.fromAgent;
				this.callClientAskSeg=opts.askUpwardSeg;
				try{
					result=await this.callClient("CallAgent",{agent:path,arg:input});
				}finally {
					this.callClientFromAgent=oldFromAgent;
					this.callClientAskSeg=oldAskSeg;
				}
				return result;
			}else{
				return await RemoteSession.exec(this,agentNode,path,input,opts);
			}
		}else{
			return await this.execAgent(path, input,opts);
		}
	}
	
	//-----------------------------------------------------------------------
	async pipeChat(path, input, hideInter = false) {
		return await this.execAgent(path, input);
	}
	
	//-----------------------------------------------------------------------
	async webCall(vo, fromAgent, timeout) {
		const url = vo.url;
		const method = vo.method || "GET";
		const headers = vo.headers || {};
		const argMode = vo.argMode || null;
		
		let response;
		
		if (argMode === "JSON") {
			headers["Content-Type"] = "application/json";
			response = await fetch(url, {
				method,
				headers,
				body: JSON.stringify(vo.json),
			});
		} else if (argMode === "TEXT") {
			headers["Content-Type"] = "text/plain";
			response = await fetch(url, {
				method,
				headers,
				body: vo.text,
			});
		} else if (argMode === "DATA") {
			headers["Content-Type"] = "application/octet-stream";
			response = await fetch(url, {
				method,
				headers,
				body: vo.data,
			});
		} else {
			response = await fetch(url, { method, headers });
		}
		
		const responseBody = await response.text();
		if (response.ok) {
			return { code: 200, data: responseBody };
		} else {
			return { code: response.status, info: responseBody };
		}
	}
	
	//-----------------------------------------------------------------------
	async askUserRaw(vo) {
		return await this.callClient("AskUserRaw", vo);
	}
	
	//-----------------------------------------------------------------------
	async askUserDlg(vo) {
		return await this.callClient("AskUserDlg", vo);
	}
	
	//-----------------------------------------------------------------------
	async askUserView(vo) {
		return await this.callClient("AskUserView", vo);
	}

	//-----------------------------------------------------------------------
	async showWait(text) {
		return await this.callClient("AddWaitBlock", { text: text || "..." });
	}
	
	//-----------------------------------------------------------------------
	async setWaitText(waitBlk, text) {
		await this.sendToClient("SetWaitBlockText", { block: waitBlk, text });
	}
	
	//-----------------------------------------------------------------------
	async removeWait(waitBlk) {
		await this.sendToClient("RemoveWaitBlock", { block: waitBlk });
	}	// Additional methods would follow the same pattern
	
	//-----------------------------------------------------------------------
	regTerminal(term,ownBySession){
		if(ownBySession!==false) {
			this.termMap.set(term.sessionId, term);
		}
		this.agentNode.regTerminal(term);
	}
	
	//-----------------------------------------------------------------------
	async closeTerminals(){
		let terms=this.termMap.values();
		for(let term of terms){
			await term.close();
		}
		this.termMap.clear();
	}

	//-----------------------------------------------------------------------
	arrayBufferToDataURL(fileName,buf){
		let ext,result;
		if(fileName){
			ext=pathLib.extname(fileName);
		}
		result=buf.toString("base64");
		//result=Base64.encode(buf);
		switch(ext){
			case ".jpg":
				result="data:image/jpeg;base64,"+result;
				break;
			case ".png":
				result="data:image/png;base64,"+result;
				break;
			case ".txt":
				result="data:text/plain;base64,"+result;
				break;
			case ".json":
				result="data:text/json;base64,"+result;
				break;
			case '.pdf':
				result="data:application/pdf;base64,"+result;
				break;
			default:
				result="data:application/octet-stream;base64,"+result;
				break;
		}
		return result;
	}
}

export default ChatSession;
// Exports:
export { ChatSession, trimJSON };