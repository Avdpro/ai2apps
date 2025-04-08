//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1ICJD7Q850MoreImports*/
import {RemoteSession} from "./remotesession.mjs";
/*}#1ICJD7Q850MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"nodeName":{
			"name":"nodeName","type":"string",
			"label":"Node Name",
			"defaultValue":"",
			"desc":"",
		},
		"callAgent":{
			"name":"callAgent","type":"string",
			"label":"Agent",
			"defaultValue":"",
			"desc":"",
		},
		"callArg":{
			"name":"callArg","type":"auto",
			"label":"Call argument",
			"defaultValue":undefined,
			"desc":"",
		},
		"checkUpdate":{
			"name":"checkUpdate","type":"bool",
			"label":"Check update",
			"defaultValue":true,
			"desc":"",
		},
		"options":{
			"name":"options","type":"auto",
			"label":"Options",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1ICJD7Q850ArgsView*/
	/*}#1ICJD7Q850ArgsView*/
};

/*#{1ICJD7Q850StartDoc*/
/*}#1ICJD7Q850StartDoc*/
//----------------------------------------------------------------------------
let RemoteChat=async function(session){
	let nodeName,callAgent,callArg,checkUpdate,options;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Exec;
	/*#{1ICJD7Q850LocalVals*/
	/*}#1ICJD7Q850LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			nodeName=input.nodeName;
			callAgent=input.callAgent;
			callArg=input.callArg;
			checkUpdate=input.checkUpdate;
			options=input.options;
		}else{
			nodeName=undefined;
			callAgent=undefined;
			callArg=undefined;
			checkUpdate=undefined;
			options=undefined;
		}
		/*#{1ICJD7Q850ParseArgs*/
		/*}#1ICJD7Q850ParseArgs*/
	}
	
	/*#{1ICJD7Q850PreContext*/
	/*}#1ICJD7Q850PreContext*/
	context={};
	/*#{1ICJD7Q850PostContext*/
	/*}#1ICJD7Q850PostContext*/
	let agent,segs={};
	segs["Exec"]=Exec=async function(input){//:1ICSOGS7J0
		let result=input
		/*#{1ICSOGS7J0Code*/
		options=options||{};
		result=await RemoteSession.exec(session,nodeName,callAgent,callArg,{...options,checkUpdate:!!checkUpdate});
		/*}#1ICSOGS7J0Code*/
		return {result:result};
	};
	Exec.jaxId="1ICSOGS7J0"
	Exec.url="Exec@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"RemoteChat",
		url:agentURL,
		autoStart:true,
		jaxId:"1ICJD7Q850",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{nodeName,callAgent,callArg,checkUpdate,options}*/){
			let result;
			parseAgentArgs(input);
			/*#{1ICJD7Q850PreEntry*/
			/*}#1ICJD7Q850PreEntry*/
			result={seg:Exec,"input":input};
			/*#{1ICJD7Q850PostEntry*/
			/*}#1ICJD7Q850PostEntry*/
			return result;
		},
		/*#{1ICJD7Q850MoreAgentAttrs*/
		/*}#1ICJD7Q850MoreAgentAttrs*/
	};
	/*#{1ICJD7Q850PostAgent*/
	/*}#1ICJD7Q850PostAgent*/
	return agent;
};
/*#{1ICJD7Q850ExCodes*/
/*}#1ICJD7Q850ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "RemoteChat",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				nodeName:{type:"string",description:""},
				callAgent:{type:"string",description:""},
				callArg:{type:"auto",description:""},
				checkUpdate:{type:"bool",description:""},
				options:{type:"auto",description:""}
			}
		}
	},
	path: "${this.agentInBrowser?'/@aichat/ai/RemoteChat.js':'/@tabos/RemoteChat.mjs'}",
	label: "Remote Chat",
	icon: "cloudact.svg"
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
		name:"RemoteChat",showName:"Remote Chat",icon:"cloudact.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"nodeName":{name:"nodeName",showName:(($ln==="CN")?("节点名称"):("Node Name")),type:"string",key:1,fixed:1,initVal:""},
			"callAgent":{name:"callAgent",showName:(($ln==="CN")?("代理"):("Agent")),type:"string",key:1,fixed:1,initVal:""},
			"callArg":{name:"callArg",showName:(($ln==="CN")?("调用参数"):("Call argument")),type:"auto",key:1,fixed:1,initVal:undefined},
			"checkUpdate":{name:"checkUpdate",showName:(($ln==="CN")?("检查更新"):("Check update")),type:"bool",key:1,fixed:1,initVal:true},
			"options":{name:"options",showName:"Options",type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","nodeName","callAgent","callArg","checkUpdate","options","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["RemoteChat"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['nodeName']=");this.genAttrStatement(seg.getAttr("nodeName"));coder.packText(";");coder.newLine();
			coder.packText("args['callAgent']=");this.genAttrStatement(seg.getAttr("callAgent"));coder.packText(";");coder.newLine();
			coder.packText("args['callArg']=");this.genAttrStatement(seg.getAttr("callArg"));coder.packText(";");coder.newLine();
			coder.packText("args['checkUpdate']=");this.genAttrStatement(seg.getAttr("checkUpdate"));coder.packText(";");coder.newLine();
			coder.packText("args['options']=");this.genAttrStatement(seg.getAttr("options"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("${this.agentInBrowser?'/@aichat/ai/RemoteChat.js':'/@tabos/RemoteChat.mjs'}",args,false);`);coder.newLine();
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
/*#{1ICJD7Q850PostDoc*/
RemoteChat.pythonAddOn=function(){
	//:Export Edit-AddOn:
	const DocPyAgentExporter=VFACT.classRegs.DocPyAgentExporter;
	if(DocPyAgentExporter){
		const EditAttr=VFACT.classRegs.EditAttr;
		const EditAISeg=VFACT.classRegs.EditAISeg;
		const EditAISegOutlet=VFACT.classRegs.EditAISegOutlet;
		const SegObjShellAttr=EditAISeg.SegObjShellAttr;
		const SegOutletDef=EditAISegOutlet.SegOutletDef;
		const docPyAgentExporter=DocPyAgentExporter.prototype;
		const packExtraCodes=docPyAgentExporter.packExtraCodes;
		const packResult=docPyAgentExporter.packResult;
		const varNameRegex = /^[a-zA-Z_$][a-zA-Z0-9_$]*$/;

		DocPyAgentExporter.segTypeExporters["RemoteChat"]=
			function(seg){
			let coder=this.coder;
			let segName=seg.idVal.val;
			let exportDebug=this.isExportDebug();
			segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
			coder.packText(`async def ${segName}_exec(input):#//:${seg.jaxId}`);
			coder.indentMore();coder.newLine();
			{
				coder.packText(`result=None`);coder.newLine();
				coder.packText(`args={}`);coder.newLine();
				coder.packText("args['nodeName']=");this.genAttrStatement(seg.getAttr("nodeName"));coder.newLine();
				coder.packText("args['callAgent']=");this.genAttrStatement(seg.getAttr("callAgent"));coder.newLine();
				coder.packText("args['callArg']=");this.genAttrStatement(seg.getAttr("callArg"));coder.newLine();
				coder.packText("args['checkUpdate']=");this.genAttrStatement(seg.getAttr("checkUpdate"));coder.newLine();
				coder.packText("args['options']=");this.genAttrStatement(seg.getAttr("options"));coder.newLine();
				this.packExtraCodes(coder,seg,"PreCodes");
				coder.packText(`result= await session.pipeChat("/@tabos/RemoteChat.py",args,false)`);coder.newLine();
				this.packExtraCodes(coder,seg,"PostCodes");
				this.packUpdateContext(coder,seg);
				this.packUpdateGlobal(coder,seg);
				this.packResult(coder,seg,seg.outlet);
			}
			coder.indentLess();coder.maybeNewLine();
			coder.packText(`segs["${segName}"]=${segName}={`);
			coder.indentMore();coder.newLine();
			coder.packText(`"name":"${segName}",`);coder.newLine()
			coder.packText(`"exec":${segName}_exec,`);coder.newLine()
			coder.packText(`"jaxId":"${seg.jaxId}",`);coder.newLine()
			coder.packText(`"url":"${segName}@"+agentURL`);coder.newLine()
			coder.indentLess();coder.maybeNewLine();coder.packText("}");coder.newLine();
			coder.newLine();
		};
	}
}
/*}#1ICJD7Q850PostDoc*/


export default RemoteChat;
export{RemoteChat,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1ICJD7Q850",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1ICJD7Q851",
//			"attrs": {
//				"RemoteChat": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1ICJD7Q857",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1ICJD7Q858",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1ICJD7Q859",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1ICJD7Q8510",
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
//			"jaxId": "1ICJD7Q852",
//			"attrs": {}
//		},
//		"entry": "Exec",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1ICJD7Q853",
//			"attrs": {
//				"nodeName": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ICUSO3750",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "",
//						"label": {
//							"type": "string",
//							"valText": "Node Name",
//							"localize": {
//								"EN": "Node Name",
//								"CN": "节点名称"
//							},
//							"localizable": true
//						}
//					}
//				},
//				"callAgent": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ICUSO3751",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "",
//						"label": {
//							"type": "string",
//							"valText": "Agent",
//							"localize": {
//								"EN": "Agent",
//								"CN": "代理"
//							},
//							"localizable": true
//						}
//					}
//				},
//				"callArg": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ICUSO3752",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "#input",
//						"desc": "",
//						"label": {
//							"type": "string",
//							"valText": "Call argument",
//							"localize": {
//								"EN": "Call argument",
//								"CN": "调用参数"
//							},
//							"localizable": true
//						}
//					}
//				},
//				"checkUpdate": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ID02QSL90",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "true",
//						"desc": "",
//						"label": {
//							"type": "string",
//							"valText": "Check update",
//							"localize": {
//								"EN": "Check update",
//								"CN": "检查更新"
//							},
//							"localizable": true
//						}
//					}
//				},
//				"options": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1INTU6IVN0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "",
//						"label": "Options"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1ICJD7Q854",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1ICJD7Q855",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1ICJD7Q856",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ICSOGS7J0",
//					"attrs": {
//						"id": "Exec",
//						"viewName": "",
//						"label": "",
//						"x": "110",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ICSOHFAI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ICSOHFAI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ICSOHFAE0",
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
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"Remote Chat\",\"path\":\"${this.agentInBrowser?'/@aichat/ai/RemoteChat.js':'/@tabos/RemoteChat.mjs'}\",\"pathInHub\":\"\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"cloudact.svg\",\"catalog\":\"AI Call\"}"
//	}
//}