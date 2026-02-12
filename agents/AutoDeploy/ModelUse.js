//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1JH0RJ1S60MoreImports*/
/*}#1JH0RJ1S60MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JH0RJ1S60ArgsView*/
	/*}#1JH0RJ1S60ArgsView*/
};

/*#{1JH0RJ1S60StartDoc*/
/*}#1JH0RJ1S60StartDoc*/
//----------------------------------------------------------------------------
let ModelUse=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Check,Github,Ollama,Openrouter;
	/*#{1JH0RJ1S60LocalVals*/
	let model_type;
	/*}#1JH0RJ1S60LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
		}else{
			model=undefined;
		}
		/*#{1JH0RJ1S60ParseArgs*/
		/*}#1JH0RJ1S60ParseArgs*/
	}
	
	/*#{1JH0RJ1S60PreContext*/
	/*}#1JH0RJ1S60PreContext*/
	context={};
	/*#{1JH0RJ1S60PostContext*/
	/*}#1JH0RJ1S60PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1JH0RJ9FE0
		let result=input;
		let missing=false;
		let smartAsk=false;
		/*#{1JH0RJ9FE0PreCodes*/
		/*}#1JH0RJ9FE0PreCodes*/
		if(model===undefined || model==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		/*#{1JH0RJ9FE0PostCodes*/
		const apiUrl = process.env.MODELHUNT_API_URL;
		const basicUrl = `${apiUrl.replace(/\/$/, '')}/api/v1/models/${model}`;
		const response = await fetch(basicUrl)
		if (!response.ok) {
			throw new Error(`Failed to fetch basic information: ${response.status} ${response.statusText}`);
		}
		const Config = await response.json();
		model_type = Config.model_type;
		/*}#1JH0RJ9FE0PostCodes*/
		return {seg:Check,result:(result),preSeg:"1JH0RJ9FE0",outlet:"1JH0RJBUU0"};
	};
	FixArgs.jaxId="1JH0RJ9FE0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1JH0RLRPT0
		let result=input;
		if(model_type==="github"){
			return {seg:Github,result:(input),preSeg:"1JH0RLRPT0",outlet:"1JH0RMESB0"};
		}
		if(model_type==="ollama"){
			return {seg:Ollama,result:(input),preSeg:"1JH0RLRPT0",outlet:"1JH0RLVMT0"};
		}
		return {seg:Openrouter,result:(result),preSeg:"1JH0RLRPT0",outlet:"1JH0RMESD0"};
	};
	Check.jaxId="1JH0RLRPT0"
	Check.url="Check@"+agentURL
	
	segs["Github"]=Github=async function(input){//:1JH0RMOTH0
		let result;
		let arg={model:model};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./ModelAgent.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	Github.jaxId="1JH0RMOTH0"
	Github.url="Github@"+agentURL
	
	segs["Ollama"]=Ollama=async function(input){//:1JH0RMVOO0
		let result;
		let arg={model:model};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./OllamaAgent.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	Ollama.jaxId="1JH0RMVOO0"
	Ollama.url="Ollama@"+agentURL
	
	segs["Openrouter"]=Openrouter=async function(input){//:1JH0RN8MN0
		let result;
		let arg={model:model};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./OpenrouterAgent.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	Openrouter.jaxId="1JH0RN8MN0"
	Openrouter.url="Openrouter@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ModelUse",
		url:agentURL,
		autoStart:true,
		jaxId:"1JH0RJ1S60",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JH0RJ1S60PreEntry*/
			/*}#1JH0RJ1S60PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1JH0RJ1S60PostEntry*/
			/*}#1JH0RJ1S60PostEntry*/
			return result;
		},
		/*#{1JH0RJ1S60MoreAgentAttrs*/
		/*}#1JH0RJ1S60MoreAgentAttrs*/
	};
	/*#{1JH0RJ1S60PostAgent*/
	/*}#1JH0RJ1S60PostAgent*/
	return agent;
};
/*#{1JH0RJ1S60ExCodes*/
/*}#1JH0RJ1S60ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JH0RJ1S60PostDoc*/
/*}#1JH0RJ1S60PostDoc*/


export default ModelUse;
export{ModelUse};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JH0RJ1S60",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JH0RJBV10",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1JH0RJBV11",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JH0RJBV12",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JH0RJPRC0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JH0RJBV13",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JH0RJBV14",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JH0RJBV15",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1JH0RJ9FE0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "260",
//						"y": "290",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1JH0RJBUU0",
//							"attrs": {
//								"id": "Next",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH0RLRPT0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JH0RLRPT0",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "500",
//						"y": "290",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0RMESH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0RMESH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH0RMESD0",
//							"attrs": {
//								"id": "Openrouter",
//								"desc": "Outlet.",
//								"output": ""
//							},
//							"linkedSeg": "1JH0RN8MN0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JH0RMESB0",
//									"attrs": {
//										"id": "Github",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JH0RMESH2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JH0RMESH3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#model_type===\"github\""
//									},
//									"linkedSeg": "1JH0RMOTH0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JH0RLVMT0",
//									"attrs": {
//										"id": "Ollama",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JH0RMESH4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JH0RMESH5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#model_type===\"ollama\""
//									},
//									"linkedSeg": "1JH0RMVOO0"
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
//					"jaxId": "1JH0RMOTH0",
//					"attrs": {
//						"id": "Github",
//						"viewName": "",
//						"label": "",
//						"x": "730",
//						"y": "150",
//						"desc": "Call AI Agent, use it's output as result",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0RNSKH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0RNSKH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/ModelAgent.js",
//						"argument": "#{model:model}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JH0RNSKD0",
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
//					"jaxId": "1JH0RMVOO0",
//					"attrs": {
//						"id": "Ollama",
//						"viewName": "",
//						"label": "",
//						"x": "730",
//						"y": "290",
//						"desc": "Call AI Agent, use it's output as result",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0RNSKH2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0RNSKH3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/OllamaAgent.js",
//						"argument": "#{model:model}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JH0RNSKD1",
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
//					"jaxId": "1JH0RN8MN0",
//					"attrs": {
//						"id": "Openrouter",
//						"viewName": "",
//						"label": "",
//						"x": "730",
//						"y": "450",
//						"desc": "Call AI Agent, use it's output as result",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0RNSKH4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0RNSKH5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/OpenrouterAgent.js",
//						"argument": "#{model:model}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JH0RNSKD2",
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
//				}
//			]
//		},
//		"desc": "This is an AI agent.",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}