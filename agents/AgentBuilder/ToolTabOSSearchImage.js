//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IO2JLGLK0MoreImports*/
/*}#1IO2JLGLK0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1IO2JLGLK0StartDoc*/
/*}#1IO2JLGLK0StartDoc*/
//----------------------------------------------------------------------------
let ToolTabOSSearchImage=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let SearchImage;
	/*#{1IO2JLGLK0LocalVals*/
	/*}#1IO2JLGLK0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IO2JLGLK0ParseArgs*/
		/*}#1IO2JLGLK0ParseArgs*/
	}
	
	/*#{1IO2JLGLK0PreContext*/
	/*}#1IO2JLGLK0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IO2JLGLK0PostContext*/
	/*}#1IO2JLGLK0PostContext*/
	let $agent,agent,segs={};
	segs["SearchImage"]=SearchImage=async function(input){//:1IO2JKD800
		let result,args={};
		args['nodeName']="builder_new";
		args['callAgent']="ToolSearchImage.js";
		args['callArg']=input;
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	SearchImage.jaxId="1IO2JKD800"
	SearchImage.url="SearchImage@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolTabOSSearchImage",
		url:agentURL,
		autoStart:true,
		jaxId:"1IO2JLGLK0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IO2JLGLK0PreEntry*/
			/*}#1IO2JLGLK0PreEntry*/
			result={seg:SearchImage,"input":input};
			/*#{1IO2JLGLK0PostEntry*/
			/*}#1IO2JLGLK0PostEntry*/
			return result;
		},
		/*#{1IO2JLGLK0MoreAgentAttrs*/
		/*}#1IO2JLGLK0MoreAgentAttrs*/
	};
	/*#{1IO2JLGLK0PostAgent*/
	/*}#1IO2JLGLK0PostAgent*/
	return agent;
};
/*#{1IO2JLGLK0ExCodes*/
/*}#1IO2JLGLK0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "ToolTabOSSearchImage",
		description: "这是一个搜索图片的工具，返回图片的url，请提供图片的英文描述和图片数量。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	label: "ImageSearch",
	agent: ToolTabOSSearchImage
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
		name:"ToolTabOSSearchImage",showName:"ImageSearch",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"这是一个搜索图片的工具，返回图片的url，请提供图片的英文描述和图片数量。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolTabOSSearchImage"]=
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
			coder.packText(`result= await session.pipeChat("/~/builder_new/ai/ToolTabOSSearchImage.js",args,false);`);coder.newLine();
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
/*#{1IO2JLGLK0PostDoc*/
/*}#1IO2JLGLK0PostDoc*/


export default ToolTabOSSearchImage;
export{ToolTabOSSearchImage};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IO2JLGLK0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IO2JLGLO0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1IO2JLGLO1",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IO2JLGLO2",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IO2JLGLO3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IO2JLGLO4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IO2JLGLO5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1IO2JKD800",
//					"attrs": {
//						"id": "SearchImage",
//						"viewName": "",
//						"label": "",
//						"x": "375",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IO2JLGLO6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IO2JLGLO7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "builder_new",
//						"callAgent": "ToolSearchImage.js",
//						"callArg": "#input",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IO2JLGLM0",
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
//		"desc": "这是一个搜索图片的工具，返回图片的url，请提供图片的英文描述和图片数量。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"ImageSearch\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":false,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
//	}
//}