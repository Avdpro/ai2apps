//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1JM7GKOH80MoreImports*/
/*}#1JM7GKOH80MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?decodeURI(baseURL):baseURL;
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"task":{
			"name":"task","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JM7GKOH80ArgsView*/
	/*}#1JM7GKOH80ArgsView*/
};

/*#{1JM7GKOH80StartDoc*/
/*}#1JM7GKOH80StartDoc*/
//----------------------------------------------------------------------------
let ModelUseAgentTest=async function(session){
	let model,task;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Run;
	/*#{1JM7GKOH80LocalVals*/
	/*}#1JM7GKOH80LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
			task=input.task;
		}else{
			model=undefined;
			task=undefined;
		}
		/*#{1JM7GKOH80ParseArgs*/
		/*}#1JM7GKOH80ParseArgs*/
	}
	
	/*#{1JM7GKOH80PreContext*/
	/*}#1JM7GKOH80PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1JM7GKOH80PostContext*/
	/*}#1JM7GKOH80PostContext*/
	let $agent,agent,segs={};
	segs["Run"]=Run=async function(input){//:1JM7GJI4P0
		let result,args={};
		args['nodeName']="AutoDeploy";
		args['callAgent']="ModelTest.js";
		args['callArg']={model:model,task:task};
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	Run.jaxId="1JM7GJI4P0"
	Run.url="Run@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ModelUseAgentTest",
		url:agentURL,
		autoStart:true,
		jaxId:"1JM7GKOH80",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model,task}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JM7GKOH80PreEntry*/
			/*}#1JM7GKOH80PreEntry*/
			result={seg:Run,"input":input};
			/*#{1JM7GKOH80PostEntry*/
			/*}#1JM7GKOH80PostEntry*/
			return result;
		},
		/*#{1JM7GKOH80MoreAgentAttrs*/
		/*}#1JM7GKOH80MoreAgentAttrs*/
	};
	/*#{1JM7GKOH80PostAgent*/
	/*}#1JM7GKOH80PostAgent*/
	return agent;
};
/*#{1JM7GKOH80ExCodes*/
/*}#1JM7GKOH80ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "ModelUseAgentTest",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				model:{type:"auto",description:""},
				task:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true,
	agent: ModelUseAgentTest
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
		name:"ModelUseAgentTest",showName:"ModelUseAgentTest",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"model":{name:"model",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"task":{name:"task",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","model","task","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["ModelUseAgentTest"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['model']=");this.genAttrStatement(seg.getAttr("model"));coder.packText(";");coder.newLine();
			coder.packText("args['task']=");this.genAttrStatement(seg.getAttr("task"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AutoDeploy_dev/ai/ModelUseAgentTest.js",args,false);`);coder.newLine();
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
/*#{1JM7GKOH80PostDoc*/
/*}#1JM7GKOH80PostDoc*/


export default ModelUseAgentTest;
export{ModelUseAgentTest};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JM7GKOH80",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JM7GKOH90",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JM7GKOH91",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JM7GKOH92",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JM7GLN820",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"task": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JM7GLN821",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JM7GKOH93",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JM7GKOH94",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JM7GKOH95",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1JM7GJI4P0",
//					"attrs": {
//						"id": "Run",
//						"viewName": "",
//						"label": "",
//						"x": "625",
//						"y": "470",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JM7GJI4P1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JM7GJI4P2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AutoDeploy",
//						"callAgent": "ModelTest.js",
//						"callArg": "#{model:model,task:task}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JM7GJI4Q0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							}
//						}
//					},
//					"icon": "cloudact.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}