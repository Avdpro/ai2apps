//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1INT5CI5S0MoreImports*/
/*}#1INT5CI5S0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1INT5CI5S0StartDoc*/
/*}#1INT5CI5S0StartDoc*/
//----------------------------------------------------------------------------
let ToolTabOSReadFile=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ReadFile;
	/*#{1INT5CI5S0LocalVals*/
	/*}#1INT5CI5S0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1INT5CI5S0ParseArgs*/
		/*}#1INT5CI5S0ParseArgs*/
	}
	
	/*#{1INT5CI5S0PreContext*/
	/*}#1INT5CI5S0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1INT5CI5S0PostContext*/
	/*}#1INT5CI5S0PostContext*/
	let agent,segs={};
	segs["ReadFile"]=ReadFile=async function(input){//:1INT5CUGM0
		let result,args={};
		args['nodeName']="builder_new";
		args['callAgent']="ToolReadFile.js";
		args['callArg']=input;
		args['checkUpdate']=true;
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	ReadFile.jaxId="1INT5CUGM0"
	ReadFile.url="ReadFile@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolTabOSReadFile",
		url:agentURL,
		autoStart:true,
		jaxId:"1INT5CI5S0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1INT5CI5S0PreEntry*/
			/*}#1INT5CI5S0PreEntry*/
			result={seg:ReadFile,"input":input};
			/*#{1INT5CI5S0PostEntry*/
			/*}#1INT5CI5S0PostEntry*/
			return result;
		},
		/*#{1INT5CI5S0MoreAgentAttrs*/
		/*}#1INT5CI5S0MoreAgentAttrs*/
	};
	/*#{1INT5CI5S0PostAgent*/
	/*}#1INT5CI5S0PostAgent*/
	return agent;
};
/*#{1INT5CI5S0ExCodes*/
/*}#1INT5CI5S0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "ToolTabOSReadFile",
		description: "这是一个读取文件内容的工具，支持pdf，doc，docx以及其他纯文本文件格式，需要提供文件的绝对路径。注意：在调用前请使用ls命令确认文件路径存在，一次可以读取多个文件，请完整列出所有文件的绝对路径。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	label: "ReadFile",
	agent: ToolTabOSReadFile
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
		name:"ToolTabOSReadFile",showName:"ReadFile",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"这是一个读取文件内容的工具，支持pdf，doc，docx以及其他纯文本文件格式，需要提供文件的绝对路径。注意：在调用前请使用ls命令确认文件路径存在，一次可以读取多个文件，请完整列出所有文件的绝对路径。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolTabOSReadFile"]=
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
			coder.packText(`result= await session.pipeChat("/~/builder_new/ai/ToolTabOSReadFile.js",args,false);`);coder.newLine();
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
/*#{1INT5CI5S0PostDoc*/
/*}#1INT5CI5S0PostDoc*/


export default ToolTabOSReadFile;
export{ToolTabOSReadFile};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1INT5CI5S0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1INT5DOOO0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1INT5DMUT0",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1INT5DOOO1",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1INT5DOOO2",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1INT5DOOO3",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1INT5DOOO4",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1INT5CUGM0",
//					"attrs": {
//						"id": "ReadFile",
//						"viewName": "",
//						"label": "",
//						"x": "345",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INT5DOOO5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INT5DOOO6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "builder_new",
//						"callAgent": "ToolReadFile.js",
//						"callArg": "#input",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1INT5DOON0",
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
//		"desc": "这是一个读取文件内容的工具，支持pdf，doc，docx以及其他纯文本文件格式，需要提供文件的绝对路径。注意：在调用前请使用ls命令确认文件路径存在，一次可以读取多个文件，请完整列出所有文件的绝对路径。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"ReadFile\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":false,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
//	}
//}