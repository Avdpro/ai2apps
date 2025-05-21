//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IHTBN3H00MoreImports*/
import {appCfg} from "../cfg/appCfg.js";
/*}#1IHTBN3H00MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1IHTBN3H00StartDoc*/
const xtermMeta={
	type:"app",
	name:"AgentTerminal",
	caption:"Agent Terminal",
	icon:appCfg.sharedAssets+"/terminal.svg",iconPad:12,
	appFrame:{
		main:pathLib.join(basePath,"../xterm.html"),
		group:"AgentTerminal",caption:(($ln==="CN")?("智能体终端"):("Agent Terminal")),
		openApp:true,
		width:640,height:380,
		icon:appCfg.sharedAssets+"/terminal.svg",iconPad:2,
		sizeable:false
	}
};
async function createXTerm(message){
	let app,appFrame,sessionId;
	sessionId=message.session||message.sessionId;
	app=VFACT.app;
	if(app.uiTerminal){
		app.uiTerminal.connectBash(sessionId);
	}else{
		appFrame=app.appFrame;
		if(app.openAppMeta){
			app.openAppMeta(xtermMeta,`session=${sessionId}`);
		}else{
			window.open(pathLib.join(basePath,"../xterm.html")+`?session=${sessionId}`);
		}
	}
};
async function connectAgentNode(port,entryURL,agentDef){
	let app,address,result;
	app=VFACT.app;
	if(app.uiInference){
		address=`localhost:${port}`;//TODO:Address
		result=await app.uiInference.connect(address,entryURL,agentDef);
		console.log("app.uiInference.connect result: "+result);
		return result;
	}
	return false;
};
/*}#1IHTBN3H00StartDoc*/
//----------------------------------------------------------------------------
let UxEntry=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ShowLogo,GreetingMenu,AskGitAddr,GitHubSetup,ShowTodo,AskPrjPath,SetupAgentNode;
	/*#{1IHTBN3H00LocalVals*/
	session.getRoleDef=function(role){
		if(role==="assistant"){
			return {icon:appCfg.sharedAssets+"/ablogo.svg"};
		}
	};
	/*}#1IHTBN3H00LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IHTBN3H00ParseArgs*/
		/*}#1IHTBN3H00ParseArgs*/
	}
	
	/*#{1IHTBN3H00PreContext*/
	/*}#1IHTBN3H00PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IHTBN3H00PostContext*/
	const app=VFACT.app;
	if(!session.WSCall_CreateXTerm){
		session.WSCall_CreateXTerm=createXTerm;
	}
	if(!session.WSCall_AddNote){
		session.WSCall_AddNote=function(message){
			if(app.tbxNotes){
				app.tbxNotes.addNote(message.note);
			}
		};
	}
	if(!session.WSCall_RegEnvProjectInfo){
		session.WSCall_RegEnvProjectInfo=function(message){
			if(app.tbxNotes){
				app.tbxNotes.regEnv(message.env,message.project);
			}
		};
	}
	if(!session.WSCall_ConnectAgentDebug){
		session.WSCall_ConnectAgentDebug=async function(message){
			await connectAgentNode(message.port,message.entryURL,message.entryAgent);
		};
	}
	/*}#1IHTBN3H00PostContext*/
	let $agent,agent,segs={};
	segs["ShowLogo"]=ShowLogo=async function(input){//:1IHTBNCK20
		let result=input;
		let role="assistant";
		let content=" ";
		/*#{1IHTBNCK20PreCodes*/
		/*}#1IHTBNCK20PreCodes*/
		let vo={image:"/~/tabos/shared/assets/ablogo.svg"};
		/*#{1IHTBNCK20Options*/
		vo.button=false;
		vo.icon=false;
		/*}#1IHTBNCK20Options*/
		session.addChatText(role,content,vo);
		/*#{1IHTBNCK20PostCodes*/
		session.debugLog("Greeting!");
		result="Done";
		/*}#1IHTBNCK20PostCodes*/
		return {seg:GreetingMenu,result:(result),preSeg:"1IHTBNCK20",outlet:"1IHTBQH3H0"};
	};
	ShowLogo.jaxId="1IHTBNCK20"
	ShowLogo.url="ShowLogo@"+agentURL
	
	segs["GreetingMenu"]=GreetingMenu=async function(input){//:1IHTCTUTI0
		let prompt=((($ln==="CN")?("你想创建什么样的项目工程？选择一个选项或者输入你对新项目需求描述。"):("What kind of project do you want to create? Choose an option or describe your new project requirements.")))||input;
		let countdown=false;
		let placeholder=((($ln==="CN")?("描述你的项目需求"):("Describe your project requirements")))||null;
		let withChat=true;
		let silent=false;
		let items=[
			{icon:"/~/tabos/shared/assets/cloudact.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("从GitHub项目创建项目工程"):("Create project from GitHub")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Setup Agent Node",code:1},
			{icon:"/~/tabos/shared/assets/agent.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("创建AI智能体/聊天机器人"):("Create AI agent / chat bot")),code:2},
			{icon:"/~/tabos/shared/assets/web.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("网站页面"):("Website pages")),code:3},
			{icon:"/~/tabos/shared/assets/app.svg"||"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("应用程序"):("Application")),code:4},
		];
		let result="";
		let item=null;
		
		if(silent){
			result=input;
			return {seg:AskGitAddr,result:(result),preSeg:"1IHTCTUTI0",outlet:"1IHTCTUT00"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {seg:ShowTodo,result:(result),preSeg:"1IHTCTUTI0",outlet:"1IHTD7M4U0"};
		}else if(item.code===0){
			result=(input);
			return {seg:AskGitAddr,result:(result),preSeg:"1IHTCTUTI0",outlet:"1IHTCTUT00"};
		}else if(item.code===1){
			return {seg:AskPrjPath,result:(result),preSeg:"1IHTCTUTI0",outlet:"1IJ46HTS30"};
		}else if(item.code===2){
			return {seg:ShowTodo,result:(result),preSeg:"1IHTCTUTI0",outlet:"1IHTCTUT01"};
		}else if(item.code===3){
			return {seg:ShowTodo,result:(result),preSeg:"1IHTCTUTI0",outlet:"1IHTCTUT02"};
		}else if(item.code===4){
			return {seg:ShowTodo,result:(result),preSeg:"1IHTCTUTI0",outlet:"1IHTDPR1B0"};
		}
		return {seg:ShowTodo,result:(result),preSeg:"1IHTCTUTI0",outlet:"1IHTD7M4U0"};
	};
	GreetingMenu.jaxId="1IHTCTUTI0"
	GreetingMenu.url="GreetingMenu@"+agentURL
	
	segs["AskGitAddr"]=AskGitAddr=async function(input){//:1IHTE365K0
		let tip=((($ln==="CN")?("请输入GitHub项目的地址，例如：github.com/Avdpro/ai2apps"):("Please enter the GitHub project address, for example: github.com/Avdpro/ai2apps")));
		let tipRole=("assistant");
		let placeholder=("GitHub project address");
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
		return {seg:GitHubSetup,result:(result),preSeg:"1IHTE365K0",outlet:"1IHTE559S0"};
	};
	AskGitAddr.jaxId="1IHTE365K0"
	AskGitAddr.url="AskGitAddr@"+agentURL
	
	segs["GitHubSetup"]=GitHubSetup=async function(input){//:1IHTE7JB40
		let result,args={};
		args['nodeName']="AgentBuilder";
		args['callAgent']="PrjSetupPrj.js";
		args['callArg']={prjURL:input};
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	GitHubSetup.jaxId="1IHTE7JB40"
	GitHubSetup.url="GitHubSetup@"+agentURL
	
	segs["ShowTodo"]=ShowTodo=async function(input){//:1II12JPBJ0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=(($ln==="CN")?("抱歉，当前演示版本只支持通过GitHub创建工程"):("Sorry, the current demo version only supports creating projects through GitHub"));
		session.addChatText(role,content,opts);
		return {seg:GreetingMenu,result:(result),preSeg:"1II12JPBJ0",outlet:"1II12MRH70"};
	};
	ShowTodo.jaxId="1II12JPBJ0"
	ShowTodo.url="ShowTodo@"+agentURL
	
	segs["AskPrjPath"]=AskPrjPath=async function(input){//:1IJ46ENDS0
		let tip=("请输入要安装的AgentNode项目路径");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let askUpward=(false);
		let text=("/Users/avdpropang/sdk/cchome/home/agents/FishSpeech");
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
		return {seg:SetupAgentNode,result:(result),preSeg:"1IJ46ENDS0",outlet:"1IJ46HTS40"};
	};
	AskPrjPath.jaxId="1IJ46ENDS0"
	AskPrjPath.url="AskPrjPath@"+agentURL
	
	segs["SetupAgentNode"]=SetupAgentNode=async function(input){//:1IJ46G28U0
		let result,args={};
		args['nodeName']="AgentBuilder";
		args['callAgent']="PrjSetupBySteps.js";
		args['callArg']={prjPath:input};
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	SetupAgentNode.jaxId="1IJ46G28U0"
	SetupAgentNode.url="SetupAgentNode@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"UxEntry",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHTBN3H00",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IHTBN3H00PreEntry*/
			/*}#1IHTBN3H00PreEntry*/
			result={seg:ShowLogo,"input":input};
			/*#{1IHTBN3H00PostEntry*/
			/*}#1IHTBN3H00PostEntry*/
			return result;
		},
		/*#{1IHTBN3H00MoreAgentAttrs*/
		/*}#1IHTBN3H00MoreAgentAttrs*/
	};
	/*#{1IHTBN3H00PostAgent*/
	/*}#1IHTBN3H00PostAgent*/
	return agent;
};
/*#{1IHTBN3H00ExCodes*/
/*}#1IHTBN3H00ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IHTBN3H00PostDoc*/
/*}#1IHTBN3H00PostDoc*/


export default UxEntry;
export{UxEntry};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHTBN3H00",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHTBN3H01",
//			"attrs": {
//				"UxEntry": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHTBN3H10",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHTBN3H11",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHTBN3H12",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHTBN3H13",
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
//			"jaxId": "1IHTBN3H02",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHTBN3H03",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IHTBN3H04",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IHTBN3H05",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHTBN3H06",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "image",
//					"jaxId": "1IHTBNCK20",
//					"attrs": {
//						"id": "ShowLogo",
//						"viewName": "",
//						"label": "",
//						"x": "155",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHTBQH3I0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHTBQH3I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"text": " ",
//						"image": "#\"/~/tabos/shared/assets/ablogo.svg\"",
//						"role": "Assistant",
//						"sizeLimit": "",
//						"format": "JEPG",
//						"outlet": {
//							"jaxId": "1IHTBQH3H0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHTCTUTI0"
//						}
//					},
//					"icon": "hudimg.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IHTCTUTI0",
//					"attrs": {
//						"id": "GreetingMenu",
//						"viewName": "",
//						"label": "",
//						"x": "380",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "What kind of project do you want to create? Choose an option or describe your new project requirements.",
//							"localize": {
//								"EN": "What kind of project do you want to create? Choose an option or describe your new project requirements.",
//								"CN": "你想创建什么样的项目工程？选择一个选项或者输入你对新项目需求描述。"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1IHTD7M4U0",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1II12JPBJ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHTCTUT00",
//									"attrs": {
//										"id": "GitHub",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Create project from GitHub",
//											"localize": {
//												"EN": "Create project from GitHub",
//												"CN": "从GitHub项目创建项目工程"
//											},
//											"localizable": true
//										},
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHTD7M510",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHTD7M511",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/cloudact.svg"
//									},
//									"linkedSeg": "1IHTE365K0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ46HTS30",
//									"attrs": {
//										"id": "Setup",
//										"desc": "输出节点。",
//										"text": "Setup Agent Node",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ46HTS50",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ46HTS51",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ46ENDS0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHTCTUT01",
//									"attrs": {
//										"id": "ChatBot",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Create AI agent / chat bot",
//											"localize": {
//												"EN": "Create AI agent / chat bot",
//												"CN": "创建AI智能体/聊天机器人"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHTD7M512",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHTD7M513",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/agent.svg"
//									},
//									"linkedSeg": "1II12JPBJ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHTCTUT02",
//									"attrs": {
//										"id": "WebSite",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Website pages",
//											"localize": {
//												"EN": "Website pages",
//												"CN": "网站页面"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHTD7M514",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHTD7M515",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/web.svg"
//									},
//									"linkedSeg": "1II12JPBJ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHTDPR1B0",
//									"attrs": {
//										"id": "App",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Application",
//											"localize": {
//												"EN": "Application",
//												"CN": "应用程序"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHTDQHOD0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHTDQHOD1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/tabos/shared/assets/app.svg"
//									},
//									"linkedSeg": "1II12JPBJ0"
//								}
//							]
//						},
//						"silent": "false",
//						"silentOutlet": "GitHub",
//						"countdown": "None",
//						"placeholder": {
//							"type": "string",
//							"valText": "Describe your project requirements",
//							"localize": {
//								"EN": "Describe your project requirements",
//								"CN": "描述你的项目需求"
//							},
//							"localizable": true
//						}
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IHTE365K0",
//					"attrs": {
//						"id": "AskGitAddr",
//						"viewName": "",
//						"label": "",
//						"x": "665",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHTE55A10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHTE55A11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": {
//							"type": "string",
//							"valText": "Please enter the GitHub project address, for example: github.com/Avdpro/ai2apps",
//							"localize": {
//								"EN": "Please enter the GitHub project address, for example: github.com/Avdpro/ai2apps",
//								"CN": "请输入GitHub项目的地址，例如：github.com/Avdpro/ai2apps"
//							},
//							"localizable": true
//						},
//						"tipRole": "Assistant",
//						"placeholder": "GitHub project address",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1IHTE559S0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHTE7JB40"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1IHTE7JB40",
//					"attrs": {
//						"id": "GitHubSetup",
//						"viewName": "",
//						"label": "",
//						"x": "895",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHTE90D20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHTE90D21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AgentBuilder",
//						"callAgent": "PrjSetupPrj.js",
//						"callArg": "#{prjURL:input}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IHTE90CT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1II12JPBJ0",
//					"attrs": {
//						"id": "ShowTodo",
//						"viewName": "",
//						"label": "",
//						"x": "665",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II12MRHA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II12MRHA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "Sorry, the current demo version only supports creating projects through GitHub",
//							"localize": {
//								"EN": "Sorry, the current demo version only supports creating projects through GitHub",
//								"CN": "抱歉，当前演示版本只支持通过GitHub创建工程"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1II12MRH70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II12MGRF0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1II12MGRF0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "805",
//						"y": "520",
//						"outlet": {
//							"jaxId": "1II12MRHB0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II12MLC60"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1II12MLC60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "410",
//						"y": "520",
//						"outlet": {
//							"jaxId": "1II12MRHB1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHTCTUTI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IJ46ENDS0",
//					"attrs": {
//						"id": "AskPrjPath",
//						"viewName": "",
//						"label": "",
//						"x": "665",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ46HTS52",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ46HTS53",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "请输入要安装的AgentNode项目路径",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "/Users/avdpropang/sdk/cchome/home/agents/FishSpeech",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1IJ46HTS40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ46G28U0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1IJ46G28U0",
//					"attrs": {
//						"id": "SetupAgentNode",
//						"viewName": "",
//						"label": "",
//						"x": "890",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ46HTS54",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ46HTS55",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AgentBuilder",
//						"callAgent": "PrjSetupBySteps.js",
//						"callArg": "#{prjPath:input}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IJ46HTS41",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "cloudact.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}