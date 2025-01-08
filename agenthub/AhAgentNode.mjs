import {spawn} from "child_process";
import { promises as fs } from 'fs';
import pathLib from "path";
import {AhSession} from "./AhSession.mjs";
import AhXTerm from './AhXTerm.mjs'

//---------------------------------------------------------------------------
async function getLatestModifiedTime(dirPath) {
	let latestTime = 0;
	
	async function findLatestTime(directory) {
		const files = await fs.readdir(directory, { withFileTypes: true });
		
		for (const file of files) {
			const filePath = pathLib.join(directory, file.name);
			const stats = await fs.stat(filePath);
			
			if (file.isDirectory()) {
				await findLatestTime(filePath);
			} else if (stats.mtimeMs > latestTime) {
				latestTime = stats.mtimeMs;
			}
		}
	}
	
	await findLatestTime(dirPath);
	return latestTime;
}

//***************************************************************************
//AhAgentNode
//***************************************************************************
let AhAgentNode,ahAgentNode;
{
	let nextCallId=0;
	//-----------------------------------------------------------------------
	AhAgentNode=function(system,name){
		this.system=system;
		this.app=system.app;
		this.name=name;
		this.type=null;
		this.description=null;
		this.chatEntry=null;
		this.userGroups=new Set();
		this.agents=[];
		
		this.path=null;
		this.entryPath=null;
		this.entryDate=0;
		this.process=null;
		this.starting=false;
		this.connectCallback=null;
		this.connectCallErr=null;
		this.nodeWS=null;
		
		this.sessionMap=new Map();
		this.callMap=new Map();
		this.handlerMap=new Map();
		this.termMap=new Map();
		
		this.workload=0;
	};
	ahAgentNode=AhAgentNode.prototype={};
	const Type_Python="Python";
	const Type_Node="Node";
	
	//-----------------------------------------------------------------------
	ahAgentNode.OnNodeConnect=async function(ws,connectMsg){
		let nodeInfo;
		
		let timeouts=0;
		nodeInfo=connectMsg.info;
		this.name=this.name||nodeInfo.name;
		this.description=nodeInfo.description||"Agent node.";
		this.chatEntry=nodeInfo.chatEntry||null;
		this.userGroups=new Set(nodeInfo.userGroups||[]);
		this.agents=nodeInfo.agents||[];

		//TODO: parse more agentNode info:
		
		this.nodeWS=ws;
		
		//Setup message handling:
		ws.on('message',async (message)=>{
			let msgCode;
			if (message instanceof Buffer || message instanceof Uint8Array) {
				message = message.toString();
			}
			try{
				message=JSON.parse(message);
			}catch{
				message={};
			}
			msgCode=message.msg;
			if(msgCode!=="State") {
				console.log(`Message from AgentNode: ${msgCode}`);
			}
			try{
				switch(msgCode){
					case "CallClient": {//Agent call server/session-client:
						let callVO,callId,handler,msg,result,sessionId;
						callVO=message.message;
						callId=message.callId;
						sessionId=message.session||message.sessionId;
						if(sessionId){//Call client:
							let session;
							session=this.sessionMap.get(sessionId);
							if(session){
								try {
									result=await session.callClient(callVO.msg,callVO.vo,callVO.timeout||0);
								}catch(err){
									ws.send(JSON.stringify({
										msg: "CallResult",
										session:sessionId,
										callId: callId,
										error: "" + err
									}));
									return;
								}
								ws.send(JSON.stringify({ msg: "CallResult", session:sessionId, callId: callId, result: result }));
							}else{
								console.error(`Can't find session: ${sessionId}`);
							}
						}else {
						}
						return;
					}
					case "CallResult": {//Agent return call result:
						let stub,callMap,callId;
						callMap=this.callMap;
						callId=message.callId;
						stub=callMap.get(callId);
						if(stub){
							callMap.delete(callId);
							if(message.error){
								stub.error(message.result);
							}else {
								stub.callback(message.result);
							}
						}
						break;
					}
					case "MessageToClient":{
						let callVO,sessionId;
						callVO=message.message;
						sessionId=message.session||message.sessionId;
						if(sessionId) {//Call client:
							let session;
							session=this.sessionMap.get(sessionId);
							if(session){
								try {
									await session.sendToClient(callVO.msg,callVO.vo);
								}catch(err){
									console.warn(`Send message to client error: ${err}`);
								}
							}
						}
						break;
					}
					case "Message": {
						let handler,msg;
						msg=message.msg;
						handler=this.handlerMap.get(msg);
						if(handler){
							try {
								handler(message.message.vo);
							}catch(err){
								console.error(`Handle message ${msg} error:`);
								console.error(err);
							}
						}else{
							console.error(`Can't find messsage-handler: ${msg}`);
						}
						break;
					}
					case "CallHub":{
						let callVO,callId,result,devKey;
						let sessionId;
						callVO=message.message;
						callId=message.callId;
						devKey=message.devKey;
						sessionId=message.session||message.sessionId;
						try {
							result = await this.callHub(callVO.msg, callVO.vo,sessionId,devKey)
							await ws.send(JSON.stringify({ msg: "CallResult", callId: callId, result: result }));
						}catch(err){
							await ws.send(JSON.stringify({ msg: "CallResult", callId: callId, error: ""+err}));
						}
						return;
					}
					case "DebugLog": {
						this.OnDebugLog(message);
						return;
					}
					case "SessionReady":{
						let sessionId;
						sessionId=message.session||message.sessionId;
						this.OnSessionReady(sessionId);
						return;
					}
					case "SessionStartError":{
						let sessionId;
						sessionId=message.session||message.sessionId;
						this.OnSessionStartError(sessionId);
						return;
					}
					case "EndExecAgent":{
						let sessionId;
						sessionId=message.session||message.sessionId;
						this.OnExecAgentEnd(message);
						return;
					}
					case "State": {
						timeouts = 0;
						this.workload = message.workload || 0;
						return;
					}
					case "XTermData":{//AgentNode send data to client terminal:
						let callVO,sessionId,term;
						callVO=message.message;
						sessionId=callVO.session||callVO.sessionId;
						term=this.termMap.get(sessionId);
						if(term){
							term.write(callVO.data);
						}
					}
				}
			}catch (err){
				console.log("Handle bot message error:");
				console.error(err);
			}
		});

		//Setup error handler:
		ws.on('error', (err)=> {
			console.log(`AgentNode<${this.name}> websocket err:`);
			console.log(err);
		});
		
		ws.on('close', (reason)=>{
			console.log(`AgentNode<${this.name}>: connection lost: ${reason}`);
			if(this.nodeWS) {
				this.nodeWS = null;
				this.stop(false);
			}
		});
		
		ws.send(JSON.stringify({msg:"CONNECTED"}));
		let callback=this.connectCallback;
		if(callback){
			this.connectCallback=null;
			this.connectCallErr=null;
			callback();
		}
		this.heartBeat=setInterval(async ()=>{
			try {
				if(this.nodeWS) {
					await this.nodeWS.send(JSON.stringify({ msg: "State", message: {} }));//TODO: add hub state
					timeouts++;
					if (timeouts >= 5) {
						//ws.close(3001,"Timeout")
					}
				}else{
					clearInterval(this.heartBeat);
				}
			}catch(err){
			}
		},2000)
	};
	
	//-----------------------------------------------------------------------
	ahAgentNode.start=async function(path,options){
		let jsonPath,conda,ext,pms,nodeJSON,pathTime,entryPath,hostAddress;
		
		if(this.starting){
			console.log(`AgentNode ${this.name} is starting.`);
			return;
		}
		this.path=path||this.path;
		path=this.path;
		options=options||{};
		hostAddress=`ws://localhost:${this.app.get("port")}`;
		
		try {
			nodeJSON=await fs.readFile(pathLib.join(path, "agent.json"), "utf8");
			nodeJSON=JSON.parse(nodeJSON);
			nodeJSON.entry=nodeJSON.entry||"../tabos/AgentNodeMain.py"
		}catch(err){
			nodeJSON={
				entry:"../tabos/AgentNodeMain.py"
			}
		}
		entryPath=this.entryPath=pathLib.join(path,nodeJSON.entry);
		
		try {
			pathTime = await getLatestModifiedTime(path);
		}catch(err){
			pathTime=0;
		}

		//Check exist process, restart if needed:
		this.starting=true;
		this.entryPath=entryPath;
		this.entryDate=pathTime;

		//Start listen for agentNode websocket connection:
		{
			pms=new Promise((resolve,reject)=>{
				this.connectCallback=resolve;
				this.connectCallErr=reject;
			});
		}
		
		//Start the agent process
		ext=pathLib.extname(this.entryPath).toLowerCase();
		let errList=[];
		switch(ext){
			case ".mjs":
			case ".js":{
				this.type=Type_Node;
				let process;
				process=this.process = spawn('bash', ['-i', '-c', `node ${entryPath} ${this.path} ${hostAddress} ${this.name}`]);
				process.stdout.on('data', (data) => {
					console.log(`AgentNode<${this.name}> LOG: ${data.toString()}`);
				});
				process.stderr.on('data', (data) => {
					if(this.connectCallErr) {
						errList.push(data.toString());
					}
					console.error(`AgentNode<${this.name}> ERROR: ${data.toString()}`);
				});
				process.on('close', (code) => {
					let callErr=this.connectCallErr;
					if(callErr){
						let info;
						info=`Start agent node ERROR: ${errList.join(" \n")}`
						this.connectCallErr=null;
						this.connectCallback=null;
						callErr(info);
					}
				});
				break;
			}
			case ".py":{
				this.type=Type_Python;
				conda=options.conda||nodeJSON.conda||this.system.condaEnv;
				if(conda){
					let process;
					let condaPath=this.system.condaPath;
					process=this.process = spawn('bash', ['-i', '-c', `source ${condaPath} && conda activate ${conda} && python ${entryPath} ${this.path} ${hostAddress} ${this.name}`]);
					process.stdout.on('data', (data) => {
						console.log(`AgentNode<${this.name}> LOG: ${data.toString()}`);
					});
					process.stderr.on('data', (data) => {
						if(this.connectCallErr) {
							errList.push(data.toString());
						}
						console.log(`AgentNode<${this.name}>: ${data.toString()}`);
					});
					process.on('close', (code) => {
						let callErr=this.connectCallErr;
						if(callErr){
							let info;
							info=`Start agent node ERROR: ${errList.join(" \n")}`
							this.connectCallErr=null;
							this.connectCallback=null;
							callErr(info);
						}
					});
				}else{
					let process;
					process=this.process = spawn('bash', ['-i', '-c', `python ${entryPath} ${this.path} ${hostAddress} ${this.name}`]);
					process.stdout.on('data', (data) => {
						console.log(`AgentNode<${this.name}> LOG: ${data.toString()}`);
					});
					process.stderr.on('data', (data) => {
						if(this.connectCallErr) {
							errList.push(data.toString());
						}
						console.error(`AgentNode<${this.name}> ERROR: ${data.toString()}`);
					});
					process.on('close', (code) => {
						let callErr=this.connectCallErr;
						if(callErr){
							let info;
							info=`Start agent node ERROR: ${errList.join(" \n")}`
							this.connectCallErr=null;
							this.connectCallback=null;
							callErr(info);
						}
					});
				}
				break;
			}
		}
		
		//Wait agent's websocket connection:
		await pms;
		this.starting=false;
	};
	
	//-----------------------------------------------------------------------
	ahAgentNode.checkUpdate=async function(){
		let pathTime;
		if(!this.path){
			return false;
		}
		try {
			pathTime = await getLatestModifiedTime(this.path);
		}catch(err){
			pathTime=0;
		}
		if(pathTime>this.entryDate){
			return true;
		}
		return false;
	};
	
	//-----------------------------------------------------------------------
	ahAgentNode.stop=async function(){
		let sessions,ssn;
		
		this.stoping=true;
		if(this.heartBeat) {
			clearInterval(this.heartBeat);
			this.heartBeat=null;
		}
		sessions = this.sessionMap.values();
		for (ssn of sessions) {
			if (ssn.isExecuting) {
				try {
					await ssn.execAgentEnd(null, "AgentNode shutdown.");
				}catch(err) {
				}
			}
		}
		this.sessionMap.clear();
		this.system.OnNodeStop(this.name,this);
		if(this.process){
			try {
				this.process.kill('SIGTERM');
				this.process = null;
			}catch(err){
				//Do thing
			}
			return true;
		}else{
			if(this.nodeWS){
				this.nodeWS.close(1000,"Stop");
			}
		}
		this.nodeWS=null;
		return true;
	};
	
	//-----------------------------------------------------------------------
	/**
	 * New chat session, return new session object
	 *
	 * @param options
	 * @returns {Promise<void>}
	 */
	ahAgentNode.newSession=async function(options){
		let session;
		session=new AhSession(this);
		this.sessionMap.set(session.sessionId,session);
		await session.start(options);
		return session;
	};
	
	//-----------------------------------------------------------------------
	ahAgentNode.newTerm=async function(options){
		let term;
		term=new AhXTerm(this);
		this.termMap.set(term.sessionId,term);
		term.start(options);
		return term;
	};
	
	//----------------------------------------------------------------------
	ahAgentNode.closeTerm=async function(sessionId){
		let term;
		term=this.termMap.get(sessionId);
		if(term){
			await term.close();
			this.termMap.delete(sessionId);
		}
	};
	
	//-----------------------------------------------------------------------
	//Session end by session object or client (call from session):
	ahAgentNode.endSession=async function(session){
		this.sessionMap.delete(session.sessionId);
	};

	//-----------------------------------------------------------------------
	ahAgentNode.OnSessionReady=async function(sessionId){
		let session;
		session=this.sessionMap.get(sessionId);
		if(session) {
			await session.OnReady();
		}
	}

	//-----------------------------------------------------------------------
	ahAgentNode.OnSessionStartError=async function(sessionId){
		let session;
		session=this.sessionMap.get(sessionId);
		if(session) {
			await session.OnStartError();
		}
	}

	//-----------------------------------------------------------------------
	//Session end by agent:
	ahAgentNode.OnExecAgentEnd=async function(message){
		let session;
		session=message.session||message.sessionId;
		session=this.sessionMap.get(session);
		if(session){
			await session.execAgentEnd(message.result,message.error);//Will trigger ahAgentNode.endSession, so we don't need to remove it from map.
			return true;
		}
		return false;
	};
	
	//-----------------------------------------------------------------------
	ahAgentNode.OnDebugLog=async function(message){
		let session;
		session=message.session||message.sessionId;
		session=this.sessionMap.get(session);
		if(session){
			await session.sendToClient("DebugLog",message.log);//send debug log to client
			return true;
		}
	}
	
	//-----------------------------------------------------------------------
	ahAgentNode.send=async function(msg,vo,sessionId){
		let msgVO;
		msgVO={msg:msg,vo:vo};
		this.nodeWS.send(JSON.stringify({msg:"Message", session:sessionId,message:msgVO}));
	};
	
	//-----------------------------------------------------------------------
	ahAgentNode.call=ahAgentNode.callNode=async function(msg,vo,sessionId,timeout){
		let msgVO,callId,pms,errCbk,stub;
		callId=""+(nextCallId++);
		msgVO={msg:msg,vo:vo};
		stub={
			callback:null,callId:callId,error:null
		};
		pms=new Promise((resolve,reject)=>{
			stub.callback=resolve;
			stub.error=reject;
			errCbk=reject;
		});
		if(timeout>0){
			setTimeout(()=>{
				errCbk("Time out.");
			},timeout);
		}
		this.nodeWS.send(JSON.stringify({msg:"Call", session:sessionId, callId:callId, message:msgVO}));
		this.callMap.set(callId,stub);
		return await pms;
	};
	
	//-----------------------------------------------------------------------
	ahAgentNode.callHub=async function(msg,vo,sessionId,devKey){
		let handler,result,session;
		if(sessionId){
			session=this.sessionMap.get(sessionId);
		}
		handler=this.handlerMap.get(msg);
		if(handler){
			return await handler(msg,vo);
		}
		return this.system.handleCallHub(msg,vo,session,devKey);
	};
}
export default AhAgentNode;
export {AhAgentNode};
