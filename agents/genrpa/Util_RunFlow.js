//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JF9I9VVS0MoreImports*/
/*}#1JF9I9VVS0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"pageRef":{
			"name":"pageRef","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"flow":{
			"name":"flow","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"args":{
			"name":"args","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"opts":{
			"name":"opts","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JF9I9VVS0ArgsView*/
	/*}#1JF9I9VVS0ArgsView*/
};

/*#{1JF9I9VVS0StartDoc*/
/*}#1JF9I9VVS0StartDoc*/
//----------------------------------------------------------------------------
let Util_RunFlow=async function(session){
	let pageRef,flow,args,opts;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,Start,NextStep,HasQuery,QuerySelector,RunStep,CheckSelector,StepResult,FinDone,FinNextError,FailQuery,SkipStep,FinNoStep,RunCodeStep,FinAbort;
	let curStep=undefined;
	let stepAction=null;
	let flowPath="null";
	let lastResult=null;
	let execedSteps=[];
	let flowArgs=undefined;
	let flowOpts=undefined;
	let flowVars={};
	
	/*#{1JF9I9VVS0LocalVals*/
	let steps={};
	/*}#1JF9I9VVS0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			flow=input.flow;
			args=input.args;
			opts=input.opts;
		}else{
			pageRef=undefined;
			flow=undefined;
			args=undefined;
			opts=undefined;
		}
		/*#{1JF9I9VVS0ParseArgs*/
		flowArgs=args;
		flowOpts=opts;
		flowPath=flow.id;
		/*}#1JF9I9VVS0ParseArgs*/
	}
	
	/*#{1JF9I9VVS0PreContext*/
	/*}#1JF9I9VVS0PreContext*/
	context={};
	/*#{1JF9I9VVS0PostContext*/
	/*}#1JF9I9VVS0PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JF9IAF1M0
		let result=true;
		let aiQuery=true;
		let $alias="";
		let $url="";
		let $ref=pageRef;
		let $waitBefore=0;
		let $waitAfter=0;
		let $webRpa=null;
		try{
			if($ref){
				let $page,$browser;
				let $pageVal="aaPage";
				$page=WebRpa.getPageByRef($ref);
				context.rpaBrowser=$browser=$page.webDrive;
				context.webRpa=$webRpa=$browser.aaWebRpa;
				Object.defineProperty(context, $pageVal, {enumerable:true,get(){return $webRpa.currentPage},set(v){$webRpa.setCurrentPage(v)}});
				context[$pageVal]=$page;
			}else{
				let $pageVal="aaPage";
				context.webRpa=$webRpa=session.webRpa || new WebRpa(session);
				session.webRpa=$webRpa;
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JF9IAF1M0"));
				if($alias){
					let $headless=false;
					let $devtools=false;
					let options={$headless:false,$devtools:false,autoDataDir:false};
					let $browser=null;
					context.rpaBrowser=$browser=await context.webRpa.openBrowser($alias,options);
					context.rpaHostPage=$browser.hostPage;
					Object.defineProperty(context, $pageVal, {enumerable:true,get(){return $webRpa.currentPage},set(v){$webRpa.setCurrentPage(v)}});
					if($url){
						let $page=null;
						let $opts={};
						context[$pageVal]=$page=await $browser.newPage();
						await $page.goto($url,{});
					}
				}
			}
			$waitAfter && (await sleep($waitAfter));
		}catch(error){
			throw error;
		}
		return {seg:Start,result:(result),preSeg:"1JF9IAF1M0",outlet:"1JF9IAF1N0"};
	};
	StartRpa.jaxId="1JF9IAF1M0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["Start"]=Start=async function(input){//:1JF9IO87Q0
		let result=input
		try{
			/*#{1JF9IO87Q0Code*/
			let entry,step;
			for(step of flow.steps){
				steps[step.id]=step;
			}
			entry=flow.start;
			curStep=steps[entry];
			lastResult={status:"Ready",result:"Ready"};
			{
				let $channel="Process";
				let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
				let role="assistant";
				let content=`Util_RunFlow: [Start]: ${flow.id}`;
				session.addChatText(role,content,opts);
			}
			/*}#1JF9IO87Q0Code*/
		}catch(error){
			/*#{1JF9IO87Q0ErrorCode*/
			/*}#1JF9IO87Q0ErrorCode*/
		}
		return {seg:NextStep,result:(result),preSeg:"1JF9IO87Q0",outlet:"1JF9IOMS70"};
	};
	Start.jaxId="1JF9IO87Q0"
	Start.url="Start@"+agentURL
	
	segs["NextStep"]=NextStep=async function(input){//:1JF9ID44I0
		let result=input;
		/*#{1JF9ID44I0Start*/
		{
			let $channel="Process";
			let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
			let role="assistant";
			let content=`Util_RunFlow: [NextStep]: ${curStep?.id}`;
			session.addChatText(role,content,opts);
		}
		/*}#1JF9ID44I0Start*/
		if(curStep && curStep.action){
			let output=curStep;
			/*#{1JF9ID44I4Codes*/
			stepAction=curStep.action;
			/*}#1JF9ID44I4Codes*/
			return {seg:HasQuery,result:(output),preSeg:"1JF9ID44I0",outlet:"1JF9ID44I4"};
		}
		/*#{1JF9ID44I0Post*/
		/*}#1JF9ID44I0Post*/
		return {seg:FinNoStep,result:(result),preSeg:"1JF9ID44I0",outlet:"1JF9ID44I3"};
	};
	NextStep.jaxId="1JF9ID44I0"
	NextStep.url="NextStep@"+agentURL
	
	segs["HasQuery"]=HasQuery=async function(input){//:1JF9IEPFR0
		let result=input;
		/*#{1JF9IEPFR0Start*/
		/*}#1JF9IEPFR0Start*/
		if(stepAction.query && stepAction.type!=="js_code"){
			return {seg:QuerySelector,result:(input),preSeg:"1JF9IEPFR0",outlet:"1JF9IGO5D0"};
		}
		if(stepAction.type!=="js_code"){
			return {seg:RunStep,result:(input),preSeg:"1JF9IEPFR0",outlet:"1JFB9BF3S0"};
		}
		/*#{1JF9IEPFR0Post*/
		/*}#1JF9IEPFR0Post*/
		return {seg:RunCodeStep,result:(result),preSeg:"1JF9IEPFR0",outlet:"1JF9IGO5D1"};
	};
	HasQuery.jaxId="1JF9IEPFR0"
	HasQuery.url="HasQuery@"+agentURL
	
	segs["QuerySelector"]=QuerySelector=async function(input){//:1JF9IFLCQ0
		let result;
		let arg={"pageRef":pageRef,"query":curStep.action.query,"multiSelect":"","rulePath":flowPath+"_"+curStep.id,"opts":flowOpts};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./Util_QuerySelector.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CheckSelector,result:(result),preSeg:"1JF9IFLCQ0",outlet:"1JF9IGO5E0"};
	};
	QuerySelector.jaxId="1JF9IFLCQ0"
	QuerySelector.url="QuerySelector@"+agentURL
	
	segs["RunStep"]=RunStep=async function(input){//:1JF9IGANO0
		let result;
		let arg={"pageRef":pageRef,"action":curStep.action,"args":flowArgs,"opts":flowOpts,"vars":flowVars,"lastResult":lastResult};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./Util_StepAction.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:StepResult,result:(result),preSeg:"1JF9IGANO0",outlet:"1JF9IGO5E1"};
	};
	RunStep.jaxId="1JF9IGANO0"
	RunStep.url="RunStep@"+agentURL
	
	segs["CheckSelector"]=CheckSelector=async function(input){//:1JF9IHEG50
		let result=input;
		/*#{1JF9IHEG50Start*/
		let $status;
		$status=input.status.toLowerCase();
		/*}#1JF9IHEG50Start*/
		if($status==="failed"){
			return {seg:FailQuery,result:(input),preSeg:"1JF9IHEG50",outlet:"1JF9IIN7O0"};
		}
		if($status==="skipped"){
			let output=input;
			return {seg:SkipStep,result:(output),preSeg:"1JF9IHEG50",outlet:"1JF9JKU2K0"};
		}
		/*#{1JF9IHEG50Post*/
		switch(curStep.action.type){
			case "js_code":{
				break;
			}
			default:{
				curStep.action.by=input.selector||input.value;
				break;
			}
		}
		/*}#1JF9IHEG50Post*/
		return {seg:RunStep,result:(result),preSeg:"1JF9IHEG50",outlet:"1JF9IIN7O1"};
	};
	CheckSelector.jaxId="1JF9IHEG50"
	CheckSelector.url="CheckSelector@"+agentURL
	
	segs["StepResult"]=StepResult=async function(input){//:1JF9IJ7HH0
		let result=input;
		/*#{1JF9IJ7HH0Start*/
		if(true){
			let $channel="Process";
			let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
			let role="assistant";
			let content=`Util_RunFlow: [StepResult]: ${JSON.stringify(input)}}`;
			session.addChatText(role,content,opts);
		}
		let status,value,stepNext,nextType,nextStep;
		lastResult=input||{};
		status=(input?.status||"done").toLowerCase();
		if(status==="done" && curStep.saveAs && (typeof(input)==="object") && ("value" in input)){
			let saveAs=curStep.saveAs;
			const { parseFlowVal } = await import(pathLib.join(basePath, "./utils_flow.js"));
			let toSave = saveAs;
			if (typeof saveAs === "string") {
				// 旧模式，直接保存 result.value
				flowVars[saveAs] = input.value;
			} else if (saveAs && typeof saveAs === "object") {
				// 新模式，对象映射模式
				for (const key of Object.keys(saveAs)) {
					// 跳过危险属性
					if (key === "__proto__" || key === "constructor" || key === "prototype") continue;
					try {
						flowVars[key] = parseFlowVal(saveAs[key], flowArgs, flowOpts, flowVars, input);
					} catch (e) {
						flowVars[key] = undefined;
					}
				}
			}
		}
		if(curStep.action.type==="branch"){
			value=input?.value;
			curStep=steps[input?.nextStep];
		}else{
			value=input?.value;
			stepNext=curStep.next;
			nextType=typeof(stepNext);
			if(nextType==="string"){
				nextStep=stepNext;
			}else if(nextType==="object"){
				let router;
				router=stepNext.router;
				if(router){
					if(router instanceof Function){
						nextStep=await router(lastResult,flowArgs,flowVars,flowOpts);
					}else{
						throw Error("None function next-step-router is not supported yet.");
					}
				}else{
					nextStep=stepNext[status]||null;
				}
			}
			curStep=steps[nextStep];
		}
		if(!curStep && nextType==="object"){
			if(stepNext.default){
				nextStep=stepNext.default;
			}else{
				nextStep=stepNext["failed"]||null;
			}
			curStep=steps[nextStep];
		}
		/*}#1JF9IJ7HH0Start*/
		if(curStep?.action && curStep.action.type==="done"){
			return {seg:FinDone,result:(input),preSeg:"1JF9IJ7HH0",outlet:"1JFD7VF7H0"};
		}
		if(curStep?.action && curStep.action.type==="abort"){
			return {seg:FinAbort,result:(input),preSeg:"1JF9IJ7HH0",outlet:"1JFD7UONE0"};
		}
		if(curStep){
			let output=curStep;
			/*#{1JF9IKHE90Codes*/
			/*}#1JF9IKHE90Codes*/
			return {seg:NextStep,result:(output),preSeg:"1JF9IJ7HH0",outlet:"1JF9IKHE90"};
		}
		/*#{1JF9IJ7HH0Post*/
		/*}#1JF9IJ7HH0Post*/
		return {seg:FinNextError,result:(result),preSeg:"1JF9IJ7HH0",outlet:"1JF9ILTAC1"};
	};
	StepResult.jaxId="1JF9IJ7HH0"
	StepResult.url="StepResult@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JF9IM6620
		let result=input
		try{
			/*#{1JF9IM6620Code*/
			/*}#1JF9IM6620Code*/
		}catch(error){
			/*#{1JF9IM6620ErrorCode*/
			/*}#1JF9IM6620ErrorCode*/
		}
		return {result:result};
	};
	FinDone.jaxId="1JF9IM6620"
	FinDone.url="FinDone@"+agentURL
	
	segs["FinNextError"]=FinNextError=async function(input){//:1JF9IMGBK0
		let result=input
		try{
			/*#{1JF9IMGBK0Code*/
			/*}#1JF9IMGBK0Code*/
		}catch(error){
			/*#{1JF9IMGBK0ErrorCode*/
			/*}#1JF9IMGBK0ErrorCode*/
		}
		return {result:result};
	};
	FinNextError.jaxId="1JF9IMGBK0"
	FinNextError.url="FinNextError@"+agentURL
	
	segs["FailQuery"]=FailQuery=async function(input){//:1JF9IMQ9N0
		let result=input
		try{
			/*#{1JF9IMQ9N0Code*/
			/*}#1JF9IMQ9N0Code*/
		}catch(error){
			/*#{1JF9IMQ9N0ErrorCode*/
			/*}#1JF9IMQ9N0ErrorCode*/
		}
		return {seg:StepResult,result:(result),preSeg:"1JF9IMQ9N0",outlet:"1JF9IND0E0"};
	};
	FailQuery.jaxId="1JF9IMQ9N0"
	FailQuery.url="FailQuery@"+agentURL
	
	segs["SkipStep"]=SkipStep=async function(input){//:1JF9JMJTC0
		let result=input
		try{
			/*#{1JF9JMJTC0Code*/
			/*}#1JF9JMJTC0Code*/
		}catch(error){
			/*#{1JF9JMJTC0ErrorCode*/
			/*}#1JF9JMJTC0ErrorCode*/
		}
		return {seg:StepResult,result:(result),preSeg:"1JF9JMJTC0",outlet:"1JF9JNAEG0"};
	};
	SkipStep.jaxId="1JF9JMJTC0"
	SkipStep.url="SkipStep@"+agentURL
	
	segs["FinNoStep"]=FinNoStep=async function(input){//:1JFALJR7N0
		let result=input
		try{
			/*#{1JFALJR7N0Code*/
			/*}#1JFALJR7N0Code*/
		}catch(error){
			/*#{1JFALJR7N0ErrorCode*/
			/*}#1JFALJR7N0ErrorCode*/
		}
		return {result:result};
	};
	FinNoStep.jaxId="1JFALJR7N0"
	FinNoStep.url="FinNoStep@"+agentURL
	
	segs["RunCodeStep"]=RunCodeStep=async function(input){//:1JFB99HRT0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:StepResult,result:(result),preSeg:"1JFB99HRT0",outlet:"1JFB9BF3U0"};
	};
	RunCodeStep.jaxId="1JFB99HRT0"
	RunCodeStep.url="RunCodeStep@"+agentURL
	
	segs["FinAbort"]=FinAbort=async function(input){//:1JFD6ORII0
		let result=input
		try{
			/*#{1JFD6ORII0Code*/
			/*}#1JFD6ORII0Code*/
		}catch(error){
			/*#{1JFD6ORII0ErrorCode*/
			/*}#1JFD6ORII0ErrorCode*/
		}
		return {result:result};
	};
	FinAbort.jaxId="1JFD6ORII0"
	FinAbort.url="FinAbort@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"Util_RunFlow",
		url:agentURL,
		autoStart:true,
		jaxId:"1JF9I9VVS0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,flow,args,opts}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JF9I9VVS0PreEntry*/
			/*}#1JF9I9VVS0PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JF9I9VVS0PostEntry*/
			/*}#1JF9I9VVS0PostEntry*/
			return result;
		},
		/*#{1JF9I9VVS0MoreAgentAttrs*/
		/*}#1JF9I9VVS0MoreAgentAttrs*/
	};
	/*#{1JF9I9VVS0PostAgent*/
	/*}#1JF9I9VVS0PostAgent*/
	return agent;
};
/*#{1JF9I9VVS0ExCodes*/
/*}#1JF9I9VVS0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "Util_RunFlow",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				flow:{type:"auto",description:""},
				args:{type:"auto",description:""},
				opts:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1JF9I9VVS0PostDoc*/
/*}#1JF9I9VVS0PostDoc*/


export default Util_RunFlow;
export{Util_RunFlow,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JF9I9VVS0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JF9I9VVT0",
//			"attrs": {
//				"Util_RunFlow": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JF9I9VVT6",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JF9I9VVT7",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JF9I9VVT8",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JF9I9VVT9",
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
//			"jaxId": "1JF9I9VVT1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JF9I9VVT2",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF9IBQ6D0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flow": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF9IBQ6D1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"args": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF9IBQ6E0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"opts": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF9IBQ6E1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JF9I9VVT3",
//			"attrs": {
//				"curStep": {
//					"type": "auto",
//					"valText": ""
//				},
//				"stepAction": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"flowPath": {
//					"type": "string",
//					"valText": "null"
//				},
//				"lastResult": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"execedSteps": {
//					"type": "auto",
//					"valText": "[]"
//				},
//				"flowArgs": {
//					"type": "auto",
//					"valText": ""
//				},
//				"flowOpts": {
//					"type": "auto",
//					"valText": ""
//				},
//				"flowVars": {
//					"type": "auto",
//					"valText": "{}"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JF9I9VVT4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JF9I9VVT5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JF9IAF1M0",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "115",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF9IAF1M1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IAF1M2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"browser": "",
//						"headless": "false",
//						"devtools": "false",
//						"url": "",
//						"valName": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF9IAF1N0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9IO87Q0"
//						},
//						"catchlet": {
//							"jaxId": "1JF9IAF1N1",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JF9IAF1N2",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JF9IAF1N3",
//									"attrs": {
//										"cast": ""
//									}
//								}
//							}
//						},
//						"aiQuery": "true",
//						"autoCurrentPage": "true",
//						"ref": "#pageRef"
//					},
//					"icon": "start.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JF9IO87Q0",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "370",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9IOMS90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IOMS91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9IOMS70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9ID44I0"
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
//					"jaxId": "1JF9ID44I0",
//					"attrs": {
//						"id": "NextStep",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9ID44I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9ID44I2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9ID44I3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFALJR7N0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF9ID44I4",
//									"attrs": {
//										"id": "Step",
//										"desc": "输出节点。",
//										"output": "#curStep",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JF9ID44I5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF9ID44I6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curStep && curStep.action"
//									},
//									"linkedSeg": "1JF9IEPFR0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JF9IEPFR0",
//					"attrs": {
//						"id": "HasQuery",
//						"viewName": "",
//						"label": "",
//						"x": "895",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JF9IGO5F0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IGO5F1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9IGO5D1",
//							"attrs": {
//								"id": "Code",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFB99HRT0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF9IGO5D0",
//									"attrs": {
//										"id": "Query",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF9IGO5F2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF9IGO5F3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#stepAction.query && stepAction.type!==\"js_code\""
//									},
//									"linkedSeg": "1JF9IFLCQ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFB9BF3S0",
//									"attrs": {
//										"id": "NotCode",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFB9G0VB0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFB9G0VB1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#stepAction.type!==\"js_code\""
//									},
//									"linkedSeg": "1JFBIVJCP0"
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
//					"jaxId": "1JF9IFLCQ0",
//					"attrs": {
//						"id": "QuerySelector",
//						"viewName": "",
//						"label": "",
//						"x": "1150",
//						"y": "280",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JF9IGO5F4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IGO5F5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Util_QuerySelector.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"query\":\"#curStep.action.query\",\"multiSelect\":\"\",\"rulePath\":\"#flowPath+\\\"_\\\"+curStep.id\",\"opts\":\"#flowOpts\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JF9IGO5E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9IHEG50"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JF9IGANO0",
//					"attrs": {
//						"id": "RunStep",
//						"viewName": "",
//						"label": "",
//						"x": "1725",
//						"y": "355",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9IGO5F6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IGO5F7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Util_StepAction.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"action\":\"#curStep.action\",\"args\":\"#flowArgs\",\"opts\":\"#flowOpts\",\"vars\":\"#flowVars\",\"lastResult\":\"#lastResult\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JF9IGO5E1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9IJ7HH0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JF9IHEG50",
//					"attrs": {
//						"id": "CheckSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1430",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9IIN7Q0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IIN7Q1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9IIN7O1",
//							"attrs": {
//								"id": "Selector",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JF9IGANO0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF9IIN7O0",
//									"attrs": {
//										"id": "Failed",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF9IIN7Q2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF9IIN7Q3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#$status===\"failed\""
//									},
//									"linkedSeg": "1JF9IMQ9N0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF9JKU2K0",
//									"attrs": {
//										"id": "Skip",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF9JNAEI0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF9JNAEI1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#$status===\"skipped\""
//									},
//									"linkedSeg": "1JF9JMJTC0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JF9IJ7HH0",
//					"attrs": {
//						"id": "StepResult",
//						"viewName": "",
//						"label": "",
//						"x": "1980",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9ILTAD0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9ILTAD1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9ILTAC1",
//							"attrs": {
//								"id": "NoNext",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JF9IMGBK0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFD7VF7H0",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFD7VF7M0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFD7VF7M1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curStep?.action && curStep.action.type===\"done\""
//									},
//									"linkedSeg": "1JF9IM6620"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFD7UONE0",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFD7VF7M2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFD7VF7M3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curStep?.action && curStep.action.type===\"abort\""
//									},
//									"linkedSeg": "1JFD6ORII0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF9IKHE90",
//									"attrs": {
//										"id": "Next",
//										"desc": "输出节点。",
//										"output": "#curStep",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JF9ILTAD2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF9ILTAD3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curStep"
//									},
//									"linkedSeg": "1JF9IL8ML0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JF9IL8ML0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2130",
//						"y": "120",
//						"outlet": {
//							"jaxId": "1JF9ILTAD8",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9ILDO60"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JF9ILDO60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "660",
//						"y": "120",
//						"outlet": {
//							"jaxId": "1JF9ILTAD9",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9ID44I0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JF9IM6620",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9IMM4H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IMM4H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9IMM4G0",
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
//					"def": "code",
//					"jaxId": "1JF9IMGBK0",
//					"attrs": {
//						"id": "FinNextError",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9IMM4H2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IMM4H3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9IMM4G1",
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
//					"def": "code",
//					"jaxId": "1JF9IMQ9N0",
//					"attrs": {
//						"id": "FailQuery",
//						"viewName": "",
//						"label": "",
//						"x": "1725",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9IND0H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IND0H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9IND0E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9IJ7HH0"
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
//					"jaxId": "1JF9JMJTC0",
//					"attrs": {
//						"id": "SkipStep",
//						"viewName": "",
//						"label": "",
//						"x": "1725",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9JNAEI2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9JNAEI3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9JNAEG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9IJ7HH0"
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
//					"jaxId": "1JFALJR7N0",
//					"attrs": {
//						"id": "FinNoStep",
//						"viewName": "",
//						"label": "",
//						"x": "895",
//						"y": "530",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFALLP9N0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFALLP9N1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFALLP9K0",
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
//					"def": "aiBot",
//					"jaxId": "1JFB99HRT0",
//					"attrs": {
//						"id": "RunCodeStep",
//						"viewName": "",
//						"label": "",
//						"x": "1150",
//						"y": "435",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFB9G0VB2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFB9G0VB3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JFB9BF3U0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBIH2FB0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JFBIH2FB0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1825",
//						"y": "435",
//						"outlet": {
//							"jaxId": "1JFBIHACI0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9IJ7HH0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JFBIVJCP0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1150",
//						"y": "355",
//						"outlet": {
//							"jaxId": "1JFBJ041Q2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9IGANO0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JFD6ORII0",
//					"attrs": {
//						"id": "FinAbort",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFD6P5PV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFD6P5PV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFD6P5PP0",
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
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}