//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1ILQ95V4G0MoreImports*/
/*}#1ILQ95V4G0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1ILQ95V4G0StartDoc*/
/*}#1ILQ95V4G0StartDoc*/
//----------------------------------------------------------------------------
let ToolTabOSWebSearch=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let CallNode;
	/*#{1ILQ95V4G0LocalVals*/
	/*}#1ILQ95V4G0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1ILQ95V4G0ParseArgs*/
		/*}#1ILQ95V4G0ParseArgs*/
	}
	
	/*#{1ILQ95V4G0PreContext*/
	/*}#1ILQ95V4G0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1ILQ95V4G0PostContext*/
	/*}#1ILQ95V4G0PostContext*/
	let agent,segs={};
	segs["CallNode"]=CallNode=async function(input){//:1ILQ96BKV0
		let result,args={};
		args['nodeName']="AgentBuilder";
		args['callAgent']="RpaWebSearch.js";
		args['callArg']=input;
		args['checkUpdate']=true;
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	CallNode.jaxId="1ILQ96BKV0"
	CallNode.url="CallNode@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolTabOSWebSearch",
		url:agentURL,
		autoStart:true,
		jaxId:"1ILQ95V4G0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1ILQ95V4G0PreEntry*/
			/*}#1ILQ95V4G0PreEntry*/
			result={seg:CallNode,"input":input};
			/*#{1ILQ95V4G0PostEntry*/
			/*}#1ILQ95V4G0PostEntry*/
			return result;
		},
		/*#{1ILQ95V4G0MoreAgentAttrs*/
		/*}#1ILQ95V4G0MoreAgentAttrs*/
	};
	/*#{1ILQ95V4G0PostAgent*/
	/*}#1ILQ95V4G0PostAgent*/
	return agent;
};
/*#{1ILQ95V4G0ExCodes*/
/*}#1ILQ95V4G0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "ToolTabOSWebSearch",
		description: "使用Google进行网页搜索并返回总结后的搜索结果。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	agent: ToolTabOSWebSearch
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
		name:"ToolTabOSWebSearch",showName:"ToolTabOSWebSearch",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"使用Google进行网页搜索并返回总结后的搜索结果。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolTabOSWebSearch"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/ToolTabOSWebSearch.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
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
/*#{1ILQ95V4G0PostDoc*/
/*}#1ILQ95V4G0PostDoc*/


export default ToolTabOSWebSearch;
export{ToolTabOSWebSearch};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1ILQ95V4G0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1ILQ95V4G1",
//			"attrs": {
//				"ToolTabOSWebSearch": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1ILQ95V4G7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1ILQ95V4G8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1ILQ95V4G9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1ILQ95V4G10",
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
//			"jaxId": "1ILQ95V4G2",
//			"attrs": {}
//		},
//		"entry": "CallNode",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1ILQ95V4G3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1ILQ95V4G4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1ILQ95V4G5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1ILQ95V4G6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1ILQ96BKV0",
//					"attrs": {
//						"id": "CallNode",
//						"viewName": "",
//						"label": "",
//						"x": "135",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQ97ATF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQ97ATF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AgentBuilder",
//						"callAgent": "RpaWebSearch.js",
//						"callArg": "#input",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1ILQ97ATD0",
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
//		"desc": "使用Google进行网页搜索并返回总结后的搜索结果。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}