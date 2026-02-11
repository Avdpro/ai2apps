//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JFBHOVBL0MoreImports*/
import {parseFlowVal,briefJSON,buildRpaStepDeciderPrompt,execRunJsAction} from "./utils_flow.js";
/*}#1JFBHOVBL0MoreImports*/
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
		}
	},
	/*#{1JFBHOVBL0ArgsView*/
	/*}#1JFBHOVBL0ArgsView*/
};

/*#{1JFBHOVBL0StartDoc*/
/*}#1JFBHOVBL0StartDoc*/
//----------------------------------------------------------------------------
let Util_WriteCode=async function(session){
	let pageRef,action,flowArgs,flowVars,flowOpts,flowResult;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,ReadPage,GenAgentCode,TryCode,CheckResult,CheckRetry,FailRetry,FinDone,FailAIError,GoRetry;
	let codeQuery=undefined;
	let codeRetryNum=0;
	
	/*#{1JFBHOVBL0LocalVals*/
	/*}#1JFBHOVBL0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			action=input.action;
			flowArgs=input.flowArgs;
			flowVars=input.flowVars;
			flowOpts=input.flowOpts;
			flowResult=input.flowResult;
		}else{
			pageRef=undefined;
			action=undefined;
			flowArgs=undefined;
			flowVars=undefined;
			flowOpts=undefined;
			flowResult=undefined;
		}
		/*#{1JFBHOVBL0ParseArgs*/
		/*}#1JFBHOVBL0ParseArgs*/
	}
	
	/*#{1JFBHOVBL0PreContext*/
	/*}#1JFBHOVBL0PreContext*/
	context={
		html: "",
		codeAction: "",
		codeResult: "",
		actionRes: "",
		/*#{1JFBHOVBL5ExCtxAttrs*/
		/*}#1JFBHOVBL5ExCtxAttrs*/
	};
	/*#{1JFBHOVBL0PostContext*/
	/*}#1JFBHOVBL0PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JFBHPDP20
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JFBHPDP20"));
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
		return {seg:ReadPage,result:(result),preSeg:"1JFBHPDP20",outlet:"1JFBHPDP30"};
	};
	StartRpa.jaxId="1JFBHPDP20"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1JFBI4I150
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		let $target="cleanHTML";
		$waitBefore && (await sleep($waitBefore));
		/*#{1JFBI4I150PreCodes*/
		/*}#1JFBI4I150PreCodes*/
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
			/*#{1JFBI4I150ErrorCode*/
			/*}#1JFBI4I150ErrorCode*/
		}
		/*#{1JFBI4I150PostCodes*/
		let scope;
		scope=action.scope==="agent"?"agent":page;
		context["html"]=result;
		result={
			html:scope==="page"?result:undefined,
		};
		/*}#1JFBI4I150PostCodes*/
		return {seg:GenAgentCode,result:(result),preSeg:"1JFBI4I150",outlet:"1JFBIALM04"};
	};
	ReadPage.jaxId="1JFBI4I150"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["GenAgentCode"]=GenAgentCode=async function(input){//:1JFBI5TSI0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5";
		let $agent;
		let result=null;
		/*#{1JFBI5TSI0Input*/
		let $notes,$itemCode,$fields,$itemDef;
		$notes=`"${$itemDef.code}"是指：${$itemDef.desc}\n\n`+
			`"run_js"动作返回函数代码，执行后返回需求规定的内容，如果需求没有特别规定，默认返回JSON对象。\n\n`+
			'如果当前页面的内容无法编写代码达成需求，比如当前页面是404/500，或者没有可供提取的信息，返回abort动作\n\n'
		let $system=buildRpaStepDeciderPrompt(
			`
			给定：当前页面清洗后的HTML代码，也许在附件里给出以及当前的args、vars以及result环境变量。为以下需求编写代码：
			${action.query}
			`,
			$notes,
			["run_js"]
		);
		/*}#1JFBI5TSI0Input*/
		
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
		let chatMem=GenAgentCode.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:$system},
		];
		messages.push(...chatMem);
		/*#{1JFBI5TSI0PrePrompt*/
		/*}#1JFBI5TSI0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JFBI5TSI0FilterMessage*/
			/*}#1JFBI5TSI0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JFBI5TSI0PreCall*/
		/*}#1JFBI5TSI0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("GenAgentCode@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JFBI5TSI0PostLLM*/
		//Compact old codes:
		if(chatMem.length>=6){//保留两个旧的代码版本
			let line=chatMem[chatMem.length-5];
			if(line.code){
				line.code=`...已省略...`;
			}
		}
		/*}#1JFBI5TSI0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>20){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1JFBI5TSI0PostClear*/
			/*}#1JFBI5TSI0PostClear*/
		}
		result=trimJSON(result);
		/*#{1JFBI5TSI0PostCall*/
		/*}#1JFBI5TSI0PostCall*/
		if(result?.action?.code){
			/*#{1JGAVH95H0Codes*/
			/*}#1JGAVH95H0Codes*/
			return {seg:TryCode,result:(input),preSeg:"1JFBI5TSI0",outlet:"1JGAVH95H0"};context["codeAction"]=result.action;
		}
		/*#{1JFBI5TSI0PreResult*/
		/*}#1JFBI5TSI0PreResult*/
		return {seg:FailAIError,result:(result),preSeg:"1JFBI5TSI0",outlet:"1JFBIALM11"};
	};
	GenAgentCode.jaxId="1JFBI5TSI0"
	GenAgentCode.url="GenAgentCode@"+agentURL
	GenAgentCode.messages=[];
	
	segs["TryCode"]=TryCode=async function(input){//:1JFBI7J550
		let result=input;
		/*#{1JFBI7J550Start*/
		let page,res,status;
		page=context.aaPage;
		res=await execRunJsAction(context.codeAction,{
			args:flowArgs,
			vars:flowVars,
			opts:flowOpts,
			result:flowResult,
			parseVal:parseFlowVal,
			pageEval:async function(code,args){
				return await page.callFunction(code,args);
			}
		});
		status=res.status;
		/*}#1JFBI7J550Start*/
		if(status==="done"){
			let output=result;
			/*#{1JFBIALM12Codes*/
			context.actionRes=res;
			output=context.codeResult=res.avalue;
			/*}#1JFBIALM12Codes*/
			return {seg:CheckResult,result:(output),preSeg:"1JFBI7J550",outlet:"1JFBIALM12"};
		}
		/*#{1JFBI7J550Post*/
		result=`代码无法正确执行，错误及日志在这里: ${briefJSON(res)}。\n\n请根据信息修改代码，再给一个版本。`;
		context.actionRes=res;
		/*}#1JFBI7J550Post*/
		return {seg:CheckRetry,result:(result),preSeg:"1JFBI7J550",outlet:"1JFBIALM13"};
	};
	TryCode.jaxId="1JFBI7J550"
	TryCode.url="TryCode@"+agentURL
	
	segs["CheckResult"]=CheckResult=async function(input){//:1JGAU8NAR0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5-mini";
		let $agent;
		let result=null;
		/*#{1JGAU8NAR0Input*/
		/*}#1JGAU8NAR0Input*/
		
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
		let chatMem=CheckResult.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你是一个严格的“run_js 执行结果校验器（validator）”。\n\n你将收到**且只会收到**一个输入 JSON 对象：\n{\n  \"query\": \"...\",    // 代码的目的/要求（预期）\n  \"result\": \"...\",   // 代码执行的结果 JSON（可能被简化/裁剪）\n  \"html\": \"...\"      // 可选：如果 scope 是 page，可能提供页面 HTML\n}\n\n你的任务：\n判断“result 是否满足 query 的要求”（必要时结合 html 佐证）。你必须**只输出一个 JSON 对象**（不要输出 Markdown、不要输出解释性文字、不要输出多余字段）。\n\n输出格式（只能二选一）：\n\n1) 符合预期：\n{\n  \"status\": \"ok\",\n  \"summary\": \"...\"   // 1-4 句，简洁说明为什么符合；指出 result/html 中的关键证据\n}\n\n2) 不符合预期（包括证据不足无法判断）：\n{\n  \"status\": \"error\",\n  \"reason\": \"...\"    // 简洁说明不符合的点；若证据不足，说明缺什么信息以及为什么无法验证\n}\n\n校验规则（必须遵守）：\n- **保守判断**：缺少关键信息就不能判定为 ok。不要把“未出现的问题”当作“已满足”。\n- **禁止臆测**：不得编造值、不得假设 DOM 状态、不得假设执行上下文。只使用 query/result/html 中明确给出的信息。\n- **result 权威**：把 result 视为执行输出的权威来源。\n  - 如果 result 是“字符串形式的 JSON”，你要在脑中解析后再校验；若无法可靠解析（格式错误/缺失关键结构），返回 error。\n- **多条要求必须全满足**：query 包含多个要求时，只有全部满足才能返回 ok；否则返回 error，并指出未满足的项。\n- **精确性**：若 query 隐含或明确要求精确匹配（数值/布尔/字符串/枚举/字段存在性），必须严格按精确匹配判断；除非 query 明确允许近似/部分。\n- **DOM 副作用**（点击/输入/设置属性/新增或删除元素/改文本等）：\n  - 优先要求 result 中有“直接证据”证明副作用发生（例如 before/after、计数变化、命中节点标识、返回值确认）。\n  - 若提供了 html 且与预期相关，应交叉验证：若 html 未体现预期变化或 html 不足以验证（例如缺少相关片段/是旧快照/无法定位），返回 error。\n- **元素选择类任务**：\n  - 需要证据证明选择器命中：例如匹配数量 > 0；若要求唯一，则需要匹配数量为 1 或有唯一性证据；若返回节点信息，需可用于确认命中目标。\n- **数据返回类任务**：\n  - 校验返回数据的结构与类型：必需字段存在、类型正确、值满足约束（范围/格式/非空/去重/排序/长度等，按 query 描述为准）。\n- **错误处理/无异常要求**：\n  - 若 result 中包含 error/exception/stack/rejected/stderr 或状态显示失败，则默认判定为 error；除非 query 明确“预期失败/预期抛错”。\n- **“不应改变 X”**：\n  - 必须有明确证据证明 X 未改变（来自 result 或 html）；没有证据就返回 error。\n- **兼容常见 run_js 输出约定**：\n  - 如果 result 含 { ok, status, value, error, logs } 等字段，用它们作为主要证据。\n  - 如果 result 明示失败（例如 status 为 fail/error、或存在 error 字段），直接返回 error（除非 query 预期失败）。\n\n表达约束：\n- summary/reason 必须简短、客观、基于证据。\n- **ok 结论中不得出现“可能/大概/应该”等不确定措辞**；如果不确定，一律返回 error。\n- 最终输出只能是 JSON 对象本体，不能夹带任何其他文本。\n\n现在开始对给定输入 JSON 进行校验并输出最终 JSON。"},
		];
		/*#{1JGAU8NAR0PrePrompt*/
		input={
			query:action.query,
			result:input,
		};
		if(action.scope!=="agent"){
			input.html=context.html;
		}
		/*}#1JGAU8NAR0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JGAU8NAR0FilterMessage*/
			/*}#1JGAU8NAR0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JGAU8NAR0PreCall*/
		/*}#1JGAU8NAR0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("CheckResult@"+agentURL,opts,messages,true)):result;
		}
		result=trimJSON(result);
		/*#{1JGAU8NAR0PostCall*/
		/*}#1JGAU8NAR0PostCall*/
		if(result.status!=="done"){
			let output=result;
			/*#{1JGAUDAV20Codes*/
			output={status:"failed",reason:`代码执行后，AI判定无效：${result.reason}。\n\n代码执结果:${briefJSON(context.codeResult)}。\n\n执行辅助信息/日志：${context.actionRes?.meta}。请修一下再给一个版本。`};
			/*}#1JGAUDAV20Codes*/
			return {seg:GoRetry,result:(output),preSeg:"1JGAU8NAR0",outlet:"1JGAUDAV20"};
		}
		/*#{1JGAU8NAR0PreResult*/
		/*}#1JGAU8NAR0PreResult*/
		return {seg:FinDone,result:(result),preSeg:"1JGAU8NAR0",outlet:"1JGAUDAV21"};
	};
	CheckResult.jaxId="1JGAU8NAR0"
	CheckResult.url="CheckResult@"+agentURL
	
	segs["CheckRetry"]=CheckRetry=async function(input){//:1JFBI8LUP0
		let result=input;
		/*#{1JFBI8LUP0Start*/
		/*}#1JFBI8LUP0Start*/
		if(++codeRetryNum>3){
			let output=result;
			/*#{1JFBIALM14Codes*/
			/*}#1JFBIALM14Codes*/
			return {seg:FailRetry,result:(output),preSeg:"1JFBI8LUP0",outlet:"1JFBIALM14"};
		}
		/*#{1JFBI8LUP0Post*/
		result=`代码无法正确执行，错误及日志在这里: ${briefJSON(context.actionRes)}。\n\n请根据信息修改代码，再给一个版本。`;
		/*}#1JFBI8LUP0Post*/
		return {seg:GenAgentCode,result:(result),preSeg:"1JFBI8LUP0",outlet:"1JFBIALM15"};
	};
	CheckRetry.jaxId="1JFBI8LUP0"
	CheckRetry.url="CheckRetry@"+agentURL
	
	segs["FailRetry"]=FailRetry=async function(input){//:1JFBIAPQG0
		let result={status:"failed",reason:"Max retry"}
		try{
			/*#{1JFBIAPQG0Code*/
			/*}#1JFBIAPQG0Code*/
		}catch(error){
			/*#{1JFBIAPQG0ErrorCode*/
			/*}#1JFBIAPQG0ErrorCode*/
		}
		return {result:result};
	};
	FailRetry.jaxId="1JFBIAPQG0"
	FailRetry.url="FailRetry@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JFBIBL840
		let result=""
		try{
			/*#{1JFBIBL840Code*/
			result={status:"done",value:context.codeAction,action:context.codeAction};
			/*}#1JFBIBL840Code*/
		}catch(error){
			/*#{1JFBIBL840ErrorCode*/
			/*}#1JFBIBL840ErrorCode*/
		}
		return {result:result};
	};
	FinDone.jaxId="1JFBIBL840"
	FinDone.url="FinDone@"+agentURL
	
	segs["FailAIError"]=FailAIError=async function(input){//:1JFBNI6C60
		let result=input
		try{
			/*#{1JFBNI6C60Code*/
			result={status:"failed",reason:"AI can't write code: "+briefJSON(input)};
			/*}#1JFBNI6C60Code*/
		}catch(error){
			/*#{1JFBNI6C60ErrorCode*/
			/*}#1JFBNI6C60ErrorCode*/
		}
		return {result:result};
	};
	FailAIError.jaxId="1JFBNI6C60"
	FailAIError.url="FailAIError@"+agentURL
	
	segs["GoRetry"]=GoRetry=async function(input){//:1JGAUCOU40
		let result=input;
		return {seg:CheckRetry,result:result,preSeg:"1JFBI8LUP0",outlet:"1JGAUDAV22"};
	
	};
	GoRetry.jaxId="1JFBI8LUP0"
	GoRetry.url="GoRetry@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"Util_WriteCode",
		url:agentURL,
		autoStart:true,
		jaxId:"1JFBHOVBL0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,action,flowArgs,flowVars,flowOpts,flowResult}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JFBHOVBL0PreEntry*/
			/*}#1JFBHOVBL0PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JFBHOVBL0PostEntry*/
			/*}#1JFBHOVBL0PostEntry*/
			return result;
		},
		/*#{1JFBHOVBL0MoreAgentAttrs*/
		/*}#1JFBHOVBL0MoreAgentAttrs*/
	};
	/*#{1JFBHOVBL0PostAgent*/
	/*}#1JFBHOVBL0PostAgent*/
	return agent;
};
/*#{1JFBHOVBL0ExCodes*/
/*}#1JFBHOVBL0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "Util_WriteCode",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				action:{type:"auto",description:""},
				flowArgs:{type:"auto",description:""},
				flowVars:{type:"auto",description:""},
				flowOpts:{type:"auto",description:""},
				flowResult:{type:"auto",description:""}
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1JFBHOVBL0PostDoc*/
/*}#1JFBHOVBL0PostDoc*/


export default Util_WriteCode;
export{Util_WriteCode,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JFBHOVBL0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JFBHOVBL1",
//			"attrs": {
//				"Util_WriteCode": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JFBHOVBL7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JFBHOVBM0",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JFBHOVBM1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JFBHOVBM2",
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
//			"jaxId": "1JFBHOVBL2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JFBHOVBL3",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFBIALM20",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"action": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFBJGGKB0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flowArgs": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFBJI84P0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flowVars": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFBJI84P1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flowOpts": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFBJI84P2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flowResult": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFBJI84P3",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JFBHOVBL4",
//			"attrs": {
//				"codeQuery": {
//					"type": "auto",
//					"valText": ""
//				},
//				"codeRetryNum": {
//					"type": "int",
//					"valText": "0"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JFBHOVBL5",
//			"attrs": {
//				"html": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFBNEL4O0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"codeAction": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGB0TIG00",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"codeResult": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGB7CIK80",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"actionRes": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGB89OFB0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1JFBHOVBL6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JFBHPDP20",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "90",
//						"y": "390",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFBHPDP21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBHPDP22",
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
//							"jaxId": "1JFBHPDP30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBI4I150"
//						},
//						"catchlet": {
//							"jaxId": "1JFBHPDP31",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JFBHPDP32",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JFBHPDP33",
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
//					"def": "WebRpaReadPage",
//					"jaxId": "1JFBI4I150",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "335",
//						"y": "375",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFBIALM220",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIALM221",
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
//							"jaxId": "1JFBIALM04",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBI5TSI0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JFBI5TSI0",
//					"attrs": {
//						"id": "GenAgentCode",
//						"viewName": "",
//						"label": "",
//						"x": "585",
//						"y": "375",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFBIALM224",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIALM225",
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
//							"jaxId": "1JFBIALM11",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBNI6C60"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "20 messages",
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
//									"jaxId": "1JGAVH95H0",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JGAVH95J0",
//											"attrs": {
//												"cast": "{\"html\":\"\",\"codeAction\":\"#result.action\"}"
//											}
//										},
//										"global": {
//											"jaxId": "1JGAVH95K0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result?.action?.code"
//									},
//									"linkedSeg": "1JFBI7J550"
//								}
//							]
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JFBI7J550",
//					"attrs": {
//						"id": "TryCode",
//						"viewName": "",
//						"label": "",
//						"x": "825",
//						"y": "360",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFBIALM226",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIALM227",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBIALM13",
//							"attrs": {
//								"id": "ExecError",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFBI8LUP0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBIALM12",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "#result",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JFBIALM228",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBIALM229",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#status===\"done\""
//									},
//									"linkedSeg": "1JGAU8NAR0"
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
//					"jaxId": "1JGAU8NAR0",
//					"attrs": {
//						"id": "CheckResult",
//						"viewName": "",
//						"label": "",
//						"x": "1075",
//						"y": "345",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JGAUDAV90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGAUDAV91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-5-mini",
//						"system": "你是一个严格的“run_js 执行结果校验器（validator）”。\n\n你将收到**且只会收到**一个输入 JSON 对象：\n{\n  \"query\": \"...\",    // 代码的目的/要求（预期）\n  \"result\": \"...\",   // 代码执行的结果 JSON（可能被简化/裁剪）\n  \"html\": \"...\"      // 可选：如果 scope 是 page，可能提供页面 HTML\n}\n\n你的任务：\n判断“result 是否满足 query 的要求”（必要时结合 html 佐证）。你必须**只输出一个 JSON 对象**（不要输出 Markdown、不要输出解释性文字、不要输出多余字段）。\n\n输出格式（只能二选一）：\n\n1) 符合预期：\n{\n  \"status\": \"ok\",\n  \"summary\": \"...\"   // 1-4 句，简洁说明为什么符合；指出 result/html 中的关键证据\n}\n\n2) 不符合预期（包括证据不足无法判断）：\n{\n  \"status\": \"error\",\n  \"reason\": \"...\"    // 简洁说明不符合的点；若证据不足，说明缺什么信息以及为什么无法验证\n}\n\n校验规则（必须遵守）：\n- **保守判断**：缺少关键信息就不能判定为 ok。不要把“未出现的问题”当作“已满足”。\n- **禁止臆测**：不得编造值、不得假设 DOM 状态、不得假设执行上下文。只使用 query/result/html 中明确给出的信息。\n- **result 权威**：把 result 视为执行输出的权威来源。\n  - 如果 result 是“字符串形式的 JSON”，你要在脑中解析后再校验；若无法可靠解析（格式错误/缺失关键结构），返回 error。\n- **多条要求必须全满足**：query 包含多个要求时，只有全部满足才能返回 ok；否则返回 error，并指出未满足的项。\n- **精确性**：若 query 隐含或明确要求精确匹配（数值/布尔/字符串/枚举/字段存在性），必须严格按精确匹配判断；除非 query 明确允许近似/部分。\n- **DOM 副作用**（点击/输入/设置属性/新增或删除元素/改文本等）：\n  - 优先要求 result 中有“直接证据”证明副作用发生（例如 before/after、计数变化、命中节点标识、返回值确认）。\n  - 若提供了 html 且与预期相关，应交叉验证：若 html 未体现预期变化或 html 不足以验证（例如缺少相关片段/是旧快照/无法定位），返回 error。\n- **元素选择类任务**：\n  - 需要证据证明选择器命中：例如匹配数量 > 0；若要求唯一，则需要匹配数量为 1 或有唯一性证据；若返回节点信息，需可用于确认命中目标。\n- **数据返回类任务**：\n  - 校验返回数据的结构与类型：必需字段存在、类型正确、值满足约束（范围/格式/非空/去重/排序/长度等，按 query 描述为准）。\n- **错误处理/无异常要求**：\n  - 若 result 中包含 error/exception/stack/rejected/stderr 或状态显示失败，则默认判定为 error；除非 query 明确“预期失败/预期抛错”。\n- **“不应改变 X”**：\n  - 必须有明确证据证明 X 未改变（来自 result 或 html）；没有证据就返回 error。\n- **兼容常见 run_js 输出约定**：\n  - 如果 result 含 { ok, status, value, error, logs } 等字段，用它们作为主要证据。\n  - 如果 result 明示失败（例如 status 为 fail/error、或存在 error 字段），直接返回 error（除非 query 预期失败）。\n\n表达约束：\n- summary/reason 必须简短、客观、基于证据。\n- **ok 结论中不得出现“可能/大概/应该”等不确定措辞**；如果不确定，一律返回 error。\n- 最终输出只能是 JSON 对象本体，不能夹带任何其他文本。\n\n现在开始对给定输入 JSON 进行校验并输出最终 JSON。",
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
//							"jaxId": "1JGAUDAV21",
//							"attrs": {
//								"id": "Done",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBIBL840"
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
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JGAUDAV20",
//									"attrs": {
//										"id": "Error",
//										"desc": "输出节点。",
//										"output": "#result",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JGAUDAV92",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGAUDAV93",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result.status!==\"done\""
//									},
//									"linkedSeg": "1JGAUCOU40"
//								}
//							]
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JFBI8LUP0",
//					"attrs": {
//						"id": "CheckRetry",
//						"viewName": "",
//						"label": "",
//						"x": "1075",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFBIALM230",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIALM231",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBIALM15",
//							"attrs": {
//								"id": "Retry",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFBI9DQQ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBIALM14",
//									"attrs": {
//										"id": "MaxRetry",
//										"desc": "输出节点。",
//										"output": "#result",
//										"codes": "true",
//										"context": {
//											"jaxId": "1JFBIALM232",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBIALM233",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#++codeRetryNum>3"
//									},
//									"linkedSeg": "1JFBIAPQG0"
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
//					"jaxId": "1JFBI9DQQ0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1240",
//						"y": "570",
//						"outlet": {
//							"jaxId": "1JFBIALM234",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBI9K4T0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JFBI9K4T0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "620",
//						"y": "570",
//						"outlet": {
//							"jaxId": "1JFBIALM235",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBI5TSI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JFBIAPQG0",
//					"attrs": {
//						"id": "FailRetry",
//						"viewName": "",
//						"label": "",
//						"x": "1330",
//						"y": "450",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFBIBR6G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIBR6G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBIBR6F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#{status:\"failed\",reason:\"Max retry\"}",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JFBIBL840",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "1330",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFBIBR6G4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIBR6G5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBIBR6F2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JFBNI6C60",
//					"attrs": {
//						"id": "FailAIError",
//						"viewName": "",
//						"label": "",
//						"x": "825",
//						"y": "470",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFBNIOAC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBNIOAC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBNIOA10",
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
//					"jaxId": "1JGAUCOU40",
//					"attrs": {
//						"id": "GoRetry",
//						"viewName": "",
//						"label": "",
//						"x": "1330",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JFBI8LUP0",
//						"outlet": {
//							"jaxId": "1JGAUDAV22",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}