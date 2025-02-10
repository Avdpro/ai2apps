//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IJ0920GO0MoreImports*/
/*}#1IJ0920GO0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"dirPath":{
			"name":"dirPath","type":"string",
			"defaultValue":"",
			"desc":"项目所在目录的完全路径",
		},
		"bashCommands":{
			"name":"bashCommands","type":"auto",
			"required":false,
			"defaultValue":"",
			"desc":"项目安装时执行的所有bash命令的数组",
		}
	},
	/*#{1IJ0920GO0ArgsView*/
	/*}#1IJ0920GO0ArgsView*/
};

/*#{1IJ0920GO0StartDoc*/
/*}#1IJ0920GO0StartDoc*/
//----------------------------------------------------------------------------
let PrjUninstall=async function(session){
	let dirPath,bashCommands;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let InitEnv,HasCmds,ReadCmds,CheckConda,AskConda,CheckBrew,AllCondas,RemoveConda,AskBrew,AllBrews,RemoveBrew,CheckDocker,AllDockers,AskDocker,RemoveDocker,AskDir,RemoveDir,FinKeepDir,FinDelDir;
	/*#{1IJ0920GO0LocalVals*/
	/*}#1IJ0920GO0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			dirPath=input.dirPath;
			bashCommands=input.bashCommands;
		}else{
			dirPath=undefined;
			bashCommands=undefined;
		}
		/*#{1IJ0920GO0ParseArgs*/
		/*}#1IJ0920GO0ParseArgs*/
	}
	
	/*#{1IJ0920GO0PreContext*/
	/*}#1IJ0920GO0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IJ0920GO0PostContext*/
	/*}#1IJ0920GO0PostContext*/
	let agent,segs={};
	segs["InitEnv"]=InitEnv=async function(input){//:1IJ092A450
		let result=input
		/*#{1IJ092A450Code*/
		/*}#1IJ092A450Code*/
		return {seg:HasCmds,result:(result),preSeg:"1IJ092A450",outlet:"1IJ0BC3530"};
	};
	InitEnv.jaxId="1IJ092A450"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["HasCmds"]=HasCmds=async function(input){//:1IJ096KP00
		let result=input;
		if(bashCommands && bashCommands.length>0){
			return {seg:ReadCmds,result:(input),preSeg:"1IJ096KP00",outlet:"1IJ0BC3540"};
		}
		return {seg:CheckConda,result:(result),preSeg:"1IJ096KP00",outlet:"1IJ0BC3541"};
	};
	HasCmds.jaxId="1IJ096KP00"
	HasCmds.url="HasCmds@"+agentURL
	
	segs["ReadCmds"]=ReadCmds=async function(input){//:1IJ0988H30
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-3.5-turbo",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=ReadCmds.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		result=await session.callSegLLM("ReadCmds@"+agentURL,opts,messages,true);
		return {seg:CheckConda,result:(result),preSeg:"1IJ0988H30",outlet:"1IJ0BC3542"};
	};
	ReadCmds.jaxId="1IJ0988H30"
	ReadCmds.url="ReadCmds@"+agentURL
	
	segs["CheckConda"]=CheckConda=async function(input){//:1IJ099QMU0
		let result=input;
		if(input==="Conda"){
			return {seg:AllCondas,result:(input),preSeg:"1IJ099QMU0",outlet:"1IJ0BC3543"};
		}
		return {seg:CheckBrew,result:(result),preSeg:"1IJ099QMU0",outlet:"1IJ0BC3544"};
	};
	CheckConda.jaxId="1IJ099QMU0"
	CheckConda.url="CheckConda@"+agentURL
	
	segs["AskConda"]=AskConda=async function(input){//:1IJ09BA8V0
		let prompt=("Please confirm")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Remove new conda env(s)",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Keep new conda env(s)",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:RemoveConda,result:(result),preSeg:"1IJ09BA8V0",outlet:"1IJ09BA8D0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:false,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:RemoveConda,result:(result),preSeg:"1IJ09BA8V0",outlet:"1IJ09BA8D0"};
		}else if(item.code===1){
			return {result:result};
		}
		return {result:result};
	};
	AskConda.jaxId="1IJ09BA8V0"
	AskConda.url="AskConda@"+agentURL
	
	segs["CheckBrew"]=CheckBrew=async function(input){//:1IJ09DFFL0
		let result=input;
		if(input==="Brew"){
			return {seg:AllBrews,result:(input),preSeg:"1IJ09DFFL0",outlet:"1IJ0BC3551"};
		}
		return {seg:CheckDocker,result:(result),preSeg:"1IJ09DFFL0",outlet:"1IJ0BC3552"};
	};
	CheckBrew.jaxId="1IJ09DFFL0"
	CheckBrew.url="CheckBrew@"+agentURL
	
	segs["AllCondas"]=AllCondas=async function(input){//:1IJ09FBV90
		let result=input;
		let list=input;
		let i,n,item;
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			await session.runAISeg(agent,AskConda,item,"1IJ09FBV90","1IJ0BC3553")
		}
		return {seg:CheckBrew,result:(result),preSeg:"1IJ09FBV90",outlet:"1IJ0BC3554"};
	};
	AllCondas.jaxId="1IJ09FBV90"
	AllCondas.url="AllCondas@"+agentURL
	
	segs["RemoveConda"]=RemoveConda=async function(input){//:1IJ09H40N0
		let result=input
		/*#{1IJ09H40N0Code*/
		/*}#1IJ09H40N0Code*/
		return {result:result};
	};
	RemoveConda.jaxId="1IJ09H40N0"
	RemoveConda.url="RemoveConda@"+agentURL
	
	segs["AskBrew"]=AskBrew=async function(input){//:1IJ09I5TP0
		let prompt=("Please confirm")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Remove brew package",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Keep brew package",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:RemoveBrew,result:(result),preSeg:"1IJ09I5TP0",outlet:"1IJ09I5T80"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:false,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:RemoveBrew,result:(result),preSeg:"1IJ09I5TP0",outlet:"1IJ09I5T80"};
		}else if(item.code===1){
			return {result:result};
		}
		return {result:result};
	};
	AskBrew.jaxId="1IJ09I5TP0"
	AskBrew.url="AskBrew@"+agentURL
	
	segs["AllBrews"]=AllBrews=async function(input){//:1IJ09II0F0
		let result=input;
		let list=input;
		let i,n,item;
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			await session.runAISeg(agent,AskBrew,item,"1IJ09II0F0","1IJ0BC3557")
		}
		return {seg:CheckDocker,result:(result),preSeg:"1IJ09II0F0",outlet:"1IJ0BC3558"};
	};
	AllBrews.jaxId="1IJ09II0F0"
	AllBrews.url="AllBrews@"+agentURL
	
	segs["RemoveBrew"]=RemoveBrew=async function(input){//:1IJ09K9TE0
		let result=input
		/*#{1IJ09K9TE0Code*/
		/*}#1IJ09K9TE0Code*/
		return {result:result};
	};
	RemoveBrew.jaxId="1IJ09K9TE0"
	RemoveBrew.url="RemoveBrew@"+agentURL
	
	segs["CheckDocker"]=CheckDocker=async function(input){//:1IJ09NFJE0
		let result=input;
		if(input==="Docker"){
			return {seg:AllDockers,result:(input),preSeg:"1IJ09NFJE0",outlet:"1IJ0BC35510"};
		}
		return {seg:AskDir,result:(result),preSeg:"1IJ09NFJE0",outlet:"1IJ0BC35511"};
	};
	CheckDocker.jaxId="1IJ09NFJE0"
	CheckDocker.url="CheckDocker@"+agentURL
	
	segs["AllDockers"]=AllDockers=async function(input){//:1IJ09OK5C0
		let result=input;
		let list=input;
		let i,n,item;
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			await session.runAISeg(agent,AskDocker,item,"1IJ09OK5C0","1IJ0BC35512")
		}
		return {seg:AskDir,result:(result),preSeg:"1IJ09OK5C0",outlet:"1IJ0BC35513"};
	};
	AllDockers.jaxId="1IJ09OK5C0"
	AllDockers.url="AllDockers@"+agentURL
	
	segs["AskDocker"]=AskDocker=async function(input){//:1IJ09P9O10
		let prompt=("Please confirm")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Remove docker image",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Keep docker image",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:RemoveDocker,result:(result),preSeg:"1IJ09P9O10",outlet:"1IJ09P9NE0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:false,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:RemoveDocker,result:(result),preSeg:"1IJ09P9O10",outlet:"1IJ09P9NE0"};
		}else if(item.code===1){
			return {result:result};
		}
		return {result:result};
	};
	AskDocker.jaxId="1IJ09P9O10"
	AskDocker.url="AskDocker@"+agentURL
	
	segs["RemoveDocker"]=RemoveDocker=async function(input){//:1IJ09QHM10
		let result=input
		/*#{1IJ09QHM10Code*/
		/*}#1IJ09QHM10Code*/
		return {result:result};
	};
	RemoveDocker.jaxId="1IJ09QHM10"
	RemoveDocker.url="RemoveDocker@"+agentURL
	
	segs["AskDir"]=AskDir=async function(input){//:1IJ09TUQQ0
		let prompt=("Please confirm")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Remove project dir and it's contents",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Keep project dir contents",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:RemoveDir,result:(result),preSeg:"1IJ09TUQQ0",outlet:"1IJ09TUQ70"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:false,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:RemoveDir,result:(result),preSeg:"1IJ09TUQQ0",outlet:"1IJ09TUQ70"};
		}else if(item.code===1){
			return {seg:FinKeepDir,result:(result),preSeg:"1IJ09TUQQ0",outlet:"1IJ09TUQ71"};
		}
		return {result:result};
	};
	AskDir.jaxId="1IJ09TUQQ0"
	AskDir.url="AskDir@"+agentURL
	
	segs["RemoveDir"]=RemoveDir=async function(input){//:1IJ0A00V60
		let result=input
		/*#{1IJ0A00V60Code*/
		/*}#1IJ0A00V60Code*/
		return {seg:FinDelDir,result:(result),preSeg:"1IJ0A00V60",outlet:"1IJ0BC35517"};
	};
	RemoveDir.jaxId="1IJ0A00V60"
	RemoveDir.url="RemoveDir@"+agentURL
	
	segs["FinKeepDir"]=FinKeepDir=async function(input){//:1IJ0A0D8E0
		let result=input
		/*#{1IJ0A0D8E0Code*/
		/*}#1IJ0A0D8E0Code*/
		return {result:result};
	};
	FinKeepDir.jaxId="1IJ0A0D8E0"
	FinKeepDir.url="FinKeepDir@"+agentURL
	
	segs["FinDelDir"]=FinDelDir=async function(input){//:1IJ0A15E80
		let result=input
		/*#{1IJ0A15E80Code*/
		/*}#1IJ0A15E80Code*/
		return {result:result};
	};
	FinDelDir.jaxId="1IJ0A15E80"
	FinDelDir.url="FinDelDir@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"PrjUninstall",
		url:agentURL,
		autoStart:true,
		jaxId:"1IJ0920GO0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{dirPath,bashCommands}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IJ0920GO0PreEntry*/
			/*}#1IJ0920GO0PreEntry*/
			result={seg:InitEnv,"input":input};
			/*#{1IJ0920GO0PostEntry*/
			/*}#1IJ0920GO0PostEntry*/
			return result;
		},
		/*#{1IJ0920GO0MoreAgentAttrs*/
		/*}#1IJ0920GO0MoreAgentAttrs*/
	};
	/*#{1IJ0920GO0PostAgent*/
	/*}#1IJ0920GO0PostAgent*/
	return agent;
};
/*#{1IJ0920GO0ExCodes*/
/*}#1IJ0920GO0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IJ0920GO0PostDoc*/
/*}#1IJ0920GO0PostDoc*/


export default PrjUninstall;
export{PrjUninstall};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IJ0920GO0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IJ0920GO1",
//			"attrs": {
//				"PrjUninstall": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IJ0920GO7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IJ0920GP0",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IJ0920GP1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IJ0920GP2",
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
//			"jaxId": "1IJ0920GO2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IJ0920GO3",
//			"attrs": {
//				"dirPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ0BC3580",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "项目所在目录的完全路径"
//					}
//				},
//				"bashCommands": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ0BC3581",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "项目安装时执行的所有bash命令的数组",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IJ0920GO4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IJ0920GO5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IJ0920GO6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ092A450",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "100",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC3582",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC3583",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC3530",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ096KP00"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJ096KP00",
//					"attrs": {
//						"id": "HasCmds",
//						"viewName": "",
//						"label": "",
//						"x": "300",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC3584",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC3585",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC3541",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJ099QMU0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ0BC3540",
//									"attrs": {
//										"id": "Bash",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC3586",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC3587",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#bashCommands && bashCommands.length>0"
//									},
//									"linkedSeg": "1IJ0988H30"
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
//					"jaxId": "1IJ0988H30",
//					"attrs": {
//						"id": "ReadCmds",
//						"viewName": "",
//						"label": "",
//						"x": "525",
//						"y": "195",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC3588",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC3589",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "GPT-3.5",
//						"system": "You are a smart assistant.",
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
//							"jaxId": "1IJ0BC3542",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ099QMU0"
//						},
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
//						"responseFormat": "text",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJ099QMU0",
//					"attrs": {
//						"id": "CheckConda",
//						"viewName": "",
//						"label": "",
//						"x": "750",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC35810",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC35811",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC3544",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJ09GBME0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ0BC3543",
//									"attrs": {
//										"id": "Conda",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC35812",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC35813",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1IJ09FBV90"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IJ09BA8V0",
//					"attrs": {
//						"id": "AskConda",
//						"viewName": "",
//						"label": "",
//						"x": "1220",
//						"y": "130",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "Please confirm",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJ0BC3550",
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
//									"jaxId": "1IJ09BA8D0",
//									"attrs": {
//										"id": "Remove",
//										"desc": "输出节点。",
//										"text": "Remove new conda env(s)",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC35814",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC35815",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ09H40N0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ09BA8D1",
//									"attrs": {
//										"id": "Keep",
//										"desc": "输出节点。",
//										"text": "Keep new conda env(s)",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC35816",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC35817",
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
//					"def": "brunch",
//					"jaxId": "1IJ09DFFL0",
//					"attrs": {
//						"id": "CheckBrew",
//						"viewName": "",
//						"label": "",
//						"x": "1220",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC35818",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC35819",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC3552",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJ09MSAH0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ0BC3551",
//									"attrs": {
//										"id": "Brew",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC35820",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC35821",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1IJ09II0F0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1IJ09FBV90",
//					"attrs": {
//						"id": "AllCondas",
//						"viewName": "",
//						"label": "",
//						"x": "995",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC35822",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC35823",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1IJ0BC3553",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ09BA8V0"
//						},
//						"catchlet": {
//							"jaxId": "1IJ0BC3554",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ09DFFL0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IJ09GBME0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1065",
//						"y": "270",
//						"outlet": {
//							"jaxId": "1IJ0BC35824",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ09DFFL0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ09H40N0",
//					"attrs": {
//						"id": "RemoveConda",
//						"viewName": "",
//						"label": "",
//						"x": "1475",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC35825",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC3590",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC3555",
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
//					"def": "askMenu",
//					"jaxId": "1IJ09I5TP0",
//					"attrs": {
//						"id": "AskBrew",
//						"viewName": "",
//						"label": "",
//						"x": "1695",
//						"y": "130",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "Please confirm",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJ0BC3556",
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
//									"jaxId": "1IJ09I5T80",
//									"attrs": {
//										"id": "Remove",
//										"desc": "输出节点。",
//										"text": "Remove brew package",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC3591",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC3592",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ09K9TE0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ09I5T81",
//									"attrs": {
//										"id": "Keep",
//										"desc": "输出节点。",
//										"text": "Keep brew package",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC3593",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC3594",
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
//					"def": "loopArray",
//					"jaxId": "1IJ09II0F0",
//					"attrs": {
//						"id": "AllBrews",
//						"viewName": "",
//						"label": "",
//						"x": "1470",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC3595",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC3596",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1IJ0BC3557",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ09I5TP0"
//						},
//						"catchlet": {
//							"jaxId": "1IJ0BC3558",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ09NFJE0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ09K9TE0",
//					"attrs": {
//						"id": "RemoveBrew",
//						"viewName": "",
//						"label": "",
//						"x": "1960",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC3597",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC3598",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC3559",
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
//					"def": "connectorL",
//					"jaxId": "1IJ09MSAH0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1585",
//						"y": "255",
//						"outlet": {
//							"jaxId": "1IJ0BC3599",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ09NFJE0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJ09NFJE0",
//					"attrs": {
//						"id": "CheckDocker",
//						"viewName": "",
//						"label": "",
//						"x": "1705",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC35910",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC35911",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC35511",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJ09RC3F0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ0BC35510",
//									"attrs": {
//										"id": "Docker",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC35912",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC35913",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1IJ09OK5C0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1IJ09OK5C0",
//					"attrs": {
//						"id": "AllDockers",
//						"viewName": "",
//						"label": "",
//						"x": "1960",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC35914",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC35915",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1IJ0BC35512",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ09P9O10"
//						},
//						"catchlet": {
//							"jaxId": "1IJ0BC35513",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ09RC3F0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IJ09P9O10",
//					"attrs": {
//						"id": "AskDocker",
//						"viewName": "",
//						"label": "",
//						"x": "2225",
//						"y": "130",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "Please confirm",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJ0BC35514",
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
//									"jaxId": "1IJ09P9NE0",
//									"attrs": {
//										"id": "Remove",
//										"desc": "输出节点。",
//										"text": "Remove docker image",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC35916",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC35917",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ09QHM10"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ09P9NE1",
//									"attrs": {
//										"id": "Keep",
//										"desc": "输出节点。",
//										"text": "Keep docker image",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC35918",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC35919",
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
//					"def": "code",
//					"jaxId": "1IJ09QHM10",
//					"attrs": {
//						"id": "RemoveDocker",
//						"viewName": "",
//						"label": "",
//						"x": "2485",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC35920",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC35921",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC35515",
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
//					"def": "connectorL",
//					"jaxId": "1IJ09RC3F0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2190",
//						"y": "255",
//						"outlet": {
//							"jaxId": "1IJ0BC35922",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ09S36E0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IJ09S36E0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2295",
//						"y": "240",
//						"outlet": {
//							"jaxId": "1IJ0BC35923",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ09TUQQ0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IJ09TUQQ0",
//					"attrs": {
//						"id": "AskDir",
//						"viewName": "",
//						"label": "",
//						"x": "2450",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "Please confirm",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJ0BC35516",
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
//									"jaxId": "1IJ09TUQ70",
//									"attrs": {
//										"id": "Remove",
//										"desc": "输出节点。",
//										"text": "Remove project dir and it's contents",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC35924",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC35925",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ0A00V60"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ09TUQ71",
//									"attrs": {
//										"id": "Keep",
//										"desc": "输出节点。",
//										"text": "Keep project dir contents",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0BC35926",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0BC35927",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ0A0D8E0"
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
//					"def": "code",
//					"jaxId": "1IJ0A00V60",
//					"attrs": {
//						"id": "RemoveDir",
//						"viewName": "",
//						"label": "",
//						"x": "2665",
//						"y": "150",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC35928",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC35929",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC35517",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ0A15E80"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ0A0D8E0",
//					"attrs": {
//						"id": "FinKeepDir",
//						"viewName": "",
//						"label": "",
//						"x": "2665",
//						"y": "295",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC35930",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC35931",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC35518",
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
//					"def": "code",
//					"jaxId": "1IJ0A15E80",
//					"attrs": {
//						"id": "FinDelDir",
//						"viewName": "",
//						"label": "",
//						"x": "2905",
//						"y": "150",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ0BC35932",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0BC35933",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0BC35519",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}