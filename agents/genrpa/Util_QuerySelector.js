//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JF9IR9640MoreImports*/
import {urlToJsonName,readJson,saveJson,resolveUrl,buildRpaMicroDeciderPrompt,readRule,saveRule} from "./utils.js";
/*}#1JF9IR9640MoreImports*/
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
		"query":{
			"name":"query","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"rulePath":{
			"name":"rulePath","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JF9IR9640ArgsView*/
	/*}#1JF9IR9640ArgsView*/
};

/*#{1JF9IR9640StartDoc*/
/*}#1JF9IR9640StartDoc*/
//----------------------------------------------------------------------------
let Util_QuerySelector=async function(session){
	let pageRef,query,rulePath;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,ReadRule,CheckSkip,FinSkip,LoopSelectors,QueryRule,BreakFind,CheckFind,FindSelector,CheckSelector,FailSelector,FinDone,SaveRule;
	let ruleSelectors=undefined;
	let curRuleSelector="";
	let checkedSelector="";
	
	/*#{1JF9IR9640LocalVals*/
	/*}#1JF9IR9640LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			query=input.query;
			rulePath=input.rulePath;
		}else{
			pageRef=undefined;
			query=undefined;
			rulePath=undefined;
		}
		/*#{1JF9IR9640ParseArgs*/
		/*}#1JF9IR9640ParseArgs*/
	}
	
	/*#{1JF9IR9640PreContext*/
	/*}#1JF9IR9640PreContext*/
	context={};
	/*#{1JF9IR9640PostContext*/
	/*}#1JF9IR9640PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JF9ISD5T0
		let result=true;
		let aiQuery=true;
		let $alias="";
		let $url="";
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JF9ISD5T0"));
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
		return {seg:ReadRule,result:(result),preSeg:"1JF9ISD5T0",outlet:"1JF9ISD5T3"};
	};
	StartRpa.jaxId="1JF9ISD5T0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["ReadRule"]=ReadRule=async function(input){//:1JF9IT8CG0
		let result=input;
		/*#{1JF9IT8CG0Start*/
		let rule;
		rule=await readRule(session,context.aaPage,rulePath);
		/*}#1JF9IT8CG0Start*/
		if(rule){
			let output=rule;
			return {seg:CheckSkip,result:(output),preSeg:"1JF9IT8CG0",outlet:"1JF9IT8CH3"};
		}
		/*#{1JF9IT8CG0Post*/
		/*}#1JF9IT8CG0Post*/
		return {seg:FindSelector,result:(result),preSeg:"1JF9IT8CG0",outlet:"1JF9IT8CH2"};
	};
	ReadRule.jaxId="1JF9IT8CG0"
	ReadRule.url="ReadRule@"+agentURL
	
	segs["CheckSkip"]=CheckSkip=async function(input){//:1JF9IU0260
		let result=input;
		/*#{1JF9IU0260Start*/
		if(typeof(input)==="string"){
			ruleSelectors=[input];
		}else if(Array.isArray(input)){
			ruleSelectors=[...input].reverse();;
		}
		/*}#1JF9IU0260Start*/
		if(input==="skip"){
			return {seg:FinSkip,result:(input),preSeg:"1JF9IU0260",outlet:"1JF9IU0264"};
		}
		if(ruleSelectors){
			return {seg:LoopSelectors,result:(input),preSeg:"1JF9IU0260",outlet:"1JFDAOTIF0"};
		}
		/*#{1JF9IU0260Post*/
		/*}#1JF9IU0260Post*/
		return {seg:FindSelector,result:(result),preSeg:"1JF9IU0260",outlet:"1JF9IU0263"};
	};
	CheckSkip.jaxId="1JF9IU0260"
	CheckSkip.url="CheckSkip@"+agentURL
	
	segs["FinSkip"]=FinSkip=async function(input){//:1JF9IUAK60
		let result=input
		try{
			/*#{1JF9IUAK60Code*/
			/*}#1JF9IUAK60Code*/
		}catch(error){
			/*#{1JF9IUAK60ErrorCode*/
			/*}#1JF9IUAK60ErrorCode*/
		}
		return {result:result};
	};
	FinSkip.jaxId="1JF9IUAK60"
	FinSkip.url="FinSkip@"+agentURL
	
	segs["LoopSelectors"]=LoopSelectors=async function(input){//:1JF9IUNK00
		let result=input;
		let list=ruleSelectors;
		let i,n,item,loopR;
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			loopR=await session.runAISeg(agent,QueryRule,item,"1JF9IUNK00","1JF9IUNK03")
			if(loopR==="break"){
				break;
			}
		}
		return {seg:CheckFind,result:(result),preSeg:"1JF9IUNK00",outlet:"1JF9IUNK04"};
	};
	LoopSelectors.jaxId="1JF9IUNK00"
	LoopSelectors.url="LoopSelectors@"+agentURL
	
	segs["QueryRule"]=QueryRule=async function(input){//:1JF9J0OB91
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query=input;
		let $multi=false;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1JF9J0OB91PreCodes*/
		curRuleSelector=input;
		/*}#1JF9J0OB91PreCodes*/
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			/*#{1JF9J0OB91CheckItem*/
			/*}#1JF9J0OB91CheckItem*/
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JF9J0OB91ErrorCode*/
			/*}#1JF9J0OB91ErrorCode*/
		}
		/*#{1JF9J0OB91PostCodes*/
		/*}#1JF9J0OB91PostCodes*/
		return {seg:BreakFind,result:(result),preSeg:"1JF9J0OB91",outlet:"1JF9J0OB94"};
	};
	QueryRule.jaxId="1JF9J0OB91"
	QueryRule.url="QueryRule@"+agentURL
	
	segs["BreakFind"]=BreakFind=async function(input){//:1JF9J15UK0
		let result=input
		try{
			/*#{1JF9J15UK0Code*/
			checkedSelector=curRuleSelector;
			result="break";
			/*}#1JF9J15UK0Code*/
		}catch(error){
			/*#{1JF9J15UK0ErrorCode*/
			/*}#1JF9J15UK0ErrorCode*/
		}
		return {result:result};
	};
	BreakFind.jaxId="1JF9J15UK0"
	BreakFind.url="BreakFind@"+agentURL
	
	segs["CheckFind"]=CheckFind=async function(input){//:1JF9J1PGL0
		let result=input;
		if(checkedSelector){
			return {seg:FinDone,result:(input),preSeg:"1JF9J1PGL0",outlet:"1JF9J1PGL4"};
		}
		return {seg:FindSelector,result:(result),preSeg:"1JF9J1PGL0",outlet:"1JF9J1PGL3"};
	};
	CheckFind.jaxId="1JF9J1PGL0"
	CheckFind.url="CheckFind@"+agentURL
	
	segs["FindSelector"]=FindSelector=async function(input){//:1JF9J2J820
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CheckSelector,result:(result),preSeg:"1JF9J2J820",outlet:"1JF9J2J830"};
	};
	FindSelector.jaxId="1JF9J2J820"
	FindSelector.url="FindSelector@"+agentURL
	
	segs["CheckSelector"]=CheckSelector=async function(input){//:1JF9J31E70
		let result=input;
		if(input==="Selector"){
			return {seg:SaveRule,result:(input),preSeg:"1JF9J31E70",outlet:"1JF9J31E80"};
		}
		return {seg:FailSelector,result:(result),preSeg:"1JF9J31E70",outlet:"1JF9J31E73"};
	};
	CheckSelector.jaxId="1JF9J31E70"
	CheckSelector.url="CheckSelector@"+agentURL
	
	segs["FailSelector"]=FailSelector=async function(input){//:1JF9J3L100
		let result=input
		try{
			/*#{1JF9J3L100Code*/
			/*}#1JF9J3L100Code*/
		}catch(error){
			/*#{1JF9J3L100ErrorCode*/
			/*}#1JF9J3L100ErrorCode*/
		}
		return {result:result};
	};
	FailSelector.jaxId="1JF9J3L100"
	FailSelector.url="FailSelector@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JF9J40NV0
		let result=input
		try{
			/*#{1JF9J40NV0Code*/
			/*}#1JF9J40NV0Code*/
		}catch(error){
			/*#{1JF9J40NV0ErrorCode*/
			/*}#1JF9J40NV0ErrorCode*/
		}
		return {result:result};
	};
	FinDone.jaxId="1JF9J40NV0"
	FinDone.url="FinDone@"+agentURL
	
	segs["SaveRule"]=SaveRule=async function(input){//:1JF9J5R210
		let result=input
		try{
			/*#{1JF9J5R210Code*/
			/*}#1JF9J5R210Code*/
		}catch(error){
			/*#{1JF9J5R210ErrorCode*/
			/*}#1JF9J5R210ErrorCode*/
		}
		return {seg:FinDone,result:(result),preSeg:"1JF9J5R210",outlet:"1JF9J72R00"};
	};
	SaveRule.jaxId="1JF9J5R210"
	SaveRule.url="SaveRule@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"Util_QuerySelector",
		url:agentURL,
		autoStart:true,
		jaxId:"1JF9IR9640",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,query,rulePath}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JF9IR9640PreEntry*/
			/*}#1JF9IR9640PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JF9IR9640PostEntry*/
			/*}#1JF9IR9640PostEntry*/
			return result;
		},
		/*#{1JF9IR9640MoreAgentAttrs*/
		/*}#1JF9IR9640MoreAgentAttrs*/
	};
	/*#{1JF9IR9640PostAgent*/
	/*}#1JF9IR9640PostAgent*/
	return agent;
};
/*#{1JF9IR9640ExCodes*/
/*}#1JF9IR9640ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "Util_QuerySelector",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				query:{type:"auto",description:""},
				rulePath:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1JF9IR9640PostDoc*/
/*}#1JF9IR9640PostDoc*/


export default Util_QuerySelector;
export{Util_QuerySelector,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JF9IR9640",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JF9IR9641",
//			"attrs": {
//				"Util_QuerySelector": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JF9IR9647",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JF9IR9648",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JF9IR9649",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JF9IR96410",
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
//			"jaxId": "1JF9IR9642",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JF9IR9643",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF9JA1440",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"query": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF9JA1441",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"rulePath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF9JA1442",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JF9IR9644",
//			"attrs": {
//				"ruleSelectors": {
//					"type": "auto",
//					"valText": ""
//				},
//				"curRuleSelector": {
//					"type": "string",
//					"valText": ""
//				},
//				"checkedSelector": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JF9IR9645",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JF9IR9646",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JF9ISD5T0",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "105",
//						"y": "335",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF9ISD5T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9ISD5T2",
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
//							"jaxId": "1JF9ISD5T3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9IT8CG0"
//						},
//						"catchlet": {
//							"jaxId": "1JF9ISD5T4",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JF9ISD5T5",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JF9ISD5T6",
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
//					"jaxId": "1JF9IT8CG0",
//					"attrs": {
//						"id": "ReadRule",
//						"viewName": "",
//						"label": "",
//						"x": "350",
//						"y": "320",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JF9IT8CH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IT8CH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9IT8CH2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JF9J4R080"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF9IT8CH3",
//									"attrs": {
//										"id": "Rule",
//										"desc": "输出节点。",
//										"output": "#rule",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF9IT8CH4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF9IT8CH5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#rule"
//									},
//									"linkedSeg": "1JF9IU0260"
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
//					"jaxId": "1JF9IU0260",
//					"attrs": {
//						"id": "CheckSkip",
//						"viewName": "",
//						"label": "",
//						"x": "590",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9IU0261",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IU0262",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9IU0263",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFDAPS5E0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF9IU0264",
//									"attrs": {
//										"id": "Skip",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF9IU0265",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF9IU0266",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input===\"skip\""
//									},
//									"linkedSeg": "1JF9IUAK60"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFDAOTIF0",
//									"attrs": {
//										"id": "Selectors",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFDAQ8SI0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFDAQ8SI1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#ruleSelectors"
//									},
//									"linkedSeg": "1JF9IUNK00"
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
//					"jaxId": "1JF9IUAK60",
//					"attrs": {
//						"id": "FinSkip",
//						"viewName": "",
//						"label": "",
//						"x": "840",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9IUAK61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IUAK62",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9IUAK63",
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
//					"def": "loopArray",
//					"jaxId": "1JF9IUNK00",
//					"attrs": {
//						"id": "LoopSelectors",
//						"viewName": "",
//						"label": "",
//						"x": "840",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF9IUNK01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9IUNK02",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#ruleSelectors",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1JF9IUNK03",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9J0OB91"
//						},
//						"catchlet": {
//							"jaxId": "1JF9IUNK04",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9J1PGL0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JF9J0OB91",
//					"attrs": {
//						"id": "QueryRule",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9J0OB92",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9J0OB93",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "#input",
//						"queryHint": "",
//						"multi": "false",
//						"options": "",
//						"errorSeg": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF9J0OB94",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9J15UK0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JF9J0OB95",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									}
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JF9J15UK0",
//					"attrs": {
//						"id": "BreakFind",
//						"viewName": "",
//						"label": "",
//						"x": "1405",
//						"y": "310",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9J15UK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9J15UL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9J15UL1",
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
//					"jaxId": "1JF9J1PGL0",
//					"attrs": {
//						"id": "CheckFind",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "475",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9J1PGL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9J1PGL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9J1PGL3",
//							"attrs": {
//								"id": "NotFind",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JF9J2J820"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF9J1PGL4",
//									"attrs": {
//										"id": "Find",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF9J1PGL5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF9J1PGL6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#checkedSelector"
//									},
//									"linkedSeg": "1JF9J40NV0"
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
//					"jaxId": "1JF9J2J820",
//					"attrs": {
//						"id": "FindSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1405",
//						"y": "575",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9J2J821",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9J2J822",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JF9J2J830",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9J31E70"
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
//					"jaxId": "1JF9J31E70",
//					"attrs": {
//						"id": "CheckSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1650",
//						"y": "575",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9J31E71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9J31E72",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9J31E73",
//							"attrs": {
//								"id": "Failed",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JF9J3L100"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF9J31E80",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF9J31E81",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF9J31E82",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JF9J5R210"
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
//					"jaxId": "1JF9J3L100",
//					"attrs": {
//						"id": "FailSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1930",
//						"y": "655",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9J3L101",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9J3L102",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9J3L103",
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
//					"jaxId": "1JF9J40NV0",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "2180",
//						"y": "460",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9J72R20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9J72R21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9J72QV0",
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
//					"def": "connectorL",
//					"jaxId": "1JF9J4R080",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "590",
//						"y": "575",
//						"outlet": {
//							"jaxId": "1JF9J72R22",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFDAPS5E0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JF9J5R210",
//					"attrs": {
//						"id": "SaveRule",
//						"viewName": "",
//						"label": "",
//						"x": "1930",
//						"y": "560",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF9J72R23",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9J72R24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9J72R00",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9J40NV0"
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
//					"def": "connectorL",
//					"jaxId": "1JFDAPS5E0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "850",
//						"y": "575",
//						"outlet": {
//							"jaxId": "1JFDAQ8SI2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9J2J820"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}