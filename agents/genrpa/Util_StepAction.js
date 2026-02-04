//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JF1KICQ10MoreImports*/
import {parseFlowVal,runBranchAction,execRunJsAction} from "./utils_flow.js";
import {expandDottedKeys} from "./utils.js";
/*}#1JF1KICQ10MoreImports*/
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
		"action":{
			"name":"action","type":"auto",
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
		},
		"vars":{
			"name":"vars","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"lastResult":{
			"name":"lastResult","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JF1KICQ10ArgsView*/
	/*}#1JF1KICQ10ArgsView*/
};

/*#{1JF1KICQ10StartDoc*/
/*}#1JF1KICQ10StartDoc*/
//----------------------------------------------------------------------------
let Util_StepAction=async function(session){
	let pageRef,action,args,opts,vars,lastResult;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,OnAction,HyperInput,Click,Hover,Wheel,Scroll2Show,OldInput,PressKey,GotoUrl,RunJS,FinDone,Invoke,ShowPage,TipAndWait,FinManual,Branch,FailManual,FinFailed,CanManual,FailNoManual,Selector,Wait,OldSelector,_FlagWait,WaitSelector,FinWaitDone,FinWaitError,FlagFile,ClickFile,AwaitFile,UploadFile,FinUploadFile,RunAI,FinAI,ReadPage,ReadElement,SetChecked,SetSelect;
	let ctxArgs=undefined;
	let ctxOpts=undefined;
	let ctxVars=undefined;
	let ctxResult=undefined;
	
	/*#{1JF1KICQ10LocalVals*/
	/*}#1JF1KICQ10LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			action=input.action;
			args=input.args;
			opts=input.opts;
			vars=input.vars;
			lastResult=input.lastResult;
		}else{
			pageRef=undefined;
			action=undefined;
			args=undefined;
			opts=undefined;
			vars=undefined;
			lastResult=undefined;
		}
		/*#{1JF1KICQ10ParseArgs*/
		ctxArgs=args;
		ctxVars=vars;
		ctxOpts=opts;
		ctxResult=lastResult;
		/*}#1JF1KICQ10ParseArgs*/
	}
	
	/*#{1JF1KICQ10PreContext*/
	/*}#1JF1KICQ10PreContext*/
	context={};
	/*#{1JF1KICQ10PostContext*/
	/*}#1JF1KICQ10PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JF1KIV0I0
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JF1KIV0I0"));
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
		return {seg:OnAction,result:(result),preSeg:"1JF1KIV0I0",outlet:"1JF1KIV0J0"};
	};
	StartRpa.jaxId="1JF1KIV0I0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["OnAction"]=OnAction=async function(input){//:1JF1KJM740
		let result=input;
		/*#{1JF1KJM740Start*/
		/*}#1JF1KJM740Start*/
		if(action.type==="input"){
			return {seg:HyperInput,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KM9ER0"};
		}
		if(action.type==="click"){
			return {seg:Click,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KN5DK0"};
		}
		if(action.type==="hover"){
			return {seg:Hover,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KK46L0"};
		}
		if(action.type==="scroll"){
			return {seg:Wheel,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KK9E00"};
		}
		if(action.type==="scroll_show"){
			return {seg:Scroll2Show,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KR6PS0"};
		}
		if(action.type==="press_key"){
			return {seg:PressKey,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KMOVH0"};
		}
		if(action.type==="goto"){
			return {seg:GotoUrl,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KNH540"};
		}
		if(action.type==="selector"){
			return {seg:Selector,result:(input),preSeg:"1JF1KJM740",outlet:"1JFFFK1KH0"};
		}
		if(action.type==="run_js"){
			return {seg:RunJS,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KRRDF0"};
		}
		if(action.type==="branch"){
			return {seg:Branch,result:(input),preSeg:"1JF1KJM740",outlet:"1JF9EG0BU0"};
		}
		if(action.type==="invoke"){
			return {seg:Invoke,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1LAEJO0"};
		}
		if(action.type==="ask_assist"){
			return {seg:CanManual,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KSDT00"};
		}
		if(action.type==="wait"){
			return {seg:Wait,result:(input),preSeg:"1JF1KJM740",outlet:"1JFH7FACN0"};
		}
		if(action.type==="uploadFile"){
			return {seg:FlagFile,result:(input),preSeg:"1JF1KJM740",outlet:"1JFPV72S70"};
		}
		if(action.type==="run_ai"){
			return {seg:RunAI,result:(input),preSeg:"1JF1KJM740",outlet:"1JFRQISI60"};
		}
		if(action.type==="readPage"){
			return {seg:ReadPage,result:(input),preSeg:"1JF1KJM740",outlet:"1JFRU6FBD0"};
		}
		if(action.type==="readElement"){
			return {seg:ReadElement,result:(input),preSeg:"1JF1KJM740",outlet:"1JFTFRP900"};
		}
		if(input==="DragDrop"){
			return {result:input};
		}
		if(action.type==="setChecked"){
			return {seg:SetChecked,result:(input),preSeg:"1JF1KJM740",outlet:"1JFTFMBBF0"};
		}
		if(input==="SetSelection"){
			return {seg:SetSelect,result:(input),preSeg:"1JF1KJM740",outlet:"1JFTFRE590"};
		}
		/*#{1JF1KJM740Post*/
		/*}#1JF1KJM740Post*/
		return {result:result};
	};
	OnAction.jaxId="1JF1KJM740"
	OnAction.url="OnAction@"+agentURL
	
	segs["HyperInput"]=HyperInput=async function(input){//:1JFPB8MPS0
		let result=input
		try{
			/*#{1JFPB8MPS0Code*/
			let page,$text;
			page=context.aaPage;
			$text=action.text;
			$text=parseFlowVal($text,ctxArgs,ctxOpts,ctxVars,ctxResult);
			if(action.clear || action.mode==="fill"){
				await page.pressShortcut(["SelectAll","Backspace"],{});
			}else{
				let caret=action.caret||"end";
				if(caret==="end"){
					await page.pressShortcut(["SelectAll","ArrowDown"],{});
				}else if(caret==="start"){
					await page.pressShortcut(["SelectAll","ArrowUp"],{});
				}
			}
			if(action.mode==="paste"){
				await page.pasteText($text,{});
			}else{
				await page.keyboard.type($text,{});
			}
			if(action.pressEnter){
				await page.pressShortcut(["Enter"],{});
			}
			/*}#1JFPB8MPS0Code*/
		}catch(error){
			/*#{1JFPB8MPS0ErrorCode*/
			/*}#1JFPB8MPS0ErrorCode*/
		}
		return {seg:FinDone,result:(result),preSeg:"1JFPB8MPS0",outlet:"1JFPB8V9A0"};
	};
	HyperInput.jaxId="1JFPB8MPS0"
	HyperInput.url="HyperInput@"+agentURL
	
	segs["Click"]=Click=async function(input){//:1JF1KV6480
		let result=true;
		let pageVal="aaPage";
		let $query=action.by;
		let $queryHint="";
		let $x=0;
		let $y=0;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=500;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JF1KV6480")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.click($query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
			}else{
				$pms=page.mouse.click($x,$y,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JF1KV6480ErrorCode*/
			/*}#1JF1KV6480ErrorCode*/
			return {seg:FinFailed,result:error,preSeg:"1JF1KV6480",outlet:null};
		}
		return {seg:FinDone,result:(result),preSeg:"1JF1KV6480",outlet:"1JF1L0EI40"};
	};
	Click.jaxId="1JF1KV6480"
	Click.url="Click@"+agentURL
	
	segs["Hover"]=Hover=async function(input){//:1JF1KVGRK0
		let result=true;
		let pageVal="aaPage";
		let $query=input.by;
		let $queryHint=action.by;
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
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JF1KVGRK0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.hover($query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
			}else{
				$pms=page.mouse.move($x,$y,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JF1KVGRK0ErrorCode*/
			/*}#1JF1KVGRK0ErrorCode*/
			return {seg:FinFailed,result:error,preSeg:"1JF1KVGRK0",outlet:null};
		}
		return {seg:FinDone,result:(result),preSeg:"1JF1KVGRK0",outlet:"1JF1L0EI41"};
	};
	Hover.jaxId="1JF1KVGRK0"
	Hover.url="Hover@"+agentURL
	
	segs["Wheel"]=Wheel=async function(input){//:1JF1L05JJ0
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint="";
		let $deltaX=0;
		let $deltaY=action.y||action.by||300;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JF1L05JJ0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.mouseWheel($query,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
			}else{
				$pms=page.mouseWheel(null,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JF1L05JJ0ErrorCode*/
			/*}#1JF1L05JJ0ErrorCode*/
			return {seg:FinFailed,result:error,preSeg:"1JF1L05JJ0",outlet:null};
		}
		return {seg:FinDone,result:(result),preSeg:"1JF1L05JJ0",outlet:"1JF1L0EI42"};
	};
	Wheel.jaxId="1JF1L05JJ0"
	Wheel.url="Wheel@"+agentURL
	
	segs["Scroll2Show"]=Scroll2Show=async function(input){//:1JF1L0NDP0
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint=action.by;
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
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JF1L0NDP0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.scrollIntoView($query);
			}
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JF1L0NDP0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.mouseWheel($query,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
			}else{
				$pms=page.mouseWheel(null,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JF1L0NDP0ErrorCode*/
			/*}#1JF1L0NDP0ErrorCode*/
			return {seg:FinFailed,result:error,preSeg:"1JF1L0NDP0",outlet:null};
		}
		return {seg:FinDone,result:(result),preSeg:"1JF1L0NDP0",outlet:"1JF1L3ORS0"};
	};
	Scroll2Show.jaxId="1JF1L0NDP0"
	Scroll2Show.url="Scroll2Show@"+agentURL
	
	segs["OldInput"]=OldInput=async function(input){//:1JF1L428T0
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="";
		let $queryHint="";
		let $key=action.text;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		/*#{1JF1L428T0PreCodes*/
		if(action.clear||action.mode==="fill"){
			page.pressShortcut(["SelectAll","Backspace"],$options||{});
		}
		$key=parseFlowVal($key,ctxArgs,ctxOpts,ctxVars,ctxResult);
		/*}#1JF1L428T0PreCodes*/
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JF1L428T0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.type($query,$key,$options||{});
			}else{
				$pms=page.keyboard.type($key,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JF1L428T0ErrorCode*/
			/*}#1JF1L428T0ErrorCode*/
			return {seg:FinFailed,result:error,preSeg:"1JF1L428T0",outlet:null};
		}
		/*#{1JF1L428T0PostCodes*/
		/*}#1JF1L428T0PostCodes*/
		return {result:result};
	};
	OldInput.jaxId="1JF1L428T0"
	OldInput.url="OldInput@"+agentURL
	
	segs["PressKey"]=PressKey=async function(input){//:1JF1L49S30
		let result=true;
		let pageVal="aaPage";
		let $action="KeyPress";
		let $query="";
		let $queryHint="";
		let $key=action.key;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		try{
			$pms=page.keyboard.press($key,$options||{});
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JF1L49S30ErrorCode*/
			/*}#1JF1L49S30ErrorCode*/
			return {seg:FinFailed,result:error,preSeg:"1JF1L49S30",outlet:null};
		}
		return {seg:FinDone,result:(result),preSeg:"1JF1L49S30",outlet:"1JF1L6UNH1"};
	};
	PressKey.jaxId="1JF1L49S30"
	PressKey.url="PressKey@"+agentURL
	
	segs["GotoUrl"]=GotoUrl=async function(input){//:1JF1L4QRI0
		let result=true;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let timeout=(undefined)||0;
		let url=action.url;
		let page=context[pageVal];
		let opts={timeout:timeout};
		waitBefore && (await sleep(waitBefore));
		/*#{1JF1L4QRI0PreCodes*/
		/*}#1JF1L4QRI0PreCodes*/
		try{
			await page.goto(url,opts);
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JF1L4QRI0ErrorCode*/
			/*}#1JF1L4QRI0ErrorCode*/
			return {seg:FinFailed,result:error,preSeg:"1JF1L4QRI0",outlet:null};
		}
		/*#{1JF1L4QRI0PostCodes*/
		/*}#1JF1L4QRI0PostCodes*/
		return {seg:FinDone,result:(result),preSeg:"1JF1L4QRI0",outlet:"1JF1L6UNH2"};
	};
	GotoUrl.jaxId="1JF1L4QRI0"
	GotoUrl.url="GotoUrl@"+agentURL
	
	segs["RunJS"]=RunJS=async function(input){//:1JF1L5VP90
		let result=input
		try{
			/*#{1JF1L5VP90Code*/
			let ctx,page,value;
			page=context.aaPage;
			ctx={
				args:ctxArgs,
				vars:ctxVars,
				opts:ctxOpts,
				result:ctxResult,
				pageEval:async function(code,args){
					return await page.callFunction(code,args);
				}
			};
			result=await execRunJsAction(action,ctx);
			/*}#1JF1L5VP90Code*/
		}catch(error){
			/*#{1JF1L5VP90ErrorCode*/
			result={status:"Failed",result:"Failed",reaon:`run_js action error: ${error}`}
			/*}#1JF1L5VP90ErrorCode*/
			return {seg:FinFailed,result:error,preSeg:"1JF1L5VP90",outlet:null};
		}
		return {seg:FinDone,result:(result),preSeg:"1JF1L5VP90",outlet:"1JF1L6UNH3"};
	};
	RunJS.jaxId="1JF1L5VP90"
	RunJS.url="RunJS@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JF1L7U0V0
		let result=input
		try{
			/*#{1JF1L7U0V0Code*/
			let value=true;
			if(input && (typeof(input)==="object") && ("value" in input)){
				value=input.value;
			}
			result={status:"done",result:"done",value:value};
			if(action.saveAs){
				ctxVars[action.saveAs]=value;
			}
			/*}#1JF1L7U0V0Code*/
		}catch(error){
			/*#{1JF1L7U0V0ErrorCode*/
			/*}#1JF1L7U0V0ErrorCode*/
		}
		return {result:result};
	};
	FinDone.jaxId="1JF1L7U0V0"
	FinDone.url="FinDone@"+agentURL
	
	segs["Invoke"]=Invoke=async function(input){//:1JF1LBDNU0
		let result;
		let arg=action.args;
		let agentNode=(undefined)||null;
		let $query=(action.find)||null;
		let sourcePath=pathLib.join(basePath,"");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JF1LBDNU0Input*/
		arg=expandDottedKeys(arg);
		arg=parseFlowVal(arg,ctxArgs,ctxOpts,ctxVars,ctxResult);
		arg.pageRef=context.aaPage?.pageRef||pageRef;
		/*}#1JF1LBDNU0Input*/
		result= await session.callAgent(null,$query,arg,opts);
		/*#{1JF1LBDNU0Output*/
		/*}#1JF1LBDNU0Output*/
		return {result:result};
	};
	Invoke.jaxId="1JF1LBDNU0"
	Invoke.url="Invoke@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1JF1LIBD90
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let $options={"focusBrowser":true,"switchBack":0};
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		/*#{1JF1LIBD90PreCodes*/
		/*}#1JF1LIBD90PreCodes*/
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
			/*#{1JF1LIBD90ErrorCode*/
			/*}#1JF1LIBD90ErrorCode*/
		}
		/*#{1JF1LIBD90PostCodes*/
		/*}#1JF1LIBD90PostCodes*/
		return {seg:TipAndWait,result:(result),preSeg:"1JF1LIBD90",outlet:"1JF1LM60L0"};
	};
	ShowPage.jaxId="1JF1LIBD90"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["TipAndWait"]=TipAndWait=async function(input){//:1JF1LJM940
		let prompt=("Please confirm")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Finish",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Item 2",code:1},
		];
		let result="";
		let item=null;
		
		/*#{1JF1LJM940PreCodes*/
		/*}#1JF1LJM940PreCodes*/
		if(silent){
			result="";
			return {seg:FinManual,result:(result),preSeg:"1JF1LJM940",outlet:"1JF1LJM8O0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1JF1LJM940PostCodes*/
		/*}#1JF1LJM940PostCodes*/
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:FinManual,result:(result),preSeg:"1JF1LJM940",outlet:"1JF1LJM8O0"};
		}else if(item.code===1){
			return {seg:FailManual,result:(result),preSeg:"1JF1LJM940",outlet:"1JF1LJM8O1"};
		}
		/*#{1JF1LJM940FinCodes*/
		/*}#1JF1LJM940FinCodes*/
		return {result:result};
	};
	TipAndWait.jaxId="1JF1LJM940"
	TipAndWait.url="TipAndWait@"+agentURL
	
	segs["FinManual"]=FinManual=async function(input){//:1JF1LL26H0
		let result=input
		try{
			/*#{1JF1LL26H0Code*/
			/*}#1JF1LL26H0Code*/
		}catch(error){
			/*#{1JF1LL26H0ErrorCode*/
			/*}#1JF1LL26H0ErrorCode*/
		}
		return {result:result};
	};
	FinManual.jaxId="1JF1LL26H0"
	FinManual.url="FinManual@"+agentURL
	
	segs["Branch"]=Branch=async function(input){//:1JF9EHQKF0
		let result=input
		try{
			/*#{1JF9EHQKF0Code*/
			let nextId;
			nextId=runBranchAction(action,ctxArgs,ctxOpts,ctxVars,ctxResult);
			result={status:"Done",result:"Finish",value:nextId,nextStep:nextId};
			/*}#1JF9EHQKF0Code*/
		}catch(error){
			/*#{1JF9EHQKF0ErrorCode*/
			result={status:"Failed",result:"Failed",reason:`Branch action failed: ${error}`};
			/*}#1JF9EHQKF0ErrorCode*/
			return {seg:FinFailed,result:error,preSeg:"1JF9EHQKF0",outlet:null};
		}
		return {result:result};
	};
	Branch.jaxId="1JF9EHQKF0"
	Branch.url="Branch@"+agentURL
	
	segs["FailManual"]=FailManual=async function(input){//:1JF1LLFB40
		let result=input
		try{
			/*#{1JF1LLFB40Code*/
			/*}#1JF1LLFB40Code*/
		}catch(error){
			/*#{1JF1LLFB40ErrorCode*/
			/*}#1JF1LLFB40ErrorCode*/
		}
		return {result:result};
	};
	FailManual.jaxId="1JF1LLFB40"
	FailManual.url="FailManual@"+agentURL
	
	segs["FinFailed"]=FinFailed=async function(input){//:1JFAMJ9GE0
		let result=input
		try{
			/*#{1JFAMJ9GE0Code*/
			result={status:"failed",result:"failed",reason:input?.reason||`Action "${action.id}" failed.`};
			/*}#1JFAMJ9GE0Code*/
		}catch(error){
			/*#{1JFAMJ9GE0ErrorCode*/
			/*}#1JFAMJ9GE0ErrorCode*/
		}
		return {result:result};
	};
	FinFailed.jaxId="1JFAMJ9GE0"
	FinFailed.url="FinFailed@"+agentURL
	
	segs["CanManual"]=CanManual=async function(input){//:1JFAOR4CG0
		let result=input;
		if(input==="Allow"){
			let output=ctxOpts.allowManual||ctxArgs.ctxOpts.allowManual||ctxOpts.manual||ctxArgs.manual;
			return {seg:ShowPage,result:(output),preSeg:"1JFAOR4CG0",outlet:"1JFAOUFCH0"};
		}
		return {seg:FailNoManual,result:(result),preSeg:"1JFAOR4CG0",outlet:"1JFAOUFCH1"};
	};
	CanManual.jaxId="1JFAOR4CG0"
	CanManual.url="CanManual@"+agentURL
	
	segs["FailNoManual"]=FailNoManual=async function(input){//:1JFAOSB7A0
		let result=input
		try{
			/*#{1JFAOSB7A0Code*/
			/*}#1JFAOSB7A0Code*/
		}catch(error){
			/*#{1JFAOSB7A0ErrorCode*/
			/*}#1JFAOSB7A0ErrorCode*/
		}
		return {result:result};
	};
	FailNoManual.jaxId="1JFAOSB7A0"
	FailNoManual.url="FailNoManual@"+agentURL
	
	segs["Selector"]=Selector=async function(input){//:1JFT5Q9HU0
		let result=input;
		/*#{1JFT5Q9HU0Start*/
		let $find,$scope,$multi,$options;
		let $query=action.by;
		let $autoSwitch=action.autoSwitch!==false;
		$options={timeout:action.timeout||0};
		$scope=action.scope||"current";
		$multi=!!action.multi;
		try{
			if($multi){
				$find=await context.webRpa.queryNodesInPages(null,null,$query,$scope);
			}else{
				$find=await context.webRpa.queryNodeInPages(null,null,$query,$scope);
			}
			if($find && $autoSwitch){
				context.webRpa.setCurrentPage($find.page);
			}
		}catch(err){
			$find=null;
		}
		/*}#1JFT5Q9HU0Start*/
		if($find){
			let output=result;
			/*#{1JFT5RC2L0Codes*/
			output={status:"done",page:$find.page,node:$find.node||$find.nodes,$value:$find.node||$find.nodes,page:context.aaPage?.pageRef};
			/*}#1JFT5RC2L0Codes*/
			return {result:output};
		}
		/*#{1JFT5Q9HU0Post*/
		result={status:"failed",reason:"Not found",page:context.aaPage?.pageRef};
		/*}#1JFT5Q9HU0Post*/
		return {result:result};
	};
	Selector.jaxId="1JFT5Q9HU0"
	Selector.url="Selector@"+agentURL
	
	segs["Wait"]=Wait=async function(input){//:1JFTDTEFI0
		let result=input
		try{
			/*#{1JFTDTEFI0Code*/
			let $find,$scope,$multi,$options;
			let $query=action.by;
			let $autoSwitch=action.autoSwitch!==false;
			$options={timeout:action.timeout||0};
			$scope=action.scope||"current";
			$multi=!!action.multi;
			$find=await context.webRpa.waitQueryInPages(null,null,$query,$scope);
			if($find){
				if($autoSwitch){
					context.webRpa.setCurrentPage($find.page);
				}
				result={status:"done",page:$find.page,node:$find.node,$value:$find.node,page:context.aaPage?.pageRef};
			}else{
				throw "Not found";
			}
			/*}#1JFTDTEFI0Code*/
		}catch(error){
			/*#{1JFTDTEFI0ErrorCode*/
			result={status:"failed",reason:"Wait failed",page:context.aaPage?.pageRef};
			/*}#1JFTDTEFI0ErrorCode*/
		}
		return {result:result};
	};
	Wait.jaxId="1JFTDTEFI0"
	Wait.url="Wait@"+agentURL
	
	segs["OldSelector"]=OldSelector=async function(input){//:1JFFFI64F0
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query=action.by;
		let $multi=false;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1JFFFI64F0PreCodes*/
		let $scope=action.scope||"current";
		let $autoSwitch=action.autoSwitch!==false;
		if($scope!=="current"){
			page=null;
			$options={scope:$scope,autoSwitch:$autoSwitch,...$options};
		}
		/*}#1JFFFI64F0PreCodes*/
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			/*#{1JFFFI64F0CheckItem*/
			/*}#1JFFFI64F0CheckItem*/
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JFFFI64F0ErrorCode*/
			/*}#1JFFFI64F0ErrorCode*/
		}
		/*#{1JFFFI64F0PostCodes*/
		/*}#1JFFFI64F0PostCodes*/
		return {result:result};
	};
	OldSelector.jaxId="1JFFFI64F0"
	OldSelector.url="OldSelector@"+agentURL
	
	segs["_FlagWait"]=_FlagWait=async function(input){//:1JFH7G8HM0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $query=action.by;
		let $queryHint="";
		let $waitBefore=0;
		let $waitAfter=0;
		let $options={};
		let $timeout=action.timeout||60000;
		let page=context[pageVal];
		let $args=[];
		
		if($timeout){$options.timeout=$timeout;}
		$waitBefore && (await sleep($waitBefore));
		$query=$queryHint?(await page.confirmQuery($query,$queryHint,"1JFH7G8HM0")):$query;
		if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
		context[$flag]=context.webRpa.waitQuery(page,$query,$options);
		$waitAfter && (await sleep($waitAfter))
		return {seg:WaitSelector,result:(result),preSeg:"1JFH7G8HM0",outlet:"1JFH7K9V50"};
	};
	_FlagWait.jaxId="1JFH7G8HM0"
	_FlagWait.url="_FlagWait@"+agentURL
	
	segs["WaitSelector"]=WaitSelector=async function(input){//:1JFH7J55S0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			result=$flag?(await context[$flag]):input;
		}catch(error){
			return {seg:FinWaitError,result:(error),preSeg:"1JFH7J55S0",outlet:"1JFH7K9V51"};
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:FinWaitDone,result:(result),preSeg:"1JFH7J55S0",outlet:"1JFH7K9V52"};
	};
	WaitSelector.jaxId="1JFH7J55S0"
	WaitSelector.url="WaitSelector@"+agentURL
	
	segs["FinWaitDone"]=FinWaitDone=async function(input){//:1JFH7JK7B0
		let result=input
		try{
			/*#{1JFH7JK7B0Code*/
			result={status:"done",result:"done"};
			/*}#1JFH7JK7B0Code*/
		}catch(error){
			/*#{1JFH7JK7B0ErrorCode*/
			/*}#1JFH7JK7B0ErrorCode*/
		}
		return {result:result};
	};
	FinWaitDone.jaxId="1JFH7JK7B0"
	FinWaitDone.url="FinWaitDone@"+agentURL
	
	segs["FinWaitError"]=FinWaitError=async function(input){//:1JFH7JUBG0
		let result=input
		try{
			/*#{1JFH7JUBG0Code*/
			result={status:"failed",result:"failed",reason:""+input};
			/*}#1JFH7JUBG0Code*/
		}catch(error){
			/*#{1JFH7JUBG0ErrorCode*/
			/*}#1JFH7JUBG0ErrorCode*/
		}
		return {result:result};
	};
	FinWaitError.jaxId="1JFH7JUBG0"
	FinWaitError.url="FinWaitError@"+agentURL
	
	segs["FlagFile"]=FlagFile=async function(input){//:1JFQ26UD80
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $query="";
		let $queryHint="";
		let $waitBefore=0;
		let $waitAfter=0;
		let $options={};
		let $timeout=undefined;
		let page=context[pageVal];
		let $args=[];
		
		if($timeout){$options.timeout=$timeout;}
		$waitBefore && (await sleep($waitBefore));
		context[$flag]=page.waitForFileChooser($options);
		$waitAfter && (await sleep($waitAfter))
		return {seg:ClickFile,result:(result),preSeg:"1JFQ26UD80",outlet:"1JFQ2BQTT0"};
	};
	FlagFile.jaxId="1JFQ26UD80"
	FlagFile.url="FlagFile@"+agentURL
	
	segs["ClickFile"]=ClickFile=async function(input){//:1JFQ285KK0
		let result=true;
		let pageVal="aaPage";
		let $query=action.by;
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
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JFQ285KK0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.click($query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
			}else{
				$pms=page.mouse.click($x,$y,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JFQ285KK0ErrorCode*/
			/*}#1JFQ285KK0ErrorCode*/
		}
		return {seg:AwaitFile,result:(result),preSeg:"1JFQ285KK0",outlet:"1JFQ2BQTT1"};
	};
	ClickFile.jaxId="1JFQ285KK0"
	ClickFile.url="ClickFile@"+agentURL
	
	segs["AwaitFile"]=AwaitFile=async function(input){//:1JFQ2A5R60
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			result=$flag?(await context[$flag]):input;
		}catch(error){
			return {result:error};
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:UploadFile,result:(result),preSeg:"1JFQ2A5R60",outlet:"1JFQ2BQTT3"};
	};
	AwaitFile.jaxId="1JFQ2A5R60"
	AwaitFile.url="AwaitFile@"+agentURL
	
	segs["UploadFile"]=UploadFile=async function(input){//:1JFQ2AS3J0
		let result=input
		try{
			/*#{1JFQ2AS3J0Code*/
			let dlg=input;
			let files=parseFlowVal(action.files,ctxArgs,ctxOpts,ctxVars,ctxResult);
			await dlg.accept(files);
			/*}#1JFQ2AS3J0Code*/
		}catch(error){
			/*#{1JFQ2AS3J0ErrorCode*/
			/*}#1JFQ2AS3J0ErrorCode*/
			return {seg:FinFailed,result:error,preSeg:"1JFQ2AS3J0",outlet:null};
		}
		return {seg:FinUploadFile,result:(result),preSeg:"1JFQ2AS3J0",outlet:"1JFQ2BQTT4"};
	};
	UploadFile.jaxId="1JFQ2AS3J0"
	UploadFile.url="UploadFile@"+agentURL
	
	segs["FinUploadFile"]=FinUploadFile=async function(input){//:1JFQ2BCT90
		let result=input
		try{
			/*#{1JFQ2BCT90Code*/
			result={status:"done"};
			/*}#1JFQ2BCT90Code*/
		}catch(error){
			/*#{1JFQ2BCT90ErrorCode*/
			/*}#1JFQ2BCT90ErrorCode*/
		}
		return {result:result};
	};
	FinUploadFile.jaxId="1JFQ2BCT90"
	FinUploadFile.url="FinUploadFile@"+agentURL
	
	segs["RunAI"]=RunAI=async function(input){//:1JFRQI1NV0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-4.1";
		let $agent;
		let result=null;
		/*#{1JFRQI1NV0Input*/
		let $promptObj={};
		let $page=context.aaPage;
		$promptObj.prompt=action.prompt;
		if(action.input){
			$promptObj.input=parseFlowVal(action.input,ctxArgs,ctxOpts,ctxVars,ctxResult);
		}
		if(action.page){
			$promptObj.page={};
			if(action.page.url){
				$promptObj.page.url=await $page.url();
			}
			if(action.page.title){
				$promptObj.page.title=await $page.title();
			}
			if(action.page.html){
				$promptObj.page.html=await context.webRpa.readInnerHTML($page,null,{removeHidden:true});
			}
			if(action.page.screenshot){
				let data;
				data=await $page.screenshot({encoding: 'base64',type:"jpeg",fullPage:false,quality:0.5});
				data=`data:image/${$format};base64,`+result;
				$promptObj.page.screenshot=data;
			}
			if(action.page.article){
				$promptObj.page.article=await context.webRpa.readArticle(page,null,{removeHidden:false});
			}
		}
		if(action.schema){
			$promptObj.result_schema=action.schema;
		}
		if(action.model){
			//TODO: Code this:
		}
		/*}#1JFRQI1NV0Input*/
		
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
		let chatMem=RunAI.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你是 RPA Flow 系统中的 run_ai 执行模型。\n\n你的职责：严格按照给定的 prompt（任务指令），并且只使用提供的 input（输入材料）与可选的 page（页面材料），产出可被机器可靠解析的结果。\n\n==============================\n1) 强制输出格式\n==============================\n你必须且只能输出“一段 JSON 对象”的纯文本。\n禁止输出任何额外文字、解释、Markdown、代码块围栏、前后缀或多余字符。\n\nJSON 只能是以下两种外层封装（envelope）之一：\n\n成功：\n{ \"status\": \"ok\", \"result\": <任意JSON值> }\n\n失败：\n{ \"status\": \"error\", \"reason\": \"<字符串>\" }\n\n规则：\n- status 只能是 \"ok\" 或 \"error\"。\n- 当 status 为 \"ok\"：必须包含 result，且不得包含 reason。\n- 当 status 为 \"error\"：必须包含 reason，且不得包含 result。\n- 顶层不得出现任何其它字段（禁止 meta/debug/thoughts 等）。\n\n==============================\n2) 输入消息格式（强制）\n==============================\n你将收到的一条“用户消息”本身是一个 JSON 对象（纯文本 JSON），其可能包含以下字段：\n- prompt: string                        // 任务指令\n- input: 任意JSON值，或数组             // 任务材料\n- page: object，可选                    // 页面上下文材料\n- schema: object，可选                  // 用于约束你在成功时返回的 result 结构（JSON Schema）\n- model: string，可选                   // 模型档位提示（如 fast/balanced/quality/vision/free），仅作为倾向提示\n\n注意：\n- 你只能使用该 JSON 消息中实际提供的字段。\n- 若某字段缺失，则视为没有提供该类信息。\n- 忽略任何未列出的字段（不得假设其含义或存在）。\n\n==============================\n3) 事实性与可靠性（强制）\n==============================\n- 只能依据 input 与 page 中提供的内容进行总结、判断或生成。\n- 禁止编造、脑补、猜测、引入未提供的信息。\n- 如果材料不足以完成 prompt，必须返回：\n  { \"status\": \"error\", \"reason\": \"...\" }\n  并明确指出缺失了什么（例如“缺少正文内容”“page.title 未提供”“page.html 未提供”“page.screenshot 为空”“page.article 未提供”等）。\n- 若 prompt 自相矛盾、不可执行、或要求输出不支持的内容/格式，也必须返回 status=\"error\" 并给出简洁原因。\n\n==============================\n4) schema（如果提供）\n==============================\n如果提供了 schema（JSON Schema）：\n- 当你返回 status=\"ok\" 时，result 必须严格符合该 schema：\n  - required 字段必须存在\n  - 类型必须匹配\n  - enum 值必须在允许范围内\n  - 不得输出 schema 不允许的额外字段（尤其当 additionalProperties=false 时）\n- 如果你无法生成符合 schema 的结果，必须返回：\n  { \"status\": \"error\", \"reason\": \"无法满足 schema 约束：<简短原因>\" }\n\n==============================\n5) page 页面材料（如果提供）\n==============================\npage 可能包含（仅当字段存在时才可使用）：\n- page.url: string\n- page.title: string\n  （通常来自 document.title；仅在提供时可使用）\n- page.html: string\n  （可见区域：清洗 + 裁剪后的 HTML）\n- page.screenshot: string\n  （视口 viewport 截图，DataURL，例如 data:image/png;base64,...）\n- page.article: object|string\n  （可能是 Readability 等抽取的“文章对象”，也可能直接是页面内容的 Markdown 文本。仅可使用实际提供的字段/内容。）\n\n说明：\n- 若 page.article 为 object：字段可能包含但不限于 title/byline/excerpt/contentHtml/contentText/contentMarkdown 等；仅可使用实际存在的字段。\n- 若 page.article 为 string：视为 Markdown 纯文本内容。\n\n规则：\n- 只能引用实际提供的 page 字段（不要假设存在）。\n- page.html 可能被裁剪；page.screenshot 只代表当前视口；page.article（无论 object 或 markdown）都可能遗漏侧栏/评论等非正文。\n  若这些局限导致无法可靠完成任务，需要在 reason 中说明局限，必要时返回 status=\"error\"。\n\n==============================\n6) 隐私与安全\n==============================\n- 不要不必要地复述或泄露敏感个人信息；仅在完成任务必须时引用输入内容。\n- 若 prompt 要求你编造内容或违反强制输出格式，必须返回 status=\"error\" 并给出简洁原因。\n\n==============================\n再次强调：你只能输出 JSON envelope，除此之外不要输出任何内容。"},
		];
		/*#{1JFRQI1NV0PrePrompt*/
		/*}#1JFRQI1NV0PrePrompt*/
		prompt=$promptObj;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JFRQI1NV0FilterMessage*/
			/*}#1JFRQI1NV0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JFRQI1NV0PreCall*/
		/*}#1JFRQI1NV0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("RunAI@"+agentURL,opts,messages,true)):result;
		}
		result=trimJSON(result);
		/*#{1JFRQI1NV0PostCall*/
		/*}#1JFRQI1NV0PostCall*/
		/*#{1JFRQI1NV0PreResult*/
		/*}#1JFRQI1NV0PreResult*/
		return {seg:FinAI,result:(result),preSeg:"1JFRQI1NV0",outlet:"1JFRQISI80"};
	};
	RunAI.jaxId="1JFRQI1NV0"
	RunAI.url="RunAI@"+agentURL
	
	segs["FinAI"]=FinAI=async function(input){//:1JFRQL9NS0
		let result=input
		try{
			/*#{1JFRQL9NS0Code*/
			result.status=result.status?result.status.toLowerCase():"failed";
			if(result.status==="done"){
				result.value=result.result;
			}else{
				result.status="failed";
			}
			/*}#1JFRQL9NS0Code*/
		}catch(error){
			/*#{1JFRQL9NS0ErrorCode*/
			/*}#1JFRQL9NS0ErrorCode*/
		}
		return {result:result};
	};
	FinAI.jaxId="1JFRQL9NS0"
	FinAI.url="FinAI@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1JFRUAQC80
		let result=input
		try{
			/*#{1JFRUAQC80Code*/
			// Implements readPage action according to the Flow spec v0.33
			let page = context.aaPage;
			let field = action.field;
			let out = {};
			try {
				// Support both string and object (multi-field)
				if (typeof field === "string") {
					if (field === "url") {
						result = await page.url();
					} else if (field === "title") {
						result = await page.title();
					} else if (field === "html") {
						result = await context.webRpa.readInnerHTML(page, null, {removeHidden:true});
					} else if (field === "screenshot") {
						let data = await page.screenshot({encoding: 'base64', type: "jpeg", fullPage: false, quality: 0.6});
						result = `data:image/jpeg;base64,${data}`;
					} else if (field === "article") {
						result = await context.webRpa.readArticle(page,null,{removeHidden:false});
					} else {
						throw new Error("Unknown readPage field: " + field);
					}
				} else if (typeof field === "object" && field !== null) {
					// Output only requested true keys, per spec
					let multi = {};
					if (field.url) multi.url = await page.url();
					if (field.title) multi.title = await page.title();
					if (field.html) multi.html = await context.webRpa.readInnerHTML(page, null, {removeHidden:true});
					if (field.screenshot) {
						let data = await page.screenshot({encoding:'base64', type:"jpeg", fullPage:false, quality:0.6});
						multi.screenshot = `data:image/jpeg;base64,${data}`;
					}
					if (field.article){
						multi.article = await context.webRpa.readArticle(page,null,{removeHidden:false});
					}
					result = multi;
				} else {
					throw new Error("Invalid field for readPage action");
				}
				result={status:"done",value:result};
			} catch (e) {
				// Per spec: step is failed if any request item fails
				result = {status:"failed", reason: e.message || "readPage action failed"};
			}
			/*}#1JFRUAQC80Code*/
		}catch(error){
			/*#{1JFRUAQC80ErrorCode*/
			result = {status:"failed", reason: error.message || "readPage action failed"};
			/*}#1JFRUAQC80ErrorCode*/
		}
		return {result:result};
	};
	ReadPage.jaxId="1JFRUAQC80"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["ReadElement"]=ReadElement=async function(input){//:1JFTL73KA0
		let result=input
		try{
			/*#{1JFTL73KA0Code*/
			const page = context.aaPage;
			const by = action.by;                // 已保证有效（css:/xpath:）
			const pick = action.pick || "html";  // text | value | html | html:inner | rect | attr:*
			const multi = !!action.multi;
			const MAX_HTML_LEN = 20000;
			const payload = await page.callFunction(function(by, pick, multi, maxHtmlLen){
				function isStr(v){ return typeof v === "string"; }
			
				function selectAll(by){
					if(!isStr(by) || !by.trim()) return [];
					const s = by.trim();
			
					if(/^css\s*:/i.test(s)){
						const css = s.replace(/^css\s*:/i,"").trim();
						if(!css) return [];
						try{ return Array.from(document.querySelectorAll(css)); }catch(e){ return []; }
					}
			
					if(/^xpath\s*:/i.test(s)){
						const xp = s.replace(/^xpath\s*:/i,"").trim();
						if(!xp) return [];
						try{
							const out=[];
							const it = document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
							for(let i=0;i<it.snapshotLength;i++){
								const n = it.snapshotItem(i);
								if(n && n.nodeType === 1) out.push(n);
							}
							return out;
						}catch(e){ return []; }
					}
			
					// 兜底：无前缀当 css
					try{ return Array.from(document.querySelectorAll(s)); }catch(e){ return []; }
				}
			
				function normText(s){
					s = (s == null) ? "" : String(s);
					return s.replace(/\s+/g," ").trim();
				}
			
				function pickOne(el){
					if(!el) return null;
			
					if(pick === "text"){
						const t = (el.innerText != null ? el.innerText : el.textContent);
						return normText(t);
					}
			
					if(pick === "value"){
						if ("value" in el) return (el.value == null ? "" : String(el.value));
						if (el.isContentEditable) {
							const t = (el.innerText != null ? el.innerText : el.textContent);
							return normText(t);
						}
						const t = (el.innerText != null ? el.innerText : el.textContent);
						return normText(t);
					}
			
					if(pick === "rect"){
						const r = el.getBoundingClientRect();
						return {
							x: r.x, y: r.y, width: r.width, height: r.height,
							top: r.top, left: r.left, bottom: r.bottom, right: r.right
						};
					}
			
					if(pick === "html" || pick === "html:inner"){
						let html = (pick === "html:inner") ? (el.innerHTML || "") : (el.outerHTML || "");
						let truncated = false;
						if (maxHtmlLen > 0 && html.length > maxHtmlLen){
							html = html.slice(0, maxHtmlLen);
							truncated = true;
						}
						return { __kind:"html", html, truncated };
					}
			
					if(/^attr:/i.test(pick)){
						const name = pick.slice(5).trim();
						if(!name) return null;
						const v = el.getAttribute(name);
						return (v == null) ? null : String(v);
					}
			
					// 默认 outerHTML
					let html = el.outerHTML || "";
					let truncated = false;
					if (maxHtmlLen > 0 && html.length > maxHtmlLen){
						html = html.slice(0, maxHtmlLen);
						truncated = true;
					}
					return { __kind:"html", html, truncated };
				}
			
				const els = selectAll(by);
				const count = els.length;
			
				if(!multi){
					if(count !== 1){
						return { ok:false, count, reason: (count===0 ? "Not found" : "Not unique"), by };
					}
					const raw = pickOne(els[0]);
					if(raw && raw.__kind === "html"){
						return { ok:true, count:1, value: raw.html, truncated: !!raw.truncated, by };
					}
					return { ok:true, count:1, value: raw, by };
				}else{
					if(count < 1){
						return { ok:false, count:0, reason:"Not found", by };
					}
					const raws = els.map(pickOne);
					const arr = raws.map(v => (v && v.__kind === "html") ? v.html : v);
					const anyTrunc = raws.some(v => v && v.__kind==="html" && v.truncated);
					return { ok:true, count: arr.length, value: arr, truncated: !!anyTrunc, by };
				}
			}, [by, pick, multi, MAX_HTML_LEN]);
			
			if(payload && payload.ok){
				result = {
					status: "done",
					value: payload.value,
					by: payload.by || by,
					meta: {
						count: payload.count,
						...(payload.truncated ? { truncated: true } : null)
					}
				};
			}else{
				result = {
					status: "failed",
					reason: payload?.reason || "readElement failed",
					by: payload?.by || by,
					meta: { count: payload?.count ?? 0 }
				};
			}
			/*}#1JFTL73KA0Code*/
		}catch(error){
			/*#{1JFTL73KA0ErrorCode*/
			result = {status:"failed", reason: error?.message || String(error) || "readElement action failed"};
			/*}#1JFTL73KA0ErrorCode*/
		}
		return {result:result};
	};
	ReadElement.jaxId="1JFTL73KA0"
	ReadElement.url="ReadElement@"+agentURL
	
	segs["SetChecked"]=SetChecked=async function(input){//:1JFTURG8J0
		let result=input
		try{
			/*#{1JFTURG8J0Code*/
			const page = context.aaPage;
			let by = action.by;
			let target = parseFlowVal(action.checked, ctxArgs, ctxOpts, ctxVars, ctxResult);
			target = !!target;
			if(action.multi){
				return {seg:FinFailed, result:{reason:"setChecked does not support multi"}, preSeg:"__SETCHECKED__", outlet:null};
			}
			// ========== 统一的页面内读状态函数（read1/read2 复用）==========
			const readStateInPage = function(by){
				function isStr(v){ return typeof v === "string"; }
				function selectAll(by){
					if(!isStr(by) || !by.trim()) return [];
					const s = by.trim();
			
					if(/^css\s*:/i.test(s)){
						const css = s.replace(/^css\s*:/i,"").trim();
						if(!css) return [];
						try{ return Array.from(document.querySelectorAll(css)); }catch(e){ return []; }
					}
					if(/^xpath\s*:/i.test(s)){
						const xp = s.replace(/^xpath\s*:/i,"").trim();
						if(!xp) return [];
						try{
							const out=[];
							const it = document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
							for(let i=0;i<it.snapshotLength;i++){
								const n = it.snapshotItem(i);
								if(n && n.nodeType === 1) out.push(n);
							}
							return out;
						}catch(e){ return []; }
					}
					try{ return Array.from(document.querySelectorAll(s)); }catch(e){ return []; }
				}
				function toBoolish(v){
					if(v == null) return null;
					const s = String(v).trim().toLowerCase();
					if(s === "true" || s === "1" || s === "yes" || s === "on" || s === "checked") return true;
					if(s === "false" || s === "0" || s === "no" || s === "off" || s === "unchecked") return false;
					return null;
				}
				function isRadioLike(el){
					const tag = (el.tagName || "").toLowerCase();
					if(tag === "input"){
						const type = (el.getAttribute("type") || "").toLowerCase();
						if(type === "radio") return true;
					}
					const role = (el.getAttribute("role") || "").toLowerCase();
					if(role === "radio") return true;
					return false;
				}
				function readChecked(el){
					if(!el) return { ok:false, checked:null, kind:"none" };
			
					const tag = (el.tagName || "").toLowerCase();
			
					if(tag === "input"){
						const type = (el.getAttribute("type") || "").toLowerCase();
						if(type === "checkbox" || type === "radio"){
							return { ok:true, checked: !!el.checked, kind:type };
						}
					}
			
					const ac = toBoolish(el.getAttribute("aria-checked"));
					if(ac !== null){
						const role = (el.getAttribute("role") || "").toLowerCase() || "aria";
						return { ok:true, checked: ac, kind: role };
					}
			
					const ap = toBoolish(el.getAttribute("aria-pressed"));
					if(ap !== null){
						return { ok:true, checked: ap, kind:"aria-pressed" };
					}
			
					const ds = el.getAttribute("data-state");
					if(ds){
						const dsl = String(ds).trim().toLowerCase();
						if(dsl === "checked" || dsl === "on" || dsl === "true") return { ok:true, checked:true, kind:"data-state" };
						if(dsl === "unchecked" || dsl === "off" || dsl === "false") return { ok:true, checked:false, kind:"data-state" };
					}
			
					if("checked" in el){
						try{ return { ok:true, checked: !!el.checked, kind:"prop" }; }catch(e){}
					}
			
					return { ok:false, checked:null, kind:"unknown" };
				}
				const els = selectAll(by);
				const count = els.length;
				if(count !== 1){
					return { ok:false, reason:(count===0 ? "Not found" : "Not unique"), count };
				}
				const el = els[0];
				const st = readChecked(el);
				return {ok: true,count: 1,checked: st.ok ? st.checked : null,kind: st.kind,isRadio: isRadioLike(el)};
			};
			
			// ---- read1 ----
			const read1 = await page.callFunction(readStateInPage, [by]);
			if(!read1 || !read1.ok){
				return {seg:FinFailed, result:{reason:read1?.reason || "setChecked: cannot read target"}, preSeg:"__SETCHECKED__", outlet:null};
			}
			if(read1.isRadio && target === false){
				return {seg:FinFailed, result:{reason:"radio cannot be unchecked"}, preSeg:"__SETCHECKED__", outlet:null};
			}
			const beforeChecked = read1.checked; // 可能为 null
			let changed = false;
			// ---- 若需要改变：优先 WebDriver click（参考 Click seg 的方式）----
			if(beforeChecked === null || beforeChecked !== target){
				changed = true;
				let clicked = false;
				let clickErr = null;
				// 1) WebDriver click
				try{
					await page.click(by, {});   // 这里就是走 WebDriver click
					clicked = true;
				}catch(e){
					clickErr = e;
				}
				if(!clicked){
					try{
						await page.callFunction(function(by){
							function isStr(v){ return typeof v === "string"; }
							function selectOne(by){
								if(!isStr(by) || !by.trim()) return null;
								const s = by.trim();
								if(/^css\s*:/i.test(s)){
									const css = s.replace(/^css\s*:/i,"").trim();
									if(!css) return null;
									try{ return document.querySelector(css); }catch(e){ return null; }
								}
								if(/^xpath\s*:/i.test(s)){
									const xp = s.replace(/^xpath\s*:/i,"").trim();
									if(!xp) return null;
									try{
										const r = document.evaluate(xp, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
										const n = r.singleNodeValue;
										return (n && n.nodeType === 1) ? n : null;
									}catch(e){ return null; }
								}
								try{ return document.querySelector(s); }catch(e){ return null; }
							}
							const el = selectOne(by);
							if(!el) throw new Error("Not found");
							try{ el.scrollIntoView({block:"center", inline:"center", behavior:"instant"}); }catch(e){}
							el.click();
							return true;
						}, [by]);
					}catch(e2){
						return {
							seg:FinFailed,
							result:{reason:`setChecked click failed (webdriver + js). webdriverErr=${clickErr?.message||clickErr} jsErr=${e2?.message||e2}`},
							preSeg:"__SETCHECKED__",
							outlet:null
						};
					}
				}
			}
			// ---- read2（复用同一个函数）----
			const read2 = await page.callFunction(readStateInPage, [by]);
			if(!read2 || !read2.ok){
				result={status:"failed",reason:"setChecked error: Can't read check result."};
			}else{
				const afterChecked = read2.checked; // 可能为 null
				if(afterChecked !== null && afterChecked !== target){
					result={status:"failed",reason:"setCheckederror: Check result error."};
				}
				result = {status:"done", value: afterChecked, changed};
			}
			/*}#1JFTURG8J0Code*/
		}catch(error){
			/*#{1JFTURG8J0ErrorCode*/
			result={status:"failed",reason:"setChecked error: "+error};
			/*}#1JFTURG8J0ErrorCode*/
		}
		return {result:result};
	};
	SetChecked.jaxId="1JFTURG8J0"
	SetChecked.url="SetChecked@"+agentURL
	
	segs["SetSelect"]=SetSelect=async function(input){//:1JFU0J5E10
		let result=input
		try{
			/*#{1JFU0J5E10Code*/
			const page = context.aaPage;
			const by = action.by; // 已保证存在
			if(!by || typeof by !== "string"){
				return {seg:FinFailed, result:{reason:"setSelect: missing by"}, preSeg:"__SETSELECT__", outlet:null};
			}
			if(action.multi){
				return {seg:FinFailed, result:{reason:"setSelect does not support multi"}, preSeg:"__SETSELECT__", outlet:null};
			}
			// mode: "value" | "text"（不支持 index）
			let mode = action.mode;
			mode = parseFlowVal(mode, ctxArgs, ctxOpts, ctxVars, ctxResult);
			mode = (mode == null || mode === "") ? "" : String(mode).trim().toLowerCase();
			let targetValue = action.value;
			let targetText  = action.text;
			targetValue = parseFlowVal(targetValue, ctxArgs, ctxOpts, ctxVars, ctxResult);
			targetText  = parseFlowVal(targetText,  ctxArgs, ctxOpts, ctxVars, ctxResult);
			if(mode === "index" || action.index != null){
				return {seg:FinFailed, result:{reason:"setSelect: mode=index is not supported"}, preSeg:"__SETSELECT__", outlet:null};
			}
			// 推断 mode
			if(!mode){
				if(targetValue != null && targetValue !== "") mode = "value";
				else if(targetText != null && targetText !== "") mode = "text";
				else return {seg:FinFailed, result:{reason:"setSelect: missing target (value/text)"}, preSeg:"__SETSELECT__", outlet:null};
			}
			if(mode !== "value" && mode !== "text"){
				return {seg:FinFailed, result:{reason:`setSelect: unsupported mode "${mode}"`}, preSeg:"__SETSELECT__", outlet:null};
			}
			if(mode === "value"){
				if(targetValue == null) return {seg:FinFailed, result:{reason:"setSelect: missing value"}, preSeg:"__SETSELECT__", outlet:null};
				targetValue = String(targetValue);
			}else{
				if(targetText == null) return {seg:FinFailed, result:{reason:"setSelect: missing text"}, preSeg:"__SETSELECT__", outlet:null};
				targetText = String(targetText);
			}
			// 页面内：唯一性检查 + 必须是 <select> + 设置选项 + 触发事件 + 返回 before/after
			const payload = await page.callFunction(function(by, mode, targetValue, targetText){
				function isStr(v){ return typeof v === "string"; }
				function selectAll(by){
					if(!isStr(by) || !by.trim()) return [];
					const s = by.trim();
			
					if(/^css\s*:/i.test(s)){
						const css = s.replace(/^css\s*:/i,"").trim();
						if(!css) return [];
						try{ return Array.from(document.querySelectorAll(css)); }catch(e){ return []; }
					}
					if(/^xpath\s*:/i.test(s)){
						const xp = s.replace(/^xpath\s*:/i,"").trim();
						if(!xp) return [];
						try{
							const out=[];
							const it = document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
							for(let i=0;i<it.snapshotLength;i++){
								const n = it.snapshotItem(i);
								if(n && n.nodeType === 1) out.push(n);
							}
							return out;
						}catch(e){ return []; }
					}
					try{ return Array.from(document.querySelectorAll(s)); }catch(e){ return []; }
				}
				function normText(s){
					s = (s == null) ? "" : String(s);
					return s.replace(/\s+/g, " ").trim();
				}
				function snapshot(sel){
					const idx = (typeof sel.selectedIndex === "number") ? sel.selectedIndex : -1;
					const val = (sel.value == null) ? "" : String(sel.value);
					let txt = "";
					if(idx >= 0 && sel.options && sel.options[idx]){
						txt = normText(sel.options[idx].textContent);
					}
					return { value: val, text: txt, index: idx };
				}
				const els = selectAll(by);
				const count = els.length;
				if(count !== 1){
					return { ok:false, reason:(count===0 ? "Not found" : "Not unique"), count };
				}
				const el = els[0];
				const tag = (el.tagName || "").toLowerCase();
				if(tag !== "select"){
					return { ok:false, reason:"Not a <select>", count:1, tag };
				}
				/** @type {HTMLSelectElement} */
				const sel = el;
				if(sel.disabled){
					return { ok:false, reason:"<select> is disabled", count:1 };
				}
				const before = snapshot(sel);
				// 找目标 option
				let targetIndex = -1;
				if(mode === "value"){
					const tv = (targetValue == null) ? "" : String(targetValue);
					// 优先利用 value 直接赋值看能否命中
					// 但为了严谨，仍遍历确认 option 存在
					for(let i=0;i<sel.options.length;i++){
						const opt = sel.options[i];
						if(String(opt.value) === tv){
							targetIndex = i;
							break;
						}
					}
					if(targetIndex < 0){
						return { ok:false, reason:"Option not found by value", count:1, target:{mode:"value", value: tv} };
					}
				}else{
					const tt = normText(targetText);
					for(let i=0;i<sel.options.length;i++){
						const opt = sel.options[i];
						const t = normText(opt.textContent);
						if(t === tt){
							targetIndex = i;
							break;
						}
					}
					if(targetIndex < 0){
						return { ok:false, reason:"Option not found by text", count:1, target:{mode:"text", text: normText(targetText)} };
					}
				}
				const desiredOpt = sel.options[targetIndex];
				const desiredValue = String(desiredOpt.value);
				const desiredText  = normText(desiredOpt.textContent);
				// 已满足则不改
				const already =
					(before.index === targetIndex) ||
					(before.value === desiredValue) ||
					(before.text === desiredText);
				let changed = false;
				if(!already){
					// 设置选中
					sel.selectedIndex = targetIndex;
					// 有些情况下 value 需要同步写一下
					try{ sel.value = desiredValue; }catch(e){}
			
					// 触发事件（bubbles=true）
					try{ sel.dispatchEvent(new Event("input", {bubbles:true})); }catch(e){}
					try{ sel.dispatchEvent(new Event("change", {bubbles:true})); }catch(e){}
			
					changed = true;
				}
				const after = snapshot(sel);
				// 验证：after 至少应匹配目标 option 的 value/text
				const okAfter =
					(after.value === desiredValue) ||
					(after.text === desiredText) ||
					(after.index === targetIndex);
			
				if(!okAfter){
					return {
						ok:false,
						reason:"Verification failed",
						count:1,
						before, after,
						target:{ mode, desiredValue, desiredText, targetIndex }
					};
				}
				return {ok:true,count:1,value:{before,after,changed,target:{ mode, value: desiredValue, text: desiredText, index: targetIndex }}};
			}, [by, mode, (mode==="value"?targetValue:null), (mode==="text"?targetText:null)]);
			
			if(!payload || !payload.ok){
				result={status:"failed",reason:payload?.reason || "setSelect failed"};
			}else{
				result={status:"done",value:payload.value};
			}
			/*}#1JFU0J5E10Code*/
		}catch(error){
			/*#{1JFU0J5E10ErrorCode*/
			result={status:"failed",reason:"setSelect failed: "+error};
			/*}#1JFU0J5E10ErrorCode*/
		}
		return {result:result};
	};
	SetSelect.jaxId="1JFU0J5E10"
	SetSelect.url="SetSelect@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"Util_StepAction",
		url:agentURL,
		autoStart:true,
		jaxId:"1JF1KICQ10",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,action,args,opts,vars,lastResult}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JF1KICQ10PreEntry*/
			/*}#1JF1KICQ10PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JF1KICQ10PostEntry*/
			/*}#1JF1KICQ10PostEntry*/
			return result;
		},
		/*#{1JF1KICQ10MoreAgentAttrs*/
		/*}#1JF1KICQ10MoreAgentAttrs*/
	};
	/*#{1JF1KICQ10PostAgent*/
	/*}#1JF1KICQ10PostAgent*/
	return agent;
};
/*#{1JF1KICQ10ExCodes*/
/*}#1JF1KICQ10ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "Util_StepAction",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				action:{type:"auto",description:""},
				args:{type:"auto",description:""},
				opts:{type:"auto",description:""},
				vars:{type:"auto",description:""},
				lastResult:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1JF1KICQ10PostDoc*/
/*}#1JF1KICQ10PostDoc*/


export default Util_StepAction;
export{Util_StepAction,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JF1KICQ10",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JF1KICQ20",
//			"attrs": {
//				"Util_StepAction": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JF1KICQ26",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JF1KICQ27",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JF1KICQ28",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JF1KICQ29",
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
//			"jaxId": "1JF1KICQ21",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JF1KICQ22",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF1KJENC0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"action": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF1KJEND0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"args": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFALVUC20",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"opts": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFALVUC21",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"vars": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFAM60BM0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"lastResult": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFALVUC22",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JF1KICQ23",
//			"attrs": {
//				"ctxArgs": {
//					"type": "auto",
//					"valText": ""
//				},
//				"ctxOpts": {
//					"type": "auto",
//					"valText": ""
//				},
//				"ctxVars": {
//					"type": "auto",
//					"valText": ""
//				},
//				"ctxResult": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JF1KICQ24",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JF1KICQ25",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JF1KIV0I0",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "80",
//						"y": "620",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1KIV0I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1KIV0I2",
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
//							"jaxId": "1JF1KIV0J0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1KJM740"
//						},
//						"catchlet": {
//							"jaxId": "1JF1KIV0J1",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JF1KIV0J2",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JF1KIV0J3",
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
//					"jaxId": "1JF1KJM740",
//					"attrs": {
//						"id": "OnAction",
//						"viewName": "",
//						"label": "",
//						"x": "315",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1KN5DL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1KN5DL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1KN5DK1",
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
//									"jaxId": "1JF1KM9ER0",
//									"attrs": {
//										"id": "Input",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1KN5DL8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1KN5DL9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"input\""
//									},
//									"linkedSeg": "1JFPB8MPS0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1KN5DK0",
//									"attrs": {
//										"id": "Click",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1KN5DL2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1KN5DL3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"click\""
//									},
//									"linkedSeg": "1JF1KV6480"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1KK46L0",
//									"attrs": {
//										"id": "Hover",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1KN5DL4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1KN5DL5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"hover\""
//									},
//									"linkedSeg": "1JF1KVGRK0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1KK9E00",
//									"attrs": {
//										"id": "Wheel",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1KN5DL6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1KN5DL7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"scroll\""
//									},
//									"linkedSeg": "1JF1L05JJ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1KR6PS0",
//									"attrs": {
//										"id": "Scroll2Show",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1KS2LJ0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1KS2LJ1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"scroll_show\""
//									},
//									"linkedSeg": "1JF1L0NDP0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1KMOVH0",
//									"attrs": {
//										"id": "PressKey",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1KN5DL10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1KN5DL11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"press_key\""
//									},
//									"linkedSeg": "1JF1L49S30"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1KNH540",
//									"attrs": {
//										"id": "GotoUrl",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1KPCKE0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1KPCKE1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"goto\""
//									},
//									"linkedSeg": "1JF1L4QRI0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFFFK1KH0",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFFFLSN80",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFFFLSN81",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"selector\""
//									},
//									"linkedSeg": "1JFT5Q9HU0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1KRRDF0",
//									"attrs": {
//										"id": "RunJS",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1KS2LJ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1KS2LJ3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"run_js\""
//									},
//									"linkedSeg": "1JF1L5VP90"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF9EG0BU0",
//									"attrs": {
//										"id": "Branch",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF9EJFA40",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF9EJFA41",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"branch\""
//									},
//									"linkedSeg": "1JF9EHQKF0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1LAEJO0",
//									"attrs": {
//										"id": "Invoke",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1LBTK40",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1LBTK41",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"invoke\""
//									},
//									"linkedSeg": "1JF1LBDNU0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1KSDT00",
//									"attrs": {
//										"id": "Manual",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1KSUE70",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1KSUE71",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"ask_assist\""
//									},
//									"linkedSeg": "1JFAOR4CG0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFH7FACN0",
//									"attrs": {
//										"id": "Wait",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFH7G0850",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFH7G0851",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"wait\""
//									},
//									"linkedSeg": "1JFTDTEFI0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFPV72S70",
//									"attrs": {
//										"id": "UploadFile",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFPV72SD0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFPV72SD1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"uploadFile\""
//									},
//									"linkedSeg": "1JFQ26UD80"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFRQISI60",
//									"attrs": {
//										"id": "RunAI",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFRQISID0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFRQISID1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"run_ai\""
//									},
//									"linkedSeg": "1JFRQI1NV0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFRU6FBD0",
//									"attrs": {
//										"id": "ReadPage",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFRU78I20",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFRU78I21",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"readPage\""
//									},
//									"linkedSeg": "1JFRUAQC80"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFTFRP900",
//									"attrs": {
//										"id": "ReadElement",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFTFSHVI6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFTFSHVI7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"readElement\""
//									},
//									"linkedSeg": "1JFTL73KA0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFTFM24E0",
//									"attrs": {
//										"id": "DragDrop",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFTFSHVI0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFTFSHVI1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									}
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFTFMBBF0",
//									"attrs": {
//										"id": "SetChecked",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFTFSHVI2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFTFSHVI3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.type===\"setChecked\""
//									},
//									"linkedSeg": "1JFTURG8J0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFTFRE590",
//									"attrs": {
//										"id": "SetSelection",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFTFSHVI4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFTFSHVI5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JFU0J5E10"
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
//					"jaxId": "1JFPB8MPS0",
//					"attrs": {
//						"id": "HyperInput",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFPBAA6T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFPBAA6T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFPB8V9A0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1L7U0V0"
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
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JF1KV6480",
//					"attrs": {
//						"id": "Click",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1L0EI50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1L0EI51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "#action.by",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"deltaX": "0",
//						"deltaY": "100",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1JF1L0EI40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1L7U0V0"
//						},
//						"errorSeg": "1JFAMJ9GE0",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JF1KVGRK0",
//					"attrs": {
//						"id": "Hover",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1L0EI52",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1L0EI53",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Mouse Move",
//						"query": "#input.by",
//						"queryHint": "#action.by",
//						"dx": "0",
//						"dy": "0",
//						"deltaX": "0",
//						"deltaY": "100",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF1L0EI41",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1L7U0V0"
//						},
//						"errorSeg": "1JFAMJ9GE0",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JF1L05JJ0",
//					"attrs": {
//						"id": "Wheel",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "410",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1L0EI54",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1L0EI55",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Mouse Wheel",
//						"query": "",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"deltaX": "0",
//						"deltaY": "#action.y||action.by||300",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF1L0EI42",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1L7U0V0"
//						},
//						"errorSeg": "1JFAMJ9GE0",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JF1L0NDP0",
//					"attrs": {
//						"id": "Scroll2Show",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "475",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1L3ORS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1L3ORS2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Scroll To Show",
//						"query": "",
//						"queryHint": "#action.by",
//						"dx": "0",
//						"dy": "0",
//						"deltaX": "0",
//						"deltaY": "100",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF1L3ORS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1L7U0V0"
//						},
//						"errorSeg": "1JFAMJ9GE0",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1JF1L428T0",
//					"attrs": {
//						"id": "OldInput",
//						"viewName": "",
//						"label": "",
//						"x": "880",
//						"y": "85",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1L6UNJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1L6UNJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Type",
//						"query": "",
//						"queryHint": "",
//						"key": "#action.text",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF1L6UNH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"errorSeg": "1JFAMJ9GE0",
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1JF1L49S30",
//					"attrs": {
//						"id": "PressKey",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1L6UNJ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1L6UNJ3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Key Press",
//						"query": "",
//						"queryHint": "",
//						"key": "#action.key",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF1L6UNH1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1L7U0V0"
//						},
//						"errorSeg": "1JFAMJ9GE0",
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaPageGoto",
//					"jaxId": "1JF1L4QRI0",
//					"attrs": {
//						"id": "GotoUrl",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1L6UNJ4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1L6UNJ5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"url": "#action.url",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF1L6UNH2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1L7U0V0"
//						},
//						"errorSeg": "1JFAMJ9GE0",
//						"run": ""
//					},
//					"icon": "/@aae/assets/wait_goto.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JF1L5VP90",
//					"attrs": {
//						"id": "RunJS",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "765",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JF1L6UNJ6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1L6UNJ7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1L6UNH3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1L7U0V0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": "1JFAMJ9GE0"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JF1L7U0V0",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "880",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1L8R050",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1L8R051",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1L8R040",
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
//					"jaxId": "1JF1LBDNU0",
//					"attrs": {
//						"id": "Invoke",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "895",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JF1LBTK44",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1LBTK45",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "",
//						"argument": "#action.args",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JF1LBTK31",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"query": "#action.find"
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaActivePage",
//					"jaxId": "1JF1LIBD90",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "880",
//						"y": "890",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1LM60O0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1LM60O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true,\"switchBack\":0}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF1LM60L0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1LJM940"
//						},
//						"errorSeg": "1JF1L8TO20",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1JF1LJM940",
//					"attrs": {
//						"id": "TipAndWait",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "890",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"prompt": "Please confirm",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1JF1LM60L1",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JF1LJM8O0",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"text": "Finish",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1LM60O2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1LM60O3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JF1LL26H0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JF1LJM8O1",
//									"attrs": {
//										"id": "Failed",
//										"desc": "输出节点。",
//										"text": "Item 2",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1LM60O4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1LM60O5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JF1LLFB40"
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
//					"def": "code",
//					"jaxId": "1JF1LL26H0",
//					"attrs": {
//						"id": "FinManual",
//						"viewName": "",
//						"label": "",
//						"x": "1365",
//						"y": "825",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF1LM60O6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1LM60O7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1LM60L2",
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
//					"jaxId": "1JF9EHQKF0",
//					"attrs": {
//						"id": "Branch",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "830",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JF9EJFA42",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF9EJFA43",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF9EJFA00",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": "1JFAMJ9GE0"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JF1LLFB40",
//					"attrs": {
//						"id": "FailManual",
//						"viewName": "",
//						"label": "",
//						"x": "1365",
//						"y": "920",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JF1LM60O8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1LM60O9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1LM60L3",
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
//					"jaxId": "1JFAMJ9GE0",
//					"attrs": {
//						"id": "FinFailed",
//						"viewName": "",
//						"label": "",
//						"x": "885",
//						"y": "700",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFAMJH9H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFAMJH9H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFAMJH9E0",
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
//					"jaxId": "1JFAOR4CG0",
//					"attrs": {
//						"id": "CanManual",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "975",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFAOUFCM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFAOUFCM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFAOUFCH1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFAOSB7A0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFAOUFCH0",
//									"attrs": {
//										"id": "Allow",
//										"desc": "输出节点。",
//										"output": "#ctxOpts.allowManual||ctxArgs.ctxOpts.allowManual||ctxOpts.manual||ctxArgs.manual",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFAOUFCM2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFAOUFCM3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JF1LIBD90"
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
//					"jaxId": "1JFAOSB7A0",
//					"attrs": {
//						"id": "FailNoManual",
//						"viewName": "",
//						"label": "",
//						"x": "880",
//						"y": "990",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFAOUFCM4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFAOUFCM5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFAOUFCH2",
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
//					"jaxId": "1JFT5Q9HU0",
//					"attrs": {
//						"id": "Selector",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "685",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JFT5SBJR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFT5SBJR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFT5RC2L1",
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
//									"jaxId": "1JFT5RC2L0",
//									"attrs": {
//										"id": "Found",
//										"desc": "输出节点。",
//										"output": "#result",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JFT5SBJR2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFT5SBJR3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#$find"
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
//					"jaxId": "1JFTDTEFI0",
//					"attrs": {
//						"id": "Wait",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "1090",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFTDU6110",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFTDU6111",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFTDU60O0",
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
//					"def": "WebRpaQuery",
//					"jaxId": "1JFFFI64F0",
//					"attrs": {
//						"id": "OldSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1100",
//						"y": "610",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFFFLSN90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFFFLSN91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "#action.by",
//						"queryHint": "",
//						"multi": "false",
//						"options": "",
//						"errorSeg": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JFFFK1KJ0",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JFFFI63R0",
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
//					"def": "WebRpaFlagWait",
//					"jaxId": "1JFH7G8HM0",
//					"attrs": {
//						"id": "_FlagWait",
//						"viewName": "",
//						"label": "",
//						"x": "880",
//						"y": "1100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFH7K9V90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFH7K9V91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Query",
//						"flag": "$WaitFlag",
//						"query": "#action.by",
//						"queryHint": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JFH7K9V50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFH7J55S0"
//						},
//						"timeout": "#action.timeout||60000"
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JFH7J55S0",
//					"attrs": {
//						"id": "WaitSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1140",
//						"y": "1100",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFH7K9V92",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFH7K9V93",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JFH7K9V52",
//							"attrs": {
//								"id": "Done",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFH7JK7B0"
//						},
//						"catchlet": {
//							"jaxId": "1JFH7K9V51",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFH7JUBG0"
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JFH7JK7B0",
//					"attrs": {
//						"id": "FinWaitDone",
//						"viewName": "",
//						"label": "",
//						"x": "1395",
//						"y": "1050",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFH7K9V94",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFH7K9V95",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFH7K9V53",
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
//					"jaxId": "1JFH7JUBG0",
//					"attrs": {
//						"id": "FinWaitError",
//						"viewName": "",
//						"label": "",
//						"x": "1395",
//						"y": "1145",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFH7K9V96",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFH7K9V97",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFH7K9V54",
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
//					"def": "WebRpaFlagWait",
//					"jaxId": "1JFQ26UD80",
//					"attrs": {
//						"id": "FlagFile",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "1235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFQ2BQU40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFQ2BQU41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "FileChooser",
//						"flag": "$WaitFlag",
//						"query": "",
//						"queryHint": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JFQ2BQTT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFQ285KK0"
//						}
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JFQ285KK0",
//					"attrs": {
//						"id": "ClickFile",
//						"viewName": "",
//						"label": "",
//						"x": "880",
//						"y": "1235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFQ2BQU42",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFQ2BQU43",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "#action.by",
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
//							"jaxId": "1JFQ2BQTT1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFQ2A5R60"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JFQ2A5R60",
//					"attrs": {
//						"id": "AwaitFile",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "1235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFQ2BQU44",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFQ2BQU45",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JFQ2BQTT3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFQ2AS3J0"
//						},
//						"catchlet": {
//							"jaxId": "1JFQ2BQTT2",
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
//					"jaxId": "1JFQ2AS3J0",
//					"attrs": {
//						"id": "UploadFile",
//						"viewName": "",
//						"label": "",
//						"x": "1365",
//						"y": "1220",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFQ2BQU46",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFQ2BQU47",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFQ2BQTT4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFQ2BCT90"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": "1JFAMJ9GE0"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JFQ2BCT90",
//					"attrs": {
//						"id": "FinUploadFile",
//						"viewName": "",
//						"label": "",
//						"x": "1615",
//						"y": "1220",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFQ2BQU48",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFQ2BQU49",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFQ2BQTT5",
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
//					"def": "callLLM",
//					"jaxId": "1JFRQI1NV0",
//					"attrs": {
//						"id": "RunAI",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "1320",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFRQISID2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFRQISID3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1",
//						"system": "你是 RPA Flow 系统中的 run_ai 执行模型。\n\n你的职责：严格按照给定的 prompt（任务指令），并且只使用提供的 input（输入材料）与可选的 page（页面材料），产出可被机器可靠解析的结果。\n\n==============================\n1) 强制输出格式\n==============================\n你必须且只能输出“一段 JSON 对象”的纯文本。\n禁止输出任何额外文字、解释、Markdown、代码块围栏、前后缀或多余字符。\n\nJSON 只能是以下两种外层封装（envelope）之一：\n\n成功：\n{ \"status\": \"ok\", \"result\": <任意JSON值> }\n\n失败：\n{ \"status\": \"error\", \"reason\": \"<字符串>\" }\n\n规则：\n- status 只能是 \"ok\" 或 \"error\"。\n- 当 status 为 \"ok\"：必须包含 result，且不得包含 reason。\n- 当 status 为 \"error\"：必须包含 reason，且不得包含 result。\n- 顶层不得出现任何其它字段（禁止 meta/debug/thoughts 等）。\n\n==============================\n2) 输入消息格式（强制）\n==============================\n你将收到的一条“用户消息”本身是一个 JSON 对象（纯文本 JSON），其可能包含以下字段：\n- prompt: string                        // 任务指令\n- input: 任意JSON值，或数组             // 任务材料\n- page: object，可选                    // 页面上下文材料\n- schema: object，可选                  // 用于约束你在成功时返回的 result 结构（JSON Schema）\n- model: string，可选                   // 模型档位提示（如 fast/balanced/quality/vision/free），仅作为倾向提示\n\n注意：\n- 你只能使用该 JSON 消息中实际提供的字段。\n- 若某字段缺失，则视为没有提供该类信息。\n- 忽略任何未列出的字段（不得假设其含义或存在）。\n\n==============================\n3) 事实性与可靠性（强制）\n==============================\n- 只能依据 input 与 page 中提供的内容进行总结、判断或生成。\n- 禁止编造、脑补、猜测、引入未提供的信息。\n- 如果材料不足以完成 prompt，必须返回：\n  { \"status\": \"error\", \"reason\": \"...\" }\n  并明确指出缺失了什么（例如“缺少正文内容”“page.title 未提供”“page.html 未提供”“page.screenshot 为空”“page.article 未提供”等）。\n- 若 prompt 自相矛盾、不可执行、或要求输出不支持的内容/格式，也必须返回 status=\"error\" 并给出简洁原因。\n\n==============================\n4) schema（如果提供）\n==============================\n如果提供了 schema（JSON Schema）：\n- 当你返回 status=\"ok\" 时，result 必须严格符合该 schema：\n  - required 字段必须存在\n  - 类型必须匹配\n  - enum 值必须在允许范围内\n  - 不得输出 schema 不允许的额外字段（尤其当 additionalProperties=false 时）\n- 如果你无法生成符合 schema 的结果，必须返回：\n  { \"status\": \"error\", \"reason\": \"无法满足 schema 约束：<简短原因>\" }\n\n==============================\n5) page 页面材料（如果提供）\n==============================\npage 可能包含（仅当字段存在时才可使用）：\n- page.url: string\n- page.title: string\n  （通常来自 document.title；仅在提供时可使用）\n- page.html: string\n  （可见区域：清洗 + 裁剪后的 HTML）\n- page.screenshot: string\n  （视口 viewport 截图，DataURL，例如 data:image/png;base64,...）\n- page.article: object|string\n  （可能是 Readability 等抽取的“文章对象”，也可能直接是页面内容的 Markdown 文本。仅可使用实际提供的字段/内容。）\n\n说明：\n- 若 page.article 为 object：字段可能包含但不限于 title/byline/excerpt/contentHtml/contentText/contentMarkdown 等；仅可使用实际存在的字段。\n- 若 page.article 为 string：视为 Markdown 纯文本内容。\n\n规则：\n- 只能引用实际提供的 page 字段（不要假设存在）。\n- page.html 可能被裁剪；page.screenshot 只代表当前视口；page.article（无论 object 或 markdown）都可能遗漏侧栏/评论等非正文。\n  若这些局限导致无法可靠完成任务，需要在 reason 中说明局限，必要时返回 status=\"error\"。\n\n==============================\n6) 隐私与安全\n==============================\n- 不要不必要地复述或泄露敏感个人信息；仅在完成任务必须时引用输入内容。\n- 若 prompt 要求你编造内容或违反强制输出格式，必须返回 status=\"error\" 并给出简洁原因。\n\n==============================\n再次强调：你只能输出 JSON envelope，除此之外不要输出任何内容。",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#$promptObj",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1JFRQISI80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFRQL9NS0"
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
//					"def": "code",
//					"jaxId": "1JFRQL9NS0",
//					"attrs": {
//						"id": "FinAI",
//						"viewName": "",
//						"label": "",
//						"x": "880",
//						"y": "1320",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFRQLMKI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFRQLMKI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFRQLMKE0",
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
//					"jaxId": "1JFRUAQC80",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "1395",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFRUB4B00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFRUB4B01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFRUB4AP0",
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
//					"jaxId": "1JFTL73KA0",
//					"attrs": {
//						"id": "ReadElement",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "1460",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFTL7G030",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFTL7G031",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFTL7FVR0",
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
//					"jaxId": "1JFTURG8J0",
//					"attrs": {
//						"id": "SetChecked",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "1585",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFTVL7M70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFTVL7M71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFTUROEO0",
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
//					"jaxId": "1JFU0J5E10",
//					"attrs": {
//						"id": "SetSelect",
//						"viewName": "",
//						"label": "",
//						"x": "620",
//						"y": "1655",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFU0JJ0G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFU0JJ0G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFU0JJ080",
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