import WebSocket, { WebSocketServer }from 'ws';

let RemoteSession,remoteSession;
//----------------------------------------------------------------------------
RemoteSession=function(localSession,sessionId){
	this.session=localSession;
	this.sessionId=sessionId;
	this.ws=null;
	this.isConnected=false;
	
	this.execCallback=null;
	this.execErrorCallback=null;
};
remoteSession=RemoteSession.prototype={};

//----------------------------------------------------------------------------
RemoteSession.exec=async function(session,nodeName,agent,input,options){
	let res,startNodeOpts,callAgentOpts;
	options=options||{};
	if(options){
		startNodeOpts={checkUpdate:options.checkUpdate??false};
		callAgentOpts={fromAgent:options.fromAgent??null,askUpwardSeg:options.askUpwardSeg??null};
	}else{
		startNodeOpts={checkUpdate:true};
		callAgentOpts={};
	}

	res=await session.callHub("StartAgentNode",{name:nodeName,path:options.nodeEntry,options:startNodeOpts,language:session.langauge});
	if(!res || res.code!==200){
		if(res){
			throw Error(`Start AgentNode error: ${res.info}`);
		}else{
			throw Error(`Start AgentNode error`);
		}
	}
	res=await session.callHub("AhCreateSession",{node:nodeName,language:session.language});
	if(!res || res.code!==200){
		if(res){
			throw Error(`Start AgentNode error: ${res.info}`);
		}else{
			throw Error(`Start AgentNode error`);
		}
	}
	let sessionId=res.sessionId;
	let remoteSsn=new RemoteSession(session,sessionId);
	await remoteSsn.start();
	return await remoteSsn.execAgent(agent,input,callAgentOpts);
};

//----------------------------------------------------------------------------
remoteSession.start=async function(){
	let pms,callback,callerror;
	pms=new Promise((resolve,reject)=>{
		callback=resolve;
		callerror=reject;
	});
	let selector,ws;	
	this.isConnected=false;
	selector=this.sessionId;
	ws=this.ws=new WebSocket(this.session.agentNode.host);
	ws.addEventListener('open',()=>{
		ws.send(JSON.stringify({msg:"CONNECT",selector:selector}));
		console.log("Remote session WS connected.");
	});
	ws.addEventListener('message', (msg) => {
		let msgVO,msgCode;
		console.log("Message from remote session:");
		console.log(msg)
		msgVO=JSON.parse(msg.data);
		msgCode=msgVO.msg;
		if(!this.isConnected){
			if(msgCode==="CONNECTED"){
				let call;
				this.isConnected=true;
				//Notify into chat session:
				call=callback;
				if(call){
					callback=null;
					callerror=null;
					call();
				}
				console.log("Remote session ready.");
			}else{
				let handler;
				handler="WSMSG_"+msgCode;
				handler=this[handler]||ws[handler];
				if(handler){
					handler.call(this,msgVO);
				}
				console.log("Message from remote session:");
				console.log()
			}
		}else{
			let handler;
			handler="WSMSG_"+msgCode;
			handler=this[handler]||ws[handler];
			if(handler){
				handler.call(this,msgVO);
			}
		}
	});
	ws.addEventListener('close', (msg) => {
		if(this.isConnected){
			let call;
			this.isConnected=false;
			call=this.execErrorCallback;
			if(call){
				this.execCallback=null;
				this.execErrorCallback=null;
				call("Session end.");
			}
			//Notify not connected...
		}else{
			let call;
			call=callerror;
			if(call){
				callback=null;
				callerror=null;
				call("Session start failed.");
			}
		}
		this.webSocket=null;
		this.sessionId=null;
	});
	ws.addEventListener('error', (msg) => {
		//wsError(msg);
		//TODO: Show error in session?
	});
	
	//Wait remote session ready:
	try{
		await pms;
	}catch(err){
		console.log("RemoteSession start failed:");
		console.error(err);
		return;
	}
};

//----------------------------------------------------------------------------
remoteSession.execAgent=async function(agent,prompt,opts){
	let ws,pms,callback,callerror,result;
	opts=opts||{};
	ws=this.ws;
	if(!ws){
		throw Error("RemoteSession missing websocket to execAgent");
	}
	pms=new Promise((resolve,reject)=>{
		this.execCallback=resolve;
		this.execErrorCallback=reject;
	});
	this.upperAgent=this.fromAgent=opts.fromAgent;
	this.askUpwardSeg=opts.askUpwardSeg;

	//Execute agent:
	ws.send(JSON.stringify({msg:"ExecAgent",sessionId:this.sessionId,agent:agent,prompt:prompt}));
	result=await pms;
	console.log("RemoteSession execute result: ");
	console.log(result);
	return result;
};

//----------------------------------------------------------------------------
//Agent send message to client:
remoteSession.WSMSG_Message=async function(msg){
	let session,callVO,msgCode,msgVO;
	callVO=msg.message;
	msgCode=callVO.msg;
	msgVO=callVO.vo;
	session=this.session;
	await session.sendToClient(msgCode, msgVO);
};

//----------------------------------------------------------------------------
//Agent call client:
remoteSession.WSMSG_Call=async function(msg){
	let session,callVO,callId,msgCode,msgVO,result;
	callId=msg.callId;
	callVO=msg.message;
	msgCode=callVO.msg;
	msgVO=callVO.vo;
	session=this.session;
	try{
		switch(msgCode){
			case "AskUpward": {
				result=await session.askUpward(this,msgVO.prompt);
				break;
			}
			default:{
				result =await session.callClient(msgCode,msgVO);
				break;
			}
		}
		this.ws.send(JSON.stringify({msg:"CallResult",sessionId:this.sessionId,callId:callId,result:result}));
		return result;
	}catch(err){
		let errMsg=JSON.stringify({msg:"CallResult",sessionId:this.sessionId,callId:callId,error:""+err});
		this.ws.send(errMsg);
	}
};

//----------------------------------------------------------------------------
//Agent send message to client:
remoteSession.WSMSG_ExecAgentEnd=async function(msg){
	let session,result,error,call;
	result=msg.result;
	error=msg.error;

	await this.ws.close(1000,"Finish");

	if(error){
		call=this.execErrorCallback;
		if(call){
			this.execCallback=null;
			this.execErrorCallback=null;
			call(error);
		}
	}else{
		call=this.execCallback;
		if(call){
			this.execCallback=null;
			this.execErrorCallback=null;
			call(result);
		}
	}
};

export default RemoteSession;
export {RemoteSession};
