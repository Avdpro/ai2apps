//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1IHCHS17T0MoreImports*/
import axios from 'axios';
/*}#1IHCHS17T0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"search":{
			"name":"search","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"要搜索的文本，注意文本应该尽量适合搜索。",
		},
		"top_k":{
			"name":"top_k","type":"integer",
			"required":false,
			"defaultValue":3,
			"desc":"要读取的搜索结果网页数量",
		},
		"linkOnly":{
			"name":"linkOnly","type":"bool",
			"required":false,
			"defaultValue":"",
			"desc":"是否只需要搜索到的网页链接列表，而不需要读取搜索到的页面内的内容。",
		}
	},
	/*#{1IHCHS17T0ArgsView*/
	/*}#1IHCHS17T0ArgsView*/
};

/*#{1IHCHS17T0StartDoc*/

async function googleSearch(query,apiKey,cx,proxies) {
	const API_KEY = apiKey;
	const CX = cx;
	const url = `https://www.googleapis.com/customsearch/v1?key=${API_KEY}&cx=${CX}&q=${query}`;
	try {
		let response;
		if(proxies && proxies.ip && proxies.port){
			response = await axios.get(url,{
			proxy: {
				protocol: "http",
				host: proxies.ip,
				port: proxies.port
			}
			});
		}else{
			response = await axios.get(url);
		}
		const data = await response.data;
		if (data.items) {
			return data.items.map((item)=>{
				return item.link;
			});
		}else{
			return null;
		}
	} catch (error) {
		return null;
	}
}
/*}#1IHCHS17T0StartDoc*/
//----------------------------------------------------------------------------
let RpaWebSearch=async function(session){
	let search,top_k,linkOnly;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,TryCatch,StartRPA,HandleError,NoRPA,OpenBrowser,OpenPage,ClickInput,TypeSearch,FlagNavi,PressEnter,WaitNavi,ReadSearch,SearchError,FindUrls,LoopUrls,OpenUrl,ReadPage,CheckResult,CheckContent,SaveContent,IgnorePage2,Summary,CheckUrls,AskCheck,TryAgain,UserAbort,TryPage,NextPage,CloseSearch,CheckPage,CloseErrorPage,CloseLoopPage,CheckApiKey,TryApi,CallSearchApi,TipUseRpa,TipNoApiKey,OpenBrowser2,TipPage,TipStart,CheckPageContent,IgnorePage,CheckLinkOnly,ReturnLinks,CheckLinkOnly2,ReturnLinks2,CloseBrowser,CloseBrowser2,JumpClose,JumpClose2,AsyncLoop,AsyncTryPage,AsyncTipPage,AsyncCheckPage,AsyncCloseErrorPage,AsyncNextPage,AsyncOpenUrl,AsyncReadPage,AsyncCloseLoopPage,LoopContents,AsyncCheckPageContent,AsyncReadContent,AsyncCheckContent,AsyncCheckFinish,AsyncSummary,AsyncCloseBrowser;
	let searchApiKey="";
	let searchUrls=null;
	let searchResults=[];
	let readingUrl="";
	let pageContents={};
	let usefulPages=0;
	let searchSummary="";
	
	/*#{1IHCHS17T0LocalVals*/
	/*}#1IHCHS17T0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			search=input.search;
			top_k=input.top_k;
			linkOnly=input.linkOnly;
		}else{
			search=undefined;
			top_k=undefined;
			linkOnly=undefined;
		}
		/*#{1IHCHS17T0ParseArgs*/
		/*}#1IHCHS17T0ParseArgs*/
	}
	
	/*#{1IHCHS17T0PreContext*/
	/*}#1IHCHS17T0PreContext*/
	context={};
	/*#{1IHCHS17T0PostContext*/
	/*}#1IHCHS17T0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IHCKI9BO0
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(search===undefined || search==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:TipStart,result:(result),preSeg:"1IHCKI9BO0",outlet:"1IHCKJ60E0"};
	};
	FixArgs.jaxId="1IHCKI9BO0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["TryCatch"]=TryCatch=async function(input){//:1ILPRD97O0
		let result=input;
		/*#{1ILPRD97O0Code*/
		false
		/*}#1ILPRD97O0Code*/
		return {seg:StartRPA,result:(result),preSeg:"1ILPRD97O0",outlet:"1ILPRDVGB0",catchSeg:HandleError,catchlet:"1ILPRI2NT0"};
	};
	TryCatch.jaxId="1ILPRD97O0"
	TryCatch.url="TryCatch@"+agentURL
	
	segs["StartRPA"]=StartRPA=async function(input){//:1ILPREJOP0
		let result=true;
		let aiQuery=true;
		try{
			context.webRpa=new WebRpa(session);
			aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1ILPREJOP0"));
		}catch(err){
			return {seg:NoRPA,result:(err),preSeg:"1ILPREJOP0",outlet:"1ILPRI2NT1",catchSeg:NoRPA,catchlet:"1ILPRI2NT1"};
		}
		return {seg:CheckApiKey,result:(result),preSeg:"1ILPREJOP0",outlet:"1ILPRI2NT2"};
	};
	StartRPA.jaxId="1ILPREJOP0"
	StartRPA.url="StartRPA@"+agentURL
	
	segs["HandleError"]=HandleError=async function(input){//:1ILPRF09L0
		let result=input
		/*#{1ILPRF09L0Code*/
		result={result:"Failed",content:`Web search error: ${input}.`};
		/*}#1ILPRF09L0Code*/
		return {result:result};
	};
	HandleError.jaxId="1ILPRF09L0"
	HandleError.url="HandleError@"+agentURL
	
	segs["NoRPA"]=NoRPA=async function(input){//:1ILPRFDRO0
		let result=input
		/*#{1ILPRFDRO0Code*/
		result={result:"Failed",content:`Error: can't init Web-RPA.`};
		/*}#1ILPRFDRO0Code*/
		return {result:result};
	};
	NoRPA.jaxId="1ILPRFDRO0"
	NoRPA.url="NoRPA@"+agentURL
	
	segs["OpenBrowser"]=OpenBrowser=async function(input){//:1ILPRGHL00
		let result=true;
		let browser=null;
		let headless=false;
		let devtools=false;
		let dataDir=true;
		let alias="RPAHOME";
		let options={headless,devtools,autoDataDir:dataDir};
		/*#{1ILPRGHL00PreCodes*/
		let pptRect;
		try{
			//pptRect=await session.callClient("GetClientRect",{});
			pptRect=await session.callClient("GetToolDockRect",{});
		}catch{
			pptRect=null;
		}
		if(pptRect){
			let args;
			args=options.args;
			if(!args){
				options.args=args=[];
			}
			if((pptRect.left>=0||pptRect.x>=0) && (pptRect.top>=0||pptRect.y>=0)){
				args.push(`--window-position=${pptRect.left||pptRect.x},${pptRect.top||pptRect.y}`);
			}
			args.push(`--window-size=${pptRect.width||pptRect.w||1200},${pptRect.height||pptRect.h||800}`);
		}
		/*}#1ILPRGHL00PreCodes*/
		context.rpaBrowser=browser=await context.webRpa.openBrowser(alias,options);
		context.rpaHostPage=browser.hostPage;
		/*#{1ILPRGHL00PostCodes*/
		/*}#1ILPRGHL00PostCodes*/
		return {seg:OpenPage,result:(result),preSeg:"1ILPRGHL00",outlet:"1ILPRI2NU0"};
	};
	OpenBrowser.jaxId="1ILPRGHL00"
	OpenBrowser.url="OpenBrowser@"+agentURL
	
	segs["OpenPage"]=OpenPage=async function(input){//:1ILPRH9P30
		let pageVal="aaPage";
		let $url="https://www.google.com";
		let $waitBefore=0;
		let $waitAfter=0;
		let $width=800;
		let $height=600;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url,$openOpts);
		$waitAfter && (await sleep($waitAfter));
		return {seg:ClickInput,result:(page),preSeg:"1ILPRH9P30",outlet:"1ILPRI2NU1"};
	};
	OpenPage.jaxId="1ILPRH9P30"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["ClickInput"]=ClickInput=async function(input){//:1ILPRJKP40
		let result=true;
		let pageVal="aaPage";
		let $query="(//TEXTAREA)";
		let $queryHint="Search input";
		let $x=0;
		let $y=0;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1ILPRJKP40")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			await page.click("::-p-xpath"+$query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
		}else{
			await page.mouse.click($x,$y,$options||{});
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:TypeSearch,result:(result),preSeg:"1ILPRJKP40",outlet:"1ILPRP8EH0"};
	};
	ClickInput.jaxId="1ILPRJKP40"
	ClickInput.url="ClickInput@"+agentURL
	
	segs["TypeSearch"]=TypeSearch=async function(input){//:1ILPRM0HP0
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="";
		let $queryHint="";
		let $key=search;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1ILPRM0HP0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			await page.type("::-p-xpath"+$query,$key,$options||{});
		}else{
			await page.keyboard.type($key,$options||{});
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:FlagNavi,result:(result),preSeg:"1ILPRM0HP0",outlet:"1ILPRP8EH1"};
	};
	TypeSearch.jaxId="1ILPRM0HP0"
	TypeSearch.url="TypeSearch@"+agentURL
	
	segs["FlagNavi"]=FlagNavi=async function(input){//:1ILPRO6LH0
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
		context[$flag]=page.waitForNavigation($options);
		$waitAfter && (await sleep($waitAfter))
		return {seg:PressEnter,result:(result),preSeg:"1ILPRO6LH0",outlet:"1ILPRP8EH2"};
	};
	FlagNavi.jaxId="1ILPRO6LH0"
	FlagNavi.url="FlagNavi@"+agentURL
	
	segs["PressEnter"]=PressEnter=async function(input){//:1ILPROQPC0
		let result=true;
		let pageVal="aaPage";
		let $action="KeyPress";
		let $query="";
		let $queryHint="";
		let $key="Enter";
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		await page.keyboard.press($key,$options||{});
		$waitAfter && (await sleep($waitAfter))
		return {seg:WaitNavi,result:(result),preSeg:"1ILPROQPC0",outlet:"1ILPRP8EH3"};
	};
	PressEnter.jaxId="1ILPROQPC0"
	PressEnter.url="PressEnter@"+agentURL
	
	segs["WaitNavi"]=WaitNavi=async function(input){//:1ILPRPEG30
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			await context[$flag];
		}catch(error){
			return {seg:SearchError,result:(error),preSeg:"1ILPRPEG30",outlet:"1ILPS33ST0"};
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:ReadSearch,result:(result),preSeg:"1ILPRPEG30",outlet:"1ILPS33ST1"};
	};
	WaitNavi.jaxId="1ILPRPEG30"
	WaitNavi.url="WaitNavi@"+agentURL
	
	segs["ReadSearch"]=ReadSearch=async function(input){//:1ILPRQC4P0
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $target="cleanHTML";
		$waitBefore && (await sleep($waitBefore));
		switch($target){
			case "cleanHTML":{
				result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:true,...$options});
				break;
			}
			case "html":{
				result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:false,...$options});
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
		return {seg:FindUrls,result:(result),preSeg:"1ILPRQC4P0",outlet:"1ILPS33ST2"};
	};
	ReadSearch.jaxId="1ILPRQC4P0"
	ReadSearch.url="ReadSearch@"+agentURL
	
	segs["SearchError"]=SearchError=async function(input){//:1ILPRQRUV0
		let result=input
		/*#{1ILPRQRUV0Code*/
		result={result:"Failed",content:`Web search error: ${input}`};
		/*}#1ILPRQRUV0Code*/
		return {seg:JumpClose2,result:(result),preSeg:"1ILPRQRUV0",outlet:"1ILPS33ST3"};
	};
	SearchError.jaxId="1ILPRQRUV0"
	SearchError.url="SearchError@"+agentURL
	
	segs["FindUrls"]=FindUrls=async function(input){//:1ILPRT4DQ0
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query=".yuRUbf a:not(.fl.iUh30)";
		let $multi=true;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1ILPRT4DQ0PreCodes*/
		/*}#1ILPRT4DQ0PreCodes*/
		if($multi){
			result=await context.webRpa.queryNodes(page,$node,$query,$options);
		}else{
			result=await context.webRpa.queryNode(page,$node,$query,$options);
		}$waitAfter && (await sleep($waitAfter))
		/*#{1ILPRT4DQ0PostCodes*/
		result = result.map(link => link.attrs.href);
		searchUrls=result;
		/*}#1ILPRT4DQ0PostCodes*/
		return {seg:CheckUrls,result:(result),preSeg:"1ILPRT4DQ0",outlet:"1ILPS33ST4"};
	};
	FindUrls.jaxId="1ILPRT4DQ0"
	FindUrls.url="FindUrls@"+agentURL
	
	segs["LoopUrls"]=LoopUrls=async function(input){//:1ILPS02BB0
		let result=input;
		let list=input;
		let i,n,item,loopR;
		/*#{1ILPS02BB0PreLoop*/
		/*}#1ILPS02BB0PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1ILPS02BB0InLoopPre*/
			readingUrl=item;
			/*}#1ILPS02BB0InLoopPre*/
			loopR=await session.runAISeg(agent,TryPage,item,"1ILPS02BB0","1ILPS33ST5")
			if(loopR==="break"){
				break;
			}
			/*#{1ILPS02BB0InLoopPost*/
			/*}#1ILPS02BB0InLoopPost*/
		}
		/*#{1ILPS02BB0PostCodes*/
		/*}#1ILPS02BB0PostCodes*/
		return {seg:Summary,result:(result),preSeg:"1ILPS02BB0",outlet:"1ILPS33ST6"};
	};
	LoopUrls.jaxId="1ILPS02BB0"
	LoopUrls.url="LoopUrls@"+agentURL
	
	segs["OpenUrl"]=OpenUrl=async function(input){//:1ILPS1SK70
		let pageVal="aaPage";
		let $url=input;
		let $waitBefore=0;
		let $waitAfter=0;
		let $width=800;
		let $height=600;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url,$openOpts);
		$waitAfter && (await sleep($waitAfter));
		return {seg:ReadPage,result:(page),preSeg:"1ILPS1SK70",outlet:"1ILPS33ST7"};
	};
	OpenUrl.jaxId="1ILPS1SK70"
	OpenUrl.url="OpenUrl@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1ILPS2MVR0
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $target="article";
		$waitBefore && (await sleep($waitBefore));
		switch($target){
			case "cleanHTML":{
				result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:true,...$options});
				break;
			}
			case "html":{
				result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:false,...$options});
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
		return {seg:CloseLoopPage,result:(result),preSeg:"1ILPS2MVR0",outlet:"1ILPS33ST8"};
	};
	ReadPage.jaxId="1ILPS2MVR0"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["CheckResult"]=CheckResult=async function(input){//:1ILPS42SL0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=CheckResult.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
### 角色
你是一个判断输入的搜索的网页结果内容是否与搜索目标相关的AI

### 搜索目标
当前的搜索目标是：
${search}

### 对话
对话时用户会输入搜索到的网页内容，可能是纯文本、HTML文本或者Markdown格式。你解析并提取网页内容里与搜索目标相关的内容并以JSON格式返回。例如：
\`\`\`
//找到了相关内容：
{
	"content":"北京奥运会是2008年举行的"
}
//没有找到相关内容：
{
	"content":null
}
\`\`\`
返回JSON只有一个属性"content"：
- 当输入的内容与搜索目标相关时，"content"是你对内容根据搜索目标总结的结果。
- 当输入的内容与搜索目标无关时，设置"content"属性为null

`},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("CheckResult@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:CheckContent,result:(result),preSeg:"1ILPS42SL0",outlet:"1ILPS4F5O0"};
	};
	CheckResult.jaxId="1ILPS42SL0"
	CheckResult.url="CheckResult@"+agentURL
	
	segs["CheckContent"]=CheckContent=async function(input){//:1ILPS5NJJ0
		let result=input;
		if(input.content){
			let output=input.content;
			return {seg:SaveContent,result:(output),preSeg:"1ILPS5NJJ0",outlet:"1ILPSH2CS0"};
		}
		return {seg:IgnorePage2,result:(result),preSeg:"1ILPS5NJJ0",outlet:"1ILPSH2CS1"};
	};
	CheckContent.jaxId="1ILPS5NJJ0"
	CheckContent.url="CheckContent@"+agentURL
	
	segs["SaveContent"]=SaveContent=async function(input){//:1ILPS7HBD0
		let result=input
		/*#{1ILPS7HBD0Code*/
		searchResults.push({url:readingUrl,content:input});
		if(searchResults.length>=top_k){
			result="break";
		}
		/*}#1ILPS7HBD0Code*/
		return {result:result};
	};
	SaveContent.jaxId="1ILPS7HBD0"
	SaveContent.url="SaveContent@"+agentURL
	
	segs["IgnorePage2"]=IgnorePage2=async function(input){//:1ILPS83A00
		let result=input
		/*#{1ILPS83A00Code*/
		/*}#1ILPS83A00Code*/
		return {result:result};
	};
	IgnorePage2.jaxId="1ILPS83A00"
	IgnorePage2.url="IgnorePage2@"+agentURL
	
	segs["Summary"]=Summary=async function(input){//:1ILPS8MPC0
		let prompt;
		let result=null;
		/*#{1ILPS8MPC0Input*/
		/*}#1ILPS8MPC0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=Summary.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
### 角色
你是一个分析总结网页搜索结果的AI，根据输入的搜索结果内容的AI

### 搜索目标
当前的搜索目标是：
${search}

### 搜索结果
当前的搜索网页并初步总结的结果，用JSON格式表达为：

${JSON.stringify(searchResults,null,"\t")}


`},
		];
		/*#{1ILPS8MPC0PrePrompt*/
		/*}#1ILPS8MPC0PrePrompt*/
		prompt="请根据搜索结果，回答搜索问题";
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1ILPS8MPC0FilterMessage*/
			/*}#1ILPS8MPC0FilterMessage*/
			messages.push(msg);
		}
		/*#{1ILPS8MPC0PreCall*/
		/*}#1ILPS8MPC0PreCall*/
		result=(result===null)?(await session.callSegLLM("Summary@"+agentURL,opts,messages,true)):result;
		/*#{1ILPS8MPC0PostCall*/
		result={result:"Finish",content:result};
		/*}#1ILPS8MPC0PostCall*/
		return {seg:CloseBrowser2,result:(result),preSeg:"1ILPS8MPC0",outlet:"1ILPSH2CS4"};
	};
	Summary.jaxId="1ILPS8MPC0"
	Summary.url="Summary@"+agentURL
	
	segs["CheckUrls"]=CheckUrls=async function(input){//:1ILQ5Q6DE0
		let result=input;
		if(input&&input.length>0){
			let output=input;
			return {seg:CloseSearch,result:(output),preSeg:"1ILQ5Q6DE0",outlet:"1ILQ60KIH0"};
		}
		return {seg:AskCheck,result:(result),preSeg:"1ILQ5Q6DE0",outlet:"1ILQ60KIH1"};
	};
	CheckUrls.jaxId="1ILQ5Q6DE0"
	CheckUrls.url="CheckUrls@"+agentURL
	
	segs["AskCheck"]=AskCheck=async function(input){//:1ILQ5S0920
		let prompt=((($ln==="CN")?("没有找到正确的搜索结果，可能遇到真人识别/登陆等问题，请帮助解决问题后再次尝试"):("No correct search results found. There might be issues with human recognition/login. Please help resolve the issue and try again.")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"问题已处理，网页内已包含搜索结果，再次尝试",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"遇到问题，无法获得搜索结果，放弃本次搜索",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:TryAgain,result:(result),preSeg:"1ILQ5S0920",outlet:"1ILQ5S08M0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:TryAgain,result:(result),preSeg:"1ILQ5S0920",outlet:"1ILQ5S08M0"};
		}else if(item.code===1){
			return {seg:UserAbort,result:(result),preSeg:"1ILQ5S0920",outlet:"1ILQ5S08M1"};
		}
		return {result:result};
	};
	AskCheck.jaxId="1ILQ5S0920"
	AskCheck.url="AskCheck@"+agentURL
	
	segs["TryAgain"]=TryAgain=async function(input){//:1ILQ5VJ8Q0
		let result=input;
		return {seg:ReadSearch,result:result,preSeg:"1ILPRQC4P0",outlet:"1ILQ60KII1"};
	
	};
	TryAgain.jaxId="1ILPRQC4P0"
	TryAgain.url="TryAgain@"+agentURL
	
	segs["UserAbort"]=UserAbort=async function(input){//:1ILQ62B570
		let result=input
		/*#{1ILQ62B570Code*/
		result={result:"Abort",content:`Can't get search result, user aborted.`};
		/*}#1ILQ62B570Code*/
		return {seg:JumpClose,result:(result),preSeg:"1ILQ62B570",outlet:"1ILQ63DP20"};
	};
	UserAbort.jaxId="1ILQ62B570"
	UserAbort.url="UserAbort@"+agentURL
	
	segs["TryPage"]=TryPage=async function(input){//:1ILQ7PRKL0
		let result=input;
		/*#{1ILQ7PRKL0Code*/
		context["aaPage"]=null;
		/*}#1ILQ7PRKL0Code*/
		return {seg:TipPage,result:(result),preSeg:"1ILQ7PRKL0",outlet:"1ILQ7S47S0",catchSeg:CheckPage,catchlet:"1ILQ7S47S1"};
	};
	TryPage.jaxId="1ILQ7PRKL0"
	TryPage.url="TryPage@"+agentURL
	
	segs["NextPage"]=NextPage=async function(input){//:1ILQ7QFH70
		let result=input
		/*#{1ILQ7QFH70Code*/
		/*}#1ILQ7QFH70Code*/
		return {result:result};
	};
	NextPage.jaxId="1ILQ7QFH70"
	NextPage.url="NextPage@"+agentURL
	
	segs["CloseSearch"]=CloseSearch=async function(input){//:1ILQ9NEEU0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		return {seg:CheckLinkOnly,result:(result),preSeg:"1ILQ9NEEU0",outlet:"1ILQ9P5BK0"};
	};
	CloseSearch.jaxId="1ILQ9NEEU0"
	CloseSearch.url="CloseSearch@"+agentURL
	
	segs["CheckPage"]=CheckPage=async function(input){//:1ILQ9SL9V0
		let result=input;
		if(!!context.aaPage){
			return {seg:CloseErrorPage,result:(input),preSeg:"1ILQ9SL9V0",outlet:"1ILQ9ULAR0"};
		}
		return {seg:NextPage,result:(result),preSeg:"1ILQ9SL9V0",outlet:"1ILQ9ULAR1"};
	};
	CheckPage.jaxId="1ILQ9SL9V0"
	CheckPage.url="CheckPage@"+agentURL
	
	segs["CloseErrorPage"]=CloseErrorPage=async function(input){//:1ILQ9TPKF0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		return {result:result};
	};
	CloseErrorPage.jaxId="1ILQ9TPKF0"
	CloseErrorPage.url="CloseErrorPage@"+agentURL
	
	segs["CloseLoopPage"]=CloseLoopPage=async function(input){//:1ILQA032A0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		return {seg:CheckPageContent,result:(result),preSeg:"1ILQA032A0",outlet:"1ILQA1C6I0"};
	};
	CloseLoopPage.jaxId="1ILQA032A0"
	CloseLoopPage.url="CloseLoopPage@"+agentURL
	
	segs["CheckApiKey"]=CheckApiKey=async function(input){//:1ILQJR3OG0
		let result=input;
		/*#{1ILQJR3OG0Start*/
		let hubJSON,apis;
		hubJSON=session.agentNode.hubJSON;
		if(hubJSON){
			apis=hubJSON.api_keys;
			if(apis){
				searchApiKey=apis.google_search;
			}
		}
		/*}#1ILQJR3OG0Start*/
		if(searchApiKey){
			/*#{1ILQK3OCK0Codes*/
			/*}#1ILQK3OCK0Codes*/
			return {seg:TryApi,result:(input),preSeg:"1ILQJR3OG0",outlet:"1ILQK3OCK0"};
		}
		/*#{1ILQJR3OG0Post*/
		/*}#1ILQJR3OG0Post*/
		return {seg:TipNoApiKey,result:(result),preSeg:"1ILQJR3OG0",outlet:"1ILQK3OCK1"};
	};
	CheckApiKey.jaxId="1ILQJR3OG0"
	CheckApiKey.url="CheckApiKey@"+agentURL
	
	segs["TryApi"]=TryApi=async function(input){//:1ILQJT0JN0
		let result=input;
		/*#{1ILQJT0JN0Code*/
		/*}#1ILQJT0JN0Code*/
		return {seg:CallSearchApi,result:(result),preSeg:"1ILQJT0JN0",outlet:"1ILQK3OCK2",catchSeg:TipUseRpa,catchlet:"1ILQK3OCK3"};
	};
	TryApi.jaxId="1ILQJT0JN0"
	TryApi.url="TryApi@"+agentURL
	
	segs["CallSearchApi"]=CallSearchApi=async function(input){//:1ILQJTSGU0
		let result=input
		/*#{1ILQJTSGU0Code*/
		let links;
		let hubJSON;
		hubJSON=session.agentNode.hubJSON;
		links=await googleSearch(search,searchApiKey.key,searchApiKey.cx,hubJSON.proxies);
		if(!links ||!links.length){
			throw "No links found.";
		}
		result=links;
		/*}#1ILQJTSGU0Code*/
		return {seg:CheckLinkOnly2,result:(result),preSeg:"1ILQJTSGU0",outlet:"1ILQK3OCK4"};
	};
	CallSearchApi.jaxId="1ILQJTSGU0"
	CallSearchApi.url="CallSearchApi@"+agentURL
	
	segs["TipUseRpa"]=TipUseRpa=async function(input){//:1ILQJU6R50
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=`调用Google Search API时发生错误:  ${input}。转用Web-RPA模式进行搜索。`;
		session.addChatText(role,content,opts);
		return {seg:OpenBrowser,result:(result),preSeg:"1ILQJU6R50",outlet:"1ILQK3OCK5"};
	};
	TipUseRpa.jaxId="1ILQJU6R50"
	TipUseRpa.url="TipUseRpa@"+agentURL
	
	segs["TipNoApiKey"]=TipNoApiKey=async function(input){//:1ILQK304N0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=(($ln==="CN")?("没有找到Google search的API-Key，采用Web-RPA方式进行搜索。"):("No Google Search API key found, using Web-RPA method for Search."));
		session.addChatText(role,content,opts);
		return {seg:OpenBrowser,result:(result),preSeg:"1ILQK304N0",outlet:"1ILQK3OCK6"};
	};
	TipNoApiKey.jaxId="1ILQK304N0"
	TipNoApiKey.url="TipNoApiKey@"+agentURL
	
	segs["OpenBrowser2"]=OpenBrowser2=async function(input){//:1ILQTBDM90
		let result=true;
		let browser=null;
		let headless=false;
		let devtools=false;
		let dataDir=true;
		let alias="RPAHOME";
		let options={headless,devtools,autoDataDir:dataDir};
		/*#{1ILQTBDM90PreCodes*/
		let pptRect;
		try{
			//pptRect=await session.callClient("GetClientRect",{});
			pptRect=await session.callClient("GetToolDockRect",{});
		}catch{
			pptRect=null;
		}
		if(pptRect){
			let args;
			args=options.args;
			if(!args){
				options.args=args=[];
			}
			if((pptRect.left>=0||pptRect.x>=0) && (pptRect.top>=0||pptRect.y>=0)){
				args.push(`--window-position=${pptRect.left||pptRect.x},${pptRect.top||pptRect.y}`);
			}
			args.push(`--window-size=${pptRect.width||pptRect.w||1200},${pptRect.height||pptRect.h||800}`);
		}
		/*}#1ILQTBDM90PreCodes*/
		context.rpaBrowser=browser=await context.webRpa.openBrowser(alias,options);
		context.rpaHostPage=browser.hostPage;
		/*#{1ILQTBDM90PostCodes*/
		result=input;
		/*}#1ILQTBDM90PostCodes*/
		return {seg:CheckLinkOnly,result:(result),preSeg:"1ILQTBDM90",outlet:"1ILQTBUNR0"};
	};
	OpenBrowser2.jaxId="1ILQTBDM90"
	OpenBrowser2.url="OpenBrowser2@"+agentURL
	
	segs["TipPage"]=TipPage=async function(input){//:1ILQU5D560
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="log";
		let content=(($ln==="CN")?(`正在查看: ${input}`):/*EN*/(`Viewing: ${input}`));
		session.addChatText(role,content,opts);
		return {seg:OpenUrl,result:(result),preSeg:"1ILQU5D560",outlet:"1ILQU7PTN0"};
	};
	TipPage.jaxId="1ILQU5D560"
	TipPage.url="TipPage@"+agentURL
	
	segs["TipStart"]=TipStart=async function(input){//:1ILR0ACES0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=(($ln==="CN")?(`开始搜索：${search}`):/*EN*/(`Start searching: ${search}`));
		session.addChatText(role,content,opts);
		return {seg:TryCatch,result:(result),preSeg:"1ILR0ACES0",outlet:"1ILR0BLB20"};
	};
	TipStart.jaxId="1ILR0ACES0"
	TipStart.url="TipStart@"+agentURL
	
	segs["CheckPageContent"]=CheckPageContent=async function(input){//:1ILS7VRLH0
		let result=input;
		if(!!input){
			let output=input;
			return {seg:CheckResult,result:(output),preSeg:"1ILS7VRLH0",outlet:"1ILS82LJH0"};
		}
		return {seg:IgnorePage,result:(result),preSeg:"1ILS7VRLH0",outlet:"1ILS82LJH1"};
	};
	CheckPageContent.jaxId="1ILS7VRLH0"
	CheckPageContent.url="CheckPageContent@"+agentURL
	
	segs["IgnorePage"]=IgnorePage=async function(input){//:1ILS81QP10
		let result=input
		/*#{1ILS81QP10Code*/
		/*}#1ILS81QP10Code*/
		return {result:result};
	};
	IgnorePage.jaxId="1ILS81QP10"
	IgnorePage.url="IgnorePage@"+agentURL
	
	segs["CheckLinkOnly"]=CheckLinkOnly=async function(input){//:1ILSN40IP0
		let result=input;
		if(linkOnly){
			let output=input;
			return {seg:ReturnLinks,result:(output),preSeg:"1ILSN40IP0",outlet:"1ILSN6TI40"};
		}
		result=input;
		return {seg:AsyncLoop,result:(result),preSeg:"1ILSN40IP0",outlet:"1ILSN6TI41"};
	};
	CheckLinkOnly.jaxId="1ILSN40IP0"
	CheckLinkOnly.url="CheckLinkOnly@"+agentURL
	
	segs["ReturnLinks"]=ReturnLinks=async function(input){//:1ILSN672K0
		let result=input
		/*#{1ILSN672K0Code*/
		result={result:"Finish",content:input};
		/*}#1ILSN672K0Code*/
		return {seg:CloseBrowser,result:(result),preSeg:"1ILSN672K0",outlet:"1ILSN6TI42"};
	};
	ReturnLinks.jaxId="1ILSN672K0"
	ReturnLinks.url="ReturnLinks@"+agentURL
	
	segs["CheckLinkOnly2"]=CheckLinkOnly2=async function(input){//:1IM98KOBT0
		let result=input;
		if(linkOnly){
			let output=input;
			return {seg:ReturnLinks2,result:(output),preSeg:"1IM98KOBT0",outlet:"1IM98KOBU3"};
		}
		result=input;
		return {seg:OpenBrowser2,result:(result),preSeg:"1IM98KOBT0",outlet:"1IM98KOBU2"};
	};
	CheckLinkOnly2.jaxId="1IM98KOBT0"
	CheckLinkOnly2.url="CheckLinkOnly2@"+agentURL
	
	segs["ReturnLinks2"]=ReturnLinks2=async function(input){//:1IM98LRN90
		let result=input
		/*#{1IM98LRN90Code*/
		result={result:"Finish",content:input};
		/*}#1IM98LRN90Code*/
		return {result:result};
	};
	ReturnLinks2.jaxId="1IM98LRN90"
	ReturnLinks2.url="ReturnLinks2@"+agentURL
	
	segs["CloseBrowser"]=CloseBrowser=async function(input){//:1IM98O14D0
		let result=input;
		let browser=context.rpaBrowser;
		if(browser){
			await context.webRpa.closeBrowser(browser);
		}
		context.rpaBrowser=null;
		context.rpaHostPage=null;
		return {result:result};
	};
	CloseBrowser.jaxId="1IM98O14D0"
	CloseBrowser.url="CloseBrowser@"+agentURL
	
	segs["CloseBrowser2"]=CloseBrowser2=async function(input){//:1IM98OJJK0
		let result=input;
		let browser=context.rpaBrowser;
		if(browser){
			await context.webRpa.closeBrowser(browser);
		}
		context.rpaBrowser=null;
		context.rpaHostPage=null;
		return {result:result};
	};
	CloseBrowser2.jaxId="1IM98OJJK0"
	CloseBrowser2.url="CloseBrowser2@"+agentURL
	
	segs["JumpClose"]=JumpClose=async function(input){//:1IM98ROVI0
		let result=input;
		return {seg:CloseBrowser2,result:result,preSeg:"1IM98OJJK0",outlet:"1IM98S99B0"};
	
	};
	JumpClose.jaxId="1IM98OJJK0"
	JumpClose.url="JumpClose@"+agentURL
	
	segs["JumpClose2"]=JumpClose2=async function(input){//:1IM98TTCN0
		let result=input;
		return {seg:CloseBrowser2,result:result,preSeg:"1IM98OJJK0",outlet:"1IM98VLT00"};
	
	};
	JumpClose2.jaxId="1IM98OJJK0"
	JumpClose2.url="JumpClose2@"+agentURL
	
	segs["AsyncLoop"]=AsyncLoop=async function(input){//:1INRKIURH0
		let result;
		let tasks=[];
		let list=input;
		let i,n,item,loopR;
		/*#{1INRKIURH0PreLoop*/
		input=[input[0]];
		/*}#1INRKIURH0PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1INRKIURH0InLoopPre*/
			/*}#1INRKIURH0InLoopPre*/
			tasks.push(session.runAISeg(agent,AsyncTryPage,item,"1INRKIURH0","1INRKJDT52"));
			/*#{1INRKIURH0InLoopPost*/
			/*}#1INRKIURH0InLoopPost*/
		}
		result=await Promise.all(tasks);
		/*#{1INRKIURH0PostCodes*/
		/*}#1INRKIURH0PostCodes*/
		return {seg:AsyncCloseBrowser,result:(result),preSeg:"1INRKIURH0",outlet:"1INRKJDT00"};
	};
	AsyncLoop.jaxId="1INRKIURH0"
	AsyncLoop.url="AsyncLoop@"+agentURL
	
	segs["AsyncTryPage"]=AsyncTryPage=async function(input){//:1INRKM9HN0
		let result=input;
		/*#{1INRKM9HN0Code*/
		true
		/*}#1INRKM9HN0Code*/
		return {seg:AsyncTipPage,result:(result),preSeg:"1INRKM9HN0",outlet:"1INRKMKDK0",catchSeg:AsyncCheckPage,catchlet:"1INRKMKDQ2"};
	};
	AsyncTryPage.jaxId="1INRKM9HN0"
	AsyncTryPage.url="AsyncTryPage@"+agentURL
	
	segs["AsyncTipPage"]=AsyncTipPage=async function(input){//:1INRKNSM30
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="log";
		let content=(($ln==="CN")?(`正在查看: ${input}`):/*EN*/(`Viewing: ${input}`));
		session.addChatText(role,content,opts);
		return {seg:AsyncOpenUrl,result:(result),preSeg:"1INRKNSM30",outlet:"1INRKNSM42"};
	};
	AsyncTipPage.jaxId="1INRKNSM30"
	AsyncTipPage.url="AsyncTipPage@"+agentURL
	
	segs["AsyncCheckPage"]=AsyncCheckPage=async function(input){//:1INRKPKVI0
		let result=input;
		if(context["Page_"+input]){
			let output=input;
			return {seg:AsyncCloseErrorPage,result:(output),preSeg:"1INRKPKVI0",outlet:"1INRL2ESR0"};
		}
		return {seg:AsyncNextPage,result:(result),preSeg:"1INRKPKVI0",outlet:"1INRL2ESR1"};
	};
	AsyncCheckPage.jaxId="1INRKPKVI0"
	AsyncCheckPage.url="AsyncCheckPage@"+agentURL
	
	segs["AsyncCloseErrorPage"]=AsyncCloseErrorPage=async function(input){//:1INRKRLU40
		let result=input;
		let pageVal="Page_"+input;
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		/*#{1INRKRLU40PreCodes*/
		/*}#1INRKRLU40PreCodes*/
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		/*#{1INRKRLU40PostCodes*/
		/*}#1INRKRLU40PostCodes*/
		return {result:result};
	};
	AsyncCloseErrorPage.jaxId="1INRKRLU40"
	AsyncCloseErrorPage.url="AsyncCloseErrorPage@"+agentURL
	
	segs["AsyncNextPage"]=AsyncNextPage=async function(input){//:1INRKTGQ70
		let result=input
		/*#{1INRKTGQ70Code*/
		/*}#1INRKTGQ70Code*/
		return {result:result};
	};
	AsyncNextPage.jaxId="1INRKTGQ70"
	AsyncNextPage.url="AsyncNextPage@"+agentURL
	
	segs["AsyncOpenUrl"]=AsyncOpenUrl=async function(input){//:1INRL10TH0
		let pageVal="Page_"+input;
		let $url=input;
		let $waitBefore=0;
		let $waitAfter=0;
		let $width=800;
		let $height=600;
		let $userAgent="";
		let $timeout=(5000)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		/*#{1INRL10TH0PreCodes*/
		/*}#1INRL10TH0PreCodes*/
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url,$openOpts);
		$waitAfter && (await sleep($waitAfter));
		/*#{1INRL10TH0PostCodes*/
		page=input;
		/*}#1INRL10TH0PostCodes*/
		return {seg:AsyncReadPage,result:(page),preSeg:"1INRL10TH0",outlet:"1INRL10TH3"};
	};
	AsyncOpenUrl.jaxId="1INRL10TH0"
	AsyncOpenUrl.url="AsyncOpenUrl@"+agentURL
	
	segs["AsyncReadPage"]=AsyncReadPage=async function(input){//:1INRL50LD0
		let result=null;
		let pageVal="Page_"+input;
		let $node=null;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $target="article";
		$waitBefore && (await sleep($waitBefore));
		/*#{1INRL50LD0PreCodes*/
		/*}#1INRL50LD0PreCodes*/
		switch($target){
			case "cleanHTML":{
				result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:true,...$options});
				break;
			}
			case "html":{
				result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:false,...$options});
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
		/*#{1INRL50LD0PostCodes*/
		//Make sure next seg get url
		pageContents[input]=result;
		result=input;
		/*}#1INRL50LD0PostCodes*/
		return {seg:AsyncCloseLoopPage,result:(result),preSeg:"1INRL50LD0",outlet:"1INRL50LD3"};
	};
	AsyncReadPage.jaxId="1INRL50LD0"
	AsyncReadPage.url="AsyncReadPage@"+agentURL
	
	segs["AsyncCloseLoopPage"]=AsyncCloseLoopPage=async function(input){//:1INRL97SR0
		let result=input;
		let pageVal="Page_"+input;
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		/*#{1INRL97SR0PreCodes*/
		/*}#1INRL97SR0PreCodes*/
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		/*#{1INRL97SR0PostCodes*/
		/*}#1INRL97SR0PostCodes*/
		return {result:result};
	};
	AsyncCloseLoopPage.jaxId="1INRL97SR0"
	AsyncCloseLoopPage.url="AsyncCloseLoopPage@"+agentURL
	
	segs["LoopContents"]=LoopContents=async function(input){//:1INRLDQ370
		let result=input;
		let list=input;
		let i,n,item,loopR;
		/*#{1INRLDQ370PreLoop*/
		usefulPages=0;
		searchResults=[];
		/*}#1INRLDQ370PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1INRLDQ370InLoopPre*/
			readingUrl=item;
			/*}#1INRLDQ370InLoopPre*/
			loopR=await session.runAISeg(agent,AsyncCheckPageContent,item,"1INRLDQ370","1INRLR9410")
			if(loopR==="break"){
				break;
			}
			/*#{1INRLDQ370InLoopPost*/
			/*}#1INRLDQ370InLoopPost*/
		}
		/*#{1INRLDQ370PostCodes*/
		/*}#1INRLDQ370PostCodes*/
		return {seg:AsyncSummary,result:(result),preSeg:"1INRLDQ370",outlet:"1INRLR9411"};
	};
	LoopContents.jaxId="1INRLDQ370"
	LoopContents.url="LoopContents@"+agentURL
	
	segs["AsyncCheckPageContent"]=AsyncCheckPageContent=async function(input){//:1INRLESDV0
		let result=input;
		if(!!pageContents[input]){
			let output=`
From link: ${input}
- - -
${pageContents[input]}
`;
			return {seg:AsyncReadContent,result:(output),preSeg:"1INRLESDV0",outlet:"1INRLESDV4"};
		}
		return {result:result};
	};
	AsyncCheckPageContent.jaxId="1INRLESDV0"
	AsyncCheckPageContent.url="AsyncCheckPageContent@"+agentURL
	
	segs["AsyncReadContent"]=AsyncReadContent=async function(input){//:1INRLG50O0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=AsyncReadContent.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
### 角色
你是一个判断输入的搜索的网页结果内容是否与搜索目标相关的AI

### 搜索目标
当前的搜索目标是：
${search}

### 对话
- 每轮对话时用户会输入搜索到的网页内容，可能是纯文本、HTML文本或者Markdown格式。
- 你根据用户的输入，判断用户输入的网页内容是否与回答当前的搜索目标相关，并用JSON返回，例如：
\`\`\`
//找到了相关内容：
{
    "useful":true,
}
//没有找到相关内容：
{
    "useful":false,
}
\`\`\`

### 返回JSON属性说明
"useful" {bool}: 本回合对话用户输入的内容是否对搜索目标有帮助
`},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("AsyncReadContent@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:AsyncCheckContent,result:(result),preSeg:"1INRLG50O0",outlet:"1INRLG50O3"};
	};
	AsyncReadContent.jaxId="1INRLG50O0"
	AsyncReadContent.url="AsyncReadContent@"+agentURL
	
	segs["AsyncCheckContent"]=AsyncCheckContent=async function(input){//:1INRLH17U0
		let result=input;
		if(input.useful){
			let output=input.content;
			return {seg:AsyncCheckFinish,result:(output),preSeg:"1INRLH17U0",outlet:"1INRLH17U4"};
		}
		return {result:result};
	};
	AsyncCheckContent.jaxId="1INRLH17U0"
	AsyncCheckContent.url="AsyncCheckContent@"+agentURL
	
	segs["AsyncCheckFinish"]=AsyncCheckFinish=async function(input){//:1INRLKIME0
		let result=input
		/*#{1INRLKIME0Code*/
		usefulPages+=1;
		searchResults.push({url:readingUrl,content:pageContents[readingUrl]});
		if(usefulPages>=top_k){
			result="break";
		}
		/*}#1INRLKIME0Code*/
		return {result:result};
	};
	AsyncCheckFinish.jaxId="1INRLKIME0"
	AsyncCheckFinish.url="AsyncCheckFinish@"+agentURL
	
	segs["AsyncSummary"]=AsyncSummary=async function(input){//:1INRLLTLI0
		let prompt;
		let result=null;
		/*#{1INRLLTLI0Input*/
		/*}#1INRLLTLI0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=AsyncSummary.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
### 角色
你是一个分析总结网页搜索结果的AI，根据输入的搜索结果内容的AI

### 搜索目标
当前的搜索目标是：
${search}

### 搜索结果
当前的搜索网页并初步总结的结果，用JSON格式表达为：

${JSON.stringify(searchResults,null,"\t")}


`},
		];
		/*#{1INRLLTLI0PrePrompt*/
		/*}#1INRLLTLI0PrePrompt*/
		prompt="请根据搜索结果，回答搜索问题";
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1INRLLTLI0FilterMessage*/
			/*}#1INRLLTLI0FilterMessage*/
			messages.push(msg);
		}
		/*#{1INRLLTLI0PreCall*/
		/*}#1INRLLTLI0PreCall*/
		result=(result===null)?(await session.callSegLLM("AsyncSummary@"+agentURL,opts,messages,true)):result;
		/*#{1INRLLTLI0PostCall*/
		result={result:"Finish",content:result};
		/*}#1INRLLTLI0PostCall*/
		return {result:result};
	};
	AsyncSummary.jaxId="1INRLLTLI0"
	AsyncSummary.url="AsyncSummary@"+agentURL
	
	segs["AsyncCloseBrowser"]=AsyncCloseBrowser=async function(input){//:1INRLOS0A0
		let result=input;
		let browser=context.rpaBrowser;
		/*#{1INRLOS0A0PreCodes*/
		/*}#1INRLOS0A0PreCodes*/
		if(browser){
			await context.webRpa.closeBrowser(browser);
		}
		context.rpaBrowser=null;
		context.rpaHostPage=null;
		/*#{1INRLOS0A0PostCodes*/
		/*}#1INRLOS0A0PostCodes*/
		return {seg:LoopContents,result:(result),preSeg:"1INRLOS0A0",outlet:"1INRLOS0A3"};
	};
	AsyncCloseBrowser.jaxId="1INRLOS0A0"
	AsyncCloseBrowser.url="AsyncCloseBrowser@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"RpaWebSearch",
		url:agentURL,
		autoStart:true,
		jaxId:"1IHCHS17T0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{search,top_k,linkOnly}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IHCHS17T0PreEntry*/
			/*}#1IHCHS17T0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IHCHS17T0PostEntry*/
			/*}#1IHCHS17T0PostEntry*/
			return result;
		},
		/*#{1IHCHS17T0MoreAgentAttrs*/
		/*}#1IHCHS17T0MoreAgentAttrs*/
	};
	/*#{1IHCHS17T0PostAgent*/
	/*}#1IHCHS17T0PostAgent*/
	return agent;
};
/*#{1IHCHS17T0ExCodes*/
/*}#1IHCHS17T0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "RpaWebSearch",
		description: "使用Google进行网页搜索并返回总结后的搜索结果。",
		parameters:{
			type: "object",
			properties:{
				search:{type:"string",description:"要搜索的文本，注意文本应该尽量适合搜索。"},
				top_k:{type:"integer",description:"要读取的搜索结果网页数量"},
				linkOnly:{type:"bool",description:"是否只需要搜索到的网页链接列表，而不需要读取搜索到的页面内的内容。"}
			}
		}
	},
	agentNode: "AgentBuilder",
	agentName: "RpaWebSearch.js",
	label: "{\"EN\":\"Web Search\",\"CN\":\"网络搜索\"}",
	isRPA: true,
	chatEntry: "Tool",
	icon: "/~/-tabos/shared/assets/browser.svg"
}];

//:Export Edit-AddOn:
const DocAIAgentExporter=VFACT?VFACT.classRegs.DocAIAgentExporter:null;
if(DocAIAgentExporter){
	const EditAttr=VFACT.classRegs.EditAttr;
	const EditAISeg=VFACT.classRegs.EditAISeg;
	const EditAISegOutlet=VFACT.classRegs.EditAISegOutlet;
	const SegObjShellAttr=EditAISeg.SegObjShellAttr;
	const SegOutletDef=EditAISegOutlet.SegOutletDef;
	const docAIAgentExporter=DocAIAgentExporter.prototype;
	const packExtraCodes=docAIAgentExporter.packExtraCodes;
	const packResult=docAIAgentExporter.packResult;
	const varNameRegex = /^[a-zA-Z_$][a-zA-Z0-9_$]*$/;
	
	EditAISeg.regDef({
		name:"RpaWebSearch",showName:"{\"EN\":\"Web Search\",\"CN\":\"网络搜索\"}",icon:"/~/-tabos/shared/assets/browser.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"search":{name:"search",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"top_k":{name:"top_k",showName:undefined,type:"integer",key:1,fixed:1,initVal:3},
			"linkOnly":{name:"linkOnly",showName:undefined,type:"bool",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","search","top_k","linkOnly","codes","desc"],
		desc:"使用Google进行网页搜索并返回总结后的搜索结果。"
	});
	
	DocAIAgentExporter.segTypeExporters["RpaWebSearch"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['search']=");this.genAttrStatement(seg.getAttr("search"));coder.packText(";");coder.newLine();
			coder.packText("args['top_k']=");this.genAttrStatement(seg.getAttr("top_k"));coder.packText(";");coder.newLine();
			coder.packText("args['linkOnly']=");this.genAttrStatement(seg.getAttr("linkOnly"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/RpaWebSearch.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
			this.packUpdateContext(coder,seg);
			this.packUpdateGlobal(coder,seg);
			this.packResult(coder,seg,seg.outlet);
		}
		coder.indentLess();coder.maybeNewLine();
		coder.packText(`};`);coder.newLine();
		if(exportDebug){
			coder.packText(`${segName}.jaxId="${seg.jaxId}"`);coder.newLine();
		}
		coder.packText(`${segName}.url="${segName}@"+agentURL`);coder.newLine();
		coder.newLine();
	};
}
//#CodyExport<<<
/*#{1IHCHS17T0PostDoc*/
/*}#1IHCHS17T0PostDoc*/


export default RpaWebSearch;
export{RpaWebSearch,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IHCHS17T0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IHCHS17T1",
//			"attrs": {
//				"RpaWebSearch": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IHCHS17U0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IHCHS17U1",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IHCHS17U2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IHCHS17U3",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportClass": "false"
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1IHCHS17T2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IHCHS17T3",
//			"attrs": {
//				"search": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IHCKJ60G0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要搜索的文本，注意文本应该尽量适合搜索。",
//						"required": "true"
//					}
//				},
//				"top_k": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILPRP8EL0",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "3",
//						"desc": "要读取的搜索结果网页数量",
//						"required": "false"
//					}
//				},
//				"linkOnly": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILSMVNAL0",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "\"\"",
//						"desc": "是否只需要搜索到的网页链接列表，而不需要读取搜索到的页面内的内容。",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IHCHS17T4",
//			"attrs": {
//				"searchApiKey": {
//					"type": "string",
//					"valText": ""
//				},
//				"searchUrls": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"searchResults": {
//					"type": "auto",
//					"valText": "#[]"
//				},
//				"readingUrl": {
//					"type": "string",
//					"valText": "#\"\""
//				},
//				"pageContents": {
//					"type": "auto",
//					"valText": "{}"
//				},
//				"usefulPages": {
//					"type": "int",
//					"valText": "0"
//				},
//				"searchSummary": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IHCHS17T5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IHCHS17T6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IHCKI9BO0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "50",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1IHCKJ60E0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILR0ACES0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1ILPRD97O0",
//					"attrs": {
//						"id": "TryCatch",
//						"viewName": "",
//						"label": "",
//						"x": "490",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPRI2O30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPRI2O31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILPRDVGB0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPREJOP0"
//						},
//						"catchlet": {
//							"jaxId": "1ILPRI2NT0",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRF09L0"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1ILPREJOP0",
//					"attrs": {
//						"id": "StartRPA",
//						"viewName": "",
//						"label": "",
//						"x": "705",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPRI2O32",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPRI2O33",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILPRI2NT2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILQJR3OG0"
//						},
//						"catchlet": {
//							"jaxId": "1ILPRI2NT1",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1ILPRI2O34",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1ILPRI2O35",
//									"attrs": {
//										"cast": ""
//									}
//								}
//							},
//							"linkedSeg": "1ILPRFDRO0"
//						},
//						"aiQuery": "true"
//					},
//					"icon": "start.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILPRF09L0",
//					"attrs": {
//						"id": "HandleError",
//						"viewName": "",
//						"label": "",
//						"x": "700",
//						"y": "445",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILPRI2O36",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPRI2O37",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILPRI2NT3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILPRFDRO0",
//					"attrs": {
//						"id": "NoRPA",
//						"viewName": "",
//						"label": "",
//						"x": "935",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILPRI2O38",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPRI2O39",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILPRI2NT4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenBrowser",
//					"jaxId": "1ILPRGHL00",
//					"attrs": {
//						"id": "OpenBrowser",
//						"viewName": "",
//						"label": "",
//						"x": "1475",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPRI2O310",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPRI2O311",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"alias": "RPAHOME",
//						"headless": "false",
//						"devtools": "false",
//						"dataDir": "true",
//						"outlet": {
//							"jaxId": "1ILPRI2NU0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRH9P30"
//						},
//						"run": ""
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1ILPRH9P30",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "1730",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPRI2O312",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPRI2O313",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "https://www.google.com",
//						"vpWidth": "800",
//						"vpHeight": "600",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILPRI2NU1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRJKP40"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1ILPRJKP40",
//					"attrs": {
//						"id": "ClickInput",
//						"viewName": "",
//						"label": "",
//						"x": "1955",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPRP8EL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPRP8EL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "(//TEXTAREA)",
//						"queryHint": "Search input",
//						"dx": "0",
//						"dy": "0",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILPRP8EH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRM0HP0"
//						},
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1ILPRM0HP0",
//					"attrs": {
//						"id": "TypeSearch",
//						"viewName": "",
//						"label": "",
//						"x": "2180",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPRP8EL3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPRP8EL4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Type",
//						"query": "",
//						"queryHint": "",
//						"key": "#search",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILPRP8EH1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRO6LH0"
//						},
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1ILPRO6LH0",
//					"attrs": {
//						"id": "FlagNavi",
//						"viewName": "",
//						"label": "",
//						"x": "2415",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPRP8EM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPRP8EM1",
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
//							"jaxId": "1ILPRP8EH2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPROQPC0"
//						}
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1ILPROQPC0",
//					"attrs": {
//						"id": "PressEnter",
//						"viewName": "",
//						"label": "",
//						"x": "2625",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPRP8EM2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPRP8EM3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Key Press",
//						"query": "",
//						"queryHint": "",
//						"key": "Enter",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILPRP8EH3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRPEG30"
//						},
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1ILPRPEG30",
//					"attrs": {
//						"id": "WaitNavi",
//						"viewName": "",
//						"label": "",
//						"x": "2845",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPS33T30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPS33T31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILPS33ST1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRQC4P0"
//						},
//						"catchlet": {
//							"jaxId": "1ILPS33ST0",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRQRUV0"
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1ILPRQC4P0",
//					"attrs": {
//						"id": "ReadSearch",
//						"viewName": "",
//						"label": "",
//						"x": "3060",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPS33T32",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPS33T33",
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
//							"jaxId": "1ILPS33ST2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRT4DQ0"
//						},
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILPRQRUV0",
//					"attrs": {
//						"id": "SearchError",
//						"viewName": "",
//						"label": "",
//						"x": "3060",
//						"y": "330",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILPS33T34",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPS33T35",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILPS33ST3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IM98TTCN0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1ILPRT4DQ0",
//					"attrs": {
//						"id": "FindUrls",
//						"viewName": "",
//						"label": "",
//						"x": "3295",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPS33T36",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPS33T37",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": ".yuRUbf a:not(.fl.iUh30)",
//						"queryHint": "link in the google search result page",
//						"multi": "true",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILPS33ST4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILQ5Q6DE0"
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1ILPS02BB0",
//					"attrs": {
//						"id": "LoopUrls",
//						"viewName": "",
//						"label": "",
//						"x": "4265",
//						"y": "150",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPS33T38",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPS33T39",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1ILPS33ST5",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILQ7PRKL0"
//						},
//						"catchlet": {
//							"jaxId": "1ILPS33ST6",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPS8MPC0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1ILPS1SK70",
//					"attrs": {
//						"id": "OpenUrl",
//						"viewName": "",
//						"label": "",
//						"x": "4915",
//						"y": "75",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPS33T310",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPS33T311",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "#input",
//						"vpWidth": "800",
//						"vpHeight": "600",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILPS33ST7",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPS2MVR0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1ILPS2MVR0",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "5135",
//						"y": "75",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPS33T312",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPS33T313",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"target": "Article",
//						"node": "null",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILPS33ST8",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILQA032A0"
//						},
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1ILPS42SL0",
//					"attrs": {
//						"id": "CheckResult",
//						"viewName": "",
//						"label": "",
//						"x": "5925",
//						"y": "60",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPS4F5U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPS4F5U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o-mini",
//						"system": "#`\n### 角色\n你是一个判断输入的搜索的网页结果内容是否与搜索目标相关的AI\n\n### 搜索目标\n当前的搜索目标是：\n${search}\n\n### 对话\n对话时用户会输入搜索到的网页内容，可能是纯文本、HTML文本或者Markdown格式。你解析并提取网页内容里与搜索目标相关的内容并以JSON格式返回。例如：\n\\`\\`\\`\n//找到了相关内容：\n{\n\t\"content\":\"北京奥运会是2008年举行的\"\n}\n//没有找到相关内容：\n{\n\t\"content\":null\n}\n\\`\\`\\`\n返回JSON只有一个属性\"content\"：\n- 当输入的内容与搜索目标相关时，\"content\"是你对内容根据搜索目标总结的结果。\n- 当输入的内容与搜索目标无关时，设置\"content\"属性为null\n\n`",
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
//							"jaxId": "1ILPS4F5O0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPS5NJJ0"
//						},
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILPS5NJJ0",
//					"attrs": {
//						"id": "CheckContent",
//						"viewName": "",
//						"label": "",
//						"x": "6170",
//						"y": "60",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPSH2D20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPSH2D21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILPSH2CS1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILPS83A00"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILPSH2CS0",
//									"attrs": {
//										"id": "Useful",
//										"desc": "输出节点。",
//										"output": "#input.content",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILPSH2D22",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILPSH2D23",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.content"
//									},
//									"linkedSeg": "1ILPS7HBD0"
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
//					"jaxId": "1ILPS7HBD0",
//					"attrs": {
//						"id": "SaveContent",
//						"viewName": "",
//						"label": "",
//						"x": "6400",
//						"y": "10",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPSH2D24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPSH2D25",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILPSH2CS2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILPS83A00",
//					"attrs": {
//						"id": "IgnorePage2",
//						"viewName": "",
//						"label": "",
//						"x": "6400",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILPSH2D26",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPSH2D27",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILPSH2CS3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1ILPS8MPC0",
//					"attrs": {
//						"id": "Summary",
//						"viewName": "",
//						"label": "",
//						"x": "4475",
//						"y": "310",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1ILPSH2D28",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILPSH2D29",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`\n### 角色\n你是一个分析总结网页搜索结果的AI，根据输入的搜索结果内容的AI\n\n### 搜索目标\n当前的搜索目标是：\n${search}\n\n### 搜索结果\n当前的搜索网页并初步总结的结果，用JSON格式表达为：\n\n${JSON.stringify(searchResults,null,\"\\t\")}\n\n\n`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "请根据搜索结果，回答搜索问题",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1ILPSH2CS4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IM98OJJK0"
//						},
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILQ5Q6DE0",
//					"attrs": {
//						"id": "CheckUrls",
//						"viewName": "",
//						"label": "",
//						"x": "3520",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQ60KIP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQ60KIP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILQ60KIH1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILQ5S0920"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILQ60KIH0",
//									"attrs": {
//										"id": "Find",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILQ60KIP2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILQ60KIP3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input&&input.length>0"
//									},
//									"linkedSeg": "1ILQ9NEEU0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1ILQ5S0920",
//					"attrs": {
//						"id": "AskCheck",
//						"viewName": "",
//						"label": "",
//						"x": "3750",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "No correct search results found. There might be issues with human recognition/login. Please help resolve the issue and try again.",
//							"localize": {
//								"EN": "No correct search results found. There might be issues with human recognition/login. Please help resolve the issue and try again.",
//								"CN": "没有找到正确的搜索结果，可能遇到真人识别/登陆等问题，请帮助解决问题后再次尝试"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1ILQ60KII0",
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
//									"jaxId": "1ILQ5S08M0",
//									"attrs": {
//										"id": "TryAgain",
//										"desc": "输出节点。",
//										"text": "问题已处理，网页内已包含搜索结果，再次尝试",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILQ60KIP4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILQ60KIP5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1ILQ5VJ8Q0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1ILQ5S08M1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "遇到问题，无法获得搜索结果，放弃本次搜索",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILQ60KIP6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILQ60KIP7",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1ILQ62B570"
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
//					"def": "jumper",
//					"jaxId": "1ILQ5VJ8Q0",
//					"attrs": {
//						"id": "TryAgain",
//						"viewName": "",
//						"label": "",
//						"x": "3990",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1ILPRQC4P0",
//						"outlet": {
//							"jaxId": "1ILQ60KII1",
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
//					"def": "code",
//					"jaxId": "1ILQ62B570",
//					"attrs": {
//						"id": "UserAbort",
//						"viewName": "",
//						"label": "",
//						"x": "3990",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILQ63DP90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQ63DP91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILQ63DP20",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IM98ROVI0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1ILQ7PRKL0",
//					"attrs": {
//						"id": "TryPage",
//						"viewName": "",
//						"label": "",
//						"x": "4475",
//						"y": "90",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQ7S4840",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQ7S4841",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILQ7S47S0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILQU5D560"
//						},
//						"catchlet": {
//							"jaxId": "1ILQ7S47S1",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILQ9SL9V0"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILQ7QFH70",
//					"attrs": {
//						"id": "NextPage",
//						"viewName": "",
//						"label": "",
//						"x": "4915",
//						"y": "250",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQ7S4842",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQ7S4843",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILQ7S47S2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1ILQ9NEEU0",
//					"attrs": {
//						"id": "CloseSearch",
//						"viewName": "",
//						"label": "",
//						"x": "3750",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQ9P5BR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQ9P5BR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILQ9P5BK0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSN40IP0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILQ9SL9V0",
//					"attrs": {
//						"id": "CheckPage",
//						"viewName": "",
//						"label": "",
//						"x": "4695",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQA1O770",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQA1O771",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILQ9ULAR1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILQ7QFH70"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILQ9ULAR0",
//									"attrs": {
//										"id": "HasPage",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILQA1O772",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILQA1O773",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!context.aaPage"
//									},
//									"linkedSeg": "1ILQ9TPKF0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1ILQ9TPKF0",
//					"attrs": {
//						"id": "CloseErrorPage",
//						"viewName": "",
//						"label": "",
//						"x": "4915",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQA1O774",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQA1O775",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILQ9ULAR2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1ILQA032A0",
//					"attrs": {
//						"id": "CloseLoopPage",
//						"viewName": "",
//						"label": "",
//						"x": "5375",
//						"y": "75",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQA1O776",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQA1O777",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILQA1C6I0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILS7VRLH0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILQJR3OG0",
//					"attrs": {
//						"id": "CheckApiKey",
//						"viewName": "",
//						"label": "",
//						"x": "935",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQK3OCS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQK3OCS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILQK3OCK1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILQK304N0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILQK3OCK0",
//									"attrs": {
//										"id": "FindKey",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1ILQK3OCS2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILQK3OCS3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#searchApiKey"
//									},
//									"linkedSeg": "1ILQJT0JN0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1ILQJT0JN0",
//					"attrs": {
//						"id": "TryApi",
//						"viewName": "",
//						"label": "",
//						"x": "1200",
//						"y": "80",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQK3OCS4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQK3OCS5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILQK3OCK2",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILQJTSGU0"
//						},
//						"catchlet": {
//							"jaxId": "1ILQK3OCK3",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILQJU6R50"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILQJTSGU0",
//					"attrs": {
//						"id": "CallSearchApi",
//						"viewName": "",
//						"label": "",
//						"x": "1395",
//						"y": "30",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQK3OCS6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQK3OCS7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILQK3OCK4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IM98KOBT0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1ILQJU6R50",
//					"attrs": {
//						"id": "TipUseRpa",
//						"viewName": "",
//						"label": "",
//						"x": "1395",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQK3OCS8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQK3OCS9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`调用Google Search API时发生错误:  ${input}。转用Web-RPA模式进行搜索。`",
//						"outlet": {
//							"jaxId": "1ILQK3OCK5",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILQJVB630"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1ILQJVB630",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1535",
//						"y": "195",
//						"outlet": {
//							"jaxId": "1ILQK3OCS10",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRGHL00"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1ILQK0MRV0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3870",
//						"y": "45",
//						"outlet": {
//							"jaxId": "1ILQK3OCS11",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSN40IP0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1ILQK304N0",
//					"attrs": {
//						"id": "TipNoApiKey",
//						"viewName": "",
//						"label": "",
//						"x": "1200",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQK3OCS12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQK3OCS13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "No Google Search API key found, using Web-RPA method for Search.",
//							"localize": {
//								"EN": "No Google Search API key found, using Web-RPA method for Search.",
//								"CN": "没有找到Google search的API-Key，采用Web-RPA方式进行搜索。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1ILQK3OCK6",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRGHL00"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenBrowser",
//					"jaxId": "1ILQTBDM90",
//					"attrs": {
//						"id": "OpenBrowser2",
//						"viewName": "",
//						"label": "",
//						"x": "1960",
//						"y": "45",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQTBUO30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQTBUO31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"alias": "RPAHOME",
//						"headless": "false",
//						"devtools": "false",
//						"dataDir": "true",
//						"outlet": {
//							"jaxId": "1ILQTBUNR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILQK0MRV0"
//						},
//						"run": ""
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1ILQU5D560",
//					"attrs": {
//						"id": "TipPage",
//						"viewName": "",
//						"label": "",
//						"x": "4695",
//						"y": "75",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILQU8TLU0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILQU8TLU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "log",
//						"text": "#(($ln===\"CN\")?(`正在查看: ${input}`):/*EN*/(`Viewing: ${input}`))",
//						"outlet": {
//							"jaxId": "1ILQU7PTN0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPS1SK70"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1ILR0ACES0",
//					"attrs": {
//						"id": "TipStart",
//						"viewName": "",
//						"label": "",
//						"x": "265",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILR0BLB70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILR0BLB71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#(($ln===\"CN\")?(`开始搜索：${search}`):/*EN*/(`Start searching: ${search}`))",
//						"outlet": {
//							"jaxId": "1ILR0BLB20",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILPRD97O0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILS7VRLH0",
//					"attrs": {
//						"id": "CheckPageContent",
//						"viewName": "",
//						"label": "",
//						"x": "5635",
//						"y": "75",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILS82LJQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILS82LJQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILS82LJH1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILS81QP10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILS82LJH0",
//									"attrs": {
//										"id": "Content",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILS82LJQ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILS82LJQ3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!input"
//									},
//									"linkedSeg": "1ILPS42SL0"
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
//					"jaxId": "1ILS81QP10",
//					"attrs": {
//						"id": "IgnorePage",
//						"viewName": "",
//						"label": "",
//						"x": "5925",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILS82LJQ4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILS82LJQ5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILS82LJH2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILSN40IP0",
//					"attrs": {
//						"id": "CheckLinkOnly",
//						"viewName": "",
//						"label": "",
//						"x": "3990",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSN6TIC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSN6TIC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSN6TI41",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": "#input"
//							},
//							"linkedSeg": "1INSVEQP10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSN6TI40",
//									"attrs": {
//										"id": "Link",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSN6TIC2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSN6TIC3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#linkOnly"
//									},
//									"linkedSeg": "1ILSN672K0"
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
//					"jaxId": "1ILSN672K0",
//					"attrs": {
//						"id": "ReturnLinks",
//						"viewName": "",
//						"label": "",
//						"x": "4265",
//						"y": "30",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILSN6TIC4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSN6TIC5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSN6TI42",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IM98O14D0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IM98KOBT0",
//					"attrs": {
//						"id": "CheckLinkOnly2",
//						"viewName": "",
//						"label": "",
//						"x": "1685",
//						"y": "30",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IM98KOBU0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IM98KOBU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IM98KOBU2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": "#input"
//							},
//							"linkedSeg": "1ILQTBDM90"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IM98KOBU3",
//									"attrs": {
//										"id": "Link",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IM98KOBU4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IM98KOBU5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#linkOnly"
//									},
//									"linkedSeg": "1IM98LRN90"
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
//					"jaxId": "1IM98LRN90",
//					"attrs": {
//						"id": "ReturnLinks2",
//						"viewName": "",
//						"label": "",
//						"x": "1955",
//						"y": "-35",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IM98LRN91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IM98LRN92",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IM98LRN93",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaCloseBrowser",
//					"jaxId": "1IM98O14D0",
//					"attrs": {
//						"id": "CloseBrowser",
//						"viewName": "",
//						"label": "",
//						"x": "4500",
//						"y": "-35",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IM98P2410",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IM98P2411",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IM98P23R0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaCloseBrowser",
//					"jaxId": "1IM98OJJK0",
//					"attrs": {
//						"id": "CloseBrowser2",
//						"viewName": "",
//						"label": "",
//						"x": "4695",
//						"y": "310",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IM98P2412",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IM98P2413",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IM98P23R1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IM98ROVI0",
//					"attrs": {
//						"id": "JumpClose",
//						"viewName": "",
//						"label": "",
//						"x": "4215",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1IM98OJJK0",
//						"outlet": {
//							"jaxId": "1IM98S99B0",
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
//					"def": "jumper",
//					"jaxId": "1IM98TTCN0",
//					"attrs": {
//						"id": "JumpClose2",
//						"viewName": "",
//						"label": "",
//						"x": "3295",
//						"y": "330",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1IM98OJJK0",
//						"outlet": {
//							"jaxId": "1IM98VLT00",
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
//					"def": "loopArray",
//					"jaxId": "1INRKIURH0",
//					"attrs": {
//						"id": "AsyncLoop",
//						"viewName": "",
//						"label": "",
//						"x": "4440",
//						"y": "560",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRKJDT50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRKJDT51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "asyncForEach",
//						"outlet": {
//							"jaxId": "1INRKJDT52",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRKM9HN0"
//						},
//						"catchlet": {
//							"jaxId": "1INRKJDT00",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRLOS0A0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1INRKM9HN0",
//					"attrs": {
//						"id": "AsyncTryPage",
//						"viewName": "",
//						"label": "",
//						"x": "4670",
//						"y": "485",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRKMKDQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRKMKDQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INRKMKDK0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRKNSM30"
//						},
//						"catchlet": {
//							"jaxId": "1INRKMKDQ2",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRKPKVI0"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1INRKNSM30",
//					"attrs": {
//						"id": "AsyncTipPage",
//						"viewName": "",
//						"label": "",
//						"x": "4915",
//						"y": "470",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRKNSM40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRKNSM41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "log",
//						"text": "#(($ln===\"CN\")?(`正在查看: ${input}`):/*EN*/(`Viewing: ${input}`))",
//						"outlet": {
//							"jaxId": "1INRKNSM42",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRL10TH0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1INRKPKVI0",
//					"attrs": {
//						"id": "AsyncCheckPage",
//						"viewName": "",
//						"label": "",
//						"x": "4915",
//						"y": "615",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRL2KGJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRL2KGJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INRL2ESR1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INRKTGQ70"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INRL2ESR0",
//									"attrs": {
//										"id": "HasPage",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INRL2KGJ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INRL2KGJ3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#context[\"Page_\"+input]"
//									},
//									"linkedSeg": "1INRKRLU40"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1INRKRLU40",
//					"attrs": {
//						"id": "AsyncCloseErrorPage",
//						"viewName": "",
//						"label": "",
//						"x": "5205",
//						"y": "600",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRKRLU41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRKRLU42",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "#\"Page_\"+input",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1INRKRLU43",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1INRKTGQ70",
//					"attrs": {
//						"id": "AsyncNextPage",
//						"viewName": "",
//						"label": "",
//						"x": "5205",
//						"y": "700",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRL2KGJ4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRL2KGJ5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INRL2ESR2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1INRL10TH0",
//					"attrs": {
//						"id": "AsyncOpenUrl",
//						"viewName": "",
//						"label": "",
//						"x": "5205",
//						"y": "470",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRL10TH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRL10TH2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "#\"Page_\"+input",
//						"url": "#input",
//						"vpWidth": "800",
//						"vpHeight": "600",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1INRL10TH3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRL50LD0"
//						},
//						"run": "",
//						"timeout": "5000"
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1INRL50LD0",
//					"attrs": {
//						"id": "AsyncReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "5475",
//						"y": "470",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRL50LD1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRL50LD2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "#\"Page_\"+input",
//						"target": "Article",
//						"node": "null",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1INRL50LD3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRL97SR0"
//						},
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1INRL97SR0",
//					"attrs": {
//						"id": "AsyncCloseLoopPage",
//						"viewName": "",
//						"label": "",
//						"x": "5745",
//						"y": "470",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRL97SR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRL97SR2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "#\"Page_\"+input",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1INRL97SR3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1INRLDQ370",
//					"attrs": {
//						"id": "LoopContents",
//						"viewName": "",
//						"label": "",
//						"x": "4945",
//						"y": "835",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRLR9480",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRLR9481",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1INRLR9410",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRLESDV0"
//						},
//						"catchlet": {
//							"jaxId": "1INRLR9411",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRLLTLI0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1INRLESDV0",
//					"attrs": {
//						"id": "AsyncCheckPageContent",
//						"viewName": "",
//						"label": "",
//						"x": "5190",
//						"y": "820",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRLESDV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRLESDV2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INRLESDV3",
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
//									"jaxId": "1INRLESDV4",
//									"attrs": {
//										"id": "Content",
//										"desc": "输出节点。",
//										"output": "#`\nFrom link: ${input}\n- - -\n${pageContents[input]}\n`",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INRLESE00",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INRLESE01",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!pageContents[input]"
//									},
//									"linkedSeg": "1INRLG50O0"
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
//					"jaxId": "1INRLG50O0",
//					"attrs": {
//						"id": "AsyncReadContent",
//						"viewName": "",
//						"label": "",
//						"x": "5480",
//						"y": "805",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRLG50O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRLG50O2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o-mini",
//						"system": "#`\n### 角色\n你是一个判断输入的搜索的网页结果内容是否与搜索目标相关的AI\n\n### 搜索目标\n当前的搜索目标是：\n${search}\n\n### 对话\n- 每轮对话时用户会输入搜索到的网页内容，可能是纯文本、HTML文本或者Markdown格式。\n- 你根据用户的输入，判断用户输入的网页内容是否与回答当前的搜索目标相关，并用JSON返回，例如：\n\\`\\`\\`\n//找到了相关内容：\n{\n    \"useful\":true,\n}\n//没有找到相关内容：\n{\n    \"useful\":false,\n}\n\\`\\`\\`\n\n### 返回JSON属性说明\n\"useful\" {bool}: 本回合对话用户输入的内容是否对搜索目标有帮助\n`",
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
//							"jaxId": "1INRLG50O3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRLH17U0"
//						},
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1INRLH17U0",
//					"attrs": {
//						"id": "AsyncCheckContent",
//						"viewName": "",
//						"label": "",
//						"x": "5750",
//						"y": "805",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRLH17U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRLH17U2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INRLH17U3",
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
//									"jaxId": "1INRLH17U4",
//									"attrs": {
//										"id": "Useful",
//										"desc": "输出节点。",
//										"output": "#input.content",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INRLH17U5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INRLH17U6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.useful"
//									},
//									"linkedSeg": "1INRLKIME0"
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
//					"jaxId": "1INRLKIME0",
//					"attrs": {
//						"id": "AsyncCheckFinish",
//						"viewName": "",
//						"label": "",
//						"x": "6020",
//						"y": "790",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INRLKIMF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRLKIMF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INRLKIMF2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1INRLLTLI0",
//					"attrs": {
//						"id": "AsyncSummary",
//						"viewName": "",
//						"label": "",
//						"x": "5190",
//						"y": "1055",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1INRLLTLI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRLLTLI2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`\n### 角色\n你是一个分析总结网页搜索结果的AI，根据输入的搜索结果内容的AI\n\n### 搜索目标\n当前的搜索目标是：\n${search}\n\n### 搜索结果\n当前的搜索网页并初步总结的结果，用JSON格式表达为：\n\n${JSON.stringify(searchResults,null,\"\\t\")}\n\n\n`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "请根据搜索结果，回答搜索问题",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1INRLLTLI3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaCloseBrowser",
//					"jaxId": "1INRLOS0A0",
//					"attrs": {
//						"id": "AsyncCloseBrowser",
//						"viewName": "",
//						"label": "",
//						"x": "4670",
//						"y": "835",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1INRLOS0A1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INRLOS0A2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INRLOS0A3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRLDQ370"
//						}
//					},
//					"icon": "close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1INSVEQP10",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "4335",
//						"y": "280",
//						"outlet": {
//							"jaxId": "1INT03PO30",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INRKIURH0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "使用Google进行网页搜索并返回总结后的搜索结果。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"{\\\"EN\\\":\\\"Web Search\\\",\\\"CN\\\":\\\"网络搜索\\\"}\",\"path\":\"\",\"pathInHub\":\"AgentBuilder\",\"chatEntry\":\"Tool\",\"isRPA\":true,\"rpaHost\":\"\",\"segIcon\":\"/~/-tabos/shared/assets/browser.svg\",\"catalog\":\"AI Call\"}"
//	}
//}