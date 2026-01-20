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
	let StartRpa,OnAction,Click,Hover,Wheel,Scroll2Show,Input,PressKey,GotoUrl,RunJS,FinDone,Invoke,ShowPage,TipAndWait,FinManual,Branch,FailManual,FinFailed,CanManual,FailNoManual;
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JF1KIV0I0"));
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
		return {seg:OnAction,result:(result),preSeg:"1JF1KIV0I0",outlet:"1JF1KIV0J0"};
	};
	StartRpa.jaxId="1JF1KIV0I0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["OnAction"]=OnAction=async function(input){//:1JF1KJM740
		let result=input;
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
		if(action.type==="input"){
			return {seg:Input,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KM9ER0"};
		}
		if(action.type==="press_key"){
			return {seg:PressKey,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KMOVH0"};
		}
		if(action.type==="goto"){
			return {seg:GotoUrl,result:(input),preSeg:"1JF1KJM740",outlet:"1JF1KNH540"};
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
		return {result:result};
	};
	OnAction.jaxId="1JF1KJM740"
	OnAction.url="OnAction@"+agentURL
	
	segs["Click"]=Click=async function(input){//:1JF1KV6480
		let result=true;
		let pageVal="aaPage";
		let $query=input.by;
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
		let $queryHint=input.by;
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
		let $deltaY=input.y||input.by||300;
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
		let $queryHint=input.by;
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
	
	segs["Input"]=Input=async function(input){//:1JF1L428T0
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="";
		let $queryHint="";
		let $key=input;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		/*#{1JF1L428T0PreCodes*/
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
		return {seg:FinDone,result:(result),preSeg:"1JF1L428T0",outlet:"1JF1L6UNH0"};
	};
	Input.jaxId="1JF1L428T0"
	Input.url="Input@"+agentURL
	
	segs["PressKey"]=PressKey=async function(input){//:1JF1L49S30
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="";
		let $queryHint="";
		let $key="Enter";
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
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JF1L49S30")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.type($query,$key,$options||{});
			}else{
				$pms=page.keyboard.type($key,$options||{});
			}
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
		let url="https://www.google.com";
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
			value=await execRunJsAction(action,ctx);
			result={status:"Done",result:"Done",value:value};
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
		arg.pageRef=pageRef;
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
		return {seg:FinDone,result:(result),preSeg:"1JF9EHQKF0",outlet:"1JF9EJFA00"};
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
//						"x": "85",
//						"y": "450",
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
//						"x": "325",
//						"y": "435",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
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
//									"linkedSeg": "1JF1L428T0"
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
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JF1KV6480",
//					"attrs": {
//						"id": "Click",
//						"viewName": "",
//						"label": "",
//						"x": "625",
//						"y": "75",
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
//						"query": "#input.by",
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
//						"x": "625",
//						"y": "140",
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
//						"queryHint": "#input.by",
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
//						"x": "625",
//						"y": "205",
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
//						"deltaY": "#input.y||input.by||300",
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
//						"x": "625",
//						"y": "270",
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
//						"queryHint": "#input.by",
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
//						"id": "Input",
//						"viewName": "",
//						"label": "",
//						"x": "625",
//						"y": "335",
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
//						"key": "#input",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF1L6UNH0",
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
//					"def": "AAFKeyboardAction",
//					"jaxId": "1JF1L49S30",
//					"attrs": {
//						"id": "PressKey",
//						"viewName": "",
//						"label": "",
//						"x": "625",
//						"y": "400",
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
//						"action": "Type",
//						"query": "",
//						"queryHint": "",
//						"key": "Enter",
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
//						"x": "625",
//						"y": "465",
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
//						"url": "https://www.google.com",
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
//						"x": "625",
//						"y": "525",
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
//						"x": "885",
//						"y": "435",
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
//						"x": "625",
//						"y": "655",
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
//						"x": "885",
//						"y": "720",
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
//						"x": "1140",
//						"y": "720",
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
//						"x": "1370",
//						"y": "655",
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
//						"x": "625",
//						"y": "590",
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
//					"jaxId": "1JF1LLFB40",
//					"attrs": {
//						"id": "FailManual",
//						"viewName": "",
//						"label": "",
//						"x": "1370",
//						"y": "750",
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
//						"y": "560",
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
//						"x": "625",
//						"y": "735",
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
//						"y": "810",
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
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}