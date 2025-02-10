import pathLib from "path";
import EventEmitter from "events";

//****************************************************************************
//:AATool
//****************************************************************************
let AATool,aaTool;
{
	//------------------------------------------------------------------------
	AATool=function(){
		EventEmitter.call(this);
		this.filePath="";
		this.type="";
		this.codeName="";
		this.name="";
		this.description="";
		this.icon="";
		this.package="";
		this.modual=null;
		this.isRPA=false;
		this.rpaHost="";
		this.enable=true;
		this.multiInstance=true;
	};
	aaTool=AATool.prototype = Object.create(EventEmitter.prototype);
	aaTool.constructor = AATool;

	AATool.TYPE_NONE="";
	AATool.TYPE_APP="App";
	AATool.TYPE_PAGE="Page";
	AATool.TYPE_AGENT="Agent";
	AATool.TYPE_GUIDE="Guide";
	AATool.TYPE_API="API";
	
	//-----------------------------------------------------------------------
	aaTool.load=async function(path){
		let apiList,apiVO,modual;
		this.filePath=path;
		try {
			modual = this.modual = await import(path);
			apiList = modual.ChatAPI;
			if (Array.isArray(apiList)) {
				apiVO = apiList[0];
			}
			if (apiVO) {
				this.name = apiVO.def.name;
				this.description = apiVO.def.description;
				this.icon = apiVO.icon;
				if (apiVO.agent) {
					this.type = AATool.TYPE_AGENT;
				} else {
					this.type = AATool.TYPE_API;
				}
				this.isRPA = apiVO.isRPA;
				if (this.isRPA) {
					this.rpaHost = apiVO.rpaHost;
				}
				return true;
			}
			return false;
		}catch(err){
			return false;
		}
	};

	//------------------------------------------------------------------------
	aaTool.getName=aaTool.getNameText=function(lan){
		let text=this.name;
		if(text.EN){
			text=text[lan]||text.EN;
		}
		return text;
	};
	
	//------------------------------------------------------------------------
	aaTool.getDescText=function(lan){
		let text=this.description;
		if(text.EN){
			text=text[lan]||text.EN;
		}
		return text;
	};
}

//****************************************************************************
//:AATools
//****************************************************************************
let AATools;
{
	let aaTools;
	let toolMap=new Map();
	//------------------------------------------------------------------------
	AATools=function(session,basePath){
		this.basePath=basePath;
		this.session=session;
		this.tools=null;
		this.scope=null;
		this.scopeHash=null;
	};
	aaTools=AATools.prototype={};
	
	//------------------------------------------------------------------------
	aaTools.load=async function(toolList){
		let path,tools,tool,session,basePath;
		session=this.session;
		basePath=this.basePath;
		if(!basePath){
			basePath=session.agentNode.path;
		}
		if(typeof(toolList)==="string"){
			if(session.agentNode.nodeJSON.tools) {
				toolList = session.agentNode.nodeJSON.tools[toolList];
				if(!toolList || !toolList.length){
					return false;
				}
			}else{
				return false;
			}
		}
		tools=this.tools=[];
		for(path of toolList){
			if (path.startsWith("/@")) {
				path = "../" + path.slice(2);
			}
			if(path[0]!=="/"){
				path=pathLib.join(this.basePath,path);
			}
			tool=toolMap.get(path);
			if(tool){
				tools.push(tool);
			}else{
				tool=new AATool(basePath);
				if(await tool.load(path)){
					toolMap.set(path,tool);
					tools.push(tool);
				}
			}
		}
		return tools.length>0;
	};
	
	//------------------------------------------------------------------------
	aaTools.getScope=function(lan="EN"){
		let scope,scopeHash,tools,tool,i,n,name;
		if(this.scope){
			return this.scope;
		}
		scope={};
		scopeHash={};
		tools=this.tools||[];
		if(!tools){
			return null;
		}
		n=tools.length;
		for (i=0;i<n;i++) {
			tool=tools[i];
			name=tool.getName(lan);
			scope[name]=tool.getDescText(lan);
			scopeHash[name]=tool;
		}
		this.scope=scope;
		this.scopeHash=scopeHash;
		return scope;
	};
	
	//------------------------------------------------------------------------
	aaTools.runTool=async function(toolName,args){
		let tool;
		if(!this.scopeHash){
			throw Error("Missing scopeHash.");
		}
		tool=this.scopeHash[toolName];
		if(!tool){
			throw Error("Missing tool: "+toolName);
		}
		return await this.session.pipeChat(tool.filePath,args);
	};
}

export default AATools;
export {AATools};