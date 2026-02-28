//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1JIEF1OI60MoreImports*/
import {tabOS,tabFS,tabNT} from "/@tabos";
/*}#1JIEF1OI60MoreImports*/
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
		}
	},
	/*#{1JIEF1OI60ArgsView*/
	/*}#1JIEF1OI60ArgsView*/
};

/*#{1JIEF1OI60StartDoc*/
/*}#1JIEF1OI60StartDoc*/
//----------------------------------------------------------------------------
let DeleteModelAgent=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Delete,Save;
	/*#{1JIEF1OI60LocalVals*/
	/*}#1JIEF1OI60LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
		}else{
			model=undefined;
		}
		/*#{1JIEF1OI60ParseArgs*/
		/*}#1JIEF1OI60ParseArgs*/
	}
	
	/*#{1JIEF1OI60PreContext*/
	/*}#1JIEF1OI60PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1JIEF1OI60PostContext*/
	/*}#1JIEF1OI60PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1JIEF1KHF0
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(model===undefined || model==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@aichat/ai/CompleteArgs.js",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:Delete,result:(result),preSeg:"1JIEF1KHF0",outlet:"1JIEF1OI61"};
	};
	FixArgs.jaxId="1JIEF1KHF0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Delete"]=Delete=async function(input){//:1JIEF29T10
		let result,args={};
		args['nodeName']="AutoDeploy";
		args['callAgent']="DeleteModel.js";
		args['callArg']={model:model};
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {seg:Save,result:(result),preSeg:"1JIEF29T10",outlet:"1JIEF468V0"};
	};
	Delete.jaxId="1JIEF29T10"
	Delete.url="Delete@"+agentURL
	
	segs["Save"]=Save=async function(input){//:1JIEF42RA0
		let result=input
		try{
			/*#{1JIEF42RA0Code*/
			let modelJSON=await tabFS.readFile(pathLib.join("/doc/ModelHunt","model.json"),"utf8");
			modelJSON=JSON.parse(modelJSON);
			result=modelJSON;
			if (modelJSON.deployable.includes(model)) {
				modelJSON.deployable = modelJSON.deployable.filter(item => item !== model);
			}
			await tabFS.writeFile(pathLib.join("/doc/ModelHunt","model.json"),JSON.stringify(modelJSON,null,"\t"));
			/*}#1JIEF42RA0Code*/
		}catch(error){
			/*#{1JIEF42RA0ErrorCode*/
			/*}#1JIEF42RA0ErrorCode*/
		}
		return {result:result};
	};
	Save.jaxId="1JIEF42RA0"
	Save.url="Save@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"DeleteModelAgent",
		url:agentURL,
		autoStart:true,
		jaxId:"1JIEF1OI60",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JIEF1OI60PreEntry*/
			/*}#1JIEF1OI60PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1JIEF1OI60PostEntry*/
			/*}#1JIEF1OI60PostEntry*/
			return result;
		},
		/*#{1JIEF1OI60MoreAgentAttrs*/
		/*}#1JIEF1OI60MoreAgentAttrs*/
	};
	/*#{1JIEF1OI60PostAgent*/
	/*}#1JIEF1OI60PostAgent*/
	return agent;
};
/*#{1JIEF1OI60ExCodes*/
/*}#1JIEF1OI60ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "DeleteModelAgent",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				model:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true,
	agent: DeleteModelAgent
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
		name:"DeleteModelAgent",showName:"DeleteModelAgent",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"model":{name:"model",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","model","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["DeleteModelAgent"]=
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
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AutoDeploy_dev/ai/DeleteModelAgent.js",args,false);`);coder.newLine();
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
/*#{1JIEF1OI60PostDoc*/
/*}#1JIEF1OI60PostDoc*/


export default DeleteModelAgent;
export{DeleteModelAgent};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JIEF1OI60",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JIEF1OI62",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JIEF1OI63",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JIEF1OI64",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JIEF1TDM0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JIEF1OI65",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JIEF1OI66",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JIEF1OI67",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1JIEF1KHF0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "205",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1JIEF1OI61",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIEF29T10"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1JIEF29T10",
//					"attrs": {
//						"id": "Delete",
//						"viewName": "",
//						"label": "",
//						"x": "435",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIEF46900",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIEF46901",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AutoDeploy",
//						"callAgent": "DeleteModel.js",
//						"callArg": "#{model:model}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JIEF468V0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JIEF42RA0"
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JIEF42RA0",
//					"attrs": {
//						"id": "Save",
//						"viewName": "",
//						"label": "",
//						"x": "645",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JIEF46902",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JIEF46903",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JIEF468V1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}