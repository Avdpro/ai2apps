import pathLib from "path";
import {AhAgentNode} from "./AhAgentNode.mjs";
import {proxyCall} from "../util/ProxyCall.js";

//***************************************************************************
//AhSystem
//***************************************************************************
let AhSystem,ahSystem;
{
	const AH_AgentDir=process.env.AGENT_HUB_AGENTDIR||"agents";
	const AH_CondaPath=process.env.AGENT_HUB_CONDAPATH||"~/anaconda3/etc/profile.d/conda.sh";
	const AH_CondaEnv=process.env.AGENT_HUB_CONDAENV||null;
	
	//-----------------------------------------------------------------------
	AhSystem=function(app){
		this.app=app;
		this.nodeMap=new Map();
		//Make agent dir path:
		this.agentDir=AH_AgentDir;
		this.condaPath=AH_CondaPath;
		this.condaEnv=AH_CondaEnv;
		if(this.agentDir[0]!=="/"){
			this.agentDir=pathLib.join(this.app.get("AppHomePath"),this.agentDir);
		}
	};
	ahSystem=AhSystem.prototype={};
	
	//-----------------------------------------------------------------------
	ahSystem.startAgentNode=async function(nodeName,path,options){
		let agentNode;
		options=options||{};
		
		//TODO: load node info from file?
		
		//Make sure path:
		path=path||options.path;
		if(!path){
			path=pathLib.join(this.agentDir,nodeName);
		}else if(path[0]!=="/"){
			path=pathLib.join(this.agentDir,path);
		}
		
		//Find current instance:
		agentNode=this.nodeMap.get(nodeName);
		if(agentNode){
			if(options.forceRestart){
				this.nodeMap.delete(nodeName);
				await agentNode.stop();
				agentNode=null;
			}else if(options.checkUpdate){
				if(await agentNode.checkUpdate()){
					this.nodeMap.delete(nodeName);
					await agentNode.stop();
					agentNode=null;
				}
			}
			if(agentNode) {
				return agentNode;
			}
		}
		
		agentNode=new AhAgentNode(this,nodeName);
		this.nodeMap.set(nodeName,agentNode);
		await agentNode.start(path,options);
		return agentNode;
	};
	
	//-----------------------------------------------------------------------
	ahSystem.createSession=async function(nodeName){
		let agent,session;
		agent=await this.getAgentNode(nodeName);
		session=await agent.newSession();
		return session;
	};
	
	//-----------------------------------------------------------------------
	ahSystem.getAgentNode=async function(path,options){
		let agent;
		agent=this.nodeMap.get(path);
		if(!agent){
			agent=new AhAgentNode(this);
			this.nodeMap.set(path,agent);
			await agent.start(path,options);
		}
		return agent;
	};
	
	//-----------------------------------------------------------------------
	ahSystem.OnNodeStop=function(nodeName,node){
		if(this.nodeMap.get(nodeName)===node) {
			this.nodeMap.delete(nodeName);
		}
	};
	
	//-----------------------------------------------------------------------
	ahSystem.handleCallHub=async function(msg,vo,session){
		let handler;
		handler=this.apiMap[msg]||proxyCall;
		if(handler){
			let callReq,callRes,result,pms,callback,callerr;
			pms=new Promise((resolve,reject)=>{
				callback=resolve;
				callerr=reject;
			});
			callReq={
				body:{msg:msg,vo:vo},
			};
			if(session){
				callReq.headers={host:session.userReqHost};
				vo.userId=session.userId;
				vo.token=session.userToken;
			}
			callRes={
				json:async function(res){
					result=res;
					callback();
				}
			}
			try {
				await handler(callReq, callRes);
			}catch(err){
				callback();
				result={code:500,info:""+err};
			}
			await pms;
			return result;
		}else{
			return {code:404,info:`Can't find callHub handler: ${msg}`};
		}
	};
	
	//-----------------------------------------------------------------------
	ahSystem.setup=async function(router,apiMap){
		let app,cfgPath,self;
		self=this;
		app=self.app;
		this.apiMap=apiMap;
		
		//Apply external agent connection:
		let selectorMap=app.get("WebSocketSelectorMap");
		selectorMap.set("RegisterAgentNode",(ws,msg)=>{
			let name,agentNode;
			name=msg.name;
			if(name) {
				agentNode = self.nodeMap.get(name);
				if (!agentNode) {
					agentNode = new AhAgentNode(self, name);
					self.nodeMap.set(msg.name, agentNode);
				}
				agentNode.OnNodeConnect(ws, msg).then(()=>{
					console.log(`AgentNode<${name}> connectd.`);
				});
			}
		});
		
		//-------------------------------------------------------------------
		apiMap['StartAgentNode']=async function(req,res){
			let reqVO,nodeName,path,options,node;
			reqVO = req.body.vo;
			nodeName=reqVO.name;
			path=reqVO.path;
			options=reqVO.options||reqVO.opts||{};
			if(!nodeName){
				res.json({ code: 400, info:`StartAgentNode: Missing AgentNode name to start.`});
				return;
			}
			node=self.nodeMap.get(nodeName);
			if(!node){//Make sure path:
				if(!path && !nodeName){
					res.json({ code: 400, info:`StartAgentNode: Missing AgentNode name and path to start.`});
					return;
				}
			}
			await self.startAgentNode(nodeName,path,options);
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		apiMap['AhCreateSession']=async function(req,res){
			let reqVO,nodeName,options,session;
			let userId,token;
			reqVO = req.body.vo;
			nodeName=reqVO.node;
			options=reqVO.options||{};
			if(!nodeName){
				res.json({ code: 400, info:`CreateSession: Missing agent-node-name to create.`});
				return;
			}
			session=await self.createSession(nodeName);
			if(!session){
				res.json({ code: 500, info:`Create session failed`});
				return;
			}
			//Keep userInfo for later hubCall
			session.userReqHost=req.headers.host;
			session.userId=reqVO.userId;
			session.userToken = reqVO.token;
			res.json({ code: 200, sessionId: session.sessionId});
		};
	};
}
export default async function(app,router,apiMap) {
	let ahSys;
	ahSys=new AhSystem(app);
	await ahSys.setup(router,apiMap);
	return ahSys;
};
export {AhSystem};
