//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1JC0LF9K60MoreImports*/
/*}#1JC0LF9K60MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?decodeURI(baseURL):baseURL;
const $ln=VFACT.lanCode||"EN";
/*#{1JC0LF9K60StartDoc*/
/*}#1JC0LF9K60StartDoc*/
//----------------------------------------------------------------------------
let AnySearch=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Entry,WriteHtml,CheckChat,ShowCode,AIRetry,ShowPage,Finish,CheckType,ShowReportAPIRes,SaveMDReport;
	let htmlCode="";
	
	/*#{1JC0LF9K60LocalVals*/
	/*}#1JC0LF9K60LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1JC0LF9K60ParseArgs*/
		/*}#1JC0LF9K60ParseArgs*/
	}
	
	/*#{1JC0LF9K60PreContext*/
	/*}#1JC0LF9K60PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1JC0LF9K60PostContext*/
	/*}#1JC0LF9K60PostContext*/
	let $agent,agent,segs={};
	segs["Entry"]=Entry=async function(input){//:1JC0LFH770
		let result,args={};
		args['nodeName']="AgentBuilder";
		args['callAgent']="AnySearchWorkflow.js";
		args['callArg']=input;
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {seg:CheckType,result:(result),preSeg:"1JC0LFH770",outlet:"1JC0LGI5E0"};
	};
	Entry.jaxId="1JC0LFH770"
	Entry.url="Entry@"+agentURL
	
	segs["WriteHtml"]=WriteHtml=async function(input){//:1JCIQ227E0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-4.1";
		let $agent;
		let result=null;
		/*#{1JCIQ227E0Input*/
		/*}#1JCIQ227E0Input*/
		
		let opts={
			platform:$platform,
			mode:$model,
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=WriteHtml.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:(($ln==="CN")?(`
## 角色 你是一个根据用户需求，编写简单的HTML页面的AI智能体。
## 对话 
- 用户会给出当前HTML需要渲染的内容：\${input.userPrompt}
- 你根据当前内容，用JSON回复用户 
- 如果你可以根据当前掌握信息可以输出HTML，请在JSON中的"html"属性中提供完整的HTML页面代码（包括必须的CSS/JS以及引用的外部脚本等）。例如： 
\`\`\` 
{ "html":"<html>...</html>" } 
\`\`\` 
## 回复JSON对象属性 
- "html" {string}: 你生成的HTML页面代码，注意一定是完整的HTML页面代码（包括必须的CSS/JS以及引用的外部脚本等）。 `):(`
## Role
You are an AI agent that creates simple HTML pages according to user requirements.
## Dialogue
- The user will provide the content to be rendered in HTML: \${input.userPrompt}
- Based on the given content, reply to the user with a JSON object.
- If you are able to generate the HTML page based on the information provided, include the complete HTML page code (including the necessary CSS/JS and external scripts) in the "html" property of the JSON. For example:
\`\`\`
{ "html":"<html>...</html>" }
\`\`\`
## Reply JSON Object Properties
- "html" {string}: The HTML page code you generate. Make sure it is a complete HTML page code (including all necessary CSS/JS and any required external scripts).`))},
		];
		messages.push(...chatMem);
		/*#{1JCIQ227E0PrePrompt*/
		/*}#1JCIQ227E0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JCIQ227E0FilterMessage*/
			/*}#1JCIQ227E0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JCIQ227E0PreCall*/
		/*}#1JCIQ227E0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("WriteHtml@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JCIQ227E0PostLLM*/
		/*}#1JCIQ227E0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1JCIQ227E0PostClear*/
			/*}#1JCIQ227E0PostClear*/
		}
		result=trimJSON(result);
		/*#{1JCIQ227E0PostCall*/
		/*}#1JCIQ227E0PostCall*/
		/*#{1JCIQ227E0PreResult*/
		/*}#1JCIQ227E0PreResult*/
		return {seg:CheckChat,result:(result),preSeg:"1JCIQ227E0",outlet:"1JCIQ2GT40"};
	};
	WriteHtml.jaxId="1JCIQ227E0"
	WriteHtml.url="WriteHtml@"+agentURL
	WriteHtml.messages=[];
	
	segs["CheckChat"]=CheckChat=async function(input){//:1JCIQ496N0
		let result=input;
		if(input.html){
			return {seg:ShowCode,result:(input),preSeg:"1JCIQ496N0",outlet:"1JCIQ5PIN0"};
		}
		return {seg:AIRetry,result:(result),preSeg:"1JCIQ496N0",outlet:"1JCIQ5PIN1"};
	};
	CheckChat.jaxId="1JCIQ496N0"
	CheckChat.url="CheckChat@"+agentURL
	
	segs["ShowCode"]=ShowCode=async function(input){//:1JCIQ60BS0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?(`
代码如下： 
\`\`\`
${input.html}
\`\`\` 
`):(`
Codes are as follows:
\`\`\`
${input.html} 
\`\`\`
`));
		session.addChatText(role,content,opts);
		return {seg:ShowPage,result:(result),preSeg:"1JCIQ60BS0",outlet:"1JCIQ77TJ0"};
	};
	ShowCode.jaxId="1JCIQ60BS0"
	ShowCode.url="ShowCode@"+agentURL
	
	segs["AIRetry"]=AIRetry=async function(input){//:1JCIQ7FSF0
		let result=input
		try{
			/*#{1JCIQ7FSF0Code*/
			/*}#1JCIQ7FSF0Code*/
		}catch(error){
			/*#{1JCIQ7FSF0ErrorCode*/
			/*}#1JCIQ7FSF0ErrorCode*/
		}
		return {seg:WriteHtml,result:(result),preSeg:"1JCIQ7FSF0",outlet:"1JCIQ8OAO0"};
	};
	AIRetry.jaxId="1JCIQ7FSF0"
	AIRetry.url="AIRetry@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1JCIQDUEP0
		let result=input
		try{
			/*#{1JCIQDUEP0Code*/
			htmlCode=input.html;
			result=session.WSCall_WebSandbox(htmlCode);
			/*}#1JCIQDUEP0Code*/
		}catch(error){
			/*#{1JCIQDUEP0ErrorCode*/
			/*}#1JCIQDUEP0ErrorCode*/
		}
		return {seg:Finish,result:(result),preSeg:"1JCIQDUEP0",outlet:"1JCIQEIVC0"};
	};
	ShowPage.jaxId="1JCIQDUEP0"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1JCIQI2MU0
		let result=input
		try{
			/*#{1JCIQI2MU0Code*/
			let codeData,hubFileName;
			codeData=Base64.encode(htmlCode);
			hubFileName=session.saveHubFile("sandbox.html",codeData);
			result={result:"Finish",content:"Sandbox page finished with: "+JSON.stringify(input.result)};
			/*}#1JCIQI2MU0Code*/
		}catch(error){
			/*#{1JCIQI2MU0ErrorCode*/
			/*}#1JCIQI2MU0ErrorCode*/
		}
		return {result:result};
	};
	Finish.jaxId="1JCIQI2MU0"
	Finish.url="Finish@"+agentURL
	
	segs["CheckType"]=CheckType=async function(input){//:1JCIRCVEA0
		let result=input;
		if( input.type === 'Md'){
			return {seg:ShowReportAPIRes,result:(input),preSeg:"1JCIRCVEA0",outlet:"1JCIRGDB80"};
		}
		if( input.type === 'Html'){
			return {seg:WriteHtml,result:(input),preSeg:"1JCIRCVEA0",outlet:"1JCLAVLPC0"};
		}
		return {result:result};
	};
	CheckType.jaxId="1JCIRCVEA0"
	CheckType.url="CheckType@"+agentURL
	
	segs["ShowReportAPIRes"]=ShowReportAPIRes=async function(input){//:1JCIRE94B0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.userPrompt;
		session.addChatText(role,content,opts);
		return {seg:SaveMDReport,result:(result),preSeg:"1JCIRE94B0",outlet:"1JCIRGDB82"};
	};
	ShowReportAPIRes.jaxId="1JCIRE94B0"
	ShowReportAPIRes.url="ShowReportAPIRes@"+agentURL
	
	segs["SaveMDReport"]=SaveMDReport=async function(input){//:1JCIRF6V90
		let result,args={};
		args['nodeName']="AgentBuilder";
		args['callAgent']="ToolWriteFile.js";
		args['callArg']={content:input.userPrompt,filePath:"/tmp/report.md",append:false};
		args['checkUpdate']=true;
		args['options']="";
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		return {result:result};
	};
	SaveMDReport.jaxId="1JCIRF6V90"
	SaveMDReport.url="SaveMDReport@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"AnySearch",
		url:agentURL,
		autoStart:true,
		jaxId:"1JC0LF9K60",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1JC0LF9K60PreEntry*/
			/*}#1JC0LF9K60PreEntry*/
			result={seg:Entry,"input":input};
			/*#{1JC0LF9K60PostEntry*/
			/*}#1JC0LF9K60PostEntry*/
			return result;
		},
		/*#{1JC0LF9K60MoreAgentAttrs*/
		/*}#1JC0LF9K60MoreAgentAttrs*/
	};
	/*#{1JC0LF9K60PostAgent*/
	/*}#1JC0LF9K60PostAgent*/
	return agent;
};
/*#{1JC0LF9K60ExCodes*/
/*}#1JC0LF9K60ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "AnySearch",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	isChatApi: true,
	agent: AnySearch
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
		name:"AnySearch",showName:"AnySearch",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["AnySearch"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/builder/ai/AnySearch.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
			this.packUpdateContext(coder,seg);
			this.packUpdateGlobal(coder,seg);
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
/*#{1JC0LF9K60PostDoc*/
/*}#1JC0LF9K60PostDoc*/


export default AnySearch;
export{AnySearch};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JC0LF9K60",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JC0LF9K70",
//			"attrs": {
//				"qa": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JC0LF9K76",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JC0LF9K77",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JC0LF9K78",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JC0LF9K79",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportClass": "false",
//						"superClass": ""
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1JC0LF9K71",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "Entry",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JC0LF9K72",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1JC0LF9K73",
//			"attrs": {
//				"htmlCode": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JC0LF9K74",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JC0LF9K75",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1JC0LFH770",
//					"attrs": {
//						"id": "Entry",
//						"viewName": "",
//						"label": "",
//						"x": "-245",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC0LGI5G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC0LGI5G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AgentBuilder",
//						"callAgent": "AnySearchWorkflow.js",
//						"callArg": "#input",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JC0LGI5E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCIRCVEA0"
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JCIQ227E0",
//					"attrs": {
//						"id": "WriteHtml",
//						"viewName": "",
//						"label": "",
//						"x": "245",
//						"y": "115",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIQ2GT70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIQ2GT71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1",
//						"system": {
//							"type": "string",
//							"valText": "#`\n## Role\nYou are an AI agent that creates simple HTML pages according to user requirements.\n## Dialogue\n- The user will provide the content to be rendered in HTML: \\${input.userPrompt}\n- Based on the given content, reply to the user with a JSON object.\n- If you are able to generate the HTML page based on the information provided, include the complete HTML page code (including the necessary CSS/JS and external scripts) in the \"html\" property of the JSON. For example:\n\\`\\`\\`\n{ \"html\":\"<html>...</html>\" }\n\\`\\`\\`\n## Reply JSON Object Properties\n- \"html\" {string}: The HTML page code you generate. Make sure it is a complete HTML page code (including all necessary CSS/JS and any required external scripts).`",
//							"localize": {
//								"EN": "#`\n## Role\nYou are an AI agent that creates simple HTML pages according to user requirements.\n## Dialogue\n- The user will provide the content to be rendered in HTML: \\${input.userPrompt}\n- Based on the given content, reply to the user with a JSON object.\n- If you are able to generate the HTML page based on the information provided, include the complete HTML page code (including the necessary CSS/JS and external scripts) in the \"html\" property of the JSON. For example:\n\\`\\`\\`\n{ \"html\":\"<html>...</html>\" }\n\\`\\`\\`\n## Reply JSON Object Properties\n- \"html\" {string}: The HTML page code you generate. Make sure it is a complete HTML page code (including all necessary CSS/JS and any required external scripts).`",
//								"CN": "#`\n## 角色 你是一个根据用户需求，编写简单的HTML页面的AI智能体。\n## 对话 \n- 用户会给出当前HTML需要渲染的内容：\\${input.userPrompt}\n- 你根据当前内容，用JSON回复用户 \n- 如果你可以根据当前掌握信息可以输出HTML，请在JSON中的\"html\"属性中提供完整的HTML页面代码（包括必须的CSS/JS以及引用的外部脚本等）。例如： \n\\`\\`\\` \n{ \"html\":\"<html>...</html>\" } \n\\`\\`\\` \n## 回复JSON对象属性 \n- \"html\" {string}: 你生成的HTML页面代码，注意一定是完整的HTML页面代码（包括必须的CSS/JS以及引用的外部脚本等）。 `"
//							},
//							"localizable": true
//						},
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
//							"jaxId": "1JCIQ2GT40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCIQ496N0"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "50 messages",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"\"",
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JCIQ496N0",
//					"attrs": {
//						"id": "CheckChat",
//						"viewName": "",
//						"label": "",
//						"x": "460",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIQ5PIT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIQ5PIT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JCIQ5PIN1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JCIQ7FSF0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JCIQ5PIN0",
//									"attrs": {
//										"id": "Html",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JCIQ5PIT2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JCIQ5PIT3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.html"
//									},
//									"linkedSeg": "1JCIQ60BS0"
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
//					"jaxId": "1JCIQ60BS0",
//					"attrs": {
//						"id": "ShowCode",
//						"viewName": "",
//						"label": "",
//						"x": "690",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIQ77TN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIQ77TN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "#`\nCodes are as follows:\n\\`\\`\\`\n${input.html} \n\\`\\`\\`\n`",
//							"localize": {
//								"EN": "#`\nCodes are as follows:\n\\`\\`\\`\n${input.html} \n\\`\\`\\`\n`",
//								"CN": "#`\n代码如下： \n\\`\\`\\`\n${input.html}\n\\`\\`\\` \n`"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JCIQ77TJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCIQDUEP0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JCIQ7FSF0",
//					"attrs": {
//						"id": "AIRetry",
//						"viewName": "",
//						"label": "",
//						"x": "690",
//						"y": "155",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIQ8OAT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIQ8OAT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JCIQ8OAO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCIQ809T0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JCIQ809T0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "825",
//						"y": "210",
//						"outlet": {
//							"jaxId": "1JCIQ8OAT2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCIQ81AP0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JCIQ81AP0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "270",
//						"y": "210",
//						"outlet": {
//							"jaxId": "1JCIQ8OAT3",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCIQ227E0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JCIQDUEP0",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "910",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIQER7L0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIQER7L1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JCIQEIVC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCIQI2MU0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JCIQI2MU0",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "1125",
//						"y": "100",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIQIGL70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIQIGL71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JCIQIGL30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JCIRCVEA0",
//					"attrs": {
//						"id": "CheckType",
//						"viewName": "",
//						"label": "",
//						"x": "-50",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIRGDBA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIRGDBA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JCIRGDB81",
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
//									"jaxId": "1JCIRGDB80",
//									"attrs": {
//										"id": "Md",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JCIRGDBA2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JCIRGDBA3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "# input.type === 'Md'"
//									},
//									"linkedSeg": "1JCIRE94B0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JCLAVLPC0",
//									"attrs": {
//										"id": "Html",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JCLAVLPE0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JCLAVLPE1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "# input.type === 'Html'"
//									},
//									"linkedSeg": "1JCIQ227E0"
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
//					"jaxId": "1JCIRE94B0",
//					"attrs": {
//						"id": "ShowReportAPIRes",
//						"viewName": "",
//						"label": "",
//						"x": "245",
//						"y": "45",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIRGDBA4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIRGDBA5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.userPrompt",
//						"outlet": {
//							"jaxId": "1JCIRGDB82",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCIRF6V90"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1JCIRF6V90",
//					"attrs": {
//						"id": "SaveMDReport",
//						"viewName": "",
//						"label": "",
//						"x": "500",
//						"y": "45",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIRGDBA6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIRGDBA7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AgentBuilder",
//						"callAgent": "ToolWriteFile.js",
//						"callArg": "#{content:input.userPrompt,filePath:\"/tmp/report.md\",append:false}",
//						"checkUpdate": "true",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JCIRGDB83",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "cloudact.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}