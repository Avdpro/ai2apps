//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IMT36Q810MoreImports*/
/*}#1IMT36Q810MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"callPrompt":{
			"name":"callPrompt","type":"string",
			"defaultValue":"",
			"desc":"用户关于输入图片的问题",
		},
		"images":{
			"name":"images","type":"auto",
			"defaultValue":"",
			"desc":"字符串数组，每一项是一张输入图片的URL字符串。",
		},
		"returnJSON":{
			"name":"returnJSON","type":"bool",
			"required":false,
			"defaultValue":false,
			"desc":"",
		}
	},
	/*#{1IMT36Q810ArgsView*/
	/*}#1IMT36Q810ArgsView*/
};

/*#{1IMT36Q810StartDoc*/
/*}#1IMT36Q810StartDoc*/
//----------------------------------------------------------------------------
let ToolReadImage=async function(session){
	let callPrompt,images,returnJSON;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,CallLLM;
	/*#{1IMT36Q810LocalVals*/
	/*}#1IMT36Q810LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			callPrompt=input.callPrompt;
			images=input.images;
			returnJSON=input.returnJSON;
		}else{
			callPrompt=undefined;
			images=undefined;
			returnJSON=undefined;
		}
		/*#{1IMT36Q810ParseArgs*/
		/*}#1IMT36Q810ParseArgs*/
	}
	
	/*#{1IMT36Q810PreContext*/
	/*}#1IMT36Q810PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IMT36Q810PostContext*/
	/*}#1IMT36Q810PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IMT3BKBI0
		let result=input;
		let missing=false;
		if(callPrompt===undefined || callPrompt==="") missing=true;
		if(images===undefined || images==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@aichat/ai/CompleteArgs.js",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:CallLLM,result:(result),preSeg:"1IMT3BKBI0",outlet:"1IMT3CGNM0"};
	};
	FixArgs.jaxId="1IMT3BKBI0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["CallLLM"]=CallLLM=async function(input){//:1IMT3C5M40
		let prompt;
		let result=null;
		/*#{1IMT3C5M40Input*/
		/*}#1IMT3C5M40Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=CallLLM.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你是一个根据用户指令和输入的图片内容，做出回复的AI"},
		];
		/*#{1IMT3C5M40PrePrompt*/
		if(returnJSON){
			opts.responseFormat="json_object";
		}
		/*}#1IMT3C5M40PrePrompt*/
		prompt=callPrompt;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IMT3C5M40FilterMessage*/
			if(images){
				let content=[{type:"text",text:prompt}];
				for(let url of images){
					if(url.startsWith("hub://")){
						url=await session.normURL(url);
					}
					content.push({type:"image_url","image_url":{"url":url}});
				}
				msg={role:"user",content:content};
			}
			/*}#1IMT3C5M40FilterMessage*/
			messages.push(msg);
		}
		/*#{1IMT3C5M40PreCall*/
		/*}#1IMT3C5M40PreCall*/
		result=(result===null)?(await session.callSegLLM("CallLLM@"+agentURL,opts,messages,true)):result;
		/*#{1IMT3C5M40PostCall*/
		result={result:"Finish",content:result};
		/*}#1IMT3C5M40PostCall*/
		return {result:result};
	};
	CallLLM.jaxId="1IMT3C5M40"
	CallLLM.url="CallLLM@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolReadImage",
		url:agentURL,
		autoStart:true,
		jaxId:"1IMT36Q810",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{callPrompt,images,returnJSON}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IMT36Q810PreEntry*/
			/*}#1IMT36Q810PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IMT36Q810PostEntry*/
			/*}#1IMT36Q810PostEntry*/
			return result;
		},
		/*#{1IMT36Q810MoreAgentAttrs*/
		/*}#1IMT36Q810MoreAgentAttrs*/
	};
	/*#{1IMT36Q810PostAgent*/
	/*}#1IMT36Q810PostAgent*/
	return agent;
};
/*#{1IMT36Q810ExCodes*/
/*}#1IMT36Q810ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "ToolReadImage",
		description: "读取一张或多张图片内容，回答用户有关图片内容的问题的智能体",
		parameters:{
			type: "object",
			properties:{
				callPrompt:{type:"string",description:"用户关于输入图片的问题"},
				images:{type:"auto",description:"字符串数组，每一项是一张输入图片的URL字符串。"},
				returnJSON:{type:"bool",description:""}
			}
		}
	},
	label: "{\"EN\":\"Analyze Image\",\"CN\":\"分析图片\"}",
	chatEntry: "Tool",
	icon: "yulan.svg",
	agent: ToolReadImage
}];
//#CodyExport<<<
/*#{1IMT36Q810PostDoc*/
/*}#1IMT36Q810PostDoc*/


export default ToolReadImage;
export{ToolReadImage};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IMT36Q810",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IMT36Q811",
//			"attrs": {
//				"ToolReadImage": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IMT36Q817",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IMT36Q818",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IMT36Q819",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IMT36Q8110",
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
//			"jaxId": "1IMT36Q812",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IMT36Q813",
//			"attrs": {
//				"callPrompt": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IMT3BCF90",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "用户关于输入图片的问题"
//					}
//				},
//				"images": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IMT3BCF91",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "字符串数组，每一项是一张输入图片的URL字符串。"
//					}
//				},
//				"returnJSON": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IMTQ2PP50",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "false",
//						"desc": "",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IMT36Q814",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IMT36Q815",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IMT36Q816",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IMT3BKBI0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "115",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IMT3CGNM0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMT3C5M40"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IMT3C5M40",
//					"attrs": {
//						"id": "CallLLM",
//						"viewName": "",
//						"label": "",
//						"x": "310",
//						"y": "265",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMT3CGNN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMT3CGNN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o-mini",
//						"system": "你是一个根据用户指令和输入的图片内容，做出回复的AI",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#callPrompt",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IMT3CGNM1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
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
//						"responseFormat": "text",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				}
//			]
//		},
//		"desc": "读取一张或多张图片内容，回答用户有关图片内容的问题的智能体",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"{\\\"EN\\\":\\\"Analyze Image\\\",\\\"CN\\\":\\\"分析图片\\\"}\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":\"Tool\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"yulan.svg\",\"catalog\":\"AI Call\"}"
//	}
//}