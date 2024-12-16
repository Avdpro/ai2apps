import { promises as fsp } from 'fs';
import pathLib from "path";
import sharp from "sharp";
import OpenAI from "openai";

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
		let startIdx = inputString.indexOf("{");
		if (startIdx === -1) return null;
		
		const decoder = new JSONDecoder();
		while (startIdx < inputString.length) {
			try {
				const { value } = decoder.decode(inputString.slice(startIdx));
				return value;
			} catch {
				startIdx = inputString.indexOf("{", startIdx + 1);
				if (startIdx === -1) break;
			}
		}
	} catch {
		return null;
	}
	return null;
}

// *****************************************************************************
async function importModuleFromFile(filePath) {
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

class ChatSession {
	static basePath = null;
	static curAgent = null;
	static curPath = null;
	static agentDict = {};
	static globalContext = {};
	
	constructor(basePath, node = null, sessionId = null, options = {}) {
		this.basePath = basePath;
		this.curPath = null;
		this.agentNode = node;
		this.sessionId = sessionId;
		this.nextCallId = 0;
		this.callMap = new Map();
		this.version = "0.0.2";
		this.curAgent = null;
		this.options = options || {};
		this.language = this.options.language || "CN";
		this.globalContext=options.globalContext||{};
	}
	
	// -------------------------------------------------------------------------
	// Show version:
	showVersion() {
		console.log("ChatSession 0.02");
	}
	
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
	
	// -------------------------------------------------------------------------
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
	
	// -------------------------------------------------------------------------
	async clientCallResult(callId, result) {
		const stub = this.callMap.get(callId);
		if (!stub) return;
		this.callMap.delete(callId);
		stub.resolve(result);
	}
	
	// -------------------------------------------------------------------------
	async clientCallError(callId, error) {
		const stub = this.callMap.get(callId);
		if (!stub) return;
		this.callMap.delete(callId);
		stub.reject(new Error(error));
	}
	
	//-----------------------------------------------------------------------
	async loadAgent(fromAgent, path) {
		let agent = null;
		const agentDict=ChatSession.agentDict;
		if (!path.startsWith("/")) {
			if (!fromAgent) {
				path = pathLib.join(this.basePath, path);
			} else {
				path = pathLib.join(fromAgent.baseDir || this.basePath, path);
			}
			path = pathLib.resolve(path);
		}
		agent = agentDict[path];
		if (agent) return agent;
		
		let entryPath = path;
		if (entryPath.startsWith("/@")) {
			entryPath = "../" + entryPath.slice(2);
		}
		if(entryPath[0]!=="/") {
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
		
		if ("catchSeg" in segVO) {
			catchSeg = segVO.catchSeg;
		}
		
		try {
			while (seg) {
				const segAct = await this.logSegStart(agent, result || segVO);
				if(seg instanceof Function){
					result = await seg(input);
				}else {
					result = await seg.exec(input);
				}
				await this.logSegEnd(agent, segAct, result);
				
				if (result.result) {
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
				const catchSegVO = { input: info, seg: catchSeg };
				result = await this.runSeg(agent, catchSegVO);
			} else {
				throw e;
			}
		}
		return result;
	}
	
	//-----------------------------------------------------------------------
	async execAgent(agentPath, input) {
		const fromAgent = this.curAgent;
		
		let agent;
		if (typeof agentPath === "function") {
			agent = agentPath;
		} else {
			agent = await this.loadAgent(fromAgent, agentPath);
		}
		
		agent = await agent(this);
		
		await this.logAgentStart(agent,input);
		const entry = await agent.execChat(input);
		const result = await this.runSeg(agent, entry);
		await this.logAgentEnd(agent,result);
		this.curAgent = fromAgent; // Restore the previous agent
		return result;
	}
	
	//-----------------------------------------------------------------------
	async execAISeg(agent, seg, input) {
		const execVO = { seg, input };
		return await this.runSeg(agent, execVO);
	}
	
	//-----------------------------------------------------------------------
	async logAgentStart(agent,input) {
		if (!this.agentNode) return;
		
		const log = {
			type: "StartAgent",
			agent: agent.jaxId,
			name:agent.name,
			url:agent.url,
			input:input
		};
		if(await this.agentNode.sendDebugLog(log)){
			return;
		}
		await this.sendToClient("DebugLog", log);
	}
	
	//-----------------------------------------------------------------------
	async logAgentEnd(agent,result) {
		if (!this.agentNode) return;
		const log = {
			type: "EndAgent",
			agent: agent.jaxId,
			name:agent.name,
			url:agent.url,
			result:result
		};
		if(await this.agentNode.sendDebugLog(log)){
			return;
		}
		await this.sendToClient("DebugLog", log);
	}
	
	//-----------------------------------------------------------------------
	async logSegStart(agent, segVO) {
		if (!this.agentNode) return;
		
		const seg = segVO.seg || null;
		if (!seg) return;
		
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
		if(await this.agentNode.sendDebugLog(log)){
			return segAct;
		}
		await this.sendToClient("DebugLog", log);
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
		await this.sendToClient("DebugLog", log);
	}
	
	//-----------------------------------------------------------------------
	async logLlmCall(codeURL,opts,messages){
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
		if(await this.agentNode.sendDebugLog(log)){
			return;
		}
		await this.sendToClient("DebugLog", log);
	}
	
	//-----------------------------------------------------------------------
	async logLlmResult(codeURL,opts,messages,result){
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
		if(await this.agentNode.sendDebugLog(log)){
			return;
		}
		await this.sendToClient("DebugLog", log);
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
			};
			if (role !== "user" && role !== "log") {
				blockVO.txtHeader = this.agentNode.name;
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
			role: vo.role || "assistant",
			prompt: vo.prompt || "Please input",
			initText: vo.initText || "",
		};
		return await this.callClient("AskChatInput", askVO);
	}
	
	//-----------------------------------------------------------------------
	async callHub(msg, vo) {
		return await this.agentNode.callHub(msg, vo, this);
	}
	
	//-----------------------------------------------------------------------
	async callHubLLM(opts, messages, waitBlk) {
		let res;
		const callVO = {
			platform: opts.platform || "OpenAI",
			model: opts.model || "gpt-4o",
			temperature: opts.temperature || 0,
			max_tokens: opts.maxToken || 4096,
			messages,
			top_p: opts.topP || 1,
			presence_penalty: opts.prcP || 0,
			frequency_penalty: opts.fqcP || 0,
			response_format: opts.responseFormat || "text",
		};
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

		await this.logLlmCall(codeURL,opts,messages);
		
		const model = opts.model || opts.mode || "gpt-4o-mini";
		const platform = model2Platform[model] || opts.platform;
		
		let waitBlk = 0;
		if (this.agentNode) {
			waitBlk = await this.callClient("AddWaitBlock", { text: "..." });
		}
		
		try {
			if (platform === "OpenAI") {
				const openAI = setupOpenAI(this);
				if (!openAI) {
					return await this.callHubLLM(opts, messages, waitBlk);
				}
				
				const useStream = opts.stream !== false;
				const temperature = opts.temperature || 1;
				
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
						response_format: opts.responseFormat === "json_object" ? "json_object" : "text",
						stream: useStream,
					});
				} else {
					completion = await openAI.createChatCompletion({
						model,
						temperature,
						messages,
						response_format: opts.responseFormat === "json_object" ? "json_object" : "text",
						stream: useStream,
					});
				}
				
				if (useStream) {
					const content = [];
					for await (const chunk of completion) {
						const delta = chunk.choices[0].delta;
						if (delta.content) content.push(delta.content);
						if (this.agentNode) {
							await this.sendToClient("SetWaitBlockText", {
								block: waitBlk,
								text: delta.content || "...",
							});
						}
					}
					let result=content.join("");
					await this.logLlmResult(codeURL,opts,messages,result);
					return result;
				} else {
					let result=completion.choices[0].message.content;
					await this.logLlmResult(codeURL,opts,messages,result);
					return result;
				}
			} else {
				let result=await this.callHubLLM(opts, messages, waitBlk);
				await this.logLlmResult(codeURL,opts,messages,result);
				return result;
			}
		} finally {
			if (this.agentNode) {
				await this.sendToClient("RemoveWaitBlock", { block: waitBlk });
			}
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
}

export default ChatSession;
// Exports:
export { ChatSession, trimJSON };