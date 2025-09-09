//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1J3030O8J0MoreImports*/
import fsp from 'fs/promises';
/*}#1J3030O8J0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"input_type":{
			"name":"input_type","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"",
		},
		"output_type":{
			"name":"output_type","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"",
		},
		"input_content":{
			"name":"input_content","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"api":{
			"name":"api","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"output_path":{
			"name":"output_path","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1J3030O8J0ArgsView*/
	/*}#1J3030O8J0ArgsView*/
};

/*#{1J3030O8J0StartDoc*/
/*}#1J3030O8J0StartDoc*/
//----------------------------------------------------------------------------
let AutoAPI=async function(session){
	let input_type,output_type,input_content,api,output_path;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Call,Output,OutputText,SaveFile,CheckSuccess,OutputFail,Read,OutputError,OutputSuccess,OutputFile;
	/*#{1J3030O8J0LocalVals*/
	let output, error="";
	/*}#1J3030O8J0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			input_type=input.input_type;
			output_type=input.output_type;
			input_content=input.input_content;
			api=input.api;
			output_path=input.output_path;
		}else{
			input_type=undefined;
			output_type=undefined;
			input_content=undefined;
			api=undefined;
			output_path=undefined;
		}
		/*#{1J3030O8J0ParseArgs*/
		/*}#1J3030O8J0ParseArgs*/
	}
	
	/*#{1J3030O8J0PreContext*/
	/*}#1J3030O8J0PreContext*/
	context={};
	/*#{1J3030O8J0PostContext*/
	/*}#1J3030O8J0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1J30345RS0
		let result=input;
		let missing=false;
		let smartAsk=false;
		/*#{1J30345RS0PreCodes*/
		/*}#1J30345RS0PreCodes*/
		if(input_type===undefined || input_type==="") missing=true;
		if(output_type===undefined || output_type==="") missing=true;
		if(input_content===undefined || input_content==="") missing=true;
		if(api===undefined || api==="") missing=true;
		if(output_path===undefined || output_path==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		/*#{1J30345RS0PostCodes*/
		if(input_type === "image" || input_type === "file"){
			if(input_content.startsWith("hub:")){
				input_content = await session.getHubPath(input_content);
			}
		}
		/*}#1J30345RS0PostCodes*/
		return {seg:Call,result:(result),preSeg:"1J30345RS0",outlet:"1J30348R50"};
	};
	FixArgs.jaxId="1J30345RS0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Call"]=Call=async function(input){//:1J30386FV0
		let result;
		let arg={input:input_content, output_path:output_path, timeout:300};
		let server=("http://127.0.0.1:8082")||null;
		let tool=`${api}`;
		/*#{1J30386FV0Input*/
		/*}#1J30386FV0Input*/
		result= await fetch(`http://127.0.0.1:8082/dynamic${tool}`,{method: 'POST',headers: {'Content-Type': 'application/json'},body: JSON.stringify(arg)});
		/*#{1J30386FV0Output*/
		result = await result.json();
		if(result.success){
			output=result.output;
		}
		else{
			output="fail";
			error=result.error;
		}
		/*}#1J30386FV0Output*/
		return {seg:CheckSuccess,result:(result),preSeg:"1J30386FV0",outlet:"1J3046RL03"};
	};
	Call.jaxId="1J30386FV0"
	Call.url="Call@"+agentURL
	
	segs["Output"]=Output=async function(input){//:1J304NKR00
		let result=input;
		if(output_type==="text"){
			return {seg:Read,result:(input),preSeg:"1J304NKR00",outlet:"1J304UGP90"};
		}
		if(output_type==="filePath"){
			return {seg:OutputFile,result:(input),preSeg:"1J304NKR00",outlet:"1J304NSJU0"};
		}
		return {result:result};
	};
	Output.jaxId="1J304NKR00"
	Output.url="Output@"+agentURL
	
	segs["OutputText"]=OutputText=async function(input){//:1J30CP6CF0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:SaveFile,result:(result),preSeg:"1J30CP6CF0",outlet:"1J30CU5M53"};
	};
	OutputText.jaxId="1J30CP6CF0"
	OutputText.url="OutputText@"+agentURL
	
	segs["SaveFile"]=SaveFile=async function(input){//:1J49J1FSF0
		let result=input
		/*#{1J49J1FSF0Code*/
		let data = await fsp.readFile(output_path);
		result = await session.saveHubFile(pathLib.basename(output_path),data);
		/*}#1J49J1FSF0Code*/
		return {result:result};
	};
	SaveFile.jaxId="1J49J1FSF0"
	SaveFile.url="SaveFile@"+agentURL
	
	segs["CheckSuccess"]=CheckSuccess=async function(input){//:1J4CA9GL80
		let result=input;
		if(output==="fail"){
			return {seg:OutputFail,result:(input),preSeg:"1J4CA9GL80",outlet:"1J4CAB04E0"};
		}
		return {seg:OutputSuccess,result:(result),preSeg:"1J4CA9GL80",outlet:"1J4CAB04E1"};
	};
	CheckSuccess.jaxId="1J4CA9GL80"
	CheckSuccess.url="CheckSuccess@"+agentURL
	
	segs["OutputFail"]=OutputFail=async function(input){//:1J4CABOIB0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("调用失败"):("Call failed"));
		session.addChatText(role,content,opts);
		return {seg:OutputError,result:(result),preSeg:"1J4CABOIB0",outlet:"1J4CACUAM0"};
	};
	OutputFail.jaxId="1J4CABOIB0"
	OutputFail.url="OutputFail@"+agentURL
	
	segs["Read"]=Read=async function(input){//:1J4CO7C6B0
		let result=input
		/*#{1J4CO7C6B0Code*/
		result=await fsp.readFile(output_path,'utf-8');
		/*}#1J4CO7C6B0Code*/
		return {seg:OutputText,result:(result),preSeg:"1J4CO7C6B0",outlet:"1J4CO7OS00"};
	};
	Read.jaxId="1J4CO7C6B0"
	Read.url="Read@"+agentURL
	
	segs["OutputError"]=OutputError=async function(input){//:1J4COEKDM0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=error;
		session.addChatText(role,content,opts);
		return {result:result};
	};
	OutputError.jaxId="1J4COEKDM0"
	OutputError.url="OutputError@"+agentURL
	
	segs["OutputSuccess"]=OutputSuccess=async function(input){//:1J4EMUL600
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("调用成功"):("Call success"));
		session.addChatText(role,content,opts);
		return {seg:Output,result:(result),preSeg:"1J4EMUL600",outlet:"1J4EN0SA60"};
	};
	OutputSuccess.jaxId="1J4EMUL600"
	OutputSuccess.url="OutputSuccess@"+agentURL
	
	segs["OutputFile"]=OutputFile=async function(input){//:1J4ENDTIU0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("请从右边File下载文件"):("Please download the file from the File on the right"));
		session.addChatText(role,content,opts);
		return {seg:SaveFile,result:(result),preSeg:"1J4ENDTIU0",outlet:"1J4ENEOL60"};
	};
	OutputFile.jaxId="1J4ENDTIU0"
	OutputFile.url="OutputFile@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"AutoAPI",
		url:agentURL,
		autoStart:true,
		jaxId:"1J3030O8J0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{input_type,output_type,input_content,api,output_path}*/){
			let result;
			parseAgentArgs(input);
			/*#{1J3030O8J0PreEntry*/
			/*}#1J3030O8J0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1J3030O8J0PostEntry*/
			/*}#1J3030O8J0PostEntry*/
			return result;
		},
		/*#{1J3030O8J0MoreAgentAttrs*/
		/*}#1J3030O8J0MoreAgentAttrs*/
	};
	/*#{1J3030O8J0PostAgent*/
	/*}#1J3030O8J0PostAgent*/
	return agent;
};
/*#{1J3030O8J0ExCodes*/
/*}#1J3030O8J0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1J3030O8J0PostDoc*/
/*}#1J3030O8J0PostDoc*/


export default AutoAPI;
export{AutoAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1J3030O8J0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1J3030O8K0",
//			"attrs": {}
//		},
//		"agent": {
//			"jaxId": "1J3030O8K1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1J3030O8K2",
//			"attrs": {
//				"input_type": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J30319N50",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "",
//						"enum": {
//							"type": "array",
//							"def": "Array",
//							"attrs": [
//								{
//									"type": "auto",
//									"valText": "text"
//								},
//								{
//									"type": "auto",
//									"valText": "filePath"
//								}
//							]
//						},
//						"required": "true"
//					}
//				},
//				"output_type": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J3031HDC0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "",
//						"enum": {
//							"type": "array",
//							"def": "Array",
//							"attrs": [
//								{
//									"type": "auto",
//									"valText": "text"
//								},
//								{
//									"type": "auto",
//									"valText": "filePath"
//								}
//							]
//						},
//						"required": "true"
//					}
//				},
//				"input_content": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J3033VGV0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"api": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J3046RL00",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"output_path": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J4CNT6AJ0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1J3030O8K3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1J3030O8K4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1J3030O8K5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1J30345RS0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "200",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1J30348R50",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J30386FV0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AutoAPI",
//					"jaxId": "1J30386FV0",
//					"attrs": {
//						"id": "Call",
//						"viewName": "",
//						"label": "",
//						"x": "435",
//						"y": "100",
//						"desc": "调用MCP 工具，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3046RL01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3046RL02",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"server": "http://127.0.0.1:8082",
//						"tool": "#`${api}`",
//						"argument": "#{input:input_content, output_path:output_path, timeout:300}",
//						"outlet": {
//							"jaxId": "1J3046RL03",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4CA9GL80"
//						}
//					},
//					"icon": "mcp.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J304NKR00",
//					"attrs": {
//						"id": "Output",
//						"viewName": "",
//						"label": "",
//						"x": "1080",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J304UGPI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J304UGPI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J304UGP91",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J304UGP90",
//									"attrs": {
//										"id": "Text",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J304UGPI2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J304UGPI3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#output_type===\"text\""
//									},
//									"linkedSeg": "1J4CO7C6B0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J304NSJU0",
//									"attrs": {
//										"id": "File",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J304UGPI6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J304UGPI7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#output_type===\"filePath\""
//									},
//									"linkedSeg": "1J4ENDTIU0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J30CP6CF0",
//					"attrs": {
//						"id": "OutputText",
//						"viewName": "",
//						"label": "",
//						"x": "1500",
//						"y": "5",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J30CU5MD2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J30CU5MD3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1J30CU5M53",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J49J1FSF0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J49J1FSF0",
//					"attrs": {
//						"id": "SaveFile",
//						"viewName": "",
//						"label": "",
//						"x": "1515",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J49J2B750",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J49J2B751",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J49J2B730",
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
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J4CA9GL80",
//					"attrs": {
//						"id": "CheckSuccess",
//						"viewName": "",
//						"label": "",
//						"x": "625",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4CABGVQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4CABGVQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J4CAB04E1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J4EMUL600"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J4CAB04E0",
//									"attrs": {
//										"id": "Fail",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J4CABGVQ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J4CABGVQ3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#output===\"fail\""
//									},
//									"linkedSeg": "1J4CABOIB0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J4CABOIB0",
//					"attrs": {
//						"id": "OutputFail",
//						"viewName": "",
//						"label": "",
//						"x": "875",
//						"y": "-45",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4CACUAS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4CACUAS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Call failed",
//							"localize": {
//								"EN": "Call failed",
//								"CN": "调用失败"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J4CACUAM0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4COEKDM0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J4CO7C6B0",
//					"attrs": {
//						"id": "Read",
//						"viewName": "",
//						"label": "",
//						"x": "1275",
//						"y": "5",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4CO8P2U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4CO8P2U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J4CO7OS00",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J30CP6CF0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J4COEKDM0",
//					"attrs": {
//						"id": "OutputError",
//						"viewName": "",
//						"label": "",
//						"x": "1105",
//						"y": "-45",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4COGDF80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4COGDF81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#error",
//						"outlet": {
//							"jaxId": "1J4COESH80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J4EMUL600",
//					"attrs": {
//						"id": "OutputSuccess",
//						"viewName": "",
//						"label": "",
//						"x": "855",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4EN0SAB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4EN0SAB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Call success",
//							"localize": {
//								"EN": "Call success",
//								"CN": "调用成功"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J4EN0SA60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J304NKR00"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J4ENDTIU0",
//					"attrs": {
//						"id": "OutputFile",
//						"viewName": "",
//						"label": "",
//						"x": "1275",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4ENEOLG0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4ENEOLG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Please download the file from the File on the right",
//							"localize": {
//								"EN": "Please download the file from the File on the right",
//								"CN": "请从右边File下载文件"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J4ENEOL60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J49J1FSF0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}