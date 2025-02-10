//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IGG8KAGL0MoreImports*/
import fsp from 'fs/promises';
/*}#1IGG8KAGL0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
/*#{1IGG8KAGL0StartDoc*/
/*}#1IGG8KAGL0StartDoc*/
//----------------------------------------------------------------------------
let PrjDoSetupPrj=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let InitEnv,GenGuide,SetupTask;
	let env=globalContext.env;
	let project=globalContext.project;
	let dirPath=project.dirPath;
	let issues=[];
	let setupGuide="";
	let config=session.agentNode.nodeJSON;
	
	/*#{1IGG8KAGL0LocalVals*/
	let bashContent="";
	/*}#1IGG8KAGL0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IGG8KAGL0ParseArgs*/
		/*}#1IGG8KAGL0ParseArgs*/
	}
	
	/*#{1IGG8KAGL0PreContext*/
	/*}#1IGG8KAGL0PreContext*/
	context={};
	/*#{1IGG8KAGL0PostContext*/
	/*}#1IGG8KAGL0PostContext*/
	let agent,segs={};
	segs["InitEnv"]=InitEnv=async function(input){//:1IGG8KL6O0
		let result=input
		/*#{1IGG8KL6O0Code*/
		//Make sure we have readme:
		if(!project.readme){
			let readme;
			readme=await fsp.readFile(pathLib.join(project.dirPath,"README.md"),"utf8");
			if(readme){
				project.readme=readme;
			}
		}
		/*}#1IGG8KL6O0Code*/
		return {seg:GenGuide,result:(result),preSeg:"1IGG8KL6O0",outlet:"1IGG97JSA0"};
	};
	InitEnv.jaxId="1IGG8KL6O0"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["GenGuide"]=GenGuide=async function(input){//:1IH3GKERL0
		let result;
		let sourcePath=pathLib.join(basePath,"./PrjGenSetupGuide.js");
		let arg={};
		/*#{1IH3GKERL0Input*/
		/*}#1IH3GKERL0Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IH3GKERL0Output*/
		setupGuide=result;
		/*}#1IH3GKERL0Output*/
		return {seg:SetupTask,result:(result),preSeg:"1IH3GKERL0",outlet:"1IH3GLG8R0"};
	};
	GenGuide.jaxId="1IH3GKERL0"
	GenGuide.url="GenGuide@"+agentURL
	
	segs["SetupTask"]=SetupTask=async function(input){//:1IHAT14K50
		let result;
		let sourcePath=pathLib.join(basePath,"./SysHandleTask.js");
		let arg={"task":"Setup project","roleTask":"你是一个完善安装、配置软件项目环境的AI，使项目能够运行/测试的AI。注意：你只需要安装配置好工程，不要运行/测试工程。","prjDesc":"","guide":`根据当前项目的README.md文件总结的部署（安装、配置）指南:  \n${setupGuide}\n\n`,"tools":null,"handleIssue":true};
		result= await session.pipeChat(sourcePath,arg,false);
		return {result:result};
	};
	SetupTask.jaxId="1IHAT14K50"
	SetupTask.url="SetupTask@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"PrjDoSetupPrj",
		url:agentURL,
		autoStart:true,
		jaxId:"1IGG8KAGL0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IGG8KAGL0PreEntry*/
			/*}#1IGG8KAGL0PreEntry*/
			result={seg:InitEnv,"input":input};
			/*#{1IGG8KAGL0PostEntry*/
			/*}#1IGG8KAGL0PostEntry*/
			return result;
		},
		/*#{1IGG8KAGL0MoreAgentAttrs*/
		/*}#1IGG8KAGL0MoreAgentAttrs*/
	};
	/*#{1IGG8KAGL0PostAgent*/
	/*}#1IGG8KAGL0PostAgent*/
	return agent;
};
/*#{1IGG8KAGL0ExCodes*/
/*}#1IGG8KAGL0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "PrjDoSetupPrj",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IGG8KAGL0PostDoc*/
/*}#1IGG8KAGL0PostDoc*/


export default PrjDoSetupPrj;
export{PrjDoSetupPrj,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IGG8KAGL0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IGG8KAGL1",
//			"attrs": {
//				"PrjDoSetupPrj": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IGG8KAGL7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IGG8KAGL8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IGG8KAGL9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IGG8KAGL10",
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
//			"jaxId": "1IGG8KAGL2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IGG8KAGL3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IGG8KAGL4",
//			"attrs": {
//				"env": {
//					"type": "auto",
//					"valText": "#globalContext.env"
//				},
//				"project": {
//					"type": "auto",
//					"valText": "#globalContext.project"
//				},
//				"dirPath": {
//					"type": "string",
//					"valText": "#project.dirPath"
//				},
//				"issues": {
//					"type": "auto",
//					"valText": "#[]"
//				},
//				"setupGuide": {
//					"type": "string",
//					"valText": ""
//				},
//				"config": {
//					"type": "auto",
//					"valText": "#session.agentNode.nodeJSON"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IGG8KAGL5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IGG8KAGL6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IGG8KL6O0",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "60",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGG98O610",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGG98O611",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGG97JSA0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3GKERL0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IH3GKERL0",
//					"attrs": {
//						"id": "GenGuide",
//						"viewName": "",
//						"label": "",
//						"x": "280",
//						"y": "265",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH3GLG930",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH3GLG931",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/PrjGenSetupGuide.js",
//						"argument": "#null",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IH3GLG8R0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHAT14K50"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IHAT14K50",
//					"attrs": {
//						"id": "SetupTask",
//						"viewName": "",
//						"label": "",
//						"x": "530",
//						"y": "265",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHAT1T4G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHAT1T4G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysHandleTask.js",
//						"argument": "{\"task\":\"Setup project\",\"roleTask\":\"你是一个完善安装、配置软件项目环境的AI，使项目能够运行/测试的AI。注意：你只需要安装配置好工程，不要运行/测试工程。\",\"prjDesc\":\"\",\"guide\":\"#`根据当前项目的README.md文件总结的部署（安装、配置）指南:  \\\\n${setupGuide}\\\\n\\\\n`\",\"tools\":\"#null\",\"handleIssue\":\"#true\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IHAT1T4D0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "agent.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}