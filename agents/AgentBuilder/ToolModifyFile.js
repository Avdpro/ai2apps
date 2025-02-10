//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHHJHFN30MoreImports*/
import fsp from 'fs/promises';
/*}#1IHHJHFN30MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"filePath":{
			"name":"filePath","type":"string",
			"defaultValue":"",
			"desc":"要修改的文件路径",
		},
		"guide":{
			"name":"guide","type":"string",
			"defaultValue":"",
			"desc":"如何修改的说明",
		}
	},
	/*#{1IHHJHFN30ArgsView*/
	/*}#1IHHJHFN30ArgsView*/
};

/*#{1IHHJHFN30StartDoc*/
/*}#1IHHJHFN30StartDoc*/
//----------------------------------------------------------------------------
let ToolModifyFile=async function(session){
	let filePath,guide;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,LoadFile,CheckLoad,FailResult,AIModify,ShowDiff,AskConfirm,Finsh,Abort,EditCode;
	let orgContent="";
	let newContent=undefined;
	
	/*#{1IHHJHFN30LocalVals*/
	/*}#1IHHJHFN30LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			filePath=input.filePath;
			guide=input.guide;
		}else{
			filePath=undefined;
			guide=undefined;
		}
		/*#{1IHHJHFN30ParseArgs*/
		/*}#1IHHJHFN30ParseArgs*/
	}
	
	/*#{1IHHJHFN30PreContext*/
	/*}#1IHHJHFN30PreContext*/
	context={};
	/*#{1IHHJHFN30PostContext*/
	/*}#1IHHJHFN30PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHHJSJTQ0
		let result=input;
		let missing=false;
		if(filePath===undefined || filePath==="") missing=true;
		if(guide===undefined || guide==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:LoadFile,result:(result),preSeg:"1IHHJSJTQ0",outlet:"1IHHJVS0I0"};
	};
	FixArgs.jaxId="1IHHJSJTQ0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["LoadFile"]=LoadFile=async function(input){//:1IHHJSREJ0
		let result=input
		/*#{1IHHJSREJ0Code*/
		try{
			orgContent=await fsp.readFile(filePath,"utf8");
		}catch(err){
			orgContent=null;
		}
		/*}#1IHHJSREJ0Code*/
		return {seg:CheckLoad,result:(result),preSeg:"1IHHJSREJ0",outlet:"1IHHJVS0I1"};
	};
	LoadFile.jaxId="1IHHJSREJ0"
	LoadFile.url="LoadFile@"+agentURL
	
	segs["CheckLoad"]=CheckLoad=async function(input){//:1IHHJTFSS0
		let result=input;
		if(orgContent!==null){
			let output=guide;
			return {seg:AIModify,result:(output),preSeg:"1IHHJTFSS0",outlet:"1IHHJVS0I2"};
		}
		return {seg:FailResult,result:(result),preSeg:"1IHHJTFSS0",outlet:"1IHHJVS0I3"};
	};
	CheckLoad.jaxId="1IHHJTFSS0"
	CheckLoad.url="CheckLoad@"+agentURL
	
	segs["FailResult"]=FailResult=async function(input){//:1IHHJUBTD0
		let result=input
		/*#{1IHHJUBTD0Code*/
		if(filePath[0]!=="/"){
			result={result:"Failed",content:`文件路径 "${filePath}" 不是完整路径，需要文件的完整路径才能编辑。`}
		}else{
			result={result:"Failed",content:`无法打开文件"${filePath}"编辑，请注意提供的是否是正确的且是完整路径。`}
		}
		/*}#1IHHJUBTD0Code*/
		return {result:result};
	};
	FailResult.jaxId="1IHHJUBTD0"
	FailResult.url="FailResult@"+agentURL
	
	segs["AIModify"]=AIModify=async function(input){//:1IHHJV0QQ0
		let prompt;
		let result=null;
		/*#{1IHHJV0QQ0Input*/
		/*}#1IHHJV0QQ0Input*/
		
		let opts={
			platform:"",
			mode:"$fast",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=AIModify.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`---
### 角色
你是一个根据指令修改文件内容的AI

---
### 原始文件内容:
\`\`\`
${orgContent}
\`\`\`

${newContent?`
---
### 当前修改后的文件内容:
${newContent}
`:""}

---
### 对话
在每次对话时根据用户指令修改当前文件内容，用JSON返回。
请把修改后的完整文件内容放到返回JOSN的"content"属性里
{
	"content":"...修改后的内容..."
}
`},
		];
		messages.push(...chatMem);
		/*#{1IHHJV0QQ0PrePrompt*/
		/*}#1IHHJV0QQ0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		/*#{1IHHJV0QQ0PreCall*/
		/*}#1IHHJV0QQ0PreCall*/
		result=(result===null)?(await session.callSegLLM("AIModify@"+agentURL,opts,messages,true)):result;
		/*#{1IHHJV0QQ0PostLLM*/
		/*}#1IHHJV0QQ0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>20){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1IHHJV0QQ0PostClear*/
			/*}#1IHHJV0QQ0PostClear*/
		}
		result=trimJSON(result);
		/*#{1IHHJV0QQ0PostCall*/
		chatMem.splice(chatMem.length-1,1,{role:"assistant",content:"...已略: 修改后的代码...."});
		/*}#1IHHJV0QQ0PostCall*/
		return {seg:ShowDiff,result:(result),preSeg:"1IHHJV0QQ0",outlet:"1IHHJVS0I5"};
	};
	AIModify.jaxId="1IHHJV0QQ0"
	AIModify.url="AIModify@"+agentURL
	AIModify.messages=[];
	
	segs["ShowDiff"]=ShowDiff=async function(input){//:1IHHK1ANQ0
		let result=input;
		let role="assistant";
		let content=input;
		/*#{1IHHK1ANQ0PreCodes*/
		newContent=input.content;
		content=(($ln==="CN")?(`### 原文件: \n\`\`\`${orgContent}\`\`\`\n### 修改后的文件: \n\`\`\`${newContent}\`\`\`\n`):/*EN*/(`### Original file: \n\`\`\`${orgContent}\`\`\`\n### Modified file: \n\`\`\`${newContent}\`\`\`\n`));
		/*}#1IHHK1ANQ0PreCodes*/
		session.addChatText(role,content);
		/*#{1IHHK1ANQ0PostCodes*/
		/*}#1IHHK1ANQ0PostCodes*/
		return {seg:AskConfirm,result:(result),preSeg:"1IHHK1ANQ0",outlet:"1IHHK8AH30"};
	};
	ShowDiff.jaxId="1IHHK1ANQ0"
	ShowDiff.url="ShowDiff@"+agentURL
	
	segs["AskConfirm"]=AskConfirm=async function(input){//:1IHHK9L2R0
		let prompt=("是否照此修改文件？你也可以提出进一步修改意见")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("确认修改"):("Confirm changes")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:("Abort changes"),code:1},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("手动编辑"):("Manual edit")),code:2},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Finsh,result:(result),preSeg:"1IHHK9L2R0",outlet:"1IHHK9L290"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:false,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {seg:AIModify,result:(result),preSeg:"1IHHK9L2R0",outlet:"1IHHKBJBP0"};
		}else if(item.code===0){
			return {seg:Finsh,result:(result),preSeg:"1IHHK9L2R0",outlet:"1IHHK9L290"};
		}else if(item.code===1){
			return {seg:Abort,result:(result),preSeg:"1IHHK9L2R0",outlet:"1IHHK9L291"};
		}else if(item.code===2){
			return {seg:EditCode,result:(result),preSeg:"1IHHK9L2R0",outlet:"1IICCLNFO0"};
		}
	};
	AskConfirm.jaxId="1IHHK9L2R0"
	AskConfirm.url="AskConfirm@"+agentURL
	
	segs["Finsh"]=Finsh=async function(input){//:1IHHKDEUC0
		let result=input
		/*#{1IHHKDEUC0Code*/
		try{
			await fsp.writeFile(filePath,newContent);
			result={result:"Finish",content:"文件已修改。"}
		}catch(err){
			result={result:"Fail",content:"保存文件失败。"}
		}
		/*}#1IHHKDEUC0Code*/
		return {result:result};
	};
	Finsh.jaxId="1IHHKDEUC0"
	Finsh.url="Finsh@"+agentURL
	
	segs["Abort"]=Abort=async function(input){//:1IHHKDU150
		let result=input
		/*#{1IHHKDU150Code*/
		result={result:"Abort",content:"用户取消文件修改。"};
		/*}#1IHHKDU150Code*/
		return {result:result};
	};
	Abort.jaxId="1IHHKDU150"
	Abort.url="Abort@"+agentURL
	
	segs["EditCode"]=EditCode=async function(input){//:1IICCJPMR0
		let result;
		let role="assistant";
		let tip="";
		let showResult=false;
		let dlgVO={title:"Edit text",text:newContent};
		/*#{1IICCJPMR0Pre*/
		/*}#1IICCJPMR0Pre*/
		result= await session.askUserDlg({"dlgPath":"/@editkit/ui/DlgLongText.js","arg":dlgVO,"role":role,tip:tip,showResult:showResult});
		/*#{1IICCJPMR0Codes*/
		if(result){
			newContent=result;
		}
		/*}#1IICCJPMR0Codes*/
		return {seg:ShowDiff,result:(result),preSeg:"1IICCJPMR0",outlet:"1IICCLNFP0"};
	};
	EditCode.jaxId="1IICCJPMR0"
	EditCode.url="EditCode@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"ToolModifyFile",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHHJHFN30",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{filePath,guide}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHHJHFN30PreEntry*/
			/*}#1IHHJHFN30PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHHJHFN30PostEntry*/
			/*}#1IHHJHFN30PostEntry*/
			return result;
		},
		/*#{1IHHJHFN30MoreAgentAttrs*/
		/*}#1IHHJHFN30MoreAgentAttrs*/
	};
	/*#{1IHHJHFN30PostAgent*/
	/*}#1IHHJHFN30PostAgent*/
	return agent;
};
/*#{1IHHJHFN30ExCodes*/
/*}#1IHHJHFN30ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolModifyFile",
		description: "修改文件内容的工具智能体，如修改文件内容，例如代码、配置文件。\n请提供要编辑的文件的完整路径，不要提供相对路径。\n本工具仅具备简单的编程能力。",
		parameters:{
			type: "object",
			properties:{
				filePath:{type:"string",description:"要修改的文件路径"},
				guide:{type:"string",description:"如何修改的说明"}
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IHHJHFN30PostDoc*/
/*}#1IHHJHFN30PostDoc*/


export default ToolModifyFile;
export{ToolModifyFile,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHHJHFN30",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHHJHFN31",
//			"attrs": {
//				"ToolModifyFile": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHHJHFN37",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHHJHFN38",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHHJHFN39",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHHJHFN310",
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
//			"jaxId": "1IHHJHFN32",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHHJHFN33",
//			"attrs": {
//				"filePath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHHJSDKO0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要修改的文件路径"
//					}
//				},
//				"guide": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHHJSDKO1",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "如何修改的说明"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHHJHFN34",
//			"attrs": {
//				"orgContent": {
//					"type": "string",
//					"valText": ""
//				},
//				"newContent": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IHHJHFN35",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHHJHFN36",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHHJSJTQ0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "85",
//						"y": "250",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IHHJVS0I0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHJSREJ0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHHJSREJ0",
//					"attrs": {
//						"id": "LoadFile",
//						"viewName": "",
//						"label": "",
//						"x": "285",
//						"y": "250",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHHJVS0J0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHJVS0J1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHHJVS0I1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHJTFSS0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IHHJTFSS0",
//					"attrs": {
//						"id": "CheckLoad",
//						"viewName": "",
//						"label": "",
//						"x": "500",
//						"y": "250",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHHJVS0J2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHJVS0J3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHHJVS0I3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IHHJUBTD0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHHJVS0I2",
//									"attrs": {
//										"id": "Success",
//										"desc": "输出节点。",
//										"output": "#guide",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHHJVS0J4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHHJVS0J5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#orgContent!==null"
//									},
//									"linkedSeg": "1IHHJV0QQ0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHHJUBTD0",
//					"attrs": {
//						"id": "FailResult",
//						"viewName": "",
//						"label": "",
//						"x": "760",
//						"y": "330",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHHJVS0J6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHJVS0J7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHHJVS0I4",
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
//					"def": "callLLM",
//					"jaxId": "1IHHJV0QQ0",
//					"attrs": {
//						"id": "AIModify",
//						"viewName": "",
//						"label": "",
//						"x": "760",
//						"y": "160",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHHJVS0J8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHJVS0J9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "",
//						"mode": "$fast",
//						"system": "#`---\n### 角色\n你是一个根据指令修改文件内容的AI\n\n---\n### 原始文件内容:\n\\`\\`\\`\n${orgContent}\n\\`\\`\\`\n\n${newContent?`\n---\n### 当前修改后的文件内容:\n${newContent}\n`:\"\"}\n\n---\n### 对话\n在每次对话时根据用户指令修改当前文件内容，用JSON返回。\n请把修改后的完整文件内容放到返回JOSN的\"content\"属性里\n{\n\t\"content\":\"...修改后的内容...\"\n}\n`",
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
//							"jaxId": "1IHHJVS0I5",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHK1ANQ0"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "20 messages",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IHHK1ANQ0",
//					"attrs": {
//						"id": "ShowDiff",
//						"viewName": "",
//						"label": "",
//						"x": "985",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IHHK8AH40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHK8AH41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IHHK8AH30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHK9L2R0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IHHK9L2R0",
//					"attrs": {
//						"id": "AskConfirm",
//						"viewName": "",
//						"label": "",
//						"x": "1205",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "是否照此修改文件？你也可以提出进一步修改意见",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IHHKBJBP0",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1IHHKCG9P0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHHK9L290",
//									"attrs": {
//										"id": "Confirm",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Confirm changes",
//											"localize": {
//												"EN": "Confirm changes",
//												"CN": "确认修改"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHHKBJBQ0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHHKBJBQ1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHHKDEUC0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHHK9L291",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Abort changes",
//											"localize": {
//												"EN": "Abort changes"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHHKBJBQ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHHKBJBQ3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHHKDU150"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IICCLNFO0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Manual edit",
//											"localize": {
//												"EN": "Manual edit",
//												"CN": "手动编辑"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IICCLNFR0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IICCLNFR1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IICCJPMR0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHHKCG9P0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1370",
//						"y": "265",
//						"outlet": {
//							"jaxId": "1IHHKE9OT0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHKCLOI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHHKCLOI0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "780",
//						"y": "265",
//						"outlet": {
//							"jaxId": "1IHHKE9OT1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHJV0QQ0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHHKDEUC0",
//					"attrs": {
//						"id": "Finsh",
//						"viewName": "",
//						"label": "",
//						"x": "1455",
//						"y": "45",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHHKE9OT2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHKE9OT3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHHKE9OR0",
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
//					"jaxId": "1IHHKDU150",
//					"attrs": {
//						"id": "Abort",
//						"viewName": "",
//						"label": "",
//						"x": "1455",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHHKE9OT4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHHKE9OT5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHHKE9OR1",
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
//					"def": "askUIDlg",
//					"jaxId": "1IICCJPMR0",
//					"attrs": {
//						"id": "EditCode",
//						"viewName": "",
//						"label": "",
//						"x": "1455",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IICCLNFR2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IICCLNFR3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "/@editkit/ui/DlgLongText.js",
//						"callArg": "#{title:\"Edit text\",text:newContent}",
//						"role": "Assistant",
//						"tip": "",
//						"showResult": "false",
//						"outlet": {
//							"jaxId": "1IICCLNFP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IICCPEDN0"
//						}
//					},
//					"icon": "idcard.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IICCPEDN0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1675",
//						"y": "195",
//						"outlet": {
//							"jaxId": "1IICCTCVK0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IICCPJ8J0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IICCPJ8J0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1710",
//						"y": "-30",
//						"outlet": {
//							"jaxId": "1IICCTCVK1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IICCPR5U0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IICCPR5U0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1020",
//						"y": "-30",
//						"outlet": {
//							"jaxId": "1IICCTCVK2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHHK1ANQ0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "修改文件内容的工具智能体，如修改文件内容，例如代码、配置文件。\n请提供要编辑的文件的完整路径，不要提供相对路径。\n本工具仅具备简单的编程能力。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}