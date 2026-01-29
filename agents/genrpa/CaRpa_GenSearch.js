//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JE5HADIA0MoreImports*/
import {urlToJsonName,readJson,saveJson,resolveUrl,buildRpaMicroDeciderPrompt,readRule,saveRule} from "./utils.js";
/*}#1JE5HADIA0MoreImports*/
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
		"search":{
			"name":"search","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"searchNum":{
			"name":"searchNum","type":"integer",
			"defaultValue":0,
			"desc":"",
		},
		"waitAfter":{
			"name":"waitAfter","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"opts":{
			"name":"opts","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JE5HADIA0ArgsView*/
	/*}#1JE5HADIA0ArgsView*/
};

/*#{1JE5HADIA0StartDoc*/
/*}#1JE5HADIA0StartDoc*/
//----------------------------------------------------------------------------
let CaRpa_GenSearch=async function(session){
	let pageRef,url,profile,search,searchNum,waitAfter,opts;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,CheckRule,FindClick,ReadPage,FindSearch,ClickSearch,InputSearch,AwaitNav,WaitNav,ReadList,Success,FinDone,FinFailed,WaitAfter,PressEnter,FinNoSearch,CheckNewRule,SaveRule,GotoPage,FinTimeout,Blockers,FailBlcocked,QuerySelector,CheckSelector;
	let usedRule=null;
	let wrongSelectors=[];
	let searchOpts=undefined;
	
	/*#{1JE5HADIA0LocalVals*/
	/*}#1JE5HADIA0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			url=input.url;
			profile=input.profile;
			search=input.search;
			searchNum=input.searchNum;
			waitAfter=input.waitAfter;
			opts=input.opts;
		}else{
			pageRef=undefined;
			url=undefined;
			profile=undefined;
			search=undefined;
			searchNum=undefined;
			waitAfter=undefined;
			opts=undefined;
		}
		/*#{1JE5HADIA0ParseArgs*/
		searchOpts=opts||{};
		/*}#1JE5HADIA0ParseArgs*/
	}
	
	/*#{1JE5HADIA0PreContext*/
	/*}#1JE5HADIA0PreContext*/
	context={
		searchResult: "",
		/*#{1JE5HADIA5ExCtxAttrs*/
		/*}#1JE5HADIA5ExCtxAttrs*/
	};
	/*#{1JE5HADIA0PostContext*/
	/*}#1JE5HADIA0PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JE5JK3AB0
		let result=true;
		let aiQuery=true;
		let $alias=profile;
		let $url=url;
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JE5JK3AB0"));
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
		return {seg:Blockers,result:(result),preSeg:"1JE5JK3AB0",outlet:"1JE5JK3AB3"};
	};
	StartRpa.jaxId="1JE5JK3AB0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["CheckRule"]=CheckRule=async function(input){//:1JE5JN9BL0
		let result=input;
		/*#{1JE5JN9BL0Start*/
		let rule;
		if(input?.status==="done" && !input.blocker){
			rule=await readRule(session,context.aaPage,"search.input");
		}
		/*}#1JE5JN9BL0Start*/
		if(input?.status!=="done" || !!input.blocker){
			return {seg:FailBlcocked,result:(input),preSeg:"1JE5JN9BL0",outlet:"1JG24CKED0"};
		}
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
		return {seg:QuerySelector,result:(result),preSeg:"1JE5JN9BL0",outlet:"1JE5JN9BL3"};
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
			/*#{1JE5JVJ4R1CheckItem*/
			/*}#1JE5JVJ4R1CheckItem*/
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JE5JVJ4R1ErrorCode*/
			wrongSelectors.push($query);
			/*}#1JE5JVJ4R1ErrorCode*/
		}
		/*#{1JE5JVJ4R1PostCodes*/
		result=$query;
		/*}#1JE5JVJ4R1PostCodes*/
		return {seg:ClickSearch,result:(result),preSeg:"1JE5JVJ4R1",outlet:"1JE5JVJ4S0"};
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
		return {seg:FindSearch,result:(result),preSeg:"1JE5K5CHS0",outlet:"1JE5K8RPV0"};
	};
	ReadPage.jaxId="1JE5K5CHS0"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["FindSearch"]=FindSearch=async function(input){//:1JE5K5SH60
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
		let chatMem=FindSearch.messages
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
			result=(result===null)?(await session.callSegLLM("FindSearch@"+agentURL,opts,messages,true)):result;
		}
		result=trimJSON(result);
		/*#{1JE5K5SH60PostCall*/
		/*}#1JE5K5SH60PostCall*/
		if(result && result.action && result.action.type==="selector"){
			let output=result.action.by;
			return {result:output};
		}
		if(input==="NoFind"){
			return {result:input};
		}
		/*#{1JE5K5SH60PreResult*/
		/*}#1JE5K5SH60PreResult*/
		return {result:result};
	};
	FindSearch.jaxId="1JE5K5SH60"
	FindSearch.url="FindSearch@"+agentURL
	
	segs["ClickSearch"]=ClickSearch=async function(input){//:1JE5K7TEP0
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
			return {seg:FindSearch,result:error,preSeg:"1JE5K7TEP0",outlet:null};
		}
		/*#{1JE5K7TEP0PostCodes*/
		usedRule={click:$query};
		/*}#1JE5K7TEP0PostCodes*/
		return {seg:WaitNav,result:(result),preSeg:"1JE5K7TEP0",outlet:"1JE5K8RPV3"};
	};
	ClickSearch.jaxId="1JE5K7TEP0"
	ClickSearch.url="ClickSearch@"+agentURL
	
	segs["InputSearch"]=InputSearch=async function(input){//:1JE5K89FR0
		let result=true;
		let pageVal="aaPage";
		let $action="Paste";
		let $query="";
		let $queryHint="";
		let $key=search.query||search;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		try{
			$pms=page.pasteText($key,$options||{});
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JE5K89FR0ErrorCode*/
			/*}#1JE5K89FR0ErrorCode*/
		}
		return {seg:PressEnter,result:(result),preSeg:"1JE5K89FR0",outlet:"1JE5K8RPV4"};
	};
	InputSearch.jaxId="1JE5K89FR0"
	InputSearch.url="InputSearch@"+agentURL
	
	segs["AwaitNav"]=AwaitNav=async function(input){//:1JE5KARKQ0
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
			return {seg:FinTimeout,result:(error),preSeg:"1JE5KARKQ0",outlet:"1JE5KG0AF0"};
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:ReadList,result:(result),preSeg:"1JE5KARKQ0",outlet:"1JE5KG0AF1"};
	};
	AwaitNav.jaxId="1JE5KARKQ0"
	AwaitNav.url="AwaitNav@"+agentURL
	
	segs["WaitNav"]=WaitNav=async function(input){//:1JE5KB3VD0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $query="";
		let $queryHint="";
		let $waitBefore=0;
		let $waitAfter=0;
		let $options={};
		let $timeout=15000;
		let page=context[pageVal];
		let $args=[];
		
		if($timeout){$options.timeout=$timeout;}
		$waitBefore && (await sleep($waitBefore));
		context[$flag]=page.waitForNavigation($options);
		$waitAfter && (await sleep($waitAfter))
		return {seg:InputSearch,result:(result),preSeg:"1JE5KB3VD0",outlet:"1JE5KG0AF2"};
	};
	WaitNav.jaxId="1JE5KB3VD0"
	WaitNav.url="WaitNav@"+agentURL
	
	segs["ReadList"]=ReadList=async function(input){//:1JE5KEN800
		let result;
		let arg={"pageRef":pageRef,"url":"","profile":"","waitAfter":"","read":{listTarget:"search_result",fields:["url","title"]},"minItems":"","maxItems":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenReadList.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:Success,result:(result),preSeg:"1JE5KEN800",outlet:"1JE5KG0AF3"};
	};
	ReadList.jaxId="1JE5KEN800"
	ReadList.url="ReadList@"+agentURL
	
	segs["Success"]=Success=async function(input){//:1JE5KFLIL0
		let result=input;
		if(input.items){
			let output=input.items;
			/*#{1JE5KJIBS0Codes*/
			context.searchResult=output;
			/*}#1JE5KJIBS0Codes*/
			return {seg:FinDone,result:(output),preSeg:"1JE5KFLIL0",outlet:"1JE5KJIBS0"};
		}
		return {seg:FinFailed,result:(result),preSeg:"1JE5KFLIL0",outlet:"1JE5KG0AF4"};
	};
	Success.jaxId="1JE5KFLIL0"
	Success.url="Success@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JE5KGERJ0
		let result=input
		try{
			/*#{1JE5KGERJ0Code*/
			let list,urls;;
			list=context.searchResult||[];
			if(Array.isArray(list)){
				urls=list.map((item)=>{return item.url});
				result={status:"done",value:{urls:urls,items:list}};
			}else{
				result={status:"failed",reason:"Can't find search result."};
			}
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
			result={status:"failed",reason:input&&input.reason?input.reason:"Search process failed."};
			/*}#1JE5KGM2I0Code*/
		}catch(error){
			/*#{1JE5KGM2I0ErrorCode*/
			/*}#1JE5KGM2I0ErrorCode*/
		}
		return {seg:WaitAfter,result:(result),preSeg:"1JE5KGM2I0",outlet:"1JE5KJIBS2"};
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
	
	segs["PressEnter"]=PressEnter=async function(input){//:1JE5KLMCB0
		let result=true;
		let pageVal="aaPage";
		let $action="KeyPress";
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
			$pms=page.keyboard.press($key,$options||{});
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JE5KLMCB0ErrorCode*/
			/*}#1JE5KLMCB0ErrorCode*/
		}
		return {seg:AwaitNav,result:(result),preSeg:"1JE5KLMCB0",outlet:"1JE5KM1IT0"};
	};
	PressEnter.jaxId="1JE5KLMCB0"
	PressEnter.url="PressEnter@"+agentURL
	
	segs["FinNoSearch"]=FinNoSearch=async function(input){//:1JE5KMS000
		let result=input
		try{
			/*#{1JE5KMS000Code*/
			result={status:"failed",reason:"Can't initial search。"};
			/*}#1JE5KMS000Code*/
		}catch(error){
			/*#{1JE5KMS000ErrorCode*/
			/*}#1JE5KMS000ErrorCode*/
		}
		return {result:result};
	};
	FinNoSearch.jaxId="1JE5KMS000"
	FinNoSearch.url="FinNoSearch@"+agentURL
	
	segs["CheckNewRule"]=CheckNewRule=async function(input){//:1JE5KRV8T0
		let result=input;
		if(usedRule){
			let output=input;
			return {seg:SaveRule,result:(output),preSeg:"1JE5KRV8T0",outlet:"1JE5KU7D50"};
		}
		return {result:result};
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
		return {result:result};
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
		return {seg:ReadList,result:(result),preSeg:"1JEBI23L30",outlet:"1JEBI54HP2"};
	};
	GotoPage.jaxId="1JEBI23L30"
	GotoPage.url="GotoPage@"+agentURL
	
	segs["FinTimeout"]=FinTimeout=async function(input){//:1JEHVHS0D0
		let result=input
		try{
			/*#{1JEHVHS0D0Code*/
			result = {status:"failed",reason:"Navigation timed out or did not complete in expected time."};
			/*}#1JEHVHS0D0Code*/
		}catch(error){
			/*#{1JEHVHS0D0ErrorCode*/
			/*}#1JEHVHS0D0ErrorCode*/
		}
		return {result:result};
	};
	FinTimeout.jaxId="1JEHVHS0D0"
	FinTimeout.url="FinTimeout@"+agentURL
	
	segs["Blockers"]=Blockers=async function(input){//:1JG1J7SR90
		let result;
		let arg={"pageRef":context.aaPage.pageRef,"blockers":"${clear:true}","waitAfter":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenBlockers.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JG1J7SR90Input*/
		/*}#1JG1J7SR90Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JG1J7SR90Output*/
		/*}#1JG1J7SR90Output*/
		return {seg:CheckRule,result:(result),preSeg:"1JG1J7SR90",outlet:"1JG1J9QJQ0"};
	};
	Blockers.jaxId="1JG1J7SR90"
	Blockers.url="Blockers@"+agentURL
	
	segs["FailBlcocked"]=FailBlcocked=async function(input){//:1JG24C67Q0
		let result=input
		try{
			/*#{1JG24C67Q0Code*/
			/*}#1JG24C67Q0Code*/
		}catch(error){
			/*#{1JG24C67Q0ErrorCode*/
			/*}#1JG24C67Q0ErrorCode*/
		}
		return {result:result};
	};
	FailBlcocked.jaxId="1JG24C67Q0"
	FailBlcocked.url="FailBlcocked@"+agentURL
	
	segs["QuerySelector"]=QuerySelector=async function(input){//:1JG24SM040
		let result;
		let arg={"pageRef":context.aaPage?.pageRef,"query":"点击能后输入搜索内容的HTML元素","multiSelect":"","rulePath":"search.input","cacheMode":"","opts":searchOpts};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./Util_QuerySelector.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CheckSelector,result:(result),preSeg:"1JG24SM040",outlet:"1JG24SM052"};
	};
	QuerySelector.jaxId="1JG24SM040"
	QuerySelector.url="QuerySelector@"+agentURL
	
	segs["CheckSelector"]=CheckSelector=async function(input){//:1JG2583HD0
		let result=input;
		/*#{1JG2583HD0Start*/
		let $status,$selector;
		$status=input.status.toLowerCase();
		$selector=input.value?.selector||input.selector||input.value;
		/*}#1JG2583HD0Start*/
		if($status==="done" && $selector){
			let output=$selector;
			return {seg:ClickSearch,result:(output),preSeg:"1JG2583HD0",outlet:"1JG2583HD4"};
		}
		/*#{1JG2583HD0Post*/
		result=$selector;
		/*}#1JG2583HD0Post*/
		return {seg:FinNoSearch,result:(result),preSeg:"1JG2583HD0",outlet:"1JG2583HD3"};
	};
	CheckSelector.jaxId="1JG2583HD0"
	CheckSelector.url="CheckSelector@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CaRpa_GenSearch",
		url:agentURL,
		autoStart:true,
		jaxId:"1JE5HADIA0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,url,profile,search,searchNum,waitAfter,opts}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JE5HADIA0PreEntry*/
			/*}#1JE5HADIA0PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JE5HADIA0PostEntry*/
			/*}#1JE5HADIA0PostEntry*/
			return result;
		},
		/*#{1JE5HADIA0MoreAgentAttrs*/
		/*}#1JE5HADIA0MoreAgentAttrs*/
	};
	/*#{1JE5HADIA0PostAgent*/
	/*}#1JE5HADIA0PostAgent*/
	return agent;
};
/*#{1JE5HADIA0ExCodes*/
/*}#1JE5HADIA0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CaRpa_GenSearch",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				url:{type:"auto",description:""},
				profile:{type:"auto",description:""},
				search:{type:"auto",description:""},
				searchNum:{type:"integer",description:""},
				waitAfter:{type:"auto",description:""},
				opts:{type:"auto",description:""}
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
/*#{1JE5HADIA0PostDoc*/
/*}#1JE5HADIA0PostDoc*/


export default CaRpa_GenSearch;
export{CaRpa_GenSearch,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JE5HADIA0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JE5HADIA1",
//			"attrs": {
//				"CaRpa_GenSearch": {
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
//				"search": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5JLAI30",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"searchNum": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5JMVQF0",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "0",
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
//				"opts": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JG24UTKF0",
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
//				},
//				"searchOpts": {
//					"type": "auto",
//					"valText": ""
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
//							"linkedSeg": "1JG1J7SR90"
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
//						"autoCurrentPage": "true",
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
//						"x": "590",
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
//									"jaxId": "1JG24CKED0",
//									"attrs": {
//										"id": "Blocked",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JG24CKEL0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG24CKEL1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input?.status!==\"done\" || !!input.blocker"
//									},
//									"linkedSeg": "1JG24C67Q0"
//								},
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
//						"x": "830",
//						"y": "420",
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
//									}
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
//						"x": "1055",
//						"y": "845",
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
//						"id": "FindSearch",
//						"viewName": "",
//						"label": "",
//						"x": "1315",
//						"y": "845",
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
//							}
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
//									}
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
//									}
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
//						"id": "ClickSearch",
//						"viewName": "",
//						"label": "",
//						"x": "1590",
//						"y": "405",
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
//							"linkedSeg": "1JE5KB3VD0"
//						},
//						"errorSeg": "1JE5K5SH60",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1JE5K89FR0",
//					"attrs": {
//						"id": "InputSearch",
//						"viewName": "",
//						"label": "",
//						"x": "2095",
//						"y": "405",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5K8RQ30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5K8RQ31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Paste",
//						"query": "",
//						"queryHint": "",
//						"key": "#search.query||search",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE5K8RPV4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5KLMCB0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JE5KARKQ0",
//					"attrs": {
//						"id": "AwaitNav",
//						"viewName": "",
//						"label": "",
//						"x": "2570",
//						"y": "405",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5KG0AI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KG0AI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE5KG0AF1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5KEN800"
//						},
//						"catchlet": {
//							"jaxId": "1JE5KG0AF0",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEHVHS0D0"
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1JE5KB3VD0",
//					"attrs": {
//						"id": "WaitNav",
//						"viewName": "",
//						"label": "",
//						"x": "1845",
//						"y": "405",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5KG0AI2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KG0AI3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Navigate",
//						"flag": "$WaitFlag",
//						"query": "",
//						"queryHint": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE5KG0AF2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5K89FR0"
//						},
//						"timeout": "15000"
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JE5KEN800",
//					"attrs": {
//						"id": "ReadList",
//						"viewName": "",
//						"label": "",
//						"x": "2830",
//						"y": "390",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5KG0AI4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KG0AI5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenReadList.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"url\":\"\",\"profile\":\"\",\"waitAfter\":\"\",\"read\":\"#{listTarget:\\\"search_result\\\",fields:[\\\"url\\\",\\\"title\\\"]}\",\"minItems\":\"\",\"maxItems\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JE5KG0AF3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5KFLIL0"
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
//					"jaxId": "1JE5KFLIL0",
//					"attrs": {
//						"id": "Success",
//						"viewName": "",
//						"label": "",
//						"x": "3060",
//						"y": "390",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5KG0AI6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KG0AI7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5KG0AF4",
//							"attrs": {
//								"id": "Failed",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE5KGM2I0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE5KJIBS0",
//									"attrs": {
//										"id": "Sucess",
//										"desc": "输出节点。",
//										"output": "#input.items",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JE5KJIBV0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE5KJIBV1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.items"
//									},
//									"linkedSeg": "1JE5KGERJ0"
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
//					"jaxId": "1JE5KGERJ0",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "3300",
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
//						"x": "3300",
//						"y": "435",
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
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JE5KJ1SM0",
//					"attrs": {
//						"id": "WaitAfter",
//						"viewName": "",
//						"label": "",
//						"x": "3550",
//						"y": "390",
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
//					"def": "AAFKeyboardAction",
//					"jaxId": "1JE5KLMCB0",
//					"attrs": {
//						"id": "PressEnter",
//						"viewName": "",
//						"label": "",
//						"x": "2335",
//						"y": "405",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5KM1J00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5KM1J01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Key Press",
//						"query": "",
//						"queryHint": "",
//						"key": "Enter",
//						"async": "false",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE5KM1IT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5KARKQ0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JE5KMS000",
//					"attrs": {
//						"id": "FinNoSearch",
//						"viewName": "",
//						"label": "",
//						"x": "1590",
//						"y": "550",
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
//						"x": "3115",
//						"y": "240",
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
//							}
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
//						"x": "3415",
//						"y": "225",
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
//					"def": "WebRpaPageGoto",
//					"jaxId": "1JEBI23L30",
//					"attrs": {
//						"id": "GotoPage",
//						"viewName": "",
//						"label": "",
//						"x": "830",
//						"y": "325",
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
//							},
//							"linkedSeg": "1JEIB09JI0"
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
//						"x": "830",
//						"y": "535",
//						"outlet": {
//							"jaxId": "1JEBIR1UR2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG24SM040"
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
//						"x": "1250",
//						"y": "405",
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
//					"def": "code",
//					"jaxId": "1JEHVHS0D0",
//					"attrs": {
//						"id": "FinTimeout",
//						"viewName": "",
//						"label": "",
//						"x": "2830",
//						"y": "510",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JEHVI2LB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEHVI2LB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEHVI2L70",
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
//					"jaxId": "1JEIB09JI0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2685",
//						"y": "325",
//						"outlet": {
//							"jaxId": "1JEIB1A7B0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5KEN800"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JG1J7SR90",
//					"attrs": {
//						"id": "Blockers",
//						"viewName": "",
//						"label": "",
//						"x": "355",
//						"y": "405",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JG1J9QJU0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG1J9QJU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenBlockers.js",
//						"argument": "{\"pageRef\":\"#context.aaPage.pageRef\",\"blockers\":\"${clear:true}\",\"waitAfter\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JG1J9QJQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5JN9BL0"
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
//					"jaxId": "1JG24C67Q0",
//					"attrs": {
//						"id": "FailBlcocked",
//						"viewName": "",
//						"label": "",
//						"x": "830",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JG24CKEL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG24CKEL3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG24CKEF0",
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
//					"jaxId": "1JG24SM040",
//					"attrs": {
//						"id": "QuerySelector",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "535",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JG24SM050",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG24SM051",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Util_QuerySelector.js",
//						"argument": "{\"pageRef\":\"#context.aaPage?.pageRef\",\"query\":\"点击能后输入搜索内容的HTML元素\",\"multiSelect\":\"\",\"rulePath\":\"search.input\",\"cacheMode\":\"\",\"opts\":\"#searchOpts\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JG24SM052",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG2583HD0"
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
//					"jaxId": "1JG2583HD0",
//					"attrs": {
//						"id": "CheckSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1325",
//						"y": "535",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JG2583HD1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG2583HD2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JG2583HD3",
//							"attrs": {
//								"id": "Failed",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE5KMS000"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JG2583HD4",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "#$selector",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JG2583HD5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JG2583HD6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#$status===\"done\" && $selector"
//									},
//									"linkedSeg": "1JE5K7TEP0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":false,\"isChatApi\":1,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\",\"kind\":\"rpa\",\"capabilities\":[\"search\",\"search.keyword\",\"searchNum\"],\"filters\":[{\"key\":\"domain\",\"value\":\"*\"}],\"metrics\":{\"quality\":6.5,\"costPerCall\":0.1,\"costPer1M\":\"\",\"speed\":6,\"size\":0},\"meta\":\"\"}"
//	}
//}