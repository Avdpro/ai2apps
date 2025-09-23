//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IG0KVFDB0MoreImports*/
import {AgentNodeTerminal} from "../../agenthub/AgentNodeTerm.mjs";
/*}#1IG0KVFDB0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"bashId":{
			"name":"bashId","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"action":{
			"name":"action","type":"string",
			"defaultValue":"",
			"desc":"操作类型",
		},
		"commands":{
			"name":"commands","type":"auto",
			"defaultValue":"",
			"desc":"要执行的命令行文本/数组",
		},
		"options":{
			"name":"options","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IG0KVFDB0ArgsView*/
	/*}#1IG0KVFDB0ArgsView*/
};

/*#{1IG0KVFDB0StartDoc*/
async function sleep(time){
	let func,pms;
	pms=new Promise((resolve,reject)=>{
		setTimeout(resolve,time);
	});
	return pms;
}

const IDLEMaker="__AGENT_SHELL__>";
const bashMap=new Map();
/*}#1IG0KVFDB0StartDoc*/
//----------------------------------------------------------------------------
let Bash=async function(session){
	let bashId,action,commands,options;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let SwitchAction,CreateBash,RunCommand,LoopCmd,RunOneCmd,IsDone,CloseBash,GetContent,Clear,Wait,GetReact,GenResult,NextCmd,CheckReact,DoInput,NotifyUser,WaitIdle,AskUser;
	let cmdBash=null;
	let orgContent="";
	let orgCmdContent="";
	let project=globalContext.project;
	
	/*#{1IG0KVFDB0LocalVals*/
	/*}#1IG0KVFDB0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			bashId=input.bashId;
			action=input.action;
			commands=input.commands;
			options=input.options;
		}else{
			bashId=undefined;
			action=undefined;
			commands=undefined;
			options=undefined;
		}
		/*#{1IG0KVFDB0ParseArgs*/
		options=options||{};
		/*}#1IG0KVFDB0ParseArgs*/
	}
	
	/*#{1IG0KVFDB0PreContext*/
	if(!globalContext.getBash){
		globalContext.getBash=function(id){
			return bashMap.get(id);
		};
	}
	/*}#1IG0KVFDB0PreContext*/
	context={};
	/*#{1IG0KVFDB0PostContext*/
	/*}#1IG0KVFDB0PostContext*/
	let $agent,agent,segs={};
	segs["SwitchAction"]=SwitchAction=async function(input){//:1IG0L3R920
		let result=input;
		if(action==="Create"){
			return {seg:CreateBash,result:(input),preSeg:"1IG0L3R920",outlet:"1IG0LAEGR0"};
		}
		if(action==="Command"){
			return {seg:RunCommand,result:(input),preSeg:"1IG0L3R920",outlet:"1IG0L4HVP0"};
		}
		if(action==="Close"){
			return {seg:CloseBash,result:(input),preSeg:"1IG0L3R920",outlet:"1IG0L4SCA0"};
		}
		if(action==="Content"){
			return {seg:GetContent,result:(input),preSeg:"1IG0L3R920",outlet:"1IG2VD41R0"};
		}
		if(action==="Clear"){
			return {seg:Clear,result:(input),preSeg:"1IG0L3R920",outlet:"1IG2VAS500"};
		}
		if(action==="Wait"){
			return {seg:Wait,result:(input),preSeg:"1IG0L3R920",outlet:"1IH4M0AUA0"};
		}
		return {result:result};
	};
	SwitchAction.jaxId="1IG0L3R920"
	SwitchAction.url="SwitchAction@"+agentURL
	
	segs["CreateBash"]=CreateBash=async function(input){//:1IG0L7VK60
		let result=input
		/*#{1IG0L7VK60Code*/
		let bash;
		if(!globalContext.bash){
			bash=new AgentNodeTerminal(session);
			options=options||{};
			options.initConda=true;
			await bash.start(options,commands);
			bashMap.set(bash.id,bash);
			result=bash.id;
		}else{
			result=globalContext.bash;
		}
		/*}#1IG0L7VK60Code*/
		return {result:result};
	};
	CreateBash.jaxId="1IG0L7VK60"
	CreateBash.url="CreateBash@"+agentURL
	
	segs["RunCommand"]=RunCommand=async function(input){//:1IG0L8V2P0
		let result=input
		/*#{1IG0L8V2P0Code*/
		let bash;
		bash=bashMap.get(bashId);
		if(!bash){
			throw Error(`Can't find bash: "${bashId}"`);
		}
		cmdBash=bash;
		if(options.clear){
			bash.clear();
		}
		if(typeof(commands)==="string"){
			commands=commands.split("\n");	
		}
		orgContent=await bash.getContent();
		//result=await bash.runCommands(commands);
		/*}#1IG0L8V2P0Code*/
		return {seg:LoopCmd,result:(result),preSeg:"1IG0L8V2P0",outlet:"1IG0LAEGS2"};
	};
	RunCommand.jaxId="1IG0L8V2P0"
	RunCommand.url="RunCommand@"+agentURL
	
	segs["LoopCmd"]=LoopCmd=async function(input){//:1IIF4OKS70
		let result=input;
		let list=commands;
		let i,n,item,loopR;
		/*#{1IIF4OKS70PreLoop*/
		/*}#1IIF4OKS70PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1IIF4OKS70InLoopPre*/
			/*}#1IIF4OKS70InLoopPre*/
			loopR=await session.runAISeg(agent,RunOneCmd,item,"1IIF4OKS70","1IIF4PTNV2")
			if(loopR==="break"){
				break;
			}
			/*#{1IIF4OKS70InLoopPost*/
			/*}#1IIF4OKS70InLoopPost*/
		}
		/*#{1IIF4OKS70PostCodes*/
		/*}#1IIF4OKS70PostCodes*/
		return {seg:GenResult,result:(result),preSeg:"1IIF4OKS70",outlet:"1IIF4PTNQ0"};
	};
	LoopCmd.jaxId="1IIF4OKS70"
	LoopCmd.url="LoopCmd@"+agentURL
	
	segs["RunOneCmd"]=RunOneCmd=async function(input){//:1IIF4QE770
		let result=input
		/*#{1IIF4QE770Code*/
		orgCmdContent=await cmdBash.getContent();//TODO: Just use length?
		if(project){
			let logs=project.bashLogs;
			if(logs){
				logs.push(input);
			}
		}
		await cmdBash.runCommands(input,{idleTime:options.idleTime||0});
		result=await cmdBash.getContent();
		result=result.substring(orgCmdContent.length);
		/*}#1IIF4QE770Code*/
		return {seg:IsDone,result:(result),preSeg:"1IIF4QE770",outlet:"1IIF5P1F20"};
	};
	RunOneCmd.jaxId="1IIF4QE770"
	RunOneCmd.url="RunOneCmd@"+agentURL
	
	segs["IsDone"]=IsDone=async function(input){//:1IIF4R4RO0
		let result=input;
		/*#{1IIF4R4RO0Start*/
		let lines,lastLine,isIdle;
		lines=input.split("\n");
		lastLine=lines[lines.length-1].trim();
		isIdle=(lastLine.endsWith(IDLEMaker));
		/*}#1IIF4R4RO0Start*/
		if(!isIdle){
			/*#{1IIF5P1F21Codes*/
			if(lines>10){
				input=lines.slice(-10).join("\n");
			}
			/*}#1IIF5P1F21Codes*/
			return {seg:GetReact,result:(input),preSeg:"1IIF4R4RO0",outlet:"1IIF5P1F21"};
		}
		/*#{1IIF4R4RO0Post*/
		/*}#1IIF4R4RO0Post*/
		return {seg:NextCmd,result:(result),preSeg:"1IIF4R4RO0",outlet:"1IIF5P1F22"};
	};
	IsDone.jaxId="1IIF4R4RO0"
	IsDone.url="IsDone@"+agentURL
	
	segs["CloseBash"]=CloseBash=async function(input){//:1IG0L9DUD0
		let result=input
		/*#{1IG0L9DUD0Code*/
		let bash;
		bash=bashMap.get(bashId);
		if(!bash){
			throw Error(`Can't find bash: "${bashId}"`);
		}
		await bash.close();
		bashMap.delete(bashId);
		result=true;
		/*}#1IG0L9DUD0Code*/
		return {result:result};
	};
	CloseBash.jaxId="1IG0L9DUD0"
	CloseBash.url="CloseBash@"+agentURL
	
	segs["GetContent"]=GetContent=async function(input){//:1IG2VAJS20
		let result=input
		/*#{1IG2VAJS20Code*/
		let bash;
		bash=bashMap.get(bashId);
		if(!bash){
			throw Error(`Can't find bash: "${bashId}"`);
		}
		result=await bash.getContent();
		/*}#1IG2VAJS20Code*/
		return {result:result};
	};
	GetContent.jaxId="1IG2VAJS20"
	GetContent.url="GetContent@"+agentURL
	
	segs["Clear"]=Clear=async function(input){//:1IG2VBQIK0
		let result=input
		/*#{1IG2VBQIK0Code*/
		let bash;
		bash=bashMap.get(bashId);
		if(!bash){
			throw Error(`Can't find bash: "${bashId}"`);
		}
		await bash.clear();
		result=true;
		/*}#1IG2VBQIK0Code*/
		return {result:result};
	};
	Clear.jaxId="1IG2VBQIK0"
	Clear.url="Clear@"+agentURL
	
	segs["Wait"]=Wait=async function(input){//:1IH4M02OP0
		let result=input
		/*#{1IH4M02OP0Code*/
		/*}#1IH4M02OP0Code*/
		return {result:result};
	};
	Wait.jaxId="1IH4M02OP0"
	Wait.url="Wait@"+agentURL
	
	segs["GetReact"]=GetReact=async function(input){//:1IIDUEG0G0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=GetReact.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
### 角色任务
你是一个根据Terminal输出的最后几行内容来判断是否需要需要向terminal内输入，以继续执行当前操作的AI

### 对话
- 对话的输入是当前Terminal输出的最后几行内容
- 请用JSON格式返回当前需要进行的操作

### 返回JSON属性
- "action" {string}: 下一步的动作，可以取的值有:"Wait"， "Input", "Finish"和"AskUser"
	- "Wait": 当前Termnial还在执行任务，不需要干预
    - "Input": 当前Terminal需要用户输入才能继续执行，而你可以生成输入内容，例如询问是否确认某个操作。
    - "AskUser": 当前Terminal需要用户输入才能继续执行，而你无法生成输入内容，例如询问sudo、登陆密码等

- "input" {string}: 当"action"属性为"Input"时，需要向terminal里输入的内容。例如, 当询问是否继续时: "y"等。当"action"属性为"AskUser"时，需要询问用户的内容。

### 确保流程进行
- 除非是有明确的安全风险或者你无法提供相应的信息，你应该尽量使用"Input"的action来自动回复，保证流程不受中断。
`
},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("GetReact@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:CheckReact,result:(result),preSeg:"1IIDUEG0G0",outlet:"1IIDV9VFE0"};
	};
	GetReact.jaxId="1IIDUEG0G0"
	GetReact.url="GetReact@"+agentURL
	
	segs["GenResult"]=GenResult=async function(input){//:1IIF4PECH0
		let result=input
		/*#{1IIF4PECH0Code*/
		result=await cmdBash.getContent();
		result=result.substring(orgContent.length);
		/*}#1IIF4PECH0Code*/
		return {result:result};
	};
	GenResult.jaxId="1IIF4PECH0"
	GenResult.url="GenResult@"+agentURL
	
	segs["NextCmd"]=NextCmd=async function(input){//:1IIF4SPFB0
		let result=input
		/*#{1IIF4SPFB0Code*/
		/*}#1IIF4SPFB0Code*/
		return {result:result};
	};
	NextCmd.jaxId="1IIF4SPFB0"
	NextCmd.url="NextCmd@"+agentURL
	
	segs["CheckReact"]=CheckReact=async function(input){//:1IIF4UL9V0
		let result=input;
		if(input.action==="AskUser"){
			return {seg:AskUser,result:(input),preSeg:"1IIF4UL9V0",outlet:"1IIF5056O0"};
		}
		if(input.action==="Input"){
			let output=input.input;
			return {seg:DoInput,result:(output),preSeg:"1IIF4UL9V0",outlet:"1IIF5P1F24"};
		}
		if(input.action==="Wait"){
			return {seg:WaitIdle,result:(input),preSeg:"1IIF4UL9V0",outlet:"1IIF50B2J0"};
		}
		return {result:result};
	};
	CheckReact.jaxId="1IIF4UL9V0"
	CheckReact.url="CheckReact@"+agentURL
	
	segs["DoInput"]=DoInput=async function(input){//:1IIF512K60
		let result=input
		/*#{1IIF512K60Code*/
		cmdBash.write(input+"\n");
		/*
		let contentLen,curLen;
		let content;
		content=await cmdBash.getRawContent();
		console.log(JSON.stringify(content));
		contentLen=content.length+input.length;
		cmdBash.write(input);
		await sleep(1000);
		content=await cmdBash.getRawContent();
		console.log(JSON.stringify(content));
		curLen=content.length;
		if(curLen===contentLen){
			cmdBash.write("\n");
		}*/
		/*}#1IIF512K60Code*/
		return {seg:WaitIdle,result:(result),preSeg:"1IIF512K60",outlet:"1IIF5P1F31"};
	};
	DoInput.jaxId="1IIF512K60"
	DoInput.url="DoInput@"+agentURL
	
	segs["NotifyUser"]=NotifyUser=async function(input){//:1IIF53A7Q0
		let result=input
		/*#{1IIF53A7Q0Code*/
		//Notify user:
		try{
			session.callClient("BashNotify",{bash:cmdBash.id,info:(($ln==="CN")?("Terminal操作需要你的响应"):/*EN*/("Terminal operation requires your response"))});
		}catch(err){
			//missing BashNotify? Do nothing...
		}
		/*}#1IIF53A7Q0Code*/
		return {result:result};
	};
	NotifyUser.jaxId="1IIF53A7Q0"
	NotifyUser.url="NotifyUser@"+agentURL
	
	segs["WaitIdle"]=WaitIdle=async function(input){//:1IIF89Q1I0
		let result=input
		/*#{1IIF89Q1I0Code*/
		let changes="";
		let contentLen;
		contentLen=(await cmdBash.getContent()).length;
		while(!changes){
			console.log("Wait bash idle...");
			await cmdBash.waitIdle(true);
			changes=await cmdBash.getContent();
			changes=changes.substring(contentLen);
			console.log("Bash idle end: "+changes);
		}
		result=await cmdBash.getContent();
		result=result.substring(orgCmdContent);
		/*}#1IIF89Q1I0Code*/
		return {seg:IsDone,result:(result),preSeg:"1IIF89Q1I0",outlet:"1IIF8ATEI0"};
	};
	WaitIdle.jaxId="1IIF89Q1I0"
	WaitIdle.url="WaitIdle@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1J1V9GOIF0
		let tip=(input.input);
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		if(askUpward && tip){
			result=await session.askUpward($agent,tip);
		}else{
			if(tip){
				session.addChatText(tipRole,tip);
			}
			result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		}
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		return {seg:DoInput,result:(result),preSeg:"1J1V9GOIF0",outlet:"1J1V9HK8H0"};
	};
	AskUser.jaxId="1J1V9GOIF0"
	AskUser.url="AskUser@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"Bash",
		url:agentURL,
		autoStart:true,
		jaxId:"1IG0KVFDB0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{bashId,action,commands,options}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IG0KVFDB0PreEntry*/
			/*}#1IG0KVFDB0PreEntry*/
			result={seg:SwitchAction,"input":input};
			/*#{1IG0KVFDB0PostEntry*/
			/*}#1IG0KVFDB0PostEntry*/
			return result;
		},
		/*#{1IG0KVFDB0MoreAgentAttrs*/
		/*}#1IG0KVFDB0MoreAgentAttrs*/
	};
	/*#{1IG0KVFDB0PostAgent*/
	/*}#1IG0KVFDB0PostAgent*/
	return agent;
};
/*#{1IG0KVFDB0ExCodes*/
Bash.getBash=function(id){
	return bashMap.get(id);
};
/*}#1IG0KVFDB0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "Bash",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				bashId:{type:"auto",description:""},
				action:{type:"string",description:"操作类型"},
				commands:{type:"auto",description:"要执行的命令行文本/数组"},
				options:{type:"auto",description:""}
			}
		}
	},
	path: "/@AgentBuilder/Bash.js",
	label: "Bash Ops",
	isChatApi: true,
	icon: "terminal.svg"
}];

//:Export Edit-AddOn:
const DocAIAgentExporter=VFACT?VFACT.classRegs.DocAIAgentExporter:null;
if(DocAIAgentExporter){
	const EditAttr=VFACT.classRegs.EditAttr;
	const EditAISeg=VFACT.classRegs.EditAISeg;
	const EditAISegOutlet=VFACT.classRegs.EditAISegOutlet;
	const SegObjShellAttr=EditAISeg.SegObjShellAttr;
	const SegOutletDef=EditAISegOutlet.SegOutletDef;
	const docAIAgentExporter=DocAIAgentExporter.prototype;
	const packExtraCodes=docAIAgentExporter.packExtraCodes;
	const packResult=docAIAgentExporter.packResult;
	const varNameRegex = /^[a-zA-Z_$][a-zA-Z0-9_$]*$/;
	
	EditAISeg.regDef({
		name:"Bash",showName:"Bash Ops",icon:"terminal.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"bashId":{name:"bashId",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"action":{name:"action",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"commands":{name:"commands",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"options":{name:"options",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","bashId","action","commands","options","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["Bash"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['bashId']=");this.genAttrStatement(seg.getAttr("bashId"));coder.packText(";");coder.newLine();
			coder.packText("args['action']=");this.genAttrStatement(seg.getAttr("action"));coder.packText(";");coder.newLine();
			coder.packText("args['commands']=");this.genAttrStatement(seg.getAttr("commands"));coder.packText(";");coder.newLine();
			coder.packText("args['options']=");this.genAttrStatement(seg.getAttr("options"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
			this.packUpdateContext(coder,seg);
			this.packUpdateGlobal(coder,seg);
			this.packResult(coder,seg,seg.outlet);
		}
		coder.indentLess();coder.maybeNewLine();
		coder.packText(`};`);coder.newLine();
		if(exportDebug){
			coder.packText(`${segName}.jaxId="${seg.jaxId}"`);coder.newLine();
		}
		coder.packText(`${segName}.url="${segName}@"+agentURL`);coder.newLine();
		coder.newLine();
	};
}
//#CodyExport<<<
/*#{1IG0KVFDB0PostDoc*/
/*}#1IG0KVFDB0PostDoc*/


export default Bash;
export{Bash,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IG0KVFDB0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IG0KVFDB1",
//			"attrs": {
//				"Bash": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IG0KVFDB7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IG0KVFDC0",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IG0KVFDC1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IG0KVFDC2",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportClass": "false"
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1IG0KVFDB2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IG0KVFDB3",
//			"attrs": {
//				"bashId": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IG0LAEGU0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"action": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IG0LAEGU1",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "操作类型"
//					}
//				},
//				"commands": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IG0LAEGU2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "要执行的命令行文本/数组"
//					}
//				},
//				"options": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IG0LAEGU3",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IG0KVFDB4",
//			"attrs": {
//				"cmdBash": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"orgContent": {
//					"type": "string",
//					"valText": ""
//				},
//				"orgCmdContent": {
//					"type": "string",
//					"valText": ""
//				},
//				"project": {
//					"type": "auto",
//					"valText": "#globalContext.project"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IG0KVFDB5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IG0KVFDB6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IG0L3R920",
//					"attrs": {
//						"id": "SwitchAction",
//						"viewName": "",
//						"label": "",
//						"x": "145",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG0LAEGU4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG0LAEGU5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG0LAEGS0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IG0LAEGR0",
//									"attrs": {
//										"id": "Create",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG0LAEGU6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG0LAEGU7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action===\"Create\""
//									},
//									"linkedSeg": "1IG0L7VK60"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IG0L4HVP0",
//									"attrs": {
//										"id": "Command",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG0LAEGU8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG0LAEGU9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action===\"Command\""
//									},
//									"linkedSeg": "1IG0L8V2P0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IG0L4SCA0",
//									"attrs": {
//										"id": "Close",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG0LAEGU10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG0LAEGU11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action===\"Close\""
//									},
//									"linkedSeg": "1IG0L9DUD0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IG2VD41R0",
//									"attrs": {
//										"id": "Content",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG2VD4210",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG2VD4211",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action===\"Content\""
//									},
//									"linkedSeg": "1IG2VAJS20"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IG2VAS500",
//									"attrs": {
//										"id": "Clear",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG2VD4212",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG2VD4213",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action===\"Clear\""
//									},
//									"linkedSeg": "1IG2VBQIK0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH4M0AUA0",
//									"attrs": {
//										"id": "Wait",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH4M0AUH0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH4M0AUH1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action===\"Wait\""
//									},
//									"linkedSeg": "1IH4M02OP0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IG0L7VK60",
//					"attrs": {
//						"id": "CreateBash",
//						"viewName": "",
//						"label": "",
//						"x": "425",
//						"y": "125",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG0LAEGU12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG0LAEGU13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG0LAEGS1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IG0L8V2P0",
//					"attrs": {
//						"id": "RunCommand",
//						"viewName": "",
//						"label": "",
//						"x": "425",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG0LAEGU14",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG0LAEGU15",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG0LAEGS2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF4OKS70"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1IIF4OKS70",
//					"attrs": {
//						"id": "LoopCmd",
//						"viewName": "",
//						"label": "",
//						"x": "670",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF4PTNV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF4PTNV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#commands",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1IIF4PTNV2",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF4QE770"
//						},
//						"catchlet": {
//							"jaxId": "1IIF4PTNQ0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF4PECH0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IIF4QE770",
//					"attrs": {
//						"id": "RunOneCmd",
//						"viewName": "",
//						"label": "",
//						"x": "890",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF5P1FA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF5P1FA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIF5P1F20",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF4R4RO0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IIF4R4RO0",
//					"attrs": {
//						"id": "IsDone",
//						"viewName": "",
//						"label": "",
//						"x": "1115",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF5P1FA2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF5P1FA3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIF5P1F22",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IIF7R6230"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IIF5P1F21",
//									"attrs": {
//										"id": "NotDone",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IIF5P1FA4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IIF5P1FA5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!isIdle"
//									},
//									"linkedSeg": "1IIDUEG0G0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IG0L9DUD0",
//					"attrs": {
//						"id": "CloseBash",
//						"viewName": "",
//						"label": "",
//						"x": "425",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG0LAEGU16",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG0LAEGU17",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG0LAEGS3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IG2VAJS20",
//					"attrs": {
//						"id": "GetContent",
//						"viewName": "",
//						"label": "",
//						"x": "425",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG2VD4214",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG2VD4215",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG2VD41S0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IG2VBQIK0",
//					"attrs": {
//						"id": "Clear",
//						"viewName": "",
//						"label": "",
//						"x": "425",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG2VD4216",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG2VD4217",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG2VD41S1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH4M02OP0",
//					"attrs": {
//						"id": "Wait",
//						"viewName": "",
//						"label": "",
//						"x": "425",
//						"y": "450",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IH4M0AUH2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH4M0AUH3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH4M0AUB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IIDUEG0G0",
//					"attrs": {
//						"id": "GetReact",
//						"viewName": "",
//						"label": "",
//						"x": "1315",
//						"y": "95",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIDV9VFL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIDV9VFL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`\n### 角色任务\n你是一个根据Terminal输出的最后几行内容来判断是否需要需要向terminal内输入，以继续执行当前操作的AI\n\n### 对话\n- 对话的输入是当前Terminal输出的最后几行内容\n- 请用JSON格式返回当前需要进行的操作\n\n### 返回JSON属性\n- \"action\" {string}: 下一步的动作，可以取的值有:\"Wait\"， \"Input\", \"Finish\"和\"AskUser\"\n\t- \"Wait\": 当前Termnial还在执行任务，不需要干预\n    - \"Input\": 当前Terminal需要用户输入才能继续执行，而你可以生成输入内容，例如询问是否确认某个操作。\n    - \"AskUser\": 当前Terminal需要用户输入才能继续执行，而你无法生成输入内容，例如询问sudo、登陆密码等\n\n- \"input\" {string}: 当\"action\"属性为\"Input\"时，需要向terminal里输入的内容。例如, 当询问是否继续时: \"y\"等。当\"action\"属性为\"AskUser\"时，需要询问用户的内容。\n\n### 确保流程进行\n- 除非是有明确的安全风险或者你无法提供相应的信息，你应该尽量使用\"Input\"的action来自动回复，保证流程不受中断。\n`\n",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IIDV9VFE0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF4UL9V0"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "No",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"1IIF6SA1I2\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IIF4PECH0",
//					"attrs": {
//						"id": "GenResult",
//						"viewName": "",
//						"label": "",
//						"x": "890",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF4PTNV3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF4PTNV4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIF4PTNQ1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IIF4SPFB0",
//					"attrs": {
//						"id": "NextCmd",
//						"viewName": "",
//						"label": "",
//						"x": "1790",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF5P1FA6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF5P1FA7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIF5P1F23",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IIF4UL9V0",
//					"attrs": {
//						"id": "CheckReact",
//						"viewName": "",
//						"label": "",
//						"x": "1535",
//						"y": "95",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF5P1FA8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF5P1FA9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIF5P1F30",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IIF5056O0",
//									"attrs": {
//										"id": "AskUser",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IIF5P1FA10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IIF5P1FA11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"AskUser\""
//									},
//									"linkedSeg": "1J1V9GOIF0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IIF5P1F24",
//									"attrs": {
//										"id": "Input",
//										"desc": "输出节点。",
//										"output": "#input.input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IIF5P1FA12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IIF5P1FA13",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Input\""
//									},
//									"linkedSeg": "1IIF512K60"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IIF50B2J0",
//									"attrs": {
//										"id": "Wait",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IIF5P1FA14",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IIF5P1FA15",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Wait\""
//									},
//									"linkedSeg": "1IIF8FDCS0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IIF512K60",
//					"attrs": {
//						"id": "DoInput",
//						"viewName": "",
//						"label": "",
//						"x": "1790",
//						"y": "65",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF5P1FA16",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF5P1FA17",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIF5P1F31",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF89Q1I0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IIF53A7Q0",
//					"attrs": {
//						"id": "NotifyUser",
//						"viewName": "",
//						"label": "",
//						"x": "1770",
//						"y": "-160",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF5P1FA18",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF5P1FA19",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIF5P1F32",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IIF89Q1I0",
//					"attrs": {
//						"id": "WaitIdle",
//						"viewName": "",
//						"label": "",
//						"x": "2025",
//						"y": "65",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIF8ATEQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIF8ATEQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIF8ATEI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF54S290"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IIF54S290",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2150",
//						"y": "-70",
//						"outlet": {
//							"jaxId": "1IIF5P1FA23",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF556UM0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IIF556UM0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1145",
//						"y": "-70",
//						"outlet": {
//							"jaxId": "1IIF5P1FA24",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF4R4RO0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IIF7R6230",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1315",
//						"y": "205",
//						"outlet": {
//							"jaxId": "1IIF7RN080",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF4SPFB0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IIF8FDCS0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1795",
//						"y": "135",
//						"outlet": {
//							"jaxId": "1IIF8G9EB0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF8G3UP0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IIF8G3UP0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1905",
//						"y": "135",
//						"outlet": {
//							"jaxId": "1IIF8G9EB1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF89Q1I0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1J1V9GOIF0",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "1790",
//						"y": "-10",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1V9HK8O0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1V9HK8O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#input.input",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1J1V9HK8H0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIF512K60"
//						}
//					},
//					"icon": "chat.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"Bash Ops\",\"path\":\"/@AgentBuilder/Bash.js\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"terminal.svg\",\"catalog\":\"AI Call\"}"
//	}
//}