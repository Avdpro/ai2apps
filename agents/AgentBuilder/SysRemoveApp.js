//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IT5DSBVS0MoreImports*/
/*}#1IT5DSBVS0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"appStub":{
			"name":"appStub","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IT5DSBVS0ArgsView*/
	/*}#1IT5DSBVS0ArgsView*/
};

/*#{1IT5DSBVS0StartDoc*/
/*}#1IT5DSBVS0StartDoc*/
//----------------------------------------------------------------------------
let SysRemoveApp=async function(session){
	let appStub;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,ConfirmError,Error,CreateTTY,TipRemovePkg,RemovePkg,ConfirmFin,Finish;
	let tty=null;
	
	/*#{1IT5DSBVS0LocalVals*/
	/*}#1IT5DSBVS0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			appStub=input.appStub;
		}else{
			appStub=undefined;
		}
		/*#{1IT5DSBVS0ParseArgs*/
		/*}#1IT5DSBVS0ParseArgs*/
	}
	
	/*#{1IT5DSBVS0PreContext*/
	/*}#1IT5DSBVS0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IT5DSBVS0PostContext*/
	/*}#1IT5DSBVS0PostContext*/
	let $agent,agent,segs={};
	segs["Start"]=Start=async function(input){//:1IT5DT8H60
		let result=input;
		/*#{1IT5DT8H60Code*/
		false
		/*}#1IT5DT8H60Code*/
		return {seg:CreateTTY,result:(result),preSeg:"1IT5DT8H60",outlet:"1IT5DT8H63",catchSeg:ConfirmError,catchlet:"1IT5DT8H64"};
	};
	Start.jaxId="1IT5DT8H60"
	Start.url="Start@"+agentURL
	
	segs["ConfirmError"]=ConfirmError=async function(input){//:1IT5DTDJP3
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
			result=input;
			return {seg:Error,result:(result),preSeg:"1IT5DTDJP3",outlet:"1IT5DTDJP5"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			result=(input);
			return {seg:Error,result:(result),preSeg:"1IT5DTDJP3",outlet:"1IT5DTDJP5"};
		}
		return {result:result};
	};
	ConfirmError.jaxId="1IT5DTDJP3"
	ConfirmError.url="ConfirmError@"+agentURL
	
	segs["Error"]=Error=async function(input){//:1IT5DTKAQ0
		let result=input
		/*#{1IT5DTKAQ0Code*/
		result={result:"Failed",content:""+input};
		/*}#1IT5DTKAQ0Code*/
		return {result:result};
	};
	Error.jaxId="1IT5DTKAQ0"
	Error.url="Error@"+agentURL
	
	segs["CreateTTY"]=CreateTTY=async function(input){//:1IT5DU0I60
		let result=input
		/*#{1IT5DU0I60Code*/
		tty=await session.WSCall_CreateTTY();
		/*}#1IT5DU0I60Code*/
		return {seg:TipRemovePkg,result:(result),preSeg:"1IT5DU0I60",outlet:"1IT5DU0I63"};
	};
	CreateTTY.jaxId="1IT5DU0I60"
	CreateTTY.url="CreateTTY@"+agentURL
	
	segs["TipRemovePkg"]=TipRemovePkg=async function(input){//:1IT5DUB690
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=(($ln==="CN")?(`删除：${appStub.name}`):/*EN*/(`Remove: ${appStub.name}`));
		session.addChatText(role,content,opts);
		return {seg:RemovePkg,result:(result),preSeg:"1IT5DUB690",outlet:"1IT5DUB693"};
	};
	TipRemovePkg.jaxId="1IT5DUB690"
	TipRemovePkg.url="TipRemovePkg@"+agentURL
	
	segs["RemovePkg"]=RemovePkg=async function(input){//:1IT5DV5B60
		let result=input
		/*#{1IT5DV5B60Code*/
		let workFunc;
		workFunc=(await import("/@pkg/pkgUtil.js")).uninstallPkg;
		result=await workFunc(null,appStub.appId||appStub._id,{tty:tty});
		/*}#1IT5DV5B60Code*/
		return {seg:ConfirmFin,result:(result),preSeg:"1IT5DV5B60",outlet:"1IT5DV5B63"};
	};
	RemovePkg.jaxId="1IT5DV5B60"
	RemovePkg.url="RemovePkg@"+agentURL
	
	segs["ConfirmFin"]=ConfirmFin=async function(input){//:1IT5EE8JL3
		let prompt=((($ln==="CN")?("卸载已完成"):("Remove completed")))||input;
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
			return {seg:Finish,result:(result),preSeg:"1IT5EE8JL3",outlet:"1IT5EE8JM1"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Finish,result:(result),preSeg:"1IT5EE8JL3",outlet:"1IT5EE8JM1"};
		}
		return {result:result};
	};
	ConfirmFin.jaxId="1IT5EE8JL3"
	ConfirmFin.url="ConfirmFin@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1IT5EF4OJ0
		let result=input
		/*#{1IT5EF4OJ0Code*/
		result={result:"Finish",content:`"${appStub.name} 已经成功的卸载完毕。"`}
		/*}#1IT5EF4OJ0Code*/
		return {result:result};
	};
	Finish.jaxId="1IT5EF4OJ0"
	Finish.url="Finish@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"SysRemoveApp",
		url:agentURL,
		autoStart:true,
		jaxId:"1IT5DSBVS0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{appStub}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IT5DSBVS0PreEntry*/
			/*}#1IT5DSBVS0PreEntry*/
			result={seg:Start,"input":input};
			/*#{1IT5DSBVS0PostEntry*/
			/*}#1IT5DSBVS0PostEntry*/
			return result;
		},
		/*#{1IT5DSBVS0MoreAgentAttrs*/
		/*}#1IT5DSBVS0MoreAgentAttrs*/
	};
	/*#{1IT5DSBVS0PostAgent*/
	/*}#1IT5DSBVS0PostAgent*/
	return agent;
};
/*#{1IT5DSBVS0ExCodes*/
/*}#1IT5DSBVS0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IT5DSBVS0PostDoc*/
/*}#1IT5DSBVS0PostDoc*/


export default SysRemoveApp;
export{SysRemoveApp};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IT5DSBVS0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IT5DSBVS1",
//			"attrs": {
//				"SysRemoveApp": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IT5DSBVS7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IT5DSBVT0",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IT5DSBVT1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IT5DSBVT2",
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
//			"jaxId": "1IT5DSBVS2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IT5DSBVS3",
//			"attrs": {
//				"appStub": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IT5F36C10",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IT5DSBVS4",
//			"attrs": {
//				"tty": {
//					"type": "auto",
//					"valText": "null"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IT5DSBVS5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IT5DSBVS6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IT5DT8H60",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "120",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IT5DT8H61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IT5DT8H62",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IT5DT8H63",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IT5DU0I60"
//						},
//						"catchlet": {
//							"jaxId": "1IT5DT8H64",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IT5DTDJP3"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IT5DTDJP3",
//					"attrs": {
//						"id": "ConfirmError",
//						"viewName": "",
//						"label": "",
//						"x": "315",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "#input",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IT5DTDJP4",
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
//									"jaxId": "1IT5DTDJP5",
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
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IT5DTDJP6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IT5DTDJP7",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IT5DTKAQ0"
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
//					"jaxId": "1IT5DTKAQ0",
//					"attrs": {
//						"id": "Error",
//						"viewName": "",
//						"label": "",
//						"x": "585",
//						"y": "335",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IT5DTKAQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IT5DTKAQ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IT5DTKAQ3",
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
//					"jaxId": "1IT5DU0I60",
//					"attrs": {
//						"id": "CreateTTY",
//						"viewName": "",
//						"label": "",
//						"x": "315",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IT5DU0I61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IT5DU0I62",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IT5DU0I63",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IT5DUB690"
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
//					"jaxId": "1IT5DUB690",
//					"attrs": {
//						"id": "TipRemovePkg",
//						"viewName": "",
//						"label": "",
//						"x": "585",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IT5DUB691",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IT5DUB692",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#(($ln===\"CN\")?(`删除：${appStub.name}`):/*EN*/(`Remove: ${appStub.name}`))",
//						"outlet": {
//							"jaxId": "1IT5DUB693",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IT5DV5B60"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IT5DV5B60",
//					"attrs": {
//						"id": "RemovePkg",
//						"viewName": "",
//						"label": "",
//						"x": "845",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IT5DV5B61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IT5DV5B62",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IT5DV5B63",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IT5EE8JL3"
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
//					"jaxId": "1IT5EE8JL3",
//					"attrs": {
//						"id": "ConfirmFin",
//						"viewName": "",
//						"label": "",
//						"x": "1090",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Remove completed",
//							"localize": {
//								"EN": "Remove completed",
//								"CN": "卸载已完成"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IT5EE8JM0",
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
//									"jaxId": "1IT5EE8JM1",
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
//											"jaxId": "1IT5EE8JM2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IT5EE8JM3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IT5EF4OJ0"
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
//					"jaxId": "1IT5EF4OJ0",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "1370",
//						"y": "165",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IT5EF4OJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IT5EF4OJ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IT5EF4OJ3",
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
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}