//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IOFAKA9O0MoreImports*/
/*}#1IOFAKA9O0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1IOFAKA9O0StartDoc*/
/*}#1IOFAKA9O0StartDoc*/
//----------------------------------------------------------------------------
let ToolTabOSModifyFile=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Run;
	/*#{1IOFAKA9O0LocalVals*/
	/*}#1IOFAKA9O0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IOFAKA9O0ParseArgs*/
		/*}#1IOFAKA9O0ParseArgs*/
	}
	
	/*#{1IOFAKA9O0PreContext*/
	/*}#1IOFAKA9O0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IOFAKA9O0PostContext*/
	/*}#1IOFAKA9O0PostContext*/
	let $agent,agent,segs={};
	segs["Run"]=Run=async function(input){//:1IOFAJ96I0
		let result,args={};
		args['nodeName']="builder_new";
		args['callAgent']="ToolModifyFile.js";
		args['callArg']=input;
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	Run.jaxId="1IOFAJ96I0"
	Run.url="Run@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolTabOSModifyFile",
		url:agentURL,
		autoStart:true,
		jaxId:"1IOFAKA9O0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IOFAKA9O0PreEntry*/
			/*}#1IOFAKA9O0PreEntry*/
			result={seg:Run,"input":input};
			/*#{1IOFAKA9O0PostEntry*/
			/*}#1IOFAKA9O0PostEntry*/
			return result;
		},
		/*#{1IOFAKA9O0MoreAgentAttrs*/
		/*}#1IOFAKA9O0MoreAgentAttrs*/
	};
	/*#{1IOFAKA9O0PostAgent*/
	/*}#1IOFAKA9O0PostAgent*/
	return agent;
};
/*#{1IOFAKA9O0ExCodes*/
/*}#1IOFAKA9O0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "ToolTabOSModifyFile",
		description: "修改文件内容的工具智能体，如修改文件内容，例如代码、配置文件。\n请提供要编辑的文件的完整绝对路径和如何修改的说明。\n请提供{filePath:\"\",guide:\"\"}",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	label: "ModifyFile",
	agent: ToolTabOSModifyFile
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
		name:"ToolTabOSModifyFile",showName:"ModifyFile",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"修改文件内容的工具智能体，如修改文件内容，例如代码、配置文件。\n请提供要编辑的文件的完整绝对路径和如何修改的说明。\n请提供{filePath:\"\",guide:\"\"}"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolTabOSModifyFile"]=
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
			coder.packText(`result= await session.pipeChat("/~/builder_new/ai/ToolTabOSModifyFile.js",args,false);`);coder.newLine();
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
/*#{1IOFAKA9O0PostDoc*/
/*}#1IOFAKA9O0PostDoc*/


export default ToolTabOSModifyFile;
export{ToolTabOSModifyFile};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IOFAKA9O0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IOFAKA9T0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1IOFAK06P0",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IOFAKA9T1",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IOFAKA9T2",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IOFAKA9T3",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IOFAKA9T4",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1IOFAJ96I0",
//					"attrs": {
//						"id": "Run",
//						"viewName": "",
//						"label": "",
//						"x": "200",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOFAKA9U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOFAKA9U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "builder_new",
//						"callAgent": "ToolModifyFile.js",
//						"callArg": "#input",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IOFAKA9Q0",
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
//		"desc": "修改文件内容的工具智能体，如修改文件内容，例如代码、配置文件。\n请提供要编辑的文件的完整绝对路径和如何修改的说明。\n请提供{filePath:\"\",guide:\"\"}",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"ModifyFile\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":false,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
//	}
//}