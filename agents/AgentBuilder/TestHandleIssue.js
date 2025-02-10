//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHVKQAT90MoreImports*/
/*}#1IHVKQAT90MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
/*#{1IHVKQAT90StartDoc*/
import AATask from "./Task.js";
/*}#1IHVKQAT90StartDoc*/
//----------------------------------------------------------------------------
let TestHandleIssue=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let InitPrj,InitEnv,InitIsuue,HandleIssue;
	let project=null;
	let env=null;
	let task=null;
	let issue=null;
	
	/*#{1IHVKQAT90LocalVals*/
	/*}#1IHVKQAT90LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IHVKQAT90ParseArgs*/
		/*}#1IHVKQAT90ParseArgs*/
	}
	
	/*#{1IHVKQAT90PreContext*/
	/*}#1IHVKQAT90PreContext*/
	context={};
	/*#{1IHVKQAT90PostContext*/
	/*}#1IHVKQAT90PostContext*/
	let agent,segs={};
	segs["InitPrj"]=InitPrj=async function(input){//:1IHVKRN9B0
		let result=input
		/*#{1IHVKRN9B0Code*/
		project={
			owner:"Avdpro",
			repo:"ai2apps",
			branch:"main",
			name:"ai2apps",
			url:"https://github.com/Avdpro/ai2apps",
			gitURL:"https://github.com/Avdpro/ai2apps.git",
			rawURL:"https://raw.githubusercontent.com/Avdpro/ai2apps/refs/heads/main",
			dirPath:"/Users/avdpropang/sdk/cchome/home/agents/AgentBuilder/projects/ai2apps",
			requirements:{node:true,python:false},
			conda:"base",
			venv:false,
			progress:[
				"已从GitHub下载了项目",
			]
		};
		globalContext.project=project;
		task=new AATask(session,"测试ai2apps项目",null);
		task.log(`Bash commands: node start.mjs
		node:internal/modules/cjs/loader:1147
		throw err;
		^
		
		Error: Cannot find module '/Users/avdpropang/sdk/cchome/home/agents/AgentBuilder/projects/ai2apps/start.mjs'
		at Module._resolveFilename (node:internal/modules/cjs/loader:1144:15)
		at Module._load (node:internal/modules/cjs/loader:985:27)
		at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:135:12)
		at node:internal/main/run_main_module:28:49 {
		code: 'MODULE_NOT_FOUND',
		requireStack: []
		}
		
		Node.js v20.11.0`,"bash");
		/*}#1IHVKRN9B0Code*/
		return {seg:InitEnv,result:(result),preSeg:"1IHVKRN9B0",outlet:"1IHVMPNED1"};
	};
	InitPrj.jaxId="1IHVKRN9B0"
	InitPrj.url="InitPrj@"+agentURL
	
	segs["InitEnv"]=InitEnv=async function(input){//:1IHVPCVRL0
		let result;
		let sourcePath=pathLib.join(basePath,"./SysInitWorkEnv.js");
		let arg={};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:InitIsuue,result:(result),preSeg:"1IHVPCVRL0",outlet:"1IHVPCVRL3"};
	};
	InitEnv.jaxId="1IHVPCVRL0"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["InitIsuue"]=InitIsuue=async function(input){//:1IHVKS3JS0
		let result=input
		/*#{1IHVKS3JS0Code*/
		env=globalContext.env;
		issue={
			issue:"启动ai2apps的时候node报错，说找不到start.mjs",
			issueBrief:"无法启动ai2apps"
		};
		result=issue;
		/*}#1IHVKS3JS0Code*/
		return {seg:HandleIssue,result:(result),preSeg:"1IHVKS3JS0",outlet:"1IHVMPNED2"};
	};
	InitIsuue.jaxId="1IHVKS3JS0"
	InitIsuue.url="InitIsuue@"+agentURL
	
	segs["HandleIssue"]=HandleIssue=async function(input){//:1IHVKSE6D0
		let result;
		let sourcePath=pathLib.join(basePath,"./SysHandleIssue.js");
		let arg={"issue":input.issue,"issueBrief":input.issueBrief};
		result= await session.pipeChat(sourcePath,arg,false);
		return {result:result};
	};
	HandleIssue.jaxId="1IHVKSE6D0"
	HandleIssue.url="HandleIssue@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"TestHandleIssue",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHVKQAT90",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IHVKQAT90PreEntry*/
			/*}#1IHVKQAT90PreEntry*/
			result={seg:InitPrj,"input":input};
			/*#{1IHVKQAT90PostEntry*/
			/*}#1IHVKQAT90PostEntry*/
			return result;
		},
		/*#{1IHVKQAT90MoreAgentAttrs*/
		/*}#1IHVKQAT90MoreAgentAttrs*/
	};
	/*#{1IHVKQAT90PostAgent*/
	/*}#1IHVKQAT90PostAgent*/
	return agent;
};
/*#{1IHVKQAT90ExCodes*/
/*}#1IHVKQAT90ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IHVKQAT90PostDoc*/
/*}#1IHVKQAT90PostDoc*/


export default TestHandleIssue;
export{TestHandleIssue};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHVKQAT90",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHVKQAT91",
//			"attrs": {
//				"TestHandleIssue": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHVKQAT97",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHVKQAT98",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHVKQAT99",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHVKQAT910",
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
//			"jaxId": "1IHVKQAT92",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHVKQAT93",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IHVKQAT94",
//			"attrs": {
//				"project": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"env": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"task": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"issue": {
//					"type": "auto",
//					"valText": "null"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IHVKQAT95",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHVKQAT96",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHVKRN9B0",
//					"attrs": {
//						"id": "InitPrj",
//						"viewName": "",
//						"label": "",
//						"x": "85",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHVMPNEF2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHVMPNEF3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHVMPNED1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHVPCVRL0"
//						},
//						"result": "#input"
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IHVPCVRL0",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "295",
//						"y": "240",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHVPCVRL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHVPCVRL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysInitWorkEnv.js",
//						"argument": "{}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IHVPCVRL3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHVKS3JS0"
//						}
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHVKS3JS0",
//					"attrs": {
//						"id": "InitIsuue",
//						"viewName": "",
//						"label": "",
//						"x": "515",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHVMPNEF4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHVMPNEF5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHVMPNED2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHVKSE6D0"
//						},
//						"result": "#input"
//					}
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IHVKSE6D0",
//					"attrs": {
//						"id": "HandleIssue",
//						"viewName": "",
//						"label": "",
//						"x": "740",
//						"y": "240",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHVMPNEF6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHVMPNEF7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysHandleIssue.js",
//						"argument": "{\"issue\":\"#input.issue\",\"issueBrief\":\"#input.issueBrief\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IHVMPNED3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					}
//				}
//			]
//		},
//		"desc": "这是专门用来测试HandleIssue智能体的智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}