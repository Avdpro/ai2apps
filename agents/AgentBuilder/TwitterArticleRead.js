//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1JBC9KUBF0MoreImports*/
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*}#1JBC9KUBF0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1JBC9KUBF0StartDoc*/
/*}#1JBC9KUBF0StartDoc*/
//----------------------------------------------------------------------------
let twitterArticleRead=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let ShowProcess,ReadUrl,OpenPage,GetArtical,AIGetComments,ShowComments,CheckNum,Scroll,GetNextHtml,ClosePage,ttt,AIGetComments_1,ShowComments_1,End,GetHtml,CheckHtml,GetMore,CallAI,SaveComments,ClosePage_1,CheckLength,NoData;
	let readRounds=0;
	
	/*#{1JBC9KUBF0LocalVals*/
	/*}#1JBC9KUBF0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1JBC9KUBF0ParseArgs*/
		/*}#1JBC9KUBF0ParseArgs*/
	}
	
	/*#{1JBC9KUBF0PreContext*/
	/*}#1JBC9KUBF0PreContext*/
	context={
		pageArticles: [],
		divLen: 0,
		contentItem: "",
		commentsArr: [],
		allData: "",
		/*#{1JBC9KUBF5ExCtxAttrs*/
		/*}#1JBC9KUBF5ExCtxAttrs*/
	};
	/*#{1JBC9KUBF0PostContext*/
	/*}#1JBC9KUBF0PostContext*/
	let $agent,agent,segs={};
	segs["ShowProcess"]=ShowProcess=async function(input){//:1JBCBBN5G0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("正在读取内容，请稍等..."):("Loading content, please wait..."));
		/*#{1JBCBBN5G0PreCodes*/
		/*}#1JBCBBN5G0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JBCBBN5G0PostCodes*/
		context.comments = input.comments; // 需要获取的评论条数
		result = input.finds;
		/*}#1JBCBBN5G0PostCodes*/
		return {result:result};
	};
	ShowProcess.jaxId="1JBCBBN5G0"
	ShowProcess.url="ShowProcess@"+agentURL
	
	segs["ReadUrl"]=ReadUrl=async function(input){//:1JBCAFG9K0
		let result=input;
		let list=input.finds;
		let i,n,item,loopR;
		/*#{1JBCAFG9K0PreLoop*/
		context.comments = input.comments; // 需要获取的评论条数
		/*}#1JBCAFG9K0PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1JBCAFG9K0InLoopPre*/
			/*}#1JBCAFG9K0InLoopPre*/
			loopR=await session.runAISeg(agent,OpenPage,item,"1JBCAFG9K0","1JBCAFR382")
			if(loopR==="break"){
				break;
			}
			/*#{1JBCAFG9K0InLoopPost*/
			/*}#1JBCAFG9K0InLoopPost*/
		}
		/*#{1JBCAFG9K0PostCodes*/
		/*}#1JBCAFG9K0PostCodes*/
		return {seg:End,result:(result),preSeg:"1JBCAFG9K0",outlet:"1JBCAFR330"};
	};
	ReadUrl.jaxId="1JBCAFG9K0"
	ReadUrl.url="ReadUrl@"+agentURL
	
	segs["OpenPage"]=OpenPage=async function(input){//:1JBCAGK3A0
		let pageVal="aaPage";
		let $url=input.url;
		let $waitBefore=0;
		let $waitAfter=2500;
		let $width=1200;
		let $height=900;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		/*#{1JBCAGK3A0PreCodes*/
		context.rpaBrowser = globalContext.rpaBrowser;
		context.webRpa = globalContext.webRpa;
		context.contentItem = input;
		/*}#1JBCAGK3A0PreCodes*/
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url,$openOpts);
		$waitAfter && (await sleep($waitAfter));
		/*#{1JBCAGK3A0PostCodes*/
		/*}#1JBCAGK3A0PostCodes*/
		return {seg:GetArtical,result:(true),preSeg:"1JBCAGK3A0",outlet:"1JBCAHRKC0"};
	};
	OpenPage.jaxId="1JBCAGK3A0"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["GetArtical"]=GetArtical=async function(input){//:1JBHKBHIL0
		let result=input
		/*#{1JBHKBHIL0Code*/
		let page=context["aaPage"];
		
		const { content, time } = await page.callFunction(() => {
			const tweet = document.querySelector('[data-testid="tweet"]');
			if (!tweet) return { content: '', time: '' };
		
			const textBlock = tweet.querySelector('[data-testid="tweetText"]');
			let content = '';
			if (textBlock) {
				const clone = textBlock.cloneNode(true);
				clone.querySelectorAll('img[alt]').forEach(img => img.replaceWith(img.alt));
				content = clone.innerText.trim();
			}
		
			const timeTag = tweet.querySelector('time');
			const time =  timeTag ? timeTag.innerText.trim() : ''; 
			
			return { content, time };
		});
		
		result = { 
			key: context.contentItem?.url,
			title: context.contentItem?.title,
			content, 
			platform: "x",
			time,
			//views: context.contentItem?.views,
		}
		console.log("GetArtical",result);
		context.pageArticles.push(result);
		/*}#1JBHKBHIL0Code*/
		return {seg:ClosePage_1,result:(result),preSeg:"1JBHKBHIL0",outlet:"1JBHKOL890"};
	};
	GetArtical.jaxId="1JBHKBHIL0"
	GetArtical.url="GetArtical@"+agentURL
	
	segs["AIGetComments"]=AIGetComments=async function(input){//:1JBM4PRTJ0
		let prompt;
		let result=null;
		/*#{1JBM4PRTJ0Input*/
		console.log('+++', input.length);
		//console.log(context.tag,'AIGetComments');
		/*}#1JBM4PRTJ0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1-mini",
			maxToken:20000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=AIGetComments.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
${input} 是推特评论区 HTML 片段数组，每个片段即一个 <div data-testid="cellInnerDiv"> 
	<div> 
    	<div> 
        	<article data-testid="tweet">...</article> 
        </div> 
    </div> 
</div> 的根节点。

请按以下要求提取并返回 JSON 数组，字段名用英文：
data : [
	{
      userName：显示名称（例：⨝）,
      userHandle：@账号（例：@Zen_of_Nemesis）,
      avatar：用户头像（例：https://pbs.twimg.com/profile_images/1996591321184706560/cX8W72l__normal.jpg）,
      commentText：评论正文,
      publishTime：发布时间原始字符串（例：Nov 23）,
      likes：点赞量原始字符串（例：1）,
    }
]

提取规则（必须仅在当前 article 内部执行，禁止跨 article 拼接）：
1. 骨架过滤：若不存在article标签，则为页面骨架结构，跳过该条数据。

2. 务必按照顺序获取当前 article 片段的相关信息，绝不可以跨片段获取数据内容。

3. 最终返回 JSON 数组，不输出任何解释、注释或 Markdown 包裹。
`},
		];
		/*#{1JBM4PRTJ0PrePrompt*/
		/*}#1JBM4PRTJ0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JBM4PRTJ0FilterMessage*/
			/*}#1JBM4PRTJ0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JBM4PRTJ0PreCall*/
		/*}#1JBM4PRTJ0PreCall*/
		result=(result===null)?(await session.callSegLLM("AIGetComments@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1JBM4PRTJ0PostCall*/
		/*}#1JBM4PRTJ0PostCall*/
		/*#{1JBM4PRTJ0PreResult*/
		/*}#1JBM4PRTJ0PreResult*/
		return {seg:ShowComments,result:(result),preSeg:"1JBM4PRTJ0",outlet:"1JBM4QQVH0"};
	};
	AIGetComments.jaxId="1JBM4PRTJ0"
	AIGetComments.url="AIGetComments@"+agentURL
	
	segs["ShowComments"]=ShowComments=async function(input){//:1JBM8CCDD0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=`
  \`\`\`	
  	${JSON.stringify(input,null,"\t")}
  \`\`\`
` ;
		/*#{1JBM8CCDD0PreCodes*/
		/*}#1JBM8CCDD0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JBM8CCDD0PostCodes*/
		console.log("ShowComments",input);
		/*}#1JBM8CCDD0PostCodes*/
		return {seg:CheckNum,result:(result),preSeg:"1JBM8CCDD0",outlet:"1JBM8CP7P0"};
	};
	ShowComments.jaxId="1JBM8CCDD0"
	ShowComments.url="ShowComments@"+agentURL
	
	segs["CheckNum"]=CheckNum=async function(input){//:1JBMJ4EK80
		let result=input;
		if( input?.data?.length < context.comments){
			return {seg:Scroll,result:(input),preSeg:"1JBMJ4EK80",outlet:"1JBMJ5U6C0"};
		}
		return {seg:ttt,result:(result),preSeg:"1JBMJ4EK80",outlet:"1JBMJ5U6C1"};
	};
	CheckNum.jaxId="1JBMJ4EK80"
	CheckNum.url="CheckNum@"+agentURL
	
	segs["Scroll"]=Scroll=async function(input){//:1JBMCFU1R0
		let result=input
		/*#{1JBMCFU1R0Code*/
		let page=context["aaPage"];
		await page.callFunction(async () => {
			const distance = window.innerHeight; 
			const times = 2;                    
			for (let i = 0; i < times; i++) {
				window.scrollBy(0, distance);      
				await new Promise(r => setTimeout(r, 1000)); 
			}
		}, []);
		console.log("divLen",context.divLen);
		/*}#1JBMCFU1R0Code*/
		return {seg:GetNextHtml,result:(result),preSeg:"1JBMCFU1R0",outlet:"1JBMCG65K0"};
	};
	Scroll.jaxId="1JBMCFU1R0"
	Scroll.url="Scroll@"+agentURL
	
	segs["GetNextHtml"]=GetNextHtml=async function(input){//:1JBMKS1280
		let result=input
		/*#{1JBMKS1280Code*/
		let page=context["aaPage"];
		// 获取滚动区域的评论
		//const cells = await page.callFunction(() => {
			//const region = document.querySelector('[aria-label="Timeline: Conversation"]');
			//if (!region) return [];
			//return Array.from(region.querySelectorAll('[data-testid="cellInnerDiv"]'));
		//});
		//console.log("cells",cells.length);
		// 计算需要的新片段：去掉前 2 个，再跳过上次已采集的条数
		const newHtmls = await page.callFunction((start) => {
		const region = document.querySelector('[aria-label="Timeline: Conversation"]');
		if (!region) return [];
		return Array.from(region.querySelectorAll('[data-testid="cellInnerDiv"]'))
				.slice(start)
				.map(el => el.outerHTML);
		}, [context.divLen + 2]);   // 把 start 当参数传进去
		console.log("newHtmls",newHtmls);
		// 更新累计长度，供下次使用
		context.divLen = context.divLen + newHtmls.length;
		result = newHtmls;
		/*}#1JBMKS1280Code*/
		return {seg:AIGetComments_1,result:(result),preSeg:"1JBMKS1280",outlet:"1JBMKS3D40"};
	};
	GetNextHtml.jaxId="1JBMKS1280"
	GetNextHtml.url="GetNextHtml@"+agentURL
	
	segs["ClosePage"]=ClosePage=async function(input){//:1JBCC5FKP0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=300;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		return {result:result};
	};
	ClosePage.jaxId="1JBCC5FKP0"
	ClosePage.url="ClosePage@"+agentURL
	
	segs["ttt"]=ttt=async function(input){//:1JBML4BQ70
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content="test";
		session.addChatText(role,content,opts);
		return {result:result};
	};
	ttt.jaxId="1JBML4BQ70"
	ttt.url="ttt@"+agentURL
	
	segs["AIGetComments_1"]=AIGetComments_1=async function(input){//:1JBMRIS8V0
		let prompt;
		let result=null;
		/*#{1JBMRIS8V0Input*/
		/*}#1JBMRIS8V0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1-mini",
			maxToken:20000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=AIGetComments_1.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
${input} 是推特评论区 HTML 片段数组，每个片段即一个 <div data-testid="cellInnerDiv"> 
	<div> 
    	<div> 
        	<article data-testid="tweet">...</article> 
        </div> 
    </div> 
</div> 的根节点。

请按以下要求提取并返回 JSON 数组，字段名用英文：
data : [
	{
      userName：显示名称（例：⨝）,
      userHandle：@账号（例：@Zen_of_Nemesis）,
      avatar：用户头像（例：https://pbs.twimg.com/profile_images/1996591321184706560/cX8W72l__normal.jpg）,
      commentText：评论正文,
      publishTime：发布时间原始字符串（例：Nov 23）,
      likes：点赞量原始字符串（例：1）,
    }
]

提取规则（必须仅在当前 article 内部执行，禁止跨 article 拼接）：
1. 骨架过滤：若不存在article标签，则为页面骨架结构，跳过该条数据。

2. 务必按照顺序获取当前 article 片段的相关信息，绝不可以跨片段获取数据内容。

3. 最终返回 JSON 数组，不输出任何解释、注释或 Markdown 包裹。
`},
		];
		/*#{1JBMRIS8V0PrePrompt*/
		/*}#1JBMRIS8V0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JBMRIS8V0FilterMessage*/
			/*}#1JBMRIS8V0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JBMRIS8V0PreCall*/
		/*}#1JBMRIS8V0PreCall*/
		result=(result===null)?(await session.callSegLLM("AIGetComments_1@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1JBMRIS8V0PostCall*/
		/*}#1JBMRIS8V0PostCall*/
		/*#{1JBMRIS8V0PreResult*/
		/*}#1JBMRIS8V0PreResult*/
		return {seg:ShowComments_1,result:(result),preSeg:"1JBMRIS8V0",outlet:"1JBMRIS900"};
	};
	AIGetComments_1.jaxId="1JBMRIS8V0"
	AIGetComments_1.url="AIGetComments_1@"+agentURL
	
	segs["ShowComments_1"]=ShowComments_1=async function(input){//:1JBMRJ1UI0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=`
  \`\`\`	
  	${JSON.stringify(input,null,"\t")}
  \`\`\`
` ;
		/*#{1JBMRJ1UI0PreCodes*/
		/*}#1JBMRJ1UI0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JBMRJ1UI0PostCodes*/
		/*}#1JBMRJ1UI0PostCodes*/
		return {result:result};
	};
	ShowComments_1.jaxId="1JBMRJ1UI0"
	ShowComments_1.url="ShowComments_1@"+agentURL
	
	segs["End"]=End=async function(input){//:1JC32NKT70
		let result=input
		/*#{1JC32NKT70Code*/
		//result = context.allData;
		console.log("pageArticles",context.pageArticles);
		result = context.pageArticles;
		/*}#1JC32NKT70Code*/
		return {result:result};
	};
	End.jaxId="1JC32NKT70"
	End.url="End@"+agentURL
	
	segs["GetHtml"]=GetHtml=async function(input){//:1JC3LDBR90
		let result=input
		/*#{1JC3LDBR90Code*/
		let page = context['aaPage'];
		const data = await page.callFunction(() => {
			const sectionEle = document.querySelector('section.css-175oi2r');
			//console.log('sectionEle',sectionEle);
			const contentEle = sectionEle && sectionEle.querySelector('div[aria-label="Timeline: Conversation"]');
			//console.log('contentEle',contentEle);
			const lists = contentEle && contentEle.querySelectorAll('[data-testid="cellInnerDiv"]');
			//console.log("lists",lists);
			const usefulLists = lists && lists.length > 3 ? Array.from(lists).slice(2).map(el => el.outerHTML): [];
			//console.log("usefulLists",usefulLists);
			const articles = usefulLists.filter(html => html.includes('<article'));
			console.log('含article的条目：', articles);
			return articles;
		},[]);
		result = data;
		readRounds+=1;
		/*}#1JC3LDBR90Code*/
		return {seg:CheckHtml,result:(result),preSeg:"1JC3LDBR90",outlet:"1JC3LDQCB0"};
	};
	GetHtml.jaxId="1JC3LDBR90"
	GetHtml.url="GetHtml@"+agentURL
	
	segs["CheckHtml"]=CheckHtml=async function(input){//:1JC3LFBTN0
		let result=input;
		/*#{1JC3LFBTN0Start*/
		/*}#1JC3LFBTN0Start*/
		if(!result.length){
			return {seg:GetMore,result:(input),preSeg:"1JC3LFBTN0",outlet:"1JC3LGP1M0"};
		}
		if(result.length < context.comments && readRounds<10){
			return {seg:GetMore,result:(input),preSeg:"1JC3LFBTN0",outlet:"1JC3LFQV40"};
		}
		/*#{1JC3LFBTN0Post*/
		/*}#1JC3LFBTN0Post*/
		return {seg:CallAI,result:(result),preSeg:"1JC3LFBTN0",outlet:"1JC3LGP1N0"};
	};
	CheckHtml.jaxId="1JC3LFBTN0"
	CheckHtml.url="CheckHtml@"+agentURL
	
	segs["GetMore"]=GetMore=async function(input){//:1JC3LGTPJ0
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint="";
		let $deltaX=0;
		let $deltaY=500;
		let $options={"steps":10};
		let $waitBefore=500;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JC3LGTPJ0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			$pms=page.mouseWheel($query,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
		}else{
			$pms=page.mouseWheel(null,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
		}
		if($pms && (!$async)){await $pms;}$waitAfter && (await sleep($waitAfter))
		return {seg:GetHtml,result:(result),preSeg:"1JC3LGTPJ0",outlet:"1JC3LI4VJ0"};
	};
	GetMore.jaxId="1JC3LGTPJ0"
	GetMore.url="GetMore@"+agentURL
	
	segs["CallAI"]=CallAI=async function(input){//:1JC3LI8K10
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-5",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=CallAI.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
${JSON.stringify(input,null,"\t")} 是推特评论区 HTML 片段数组，每个片段即一个 <div data-testid="cellInnerDiv"> 
	<div> 
    	<div> 
        	<article data-testid="tweet">...</article> 
        </div> 
    </div> 
</div> 的根节点。

请按以下要求提取并返回 JSON 数组，字段名用英文：
data : [
	{
      commentText：评论正文,
      publishTime：发布时间原始字符串（例：Nov 23）,
      likes：点赞量原始字符串（例：1）,
      view：帖子观看人数（例：1.1K）
    }
]

提取规则：
1. 必须仅在当前 article 内部执行，禁止跨 article 拼接；
2. 务必按照顺序获取当前 article 片段的相关信息，绝不可以跨片段获取数据内容；
3. 最终返回 JSON 数组，不输出任何解释、注释或 Markdown 包裹。
`},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("CallAI@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:SaveComments,result:(result),preSeg:"1JC3LI8K10",outlet:"1JC3LIN7C0"};
	};
	CallAI.jaxId="1JC3LI8K10"
	CallAI.url="CallAI@"+agentURL
	
	segs["SaveComments"]=SaveComments=async function(input){//:1JC3M4IAB0
		let result=input
		/*#{1JC3M4IAB0Code*/
		console.log(input?.data,'SaveComments');
		if(input){ 
			context.commentsArr.push(input) 
		};
		const merged = context.pageArticles.map((tweet, index) => ({
			...tweet,
			comments: context.commentsArr.length ? (context.commentsArr[index]?.data || []) : []
		}));
		result = merged;
		context.allData = merged;
		/*}#1JC3M4IAB0Code*/
		return {seg:ClosePage,result:(result),preSeg:"1JC3M4IAB0",outlet:"1JC3M4TGD0"};
	};
	SaveComments.jaxId="1JC3M4IAB0"
	SaveComments.url="SaveComments@"+agentURL
	
	segs["ClosePage_1"]=ClosePage_1=async function(input){//:1JC5LU0UL0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=300;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		return {result:result};
	};
	ClosePage_1.jaxId="1JC5LU0UL0"
	ClosePage_1.url="ClosePage_1@"+agentURL
	
	segs["CheckLength"]=CheckLength=async function(input){//:1JCIGJ1QH0
		let result=input;
		if(input.finds && input.finds.length > 0){
			return {seg:ReadUrl,result:(input),preSeg:"1JCIGJ1QH0",outlet:"1JCIGJELG0"};
		}
		return {seg:NoData,result:(result),preSeg:"1JCIGJ1QH0",outlet:"1JCIGJELG1"};
	};
	CheckLength.jaxId="1JCIGJ1QH0"
	CheckLength.url="CheckLength@"+agentURL
	
	segs["NoData"]=NoData=async function(input){//:1JCIJAR3L0
		let result=input
		/*#{1JCIJAR3L0Code*/
		result = [];
		/*}#1JCIJAR3L0Code*/
		return {result:result};
	};
	NoData.jaxId="1JCIJAR3L0"
	NoData.url="NoData@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"twitterArticleRead",
		url:agentURL,
		autoStart:true,
		jaxId:"1JBC9KUBF0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1JBC9KUBF0PreEntry*/
			/*}#1JBC9KUBF0PreEntry*/
			result={seg:CheckLength,"input":input};
			/*#{1JBC9KUBF0PostEntry*/
			/*}#1JBC9KUBF0PostEntry*/
			return result;
		},
		/*#{1JBC9KUBF0MoreAgentAttrs*/
		/*}#1JBC9KUBF0MoreAgentAttrs*/
	};
	/*#{1JBC9KUBF0PostAgent*/
	/*}#1JBC9KUBF0PostAgent*/
	return agent;
};
/*#{1JBC9KUBF0ExCodes*/
/*}#1JBC9KUBF0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JBC9KUBF0PostDoc*/
/*}#1JBC9KUBF0PostDoc*/


export default twitterArticleRead;
export{twitterArticleRead};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JBC9KUBF0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JBC9KUBF1",
//			"attrs": {
//				"baiduRead": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JBC9KUBF7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JBC9KUBF8",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JBC9KUBF9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JBC9KUBF10",
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
//			"jaxId": "1JBC9KUBF2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "CheckLength",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JBC9KUBF3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1JBC9KUBF4",
//			"attrs": {
//				"readRounds": {
//					"type": "number",
//					"valText": "0"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JBC9KUBF5",
//			"attrs": {
//				"pageArticles": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JBCCBN1U0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"divLen": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JBJV2HT40",
//					"attrs": {
//						"type": "Number",
//						"mockup": "0",
//						"desc": ""
//					}
//				},
//				"contentItem": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JBM9CPMV0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"commentsArr": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC3NU6L50",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"allData": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC3P5O1I0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1JBC9KUBF6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JBCBBN5G0",
//					"attrs": {
//						"id": "ShowProcess",
//						"viewName": "",
//						"label": "",
//						"x": "335",
//						"y": "585",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBCBC0FD0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBCBC0FD1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Loading content, please wait...",
//							"localize": {
//								"EN": "Loading content, please wait...",
//								"CN": "正在读取内容，请稍等..."
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JBCBC0F80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1JBCAFG9K0",
//					"attrs": {
//						"id": "ReadUrl",
//						"viewName": "",
//						"label": "",
//						"x": "65",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBCAFR380",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBCAFR381",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input.finds",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1JBCAFR382",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBCAGK3A0"
//						},
//						"catchlet": {
//							"jaxId": "1JBCAFR330",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC32NKT70"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1JBCAGK3A0",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "270",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBCAHRKG0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBCAHRKG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "#input.url",
//						"vpWidth": "1200",
//						"vpHeight": "900",
//						"userAgent": "",
//						"waitBefore": "",
//						"waitAfter": "2500",
//						"outlet": {
//							"jaxId": "1JBCAHRKC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBHKBHIL0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JBHKBHIL0",
//					"attrs": {
//						"id": "GetArtical",
//						"viewName": "",
//						"label": "",
//						"x": "475",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBHKOL8B0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBHKOL8B1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JBHKOL890",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC5LU0UL0"
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
//					"jaxId": "1JBM4PRTJ0",
//					"attrs": {
//						"id": "AIGetComments",
//						"viewName": "",
//						"label": "",
//						"x": "835",
//						"y": "730",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBM4QQVK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBM4QQVK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "#`\n${input} 是推特评论区 HTML 片段数组，每个片段即一个 <div data-testid=\"cellInnerDiv\"> \n\t<div> \n    \t<div> \n        \t<article data-testid=\"tweet\">...</article> \n        </div> \n    </div> \n</div> 的根节点。\n\n请按以下要求提取并返回 JSON 数组，字段名用英文：\ndata : [\n\t{\n      userName：显示名称（例：⨝）,\n      userHandle：@账号（例：@Zen_of_Nemesis）,\n      avatar：用户头像（例：https://pbs.twimg.com/profile_images/1996591321184706560/cX8W72l__normal.jpg）,\n      commentText：评论正文,\n      publishTime：发布时间原始字符串（例：Nov 23）,\n      likes：点赞量原始字符串（例：1）,\n    }\n]\n\n提取规则（必须仅在当前 article 内部执行，禁止跨 article 拼接）：\n1. 骨架过滤：若不存在article标签，则为页面骨架结构，跳过该条数据。\n\n2. 务必按照顺序获取当前 article 片段的相关信息，绝不可以跨片段获取数据内容。\n\n3. 最终返回 JSON 数组，不输出任何解释、注释或 Markdown 包裹。\n`",
//						"temperature": "0",
//						"maxToken": "20000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1JBM4QQVH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBM8CCDD0"
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
//					"def": "output",
//					"jaxId": "1JBM8CCDD0",
//					"attrs": {
//						"id": "ShowComments",
//						"viewName": "",
//						"label": "",
//						"x": "1090",
//						"y": "730",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBM8CP7T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBM8CP7T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#`\n  \\`\\`\\`\t\n  \t${JSON.stringify(input,null,\"\\t\")}\n  \\`\\`\\`\n` ",
//						"outlet": {
//							"jaxId": "1JBM8CP7P0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBMJ4EK80"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JBMJ4EK80",
//					"attrs": {
//						"id": "CheckNum",
//						"viewName": "",
//						"label": "",
//						"x": "1335",
//						"y": "730",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBMJ6JFS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBMJ6JFS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JBMJ5U6C1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JBML4BQ70"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JBMJ5U6C0",
//									"attrs": {
//										"id": "More",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JBMJ6JFS2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JBMJ6JFS3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "# input?.data?.length < context.comments"
//									},
//									"linkedSeg": "1JBMCFU1R0"
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
//					"jaxId": "1JBMCFU1R0",
//					"attrs": {
//						"id": "Scroll",
//						"viewName": "",
//						"label": "",
//						"x": "1560",
//						"y": "715",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBMCH1UO0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBMCH1UO1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JBMCG65K0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBMKS1280"
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
//					"jaxId": "1JBMKS1280",
//					"attrs": {
//						"id": "GetNextHtml",
//						"viewName": "",
//						"label": "",
//						"x": "1750",
//						"y": "715",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBMKS3DB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBMKS3DB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JBMKS3D40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBMRIS8V0"
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
//					"jaxId": "1JBCC5FKP0",
//					"attrs": {
//						"id": "ClosePage",
//						"viewName": "",
//						"label": "",
//						"x": "1605",
//						"y": "65",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBCC5T9J0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBCC5T9J1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "300",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JBCC5T9F0",
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
//					"def": "output",
//					"jaxId": "1JBML4BQ70",
//					"attrs": {
//						"id": "ttt",
//						"viewName": "",
//						"label": "",
//						"x": "1585",
//						"y": "805",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBML4LS10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBML4LS11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "test",
//						"outlet": {
//							"jaxId": "1JBML4LRR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JBMRIS8V0",
//					"attrs": {
//						"id": "AIGetComments_1",
//						"viewName": "",
//						"label": "",
//						"x": "1985",
//						"y": "715",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBMRIS8V1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBMRIS8V2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "#`\n${input} 是推特评论区 HTML 片段数组，每个片段即一个 <div data-testid=\"cellInnerDiv\"> \n\t<div> \n    \t<div> \n        \t<article data-testid=\"tweet\">...</article> \n        </div> \n    </div> \n</div> 的根节点。\n\n请按以下要求提取并返回 JSON 数组，字段名用英文：\ndata : [\n\t{\n      userName：显示名称（例：⨝）,\n      userHandle：@账号（例：@Zen_of_Nemesis）,\n      avatar：用户头像（例：https://pbs.twimg.com/profile_images/1996591321184706560/cX8W72l__normal.jpg）,\n      commentText：评论正文,\n      publishTime：发布时间原始字符串（例：Nov 23）,\n      likes：点赞量原始字符串（例：1）,\n    }\n]\n\n提取规则（必须仅在当前 article 内部执行，禁止跨 article 拼接）：\n1. 骨架过滤：若不存在article标签，则为页面骨架结构，跳过该条数据。\n\n2. 务必按照顺序获取当前 article 片段的相关信息，绝不可以跨片段获取数据内容。\n\n3. 最终返回 JSON 数组，不输出任何解释、注释或 Markdown 包裹。\n`",
//						"temperature": "0",
//						"maxToken": "20000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1JBMRIS900",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBMRJ1UI0"
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
//					"def": "output",
//					"jaxId": "1JBMRJ1UI0",
//					"attrs": {
//						"id": "ShowComments_1",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "715",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBMRJ1UI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBMRJ1UI2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#`\n  \\`\\`\\`\t\n  \t${JSON.stringify(input,null,\"\\t\")}\n  \\`\\`\\`\n` ",
//						"outlet": {
//							"jaxId": "1JBMRJ1UI3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JC32NKT70",
//					"attrs": {
//						"id": "End",
//						"viewName": "",
//						"label": "",
//						"x": "315",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC32NRNJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC32NRNJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JC32NRNF0",
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
//					"jaxId": "1JC3LDBR90",
//					"attrs": {
//						"id": "GetHtml",
//						"viewName": "",
//						"label": "",
//						"x": "720",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC3LDQCI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC3LDQCI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JC3LDQCB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC3LFBTN0"
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
//					"jaxId": "1JC3LFBTN0",
//					"attrs": {
//						"id": "CheckHtml",
//						"viewName": "",
//						"label": "",
//						"x": "920",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC3LGP1U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC3LGP1U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JC3LGP1N0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JC3LI8K10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JC3LGP1M0",
//									"attrs": {
//										"id": "GetData",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JC3LGP1U2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC3LGP1U3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!result.length"
//									},
//									"linkedSeg": "1JC3LGTPJ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JC3LFQV40",
//									"attrs": {
//										"id": "More",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JC3LGP1U4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC3LGP1U5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result.length < context.comments && readRounds<10"
//									},
//									"linkedSeg": "1JC3LGTPJ0"
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
//					"jaxId": "1JC3LGTPJ0",
//					"attrs": {
//						"id": "GetMore",
//						"viewName": "",
//						"label": "",
//						"x": "1165",
//						"y": "5",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC3LI4VN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC3LI4VN1",
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
//						"options": "{\"steps\":10}",
//						"waitBefore": "500",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JC3LI4VJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC3LJP3A0"
//						},
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JC3LI8K10",
//					"attrs": {
//						"id": "CallAI",
//						"viewName": "",
//						"label": "",
//						"x": "1165",
//						"y": "65",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC3LIN7H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC3LIN7H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-5",
//						"system": "#`\n${JSON.stringify(input,null,\"\\t\")} 是推特评论区 HTML 片段数组，每个片段即一个 <div data-testid=\"cellInnerDiv\"> \n\t<div> \n    \t<div> \n        \t<article data-testid=\"tweet\">...</article> \n        </div> \n    </div> \n</div> 的根节点。\n\n请按以下要求提取并返回 JSON 数组，字段名用英文：\ndata : [\n\t{\n      commentText：评论正文,\n      publishTime：发布时间原始字符串（例：Nov 23）,\n      likes：点赞量原始字符串（例：1）,\n      view：帖子观看人数（例：1.1K）\n    }\n]\n\n提取规则：\n1. 必须仅在当前 article 内部执行，禁止跨 article 拼接；\n2. 务必按照顺序获取当前 article 片段的相关信息，绝不可以跨片段获取数据内容；\n3. 最终返回 JSON 数组，不输出任何解释、注释或 Markdown 包裹。\n`",
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
//							"jaxId": "1JC3LIN7C0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC3M4IAB0"
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
//					"def": "connector",
//					"jaxId": "1JC3LJP3A0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1295",
//						"y": "-40",
//						"outlet": {
//							"jaxId": "1JC3LKMFH0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC3LJSTV0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JC3LJSTV0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "740",
//						"y": "-40",
//						"outlet": {
//							"jaxId": "1JC3LKMFH1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC3LDBR90"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JC3M4IAB0",
//					"attrs": {
//						"id": "SaveComments",
//						"viewName": "",
//						"label": "",
//						"x": "1350",
//						"y": "65",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC3M4TGN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC3M4TGN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JC3M4TGD0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JBCC5FKP0"
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
//					"jaxId": "1JC5LU0UL0",
//					"attrs": {
//						"id": "ClosePage_1",
//						"viewName": "",
//						"label": "",
//						"x": "700",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC5LU0UL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC5LU0UL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "300",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JC5LU0UM0",
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
//					"def": "brunch",
//					"jaxId": "1JCIGJ1QH0",
//					"attrs": {
//						"id": "CheckLength",
//						"viewName": "",
//						"label": "",
//						"x": "-175",
//						"y": "220",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIGJELP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIGJELP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JCIGJELG1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JCIJAR3L0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JCIGJELG0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JCIGJELP2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JCIGJELP3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.finds && input.finds.length > 0"
//									},
//									"linkedSeg": "1JBCAFG9K0"
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
//					"jaxId": "1JCIJAR3L0",
//					"attrs": {
//						"id": "NoData",
//						"viewName": "",
//						"label": "",
//						"x": "65",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIJB4GP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIJB4GP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JCIJB4GH0",
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
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}