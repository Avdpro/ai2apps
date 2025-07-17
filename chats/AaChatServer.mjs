import {nanoid} from "nanoid";
import {AaChatDb} from './AaChatDb.mjs';
import {InvokeApi} from "../util/InvokeApi.mjs";
const MAX_LIVE_THREADS=5;

//***************************************************************************
//AaChatThread
//***************************************************************************
let AaChatThread,aaChatThread;
{
	let STATUS_NONE,STATUS_LIVE,STATUS_DORMANT,STATUS_ARCHIVED;
	AaChatThread=function(chatServer,userId){
		this.client=null;
		this.formerClient=null;
		this.server=chatServer;
		this.app=chatServer.app;
		this.userId=userId;
		this.id=null;
		this.messages=null;
		this.title="New thread";
		this.status=STATUS_NONE;
		this.allowTakeOver=false;
		this.archived=false;
		this.stared=false;
		this.asking=false;
		this.askVo=null;
	};
	aaChatThread=AaChatThread.prototype={};
	
	STATUS_NONE=AaChatThread.STATUS_NONE="none";
	STATUS_LIVE=AaChatThread.STATUS_LIVE="live";
	STATUS_DORMANT=AaChatThread.STATUS_DORMANT="dormant";
	STATUS_ARCHIVED=AaChatThread.STATUS_ARCHIVED="archived";
	
	//-----------------------------------------------------------------------
	aaChatThread.start=async function(client,prompt){
		if(this.id){
			throw Error(`Start thread error: thread ${this.id} already has threadId.`);
		}
		this.id=nanoid();
		
		this.client=client;
		this.status=STATUS_LIVE;
		this.title=prompt.prompt||prompt;
		this.timeStamp=Date.now();
		this.messages=[];
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.loadFromVo=async function(vo){
		if(this.id){
			throw Error(`Load thread error: thread ${this.id} already has threadId.`);
		}
		this.title=vo.title;
		this.id=vo.id||vo._id||vo.threadId;
		this.messages=vo.messages?vo.messages.slice(0):null;
		this.allowTakeOver=!!vo.allowTakeOver;
		this.status=STATUS_DORMANT;
		this.timeStamp=vo.timeStamp||0;
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.wakeup=async function(client){
		if(!this.id){
			throw Error(`Thread go live missing threadId`);
		}
		if(this.status!==TYPE_DORMANT){
			throw Error(`Thread ${this.id} go live with wrong type: ${this.status}.`);
		}
		this.client=client;
		this.status=STATUS_LIVE;
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.loadMessages=async function(){
		this.messages=await this.server.chatDb.getThreadMessages(this.id)
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.newMessage=async function(client,msgVo){
		let vo;
		if(client.userId!==this.userId){
			throw Error(`Thread ${this.id} can't be takeOver.`);
		}
		if(!this.messages){
			await this.loadMessages();
		}
		vo={};
		vo.type="Message";
		vo.idx=this.messages.length;
		vo.time=Date.now();
		vo.message=msgVo;
		this.messages.push(vo);
		await this.server.chatDb.newThreadMessage(this,vo);
		this.server.castMessage(client,this,vo);
		return vo;
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.getMessages=async function(fromId){
		if(!this.messages){
			await this.loadMessages();
		}
		fromId=fromId>0?fromId:0;
		return this.messages.slice(fromId);
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.rollback=async function(msgId){
		if(!this.messages){
			await this.loadMessages();
		}
		this.messaes=this.messages.slice(0,msgId+1);
		//TODO: Call DB to rollback
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.genSaveVo=function(withMessages){
		let vo;
		vo={
			id:this.id,
			status:this.status,
			title:this.title,
			userId:this.userId,
			client:this.client?this.client.id:null,
			archived:this.archived,
			asking:this.asking,
			askVo:this.askVo
		};
		if(withMessages){
			vo.messages=this.messages;
		}
		return vo;
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.askUser=async function(fromClient,vo){
		if(this.asking){
			throw Error("Thread is already asking...");
		}
		this.asking=vo.type;
		this.askVo=vo.askVo;
		await this.server.castAskUser(fromClient,this,vo);
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.userReply=async function(fromClient,result){
		if(!this.asking){
			throw Error("Thread is not asking...");
		}
		this.asking=false;
		this.askVo=null;
		await this.server.castUserReply(fromClient,this,result);
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.rename=async function(fromClient,newName){
		this.title=newName;
		this.server.castRenameThread(fromClient,this);
	};
	
	//-----------------------------------------------------------------------
	aaChatThread.clientOffline=async function(client){
		if(client!==this.client){
			return;
		}
		this.client=null;
		this.formerClient=client;
		this.status=STATUS_DORMANT;
		this.server.castThreadOffline(client,this);
	};
}

//***************************************************************************
//AaChatClient
//***************************************************************************
let AaChatClient,aaChatClient;
{
	let TYPE_HOST,TYPE_SHADOW;
	//-----------------------------------------------------------------------
	AaChatClient=function(chatServer,userId){
		this.id=null;
		this.server=chatServer;
		this.app=chatServer.app;
		this.userId=userId;
		this.type=TYPE_HOST;
		this.hostClient=null;
		this.threads=[];
		this.ws=null;//Websocket
		this.nextCallId=0;
		this.callMap=new Map();
	};
	aaChatClient=AaChatClient.prototype={};
	
	TYPE_HOST=AaChatClient.TYPE_HOST="host";
	TYPE_SHADOW=AaChatClient.TYPE_SHADOW="shadow";
	
	//***********************************************************************
	//Network functions:
	//***********************************************************************
	{
		//-----------------------------------------------------------------------
		AaChatClient.onWsMessage = async function (ws, message) {
			let method, msgCode, handler;
			if (this.ws !== ws) {
				return;
			}
			if (message instanceof Buffer || message instanceof Uint8Array) {
				message = message.toString();
			}
			try {
				message = JSON.parse(message);
			} catch {
				message = {};
			}
			console.log("Chat-Server-Message:");
			console.log(message);
			try {
				method = message.method;
				msgCode = message.msg;
				switch (method) {
					case "Call": {
						let result, callId, resultVo;
						handler = this["onWs_" + msgCode];
						callId = message.callId;
						if (!handler) {
							console.log("AaChatClient-HandleCall error: can't find handler for message: "+msgCode);
							await ws.send(JSON.stringify({
								method: "CallResult",
								callId: callId,
								error: "Handler not found."
							}));
							return;
						}
						try {
							result = await handler.call(this, message.vo);
							resultVo={ method: "CallResult", callId: callId, result: result };
						} catch (err) {
							console.error(err);
							resultVo={ method: "CallResult", callId: callId, err: "" + err };
							return;
						}
						resultVo=JSON.stringify(resultVo,null,"\t");
						console.log("Chat-Server-Call-Result:");
						console.log(resultVo);
						await ws.send(resultVo);
						return;
					}
					case "Post": {
						handler = this["onWs_" + msgCode];
						if (!handler) {
							console.log("AaChatClient-HandleCall error: can't find handler for message: "+msgCode);
							return;
						}
						try {
							await handler.call(this, message.vo);
						}catch(err){
							console.log(`Handle client-post "${msgCode}" error:`);
							console.error(err);
						}
						return;
					}
					case "CallHostClient":{
						let result,resultVo,callId,hostClientId,hostClient;
						hostClientId=message.host;
						hostClient=this.server.clientMap.get(hostClientId);
						if(!hostClient || hostClient===this){
							console.log("AaChatClient-HandleCall error: can't find handler for message: "+msgCode);
							await ws.send(JSON.stringify({
								method: "CallResult",
								callId: callId,
								error: "Host client error."
							}));
							return;
						}
						try{
							result=await hostClient.callClient(msgCode,message.vo);
							resultVo={ method: "CallResult", callId: message.callId, result: result };
						} catch (err) {
							resultVo={ method: "CallResult", callId: message.callId, err: "" + err };
							return;
						}
						resultVo=JSON.stringify(resultVo,null,"\t");
						console.log("Chat-Server-Call-Host-Result:");
						console.log(resultVo);
						await ws.send(resultVo);
						return;
					}
					case "PostHostClient":{
						let result,resultVo,callId,hostClientId,hostClient;
						hostClientId=message.host;
						hostClient=this.server.clientMap.get(hostClientId);
						if(!hostClient || hostClient===this){
							console.log("AaChatClient-HandleCall error: can't find handler for message: "+msgCode);
							await ws.send(JSON.stringify({
								method: "CallResult",
								callId: callId,
								error: "Host client error."
							}));
							return;
						}
						hostClient.postClient(msgCode,message.vo);
						return;
					}
					case "CallResult": {
						let stub, callMap, callId;
						callMap = this.callMap;
						callId = message.callId;
						stub = callMap.get(callId);
						if (stub) {
							callMap.delete(callId);
							if (message.error) {
								stub.reject(message.error);
							} else {
								stub.resolve(message.result);
							}
						}
						return;
					}
				}
			} catch (err) {
				console.log("Handle client websocket message error:");
				console.error(err);
			}
		};
		
		//-----------------------------------------------------------------------
		AaChatClient.onWsError = async function (ws, err) {
			if (this.ws !== ws) {
				return;
			}
			console.log(`ChatClient<${this.id}> websocket err:`);
			console.log(err);
		};
		
		//-----------------------------------------------------------------------
		AaChatClient.onWsClose = async function (ws, reason) {
			if (this.ws !== ws) {
				return;
			}
			console.log(`ChatClient<${this.id}>: connection lost: ${reason}`);
			this.ws=null;
			//Reject all pending calls:
			{
				let calls,stub;
				calls=this.callMap.values();
				for(stub of calls){
					stub.reject("Client closed.");
				}
				this.callMap.clear();
			}
			this.server.clientOffline(this);
			//Offline all live threads belong to this client:
			{
				let threads=this.server.threads;
				for(let thread of threads){
					if(thread.client===this){
						thread.clientOffline(this);
					}
				}
			}
			this.ws = null;
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.onWs_Ping=async function(vo){
			//Do nothing...
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.onWs_GetThread=async function(vo){
			let threadId,thread,withMessages;
			threadId=vo.thread||vo.treadId||vo.id;
			thread=this.server.threadMap.get(threadId);
			if(thread.userId!==this.userId){
				return null;
			}
			withMessages=vo.withMessages||vo.messages||true;
			if(thread){
				return thread.genSaveVo(withMessages);
			}
		};

		//-----------------------------------------------------------------------
		aaChatClient.onWs_GetThreads=async function(vo){
			let list,archives,thread,server;
			server=this.server;
			list=this.server.threads||[];
			list=list.filter((item)=>{return item.userId===this.userId;});
			list=list.sort((item1,item2)=>{return item2.timeStamp-item1.timeStamp});
			archives=list.splice(MAX_LIVE_THREADS);
			list=list.splice(0,MAX_LIVE_THREADS);
			for(thread of archives){
				await server.archiveThread(this,thread);
			}
			list=list.map((item)=>{
				return item.genSaveVo(false);
			});
			return list;
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.onWs_GetThreadMessages=async function(vo){
			let threadId,thread,fromIdx,messages;
			threadId=vo.thread;
			fromIdx=vo.from||vo.fromIdx||vo.fromId||0;
			thread=this.server.threadMap.get(threadId);
			if(!thread || thread.userId!==this.userId){
				return [];
			}
			messages=await thread.getMessages(fromIdx);
			return messages;
		};

		//-----------------------------------------------------------------------
		aaChatClient.onWs_NewThread=async function(vo){
			let thread,server,prompt;
			server=this.server;
			prompt=vo.prompt;
			if(this.hostClient && this.hostClient!==this){
				//TODO: CallHostClient to start new
				return;
			}
			thread=new AaChatThread(server,this.userId);
			await thread.start(this.hostClient,prompt);
			await server.castNewThread(thread);
			return thread.id;
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.onWs_NewMessage=async function(vo){
			let threadId,thread,msgVO;
			threadId=vo.thread||vo.threadId;
			thread=this.server.threadMap.get(threadId);
			if(!thread) {
				throw Error("NewMessage error: can't find thread.");
			}
			if(thread.userId!==this.userId){
				throw Error("NewMessage error: can't find thread.");
			}
			msgVO=await thread.newMessage(this,vo.message);
			return msgVO.idx;
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.onWs_AskUser=async function(vo){
			let threadId,thread;
			threadId=vo.thread;
			thread=this.server.threadMap.get(threadId);
			if(!thread){
				return;
			}
			if(thread.userId!==this.userId){
				return;
			}
			await thread.askUser(this,vo);
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.onWs_UserReply=async function(vo){
			let threadId,thread;
			threadId=vo.thread;
			thread=this.server.threadMap.get(threadId);
			if(!thread){
				return;
			}
			if(thread.userId!==this.userId){
				return;
			}
			await thread.userReply(this,vo.result);
		};
		
		//----------------------------------------------------------------------
		aaChatClient.onWs_RenameThread=async function(vo){
			let threadId,thread;
			threadId=vo.thread||vo.threadId||vo.id;
			thread=this.server.threadMap.get(threadId);
			if(!thread){
				return;
			}
			if(thread.userId!==this.userId){
				return;
			}
			thread.rename(this,vo.name||vo.title);
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.onWs_ClientActive=async function(vo){
			//TODO: Code this:
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.onWs_ArchiveThread=async function(vo){
			let threadId,thread,fromIdx,messages;
			threadId=vo.thread;
			thread=this.server.threadMap.get(threadId);
			if(!thread || thread.userId!==this.userId){
				return false;
			}
			await this.server.archiveThread(this,thread);
			return true;
		};

		//-----------------------------------------------------------------------
		aaChatClient.onWs_DeleteThread=async function(vo){
			let threadId,thread,fromIdx,messages;
			threadId=vo.thread;
			thread=this.server.threadMap.get(threadId);
			if(!thread || thread.userId!==this.userId){
				return false;
			}
			await this.server.deleteThread(this,thread);
			return true;
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.onWs_GetArchivedThreads=async function(vo){
			//TODO: Code this:
		};

		//-----------------------------------------------------------------------
		aaChatClient.onWs_RecallArchivedThreads=async function(vo){
			//TODO: Code this:
		};

		//-----------------------------------------------------------------------
		aaChatClient.onWs_FindThreads=async function(vo){
			//TODO: Code this:
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.callClient=async function(msg,vo,timeout=0){
			if(!this.ws){
				throw Error(`Client not connected.`);
			}
			let stub,timer,result;
			const callId = String(this.nextCallId++);
			const pms = new Promise((resolve, reject) => {
				stub={ resolve, reject };
				this.callMap.set(callId,stub);
			});
			const message = JSON.stringify({
				method: "Call",
				msg:msg,vo:vo,
				callId,
			});
			await this.ws.send(message);
			if(timeout>0){
				timeout*=1000;
				timer=setTimeout(()=>{
					this.callMap.delete(callId);
					stub.reject(Error("Time out"));
				},timeout);
			}
			result=await pms;
			if(timer){
				clearTimeout(timer);
			}
			return result;
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.postClient=async function(msg,vo){
			if(!this.ws){
				return;
			}
			const message = JSON.stringify({
				method: "Post",
				msg:msg,vo:vo,
			});
			await this.ws.send(message);
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.callHostClient=async function(msgCode,vo,timeout=10){
			let result,handler,hostClient;
			hostClient=this.hostClient;
			if(!hostClient || hostClient===this){
				throw Error("CallHostClient error: host client error.");
			}
			handler=hostClient["onWs_"+msgCode];
			if(!handler){
				throw Error("CallHostClient error: handler not found.");
			}
			return await handler.call(hostClient,vo);
		};
	}
	
	//***********************************************************************
	//Create new client:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaChatClient.newHostClient = async function (id) {
			let app, selectorMap;
			app = this.app;
			selectorMap = app.get("WebSocketSelectorMap");
			this.id = id||nanoid();
			this.hostClient = this;
			this.type = TYPE_HOST;
			selectorMap.set("ChatClient:" + this.id, (ws, msg) => {
				if (this.ws) {
					this.ws.close();
				}
				this.ws = ws;
				ws.on('message', AaChatClient.onWsMessage.bind(this, ws));
				ws.on('error', AaChatClient.onWsError.bind(this, ws));
				ws.on('close', AaChatClient.onWsClose.bind(this, ws));
				ws.send(JSON.stringify({ msg: "CONNECTED" }));
				selectorMap.delete("ChatClient:" + this.id);
			});
		};
		
		//-------------------------------------------------------------------
		aaChatClient.newShadowClient = async function (hostClient) {
			let app, selectorMap;
			app = this.app;
			selectorMap = app.get("WebSocketSelectorMap");
			this.id = nanoid();
			this.hostClient = hostClient;
			this.type = TYPE_SHADOW;
			selectorMap.set("ChatClient:" + this.id, (ws, msg) => {
				selectorMap.delete("ChatClient:" + this.id);
				this.ws = ws;
				ws.on('message', AaChatClient.onWsMessage.bind(this, ws));
				ws.on('error', AaChatClient.onWsError.bind(this, ws));
				ws.on('close', AaChatClient.onWsClose.bind(this, ws));
				ws.send(JSON.stringify({ msg: "CONNECTED" }));
			});
		};
		
		//-------------------------------------------------------------------
		aaChatClient.resume = async function () {
			let app, selectorMap;
			app = this.app;
			selectorMap = app.get("WebSocketSelectorMap");
			//Close current websocket:
			if (this.ws) {
				this.ws.close();
				this.ws=null;
			}
			selectorMap.set("ChatClient:" + this.id, (ws, msg) => {
				selectorMap.delete("ChatClient:" + this.id);
				this.ws = ws;
				ws.on('message', AaChatClient.onWsMessage.bind(this, ws));
				ws.on('error', AaChatClient.onWsError.bind(this, ws));
				ws.on('close', AaChatClient.onWsClose.bind(this, ws));
				ws.send(JSON.stringify({ msg: "CONNECTED" }));
			});
		};
	}
	
	//***********************************************************************
	//Threads
	//***********************************************************************
	{
		//-----------------------------------------------------------------------
		aaChatClient.newThread = async function (prompt) {
			//TODO: Code this:
		};
		
		//-----------------------------------------------------------------------
		aaChatClient.postNewMessage = async function (thread, msgVo) {
			//TODO: Code this:
		};
	}
}

//***************************************************************************
//AaChatServer
//***************************************************************************
let AaChatServer,aaChatServer
{
	AaChatServer=function(app){
		this.app=app;
		this.chatDb=null;
		this.clients=[];
		this.clientMap=new Map();
		this.threads=[];
		this.threadMap=new Map();
	};
	aaChatServer=AaChatServer.prototype={};
	
	//***********************************************************************
	//Client, shadow client related
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaChatServer.clientOffline=async function(client){
			let c,clients,clientId;
			try {
				clientId=client.id;
				clients = this.clients;
				for (c of clients) {
					if (c.hostClient === client && client!==c) {
						await c.postClient("HostClientOffline", {client:clientId});
					}
				}
			}catch(err){
			}
		};
		
		//-------------------------------------------------------------------
		aaChatServer.castToClients=async function(hostClient,msg,vo){
			let client,clients;
			clients=this.clients;
			for(client of clients){
				if(client.hostClient===hostClient){
					await client.postClient(msg,vo);
				}
			}
		};
	}
	
	//***********************************************************************
	//Thread, message related
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaChatServer.loadLiveThreads=async function(){
			let list,vo,thread;
			list=await this.chatDb.getAllLiveThreads({archive:true});
			for(vo of list){
				thread=new AaChatThread(this,vo.userId);
				await thread.loadFromVo(vo);
				this.threads.push(thread);
				this.threadMap.set(thread.id,thread);
			}
		};
		
		//-------------------------------------------------------------------
		aaChatServer.archiveThread=async function(fromClient,thread){
			let idx,clients,client;
			if(fromClient.userId!==thread.userId){
				throw new Error("archiveThread: userId error.");
			}
			await this.chatDb.archiveThread(thread);
			this.threadMap.delete(thread.key);
			idx=this.threads.indexOf(thread);
			if(idx>=0){
				this.threads.splice(idx,1);
			}
			clients=this.clients;
			for(client of clients){
				if(client.userId===thread.userId) {
					client.postClient("ArchiveThread",{thread:thread.id});
				}
			}
		};

		//-------------------------------------------------------------------
		aaChatServer.deleteThread=async function(fromClient,thread){
			let idx,clients,client;
			if(fromClient.userId!==thread.userId){
				throw new Error("deleteThread: userId error.");
			}
			await this.chatDb.deleteThread(thread);
			this.threadMap.delete(thread.id);
			idx=this.threads.indexOf(thread);
			if(idx>=0){
				this.threads.splice(idx,1);
			}
			clients=this.clients;
			for(client of clients){
				if(client.userId===thread.userId) {
					await client.postClient("DeleteThread", { thread: thread.id });
				}
			}
		};
		
		//-------------------------------------------------------------------
		aaChatServer.castNewThread=async function(thread){
			let clients,client,fromClient,list;
			this.threads.push(thread);
			this.threadMap.set(thread.id,thread);
			this.chatDb.newThread(thread);
			fromClient=thread.client;
			clients=this.clients;
			for(client of clients){
				if(client!==fromClient && client.userId===thread.userId) {
					client.postClient("NewThread",{client:fromClient.id,thread:thread.id,title:thread.title});
				}
			}
			list=this.threads.filter((t)=>{return t.userId===fromClient.userId;});
			if(list.length>MAX_LIVE_THREADS){
				list=list.sort((item1,item2)=>{return item2.timeStamp-item1.timeStamp;});
				list=list.splice(MAX_LIVE_THREADS);
				for(thread of list){
					await this.archiveThread(fromClient,thread);
				}
			}
		};
		
		//-------------------------------------------------------------------
		aaChatServer.castMessage=async function(fromClient,thread,msgVo){
			let clients,client;
			clients=this.clients;
			for(client of clients){
				if(client!==fromClient && thread.userId===client.userId) {
					client.postClient("NewThreadMessage",{thread:thread.id, message:msgVo});
				}
			}
		};
		
		//-------------------------------------------------------------------
		aaChatServer.castAskUser=async function(fromClient,thread,msgVo){
			let clients,client;
			clients=this.clients;
			for(client of clients){
				if(client!==fromClient && thread.userId===client.userId) {
					client.postClient("AskUser",{thread:thread.id, type:msgVo.type,askVo:msgVo.askVo});
				}
			}
		};
		
		//-------------------------------------------------------------------
		aaChatServer.castUserReply=async function(fromClient,thread,result){
			let clients,client;
			clients=this.clients;
			for(client of clients){
				if(client!==fromClient && thread.userId===client.userId) {
					client.postClient("UserReply",{thread:thread.id, result:result});
				}
			}
		};
		
		//-------------------------------------------------------------------
		aaChatServer.castThreadOffline=async function(fromClient,thread){
			let clients,client;
			clients=this.clients;
			for(client of clients){
				if(client!==fromClient && client.userId===thread.userId) {
					client.postClient("ThreadOffline",{thread:thread.id});
				}
			}
		};
		
		//-------------------------------------------------------------------
		aaChatServer.castRenameThread=async function(fromClient,thread){
			let clients,client;
			if(fromClient.userId!==thread.userId){
				throw new Error("castRenameThread: userId error.");
			}
			this.chatDb.renameThread(thread);
			clients=this.clients;
			for(client of clients){
				if(client.userId===thread.userId) {
					await client.postClient("RenameThread", { thread: thread.id, title: thread.title });
				}
			}
		};
		
		//-------------------------------------------------------------------
		aaChatServer.castCallbackArchivedThread=async function(fromClient,thread){
			let clients,client;
			if(fromClient.userId!==thread.userId){
				throw new Error("castCallbackArchivedThread: userId error.");
			}
			clients=this.clients;
			this.threadMap.set(thread.id,thread);
			for(client of clients){
				await client.postClient("CallbackArchivedThread",{thread:thread.id});
			}
		};
	}
	
	//***********************************************************************
	//Setup and web-call-api
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		aaChatServer.setup=async function(router,apiMap){
			let app,cfgPath,self;
			self=this;
			app=self.app;
			this.apiMap=apiMap;
			this.chatDb=new AaChatDb(this);
			await this.chatDb.init();//TODO: Add DB name?
			await this.loadLiveThreads();
			
			//---------------------------------------------------------------
			apiMap['AcsNewClient']=async function(req,res){
				let reqVo,type,client,userId,hostId,hostClient;
				reqVo=req.body.vo;
				userId=reqVo.userId;
				type=reqVo.type||"host";
				hostId=reqVo.host||reqVo.hostId||reqVo.hostClient;
				if(!userId){
					res.json({ code: 403, info:`Missing userId to create new session.`});
					return;
				}
				client=new AaChatClient(self,userId)
				if(type==="host"){
					await client.newHostClient();
				}else if(type==="shadow"){
					if(hostId) {
						hostClient = self.clientMap.get(hostId);
						if (!hostClient) {
							res.json({ code: 404, info: `Can't find host client: ${hostId}` });
							return;
						}
					}else{
						let clients;
						clients=self.clients;
						FindHost:{
							for (hostClient of clients) {
								if (hostClient.ws && hostClient.type === "host") {
									break FindHost;
								}
							}
							res.json({ code: 404, info: `Can't find host available host client.` });
							return;
						}
					}
					await client.newShadowClient(hostClient);
				}else {
					res.json({ code: 400, info:`Wrong client type:: ${type}`});
					return;
				}
				self.clientMap.set(client.id,client);
				self.clients.push(client);
				if(type==="host") {
					await self.chatDb.newClient(client.id, userId);
				}
				res.json({ code: 200, clientId:client.id,hostId:client.hostClient?.id||null});
			};
			
			//---------------------------------------------------------------
			apiMap['AcsResumeClient']=async function(req,res){
				let reqVo,type,client,userId,clientId,hostId,hostClient;
				reqVo=req.body.vo;
				userId=reqVo.userId;
				clientId=reqVo.clientId;
				type=reqVo.type||"host";
				hostId=reqVo.host||reqVo.hostId||reqVo.hostClient;
				
				client=self.clientMap.get(clientId);
				if(client){
					if(client.userId!==userId){
						res.json({ code: 403, info:`Wrong user id.`});
						return;
					}
					if(client.type!==type){
						res.json({ code: 400, info:`Wrong client type.`});
						return;
					}
					if(type==="shadow"){
						if(hostId!==client.hostClient.id) {
							res.json({ code: 400, info: `Wrong host client.` });
							return;
						}
						hostClient=self.clientMap.get(hostId);
						if(!hostClient || !hostClient.ws){
							res.json({ code: 405, info: `Host client is not active.` });
							return;
						}
					}
					await client.resume();
					res.json({ code: 200, info:`Client is ready for connect.`});
					return;
				}
				if(type!=="host"){
					res.json({ code: 400, info:`Shadow client can not resume from database.`});
					return;
				}
				let dbClient;
				dbClient=await self.chatDb.getClient(clientId);
				if(dbClient){
					if(dbClient.userId!==userId){
						res.json({ code: 403, info:`Wrong user id.`});
						return;
					}
					client=new AaChatClient(self,userId);
					await client.newHostClient(clientId);
					self.clientMap.set(client.id,client);
					self.clients.push(client);
					res.json({ code: 200, info:`Client is ready for connect.`});
					return;
				}
				res.json({ code: 404, info:`Client not found.`});
			};
		};
	}
}

export default async function(app,router,apiMap) {
	let chatSys;
	chatSys=new AaChatServer(app);
	await chatSys.setup(router,apiMap);
	return chatSys;
};
export {AaChatServer};
