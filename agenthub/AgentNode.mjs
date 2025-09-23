import pathLib from 'path';
import { fileURLToPath } from "node:url";
import { promises as fsp } from 'fs';
import { createServer } from 'http';
import WebSocket, { WebSocketServer }from 'ws';
import ChatSession from './ChatSession.mjs';
import net from 'net';

const currentPath = pathLib.dirname(fileURLToPath(import.meta.url));

function getErrorLocation(e) {
	if(e && e.stack) {
		const stack = e.stack.split('\n');
		return stack[stack.length - 1];
	}
	return "NA";
}

async function isPortInUse(port, host = '127.0.0.1') {
	return new Promise((resolve) => {
		const server = net.createServer();
		
		server.once('error', (err) => {
			resolve(err.code === 'EADDRINUSE');
		});
		
		server.once('listening', () => {
			server.close(() => resolve(false));
		});
		
		server.listen(port, host);
	});
}

async function readJSON(filePath) {
	try {
		const data = await fsp.readFile(filePath, 'utf8');
		return JSON.parse(data);
	} catch (e) {
		if (e.code === 'ENOENT') {
			console.log(`File ${filePath} not found`);
		} else if (e instanceof SyntaxError) {
			console.log(`JSON ${filePath} parse error: ${e.message}`);
		} else {
			console.log(`Error: ${e.message}`);
		}
		return {};
	}
}
function safeJSON(obj,deep=0,maxDeep=3){
	let text,id;
	try{
		text=JSON.stringify(obj);
	}catch (err){
		let val,tmp,replaced;
		replaced={};
		for(id in obj){
			val=obj[id];
			if(typeof(val)==="object") {
				try {
					tmp = JSON.stringify(val);
				} catch (err) {
					replaced[id]=val;
					if(deep>=maxDeep){
						obj[id]="[Object]";
					}else{
						tmp=safeJSON(obj,deep+1,maxDeep);
						obj[id]=JSON.parse(tmp);
					}
				}
			}
		}
		try{
			text=JSON.stringify(obj);
			Object.assign(obj,replaced);
		}catch (err){
			text='{}';
		}
	}
	return text;
}

let hubPath;
let hubConfig;
//***************************************************************************
//AgentNode:
//***************************************************************************
let AgentNode,agentNode;
{
	const AH_AgentDir=process.env.AGENT_HUB_AGENTDIR||"agents";
	AgentNode=function(path,host,name){
		let jsonPath
		//path = path.startsWith('/') ? path : pathLib.join(hubPath, path);
		path = pathLib.isAbsolute(path) ? path : pathLib.join(hubPath, path);
		// if(path[0]!=="/"){
		if(!pathLib.isAbsolute(path)){
			path=pathLib.join(currentPath,"../",path);
		}
		path=pathLib.normalize(path);
		if(path.endsWith(".json")){
			jsonPath=path;
			path=pathLib.dirname(path);
		}else{
			jsonPath=pathLib.join(path,"agent.json");
		}
		this.path =path;
		this.configPath=jsonPath;
		this.hubPath = hubPath;
		this.name = name || null;
		this.host = host;
		this.address=null;
		this.connected = false;
		this.websocket = null;
		this.agent = null;
		this.sessionMap = new Map();
		this.nodeJSON = null;
		this.hubJSON = hubConfig;
		this.devKey=null;
		this.callMap = new Map();
		this.nextCallId = 0;
		this.callHandlers = new Map();
		this.workload = 0;
		
		this.debugStepRun = false;
		this.debugClients=[];
		this.debugConnected = false;
		this.debugServer = null;
		this.slowMo=false;
		this.debugPort=-1;
		
		this.termMap=new Map();
	}
	agentNode=AgentNode.prototype={};
	
	//-----------------------------------------------------------------------
	AgentNode.setupPath=async function(){
		hubPath=process.env.AGENT_HUB_AGENTDIR||pathLib.join(currentPath,"../agents");
		if(hubPath[0]!=="/"){
			hubPath=pathLib.join(currentPath,"../",hubPath);
		}
		hubConfig=await readJSON(pathLib.join(currentPath, "../agents/agenthub.json"));
	};
	
	//-----------------------------------------------------------------------
	agentNode.start = async function () {
		const jsonPath = this.configPath;
		try {
			const data = await fsp.readFile(jsonPath, 'utf8');
			this.nodeJSON = JSON.parse(data);
			this.nodeJSON.path = this.nodeJSON.path || this.path;
			console.log("JSON 数据:", this.nodeJSON);
		} catch {
			this.nodeJSON = {
				name: this.name || this.path,
				path: this.path,
				description: "Agent node"
			};
		}
		
		this.name = this.nodeJSON.name || this.name;
		this.host = this.host || hubConfig.host;
		this.devKey= this.nodeJSON.devKey||this.hubJSON.devKey||null;
		this.address=this.nodeJSON.address||this.address;
		
		try {
			await this.startDebug();
		}catch(err){
			console.warn(`Agent ${this.name} start debug failed: ${err}`);
		}
		
		this.websocket = new WebSocket(this.host);
		this.websocket.on('open', () => this.onOpen());
		this.websocket.on('message', (message) => this.onMessage(message));
		this.websocket.on('close', () => this.onClose());
	};
	
	//-----------------------------------------------------------------------
	agentNode.onOpen = async function () {
		const message = JSON.stringify({
			msg: "CONNECT",
			name: this.name,
			selector: "RegisterAgentNode",
			info: this.nodeJSON
		});
		this.websocket.send(message);
	};
	
	//-----------------------------------------------------------------------
	agentNode.onMessage = async function (message) {
		try {
			message = JSON.parse(message);
		} catch {
			console.log(`Parse message error, message: ${message}`);
			return;
		}
		
		const msgCode = message.msg;
		if (msgCode !== "State") {
			console.log(`Got websocket message: ${JSON.stringify(message)}`);
		}
		
		if (!this.connected) {
			if (msgCode === 'CONNECTED') {
				await this.onConnect();
			}
		} else {
			switch (msgCode) {
				case 'CreateSession':
					await this.createSession(message.sessionId, message.options || {});
					break;
				case 'State':
					this.websocket.send(JSON.stringify({ msg: "State", workload: this.workload }));
					break;
				case 'StopNode':
					await this.websocket.close(1000);
					process.exit(0);
					break;
				case 'RestartNode':
					this.websocket.close(1000);
					//TODO: Code this:
					break;
				case 'Message':{
					await this.handleMessage(message);
					break;
				}
				case 'Call': {
					let result;
					try {
						result = await this.handleCall(message);
						this.websocket.send(JSON.stringify({ msg: "CallResult", result:result,callId:message.callId,session:message.session,sessionId:message.sessionId}));
					}catch (err){
						this.websocket.send(JSON.stringify({ msg: "CallResult", error:""+err,callId:message.callId,session:message.session,sessionId:message.sessionId}));
					}
					break;
				}
				case 'ExecAgent':
					await this.execAgentMessage(message);
					break;
				case 'CallResult':
					await this.callResult(message);
					break;
				case 'XTermData':
					await this.writeXTermData(message);
					break;
			}
		}
	};
	
	//-----------------------------------------------------------------------
	agentNode.onConnect = async function () {
		if (!this.connected) {
			this.connected = true;
		}
	};
	
	//-----------------------------------------------------------------------
	agentNode.onClose = function () {
		this.connected = false;
		console.log("Will close agent.");
		return true;
	};
	
	//-----------------------------------------------------------------------
	agentNode.createSession = async function (sessionId, options) {
		if (!this.connected) return false;
		const ssn = new ChatSession(this.path, this, sessionId, options);
		this.sessionMap.set(sessionId, ssn);
		this.websocket.send(JSON.stringify({ msg: "SessionReady", session: sessionId }));
	};
	
	//-----------------------------------------------------------------------
	agentNode.endSession=async function(session){
		const sessionId=session.sessionId;
		this.sessionMap.delete(sessionId);
		this.websocket.send(JSON.stringify({ msg: "EndSession", session: sessionId }));
		
		//Release resources alloced by session:
		session.closeTerminals();
		let term=this.termMap.get(sessionId);
		if(term){
			this.termMap.delete(sessionId);
			//TODO: Code this:
		}
	};
	
	//-----------------------------------------------------------------------
	agentNode.execAgentMessage = async function (message) {
		const sessionId = message.sessionId;
		const agentPath = message.agent;
		if (!agentPath) {
			this.websocket.send(JSON.stringify({ msg: "EndExecAgent", session: sessionId, error: "Error: missing agent name/path" }));
			return;
		}
		
		try {
			const result = await this.execAgent(sessionId, agentPath, message.prompt || "");
			this.websocket.send(safeJSON({ msg: "EndExecAgent", session: sessionId, result }));
		} catch (e) {
			console.log(`ExecAgent error: ${e.message}. At: ${getErrorLocation(e)}`);
			console.error(e);
			this.websocket.send(JSON.stringify({ msg: "EndExecAgent", session: sessionId, error: `Error: ${e}. At: ${getErrorLocation(e)}` }));
		}
	};
	
	//-----------------------------------------------------------------------
	agentNode.execAgent = async function (sessionId, path, prompt) {
		const ssn = this.sessionMap.get(sessionId); // 使用 Map 的 get 方法
		if (!ssn) return false;
		const result = await ssn.execAgent(path, prompt,{fromAgent:"$client",askUpwardSeg:true});
		return result;
	};
	
	
	//-----------------------------------------------------------------------
	agentNode.handleMessage=async function(message){
		const sessionId=message.session||message.sessionId;
		const callMsg = message.message?.msg;
		const callVO = message.message?.vo;
		
		if(sessionId){
			let session;
			session=this.sessionMap.get(sessionId);
			if(!session){
				throw `Session "sessionId" not found.`;
			}
			return await session.handleMessage(callMsg,callVO);
		}else{
			let handler = this.callHandlers.get(callMsg);
			if(handler){
				try {
					handler(callVO, this);
				}catch(err){
					//Do nothing
				}
			}else{
				handler=this["WSMsg_"+callMsg];
				if(handler){
					try {
						handler.call(this,callVO);
					}catch(err){
						//Do nothing
					}
				}else {
					console.warn(`AgentNode[${this.name}] can't find message handler for: "${callMsg}"`);
				}
			}
		}
	};
	
	//-----------------------------------------------------------------------
	agentNode.handleCall = async function (message) {
		const sessionId=message.session||message.sessionId;
		const callMsg = message.message?.msg;
		const callVO = message.message?.vo;
		
		if(sessionId){
			let session;
			session=this.sessionMap.get(sessionId);
			if(!session){
				throw `Session "sessionId" not found.`;
			}
			return await session.handleCall(callMsg,callVO);
		}
		
		if (callMsg === 'State') {
			return { workload: this.workload };
		}
		
		if (this.callHandlers.has(callMsg)) {
			const handler = this.callHandlers.get(callMsg);
			return handler(callVO);
		} else {
			throw new Error(`No call handler for '${callMsg}'.`);
		}
	};
	
	//-----------------------------------------------------------------------
	agentNode.callResult = async function (message) {
		const callId = message.callId;
		const sessionId= message.session||message.sessionId;
		if(sessionId){
			let session=this.sessionMap.get(sessionId);
			if(session){
				if(message.error){
					await session.clientCallError(callId,message.error);
				}else {
					await session.clientCallResult(callId,message.result);
				}
			}
		}else if(this.callMap.has(callId)) {
			const stub = this.callMap.get(callId);
			if (message.error) {
				stub.reject(message.error);
			} else {
				stub.resolve(message.result);
			}
			this.callMap.delete(callId);
		}
	};
	
	//-----------------------------------------------------------------------
	agentNode.callHub = async function (msg, vo, session) {
		const callId = String(this.nextCallId++);
		return new Promise((resolve, reject) => {
			this.callMap.set(callId, { resolve, reject });
			let message = {
				msg: "CallHub",
				callId,
				message: { msg, vo }
			};
			if(session){
				message.session=session.sessionId;
			}
			if(this.devKey){
				message.devKey=this.devKey;
			}
			message=JSON.stringify(message);
			this.websocket.send(message);
		});
	};
	
	//-----------------------------------------------------------------------
	agentNode.sendToHub=async function(msg,vo,session){
		let message = {
			msg: msg,
			message: vo
		};
		if(session){
			message.session=session.sessionId;
		}
		if(this.devKey){
			message.devKey=this.devKey;
		}
		message=JSON.stringify(message);
		this.websocket.send(message);
	};
	
	//-----------------------------------------------------------------------
	agentNode.hubCallResult = async function (callId, result) {
		const stub = this.callMap.get(callId);
		if (!stub) return;
		stub.resolve(result);
		this.callMap.delete(callId);
	};
	
	//-----------------------------------------------------------------------
	agentNode.hubCallReject = async function (callId, error) {
		const stub = this.callMap.get(callId);
		if (!stub) return;
		stub.reject(error);
		this.callMap.delete(callId);
	};
	
	
	//-----------------------------------------------------------------------
	async function startWSServer(port){
		return new Promise((resolve,reject)=>{
			let server=createServer();
			let wss=new WebSocketServer({server:server,maxPayload: 1024 * 1024 * 100 });
			wss.on('error', (err) => {
				resolve(null);
				console.log(`Debug port ${port} is in use.`);
			});
			server.listen(port,()=>{
				console.log(`Debug port ${port} is listening.`);
				resolve(wss);
			});
		});
	}
	
	//-----------------------------------------------------------------------
	agentNode.startDebug=async function() {
		const handler = async (ws, req) => {
			console.log('Debug client connected');
			
			this.debugConnected = true;
			this.debugClients.push(ws);
			
			ws.on('message', async (message) => {
				try {
					console.log(`Debug port received: ${message}`);
					const parsedMessage = JSON.parse(message);
					const cmd = parsedMessage.cmd;
					
					//TODO: apply these to session?
					if (cmd === 'StepRunOn') {
						ws.debugStepRun = true;
						await ws.send(JSON.stringify({ type: 'StepRunOn' }));
					} else if (cmd === 'StepRunOff') {
						ws.debugStepRun = false;
						if (ws.debugStepTask) {
							let callback=ws.debugStepCallback;
							ws.debugStepTask = null;
							if(callback) {
								ws.debugStepCallback=null;
								callback(true);
							}
						}
						await ws.send(JSON.stringify({ type: 'StepRunOff' }));
					} else if (cmd === 'RunStep') {
						if (ws.debugStepTask) {
							let callback=ws.debugStepCallback;
							ws.debugStepTask = null;
							if(callback) {
								ws.debugStepCallback=null;
								callback(true);
							}
							await ws.send(JSON.stringify({ type: 'StepRun' }));
						}
					} else if (cmd === 'SlowMo') {
						this.slowMo=!!parsedMessage.enable;
					}
				} catch (err) {
					console.error(err);
				}
			});
			
			ws.on('close', () => {
				let idx;
				console.log('Client disconnected');
				if (ws.debugStepTask) {
					let callback=ws.debugStepCallback;
					ws.debugStepTask = null;
					if(callback) {
						ws.debugStepCallback=null;
						callback(true);
					}
				}
				idx=this.debugClients.indexOf(ws);
				if(idx>=0) {
					this.debugClients.splice(idx,1);
					if(!this.debugClients.length){
						this.debugConnected=false;
					}
				}
				
			});
		};
		
		let port = this.nodeJSON.debugPort || 5001;
		let portError=false;
		let debugServer=null;
		do {
			debugServer=await startWSServer(port);
			if(debugServer){
				break;
			}
			console.log(`Port ${port} is used.`);
			port+=1;
		}while(true);
		this.debugPort=port;
		this.debugServer = debugServer;//new WebSocketServer({ port, maxPayload: 1024 * 1024 * 10 });
		this.debugServer.on('connection', handler);
		console.log(`Debug WebSocket server started at port: ${port}`);
		this.debugServer.on('error', (err) => {
			console.log(`Agent ${this.name} start debug error: ${err}`);
		});
	};
	
	//-----------------------------------------------------------------------
	agentNode.sendDebugLog=async function(log) {
		try {
			const logType = log.type;
			const serializedLog = safeJSON(log);
			for(let ws of this.debugClients) {
				await ws.send(serializedLog);
				if (logType === 'StartSeg' && ws.debugStepRun) {
					await ws.send(JSON.stringify({ type: 'StepPaused' }));
					ws.debugStepTask = new Promise((resolve) => {
						ws.debugStepCallback = resolve;
					});
					await ws.debugStepTask;
				}
			}
			return true;
		} catch (err) {
			console.error(err);
		}
	};
	
	//-----------------------------------------------------------------------
	agentNode.regTerminal=function(term){
		this.termMap.set(term.sessionId,term);
	};
	
	//-----------------------------------------------------------------------
	agentNode.writeXTermData=async function(message){
		let sessionId,msgVO,term;
		sessionId=message.session||message.sessionId;
		term=this.termMap.get(sessionId);
		if(!term){
			return;
		}
		term.write(message.data);
	};
}

export default AgentNode;
export {AgentNode}