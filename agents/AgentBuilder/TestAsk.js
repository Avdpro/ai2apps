//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IOEPFBTI0MoreImports*/
/*}#1IOEPFBTI0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"city":{
			"name":"city","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"要查询天气的城市",
		},
		"wind":{
			"name":"wind","type":"bool",
			"required":true,
			"defaultValue":"",
			"desc":"是否需要风力信息，如果没有明确，必须询问",
		},
		"token":{
			"name":"token","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"调用天气API的token",
		}
	},
	/*#{1IOEPFBTI0ArgsView*/
	/*}#1IOEPFBTI0ArgsView*/
};

/*#{1IOEPFBTI0StartDoc*/
/*}#1IOEPFBTI0StartDoc*/
//----------------------------------------------------------------------------
let TestAsk=async function(session){
	let city,wind,token;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,TipTest,AskUpper,FakeResult;
	/*#{1IOEPFBTI0LocalVals*/
	/*}#1IOEPFBTI0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			city=input.city;
			wind=input.wind;
			token=input.token;
		}else{
			city=undefined;
			wind=undefined;
			token=undefined;
		}
		/*#{1IOEPFBTI0ParseArgs*/
		/*}#1IOEPFBTI0ParseArgs*/
	}
	
	/*#{1IOEPFBTI0PreContext*/
	/*}#1IOEPFBTI0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IOEPFBTI0PostContext*/
	/*}#1IOEPFBTI0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IOFV469B0
		let result=input;
		let missing=false;
		let smartAsk=true;
		if(city===undefined || city==="") missing=true;
		if(wind===undefined || wind==="") missing=true;
		if(token===undefined || token==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@aichat/ai/CompleteArgs.js",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:TipTest,result:(result),preSeg:"1IOFV469B0",outlet:"1IOFV96P30"};
	};
	FixArgs.jaxId="1IOFV469B0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["TipTest"]=TipTest=async function(input){//:1IOEPFORQ0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="log";
		let content="这是测试层级询问机制的智能体，并没有实际功能。";
		session.addChatText(role,content,opts);
		return {seg:FakeResult,result:(result),preSeg:"1IOEPFORQ0",outlet:"1IOETHB4C0"};
	};
	TipTest.jaxId="1IOEPFORQ0"
	TipTest.url="TipTest@"+agentURL
	
	segs["AskUpper"]=AskUpper=async function(input){//:1IOEPJHGO0
		let tip=("是否需要风力信息？");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		if(askUpward && tip){
			result=await session.askUpward(askUpward==="$up"?($agent.upperAgent||$agent):$agent,tip);
		}else{
			if(tip){
				session.addChatText(tipRole,tip);
			}
			result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		}
		return {result:result};
	};
	AskUpper.jaxId="1IOEPJHGO0"
	AskUpper.url="AskUpper@"+agentURL
	
	segs["FakeResult"]=FakeResult=async function(input){//:1IOETGVAJ0
		let result=input
		/*#{1IOETGVAJ0Code*/
		result={result:"Finish",content:`{"Temputure": 20,"condition":"Cloudy"}`};
		/*}#1IOETGVAJ0Code*/
		return {result:result};
	};
	FakeResult.jaxId="1IOETGVAJ0"
	FakeResult.url="FakeResult@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"TestAsk",
		url:agentURL,
		autoStart:true,
		jaxId:"1IOEPFBTI0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{city,wind,token}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IOEPFBTI0PreEntry*/
			/*}#1IOEPFBTI0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IOEPFBTI0PostEntry*/
			/*}#1IOEPFBTI0PostEntry*/
			return result;
		},
		/*#{1IOEPFBTI0MoreAgentAttrs*/
		/*}#1IOEPFBTI0MoreAgentAttrs*/
	};
	/*#{1IOEPFBTI0PostAgent*/
	/*}#1IOEPFBTI0PostAgent*/
	return agent;
};
/*#{1IOEPFBTI0ExCodes*/
/*}#1IOEPFBTI0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "TestAsk",
		description: "这是获取制定城市天气情况的智能体。",
		parameters:{
			type: "object",
			properties:{
				city:{type:"string",description:"要查询天气的城市"},
				wind:{type:"bool",description:"是否需要风力信息，如果没有明确，必须询问"},
				token:{type:"string",description:"调用天气API的token"}
			}
		}
	},
	agent: TestAsk
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
		name:"TestAsk",showName:"TestAsk",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"city":{name:"city",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"wind":{name:"wind",showName:undefined,type:"bool",key:1,fixed:1,initVal:""},
			"token":{name:"token",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","city","wind","token","codes","desc"],
		desc:"这是获取制定城市天气情况的智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["TestAsk"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['city']=");this.genAttrStatement(seg.getAttr("city"));coder.packText(";");coder.newLine();
			coder.packText("args['wind']=");this.genAttrStatement(seg.getAttr("wind"));coder.packText(";");coder.newLine();
			coder.packText("args['token']=");this.genAttrStatement(seg.getAttr("token"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/TestAsk.js",args,false);`);coder.newLine();
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
/*#{1IOEPFBTI0PostDoc*/
/*}#1IOEPFBTI0PostDoc*/


export default TestAsk;
export{TestAsk};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IOEPFBTI0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IOEPFBTI1",
//			"attrs": {
//				"TestAsk": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IOEPFBTI7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IOEPFBTI8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IOEPFBTI9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IOEPFBTI10",
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
//			"jaxId": "1IOEPFBTI2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IOEPFBTI3",
//			"attrs": {
//				"city": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOFV96P70",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要查询天气的城市",
//						"required": "true"
//					}
//				},
//				"wind": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOFV96P71",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "\"\"",
//						"desc": "是否需要风力信息，如果没有明确，必须询问",
//						"required": "true"
//					}
//				},
//				"token": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOG3PALT0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "调用天气API的token",
//						"required": "true"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IOEPFBTI4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IOEPFBTI5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IOEPFBTI6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IOFV469B0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "115",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "true",
//						"outlet": {
//							"jaxId": "1IOFV96P30",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOEPFORQ0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IOEPFORQ0",
//					"attrs": {
//						"id": "TipTest",
//						"viewName": "",
//						"label": "",
//						"x": "340",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOETLLD20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOETLLD21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Log",
//						"text": "这是测试层级询问机制的智能体，并没有实际功能。",
//						"outlet": {
//							"jaxId": "1IOETHB4C0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOETGVAJ0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IOEPJHGO0",
//					"attrs": {
//						"id": "AskUpper",
//						"viewName": "",
//						"label": "",
//						"x": "565",
//						"y": "335",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOETLLD22",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOETLLD23",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "是否需要风力信息？",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "false",
//						"askUpward": "No",
//						"outlet": {
//							"jaxId": "1IOETHB4C1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IOETGVAJ0",
//					"attrs": {
//						"id": "FakeResult",
//						"viewName": "",
//						"label": "",
//						"x": "785",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOETLLD24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOETLLD25",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOETHB4C2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是获取制定城市天气情况的智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}