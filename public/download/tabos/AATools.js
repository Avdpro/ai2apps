import {VFACT} from "/@vfact";
import {makeObjEventEmitter,makeNotify} from "./utils/events.js";
import pathLib from "./utils/path.js";
function getDomain(url) {
	try{
		if((!url.startsWith("http://"))||(!url.startsWith("https://"))){
			url="https://"+url;
		}
		const parsedUrl = new URL(url);
		const hostname = parsedUrl.hostname;
		if (hostname) {
			const domainParts = hostname.split('.');
			if (domainParts.length >= 2) {
				return domainParts.slice(-2).join('.');
			} else {
				return hostname;
			}
		}
		return url;
	}catch(err){
		return url;
	}
}
const safeToolsJSON={
	"tools": [
		{
			"type": "ChatApp",
			"chatEntry": "Tool",
			"filePath": "/~/-AutoDeploy/app.html",
			"name": {
				"EN": "AI Frontier",
				"CN": "AI Frontier"
			},
			"description": {
				"EN": "Find, delopy and use newest AI models as agents.",
				"CN": "发现、部署最新的AI模型，并作为智能体使用。"
			},
			"icon": "/@AutoDeploy/assets/aifrontier.svg",
			"package": "AutoDeploy",
			"group": "Tools",
			"enable": true
		},
		{
			"type": "Agent",
			"filePath": "/~/-AutoDeploy/ai/AutoDeploy.js",
			"package": "AutoDeploy",
			"enable": true
		},
		{
			"filePath": "/~/-user/toolmart.html",
			"type": "App",
			"name": {
				"EN": "Tool Mart",
				"CN": "工具市场"
			},
			"description": {
				"EN": "Find and install Tool, App, AI Agent and develop API from community cloud.",
				"CN": "在社区云上发现安装各种工具、App、AI智能体和开发API。"
			},
			"icon": "store.svg",
			"package": "user",
			"enable": true,
			"keyTool": true,
			"metaName": "ToolMart@user",
			"multiInstance": false,
			"appFrameW": 800,
			"appFrameH": 600
		},
		{
			"filePath": "/@tabedit/app.html",
			"type": "Page",
			"name": "TabOS IDE",
			"description": {
				"EN": "A powerful visual IDE for developing various AI agents and apps.",
				"CN": "用于开发各种AI智能体以及App的强大的可视化IDE。"
			},
			"keyTool":true,
			"icon": "prj.svg",
			"package": "tabedit",
			"enable": true,
			"handleFiles":{
				"edit":[".project.json"],
				"open":[".project.json"]
			}
		},
		{
			"filePath": "/@tabedit/edlit.html",
			"type": "App",
			"name": "Edit Pad",
			"metaName":"EditPad@tabedit",
			"appFrameW": 800,
			"appFrameH": 800,
			"description": {
				"EN": "Simple yet powerful text editor.",
				"CN": "简单而强大的文本编辑器。"
			},
			"keyTool":true,
			"icon": "hudedit.svg",
			"package": "tabedit",
			"enable": true,
			"handleFiles":{
				"edit":[".js",".mjs",".json",".css",".jsx",".ts",".html",".htm",".svg",".md",".c",".cpp",".h",".hpp",".py",".ini",".inf",".link",".sh",".conflict",".baseversion",".compare",".compath"],
				"open":[".js",".mjs",".json",".css",".jsx",".ts",".svg",".c",".cpp",".h",".hpp",".py",".ini",".inf",".link",".conflict",".baseversion",".compare",".compath"]
			}
		},
		{
			"filePath": "/@homekit/ui/DlgProjects.js",
			"type": "App",
			"appFrameW": 600,
			"appFrameH": 750,
			"name": {
				"EN": "New Dev. Project",
				"CN": "新建开发工程"
			},
			"keyTool":true,
			"description": {
				"EN": "Create new dev. project.",
				"CN": "创建新的开发工程项目。"
			},
			"icon": "labadd.svg",
			"package": "homekit"
		},
		{
			"filePath": "/@files/app.html",
			"type": "App",
			"appFrameW": 800,
			"appFrameH": 600,
			"name": {
				"EN": "File Manager",
				"CN": "文件管理器"
			},
			"metaName":"Files@files",
			"keyTool":true,
			"description": {
				"EN": "File manager App for Tab-OS.",
				"CN": "Tab-OS的文件管理器App。"
			},
			"icon": "disk.svg",
			"package": "files"
		},
		{
			"filePath": "/~/-terminal/app.html",
			"type": "App",
			"appFrameW": 800,
			"appFrameH": 500,
			"name": {
				"EN": "Terminal",
				"CN": "命令行终端"
			},
			"metaName":"Terminal@terminal",
			"keyTool":true,
			"description": {
				"EN": "Command line terminal App for Tab-OS.",
				"CN": "Tab-OS的命令行终端App。"
			},
			"icon": "terminal.svg",
			"package": "files"
		},
		//System agents:
		{
			"type": "Agent",
			"filePath": "/@aae/ai/DateTime.js",
			"enable": true,
			"keyTool":true,
		},
		{
			"type": "Agent",
			"filePath": "/@AgentBuilder/ai/ToolReadImage.js",
			"keyTool":true,
			"enable":true,
		},
		{
			"type": "Agent",
			"enable": true,
			"keyTool": true,
			"filePath": "/@AgentBuilder/ai/RpaWebSearch.js"
		},
		{
			"type": "Agent",
			"enable": true,
			"keyTool": true,
			"filePath": "/@AgentBuilder/ai/CodeSingleHtml.js"
		},
	],
	"groups": [
		{
			"codeName": "Favorites",
			"name": {
				"CN": "日常任务",
				"EN": " Favorites"
			},
			"description": "Favorite Apps, Tools or Agents",
			"icon": "star_s.svg",
			"tools": []
		},
		{
			"codeName": "Development",
			"name": {
				"CN": "开发",
				"EN": "Development"
			},
			"description": "Develop",
			"icon": "lab.svg",
			"tools": [
				"/@tabedit/app.html",
				"/@homekit/ui/DlgProjects.js"
			]
		},
		{
			"codeName": "Tools",
			"name": {
				"CN": "工具",
				"EN": "Tools"
			},
			"description": "Tools",
			"icon": "cal.svg",
			"tools": [
				"/@tabedit/editlit.html",
				"/~/-files/app.html",
				"/~/-terminal/app.html"
			]
		}
	],
	"sites": []
};

const defKindReg={
	min:{
		cost:0,
		size:0,
	},
	max:{
		cost:1,
		size:20000,
	},
	weights:{
		cost:{
			costPerCall:1,
			costPer1M:0.2
		},
		overallScore:{
			quality:1,
			cost:0.3,
			speed:0.2,
			size:0.2,
		}
	}
};

//****************************************************************************
//:AATool
//****************************************************************************
let AATool,aaTool;
{
	AATool=function(tools){
		this.aaTools=tools;
		this.filePath="";
		this.type="";
		this.codeName="";
		this.name="";
		this.description="";
		this.icon="";
		this.package="";
		this.modual=null;
		this.isChatApi=true;
		this.isRPA=false;
		this.chatEntry=false;
		this.rpaHost="";
		this.agentNode=null;
		this.appMeta=null;
		this.appFrameW=0;
		this.appFrameH=0;
		this.enable=true;
		this.handleFiles=null;
		this.keyTool=false;
		this.metaName="";
		this.multiInstance=true;
		this.kind="";
		this.capabilities=[];
		this.filters=[];
		this.metrics={};
		this.ranks={
			overallScore:0,quality:0,speed:0,cost:0,size:0
		};
		this.meta=null;
		makeNotify(this);
	};
	aaTool=AATool.prototype={};
	AATool.TYPE_NONE="";
	AATool.TYPE_CHATAPP="ChatApp";
	AATool.TYPE_APP="App";
	AATool.TYPE_PAGE="Page";
	AATool.TYPE_AGENT="Agent";
	AATool.TYPE_GUIDE="Guide";
	AATool.TYPE_API="API";

	//------------------------------------------------------------------------
	aaTool.loadFromPath=async function(path){
		let apiList,apiVO,modual,dirPath,ext;
		ext=pathLib.extname(path);
		dirPath=pathLib.dirname(path);
		this.filePath=path;
		console.log("Will load tool: "+path);
		//Read package info:
		{
			let pos=path.indexOf("/@");
			if(pos>=0){
				let pos2=path.indexOf("/",pos+2);
				if(pos2>0){
					this.package=path.substring(2,pos);
				}else{
					this.package=path.substring(2);
				}
			}
		}
		try{
			modual=this.modual=await import(path);
			apiList=modual.ChatAPI;
			if(Array.isArray(apiList)){
				apiVO=apiList[0];
			}
		}catch{
			let code;
			try{
				let mk1,mk2,pos,pos2,func;
				code=await (await fetch(path)).text();
				mk1=`//#CodyExport>>>`;
				mk2=`//#CodyExport<<<`;
				pos=code.indexOf(mk1);
				if(pos>0){
					pos2=code.indexOf(mk2);
					if(pos2>pos){
						code=code.substring(pos+mk1.length,pos2);
					}else{
						code="";
					}
				}else{
					mk1=`""">>>CodyExport`;
					mk2=`>>>CodyExport"""`;
					pos=code.indexOf(mk1);
					if(pos>0){
						pos2=code.indexOf(mk2);
						if(pos2>pos){
							code=code.substring(pos+mk1.length,pos2);
						}else{
							code="";
						}
					}else{
						code="";
					}
				}
				
				if(code.indexOf("ChatAPI=[{")<0){
					throw "NoAPI"
				}
				code+="\nreturn ChatAPI;";
				func=new Function("VFACT",code);
				apiList=func(VFACT);
				apiList=apiList.api||apiList;
				if(Array.isArray(apiList)){
					apiVO=apiList[0];
				}
			}catch(err){
				apiVO=null;
			}
		}
		if(apiVO){
			let name,desc,icon;
			name=apiVO.label||apiVO.def.name;
			if(name.startsWith("{") && name.endsWith("}")){
				try{
					name=JSON.parse(name);
				}catch(err){
				}
			}
			desc=apiVO.def.description;
			if(desc.startsWith("{") && desc.endsWith("}")){
				try{
					desc=JSON.parse(desc);
				}catch(err){
				}
			}
			this.name=name
			this.description=desc;
			icon=apiVO.icon;
			if(icon){
				if(icon[0]==="."){
					icon=pathLib.join(dirPath,icon);
				}else if(icon.indexOf("/")<0){
					icon=`/~/-tabos/shared/assets/${icon}`;
				}
			}
			this.icon=icon;
			if(apiVO.agentNode){
				this.type=AATool.TYPE_AGENT;
				this.agentNode=apiVO.agentNode;
			}else if(apiVO.agent){
				this.type=AATool.TYPE_AGENT;
			}else{
				this.type=AATool.TYPE_API;
			}
			this.isRPA=apiVO.isRPA;
			if(this.isRPA){
				this.rpaHost=apiVO.rpaHost;
			}
			this.isChatApi=apiVO.isChatApi!==false;
			this.chatEntry=apiVO.chatEntry;
			this.kind=apiVO.kind||this.kind;
			this.capabilities=apiVO.capabilities||this.capabilities;
			this.filters=apiVO.filters||this.filters;
			this.metrics=apiVO.metrics||this.metrics;
			this.ranks=apiVO.ranks||this.ranks||{};
			if(apiVO.meta){
				this.meta=apiVO.meta;
			}
			if(Array.isArray(this.filters)){
				let filters,list,item,k,v;
				filters={};
				list=this.filters;
				for(item of list){
					k=item.key; v=item.value;
					if(!filters[k]){
						filters[k]=[];
					}
					filters[k].push(v);
				}
				this.filters=filters;
			}
			{
				let caps,cap,name,pos,i,n,score;
				caps=this.capabilities;
				n=caps.length;
				for(i=0;i<n;i++){
					cap=caps[i];
					pos=cap.indexOf(":");
					if(pos>0){
						name=cap.substring(0,pos).trim();
						score=parseFloat(cap.substring(pos+1).trim())||0;
						caps[i]=name;
						if(score>=0 && !(name in this.ranks)){
							this.ranks[name]=score;
						}
					}
				}
			}
			return true;
		}
		apiVO=modual.tool;
		if(apiVO && apiVO.guide){
			this.type=AATool.TYPE_GUIDE;
			this.name=apiVO.name;
			this.description=apiVO.description;
			this.icon=apiVO.icon;
			this.isRPA=true;
			this.isChatApi=false;
			this.rpaHost=apiVO.rapHost;
			return true;
		}
		throw Error(`${path} is not a tool file.`);
	};
	
	//------------------------------------------------------------------------
	aaTool.loadFromVO=async function(vo){
		this.filePath=vo.filePath;
		this.type=vo.type;
		this.name=vo.name;
		this.description=vo.description||"";
		this.icon=vo.icon||"gas.svg";
		this.package=vo.package;
		this.isRPA=vo.isRPA;
		this.isChatApi=vo.isChatApi!==false;
		this.rpaHost=vo.rpaHost;
		this.agentNode=vo.agentNode;
		this.modual=null;
		this.appMeta=null;
		this.appFrameW=vo.appFrameW||0;
		this.appFrameH=vo.appFrameH||0;
		this.enable=vo.enable===false?false:true;
		this.keyTool=vo.keyTool||false;
		this.metaName=vo.metaName||this.filePath;
		this.multiInstance=vo.multiInstance!==false;
		this.chatEntry=vo.chatEntry;
		if(vo.handleFiles){
			this.handleFiles=vo.handleFiles;
		}
	};

	//------------------------------------------------------------------------
	aaTool.genSaveVO=async function(){
		let vo = {};
		vo.filePath = this.filePath;
		vo.type = this.type;
		vo.name = this.name;
		vo.description = this.description;
		vo.icon = this.icon;
		vo.package = this.package;
		vo.isRPA = this.isRPA;
		vo.isChatApi=this.isChatApi!==false;
		vo.rpaHost = this.rpaHost;
		vo.agentNode=this.agentNode;
		vo.enable = !!this.enable;
		vo.keyTool = !!this.keyTool;
		vo.metaName = this.metaName;
		vo.multiInstance=this.multiInstance;
		this.chatEntry=vo.chatEntry;
		if(this.appFrameW>0){
			vo.appFrameW=this.appFrameW;
		}
		if(this.appFrameH>0){
			vo.appFrameH=this.appFrameH;
		}
		if(this.handleFiles){
			vo.handleFiles=this.handleFiles;
		}
		return vo;
	};
	
	//------------------------------------------------------------------------
	aaTool.genInfoVO=function(lan){
		let vo={};
		let ref;
		vo.filePath = this.filePath;
		vo.type = this.type;
		vo.name = this.getNameText();
		vo.description = this.getDescText();
		vo.icon = this.icon;
		vo.package = this.package;
		vo.isRPA = this.isRPA;
		vo.isChatApi=this.isChatApi!==false;
		vo.rpaHost = this.rpaHost||"NA";
		vo.agentNode= this.agentNode;
		vo.enable = !!this.enable;
		vo.keyTool = !!this.keyTool;
		ref=this.getReference();
		ref.groups=ref.groups.map((g)=>g.getNameText(lan));
		ref.chains=ref.chains.map((c)=>c.getNameText(lan));
		vo.reference=`Chains: ${ref.chains.length?ref.chains:0}. Groups: ${ref.groups.length?ref.groups:0}.`;
		return vo;
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
	
	//------------------------------------------------------------------------
	aaTool.getReference=function(){
		return this.aaTools.getToolRef(this);
	};
	
	//------------------------------------------------------------------------
	aaTool.genAppMeta=function(lan,orgMeta){
		let tool=this;
		switch(tool.type){
			case "App":
			case "ChatApp":{
				let meta,icon;
				meta=tool.appMeta;
				if(!meta){
					let ext;
					ext=pathLib.extname(tool.filePath).toLowerCase();
					icon=tool.icon;
					if(icon[0]!=="/"){
						icon="/~/-tabos/shared/assets/"+icon;
					}
					meta={
						type:"app",
						name:tool.name,
						caption:tool.getName(lan),
						icon:icon,
						package:tool.package,
						appFrame:{
							group:tool.filePath,
							caption:tool.name,openApp:true,
							multiInstance:(tool.multiInstance!==false),
							icon:icon,
							width:tool.appFrameW||360,
							height:tool.appFrameH||600,
						}
					};
					if(ext===".js"){
						meta.appFrame.uiDef=tool.filePath;
					}else{
						meta.appFrame.main=tool.filePath;
					}
					tool.appMeta=meta;
				}
				if(orgMeta){
					Object.assign(orgMeta,meta);
					tool.appMeta=orgMeta;
					return orgMeta;
				}
				return meta;
			}
			case "Page":{
				let meta,icon;
				meta=tool.appMeta;
				if(!meta){
					icon=tool.icon;
					if(icon[0]!=="/"){
						icon="/~/-tabos/shared/assets/"+icon;
					}
					meta={
						type:"app",
						main:tool.filePath,
						name:tool.name,
						package:tool.package,
						caption:tool.getNameText(lan),
						icon:icon,
						iconApp:null,
					};
					tool.appMeta=meta;
				}
				if(orgMeta){
					Object.assign(orgMeta,meta);
					tool.appMeta=orgMeta;
					return orgMeta;
				}
				return meta;
			}
			case "Agent":{
				return null;
			}
			case "API":{
				return null;
			}
		}
	};
}

//****************************************************************************
//::AAToolChain
//****************************************************************************
let AAToolChain,aaToolChain;
{
	//------------------------------------------------------------------------
	AAToolChain=function(tools){
		this.aaTools=tools;
		this.name="";
		this.filePath="";
		this.tools={};
		this.guide="";
		this.icon="toolchain.svg";
		this.description="";
		this.enable=true;
		makeNotify(this);
	};
	aaToolChain=AAToolChain.prototype={};
	
	//------------------------------------------------------------------------
	aaToolChain.genSaveVO=async function(){
		let vo,tool,tools;
		vo={
			name:this.name,
			guide:this.guide,
			icon:this.icon,
			description:this.description,
			tools:{}
		};
		tools=this.tools;
		for(tool of tools){
			vo.tools[tool.fileName]=tool.fileName;
		}
		return vo;
	};
	
	//------------------------------------------------------------------------
	aaToolChain.loadFromVO=async function(vo){
		let tool,path,name;
		// Load tool chains from the provided value object (VO):
		this.name = vo.name || '';
		this.guide = vo.guide || '';
		this.icon=vo.icon||'';
		this.description=vo.description||'';
		let chainTools = vo.tools || {};
		for(name in chainTools){
			path=chainTools[name];
			tool=this.aaTools.getTool(path);
			if(tool){
				this.tools[name]=tool;
			}else{
				//TODO: Report missing tools:
			}
		}
	};
	
	//------------------------------------------------------------------------
	AAToolChain.loadChainVO=async function(path){
		let chainJSON,ext;
		if(path[0]==="/" && path[1]!=="~" && path[1]!=="/"){
			path="/~"+path;
		}
		ext=pathLib.extname(path).toLowerCase();
		if(ext===".js"){
			chainJSON=(await import(path)).default;
		}else{
			chainJSON=await (await fetch(path)).json();
		}
		return chainJSON;
	};

	//------------------------------------------------------------------------
	aaToolChain.loadFromPath=async function(path){
		let chainJSON;
		chainJSON=await AAToolChain.loadChainVO(path);
		this.loadFromVO(chainJSON);
	};

	//------------------------------------------------------------------------
	aaToolChain.getNameText=function(lan){
		let text=this.name;
		if(text.EN){
			text=text[lan]||text.EN;
		}
		return text;
	};

	//------------------------------------------------------------------------
	aaToolChain.getDescText=function(lan){
		let text=this.description;
		if(text.EN){
			text=text[lan]||text.EN;
		}
		return text;
	};
	
	//------------------------------------------------------------------------
	aaToolChain.genInfoVO=function(ln){
		let vo={};
		let ref,tools,groups;
		vo.filePath = this.filePath;
		vo.type = this.type;
		vo.name = this.getNameText();
		vo.description = this.getDescText();
		vo.icon = this.icon;
		vo.package = this.package;
		vo.rpaHost = this.rpaHost||"NA";
		vo.enable = !!this.enable;
		ref=this.getReference();
		tools=ref.tools.map(s=>s.getNameText(ln));
		groups=ref.groups.map(g=>g.getNameText(ln));
		vo.reference=`Tool: ${tools.length?tools:"0"}. Group: ${groups.length?groups:"0"}`;
		return vo;
	};

	//------------------------------------------------------------------------
	aaToolChain.getReference=function(){
		let ref;
		ref=this.aaTools.getChainRef(this);
		ref.tools=Object.values(this.tools);
		return ref;
	};
}

//****************************************************************************
//:AAToolGroup
//****************************************************************************
let AAToolGroup,aaToolGroup;
{
	AAToolGroup=function(tools){
		this.aaTools=tools;
		this.codeName="";
		this.name="";
		this.icon="";
		this.description="";
		this.chains=[];
		this.tools=[];
		makeNotify(this);
	};
	aaToolGroup=AAToolGroup.prototype={};
	
	//------------------------------------------------------------------------
	aaToolGroup.genSaveVO=async function(){
		let vo={};
		vo.codeName=this.codeName||this.name;
		vo.name=this.name;
		vo.description=this.description;
		vo.tools=this.tools.map(tool => tool.filePath);
		vo.chains=this.chains.map(chain=>chain.filePath);
		vo.icon=this.icon;
		return vo;
	};

	//------------------------------------------------------------------------
	aaToolGroup.loadFromVO=async function(groupVO){
		let aaTools,toolStubs,toolStub,tools,tool,chains,chain;
		aaTools=this.aaTools;
		// Load group properties from the given value object (VO):
		this.codeName=groupVO.codeName||groupVO.name||"";
		this.name = groupVO.name || '';
		this.description = groupVO.description || '';
		this.icon = groupVO.icon || '';
		// Load the tools by creating AATool instances for each filePath in the VO:
		toolStubs=groupVO.tools;
		this.tools=tools=[];
		for(toolStub of toolStubs){
			tool=aaTools.getTool(toolStub);
			if(tool){
				tools.push(tool);
			}
		}
		// Load the tool chains from the value object:
		chains=groupVO.chains||[];
		this.chains=[];
		for(let chainPath of chains){
			chain=this.aaTools.getChain(chainPath);
			if(chain){
				this.chains.push(chain);
			}
		}
	};

	//------------------------------------------------------------------------
	aaToolGroup.addTool=function(tool){
		let idx;
		idx=this.tools.indexOf(tool);
		if(idx>=0)
			return;
		this.tools.push(tool);
	};
	
	//------------------------------------------------------------------------
	aaToolGroup.removeTool=function(tool){
		let idx;
		idx=this.tools.indexOf(tool);
		this.tools.splice(idx,1);
	};

	//------------------------------------------------------------------------
	aaToolGroup.addChain=function(chain){
		let idx;
		idx=this.chains.indexOf(chain);
		if(idx>=0)
			return;
		this.chains.push(chain);
	};

	//------------------------------------------------------------------------
	aaToolGroup.removeChain=function(chain){
		let idx;
		idx=this.chains.indexOf(chain);
		this.chains.splice(idx,1);
	};
	
	//------------------------------------------------------------------------
	aaToolGroup.getName=aaToolGroup.getNameText=function(lan){
		let text=this.name;
		if(text.EN){
			text=text[lan]||text.EN;
		}
		return text;
	};

	//------------------------------------------------------------------------
	aaToolGroup.getDescText=function(lan){
		let text=this.description;
		if(text.EN){
			text=text[lan]||text.EN;
		}
		return text;
	};
}

//****************************************************************************
//:AAToolSite
//****************************************************************************
let AAToolSite,aaToolSite;
{
	AAToolSite=function(tools,hostSite){
		this.aaTools=tools;
		this.name=getDomain(hostSite);
		this.icon="browser.svg";
		this.hostSite=hostSite;
		this.description=`Tools related to host: ${hostSite}`;
		this.tools=[];
		this.checkLogin="";
	};
	aaToolSite=AAToolSite.prototype={};
	
	//------------------------------------------------------------------------
	aaToolSite.genSaveVO=async function(){
		let vo={};
		vo.name=this.name;
		vo.description=this.description;
		vo.hostSite=this.hostSite;
		vo.icon=this.icon;
		vo.checkLogin=this.checkLogin;
		return vo;
	};

	//------------------------------------------------------------------------
	aaToolSite.loadFromVO=async function(groupVO){
		this.name = groupVO.name || '';
		this.description = groupVO.description || '';
		this.icon = groupVO.icon || '';
		this.hostSite = groupVO.hostSite || '';
		this.checkLogin=groupVO.checkLogin||"";
	};

	//------------------------------------------------------------------------
	aaToolSite.addTool=function(tool){
		this.tools.push(tool);
	};
	
	//------------------------------------------------------------------------
	aaToolSite.removeTool=function(tool){
		let idx;
		idx=this.tools.indexOf(tool);
		this.tools.splice(idx,1);
	};
}

//****************************************************************************
//:AAToolSet
//****************************************************************************
let AAToolSet,aaToolSet;
{
	//------------------------------------------------------------------------
	AAToolSet=function(){
		this.tools=null;
		this.scopeIndex=null;
		this.scopeTools=null;
	};
	aaToolSet=AAToolSet.prototype={};
	
	//-----------------------------------------------------------------------
	AAToolSet.load=async function(list){
		let toolSet;
		toolSet=new AAToolSet();
		await toolSet.loadTools(list);
		return toolSet;
	};
	
	//-----------------------------------------------------------------------
	aaToolSet.loadTool=async function(toolPath){
		let tool,host;
		tool=this.tools.get(toolPath);
		if(tool){
			return tool;
		}
		tool = new AATool(this);
		try {
			await tool.loadFromPath(toolPath);
			this.tools.set(toolPath, tool);
			return tool;
		} catch (error) {
			console.error(`Failed to load tool from path: ${toolPath}`, error);
			//throw error;
			return null;
		}
	};
	
	//------------------------------------------------------------------------
	aaToolSet.loadTools=async function(pathList){
		//Load all tools:
		await Promise.all(pathList.map(async (toolStub) => {
			await this.loadTool(toolStub);
		}));
	};
	
	//------------------------------------------------------------------------
	aaToolSet.getChatEntryTools=function(){
		return Array.from(this.tools.values()).filter((tool)=>{return (tool && !!tool.chatEntry && tool.enable);});
	};
	
	//--------------------------------------------------------------------
	aaToolSet.getToolScope=function(){
		let tools,vo,tool,i,n,tag,scopeTools;
		if(this.scopeIndex){
			return this.scopeIndex;
		}
		scopeTools=this.scopeTools={};
		tools=Array.from(this.tools.values());
		vo={};
		n=tools.length;
		for(i=0;i<n;i++){
			tool=tools[i];
			if(tool && tool.enable){
				tag="Tool-"+i;
				vo[tag]=tool.description;
				scopeTools[tag]=tool;
			}
		}
		this.scopeIndex=vo;
		return vo;
	};
	
	//------------------------------------------------------------------------
	aaToolSet.getTool=function(tag){
		let tool,scopeTools;
		tool=this.tools.get(tag);
		if(tool){
			return tool;
		}
		scopeTools=this.scopeTools;
		if(!scopeTools){
			return null;
		}
		return scopeTools[tag]||null;
	};
}

//****************************************************************************
//:AATools
//****************************************************************************
let AATools,aaTools;
{
	AATools=function(){
		this.groups=new Map();
		this.sites=new Map();
		this.tools=new Map();
		this.chains=new Map();
		this.fileHandlers=null;
		this.scopeTools=null;
		this.kinds=new Map();
		this.kindRegs=new Map();
	};
	aaTools=AATools.prototype = {};
	
	let instance=null;
	let instancePms=null;
	//------------------------------------------------------------------------
	AATools.instance=async function(){
		if(instance){
			return instancePms;
		}
		instance=new AATools();
		instancePms=instance.load().then(()=>{return instance});
		return instancePms;
	};
	
	//************************************************************************
	//I/O
	//************************************************************************
	{
		//--------------------------------------------------------------------
		aaTools.genSaveVO=async function(){
			let saveVO = {};
			let list,tool,tools,chains;
			// Generate a Save Value Object (VO) for all tools:
			tools=[];
			list=this.getTools();
			for(tool of list){
				if(tool.type==="Agent"){
					tools.push({
						type:"Agent",enable:tool.enable,
						keyTool:tool.keyTool,
						filePath:tool.filePath
					});
				}else{
					tools.push(await tool.genSaveVO());
				}
			}
			saveVO.tools=tools;
			
			// Generate a Save Value Object (VO) for all chains:
			chains=Array.from(this.chains.keys());
			saveVO.chains=chains;
			
			// Generate a Save Value Object (VO) for all groups:
			saveVO.groups = [];
			for (let [groupKey, group] of this.groups) {
				let groupSaveVO = await group.genSaveVO();
				saveVO.groups.push(groupSaveVO);
			}
			return saveVO;
		};
		
		//--------------------------------------------------------------------
		aaTools.load=async function(){
			try{
				let toolJSON;
				toolJSON=await (await fetch("/~/coke/ToolIndex.json",{cache: 'no-store'})).json();
				{
					//Merge with safe:
					let safeTools,jsonTools,tool,filePath,pos;
					let safeGroups,jsonGroups,group,groupCode,jsonGroup;
					safeTools=safeToolsJSON.tools;
					jsonTools=toolJSON.tools;
					pos=0;
					for(tool of safeTools){
						filePath=tool.filePath;
						if(!jsonTools.some((t)=>{return t.filePath===filePath;})){
							jsonTools.splice(pos++,0,tool);
						}
					}
					safeGroups=safeToolsJSON.groups;
					jsonGroups=toolJSON.groups;
					for(group of safeGroups){
						groupCode=group.codeName;
						jsonGroup=jsonGroups.find((g)=>{return g.codeName===groupCode;});
						if(!jsonGroup){
							jsonGroups.unshift(group);
						}else{
							pos=0;
							safeTools=group.tools;
							jsonTools=jsonGroup.tools;
							for(tool of safeTools){
								if(jsonTools.indexOf(tool)<0){
									jsonTools.splice(pos++,0,tool);
								}
							}
						}
					}
				}
				await this.loadFromVO(toolJSON);
			}catch(err){
				await this.loadFromVO(safeToolsJSON);
			}
			this.rankTools();
			return true;
		};

		//--------------------------------------------------------------------
		aaTools.loadFromVO=async function(vo){
			let groupStubs,toolStubs,chainStubs;
			//Load all tools:
			toolStubs = vo.tools || [];
			await Promise.all(toolStubs.map(async (toolStub) => {
				await this.loadTool(toolStub);
			}));
			chainStubs = vo.chains || [];
			await Promise.all(chainStubs.map(async (chainStub) => {
				await this.loadChain(chainStub);
			}));
			// Load all groups, hosts, and tools from the provided value object (VO):
			groupStubs = vo.groups || [];
			for(let groupVO of groupStubs){
				let group = new AAToolGroup(this);
				await group.loadFromVO(groupVO);
				this.groups.set(group.name, group);
			}
			this.loadTime=Date.now();
		};

		//--------------------------------------------------------------------
		aaTools.loadTool=async function(toolStub){
			let toolPath,tool,host;
			if(typeof(toolStub)==="object"){
				toolPath=toolStub.filePath;
				tool=this.tools.get(toolPath);
				if(tool){
					return tool;
				}
				tool=new AATool(this);
				if(toolStub.type==="Agent"){
					toolPath=toolStub.filePath;
					try {
						await tool.loadFromPath(toolPath);
						this.tools.set(toolPath, tool);
						host=tool.rpaHost;
						if(host){
							let hostSite;
							hostSite=this.sites.get(host);
							if(!hostSite){
								hostSite=new AAToolSite(this,host);
								this.sites.set(host,hostSite);
							}
							hostSite.addTool(tool);
						}
						tool.enable=toolStub.enable!==false;
						tool.keyTool=toolStub.keyTool===true;
						this.regTool(tool);
						return tool;
					} catch (error) {
						console.error(`Failed to load tool from path: ${toolPath}`, error);
						return null;
						//throw error;
					}
					
				}else{
					try {
						await tool.loadFromVO(toolStub);
						this.tools.set(toolPath, tool);
						host=tool.rpaHost;
						if(host){
							let hostSite;
							hostSite=this.sites.get(host);
							if(!hostSite){
								hostSite=new AAToolSite(this,hostSite);
								this.sites.set(host,hostSite);
							}
							hostSite.addTool(tool);
						}
						this.regTool(tool);
						return tool;
					} catch (error) {
						console.error(`Failed to load tool from path: ${toolPath}`, error);
						return null;
						//throw error;
					}
				}
			}
			//Stub is tool path:
			toolPath=toolStub;
			tool=this.tools.get(toolPath);
			if(tool){
				return tool;
			}
			tool = new AATool(this);
			try {
				await tool.loadFromPath(toolPath);
				this.tools.set(toolPath, tool);
				host=tool.rpaHost;
				if(host){
					let hostSite;
					hostSite=this.sites.get(host);
					if(!hostSite){
						hostSite=new AAToolSite(this,host);
						this.sites.set(host,hostSite);
					}
					hostSite.addTool(tool);
				}
				this.regTool(tool);
				return tool;
			} catch (error) {
				console.error(`Failed to load tool from path: ${toolPath}`, error);
				//throw error;
				return null;
			}
		};
		
		//--------------------------------------------------------------------
		aaTools.loadChain=async function(chainPath){
			let chain;
			chain=this.chains.get(chainPath);
			if(chain){
				return chain;
			}
			chain=new AAToolChain(this);
			chain.filePath=chainPath;
			await chain.loadFromPath(chainPath);
			this.chains.set(chainPath,chain);
			return chain;
		};
	}
	
	//************************************************************************
	//Access contents:
	//************************************************************************
	{	
		//--------------------------------------------------------------------
		aaTools.getFileHandler=function(filePath,mode){
			let handlers,map,handleFiles,tool,ext;
			handlers=this.fileHandlers;
			if(!handlers){
				//Build map:
				handlers=this.fileHandlers={
					open:new Map(),
					edit:new Map()
				};
				for (tool of this.tools.values()) {
					handleFiles=tool.handleFiles;
					if(handleFiles){
						let types,fileType,map;
						types=handleFiles.open;
						if(types){
							map=this.fileHandlers.open;
							for(fileType of types){
								map.set(fileType,tool);
							}
						}
						types=handleFiles.edit;
						if(types){
							map=this.fileHandlers.edit;
							for(fileType of types){
								map.set(fileType,tool);
							}
						}
					}
				}
			}
			map=handlers[mode]||handlers.open;
			ext=pathLib.ext2name(filePath);
			if(ext){
				tool=map.get(ext);
				if(tool){
					return tool;
				}
			}
			ext=pathLib.extname(filePath);
			if(ext){
				return map.get(ext)||null;
			}
			return null;
		};
		
		//--------------------------------------------------------------------
		aaTools.getTool=function(filePath){
			let tool,scopeTools;
			tool=this.tools.get(filePath);
			if(tool){
				return tool;
			}
			scopeTools=this.scopeTools;
			if(!scopeTools){
				return null;
			}
			return scopeTools[filePath]||null;
		};
		
		//--------------------------------------------------------------------
		aaTools.toolsByCapability=aaTools.toolsByCapabilities=function(cap){
			let tools,tool,caps,finds;
			if(!Array.isArray(cap)){
				cap=[cap];
			}
			finds=[];
			tools=Array.from(this.tools.values());
			for(tool of tools){
				caps=tool.capabilities;
				if(caps && cap.every(item => caps.includes(item))){
					finds.push(tool);
				}
			}
			return finds.length?finds:null;
		};
		
		//--------------------------------------------------------------------
		aaTools.getChain=function(filePath){
			return this.chains.get(filePath);
		};
		
		//--------------------------------------------------------------------
		aaTools.getGroup=function(name){
			return this.groups.get(name);
		};
		
		//--------------------------------------------------------------------
		aaTools.addGroup=function(name){
			let group;
			group=this.groups.get(name);
			if(group){
				return group;
			}
			group = new AAToolGroup(this);
			group.name=name;
			this.groups.set(name,group);
			return group;
		};
		
		//--------------------------------------------------------------------
		aaTools.renameGroup=function(group,name){
			let oldName;
			oldName=group.name;
			this.groups.delete(oldName);
			group.name=name;
			this.groups.set(name,group);
			return group;
		};

		//--------------------------------------------------------------------
		aaTools.removeGroup=function(group){
			let oldName;
			oldName=group.name;
			this.groups.delete(oldName);
		};

		//--------------------------------------------------------------------
		aaTools.getTools=function(){
			return Array.from(this.tools.values());
		};
		
		//--------------------------------------------------------------------
		aaTools.getChatEntryTools=function(){
			return Array.from(this.tools.values()).filter((tool)=>{return (!!tool.chatEntry && tool.enable);});
		};

		//--------------------------------------------------------------------
		aaTools.getChains=function(){
			return Array.from(this.chains.values());
		};

		//--------------------------------------------------------------------
		aaTools.getGroups=function(sort){
			let groups;
			groups=Array.from(this.groups.values());
			if(sort){
				groups.sort((a,b)=>{return a>b?1:(a<b?-1:0);});
			}
			return groups;
		};

		//--------------------------------------------------------------------
		aaTools.getSites=function(sort){
			let groups;
			groups=Array.from(this.sites.values());
			if(sort){
				groups.sort((a,b)=>{return a>b?1:(a<b?-1:0);});
			}
			return groups;
		};

		//--------------------------------------------------------------------
		aaTools.getToolAPIIndex=function(){
			//TODO: Code this:
		};

		//--------------------------------------------------------------------
		aaTools.getToolDescIndex=aaTools.getToolScope=function(){
			let tools,vo,tool,i,n,tag,scopeTools;
			scopeTools=this.scopeTools={};
			tools=Array.from(this.tools.values());
			vo={};
			n=tools.length;
			for(i=0;i<n;i++){
				tool=tools[i];
				if(tool.enable && tool.description && tool.isChatApi!==false){
					tag="Tool-"+i;
					vo[tag]=tool.description;
					scopeTools[tag]=tool;
				}
			}
			return vo;
		};
		
		//--------------------------------------------------------------------
		aaTools.removeTool=function(tool,ref){
			let g;
			if(!ref){
				ref=this.getToolRef(tool);
			}
			for(g of ref.groups){
				g.removeTool(tool);
			}
			this.tools.delete(tool.filePath);
		};

		//--------------------------------------------------------------------
		aaTools.removeChain=function(chain,ref){
			let g;
			if(!ref){
				ref=this.getChainRef(chain);
			}
			for(g of ref.groups){
				g.removeChain(chain);
			}
			this.chains.delete(chain.filePath);
		};
		
		//--------------------------------------------------------------------
		aaTools.removeToolPackage=function(pkg){
			let tools,tool;
			tools=Array.from(this.tools.values());
			tools=tools.filter((tool)=>{return tool.package===pkg;});
			for(tool of tools){
				this.removeTool(tool);
			}
		};
	}
	
	//************************************************************************
	//Find tool:
	//************************************************************************
	{
		//------------------------------------------------------------------------
		aaTools.regTool = function(tool){
			let kindName,set,kindReg,cost,costPerCall,costPer1M,size;
			kindName=tool.kind;
			if(!kindName){
				return;
			}

			set=this.kinds.get(kindName);
			if(!set){
				set=new Set();
				this.kinds.set(kindName,set);
			}
			set.add(tool);

			//Find/ensure kindReg
			kindReg=this.kindRegs.get(kindName);
			if(!kindReg){
				kindReg={...defKindReg};
				this.kindRegs.set(kindName,kindReg);
			}
			
			size=tool.metrics.size||0;
			//Calculate cost:
			costPerCall=tool.metrics?.costPerCall||0;
			costPer1M=tool.metrics?.costPer1M||0;
			cost=tool.metrics.cost=kindReg.weights.cost.costPerCall*costPerCall+kindReg.weights.cost.costPer1M*costPer1M;
			
			//Update kindReg's min/max
			if(size>kindReg.max.size){
				kindReg.max.size=size;
			}
			if(cost>kindReg.max.cost){
				kindReg.max.size=size;
			}
		};

		//------------------------------------------------------------------------
		aaTools.rankTools=function(){
			let kinds,kind,tools,tool,kindReg;
			kinds=Array.from(this.kinds.keys());
			for(kind of kinds){
				kindReg=this.kindRegs.get(kind);
				if(kindReg){
					tools=Array.from(this.kinds.get(kind).values());
					for(tool of tools){
						tool.ranks.cost=10 - (tool.metrics.cost - kindReg.min.cost) / (kindReg.max.cost - kindReg.min.cost + 1e-9) * 10;
						tool.ranks.size=(tool.metrics.size - kindReg.min.size) / (kindReg.max.size - kindReg.min.size + 1e-9) * 10;
						tool.ranks.quality=tool.metrics.quality||5;
						tool.ranks.speed=tool.metrics.speed||5;
						tool.ranks.overallScore=kindReg.weights.overallScore.quality * tool.ranks.quality 
							- kindReg.weights.overallScore.cost * tool.ranks.cost 
							+ kindReg.weights.overallScore.speed * tool.ranks.speed 
							- kindReg.weights.overallScore.size * tool.ranks.size;
					}
				}
			}
		};
		
		//------------------------------------------------------------------------
		aaTools.findTool = function(find, opts){
			opts = opts || {};
			const topK = Math.max(1, opts.topK || 1);
			const wantReason = !!opts.reason;

			// 兼容：find 是字符串时做简单全文检索（可选）
			if(typeof(find)==="string"){
				const q = find.trim().toLowerCase();
				if(!q) return null;
				const list = Array.from(this.tools.values()).filter(t=>{
					if(!t || t.enable===false) return false;
					const name = (t.getNameText ? String(t.getNameText("EN")||"") : String(t.name||"")).toLowerCase();
					const desc = (t.getDescText ? String(t.getDescText("EN")||"") : String(t.description||"")).toLowerCase();
					const fp = String(t.filePath||"").toLowerCase();
					const mn = String(t.metaName||"").toLowerCase();
					return name.includes(q) || desc.includes(q) || fp.includes(q) || mn.includes(q);
				});
				return topK===1 ? (list[0]||null) : list.slice(0, topK);
			}

			if(!find || typeof(find)!=="object") return null;

			// ------------------------------
			// 1) kind 粗筛
			// ------------------------------
			const kind = String(find.kind || find.primaryKind || "").trim();
			let cands;
			if(kind && this.kinds && this.kinds.get(kind)){
				cands = Array.from(this.kinds.get(kind));
			}else{
				cands = Array.from(this.tools.values());
			}
			cands = cands.filter(t=>{
				if(!t || t.enable===false) return false;
				if(kind){
					if(t.kind===kind) return true;
					if(Array.isArray(t.kinds) && t.kinds.includes(kind)) return true;
					return false;
				}
				return true;
			});

			// status=active（如你未来在 meta/status 上挂状态，这里会自动支持）
			cands = cands.filter(t=>{
				const st = t.meta?.status || t.status;
				return (!st || st==="active");
			});

			// ------------------------------
			// 2) must 硬过滤
			// ------------------------------
			const must = Array.isArray(find.must) ? find.must.filter(Boolean) : [];
			if(must.length){
				cands = cands.filter(t=>{
					const caps = t.capabilities || t.caps || [];
					return must.every(k => caps.indexOf(k) >= 0);
				});
			}

			// ------------------------------
			// 3) filter 约束（新语义）
			//   - tool 未声明该 key => 不匹配
			//   - 只有包含 "*" 才算通用
			//   - strict 优先，strict 有则剔除仅 wildcard 命中的
			//   - tiered: ["a.com","b.com","*"] 按顺序降级，每层仍 strict-first
			// ------------------------------
			const filterMap = _normFilter(find.filter);
			const tierUsed = {}; // 记录每个 key 最终用了哪一层（用于 explain）

			for(const key of Object.keys(filterMap)){
				const constraints = filterMap[key];

				for(const cons of constraints){

					// tiered：形如 ["a.com","b.com","*"]，按顺序降级；每层 strict-first
					if(Array.isArray(cons) && cons.length && cons.some(v=>v==="*")){
						let picked = null;

						for(const tier of cons){
							const strict = [];
							const wild = [];

							for(const t of cands){
								const ty = _toolArgMatchType(t, key, tier);
								if(ty === 2) strict.push(t);
								else if(ty === 1) wild.push(t);
							}

							if(strict.length){
								cands = strict;
								picked = tier;
								break;
							}
							if(wild.length){
								cands = wild;
								picked = tier;
								break;
							}
							// strict/wild 都没：继续下一层 tier
						}

						tierUsed[key] = picked;
						if(!picked){
							cands = [];
							break;
						}
						continue;
					}

					// 普通约束：同 key 重复出现时默认 AND（逐条应用）
					// 每条内部：strict-first，然后才 wildcard
					{
						const strict = [];
						const wild = [];

						for(const t of cands){
							const ty = _toolArgMatchType(t, key, cons);
							if(ty === 2) strict.push(t);
							else if(ty === 1) wild.push(t);
						}

						cands = strict.length ? strict : wild;
					}

					if(!cands.length) break;
				}

				if(!cands.length) break;
			}

			// 没候选直接返回
			if(!cands.length) return wantReason ? (topK===1 ? null : []) : null;

			// ------------------------------
			// 4) prefer 加分
			// ------------------------------
			const prefer = Array.isArray(find.prefer) ? find.prefer.filter(Boolean) : [];
			const scored = cands.map(t=>{
				const caps = t.capabilities || t.caps || [];
				let hits = [];
				if(prefer.length){
					for(const p of prefer){
						if(caps.indexOf(p) >= 0) hits.push(p);
					}
				}
				let w = t.meta?.weight ?? t.weight;
				if(typeof w!=="number" || !isFinite(w)) w = 1;
				return {
					tool: t,
					preferHits: hits,
					preferScore: hits.length * w
				};
			});

			// ------------------------------
			// 5) rank 排序（0~10 分，10最好；统一 desc） + 6) 稳定 tie-break
			//   - find.rank 支持逗号分隔多级 key
			//   - 自定义 rank key：当用户显式传 find.rank 时允许
			//   - 若 rank 不包含 overallScore，默认追加到最后一级
			// ------------------------------
			const rankKeys = _normRank(find.rank, kind, this);

			scored.sort((A, B)=>{
				// prefer 优先（命中越多越好）
				if(B.preferScore !== A.preferScore) return B.preferScore - A.preferScore;

				// rank 多级排序（统一 desc）
				for(const key of rankKeys){
					const av = _getRankVal(A.tool, key);
					const bv = _getRankVal(B.tool, key);

					const aMiss = (av==null || Number.isNaN(av));
					const bMiss = (bv==null || Number.isNaN(bv));
					if(aMiss && bMiss) continue;
					if(aMiss) return 1;     // missing last
					if(bMiss) return -1;

					if(av === bv) continue;
					return (bv - av); // desc：10最好
				}

				// 稳定 tie-break：id/metaName/filePath
				const aid = String(A.tool.id || A.tool.meta?.id || A.tool.metaName || A.tool.filePath || "");
				const bid = String(B.tool.id || B.tool.meta?.id || B.tool.metaName || B.tool.filePath || "");
				return aid.localeCompare(bid);
			});

			const picked = scored.slice(0, topK);

			if(!wantReason){
				return topK===1 ? (picked[0]?.tool || null) : picked.map(x=>x.tool);
			}

			// reason 输出（可用于 UI explain）
			const out = picked.map(x=>{
				const t = x.tool;
				const rv = {};
				for(const key of rankKeys) rv[key] = _getRankVal(t, key);

				return {
					tool: t,
					kind,
					tierUsed,
					preferHits: x.preferHits,
					preferScore: x.preferScore,
					rankKeys,
					rankValues: rv,
					metrics: (t.metrics || t.meta?.metrics || null),
					ranksVer: (t.ranks?.ver || t.meta?.ranks?.ver || null)
				};
			});
			return topK===1 ? (out[0] || null) : out;

			// ==============================
			// helpers
			// ==============================
			function _normFilter(f){
				if(!f) return {};
				// array form: [{key,value},...]
				if(Array.isArray(f)){
					const out = {};
					for(const it of f){
						if(!it || !it.key) continue;
						const k = String(it.key).trim();
						if(!k) continue;
						out[k]=out[k]||[];
						out[k].push(it.value);
					}
					return out;
				}
				// object form: {key:value,...}
				if(typeof f === "object"){
					const out = {};
					for(const [k, v] of Object.entries(f)){
						const kk = String(k).trim();
						if(!kk) continue;
						out[kk] = [v];
					}
					return out;
				}
				return {};
			}

			function _getToolFilter(tool, key){
				const f = tool.filters;
				if(!f) return undefined;
				if(typeof f === "object"){
					if(f[key] !== undefined) return f[key];
					if(tool.kind && f[tool.kind] && f[tool.kind][key] !== undefined) return f[tool.kind][key];
				}
				return undefined;
			}

			function _isDomainKey(key){
				return (key === "scope.domain" || key.endsWith(".domain") || key.includes("domain"));
			}

			function _normDomain(x){
				if(x==null) return "";
				let s = String(x).trim().toLowerCase();
				if(!s) return "";
				try{
					if(!s.startsWith("http://") && !s.startsWith("https://")){
						if(s.includes("/") || s.includes(":")) s = "https://" + s;
					}
					const u = new URL(s);
					return (u.hostname || "").toLowerCase();
				}catch(err){
					s = s.split("/")[0];
					return s;
				}
			}

			function _domainMatches(domain, patterns){
				domain = _normDomain(domain);
				if(!domain) return false;
				for(let p of patterns){
					if(p==null) continue;
					p = String(p).trim().toLowerCase();
					if(!p) continue;
					if(p === "*") return true;
					if(p.startsWith("*.") ){
						const base = p.slice(2);
						if(domain === base || domain.endsWith("." + base)) return true;
						continue;
					}
					if(domain === p || domain.endsWith("." + p)) return true;
				}
				return false;
			}

			function _deepEq(a, b){
				if(a === b) return true;
				if(a && b && typeof a==="object" && typeof b==="object"){
					try{ return JSON.stringify(a) === JSON.stringify(b); }catch(err){ return false; }
				}
				return false;
			}

			// 新：3态匹配（0=不匹配；1=仅 wildcard；2=strict）
			function _toolArgMatchType(tool, key, need){
				const tf = _getToolFilter(tool, key);

				// 新语义：未声明 = 不匹配（不再默认通用）
				if(tf === undefined) return 0;

				const tvals = Array.isArray(tf) ? tf : [tf];

				// need 数组：OR，取最好（strict 优先）
				if(Array.isArray(need)){
					let best = 0;
					for(const n of need){
						const ty = _toolArgMatchType(tool, key, n);
						if(ty === 2) return 2;
						if(ty === 1) best = 1;
					}
					return best;
				}

				const sval = (v)=> (v==null ? "" : String(v).trim());
				const hasStar = tvals.some(v => sval(v) === "*");

				// domain 特判：支持 *.openai.com / openai.com / *
				if(_isDomainKey(key) && typeof need === "string"){
					const patterns = tvals.map(v => sval(v).toLowerCase()).filter(Boolean);
					const strictPatterns = patterns.filter(p => p !== "*");

					// strict：命中任何非 "*" pattern
					if(strictPatterns.length && _domainMatches(need, strictPatterns)) return 2;

					// wildcard：只有包含 "*" 才算通用
					return hasStar ? 1 : 0;
				}

				// 非 domain：deepEq 相等算 strict；包含 "*" 算 wildcard
				for(const v of tvals){
					if(_deepEq(v, need)) return 2;
				}
				return hasStar ? 1 : 0;
			}

			// rankKey：决定“多级排序的 key 顺序”
			function _normRank(rank, kind, router){
				const hasExplicitRank = (rank != null && rank !== "");

				const parseRankList = (x) => {
					const arr = Array.isArray(x) ? x : [x];
					return arr
						.flatMap(v => String(v).split(","))
						.map(s => s.trim())
						.filter(Boolean);
				};

				let r = [];

				if(hasExplicitRank){
					// 显式 rank：允许自定义 key（不做白名单过滤）
					r = parseRankList(rank);
				}else{
					const kd = router.kindDefs?.[kind] || router.kindDefs?.get?.(kind) || null;
					const dr = kd?.defaultRanks || (kd?.defaultRank ? [kd.defaultRank] : null);
					if(dr) r = parseRankList(dr);

					if(!r.length){
						r = parseRankList(router.defaultRanks || ["overallScore"]);
					}

					// 默认 ranks：仍可用白名单约束，避免默认配置写错 key
					const allow = router.rankKeys || ["overallScore","quality","speed","cost","size"];
					r = r.filter(k => allow.indexOf(k) >= 0);
				}

				if(!r.length) r = ["overallScore"];

				// 若不包含 overallScore，默认追加到最后一级
				if(!r.includes("overallScore")) r.push("overallScore");

				return r;
			}

			// 从 tool.ranks / tool.meta.ranks 读 0~10 分（10最好）
			function _getRankVal(tool, key){
				const r = tool.ranks || tool.meta?.ranks || null;
				if(!r) return null;
				const v = r[key];
				if(v==null || v==="") return null;
				const n = Number(v);
				return (isFinite(n) ? n : null);
			}
		};		
	}
	//************************************************************************
	//Run tool or chain:
	//************************************************************************
	{
		//--------------------------------------------------------------------
		AATools.execTool=aaTools.execTool=async function(app,tool,args,session,opts){
			switch(tool.type){
				case "App":{
					let meta,icon;
					meta=tool.genAppMeta(app.lanCode||"EN");
					//app.newFrameApp(meta,{},{});
					app.openMeta(meta,args,null);
					return `App ${tool.name} started.`;
				}
				case "ChatApp":{
					let meta,icon,embed;
					let AppFrame;
					try{
						AppFrame=(await import("/@homekit/ui/AppFrame.js")).AppFrame;
					}catch(err){
						AppFrame;
					}
					embed=opts.embed||opts.frame;
					meta=tool.genAppMeta(app.lanCode||"EN");
					if(embed && embed.appendNewChild && AppFrame){
						let appFrame=embed.appendNewChild({
							type:AppFrame(app,meta,args,{embed:true}),x:0,y:0
						});
						opts.embedCallback(appFrame);
					}else if(app && app.newFrameApp){
						app.openMeta(meta,args,null);
					}
					return `App ${tool.name} started.`;
				}
				case "Page":{
					window.open(document.location.origin+tool.filePath,"","noreferrer");
					return `Page ${tool.name} started.`;
				}
				case "Agent":{
					let meta,icon;
					opts=opts||{checkUpdate:true};
					if(session){
						if(tool.agentNode){
							return await session.callAgent(tool.agentNode,pathLib.basename(tool.filePath),args,opts);
							/*let result,callArgs={};
							callArgs['nodeName']=tool.agentNode;
							callArgs['callAgent']=pathLib.basename(tool.filePath);
							callArgs['callArg']=args;
							callArgs['checkUpdate']=true;
							return await session.pipeChat("/@aichat/ai/RemoteChat.js",callArgs,false);*/
						}else{
							return await session.callAgent(null,tool.filePath,args,opts);
							//return await session.pipeChat(tool.filePath,args,false);
						}
					}else{
						meta=tool.appMeta;
						if(!meta){
							icon=tool.icon||"aichat.svg";
							if(icon[0]!=="/"){
								icon="/~/-tabos/shared/assets/"+icon;
							}
							meta={
								type:"app",
								name:"Projects",
								caption:tool.name,
								icon:icon,
								appFrame:{
									group:"Projects",caption:tool.name,openApp:true,multiInstance:(tool.multiInstance!==false),
									icon:icon,
									width:tool.appFrameW||800,
									height:tool.appFrameH||600,
								}
							};
							meta.appFrame.main=`/@aichat/app.html?chat=${encodeURIComponent(tool.filePath)}&style=pro`;
							tool.appMeta=meta;
						}					
						app.newFrameApp(meta,null,{});
					}
					return "Agent app started.";
				}
				case "API":{
					//TODO: Code this:
					break;
				}
			}
		};
		
		//--------------------------------------------------------------------
		aaTools.execChain=async function(app,chain,args,session){
			let meta,icon;
			if(session){
				//TODO: Use pipechat:
			}else{
				meta=this.chainAppMeta;
				if(!meta){
					icon="/~/-tabos/shared/assets/aalogo.svg";
					meta={
						type:"app",
						name:"Run command",
						caption:"Run command",
						icon:icon,
						appFrame:{
							group:"RunChain",caption:"Run Tool-Chain",openApp:true,multiInstance:true,
							icon:icon,width:600,height:600,
						}
					};
					this.chainAppMeta=meta;
				}
				meta.appFrame.main=`/@aichat/app.html?chat=${encodeURIComponent("/@aae/ai/RunToolChain.js")}&prompt=${encodeURIComponent(chain.filePath)}&style=pro`;
				app.newFrameApp(meta,null,{});
			}
		};
	}
	
	//************************************************************************
	//Utils:
	//************************************************************************
	{
		//--------------------------------------------------------------------
		aaTools.getToolRef=function(tool){
			let groups,group,chains,chain;
			let ref={
				groups:[],chains:[]
			};
			groups=Array.from(this.groups.values());
			chains=Array.from(this.chains.values());
			for(group of groups){
				if(group.tools.indexOf(tool)>=0){
					ref.groups.push(group);
				}
			}
			for(chain of chains){
				if(Object.values(chain.tools).indexOf(tool)>=0){
					ref.chains.push(chain);
				}
			}
			return ref;
		};

		//--------------------------------------------------------------------
		aaTools.getChainRef=function(chain){
			let groups,group;
			let ref={
				groups:[],chains:[]
			};
			groups=Array.from(this.groups.values());
			for(group of groups){
				if(group.chains.indexOf(chain)>=0){
					ref.groups.push(group);
				}
			}
			return ref;
		};
	}
}


export default AATools;
export {AATool,AAToolSet,AAToolChain,AAToolGroup,AAToolSite,AATools};