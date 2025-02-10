//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHHHKI540MoreImports*/
/*}#1IHHHKI540MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"address":{
			"name":"address","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"",
		},
		"query":{
			"name":"query","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"",
		},
		"tags":{
			"name":"tags","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IHHHKI540ArgsView*/
	/*}#1IHHHKI540ArgsView*/
};

/*#{1IHHHKI540StartDoc*/
/*}#1IHHHKI540StartDoc*/
//----------------------------------------------------------------------------
let RagQuery=async function(session){
	let address,query,tags;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,init,CallRAG,AskUser,RAGResult,CallAPI;
	let env=globalContext.env;
	let project=globalContext.project;
	let env_info=undefined;
	let project_meta=undefined;
	
	/*#{1IHHHKI540LocalVals*/
	/*}#1IHHHKI540LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			address=input.address;
			query=input.query;
			tags=input.tags;
		}else{
			address=undefined;
			query=undefined;
			tags=undefined;
		}
		/*#{1IHHHKI540ParseArgs*/
		/*}#1IHHHKI540ParseArgs*/
	}
	
	/*#{1IHHHKI540PreContext*/
	/*}#1IHHHKI540PreContext*/
	context={};
	/*#{1IHHHKI540PostContext*/
	/*}#1IHHHKI540PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHHI00QT0
		let result=input;
		let missing=false;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:init,result:(result),preSeg:"1IHHI00QT0",outlet:"1IHHI2CPS0"};
	};
	FixArgs.jaxId="1IHHI00QT0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["init"]=init=async function(input){//:1II8PMOF50
		let result=input
		/*#{1II8PMOF50Code*/
		if(!env){//Test run?
			env={
				platform:"darwin",
				arch: "arm64"
			};
			project={
				name:"testrun",
				url:"github.com/test/run"
			};
			address="http://localhost:222/solution/";
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
		/*}#1II8PMOF50Code*/
		return {seg:CallAPI,result:(result),preSeg:"1II8PMOF50",outlet:"1II8POUBG0"};
	};
	init.jaxId="1II8PMOF50"
	init.url="init@"+agentURL
	
	segs["CallRAG"]=CallRAG=async function(input){//:1IHHI0EN80
		let callVO=null;
		let result=input;
		let rsp=null;
		let url=(address||globalContext.rag.solution)+"retrieve";
		let method="POST";
		let headers={
		};
		/*#{1IHHI0EN80PreCodes*/
		/*}#1IHHI0EN80PreCodes*/
		let json={
			"env_info":env_info,"project_meta":project_meta
		};
		callVO={url:url,method:method,argMode:"JSON",headers:headers,json:json};
		/*#{1IHHI0EN80AboutCall*/
		if(tags){
			json.tags=tags;
		}
		/*}#1IHHI0EN80AboutCall*/
		rsp=await session.webCall(callVO,true,30000);
		if(rsp.code===200){
			result=JSON.parse(rsp.data);
		}else{
			throw Error("Error "+rsp.code+": "+rsp.info||"")
		}
		/*#{1IHHI0EN80AfterCall*/
		/*}#1IHHI0EN80AfterCall*/
		/*#{1IHHI0EN80PostCodes*/
		/*}#1IHHI0EN80PostCodes*/
		return {seg:RAGResult,result:(result),preSeg:"1IHHI0EN80",outlet:"1IHHI2CPU0"};
	};
	CallRAG.jaxId="1IHHI0EN80"
	CallRAG.url="CallRAG@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1IHHI1D4O0
		let tip=(`RAG查询：${query}`);
		let tipRole=("assistant");
		let placeholder=("");
		let text=("");
		let result="";
		/*#{1IHHI1D4O0PreCodes*/
		/*}#1IHHI1D4O0PreCodes*/
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		/*#{1IHHI1D4O0PostCodes*/
		/*}#1IHHI1D4O0PostCodes*/
		return {seg:RAGResult,result:(result),preSeg:"1IHHI1D4O0",outlet:"1IHHI2CPU1"};
	};
	AskUser.jaxId="1IHHI1D4O0"
	AskUser.url="AskUser@"+agentURL
	
	segs["RAGResult"]=RAGResult=async function(input){//:1IHHI1SVR0
		let result=input
		/*#{1IHHI1SVR0Code*/
		console.log(result);
		/*}#1IHHI1SVR0Code*/
		return {result:result};
	};
	RAGResult.jaxId="1IHHI1SVR0"
	RAGResult.url="RAGResult@"+agentURL
	
	segs["CallAPI"]=CallAPI=async function(input){//:1II9OJTMS0
		let result=input
		/*#{1II9OJTMS0Code*/
		let res;
		let json={
			"env_info":env_info,"project_meta":project_meta
		};		
		if(tags){
			json.tags=tags;
		}
		res=await session.callHub("RAGQuery",{apiURL:address,query:json});
		if(!res||res.code!==200){
			result=null;
		}
		result=res.guide||res.result;
		/*}#1II9OJTMS0Code*/
		return {seg:RAGResult,result:(result),preSeg:"1II9OJTMS0",outlet:"1II9OK9PT0"};
	};
	CallAPI.jaxId="1II9OJTMS0"
	CallAPI.url="CallAPI@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"RagQuery",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHHHKI540",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{address,query,tags}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHHHKI540PreEntry*/
			/*}#1IHHHKI540PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHHHKI540PostEntry*/
			/*}#1IHHHKI540PostEntry*/
			return result;
		},
		/*#{1IHHHKI540MoreAgentAttrs*/
		/*}#1IHHHKI540MoreAgentAttrs*/
	};
	/*#{1IHHHKI540PostAgent*/
	/*}#1IHHHKI540PostAgent*/
	return agent;
};
/*#{1IHHHKI540ExCodes*/
/*}#1IHHHKI540ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "RagQuery",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				address:{type:"string",description:""},
				query:{type:"string",description:""},
				tags:{type:"string",description:""}
			}
		}
	}
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
		name:"RagQuery",showName:"RagQuery",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"address":{name:"address",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"query":{name:"query",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"tags":{name:"tags",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","address","query","tags","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["RagQuery"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['address']=");this.genAttrStatement(seg.getAttr("address"));coder.packText(";");coder.newLine();
			coder.packText("args['query']=");this.genAttrStatement(seg.getAttr("query"));coder.packText(";");coder.newLine();
			coder.packText("args['tags']=");this.genAttrStatement(seg.getAttr("tags"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/RagQuery.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
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
/*#{1IHHHKI540PostDoc*/
/*}#1IHHHKI540PostDoc*/


export default RagQuery;
export{RagQuery,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHHHKI540",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHHHKI541",
//			"attrs": {
//				"RagQuery": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHHHKI547",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHHHKI548",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHHHKI549",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHHHKI5410",
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
//			"jaxId": "1IHHHKI542",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHHHKI543",
//			"attrs": {
//				"address": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1II8PJBEB0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				},
//				"query": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHHI2CPV0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				},
//				"tags": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHHI2CPV1",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHHHKI544",
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
//					"valText": ""
//				},
//				"project_meta": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IHHHKI545",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHHHKI546",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHHI00QT0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "85",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHHI2CPS0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II8PMOF50"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1II8PMOF50",
//					"attrs": {
//						"id": "init",
//						"viewName": "",
//						"label": "",
//						"x": "285",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II8POUBH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II8POUBH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1II8POUBG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II9OJTMS0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "webCall",
//					"jaxId": "1IHHI0EN80",
//					"attrs": {
//						"id": "CallRAG",
//						"viewName": "",
//						"label": "",
//						"x": "455",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHHI2CPV2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHI2CPV3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"url": "#(address||globalContext.rag.solution)+\"retrieve\"",
//						"method": "POST",
//						"argMode": "JOSN",
//						"format": "JOSN",
//						"args": {
//							"jaxId": "1IHHI2CPV4",
//							"attrs": {
//								"env_info": {
//									"type": "auto",
//									"valText": "#env_info"
//								},
//								"project_meta": {
//									"type": "auto",
//									"valText": "#project_meta"
//								}
//							}
//						},
//						"text": "",
//						"timeout": "30000",
//						"headers": {
//							"jaxId": "1IHHI2CPV5",
//							"attrs": {}
//						},
//						"outlet": {
//							"jaxId": "1IHHI2CPU0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHI1SVR0"
//						}
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IHHI1D4O0",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "455",
//						"y": "175",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHHI2CPV6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHI2CPV7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#`RAG查询：${query}`",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IHHI2CPU1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHI1SVR0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHHI1SVR0",
//					"attrs": {
//						"id": "RAGResult",
//						"viewName": "",
//						"label": "",
//						"x": "650",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHHI2CPV8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHI2CPV9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHHI2CPU2",
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
//					"jaxId": "1II9OJTMS0",
//					"attrs": {
//						"id": "CallAPI",
//						"viewName": "",
//						"label": "",
//						"x": "455",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II9OK9Q30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II9OK9Q31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1II9OK9PT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHI1SVR0"
//						},
//						"result": "#input"
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