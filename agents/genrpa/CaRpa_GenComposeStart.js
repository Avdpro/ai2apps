//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JESG24QU0MoreImports*/
import {urlToJsonName,readJson,saveJson,resolveUrl,buildRpaMicroDeciderPrompt,readRule,saveRule} from "./utils.js";
/*}#1JESG24QU0MoreImports*/
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
		"waitAfter":{
			"name":"waitAfter","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"compose":{
			"name":"compose","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JESG24QU0ArgsView*/
	/*}#1JESG24QU0ArgsView*/
};

/*#{1JESG24QU0StartDoc*/
/*}#1JESG24QU0StartDoc*/
//----------------------------------------------------------------------------
let CaRpa_GenComposeStart=async function(session){
	let pageRef,url,profile,waitAfter,compose;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,CheckRule,FindClick,ReadPage,FindStart,ClickStart,FinDone,FinFailed,WaitAfter,FinNoStart,CheckNewRule,SaveRule,GotoPage,ReadResult,ChecjStart,CheckError;
	let usedRule=null;
	let wrongSelectors=[];
	
	/*#{1JESG24QU0LocalVals*/
	/*}#1JESG24QU0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			url=input.url;
			profile=input.profile;
			waitAfter=input.waitAfter;
			compose=input.compose;
		}else{
			pageRef=undefined;
			url=undefined;
			profile=undefined;
			waitAfter=undefined;
			compose=undefined;
		}
		/*#{1JESG24QU0ParseArgs*/
		/*}#1JESG24QU0ParseArgs*/
	}
	
	/*#{1JESG24QU0PreContext*/
	/*}#1JESG24QU0PreContext*/
	context={
		searchResult: "",
		/*#{1JE5HADIA5ExCtxAttrs*/
		/*}#1JE5HADIA5ExCtxAttrs*/
	};
	/*#{1JESG24QU0PostContext*/
	/*}#1JESG24QU0PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JE5JK3AB0
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JE5JK3AB0"));
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
		return {seg:CheckRule,result:(result),preSeg:"1JE5JK3AB0",outlet:"1JE5JK3AB3"};
	};
	StartRpa.jaxId="1JE5JK3AB0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["CheckRule"]=CheckRule=async function(input){//:1JE5JN9BL0
		let result=input;
		/*#{1JE5JN9BL0Start*/
		let rule=await readRule(session,context.aaPage,"search");
		/*}#1JE5JN9BL0Start*/
		if(rule && rule.url){
			let output=rule.url;
			return {seg:GotoPage,result:(output),preSeg:"1JE5JN9BL0",outlet:"1JE5JN9BM0"};
		}
		if(rule && rule.click){
			let output=rule.click;
			return {seg:FindClick,result:(output),preSeg:"1JE5JN9BL0",outlet:"1JEBIG15I0"};
		}
		/*#{1JE5JN9BL0Post*/
		/*}#1JE5JN9BL0Post*/
		return {seg:ReadPage,result:(result),preSeg:"1JE5JN9BL0",outlet:"1JE5JN9BL3"};
	};
	CheckRule.jaxId="1JE5JN9BL0"
	CheckRule.url="CheckRule@"+agentURL
	
	segs["FindClick"]=FindClick=async function(input){//:1JE5JVJ4R1
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
		/*#{1JE5JVJ4R1PreCodes*/
		/*}#1JE5JVJ4R1PreCodes*/
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JE5JVJ4R1ErrorCode*/
			wrongSelectors.push($query);
			/*}#1JE5JVJ4R1ErrorCode*/
			return {seg:ReadPage,result:error,preSeg:"1JE5JVJ4R1",outlet:"1JE5JVJ4S1"};
		}
		/*#{1JE5JVJ4R1PostCodes*/
		result=$query;
		/*}#1JE5JVJ4R1PostCodes*/
		return {seg:ClickStart,result:(result),preSeg:"1JE5JVJ4R1",outlet:"1JE5JVJ4S0"};
	};
	FindClick.jaxId="1JE5JVJ4R1"
	FindClick.url="FindClick@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1JE5K5CHS0
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $target="cleanHTML";
		$waitBefore && (await sleep($waitBefore));
		try{
			switch($target){
				case "cleanHTML":{
					result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:true,...$options});
					break;
				}
				case "html":{
					result=await context.webRpa.getInnerHTML(page,$node);
					break;
				}
				case "view":{
					result=await context.webRpa.readNodeView(page,$node,{removeHidden:false,...$options});
					break;
				}
				case "text":{
					result=await context.webRpa.readNodeText(page,$node,{removeHidden:false,...$options});
					break;
				}
				case "article":{
					result=await context.webRpa.readArticle(page,$node,{removeHidden:false,...$options});
					break;
				}
			}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JE5K5CHS0ErrorCode*/
			/*}#1JE5K5CHS0ErrorCode*/
		}
		return {seg:FindStart,result:(result),preSeg:"1JE5K5CHS0",outlet:"1JE5K8RPV0"};
	};
	ReadPage.jaxId="1JE5K5CHS0"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["FindStart"]=FindStart=async function(input){//:1JE5K5SH60
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-4.1";
		let $agent;
		let result=null;
		/*#{1JE5K5SH60Input*/
		let $system=buildRpaMicroDeciderPrompt(
			"给定当前页面清洗后的HTML代码，确认当前页面是否有可以点击后输入搜索的元素，如果是，返回启动输入搜索需要点击的HTML的定位语句。",
			'如果找到输入搜索的元素，返回"selector"动作。'+
			'如果当前页面虽然有搜索元素，但是被Cookie/登录等对话框遮挡，需要先去除遮挡，返回"removeBlocker"动作。'+
			'如果当前页面里不存在搜索功能，无法开始搜索，返回"abort"动作'+
			(wrongSelectors.length?`\n\n重要: 已知：${JSON.stringify(wrongSelectors)} 这些selector是错误无效的，不要重复给出重复的错误答案。`:""),
			["selector","removeBlocker"]
		);
		/*}#1JE5K5SH60Input*/
		
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
		let chatMem=FindStart.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:$system},
		];
		/*#{1JE5K5SH60PrePrompt*/
		/*}#1JE5K5SH60PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JE5K5SH60FilterMessage*/
			/*}#1JE5K5SH60FilterMessage*/
			messages.push(msg);
		}
		/*#{1JE5K5SH60PreCall*/
		/*}#1JE5K5SH60PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("FindStart@"+agentURL,opts,messages,true)):result;
		}
		result=trimJSON(result);
		/*#{1JE5K5SH60PostCall*/
		/*}#1JE5K5SH60PostCall*/
		if(result && result.action && result.action.type==="selector"){
			let output=result.action.by;
			return {seg:ClickStart,result:(output),preSeg:"1JE5K5SH60",outlet:"1JE5K8RPV1"};
		}
		if(input==="NoFind"){
			return {seg:FinNoStart,result:(input),preSeg:"1JE5K5SH60",outlet:"1JE6NJK780"};
		}
		/*#{1JE5K5SH60PreResult*/
		/*}#1JE5K5SH60PreResult*/
		return {seg:FinNoStart,result:(result),preSeg:"1JE5K5SH60",outlet:"1JE5K8RPV2"};
	};
	FindStart.jaxId="1JE5K5SH60"
	FindStart.url="FindStart@"+agentURL
	
	segs["ClickStart"]=ClickStart=async function(input){//:1JE5K7TEP0
		let result=true;
		let pageVal="aaPage";
		let $query=input;
		let $queryHint="";
		let $x=0;
		let $y=0;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		/*#{1JE5K7TEP0PreCodes*/
		let isWrong=false;
		/*}#1JE5K7TEP0PreCodes*/
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JE5K7TEP0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.click($query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
			}else{
				$pms=page.mouse.click($x,$y,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JE5K7TEP0ErrorCode*/
			isWrong=true;
			wrongSelectors.push($query);
			/*}#1JE5K7TEP0ErrorCode*/
			return {seg:FindStart,result:error,preSeg:"1JE5K7TEP0",outlet:null};
		}
		/*#{1JE5K7TEP0PostCodes*/
		usedRule={click:$query};
		/*}#1JE5K7TEP0PostCodes*/
		return {seg:ReadResult,result:(result),preSeg:"1JE5K7TEP0",outlet:"1JE5K8RPV3"};
	};
	ClickStart.jaxId="1JE5K7TEP0"
	ClickStart.url="ClickStart@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JE5KGERJ0
		let result=input
		try{
			/*#{1JE5KGERJ0Code*/
			result={status:"Done",result:"Finish",items:context.searchResult||[]};
			/*}#1JE5KGERJ0Code*/
		}catch(error){
			/*#{1JE5KGERJ0ErrorCode*/
			/*}#1JE5KGERJ0ErrorCode*/
		}
		return {seg:WaitAfter,result:(result),preSeg:"1JE5KGERJ0",outlet:"1JE5KJIBS1"};
	};
	FinDone.jaxId="1JE5KGERJ0"
	FinDone.url="FinDone@"+agentURL
	
	segs["FinFailed"]=FinFailed=async function(input){//:1JE5KGM2I0
		let result=input
		try{
			/*#{1JE5KGM2I0Code*/
			result={status:"Failed", result: "Failed", reason: input && input.reason ? input.reason : "Search process failed."};
			/*}#1JE5KGM2I0Code*/
		}catch(error){
			/*#{1JE5KGM2I0ErrorCode*/
			/*}#1JE5KGM2I0ErrorCode*/
		}
		return {result:result};
	};
	FinFailed.jaxId="1JE5KGM2I0"
	FinFailed.url="FinFailed@"+agentURL
	
	segs["WaitAfter"]=WaitAfter=async function(input){//:1JE5KJ1SM0
		let result=true;
		let pageVal="aaPage";
		let $flag="";
		let $waitBefore=0;
		let $waitAfter=waitAfter;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			result=$flag?(await context[$flag]):input;
		}catch(error){
			return {result:error};
		}
		$waitAfter && (await sleep($waitAfter))
		return {result:result};
	};
	WaitAfter.jaxId="1JE5KJ1SM0"
	WaitAfter.url="WaitAfter@"+agentURL
	
	segs["FinNoStart"]=FinNoStart=async function(input){//:1JE5KMS000
		let result=input
		try{
			/*#{1JE5KMS000Code*/
			result={status:"Failed",result:"Failed",reason:"Can't initial search。"};
			/*}#1JE5KMS000Code*/
		}catch(error){
			/*#{1JE5KMS000ErrorCode*/
			/*}#1JE5KMS000ErrorCode*/
		}
		return {result:result};
	};
	FinNoStart.jaxId="1JE5KMS000"
	FinNoStart.url="FinNoStart@"+agentURL
	
	segs["CheckNewRule"]=CheckNewRule=async function(input){//:1JE5KRV8T0
		let result=input;
		if(usedRule){
			let output=input;
			return {seg:SaveRule,result:(output),preSeg:"1JE5KRV8T0",outlet:"1JE5KU7D50"};
		}
		return {seg:FinDone,result:(result),preSeg:"1JE5KRV8T0",outlet:"1JE5KU7D51"};
	};
	CheckNewRule.jaxId="1JE5KRV8T0"
	CheckNewRule.url="CheckNewRule@"+agentURL
	
	segs["SaveRule"]=SaveRule=async function(input){//:1JE5KTD4C0
		let result=input
		try{
			/*#{1JE5KTD4C0Code*/
			await saveRule(session,context.aaPage,"search",usedRule);
			/*}#1JE5KTD4C0Code*/
		}catch(error){
			/*#{1JE5KTD4C0ErrorCode*/
			/*}#1JE5KTD4C0ErrorCode*/
		}
		return {seg:FinDone,result:(result),preSeg:"1JE5KTD4C0",outlet:"1JE5KU7D52"};
	};
	SaveRule.jaxId="1JE5KTD4C0"
	SaveRule.url="SaveRule@"+agentURL
	
	segs["GotoPage"]=GotoPage=async function(input){//:1JEBI23L30
		let result=true;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let timeout=(undefined)||0;
		let url=input;
		let page=context[pageVal];
		let opts={timeout:timeout};
		waitBefore && (await sleep(waitBefore));
		try{
			await page.goto(url,opts);
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JEBI23L30ErrorCode*/
			/*}#1JEBI23L30ErrorCode*/
		}
		return {result:result};
	};
	GotoPage.jaxId="1JEBI23L30"
	GotoPage.url="GotoPage@"+agentURL
	
	segs["ReadResult"]=ReadResult=async function(input){//:1JESG8MEG0
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $target="cleanHTML";
		$waitBefore && (await sleep($waitBefore));
		try{
			switch($target){
				case "cleanHTML":{
					result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:true,...$options});
					break;
				}
				case "html":{
					result=await context.webRpa.getInnerHTML(page,$node);
					break;
				}
				case "view":{
					result=await context.webRpa.readNodeView(page,$node,{removeHidden:false,...$options});
					break;
				}
				case "text":{
					result=await context.webRpa.readNodeText(page,$node,{removeHidden:false,...$options});
					break;
				}
				case "article":{
					result=await context.webRpa.readArticle(page,$node,{removeHidden:false,...$options});
					break;
				}
			}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JESG8MEG0ErrorCode*/
			/*}#1JESG8MEG0ErrorCode*/
		}
		return {seg:ChecjStart,result:(result),preSeg:"1JESG8MEG0",outlet:"1JESGDOKN0"};
	};
	ReadResult.jaxId="1JESG8MEG0"
	ReadResult.url="ReadResult@"+agentURL
	
	segs["ChecjStart"]=ChecjStart=async function(input){//:1JESG9Q3E0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-3.5-turbo";
		let $agent;
		let result;
		
		let opts={
			platform:$platform,
			mode:$model,
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=ChecjStart.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"You are a smart assistant."},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		if($agent){
			result=await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat});
		}else{
			result=await session.callSegLLM("ChecjStart@"+agentURL,opts,messages,true);
		}
		if(input==="Start"){
			return {seg:CheckNewRule,result:(input),preSeg:"1JESG9Q3E0",outlet:"1JESGDOKN1"};
		}
		return {seg:CheckError,result:(result),preSeg:"1JESG9Q3E0",outlet:"1JESGDOKN2"};
	};
	ChecjStart.jaxId="1JESG9Q3E0"
	ChecjStart.url="ChecjStart@"+agentURL
	
	segs["CheckError"]=CheckError=async function(input){//:1JESGBUQN0
		let result=input;
		if(input==="MaxRetry"){
			return {seg:FinFailed,result:(input),preSeg:"1JESGBUQN0",outlet:"1JESGDOKN3"};
		}
		return {seg:FindStart,result:(result),preSeg:"1JESGBUQN0",outlet:"1JESGDOKN4"};
	};
	CheckError.jaxId="1JESGBUQN0"
	CheckError.url="CheckError@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CaRpa_GenComposeStart",
		url:agentURL,
		autoStart:true,
		jaxId:"1JESG24QU0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,url,profile,waitAfter,compose}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JESG24QU0PreEntry*/
			/*}#1JESG24QU0PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JESG24QU0PostEntry*/
			/*}#1JESG24QU0PostEntry*/
			return result;
		},
		/*#{1JESG24QU0MoreAgentAttrs*/
		/*}#1JESG24QU0MoreAgentAttrs*/
	};
	/*#{1JESG24QU0PostAgent*/
	/*}#1JESG24QU0PostAgent*/
	return agent;
};
/*#{1JESG24QU0ExCodes*/
/*}#1JESG24QU0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CaRpa_GenComposeStart",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				url:{type:"auto",description:""},
				profile:{type:"auto",description:""},
				waitAfter:{type:"auto",description:""},
				compose:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true,
	kind: "rpa",
	capabilities: ["search","search.keyword","searchNum"],
	filters: [{"key":"domain","value":"*"}],
	metrics: {"quality":6.5,"costPerCall":0.1,"costPer1M":"","speed":6,"size":0}
}];
//#CodyExport<<<
/*#{1JESG24QU0PostDoc*/
/*}#1JESG24QU0PostDoc*/


export default CaRpa_GenComposeStart;
export{CaRpa_GenComposeStart,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JESG24QU0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JE5HADIA1",
//			"attrs": {
//				"CaRpa_GenComposeStart": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JE5HADIB0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JE5HADIB1",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JE5HADIB2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JE5HADIB3",
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
//			"jaxId": "1JE5HADIA2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JE5HADIA3",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5JKUUA0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5JKUUA1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"profile": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5JKUUA2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"waitAfter": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5JPCO90",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"compose": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JESGHUN20",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JE5HADIA4",
//			"attrs": {
//				"usedRule": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"wrongSelectors": {
//					"type": "auto",
//					"valText": "[]"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JE5HADIA5",
//			"attrs": {
//				"searchResult": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEHUQATU0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1JE5HADIA6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JE5JK3AB0",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "105",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE5JK3AB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5JK3AB2",
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
//							"jaxId": "1JE5JK3AB3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5JN9BL0"
//						},
//						"catchlet": {
//							"jaxId": "1JE5JK3AB4",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JE5JK3AB5",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JE5JK3AB6",
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
//					"jaxId": "1JE5JN9BL0",
//					"attrs": {
//						"id": "CheckRule",
//						"viewName": "",
//						"label": "",
//						"x": "345",
//						"y": "405",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5JN9BL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5JN9BL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5JN9BL3",
//							"attrs": {
//								"id": "NoRule",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEBIK6A40"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE5JN9BM0",
//									"attrs": {
//										"id": "URL",
//										"desc": "输出节点。",
//										"output": "#rule.url",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE5JN9BM1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE5JN9BM2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#rule && rule.url"
//									},
//									"linkedSeg": "1JEBI23L30"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEBIG15I0",
//									"attrs": {
//										"id": "Click",
//										"desc": "输出节点。",
//										"output": "#rule.click",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEBIR1UR0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEBIR1UR1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#rule && rule.click"
//									},
//									"linkedSeg": "1JE5JVJ4R1"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JE5JVJ4R1",
//					"attrs": {
//						"id": "FindClick",
//						"viewName": "",
//						"label": "",
//						"x": "585",
//						"y": "405",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5JVJ4R2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5JVJ4R3",
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
//						"errorSeg": "1JDUM5BGU0",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE5JVJ4S0",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEBIKM8M0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JE5JVJ4S1",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									},
//									"linkedSeg": "1JE5K5CHS0"
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1JE5K5CHS0",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "825",
//						"y": "535",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5K8RQ20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5K8RQ21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"target": "CleanHTML",
//						"node": "null",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE5K8RPV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5K5SH60"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JE5K5SH60",
//					"attrs": {
//						"id": "FindStart",
//						"viewName": "",
//						"label": "",
//						"x": "1085",
//						"y": "535",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5K8RQ22",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5K8RQ23",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1",
//						"system": "#$system",
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
//							"jaxId": "1JE5K8RPV2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5KMS000"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1JE925JKT0",
//									"attrs": {
//										"reply": "{ \"action\": { \"type\": \"selector\", \"by\": \"css: a.search-link\" }, \"reason\": \"页头存在“Search”链接 a.search-link，点击可展开隐藏的搜索表单（form.search 的 input[name='s'] 目前 opacity:0）。未见遮挡层。\", \"summary\": \"新闻/博客首页；返回用于启动搜索的 a.search-link 选择器；预期点击后显示搜索输入框；无遮挡。\" }",
//										"prompt": ""
//									}
//								}
//							]
//						},
//						"shareChatName": "",
//						"keepChat": "No",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"\"",
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE5K8RPV1",
//									"attrs": {
//										"id": "Click",
//										"desc": "输出节点。",
//										"output": "#result.action.by",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE5K8RQ24",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE5K8RQ25",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action && result.action.type===\"selector\""
//									},
//									"linkedSeg": "1JE5K7TEP0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE6NJK780",
//									"attrs": {
//										"id": "NoFind",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE6NMT9B2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE6NMT9B3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JE5KMS000"
//								}
//							]
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JE5K7TEP0",
//					"attrs": {
//						"id": "ClickStart",
//						"viewName": "",
//						"label": "",
//						"x": "1330",
//						"y": "390",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5K8RQ26",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5K8RQ27",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "#input",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"deltaX": "0",
//						"deltaY": "100",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE5K8RPV3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESG8MEG0"
//						},
//						"errorSeg": "1JE5K5SH60",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JE5KGERJ0",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "2560",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5KJIBV2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KJIBV3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5KJIBS1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5KJ1SM0"
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
//					"jaxId": "1JE5KGM2I0",
//					"attrs": {
//						"id": "FinFailed",
//						"viewName": "",
//						"label": "",
//						"x": "2335",
//						"y": "485",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JE5KJIBV4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KJIBV5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5KJIBS2",
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
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JE5KJ1SM0",
//					"attrs": {
//						"id": "WaitAfter",
//						"viewName": "",
//						"label": "",
//						"x": "2795",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE5KJIBV6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KJIBV7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "",
//						"waitBefore": "0",
//						"waitAfter": "#waitAfter",
//						"outlet": {
//							"jaxId": "1JE5KJIBS4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"catchlet": {
//							"jaxId": "1JE5KJIBS3",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JE5KMS000",
//					"attrs": {
//						"id": "FinNoStart",
//						"viewName": "",
//						"label": "",
//						"x": "1330",
//						"y": "565",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JE5KN81U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KN81U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5KN81Q0",
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
//					"jaxId": "1JE5KRV8T0",
//					"attrs": {
//						"id": "CheckNewRule",
//						"viewName": "",
//						"label": "",
//						"x": "2070",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5KU7D82",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KU7D83",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5KU7D51",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE5KGERJ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE5KU7D50",
//									"attrs": {
//										"id": "NewRule",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE5KU7D84",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE5KU7D85",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#usedRule"
//									},
//									"linkedSeg": "1JE5KTD4C0"
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
//					"jaxId": "1JE5KTD4C0",
//					"attrs": {
//						"id": "SaveRule",
//						"viewName": "",
//						"label": "",
//						"x": "2335",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5KU7D86",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KU7D87",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5KU7D52",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5KGERJ0"
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
//					"def": "WebRpaPageGoto",
//					"jaxId": "1JEBI23L30",
//					"attrs": {
//						"id": "GotoPage",
//						"viewName": "",
//						"label": "",
//						"x": "585",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEBI54I38",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEBI54I39",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"url": "#input",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JEBI54HP2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/wait_goto.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JEBIK6A40",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "585",
//						"y": "535",
//						"outlet": {
//							"jaxId": "1JEBIR1UR2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5K5CHS0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JEBIKM8M0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1005",
//						"y": "390",
//						"outlet": {
//							"jaxId": "1JEBIR1UR3",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5K7TEP0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1JESG8MEG0",
//					"attrs": {
//						"id": "ReadResult",
//						"viewName": "",
//						"label": "",
//						"x": "1585",
//						"y": "390",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JESGDOKR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JESGDOKR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"target": "CleanHTML",
//						"node": "null",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JESGDOKN0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESG9Q3E0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JESG9Q3E0",
//					"attrs": {
//						"id": "ChecjStart",
//						"viewName": "",
//						"label": "",
//						"x": "1840",
//						"y": "390",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JESGDOKR2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JESGDOKR3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "GPT-3.5",
//						"system": "You are a smart assistant.",
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
//							"jaxId": "1JESGDOKN2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESGBUQN0"
//						},
//						"stream": "true",
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
//						"formatDef": "\"\"",
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JESGDOKN1",
//									"attrs": {
//										"id": "Start",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JESGDOKR4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JESGDOKR5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JE5KRV8T0"
//								}
//							]
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JESGBUQN0",
//					"attrs": {
//						"id": "CheckError",
//						"viewName": "",
//						"label": "",
//						"x": "2070",
//						"y": "500",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JESGDOKR6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JESGDOKR7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JESGDOKN4",
//							"attrs": {
//								"id": "Retry",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JESGCUBN0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JESGDOKN3",
//									"attrs": {
//										"id": "MaxRetry",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JESGDOKR8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JESGDOKR9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JE5KGM2I0"
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
//					"jaxId": "1JESGCUBN0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2225",
//						"y": "650",
//						"outlet": {
//							"jaxId": "1JESGDOKR10",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESGDA8E0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JESGDA8E0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1115",
//						"y": "650",
//						"outlet": {
//							"jaxId": "1JESGDOKR11",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5K5SH60"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":false,\"isChatApi\":1,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\",\"kind\":\"rpa\",\"capabilities\":[\"search\",\"search.keyword\",\"searchNum\"],\"filters\":[{\"key\":\"domain\",\"value\":\"*\"}],\"metrics\":{\"quality\":6.5,\"costPerCall\":0.1,\"costPer1M\":\"\",\"speed\":6,\"size\":0},\"meta\":\"\"}"
//	}
//}