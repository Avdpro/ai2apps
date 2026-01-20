//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JE5NNTO90MoreImports*/
import {readFileAsDataURL,buildRpaMicroDeciderPrompt,readRule,saveRule,findAvailableSelector,armWaitForScroll,waitForScrollOutcome,extractActionableLinks,ai2appsTip} from "./utils.js";
import {mergeItemsDedup} from "./util_item_types.js";
/*}#1JE5NNTO90MoreImports*/
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
		"profile":{
			"name":"profile","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"url":{
			"name":"url","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"waitAfter":{
			"name":"waitAfter","type":"integer",
			"defaultValue":2000,
			"desc":"",
		},
		"listCode":{
			"name":"listCode","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JE5NNTO90ArgsView*/
	/*}#1JE5NNTO90ArgsView*/
};

/*#{1JE5NNTO90StartDoc*/
/*}#1JE5NNTO90StartDoc*/
//----------------------------------------------------------------------------
let CaRpa_GenMoreItems=async function(session){
	let pageRef,profile,url,waitAfter,listCode;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,CheckBlocker,ReadContent,ReadRule,FindSelector,TryScroll,HasScrollMore,ReadPage,GenRule,Click,FinDone,FinAbort,SaveRule,Finish,WaitAfter,RetryClick,FinRetry,JumpFin,FlagClick,AwaitClick,GotoRetry,JumpScroll,ShowPage,Back2App,Back2App2,ViewPage;
	let orgRule=null;
	let usedRule=null;
	let retryNum=0;
	let wrongSelectors=[];
	let contentItems=[];
	let scrollNum=0;
	let armedScroll=null;
	let orgItemsNum=0;
	let isRuleClick=false;
	let clickSelector="";
	let tipOpts="";
	
	/*#{1JE5NNTO90LocalVals*/
	tipOpts={id:"system",icon:await readFileAsDataURL("./ai2apps.svg"),};
	/*}#1JE5NNTO90LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			profile=input.profile;
			url=input.url;
			waitAfter=input.waitAfter;
			listCode=input.listCode;
		}else{
			pageRef=undefined;
			profile=undefined;
			url=undefined;
			waitAfter=undefined;
			listCode=undefined;
		}
		/*#{1JE5NNTO90ParseArgs*/
		if(!listCode){
			listCode=extractActionableLinks;
		}
		waitAfter=waitAfter===undefined?2000:waitAfter;
		/*}#1JE5NNTO90ParseArgs*/
	}
	
	/*#{1JE5NNTO90PreContext*/
	/*}#1JE5NNTO90PreContext*/
	context={};
	/*#{1JE5NNTO90PostContext*/
	/*}#1JE5NNTO90PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JE6KEEK10
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JE6KEEK10"));
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
		return {seg:CheckBlocker,result:(result),preSeg:"1JE6KEEK10",outlet:"1JE6KEEK20"};
	};
	StartRpa.jaxId="1JE6KEEK10"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["CheckBlocker"]=CheckBlocker=async function(input){//:1JEJ7UQPU0
		let result;
		let arg={"pageRef":pageRef,"blocker":{remove:true},"waitAfter":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenBlockers.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:ViewPage,result:(result),preSeg:"1JEJ7UQPU0",outlet:"1JEJ7UQPV2"};
	};
	CheckBlocker.jaxId="1JEJ7UQPU0"
	CheckBlocker.url="CheckBlocker@"+agentURL
	
	segs["ReadContent"]=ReadContent=async function(input){//:1JEJHDJHA0
		let result=input
		try{
			/*#{1JEJHDJHA0Code*/
			let page,list;
			page=context.aaPage;
			list=await page.callFunction(listCode,[]);
			if(list && Array.isArray(list)){
				contentItems.push(...list);
			}
			orgItemsNum=contentItems.length;
			console.log(`GenMoreItems_ReadContent: url=${await page.url()}`);
			/*}#1JEJHDJHA0Code*/
		}catch(error){
			/*#{1JEJHDJHA0ErrorCode*/
			/*}#1JEJHDJHA0ErrorCode*/
		}
		return {seg:ReadRule,result:(result),preSeg:"1JEJHDJHA0",outlet:"1JEJHEH0F0"};
	};
	ReadContent.jaxId="1JEJHDJHA0"
	ReadContent.url="ReadContent@"+agentURL
	
	segs["ReadRule"]=ReadRule=async function(input){//:1JE6KNCPL0
		let result=input;
		/*#{1JE6KNCPL0Start*/
		let rule=await readRule(session,context.aaPage,"show_more_items");
		/*}#1JE6KNCPL0Start*/
		if(rule){
			let output=rule;
			/*#{1JE6KNCPM0Codes*/
			orgRule=rule;
			/*}#1JE6KNCPM0Codes*/
			return {seg:FindSelector,result:(output),preSeg:"1JE6KNCPL0",outlet:"1JE6KNCPM0"};
		}
		/*#{1JE6KNCPL0Post*/
		/*}#1JE6KNCPL0Post*/
		return {seg:ShowPage,result:(result),preSeg:"1JE6KNCPL0",outlet:"1JE6KNCPL3"};
	};
	ReadRule.jaxId="1JE6KNCPL0"
	ReadRule.url="ReadRule@"+agentURL
	
	segs["FindSelector"]=FindSelector=async function(input){//:1JEJF4U7C0
		let result=input;
		/*#{1JEJF4U7C0Start*/
		let selectors,selector;
		selectors=input;
		if(!Array.isArray(selectors)){
			selectors=[selectors];
		}
		selector=await findAvailableSelector(context.webRpa,context.aaPage,selectors);
		/*}#1JEJF4U7C0Start*/
		if(selector){
			let output=selector;
			/*#{1JEJFOGIH0Codes*/
			isRuleClick=true;
			/*}#1JEJFOGIH0Codes*/
			return {seg:Click,result:(output),preSeg:"1JEJF4U7C0",outlet:"1JEJFOGIH0"};
		}
		/*#{1JEJF4U7C0Post*/
		/*}#1JEJF4U7C0Post*/
		return {seg:ShowPage,result:(result),preSeg:"1JEJF4U7C0",outlet:"1JEJFOGIH1"};
	};
	FindSelector.jaxId="1JEJF4U7C0"
	FindSelector.url="FindSelector@"+agentURL
	
	segs["TryScroll"]=TryScroll=async function(input){//:1JE6KORI20
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint="";
		let $deltaX=0;
		let $deltaY=500;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		/*#{1JE6KORI20PreCodes*/
		scrollNum=scrollNum>0?scrollNum+1:1;
		armedScroll=await page.callFunction(armWaitForScroll,[{timeoutMs:2000}]);
		{
			let $channel="Process";
			let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
			let role="assistant";
			let content=`TryScroll: ${scrollNum}`;
			session.addChatText(role,content,opts);
			page.callFunction(ai2appsTip,[content,tipOpts]);
		}
		/*}#1JE6KORI20PreCodes*/
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JE6KORI20")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.mouseWheel($query,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
			}else{
				$pms=page.mouseWheel(null,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JE6KORI20ErrorCode*/
			/*}#1JE6KORI20ErrorCode*/
		}
		/*#{1JE6KORI20PostCodes*/
		/*}#1JE6KORI20PostCodes*/
		return {seg:HasScrollMore,result:(result),preSeg:"1JE6KORI20",outlet:"1JE6KPJEB2"};
	};
	TryScroll.jaxId="1JE6KORI20"
	TryScroll.url="TryScroll@"+agentURL
	
	segs["HasScrollMore"]=HasScrollMore=async function(input){//:1JEJHSRPL0
		let result=input;
		/*#{1JEJHSRPL0Start*/
		let page,outcome,scrollAgain,findMore;
		page=context.aaPage;
		outcome=await page.callFunction(waitForScrollOutcome,[armedScroll?.token]);
		if(outcome.scrolled){
			let list,oldNum;
			await sleep(500);
			list=await page.callFunction(listCode,[]);
			if(list && Array.isArray(list)){
				mergeItemsDedup(contentItems,list);
				if(contentItems.length-orgItemsNum>5){
					scrollAgain=false;
					findMore=true;
				}else if(scrollNum<5){
					scrollAgain=true;
					findMore=false;
				}else{
					scrollAgain=false;
					findMore=false;
				}
			}
		}else{
			scrollAgain=false;
			findMore=false;
		}
		/*}#1JEJHSRPL0Start*/
		if(scrollAgain){
			return {seg:TryScroll,result:(input),preSeg:"1JEJHSRPL0",outlet:"1JEK9P81I0"};
		}
		if(findMore){
			return {seg:Back2App2,result:(input),preSeg:"1JEJHSRPL0",outlet:"1JEJI4T7V3"};
		}
		/*#{1JEJHSRPL0Post*/
		/*}#1JEJHSRPL0Post*/
		return {seg:Back2App,result:(result),preSeg:"1JEJHSRPL0",outlet:"1JEJI4T7V2"};
	};
	HasScrollMore.jaxId="1JEJHSRPL0"
	HasScrollMore.url="HasScrollMore@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1JEIB2I4A0
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
			/*#{1JEIB2I4A0ErrorCode*/
			/*}#1JEIB2I4A0ErrorCode*/
		}
		return {seg:GenRule,result:(result),preSeg:"1JEIB2I4A0",outlet:"1JEIB8EF40"};
	};
	ReadPage.jaxId="1JEIB2I4A0"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["GenRule"]=GenRule=async function(input){//:1JEIB34JQ0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5";
		let $agent;
		let result=null;
		/*#{1JEIB34JQ0Input*/
		let $system=buildRpaMicroDeciderPrompt(
			"给定当前页面清洗后的HTML代码，确认是否可以通过点击以显示更多内容项目（例如搜索结果，信息，内容卡片等）。如果是，返回选择要点击的HTML元素。",
			'如果当前页面有明显的通过点击获得更多内容的元素，返回"selector"动作，给出要点击的元素的selector。\n'+
			'如果当前页面已经显示了全部内容，无法再获取更多了，返回"done"动作\n'+
			'如果当前页面出错，比如404等，返回"abort"动作\n'+
			(wrongSelectors.length?`\n\n重要: 已知：${JSON.stringify(wrongSelectors)} 这些selector是错误无效的，不要重复给出重复的错误答案。`:""),
			["selector"]
		);		
		/*}#1JEIB34JQ0Input*/
		
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
		let chatMem=GenRule.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:$system},
		];
		/*#{1JEIB34JQ0PrePrompt*/
		/*}#1JEIB34JQ0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JEIB34JQ0FilterMessage*/
			/*}#1JEIB34JQ0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JEIB34JQ0PreCall*/
		/*}#1JEIB34JQ0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("GenRule@"+agentURL,opts,messages,true)):result;
		}
		result=trimJSON(result);
		/*#{1JEIB34JQ0PostCall*/
		/*}#1JEIB34JQ0PostCall*/
		if(result && result.action && result.action.type==="selector"){
			let output=result.action.by;
			/*#{1JEIBD1CG0Codes*/
			isRuleClick=false;
			/*}#1JEIBD1CG0Codes*/
			return {seg:Click,result:(output),preSeg:"1JEIB34JQ0",outlet:"1JEIBD1CG0"};
		}
		if(result && result.action && result.action.type==="done"){
			return {seg:FinDone,result:(input),preSeg:"1JEIB34JQ0",outlet:"1JEIBFQBO0"};
		}
		if(result && result.action && result.action.type==="abort"){
			return {seg:FinAbort,result:(input),preSeg:"1JEIB34JQ0",outlet:"1JEIBG1T50"};
		}
		/*#{1JEIB34JQ0PreResult*/
		/*}#1JEIB34JQ0PreResult*/
		return {seg:GotoRetry,result:(result),preSeg:"1JEIB34JQ0",outlet:"1JEIB8EF41"};
	};
	GenRule.jaxId="1JEIB34JQ0"
	GenRule.url="GenRule@"+agentURL
	
	segs["Click"]=Click=async function(input){//:1JEIBE6BC0
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
		/*#{1JEIBE6BC0PreCodes*/
		clickSelector=$query;
		/*}#1JEIBE6BC0PreCodes*/
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JEIBE6BC0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.click($query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
			}else{
				$pms=page.mouse.click($x,$y,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JEIBE6BC0ErrorCode*/
			error=$query;
			/*}#1JEIBE6BC0ErrorCode*/
			return {seg:RetryClick,result:error,preSeg:"1JEIBE6BC0",outlet:null};
		}
		/*#{1JEIBE6BC0PostCodes*/
		usedRule=$query;
		/*}#1JEIBE6BC0PostCodes*/
		return {seg:FlagClick,result:(result),preSeg:"1JEIBE6BC0",outlet:"1JEIBHHD62"};
	};
	Click.jaxId="1JEIBE6BC0"
	Click.url="Click@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JEIBGIQH0
		let result=input
		try{
			/*#{1JEIBGIQH0Code*/
			result={status:"Done",result:"Finish"};
			/*}#1JEIBGIQH0Code*/
		}catch(error){
			/*#{1JEIBGIQH0ErrorCode*/
			/*}#1JEIBGIQH0ErrorCode*/
		}
		return {result:result};
	};
	FinDone.jaxId="1JEIBGIQH0"
	FinDone.url="FinDone@"+agentURL
	
	segs["FinAbort"]=FinAbort=async function(input){//:1JEIBH1D70
		let result=input
		try{
			/*#{1JEIBH1D70Code*/
			result={status:"Failed",result:"Failed",reason:input.reason};
			/*}#1JEIBH1D70Code*/
		}catch(error){
			/*#{1JEIBH1D70ErrorCode*/
			/*}#1JEIBH1D70ErrorCode*/
		}
		return {result:result};
	};
	FinAbort.jaxId="1JEIBH1D70"
	FinAbort.url="FinAbort@"+agentURL
	
	segs["SaveRule"]=SaveRule=async function(input){//:1JEIBIFC20
		let result=input
		try{
			/*#{1JEIBIFC20Code*/
			let page,newRule,selectors;
			page=context.aaPage;
			newRule=false;
			if(usedRule){
				selectors=(await readRule(session,page,"show_more_items"))||[];
				if(selectors.indexOf(usedRule)<0){
					selectors.push(usedRule);
					if(selectors.length>10){
						selectors=selectors.slice(-10);
					}
					await saveRule(session,page,"show_more_items",selectors);
				}
			}
			/*}#1JEIBIFC20Code*/
		}catch(error){
			/*#{1JEIBIFC20ErrorCode*/
			/*}#1JEIBIFC20ErrorCode*/
		}
		return {seg:Finish,result:(result),preSeg:"1JEIBIFC20",outlet:"1JEIBK7F00"};
	};
	SaveRule.jaxId="1JEIBIFC20"
	SaveRule.url="SaveRule@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1JEIBIUQA0
		let result=input
		try{
			/*#{1JEIBIUQA0Code*/
			result={status:"Done",result:"Finish"};
			/*}#1JEIBIUQA0Code*/
		}catch(error){
			/*#{1JEIBIUQA0ErrorCode*/
			/*}#1JEIBIUQA0ErrorCode*/
		}
		return {seg:WaitAfter,result:(result),preSeg:"1JEIBIUQA0",outlet:"1JEIBK7F01"};
	};
	Finish.jaxId="1JEIBIUQA0"
	Finish.url="Finish@"+agentURL
	
	segs["WaitAfter"]=WaitAfter=async function(input){//:1JEIBJKT50
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
	WaitAfter.jaxId="1JEIBJKT50"
	WaitAfter.url="WaitAfter@"+agentURL
	
	segs["RetryClick"]=RetryClick=async function(input){//:1JEJ8MOM50
		let result=input;
		/*#{1JEJ8MOM50Start*/
		retryNum=retryNum>0?retryNum+1:1;
		clickSelector && wrongSelectors.push(clickSelector);
		/*}#1JEJ8MOM50Start*/
		if(isRuleClick){
			return {seg:JumpScroll,result:(input),preSeg:"1JEJ8MOM50",outlet:"1JELU6UFS0"};
		}
		if(retryNum>3){
			return {seg:FinRetry,result:(input),preSeg:"1JEJ8MOM50",outlet:"1JEJ8T75O0"};
		}
		/*#{1JEJ8MOM50Post*/
		/*}#1JEJ8MOM50Post*/
		return {seg:ReadPage,result:(result),preSeg:"1JEJ8MOM50",outlet:"1JEJ8T75O1"};
	};
	RetryClick.jaxId="1JEJ8MOM50"
	RetryClick.url="RetryClick@"+agentURL
	
	segs["FinRetry"]=FinRetry=async function(input){//:1JEJ8UTKL0
		let result=input
		try{
			/*#{1JEJ8UTKL0Code*/
			result={status:"Failed",result:"Failed",reason:"Max retry."};
			/*}#1JEJ8UTKL0Code*/
		}catch(error){
			/*#{1JEJ8UTKL0ErrorCode*/
			/*}#1JEJ8UTKL0ErrorCode*/
		}
		return {result:result};
	};
	FinRetry.jaxId="1JEJ8UTKL0"
	FinRetry.url="FinRetry@"+agentURL
	
	segs["JumpFin"]=JumpFin=async function(input){//:1JEJHUALT0
		let result=input;
		return {seg:Finish,result:result,preSeg:"1JEIBIUQA0",outlet:"1JEJIN8DP3"};
	
	};
	JumpFin.jaxId="1JEIBIUQA0"
	JumpFin.url="JumpFin@"+agentURL
	
	segs["FlagClick"]=FlagClick=async function(input){//:1JEL1LBGO0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $query="";
		let $queryHint="";
		let $waitBefore=0;
		let $waitAfter=0;
		let $options={};
		let $timeout=5000;
		let page=context[pageVal];
		let $args=[];
		
		if($timeout){$options.timeout=$timeout;}
		$waitBefore && (await sleep($waitBefore));
		/*#{1JEL1LBGO0PreCodes*/
		let errNum=0;
		let items,orgNum,tryNum;
		items=contentItems;
		orgNum=items.length;
		console.log(`GenMoreItems_FlagClick: orgNum=${orgNum}`);
		console.log(`GenMoreItems_FlagClick: url=${await page.url()}`);
		tryNum=0;
		$query=async function(){
			let list;
			try{
				list=await page.callFunction(listCode,[]);
				mergeItemsDedup(items,list);
				console.log(`GenMoreItems_FlagClick: tryNum=${++tryNum}, newNum=${items.length}`);
				console.log(`GenMoreItems_FlagClick: url=${await page.url()}`);
				if(items.length-orgNum>=3){
					return true;
				}
			}catch(err){
			}
			return false;
		};
		/*}#1JEL1LBGO0PreCodes*/
		context[$flag]=page.waitForHostFunction($query,$args,$options);
		$waitAfter && (await sleep($waitAfter))
		/*#{1JEL1LBGO0PostCodes*/
		/*}#1JEL1LBGO0PostCodes*/
		return {seg:AwaitClick,result:(result),preSeg:"1JEL1LBGO0",outlet:"1JEL1RHHH0"};
	};
	FlagClick.jaxId="1JEL1LBGO0"
	FlagClick.url="FlagClick@"+agentURL
	
	segs["AwaitClick"]=AwaitClick=async function(input){//:1JEL1N6LU0
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
			return {seg:RetryClick,result:(error),preSeg:"1JEL1N6LU0",outlet:"1JEL1RHHH1"};
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:SaveRule,result:(result),preSeg:"1JEL1N6LU0",outlet:"1JEL1RHHH2"};
	};
	AwaitClick.jaxId="1JEL1N6LU0"
	AwaitClick.url="AwaitClick@"+agentURL
	
	segs["GotoRetry"]=GotoRetry=async function(input){//:1JEL5KG7F0
		let result=input;
		return {seg:RetryClick,result:result,preSeg:"1JEJ8MOM50",outlet:"1JEL5MBNG0"};
	
	};
	GotoRetry.jaxId="1JEJ8MOM50"
	GotoRetry.url="GotoRetry@"+agentURL
	
	segs["JumpScroll"]=JumpScroll=async function(input){//:1JELU5PUA0
		let result=input;
		return {seg:ShowPage,result:result,preSeg:"1JEM3EQ360",outlet:"1JELU6UFS1"};
	
	};
	JumpScroll.jaxId="1JEM3EQ360"
	JumpScroll.url="JumpScroll@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1JEM3EQ360
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=500;
		let $options={"focusBrowser":1,"switchBack":false};
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
			/*#{1JEM3EQ360ErrorCode*/
			/*}#1JEM3EQ360ErrorCode*/
		}
		return {seg:TryScroll,result:(result),preSeg:"1JEM3EQ360",outlet:"1JEM3FAP70"};
	};
	ShowPage.jaxId="1JEM3EQ360"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["Back2App"]=Back2App=async function(input){//:1JEN0QMKI0
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
			/*#{1JEN0QMKI0ErrorCode*/
			/*}#1JEN0QMKI0ErrorCode*/
		}
		return {seg:ReadPage,result:(result),preSeg:"1JEN0QMKI0",outlet:"1JEN0RU7A0"};
	};
	Back2App.jaxId="1JEN0QMKI0"
	Back2App.url="Back2App@"+agentURL
	
	segs["Back2App2"]=Back2App2=async function(input){//:1JEN0SIIO0
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
			/*#{1JEN0SIIO0ErrorCode*/
			/*}#1JEN0SIIO0ErrorCode*/
		}
		return {seg:JumpFin,result:(result),preSeg:"1JEN0SIIO0",outlet:"1JEN0T1L30"};
	};
	Back2App2.jaxId="1JEN0SIIO0"
	Back2App2.url="Back2App2@"+agentURL
	
	segs["ViewPage"]=ViewPage=async function(input){//:1JEQR5IG50
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=500;
		let $options={"focusBrowser":true,"switchBack":true};
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
			/*#{1JEQR5IG50ErrorCode*/
			/*}#1JEQR5IG50ErrorCode*/
		}
		return {seg:ReadContent,result:(result),preSeg:"1JEQR5IG50",outlet:"1JEQR9Q480"};
	};
	ViewPage.jaxId="1JEQR5IG50"
	ViewPage.url="ViewPage@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CaRpa_GenMoreItems",
		url:agentURL,
		autoStart:true,
		jaxId:"1JE5NNTO90",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,profile,url,waitAfter,listCode}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JE5NNTO90PreEntry*/
			/*}#1JE5NNTO90PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JE5NNTO90PostEntry*/
			/*}#1JE5NNTO90PostEntry*/
			return result;
		},
		/*#{1JE5NNTO90MoreAgentAttrs*/
		/*}#1JE5NNTO90MoreAgentAttrs*/
	};
	/*#{1JE5NNTO90PostAgent*/
	/*}#1JE5NNTO90PostAgent*/
	return agent;
};
/*#{1JE5NNTO90ExCodes*/
/*}#1JE5NNTO90ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CaRpa_GenMoreItems",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				profile:{type:"auto",description:""},
				url:{type:"auto",description:""},
				waitAfter:{type:"integer",description:""},
				listCode:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true,
	kind: "rpa",
	capabilities: ["showMore"],
	filters: [],
	metrics: {"quality":"","costPerCall":"","costPer1M":"","speed":"","size":""}
}];
//#CodyExport<<<
/*#{1JE5NNTO90PostDoc*/
/*}#1JE5NNTO90PostDoc*/


export default CaRpa_GenMoreItems;
export{CaRpa_GenMoreItems,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JE5NNTO90",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JE5NNTO91",
//			"attrs": {
//				"CaRpa_GenMoreItems": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JE5NNTOA0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JE5NNTOA1",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JE5NNTOA2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JE5NNTOA3",
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
//			"jaxId": "1JE5NNTO92",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JE5NNTO93",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE6KN7N30",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"profile": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE6KN7N31",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE6KN7N32",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"waitAfter": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEJ9P8270",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "2000",
//						"desc": ""
//					}
//				},
//				"listCode": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEJAULRD0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JE5NNTO94",
//			"attrs": {
//				"orgRule": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"usedRule": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"retryNum": {
//					"type": "int",
//					"valText": "0"
//				},
//				"wrongSelectors": {
//					"type": "auto",
//					"valText": "[]"
//				},
//				"contentItems": {
//					"type": "auto",
//					"valText": "[]"
//				},
//				"scrollNum": {
//					"type": "int",
//					"valText": "0"
//				},
//				"armedScroll": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"orgItemsNum": {
//					"type": "int",
//					"valText": "0"
//				},
//				"isRuleClick": {
//					"type": "bool",
//					"valText": "false"
//				},
//				"clickSelector": {
//					"type": "string",
//					"valText": ""
//				},
//				"tipOpts": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JE5NNTO95",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JE5NNTO96",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JE6KEEK10",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "105",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE6KEEK11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE6KEEK12",
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
//							"jaxId": "1JE6KEEK20",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEJ7UQPU0"
//						},
//						"catchlet": {
//							"jaxId": "1JE6KEEK21",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JE6KEEK22",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JE6KEEK23",
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
//					"def": "aiBot",
//					"jaxId": "1JEJ7UQPU0",
//					"attrs": {
//						"id": "CheckBlocker",
//						"viewName": "",
//						"label": "",
//						"x": "345",
//						"y": "230",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEJ7UQPV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEJ7UQPV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenBlockers.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"blocker\":\"#{remove:true}\",\"waitAfter\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JEJ7UQPV2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEQR5IG50"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JEJHDJHA0",
//					"attrs": {
//						"id": "ReadContent",
//						"viewName": "",
//						"label": "",
//						"x": "880",
//						"y": "230",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEJHEH0K0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEJHEH0K1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEJHEH0F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE6KNCPL0"
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
//					"jaxId": "1JE6KNCPL0",
//					"attrs": {
//						"id": "ReadRule",
//						"viewName": "",
//						"label": "",
//						"x": "1140",
//						"y": "230",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE6KNCPL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE6KNCPL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE6KNCPL3",
//							"attrs": {
//								"id": "NoRule",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEM3EQ360"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE6KNCPM0",
//									"attrs": {
//										"id": "Rule",
//										"desc": "输出节点。",
//										"output": "#rule",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JE6KNCPM1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE6KNCPM2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#rule"
//									},
//									"linkedSeg": "1JEJF4U7C0"
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
//					"jaxId": "1JEJF4U7C0",
//					"attrs": {
//						"id": "FindSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1375",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEJFOGIP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEJFOGIP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEJFOGIH1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEN0P16D0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEJFOGIH0",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "#selector",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JEJFOGIP2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEJFOGIP3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#selector"
//									},
//									"linkedSeg": "1JELU43JD0"
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
//					"jaxId": "1JE6KORI20",
//					"attrs": {
//						"id": "TryScroll",
//						"viewName": "",
//						"label": "",
//						"x": "1630",
//						"y": "435",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE6KPJEC6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE6KPJEC7",
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
//						"deltaY": "500",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE6KPJEB2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEJHSRPL0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JEJHSRPL0",
//					"attrs": {
//						"id": "HasScrollMore",
//						"viewName": "",
//						"label": "",
//						"x": "1865",
//						"y": "435",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEJI4T7V0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEJI4T7V1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEJI4T7V2",
//							"attrs": {
//								"id": "TryClick",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEN0QMKI0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEK9P81I0",
//									"attrs": {
//										"id": "Scroll",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEK9Q3CF0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEK9Q3CF1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#scrollAgain"
//									},
//									"linkedSeg": "1JEKVC6R20"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEJI4T7V3",
//									"attrs": {
//										"id": "More",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEJI4T7V4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEJI4T7V5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#findMore"
//									},
//									"linkedSeg": "1JEN0SIIO0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1JEIB2I4A0",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "2410",
//						"y": "520",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEIB8EF60",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEIB8EF61",
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
//							"jaxId": "1JEIB8EF40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEIB34JQ0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JEIB34JQ0",
//					"attrs": {
//						"id": "GenRule",
//						"viewName": "",
//						"label": "",
//						"x": "2640",
//						"y": "520",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JEIB8EF62",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEIB8EF63",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-5",
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
//							"jaxId": "1JEIB8EF41",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEL5KG7F0"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1JEQMPOOC0",
//									"attrs": {
//										"prompt": "",
//										"reply": "{ \"action\": { \"type\": \"done\", \"reason\": \"页面为“Latest”列表（Breadcrumb 显示 Page 3），源码未发现“下一页/更多/加载更多/分页”相关按钮或链接，无法通过点击获取更多内容。\", \"conclusion\": \"当前页面不存在可点击以展示更多内容的元素，无法继续通过点击获取更多项目。\" }, \"reason\": \"未见任何分页或“加载更多”按钮；仅有文章卡片与页脚链接，无法通过点击加载更多内容。\", \"summary\": \"文章列表页（Breadcrumb: Page 3）；无分页/Load More元素可点；预期无法通过点击获取更多内容；风险：无。\" }"
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
//									"jaxId": "1JEIBD1CG0",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "#result.action.by",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JEIBHHD92",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEIBHHD93",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action && result.action.type===\"selector\""
//									},
//									"linkedSeg": "1JEIBE6BC0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEIBFQBO0",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEIBHHD94",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEIBHHD95",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action && result.action.type===\"done\""
//									},
//									"linkedSeg": "1JEIBGIQH0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEIBG1T50",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEIBHHD96",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEIBHHD97",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action && result.action.type===\"abort\""
//									},
//									"linkedSeg": "1JEIBH1D70"
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
//					"jaxId": "1JEIBE6BC0",
//					"attrs": {
//						"id": "Click",
//						"viewName": "",
//						"label": "",
//						"x": "2880",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEIBHHD910",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEIBHHD911",
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
//						"waitAfter": "",
//						"outlet": {
//							"jaxId": "1JEIBHHD62",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEL1LBGO0"
//						},
//						"errorSeg": "1JEJ8MOM50",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JEIBENHF0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3695",
//						"y": "715",
//						"outlet": {
//							"jaxId": "1JEIBHHD912",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEIBF0340"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JEIBF0340",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2435",
//						"y": "715",
//						"outlet": {
//							"jaxId": "1JEIBHHD913",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEIB2I4A0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JEIBGIQH0",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "2880",
//						"y": "505",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JEIBHHD914",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEIBHHD915",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEIBHHD63",
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
//					"jaxId": "1JEIBH1D70",
//					"attrs": {
//						"id": "FinAbort",
//						"viewName": "",
//						"label": "",
//						"x": "2880",
//						"y": "585",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JEIBHHD916",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEIBHHD917",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEIBHHD64",
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
//					"jaxId": "1JEIBIFC20",
//					"attrs": {
//						"id": "SaveRule",
//						"viewName": "",
//						"label": "",
//						"x": "3545",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEIBK7F34",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEIBK7F35",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEIBK7F00",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEIBIUQA0"
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
//					"jaxId": "1JEIBIUQA0",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "3800",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JEIBK7F36",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEIBK7F37",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEIBK7F01",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEIBJKT50"
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
//					"jaxId": "1JEIBJKT50",
//					"attrs": {
//						"id": "WaitAfter",
//						"viewName": "",
//						"label": "",
//						"x": "4035",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEIBK7F38",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEIBK7F39",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "",
//						"waitBefore": "0",
//						"waitAfter": "#waitAfter",
//						"outlet": {
//							"jaxId": "1JEIBK7F03",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"catchlet": {
//							"jaxId": "1JEIBK7F02",
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
//					"def": "brunch",
//					"jaxId": "1JEJ8MOM50",
//					"attrs": {
//						"id": "RetryClick",
//						"viewName": "",
//						"label": "",
//						"x": "3545",
//						"y": "490",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEJ8TMRP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEJ8TMRP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEJ8T75O1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEIBENHF0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JELU6UFS0",
//									"attrs": {
//										"id": "RuleClick",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JELU6UG20",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JELU6UG21",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#isRuleClick"
//									},
//									"linkedSeg": "1JELU5PUA0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEJ8T75O0",
//									"attrs": {
//										"id": "MaxRetry",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEJ8TMRP2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEJ8TMRP3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#retryNum>3"
//									},
//									"linkedSeg": "1JEJ8UTKL0"
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
//					"jaxId": "1JEJ8UTKL0",
//					"attrs": {
//						"id": "FinRetry",
//						"viewName": "",
//						"label": "",
//						"x": "3800",
//						"y": "490",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JEJ902J40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEJ902J41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEJ8V9P30",
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
//					"def": "jumper",
//					"jaxId": "1JEJHUALT0",
//					"attrs": {
//						"id": "JumpFin",
//						"viewName": "",
//						"label": "",
//						"x": "2410",
//						"y": "435",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JEIBIUQA0",
//						"outlet": {
//							"jaxId": "1JEJIN8DP3",
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
//					"def": "connector",
//					"jaxId": "1JEK9QK1K0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1665",
//						"y": "305",
//						"outlet": {
//							"jaxId": "1JEK9QOGA1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE6KORI20"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JEKVC6R20",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2050",
//						"y": "305",
//						"outlet": {
//							"jaxId": "1JEKVCQN35",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEK9QK1K0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1JEL1LBGO0",
//					"attrs": {
//						"id": "FlagClick",
//						"viewName": "",
//						"label": "",
//						"x": "3085",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEL1RHHR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEL1RHHR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "HostFunction",
//						"flag": "$WaitFlag",
//						"query": "",
//						"queryHint": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JEL1RHHH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEL1N6LU0"
//						},
//						"timeout": "5000"
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JEL1N6LU0",
//					"attrs": {
//						"id": "AwaitClick",
//						"viewName": "",
//						"label": "",
//						"x": "3305",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEL1RHHR2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEL1RHHR3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JEL1RHHH2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEIBIFC20"
//						},
//						"catchlet": {
//							"jaxId": "1JEL1RHHH1",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEJ8MOM50"
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JEL5KG7F0",
//					"attrs": {
//						"id": "GotoRetry",
//						"viewName": "",
//						"label": "",
//						"x": "2880",
//						"y": "660",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JEJ8MOM50",
//						"outlet": {
//							"jaxId": "1JEL5MBNG0",
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
//					"jaxId": "1JELU43JD0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2765",
//						"y": "200",
//						"outlet": {
//							"jaxId": "1JELU4HBV0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEIBE6BC0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JELU5PUA0",
//					"attrs": {
//						"id": "JumpScroll",
//						"viewName": "",
//						"label": "",
//						"x": "3800",
//						"y": "415",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JEM3EQ360",
//						"outlet": {
//							"jaxId": "1JELU6UFS1",
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
//					"def": "WebRpaActivePage",
//					"jaxId": "1JEM3EQ360",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "1375",
//						"y": "435",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEM3FAPF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEM3FAPF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":1,\"switchBack\":false}",
//						"waitBefore": "0",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1JEM3FAP70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE6KORI20"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JEN0P16D0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1470",
//						"y": "325",
//						"outlet": {
//							"jaxId": "1JEN0P8K80",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEM3EQ360"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JEN0QMKI0",
//					"attrs": {
//						"id": "Back2App",
//						"viewName": "",
//						"label": "",
//						"x": "2135",
//						"y": "520",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEN0RU7K0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEN0RU7K1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JEN0RU7A0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEIB2I4A0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JEN0SIIO0",
//					"attrs": {
//						"id": "Back2App2",
//						"viewName": "",
//						"label": "",
//						"x": "2135",
//						"y": "435",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEN0T1LB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEN0T1LB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JEN0T1L30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEJHUALT0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaActivePage",
//					"jaxId": "1JEQR5IG50",
//					"attrs": {
//						"id": "ViewPage",
//						"viewName": "",
//						"label": "",
//						"x": "630",
//						"y": "230",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEQR9Q4I0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEQR9Q4I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true,\"switchBack\":true}",
//						"waitBefore": "0",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1JEQR9Q480",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEJHDJHA0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":false,\"isChatApi\":1,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\",\"kind\":\"rpa\",\"capabilities\":[\"showMore\"],\"filters\":[],\"metrics\":{\"quality\":\"\",\"costPerCall\":\"\",\"costPer1M\":\"\",\"speed\":\"\",\"size\":\"\"},\"meta\":\"\"}"
//	}
//}