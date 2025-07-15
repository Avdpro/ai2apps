//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IK3H9P1H0MoreImports*/
import {tabNT} from "/@tabos";
/*}#1IK3H9P1H0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"appStub":{
			"name":"appStub","type":"auto",
			"defaultValue":"",
			"desc":"App/Tool的安装描述对象",
		}
	},
	/*#{1IK3H9P1H0ArgsView*/
	/*}#1IK3H9P1H0ArgsView*/
};

/*#{1IK3H9P1H0StartDoc*/
/*}#1IK3H9P1H0StartDoc*/
//----------------------------------------------------------------------------
let SysInstallApp=async function(session){
	let appStub;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,CreateTTY,TipInstallPkg,InstallPkg,CheckInstall,CheckAgent,CheckEnv,ConfirmFin,ConfirmFailed,Finish,Failed,ConfirmError,Error,AskNoEnv,Abort;
	let tty=null;
	
	/*#{1IK3H9P1H0LocalVals*/
	/*}#1IK3H9P1H0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			appStub=input.appStub;
		}else{
			appStub=undefined;
		}
		/*#{1IK3H9P1H0ParseArgs*/
		/*}#1IK3H9P1H0ParseArgs*/
	}
	
	/*#{1IK3H9P1H0PreContext*/
	/*}#1IK3H9P1H0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IK3H9P1H0PostContext*/
	/*}#1IK3H9P1H0PostContext*/
	let $agent,agent,segs={};
	segs["Start"]=Start=async function(input){//:1IK3H9U510
		let result=input;
		/*#{1IK3H9U510Code*/
		false
		/*}#1IK3H9U510Code*/
		return {seg:CreateTTY,result:(result),preSeg:"1IK3H9U510",outlet:"1IK3HA6AU0",catchSeg:ConfirmError,catchlet:"1IK3HA6AV2"};
	};
	Start.jaxId="1IK3H9U510"
	Start.url="Start@"+agentURL
	
	segs["CreateTTY"]=CreateTTY=async function(input){//:1IK3HGFR70
		let result=input
		/*#{1IK3HGFR70Code*/
		tty=await session.WSCall_CreateTTY();
		/*}#1IK3HGFR70Code*/
		return {seg:TipInstallPkg,result:(result),preSeg:"1IK3HGFR70",outlet:"1IK3HJMPJ0"};
	};
	CreateTTY.jaxId="1IK3HGFR70"
	CreateTTY.url="CreateTTY@"+agentURL
	
	segs["TipInstallPkg"]=TipInstallPkg=async function(input){//:1IK3HH7J80
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=(($ln==="CN")?(`安装应用程序：${appStub.name}`):/*EN*/(`Installing app: ${appStub.name}`));
		session.addChatText(role,content,opts);
		return {seg:CheckAgent,result:(result),preSeg:"1IK3HH7J80",outlet:"1IK3HJMPJ1"};
	};
	TipInstallPkg.jaxId="1IK3HH7J80"
	TipInstallPkg.url="TipInstallPkg@"+agentURL
	
	segs["InstallPkg"]=InstallPkg=async function(input){//:1IK3HHJOI0
		let result=input
		/*#{1IK3HHJOI0Code*/
		let workFunc;
		workFunc=(await import("/@pkg/pkgUtil.js")).installPkg;
		result=await workFunc(null,appStub.appId||appStub._id,{tty:tty,setupType:"setupAgent"});
		/*}#1IK3HHJOI0Code*/
		return {seg:CheckInstall,result:(result),preSeg:"1IK3HHJOI0",outlet:"1IK3HJMPJ2"};
	};
	InstallPkg.jaxId="1IK3HHJOI0"
	InstallPkg.url="InstallPkg@"+agentURL
	
	segs["CheckInstall"]=CheckInstall=async function(input){//:1IK3HJ6R20
		let result=input;
		if(input){
			return {seg:ConfirmFin,result:(input),preSeg:"1IK3HJ6R20",outlet:"1IK3HJMPJ3"};
		}
		return {seg:ConfirmFailed,result:(result),preSeg:"1IK3HJ6R20",outlet:"1IK3HJMPJ4"};
	};
	CheckInstall.jaxId="1IK3HJ6R20"
	CheckInstall.url="CheckInstall@"+agentURL
	
	segs["CheckAgent"]=CheckAgent=async function(input){//:1IK3I7AT20
		let result=input;
		if(appStub.type==="AgentNode"){
			return {seg:CheckEnv,result:(input),preSeg:"1IK3I7AT20",outlet:"1IK3IAKNR0"};
		}
		return {seg:InstallPkg,result:(result),preSeg:"1IK3I7AT20",outlet:"1IK3IAKNR1"};
	};
	CheckAgent.jaxId="1IK3I7AT20"
	CheckAgent.url="CheckAgent@"+agentURL
	
	segs["CheckEnv"]=CheckEnv=async function(input){//:1IK3I98I00
		let result=input;
		/*#{1IK3I98I00Start*/
		let res,envOK=true;
		res=await tabNT.makeCall("AhListAgentNodes",{});
		if(!res || res.code!==200){
			envOK=false;
		}
		/*}#1IK3I98I00Start*/
		if(!envOK){
			return {seg:AskNoEnv,result:(input),preSeg:"1IK3I98I00",outlet:"1IK3IAKNR2"};
		}
		/*#{1IK3I98I00Post*/
		/*}#1IK3I98I00Post*/
		return {seg:InstallPkg,result:(result),preSeg:"1IK3I98I00",outlet:"1IK3IAKNR3"};
	};
	CheckEnv.jaxId="1IK3I98I00"
	CheckEnv.url="CheckEnv@"+agentURL
	
	segs["ConfirmFin"]=ConfirmFin=async function(input){//:1IK3JR4SO0
		let prompt=((($ln==="CN")?("安装已完成"):("Installation completed")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("确定"):("OK")),code:0},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Finish,result:(result),preSeg:"1IK3JR4SO0",outlet:"1IK3JR4SB0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Finish,result:(result),preSeg:"1IK3JR4SO0",outlet:"1IK3JR4SB0"};
		}
		return {result:result};
	};
	ConfirmFin.jaxId="1IK3JR4SO0"
	ConfirmFin.url="ConfirmFin@"+agentURL
	
	segs["ConfirmFailed"]=ConfirmFailed=async function(input){//:1IK3JV66M3
		let prompt=("安装未成功。")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("确定"):("OK")),code:0},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Failed,result:(result),preSeg:"1IK3JV66M3",outlet:"1IK3JV66N1"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Failed,result:(result),preSeg:"1IK3JV66M3",outlet:"1IK3JV66N1"};
		}
		return {result:result};
	};
	ConfirmFailed.jaxId="1IK3JV66M3"
	ConfirmFailed.url="ConfirmFailed@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1IK3K1L6N0
		let result=input
		/*#{1IK3K1L6N0Code*/
		result={result:"Finish",content:`"${appStub.name} 已经成功的安装完毕。"`}
		/*}#1IK3K1L6N0Code*/
		return {result:result};
	};
	Finish.jaxId="1IK3K1L6N0"
	Finish.url="Finish@"+agentURL
	
	segs["Failed"]=Failed=async function(input){//:1IK3K1VNE0
		let result=input
		/*#{1IK3K1VNE0Code*/
		result={result:"Failed",content:`"${appStub.name} 未能成功安装。"`}
		/*}#1IK3K1VNE0Code*/
		return {result:result};
	};
	Failed.jaxId="1IK3K1VNE0"
	Failed.url="Failed@"+agentURL
	
	segs["ConfirmError"]=ConfirmError=async function(input){//:1IK3KR0L30
		let prompt=(input)||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("关闭"):("Close")),code:0},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Error,result:(result),preSeg:"1IK3KR0L30",outlet:"1IK3KR0KN0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Error,result:(result),preSeg:"1IK3KR0L30",outlet:"1IK3KR0KN0"};
		}
		return {result:result};
	};
	ConfirmError.jaxId="1IK3KR0L30"
	ConfirmError.url="ConfirmError@"+agentURL
	
	segs["Error"]=Error=async function(input){//:1IK3KT2VB0
		let result=input
		/*#{1IK3KT2VB0Code*/
		result={result:"Failed",content:""+input};
		/*}#1IK3KT2VB0Code*/
		return {result:result};
	};
	Error.jaxId="1IK3KT2VB0"
	Error.url="Error@"+agentURL
	
	segs["AskNoEnv"]=AskNoEnv=async function(input){//:1IMEAEU160
		let prompt=((($ln==="CN")?("这个项目需要安装AgentNode，当前的AI2Apps不是本地部署的，不支持AgentNode。要安装AgentNode，请部署本地版本的AI2Apps。"):("This project requires installing AgentNode, the current AI2Apps is not locally deployed and does not support AgentNode. To install AgentNode, please deploy the local version of AI2Apps.")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("放弃安装"):("Abort installation")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("知道了，仍然安装"):("Got it, proceed with installation")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Abort,result:(result),preSeg:"1IMEAEU160",outlet:"1IMEAEU0I0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Abort,result:(result),preSeg:"1IMEAEU160",outlet:"1IMEAEU0I0"};
		}else if(item.code===1){
			return {seg:InstallPkg,result:(result),preSeg:"1IMEAEU160",outlet:"1IMEAEU0J0"};
		}
		return {result:result};
	};
	AskNoEnv.jaxId="1IMEAEU160"
	AskNoEnv.url="AskNoEnv@"+agentURL
	
	segs["Abort"]=Abort=async function(input){//:1IMEAMTAL0
		let result=input
		/*#{1IMEAMTAL0Code*/
		result={result:"Failed",content:"The current AI2Apps environment does not support installing AgentNode. To install AgentNode, deploy the local version of AI2Apps."};
		/*}#1IMEAMTAL0Code*/
		return {result:result};
	};
	Abort.jaxId="1IMEAMTAL0"
	Abort.url="Abort@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"SysInstallApp",
		url:agentURL,
		autoStart:true,
		jaxId:"1IK3H9P1H0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{appStub}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IK3H9P1H0PreEntry*/
			/*}#1IK3H9P1H0PreEntry*/
			result={seg:Start,"input":input};
			/*#{1IK3H9P1H0PostEntry*/
			/*}#1IK3H9P1H0PostEntry*/
			return result;
		},
		/*#{1IK3H9P1H0MoreAgentAttrs*/
		/*}#1IK3H9P1H0MoreAgentAttrs*/
	};
	/*#{1IK3H9P1H0PostAgent*/
	/*}#1IK3H9P1H0PostAgent*/
	return agent;
};
/*#{1IK3H9P1H0ExCodes*/
/*}#1IK3H9P1H0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "SysInstallApp",
		description: "这是AI2Apps系统安装App/Tool的智能体，须给出App/Tool的安装描述对象。",
		parameters:{
			type: "object",
			properties:{
				appStub:{type:"auto",description:"App/Tool的安装描述对象"}
			}
		}
	},
	agent: SysInstallApp
}];
//#CodyExport<<<
/*#{1IK3H9P1H0PostDoc*/
/*}#1IK3H9P1H0PostDoc*/


export default SysInstallApp;
export{SysInstallApp};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IK3H9P1H0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IK3H9P1H1",
//			"attrs": {
//				"SysInstallApp": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IK3H9P1H7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IK3H9P1H8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IK3H9P1H9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IK3H9P1H10",
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
//			"jaxId": "1IK3H9P1H2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "Start",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IK3H9P1H3",
//			"attrs": {
//				"appStub": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IK3HB4270",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "App/Tool的安装描述对象"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IK3H9P1H4",
//			"attrs": {
//				"tty": {
//					"type": "auto",
//					"valText": "null"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IK3H9P1H5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IK3H9P1H6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IK3H9U510",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "110",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK3HA6AV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK3HA6AV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK3HA6AU0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK3HGFR70"
//						},
//						"catchlet": {
//							"jaxId": "1IK3HA6AV2",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK3KR0L30"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IK3HGFR70",
//					"attrs": {
//						"id": "CreateTTY",
//						"viewName": "",
//						"label": "",
//						"x": "285",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK3HJMPL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK3HJMPL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK3HJMPJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK3HH7J80"
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
//					"def": "output",
//					"jaxId": "1IK3HH7J80",
//					"attrs": {
//						"id": "TipInstallPkg",
//						"viewName": "",
//						"label": "",
//						"x": "515",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK3HJMPL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK3HJMPL3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#(($ln===\"CN\")?(`安装应用程序：${appStub.name}`):/*EN*/(`Installing app: ${appStub.name}`))",
//						"outlet": {
//							"jaxId": "1IK3HJMPJ1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK3I7AT20"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IK3HHJOI0",
//					"attrs": {
//						"id": "InstallPkg",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK3HJMPL4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK3HJMPL5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK3HJMPJ2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK3HJ6R20"
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
//					"jaxId": "1IK3HJ6R20",
//					"attrs": {
//						"id": "CheckInstall",
//						"viewName": "",
//						"label": "",
//						"x": "1495",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK3HJMPL6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK3HJMPL7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK3HJMPJ4",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IK3JV66M3"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IK3HJMPJ3",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IK3HJMPL8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IK3HJMPL9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input"
//									},
//									"linkedSeg": "1IK3JR4SO0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IK3I7AT20",
//					"attrs": {
//						"id": "CheckAgent",
//						"viewName": "",
//						"label": "",
//						"x": "765",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK3IARSA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK3IARSA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK3IAKNR1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IK3HHJOI0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IK3IAKNR0",
//									"attrs": {
//										"id": "AgentNode",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IK3IARSA2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IK3IARSA3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#appStub.type===\"AgentNode\""
//									},
//									"linkedSeg": "1IK3I98I00"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IK3I98I00",
//					"attrs": {
//						"id": "CheckEnv",
//						"viewName": "",
//						"label": "",
//						"x": "1010",
//						"y": "130",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK3IARSA4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK3IARSA5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK3IAKNR3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IK3HHJOI0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IK3IAKNR2",
//									"attrs": {
//										"id": "NoEnv",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IK3IARSA6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IK3IARSA7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!envOK"
//									},
//									"linkedSeg": "1IMEAEU160"
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
//					"jaxId": "1IK3JR4SO0",
//					"attrs": {
//						"id": "ConfirmFin",
//						"viewName": "",
//						"label": "",
//						"x": "1720",
//						"y": "155",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Installation completed",
//							"localize": {
//								"EN": "Installation completed",
//								"CN": "安装已完成"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IK3JV5TQ0",
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
//									"jaxId": "1IK3JR4SB0",
//									"attrs": {
//										"id": "OK",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "OK",
//											"localize": {
//												"EN": "OK",
//												"CN": "确定"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IK3JV5TQ1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IK3JV5TQ2",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IK3K1L6N0"
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
//					"def": "askMenu",
//					"jaxId": "1IK3JV66M3",
//					"attrs": {
//						"id": "ConfirmFailed",
//						"viewName": "",
//						"label": "",
//						"x": "1720",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "安装未成功。",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IK3JV66N0",
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
//									"jaxId": "1IK3JV66N1",
//									"attrs": {
//										"id": "OK",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "OK",
//											"localize": {
//												"EN": "OK",
//												"CN": "确定"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IK3JV66N2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IK3JV66N3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IK3K1VNE0"
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
//					"jaxId": "1IK3K1L6N0",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "1975",
//						"y": "140",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK3K2F9I0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK3K2F9I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK3K2F9F0",
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
//					"jaxId": "1IK3K1VNE0",
//					"attrs": {
//						"id": "Failed",
//						"viewName": "",
//						"label": "",
//						"x": "1975",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK3K2F9I2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK3K2F9I3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK3K2F9F1",
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
//					"def": "askMenu",
//					"jaxId": "1IK3KR0L30",
//					"attrs": {
//						"id": "ConfirmError",
//						"viewName": "",
//						"label": "",
//						"x": "300",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "#input",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IK3KTMFB0",
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
//									"jaxId": "1IK3KR0KN0",
//									"attrs": {
//										"id": "Close",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Close",
//											"localize": {
//												"EN": "Close",
//												"CN": "关闭"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IK3KU7AQ0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IK3KU7AQ1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IK3KT2VB0"
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
//					"jaxId": "1IK3KT2VB0",
//					"attrs": {
//						"id": "Error",
//						"viewName": "",
//						"label": "",
//						"x": "555",
//						"y": "310",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IK3KU7AQ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IK3KU7AQ3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IK3KTMFB1",
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
//					"def": "askMenu",
//					"jaxId": "1IMEAEU160",
//					"attrs": {
//						"id": "AskNoEnv",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "30",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "This project requires installing AgentNode, the current AI2Apps is not locally deployed and does not support AgentNode. To install AgentNode, please deploy the local version of AI2Apps.",
//							"localize": {
//								"EN": "This project requires installing AgentNode, the current AI2Apps is not locally deployed and does not support AgentNode. To install AgentNode, please deploy the local version of AI2Apps.",
//								"CN": "这个项目需要安装AgentNode，当前的AI2Apps不是本地部署的，不支持AgentNode。要安装AgentNode，请部署本地版本的AI2Apps。"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IMEAN4HB0",
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
//									"jaxId": "1IMEAEU0I0",
//									"attrs": {
//										"id": "GiveUp",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Abort installation",
//											"localize": {
//												"EN": "Abort installation",
//												"CN": "放弃安装"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMEAQ90L0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMEAQ90L1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IMEAMTAL0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IMEAEU0J0",
//									"attrs": {
//										"id": "Install",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Got it, proceed with installation",
//											"localize": {
//												"EN": "Got it, proceed with installation",
//												"CN": "知道了，仍然安装"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMEAQ90L2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMEAQ90L3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IMEAQP1N0"
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
//					"jaxId": "1IMEAMTAL0",
//					"attrs": {
//						"id": "Abort",
//						"viewName": "",
//						"label": "",
//						"x": "1495",
//						"y": "0",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IMEAQ90L4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMEAQ90L5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IMEAN4HB1",
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
//					"jaxId": "1IMEAQP1N0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1380",
//						"y": "120",
//						"outlet": {
//							"jaxId": "1IMEB85B10",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK3HHJOI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是AI2Apps系统安装App/Tool的智能体，须给出App/Tool的安装描述对象。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}