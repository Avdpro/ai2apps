//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1INT58F1H0MoreImports*/
/*}#1INT58F1H0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1INT58F1H0StartDoc*/
/*}#1INT58F1H0StartDoc*/
//----------------------------------------------------------------------------
let ToolTabOSWriteFIle=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let WriteFile;
	/*#{1INT58F1H0LocalVals*/
	/*}#1INT58F1H0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1INT58F1H0ParseArgs*/
		/*}#1INT58F1H0ParseArgs*/
	}
	
	/*#{1INT58F1H0PreContext*/
	/*}#1INT58F1H0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1INT58F1H0PostContext*/
	/*}#1INT58F1H0PostContext*/
	let $agent,agent,segs={};
	segs["WriteFile"]=WriteFile=async function(input){//:1INT57N8K0
		let result,args={};
		args['nodeName']="builder_new";
		args['callAgent']="ToolWriteFIle.js";
		args['callArg']=input;
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	WriteFile.jaxId="1INT57N8K0"
	WriteFile.url="WriteFile@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolTabOSWriteFIle",
		url:agentURL,
		autoStart:true,
		jaxId:"1INT58F1H0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1INT58F1H0PreEntry*/
			/*}#1INT58F1H0PreEntry*/
			result={seg:WriteFile,"input":input};
			/*#{1INT58F1H0PostEntry*/
			/*}#1INT58F1H0PostEntry*/
			return result;
		},
		/*#{1INT58F1H0MoreAgentAttrs*/
		/*}#1INT58F1H0MoreAgentAttrs*/
	};
	/*#{1INT58F1H0PostAgent*/
	/*}#1INT58F1H0PostAgent*/
	return agent;
};
/*#{1INT58F1H0ExCodes*/
/*}#1INT58F1H0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "ToolTabOSWriteFIle",
		description: "这是一个用于写入文件的工具，需要提供完整、详细的内容和文件的绝对路径以及是否追加末尾写入，如果是纯文本文件如md,txt,py,html等等请提供完整的文本内容，如果是excel类型的文件（xlsx,csv等），请提供用^|^作为分隔符的完整表格内容，如果是pdf或者word（docx）类型的文件，请提供完整的文本内容。请按照{filePath:\"\",content:\"\",append:true/false}的格式给出。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	label: "WriteFile",
	agent: ToolTabOSWriteFIle
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
		name:"ToolTabOSWriteFIle",showName:"WriteFile",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"这是一个用于写入文件的工具，需要提供完整、详细的内容和文件的绝对路径以及是否追加末尾写入，如果是纯文本文件如md,txt,py,html等等请提供完整的文本内容，如果是excel类型的文件（xlsx,csv等），请提供用^|^作为分隔符的完整表格内容，如果是pdf或者word（docx）类型的文件，请提供完整的文本内容。请按照{filePath:\"\",content:\"\",append:true/false}的格式给出。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolTabOSWriteFIle"]=
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
			coder.packText(`result= await session.pipeChat("/~/builder_new/ai/ToolTabOSWriteFIle.js",args,false);`);coder.newLine();
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
/*#{1INT58F1H0PostDoc*/
/*}#1INT58F1H0PostDoc*/


export default ToolTabOSWriteFIle;
export{ToolTabOSWriteFIle};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1INT58F1H0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1INT58F1K0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1INT58F1K1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1INT58F1K2",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1INT58F1K3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1INT58F1K4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1INT58F1K5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1INT57N8K0",
//					"attrs": {
//						"id": "WriteFile",
//						"viewName": "",
//						"label": "",
//						"x": "200",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INT58F1K6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INT58F1K7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "builder_new",
//						"callAgent": "ToolWriteFIle.js",
//						"callArg": "#input",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1INT58F1J0",
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
//		"desc": "这是一个用于写入文件的工具，需要提供完整、详细的内容和文件的绝对路径以及是否追加末尾写入，如果是纯文本文件如md,txt,py,html等等请提供完整的文本内容，如果是excel类型的文件（xlsx,csv等），请提供用^|^作为分隔符的完整表格内容，如果是pdf或者word（docx）类型的文件，请提供完整的文本内容。请按照{filePath:\"\",content:\"\",append:true/false}的格式给出。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"WriteFile\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":false,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
//	}
//}