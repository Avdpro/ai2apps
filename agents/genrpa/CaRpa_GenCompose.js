//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JF1LRBT00MoreImports*/
/*}#1JF1LRBT00MoreImports*/
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
		"url":{
			"name":"url","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"profile":{
			"name":"profile","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"compose":{
			"name":"compose","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"opts":{
			"name":"opts","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JF1LRBT00ArgsView*/
	/*}#1JF1LRBT00ArgsView*/
};

/*#{1JF1LRBT00StartDoc*/
/*}#1JF1LRBT00StartDoc*/
//----------------------------------------------------------------------------
let CaRpa_GenCompose=async function(session){
	let pageRef,url,profile,compose,opts;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,OnAction,LoadFlow,CheckFlow,FailFlowError2,HasParent,FailFlowError1,RunFlow;
	let composeType="";
	let flow=undefined;
	let args=undefined;
	let flowArgs=undefined;
	let flowOpts=undefined;
	
	/*#{1JF1LRBT00LocalVals*/
	/*}#1JF1LRBT00LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			url=input.url;
			profile=input.profile;
			compose=input.compose;
			opts=input.opts;
		}else{
			pageRef=undefined;
			url=undefined;
			profile=undefined;
			compose=undefined;
			opts=undefined;
		}
		/*#{1JF1LRBT00ParseArgs*/
		flowArgs=compose;
		flowOpts=opts;
		/*}#1JF1LRBT00ParseArgs*/
	}
	
	/*#{1JF1LRBT00PreContext*/
	/*}#1JF1LRBT00PreContext*/
	context={};
	/*#{1JF1LRBT00PostContext*/
	/*}#1JF1LRBT00PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JF1LRNS90
		let result=true;
		let aiQuery=true;
		let $alias=profile;
		let $url=url;
		let $ref=pageRef;
		let $waitBefore=0;
		let $waitAfter=0;
		try{
			if($ref){
				let $page,$browser;
				let $pageVal="aaPage";
				$page=WebRpa.getPageByRef($ref);
				context.rpaBrowser=$browser=$page.webDrive;
				context[$pageVal]=$page;
				context.webRpa=$browser.aaWebRpa;
			}else{
				context.webRpa=session.webRpa || new WebRpa(session);
				session.webRpa=context.webRpa;
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JF1LRNS90"));
				if($alias){
					let $headless=false;
					let $devtools=false;
					let options={$headless:false,$devtools:false,autoDataDir:false};
					let $browser=null;
					context.rpaBrowser=$browser=await context.webRpa.openBrowser($alias,options);
					context.rpaHostPage=$browser.hostPage;
					if($url){
						let $page=null;
						let $pageVal="aaPage";
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
		return {seg:OnAction,result:(result),preSeg:"1JF1LRNS90",outlet:"1JF1LRNS93"};
	};
	StartRpa.jaxId="1JF1LRNS90"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["OnAction"]=OnAction=async function(input){//:1JF1LS3750
		let result=input;
		/*#{1JF1LS3750Start*/
		let flow;
		/*}#1JF1LS3750Start*/
		if(compose.action==="start"){
			/*#{1JF1LTU0V0Codes*/
			/*}#1JF1LTU0V0Codes*/
			return {seg:HasParent,result:(input),preSeg:"1JF1LS3750",outlet:"1JF1LTU0V0"};
		}
		/*#{1JF1LS3750Post*/
		/*}#1JF1LS3750Post*/
		return {seg:LoadFlow,result:(result),preSeg:"1JF1LS3750",outlet:"1JF1LTU0V1"};
	};
	OnAction.jaxId="1JF1LS3750"
	OnAction.url="OnAction@"+agentURL
	
	segs["LoadFlow"]=LoadFlow=async function(input){//:1JFAJGUTO0
		let result=input;
		/*#{1JFAJGUTO0Start*/
		let action,$flow;
		action=compose?.action||"NA";
		try{
			$flow=(await import(`./flows/compose_${action.toLowerCase()}.js`)).default;
		}catch(err){
			$flow=null;
		}
		/*}#1JFAJGUTO0Start*/
		if(!!$flow && $flow.steps && $flow.id){
			/*#{1JFAJI0RB0Codes*/
			flow=$flow;
			args={...compose};
			/*}#1JFAJI0RB0Codes*/
			return {seg:RunFlow,result:(input),preSeg:"1JFAJGUTO0",outlet:"1JFAJI0RB0"};
		}
		/*#{1JFAJGUTO0Post*/
		/*}#1JFAJGUTO0Post*/
		return {seg:FailFlowError1,result:(result),preSeg:"1JFAJGUTO0",outlet:"1JFAJI0RB1"};
	};
	LoadFlow.jaxId="1JFAJGUTO0"
	LoadFlow.url="LoadFlow@"+agentURL
	
	segs["CheckFlow"]=CheckFlow=async function(input){//:1JF1SQ27K0
		let result=input;
		/*#{1JF1SQ27K0Start*/
		/*}#1JF1SQ27K0Start*/
		if(input==="Failed"){
			return {seg:FailFlowError2,result:(input),preSeg:"1JF1SQ27K0",outlet:"1JF1SRHNT0"};
		}
		/*#{1JF1SQ27K0Post*/
		/*}#1JF1SQ27K0Post*/
		return {seg:RunFlow,result:(result),preSeg:"1JF1SQ27K0",outlet:"1JF1SRHNT1"};
	};
	CheckFlow.jaxId="1JF1SQ27K0"
	CheckFlow.url="CheckFlow@"+agentURL
	
	segs["FailFlowError2"]=FailFlowError2=async function(input){//:1JF1SRCQG0
		let result=input
		try{
			/*#{1JF1SRCQG0Code*/
			/*}#1JF1SRCQG0Code*/
		}catch(error){
			/*#{1JF1SRCQG0ErrorCode*/
			/*}#1JF1SRCQG0ErrorCode*/
		}
		return {result:result};
	};
	FailFlowError2.jaxId="1JF1SRCQG0"
	FailFlowError2.url="FailFlowError2@"+agentURL
	
	segs["HasParent"]=HasParent=async function(input){//:1JF1T9CQM0
		let result=input;
		/*#{1JF1T9CQM0Start*/
		/*}#1JF1T9CQM0Start*/
		if(compose.parent){
			return {seg:CheckFlow,result:(input),preSeg:"1JF1T9CQM0",outlet:"1JF1TEAVQ0"};
		}
		/*#{1JF1T9CQM0Post*/
		/*}#1JF1T9CQM0Post*/
		return {seg:LoadFlow,result:(result),preSeg:"1JF1T9CQM0",outlet:"1JF1TEAVQ1"};
	};
	HasParent.jaxId="1JF1T9CQM0"
	HasParent.url="HasParent@"+agentURL
	
	segs["FailFlowError1"]=FailFlowError1=async function(input){//:1JF1TDPQJ0
		let result=input
		try{
			/*#{1JF1TDPQJ0Code*/
			result={status:"Failed",result:"Failed",reason:`Can't find work flow for action: "${compose?.action}".`};
			/*}#1JF1TDPQJ0Code*/
		}catch(error){
			/*#{1JF1TDPQJ0ErrorCode*/
			/*}#1JF1TDPQJ0ErrorCode*/
		}
		return {result:result};
	};
	FailFlowError1.jaxId="1JF1TDPQJ0"
	FailFlowError1.url="FailFlowError1@"+agentURL
	
	segs["RunFlow"]=RunFlow=async function(input){//:1JF9JQ6GG0
		let result;
		let arg={"pageRef":pageRef,"flow":flow,"args":flowArgs,"opts":flowOpts};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./Util_RunFlow.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JF9JQ6GG0Input*/
		/*}#1JF9JQ6GG0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JF9JQ6GG0Output*/
		/*}#1JF9JQ6GG0Output*/
		return {result:result};
	};
	RunFlow.jaxId="1JF9JQ6GG0"
	RunFlow.url="RunFlow@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CaRpa_GenCompose",
		url:agentURL,
		autoStart:true,
		jaxId:"1JF1LRBT00",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,url,profile,compose,opts}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JF1LRBT00PreEntry*/
			/*}#1JF1LRBT00PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JF1LRBT00PostEntry*/
			/*}#1JF1LRBT00PostEntry*/
			return result;
		},
		/*#{1JF1LRBT00MoreAgentAttrs*/
		/*}#1JF1LRBT00MoreAgentAttrs*/
	};
	/*#{1JF1LRBT00PostAgent*/
	/*}#1JF1LRBT00PostAgent*/
	return agent;
};
/*#{1JF1LRBT00ExCodes*/
/*}#1JF1LRBT00ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CaRpa_GenCompose",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				url:{type:"auto",description:""},
				profile:{type:"auto",description:""},
				compose:{type:"auto",description:""},
				opts:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1JF1LRBT00PostDoc*/
/*}#1JF1LRBT00PostDoc*/


export default CaRpa_GenCompose;
export{CaRpa_GenCompose,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JF1LRBT00",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JF1LRBT01",
//			"attrs": {
//				"CaRpa_GenCompose": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JF1LRBT07",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JF1LRBT08",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JF1LRBT09",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JF1LRBT010",
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
//			"jaxId": "1JF1LRBT02",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JF1LRBT03",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF1S6LES0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF1S6LET0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"profile": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF1S6LET1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"compose": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF1S6LET2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"opts": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFAK63A40",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JF1LRBT04",
//			"attrs": {
//				"composeType": {
//					"type": "string",
//					"valText": ""
//				},
//				"flow": {
//					"type": "auto",
//					"valText": ""
//				},
//				"args": {
//					"type": "auto",
//					"valText": ""
//				},
//				"flowArgs": {
//					"type": "auto",
//					"valText": ""
//				},
//				"flowOpts": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JF1LRBT05",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JF1LRBT06",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JF1LRNS90",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "125",
//						"y": "450",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1LRNS91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1LRNS92",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"browser": "#profile",
//						"headless": "false",
//						"devtools": "false",
//						"url": "#url",
//						"valName": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF1LRNS93",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1LS3750"
//						},
//						"catchlet": {
//							"jaxId": "1JF1LRNS94",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JF1LRNS95",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JF1LRNS96",
//									"attrs": {
//										"cast": ""
//									}
//								}
//							}
//						},
//						"aiQuery": "true",
//						"ref": "#pageRef"
//					},
//					"icon": "start.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JF1LS3750",
//					"attrs": {
//						"id": "OnAction",
//						"viewName": "",
//						"label": "",
//						"x": "375",
//						"y": "435",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JF1LTU100",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1LTU101",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1LTU0V1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFAJGUTO0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1LTU0V0",
//									"attrs": {
//										"id": "Start",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JF1LTU102",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1LTU103",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#compose.action===\"start\""
//									},
//									"linkedSeg": "1JF1T9CQM0"
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
//					"jaxId": "1JFAJGUTO0",
//					"attrs": {
//						"id": "LoadFlow",
//						"viewName": "",
//						"label": "",
//						"x": "870",
//						"y": "450",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFAJI0RG0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFAJI0RG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFAJI0RB1",
//							"attrs": {
//								"id": "Failed",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JF1TDPQJ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFAJI0RB0",
//									"attrs": {
//										"id": "Flow",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JFAJI0RG2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFAJI0RG3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!$flow && $flow.steps && $flow.id"
//									},
//									"linkedSeg": "1JF9JQ6GG0"
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
//					"jaxId": "1JF1SQ27K0",
//					"attrs": {
//						"id": "CheckFlow",
//						"viewName": "",
//						"label": "",
//						"x": "870",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF1SRHO20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1SRHO21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1SRHNT1",
//							"attrs": {
//								"id": "Flow",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JF9JQ6GG0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1SRHNT0",
//									"attrs": {
//										"id": "Failed",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1SRHO22",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1SRHO23",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JF1SRCQG0"
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
//					"jaxId": "1JF1SRCQG0",
//					"attrs": {
//						"id": "FailFlowError2",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "310",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF1SRHO24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1SRHO25",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1SRHNT2",
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
//					"jaxId": "1JF1T9CQM0",
//					"attrs": {
//						"id": "HasParent",
//						"viewName": "",
//						"label": "",
//						"x": "615",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF1TEB000",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1TEB001",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1TEAVQ1",
//							"attrs": {
//								"id": "Root",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFAJGUTO0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1TEAVQ0",
//									"attrs": {
//										"id": "Parent",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1TEB002",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1TEB003",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#compose.parent"
//									},
//									"linkedSeg": "1JF1SQ27K0"
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
//					"jaxId": "1JF1TDPQJ0",
//					"attrs": {
//						"id": "FailFlowError1",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "550",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF1TEB006",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1TEB007",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1TEAVR0",
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
//					"jaxId": "1JF9JQ6GG0",
//					"attrs": {
//						"id": "RunFlow",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "435",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JF9JQAAV2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9JQAAV3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Util_RunFlow.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"flow\":\"#flow\",\"args\":\"#flowArgs\",\"opts\":\"#flowOpts\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JF9JQAAS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
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