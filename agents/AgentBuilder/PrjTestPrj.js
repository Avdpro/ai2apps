//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IHDD1EHD0MoreImports*/
import AATask from "./Task.js";
/*}#1IHDD1EHD0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
/*#{1IHDD1EHD0StartDoc*/
/*}#1IHDD1EHD0StartDoc*/
//----------------------------------------------------------------------------
let PrjTestPrj=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,InitEnv,GetTestPlan,TestType,BashTest,PageTest,TipResult,ShowPlan,AskUser,ConfirmAbort,AbortTest,EndTest,WaitManual,ManualIssue,FailTest;
	let env=globalContext.env;
	let project=globalContext.project;
	let testPlan="";
	let task=undefined;
	
	/*#{1IHDD1EHD0LocalVals*/
	/*}#1IHDD1EHD0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IHDD1EHD0ParseArgs*/
		/*}#1IHDD1EHD0ParseArgs*/
	}
	
	/*#{1IHDD1EHD0PreContext*/
	/*}#1IHDD1EHD0PreContext*/
	context={};
	/*#{1IHDD1EHD0PostContext*/
	/*}#1IHDD1EHD0PostContext*/
	let agent,segs={};
	segs["Start"]=Start=async function(input){//:1II22LJHS0
		let result=input;
		/*#{1II22LJHS0Code*/
		false
		/*}#1II22LJHS0Code*/
		return {seg:InitEnv,result:(result),preSeg:"1II22LJHS0",outlet:"1II22MS4G0",catchSeg:FailTest,catchlet:"1II22MS4G1"};
	};
	Start.jaxId="1II22LJHS0"
	Start.url="Start@"+agentURL
	
	segs["InitEnv"]=InitEnv=async function(input){//:1IHDD2DOC0
		let result=input
		/*#{1IHDD2DOC0Code*/
		task=new AATask(session,task,"测试项目是否成功部署");
		result="请给出测试方案";
		/*}#1IHDD2DOC0Code*/
		return {seg:GetTestPlan,result:(result),preSeg:"1IHDD2DOC0",outlet:"1IHDD8UR30"};
	};
	InitEnv.jaxId="1IHDD2DOC0"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["GetTestPlan"]=GetTestPlan=async function(input){//:1IHDD2QV20
		let prompt;
		let result;
		
		let opts={
			platform:"",
			mode:"$plan",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=GetTestPlan.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
---
### 角色任务
你是一个根据当前项目部署的环境以及项目内容，设计测试项目是否正确部署/安装的AI。

---
### 环境和项目
当前的系统软硬件环境和系统参数为：
\`\`\`
${JSON.stringify(env,null,"\t")}
\`\`\`

当前的项目是：${project.name}。
${project.dirPath?`当前项目所在的文件路径是: "${project.dirPath}"。`:""}  

当前项目已经下载/安装/部署完毕，你只需要生成测试方案，不要在你的方案里包括下载/安装/部署相关的内容。

---
### 项目的Readme内容：
\`\`\`markdown
${project.readme}
\`\`\`

---
### 输出：
你必须请用JSON格式返回结果，例如：
{
	"type":"CommandLine",
	"plan":"项目XXX是一个……当前系统可以部署本项目，注意本项目处于测试阶段，可能存在问题。",
}

- 参数"type" {string}: 测试方式类型包括
	- "CommandLine": 测试可以在Terminal/Bash的命令行执行，并查看结果完成。
    - "WebUI": 测试需要浏览器访问项目启动后的网址来检验结果
    - "Other": 测试需要其它的方式/手段完成，建议用户手动测试。
- 参数"plan" {string}: 测试的具体流程计划。
	- 针对当前软硬件环境生成计划，不要生成与当前环境无关的内容
    - 一步一步的生成测试方案，针对每一步给出具体操作指导
    - 包含如何检测结果是否成功的步骤以及如何评判是否成功
    - 字符串是用markdown格式的文档

---
### 对话
用户可能会对你的方案提出修改意见，你根据用户的参考意见，每轮对话输出新的测试方案。

`},
		];
		messages.push(...chatMem);
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		result=await session.callSegLLM("GetTestPlan@"+agentURL,opts,messages,true);
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
		}
		result=trimJSON(result);
		return {seg:ShowPlan,result:(result),preSeg:"1IHDD2QV20",outlet:"1IHDD8UR31"};
	};
	GetTestPlan.jaxId="1IHDD2QV20"
	GetTestPlan.url="GetTestPlan@"+agentURL
	GetTestPlan.messages=[];
	
	segs["TestType"]=TestType=async function(input){//:1IHDD46FO0
		let result=input;
		if(input.type==="CommandLine"){
			return {seg:BashTest,result:(input),preSeg:"1IHDD46FO0",outlet:"1IHDD8UR32"};
		}
		if(input.type==="WebUI"){
			return {seg:PageTest,result:(input),preSeg:"1IHDD46FO0",outlet:"1IHDD4H8P0"};
		}
		return {seg:WaitManual,result:(result),preSeg:"1IHDD46FO0",outlet:"1IHDD8UR33"};
	};
	TestType.jaxId="1IHDD46FO0"
	TestType.url="TestType@"+agentURL
	
	segs["BashTest"]=BashTest=async function(input){//:1IHDD60840
		let result;
		let sourcePath=pathLib.join(basePath,"./SysHandleTask.js");
		let arg={"task":"测试项目","roleTask":"你是一个测试已经部署完成的项目的AI智能体，你根据当前的测试方案，一步一步的测试当前项目","prjDesc":"","guide":input.plan,"tools":"bashTest","handleIssue":true};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:TipResult,result:(result),preSeg:"1IHDD60840",outlet:"1IHDD8UR34"};
	};
	BashTest.jaxId="1IHDD60840"
	BashTest.url="BashTest@"+agentURL
	
	segs["PageTest"]=PageTest=async function(input){//:1IHDD6JHE0
		let result;
		let sourcePath=pathLib.join(basePath,"./SysHandleTask.js");
		let arg={"task":"测试项目","roleTask":"你是一个测试已经部署完成的项目的AI智能体，你根据当前的测试方案，一步一步的测试当前项目","prjDesc":"","guide":input.plan,"tools":"webUITest","handleIssue":true};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:TipResult,result:(result),preSeg:"1IHDD6JHE0",outlet:"1IHDD8UR40"};
	};
	PageTest.jaxId="1IHDD6JHE0"
	PageTest.url="PageTest@"+agentURL
	
	segs["TipResult"]=TipResult=async function(input){//:1IHDD7VA40
		let result=input;
		let role="assistant";
		let content=input.content;
		session.addChatText(role,content);
		return {seg:EndTest,result:(result),preSeg:"1IHDD7VA40",outlet:"1IHDD8UR42"};
	};
	TipResult.jaxId="1IHDD7VA40"
	TipResult.url="TipResult@"+agentURL
	
	segs["ShowPlan"]=ShowPlan=async function(input){//:1IHO65G2T0
		let result=input;
		let role="assistant";
		let content=`## 测试方案：
${input.plan}
`;
		/*#{1IHO65G2T0PreCodes*/
		/*}#1IHO65G2T0PreCodes*/
		session.addChatText(role,content);
		/*#{1IHO65G2T0PostCodes*/
		testPlan=input.plan;
		/*}#1IHO65G2T0PostCodes*/
		return {seg:AskUser,result:(result),preSeg:"1IHO65G2T0",outlet:"1IHO6H24A0"};
	};
	ShowPlan.jaxId="1IHO65G2T0"
	ShowPlan.url="ShowPlan@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1IHO66UE40
		let prompt=("是否执行当前测试方案？你可以提出意见修改当前方案")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"执行测试",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"放弃测试",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result=input;
			return {seg:TestType,result:(result),preSeg:"1IHO66UE40",outlet:"1IHO66UDI0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:true,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {seg:GetTestPlan,result:(result),preSeg:"1IHO66UE40",outlet:"1IHO6H24B0"};
		}else if(item.code===0){
			result=(input);
			return {seg:TestType,result:(result),preSeg:"1IHO66UE40",outlet:"1IHO66UDI0"};
		}else if(item.code===1){
			result=(input);
			return {seg:ConfirmAbort,result:(result),preSeg:"1IHO66UE40",outlet:"1IHO66UDI1"};
		}
	};
	AskUser.jaxId="1IHO66UE40"
	AskUser.url="AskUser@"+agentURL
	
	segs["ConfirmAbort"]=ConfirmAbort=async function(input){//:1IHO6A3R10
		let prompt=("确认放弃测试项目？")||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=("放弃测试")||"OK";
		let button2=("不放弃")||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:AbortTest,result:(result),preSeg:"1IHO6A3R10",outlet:"1IHO6A3QI0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:AbortTest,result:(result),preSeg:"1IHO6A3R10",outlet:"1IHO6A3QI0"};
		}
		result=(input)||result;
		return {seg:AskUser,result:(result),preSeg:"1IHO6A3R10",outlet:"1IHO6A3QI1"};
	
	};
	ConfirmAbort.jaxId="1IHO6A3R10"
	ConfirmAbort.url="ConfirmAbort@"+agentURL
	
	segs["AbortTest"]=AbortTest=async function(input){//:1IHO6CL3S0
		let result=input
		/*#{1IHO6CL3S0Code*/
		task.abort("用户放弃测试。");
		result={result:"Abort",content:"用户放弃测试。"};
		/*}#1IHO6CL3S0Code*/
		return {result:result};
	};
	AbortTest.jaxId="1IHO6CL3S0"
	AbortTest.url="AbortTest@"+agentURL
	
	segs["EndTest"]=EndTest=async function(input){//:1IHO6GMG60
		let result=input
		/*#{1IHO6GMG60Code*/
		//Do nothing?
		if(input.reault==="Finish"){
			task.finish(input.content);
		}else{
			task.fail(input.content);
		}
		/*}#1IHO6GMG60Code*/
		return {result:result};
	};
	EndTest.jaxId="1IHO6GMG60"
	EndTest.url="EndTest@"+agentURL
	
	segs["WaitManual"]=WaitManual=async function(input){//:1II20REIJ0
		let prompt=((($ln==="CN")?("请按照测试说明进行手动测试。如果测试通过，请点击测试完成按钮。如果测试过程中出现任何问题，请输入您发现的问题。"):("Please follow the test instructions and perform manual testing. If the test passes, click the test complete button. If any issues occur during testing, input the issue you found.")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"测试完毕",code:0},
		];
		let result="";
		let item=null;
		
		if(silent){
			result={result:"Finish",content:"手动测试通过。"};
			return {seg:EndTest,result:(result),preSeg:"1II20REIJ0",outlet:"1II20REI20"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:true,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {seg:ManualIssue,result:(result),preSeg:"1II20REIJ0",outlet:"1II211K660"};
		}else if(item.code===0){
			result=({result:"Finish",content:"手动测试通过。"});
			return {seg:EndTest,result:(result),preSeg:"1II20REIJ0",outlet:"1II20REI20"};
		}
	};
	WaitManual.jaxId="1II20REIJ0"
	WaitManual.url="WaitManual@"+agentURL
	
	segs["ManualIssue"]=ManualIssue=async function(input){//:1II21F4C50
		let result;
		let sourcePath=pathLib.join(basePath,"./SysHandleIssue.js");
		let arg={"issue":`测试项目遇到问题: ${input}`,"issueBrief":"手动测试未通过"};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:EndTest,result:(result),preSeg:"1II21F4C50",outlet:"1II21JDCQ0"};
	};
	ManualIssue.jaxId="1II21F4C50"
	ManualIssue.url="ManualIssue@"+agentURL
	
	segs["FailTest"]=FailTest=async function(input){//:1II22MFGO0
		let result=input
		/*#{1II22MFGO0Code*/
		task.fail("执行测试遇到错误: "+input);
		result={result:"Failed",content:`测试的时候遇到异常错误：${input}，测试失败。`};
		/*}#1II22MFGO0Code*/
		return {result:result};
	};
	FailTest.jaxId="1II22MFGO0"
	FailTest.url="FailTest@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"PrjTestPrj",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHDD1EHD0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IHDD1EHD0PreEntry*/
			/*}#1IHDD1EHD0PreEntry*/
			result={seg:Start,"input":input};
			/*#{1IHDD1EHD0PostEntry*/
			/*}#1IHDD1EHD0PostEntry*/
			return result;
		},
		/*#{1IHDD1EHD0MoreAgentAttrs*/
		endChat:async function(result){
			if(task){
				task.endTask();
			}
			return result;
		}
		/*}#1IHDD1EHD0MoreAgentAttrs*/
	};
	/*#{1IHDD1EHD0PostAgent*/
	/*}#1IHDD1EHD0PostAgent*/
	return agent;
};
/*#{1IHDD1EHD0ExCodes*/
/*}#1IHDD1EHD0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "PrjTestPrj",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IHDD1EHD0PostDoc*/
/*}#1IHDD1EHD0PostDoc*/


export default PrjTestPrj;
export{PrjTestPrj,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHDD1EHD0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHDD1EHD1",
//			"attrs": {
//				"PrjTestPrj": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHDD1EHE0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHDD1EHE1",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHDD1EHE2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHDD1EHE3",
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
//			"jaxId": "1IHDD1EHD2",
//			"attrs": {}
//		},
//		"entry": "Start",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHDD1EHD3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IHDD1EHD4",
//			"attrs": {
//				"env": {
//					"type": "auto",
//					"valText": "#globalContext.env"
//				},
//				"project": {
//					"type": "auto",
//					"valText": "#globalContext.project"
//				},
//				"testPlan": {
//					"type": "string",
//					"valText": ""
//				},
//				"task": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IHDD1EHD5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHDD1EHD6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1II22LJHS0",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "95",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II22NO210",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II22NO211",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1II22MS4G0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHDD2DOC0"
//						},
//						"catchlet": {
//							"jaxId": "1II22MS4G1",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II22MFGO0"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHDD2DOC0",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "300",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHDD8UR50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHDD8UR51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHDD8UR30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHDD2QV20"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IHDD2QV20",
//					"attrs": {
//						"id": "GetTestPlan",
//						"viewName": "",
//						"label": "",
//						"x": "500",
//						"y": "265",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHDD8UR52",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHDD8UR53",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "",
//						"mode": "$plan",
//						"system": "#`\n---\n### 角色任务\n你是一个根据当前项目部署的环境以及项目内容，设计测试项目是否正确部署/安装的AI。\n\n---\n### 环境和项目\n当前的系统软硬件环境和系统参数为：\n\\`\\`\\`\n${JSON.stringify(env,null,\"\\t\")}\n\\`\\`\\`\n\n当前的项目是：${project.name}。\n${project.dirPath?`当前项目所在的文件路径是: \"${project.dirPath}\"。`:\"\"}  \n\n当前项目已经下载/安装/部署完毕，你只需要生成测试方案，不要在你的方案里包括下载/安装/部署相关的内容。\n\n---\n### 项目的Readme内容：\n\\`\\`\\`markdown\n${project.readme}\n\\`\\`\\`\n\n---\n### 输出：\n你必须请用JSON格式返回结果，例如：\n{\n\t\"type\":\"CommandLine\",\n\t\"plan\":\"项目XXX是一个……当前系统可以部署本项目，注意本项目处于测试阶段，可能存在问题。\",\n}\n\n- 参数\"type\" {string}: 测试方式类型包括\n\t- \"CommandLine\": 测试可以在Terminal/Bash的命令行执行，并查看结果完成。\n    - \"WebUI\": 测试需要浏览器访问项目启动后的网址来检验结果\n    - \"Other\": 测试需要其它的方式/手段完成，建议用户手动测试。\n- 参数\"plan\" {string}: 测试的具体流程计划。\n\t- 针对当前软硬件环境生成计划，不要生成与当前环境无关的内容\n    - 一步一步的生成测试方案，针对每一步给出具体操作指导\n    - 包含如何检测结果是否成功的步骤以及如何评判是否成功\n    - 字符串是用markdown格式的文档\n\n---\n### 对话\n用户可能会对你的方案提出修改意见，你根据用户的参考意见，每轮对话输出新的测试方案。\n\n`",
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
//							"jaxId": "1IHDD8UR31",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHO65G2T0"
//						},
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IHDD46FO0",
//					"attrs": {
//						"id": "TestType",
//						"viewName": "",
//						"label": "",
//						"x": "1215",
//						"y": "75",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHDD8UR54",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHDD8UR55",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHDD8UR33",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1II20REIJ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHDD8UR32",
//									"attrs": {
//										"id": "Bash",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHDD8UR56",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHDD8UR57",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.type===\"CommandLine\""
//									},
//									"linkedSeg": "1IHDD60840"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHDD4H8P0",
//									"attrs": {
//										"id": "Page",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHDD8UR58",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHDD8UR59",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.type===\"WebUI\""
//									},
//									"linkedSeg": "1IHDD6JHE0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IHDD60840",
//					"attrs": {
//						"id": "BashTest",
//						"viewName": "",
//						"label": "",
//						"x": "1470",
//						"y": "0",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHDD8UR510",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHDD8UR511",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysHandleTask.js",
//						"argument": "{\"task\":\"测试项目\",\"roleTask\":\"你是一个测试已经部署完成的项目的AI智能体，你根据当前的测试方案，一步一步的测试当前项目\",\"prjDesc\":\"\",\"guide\":\"#input.plan\",\"tools\":\"bashTest\",\"handleIssue\":\"#true\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IHDD8UR34",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHDD7VA40"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IHDD6JHE0",
//					"attrs": {
//						"id": "PageTest",
//						"viewName": "",
//						"label": "",
//						"x": "1470",
//						"y": "75",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHDD8UR512",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHDD8UR513",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysHandleTask.js",
//						"argument": "{\"task\":\"测试项目\",\"roleTask\":\"你是一个测试已经部署完成的项目的AI智能体，你根据当前的测试方案，一步一步的测试当前项目\",\"prjDesc\":\"\",\"guide\":\"#input.plan\",\"tools\":\"webUITest\",\"handleIssue\":\"#true\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IHDD8UR40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHDD7VA40"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IHDD7VA40",
//					"attrs": {
//						"id": "TipResult",
//						"viewName": "",
//						"label": "",
//						"x": "1705",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IHDD8UR516",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHDD8UR517",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input.content",
//						"outlet": {
//							"jaxId": "1IHDD8UR42",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHO6GMG60"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IHO65G2T0",
//					"attrs": {
//						"id": "ShowPlan",
//						"viewName": "",
//						"label": "",
//						"x": "720",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHO6H24F0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHO6H24F1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`## 测试方案：\n${input.plan}\n`",
//						"outlet": {
//							"jaxId": "1IHO6H24A0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHO66UE40"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IHO66UE40",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "935",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "是否执行当前测试方案？你可以提出意见修改当前方案",
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1IHO6H24B0",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1II1GVEE20"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHO66UDI0",
//									"attrs": {
//										"id": "Test",
//										"desc": "输出节点。",
//										"text": "执行测试",
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHO6H24F2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHO6H24F3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHDD46FO0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHO66UDI1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "放弃测试",
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHO6H24F4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHO6H24F5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHO6A3R10"
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
//					"def": "askConfirm",
//					"jaxId": "1IHO6A3R10",
//					"attrs": {
//						"id": "ConfirmAbort",
//						"viewName": "",
//						"label": "",
//						"x": "1215",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "确认放弃测试项目？",
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHO6A3QI0",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "放弃测试",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHO6H24F6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHO6H24F7",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHO6CL3S0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHO6A3QI1",
//									"attrs": {
//										"id": "NotAbort",
//										"desc": "输出节点。",
//										"text": "不放弃",
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHO6H24F8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHO6H24F9",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHO6C7FH0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHO6C7FH0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1390",
//						"y": "375",
//						"outlet": {
//							"jaxId": "1IHO6H24F10",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHO6CE2F0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHO6CE2F0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "960",
//						"y": "375",
//						"outlet": {
//							"jaxId": "1IHO6H24F11",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHO66UE40"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHO6CL3S0",
//					"attrs": {
//						"id": "AbortTest",
//						"viewName": "",
//						"label": "",
//						"x": "1470",
//						"y": "250",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHO6H24F12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHO6H24F13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHO6H24B1",
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
//					"jaxId": "1IHO6GMG60",
//					"attrs": {
//						"id": "EndTest",
//						"viewName": "",
//						"label": "",
//						"x": "1965",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IHO6H24F14",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHO6H24F15",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHO6H24B2",
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
//					"def": "connector",
//					"jaxId": "1II1GVEE20",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1080",
//						"y": "435",
//						"outlet": {
//							"jaxId": "1II1H273C0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II1H0G470"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1II1H0G470",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "530",
//						"y": "435",
//						"outlet": {
//							"jaxId": "1II1H273C1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHDD2QV20"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1II20REIJ0",
//					"attrs": {
//						"id": "WaitManual",
//						"viewName": "",
//						"label": "",
//						"x": "1470",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Please follow the test instructions and perform manual testing. If the test passes, click the test complete button. If any issues occur during testing, input the issue you found.",
//							"localize": {
//								"EN": "Please follow the test instructions and perform manual testing. If the test passes, click the test complete button. If any issues occur during testing, input the issue you found.",
//								"CN": "请按照测试说明进行手动测试。如果测试通过，请点击测试完成按钮。如果测试过程中出现任何问题，请输入您发现的问题。"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1II211K660",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1II21F4C50"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1II20REI20",
//									"attrs": {
//										"id": "TestOK",
//										"desc": "输出节点。",
//										"text": "测试完毕",
//										"result": "#{result:\"Finish\",content:\"手动测试通过。\"}",
//										"codes": "false",
//										"context": {
//											"jaxId": "1II21JDCU0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1II21JDCU1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1II21E33F0"
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
//					"def": "connectorL",
//					"jaxId": "1II21E33F0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1705",
//						"y": "115",
//						"outlet": {
//							"jaxId": "1II21JDCU2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II21G6DE0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1II21F4C50",
//					"attrs": {
//						"id": "ManualIssue",
//						"viewName": "",
//						"label": "",
//						"x": "1715",
//						"y": "215",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II21JDCU3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II21JDCU4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysHandleIssue.js",
//						"argument": "{\"issue\":\"#`测试项目遇到问题: ${input}`\",\"issueBrief\":\"手动测试未通过\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1II21JDCQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHO6GMG60"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1II21G6DE0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1820",
//						"y": "115",
//						"outlet": {
//							"jaxId": "1II21JDCU5",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHO6GMG60"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1II22MFGO0",
//					"attrs": {
//						"id": "FailTest",
//						"viewName": "",
//						"label": "",
//						"x": "300",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II22NO220",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II22NO221",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1II22MS4G2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}