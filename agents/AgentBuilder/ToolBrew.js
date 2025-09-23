//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IJ40NO870MoreImports*/
import child_process from "child_process";
/*}#1IJ40NO870MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"action":{
			"name":"action","type":"string",
			"defaultValue":"",
			"desc":"要执行的操作：install/uninstall/check",
		},
		"pkgName":{
			"name":"pkgName","type":"string",
			"defaultValue":"",
			"desc":"要操作的软件包名称",
		}
	},
	/*#{1IJ40NO870ArgsView*/
	/*}#1IJ40NO870ArgsView*/
};

/*#{1IJ40NO870StartDoc*/
function checkBrewInstallation() {
	return new Promise((resolve, reject) => {
		child_process.exec('brew --version', (error, stdout, stderr) => {
			if (error) {
				reject(`Error: ${error.message}`);
				return;
			}
			if (stderr) {
				reject(`stderr: ${stderr}`);
				return;
			}
			resolve(`Brew installed: ${stdout}`);
		});
	});
}/*}#1IJ40NO870StartDoc*/
//----------------------------------------------------------------------------
let ToolBrew=async function(session){
	let action,pkgName;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,SwitchAction,Install,Uninstall,Check,AskInstallBrew,SwitchBrew,InstallBrew,AbortInstall,FinInstall,FinUninstall,FinCheck,CheckBrew,Verify,CheckInstall,LLMcheck,Success,Failure,Retry;
	/*#{1IJ40NO870LocalVals*/
	/*}#1IJ40NO870LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			action=input.action;
			pkgName=input.pkgName;
		}else{
			action=undefined;
			pkgName=undefined;
		}
		/*#{1IJ40NO870ParseArgs*/
		/*}#1IJ40NO870ParseArgs*/
	}
	
	/*#{1IJ40NO870PreContext*/
	/*}#1IJ40NO870PreContext*/
	context={};
	/*#{1IJ40NO870PostContext*/
	/*}#1IJ40NO870PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IJ40NV0F0
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(action===undefined || action==="") missing=true;
		if(pkgName===undefined || pkgName==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:CheckBrew,result:(result),preSeg:"1IJ40NV0F0",outlet:"1IJ411OA50"};
	};
	FixArgs.jaxId="1IJ40NV0F0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["SwitchAction"]=SwitchAction=async function(input){//:1IJ41329S0
		let result=input;
		if(action.toLowerCase()==="install"){
			return {seg:Verify,result:(input),preSeg:"1IJ41329S0",outlet:"1IJ415BPN0"};
		}
		if(action.toLowerCase()==="uninstall"){
			return {seg:Uninstall,result:(input),preSeg:"1IJ41329S0",outlet:"1IJ413I2I0"};
		}
		if(action.toLowerCase()==="check"){
			return {seg:Check,result:(input),preSeg:"1IJ41329S0",outlet:"1IJ413NIB0"};
		}
		return {result:result};
	};
	SwitchAction.jaxId="1IJ41329S0"
	SwitchAction.url="SwitchAction@"+agentURL
	
	segs["Install"]=Install=async function(input){//:1IJ414D9E0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`brew install ${pkgName}`;
		args['options']="";
		/*#{1IJ414D9E0PreCodes*/
		/*}#1IJ414D9E0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IJ414D9E0PostCodes*/
		/*}#1IJ414D9E0PostCodes*/
		return {seg:LLMcheck,result:(result),preSeg:"1IJ414D9E0",outlet:"1IJ415BPN2"};
	};
	Install.jaxId="1IJ414D9E0"
	Install.url="Install@"+agentURL
	
	segs["Uninstall"]=Uninstall=async function(input){//:1IJ414S3J0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`brew uninstall ${pkgName}`;
		args['options']="";
		/*#{1IJ414S3J0PreCodes*/
		/*}#1IJ414S3J0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IJ414S3J0PostCodes*/
		/*}#1IJ414S3J0PostCodes*/
		return {seg:FinUninstall,result:(result),preSeg:"1IJ414S3J0",outlet:"1IJ415BPN3"};
	};
	Uninstall.jaxId="1IJ414S3J0"
	Uninstall.url="Uninstall@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1IJ4156ER0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`brew list ${pkgName}`;
		args['options']="";
		/*#{1IJ4156ER0PreCodes*/
		/*}#1IJ4156ER0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IJ4156ER0PostCodes*/
		/*}#1IJ4156ER0PostCodes*/
		return {seg:FinCheck,result:(result),preSeg:"1IJ4156ER0",outlet:"1IJ415BPN4"};
	};
	Check.jaxId="1IJ4156ER0"
	Check.url="Check@"+agentURL
	
	segs["AskInstallBrew"]=AskInstallBrew=async function(input){//:1IJ41EDJ00
		let prompt=("当前没有Brew环境，是否安装Brew?")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"安装",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"放弃安装",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:InstallBrew,result:(result),preSeg:"1IJ41EDJ00",outlet:"1IJ41EDIE0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:InstallBrew,result:(result),preSeg:"1IJ41EDJ00",outlet:"1IJ41EDIE0"};
		}else if(item.code===1){
			return {seg:AbortInstall,result:(result),preSeg:"1IJ41EDJ00",outlet:"1IJ41EDIE1"};
		}
		return {result:result};
	};
	AskInstallBrew.jaxId="1IJ41EDJ00"
	AskInstallBrew.url="AskInstallBrew@"+agentURL
	
	segs["SwitchBrew"]=SwitchBrew=async function(input){//:1IJ41EPKU0
		let result=input;
		if(!input.includes("not found")){
			return {seg:SwitchAction,result:(input),preSeg:"1IJ41EPKU0",outlet:"1IJ41MM8M2"};
		}
		return {seg:AskInstallBrew,result:(result),preSeg:"1IJ41EPKU0",outlet:"1IJ41MM8M3"};
	};
	SwitchBrew.jaxId="1IJ41EPKU0"
	SwitchBrew.url="SwitchBrew@"+agentURL
	
	segs["InstallBrew"]=InstallBrew=async function(input){//:1IJ41M3D80
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`,`echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.bash_profile`,`source ~/.bash_profile`,`echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc`,`source ~/.zshrc`];
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:SwitchAction,result:(result),preSeg:"1IJ41M3D80",outlet:"1IJ41MM8M4"};
	};
	InstallBrew.jaxId="1IJ41M3D80"
	InstallBrew.url="InstallBrew@"+agentURL
	
	segs["AbortInstall"]=AbortInstall=async function(input){//:1IJ41MD230
		let result=input
		/*#{1IJ41MD230Code*/
		result={result:"Abort",content:(($ln==="CN")?("当前环境下没有安装brew工具。"):/*EN*/("The brew tool is not installed in the current environment."))};
		/*}#1IJ41MD230Code*/
		return {result:result};
	};
	AbortInstall.jaxId="1IJ41MD230"
	AbortInstall.url="AbortInstall@"+agentURL
	
	segs["FinInstall"]=FinInstall=async function(input){//:1IJ42E4DL0
		let result=input
		/*#{1IJ42E4DL0Code*/
		input=""+input;
		if(input.indexOf("Error:")>=0){
			result={result:"Failed",content:`安装失败，操作日志：\n${input}`};
		}else{
			result={result:"Finish",content:`安装成功。`};
		}
		/*}#1IJ42E4DL0Code*/
		return {result:result};
	};
	FinInstall.jaxId="1IJ42E4DL0"
	FinInstall.url="FinInstall@"+agentURL
	
	segs["FinUninstall"]=FinUninstall=async function(input){//:1IJ42ECIF0
		let result=input
		/*#{1IJ42ECIF0Code*/
		input=""+input;
		if(input.indexOf("Error:")>=0){
			result={result:"Failed",content:`卸载失败，操作日志：\n${input}`};
		}else{
			result={result:"Finish",content:`卸载成功`};
		}
		/*}#1IJ42ECIF0Code*/
		return {result:result};
	};
	FinUninstall.jaxId="1IJ42ECIF0"
	FinUninstall.url="FinUninstall@"+agentURL
	
	segs["FinCheck"]=FinCheck=async function(input){//:1IJ42EMUJ0
		let result=input
		/*#{1IJ42EMUJ0Code*/
		input=""+input;
		if(input.indexOf("Error:")>=0){
			result={result:"Missing",content:`${pkgName} 没有安装。`};
		}else{
			result={result:"Ready",content:`${pkgName} 已安装。`};
		}
		/*}#1IJ42EMUJ0Code*/
		return {result:result};
	};
	FinCheck.jaxId="1IJ42EMUJ0"
	FinCheck.url="FinCheck@"+agentURL
	
	segs["CheckBrew"]=CheckBrew=async function(input){//:1IL0IJ4I00
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="brew";
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:SwitchBrew,result:(result),preSeg:"1IL0IJ4I00",outlet:"1IL0IJUFL0"};
	};
	CheckBrew.jaxId="1IL0IJ4I00"
	CheckBrew.url="CheckBrew@"+agentURL
	
	segs["Verify"]=Verify=async function(input){//:1IVRNAS4R0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`brew list --versions ${pkgName}`;
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:CheckInstall,result:(result),preSeg:"1IVRNAS4R0",outlet:"1IVRNC0TA0"};
	};
	Verify.jaxId="1IVRNAS4R0"
	Verify.url="Verify@"+agentURL
	
	segs["CheckInstall"]=CheckInstall=async function(input){//:1IVRNCEQR0
		let result=input;
		if(input.split(pkgName).length - 1 === 2){
			return {result:input};
		}
		return {seg:Install,result:(result),preSeg:"1IVRNCEQR0",outlet:"1IVRNF36F1"};
	};
	CheckInstall.jaxId="1IVRNCEQR0"
	CheckInstall.url="CheckInstall@"+agentURL
	
	segs["LLMcheck"]=LLMcheck=async function(input){//:1J58KVSNO0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=LLMcheck.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:(($ln==="CN")?(`用户的输入是终端的输出，你需要解析这个输出，判断安装是否成功。若成功，返回以下格式的JSON： { "status": "success" } 若失败，返回失败的原因以及相关的错误信息，格式如下： { "status": "failure", "failure_reason": "<原因>"}`):(`User input is the output of the terminal. You need to parse this output to determine if the installation was successful. If successful, return the following JSON format: { "status": "success" } If failed, return the reason for failure and relevant error information in the following format: { "status": "failure", "failure_reason": "<reason>"}`))},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("LLMcheck@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:Success,result:(result),preSeg:"1J58KVSNO0",outlet:"1J58L5AM60"};
	};
	LLMcheck.jaxId="1J58KVSNO0"
	LLMcheck.url="LLMcheck@"+agentURL
	
	segs["Success"]=Success=async function(input){//:1J58L5O440
		let result=input;
		if(input.status==="success"){
			return {seg:FinInstall,result:(input),preSeg:"1J58L5O440",outlet:"1J58LALL70"};
		}
		return {seg:Failure,result:(result),preSeg:"1J58L5O440",outlet:"1J58LALL71"};
	};
	Success.jaxId="1J58L5O440"
	Success.url="Success@"+agentURL
	
	segs["Failure"]=Failure=async function(input){//:1J58L8IA10
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?(`${pkgName}安装失败，原因是${input.reason}`):(`${pkgName} installation failed due to ${input.reason}`));
		session.addChatText(role,content,opts);
		return {seg:Retry,result:(result),preSeg:"1J58L8IA10",outlet:"1J58LALL72"};
	};
	Failure.jaxId="1J58L8IA10"
	Failure.url="Failure@"+agentURL
	
	segs["Retry"]=Retry=async function(input){//:1J58LFBGK0
		let prompt=((($ln==="CN")?("是否重试"):("Whether to retry")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("是的"):("Yes")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("否"):("No")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Install,result:(result),preSeg:"1J58LFBGK0",outlet:"1J58LFBG80"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Install,result:(result),preSeg:"1J58LFBGK0",outlet:"1J58LFBG80"};
		}else if(item.code===1){
			return {result:result};
		}
		return {result:result};
	};
	Retry.jaxId="1J58LFBGK0"
	Retry.url="Retry@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolBrew",
		url:agentURL,
		autoStart:true,
		jaxId:"1IJ40NO870",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{action,pkgName}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IJ40NO870PreEntry*/
			/*}#1IJ40NO870PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IJ40NO870PostEntry*/
			/*}#1IJ40NO870PostEntry*/
			return result;
		},
		/*#{1IJ40NO870MoreAgentAttrs*/
		/*}#1IJ40NO870MoreAgentAttrs*/
	};
	/*#{1IJ40NO870PostAgent*/
	/*}#1IJ40NO870PostAgent*/
	return agent;
};
/*#{1IJ40NO870ExCodes*/
/*}#1IJ40NO870ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolBrew",
		description: "这是在MacOS下通过brew工具安装/检查/卸载软件的智能体。请告知：\n1）要进行的操作。\n2）软件的名称。\n3）如果有必要，软件的版本。本智能体会执行brew命令并返回执行的结果。",
		parameters:{
			type: "object",
			properties:{
				action:{type:"string",description:"要执行的操作：install/uninstall/check",enum:["install","uninstall","check"]},
				pkgName:{type:"string",description:"要操作的软件包名称"}
			}
		}
	},
	isChatApi: true
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
		name:"ToolBrew",showName:"ToolBrew",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"action":{name:"action",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"pkgName":{name:"pkgName",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","action","pkgName","codes","desc"],
		desc:"这是在MacOS下通过brew工具安装/检查/卸载软件的智能体。请告知：\n1）要进行的操作。\n2）软件的名称。\n3）如果有必要，软件的版本。本智能体会执行brew命令并返回执行的结果。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolBrew"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['action']=");this.genAttrStatement(seg.getAttr("action"));coder.packText(";");coder.newLine();
			coder.packText("args['pkgName']=");this.genAttrStatement(seg.getAttr("pkgName"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/builder2/ai/ToolBrew.js",args,false);`);coder.newLine();
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
/*#{1IJ40NO870PostDoc*/
/*}#1IJ40NO870PostDoc*/


export default ToolBrew;
export{ToolBrew,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IJ40NO870",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IJ40NO871",
//			"attrs": {
//				"ToolBrew": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IJ40NO877",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IJ40NO878",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IJ40NO879",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IJ40NO8710",
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
//			"jaxId": "1IJ40NO872",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IJ40NO873",
//			"attrs": {
//				"action": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ411OA80",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要执行的操作：install/uninstall/check",
//						"enum": {
//							"type": "array",
//							"def": "Array",
//							"attrs": [
//								{
//									"type": "auto",
//									"valText": "install"
//								},
//								{
//									"type": "auto",
//									"valText": "uninstall"
//								},
//								{
//									"type": "auto",
//									"valText": "check"
//								}
//							]
//						}
//					}
//				},
//				"pkgName": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ411OA81",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要操作的软件包名称"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IJ40NO874",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IJ40NO875",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IJ40NO876",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IJ40NV0F0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "100",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1IJ411OA50",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0IJ4I00"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJ41329S0",
//					"attrs": {
//						"id": "SwitchAction",
//						"viewName": "",
//						"label": "",
//						"x": "840",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ415BPR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ415BPR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ415BPN1",
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
//									"jaxId": "1IJ415BPN0",
//									"attrs": {
//										"id": "Install",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ415BPR2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ415BPR3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.toLowerCase()===\"install\""
//									},
//									"linkedSeg": "1IVRNAS4R0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ413I2I0",
//									"attrs": {
//										"id": "Uninstall",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ415BPR4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ415BPR5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.toLowerCase()===\"uninstall\""
//									},
//									"linkedSeg": "1IJ414S3J0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ413NIB0",
//									"attrs": {
//										"id": "Check",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ415BPR6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ415BPR7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.toLowerCase()===\"check\""
//									},
//									"linkedSeg": "1IJ4156ER0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IJ414D9E0",
//					"attrs": {
//						"id": "Install",
//						"viewName": "",
//						"label": "",
//						"x": "1615",
//						"y": "60",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ415BPR8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ415BPR9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`brew install ${pkgName}`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IJ415BPN2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J58KVSNO0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IJ414S3J0",
//					"attrs": {
//						"id": "Uninstall",
//						"viewName": "",
//						"label": "",
//						"x": "1095",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ415BPR10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ415BPR11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`brew uninstall ${pkgName}`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IJ415BPN3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ42ECIF0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IJ4156ER0",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "1095",
//						"y": "260",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ415BPR12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ415BPR13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`brew list ${pkgName}`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IJ415BPN4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ42EMUJ0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IJ41EDJ00",
//					"attrs": {
//						"id": "AskInstallBrew",
//						"viewName": "",
//						"label": "",
//						"x": "815",
//						"y": "500",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "当前没有Brew环境，是否安装Brew?",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJ41MM8M1",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ41EDIE0",
//									"attrs": {
//										"id": "Install",
//										"desc": "输出节点。",
//										"text": "安装",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ41MM8R2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ41MM8R3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ41M3D80"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ41EDIE1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "放弃安装",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ41MM8R4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ41MM8R5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ41MD230"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJ41EPKU0",
//					"attrs": {
//						"id": "SwitchBrew",
//						"viewName": "",
//						"label": "",
//						"x": "540",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ41MM8R6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ41MM8R7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ41MM8M3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJ41EDJ00"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ41MM8M2",
//									"attrs": {
//										"id": "BrewReady",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ41MM8R8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ41MM8R9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!input.includes(\"not found\")"
//									},
//									"linkedSeg": "1IJ41329S0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IJ41M3D80",
//					"attrs": {
//						"id": "InstallBrew",
//						"viewName": "",
//						"label": "",
//						"x": "1065",
//						"y": "435",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ41MM8R10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ41MM8R11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[`/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"`,`echo 'export PATH=\"/opt/homebrew/bin:$PATH\"' >> ~/.bash_profile`,`source ~/.bash_profile`,`echo 'export PATH=\"/opt/homebrew/bin:$PATH\"' >> ~/.zshrc`,`source ~/.zshrc`]",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IJ41MM8M4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ41MOO20"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ41MD230",
//					"attrs": {
//						"id": "AbortInstall",
//						"viewName": "",
//						"label": "",
//						"x": "1065",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ41MM8R12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ41MM8R13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ41MM8M5",
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
//					"def": "connector",
//					"jaxId": "1IJ41MOO20",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1215",
//						"y": "350",
//						"outlet": {
//							"jaxId": "1IJ41O2E60",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ41MTCC0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IJ41MTCC0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "870",
//						"y": "350",
//						"outlet": {
//							"jaxId": "1IJ41O2E61",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ41329S0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ42E4DL0",
//					"attrs": {
//						"id": "FinInstall",
//						"viewName": "",
//						"label": "",
//						"x": "2275",
//						"y": "45",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ42KADJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ42KADJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ42KADC0",
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
//					"jaxId": "1IJ42ECIF0",
//					"attrs": {
//						"id": "FinUninstall",
//						"viewName": "",
//						"label": "",
//						"x": "1295",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ42KADK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ42KADK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ42KADC1",
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
//					"jaxId": "1IJ42EMUJ0",
//					"attrs": {
//						"id": "FinCheck",
//						"viewName": "",
//						"label": "",
//						"x": "1295",
//						"y": "260",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ42KADK2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ42KADK3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ42KADC2",
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
//					"def": "Bash",
//					"jaxId": "1IL0IJ4I00",
//					"attrs": {
//						"id": "CheckBrew",
//						"viewName": "",
//						"label": "",
//						"x": "310",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0IKE780",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0IKE781",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "brew",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IL0IJUFL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ41EPKU0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IVRNAS4R0",
//					"attrs": {
//						"id": "Verify",
//						"viewName": "",
//						"label": "",
//						"x": "1095",
//						"y": "45",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVRNC0TG0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVRNC0TG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`brew list --versions ${pkgName}`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IVRNC0TA0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVRNCEQR0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IVRNCEQR0",
//					"attrs": {
//						"id": "CheckInstall",
//						"viewName": "",
//						"label": "",
//						"x": "1310",
//						"y": "45",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVRNF36I0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVRNF36I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IVRNF36F1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJ414D9E0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IVRNF36F0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IVRNF36I2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IVRNF36I3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.split(pkgName).length - 1 === 2"
//									}
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1J58KVSNO0",
//					"attrs": {
//						"id": "LLMcheck",
//						"viewName": "",
//						"label": "",
//						"x": "1820",
//						"y": "60",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J58L5AMC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J58L5AMC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": {
//							"type": "string",
//							"valText": "#`User input is the output of the terminal. You need to parse this output to determine if the installation was successful. If successful, return the following JSON format: { \"status\": \"success\" } If failed, return the reason for failure and relevant error information in the following format: { \"status\": \"failure\", \"failure_reason\": \"<reason>\"}`",
//							"localize": {
//								"EN": "#`User input is the output of the terminal. You need to parse this output to determine if the installation was successful. If successful, return the following JSON format: { \"status\": \"success\" } If failed, return the reason for failure and relevant error information in the following format: { \"status\": \"failure\", \"failure_reason\": \"<reason>\"}`",
//								"CN": "#`用户的输入是终端的输出，你需要解析这个输出，判断安装是否成功。若成功，返回以下格式的JSON： { \"status\": \"success\" } 若失败，返回失败的原因以及相关的错误信息，格式如下： { \"status\": \"failure\", \"failure_reason\": \"<原因>\"}`"
//							},
//							"localizable": true
//						},
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
//							"jaxId": "1J58L5AM60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J58L5O440"
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J58L5O440",
//					"attrs": {
//						"id": "Success",
//						"viewName": "",
//						"label": "",
//						"x": "2055",
//						"y": "60",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J58LALLD0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J58LALLD1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J58LALL71",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J58L8IA10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J58LALL70",
//									"attrs": {
//										"id": "Success",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J58LALLD2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J58LALLD3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.status===\"success\""
//									},
//									"linkedSeg": "1IJ42E4DL0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J58L8IA10",
//					"attrs": {
//						"id": "Failure",
//						"viewName": "",
//						"label": "",
//						"x": "2280",
//						"y": "150",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J58LALLD4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J58LALLD5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "#`${pkgName} installation failed due to ${input.reason}`",
//							"localize": {
//								"EN": "#`${pkgName} installation failed due to ${input.reason}`",
//								"CN": "#`${pkgName}安装失败，原因是${input.reason}`"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J58LALL72",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J58LFBGK0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1J58LFBGK0",
//					"attrs": {
//						"id": "Retry",
//						"viewName": "",
//						"label": "",
//						"x": "2475",
//						"y": "150",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Whether to retry",
//							"localize": {
//								"EN": "Whether to retry",
//								"CN": "是否重试"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1J58LGSMQ0",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J58LFBG80",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Yes",
//											"localize": {
//												"EN": "Yes",
//												"CN": "是的"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J58LGSN60",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J58LGSN61",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1J58LH35E0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J58LFBG81",
//									"attrs": {
//										"id": "No",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "No",
//											"localize": {
//												"EN": "No",
//												"CN": "否"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J58LGSN62",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J58LGSN63",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									}
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J58LH35E0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2610",
//						"y": "295",
//						"outlet": {
//							"jaxId": "1J58LHQIP0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J58LH8FL0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J58LH8FL0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1640",
//						"y": "295",
//						"outlet": {
//							"jaxId": "1J58LHQIP1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ414D9E0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是在MacOS下通过brew工具安装/检查/卸载软件的智能体。请告知：\n1）要进行的操作。\n2）软件的名称。\n3）如果有必要，软件的版本。本智能体会执行brew命令并返回执行的结果。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}