import pathLib from 'path';
import { promises as fsp } from 'fs';
import WebSocket, { WebSocketServer }from 'ws';
import ChatSession from './ChatSession.mjs';

const currentPath = pathLib.dirname(new URL(import.meta.url).pathname);

function getErrorLocation(e) {
	if(e && e.stack) {
		const stack = e.stack.split('\n');
		return stack[stack.length - 1];
	}
	return "NA";
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

const hubPath = process.env.AGENT_HUB_AGENTDIR||"agents";
const hubConfig = await readJSON(pathLib.join(currentPath, "../agents/agenthub.json"));

//***************************************************************************
//AgentNode:
//***************************************************************************
let AgentNode,agentNode;
{
	const AH_AgentDir=process.env.AGENT_HUB_AGENTDIR||"agents";
	AgentNode=function(path,host,name){
		let jsonPath
		path = path.startsWith('/') ? path : pathLib.join(hubPath, path);
		if(path[0]!=="/"){
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
		this.wsDebug = null;
		this.debugConnected = false;
		this.debugStepTask = null;
		this.debugServer = null;
		
	}
	agentNode=AgentNode.prototype={};
	
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
				case 'Call':
					await this.handleCallMessage(message);
					break;
				case 'ExecAgent':
					await this.execAgentMessage(message);
					break;
				case 'CallResult':
					await this.callResult(message);
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
	agentNode.execAgentMessage = async function (message) {
		const sessionId = message.sessionId;
		const agentPath = message.agent;
		if (!agentPath) {
			this.websocket.send(JSON.stringify({ msg: "EndExecAgent", session: sessionId, error: "Error: missing agent name/path" }));
			return;
		}
		
		try {
			const result = await this.execAgent(sessionId, agentPath, message.prompt || "");
			this.websocket.send(JSON.stringify({ msg: "EndExecAgent", session: sessionId, result }));
		} catch (e) {
			console.log(`ExecAgent error: ${e.message}. At: ${getErrorLocation(e)}`);
			console.error(e);
			this.websocket.send(JSON.stringify({ msg: "EndExecAgent", session: sessionId, error: `Error: ${e}. At: ${getErrorLocation(e)}` }));
			return;
		}
	};
	
	//-----------------------------------------------------------------------
	agentNode.execAgent = async function (sessionId, path, prompt) {
		const ssn = this.sessionMap.get(sessionId); // 使用 Map 的 get 方法
		if (!ssn) return false;
		const result = await ssn.execAgent(path, prompt);
		this.sessionMap.delete(sessionId); // 使用 Map 的 delete 方法
		this.websocket.send(JSON.stringify({ msg: "EndSession", session: sessionId }));
		return result;
	};
	
	//-----------------------------------------------------------------------
	agentNode.handleCall = async function (message) {
		const callMsg = message.message?.msg;
		const callVO = message.message?.vo;
		
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
	agentNode.startDebug=async function() {
		const shutdown = async (server) => {
			server.close();
			console.log('Debug Server closed.');
		};
		
		const handler = async (ws, req) => {
			console.log('Debug client connected');
			const curWebSocket = this.wsDebug;
			
			if (curWebSocket) {
				console.log('New client connected, close old connection');
				this.wsDebug = null;
				this.debugConnected = false;
				await curWebSocket.close();
			}
			
			if (this.debugStepTask) {
				this.debugStepTask.resolve(true);
				this.debugStepTask = null;
			}
			
			this.wsDebug = ws;
			this.debugConnected = true;
			
			ws.on('message', async (message) => {
				try {
					console.log(`Debug port received: ${message}`);
					const parsedMessage = JSON.parse(message);
					const cmd = parsedMessage.cmd;
					
					if (cmd === 'StepRunOn') {
						this.debugStepRun = true;
						await this.sendDebugLog({ type: 'StepRunOn' });
					} else if (cmd === 'StepRunOff') {
						this.debugStepRun = false;
						await this.sendDebugLog({ type: 'StepRunOff' });
					} else if (cmd === 'RunStep') {
						if (this.debugStepTask) {
							this.debugStepTask.resolve(true);
							this.debugStepTask = null;
						}
					}
				} catch (err) {
					console.error(err);
				}
			});
			
			ws.on('close', () => {
				console.log('Client disconnected');
				if (this.wsDebug === ws) {
					if (this.debugStepTask) {
						this.debugStepTask.resolve(true);
						this.debugStepTask = null;
					}
					this.wsDebug = null;
					this.debugConnected = false;
				}
			});
		};
		
		const port = this.nodeJSON.debugPort || 5001;
		try {
			this.debugServer = new WebSocketServer({ port, maxPayload: 1024 * 1024 * 10 });
			this.debugServer.on('connection', handler);
			this.debugServer.on('error', (err)=>{
				console.log(`Agent ${this.name} start debug error: ${err}`);
			});
		}catch(err){
			console.warn(`Agent ${this.name} start debug error: ${err}`);
		}
		
		console.log('Debug WebSocket server started');
		
		/*
		process.on('SIGINT', async () => {
			await shutdown(this.debugServer);
		});*/
	};
	
	//-----------------------------------------------------------------------
	agentNode.sendDebugLog=async function(log) {
		try {
			if (!this.wsDebug)
				return false;
			const logType = log.type;
			const serializedLog = JSON.stringify(log);
			await this.wsDebug.send(serializedLog);
			if (logType === 'StartSeg' && this.debugStepRun) {
				await this.wsDebug.send(JSON.stringify({ type: 'StepPaused' }));
				this.debugStepTask = new Promise((resolve) => {
					this.debugStepTask = { resolve };
				});
				await this.debugStepTask;
			}
			return true;
		} catch (err) {
			console.error(err);
		}
	};
}

export default AgentNode;
export {AgentNode}