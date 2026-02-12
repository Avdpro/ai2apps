//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JEV0H5CM0MoreImports*/
import {readFileAsDataURL,buildRpaMicroDeciderPrompt,readRule,saveRule,getRuleElementBySigKey,readRuleElements,findAvailableSelector,getRuleElementById} from "./utils.js";
/*}#1JEV0H5CM0MoreImports*/
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
		"selectDesc":{
			"name":"selectDesc","type":"string",
			"defaultValue":"",
			"desc":"",
		},
		"multiSelect":{
			"name":"multiSelect","type":"bool",
			"defaultValue":"",
			"desc":"",
		},
		"useManual":{
			"name":"useManual","type":"bool",
			"defaultValue":"",
			"desc":"",
		},
		"allowManual":{
			"name":"allowManual","type":"bool",
			"defaultValue":"",
			"desc":"",
		},
		"manualTraining":{
			"name":"manualTraining","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"ruleKey":{
			"name":"ruleKey","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JEV0H5CM0ArgsView*/
	/*}#1JEV0H5CM0ArgsView*/
};

/*#{1JEV0H5CM0StartDoc*/
/*}#1JEV0H5CM0StartDoc*/
//----------------------------------------------------------------------------
let Util_FindSelector=async function(session){
	let pageRef,url,profile,selectDesc,multiSelect,useManual,allowManual,manualTraining,ruleKey;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,ShowPage,ReadPage,UseManual,AskUser,ManualSelect,FinUserEnd,ReadCache,JumpAuto,ReadPicked,GenSelector,FindPicked,ConfirmPicked,TryAuto,FinManDone,RetryGen,FinManMaxRetry,FindSelector,CheckSelector,AllowManual,ConfirmSelector,CheckRetry,JumpManual,FinAutoDone,FinAutoMaxRetry,GoManual,CheckAbort,FinAbort;
	let usedSelector="";
	let wrongSelectors=[];
	let retryNum=0;
	let userResult="";
	let usedSigKey="";
	
	/*#{1JEV0H5CM0LocalVals*/
	/*}#1JEV0H5CM0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			url=input.url;
			profile=input.profile;
			selectDesc=input.selectDesc;
			multiSelect=input.multiSelect;
			useManual=input.useManual;
			allowManual=input.allowManual;
			manualTraining=input.manualTraining;
			ruleKey=input.ruleKey;
		}else{
			pageRef=undefined;
			url=undefined;
			profile=undefined;
			selectDesc=undefined;
			multiSelect=undefined;
			useManual=undefined;
			allowManual=undefined;
			manualTraining=undefined;
			ruleKey=undefined;
		}
		/*#{1JEV0H5CM0ParseArgs*/
		/*}#1JEV0H5CM0ParseArgs*/
	}
	
	/*#{1JEV0H5CM0PreContext*/
	/*}#1JEV0H5CM0PreContext*/
	context={
		html: "",
		/*#{1JEV0H5CM5ExCtxAttrs*/
		/*}#1JEV0H5CM5ExCtxAttrs*/
	};
	/*#{1JEV0H5CM0PostContext*/
	/*}#1JEV0H5CM0PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JEV0VCEL0
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JEV0VCEL0"));
				if($alias){
					let $headless=false;
					let $devtools=false;
					let options={headless:$headless,devtools:$devtools,autoDataDir:false};
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
		return {seg:ShowPage,result:(result),preSeg:"1JEV0VCEL0",outlet:"1JEV0VCEM0"};
	};
	StartRpa.jaxId="1JEV0VCEL0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1JEV12CMJ0
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
			/*#{1JEV12CMJ0ErrorCode*/
			/*}#1JEV12CMJ0ErrorCode*/
		}
		return {seg:ReadPage,result:(result),preSeg:"1JEV12CMJ0",outlet:"1JEV1EQB92"};
	};
	ShowPage.jaxId="1JEV12CMJ0"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1JEV10TS70
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
			/*#{1JEV10TS70ErrorCode*/
			/*}#1JEV10TS70ErrorCode*/
		}
		context["html"]=result;
		return {seg:UseManual,result:(result),preSeg:"1JEV10TS70",outlet:"1JEV115G20"};
	};
	ReadPage.jaxId="1JEV10TS70"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["UseManual"]=UseManual=async function(input){//:1JEV12RDR0
		let result=input;
		if(useManual){
			return {seg:AskUser,result:(input),preSeg:"1JEV12RDR0",outlet:"1JEV1EQB93"};
		}
		return {seg:FindSelector,result:(result),preSeg:"1JEV12RDR0",outlet:"1JEV1EQB94"};
	};
	UseManual.jaxId="1JEV12RDR0"
	UseManual.url="UseManual@"+agentURL
	
	segs["AskUser"]=AskUser=async function(input){//:1JFH2QBCT0
		let result=input;
		/*#{1JFH2QBCT0Start*/
		let webRpa,page,res;
		webRpa=context.webRpa;
		page=context.aaPage;
		res=await webRpa.inPagePrompt(
			page,`当前RPA步骤需要选择满足：\n"${selectDesc}"的元素。\n是否继续选择或者跳过/失败这个步骤？`,
			{
				menu:[
					{text:"🎯: 人工选择一个元素再由AI生成Selector。",code:"select"},
					{text:"🤖: 由AI自主生成Selector。",code:"auto"},
					{text:"⏭️: 跳过当前步骤。",code:"skip"},
					{text:"❌: 使当前步骤失败。",code:"fail"},
				]
			}
		);
		/*}#1JFH2QBCT0Start*/
		if(res.code==="select"){
			return {seg:ManualSelect,result:(input),preSeg:"1JFH2QBCT0",outlet:"1JFH2VUAI0"};
		}
		if(res.code==="skip"){
			/*#{1JFH2R5UO0Codes*/
			userResult="skipped";
			/*}#1JFH2R5UO0Codes*/
			return {seg:FinUserEnd,result:(input),preSeg:"1JFH2QBCT0",outlet:"1JFH2R5UO0"};
		}
		if(res.code==="fail"){
			/*#{1JFH2RGR90Codes*/
			userResult="failed";
			/*}#1JFH2RGR90Codes*/
			return {seg:FinUserEnd,result:(input),preSeg:"1JFH2QBCT0",outlet:"1JFH2RGR90"};
		}
		if(res.code==="auto"){
			return {seg:FindSelector,result:(input),preSeg:"1JFH2QBCT0",outlet:"1JFHJSK060"};
		}
		/*#{1JFH2QBCT0Post*/
		/*}#1JFH2QBCT0Post*/
		return {seg:FindSelector,result:(result),preSeg:"1JFH2QBCT0",outlet:"1JFH2VUAI1"};
	};
	AskUser.jaxId="1JFH2QBCT0"
	AskUser.url="AskUser@"+agentURL
	
	segs["ManualSelect"]=ManualSelect=async function(input){//:1JEV18PA20
		let result=input;
		/*#{1JEV18PA20Start*/
		let element;
		await context.webRpa.inPageTip(context.aaPage,`请选择满足："${selectDesc}"的元素。\n按Esc键放弃，按Control键选择当前高亮元素的上一级元素。`,{timeout:0});
		element=await context.webRpa.inPagePickDomElement(context.aaPage,{attr:"data-manual-picked"});
		await context.webRpa.inPageTipDismiss(context.aaPage);
		/*}#1JEV18PA20Start*/
		if(!element){
			return {seg:JumpAuto,result:(input),preSeg:"1JEV18PA20",outlet:"1JEV1EQB95"};
		}
		/*#{1JEV18PA20Post*/
		context.aaPage.disown(element);
		/*}#1JEV18PA20Post*/
		return {seg:ReadPicked,result:(result),preSeg:"1JEV18PA20",outlet:"1JEV1EQB96"};
	};
	ManualSelect.jaxId="1JEV18PA20"
	ManualSelect.url="ManualSelect@"+agentURL
	
	segs["FinUserEnd"]=FinUserEnd=async function(input){//:1JFH5JV6O0
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		/*#{1JFH5JV6O0PreCodes*/
		if (userResult === "skipped") {
			result = { status:"skipped", value:null };
		} else { // failed
			result = { status:"failed", reason:`User chose fail.` };
		}
		/*}#1JFH5JV6O0PreCodes*/
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JFH5JV6O0ErrorCode*/
			/*}#1JFH5JV6O0ErrorCode*/
		}
		/*#{1JFH5JV6O0PostCodes*/
		/*}#1JFH5JV6O0PostCodes*/
		return {result:result};
	};
	FinUserEnd.jaxId="1JFH5JV6O0"
	FinUserEnd.url="FinUserEnd@"+agentURL
	
	segs["ReadCache"]=ReadCache=async function(input){//:1JFKQT2KJ0
		let result=input;
		/*#{1JFKQT2KJ0Start*/
		let webRpa,page;
		let sigKey,element,selector,selectors,nodes,node,a;
		webRpa=context.webRpa;
		page=context.aaPage;
		usedSigKey=sigKey=await webRpa.computeSigKeyForSelector(page,'[data-manual-picked="true"]');
		if(sigKey){
			element=await getRuleElementBySigKey(session,page,sigKey);
			if(element){
				selectors=element.value;
				if(!Array.isArray(selectors)){
					selectors=[selectors];
				}
				FindSel:{
					for(selector of selectors){
						nodes=await webRpa.queryNodes(page,null,selector);
						for(node of nodes){
							a=node.attrs||node.attributes;
							if(a && a["data-manual-picked"]==="true"){
								usedSelector=selector;
								break FindSel;
							}
						}
					}
					usedSelector=null;
				}
			}
		}
		/*}#1JFKQT2KJ0Start*/
		if(usedSelector){
			return {seg:ConfirmPicked,result:(input),preSeg:"1JFKQT2KJ0",outlet:"1JFKRAPR60"};
		}
		/*#{1JFKQT2KJ0Post*/
		/*}#1JFKQT2KJ0Post*/
		return {seg:GenSelector,result:(result),preSeg:"1JFKQT2KJ0",outlet:"1JFKRAPR61"};
	};
	ReadCache.jaxId="1JFKQT2KJ0"
	ReadCache.url="ReadCache@"+agentURL
	
	segs["JumpAuto"]=JumpAuto=async function(input){//:1JEV50F390
		let result=input;
		return {seg:CheckAbort,result:result,preSeg:"1JF1IH4B40",outlet:"1JEV5168D0"};
	
	};
	JumpAuto.jaxId="1JF1IH4B40"
	JumpAuto.url="JumpAuto@"+agentURL
	
	segs["ReadPicked"]=ReadPicked=async function(input){//:1JF00G2A10
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
			/*#{1JF00G2A10ErrorCode*/
			/*}#1JF00G2A10ErrorCode*/
		}
		context["html"]=result;
		return {seg:ReadCache,result:(result),preSeg:"1JF00G2A10",outlet:"1JF00GKH40"};
	};
	ReadPicked.jaxId="1JF00G2A10"
	ReadPicked.url="ReadPicked@"+agentURL
	
	segs["GenSelector"]=GenSelector=async function(input){//:1JEV1AHEM0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5";
		let $agent;
		let result=null;
		/*#{1JEV1AHEM0Input*/
		let $system;
		if(multiSelect){
			$system=buildRpaMicroDeciderPrompt(
				`给定当前页面清洗后的HTML代码，写一个selector，能找到"data-manual-picked"="true"的元素以及与它类似的，满足条件"${selectDesc}"的全部元素。注意你的selector不能使用"data-manual-picked"属性。`,
				'如果有能找到目标元素的selector，返回"selector"动作，给出要点击的元素的selector。\n'+
				'如果当前页面不存在目标元素，或页面出错，比如404等，返回"abort"动作\n'+
				(wrongSelectors.length?`\n\n重要: 已知：${JSON.stringify(wrongSelectors,null,"    ")} 这些selector是错误无效的，不要重复给出重复的错误答案。`:""),
				["selector"]
			);
		}else{
			$system=buildRpaMicroDeciderPrompt(
				`给定当前页面清洗后的HTML代码，写一个selector，找到"data-manual-picked"="true"的元素。注意你的selector不能使用"data-manual-picked"属性。`,
				'如果有能找到目标元素的selector，返回"selector"动作，给出要点击的元素的selector。\n'+
				'如果当前页面不存在目标元素，或页面出错，比如404等，返回"abort"动作\n'+
				(wrongSelectors.length?`\n\n重要: 已知：${JSON.stringify(wrongSelectors,null,"    ")} 这些selector是错误无效的，不要重复给出重复的错误答案。`:""),
				["selector"]
			);
		}
		await context.webRpa.inPageTip(context.aaPage,`正在根据选择生成元素的 Selector……`,{timeout:0});
		/*}#1JEV1AHEM0Input*/
		
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
		let chatMem=GenSelector.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:$system},
		];
		/*#{1JEV1AHEM0PrePrompt*/
		/*}#1JEV1AHEM0PrePrompt*/
		prompt=context.html;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JEV1AHEM0FilterMessage*/
			/*}#1JEV1AHEM0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JEV1AHEM0PreCall*/
		/*}#1JEV1AHEM0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("GenSelector@"+agentURL,opts,messages,true)):result;
		}
		result=trimJSON(result);
		/*#{1JEV1AHEM0PostCall*/
		await context.webRpa.inPageTipDismiss(context.aaPage);
		/*}#1JEV1AHEM0PostCall*/
		if(result && result.action && result.action.type==="selector"){
			let output=result.action.by;
			return {seg:FindPicked,result:(output),preSeg:"1JEV1AHEM0",outlet:"1JEV56THG0"};
		}
		/*#{1JEV1AHEM0PreResult*/
		/*}#1JEV1AHEM0PreResult*/
		return {seg:CheckAbort,result:(result),preSeg:"1JEV1AHEM0",outlet:"1JEV1EQBA0"};
	};
	GenSelector.jaxId="1JEV1AHEM0"
	GenSelector.url="GenSelector@"+agentURL
	
	segs["FindPicked"]=FindPicked=async function(input){//:1JF01ERCT0
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query=input;
		let $multi=true;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1JF01ERCT0PreCodes*/
		usedSelector=$query;
		/*}#1JF01ERCT0PreCodes*/
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			/*#{1JF01ERCT0CheckItem*/
			if(multiSelect){
				let el,a;
				FindTgt:{
					for(el of result){
						a=el.attrs||el.attributes;
						if(a && a["data-manual-picked"]==="true"){
							break FindTgt;
						}
					}
					throw "Querry not found";
				}
			}else{
				if(result.length>1){
					throw `Not unique: matched ${result.length} elements`;
				}
				let a=result[0].attrs||result[0].attributes;
				if(a["data-manual-picked"]!=="true"){
					throw "Querry error";
				}
			}
			/*}#1JF01ERCT0CheckItem*/
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JF01ERCT0ErrorCode*/
			const msg = String(error);
			if (msg.startsWith("Not unique:")) {
				wrongSelectors.push(`${$query} 需要更精确：${msg}。请生成能唯一匹配目标元素的 selector。`);
			} else {
				wrongSelectors.push(`${$query} 无效：${msg}`);
			}
			/*}#1JF01ERCT0ErrorCode*/
			return {seg:RetryGen,result:error,preSeg:"1JF01ERCT0",outlet:"1JF01ERCE0"};
		}
		/*#{1JF01ERCT0PostCodes*/
		/*}#1JF01ERCT0PostCodes*/
		return {seg:ConfirmPicked,result:(result),preSeg:"1JF01ERCT0",outlet:"1JF01G0QA0"};
	};
	FindPicked.jaxId="1JF01ERCT0"
	FindPicked.url="FindPicked@"+agentURL
	
	segs["ConfirmPicked"]=ConfirmPicked=async function(input){//:1JF1ECNIG0
		let result=input;
		/*#{1JF1ECNIG0Start*/
		let confirm,advice;
		await context.webRpa.inPageShowSelector(context.aaPage,usedSelector);
		confirm=await context.webRpa.inPagePrompt(context.aaPage,`AI生成的 selector 是:\n"${usedSelector}"\n该 selector 选择的元素正被高亮显示，请确认选择的是否是正确的元素。你也可以提供修改意见，重新生成 selector，`,{
			menu:[
				{text:"正确，使用这个 selector。",code:true},
				{text:"错误，重新生成 selector。",code:false},
			],
			edit:true,editText:"",placeHolder:"输入修改意见",
			okText:"按修改意见重新生成 selector",
			modal:false,mask:false,
			//icon:null,okText:"正确",cancelText:"不正确",showCancel:true,modal:false
		});
		await context.webRpa.inPageDismissSelector(context.aaPage);
		if(confirm?.code===true){
			confirm=true;
		}else if(confirm?.code===false){
			confirm=false;
		}else{
			advice=confirm;
		}
		/*}#1JF1ECNIG0Start*/
		if(confirm===true){
			return {seg:FinManDone,result:(input),preSeg:"1JF1ECNIG0",outlet:"1JF1ECNIH3"};
		}
		if(advice){
			/*#{1JFHKT2B70Codes*/
			wrongSelectors.push(`'${usedSelector}' 用户修改建议：${advice}`);
			/*}#1JFHKT2B70Codes*/
			return {seg:RetryGen,result:(input),preSeg:"1JF1ECNIG0",outlet:"1JFHKT2B70"};
		}
		/*#{1JF1ECNIG0Post*/
		wrongSelectors.push(`'${usedSelector}' 错误：用户拒绝。`);
		/*}#1JF1ECNIG0Post*/
		return {seg:RetryGen,result:(result),preSeg:"1JF1ECNIG0",outlet:"1JF1ECNIH2"};
	};
	ConfirmPicked.jaxId="1JF1ECNIG0"
	ConfirmPicked.url="ConfirmPicked@"+agentURL
	
	segs["TryAuto"]=TryAuto=async function(input){//:1JEV57A4K0
		let result=input;
		return {seg:FindSelector,result:result,preSeg:"1JEV1198Q0",outlet:"1JEV57LLH0"};
	
	};
	TryAuto.jaxId="1JEV1198Q0"
	TryAuto.url="TryAuto@"+agentURL
	
	segs["FinManDone"]=FinManDone=async function(input){//:1JEV3185N0
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		/*#{1JEV3185N0PreCodes*/
		/*}#1JEV3185N0PreCodes*/
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JEV3185N0ErrorCode*/
			/*}#1JEV3185N0ErrorCode*/
		}
		/*#{1JEV3185N0PostCodes*/
		result={status:"done",selector:usedSelector,value:usedSelector,sigKey:usedSigKey};
		/*}#1JEV3185N0PostCodes*/
		return {result:result};
	};
	FinManDone.jaxId="1JEV3185N0"
	FinManDone.url="FinManDone@"+agentURL
	
	segs["RetryGen"]=RetryGen=async function(input){//:1JEV23JVF0
		let result=input;
		/*#{1JEV23JVF0Start*/
		/*}#1JEV23JVF0Start*/
		if((++retryNum)>3){
			return {seg:FinManMaxRetry,result:(input),preSeg:"1JEV23JVF0",outlet:"1JEV2593T0"};
		}
		/*#{1JEV23JVF0Post*/
		await context.webRpa.inPageTip(context.aaPage,"生成的Selector不能满足需求，需要重新生成",{id:"Info",timeout:5000});
		/*}#1JEV23JVF0Post*/
		return {seg:GenSelector,result:(result),preSeg:"1JEV23JVF0",outlet:"1JEV2593T1"};
	};
	RetryGen.jaxId="1JEV23JVF0"
	RetryGen.url="RetryGen@"+agentURL
	
	segs["FinManMaxRetry"]=FinManMaxRetry=async function(input){//:1JEV320VJ0
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		/*#{1JEV320VJ0PreCodes*/
		/*}#1JEV320VJ0PreCodes*/
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JEV320VJ0ErrorCode*/
			/*}#1JEV320VJ0ErrorCode*/
		}
		/*#{1JEV320VJ0PostCodes*/
		result={status:"failed",result:"failed",reason:"Max retry"};
		/*}#1JEV320VJ0PostCodes*/
		return {result:result};
	};
	FinManMaxRetry.jaxId="1JEV320VJ0"
	FinManMaxRetry.url="FinManMaxRetry@"+agentURL
	
	segs["FindSelector"]=FindSelector=async function(input){//:1JEV1198Q0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5";
		let $agent;
		let result=null;
		/*#{1JEV1198Q0Input*/
		let $system;
		if(multiSelect){
			$system=buildRpaMicroDeciderPrompt(
				`给定当前页面清洗后的HTML代码，确认是否可以找到全部目标为: ${selectDesc}的HTML元素。如果是，返回选择全部符合目标的HTML元素的selector。`,
				'如果有能找到目标元素的selector，返回"selector"动作，给出选择全部目标元素的selector。\n'+
				'如果当前页面不存在目标元素，或页面出错，比如404等，返回"abort"动作\n'+
				(wrongSelectors.length?`\n\n重要: 已知：${JSON.stringify(wrongSelectors)} 这些selector是错误无效的，不要重复给出重复的错误答案。`:""),
				["selector"]
			);		
		}else{
			$system=buildRpaMicroDeciderPrompt(
				`给定当前页面清洗后的HTML代码，确认是否可以找到一个目标元素: ${selectDesc}。如果是，返回更能选择到唯一的指定元素的HTML元素的selector。`,
				'如果有能找到目标元素的selector，返回"selector"动作，给出选择目标元素的selector。\n'+
				'如果当前页面不存在目标元素，或页面出错，比如404等，返回"abort"动作\n'+
				(wrongSelectors.length?`\n\n重要: 已知：${JSON.stringify(wrongSelectors)} 这些selector是错误无效的，不要重复给出重复的错误答案。`:""),
				["selector"]
			);		
		}
		await context.webRpa.inPageTip(context.aaPage,`正在根据要求生成选择成元素的 Selector……`,{timeout:0});
		/*}#1JEV1198Q0Input*/
		
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
		let chatMem=FindSelector.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:$system},
		];
		/*#{1JEV1198Q0PrePrompt*/
		/*}#1JEV1198Q0PrePrompt*/
		prompt=context.html;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JEV1198Q0FilterMessage*/
			/*}#1JEV1198Q0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JEV1198Q0PreCall*/
		/*}#1JEV1198Q0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("FindSelector@"+agentURL,opts,messages,true)):result;
		}
		result=trimJSON(result);
		/*#{1JEV1198Q0PostCall*/
		await context.webRpa.inPageTipDismiss(context.aaPage);
		/*}#1JEV1198Q0PostCall*/
		if(result && result.action && result.action.type==="selector"){
			let output=result.action.by;
			return {seg:CheckSelector,result:(output),preSeg:"1JEV1198Q0",outlet:"1JEV1EQB90"};
		}
		/*#{1JEV1198Q0PreResult*/
		/*}#1JEV1198Q0PreResult*/
		return {seg:AllowManual,result:(result),preSeg:"1JEV1198Q0",outlet:"1JEV1EQB91"};
	};
	FindSelector.jaxId="1JEV1198Q0"
	FindSelector.url="FindSelector@"+agentURL
	
	segs["CheckSelector"]=CheckSelector=async function(input){//:1JEV1BB5P0
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query=input;
		let $multi=true;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1JEV1BB5P0PreCodes*/
		usedSelector=$query;
		/*}#1JEV1BB5P0PreCodes*/
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			/*#{1JEV1BB5P0CheckItem*/
			/*}#1JEV1BB5P0CheckItem*/
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JEV1BB5P0ErrorCode*/
			wrongSelectors.push(`${usedSelector}：${error}`);
			/*}#1JEV1BB5P0ErrorCode*/
			return {seg:CheckRetry,result:error,preSeg:"1JEV1BB5P0",outlet:"1JEV1BB590"};
		}
		/*#{1JEV1BB5P0PostCodes*/
		/*}#1JEV1BB5P0PostCodes*/
		return {seg:ConfirmSelector,result:(result),preSeg:"1JEV1BB5P0",outlet:"1JEV1EQBA1"};
	};
	CheckSelector.jaxId="1JEV1BB5P0"
	CheckSelector.url="CheckSelector@"+agentURL
	
	segs["AllowManual"]=AllowManual=async function(input){//:1JEV1CR6C0
		let result=input;
		if(!allowManual && !useManual){
			return {seg:CheckRetry,result:(input),preSeg:"1JEV1CR6C0",outlet:"1JEV1EQBA2"};
		}
		return {seg:JumpManual,result:(result),preSeg:"1JEV1CR6C0",outlet:"1JEV1EQBA3"};
	};
	AllowManual.jaxId="1JEV1CR6C0"
	AllowManual.url="AllowManual@"+agentURL
	
	segs["ConfirmSelector"]=ConfirmSelector=async function(input){//:1JEV1OTG40
		let result=input;
		/*#{1JEV1OTG40Start*/
		let confirm,advice,retry;
		await context.webRpa.inPageShowSelector(context.aaPage,usedSelector);
		confirm=await context.webRpa.inPagePrompt(context.aaPage,`AI生成的 selector 是:\n"${usedSelector}"\n该 selector 选择的元素正被高亮显示，请确认选择的是否是正确的元素。你也可以提供修改意见，重新生成 selector，`,{
			menu:[
				{text:"正确，使用这个 selector。",code:true},
				{text:"错误，重新生成 selector。",code:false},
				{text:"错误，进行人工指导",code:"manual"},
			],
			edit:true,editText:"",placeHolder:"输入修改意见",
			okText:"按修改意见重新生成 selector",
			modal:false,mask:false,
			//icon:null,okText:"正确",cancelText:"不正确",showCancel:true,modal:false
		});
		await context.webRpa.inPageDismissSelector(context.aaPage);
		if(confirm?.code===true){
			confirm=true;
		}else if(confirm?.code===false){
			retry=true;
			confirm=false;
			wrongSelectors.push(`'${usedSelector}' 错误：用户拒绝`);
		}else if(confirm?.code==="manual"){
			confirm=false;
			retry=false;
		}else{
			advice=confirm;
			confirm=false;
			wrongSelectors.push(`'${usedSelector}' 用户修改建议：${advice}`);
		}
		/*}#1JEV1OTG40Start*/
		if(confirm){
			/*#{1JEV1R1H90Codes*/
			try{
				usedSigKey=await context.webRpa.computeSigKeyForSelector(context.aaPage,usedSelector);
			}catch(err){
				usedSigKey=null;
			}
			/*}#1JEV1R1H90Codes*/
			return {seg:FinAutoDone,result:(input),preSeg:"1JEV1OTG40",outlet:"1JEV1R1H90"};
		}
		if(advice){
			return {seg:FindSelector,result:(input),preSeg:"1JEV1OTG40",outlet:"1JFHN32KJ0"};
		}
		if(retry){
			return {seg:FindSelector,result:(input),preSeg:"1JEV1OTG40",outlet:"1JFHN0F3Q0"};
		}
		/*#{1JEV1OTG40Post*/
		/*}#1JEV1OTG40Post*/
		return {seg:GoManual,result:(result),preSeg:"1JEV1OTG40",outlet:"1JEV1R1H91"};
	};
	ConfirmSelector.jaxId="1JEV1OTG40"
	ConfirmSelector.url="ConfirmSelector@"+agentURL
	
	segs["CheckRetry"]=CheckRetry=async function(input){//:1JEV1G7MR0
		let result=input;
		/*#{1JEV1G7MR0Start*/
		wrongSelectors.push(usedSelector);
		/*}#1JEV1G7MR0Start*/
		if((++retryNum)>3){
			/*#{1JEV1LAM80Codes*/
			/*}#1JEV1LAM80Codes*/
			return {seg:FinAutoMaxRetry,result:(input),preSeg:"1JEV1G7MR0",outlet:"1JEV1LAM80"};
		}
		/*#{1JEV1G7MR0Post*/
		await context.webRpa.inPageTip(context.aaPage,"生成的Selector不能满足需求，需要重新生成",{id:"Info",timeout:5000});
		/*}#1JEV1G7MR0Post*/
		return {seg:FindSelector,result:(result),preSeg:"1JEV1G7MR0",outlet:"1JEV1LAM81"};
	};
	CheckRetry.jaxId="1JEV1G7MR0"
	CheckRetry.url="CheckRetry@"+agentURL
	
	segs["JumpManual"]=JumpManual=async function(input){//:1JEV1DIOG0
		let result=input;
		return {seg:AskUser,result:result,preSeg:"1JFH2QBCT0",outlet:"1JEV1EQBA4"};
	
	};
	JumpManual.jaxId="1JFH2QBCT0"
	JumpManual.url="JumpManual@"+agentURL
	
	segs["FinAutoDone"]=FinAutoDone=async function(input){//:1JEV3305O0
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		/*#{1JEV3305O0PreCodes*/
		/*}#1JEV3305O0PreCodes*/
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JEV3305O0ErrorCode*/
			/*}#1JEV3305O0ErrorCode*/
		}
		/*#{1JEV3305O0PostCodes*/
		result={status:"done",value:usedSelector,selector:usedSelector,sigKey:usedSigKey};
		/*}#1JEV3305O0PostCodes*/
		return {result:result};
	};
	FinAutoDone.jaxId="1JEV3305O0"
	FinAutoDone.url="FinAutoDone@"+agentURL
	
	segs["FinAutoMaxRetry"]=FinAutoMaxRetry=async function(input){//:1JEV33MBI0
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		/*#{1JEV33MBI0PreCodes*/
		/*}#1JEV33MBI0PreCodes*/
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JEV33MBI0ErrorCode*/
			/*}#1JEV33MBI0ErrorCode*/
		}
		/*#{1JEV33MBI0PostCodes*/
		result={status:"failed",result:"failed",reason:"Max retry"};
		/*}#1JEV33MBI0PostCodes*/
		return {result:result};
	};
	FinAutoMaxRetry.jaxId="1JEV33MBI0"
	FinAutoMaxRetry.url="FinAutoMaxRetry@"+agentURL
	
	segs["GoManual"]=GoManual=async function(input){//:1JF1E66U90
		let result=input;
		return {seg:AskUser,result:result,preSeg:"1JFH2QBCT0",outlet:"1JF1E6NA70"};
	
	};
	GoManual.jaxId="1JFH2QBCT0"
	GoManual.url="GoManual@"+agentURL
	
	segs["CheckAbort"]=CheckAbort=async function(input){//:1JF1IH4B40
		let result=input;
		/*#{1JF1IH4B40Start*/
		let confirm;
		confirm=await context.webRpa.inPagePrompt(context.aaPage,"AI无法根据你选择的元素生成选择Selector。是否使用AI重新选择并生成Selector，或者放弃生成Selector？",{
			icon:null,okText:"放弃生成Selector",cancelText:"AI重新生成",showCancel:true,modal:false
		});
		/*}#1JF1IH4B40Start*/
		if(confirm){
			return {seg:FinAbort,result:(input),preSeg:"1JF1IH4B40",outlet:"1JF1IJLSU0"};
		}
		/*#{1JF1IH4B40Post*/
		/*}#1JF1IH4B40Post*/
		return {seg:TryAuto,result:(result),preSeg:"1JF1IH4B40",outlet:"1JF1IJLSU1"};
	};
	CheckAbort.jaxId="1JF1IH4B40"
	CheckAbort.url="CheckAbort@"+agentURL
	
	segs["FinAbort"]=FinAbort=async function(input){//:1JF1IJ8BR0
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		/*#{1JF1IJ8BR0PreCodes*/
		/*}#1JF1IJ8BR0PreCodes*/
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JF1IJ8BR0ErrorCode*/
			/*}#1JF1IJ8BR0ErrorCode*/
		}
		/*#{1JF1IJ8BR0PostCodes*/
		result={status:"failed",result:"failed",reason:"User abort."};
		/*}#1JF1IJ8BR0PostCodes*/
		return {result:result};
	};
	FinAbort.jaxId="1JF1IJ8BR0"
	FinAbort.url="FinAbort@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"Util_FindSelector",
		url:agentURL,
		autoStart:true,
		jaxId:"1JEV0H5CM0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,url,profile,selectDesc,multiSelect,useManual,allowManual,manualTraining,ruleKey}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JEV0H5CM0PreEntry*/
			/*}#1JEV0H5CM0PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JEV0H5CM0PostEntry*/
			/*}#1JEV0H5CM0PostEntry*/
			return result;
		},
		/*#{1JEV0H5CM0MoreAgentAttrs*/
		/*}#1JEV0H5CM0MoreAgentAttrs*/
	};
	/*#{1JEV0H5CM0PostAgent*/
	/*}#1JEV0H5CM0PostAgent*/
	return agent;
};
/*#{1JEV0H5CM0ExCodes*/
/*}#1JEV0H5CM0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "Util_FindSelector",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				url:{type:"auto",description:""},
				profile:{type:"auto",description:""},
				selectDesc:{type:"string",description:""},
				multiSelect:{type:"bool",description:""},
				useManual:{type:"bool",description:""},
				allowManual:{type:"bool",description:""},
				manualTraining:{type:"auto",description:""},
				ruleKey:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1JEV0H5CM0PostDoc*/
/*}#1JEV0H5CM0PostDoc*/


export default Util_FindSelector;
export{Util_FindSelector,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JEV0H5CM0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JEV0H5CM1",
//			"attrs": {
//				"Util_FindSelector": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JEV0H5CM7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JEV0H5CM8",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JEV0H5CM9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JEV0H5CM10",
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
//			"jaxId": "1JEV0H5CM2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JEV0H5CM3",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEV0RUMM0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEV10I8F0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"profile": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEV10I8F1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"selectDesc": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEV0RUMM1",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"multiSelect": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEV0RUMM2",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"useManual": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEV0RUMM3",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"allowManual": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEV0RUMM4",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"manualTraining": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFH1EU4L0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"ruleKey": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFKQSCTD0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JEV0H5CM4",
//			"attrs": {
//				"usedSelector": {
//					"type": "string",
//					"valText": ""
//				},
//				"wrongSelectors": {
//					"type": "auto",
//					"valText": "[]"
//				},
//				"retryNum": {
//					"type": "int",
//					"valText": "0"
//				},
//				"userResult": {
//					"type": "string",
//					"valText": ""
//				},
//				"usedSigKey": {
//					"type": "string",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JEV0H5CM5",
//			"attrs": {
//				"html": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JEV1LMQ00",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1JEV0H5CM6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JEV0VCEL0",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "95",
//						"y": "470",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEV0VCEL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV0VCEL2",
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
//							"jaxId": "1JEV0VCEM0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV12CMJ0"
//						},
//						"catchlet": {
//							"jaxId": "1JEV0VCEM1",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JEV0VCEM2",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JEV0VCEM3",
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
//					"def": "WebRpaActivePage",
//					"jaxId": "1JEV12CMJ0",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "330",
//						"y": "455",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEV1EQBC2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV1EQBC3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true,\"switchBack\":0}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JEV1EQB92",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV10TS70"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1JEV10TS70",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "575",
//						"y": "455",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV115G30",
//							"attrs": {
//								"cast": "{\"html\":\"result\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1JEV115G31",
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
//							"jaxId": "1JEV115G20",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV12RDR0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JEV12RDR0",
//					"attrs": {
//						"id": "UseManual",
//						"viewName": "",
//						"label": "",
//						"x": "845",
//						"y": "455",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV1EQBC4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV1EQBC5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEV1EQB94",
//							"attrs": {
//								"id": "Auto",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEV1198Q0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEV1EQB93",
//									"attrs": {
//										"id": "Manual",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEV1EQBC6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEV1EQBC7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#useManual"
//									},
//									"linkedSeg": "1JFH2QBCT0"
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
//					"jaxId": "1JFH2QBCT0",
//					"attrs": {
//						"id": "AskUser",
//						"viewName": "",
//						"label": "",
//						"x": "1080",
//						"y": "40",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFH2VUAS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFH2VUAS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFH2VUAI1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFHJR2D50"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFH2VUAI0",
//									"attrs": {
//										"id": "Select",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFH2VUAS2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFH2VUAS3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#res.code===\"select\""
//									},
//									"linkedSeg": "1JEV18PA20"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFH2R5UO0",
//									"attrs": {
//										"id": "Skip",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JFH2VUAS4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFH2VUAS5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#res.code===\"skip\""
//									},
//									"linkedSeg": "1JFH5JV6O0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFH2RGR90",
//									"attrs": {
//										"id": "Fail",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JFH2VUAS6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFH2VUAS7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#res.code===\"fail\""
//									},
//									"linkedSeg": "1JFH5JV6O0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFHJSK060",
//									"attrs": {
//										"id": "Auto",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFHJSK0G0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFHJSK0G1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#res.code===\"auto\""
//									},
//									"linkedSeg": "1JFHJR2D50"
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
//					"jaxId": "1JEV18PA20",
//					"attrs": {
//						"id": "ManualSelect",
//						"viewName": "",
//						"label": "",
//						"x": "1360",
//						"y": "-20",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV1EQBC8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV1EQBC9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEV1EQB96",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JF00G2A10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEV1EQB95",
//									"attrs": {
//										"id": "Failed",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEV1EQBC10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEV1EQBC11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!element"
//									},
//									"linkedSeg": "1JEV50F390"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JFH5JV6O0",
//					"attrs": {
//						"id": "FinUserEnd",
//						"viewName": "",
//						"label": "",
//						"x": "1360",
//						"y": "95",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFH5JV6O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFH5JV6O2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JFH5JV6O3",
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
//					"def": "brunch",
//					"jaxId": "1JFKQT2KJ0",
//					"attrs": {
//						"id": "ReadCache",
//						"viewName": "",
//						"label": "",
//						"x": "1870",
//						"y": "-5",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFKRAPRF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFKRAPRF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFKRAPR61",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEV1AHEM0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFKRAPR60",
//									"attrs": {
//										"id": "FindRule",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFKRAPRF2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFKRAPRF3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#usedSelector"
//									},
//									"linkedSeg": "1JFKTM8V40"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JEV50F390",
//					"attrs": {
//						"id": "JumpAuto",
//						"viewName": "",
//						"label": "",
//						"x": "1625",
//						"y": "-95",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JF1IH4B40",
//						"outlet": {
//							"jaxId": "1JEV5168D0",
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
//					"def": "WebRpaReadPage",
//					"jaxId": "1JF00G2A10",
//					"attrs": {
//						"id": "ReadPicked",
//						"viewName": "",
//						"label": "",
//						"x": "1625",
//						"y": "-5",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF00GKHB0",
//							"attrs": {
//								"cast": "{\"html\":\"result\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1JF00GKHB1",
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
//							"jaxId": "1JF00GKH40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFKQT2KJ0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JEV1AHEM0",
//					"attrs": {
//						"id": "GenSelector",
//						"viewName": "",
//						"label": "",
//						"x": "2170",
//						"y": "50",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV1EQBC14",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV1EQBC15",
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
//						"prompt": "#context.html",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1JEV1EQBA0",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1IH4B40"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1JF12NCC80",
//									"attrs": {
//										"reply": "{ \"action\": { \"type\": \"selector\", \"by\": \"css: textarea[placeholder='有什么新鲜事想分享给大家？']\" }, \"reason\": \"目标是发布编辑区的 textarea，页面仅此一处，使用唯一的 placeholder 文案即可稳定定位，且未使用 data-manual-picked 属性。\", \"summary\": \"微博首页发布编辑器存在；定位 placeholder 为“有什么新鲜事想分享给大家？”的 textarea；预期命中目标元素；风险：若占位文案改动可能失效。\" }",
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
//									"jaxId": "1JEV56THG0",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "#result.action.by",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEV56THN0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEV56THN1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action && result.action.type===\"selector\""
//									},
//									"linkedSeg": "1JF01ERCT0"
//								}
//							]
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JF01ERCT0",
//					"attrs": {
//						"id": "FindPicked",
//						"viewName": "",
//						"label": "",
//						"x": "2445",
//						"y": "35",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF01G0QH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF01G0QH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "#input",
//						"queryHint": "",
//						"multi": "true",
//						"options": "",
//						"errorSeg": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JF01G0QA0",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1ECNIG0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JF01ERCE0",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									},
//									"linkedSeg": "1JFHKRGH30"
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JF1ECNIG0",
//					"attrs": {
//						"id": "ConfirmPicked",
//						"viewName": "",
//						"label": "",
//						"x": "2685",
//						"y": "-75",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JF1ECNIH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1ECNIH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1ECNIH2",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEV23JVF0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1ECNIH3",
//									"attrs": {
//										"id": "Comfirm",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1ECNIH4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1ECNIH5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#confirm===true"
//									},
//									"linkedSeg": "1JEV3185N0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFHKT2B70",
//									"attrs": {
//										"id": "Advice",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JFHKT2BF0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFHKT2BF1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#advice"
//									},
//									"linkedSeg": "1JEV23JVF0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JEV57A4K0",
//					"attrs": {
//						"id": "TryAuto",
//						"viewName": "",
//						"label": "",
//						"x": "2685",
//						"y": "295",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JEV1198Q0",
//						"outlet": {
//							"jaxId": "1JEV57LLH0",
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
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JEV3185N0",
//					"attrs": {
//						"id": "FinManDone",
//						"viewName": "",
//						"label": "",
//						"x": "2965",
//						"y": "-105",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV3185N1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV3185N2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JEV3185N3",
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
//					"def": "brunch",
//					"jaxId": "1JEV23JVF0",
//					"attrs": {
//						"id": "RetryGen",
//						"viewName": "",
//						"label": "",
//						"x": "2965",
//						"y": "105",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV2593V1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV2593V2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEV2593T1",
//							"attrs": {
//								"id": "Retry",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEV1TIAG0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEV2593T0",
//									"attrs": {
//										"id": "MaxRetry",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEV2593V3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEV2593V4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#(++retryNum)>3"
//									},
//									"linkedSeg": "1JEV320VJ0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JEV320VJ0",
//					"attrs": {
//						"id": "FinManMaxRetry",
//						"viewName": "",
//						"label": "",
//						"x": "3250",
//						"y": "90",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV320VK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV320VK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JEV320VK2",
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
//					"def": "callLLM",
//					"jaxId": "1JEV1198Q0",
//					"attrs": {
//						"id": "FindSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1080",
//						"y": "665",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV1EQBB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV1EQBB1",
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
//						"prompt": "#context.html",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1JEV1EQB91",
//							"attrs": {
//								"id": "NotFound",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV1CR6C0"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1JF02MMD20",
//									"attrs": {
//										"reply": "{ \"action\": { \"type\": \"selector\", \"by\": \"css: textarea[placeholder*='新鲜事']\" }, \"reason\": \"页面顶部有发帖编辑区，textarea 占位符为“有什么新鲜事想分享给大家？”，旁边带有“发送”按钮，符合目标。\", \"summary\": \"微博首页发布卡片可见；定位发帖主编辑textarea；预期选中撰写输入区以便后续输入。\" }",
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
//									"jaxId": "1JEV1EQB90",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "#result.action.by",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEV1EQBC0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEV1EQBC1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action && result.action.type===\"selector\""
//									},
//									"linkedSeg": "1JEV1BB5P0"
//								}
//							]
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JEV1BB5P0",
//					"attrs": {
//						"id": "CheckSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1360",
//						"y": "650",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV1EQBC16",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV1EQBC17",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "#input",
//						"queryHint": "",
//						"multi": "true",
//						"options": "",
//						"errorSeg": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JEV1EQBA1",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV1OTG40"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JEV1BB590",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									},
//									"linkedSeg": "1JEV1G7MR0"
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JEV1CR6C0",
//					"attrs": {
//						"id": "AllowManual",
//						"viewName": "",
//						"label": "",
//						"x": "1360",
//						"y": "785",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEV1EQBC18",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV1EQBC19",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEV1EQBA3",
//							"attrs": {
//								"id": "Allow",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEV1DIOG0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEV1EQBA2",
//									"attrs": {
//										"id": "NotAllow",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEV1EQBC20",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEV1EQBC21",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!allowManual && !useManual"
//									},
//									"linkedSeg": "1JEV1G7MR0"
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
//					"jaxId": "1JEV1OTG40",
//					"attrs": {
//						"id": "ConfirmSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1620",
//						"y": "520",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV1R1HA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV1R1HA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEV1R1H91",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JF1E66U90"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEV1R1H90",
//									"attrs": {
//										"id": "Comfirm",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JEV1R1HA2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEV1R1HA3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#confirm"
//									},
//									"linkedSeg": "1JEV3305O0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFHN32KJ0",
//									"attrs": {
//										"id": "Advice",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFHN32KT0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFHN32KT1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#advice"
//									},
//									"linkedSeg": "1JFHN22OB0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFHN0F3Q0",
//									"attrs": {
//										"id": "Retry",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFHN32KT2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFHN32KT3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#retry"
//									},
//									"linkedSeg": "1JFHN22OB0"
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
//					"jaxId": "1JEV1G7MR0",
//					"attrs": {
//						"id": "CheckRetry",
//						"viewName": "",
//						"label": "",
//						"x": "1625",
//						"y": "715",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV1LAMB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV1LAMB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEV1LAM81",
//							"attrs": {
//								"id": "Retry",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEV1K6RI0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEV1LAM80",
//									"attrs": {
//										"id": "MaxRetry",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JEV1LAMB2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEV1LAMB3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#(++retryNum)>3"
//									},
//									"linkedSeg": "1JEV33MBI0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JEV1DIOG0",
//					"attrs": {
//						"id": "JumpManual",
//						"viewName": "",
//						"label": "",
//						"x": "1625",
//						"y": "855",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JFH2QBCT0",
//						"outlet": {
//							"jaxId": "1JEV1EQBA4",
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
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JEV3305O0",
//					"attrs": {
//						"id": "FinAutoDone",
//						"viewName": "",
//						"label": "",
//						"x": "1900",
//						"y": "415",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV3305O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV3305O2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JEV3305O3",
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
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JEV33MBI0",
//					"attrs": {
//						"id": "FinAutoMaxRetry",
//						"viewName": "",
//						"label": "",
//						"x": "1900",
//						"y": "700",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JEV33MBI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEV33MBI2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JEV33MBI3",
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
//					"def": "connector",
//					"jaxId": "1JEV1K6RI0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1790",
//						"y": "950",
//						"outlet": {
//							"jaxId": "1JEV1LAMB6",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV1KSDA0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JEV1KSDA0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1095",
//						"y": "950",
//						"outlet": {
//							"jaxId": "1JEV1LAMB7",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV1198Q0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JEV1TIAG0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3115",
//						"y": "340",
//						"outlet": {
//							"jaxId": "1JEV2593V0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV250680"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JEV250680",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2195",
//						"y": "340",
//						"outlet": {
//							"jaxId": "1JEV2593V5",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV1AHEM0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JF1E66U90",
//					"attrs": {
//						"id": "GoManual",
//						"viewName": "",
//						"label": "",
//						"x": "1900",
//						"y": "610",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JFH2QBCT0",
//						"outlet": {
//							"jaxId": "1JF1E6NA70",
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
//					"def": "brunch",
//					"jaxId": "1JF1IH4B40",
//					"attrs": {
//						"id": "CheckAbort",
//						"viewName": "",
//						"label": "",
//						"x": "2445",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1IJLT40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1IJLT41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JF1IJLSU1",
//							"attrs": {
//								"id": "Auto",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JEV57A4K0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JF1IJLSU0",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JF1IJLT42",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JF1IJLT43",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#confirm"
//									},
//									"linkedSeg": "1JF1IJ8BR0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JF1IJ8BR0",
//					"attrs": {
//						"id": "FinAbort",
//						"viewName": "",
//						"label": "",
//						"x": "2685",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1IJLT44",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1IJLT45",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JF1IJLSU2",
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
//					"def": "connectorT",
//					"jaxId": "1JFHJR2D50",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1265",
//						"y": "280",
//						"outlet": {
//							"jaxId": "1JFHJSK0H0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFHJRO900"
//						},
//						"dir": "T2B"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JFHJRO900",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1115",
//						"y": "440",
//						"outlet": {
//							"jaxId": "1JFHJSK0H1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV1198Q0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JFHKRGH30",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2685",
//						"y": "105",
//						"outlet": {
//							"jaxId": "1JFHKT2BF2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV23JVF0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JFHN22OB0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1900",
//						"y": "515",
//						"outlet": {
//							"jaxId": "1JFHN32KT4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFHN2J0D0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JFHN2J0D0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2155",
//						"y": "515",
//						"outlet": {
//							"jaxId": "1JFHN32KT5",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFHN2MA60"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JFHN2MA60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2165",
//						"y": "950",
//						"outlet": {
//							"jaxId": "1JFHN32KT6",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEV1K6RI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JFKTM8V40",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2165",
//						"y": "-75",
//						"outlet": {
//							"jaxId": "1JFLNT00N0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1ECNIG0"
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