//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JGD5B9DG0MoreImports*/
import CacheAPI from "./utils_cache.js";
import {buildRpaStepDeciderPrompt,execRunJsAction} from "./utils_flow.js";
/*}#1JGD5B9DG0MoreImports*/
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
		"cacheKey":{
			"name":"cacheKey","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"cacheQuery":{
			"name":"cacheQuery","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"cacheKind":{
			"name":"cacheKind","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"cachePolicy":{
			"name":"cachePolicy","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"flowArgs":{
			"name":"flowArgs","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"flowVars":{
			"name":"flowVars","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"flowOpts":{
			"name":"flowOpts","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"flowResult":{
			"name":"flowResult","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"flowHistory":{
			"name":"flowHistory","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"selectorMode":{
			"name":"selectorMode","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"codeScope":{
			"name":"codeScope","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JGD5B9DG0ArgsView*/
	/*}#1JGD5B9DG0ArgsView*/
};

/*#{1JGD5B9DG0StartDoc*/
/*}#1JGD5B9DG0StartDoc*/
//----------------------------------------------------------------------------
let Util_ResolveQuery=async function(session){
	let pageRef,cacheKey,cacheQuery,cacheKind,cachePolicy,flowArgs,flowVars,flowOpts,flowResult,flowHistory,selectorMode,codeScope;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let CheckArray,LoopQuery,ResolveQuery,CheckResolve,FinArray,StartRpa,ReadCache,CacheKind,FinNotSelector,LoopSelectors,QueryCache,BreakFind,CheckFind,OnInputKind,FindSelector,CheckSelector,SaveSelector,AskIfCache,ShowPage,BackToApp,ReadPage,OnCacheKind,AiGetStatus,JumpAsk,FinFindSelector,WriteCode,CheckCode,SaveCode;
	let matchedSelector=undefined;
	let isLooseSelector=false;
	let usedSelector=undefined;
	let orgQuery=undefined;
	let pageHtml=undefined;
	let wrongCodes=[];
	let codeRetryNum=0;
	let queryLoopIdx=0;
	let queryLoopErrorIdx=0;
	let queryLoopError=0;
	let queryLoopResult=undefined;
	let usedCache=undefined;
	let usedSigKey=undefined;
	
	/*#{1JGD5B9DG0LocalVals*/
	/*}#1JGD5B9DG0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			cacheKey=input.cacheKey;
			cacheQuery=input.cacheQuery;
			cacheKind=input.cacheKind;
			cachePolicy=input.cachePolicy;
			flowArgs=input.flowArgs;
			flowVars=input.flowVars;
			flowOpts=input.flowOpts;
			flowResult=input.flowResult;
			flowHistory=input.flowHistory;
			selectorMode=input.selectorMode;
			codeScope=input.codeScope;
		}else{
			pageRef=undefined;
			cacheKey=undefined;
			cacheQuery=undefined;
			cacheKind=undefined;
			cachePolicy=undefined;
			flowArgs=undefined;
			flowVars=undefined;
			flowOpts=undefined;
			flowResult=undefined;
			flowHistory=undefined;
			selectorMode=undefined;
			codeScope=undefined;
		}
		/*#{1JGD5B9DG0ParseArgs*/
		orgQuery=cacheQuery;
		if(typeof(cacheQuery)==="object"){
			cacheKind=cacheQuery.kind||"selector";
			cachePolicy=cacheQuery.policy||"pool";
			selectorMode=cacheQuery.mode||"instance";
			cacheQuery=cacheQuery.text;
		}else{
			cacheKind=cacheKind||"selector";
		}
		codeScope=codeScope||"page";
		/*}#1JGD5B9DG0ParseArgs*/
	}
	
	/*#{1JGD5B9DG0PreContext*/
	/*}#1JGD5B9DG0PreContext*/
	context={};
	/*#{1JGD5B9DG0PostContext*/
	/*}#1JGD5B9DG0PostContext*/
	let $agent,agent,segs={};
	segs["CheckArray"]=CheckArray=async function(input){//:1JGBVCJVP0
		let result=input;
		if(Array.isArray(cacheQuery)){
			let output=cacheQuery;
			return {seg:LoopQuery,result:(output),preSeg:"1JGBVCJVP0",outlet:"1JGBVF9K20"};
		}
		return {seg:StartRpa,result:(result),preSeg:"1JGBVCJVP0",outlet:"1JGBVF9K21"};
	};
	CheckArray.jaxId="1JGBVCJVP0"
	CheckArray.url="CheckArray@"+agentURL
	
	segs["LoopQuery"]=LoopQuery=async function(input){//:1JGBVF02P0
		let result=input;
		let list=input;
		let i,n,item,loopR;
		/*#{1JGBVF02P0PreLoop*/
		/*}#1JGBVF02P0PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1JGBVF02P0InLoopPre*/
			queryLoopIdx=i;
			/*}#1JGBVF02P0InLoopPre*/
			loopR=await session.runAISeg(agent,ResolveQuery,item,"1JGBVF02P0","1JGBVF9KC6")
			if(loopR==="break"){
				break;
			}
			/*#{1JGBVF02P0InLoopPost*/
			/*}#1JGBVF02P0InLoopPost*/
		}
		/*#{1JGBVF02P0PostCodes*/
		/*}#1JGBVF02P0PostCodes*/
		return {seg:FinArray,result:(result),preSeg:"1JGBVF02P0",outlet:"1JGBVF9K22"};
	};
	LoopQuery.jaxId="1JGBVF02P0"
	LoopQuery.url="LoopQuery@"+agentURL
	
	segs["ResolveQuery"]=ResolveQuery=async function(input){//:1JGBVHQL70
		let result;
		let arg={"pageRef":pageRef,"cacheKey":cacheKey+"#"+queryLoopIdx,"cacheQuery":input.text||input,"cacheKind":cacheKind,"cachePolicy":cachePolicy,"flowArgs":flowArgs,"flowVars":flowVars,"flowOpts":flowOpts,"flowHistory":flowHistory,"selectorMode":selectorMode};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./Util_ResolveQuery.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JGBVHQL70Input*/
		/*}#1JGBVHQL70Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JGBVHQL70Output*/
		/*}#1JGBVHQL70Output*/
		return {seg:CheckResolve,result:(result),preSeg:"1JGBVHQL70",outlet:"1JGBVL7C20"};
	};
	ResolveQuery.jaxId="1JGBVHQL70"
	ResolveQuery.url="ResolveQuery@"+agentURL
	
	segs["CheckResolve"]=CheckResolve=async function(input){//:1JGBVJ4GM0
		let result=input;
		/*#{1JGBVJ4GM0Start*/
		/*}#1JGBVJ4GM0Start*/
		if(input.status==="done" && input.value){
			return {result:input};
		}
		/*#{1JGBVJ4GM0Post*/
		queryLoopErrorIdx=queryLoopIdx;
		queryLoopError=input.reason;
		result="break";
		/*}#1JGBVJ4GM0Post*/
		return {result:result};
	};
	CheckResolve.jaxId="1JGBVJ4GM0"
	CheckResolve.url="CheckResolve@"+agentURL
	
	segs["FinArray"]=FinArray=async function(input){//:1JGBVJQCI0
		let result=input
		try{
			/*#{1JGBVJQCI0Code*/
			if(queryLoopError){
			}
			/*}#1JGBVJQCI0Code*/
		}catch(error){
			/*#{1JGBVJQCI0ErrorCode*/
			/*}#1JGBVJQCI0ErrorCode*/
		}
		return {result:result};
	};
	FinArray.jaxId="1JGBVJQCI0"
	FinArray.url="FinArray@"+agentURL
	
	segs["StartRpa"]=StartRpa=async function(input){//:1JG7RTVB90
		let result=true;
		let aiQuery=true;
		let $alias="";
		let $url="";
		let $ref=pageRef;
		let $waitBefore=0;
		let $waitAfter=0;
		let $webRpa=null;
		/*#{1JG7RTVB90PreCodes*/
		/*}#1JG7RTVB90PreCodes*/
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JG7RTVB90"));
				if($alias){
					let $headless=false;
					let $devtools=false;
					let options={headless:$headless,devtools:$devtools,autoDataDir:false};
					let $browser=null;
					/*#{1JG7RTVB90PreBrowser*/
					/*}#1JG7RTVB90PreBrowser*/
					context.rpaBrowser=$browser=await context.webRpa.openBrowser($alias,options);
					context.rpaHostPage=$browser.hostPage;
					Object.defineProperty(context, $pageVal, {enumerable:true,get(){return $webRpa.currentPage},set(v){$webRpa.setCurrentPage(v)}});
					/*#{1JG7RTVB90PostBrowser*/
					/*}#1JG7RTVB90PostBrowser*/
					if($url){
						let $page=null;
						let $opts={};
						/*#{1JG7RTVB90PrePage*/
						/*}#1JG7RTVB90PrePage*/
						context[$pageVal]=$page=await $browser.newPage();
						await $page.goto($url,{});
						/*#{1JG7RTVB90PostPage*/
						/*}#1JG7RTVB90PostPage*/
					}
				}
			}
			$waitAfter && (await sleep($waitAfter));
		}catch(error){
			throw error;
		}
		/*#{1JG7RTVB90PostCodes*/
		/*}#1JG7RTVB90PostCodes*/
		return {seg:ReadCache,result:(result),preSeg:"1JG7RTVB90",outlet:"1JG7RTVB93"};
	};
	StartRpa.jaxId="1JG7RTVB90"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["ReadCache"]=ReadCache=async function(input){//:1JG7RUB8O0
		let result=input;
		/*#{1JG7RUB8O0Start*/
		let ctx,cache;
		ctx=await CacheAPI.openRuleCache(session, context.aaPage);
		cache=await CacheAPI.resolveRule(ctx,cacheKey);
		if(!cache && (!cacheKind || cacheKind==="selector")){
			let selector;
			selector=await CacheAPI.findLooseSelector(ctx,{key:cacheKey,queryText:cacheQuery});
			if(selector){
				if(!Array.isArray(selector)){
					selector=[selector];
				}
				cache={"kind":"selector",selectors:selector};
				isLooseSelector=true;
			}
		}
		if(cache && cacheKind){
			if(!cache.kind || cache.kind !== cacheKind){
				cache=null;
			}
		}
		/*}#1JG7RUB8O0Start*/
		if(cache){
			let output=cache;
			/*#{1JG7S2BQT0Codes*/
			usedCache=cache;
			/*}#1JG7S2BQT0Codes*/
			return {seg:CacheKind,result:(output),preSeg:"1JG7RUB8O0",outlet:"1JG7S2BQT0"};
		}
		/*#{1JG7RUB8O0Post*/
		/*}#1JG7RUB8O0Post*/
		return {seg:ShowPage,result:(result),preSeg:"1JG7RUB8O0",outlet:"1JG7RUHT20"};
	};
	ReadCache.jaxId="1JG7RUB8O0"
	ReadCache.url="ReadCache@"+agentURL
	
	segs["CacheKind"]=CacheKind=async function(input){//:1JG7RVDVE0
		let result=input;
		/*#{1JG7RVDVE0Start*/
		/*}#1JG7RVDVE0Start*/
		if(input.kind==="selector"){
			let output=input.selectors;
			/*#{1JG7S2BQT1Codes*/
			if(!Array.isArray(output)){
				output=[output];//ensure array:
			}
			/*}#1JG7S2BQT1Codes*/
			return {seg:LoopSelectors,result:(output),preSeg:"1JG7RVDVE0",outlet:"1JG7S2BQT1"};
		}
		if(input.kind==="code"){
			let output=result;
			/*#{1JG7S02II0Codes*/
			output={status:"done",value:{kind:"code",code:input.code,fromCache:true}};
			/*}#1JG7S02II0Codes*/
			return {seg:FinNotSelector,result:(output),preSeg:"1JG7RVDVE0",outlet:"1JG7S02II0"};
		}
		if(input.kind==="status"){
			let output=input;
			/*#{1JG7RVRUF0Codes*/
			output={status:"done",value:{kind:"status",status:input.status,fromCache:true}};
			/*}#1JG7RVRUF0Codes*/
			return {seg:FinNotSelector,result:(output),preSeg:"1JG7RVDVE0",outlet:"1JG7RVRUF0"};
		}
		/*#{1JG7RVDVE0Post*/
		result={status:"done",value:{kind:"value",value:input.value||null}};
		/*}#1JG7RVDVE0Post*/
		return {seg:FinNotSelector,result:(result),preSeg:"1JG7RVDVE0",outlet:"1JG7S2BQT2"};
	};
	CacheKind.jaxId="1JG7RVDVE0"
	CacheKind.url="CacheKind@"+agentURL
	
	segs["FinNotSelector"]=FinNotSelector=async function(input){//:1JG7S15S90
		let result=input
		try{
			/*#{1JG7S15S90Code*/
			/*}#1JG7S15S90Code*/
		}catch(error){
			/*#{1JG7S15S90ErrorCode*/
			/*}#1JG7S15S90ErrorCode*/
		}
		return {result:result};
	};
	FinNotSelector.jaxId="1JG7S15S90"
	FinNotSelector.url="FinNotSelector@"+agentURL
	
	segs["LoopSelectors"]=LoopSelectors=async function(input){//:1JG7S2TIS0
		let result=input;
		let list=input;
		let i,n,item,loopR;
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			loopR=await session.runAISeg(agent,QueryCache,item,"1JG7S2TIS0","1JG7S4QR10")
			if(loopR==="break"){
				break;
			}
		}
		return {seg:CheckFind,result:(result),preSeg:"1JG7S2TIS0",outlet:"1JG7S4QR11"};
	};
	LoopSelectors.jaxId="1JG7S2TIS0"
	LoopSelectors.url="LoopSelectors@"+agentURL
	
	segs["QueryCache"]=QueryCache=async function(input){//:1JG7S3V9S1
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
		/*#{1JG7S3V9S1PreCodes*/
		result=null;
		/*}#1JG7S3V9S1PreCodes*/
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			/*#{1JG7S3V9S1CheckItem*/
			result=$query;
			/*}#1JG7S3V9S1CheckItem*/
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JG7S3V9S1ErrorCode*/
			result=null;
			/*}#1JG7S3V9S1ErrorCode*/
		}
		/*#{1JG7S3V9S1PostCodes*/
		/*}#1JG7S3V9S1PostCodes*/
		return {seg:BreakFind,result:(result),preSeg:"1JG7S3V9S1",outlet:"1JG7S3V9S4"};
	};
	QueryCache.jaxId="1JG7S3V9S1"
	QueryCache.url="QueryCache@"+agentURL
	
	segs["BreakFind"]=BreakFind=async function(input){//:1JG7S53KE0
		let result=input
		try{
			/*#{1JG7S53KE0Code*/
			if(input){
				matchedSelector=input;
				result="break";
			}else{
				result=null;
			}
			/*}#1JG7S53KE0Code*/
		}catch(error){
			/*#{1JG7S53KE0ErrorCode*/
			/*}#1JG7S53KE0ErrorCode*/
		}
		return {result:result};
	};
	BreakFind.jaxId="1JG7S53KE0"
	BreakFind.url="BreakFind@"+agentURL
	
	segs["CheckFind"]=CheckFind=async function(input){//:1JG7S72D60
		let result=input;
		if(!!matchedSelector){
			let output=matchedSelector;
			return {seg:FinFindSelector,result:(output),preSeg:"1JG7S72D60",outlet:"1JG7SE6IU1"};
		}
		return {seg:ShowPage,result:(result),preSeg:"1JG7S72D60",outlet:"1JG7SE6IU2"};
	};
	CheckFind.jaxId="1JG7S72D60"
	CheckFind.url="CheckFind@"+agentURL
	
	segs["OnInputKind"]=OnInputKind=async function(input){//:1JG7S98TB0
		let result=input;
		if(cacheKind==="selector" || !cacheKind){
			return {seg:FindSelector,result:(input),preSeg:"1JG7S98TB0",outlet:"1JG7SE6IU3"};
		}
		return {seg:ReadPage,result:(result),preSeg:"1JG7S98TB0",outlet:"1JG7SE6IV0"};
	};
	OnInputKind.jaxId="1JG7S98TB0"
	OnInputKind.url="OnInputKind@"+agentURL
	
	segs["FindSelector"]=FindSelector=async function(input){//:1JG7SC7HS0
		let result;
		let arg={"pageRef":pageRef,"url":"","profile":"","selectDesc":cacheQuery,"multiSelect":selectorMode==="class","useManual":flowOpts.useManual,"allowManual":flowOpts.allowManual,"manualTraining":"","ruleKey":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./Util_FindSelector.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CheckSelector,result:(result),preSeg:"1JG7SC7HS0",outlet:"1JG7SC7HT0"};
	};
	FindSelector.jaxId="1JG7SC7HS0"
	FindSelector.url="FindSelector@"+agentURL
	
	segs["CheckSelector"]=CheckSelector=async function(input){//:1JG7SCU7L0
		let result=input;
		/*#{1JG7SCU7L0Start*/
		/*}#1JG7SCU7L0Start*/
		if(input.status==="done" && input.value){
			/*#{1JG7SI7GI0Codes*/
			usedSelector=input.value;
			usedSigKey=input.sigKey;
			/*}#1JG7SI7GI0Codes*/
			return {seg:SaveSelector,result:(input),preSeg:"1JG7SCU7L0",outlet:"1JG7SI7GI0"};
		}
		if(input.status!=="done" || input.kind==="status"){
			let output=input;
			return {seg:AskIfCache,result:(output),preSeg:"1JG7SCU7L0",outlet:"1JG7SEKCD0"};
		}
		result=input;
		/*#{1JG7SCU7L0Post*/
		/*}#1JG7SCU7L0Post*/
		return {seg:AskIfCache,result:(result),preSeg:"1JG7SCU7L0",outlet:"1JG7SE6IV1"};
	};
	CheckSelector.jaxId="1JG7SCU7L0"
	CheckSelector.url="CheckSelector@"+agentURL
	
	segs["SaveSelector"]=SaveSelector=async function(input){//:1JG7SFVRC0
		let result=input
		try{
			/*#{1JG7SFVRC0Code*/
			let ctx,selector;
			ctx=await CacheAPI.openRuleCache(session, context.aaPage);
			await CacheAPI.saveSelector(ctx,cacheKey,{
				query:orgQuery,
				selectors:usedSelector,
				sigKey:usedSigKey,
				policy:cachePolicy,
				maxLen:10
			});
			await CacheAPI.flushRuleCache(ctx);
			result={status:"done",value:{kind:"selector",selector:usedSelector,sigKey:usedSigKey,fromCache:false}};
			/*}#1JG7SFVRC0Code*/
		}catch(error){
			/*#{1JG7SFVRC0ErrorCode*/
			/*}#1JG7SFVRC0ErrorCode*/
		}
		return {seg:BackToApp,result:(result),preSeg:"1JG7SFVRC0",outlet:"1JG7SI7GJ0"};
	};
	SaveSelector.jaxId="1JG7SFVRC0"
	SaveSelector.url="SaveSelector@"+agentURL
	
	segs["AskIfCache"]=AskIfCache=async function(input){//:1JG7SGUC20
		let result=input;
		/*#{1JG7SGUC20Start*/
		let webRpa,page,res;
		const status = input?.value?.status ?? input?.status;
		const reason = input?.value?.reason ?? input?.reason ?? "";		
		if(flowOpts.useManual||flowOpts.allowManual){
			webRpa=context.webRpa;
			page=context.aaPage;
			res=await webRpa.inPagePrompt(
				page,`是否记住（缓存）这个状态结果，以后在当前页面配置下，都返回"${status}"状态？`,
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
		/*}#1JG7SGUC20Start*/
		if(!!res){
			let output=result;
			/*#{1JG7SM4FM0Codes*/
			let ctx;
			ctx=await CacheAPI.openRuleCache(session, context.aaPage);
			CacheAPI.setStatus(ctx,cacheKey,status,{query:cacheQuery,reason});
			await CacheAPI.flushRuleCache(ctx);
			output={status:"done",value:{kind:"status",status:status,fromCache:false}};
			/*}#1JG7SM4FM0Codes*/
			return {seg:BackToApp,result:(output),preSeg:"1JG7SGUC20",outlet:"1JG7SM4FM0"};
		}
		/*#{1JG7SGUC20Post*/
		result={status:"done",value:{kind:"status",status:status,fromCache:false}};
		/*}#1JG7SGUC20Post*/
		return {seg:BackToApp,result:(result),preSeg:"1JG7SGUC20",outlet:"1JG7SI7GJ1"};
	};
	AskIfCache.jaxId="1JG7SGUC20"
	AskIfCache.url="AskIfCache@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1JG7SKG3I0
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
			/*#{1JG7SKG3I0ErrorCode*/
			/*}#1JG7SKG3I0ErrorCode*/
		}
		return {seg:OnInputKind,result:(result),preSeg:"1JG7SKG3I0",outlet:"1JG7SM4FM1"};
	};
	ShowPage.jaxId="1JG7SKG3I0"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["BackToApp"]=BackToApp=async function(input){//:1JG7SN1A60
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		/*#{1JG7SN1A60PreCodes*/
		/*}#1JG7SN1A60PreCodes*/
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JG7SN1A60ErrorCode*/
			/*}#1JG7SN1A60ErrorCode*/
		}
		/*#{1JG7SN1A60PostCodes*/
		result=input;
		/*}#1JG7SN1A60PostCodes*/
		return {result:result};
	};
	BackToApp.jaxId="1JG7SN1A60"
	BackToApp.url="BackToApp@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1JG7SQJE10
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
			/*#{1JG7SQJE10ErrorCode*/
			/*}#1JG7SQJE10ErrorCode*/
		}
		return {seg:OnCacheKind,result:(result),preSeg:"1JG7SQJE10",outlet:"1JG7T20Q40"};
	};
	ReadPage.jaxId="1JG7SQJE10"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["OnCacheKind"]=OnCacheKind=async function(input){//:1JG7SSFEG0
		let result=input;
		/*#{1JG7SSFEG0Start*/
		pageHtml=input;
		/*}#1JG7SSFEG0Start*/
		if(cacheKind==="code"){
			return {seg:WriteCode,result:(input),preSeg:"1JG7SSFEG0",outlet:"1JG7T20Q41"};
		}
		/*#{1JG7SSFEG0Post*/
		/*}#1JG7SSFEG0Post*/
		return {seg:AiGetStatus,result:(result),preSeg:"1JG7SSFEG0",outlet:"1JG7T20Q42"};
	};
	OnCacheKind.jaxId="1JG7SSFEG0"
	OnCacheKind.url="OnCacheKind@"+agentURL
	
	segs["AiGetStatus"]=AiGetStatus=async function(input){//:1JG7SV6360
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5";
		let $agent;
		let result=null;
		/*#{1JG7SV6360Input*/
		/*}#1JG7SV6360Input*/
		
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
		let chatMem=AiGetStatus.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你是一个“页面状态判定器”（page-state validator）。你的任务是：根据输入提供的网页内容（HTML + 可能的截图图片）与用户的状态描述（query），判断当前页面是否符合该状态，并按要求输出严格 JSON。\n\n========================\n1) 目标\n========================\n给定：\n- 清洗后的 HTML 字符串（可能很长）\n- 用户想确认的“状态描述” query（自然语言）\n- 以及（可选）网页截图图片附件\n判断页面是否满足该状态，并返回三态之一：done / skipped / failed。\n\n========================\n2) 输入格式\n========================\n你会收到一个输入，通常是 JSON（也可能是一段可解析为 JSON 的文本），字段可能包含：\n- \"html\": string   （清洗后的 HTML）\n- \"query\": string  （用户想确认的状态描述）\n- （可选）图片附件：网页截图（可能 1 张或多张）\n\n重要：\n- 如果输入不是合法 JSON，但明显包含 \"html\" 与 \"query\"，你必须尽力提取它们。\n- 若无法可靠地提取 \"html\" 或 \"query\" 任意一个，则返回 status=\"failed\"。\n\n========================\n3) 输出格式（严格）\n========================\n你必须且只能输出 **一个 JSON 对象**（不要 markdown、不要代码围栏、不要额外解释文本），且仅允许以下字段：\n- \"status\": \"done\" | \"skipped\" | \"failed\"\n- \"reason\": string\n\n不允许出现任何其他 key（例如 evidence、confidence 等都不允许）。\n\n========================\n4) 三态定义\n========================\n- done：\n  页面内容（HTML 与/或截图）存在“明确证据”表明已经满足 query 描述的状态。\n\n- failed：\n  1) 页面内容表明不满足 query；或\n  2) 没有足够证据证明满足（不确定就算 failed）；或\n  3) query 本身不可能/自相矛盾/无法映射到可验证的页面证据。\n\n- skipped：\n  query 描述的事情“可以合理跳过”（可选、条件触发、非必须、已不再相关），且页面内容表明已满足“跳过条件”。\n\n========================\n5) 判定总原则（非常重要）\n========================\n1) 保守策略：\n   只要你不能确信“满足”，就返回 failed。不要凭常识猜测、不要脑补。\n\n2) 证据优先级：\n   - 以“直接可见证据”为主：\n     - HTML 中的可见文本（标题、按钮、提示、错误/成功消息、空状态文案等）\n     - 常见可访问性/语义信息：aria-label、role、alt、title、placeholder\n     - 关键结构特征：表单字段、登录框、验证码、订单号、进度步骤标题等\n   - 如果存在截图图片附件：\n     - 你必须结合截图中的“可见界面信息”作为证据来源（例如页面标题、弹窗、按钮、提示文案、错误条等）。\n     - 当 HTML 与截图冲突时：优先相信截图（因为截图更接近用户所见）。\n\n3) 不要过度引用：\n   reason 中不要粘贴大段 HTML。最多提及少量关键短语/特征（例如“发现‘订单已完成’提示”“存在登录表单与‘Sign in’按钮”等）。\n\n========================\n6) skipped 的使用规则（必须严格满足）\n========================\n只有在同时满足以下条件时才能返回 skipped，否则一律不要用 skipped（用 failed）：\n\nA. query 明确或隐含“可跳过/条件触发/可选”的语义，例如：\n   - 明确可选： “如果有就…”, “可忽略…”, “不需要也行…”, “若出现才处理…”\n   - 条件分支： “如果弹窗出现就关闭”, “if prompted, accept”, “如果需要验证才去验证”\n\nB. 页面证据显示“跳过条件成立”，例如（需有明确证据）：\n   - query 指的弹窗/提示并不存在（截图无弹窗，HTML 无弹窗结构/文案）\n   - 已经处在更后续步骤（例如已经登录、已经验证完成、已经在目标页面）\n   - 该步骤本身在当前页面不适用（例如用户已满足前置条件）\n\n只要你对 A 或 B 任一条件不确定，就不要返回 skipped。\n\n========================\n7) 处理矛盾与模糊\n========================\n- 矛盾：如果 query 要求互斥状态（例如“同时已登录且未登录”），返回 failed。\n- 过于模糊：例如“页面正常吗”“是不是对的”，无法映射到可验证证据，返回 failed。\n- query 可能是任意语言：你需要在 HTML 与截图中寻找对应语言或同义表达。\n\n========================\n8) 常见证据清单（非穷尽）\n========================\ndone 常见证据：\n- 成功提示：Success / 已完成 / 提交成功 / Order confirmed / Thank you\n- 明确的目标页面标题/面包屑/步骤名匹配 query\n- 已登录迹象：用户昵称、头像、Logout/Sign out\n- 订单号/支付成功/下载完成等关键标识\n\nfailed 常见证据：\n- 错误提示：Error / 失败 / 无权限 / Access denied\n- 需要登录：Sign in / Login / 输入密码\n- 不在目标页面：标题/主区域明显不匹配\n- 缺少关键元素：query 明确需要的按钮/表单/内容不存在\n\nskipped 常见证据：\n- query 提到的可选弹窗未出现（截图无弹窗，HTML 无相关文案/结构）\n- 已越过该步骤：例如已经完成验证/已绑定/已同意\n- 明确显示“此步骤可跳过/不适用”\n\n========================\n9) 最终硬性要求\n========================\n你必须始终只输出如下形状的 JSON，并且只输出这一段：\n{\"status\":\"done|skipped|failed\",\"reason\":\"...\"}"},
		];
		/*#{1JG7SV6360PrePrompt*/
		input={
			html:pageHtml,
			query:cacheQuery
		};
		/*}#1JG7SV6360PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JG7SV6360FilterMessage*/
			/*}#1JG7SV6360FilterMessage*/
			messages.push(msg);
		}
		/*#{1JG7SV6360PreCall*/
		/*}#1JG7SV6360PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("AiGetStatus@"+agentURL,opts,messages,true)):result;
		}
		result=trimJSON(result);
		/*#{1JG7SV6360PostCall*/
		result={status:"done",value:{kind:"status",status:result.status,reason:result.reason}};
		/*}#1JG7SV6360PostCall*/
		/*#{1JG7SV6360PreResult*/
		/*}#1JG7SV6360PreResult*/
		return {seg:JumpAsk,result:(result),preSeg:"1JG7SV6360",outlet:"1JG7T20Q51"};
	};
	AiGetStatus.jaxId="1JG7SV6360"
	AiGetStatus.url="AiGetStatus@"+agentURL
	
	segs["JumpAsk"]=JumpAsk=async function(input){//:1JG7T1HJU0
		let result=input;
		return {seg:AskIfCache,result:result,preSeg:"1JG7SGUC20",outlet:"1JG7T20Q52"};
	
	};
	JumpAsk.jaxId="1JG7SGUC20"
	JumpAsk.url="JumpAsk@"+agentURL
	
	segs["FinFindSelector"]=FinFindSelector=async function(input){//:1JG7TB6UB0
		let result=input
		try{
			/*#{1JG7TB6UB0Code*/
			result={status:"done",value:{kind:"selector",selector:matchedSelector,fromCache:true,loose:!!isLooseSelector},selector:matchedSelector};
			/*}#1JG7TB6UB0Code*/
		}catch(error){
			/*#{1JG7TB6UB0ErrorCode*/
			/*}#1JG7TB6UB0ErrorCode*/
		}
		return {result:result};
	};
	FinFindSelector.jaxId="1JG7TB6UB0"
	FinFindSelector.url="FinFindSelector@"+agentURL
	
	segs["WriteCode"]=WriteCode=async function(input){//:1JGBUS8VC0
		let result;
		let arg={"pageRef":pageRef,"action":"","flowArgs":flowArgs,"flowVars":flowVars,"flowOpts":flowOpts,"flowResult":flowResult};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./Util_WriteCode.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JGBUS8VC0Input*/
		arg.action={type:"run_js",query:cacheQuery,scope:codeScope};
		/*}#1JGBUS8VC0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JGBUS8VC0Output*/
		/*}#1JGBUS8VC0Output*/
		return {seg:CheckCode,result:(result),preSeg:"1JGBUS8VC0",outlet:"1JGBUTH4H0"};
	};
	WriteCode.jaxId="1JGBUS8VC0"
	WriteCode.url="WriteCode@"+agentURL
	
	segs["CheckCode"]=CheckCode=async function(input){//:1JGBUVIFQ0
		let result=input;
		/*#{1JGBUVIFQ0Start*/
		let codeText;
		codeText=input?.value?.code||input?.code;
		/*}#1JGBUVIFQ0Start*/
		if(input.status==="done" && codeText){
			let output=input;
			/*#{1JGBV18190Codes*/
			/*}#1JGBV18190Codes*/
			return {seg:SaveCode,result:(output),preSeg:"1JGBUVIFQ0",outlet:"1JGBV18190"};
		}
		/*#{1JGBUVIFQ0Post*/
		result={status:"failed",reason:`Write code failed: ${input.reason}`};
		/*}#1JGBUVIFQ0Post*/
		return {seg:BackToApp,result:(result),preSeg:"1JGBUVIFQ0",outlet:"1JGBV18191"};
	};
	CheckCode.jaxId="1JGBUVIFQ0"
	CheckCode.url="CheckCode@"+agentURL
	
	segs["SaveCode"]=SaveCode=async function(input){//:1JGLNR5O70
		let result=input
		try{
			/*#{1JGLNR5O70Code*/
			let codeText;
			codeText=input?.value?.code||input?.code;
			const ctx = await CacheAPI.openRuleCache(session, context.aaPage);
			CacheAPI.setCode(ctx, cacheKey, codeText, {
				query: cacheQuery,
			});
			await CacheAPI.flushRuleCache(ctx);
			result={status:"done",value:{kind:"code",code:codeText,fromCache:false},code:codeText};
			/*}#1JGLNR5O70Code*/
		}catch(error){
			/*#{1JGLNR5O70ErrorCode*/
			let codeText;
			codeText=input?.value?.code||input?.code;
			result={status:"done",value:{kind:"code",code:codeText,fromCache:false},code:codeText};
			/*}#1JGLNR5O70ErrorCode*/
		}
		return {seg:BackToApp,result:(result),preSeg:"1JGLNR5O70",outlet:"1JGLNS8980"};
	};
	SaveCode.jaxId="1JGLNR5O70"
	SaveCode.url="SaveCode@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"Util_ResolveQuery",
		url:agentURL,
		autoStart:true,
		jaxId:"1JGD5B9DG0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,cacheKey,cacheQuery,cacheKind,cachePolicy,flowArgs,flowVars,flowOpts,flowResult,flowHistory,selectorMode,codeScope}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JGD5B9DG0PreEntry*/
			/*}#1JGD5B9DG0PreEntry*/
			result={seg:CheckArray,"input":input};
			/*#{1JGD5B9DG0PostEntry*/
			/*}#1JGD5B9DG0PostEntry*/
			return result;
		},
		/*#{1JGD5B9DG0MoreAgentAttrs*/
		/*}#1JGD5B9DG0MoreAgentAttrs*/
	};
	/*#{1JGD5B9DG0PostAgent*/
	/*}#1JGD5B9DG0PostAgent*/
	return agent;
};
/*#{1JGD5B9DG0ExCodes*/
/*}#1JGD5B9DG0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "Util_ResolveQuery",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				cacheKey:{type:"auto",description:""},
				cacheQuery:{type:"auto",description:""},
				cacheKind:{type:"auto",description:""},
				cachePolicy:{type:"auto",description:""},
				flowArgs:{type:"auto",description:""},
				flowVars:{type:"auto",description:""},
				flowOpts:{type:"auto",description:""},
				flowResult:{type:"auto",description:""},
				flowHistory:{type:"auto",description:""},
				selectorMode:{type:"auto",description:""},
				codeScope:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1JGD5B9DG0PostDoc*/
/*}#1JGD5B9DG0PostDoc*/


export default Util_ResolveQuery;
export{Util_ResolveQuery,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JGD5B9DG0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JG7QJDMG1",
//			"attrs": {
//				"Util_ResolveQuery": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JG7QJDMH0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JG7QJDMH1",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JG7QJDMH2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JG7QJDMH3",
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
//			"jaxId": "1JG7QJDMG2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JG7QJDMG3",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JG7RU37A0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"cacheKey": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JG7RU37A1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"cacheQuery": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JG7RU37A2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"cacheKind": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JG7RU37A3",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"cachePolicy": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JG8OF94T0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flowArgs": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGAFILIN0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flowVars": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGAFILIN1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flowOpts": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JG80R24B0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flowResult": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGJGGDPS0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flowHistory": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGAFVOBN0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"selectorMode": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JG8OF94T1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"codeScope": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGLMNP2U0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JG7QJDMG4",
//			"attrs": {
//				"matchedSelector": {
//					"type": "auto",
//					"valText": ""
//				},
//				"isLooseSelector": {
//					"type": "bool",
//					"valText": "false"
//				},
//				"usedSelector": {
//					"type": "auto",
//					"valText": ""
//				},
//				"orgQuery": {
//					"type": "auto",
//					"valText": ""
//				},
//				"pageHtml": {
//					"type": "auto",
//					"valText": ""
//				},
//				"wrongCodes": {
//					"type": "auto",
//					"valText": "#[]"
//				},
//				"codeRetryNum": {
//					"type": "int",
//					"valText": "0"
//				},
//				"queryLoopIdx": {
//					"type": "int",
//					"valText": "0"
//				},
//				"queryLoopErrorIdx": {
//					"type": "int",
//					"valText": "0"
//				},
//				"queryLoopError": {
//					"type": "int",
//					"valText": "0"
//				},
//				"queryLoopResult": {
//					"type": "auto",
//					"valText": ""
//				},
//				"usedCache": {
//					"type": "auto",
//					"valText": ""
//				},
//				"usedSigKey": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JG7QJDMG5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JG7QJDMG6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JGBVCJVP0",
//					"attrs": {
//						"id": "CheckArray",
//						"viewName": "",
//						"label": "",
//						"x": "85",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGBVF9KC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGBVF9KC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JGBVF9K21",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JG7RTVB90"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JGBVF9K20",
//									"attrs": {
//										"id": "Array",
//										"desc": "输出节点。",
//										"output": "#cacheQuery",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGBVF9KC2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGBVF9KC3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#Array.isArray(cacheQuery)"
//									},
//									"linkedSeg": "1JGBVF02P0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1JGBVF02P0",
//					"attrs": {
//						"id": "LoopQuery",
//						"viewName": "",
//						"label": "",
//						"x": "325",
//						"y": "260",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JGBVF9KC4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGBVF9KC5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1JGBVF9KC6",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGBVHQL70"
//						},
//						"catchlet": {
//							"jaxId": "1JGBVF9K22",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGBVJQCI0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JGBVHQL70",
//					"attrs": {
//						"id": "ResolveQuery",
//						"viewName": "",
//						"label": "",
//						"x": "575",
//						"y": "150",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JGBVL7CA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGBVL7CA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Util_ResolveQuery.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"cacheKey\":\"#cacheKey+\\\"#\\\"+queryLoopIdx\",\"cacheQuery\":\"#input.text||input\",\"cacheKind\":\"#cacheKind\",\"cachePolicy\":\"#cachePolicy\",\"flowArgs\":\"#flowArgs\",\"flowVars\":\"#flowVars\",\"flowOpts\":\"#flowOpts\",\"flowHistory\":\"#flowHistory\",\"selectorMode\":\"#selectorMode\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JGBVL7C20",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGBVJ4GM0"
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
//					"jaxId": "1JGBVJ4GM0",
//					"attrs": {
//						"id": "CheckResolve",
//						"viewName": "",
//						"label": "",
//						"x": "820",
//						"y": "150",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGBVL7CA2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGBVL7CA3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JGBVL7C22",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。",
//								"output": ""
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JGBVL7C21",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGBVL7CA4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGBVL7CA5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.status===\"done\" && input.value"
//									}
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
//					"jaxId": "1JGBVJQCI0",
//					"attrs": {
//						"id": "FinArray",
//						"viewName": "",
//						"label": "",
//						"x": "575",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGBVL7CA6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGBVL7CA7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JGBVL7C23",
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
//					"def": "WebRpaStart",
//					"jaxId": "1JG7RTVB90",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "575",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JG7RTVB91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7RTVB92",
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
//							"jaxId": "1JG7RTVB93",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7RUB8O0"
//						},
//						"catchlet": {
//							"jaxId": "1JG7RTVB94",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JG7RTVB95",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JG7RTVB96",
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
//					"jaxId": "1JG7RUB8O0",
//					"attrs": {
//						"id": "ReadCache",
//						"viewName": "",
//						"label": "",
//						"x": "830",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7RUHT30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7RUHT31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7RUHT20",
//							"attrs": {
//								"id": "NoCache",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JG7SKG3I0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG7S2BQT0",
//									"attrs": {
//										"id": "Find",
//										"desc": "输出节点。",
//										"output": "#cache",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JG7S2BQV0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG7S2BQV1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#cache"
//									},
//									"linkedSeg": "1JG7RVDVE0"
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
//					"jaxId": "1JG7RVDVE0",
//					"attrs": {
//						"id": "CacheKind",
//						"viewName": "",
//						"label": "",
//						"x": "1095",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7S2BQV2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7S2BQV3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7S2BQT2",
//							"attrs": {
//								"id": "Value",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JG7S15S90"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG7S2BQT1",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "#input.selectors",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JG7S2BQV4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG7S2BQV5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.kind===\"selector\""
//									},
//									"linkedSeg": "1JG7S2TIS0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG7S02II0",
//									"attrs": {
//										"id": "Code",
//										"desc": "输出节点。",
//										"output": "#result",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JG7S2BQV8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG7S2BQV9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.kind===\"code\""
//									},
//									"linkedSeg": "1JG7S15S90"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG7RVRUF0",
//									"attrs": {
//										"id": "Status",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JG7S2BQV6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG7S2BQV7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.kind===\"status\""
//									},
//									"linkedSeg": "1JG7S15S90"
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
//					"jaxId": "1JG7S15S90",
//					"attrs": {
//						"id": "FinNotSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1350",
//						"y": "250",
//						"desc": "找到了非Selector的cache，直接返回。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JG7S2BQV10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7S2BQV11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7S2BQT3",
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
//					"jaxId": "1JG7S2TIS0",
//					"attrs": {
//						"id": "LoopSelectors",
//						"viewName": "",
//						"label": "",
//						"x": "1360",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7S4QR20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7S4QR21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1JG7S4QR10",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7S3V9S1"
//						},
//						"catchlet": {
//							"jaxId": "1JG7S4QR11",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7S72D60"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JG7S3V9S1",
//					"attrs": {
//						"id": "QueryCache",
//						"viewName": "",
//						"label": "",
//						"x": "1620",
//						"y": "50",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7S3V9S2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7S3V9S3",
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
//							"jaxId": "1JG7S3V9S4",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7S53KE0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JG7S3V9S5",
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
//					"jaxId": "1JG7S53KE0",
//					"attrs": {
//						"id": "BreakFind",
//						"viewName": "",
//						"label": "",
//						"x": "1885",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7SE6J00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7SE6J01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7SE6IU0",
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
//					"jaxId": "1JG7S72D60",
//					"attrs": {
//						"id": "CheckFind",
//						"viewName": "",
//						"label": "",
//						"x": "1620",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7SE6J02",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7SE6J03",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7SE6IU2",
//							"attrs": {
//								"id": "NotFind",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JG7TCHI60"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG7SE6IU1",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "#matchedSelector",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JG7SE6J04",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG7SE6J05",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!matchedSelector"
//									},
//									"linkedSeg": "1JG7TB6UB0"
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
//					"jaxId": "1JG7S98TB0",
//					"attrs": {
//						"id": "OnInputKind",
//						"viewName": "",
//						"label": "",
//						"x": "1365",
//						"y": "595",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7SE6J08",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7SE6J09",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7SE6IV0",
//							"attrs": {
//								"id": "Other",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JG7SQJE10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG7SE6IU3",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JG7SE6J010",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG7SE6J011",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#cacheKind===\"selector\" || !cacheKind"
//									},
//									"linkedSeg": "1JG7SC7HS0"
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
//					"jaxId": "1JG7SC7HS0",
//					"attrs": {
//						"id": "FindSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1620",
//						"y": "490",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7SC7HS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7SC7HS2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Util_FindSelector.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"url\":\"\",\"profile\":\"\",\"selectDesc\":\"#cacheQuery\",\"multiSelect\":\"#selectorMode===\\\"class\\\"\",\"useManual\":\"#flowOpts.useManual\",\"allowManual\":\"#flowOpts.allowManual\",\"manualTraining\":\"\",\"ruleKey\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JG7SC7HT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7SCU7L0"
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
//					"jaxId": "1JG7SCU7L0",
//					"attrs": {
//						"id": "CheckSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1885",
//						"y": "490",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7SE6J014",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7SE6J015",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7SE6IV1",
//							"attrs": {
//								"id": "Failed",
//								"desc": "输出节点。",
//								"output": "#input"
//							},
//							"linkedSeg": "1JG7SGUC20"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG7SI7GI0",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JG7SI7GK0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG7SI7GK1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.status===\"done\" && input.value"
//									},
//									"linkedSeg": "1JG7SFVRC0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG7SEKCD0",
//									"attrs": {
//										"id": "Status",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JG7SI7GK2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG7SI7GK3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.status!==\"done\" || input.kind===\"status\""
//									},
//									"linkedSeg": "1JG7SGUC20"
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
//					"jaxId": "1JG7SFVRC0",
//					"attrs": {
//						"id": "SaveSelector",
//						"viewName": "",
//						"label": "",
//						"x": "2155",
//						"y": "415",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7SI7GK4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7SI7GK5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7SI7GJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7T619E0"
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
//					"jaxId": "1JG7SGUC20",
//					"attrs": {
//						"id": "AskIfCache",
//						"viewName": "",
//						"label": "",
//						"x": "2155",
//						"y": "505",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7SI7GK6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7SI7GK7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7SI7GJ1",
//							"attrs": {
//								"id": "NotSave",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JG7T45420"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG7SM4FM0",
//									"attrs": {
//										"id": "Save",
//										"desc": "输出节点。",
//										"output": "#result",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JG7SM4FP0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG7SM4FP1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!res"
//									},
//									"linkedSeg": "1JG7T45420"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaActivePage",
//					"jaxId": "1JG7SKG3I0",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "1100",
//						"y": "595",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7SM4FP2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7SM4FP3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true,\"switchBack\":0}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JG7SM4FM1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7S98TB0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JG7SN1A60",
//					"attrs": {
//						"id": "BackToApp",
//						"viewName": "",
//						"label": "",
//						"x": "2995",
//						"y": "505",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7SNSC80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7SNSC81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JG7SNSC50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1JG7SQJE10",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "1620",
//						"y": "755",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JG7T20QA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7T20QA1",
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
//							"jaxId": "1JG7T20Q40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7SSFEG0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JG7SSFEG0",
//					"attrs": {
//						"id": "OnCacheKind",
//						"viewName": "",
//						"label": "",
//						"x": "1885",
//						"y": "755",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG7T20QA2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7T20QA3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7T20Q42",
//							"attrs": {
//								"id": "Status",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JG7SV6360"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG7T20Q41",
//									"attrs": {
//										"id": "Code",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JG7T20QA4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG7T20QA5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "cacheKind===\"code\""
//									},
//									"linkedSeg": "1JGBUS8VC0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JG7SV6360",
//					"attrs": {
//						"id": "AiGetStatus",
//						"viewName": "",
//						"label": "",
//						"x": "2155",
//						"y": "770",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JG7T20QA10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7T20QA11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-5",
//						"system": "你是一个“页面状态判定器”（page-state validator）。你的任务是：根据输入提供的网页内容（HTML + 可能的截图图片）与用户的状态描述（query），判断当前页面是否符合该状态，并按要求输出严格 JSON。\n\n========================\n1) 目标\n========================\n给定：\n- 清洗后的 HTML 字符串（可能很长）\n- 用户想确认的“状态描述” query（自然语言）\n- 以及（可选）网页截图图片附件\n判断页面是否满足该状态，并返回三态之一：done / skipped / failed。\n\n========================\n2) 输入格式\n========================\n你会收到一个输入，通常是 JSON（也可能是一段可解析为 JSON 的文本），字段可能包含：\n- \"html\": string   （清洗后的 HTML）\n- \"query\": string  （用户想确认的状态描述）\n- （可选）图片附件：网页截图（可能 1 张或多张）\n\n重要：\n- 如果输入不是合法 JSON，但明显包含 \"html\" 与 \"query\"，你必须尽力提取它们。\n- 若无法可靠地提取 \"html\" 或 \"query\" 任意一个，则返回 status=\"failed\"。\n\n========================\n3) 输出格式（严格）\n========================\n你必须且只能输出 **一个 JSON 对象**（不要 markdown、不要代码围栏、不要额外解释文本），且仅允许以下字段：\n- \"status\": \"done\" | \"skipped\" | \"failed\"\n- \"reason\": string\n\n不允许出现任何其他 key（例如 evidence、confidence 等都不允许）。\n\n========================\n4) 三态定义\n========================\n- done：\n  页面内容（HTML 与/或截图）存在“明确证据”表明已经满足 query 描述的状态。\n\n- failed：\n  1) 页面内容表明不满足 query；或\n  2) 没有足够证据证明满足（不确定就算 failed）；或\n  3) query 本身不可能/自相矛盾/无法映射到可验证的页面证据。\n\n- skipped：\n  query 描述的事情“可以合理跳过”（可选、条件触发、非必须、已不再相关），且页面内容表明已满足“跳过条件”。\n\n========================\n5) 判定总原则（非常重要）\n========================\n1) 保守策略：\n   只要你不能确信“满足”，就返回 failed。不要凭常识猜测、不要脑补。\n\n2) 证据优先级：\n   - 以“直接可见证据”为主：\n     - HTML 中的可见文本（标题、按钮、提示、错误/成功消息、空状态文案等）\n     - 常见可访问性/语义信息：aria-label、role、alt、title、placeholder\n     - 关键结构特征：表单字段、登录框、验证码、订单号、进度步骤标题等\n   - 如果存在截图图片附件：\n     - 你必须结合截图中的“可见界面信息”作为证据来源（例如页面标题、弹窗、按钮、提示文案、错误条等）。\n     - 当 HTML 与截图冲突时：优先相信截图（因为截图更接近用户所见）。\n\n3) 不要过度引用：\n   reason 中不要粘贴大段 HTML。最多提及少量关键短语/特征（例如“发现‘订单已完成’提示”“存在登录表单与‘Sign in’按钮”等）。\n\n========================\n6) skipped 的使用规则（必须严格满足）\n========================\n只有在同时满足以下条件时才能返回 skipped，否则一律不要用 skipped（用 failed）：\n\nA. query 明确或隐含“可跳过/条件触发/可选”的语义，例如：\n   - 明确可选： “如果有就…”, “可忽略…”, “不需要也行…”, “若出现才处理…”\n   - 条件分支： “如果弹窗出现就关闭”, “if prompted, accept”, “如果需要验证才去验证”\n\nB. 页面证据显示“跳过条件成立”，例如（需有明确证据）：\n   - query 指的弹窗/提示并不存在（截图无弹窗，HTML 无弹窗结构/文案）\n   - 已经处在更后续步骤（例如已经登录、已经验证完成、已经在目标页面）\n   - 该步骤本身在当前页面不适用（例如用户已满足前置条件）\n\n只要你对 A 或 B 任一条件不确定，就不要返回 skipped。\n\n========================\n7) 处理矛盾与模糊\n========================\n- 矛盾：如果 query 要求互斥状态（例如“同时已登录且未登录”），返回 failed。\n- 过于模糊：例如“页面正常吗”“是不是对的”，无法映射到可验证证据，返回 failed。\n- query 可能是任意语言：你需要在 HTML 与截图中寻找对应语言或同义表达。\n\n========================\n8) 常见证据清单（非穷尽）\n========================\ndone 常见证据：\n- 成功提示：Success / 已完成 / 提交成功 / Order confirmed / Thank you\n- 明确的目标页面标题/面包屑/步骤名匹配 query\n- 已登录迹象：用户昵称、头像、Logout/Sign out\n- 订单号/支付成功/下载完成等关键标识\n\nfailed 常见证据：\n- 错误提示：Error / 失败 / 无权限 / Access denied\n- 需要登录：Sign in / Login / 输入密码\n- 不在目标页面：标题/主区域明显不匹配\n- 缺少关键元素：query 明确需要的按钮/表单/内容不存在\n\nskipped 常见证据：\n- query 提到的可选弹窗未出现（截图无弹窗，HTML 无相关文案/结构）\n- 已越过该步骤：例如已经完成验证/已绑定/已同意\n- 明确显示“此步骤可跳过/不适用”\n\n========================\n9) 最终硬性要求\n========================\n你必须始终只输出如下形状的 JSON，并且只输出这一段：\n{\"status\":\"done|skipped|failed\",\"reason\":\"...\"}",
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
//							"jaxId": "1JG7T20Q51",
//							"attrs": {
//								"id": "Failed",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7T1HJU0"
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
//					"def": "jumper",
//					"jaxId": "1JG7T1HJU0",
//					"attrs": {
//						"id": "JumpAsk",
//						"viewName": "",
//						"label": "",
//						"x": "2420",
//						"y": "770",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JG7SGUC20",
//						"outlet": {
//							"jaxId": "1JG7T20Q52",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JG7T45420",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2415",
//						"y": "505",
//						"outlet": {
//							"jaxId": "1JG7T6E9G6",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7SN1A60"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JG7T4V2V0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2850",
//						"y": "675",
//						"outlet": {
//							"jaxId": "1JG7T6E9G7",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7SN1A60"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JG7T619E0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2820",
//						"y": "415",
//						"outlet": {
//							"jaxId": "1JG7T6E9G8",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7SN1A60"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JG7TB6UB0",
//					"attrs": {
//						"id": "FinFindSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1885",
//						"y": "175",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JG7TC44M0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG7TC44M1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG7TC44J0",
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
//					"def": "connector",
//					"jaxId": "1JG7TCHI60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1765",
//						"y": "385",
//						"outlet": {
//							"jaxId": "1JG7TEFGG0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7TCO6S0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JG7TCO6S0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1145",
//						"y": "385",
//						"outlet": {
//							"jaxId": "1JG7TEFGG1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7SKG3I0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JGBUS8VC0",
//					"attrs": {
//						"id": "WriteCode",
//						"viewName": "",
//						"label": "",
//						"x": "2155",
//						"y": "660",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGBUTH4P0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGBUTH4P1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Util_WriteCode.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"action\":\"\",\"flowArgs\":\"#flowArgs\",\"flowVars\":\"#flowVars\",\"flowOpts\":\"#flowOpts\",\"flowResult\":\"#flowResult\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JGBUTH4H0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGBUVIFQ0"
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
//					"jaxId": "1JGBUVIFQ0",
//					"attrs": {
//						"id": "CheckCode",
//						"viewName": "",
//						"label": "",
//						"x": "2420",
//						"y": "660",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGBV181H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGBV181H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JGBV18191",
//							"attrs": {
//								"id": "Failed",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JG7T4V2V0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JGBV18190",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JGBV181H2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGBV181H3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.status===\"done\" && codeText"
//									},
//									"linkedSeg": "1JGLNR5O70"
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
//					"jaxId": "1JGLNR5O70",
//					"attrs": {
//						"id": "SaveCode",
//						"viewName": "",
//						"label": "",
//						"x": "2670",
//						"y": "595",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGLNS89H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGLNS89H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JGLNS8980",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG7SN1A60"
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