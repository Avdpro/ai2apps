//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IJ44VPHU0MoreImports*/
/*}#1IJ44VPHU0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"string",
			"defaultValue":"",
			"desc":"要下载的模型，通常格式为：<username>/<model_name>",
		},
		"localPath":{
			"name":"localPath","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"如果要下载到本地目录，目标目录路径",
		}
	},
	/*#{1IJ44VPHU0ArgsView*/
	/*}#1IJ44VPHU0ArgsView*/
};

/*#{1IJ44VPHU0StartDoc*/
/*}#1IJ44VPHU0StartDoc*/
//----------------------------------------------------------------------------
let ToolHfModel=async function(session){
	let model,localPath;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Drownload;
	/*#{1IJ44VPHU0LocalVals*/
	/*}#1IJ44VPHU0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
			localPath=input.localPath;
		}else{
			model=undefined;
			localPath=undefined;
		}
		/*#{1IJ44VPHU0ParseArgs*/
		/*}#1IJ44VPHU0ParseArgs*/
	}
	
	/*#{1IJ44VPHU0PreContext*/
	/*}#1IJ44VPHU0PreContext*/
	context={};
	/*#{1IJ44VPHU0PostContext*/
	/*}#1IJ44VPHU0PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IJ45019V0
		let result=input;
		let missing=false;
		if(model===undefined || model==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:Drownload,result:(result),preSeg:"1IJ45019V0",outlet:"1IJ45342I0"};
	};
	FixArgs.jaxId="1IJ45019V0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Drownload"]=Drownload=async function(input){//:1IJ45B6Q50
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=localPath?[`huggingface-cli download ${model}`,`huggingface-cli download ${model} --local-dir ${localPath}`]:`huggingface-cli download ${model}`
;
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {result:result};
	};
	Drownload.jaxId="1IJ45B6Q50"
	Drownload.url="Drownload@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolHfModel",
		url:agentURL,
		autoStart:true,
		jaxId:"1IJ44VPHU0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model,localPath}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IJ44VPHU0PreEntry*/
			/*}#1IJ44VPHU0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IJ44VPHU0PostEntry*/
			/*}#1IJ44VPHU0PostEntry*/
			return result;
		},
		/*#{1IJ44VPHU0MoreAgentAttrs*/
		/*}#1IJ44VPHU0MoreAgentAttrs*/
	};
	/*#{1IJ44VPHU0PostAgent*/
	/*}#1IJ44VPHU0PostAgent*/
	return agent;
};
/*#{1IJ44VPHU0ExCodes*/
/*}#1IJ44VPHU0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolHfModel",
		description: "这是通过huggingface下载模型的智能体，如果需要下载模型，请使用本智能体，而不是直接通过命令行下载。",
		parameters:{
			type: "object",
			properties:{
				model:{type:"string",description:"要下载的模型，通常格式为：<username>/<model_name>"},
				localPath:{type:"string",description:"如果要下载到本地目录，目标目录路径"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IJ44VPHU0PostDoc*/
/*}#1IJ44VPHU0PostDoc*/


export default ToolHfModel;
export{ToolHfModel,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IJ44VPHU0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IJ44VPHV0",
//			"attrs": {
//				"ToolHfModel": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IJ44VPHV6",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IJ44VPHV7",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IJ44VPHV8",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IJ44VPHV9",
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
//			"jaxId": "1IJ44VPHV1",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IJ44VPHV2",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ45A5LC0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要下载的模型，通常格式为：<username>/<model_name>"
//					}
//				},
//				"localPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ45A5LC1",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "如果要下载到本地目录，目标目录路径",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IJ44VPHV3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IJ44VPHV4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IJ44VPHV5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IJ45019V0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "95",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IJ45342I0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ45B6Q50"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IJ45B6Q50",
//					"attrs": {
//						"id": "Drownload",
//						"viewName": "",
//						"label": "",
//						"x": "300",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ45SKMC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ45SKMC2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#localPath?[`huggingface-cli download ${model}`,`huggingface-cli download ${model} --local-dir ${localPath}`]:`huggingface-cli download ${model}`\n",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IJ45SKMC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "terminal.svg"
//				}
//			]
//		},
//		"desc": "这是通过huggingface下载模型的智能体，如果需要下载模型，请使用本智能体，而不是直接通过命令行下载。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}