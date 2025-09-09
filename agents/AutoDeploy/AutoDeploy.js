//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1J0BHD5IP0MoreImports*/
/*}#1J0BHD5IP0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?decodeURI(baseURL):baseURL;
const $ln=VFACT.lanCode||"EN";
/*#{1J0BHD5IP0StartDoc*/
/*}#1J0BHD5IP0StartDoc*/
//----------------------------------------------------------------------------
let AutoDeploy=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Run;
	/*#{1J0BHD5IP0LocalVals*/
	/*}#1J0BHD5IP0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1J0BHD5IP0ParseArgs*/
		/*}#1J0BHD5IP0ParseArgs*/
	}
	
	/*#{1J0BHD5IP0PreContext*/
	/*}#1J0BHD5IP0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1J0BHD5IP0PostContext*/
	/*}#1J0BHD5IP0PostContext*/
	let $agent,agent,segs={};
	segs["Run"]=Run=async function(input){//:1J0BHD35J0
		let result,args={};
		args['nodeName']="AutoDeploy";
		args['callAgent']="agent.js";
		args['callArg']=input;
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	Run.jaxId="1J0BHD35J0"
	Run.url="Run@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"AutoDeploy",
		url:agentURL,
		autoStart:true,
		jaxId:"1J0BHD5IP0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1J0BHD5IP0PreEntry*/
			/*}#1J0BHD5IP0PreEntry*/
			result={seg:Run,"input":input};
			/*#{1J0BHD5IP0PostEntry*/
			/*}#1J0BHD5IP0PostEntry*/
			return result;
		},
		/*#{1J0BHD5IP0MoreAgentAttrs*/
		/*}#1J0BHD5IP0MoreAgentAttrs*/
	};
	/*#{1J0BHD5IP0PostAgent*/
	/*}#1J0BHD5IP0PostAgent*/
	return agent;
};
/*#{1J0BHD5IP0ExCodes*/
/*}#1J0BHD5IP0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "AutoDeploy",
		description: "这是一个帮助用户自动部署github项目的agent，需要给出github的链接如https://github.com/Avdpro/ai2apps或repo的名称如Avdpro/ai2apps。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	agent: AutoDeploy
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
		name:"AutoDeploy",showName:"AutoDeploy",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"这是一个帮助用户自动部署github项目的agent，需要给出github的链接如https://github.com/Avdpro/ai2apps或repo的名称如Avdpro/ai2apps。"
	});
	
	DocAIAgentExporter.segTypeExporters["AutoDeploy"]=
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
			coder.packText(`result= await session.pipeChat("/~/AutoDeploy/ai/AutoDeploy.js",args,false);`);coder.newLine();
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
/*#{1J0BHD5IP0PostDoc*/
/*}#1J0BHD5IP0PostDoc*/


export default AutoDeploy;
export{AutoDeploy};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1J0BHD5IP0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1J0BHD5IQ0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1J0BHD5IQ1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1J0BHD5IQ2",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1J0BHD5IQ3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1J0BHD5IQ4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1J0BHD5IQ5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1J0BHD35J0",
//					"attrs": {
//						"id": "Run",
//						"viewName": "",
//						"label": "",
//						"x": "255",
//						"y": "95",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0BHD5IQ6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0BHD5IQ7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AutoDeploy",
//						"callAgent": "agent.js",
//						"callArg": "#input",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J0BHD5IP1",
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
//		"desc": "这是一个帮助用户自动部署github项目的agent，需要给出github的链接如https://github.com/Avdpro/ai2apps或repo的名称如Avdpro/ai2apps。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}