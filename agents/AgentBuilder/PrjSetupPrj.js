//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IG38I67R1MoreImports*/
import fsp from 'fs/promises';
/*}#1IG38I67R1MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"prjURL":{
			"name":"prjURL","type":"auto",
			"defaultValue":"",
			"desc":"项目的GitHub地址",
		},
		"dirPath":{
			"name":"dirPath","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"当前项目工程所在的本地目录路径",
		}
	},
	/*#{1IG38I67R1ArgsView*/
	/*}#1IG38I67R1ArgsView*/
};

/*#{1IG38I67R1StartDoc*/
//----------------------------------------------------------------------------
function extractOwnerAndRepo(url) {
	const regex = /(?:https:\/\/|git@)github\.com[:\/]([^\/]+)\/([^\/]+)(?:\.git)?/;
	const match = url.match(regex);

	if (match) {
		const owner = match[1];
		const repo = match[2];
		return { owner, repo };
	} else {
		throw new Error('Invalid GitHub URL');
	}
}
//----------------------------------------------------------------------------
async function getDefaultBranch(owner, repo, token) {
	const url = `https://api.github.com/repos/${owner}/${repo}`;
	const headers = {
		'Accept': 'application/vnd.github.v3+json'
	};
	if (token) {
		headers['Authorization'] = `token ${token}`;
	}
	try {
		const response = await fetch(url, { headers });

		if (!response.ok) {
			const errorData = await response.json();
			throw new Error(`Error: ${errorData.message}`);
		}

		const data = await response.json();
		return data.default_branch;
	} catch (error) {
		console.error('Error fetching default branch:', error.message);
		return null;
	}
}
/*}#1IG38I67R1StartDoc*/
//----------------------------------------------------------------------------
let PrjSetupPrj=async function(session){
	let prjURL,dirPath;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,InitPrj,InitEnv,AskStep,SetupDir,SetupPrj,TestPrj,GenReport,AbortSetup,CheckSetup,SetupFailed,AskTest,TestResult,TestFailed,AskUninstall,Uninstall,FailEnd,JumpUninstall,AskUninstall2,Uninstall2,DirResult,DirFailed;
	let project=null;
	
	/*#{1IG38I67R1LocalVals*/
	async function addLog(log,notify){
		let logs=globalContext.agentBuilderLogs;
		if(!logs){
			logs=globalContext.agentBuilderLogs=[];
		}
		logs.push(log);
		if(notify){
			session.addChatText("log",JSON.stringify(log));
		}
	}
	/*}#1IG38I67R1LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			prjURL=input.prjURL;
			dirPath=input.dirPath;
		}else{
			prjURL=undefined;
			dirPath=undefined;
		}
		/*#{1IG38I67R1ParseArgs*/
		/*}#1IG38I67R1ParseArgs*/
	}
	
	/*#{1IG38I67R1PreContext*/
	/*}#1IG38I67R1PreContext*/
	context={};
	/*#{1IG38I67R1PostContext*/
	//await session.callClient("ConnectAgentDebug",{port:9115,entryURL:agentURL,entryAgent:PrjSetupPrj.sourceDef});//TODO: Get port from session/AgentNode
	/*}#1IG38I67R1PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IH71L8DF0
		let result=input;
		let missing=false;
		if(prjURL===undefined || prjURL==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:InitPrj,result:(result),preSeg:"1IH71L8DF0",outlet:"1IH71LMKO0"};
	};
	FixArgs.jaxId="1IH71L8DF0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["InitPrj"]=InitPrj=async function(input){//:1IG5FD2R20
		let result=input
		/*#{1IG5FD2R20Code*/
		let gitURL,rawURL,prjName,parts,owner,branch;
		if(!prjURL.startsWith("https://")){
			prjURL="https://"+prjURL;
		}
		if(prjURL.endsWith(".git")){
			gitURL=prjURL;
			prjURL=prjURL.slice(0,-4);
		}else{
			if(prjURL.endsWith("/")){
				prjURL=prjURL.substring(0,prjURL.length-1);
			}
			gitURL=prjURL+".git";
		}
		parts = prjURL.split('/');
		prjName=parts[parts.length - 1];
		owner=parts[parts.length - 2];
		branch=await getDefaultBranch(owner,prjName)||"main";
		rawURL="https://raw.githubusercontent.com/"+prjURL.substring("https://github.com/".length)+"/refs/heads/"+branch;
		project={
			owner:owner,
			repo:prjName,
			branch:branch,
			name:prjName,
			url:prjURL,
			gitURL:gitURL,
			rawURL:rawURL,
			dirPath:dirPath,
			requirements:{},
			conda:null,
			venv:null,
			progress:[],
			bashLogs:[]
		};
		globalContext.project=project;
		session.debugLog("Project inited.");
		/*}#1IG5FD2R20Code*/
		return {seg:InitEnv,result:(result),preSeg:"1IG5FD2R20",outlet:"1IG5FDRUA0"};
	};
	InitPrj.jaxId="1IG5FD2R20"
	InitPrj.url="InitPrj@"+agentURL
	
	segs["InitEnv"]=InitEnv=async function(input){//:1IG38J1M10
		let result;
		let sourcePath=pathLib.join(basePath,"./SysInitWorkEnv.js");
		let arg={};
		/*#{1IG38J1M10Input*/
		/*}#1IG38J1M10Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IG38J1M10Output*/
		session.callClient("RegEnvProjectInfo",{env:globalContext.env,project:globalContext.project});
		/*}#1IG38J1M10Output*/
		return {seg:AskStep,result:(result),preSeg:"1IG38J1M10",outlet:"1IG392PPE0"};
	};
	InitEnv.jaxId="1IG38J1M10"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["AskStep"]=AskStep=async function(input){//:1IG38NVAB0
		let prompt=((($ln==="CN")?("是否在本地部署项目？"):("Deploy the project?")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=("部署")||"OK";
		let button2=("取消")||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:SetupDir,result:(result),preSeg:"1IG38NVAB0",outlet:"1IG38NV9U0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:true,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:SetupDir,result:(result),preSeg:"1IG38NVAB0",outlet:"1IG38NV9U0"};
		}
		result=("")||result;
		return {seg:AbortSetup,result:(result),preSeg:"1IG38NVAB0",outlet:"1IG38NV9U1"};
	
	};
	AskStep.jaxId="1IG38NVAB0"
	AskStep.url="AskStep@"+agentURL
	
	segs["SetupDir"]=SetupDir=async function(input){//:1IG38V9R90
		let result;
		let sourcePath=pathLib.join(basePath,"./PrjSetupPrjDir.js");
		let arg={};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:DirResult,result:(result),preSeg:"1IG38V9R90",outlet:"1IG392PPF4"};
	};
	SetupDir.jaxId="1IG38V9R90"
	SetupDir.url="SetupDir@"+agentURL
	
	segs["SetupPrj"]=SetupPrj=async function(input){//:1IG396KMU0
		let result;
		let sourcePath=pathLib.join(basePath,"./PrjDoSetupPrj.js");
		let arg={};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:CheckSetup,result:(result),preSeg:"1IG396KMU0",outlet:"1IG39IF140"};
	};
	SetupPrj.jaxId="1IG396KMU0"
	SetupPrj.url="SetupPrj@"+agentURL
	
	segs["TestPrj"]=TestPrj=async function(input){//:1IG399DKK0
		let result;
		let sourcePath=pathLib.join(basePath,"./PrjTestPrj.js");
		let arg={};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:TestResult,result:(result),preSeg:"1IG399DKK0",outlet:"1IG39IF142"};
	};
	TestPrj.jaxId="1IG399DKK0"
	TestPrj.url="TestPrj@"+agentURL
	
	segs["GenReport"]=GenReport=async function(input){//:1IG399QD10
		let result=input
		/*#{1IG399QD10Code*/
		/*}#1IG399QD10Code*/
		return {result:result};
	};
	GenReport.jaxId="1IG399QD10"
	GenReport.url="GenReport@"+agentURL
	
	segs["AbortSetup"]=AbortSetup=async function(input){//:1IG63NL6J0
		let result=input;
		let role="assistant";
		let content=(($ln==="CN")?("项目部署已取消."):("Project deployment has been cancelled."));
		/*#{1IG63NL6J0PreCodes*/
		/*}#1IG63NL6J0PreCodes*/
		session.addChatText(role,content);
		/*#{1IG63NL6J0PostCodes*/
		/*}#1IG63NL6J0PostCodes*/
		return {seg:JumpUninstall,result:(result),preSeg:"1IG63NL6J0",outlet:"1IG646O8P1"};
	};
	AbortSetup.jaxId="1IG63NL6J0"
	AbortSetup.url="AbortSetup@"+agentURL
	
	segs["CheckSetup"]=CheckSetup=async function(input){//:1IHB0N6CM0
		let result=input;
		if(input.result==="Finish"){
			return {seg:AskTest,result:(input),preSeg:"1IHB0N6CM0",outlet:"1IHB0QKJ70"};
		}
		return {seg:SetupFailed,result:(result),preSeg:"1IHB0N6CM0",outlet:"1IHB0QKJ71"};
	};
	CheckSetup.jaxId="1IHB0N6CM0"
	CheckSetup.url="CheckSetup@"+agentURL
	
	segs["SetupFailed"]=SetupFailed=async function(input){//:1IHB0T72F0
		let result=input;
		let role="assistant";
		let content="项目安装完毕";
		/*#{1IHB0T72F0PreCodes*/
		/*}#1IHB0T72F0PreCodes*/
		session.addChatText(role,content);
		/*#{1IHB0T72F0PostCodes*/
		/*}#1IHB0T72F0PostCodes*/
		return {seg:AskUninstall,result:(result),preSeg:"1IHB0T72F0",outlet:"1IHB0V0BB0"};
	};
	SetupFailed.jaxId="1IHB0T72F0"
	SetupFailed.url="SetupFailed@"+agentURL
	
	segs["AskTest"]=AskTest=async function(input){//:1IHB209QB0
		let prompt=("项目安装部署完毕，是否进行测试？")||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("测试"):("Test")))||"OK";
		let button2=((($ln==="CN")?("取消"):("Cancel")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:TestPrj,result:(result),preSeg:"1IHB209QB0",outlet:"1IHB209PL0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:false,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:TestPrj,result:(result),preSeg:"1IHB209QB0",outlet:"1IHB209PL0"};
		}
		result=("")||result;
		return {seg:GenReport,result:(result),preSeg:"1IHB209QB0",outlet:"1IHB209PL1"};
	
	};
	AskTest.jaxId="1IHB209QB0"
	AskTest.url="AskTest@"+agentURL
	
	segs["TestResult"]=TestResult=async function(input){//:1IHDDABOS0
		let result=input;
		if(input.result==="Abort"){
			return {seg:AskUninstall2,result:(input),preSeg:"1IHDDABOS0",outlet:"1IHDDJ1S60"};
		}
		return {seg:GenReport,result:(result),preSeg:"1IHDDABOS0",outlet:"1IHDDJ1S61"};
	};
	TestResult.jaxId="1IHDDABOS0"
	TestResult.url="TestResult@"+agentURL
	
	segs["TestFailed"]=TestFailed=async function(input){//:1IHDDC9SV0
		let result=input
		/*#{1IHDDC9SV0Code*/
		/*}#1IHDDC9SV0Code*/
		return {result:result};
	};
	TestFailed.jaxId="1IHDDC9SV0"
	TestFailed.url="TestFailed@"+agentURL
	
	segs["AskUninstall"]=AskUninstall=async function(input){//:1IJ0QT40H0
		let prompt=((($ln==="CN")?("安装配置未成功，是否移除项目?"):("Install / setup was not successful, do you want to remove the project?")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("Uninstall project"):("卸载项目")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("保留项目"):("Keep project")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Uninstall,result:(result),preSeg:"1IJ0QT40H0",outlet:"1IJ0QT4000"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:false,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Uninstall,result:(result),preSeg:"1IJ0QT40H0",outlet:"1IJ0QT4000"};
		}else if(item.code===1){
			return {seg:FailEnd,result:(result),preSeg:"1IJ0QT40H0",outlet:"1IJ0QT4001"};
		}
		return {result:result};
	};
	AskUninstall.jaxId="1IJ0QT40H0"
	AskUninstall.url="AskUninstall@"+agentURL
	
	segs["Uninstall"]=Uninstall=async function(input){//:1IJ0R34FO0
		let result;
		let sourcePath=pathLib.join(basePath,"");
		let arg=input;
		result= await session.pipeChat(sourcePath,arg,false);
		return {result:result};
	};
	Uninstall.jaxId="1IJ0R34FO0"
	Uninstall.url="Uninstall@"+agentURL
	
	segs["FailEnd"]=FailEnd=async function(input){//:1IJ0R3GNH0
		let result=input
		/*#{1IJ0R3GNH0Code*/
		/*}#1IJ0R3GNH0Code*/
		return {result:result};
	};
	FailEnd.jaxId="1IJ0R3GNH0"
	FailEnd.url="FailEnd@"+agentURL
	
	segs["JumpUninstall"]=JumpUninstall=async function(input){//:1IJ0R4SJ50
		let result=input;
		return {seg:AskUninstall,result:result,preSeg:"1IJ0R4SJ50",outlet:"1IJ0R5IGR3"};
	
	};
	JumpUninstall.jaxId="1IJ0R4SJ50"
	JumpUninstall.url="JumpUninstall@"+agentURL
	
	segs["AskUninstall2"]=AskUninstall2=async function(input){//:1IJ0R8JA10
		let prompt=("Please confirm")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Item 1",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Item 2",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Uninstall2,result:(result),preSeg:"1IJ0R8JA10",outlet:"1IJ0R8J9B0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:false,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Uninstall2,result:(result),preSeg:"1IJ0R8JA10",outlet:"1IJ0R8J9B0"};
		}else if(item.code===1){
			return {seg:TestFailed,result:(result),preSeg:"1IJ0R8JA10",outlet:"1IJ0R8J9B1"};
		}
		return {result:result};
	};
	AskUninstall2.jaxId="1IJ0R8JA10"
	AskUninstall2.url="AskUninstall2@"+agentURL
	
	segs["Uninstall2"]=Uninstall2=async function(input){//:1IJ0RA5FC0
		let result;
		let sourcePath=pathLib.join(basePath,"");
		let arg=input;
		result= await session.pipeChat(sourcePath,arg,false);
		return {result:result};
	};
	Uninstall2.jaxId="1IJ0RA5FC0"
	Uninstall2.url="Uninstall2@"+agentURL
	
	segs["DirResult"]=DirResult=async function(input){//:1IJ0SSL2O0
		let result=input;
		if(input.result!=="Finish"){
			return {seg:DirFailed,result:(input),preSeg:"1IJ0SSL2O0",outlet:"1IJ0SUV2C0"};
		}
		return {seg:SetupPrj,result:(result),preSeg:"1IJ0SSL2O0",outlet:"1IJ0SUV2C1"};
	};
	DirResult.jaxId="1IJ0SSL2O0"
	DirResult.url="DirResult@"+agentURL
	
	segs["DirFailed"]=DirFailed=async function(input){//:1IJ0T04Q20
		let result=input;
		return {seg:AskUninstall,result:result,preSeg:"1IJ0T04Q20",outlet:"1IJ0T0VDE0"};
	
	};
	DirFailed.jaxId="1IJ0T04Q20"
	DirFailed.url="DirFailed@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"PrjSetupPrj",
		url:agentURL,
		autoStart:true,
		jaxId:"1IG38I67R1",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{prjURL,dirPath}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IG38I67R1PreEntry*/
			/*}#1IG38I67R1PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IG38I67R1PostEntry*/
			/*}#1IG38I67R1PostEntry*/
			return result;
		},
		/*#{1IG38I67R1MoreAgentAttrs*/
		/*}#1IG38I67R1MoreAgentAttrs*/
	};
	/*#{1IG38I67R1PostAgent*/
	/*}#1IG38I67R1PostAgent*/
	return agent;
};
/*#{1IG38I67R1ExCodes*/
/*}#1IG38I67R1ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IG38I67R1PostDoc*/
/*}#1IG38I67R1PostDoc*/


export default PrjSetupPrj;
export{PrjSetupPrj};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IG38I67R1",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IG38I67R1",
//			"attrs": {
//				"PrjSetupPrj": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IG38I67R7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IG38I67R8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IG38I67R9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IG38I67R10",
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
//			"jaxId": "1IG38I67R2",
//			"attrs": {}
//		},
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IG38I67R3",
//			"attrs": {
//				"prjURL": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IG38ILRS0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "项目的GitHub地址"
//					}
//				},
//				"dirPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IGNGIIU40",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "当前项目工程所在的本地目录路径",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IG38I67R4",
//			"attrs": {
//				"project": {
//					"type": "auto",
//					"valText": "null"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IG38I67R5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IG38I67R6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IH71L8DF0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "65",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IH71LMKO0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG5FD2R20"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IG5FD2R20",
//					"attrs": {
//						"id": "InitPrj",
//						"viewName": "",
//						"label": "",
//						"x": "275",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG5FDRUH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG5FDRUH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG5FDRUA0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG38J1M10"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IG38J1M10",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "480",
//						"y": "190",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG392PPH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG392PPH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysInitWorkEnv.js",
//						"argument": "{}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IG392PPE0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHDMMD880"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1IG38NVAB0",
//					"attrs": {
//						"id": "AskStep",
//						"viewName": "",
//						"label": "",
//						"x": "230",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Deploy the project?",
//							"localize": {
//								"EN": "Deploy the project?",
//								"CN": "是否在本地部署项目？"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IG38NV9U0",
//									"attrs": {
//										"id": "Setup",
//										"desc": "输出节点。",
//										"text": "部署",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG392PPH14",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG392PPH15",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IG38V9R90"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IG38NV9U1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "取消",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG392PPH16",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG392PPH17",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IG63NL6J0"
//								}
//							]
//						},
//						"silent": "false",
//						"withChat": {
//							"valText": "true"
//						}
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IG38V9R90",
//					"attrs": {
//						"id": "SetupDir",
//						"viewName": "",
//						"label": "",
//						"x": "435",
//						"y": "370",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG392PPH28",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG392PPH29",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/PrjSetupPrjDir.js",
//						"argument": "{}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IG392PPF4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ0SSL2O0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IG396KMU0",
//					"attrs": {
//						"id": "SetupPrj",
//						"viewName": "",
//						"label": "",
//						"x": "280",
//						"y": "700",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG39IF172",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG39IF173",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/PrjDoSetupPrj.js",
//						"argument": "{}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IG39IF140",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHB0N6CM0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IG399DKK0",
//					"attrs": {
//						"id": "TestPrj",
//						"viewName": "",
//						"label": "",
//						"x": "935",
//						"y": "630",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG39IF182",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG39IF183",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/PrjTestPrj.js",
//						"argument": "{}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IG39IF142",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHDDABOS0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IG399QD10",
//					"attrs": {
//						"id": "GenReport",
//						"viewName": "",
//						"label": "",
//						"x": "1380",
//						"y": "690",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IG39IF184",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG39IF185",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG39IF143",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IG63NL6J0",
//					"attrs": {
//						"id": "AbortSetup",
//						"viewName": "",
//						"label": "",
//						"x": "435",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IG646O8V2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG646O8V3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "Project deployment has been cancelled.",
//							"localize": {
//								"EN": "Project deployment has been cancelled.",
//								"CN": "项目部署已取消."
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IG646O8P1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ0R4SJ50"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IHB0N6CM0",
//					"attrs": {
//						"id": "CheckSetup",
//						"viewName": "",
//						"label": "",
//						"x": "495",
//						"y": "700",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHB0QKJA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHB0QKJA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHB0QKJ71",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IHB0T72F0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHB0QKJ70",
//									"attrs": {
//										"id": "Ready",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHB0QKJA2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHB0QKJA3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result===\"Finish\""
//									},
//									"linkedSeg": "1IHB209QB0"
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
//					"jaxId": "1IHB0T72F0",
//					"attrs": {
//						"id": "SetupFailed",
//						"viewName": "",
//						"label": "",
//						"x": "715",
//						"y": "760",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHB0V0BE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHB0V0BE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "项目安装完毕",
//						"outlet": {
//							"jaxId": "1IHB0V0BB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ0QT40H0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1IHB209QB0",
//					"attrs": {
//						"id": "AskTest",
//						"viewName": "",
//						"label": "",
//						"x": "715",
//						"y": "645",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "项目安装部署完毕，是否进行测试？",
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHB209PL0",
//									"attrs": {
//										"id": "Test",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Test",
//											"localize": {
//												"EN": "Test",
//												"CN": "测试"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHB22DGN0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHB22DGN1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IG399DKK0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHB209PL1",
//									"attrs": {
//										"id": "Cancel",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Cancel",
//											"localize": {
//												"EN": "Cancel",
//												"CN": "取消"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHB22DGN2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHB22DGN3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHDMQEI50"
//								}
//							]
//						},
//						"silent": "false",
//						"withChat": {
//							"valText": "false"
//						}
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IHDDABOS0",
//					"attrs": {
//						"id": "TestResult",
//						"viewName": "",
//						"label": "",
//						"x": "1140",
//						"y": "630",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHDDJ1SB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHDDJ1SB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHDDJ1S61",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IG399QD10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHDDJ1S60",
//									"attrs": {
//										"id": "Issue",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHDDJ1SB2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHDDJ1SB3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result===\"Abort\""
//									},
//									"linkedSeg": "1IJ0R8JA10"
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
//					"jaxId": "1IHDDC9SV0",
//					"attrs": {
//						"id": "TestFailed",
//						"viewName": "",
//						"label": "",
//						"x": "1640",
//						"y": "590",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHDDJ1SB4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHDDJ1SB5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHDDJ1S62",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHDMMD880",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "605",
//						"y": "285",
//						"outlet": {
//							"jaxId": "1IHDMRUE90",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHDMMOHD0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHDMMOHD0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "260",
//						"y": "285",
//						"outlet": {
//							"jaxId": "1IHDMRUE91",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG38NVAB0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHDMP1900",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "815",
//						"y": "545",
//						"outlet": {
//							"jaxId": "1IHDMRUE92",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHDMP6KF0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHDMP6KF0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "310",
//						"y": "545",
//						"outlet": {
//							"jaxId": "1IHDMRUE93",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG396KMU0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IHDMQEI50",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "935",
//						"y": "690",
//						"outlet": {
//							"jaxId": "1IHDMRUE94",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG399QD10"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IJ0QT40H0",
//					"attrs": {
//						"id": "AskUninstall",
//						"viewName": "",
//						"label": "",
//						"x": "950",
//						"y": "845",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Install / setup was not successful, do you want to remove the project?",
//							"localize": {
//								"EN": "Install / setup was not successful, do you want to remove the project?",
//								"CN": "安装配置未成功，是否移除项目?"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJ0R5IGR0",
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
//									"jaxId": "1IJ0QT4000",
//									"attrs": {
//										"id": "Uninstall",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "卸载项目",
//											"localize": {
//												"EN": "卸载项目",
//												"CN": "Uninstall project"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0R5IH10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0R5IH11",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ0R34FO0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ0QT4001",
//									"attrs": {
//										"id": "Keep",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Keep project",
//											"localize": {
//												"EN": "Keep project",
//												"CN": "保留项目"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0R5IH12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0R5IH13",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ0R3GNH0"
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
//					"def": "aiBot",
//					"jaxId": "1IJ0R34FO0",
//					"attrs": {
//						"id": "Uninstall",
//						"viewName": "",
//						"label": "",
//						"x": "1205",
//						"y": "770",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJ0R5IH14",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0R5IH15",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ0R5IGR1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ0R3GNH0",
//					"attrs": {
//						"id": "FailEnd",
//						"viewName": "",
//						"label": "",
//						"x": "1205",
//						"y": "875",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJ0R5IH16",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0R5IH17",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0R5IGR2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IJ0R4SJ50",
//					"attrs": {
//						"id": "JumpUninstall",
//						"viewName": "",
//						"label": "",
//						"x": "650",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "AskUninstall",
//						"outlet": {
//							"jaxId": "1IJ0R5IGR3",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IJ0R8JA10",
//					"attrs": {
//						"id": "AskUninstall2",
//						"viewName": "",
//						"label": "",
//						"x": "1380",
//						"y": "560",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "Please confirm",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJ0RB7LD0",
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
//									"jaxId": "1IJ0R8J9B0",
//									"attrs": {
//										"id": "Uninstall",
//										"desc": "输出节点。",
//										"text": "Item 1",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0RB7LK0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0RB7LK1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ0RA5FC0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ0R8J9B1",
//									"attrs": {
//										"id": "Keep",
//										"desc": "输出节点。",
//										"text": "Item 2",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0RB7LK2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0RB7LK3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHDDC9SV0"
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
//					"def": "aiBot",
//					"jaxId": "1IJ0RA5FC0",
//					"attrs": {
//						"id": "Uninstall2",
//						"viewName": "",
//						"label": "",
//						"x": "1640",
//						"y": "485",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJ0RB7LK4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0RB7LK5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ0RB7LD1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJ0SSL2O0",
//					"attrs": {
//						"id": "DirResult",
//						"viewName": "",
//						"label": "",
//						"x": "650",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0SUV2H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0SUV2H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0SUV2C1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJ0T6IA80"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ0SUV2C0",
//									"attrs": {
//										"id": "Failed",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0SUV2H2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0SUV2H3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result!==\"Finish\""
//									},
//									"linkedSeg": "1IJ0T04Q20"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IJ0T04Q20",
//					"attrs": {
//						"id": "DirFailed",
//						"viewName": "",
//						"label": "",
//						"x": "855",
//						"y": "315",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "AskUninstall",
//						"outlet": {
//							"jaxId": "1IJ0T0VDE0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorT",
//					"jaxId": "1IJ0T6IA80",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "900",
//						"y": "450",
//						"outlet": {
//							"jaxId": "1IJ0T709G0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHDMP1900"
//						},
//						"dir": "T2B"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}