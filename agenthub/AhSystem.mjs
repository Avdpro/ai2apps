import pathLib from "path";
import {AhAgentNode} from "./AhAgentNode.mjs";
import { promises as fs } from 'fs';
import AhFileLib from "./AhFileLib.mjs"
import { exec } from 'child_process';
import util from "util";
import ProxyCall from '../util/ProxyCall.js'
const { callProxy,proxyCall }=ProxyCall;

const execPromise = util.promisify(exec);
const checkCondaInstallation = async () => {
	try {
		const { stdout, stderr } = await execPromise('conda info --base');
		if (stderr) {
			return null;
		}
		const condaPath = stdout.trim();
		if (condaPath) {
			return condaPath;
		} else {
			return null;
		}
	}catch(error){
		return null;
	}
};

async function getSubDirs(dirPath) {
	try {
		const files = await fs.readdir(dirPath);
		const subDirs = [];
		
		for (const file of files) {
			const filePath = pathLib.join(dirPath, file);
			const stats = await fs.stat(filePath);
			if (stats.isDirectory()) {
				subDirs.push(file);
			}
		}
		
		return subDirs;
	} catch (err) {
		console.error(`Error reading directory:${dirPath}`, err);
		return [];
	}
}


//***************************************************************************
//AhSystem
//***************************************************************************
let AhSystem,ahSystem;
{
	const AH_AgentDir=process.env.AGENT_HUB_AGENTDIR||"agents";
	let AH_CondaPath=process.env.AGENT_HUB_CONDAPATH;
	const AH_CondaEnv=process.env.AGENT_HUB_CONDAENV||null;
	
	
	//-----------------------------------------------------------------------
	AhSystem=function(app){
		this.app=app;
		this.configJSON=null;
		this.description="Agent Hub.";
		this.staticNodes=[];
		this.staticNodeMap=new Map();
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
	ahSystem.scanAgents=async function(autoStart){
		let dirs,dir,path,nodeJSON,staticNodes,staticMap;
		staticNodes=this.staticNodes;
		staticMap=this.staticNodeMap;
		dirs=await getSubDirs(this.agentDir);
		for(dir of dirs){
			path=pathLib.join(this.agentDir,dir,"agent.json");
			try{
				nodeJSON=await fs.readFile(path,"utf8");
				nodeJSON=JSON.parse(nodeJSON);
				if(nodeJSON.entry && nodeJSON.expose){
					nodeJSON.name=dir;
					if(!staticMap.get(dir)){
						staticNodes.push(nodeJSON);
						staticMap.set(dir,nodeJSON);
					}
					if(autoStart && nodeJSON.autoStart){
						await this.startAgentNode(dir,pathLib.join(this.agentDir,dir),{checkUpdate:nodeJSON.checkUpdate});
						console.log(`Static node ${dir} started.`);
					}
				}
			}catch(err){
				//Do nothing, check next dir.
			}
		}
	};
	
	//-----------------------------------------------------------------------
	ahSystem.startHub=async function(){
		let hubJSON,nodes,nodeName,nodePath,nodeJSON;
		
		if(!this.condaPath){
			//get conda path:
			console.log("Finding current system conda path");
			this.condaPath=await checkCondaInstallation();
			if(this.condaPath){
				console.log(`Found conda: ${this.condaPath}`);

				if (process.platform === "win32"){
					this.condaPath  = pathLib.join(this.condaPath, 'Scripts', 'conda.exe');
				}
				else{
					this.condaPath+="/etc/profile.d/conda.sh";
				}
			}else{
				console.log("Warning: conda not found in the system. You may encounter issues when running python agents.");
			}
		}
		
		try {
			hubJSON=await fs.readFile(pathLib.join(this.agentDir, "agenthub.json"), "utf8");
			hubJSON=JSON.parse(hubJSON);
		}catch(err){
			hubJSON= {};
		}
		if(!hubJSON){
			return;
		}
		this.configJSON=hubJSON;
		this.description=hubJSON.description||this.description;
		await this.scanAgents(true);
		/*
		nodes=hubJSON.nodes;
		for(nodeName in nodes){
			nodePath=nodes[nodeName];
			try {
				nodeJSON=await fs.readFile(pathLib.join(this.agentDir, nodePath,"agent.json"), "utf8");
				nodeJSON=JSON.parse(nodeJSON);
			}catch(err){
				nodeJSON={
					name:nodeName,
				}
			}
			console.log(`Static node ${nodeName} loaded.`);
			nodeJSON.name=nodeName;
			if(nodeJSON.expose!==false){
				this.staticNodes.push(nodeJSON);
				this.staticNodeMap.set(nodeName,nodeJSON);
			}
			if(nodeJSON.autoStart){
				await this.startAgentNode(nodeName,nodePath,{checkUpdate:nodeJSON.checkUpdate});
				console.log(`Static node ${nodeName} started.`);
			}
		}*/
	};
	
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
			if(options.forceRestart || !agentNode.nodeWS){
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
		try {
			await agentNode.start(path, options);
		}catch(err){
			if(this.nodeMap.get(nodeName)===agentNode){
				this.nodeMap.delete(nodeName);
			}
			throw err;
		}
		return agentNode;
	};
	
	//-----------------------------------------------------------------------
	ahSystem.stopAgentNode=async function(nodeName){
		let agentNode;
		//Find current instance:
		agentNode=this.nodeMap.get(nodeName);
		if(agentNode) {
			this.nodeMap.delete(nodeName);
			await agentNode.stop();
		}
	}
	
	//-----------------------------------------------------------------------
	ahSystem.createSession=async function(nodeName,options){
		let agentNode,session;
		agentNode=await this.getAgentNode(nodeName);
		if(agentNode) {
			session = await agentNode.newSession(options);
		}else{
			session=null;
		}
		return session;
	};
	
	//-----------------------------------------------------------------------
	ahSystem.createTerm=async function(nodeName,options){
		let agentNode,term;
		agentNode=await this.getAgentNode(nodeName);
		if(agentNode) {
			term = await agentNode.newTerm(options);
			return term;
		}
		return null;
	};
	
	//-----------------------------------------------------------------------
	ahSystem.closeTerm=async function(nodeName,sessionId){
		let agentNode,term;
		agentNode=await this.getAgentNode(nodeName);
		if(agentNode){
			await agentNode.closeTerm(sessionId);
		}
	}
	
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
	ahSystem.handleCallHub=async function(msg,vo,session,devKey){
		let handler;
		handler=this.apiMap[msg]||proxyCall;
		if(handler){
			let callReq,callRes,result,pms,callback,callerr;
			pms=new Promise((resolve,reject)=>{
				callback=resolve;
				callerr=reject;
			});
			callReq={
				body:{msg:msg,vo:vo,devKey:devKey},
				headers:{host:"AgentHub"}
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
				callerr(err);
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
		
		await self.startHub();
		await AhFileLib.setup(self,app,router,apiMap);
		
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
			let userId,token,language;
			reqVO = req.body.vo;
			nodeName=reqVO.node;
			options=reqVO.options||{};
			language=reqVO.language||options.language||self.configJSON.language||"CN";
			if(!nodeName){
				res.json({ code: 400, info:`CreateSession: Missing agent-node-name to create.`});
				return;
			}
			options.language=language;
			session=await self.createSession(nodeName,options);
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
		
		//-------------------------------------------------------------------
		apiMap['AhListAgentNodes']=async function(req,res){
			let reqVO,userId,token,nodeMap,nodeVO,node,staticVO;
			let list;
			reqVO = req.body.vo;
			await self.scanAgents(false);
			nodeMap=new Map();
			list=self.staticNodes;
			for(nodeVO of list){
				nodeMap.set(nodeVO.name,{...nodeVO,active:false,external:false});
			}
			list=Array.from(self.nodeMap.values());
			for(node of list){
				staticVO=nodeMap.get(node.name);
				nodeVO={
					name:node.name,
					description:node.description,
					chatEntry:node.chatEntry,
					userGroups:Array.from(node.userGroups.values()),
					agents:node.agents,
					active:true,
					external:true
				};
				if(staticVO){
					Object.assign(staticVO,nodeVO);
				}else {
					nodeMap.set(nodeVO.name, nodeVO);
				}
			}
			res.json({ code: 200, nodes:Array.from(nodeMap.values())});
		};
		
		//-------------------------------------------------------------------
		apiMap['AhNodeState']=async function(req,res){
			let reqVO,nodeName,node,stateVO,list;
			reqVO = req.body.vo;
			nodeName=reqVO.name;
			if(!nodeName){
				res.json({ code: 400, info:`StopAgentNode: Missing AgentNode name to stop.`});
				return;
			}
			node=self.nodeMap.get(nodeName);
			if(node) {//Make sure path:
				stateVO={
					name:node.name,
					description:node.description,
					chatEntry:node.chatEntry,
					agents:node.agents,
					active:true,
					workload:node.workload,
				};
				res.json({code:200,state:stateVO});
				return;
			}
			list=self.staticNodes;
			for(stateVO of list){
				if(stateVO.name===nodeName){
					stateVO={
						name:stateVO.name,
						description:stateVO.description,
						chatEntry:stateVO.chatEntry,
						agents:stateVO.agents,
						active:false
					};
					res.json({code:200,state:stateVO});
					return;
				}
			}
			res.json({code:404,info:`Node ${nodeName} not found.`});
		}
		
		//-------------------------------------------------------------------
		apiMap['StopAgentNode']=async function(req,res){
			let reqVO,nodeName,node;
			reqVO = req.body.vo;
			nodeName=reqVO.name;
			if(!nodeName){
				res.json({ code: 400, info:`StopAgentNode: Missing AgentNode name to stop.`});
				return;
			}
			node=self.nodeMap.get(nodeName);
			if(node){//Make sure path:
				self.stopAgentNode(nodeName);
			}
			res.json({ code: 200});
		};
		
		//-------------------------------------------------------------------
		apiMap['AhInstallAgentNode']=async function(req,res){
			let reqVO,nodeName,node,nodeData;
			reqVO = req.body.vo;
			nodeName=reqVO.name;
			nodeData=reqVO.data;
			if(!nodeName){
				res.json({ code: 400, info:`AhInstallAgentNode: Missing AgentNode name to install.`});
				return;
			}
			node=self.nodeMap.get(nodeName);
			if(node){//Make sure path:
				self.stopAgentNode(nodeName);
			}
			//TODO: make dir and extract data:
			
			res.json({ code: 200});
			
		};
		
		//-------------------------------------------------------------------
		apiMap['XTermCreate']=async function(req,res){
			let reqVO,nodeName,options,term;
			let userId,token,language;
			reqVO = req.body.vo;
			nodeName=reqVO.node;
			options=reqVO.options||{};
			if(!nodeName){
				res.json({ code: 400, info:`CreateSession: Missing agent-node-name to create.`});
				return;
			}
			
			term=await self.createTerm(nodeName,options);
			term.userReqHost=req.headers.host;
			term.userId=reqVO.userId;
			term.userToken = reqVO.token;
			res.json({ code: 200, sessionId:term.sessionId});
		};

		//-------------------------------------------------------------------
		apiMap['XTermClose']=async function(req,res){
			let reqVO,nodeName,term;
			let userId,token,language,sessionId;
			reqVO = req.body.vo;
			nodeName=reqVO.node;
			sessionId=reqVO.session||reqVO.sessionId;
			if(!nodeName){
				res.json({ code: 400, info:`CreateSession: Missing agent-node-name to create.`});
				return;
			}
			await self.closeTerm(nodeName,sessionId);
			res.json({ code: 200});
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
