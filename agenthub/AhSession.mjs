//***************************************************************************
//AhSession
//***************************************************************************
let AhSession,ahSession;
{
	const sessionIdPrex="Session"+Date.now();
	let nextSessionIdx=0;

	//-----------------------------------------------------------------------
	AhSession=function(agentNode){
		this.agentNode=agentNode;
		this.system=agentNode.system;
		this.app=agentNode.app;
		this.sessionId=sessionIdPrex+"-"+(nextSessionIdx++);
		this.nodeWS=agentNode.nodeWS;
		this.clientWS=null;
		this.waitPms=null;
		
		this.userId=null;
		this.userToken=null;
		
		this.isExecuting=false;
		this.nodeReadyCallback=null;
		this.nodeReadyError=null;
		
		this.nextCallId=0;
		this.clientCallMap=new Map();
	}
	ahSession=AhSession.prototype={};
	
	//-----------------------------------------------------------------------
	/**
	 * Start agent session instance:
	 */
	ahSession.start=async function(options){
		//Call agentNode to startSession:
		let readyPms;
		readyPms=new Promise((resolve,reject)=>{
			this.nodeReadyCallback=resolve;
			this.nodeReadyError=reject;
		});
		await this.nodeWS.send(JSON.stringify({msg:"CreateSession",sessionId:this.sessionId,options:options}));
		await readyPms;
		
		//Start listen for user-client websocket connection:
		{
			let selectorMap,selectCode,callback;
			selectorMap=this.app.get("WebSocketSelectorMap");
			selectCode=this.sessionId;
			this.waitPms=new Promise((resolve,reject)=>{
				callback=resolve;
			});
			selectorMap.set(selectCode,(ws)=>{
				selectorMap.delete(selectCode);
				this.clientWS=ws;
				ws.on('message',async (message)=>{
					if (message instanceof Buffer || message instanceof Uint8Array) {
						message = message.toString();
					}
					try{
						message=JSON.parse(message);
					}catch{
						message={};
					}
					try{
						switch(message.msg){
							case "Call": {//Client call agent:
								let callId,handler,msg,result;
								callId=message.callId;
								msg=message.message.msg;
								try {
									result = await this.callAgent(message.message.msg, message.message.message||message.message.vo,message.timeout||0);
								}catch(err) {
									ws.send(JSON.stringify({msg:"CallResult",callId:callId,error:""+err}));
									return;
								}
								ws.send(JSON.stringify({msg:"CallResult",callId:callId,result:result}));
								return;
							}
							case "CallResult": {//Client return call result
								let stub,callMap,callId;
								callMap=this.clientCallMap;
								callId=message.callId;
								stub=callMap.get(callId);
								if(stub){
									callMap.delete(callId);
									if(message.error){
										stub.error(message.error);
									}else {
										stub.callback(message.result);
									}
								}
								break;
							}
							case "ExecAgent":{
								this.isExecuting=true;
								message=JSON.stringify(message);
								this.nodeWS.send(message);
								break;
							}
							case "Message": {//Client send session to agent:
								let handler,msg;
								msg=message.msg;
								this.agentNode.send(msg.msg,msg.vo,this.sessionId);
								break;
							}
						}
					}catch (err){
						console.log("Handle bot message error:");
						console.error(err);
					}
				});
				
				ws.on('close',async(event)=>{
					this.OnClose(event.code,event.reason);
				});
				
				ws.on('error',(data)=>{
					console.log(`Client websocket error:`,data);
				});
				ws.send(JSON.stringify({msg:"CONNECTED"}));
				callback();
			});
		}
	};
	
	//-----------------------------------------------------------------------
	/**
	 * Wait client connect instance:
	 *
	 */
	ahSession.waitClient=async function(){
		await this.waitPms;
	};
	
	//-----------------------------------------------------------------------
	/** Callback when node's session is ready:
	 *
	 */
	ahSession.OnReady=function(){
		let callback;
		callback=this.nodeReadyCallback;
		this.nodeReadyCallback=null;
		this.nodeReadyError=null;
		if(callback){
			callback();
		}
	};
	
	//-----------------------------------------------------------------------
	/** Callback when node's session start failed:
	 *
	 */
	ahSession.OnStartError=function(){
		let callback;
		callback=this.nodeReadyError;
		this.nodeReadyCallback=null;
		this.nodeReadyError=null;
		if(callback){
			callback();
		}
	};
	//-----------------------------------------------------------------------
	/**
	 * Client websocket closed:
	 *
	 */
	ahSession.OnClose=async function(code=1000,reason="END"){
		if(!this.clientWS){
			return;
		}
		this.clientWS.close(1000,reason);
		this.clientWS=null;
		//TODO: Reject all calls?
		this.clientCallMap.clear();
		await this.agentNode.endSession(this);
	};
	
	//-----------------------------------------------------------------------
	ahSession.sendToClient=async function(msg,vo){
		let msgVO;
		msgVO={msg:msg,vo:vo};
		await this.clientWS.send(JSON.stringify({msg:"Message", session:this.sessionId,message:msgVO}));
	};

	//-----------------------------------------------------------------------
	ahSession.callClient=async function(msg,vo,timeout){
		let msgVO,callId,pms,errCbk,stub;
		callId=""+(this.nextCallId++);
		msgVO={msg:msg,vo:vo};
		stub={
			callback:null,callId:callId,error:null
		};
		this.clientCallMap.set(callId,stub);
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
		this.clientWS.send(JSON.stringify({msg:"Call", session:this.sessionId, callId:callId, message:msgVO}));
		return await pms;
	};
	
	//-----------------------------------------------------------------------
	ahSession.sendToAgent=async function(msg,vo){
		return await this.agentNode.send(msg,vo,this.sessionId);
	};
	
	//-----------------------------------------------------------------------
	ahSession.callAgent=async function(msg,vo,timeout){
		return await this.agentNode.call(msg,vo,this.sessionId,timeout);
	};
	
	//-----------------------------------------------------------------------
	ahSession.execAgentEnd=async function(result,error){
		let msgVO;
		if(!this.isExecuting){
			return;
		}
		this.isExecuting=false;
		msgVO={
			msg:"ExecAgentEnd",
			result:result,
			error:error
		};
		await this.clientWS.send(JSON.stringify(msgVO));
	};
}

export default AhSession;
export {AhSession};