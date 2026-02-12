//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1JH0A9FG20MoreImports*/
import {tabOS,tabFS,tabNT} from "/@tabos";
/*}#1JH0A9FG20MoreImports*/
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
	/*#{1JH0A9FG20ArgsView*/
	/*}#1JH0A9FG20ArgsView*/
};

/*#{1JH0A9FG20StartDoc*/
/*}#1JH0A9FG20StartDoc*/
//----------------------------------------------------------------------------
let ModelHunt=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Read,FixArgs,Check,Deploy,Use;
	/*#{1JH0A9FG20LocalVals*/
	/*}#1JH0A9FG20LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
		}else{
			model=undefined;
		}
		/*#{1JH0A9FG20ParseArgs*/
		/*}#1JH0A9FG20ParseArgs*/
	}
	
	/*#{1JH0A9FG20PreContext*/
	/*}#1JH0A9FG20PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1JH0A9FG20PostContext*/
	/*}#1JH0A9FG20PostContext*/
	let $agent,agent,segs={};
	segs["Read"]=Read=async function(input){//:1JH0A9C8N0
		let result=input
		try{
			/*#{1JH0A9C8N0Code*/
			let modelJSON=await tabFS.readFile(pathLib.join(basePath.slice(2),"model.json"),"utf8");
			modelJSON=JSON.parse(modelJSON);
			result=modelJSON;
			result = modelJSON.deployable.includes(model);
			/*}#1JH0A9C8N0Code*/
		}catch(error){
			/*#{1JH0A9C8N0ErrorCode*/
			/*}#1JH0A9C8N0ErrorCode*/
		}
		return {seg:Check,result:(result),preSeg:"1JH0A9C8N0",outlet:"1JH0A9FG40"};
	};
	Read.jaxId="1JH0A9C8N0"
	Read.url="Read@"+agentURL
	
	segs["FixArgs"]=FixArgs=async function(input){//:1JH0A9UQ00
		let result=input;
		let missing=false;
		let smartAsk=false;
		/*#{1JH0A9UQ00PreCodes*/
		/*}#1JH0A9UQ00PreCodes*/
		if(model===undefined || model==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@aichat/ai/CompleteArgs.js",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		/*#{1JH0A9UQ00PostCodes*/
		/*}#1JH0A9UQ00PostCodes*/
		return {seg:Read,result:(result),preSeg:"1JH0A9UQ00",outlet:"1JH0AA4J90"};
	};
	FixArgs.jaxId="1JH0A9UQ00"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1JH0ABO060
		let result=input;
		if(input){
			return {seg:Use,result:(input),preSeg:"1JH0ABO060",outlet:"1JH0ACAAI0"};
		}
		return {seg:Deploy,result:(result),preSeg:"1JH0ABO060",outlet:"1JH0ACAAI1"};
	};
	Check.jaxId="1JH0ABO060"
	Check.url="Check@"+agentURL
	
	segs["Deploy"]=Deploy=async function(input){//:1JH0ADNPF0
		let result;
		let arg={model:model};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.joinTabOSURL(basePath,"./ModelDeployAgent.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	Deploy.jaxId="1JH0ADNPF0"
	Deploy.url="Deploy@"+agentURL
	
	segs["Use"]=Use=async function(input){//:1JH0AENRO0
		let result;
		let arg={model:model};
		let agentNode=("")||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.joinTabOSURL(basePath,"./ModelUseAgent.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	Use.jaxId="1JH0AENRO0"
	Use.url="Use@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ModelHunt",
		url:agentURL,
		autoStart:true,
		jaxId:"1JH0A9FG20",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JH0A9FG20PreEntry*/
			/*}#1JH0A9FG20PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1JH0A9FG20PostEntry*/
			/*}#1JH0A9FG20PostEntry*/
			return result;
		},
		/*#{1JH0A9FG20MoreAgentAttrs*/
		/*}#1JH0A9FG20MoreAgentAttrs*/
	};
	/*#{1JH0A9FG20PostAgent*/
	/*}#1JH0A9FG20PostAgent*/
	return agent;
};
/*#{1JH0A9FG20ExCodes*/
/*}#1JH0A9FG20ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "ModelHunt",
		description: "This is an AI agent.",
		parameters:{
			type: "object",
			properties:{
				model:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true,
	agent: ModelHunt
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
		name:"ModelHunt",showName:"ModelHunt",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"model":{name:"model",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","model","codes","desc"],
		desc:"This is an AI agent."
	});
	
	DocAIAgentExporter.segTypeExporters["ModelHunt"]=
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
			coder.packText(`result= await session.pipeChat("/~/AutoDeploy_dev/ai/ModelHunt.js",args,false);`);coder.newLine();
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
/*#{1JH0A9FG20PostDoc*/
/*}#1JH0A9FG20PostDoc*/


export default ModelHunt;
export{ModelHunt};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JH0A9FG20",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JH0A9FG60",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JH0A9FG61",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JH0A9FG62",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JH0A9QO80",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JH0A9FG63",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JH0A9FG64",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JH0A9FG65",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JH0A9C8N0",
//					"attrs": {
//						"id": "Read",
//						"viewName": "",
//						"label": "",
//						"x": "320",
//						"y": "195",
//						"desc": "This is an AISeg.",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0A9FG70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0A9FG71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH0A9FG40",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH0ABO060"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1JH0A9UQ00",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "45",
//						"y": "195",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1JH0AA4J90",
//							"attrs": {
//								"id": "Next",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH0A9C8N0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JH0ABO060",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "550",
//						"y": "195",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0ACAAO0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0ACAAO1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH0ACAAI1",
//							"attrs": {
//								"id": "NotDeployed",
//								"desc": "Outlet.",
//								"output": ""
//							},
//							"linkedSeg": "1JH0ADNPF0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JH0ACAAI0",
//									"attrs": {
//										"id": "Deployed",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JH0ACAAO2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JH0ACAAO3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input"
//									},
//									"linkedSeg": "1JH0AENRO0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JH0ADNPF0",
//					"attrs": {
//						"id": "Deploy",
//						"viewName": "",
//						"label": "",
//						"x": "785",
//						"y": "330",
//						"desc": "Call AI Agent, use it's output as result",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0AEFKL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0AEFKL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/ModelDeployAgent.js",
//						"argument": "#{model:model}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JH0AEFKE0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							}
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JH0AENRO0",
//					"attrs": {
//						"id": "Use",
//						"viewName": "",
//						"label": "",
//						"x": "785",
//						"y": "60",
//						"desc": "Call AI Agent, use it's output as result",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0AFDQE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0AFDQE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/ModelUseAgent.js",
//						"argument": "#{model:model}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JH0AFDQB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"agentNode": ""
//					},
//					"icon": "agent.svg"
//				}
//			]
//		},
//		"desc": "This is an AI agent.",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}