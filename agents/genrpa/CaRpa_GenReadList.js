//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JE5HBFRE0MoreImports*/
import {buildRpaMicroDeciderPrompt,readRule,saveRule} from "./utils.js";
import getMergedItemSchema from "./util_item_types.js";
/*}#1JE5HBFRE0MoreImports*/
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
		"read":{
			"name":"read","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"minItems":{
			"name":"minItems","type":"integer",
			"defaultValue":0,
			"desc":"",
		},
		"maxItems":{
			"name":"maxItems","type":"integer",
			"defaultValue":0,
			"desc":"",
		}
	},
	/*#{1JE5HBFRE0ArgsView*/
	/*}#1JE5HBFRE0ArgsView*/
};

/*#{1JE5HBFRE0StartDoc*/
/*}#1JE5HBFRE0StartDoc*/
//----------------------------------------------------------------------------
let CaRpa_GenReadList=async function(session){
	let pageRef,url,profile,waitAfter,read,minItems,maxItems;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,CheckRule,RunRule,GenCode,ReadPage,RunCode,CheckNumber,NewRule,SaveRule,FinDone,WaitAfter,ShowMore,CheckMore,JumpReadPage,CheckBlocker,FinNoItems,FinFailed,JumpNoMore,HasItems,FinMaxRun;
	let wrongCodes=[];
	let runNum=0;
	
	/*#{1JE5HBFRE0LocalVals*/
	/*}#1JE5HBFRE0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			url=input.url;
			profile=input.profile;
			waitAfter=input.waitAfter;
			read=input.read;
			minItems=input.minItems;
			maxItems=input.maxItems;
		}else{
			pageRef=undefined;
			url=undefined;
			profile=undefined;
			waitAfter=undefined;
			read=undefined;
			minItems=undefined;
			maxItems=undefined;
		}
		/*#{1JE5HBFRE0ParseArgs*/
		/*}#1JE5HBFRE0ParseArgs*/
	}
	
	/*#{1JE5HBFRE0PreContext*/
	/*}#1JE5HBFRE0PreContext*/
	context={
		grabCode: "",
		items: [],
		ruleCode: "",
		/*#{1JE5HBFRE5ExCtxAttrs*/
		/*}#1JE5HBFRE5ExCtxAttrs*/
	};
	/*#{1JE5HBFRE0PostContext*/
	/*}#1JE5HBFRE0PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JE5MO6H30
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JE5MO6H30"));
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
		return {seg:CheckBlocker,result:(result),preSeg:"1JE5MO6H30",outlet:"1JE5MO6H33"};
	};
	StartRpa.jaxId="1JE5MO6H30"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["CheckRule"]=CheckRule=async function(input){//:1JE5MTC1F0
		let result=input;
		/*#{1JE5MTC1F0Start*/
		let rule,code;
		code=read?.listTarget;
		rule=await readRule(session,context.aaPage,code?"read_list_"+code:"read_list");
		/*}#1JE5MTC1F0Start*/
		if(rule){
			let output=rule;
			/*#{1JE5MTC1F4Codes*/
			context.ruleCode=rule;
			/*}#1JE5MTC1F4Codes*/
			return {seg:RunRule,result:(output),preSeg:"1JE5MTC1F0",outlet:"1JE5MTC1F4"};
		}
		/*#{1JE5MTC1F0Post*/
		/*}#1JE5MTC1F0Post*/
		return {seg:ReadPage,result:(result),preSeg:"1JE5MTC1F0",outlet:"1JE5MTC1F3"};
	};
	CheckRule.jaxId="1JE5MTC1F0"
	CheckRule.url="CheckRule@"+agentURL
	
	segs["RunRule"]=RunRule=async function(input){//:1JEAHC4860
		let result=input;
		/*#{1JEAHC4860Start*/
		let page=context.aaPage;
		let code=input;
		let error=null;
		try{
			result=await page.callFunction(code,[]);
		}catch(err){
			wrongCodes.push(code);
			error=err;
			result=null;
		}
		if(Array.isArray(result) && result.length>0){
			context.grabCode=code;
			context.items=result;
		}else{
			wrongCodes.push(code);
		}
		/*}#1JEAHC4860Start*/
		if(!context.items || !context.items.length){
			return {seg:JumpReadPage,result:(input),preSeg:"1JEAHC4860",outlet:"1JEAHFMSR1"};
		}
		result=input;
		/*#{1JEAHC4860Post*/
		/*}#1JEAHC4860Post*/
		return {seg:CheckNumber,result:(result),preSeg:"1JEAHC4860",outlet:"1JEAHFMSR2"};
	};
	RunRule.jaxId="1JEAHC4860"
	RunRule.url="RunRule@"+agentURL
	
	segs["GenCode"]=GenCode=async function(input){//:1JE5MVIBC0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-4.1";
		let $agent;
		let result=null;
		/*#{1JE5MVIBC0Input*/
		let $notes,$itemCode,$fields,$itemDef;
		$itemCode=read?.listTarget||"article";
		$fields=read?.fields||null;
		$itemDef=getMergedItemSchema($itemCode,$fields);
		$notes=`"${$itemDef.code}"是指：${$itemDef.desc}\n\n`+
			`"run_js"动作返回函数代码，执行的返回数组每一个项目是一个对象，它的属性设置为：${JSON.stringify($itemDef.fields)}\n\n`+
			'返回的函数将在页面中运行，没有任何参数，而且只返回一个函数，如果需要一些工具函数，在这个函数内部实现\n\n'+
			'如果当前页面是正常页面，但是没有任何可提取的项目（比如搜索结果为空）。返回"done"动作。\n\n'+
			'如果当前页面是错误页面，比如404/500等，返回"abort"动作。\n\n'+
			(wrongCodes.length?`\n\n重要: 已知：\n\n${JSON.stringify(wrongCodes,null,"\t")}\n\n 这些代码是错误无效的，不要重复给出重复的错误答案。`:"");
		let $system=buildRpaMicroDeciderPrompt(
			`
			给定当前页面清洗后的HTML代码，确认当前页面是否包含有${$itemDef.text}列表，如果是，返回一个函数，用于找到这些项目的html元素，并提取信息。
			你要判断清楚什么才是主要需要提取的列表，比如如果是搜索引擎网站的搜索，给出的应该是获得搜索到的网页列表的代码；如果当前是购物网站搜索页面，应该是获取商品的列表的代码。
			`,
			$notes,
			["run_js"]
		);
		/*}#1JE5MVIBC0Input*/
		
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
		let chatMem=GenCode.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:$system},
		];
		/*#{1JE5MVIBC0PrePrompt*/
		/*}#1JE5MVIBC0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JE5MVIBC0FilterMessage*/
			/*}#1JE5MVIBC0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JE5MVIBC0PreCall*/
		/*}#1JE5MVIBC0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("GenCode@"+agentURL,opts,messages,true)):result;
		}
		result=trimJSON(result);
		/*#{1JE5MVIBC0PostCall*/
		/*}#1JE5MVIBC0PostCall*/
		if(result && result.action && result.action.type==="run_js"){
			let output=result.action.code;
			/*#{1JE5MVIBC4Codes*/
			/*}#1JE5MVIBC4Codes*/
			return {seg:RunCode,result:(output),preSeg:"1JE5MVIBC0",outlet:"1JE5MVIBC4"};
		}
		if(result && result.action && result.action.type==="done"){
			return {seg:FinNoItems,result:(input),preSeg:"1JE5MVIBC0",outlet:"1JECOKA8I0"};
		}
		if(result && result.action && result.action.type==="abort"){
			return {seg:FinFailed,result:(input),preSeg:"1JE5MVIBC0",outlet:"1JECOKJBT0"};
		}
		/*#{1JE5MVIBC0PreResult*/
		/*}#1JE5MVIBC0PreResult*/
		return {seg:FinFailed,result:(result),preSeg:"1JE5MVIBC0",outlet:"1JE5MVIBC3"};
	};
	GenCode.jaxId="1JE5MVIBC0"
	GenCode.url="GenCode@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1JE5MV2G50
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
			/*#{1JE5MV2G50ErrorCode*/
			/*}#1JE5MV2G50ErrorCode*/
		}
		return {seg:GenCode,result:(result),preSeg:"1JE5MV2G50",outlet:"1JE5MVC020"};
	};
	ReadPage.jaxId="1JE5MV2G50"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["RunCode"]=RunCode=async function(input){//:1JEDDOUUI0
		let result=input
		try{
			/*#{1JEDDOUUI0Code*/
			let page,items,newItems,item;
			runNum+=1;
			page=context.aaPage;
			items=context.items;
			newItems=(await page.callFunction(input,[]))||[];
			for(item of newItems){
				if(!items.find((i)=>{return i.url===item.url;})){
					items.push(item);
				}
			}
			result=items;
			context.grabCode=input;
			/*}#1JEDDOUUI0Code*/
		}catch(error){
			/*#{1JEDDOUUI0ErrorCode*/
			wrongCodes.push(input);
			/*}#1JEDDOUUI0ErrorCode*/
			return {seg:HasItems,result:error,preSeg:"1JEDDOUUI0",outlet:null};
		}
		return {seg:CheckNumber,result:(result),preSeg:"1JEDDOUUI0",outlet:"1JEDDPQUP0"};
	};
	RunCode.jaxId="1JEDDOUUI0"
	RunCode.url="RunCode@"+agentURL
	
	segs["CheckNumber"]=CheckNumber=async function(input){//:1JE5N9P7M0
		let result=input;
		if(minItems>0 && context.items.length<minItems){
			return {seg:ShowMore,result:(input),preSeg:"1JE5N9P7M0",outlet:"1JE5NAJFJ0"};
		}
		return {seg:NewRule,result:(result),preSeg:"1JE5N9P7M0",outlet:"1JE5ND0B80"};
	};
	CheckNumber.jaxId="1JE5N9P7M0"
	CheckNumber.url="CheckNumber@"+agentURL
	
	segs["NewRule"]=NewRule=async function(input){//:1JE5N3CK70
		let result=input;
		if(context.grabCode && context.grabCode!==context.ruleCode){
			return {seg:SaveRule,result:(input),preSeg:"1JE5N3CK70",outlet:"1JE5N8IBA0"};
		}
		return {seg:FinDone,result:(result),preSeg:"1JE5N3CK70",outlet:"1JE5N8IBA1"};
	};
	NewRule.jaxId="1JE5N3CK70"
	NewRule.url="NewRule@"+agentURL
	
	segs["SaveRule"]=SaveRule=async function(input){//:1JE5N4BDT0
		let result=input
		try{
			/*#{1JE5N4BDT0Code*/
			let rule,code;
			code=read?.listTarget;
			await saveRule(session,context.aaPage,code?"read_list_"+code:"read_list",context.grabCode);
			/*}#1JE5N4BDT0Code*/
		}catch(error){
			/*#{1JE5N4BDT0ErrorCode*/
			/*}#1JE5N4BDT0ErrorCode*/
		}
		return {seg:FinDone,result:(result),preSeg:"1JE5N4BDT0",outlet:"1JE5N8IBA2"};
	};
	SaveRule.jaxId="1JE5N4BDT0"
	SaveRule.url="SaveRule@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JE5N4OH30
		let result=input
		try{
			/*#{1JE5N4OH30Code*/
			let items=context.items;
			if(maxItems && items.length>maxItems){
				// If the number of items exceeds maxItems, trim the list to maxItems
				items = items.slice(0, maxItems);
			}
			result={status:"Done",result:"Finish",items:items};
			/*}#1JE5N4OH30Code*/
		}catch(error){
			/*#{1JE5N4OH30ErrorCode*/
			/*}#1JE5N4OH30ErrorCode*/
		}
		return {seg:WaitAfter,result:(result),preSeg:"1JE5N4OH30",outlet:"1JE5N8IBA3"};
	};
	FinDone.jaxId="1JE5N4OH30"
	FinDone.url="FinDone@"+agentURL
	
	segs["WaitAfter"]=WaitAfter=async function(input){//:1JE5N58OK0
		let result=true;
		let pageVal="aaPage";
		let $flag="";
		let $waitBefore=0;
		let $waitAfter=waitAfter||0;
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
	WaitAfter.jaxId="1JE5N58OK0"
	WaitAfter.url="WaitAfter@"+agentURL
	
	segs["ShowMore"]=ShowMore=async function(input){//:1JE5NBIJM0
		let result;
		let arg={"pageRef":pageRef,"profile":"","url":"","waitAfter":1000,"listCode":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenMoreItems.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JE5NBIJM0Input*/
		/*}#1JE5NBIJM0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JE5NBIJM0Output*/
		result=context.grabCode;
		/*}#1JE5NBIJM0Output*/
		return {seg:CheckMore,result:(result),preSeg:"1JE5NBIJM0",outlet:"1JE5ND0B90"};
	};
	ShowMore.jaxId="1JE5NBIJM0"
	ShowMore.url="ShowMore@"+agentURL
	
	segs["CheckMore"]=CheckMore=async function(input){//:1JECPPUJ90
		let result=input;
		/*#{1JECPPUJ90Start*/
		let page,code,items,newItems,item;
		let baseNum,findNewItems,readMore;
		page=context.aaPage;
		code=context.grabCode||input;
		items=context.items;
		baseNum=items.length;
		newItems=(await page.callFunction(code,[]))||[];
		for(item of newItems){
			if(!items.find((i)=>{return i.url===item.url;})){
				items.push(item);
			}
		}
		if(minItems>0 && items.length>=minItems){
			readMore=false;//Done
		}else if(items.length>baseNum && minItems>0){
			readMore=true;
		}else{
			readMore=false;//Done
		}
		/*}#1JECPPUJ90Start*/
		if(readMore){
			return {seg:RunCode,result:(input),preSeg:"1JECPPUJ90",outlet:"1JECPR4TV0"};
		}
		/*#{1JECPPUJ90Post*/
		/*}#1JECPPUJ90Post*/
		return {seg:JumpNoMore,result:(result),preSeg:"1JECPPUJ90",outlet:"1JECPR4TV1"};
	};
	CheckMore.jaxId="1JECPPUJ90"
	CheckMore.url="CheckMore@"+agentURL
	
	segs["JumpReadPage"]=JumpReadPage=async function(input){//:1JEAHEN5T0
		let result=input;
		return {seg:ReadPage,result:result,preSeg:"1JE5MV2G50",outlet:"1JEAHFMSR3"};
	
	};
	JumpReadPage.jaxId="1JE5MV2G50"
	JumpReadPage.url="JumpReadPage@"+agentURL
	
	segs["CheckBlocker"]=CheckBlocker=async function(input){//:1JECO4GTC0
		let result;
		let arg={"pageRef":pageRef,"blocker":{remove:true},"waitAfter":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenBlockers.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CheckRule,result:(result),preSeg:"1JECO4GTC0",outlet:"1JECO66650"};
	};
	CheckBlocker.jaxId="1JECO4GTC0"
	CheckBlocker.url="CheckBlocker@"+agentURL
	
	segs["FinNoItems"]=FinNoItems=async function(input){//:1JECOLRAF0
		let result=input
		try{
			/*#{1JECOLRAF0Code*/
			/*}#1JECOLRAF0Code*/
		}catch(error){
			/*#{1JECOLRAF0ErrorCode*/
			/*}#1JECOLRAF0ErrorCode*/
		}
		return {result:result};
	};
	FinNoItems.jaxId="1JECOLRAF0"
	FinNoItems.url="FinNoItems@"+agentURL
	
	segs["FinFailed"]=FinFailed=async function(input){//:1JECOMCN50
		let result=input
		try{
			/*#{1JECOMCN50Code*/
			/*}#1JECOMCN50Code*/
		}catch(error){
			/*#{1JECOMCN50ErrorCode*/
			/*}#1JECOMCN50ErrorCode*/
		}
		return {result:result};
	};
	FinFailed.jaxId="1JECOMCN50"
	FinFailed.url="FinFailed@"+agentURL
	
	segs["JumpNoMore"]=JumpNoMore=async function(input){//:1JECPRG000
		let result=input;
		return {seg:NewRule,result:result,preSeg:"1JE5N3CK70",outlet:"1JECPS1PB0"};
	
	};
	JumpNoMore.jaxId="1JE5N3CK70"
	JumpNoMore.url="JumpNoMore@"+agentURL
	
	segs["HasItems"]=HasItems=async function(input){//:1JED36LEF0
		let result=input;
		if(input==="Items"){
			return {seg:NewRule,result:(input),preSeg:"1JED36LEF0",outlet:"1JED38HAD0"};
		}
		if(runNum>5){
			return {seg:FinMaxRun,result:(input),preSeg:"1JED36LEF0",outlet:"1JEHSTS7U0"};
		}
		return {seg:ReadPage,result:(result),preSeg:"1JED36LEF0",outlet:"1JED38HAD1"};
	};
	HasItems.jaxId="1JED36LEF0"
	HasItems.url="HasItems@"+agentURL
	
	segs["FinMaxRun"]=FinMaxRun=async function(input){//:1JEHSTHU70
		let result=input
		try{
			/*#{1JEHSTHU70Code*/
			/*}#1JEHSTHU70Code*/
		}catch(error){
			/*#{1JEHSTHU70ErrorCode*/
			/*}#1JEHSTHU70ErrorCode*/
		}
		return {result:result};
	};
	FinMaxRun.jaxId="1JEHSTHU70"
	FinMaxRun.url="FinMaxRun@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CaRpa_GenReadList",
		url:agentURL,
		autoStart:true,
		jaxId:"1JE5HBFRE0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,url,profile,waitAfter,read,minItems,maxItems}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JE5HBFRE0PreEntry*/
			/*}#1JE5HBFRE0PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JE5HBFRE0PostEntry*/
			/*}#1JE5HBFRE0PostEntry*/
			return result;
		},
		/*#{1JE5HBFRE0MoreAgentAttrs*/
		/*}#1JE5HBFRE0MoreAgentAttrs*/
	};
	/*#{1JE5HBFRE0PostAgent*/
	/*}#1JE5HBFRE0PostAgent*/
	return agent;
};
/*#{1JE5HBFRE0ExCodes*/
/*}#1JE5HBFRE0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CaRpa_GenReadList",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				url:{type:"auto",description:""},
				profile:{type:"auto",description:""},
				waitAfter:{type:"auto",description:""},
				read:{type:"auto",description:""},
				minItems:{type:"integer",description:""},
				maxItems:{type:"integer",description:""}
			}
		}
	},
	isChatApi: true,
	kind: "rpa",
	capabilities: ["read.list","read.listTarget","read.fields"],
	filters: [],
	metrics: {"quality":"","costPerCall":"","costPer1M":"","speed":"","size":""}
}];
//#CodyExport<<<
/*#{1JE5HBFRE0PostDoc*/
/*}#1JE5HBFRE0PostDoc*/


export default CaRpa_GenReadList;
export{CaRpa_GenReadList,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JE5HBFRE0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JE5HBFRE1",
//			"attrs": {
//				"CaRpa_GenReadList": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JE5HBFRE7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JE5HBFRE8",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JE5HBFRE9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JE5HBFRE10",
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
//			"jaxId": "1JE5HBFRE2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JE5HBFRE3",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5MUGH90",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5N8IBB0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"profile": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5N8IBB1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"waitAfter": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5N8IBB2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"read": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE5N8IBB3",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"minItems": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JED2GNUR0",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "0",
//						"desc": ""
//					}
//				},
//				"maxItems": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JED2GNUR1",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "0",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JE5HBFRE4",
//			"attrs": {
//				"wrongCodes": {
//					"type": "auto",
//					"valText": "[]"
//				},
//				"runNum": {
//					"type": "number",
//					"valText": "0"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JE5HBFRE5",
//			"attrs": {
//				"grabCode": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JECOINH90",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"items": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JECOINH91",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"ruleCode": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JECP17AL0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1JE5HBFRE6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JE5MO6H30",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "140",
//						"y": "315",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE5MO6H31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5MO6H32",
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
//							"jaxId": "1JE5MO6H33",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JECO4GTC0"
//						},
//						"catchlet": {
//							"jaxId": "1JE5MO6H34",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JE5MO6H35",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JE5MO6H36",
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
//					"jaxId": "1JE5MTC1F0",
//					"attrs": {
//						"id": "CheckRule",
//						"viewName": "",
//						"label": "",
//						"x": "650",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JE5MTC1F1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5MTC1F2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5MTC1F3",
//							"attrs": {
//								"id": "NoRule",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE5MV2G50"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE5MTC1F4",
//									"attrs": {
//										"id": "Rule",
//										"desc": "输出节点。",
//										"output": "#rule",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JE5MTC1G0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE5MTC1G1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#rule"
//									},
//									"linkedSeg": "1JEAHC4860"
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
//					"jaxId": "1JEAHC4860",
//					"attrs": {
//						"id": "RunRule",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEAHFMSU2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEAHFMSU3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEAHFMSR2",
//							"attrs": {
//								"id": "GotItems",
//								"desc": "输出节点。",
//								"output": "#input"
//							},
//							"linkedSeg": "1JEAHGTNR0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEAHFMSR1",
//									"attrs": {
//										"id": "NoItems",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEAHFMSU4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEAHFMSU5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!context.items || !context.items.length"
//									},
//									"linkedSeg": "1JEAHEN5T0"
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
//					"jaxId": "1JE5MVIBC0",
//					"attrs": {
//						"id": "GenCode",
//						"viewName": "",
//						"label": "",
//						"x": "1145",
//						"y": "525",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JE5MVIBC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5MVIBC2",
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
//							"jaxId": "1JE5MVIBC3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JECOMCN50"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1JEGTD8IK0",
//									"attrs": {
//										"reply": "{ \"action\": { \"type\": \"run_js\", \"code\": \"function() {\\n function parseDate(d) {\\n // from format DD.MM.YYYY\\n if (!d) return undefined;\\n var m = d.match(/(\\\\d{2})\\\\.(\\\\d{2})\\\\.(\\\\d{4})/);\\n if (!m) return undefined;\\n return new Date(m[3] + '-' + m[2] + '-' + m[1]).toISOString();\\n }\\n var result = [];\\n var nodes = document.querySelectorAll('.content-tile > div[class^=\\\"brand-\\\"]');\\n for (var i=0; i<nodes.length; ++i) {\\n var node = nodes[i];\\n var pos = i+1;\\n var link = node.querySelector('h2 a');\\n var aimg = node.querySelector('a');\\n var cover = aimg && aimg.style.backgroundImage ? aimg.style.backgroundImage : '';\\n cover = cover ? cover.replace(/^url\\\\([\\\"']?|[\\\"']?\\\\)$/g, '').trim() : '';\\n var summary = (node.querySelector('span[style*=\\\"overflow-wrap\\\"]')||{}).innerText || undefined;\\n var date = (node.querySelector('footer > span')||{}).innerText || undefined;\\n var tags = node.querySelectorAll('footer a[rel=\\\"tag\\\"]');\\n var badges = [];\\n var category = undefined;\\n var articleKind = undefined;\\n tags.forEach(function(t) {\\n var text = (t.innerText||'').trim();\\n if (/news/i.test(text)) articleKind = 'news';\\n if (/review/i.test(text)) articleKind = 'blog';\\n if (!category && !/Rolex|News|Reviews/i.test(text)) category = text;\\n badges.push(text);\\n });\\n result.push({\\n url: link ? link.href : undefined,\\n title: link ? link.innerText.trim() : undefined,\\n summary: summary,\\n publishedAt: parseDate(date),\\n coverImageUrl: cover,\\n position: pos,\\n badges: badges.length ? badges : undefined,\\n articleKind: articleKind,\\n category: category\\n });\\n }\\n return result;\\n}\" }, \"reason\": \"页面包含文章列表，所有文章条目都在.content-tile下的div[class^='brand-']结构中，且信息结构规整。\", \"summary\": \"检测到经典文章列表及条目结构；执行提取列表函数，采集标题、链接、摘要、时间、封面等信息；预期可输出标准化article列表。\" }",
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
//									"jaxId": "1JE5MVIBC4",
//									"attrs": {
//										"id": "Code",
//										"desc": "输出节点。",
//										"output": "#result.action.code",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JE5MVIBC5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE5MVIBC6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action && result.action.type===\"run_js\""
//									},
//									"linkedSeg": "1JEDDOUUI0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JECOKA8I0",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JECONGU90",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JECONGU91",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action && result.action.type===\"done\""
//									},
//									"linkedSeg": "1JECOLRAF0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JECOKJBT0",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JECONGU92",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JECONGU93",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action && result.action.type===\"abort\""
//									},
//									"linkedSeg": "1JECOMCN50"
//								}
//							]
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1JE5MV2G50",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "525",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE5MVC030",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5MVC031",
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
//							"jaxId": "1JE5MVC020",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5MVIBC0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JEDDOUUI0",
//					"attrs": {
//						"id": "RunCode",
//						"viewName": "",
//						"label": "",
//						"x": "1415",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JEDDPQUV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEDDPQUV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEDDPQUP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5N9P7M0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": "1JED36LEF0"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JE5N2IS10",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1525",
//						"y": "705",
//						"outlet": {
//							"jaxId": "1JE5N2TN00",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5N2O7E0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JE5N2O7E0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "935",
//						"y": "705",
//						"outlet": {
//							"jaxId": "1JE5N2TN01",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5MV2G50"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JE5N9P7M0",
//					"attrs": {
//						"id": "CheckNumber",
//						"viewName": "",
//						"label": "",
//						"x": "1690",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5ND0BA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5ND0BA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5ND0B80",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE5N3CK70"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE5NAJFJ0",
//									"attrs": {
//										"id": "NeedMore",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE5ND0BA2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE5ND0BA3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#minItems>0 && context.items.length<minItems"
//									},
//									"linkedSeg": "1JE5NBIJM0"
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
//					"jaxId": "1JE5N3CK70",
//					"attrs": {
//						"id": "NewRule",
//						"viewName": "",
//						"label": "",
//						"x": "1970",
//						"y": "570",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5N8IBC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5N8IBC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5N8IBA1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE5N4OH30"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE5N8IBA0",
//									"attrs": {
//										"id": "NewRule",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE5N8IBC2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE5N8IBC3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#context.grabCode && context.grabCode!==context.ruleCode"
//									},
//									"linkedSeg": "1JE5N4BDT0"
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
//					"jaxId": "1JE5N4BDT0",
//					"attrs": {
//						"id": "SaveRule",
//						"viewName": "",
//						"label": "",
//						"x": "2220",
//						"y": "520",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5N8IBC4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5N8IBC5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5N8IBA2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5N4OH30"
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
//					"jaxId": "1JE5N4OH30",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "2450",
//						"y": "585",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE5N8IBC6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5N8IBC7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE5N8IBA3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5N58OK0"
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
//					"jaxId": "1JE5N58OK0",
//					"attrs": {
//						"id": "WaitAfter",
//						"viewName": "",
//						"label": "",
//						"x": "2700",
//						"y": "585",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE5N8IBC8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5N8IBC9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "",
//						"waitBefore": "0",
//						"waitAfter": "#waitAfter||0",
//						"outlet": {
//							"jaxId": "1JE5N8IBA5",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"catchlet": {
//							"jaxId": "1JE5N8IBA4",
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
//					"def": "aiBot",
//					"jaxId": "1JE5NBIJM0",
//					"attrs": {
//						"id": "ShowMore",
//						"viewName": "",
//						"label": "",
//						"x": "1970",
//						"y": "405",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JE5ND0BA4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5ND0BA5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenMoreItems.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"profile\":\"\",\"url\":\"\",\"waitAfter\":1000,\"listCode\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JE5ND0B90",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JECPPUJ90"
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
//					"jaxId": "1JECPPUJ90",
//					"attrs": {
//						"id": "CheckMore",
//						"viewName": "",
//						"label": "",
//						"x": "2205",
//						"y": "405",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JECPR4U70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JECPR4U71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JECPR4TV1",
//							"attrs": {
//								"id": "NoMore",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JECPRG000"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JECPR4TV0",
//									"attrs": {
//										"id": "More",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JECPR4U72",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JECPR4U73",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#readMore"
//									},
//									"linkedSeg": "1JE5NCGNE0"
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
//					"jaxId": "1JE5NCGNE0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2365",
//						"y": "320",
//						"outlet": {
//							"jaxId": "1JE5ND0BA6",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5NCL2T0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JE5NCL2T0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1440",
//						"y": "320",
//						"outlet": {
//							"jaxId": "1JE5ND0BA7",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEDDOUUI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JEAHEN5T0",
//					"attrs": {
//						"id": "JumpReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "1145",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JE5MV2G50",
//						"outlet": {
//							"jaxId": "1JEAHFMSR3",
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
//					"jaxId": "1JEAHGTNR0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1575",
//						"y": "260",
//						"outlet": {
//							"jaxId": "1JEAHHR7O0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5N9P7M0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JECO4GTC0",
//					"attrs": {
//						"id": "CheckBlocker",
//						"viewName": "",
//						"label": "",
//						"x": "385",
//						"y": "300",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JECO666A0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JECO666A1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenBlockers.js",
//						"argument": "{\"pageRef\":\"#pageRef\",\"blocker\":\"#{remove:true}\",\"waitAfter\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JECO66650",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5MTC1F0"
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
//					"jaxId": "1JECOLRAF0",
//					"attrs": {
//						"id": "FinNoItems",
//						"viewName": "",
//						"label": "",
//						"x": "1360",
//						"y": "510",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JECONGU94",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JECONGU95",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JECONGU40",
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
//					"jaxId": "1JECOMCN50",
//					"attrs": {
//						"id": "FinFailed",
//						"viewName": "",
//						"label": "",
//						"x": "1360",
//						"y": "585",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JECONGU96",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JECONGU97",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JECONGU41",
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
//					"jaxId": "1JECPRG000",
//					"attrs": {
//						"id": "JumpNoMore",
//						"viewName": "",
//						"label": "",
//						"x": "2450",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JE5N3CK70",
//						"outlet": {
//							"jaxId": "1JECPS1PB0",
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
//					"jaxId": "1JED36LEF0",
//					"attrs": {
//						"id": "HasItems",
//						"viewName": "#context.items && context.items.length>0",
//						"label": "",
//						"x": "1690",
//						"y": "600",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JED38HAJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JED38HAJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JED38HAD1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JED3868E0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JED38HAD0",
//									"attrs": {
//										"id": "Items",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JED38HAJ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JED38HAJ3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JE5N3CK70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JEHSTS7U0",
//									"attrs": {
//										"id": "MaxRun",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JEHSTS820",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JEHSTS821",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#runNum>5"
//									},
//									"linkedSeg": "1JEHSTHU70"
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
//					"jaxId": "1JED3868E0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1830",
//						"y": "705",
//						"outlet": {
//							"jaxId": "1JED38HAJ4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5N2IS10"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JEHSTHU70",
//					"attrs": {
//						"id": "FinMaxRun",
//						"viewName": "",
//						"label": "",
//						"x": "1970",
//						"y": "705",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JEHSTS822",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEHSTS823",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEHSTS7U1",
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
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":false,\"isChatApi\":1,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\",\"kind\":\"rpa\",\"capabilities\":[\"read.list\",\"read.listTarget\",\"read.fields\"],\"filters\":[],\"metrics\":{\"quality\":\"\",\"costPerCall\":\"\",\"costPer1M\":\"\",\"speed\":\"\",\"size\":\"\"},\"meta\":\"\"}"
//	}
//}