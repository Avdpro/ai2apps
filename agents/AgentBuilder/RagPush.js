//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHHJA1210MoreImports*/
/*}#1IHHJA1210MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"address":{
			"name":"address","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"RAG服务API地址",
		},
		"doc":{
			"name":"doc","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"要提交的文档文本内容",
		},
		"desc":{
			"name":"desc","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"文档问题的简单说明",
		},
		"tags":{
			"name":"tags","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"标签，标签词之间用逗号隔开",
		}
	},
	/*#{1IHHJA1210ArgsView*/
	/*}#1IHHJA1210ArgsView*/
};

/*#{1IHHJA1210StartDoc*/
/*}#1IHHJA1210StartDoc*/
//----------------------------------------------------------------------------
let RagPush=async function(session){
	let address,doc,desc,tags;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArg,InitArgs,AddNote,CallRAG,CallAPI,RAGResult;
	let env=globalContext.env;
	let project=globalContext.project;
	let env_info=null;
	let project_meta=null;
	
	/*#{1IHHJA1210LocalVals*/
	/*}#1IHHJA1210LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			address=input.address;
			doc=input.doc;
			desc=input.desc;
			tags=input.tags;
		}else{
			address=undefined;
			doc=undefined;
			desc=undefined;
			tags=undefined;
		}
		/*#{1IHHJA1210ParseArgs*/
		/*}#1IHHJA1210ParseArgs*/
	}
	
	/*#{1IHHJA1210PreContext*/
	/*}#1IHHJA1210PreContext*/
	context={};
	/*#{1IHHJA1210PostContext*/
	/*}#1IHHJA1210PostContext*/
	let agent,segs={};
	segs["FixArg"]=FixArg=async function(input){//:1IHHJE2E20
		let result=input;
		let missing=false;
		if(doc===undefined || doc==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:InitArgs,result:(result),preSeg:"1IHHJE2E20",outlet:"1IHHJFULG0"};
	};
	FixArg.jaxId="1IHHJE2E20"
	FixArg.url="FixArg@"+agentURL
	
	segs["InitArgs"]=InitArgs=async function(input){//:1II9JKEPB0
		let result=input
		/*#{1II9JKEPB0Code*/
		if(!env){//Test run?
			env={
				platform:"darwin",
				arch: "arm64"
			};
			project={
				name:"testrun",
				url:"github.com/test/run"
			};
			address="http://localhost:222/solution/index";
		}
		env_info={
			platform:env.platform,
			arch:env.arch
		};
		project_meta={
			name:project.name,
			url:project.url,
			owner:project.owner,
			repo:project.repo,
			git_url:project.gitURL
		};
		if(tags){
			tags=tags.split(",");
		}
		/*}#1II9JKEPB0Code*/
		return {seg:AddNote,result:(result),preSeg:"1II9JKEPB0",outlet:"1II9JQD140"};
	};
	InitArgs.jaxId="1II9JKEPB0"
	InitArgs.url="InitArgs@"+agentURL
	
	segs["AddNote"]=AddNote=async function(input){//:1IHHJEFSF0
		let result=input
		/*#{1IHHJEFSF0Code*/
		let note;
		note={
			desc:desc,
			doc:doc,
			env:{
				platform:env.platform,
				arch:env.arch
			},
			project:{
				name:project.name,
				url:project.url
			},
			tags:tags
		};
		try{
			session.callClient("AddNote",{note:note});
		}catch(err){
			//Ignore err
		}
		/*}#1IHHJEFSF0Code*/
		return {seg:RAGResult,result:(result),preSeg:"1IHHJEFSF0",outlet:"1IHHJFULH0"};
	};
	AddNote.jaxId="1IHHJEFSF0"
	AddNote.url="AddNote@"+agentURL
	
	segs["CallRAG"]=CallRAG=async function(input){//:1IHHJF4JJ0
		let callVO=null;
		let result=input;
		let rsp=null;
		let url=address||(globalContext.rag.solution+"index");
		let method="POST";
		let headers={
		};
		/*#{1IHHJF4JJ0PreCodes*/
		/*}#1IHHJF4JJ0PreCodes*/
		let json={
			"env_info":env_info,"project_meta":project_meta,"procedure":doc
		};
		callVO={url:url,method:method,argMode:"JSON",headers:headers,json:json};
		/*#{1IHHJF4JJ0AboutCall*/
		if(tags){
			json.tags=tags;
		}
		/*}#1IHHJF4JJ0AboutCall*/
		rsp=await session.webCall(callVO,true,30000);
		if(rsp.code===200){
			result=JSON.parse(rsp.data);
		}else{
			throw Error("Error "+rsp.code+": "+rsp.info||"")
		}
		/*#{1IHHJF4JJ0AfterCall*/
		/*}#1IHHJF4JJ0AfterCall*/
		/*#{1IHHJF4JJ0PostCodes*/
		/*}#1IHHJF4JJ0PostCodes*/
		return {seg:RAGResult,result:(result),preSeg:"1IHHJF4JJ0",outlet:"1IHHJFULH1"};
	};
	CallRAG.jaxId="1IHHJF4JJ0"
	CallRAG.url="CallRAG@"+agentURL
	
	segs["CallAPI"]=CallAPI=async function(input){//:1II9R48KO0
		let result=input
		/*#{1II9R48KO0Code*/
		/*}#1II9R48KO0Code*/
		return {seg:RAGResult,result:(result),preSeg:"1II9R48KO0",outlet:"1II9R4M5B0"};
	};
	CallAPI.jaxId="1II9R48KO0"
	CallAPI.url="CallAPI@"+agentURL
	
	segs["RAGResult"]=RAGResult=async function(input){//:1IHHJFKF10
		let result=input
		/*#{1IHHJFKF10Code*/
		/*}#1IHHJFKF10Code*/
		return {result:result};
	};
	RAGResult.jaxId="1IHHJFKF10"
	RAGResult.url="RAGResult@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"RagPush",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHHJA1210",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{address,doc,desc,tags}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHHJA1210PreEntry*/
			/*}#1IHHJA1210PreEntry*/
			result={seg:FixArg,"input":input};
			/*#{1IHHJA1210PostEntry*/
			/*}#1IHHJA1210PostEntry*/
			return result;
		},
		/*#{1IHHJA1210MoreAgentAttrs*/
		/*}#1IHHJA1210MoreAgentAttrs*/
	};
	/*#{1IHHJA1210PostAgent*/
	/*}#1IHHJA1210PostAgent*/
	return agent;
};
/*#{1IHHJA1210ExCodes*/
/*}#1IHHJA1210ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "RagPush",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				address:{type:"string",description:"RAG服务API地址"},
				doc:{type:"string",description:"要提交的文档文本内容"},
				desc:{type:"string",description:"文档问题的简单说明"},
				tags:{type:"string",description:"标签，标签词之间用逗号隔开"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IHHJA1210PostDoc*/
/*}#1IHHJA1210PostDoc*/


export default RagPush;
export{RagPush,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHHJA1210",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHHJA1211",
//			"attrs": {
//				"RagPush": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHHJA1217",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHHJA1218",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHHJA1219",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHHJA12110",
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
//			"jaxId": "1IHHJA1212",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHHJA1213",
//			"attrs": {
//				"address": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1II9JQD160",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "RAG服务API地址",
//						"required": "false"
//					}
//				},
//				"doc": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHHJDI2E1",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要提交的文档文本内容",
//						"required": "true"
//					}
//				},
//				"desc": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHHJDI2E0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "文档问题的简单说明",
//						"required": "false"
//					}
//				},
//				"tags": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHHJDI2E2",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "标签，标签词之间用逗号隔开",
//						"label": "",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHHJA1214",
//			"attrs": {
//				"env": {
//					"type": "auto",
//					"valText": "#globalContext.env"
//				},
//				"project": {
//					"type": "auto",
//					"valText": "#globalContext.project"
//				},
//				"env_info": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"project_meta": {
//					"type": "auto",
//					"valText": "null"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IHHJA1215",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHHJA1216",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHHJE2E20",
//					"attrs": {
//						"id": "FixArg",
//						"viewName": "",
//						"label": "",
//						"x": "95",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHHJFULG0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II9JKEPB0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1II9JKEPB0",
//					"attrs": {
//						"id": "InitArgs",
//						"viewName": "",
//						"label": "",
//						"x": "280",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II9JQD170",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II9JQD171",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1II9JQD140",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHJEFSF0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHHJEFSF0",
//					"attrs": {
//						"id": "AddNote",
//						"viewName": "",
//						"label": "",
//						"x": "495",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHHJFULI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHJFULI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHHJFULH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHJFKF10"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "webCall",
//					"jaxId": "1IHHJF4JJ0",
//					"attrs": {
//						"id": "CallRAG",
//						"viewName": "",
//						"label": "",
//						"x": "495",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHHJFULI2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHJFULI3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"url": "#address||(globalContext.rag.solution+\"index\")",
//						"method": "POST",
//						"argMode": "JOSN",
//						"format": "JOSN",
//						"args": {
//							"jaxId": "1IHHJFULI4",
//							"attrs": {
//								"env_info": {
//									"type": "auto",
//									"valText": "#env_info"
//								},
//								"project_meta": {
//									"type": "auto",
//									"valText": "#project_meta"
//								},
//								"procedure": {
//									"type": "string",
//									"valText": "#doc"
//								}
//							}
//						},
//						"text": "",
//						"timeout": "30000",
//						"headers": {
//							"jaxId": "1IHHJFULI5",
//							"attrs": {}
//						},
//						"outlet": {
//							"jaxId": "1IHHJFULH1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHJFKF10"
//						}
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1II9R48KO0",
//					"attrs": {
//						"id": "CallAPI",
//						"viewName": "",
//						"label": "",
//						"x": "495",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II9R4M5G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II9R4M5G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1II9R4M5B0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHJFKF10"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHHJFKF10",
//					"attrs": {
//						"id": "RAGResult",
//						"viewName": "",
//						"label": "",
//						"x": "730",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHHJFULI6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHJFULI7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHHJFULH2",
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
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}