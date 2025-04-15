//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IIU5R41B0MoreImports*/
/*}#1IIU5R41B0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
/*#{1IIU5R41B0StartDoc*/
/*}#1IIU5R41B0StartDoc*/
//----------------------------------------------------------------------------
let SysAskUser=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FilterChat,IsMenu,Menu,Chat,ShowAsk;
	let orgInput="";
	
	/*#{1IIU5R41B0LocalVals*/
	/*}#1IIU5R41B0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IIU5R41B0ParseArgs*/
		/*}#1IIU5R41B0ParseArgs*/
	}
	
	/*#{1IIU5R41B0PreContext*/
	/*}#1IIU5R41B0PreContext*/
	context={};
	/*#{1IIU5R41B0PostContext*/
	/*}#1IIU5R41B0PostContext*/
	let $agent,agent,segs={};
	segs["FilterChat"]=FilterChat=async function(input){//:1IIU5RK0F0
		let prompt;
		let result=null;
		/*#{1IIU5RK0F0Input*/
		orgInput=input;
		let ua=$agent.upperAgent;
		if(ua){
			$agent.showName=ua.showName||ua.name;
		}
		/*}#1IIU5RK0F0Input*/
		
		let opts={
			platform:"",
			mode:"$fast",
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
		/*#{1IIU5RK0F0PrePrompt*/
		/*}#1IIU5RK0F0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IIU5RK0F0FilterMessage*/
			/*}#1IIU5RK0F0FilterMessage*/
			messages.push(msg);
		}
		/*#{1IIU5RK0F0PreCall*/
		/*}#1IIU5RK0F0PreCall*/
		result=(result===null)?(await session.callSegLLM("FilterChat@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IIU5RK0F0PostCall*/
		/*}#1IIU5RK0F0PostCall*/
		return {seg:IsMenu,result:(result),preSeg:"1IIU5RK0F0",outlet:"1IIU5VBC70"};
	};
	FilterChat.jaxId="1IIU5RK0F0"
	FilterChat.url="FilterChat@"+agentURL
	
	segs["IsMenu"]=IsMenu=async function(input){//:1IIU5T1VI0
		let result=input;
		if(input.items && input.items.length){
			let output=input;
			return {seg:ShowAsk,result:(output),preSeg:"1IIU5T1VI0",outlet:"1IIU5VBC80"};
		}
		return {seg:Chat,result:(result),preSeg:"1IIU5T1VI0",outlet:"1IIU5VBC81"};
	};
	IsMenu.jaxId="1IIU5T1VI0"
	IsMenu.url="IsMenu@"+agentURL
	
	segs["Menu"]=Menu=async function(input){//:1IIU5U92H0
		let prompt=((($ln==="CN")?("请选择或输入您的答案："):("Please choose or input your answer:")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=true;
		let items=[
		];
		let result="";
		let item=null;
		
		/*#{1IIU5U92H0PreCodes*/
		items=input.items.map((item)=>{
			return {...item};
		});
		/*}#1IIU5U92H0PreCodes*/
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1IIU5U92H0PostCodes*/
		/*}#1IIU5U92H0PostCodes*/
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}
		/*#{1IIU5U92H0FinCodes*/
		/*}#1IIU5U92H0FinCodes*/
		return {result:result};
	};
	Menu.jaxId="1IIU5U92H0"
	Menu.url="Menu@"+agentURL
	
	segs["Chat"]=Chat=async function(input){//:1IIU5TUHG0
		let tip=(orgInput);
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
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
		return {result:result};
	};
	Chat.jaxId="1IIU5TUHG0"
	Chat.url="Chat@"+agentURL
	
	segs["ShowAsk"]=ShowAsk=async function(input){//:1IOEUSM5G0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=orgInput;
		session.addChatText(role,content,opts);
		return {seg:Menu,result:(result),preSeg:"1IOEUSM5G0",outlet:"1IOEUT8TM0"};
	};
	ShowAsk.jaxId="1IOEUSM5G0"
	ShowAsk.url="ShowAsk@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"SysAskUser",
		url:agentURL,
		autoStart:true,
		jaxId:"1IIU5R41B0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IIU5R41B0PreEntry*/
			/*}#1IIU5R41B0PreEntry*/
			result={seg:FilterChat,"input":input};
			/*#{1IIU5R41B0PostEntry*/
			/*}#1IIU5R41B0PostEntry*/
			return result;
		},
		/*#{1IIU5R41B0MoreAgentAttrs*/
		/*}#1IIU5R41B0MoreAgentAttrs*/
	};
	/*#{1IIU5R41B0PostAgent*/
	/*}#1IIU5R41B0PostAgent*/
	return agent;
};
/*#{1IIU5R41B0ExCodes*/
/*}#1IIU5R41B0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1IIU5R41B0PostDoc*/
/*}#1IIU5R41B0PostDoc*/


export default SysAskUser;
export{SysAskUser};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IIU5R41B0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IIU5R41B1",
//			"attrs": {
//				"SysAskUser": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IIU5R41B7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IIU5R41C0",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IIU5R41C1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IIU5R41C2",
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
//			"jaxId": "1IIU5R41B2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "FilterChat",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IIU5R41B3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IIU5R41B4",
//			"attrs": {
//				"orgInput": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IIU5R41B5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IIU5R41B6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IIU5RK0F0",
//					"attrs": {
//						"id": "FilterChat",
//						"viewName": "",
//						"label": "",
//						"x": "140",
//						"y": "285",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIU5VBCA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIU5VBCA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "",
//						"mode": "$fast",
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
//							"jaxId": "1IIU5VBC70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIU5T1VI0"
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
//					"jaxId": "1IIU5T1VI0",
//					"attrs": {
//						"id": "IsMenu",
//						"viewName": "",
//						"label": "",
//						"x": "360",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIU5VBCA2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIU5VBCA3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IIU5VBC81",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IIU5TUHG0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IIU5VBC80",
//									"attrs": {
//										"id": "Menu",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IIU5VBCA4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IIU5VBCA5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.items && input.items.length"
//									},
//									"linkedSeg": "1IOEUSM5G0"
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
//					"jaxId": "1IIU5U92H0",
//					"attrs": {
//						"id": "Menu",
//						"viewName": "",
//						"label": "",
//						"x": "795",
//						"y": "220",
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
//							"jaxId": "1IIU5VBC83",
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
//					"jaxId": "1IIU5TUHG0",
//					"attrs": {
//						"id": "Chat",
//						"viewName": "",
//						"label": "",
//						"x": "580",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IIU5VBCA6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IIU5VBCA7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#orgInput",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1IIU5VBC82",
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
//					"jaxId": "1IOEUSM5G0",
//					"attrs": {
//						"id": "ShowAsk",
//						"viewName": "",
//						"label": "",
//						"x": "580",
//						"y": "220",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOEUT8TQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOEUT8TQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#orgInput",
//						"outlet": {
//							"jaxId": "1IOEUT8TM0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IIU5U92H0"
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