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
		"multiSelect":{
			"name":"multiSelect","type":"bool",
			"defaultValue":false,
			"desc":"",
		},
		"rulePath":{
			"name":"rulePath","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"cacheMode":{
			"name":"cacheMode","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"opts":{
			"name":"opts","type":"auto",
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
	let pageRef,query,multiSelect,rulePath,cacheMode,opts;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,ReadRule,CheckSkip,FinCacheStatus,LoopSelectors,QueryRule,BreakFind,CheckFind,FindSelector,CheckSelector,FinDone,SaveSelector,AskSaveStatus,SaveStatusCache,FinStatus,ShowPage,Back2App;
	let ruleStub=undefined;
	let ruleSelectors=undefined;
	let looseRule=false;
	let curRuleSelector="";
	let checkedSelector="";
	let ctxOpts=undefined;
	let ruleSigKey="";
	
	/*#{1JF9IR9640LocalVals*/
	/*}#1JF9IR9640LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			query=input.query;
			multiSelect=input.multiSelect;
			rulePath=input.rulePath;
			cacheMode=input.cacheMode;
			opts=input.opts;
		}else{
			pageRef=undefined;
			query=undefined;
			multiSelect=undefined;
			rulePath=undefined;
			cacheMode=undefined;
			opts=undefined;
		}
		/*#{1JF9IR9640ParseArgs*/
		ctxOpts=opts;
		cacheMode=cacheMode||"Array";
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
		let $webRpa=null;
		/*#{1JF9ISD5T0PreCodes*/
		if(false){
			let $channel="Process";
			let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
			let role="assistant";
			let content=`Util_QuerySelector: [StartRpa]: ${query}`;
			session.addChatText(role,content,opts);
		}
		/*}#1JF9ISD5T0PreCodes*/
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JF9ISD5T0"));
				if($alias){
					let $headless=false;
					let $devtools=false;
					let options={$headless:false,$devtools:false,autoDataDir:false};
					let $browser=null;
					/*#{1JF9ISD5T0PreBrowser*/
					/*}#1JF9ISD5T0PreBrowser*/
					context.rpaBrowser=$browser=await context.webRpa.openBrowser($alias,options);
					context.rpaHostPage=$browser.hostPage;
					Object.defineProperty(context, $pageVal, {enumerable:true,get(){return $webRpa.currentPage},set(v){$webRpa.setCurrentPage(v)}});
					/*#{1JF9ISD5T0PostBrowser*/
					/*}#1JF9ISD5T0PostBrowser*/
					if($url){
						let $page=null;
						let $opts={};
						/*#{1JF9ISD5T0PrePage*/
						/*}#1JF9ISD5T0PrePage*/
						context[$pageVal]=$page=await $browser.newPage();
						await $page.goto($url,{});
						/*#{1JF9ISD5T0PostPage*/
						/*}#1JF9ISD5T0PostPage*/
					}
				}
			}
			$waitAfter && (await sleep($waitAfter));
		}catch(error){
			throw error;
		}
		/*#{1JF9ISD5T0PostCodes*/
		/*}#1JF9ISD5T0PostCodes*/
		return {seg:ReadRule,result:(result),preSeg:"1JF9ISD5T0",outlet:"1JF9ISD5T3"};
	};
	StartRpa.jaxId="1JF9ISD5T0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["ReadRule"]=ReadRule=async function(input){//:1JF9IT8CG0
		let result=input;
		/*#{1JF9IT8CG0Start*/
		let rule;
		rule=await readRule(session,context.aaPage,rulePath,{loose:true,query:query,withSigKey:true});
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
		let value;
		ruleStub=input.value?input:null;
		value=input?.value;
		looseRule=input?.loose||false;
		if(typeof(value)==="string"){
			ruleSelectors=[value];
		}else if(Array.isArray(value)){
			ruleSelectors=value;
		}
		/*}#1JF9IU0260Start*/
		if(input==="skipped"){
			return {seg:FinCacheStatus,result:(input),preSeg:"1JF9IU0260",outlet:"1JF9IU0264"};
		}
		if(input==="failed"){
			return {seg:FinCacheStatus,result:(input),preSeg:"1JF9IU0260",outlet:"1JFH6H2H60"};
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
	
	segs["FinCacheStatus"]=FinCacheStatus=async function(input){//:1JF9IUAK60
		let result=input
		try{
			/*#{1JF9IUAK60Code*/
			result={status:input,result:input};
			/*}#1JF9IUAK60Code*/
		}catch(error){
			/*#{1JF9IUAK60ErrorCode*/
			/*}#1JF9IUAK60ErrorCode*/
		}
		return {result:result};
	};
	FinCacheStatus.jaxId="1JF9IUAK60"
	FinCacheStatus.url="FinCacheStatus@"+agentURL
	
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
		let sigKey;
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
			if(ruleSigKey){
				let sigKey;
				sigKey=await context.webRpa.computeSigKeyForSelector(page,$query);
				if(sigKey!==ruleSigKey){
					console.log(`Mismatch sigKey: "${ruleSigKey}" vs "${sigKey}"`);
				}
			}
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
		if(checkedSelector && !looseRule){
			/*#{1JF9J1PGL4Codes*/
			/*}#1JF9J1PGL4Codes*/
			return {seg:FinDone,result:(input),preSeg:"1JF9J1PGL0",outlet:"1JF9J1PGL4"};
		}
		if(checkedSelector){
			let output={selector:checkedSelector,sigKey:ruleStub.sigKey};
			/*#{1JFPLFCS80Codes*/
			/*}#1JFPLFCS80Codes*/
			return {seg:SaveSelector,result:(output),preSeg:"1JF9J1PGL0",outlet:"1JFPLFCS80"};
		}
		return {seg:FindSelector,result:(result),preSeg:"1JF9J1PGL0",outlet:"1JF9J1PGL3"};
	};
	CheckFind.jaxId="1JF9J1PGL0"
	CheckFind.url="CheckFind@"+agentURL
	
	segs["FindSelector"]=FindSelector=async function(input){//:1JF9J2J820
		let result;
		let arg={"pageRef":pageRef,"url":"","profile":"","selectDesc":query,"multiSelect":multiSelect,"useManual":ctxOpts.useManual,"allowManual":ctxOpts.allowManual};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./Util_FindSelector.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CheckSelector,result:(result),preSeg:"1JF9J2J820",outlet:"1JF9J2J830"};
	};
	FindSelector.jaxId="1JF9J2J820"
	FindSelector.url="FindSelector@"+agentURL
	
	segs["CheckSelector"]=CheckSelector=async function(input){//:1JF9J31E70
		let result=input;
		/*#{1JF9J31E70Start*/
		await sleep(500);
		/*}#1JF9J31E70Start*/
		if(input?.selector){
			return {seg:SaveSelector,result:(input),preSeg:"1JF9J31E70",outlet:"1JF9J31E80"};
		}
		if(input.status && input.status.toLowerCase()==="skipped"){
			return {seg:ShowPage,result:(input),preSeg:"1JF9J31E70",outlet:"1JFEEA7I80"};
		}
		/*#{1JF9J31E70Post*/
		/*}#1JF9J31E70Post*/
		return {seg:ShowPage,result:(result),preSeg:"1JF9J31E70",outlet:"1JF9J31E73"};
	};
	CheckSelector.jaxId="1JF9J31E70"
	CheckSelector.url="CheckSelector@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JF9J40NV0
		let result=input
		try{
			/*#{1JF9J40NV0Code*/
			result={status:"done",result:"done",value:checkedSelector,selector:checkedSelector};
			/*}#1JF9J40NV0Code*/
		}catch(error){
			/*#{1JF9J40NV0ErrorCode*/
			/*}#1JF9J40NV0ErrorCode*/
		}
		return {result:result};
	};
	FinDone.jaxId="1JF9J40NV0"
	FinDone.url="FinDone@"+agentURL
	
	segs["SaveSelector"]=SaveSelector=async function(input){//:1JF9J5R210
		let result=input
		try{
			/*#{1JF9J5R210Code*/
			let rule,idx,sigKey;
			checkedSelector=input.selector;
			sigKey=input.sigKey||null;
			rule=await readRule(session,context.aaPage,rulePath);
			if(!rule){
				rule=[];
			}
			if(Array.isArray(rule)){
				idx=rule.indexOf(checkedSelector);
				if(idx>=0){
					rule.splice(idx,1);
				}
				rule.unshift(checkedSelector);
				if(rule.length>10){
					rule=rule.slice(0,10);
				}
			}else{
				rule=checkedSelector;
			}
			await saveRule(session,context.aaPage,rulePath,rule,query,sigKey);
			/*}#1JF9J5R210Code*/
		}catch(error){
			/*#{1JF9J5R210ErrorCode*/
			/*}#1JF9J5R210ErrorCode*/
		}
		return {seg:FinDone,result:(result),preSeg:"1JF9J5R210",outlet:"1JF9J72R00"};
	};
	SaveSelector.jaxId="1JF9J5R210"
	SaveSelector.url="SaveSelector@"+agentURL
	
	segs["AskSaveStatus"]=AskSaveStatus=async function(input){//:1JFH5OO1N0
		let result=input;
		/*#{1JFH5OO1N0Start*/
		let webRpa,page,res;
		if(ctxOpts.useManual){
			webRpa=context.webRpa;
			page=context.aaPage;
			res=await webRpa.inPagePrompt(
				page,`是否记住（缓存）这个结果，以后在当前页面配置下，都返回"${input.status}"状态？`,
				{
					menu:[
						{text:"💾: 记住步骤结果。",code:true},
						{text:"❌: 不缓存步骤结果",code:false},
					]
				}
			);
		}else{
			res=false;
		}
		/*}#1JFH5OO1N0Start*/
		if(!!res){
			return {seg:SaveStatusCache,result:(input),preSeg:"1JFH5OO1N0",outlet:"1JFH5OO1N4"};
		}
		/*#{1JFH5OO1N0Post*/
		/*}#1JFH5OO1N0Post*/
		return {seg:Back2App,result:(result),preSeg:"1JFH5OO1N0",outlet:"1JFH5OO1N3"};
	};
	AskSaveStatus.jaxId="1JFH5OO1N0"
	AskSaveStatus.url="AskSaveStatus@"+agentURL
	
	segs["SaveStatusCache"]=SaveStatusCache=async function(input){//:1JFEEB4OQ0
		let result=input
		try{
			/*#{1JFEEB4OQ0Code*/
			await saveRule(session,context.aaPage,rulePath,input?.status||"skipped",query);
			/*}#1JFEEB4OQ0Code*/
		}catch(error){
			/*#{1JFEEB4OQ0ErrorCode*/
			/*}#1JFEEB4OQ0ErrorCode*/
		}
		return {seg:Back2App,result:(result),preSeg:"1JFEEB4OQ0",outlet:"1JFEECN9D0"};
	};
	SaveStatusCache.jaxId="1JFEEB4OQ0"
	SaveStatusCache.url="SaveStatusCache@"+agentURL
	
	segs["FinStatus"]=FinStatus=async function(input){//:1JF9J3L100
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
	FinStatus.jaxId="1JF9J3L100"
	FinStatus.url="FinStatus@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1JFHIL3VV0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let $options={"focusBrowser":true,"switchBack":0};
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		try{
			await page.bringToFront($options);
			waitAfter && (await sleep(waitAfter))
			if($options.focusBrowser && $options.switchBack){
				let $browser=context.rpaBrowser;
				if($browser){
					await $browser.backToApp();
				}
			}
		}catch(error){
			/*#{1JFHIL3VV0ErrorCode*/
			/*}#1JFHIL3VV0ErrorCode*/
		}
		return {seg:AskSaveStatus,result:(result),preSeg:"1JFHIL3VV0",outlet:"1JFHIMJMH0"};
	};
	ShowPage.jaxId="1JFHIL3VV0"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["Back2App"]=Back2App=async function(input){//:1JFHIN2P50
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JFHIN2P50ErrorCode*/
			/*}#1JFHIN2P50ErrorCode*/
		}
		return {seg:FinStatus,result:(result),preSeg:"1JFHIN2P50",outlet:"1JFHINDB80"};
	};
	Back2App.jaxId="1JFHIN2P50"
	Back2App.url="Back2App@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"Util_QuerySelector",
		url:agentURL,
		autoStart:true,
		jaxId:"1JF9IR9640",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,query,multiSelect,rulePath,cacheMode,opts}*/){
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
				multiSelect:{type:"bool",description:""},
				rulePath:{type:"auto",description:""},
				cacheMode:{type:"auto",description:""},
				opts:{type:"auto",description:""}
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
//				"multiSelect": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFEEURN60",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "false",
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
//				},
//				"cacheMode": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JG2F1VP50",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"opts": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFEE22O90",
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
//				"ruleStub": {
//					"type": "auto",
//					"valText": ""
//				},
//				"ruleSelectors": {
//					"type": "auto",
//					"valText": ""
//				},
//				"looseRule": {
//					"type": "bool",
//					"valText": "false"
//				},
//				"curRuleSelector": {
//					"type": "string",
//					"valText": ""
//				},
//				"checkedSelector": {
//					"type": "string",
//					"valText": ""
//				},
//				"ctxOpts": {
//					"type": "auto",
//					"valText": ""
//				},
//				"ruleSigKey": {
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
//						"codes": "true",
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
//						"autoCurrentPage": "true",
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
//						"segMark": "lab.svg",
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
//										"condition": "#input===\"skipped\""
//									},
//									"linkedSeg": "1JF9IUAK60"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFH6H2H60",
//									"attrs": {
//										"id": "Fail",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFH6H2HD0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFH6H2HD1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input===\"failed\""
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
//						"id": "FinCacheStatus",
//						"viewName": "",
//						"label": "",
//						"x": "845",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
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
//										"codes": "true",
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
//										"condition": "#checkedSelector && !looseRule"
//									},
//									"linkedSeg": "1JF9J40NV0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFPLFCS80",
//									"attrs": {
//										"id": "Loose",
//										"desc": "输出节点。",
//										"output": "#{selector:checkedSelector,sigKey:ruleStub.sigKey}",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JFPLGSNP0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFPLGSNP1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#checkedSelector"
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
//					"def": "aiBot",
//					"jaxId": "1JF9J2J820",
//					"attrs": {
//						"id": "FindSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1405",
//						"y": "550",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
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
//						"source": "ai/Util_FindSelector.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"url\":\"\",\"profile\":\"\",\"selectDesc\":\"#query\",\"multiSelect\":\"#multiSelect\",\"useManual\":\"#ctxOpts.useManual\",\"allowManual\":\"#ctxOpts.allowManual\"}",
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
//						"x": "1670",
//						"y": "550",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
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
//							"linkedSeg": "1JFHIL3VV0"
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
//										"condition": "#input?.selector"
//									},
//									"linkedSeg": "1JF9J5R210"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFEEA7I80",
//									"attrs": {
//										"id": "Skipped",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFEECN9L0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFEECN9L1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.status && input.status.toLowerCase()===\"skipped\""
//									},
//									"linkedSeg": "1JFHIL3VV0"
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
//					"jaxId": "1JF9J40NV0",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "2195",
//						"y": "445",
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
//						"y": "550",
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
//						"id": "SaveSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1940",
//						"y": "475",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
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
//						"y": "550",
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
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JFH5OO1N0",
//					"attrs": {
//						"id": "AskSaveStatus",
//						"viewName": "",
//						"label": "",
//						"x": "2195",
//						"y": "590",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFH5OO1N1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFH5OO1N2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFH5OO1N3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFHIN2P50"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFH5OO1N4",
//									"attrs": {
//										"id": "Cache",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFH5OO1N5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFH5OO1N6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!res"
//									},
//									"linkedSeg": "1JFEEB4OQ0"
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
//					"jaxId": "1JFEEB4OQ0",
//					"attrs": {
//						"id": "SaveStatusCache",
//						"viewName": "",
//						"label": "",
//						"x": "2460",
//						"y": "535",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFEECN9L2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFEECN9L3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFEECN9D0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFHIN2P50"
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
//					"jaxId": "1JF9J3L100",
//					"attrs": {
//						"id": "FinStatus",
//						"viewName": "",
//						"label": "",
//						"x": "2975",
//						"y": "605",
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
//					"def": "WebRpaActivePage",
//					"jaxId": "1JFHIL3VV0",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "1935",
//						"y": "590",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFHIPPM70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFHIPPM71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true,\"switchBack\":0}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JFHIMJMH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFH5OO1N0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JFHIN2P50",
//					"attrs": {
//						"id": "Back2App",
//						"viewName": "",
//						"label": "",
//						"x": "2740",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFHIPPM72",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFHIPPM73",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JFHINDB80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF9J3L100"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}