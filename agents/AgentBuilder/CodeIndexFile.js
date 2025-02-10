//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHHM4NIB0MoreImports*/
/*}#1IHHM4NIB0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"filePath":{
			"name":"filePath","type":"string",
			"defaultValue":"",
			"desc":"要读取接口的代码文件路径。",
		}
	},
	/*#{1IHHM4NIB0ArgsView*/
	/*}#1IHHM4NIB0ArgsView*/
};

/*#{1IHHM4NIB0StartDoc*/
/*}#1IHHM4NIB0StartDoc*/
//----------------------------------------------------------------------------
let CodeIndexFile=async function(session){
	let filePath;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,ReadCode,CheckRead,ReadIndex,ReadCache,CheckCache,ReadFail,SaveCache,UseCache;
	let codes="";
	let cachedIndex="";
	
	/*#{1IHHM4NIB0LocalVals*/
	/*}#1IHHM4NIB0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			filePath=input.filePath;
		}else{
			filePath=undefined;
		}
		/*#{1IHHM4NIB0ParseArgs*/
		/*}#1IHHM4NIB0ParseArgs*/
	}
	
	/*#{1IHHM4NIB0PreContext*/
	/*}#1IHHM4NIB0PreContext*/
	context={};
	/*#{1IHHM4NIB0PostContext*/
	/*}#1IHHM4NIB0PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHHMAGHL0
		let result=input;
		let missing=false;
		if(filePath===undefined || filePath==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:ReadCache,result:(result),preSeg:"1IHHMAGHL0",outlet:"1IHI3ARNS0"};
	};
	FixArgs.jaxId="1IHHMAGHL0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["ReadCode"]=ReadCode=async function(input){//:1IHI3D9ML0
		let result=input
		/*#{1IHI3D9ML0Code*/
		/*}#1IHI3D9ML0Code*/
		return {seg:CheckRead,result:(result),preSeg:"1IHI3D9ML0",outlet:"1IHI3D9ML1"};
	};
	ReadCode.jaxId="1IHI3D9ML0"
	ReadCode.url="ReadCode@"+agentURL
	
	segs["CheckRead"]=CheckRead=async function(input){//:1IHI3BG0Q0
		let result=input;
		if(codes){
			return {seg:ReadIndex,result:(input),preSeg:"1IHI3BG0Q0",outlet:"1IHI3D9ML2"};
		}
		return {seg:ReadFail,result:(result),preSeg:"1IHI3BG0Q0",outlet:"1IHI3D9ML3"};
	};
	CheckRead.jaxId="1IHI3BG0Q0"
	CheckRead.url="CheckRead@"+agentURL
	
	segs["ReadIndex"]=ReadIndex=async function(input){//:1IHI3RVGA0
		let prompt;
		let result;
		
		let opts={
			platform:"",
			mode:"$code",
			maxToken:3912,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=ReadIndex.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		result=await session.callSegLLM("ReadIndex@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:SaveCache,result:(result),preSeg:"1IHI3RVGA0",outlet:"1IHI3VGDR0"};
	};
	ReadIndex.jaxId="1IHI3RVGA0"
	ReadIndex.url="ReadIndex@"+agentURL
	
	segs["ReadCache"]=ReadCache=async function(input){//:1IHI40E500
		let result=input
		/*#{1IHI40E500Code*/
		/*}#1IHI40E500Code*/
		return {seg:CheckCache,result:(result),preSeg:"1IHI40E500",outlet:"1IHI49K070"};
	};
	ReadCache.jaxId="1IHI40E500"
	ReadCache.url="ReadCache@"+agentURL
	
	segs["CheckCache"]=CheckCache=async function(input){//:1IHI412320
		let result=input;
		if(!!cachedIndex){
			let output=cachedIndex;
			return {seg:UseCache,result:(output),preSeg:"1IHI412320",outlet:"1IHI49K071"};
		}
		return {seg:ReadCode,result:(result),preSeg:"1IHI412320",outlet:"1IHI49K072"};
	};
	CheckCache.jaxId="1IHI412320"
	CheckCache.url="CheckCache@"+agentURL
	
	segs["ReadFail"]=ReadFail=async function(input){//:1IHI426O10
		let result=input
		/*#{1IHI426O10Code*/
		/*}#1IHI426O10Code*/
		return {result:result};
	};
	ReadFail.jaxId="1IHI426O10"
	ReadFail.url="ReadFail@"+agentURL
	
	segs["SaveCache"]=SaveCache=async function(input){//:1IHI42S1J0
		let result=input
		/*#{1IHI42S1J0Code*/
		/*}#1IHI42S1J0Code*/
		return {result:result};
	};
	SaveCache.jaxId="1IHI42S1J0"
	SaveCache.url="SaveCache@"+agentURL
	
	segs["UseCache"]=UseCache=async function(input){//:1IHI475160
		let result=input
		/*#{1IHI475160Code*/
		/*}#1IHI475160Code*/
		return {result:result};
	};
	UseCache.jaxId="1IHI475160"
	UseCache.url="UseCache@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"CodeIndexFile",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHHM4NIB0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{filePath}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHHM4NIB0PreEntry*/
			/*}#1IHHM4NIB0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHHM4NIB0PostEntry*/
			/*}#1IHHM4NIB0PostEntry*/
			return result;
		},
		/*#{1IHHM4NIB0MoreAgentAttrs*/
		/*}#1IHHM4NIB0MoreAgentAttrs*/
	};
	/*#{1IHHM4NIB0PostAgent*/
	/*}#1IHHM4NIB0PostAgent*/
	return agent;
};
/*#{1IHHM4NIB0ExCodes*/
/*}#1IHHM4NIB0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CodeIndexFile",
		description: "这是从代码中提取接口信息的智能体，获取代码中输出的function, class, properties。",
		parameters:{
			type: "object",
			properties:{
				filePath:{type:"string",description:"要读取接口的代码文件路径。"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IHHM4NIB0PostDoc*/
/*}#1IHHM4NIB0PostDoc*/


export default CodeIndexFile;
export{CodeIndexFile,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHHM4NIB0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHHM4NIB1",
//			"attrs": {
//				"CodeIndexFile": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHHM4NIC0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHHM4NIC1",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHHM4NIC2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHHM4NIC3",
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
//			"jaxId": "1IHHM4NIB2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHHM4NIB3",
//			"attrs": {
//				"filePath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHHMA7SJ0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要读取接口的代码文件路径。"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHHM4NIB4",
//			"attrs": {
//				"codes": {
//					"type": "string",
//					"valText": ""
//				},
//				"cachedIndex": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IHHM4NIB5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHHM4NIB6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHHMAGHL0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "85",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHI3ARNS0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI40E500"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHI3D9ML0",
//					"attrs": {
//						"id": "ReadCode",
//						"viewName": "",
//						"label": "",
//						"x": "775",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI3D9MM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI3D9MM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI3D9ML1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI3BG0Q0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IHI3BG0Q0",
//					"attrs": {
//						"id": "CheckRead",
//						"viewName": "",
//						"label": "",
//						"x": "995",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHI3D9MM2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI3D9MM3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI3D9ML3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IHI426O10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHI3D9ML2",
//									"attrs": {
//										"id": "Success",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHI3D9MM4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHI3D9MM5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#codes"
//									},
//									"linkedSeg": "1IHI3RVGA0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IHI3RVGA0",
//					"attrs": {
//						"id": "ReadIndex",
//						"viewName": "",
//						"label": "",
//						"x": "1250",
//						"y": "335",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI3VGDS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI3VGDS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "",
//						"mode": "$code",
//						"system": "You are a smart assistant.",
//						"temperature": "0",
//						"maxToken": "3912",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IHI3VGDR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI42S1J0"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "No",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHI40E500",
//					"attrs": {
//						"id": "ReadCache",
//						"viewName": "",
//						"label": "",
//						"x": "295",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI49K080",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI49K090",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI49K070",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHI412320"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IHI412320",
//					"attrs": {
//						"id": "CheckCache",
//						"viewName": "",
//						"label": "",
//						"x": "525",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHI49K091",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI49K092",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI49K072",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IHI3D9ML0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHI49K071",
//									"attrs": {
//										"id": "Cache",
//										"desc": "输出节点。",
//										"output": "#cachedIndex",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHI49K093",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHI49K094",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!cachedIndex"
//									},
//									"linkedSeg": "1IHI475160"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHI426O10",
//					"attrs": {
//						"id": "ReadFail",
//						"viewName": "",
//						"label": "",
//						"x": "1250",
//						"y": "410",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHI49K095",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI49K096",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI49K073",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHI42S1J0",
//					"attrs": {
//						"id": "SaveCache",
//						"viewName": "",
//						"label": "",
//						"x": "1485",
//						"y": "335",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI49K097",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI49K098",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI49K074",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHI475160",
//					"attrs": {
//						"id": "UseCache",
//						"viewName": "",
//						"label": "",
//						"x": "770",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IHI49K099",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHI49K0910",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHI49K075",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是从代码中提取接口信息的智能体，获取代码中输出的function, class, properties。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}