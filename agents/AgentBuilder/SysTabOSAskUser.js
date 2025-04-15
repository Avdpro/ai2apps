//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IKDODVUT0MoreImports*/
/*}#1IKDODVUT0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1IKDODVUT0StartDoc*/
/*}#1IKDODVUT0StartDoc*/
//----------------------------------------------------------------------------
let SysTabOSAskUser=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FilterChat,IsMenu,Menu,Chat,ShowAsk;
	let orgInput="";
	
	/*#{1IKDODVUT0LocalVals*/
	/*}#1IKDODVUT0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IKDODVUT0ParseArgs*/
		/*}#1IKDODVUT0ParseArgs*/
	}
	
	/*#{1IKDODVUT0PreContext*/
	/*}#1IKDODVUT0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IKDODVUT0PostContext*/
	/*}#1IKDODVUT0PostContext*/
	let $agent,agent,segs={};
	segs["FilterChat"]=FilterChat=async function(input){//:1IKDOEJIG0
		let prompt;
		let result=null;
		/*#{1IKDOEJIG0Input*/
		let ua=$agent.upperAgent;
		if(ua){
			$agent.showName=ua.showName||ua.name;
		}
		/*}#1IKDOEJIG0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:{
				"type":"json_schema",
				"json_schema":{
					"name":"AskUser",
					"schema":{
						"type":"object",
						"description":"",
						"properties":{
							"items":{
								"type":[
									"array","null"
								],
								"description":"菜单选项列表",
								"items":{
									"$ref":"#/$defs/AskMenuItem"
								}
							}
						},
						"required":[
							"items"
						],
						"additionalProperties":false,
						"$defs":{
							"AskMenuItem":{
								"type":"object",
								"description":"",
								"properties":{
									"emoji":{
										"type":"string",
										"description":"用于描述该选项的Emoji符号，不要超过两个符号"
									},
									"text":{
										"type":"string",
										"description":"菜单选项的文本"
									}
								},
								"required":[
									"emoji","text"
								],
								"additionalProperties":false
							}
						}
					},
					"strict":true
				}
			}
		};
		let chatMem=FilterChat.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你是一个把输入的对话文本转化为更方便的用户交互方式的AI\n\n---\n### 输入\n对话的输入是一段与用户交互，需要用户输入的文本提示\n\n---\n### 转化\n请根据对话的内容判断，对话是否可以转化为菜单形式的对话。例如询问用户是否确定，让用户在多个选项中选择，都是可以转化为菜单形式的。\n\n---\n### 输出\n请用JSON格式返回，例如：\n{\n\t\"items\":[\n    \t{\n        \t\"emoji\":\"▶️\",\n            \"text\":\"Start\",\n        },\n    \t{\n        \t\"emoji\":\"🛑\",\n            \"text\":\"Stop\",\n        },\n   ]\n}\n\n返回JSON参数说明：\n- \"items\" {array<object>}: 如果不能用菜单交互，为null，可以用菜单交互，菜单的选项列表，每一个选项对象包含两个属性：\n\t- \"emoji\" {string}: 一个可以代表当前选项的Emoji符号，注意尽量用单一的符号\n    - \"text\" {string}: 菜单项的文本内容\n"},
		];
		/*#{1IKDOEJIG0PrePrompt*/
		/*}#1IKDOEJIG0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IKDOEJIG0FilterMessage*/
			/*}#1IKDOEJIG0FilterMessage*/
			messages.push(msg);
		}
		/*#{1IKDOEJIG0PreCall*/
		/*}#1IKDOEJIG0PreCall*/
		result=(result===null)?(await session.callSegLLM("FilterChat@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IKDOEJIG0PostCall*/
		/*}#1IKDOEJIG0PostCall*/
		return {seg:IsMenu,result:(result),preSeg:"1IKDOEJIG0",outlet:"1IKDOEJIH0"};
	};
	FilterChat.jaxId="1IKDOEJIG0"
	FilterChat.url="FilterChat@"+agentURL
	
	segs["IsMenu"]=IsMenu=async function(input){//:1IKDOESHL0
		let result=input;
		if(input.items && input.items.length){
			let output=input;
			return {seg:ShowAsk,result:(output),preSeg:"1IKDOESHL0",outlet:"1IKDOESHM3"};
		}
		return {seg:Chat,result:(result),preSeg:"1IKDOESHL0",outlet:"1IKDOESHM2"};
	};
	IsMenu.jaxId="1IKDOESHL0"
	IsMenu.url="IsMenu@"+agentURL
	
	segs["Menu"]=Menu=async function(input){//:1IKDOFA6I3
		let prompt=((($ln==="CN")?("请选择或输入您的答案："):("Please choose or input your answer:")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=true;
		let items=[
		];
		let result="";
		let item=null;
		
		/*#{1IKDOFA6I3PreCodes*/
		items=input.items.map((item)=>{
			return {...item};
		});
		/*}#1IKDOFA6I3PreCodes*/
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1IKDOFA6I3PostCodes*/
		/*}#1IKDOFA6I3PostCodes*/
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}
		/*#{1IKDOFA6I3FinCodes*/
		/*}#1IKDOFA6I3FinCodes*/
		return {result:result};
	};
	Menu.jaxId="1IKDOFA6I3"
	Menu.url="Menu@"+agentURL
	
	segs["Chat"]=Chat=async function(input){//:1IKDOFINU0
		let tip=(execInput);
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		/*#{1IKDOFINU0PreCodes*/
		/*}#1IKDOFINU0PreCodes*/
		if(askUpward && tip){
			result=await session.askUpward(askUpward==="$up"?($agent.upperAgent||$agent):$agent,tip);
		}else{
			if(tip){
				session.addChatText(tipRole,tip);
			}
			result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		}
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		/*#{1IKDOFINU0PostCodes*/
		/*}#1IKDOFINU0PostCodes*/
		return {result:result};
	};
	Chat.jaxId="1IKDOFINU0"
	Chat.url="Chat@"+agentURL
	
	segs["ShowAsk"]=ShowAsk=async function(input){//:1IOEUVS350
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=execInput;
		session.addChatText(role,content,opts);
		return {seg:Menu,result:(result),preSeg:"1IOEUVS350",outlet:"1IOEV0OCS0"};
	};
	ShowAsk.jaxId="1IOEUVS350"
	ShowAsk.url="ShowAsk@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"SysTabOSAskUser",
		url:agentURL,
		autoStart:true,
		jaxId:"1IKDODVUT0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IKDODVUT0PreEntry*/
			/*}#1IKDODVUT0PreEntry*/
			result={seg:FilterChat,"input":input};
			/*#{1IKDODVUT0PostEntry*/
			/*}#1IKDODVUT0PostEntry*/
			return result;
		},
		/*#{1IKDODVUT0MoreAgentAttrs*/
		/*}#1IKDODVUT0MoreAgentAttrs*/
	};
	/*#{1IKDODVUT0PostAgent*/
	/*}#1IKDODVUT0PostAgent*/
	return agent;
};
/*#{1IKDODVUT0ExCodes*/
/*}#1IKDODVUT0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IKDODVUT0PostDoc*/
/*}#1IKDODVUT0PostDoc*/


export default SysTabOSAskUser;
export{SysTabOSAskUser};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IKDODVUT0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IKDODVUT1",
//			"attrs": {
//				"SysTabOSAskUser": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IKDODVUU0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IKDODVUU1",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IKDODVUU2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IKDODVUU3",
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
//			"jaxId": "1IKDODVUT2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IKDODVUT3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IKDODVUT4",
//			"attrs": {
//				"orgInput": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IKDODVUT5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IKDODVUT6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IKDOEJIG0",
//					"attrs": {
//						"id": "FilterChat",
//						"viewName": "",
//						"label": "",
//						"x": "135",
//						"y": "240",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKDOEJIG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKDOEJIG2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o-mini",
//						"system": "你是一个把输入的对话文本转化为更方便的用户交互方式的AI\n\n---\n### 输入\n对话的输入是一段与用户交互，需要用户输入的文本提示\n\n---\n### 转化\n请根据对话的内容判断，对话是否可以转化为菜单形式的对话。例如询问用户是否确定，让用户在多个选项中选择，都是可以转化为菜单形式的。\n\n---\n### 输出\n请用JSON格式返回，例如：\n{\n\t\"items\":[\n    \t{\n        \t\"emoji\":\"▶️\",\n            \"text\":\"Start\",\n        },\n    \t{\n        \t\"emoji\":\"🛑\",\n            \"text\":\"Stop\",\n        },\n   ]\n}\n\n返回JSON参数说明：\n- \"items\" {array<object>}: 如果不能用菜单交互，为null，可以用菜单交互，菜单的选项列表，每一个选项对象包含两个属性：\n\t- \"emoji\" {string}: 一个可以代表当前选项的Emoji符号，注意尽量用单一的符号\n    - \"text\" {string}: 菜单项的文本内容\n",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IKDOEJIH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKDOESHL0"
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
//						"formatDef": "\"1IIUI7JO80\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IKDOESHL0",
//					"attrs": {
//						"id": "IsMenu",
//						"viewName": "",
//						"label": "",
//						"x": "365",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKDOESHM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKDOESHM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKDOESHM2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IKDOFINU0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKDOESHM3",
//									"attrs": {
//										"id": "Menu",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKDOESHM4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKDOESHM5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.items && input.items.length"
//									},
//									"linkedSeg": "1IOEUVS350"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IKDOFA6I3",
//					"attrs": {
//						"id": "Menu",
//						"viewName": "",
//						"label": "",
//						"x": "795",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Please choose or input your answer:",
//							"localize": {
//								"EN": "Please choose or input your answer:",
//								"CN": "请选择或输入您的答案："
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1IKDOFA6I4",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"silent": "false"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IKDOFINU0",
//					"attrs": {
//						"id": "Chat",
//						"viewName": "",
//						"label": "",
//						"x": "575",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKDOFINU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKDOFINU2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#execInput",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1IKDOFINU3",
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
//					"def": "output",
//					"jaxId": "1IOEUVS350",
//					"attrs": {
//						"id": "ShowAsk",
//						"viewName": "",
//						"label": "",
//						"x": "575",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOEV1PDJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOEV1PDJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#execInput",
//						"outlet": {
//							"jaxId": "1IOEV0OCS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKDOFA6I3"
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