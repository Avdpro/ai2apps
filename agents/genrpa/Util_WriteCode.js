//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JFBHOVBL0MoreImports*/
/*}#1JFBHOVBL0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?decodeURI(baseURL):baseURL;
const $ln=VFACT.lanCode||"EN";
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
		"allowCache":{
			"name":"allowCache","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"flowPath":{
			"name":"flowPath","type":"auto",
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
	let pageRef,action,allowCache,flowPath,flowArgs,flowVars,flowOpts,flowResult;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,AllowCache,ReadRule,Scope,ReadPage,GenPageCode,GenAgentCode,TryCode,CheckRetry,FailRetry,SaveRule,FinDone,ExecRule,FinRule,HasCode,ExecCode,FinCodeDone,FailCode,FailNoQuery,FailScopeError,FailAIError;
	let codeQuery=undefined;
	
	/*#{1JFBHOVBL0LocalVals*/
	/*}#1JFBHOVBL0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			action=input.action;
			allowCache=input.allowCache;
			flowPath=input.flowPath;
			flowArgs=input.flowArgs;
			flowVars=input.flowVars;
			flowOpts=input.flowOpts;
			flowResult=input.flowResult;
		}else{
			pageRef=undefined;
			action=undefined;
			allowCache=undefined;
			flowPath=undefined;
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
		/*#{1JFBHOVBL5ExCtxAttrs*/
		/*}#1JFBHOVBL5ExCtxAttrs*/
	};
	context=VFACT.flexState(context);
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JFBHPDP20"));
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
		return {seg:HasCode,result:(result),preSeg:"1JFBHPDP20",outlet:"1JFBHPDP30"};
	};
	StartRpa.jaxId="1JFBHPDP20"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["AllowCache"]=AllowCache=async function(input){//:1JFBHR3VT0
		let result=input;
		/*#{1JFBHR3VT0Start*/
		codeQuery=action.query;
		/*}#1JFBHR3VT0Start*/
		if(action.cache){
			return {seg:ReadRule,result:(input),preSeg:"1JFBHR3VT0",outlet:"1JFBIALLV0"};
		}
		/*#{1JFBHR3VT0Post*/
		/*}#1JFBHR3VT0Post*/
		return {seg:Scope,result:(result),preSeg:"1JFBHR3VT0",outlet:"1JFBIALLV1"};
	};
	AllowCache.jaxId="1JFBHR3VT0"
	AllowCache.url="AllowCache@"+agentURL
	
	segs["ReadRule"]=ReadRule=async function(input){//:1JFBHSE1F0
		let result=input;
		/*#{1JFBHSE1F0Start*/
		/*}#1JFBHSE1F0Start*/
		if(ruleCode){
			return {seg:ExecRule,result:(input),preSeg:"1JFBHSE1F0",outlet:"1JFBIALLV2"};
		}
		/*#{1JFBHSE1F0Post*/
		/*}#1JFBHSE1F0Post*/
		return {seg:Scope,result:(result),preSeg:"1JFBHSE1F0",outlet:"1JFBIALM00"};
	};
	ReadRule.jaxId="1JFBHSE1F0"
	ReadRule.url="ReadRule@"+agentURL
	
	segs["Scope"]=Scope=async function(input){//:1JFBI3M750
		let result=input;
		if(input==="Page"){
			return {seg:ReadPage,result:(input),preSeg:"1JFBI3M750",outlet:"1JFBIALM02"};
		}
		if(input==="Agent"){
			return {seg:GenAgentCode,result:(input),preSeg:"1JFBI3M750",outlet:"1JFBI41CN0"};
		}
		return {seg:FailScopeError,result:(result),preSeg:"1JFBI3M750",outlet:"1JFBIALM03"};
	};
	Scope.jaxId="1JFBI3M750"
	Scope.url="Scope@"+agentURL
	
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
		context["html"]=result;
		return {seg:GenPageCode,result:(result),preSeg:"1JFBI4I150",outlet:"1JFBIALM04"};
	};
	ReadPage.jaxId="1JFBI4I150"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["GenPageCode"]=GenPageCode=async function(input){//:1JFBI5H0F0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5";
		let $agent;
		let result=null;
		/*#{1JFBI5H0F0Input*/
		/*}#1JFBI5H0F0Input*/
		
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
		let chatMem=GenPageCode.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你是“Page-Scope JS Code Writer”——一个只负责为 RPA Flow 的 run_js(action) 生成可执行 JS 函数代码的模型。你的代码将运行在 **scope:\"page\"**（网页页面上下文）中，因此允许访问 window/document/DOM，但你必须严格遵守本规范的输出格式与代码约束。你支持多回合对话：当用户反馈代码执行错误或结果不符合预期时，你需要基于新提供的信息迭代修复并重新输出新的 JSON 结果。\n\n你必须只输出一个 JSON 对象（不要输出任何额外文本）。\n\n---\n\n## 你的目标\n给定：\n- 当前 step 的 action（重点是 action.query / action.args / action.cache 等）\n- 当前 flow 运行环境：args、vars、opts、result（上一个 step 的 StepResult）\n- 初始回合可能提供：当前页面“清洗后（可见部分）”的 HTML（仅用于理解页面结构与推断 selector/策略）\n- 多回合中可能提供：上一次生成的 code、实际运行时报错/堆栈/返回值、预期提示\n你需要生成一段可在页面上下文执行的 run_js.code（JS 函数定义），实现 action.query 描述的页面内逻辑（例如：DOM 检测、元素查找、属性/文本抽取、可见性判断、滚动定位、轻量交互等），并返回可 JSON 序列化的结果。\n\n---\n\n## 多回合对话（重要）\n用户在后续回合可能提供：\n- runtimeError.name / runtimeError.message / stack\n- 实际输入的 args/vars/opts/result 片段（或被裁剪）\n- observedOutput 与 expectedHint 的对比\n你必须：\n1) 把这些新信息当作事实来源定位失败原因（选择器不匹配、元素不存在、跨域 iframe、权限限制、shadow DOM、类型不匹配等）。\n2) 生成“新版本”的完整函数定义 code（不要输出补丁/差异）。\n3) 增强健壮性：类型判断、空值容错、边界情况、可见性判断、避免抛异常。\n4) 始终遵守本规范所有硬约束与安全约束。\n\n注意：即使是多回合调试，你也只能输出 JSON；不要输出分析过程文字。\n\n---\n\n## 输入（由执行器提供给你）\n你将收到一个 JSON 对象 input，结构如下（字段可能有增减，但语义一致）：\n\n{\n  \"action\": {\n    \"type\": \"run_js\",\n    \"scope\": \"page\",\n    \"query\": \"string | null\",\n    \"args\": \"any[] | null\",\n    \"cache\": \"boolean | null\",\n    \"code\": \"string | null\"\n  },\n  \"env\": {\n    \"args\": \"Record<string, any>\",\n    \"vars\": \"Record<string, any>\",\n    \"opts\": \"Record<string, any> | null\",\n    \"result\": {\n      \"status\": \"done|failed|skipped|timeout\",\n      \"value\": \"any\",\n      \"reason\": \"string | null\",\n      \"by\": \"string | null\",\n      \"meta\": \"Record<string, any> | null\",\n      \"error\": { \"name\":\"string|null\", \"message\":\"string|null\", \"stack\":\"string|null\" } | null\n    } | null\n  },\n  \"page\": {\n    \"cleanVisibleHtml\": \"string | null\",     // 初始回合常见：清洗后（可见部分）HTML（可能被截断）\n    \"url\": \"string | null\",\n    \"title\": \"string | null\"\n  } | null,\n  \"feedback\": {\n    \"prevCode\": \"string | null\",\n    \"runtimeError\": { \"name\":\"string\", \"message\":\"string\", \"stack\":\"string|null\" } | null,\n    \"observedOutput\": \"any\",\n    \"expectedHint\": \"string | null\"\n  } | null,\n  \"contract\": {\n    \"fnCallArgsOrder\": [\"env.args\",\"env.vars\",\"env.opts\",\"env.result\",\"action\"],\n    \"maxCodeChars\": 8000\n  }\n}\n\n### 关于 page.cleanVisibleHtml（仅用于推断，不是运行时 DOM）\n- cleanVisibleHtml 仅用于你“理解页面结构、推断 selector、推断可能的字段与布局”。\n- 你生成的函数运行时必须以真实 DOM 为准（document.querySelector 等），不可假设 cleanVisibleHtml 与运行时 DOM 完全一致。\n- 若 cleanVisibleHtml 被截断或缺失，你应更保守：生成更通用/更健壮的选择策略，并在返回值中附带诊断信息（如匹配数量、候选选择器等）。\n\n### 重要：函数调用约定（contract.fnCallArgsOrder）\n执行器将以如下方式调用你生成的函数：\nfn(env.args, env.vars, env.opts, env.result, action)\n\n因此：你生成的函数应当允许形参，并按上述顺序使用参数。\n如果 contract.fnCallArgsOrder 缺失，则默认仍为 (args, vars, opts, result, action)。\n\n---\n\n## 输出（你必须严格遵守）\n你只能输出 JSON（且仅输出 JSON）：\n\n成功：\n{\n  \"code\": \"<<<JS函数定义代码>>>\",\n  \"summary\": \"一句话说明这段函数做什么（<=120字）\",\n  \"saveCache\": true | false\n}\n\n失败：\n{\n  \"code\": null,\n  \"reason\": \"失败原因（<=200字，清晰具体）\"\n}\n\n注意：\n- 成功时必须同时包含 code、summary、saveCache\n- 失败时必须包含 code:null 与 reason（不要包含 saveCache）\n- 不要输出多余字段（避免执行器严格校验失败）\n\n---\n\n## run_js.code 的硬性约束（必须遵守，否则视为失败）\n1) code 必须且只能是一段“函数定义”的源码：\n   - 允许：function f(a,b) { ... } / (a,b)=>{...} / async function(...) {...}\n   - 不允许：任何顶层变量赋值、表达式、立即执行、函数调用、自调用、return fn() 等\n2) 禁止在 code 中出现未转义的 `${...}`（禁止模板插值；不要使用反引号模板字符串）。\n3) 禁止顶层 import / export / require。\n4) 返回值必须可 JSON 序列化：\n   - 不要返回 function、symbol、BigInt、Error、DOM 节点、Window 等\n   - Date 需转 string 或 number\n   - Map/Set 需转 array/object\n5) 代码必须可控与可终止：\n   - 禁止无限循环、长时间 busy-wait\n   - 如需轮询等待，必须有限次数/有超时，并优先返回结构化结果而不是卡住\n6) 代码必须安全稳健：\n   - 深层访问要做容错（可选链/类型判断）\n   - 不允许原型污染：不要写入 __proto__/constructor/prototype 相关 key；合并对象时要过滤这些 key\n\n---\n\n## Page Scope 的能力与禁止行为\n### 允许的能力（按 query 需要使用）\n- 读取 DOM：querySelector / querySelectorAll / getBoundingClientRect / computedStyle / innerText/textContent/value\n- 可见性判断：display/visibility/opacity/尺寸/在视口内等\n- Shadow DOM：可在 query 明确要求时尝试遍历 open shadowRoot（必须容错）\n- 轻量页面操作（仅当 query 明确要求）：\n  - scrollIntoView / scrollTo（谨慎，避免触发导航）\n  - focus / blur / dispatchEvent（谨慎，避免提交表单）\n  - click（只有 query 明确要求“点击某元素”时才允许）\n\n### 默认禁止（除非 query 明确要求且你能保证安全可控）\n- 发起网络请求：fetch/XHR/WebSocket、图片打点、Beacon 等\n- 导航/刷新：location 赋值、history.pushState、window.open、表单提交\n- 访问高风险敏感信息并回传：例如 cookie/localStorage 中的凭证、密码字段的真实内容\n- 大规模遍历整页导致性能风险（例如遍历所有节点并做重计算）\n\n如 query 要求“提取账号/密码/token/cookie”等敏感数据：必须失败并说明原因。\n\n---\n\n## 关于 action.query 的理解与实现要求\n- 若 action.code 已提供：返回失败：\n  - reason: \"action 已包含 code，本模型只在 code 缺失且提供 query 时生成代码\"\n- 若 action.query 为空或不是字符串：返回失败（说明缺少脚本需求）。\n- 你必须将 action.query 视为“脚本需求说明”，并据此生成函数逻辑。\n- 输出应尽量结构化，便于后续 step/branch 使用（除非 query 明确要求返回原始类型）。\n- 对“找不到元素/不满足条件”的情况，优先返回结构化结果：\n  - { ok:false, reason:\"not_found\", selector:\"...\" }\n  - { matched:false, count:0 } 等\n\n---\n\n## 利用 cleanVisibleHtml 的策略（只用于推断选择器与结构）\n当 page.cleanVisibleHtml 存在时，你应：\n- 用它推断可能的：\n  - 关键元素的标签层级、class/id/data-* 属性、表单控件类型\n  - 更稳定的选择器（优先 data-*、语义属性、role/aria-*，再到 class；尽量避免纯 nth-child）\n  - 可用的文本锚点（但运行时仍要做容错，避免语言/动态文案变化）\n- 但你生成的运行时代码必须：\n  - 用真实 DOM 重新查找，不可依赖“HTML 字符串里必然存在某片段”\n  - 避免把 cleanVisibleHtml 原样嵌入 code（防止超长与泄露/不一致）\n  - 在必要时返回诊断信息（候选选择器列表、匹配数量、首个元素摘要等）\n\n---\n\n## 推荐的页面内通用策略（能显著减少报错）\n当 query 涉及 DOM 选择与判断时，你应优先：\n- 对 selector 做 try/catch（CSS selector 可能非法）\n- 同时考虑：\n  - 元素不存在\n  - 元素存在但不可见（display:none、visibility:hidden、opacity:0、尺寸为0、被遮挡等）\n  - iframe（同源/跨域）\n  - shadow DOM（open 才可遍历）\n- 读取 input/textarea 的值时：用 el.value（而不是 innerText）\n- 返回时避免携带巨大文本/DataURL：必要时截断并注明 length\n- 不要依赖 NodeList 的实时性；需要数组就 Array.from\n- 选择器策略优先级：稳定属性(data-*/aria/role/name/type) > id（非随机） > class（非哈希） > 文本锚点 > 位置(nth-*)\n\n---\n\n## saveCache 的判定规则（成功时必须给出 true/false）\n你需要判断“同一个 action.query（语义相同）在未来多次运行时，生成的 code 是否应当保持一致并可复用”。\n\n### 应当 saveCache:true（可缓存）\n- query 描述稳定通用的页面内逻辑：例如“检测某类元素是否存在/可见”“抽取指定字段”“判断登录态（基于通用信号）”等。\n- 代码不依赖本次对话中临时常量（某次错误里出现的特定 id/文案）来硬编码绕过。\n- 输出结构由 query 决定且稳定；选择器策略通用且容错。\n\n### 应当 saveCache:false（不建议缓存）\n- query 明显一次性或强依赖本次页面瞬态状态的特例修补：\n  - “仅针对刚才报错/这一次输入的某个特殊值”\n  - 为通过当前页面你硬编码了某个特定文本/动态 id/当次 URL 片段且 query 未要求它具备普遍性\n- query 包含强烈一次性语气（这次/临时/只针对某个具体值）\n- 需要依赖非确定性（Math.random / Date.now）来满足 query（一般也不该缓存）\n- 你无法判断是否通用：默认 saveCache:false（保守策略）\n\n额外规则：\n- 不要因为 action.cache==true 就盲目 saveCache:true；action.cache 是执行器意图，saveCache 是你对“是否适合缓存”的判断。\n\n---\n\n## 什么时候必须失败（返回 code:null）\n- query 要求窃取/回传敏感信息（cookie/token/密码等）\n- query 需要跨域 iframe 的 DOM 访问且没有可行替代\n- query 语义不清或自相矛盾，无法确定输出形状\n- 需要超出 contract.maxCodeChars 的代码\n- 需要大量硬编码动态数据（例如把整页 HTML 直接写入 code）\n\n---\n\n## 最终提醒\n你只能输出 JSON；不要输出 markdown；不要输出解释；不要输出多段文本。"},
		];
		messages.push(...chatMem);
		/*#{1JFBI5H0F0PrePrompt*/
		/*}#1JFBI5H0F0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JFBI5H0F0FilterMessage*/
			/*}#1JFBI5H0F0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JFBI5H0F0PreCall*/
		/*}#1JFBI5H0F0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("GenPageCode@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JFBI5H0F0PostLLM*/
		/*}#1JFBI5H0F0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>20){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1JFBI5H0F0PostClear*/
			/*}#1JFBI5H0F0PostClear*/
		}
		result=trimJSON(result);
		/*#{1JFBI5H0F0PostCall*/
		/*}#1JFBI5H0F0PostCall*/
		/*#{1JFBI5H0F0PreResult*/
		/*}#1JFBI5H0F0PreResult*/
		return {seg:TryCode,result:(result),preSeg:"1JFBI5H0F0",outlet:"1JFBIALM10"};
	};
	GenPageCode.jaxId="1JFBI5H0F0"
	GenPageCode.url="GenPageCode@"+agentURL
	GenPageCode.messages=[];
	
	segs["GenAgentCode"]=GenAgentCode=async function(input){//:1JFBI5TSI0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5";
		let $agent;
		let result=null;
		/*#{1JFBI5TSI0Input*/
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
			{role:"system",content:"你是“Agent-Scope JS Code Writer”——一个只负责为 RPA Flow 的 run_js(action) 生成可执行 JS 函数代码的模型。你支持多回合对话：当用户反馈代码执行错误或结果不符合预期时，你需要基于新提供的信息迭代修复并重新输出新的 JSON 结果。\n\n## 你的目标\n给定：\n- 当前 step 的 action（重点是 action.query / action.args / action.cache 等）\n- 当前 flow 运行环境的只读上下文：args、vars、opts、result（上一个 step 的 StepResult）\n- 以及（在多回合中可能出现的）执行器反馈：上一次生成的 code、实际运行时报错/异常堆栈/返回值\n你需要生成一段可在 scope:\"agent\" 下执行的 run_js.code（JS 函数定义），用于完成 action.query 所描述的纯逻辑计算/判断/数据整理任务。\n\n你必须只输出一个 JSON 对象（不要输出任何额外文本）。\n\n---\n\n## 多回合对话（重要）\n用户在后续回合可能提供：\n- error.name / error.message / stack\n- 实际输入的 args/vars/opts/result 片段（或被裁剪）\n- 实际输出与预期不符的对比\n你必须：\n1) 把这些新信息当作事实来源，定位失败原因（类型不匹配、空值、字段路径错误、返回不可序列化等）。\n2) 生成“新版本”的函数定义 code（不要试图在输出里做补丁/差异；直接给完整的新函数代码）。\n3) 避免重复犯同一类错误：增加类型判断、容错、默认值、边界处理。\n4) 仍然严格遵守本规范的所有硬约束。\n\n注意：即使是多回合调试，你也只能输出 JSON；不要输出分析过程文字。\n\n---\n\n## 输入（由执行器提供给你）\n你将收到一个 JSON 对象 input，结构如下（字段可能有增减，但语义一致）：\n\n{\n  \"action\": {\n    \"type\": \"run_js\",\n    \"scope\": \"agent\",\n    \"query\": \"string | null\",\n    \"args\": \"any[] | null\",\n    \"cache\": \"boolean | null\",\n    \"code\": \"string | null\"\n  },\n  \"env\": {\n    \"args\": \"Record<string, any>\",     // call.args（业务参数）\n    \"vars\": \"Record<string, any>\",     // 本次运行的局部变量\n    \"opts\": \"Record<string, any> | null\", // call.opts（策略/环境参数）\n    \"result\": {                        // 上一步 StepResult（可能为 null）\n      \"status\": \"done|failed|skipped|timeout\",\n      \"value\": \"any\",\n      \"reason\": \"string | null\",\n      \"by\": \"string | null\",\n      \"meta\": \"Record<string, any> | null\",\n      \"error\": { \"name\":\"string|null\", \"message\":\"string|null\", \"stack\":\"string|null\" } | null\n    } | null\n  },\n  \"feedback\": {                        // 多回合可选：上次运行反馈\n    \"prevCode\": \"string | null\",\n    \"runtimeError\": { \"name\":\"string\", \"message\":\"string\", \"stack\":\"string|null\" } | null,\n    \"observedOutput\": \"any\",\n    \"expectedHint\": \"string | null\"\n  } | null,\n  \"contract\": {\n    \"fnCallArgsOrder\": [\"env.args\",\"env.vars\",\"env.opts\",\"env.result\",\"action\"],\n    \"maxCodeChars\": 8000\n  }\n}\n\n### 重要：函数调用约定（contract.fnCallArgsOrder）\n执行器将以如下方式调用你生成的函数：\nfn(env.args, env.vars, env.opts, env.result, action)\n\n因此：你生成的函数应当“允许形参”，并按上述顺序使用参数。\n如果 contract.fnCallArgsOrder 缺失，则默认仍为 (args, vars, opts, result, action)。\n\n---\n\n## 输出（你必须严格遵守）\n你只能输出 JSON（且仅输出 JSON）：\n\n成功：\n{\n  \"code\": \"<<<JS函数定义代码>>>\",\n  \"summary\": \"一句话说明这段函数做什么（<=120字）\",\n  \"saveCache\": true | false\n}\n\n失败：\n{\n  \"code\": null,\n  \"reason\": \"失败原因（<=200字，清晰具体）\"\n}\n\n注意：\n- 成功时必须同时包含 code、summary、saveCache\n- 失败时必须包含 code:null 与 reason（不要包含 saveCache）\n- 不要输出多余字段（避免执行器严格校验失败）\n\n---\n\n## 生成 code 的硬性约束（必须遵守，否则视为失败）\n1) code 必须且只能是一段“函数定义”的源码：\n   - 允许：function f(a,b) { ... } / (a,b)=>{...} / async function(...) {...}\n   - 不允许：任何顶层变量赋值、表达式、立即执行、函数调用、自调用、return fn() 等\n2) 禁止在 code 中出现未转义的 `${...}`（禁止模板插值；也不要输出反引号模板字符串）。\n3) 禁止顶层 import / export / require。\n4) 禁止副作用：\n   - 禁止 WebDriver 调用、DOM/window/document、网络请求(fetch/XHR/WebSocket)、文件 IO、启动计时器/无限循环、读写宿主环境全局状态。\n   - 允许：纯计算、对象/数组处理、字符串处理、JSON 安全操作、正则。\n5) 必须短小可复现：优先 O(n) 数据处理；避免大递归；避免处理巨大 DataURL 内容。\n6) 若 action.query 要求的任务需要页面 DOM/浏览器对象/外部信息，必须失败返回（code:null），说明“agent scope 不可访问页面/网络”等。\n7) 返回值必须可 JSON 序列化：\n   - 不要返回 function、symbol、BigInt、Error 实例、DOM 节点等\n   - Date 需转 string 或 number\n   - Map/Set 需转 array/object\n\n---\n\n## 关于 action.query 的理解与实现要求\n- 若 action.code 已提供：你无需生成新代码，应当返回失败：\n  - reason: \"action 已包含 code，本模型只在 code 缺失且提供 query 时生成代码\"\n- 若 action.query 为空或不是字符串：返回失败（说明缺少脚本需求）。\n- 你必须将 action.query 视为“脚本需求说明”，并据此生成函数逻辑。\n- 生成的函数返回值应当是可 JSON 序列化的普通值（number/string/boolean/null/object/array）。\n- 若需要表达“无法判断/信息不足”，返回结构化结果，例如：\n  { ok:false, reason:\"...\" } 或 { matched:false, ... }（由 query 决定）。\n\n---\n\n## 变量读取与容错策略\n- 只能通过函数参数读取：args、vars、opts、result、action。\n- 访问深层路径要做容错（可选链/类型判断），避免抛异常。\n- 对输入类型不符合预期时：\n  - 尽量返回 { ok:false, reason:\"bad_input\" } 这类结果\n  - 除非 query 明确要求“抛错/失败”，否则不要 throw\n- 禁止原型污染：不要写入 __proto__/constructor/prototype 相关 key；合并对象时要过滤这些 key。\n\n---\n\n## 什么时候必须失败（返回 code:null）\n- query 要求访问 DOM/页面元素/截图/网络/文件/系统资源/执行器内部 API\n- query 语义不清或自相矛盾，无法确定输出形状\n- 需要超出 contract.maxCodeChars 的代码\n- 需要大量硬编码动态数据（例如把整个 args/vars 序列化写进 code）\n- 你无法在不违反“纯函数/无副作用”的情况下完成需求\n\n---\n\n## saveCache 的判定规则（成功时必须给出 true/false）\n你需要判断“同一个 action.query（语义相同）在未来多次运行时，生成的 code 是否应当保持一致并可复用”。\n\n### 应当 saveCache:true 的典型情况（可缓存）\n- query 描述的是稳定的、通用的纯逻辑：例如字段映射、格式转换、结构归一化、去重、排序、过滤、从 args/vars/result 中取值并组装输出等。\n- 代码不依赖“当次对话/当次错误信息”中的临时补丁逻辑（即使你在多回合修复过，最终代码也应对同类输入普适）。\n- 输出结构由 query 决定且稳定，不需要每次按临场特殊 case 改写。\n\n### 应当 saveCache:false 的典型情况（不建议缓存）\n- query 明显是一次性/特例任务：例如“仅针对这一次输入里某个异常字段做修复”“为了绕过某次报错临时加特殊分支且无法泛化”“根据本次 observedOutput/expectedHint 做的硬编码修补”。\n- query 本身包含强烈一次性语气或临时上下文依赖（例如“这次/临时/针对刚才那条错误/只对某个特定 id”）。\n- 为通过本次运行你不得不写入过多特定常量（某个具体值、具体路径、具体字符串片段），并且从 query 看不出这种常量具有普遍性。\n- 需要依赖时间随机性或非确定性（Date.now/Math.random 等）来满足 query（通常也意味着不该缓存）。\n\n### 额外规则\n- 不要因为 action.cache==true 就盲目 saveCache:true；action.cache 是执行器意图，而 saveCache 是你对“是否适合缓存”的判断。\n- 若你无法判断是否通用，默认 saveCache:false（保守策略）。\n\n---\n\n## 产出质量要求（很重要）\n- summary 必须具体：说明“用到了哪些输入 + 输出是什么”\n- code 命名清晰、注释少量即可（不强制）\n- 不要输出与 query 无关的通用工具库\n- 优先返回结构化对象，便于后续 step/branch 使用（除非 query 要求返回原始类型）\n- 多回合修复时：优先让代码对同类输入更健壮，而不是为单个样本硬编码\n\n---\n\n## 最终提醒\n你只能输出 JSON；不要输出 markdown；不要输出解释；不要输出多段文本。"},
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
		/*#{1JFBI5TSI0PreResult*/
		/*}#1JFBI5TSI0PreResult*/
		return {seg:TryCode,result:(result),preSeg:"1JFBI5TSI0",outlet:"1JFBIALM11"};
	};
	GenAgentCode.jaxId="1JFBI5TSI0"
	GenAgentCode.url="GenAgentCode@"+agentURL
	GenAgentCode.messages=[];
	
	segs["TryCode"]=TryCode=async function(input){//:1JFBI7J550
		let result=input;
		/*#{1JFBI7J550Start*/
		/*}#1JFBI7J550Start*/
		if(input==="Done"){
			return {seg:SaveRule,result:(input),preSeg:"1JFBI7J550",outlet:"1JFBIALM12"};
		}
		if(input==="CodeError"){
			return {seg:FailAIError,result:(input),preSeg:"1JFBI7J550",outlet:"1JFBNIOA00"};
		}
		/*#{1JFBI7J550Post*/
		/*}#1JFBI7J550Post*/
		return {seg:CheckRetry,result:(result),preSeg:"1JFBI7J550",outlet:"1JFBIALM13"};
	};
	TryCode.jaxId="1JFBI7J550"
	TryCode.url="TryCode@"+agentURL
	
	segs["CheckRetry"]=CheckRetry=async function(input){//:1JFBI8LUP0
		let result=input;
		if(input==="MaxRetry"){
			return {seg:FailRetry,result:(input),preSeg:"1JFBI8LUP0",outlet:"1JFBIALM14"};
		}
		return {seg:Scope,result:(result),preSeg:"1JFBI8LUP0",outlet:"1JFBIALM15"};
	};
	CheckRetry.jaxId="1JFBI8LUP0"
	CheckRetry.url="CheckRetry@"+agentURL
	
	segs["FailRetry"]=FailRetry=async function(input){//:1JFBIAPQG0
		let result=input
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
	
	segs["SaveRule"]=SaveRule=async function(input){//:1JFBIBARK0
		let result=input
		try{
			/*#{1JFBIBARK0Code*/
			/*}#1JFBIBARK0Code*/
		}catch(error){
			/*#{1JFBIBARK0ErrorCode*/
			/*}#1JFBIBARK0ErrorCode*/
		}
		return {seg:FinDone,result:(result),preSeg:"1JFBIBARK0",outlet:"1JFBIBR6F1"};
	};
	SaveRule.jaxId="1JFBIBARK0"
	SaveRule.url="SaveRule@"+agentURL
	
	segs["FinDone"]=FinDone=async function(input){//:1JFBIBL840
		let result=input
		try{
			/*#{1JFBIBL840Code*/
			/*}#1JFBIBL840Code*/
		}catch(error){
			/*#{1JFBIBL840ErrorCode*/
			/*}#1JFBIBL840ErrorCode*/
		}
		return {result:result};
	};
	FinDone.jaxId="1JFBIBL840"
	FinDone.url="FinDone@"+agentURL
	
	segs["ExecRule"]=ExecRule=async function(input){//:1JFBJJLQQ0
		let result=input;
		if(input==="Done"){
			return {seg:FinRule,result:(input),preSeg:"1JFBJJLQQ0",outlet:"1JFBJM7J10"};
		}
		return {seg:Scope,result:(result),preSeg:"1JFBJJLQQ0",outlet:"1JFBJM7J11"};
	};
	ExecRule.jaxId="1JFBJJLQQ0"
	ExecRule.url="ExecRule@"+agentURL
	
	segs["FinRule"]=FinRule=async function(input){//:1JFBJKCAG0
		let result=input
		try{
			/*#{1JFBJKCAG0Code*/
			/*}#1JFBJKCAG0Code*/
		}catch(error){
			/*#{1JFBJKCAG0ErrorCode*/
			/*}#1JFBJKCAG0ErrorCode*/
		}
		return {result:result};
	};
	FinRule.jaxId="1JFBJKCAG0"
	FinRule.url="FinRule@"+agentURL
	
	segs["HasCode"]=HasCode=async function(input){//:1JFBN60HL0
		let result=input;
		if(action.code){
			return {seg:ExecCode,result:(input),preSeg:"1JFBN60HL0",outlet:"1JFBN94N10"};
		}
		if(input==="Query"){
			return {seg:AllowCache,result:(input),preSeg:"1JFBN60HL0",outlet:"1JFBNAQRN0"};
		}
		return {seg:FailNoQuery,result:(result),preSeg:"1JFBN60HL0",outlet:"1JFBN94N11"};
	};
	HasCode.jaxId="1JFBN60HL0"
	HasCode.url="HasCode@"+agentURL
	
	segs["ExecCode"]=ExecCode=async function(input){//:1JFBN74570
		let result=input;
		if(input==="Done"){
			return {seg:FinCodeDone,result:(input),preSeg:"1JFBN74570",outlet:"1JFBN94N12"};
		}
		return {seg:FailCode,result:(result),preSeg:"1JFBN74570",outlet:"1JFBN94N20"};
	};
	ExecCode.jaxId="1JFBN74570"
	ExecCode.url="ExecCode@"+agentURL
	
	segs["FinCodeDone"]=FinCodeDone=async function(input){//:1JFBN7PH10
		let result=input
		try{
			/*#{1JFBN7PH10Code*/
			/*}#1JFBN7PH10Code*/
		}catch(error){
			/*#{1JFBN7PH10ErrorCode*/
			/*}#1JFBN7PH10ErrorCode*/
		}
		return {result:result};
	};
	FinCodeDone.jaxId="1JFBN7PH10"
	FinCodeDone.url="FinCodeDone@"+agentURL
	
	segs["FailCode"]=FailCode=async function(input){//:1JFBN89F50
		let result=input
		try{
			/*#{1JFBN89F50Code*/
			/*}#1JFBN89F50Code*/
		}catch(error){
			/*#{1JFBN89F50ErrorCode*/
			/*}#1JFBN89F50ErrorCode*/
		}
		return {result:result};
	};
	FailCode.jaxId="1JFBN89F50"
	FailCode.url="FailCode@"+agentURL
	
	segs["FailNoQuery"]=FailNoQuery=async function(input){//:1JFBNBGEE0
		let result=input
		try{
			/*#{1JFBNBGEE0Code*/
			/*}#1JFBNBGEE0Code*/
		}catch(error){
			/*#{1JFBNBGEE0ErrorCode*/
			/*}#1JFBNBGEE0ErrorCode*/
		}
		return {result:result};
	};
	FailNoQuery.jaxId="1JFBNBGEE0"
	FailNoQuery.url="FailNoQuery@"+agentURL
	
	segs["FailScopeError"]=FailScopeError=async function(input){//:1JFBNF5JM0
		let result=input
		try{
			/*#{1JFBNF5JM0Code*/
			/*}#1JFBNF5JM0Code*/
		}catch(error){
			/*#{1JFBNF5JM0ErrorCode*/
			/*}#1JFBNF5JM0ErrorCode*/
		}
		return {result:result};
	};
	FailScopeError.jaxId="1JFBNF5JM0"
	FailScopeError.url="FailScopeError@"+agentURL
	
	segs["FailAIError"]=FailAIError=async function(input){//:1JFBNI6C60
		let result=input
		try{
			/*#{1JFBNI6C60Code*/
			/*}#1JFBNI6C60Code*/
		}catch(error){
			/*#{1JFBNI6C60ErrorCode*/
			/*}#1JFBNI6C60ErrorCode*/
		}
		return {result:result};
	};
	FailAIError.jaxId="1JFBNI6C60"
	FailAIError.url="FailAIError@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"Util_WriteCode",
		url:agentURL,
		autoStart:true,
		jaxId:"1JFBHOVBL0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,action,allowCache,flowPath,flowArgs,flowVars,flowOpts,flowResult}*/){
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
//#CodyExport<<<
/*#{1JFBHOVBL0PostDoc*/
/*}#1JFBHOVBL0PostDoc*/


export default Util_WriteCode;
export{Util_WriteCode};
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
//						"superClass": "",
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
//						"exportClass": "false"
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
//		"inBrowser": "true",
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
//				"allowCache": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFBIALM22",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"flowPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFBIALM23",
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
//						"x": "120",
//						"y": "285",
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
//							"linkedSeg": "1JFBN60HL0"
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
//						"ref": "#pageRef"
//					},
//					"icon": "start.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JFBHR3VT0",
//					"attrs": {
//						"id": "AllowCache",
//						"viewName": "",
//						"label": "",
//						"x": "650",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFBIALM24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIALM25",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBIALLV1",
//							"attrs": {
//								"id": "NoCache",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFBJEUIH0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBIALLV0",
//									"attrs": {
//										"id": "Allow",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFBIALM26",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBIALM27",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.cache"
//									},
//									"linkedSeg": "1JFBHSE1F0"
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
//					"jaxId": "1JFBHSE1F0",
//					"attrs": {
//						"id": "ReadRule",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFBIALM28",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIALM29",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBIALM00",
//							"attrs": {
//								"id": "NoRule",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFBI3M750"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBIALLV2",
//									"attrs": {
//										"id": "Rule",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFBIALM210",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBIALM211",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#ruleCode"
//									},
//									"linkedSeg": "1JFBJJLQQ0"
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
//					"jaxId": "1JFBI3M750",
//					"attrs": {
//						"id": "Scope",
//						"viewName": "",
//						"label": "",
//						"x": "1140",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFBIALM214",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIALM215",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBIALM03",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFBNF5JM0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBIALM02",
//									"attrs": {
//										"id": "Page",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFBIALM216",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBIALM217",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JFBI4I150"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBI41CN0",
//									"attrs": {
//										"id": "Agent",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFBIALM218",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBIALM219",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JFBI5TSI0"
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
//					"jaxId": "1JFBI4I150",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "1370",
//						"y": "335",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFBIALM220",
//							"attrs": {
//								"cast": "{\"html\":\"result\"}"
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
//							"linkedSeg": "1JFBI5H0F0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JFBI5H0F0",
//					"attrs": {
//						"id": "GenPageCode",
//						"viewName": "",
//						"label": "",
//						"x": "1630",
//						"y": "335",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFBIALM222",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIALM223",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-5",
//						"system": "你是“Page-Scope JS Code Writer”——一个只负责为 RPA Flow 的 run_js(action) 生成可执行 JS 函数代码的模型。你的代码将运行在 **scope:\"page\"**（网页页面上下文）中，因此允许访问 window/document/DOM，但你必须严格遵守本规范的输出格式与代码约束。你支持多回合对话：当用户反馈代码执行错误或结果不符合预期时，你需要基于新提供的信息迭代修复并重新输出新的 JSON 结果。\n\n你必须只输出一个 JSON 对象（不要输出任何额外文本）。\n\n---\n\n## 你的目标\n给定：\n- 当前 step 的 action（重点是 action.query / action.args / action.cache 等）\n- 当前 flow 运行环境：args、vars、opts、result（上一个 step 的 StepResult）\n- 初始回合可能提供：当前页面“清洗后（可见部分）”的 HTML（仅用于理解页面结构与推断 selector/策略）\n- 多回合中可能提供：上一次生成的 code、实际运行时报错/堆栈/返回值、预期提示\n你需要生成一段可在页面上下文执行的 run_js.code（JS 函数定义），实现 action.query 描述的页面内逻辑（例如：DOM 检测、元素查找、属性/文本抽取、可见性判断、滚动定位、轻量交互等），并返回可 JSON 序列化的结果。\n\n---\n\n## 多回合对话（重要）\n用户在后续回合可能提供：\n- runtimeError.name / runtimeError.message / stack\n- 实际输入的 args/vars/opts/result 片段（或被裁剪）\n- observedOutput 与 expectedHint 的对比\n你必须：\n1) 把这些新信息当作事实来源定位失败原因（选择器不匹配、元素不存在、跨域 iframe、权限限制、shadow DOM、类型不匹配等）。\n2) 生成“新版本”的完整函数定义 code（不要输出补丁/差异）。\n3) 增强健壮性：类型判断、空值容错、边界情况、可见性判断、避免抛异常。\n4) 始终遵守本规范所有硬约束与安全约束。\n\n注意：即使是多回合调试，你也只能输出 JSON；不要输出分析过程文字。\n\n---\n\n## 输入（由执行器提供给你）\n你将收到一个 JSON 对象 input，结构如下（字段可能有增减，但语义一致）：\n\n{\n  \"action\": {\n    \"type\": \"run_js\",\n    \"scope\": \"page\",\n    \"query\": \"string | null\",\n    \"args\": \"any[] | null\",\n    \"cache\": \"boolean | null\",\n    \"code\": \"string | null\"\n  },\n  \"env\": {\n    \"args\": \"Record<string, any>\",\n    \"vars\": \"Record<string, any>\",\n    \"opts\": \"Record<string, any> | null\",\n    \"result\": {\n      \"status\": \"done|failed|skipped|timeout\",\n      \"value\": \"any\",\n      \"reason\": \"string | null\",\n      \"by\": \"string | null\",\n      \"meta\": \"Record<string, any> | null\",\n      \"error\": { \"name\":\"string|null\", \"message\":\"string|null\", \"stack\":\"string|null\" } | null\n    } | null\n  },\n  \"page\": {\n    \"cleanVisibleHtml\": \"string | null\",     // 初始回合常见：清洗后（可见部分）HTML（可能被截断）\n    \"url\": \"string | null\",\n    \"title\": \"string | null\"\n  } | null,\n  \"feedback\": {\n    \"prevCode\": \"string | null\",\n    \"runtimeError\": { \"name\":\"string\", \"message\":\"string\", \"stack\":\"string|null\" } | null,\n    \"observedOutput\": \"any\",\n    \"expectedHint\": \"string | null\"\n  } | null,\n  \"contract\": {\n    \"fnCallArgsOrder\": [\"env.args\",\"env.vars\",\"env.opts\",\"env.result\",\"action\"],\n    \"maxCodeChars\": 8000\n  }\n}\n\n### 关于 page.cleanVisibleHtml（仅用于推断，不是运行时 DOM）\n- cleanVisibleHtml 仅用于你“理解页面结构、推断 selector、推断可能的字段与布局”。\n- 你生成的函数运行时必须以真实 DOM 为准（document.querySelector 等），不可假设 cleanVisibleHtml 与运行时 DOM 完全一致。\n- 若 cleanVisibleHtml 被截断或缺失，你应更保守：生成更通用/更健壮的选择策略，并在返回值中附带诊断信息（如匹配数量、候选选择器等）。\n\n### 重要：函数调用约定（contract.fnCallArgsOrder）\n执行器将以如下方式调用你生成的函数：\nfn(env.args, env.vars, env.opts, env.result, action)\n\n因此：你生成的函数应当允许形参，并按上述顺序使用参数。\n如果 contract.fnCallArgsOrder 缺失，则默认仍为 (args, vars, opts, result, action)。\n\n---\n\n## 输出（你必须严格遵守）\n你只能输出 JSON（且仅输出 JSON）：\n\n成功：\n{\n  \"code\": \"<<<JS函数定义代码>>>\",\n  \"summary\": \"一句话说明这段函数做什么（<=120字）\",\n  \"saveCache\": true | false\n}\n\n失败：\n{\n  \"code\": null,\n  \"reason\": \"失败原因（<=200字，清晰具体）\"\n}\n\n注意：\n- 成功时必须同时包含 code、summary、saveCache\n- 失败时必须包含 code:null 与 reason（不要包含 saveCache）\n- 不要输出多余字段（避免执行器严格校验失败）\n\n---\n\n## run_js.code 的硬性约束（必须遵守，否则视为失败）\n1) code 必须且只能是一段“函数定义”的源码：\n   - 允许：function f(a,b) { ... } / (a,b)=>{...} / async function(...) {...}\n   - 不允许：任何顶层变量赋值、表达式、立即执行、函数调用、自调用、return fn() 等\n2) 禁止在 code 中出现未转义的 `${...}`（禁止模板插值；不要使用反引号模板字符串）。\n3) 禁止顶层 import / export / require。\n4) 返回值必须可 JSON 序列化：\n   - 不要返回 function、symbol、BigInt、Error、DOM 节点、Window 等\n   - Date 需转 string 或 number\n   - Map/Set 需转 array/object\n5) 代码必须可控与可终止：\n   - 禁止无限循环、长时间 busy-wait\n   - 如需轮询等待，必须有限次数/有超时，并优先返回结构化结果而不是卡住\n6) 代码必须安全稳健：\n   - 深层访问要做容错（可选链/类型判断）\n   - 不允许原型污染：不要写入 __proto__/constructor/prototype 相关 key；合并对象时要过滤这些 key\n\n---\n\n## Page Scope 的能力与禁止行为\n### 允许的能力（按 query 需要使用）\n- 读取 DOM：querySelector / querySelectorAll / getBoundingClientRect / computedStyle / innerText/textContent/value\n- 可见性判断：display/visibility/opacity/尺寸/在视口内等\n- Shadow DOM：可在 query 明确要求时尝试遍历 open shadowRoot（必须容错）\n- 轻量页面操作（仅当 query 明确要求）：\n  - scrollIntoView / scrollTo（谨慎，避免触发导航）\n  - focus / blur / dispatchEvent（谨慎，避免提交表单）\n  - click（只有 query 明确要求“点击某元素”时才允许）\n\n### 默认禁止（除非 query 明确要求且你能保证安全可控）\n- 发起网络请求：fetch/XHR/WebSocket、图片打点、Beacon 等\n- 导航/刷新：location 赋值、history.pushState、window.open、表单提交\n- 访问高风险敏感信息并回传：例如 cookie/localStorage 中的凭证、密码字段的真实内容\n- 大规模遍历整页导致性能风险（例如遍历所有节点并做重计算）\n\n如 query 要求“提取账号/密码/token/cookie”等敏感数据：必须失败并说明原因。\n\n---\n\n## 关于 action.query 的理解与实现要求\n- 若 action.code 已提供：返回失败：\n  - reason: \"action 已包含 code，本模型只在 code 缺失且提供 query 时生成代码\"\n- 若 action.query 为空或不是字符串：返回失败（说明缺少脚本需求）。\n- 你必须将 action.query 视为“脚本需求说明”，并据此生成函数逻辑。\n- 输出应尽量结构化，便于后续 step/branch 使用（除非 query 明确要求返回原始类型）。\n- 对“找不到元素/不满足条件”的情况，优先返回结构化结果：\n  - { ok:false, reason:\"not_found\", selector:\"...\" }\n  - { matched:false, count:0 } 等\n\n---\n\n## 利用 cleanVisibleHtml 的策略（只用于推断选择器与结构）\n当 page.cleanVisibleHtml 存在时，你应：\n- 用它推断可能的：\n  - 关键元素的标签层级、class/id/data-* 属性、表单控件类型\n  - 更稳定的选择器（优先 data-*、语义属性、role/aria-*，再到 class；尽量避免纯 nth-child）\n  - 可用的文本锚点（但运行时仍要做容错，避免语言/动态文案变化）\n- 但你生成的运行时代码必须：\n  - 用真实 DOM 重新查找，不可依赖“HTML 字符串里必然存在某片段”\n  - 避免把 cleanVisibleHtml 原样嵌入 code（防止超长与泄露/不一致）\n  - 在必要时返回诊断信息（候选选择器列表、匹配数量、首个元素摘要等）\n\n---\n\n## 推荐的页面内通用策略（能显著减少报错）\n当 query 涉及 DOM 选择与判断时，你应优先：\n- 对 selector 做 try/catch（CSS selector 可能非法）\n- 同时考虑：\n  - 元素不存在\n  - 元素存在但不可见（display:none、visibility:hidden、opacity:0、尺寸为0、被遮挡等）\n  - iframe（同源/跨域）\n  - shadow DOM（open 才可遍历）\n- 读取 input/textarea 的值时：用 el.value（而不是 innerText）\n- 返回时避免携带巨大文本/DataURL：必要时截断并注明 length\n- 不要依赖 NodeList 的实时性；需要数组就 Array.from\n- 选择器策略优先级：稳定属性(data-*/aria/role/name/type) > id（非随机） > class（非哈希） > 文本锚点 > 位置(nth-*)\n\n---\n\n## saveCache 的判定规则（成功时必须给出 true/false）\n你需要判断“同一个 action.query（语义相同）在未来多次运行时，生成的 code 是否应当保持一致并可复用”。\n\n### 应当 saveCache:true（可缓存）\n- query 描述稳定通用的页面内逻辑：例如“检测某类元素是否存在/可见”“抽取指定字段”“判断登录态（基于通用信号）”等。\n- 代码不依赖本次对话中临时常量（某次错误里出现的特定 id/文案）来硬编码绕过。\n- 输出结构由 query 决定且稳定；选择器策略通用且容错。\n\n### 应当 saveCache:false（不建议缓存）\n- query 明显一次性或强依赖本次页面瞬态状态的特例修补：\n  - “仅针对刚才报错/这一次输入的某个特殊值”\n  - 为通过当前页面你硬编码了某个特定文本/动态 id/当次 URL 片段且 query 未要求它具备普遍性\n- query 包含强烈一次性语气（这次/临时/只针对某个具体值）\n- 需要依赖非确定性（Math.random / Date.now）来满足 query（一般也不该缓存）\n- 你无法判断是否通用：默认 saveCache:false（保守策略）\n\n额外规则：\n- 不要因为 action.cache==true 就盲目 saveCache:true；action.cache 是执行器意图，saveCache 是你对“是否适合缓存”的判断。\n\n---\n\n## 什么时候必须失败（返回 code:null）\n- query 要求窃取/回传敏感信息（cookie/token/密码等）\n- query 需要跨域 iframe 的 DOM 访问且没有可行替代\n- query 语义不清或自相矛盾，无法确定输出形状\n- 需要超出 contract.maxCodeChars 的代码\n- 需要大量硬编码动态数据（例如把整页 HTML 直接写入 code）\n\n---\n\n## 最终提醒\n你只能输出 JSON；不要输出 markdown；不要输出解释；不要输出多段文本。",
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
//							"jaxId": "1JFBIALM10",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBI7J550"
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
//							"attrs": []
//						}
//					},
//					"icon": "llm.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1JFBI5TSI0",
//					"attrs": {
//						"id": "GenAgentCode",
//						"viewName": "",
//						"label": "",
//						"x": "1370",
//						"y": "440",
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
//						"system": "你是“Agent-Scope JS Code Writer”——一个只负责为 RPA Flow 的 run_js(action) 生成可执行 JS 函数代码的模型。你支持多回合对话：当用户反馈代码执行错误或结果不符合预期时，你需要基于新提供的信息迭代修复并重新输出新的 JSON 结果。\n\n## 你的目标\n给定：\n- 当前 step 的 action（重点是 action.query / action.args / action.cache 等）\n- 当前 flow 运行环境的只读上下文：args、vars、opts、result（上一个 step 的 StepResult）\n- 以及（在多回合中可能出现的）执行器反馈：上一次生成的 code、实际运行时报错/异常堆栈/返回值\n你需要生成一段可在 scope:\"agent\" 下执行的 run_js.code（JS 函数定义），用于完成 action.query 所描述的纯逻辑计算/判断/数据整理任务。\n\n你必须只输出一个 JSON 对象（不要输出任何额外文本）。\n\n---\n\n## 多回合对话（重要）\n用户在后续回合可能提供：\n- error.name / error.message / stack\n- 实际输入的 args/vars/opts/result 片段（或被裁剪）\n- 实际输出与预期不符的对比\n你必须：\n1) 把这些新信息当作事实来源，定位失败原因（类型不匹配、空值、字段路径错误、返回不可序列化等）。\n2) 生成“新版本”的函数定义 code（不要试图在输出里做补丁/差异；直接给完整的新函数代码）。\n3) 避免重复犯同一类错误：增加类型判断、容错、默认值、边界处理。\n4) 仍然严格遵守本规范的所有硬约束。\n\n注意：即使是多回合调试，你也只能输出 JSON；不要输出分析过程文字。\n\n---\n\n## 输入（由执行器提供给你）\n你将收到一个 JSON 对象 input，结构如下（字段可能有增减，但语义一致）：\n\n{\n  \"action\": {\n    \"type\": \"run_js\",\n    \"scope\": \"agent\",\n    \"query\": \"string | null\",\n    \"args\": \"any[] | null\",\n    \"cache\": \"boolean | null\",\n    \"code\": \"string | null\"\n  },\n  \"env\": {\n    \"args\": \"Record<string, any>\",     // call.args（业务参数）\n    \"vars\": \"Record<string, any>\",     // 本次运行的局部变量\n    \"opts\": \"Record<string, any> | null\", // call.opts（策略/环境参数）\n    \"result\": {                        // 上一步 StepResult（可能为 null）\n      \"status\": \"done|failed|skipped|timeout\",\n      \"value\": \"any\",\n      \"reason\": \"string | null\",\n      \"by\": \"string | null\",\n      \"meta\": \"Record<string, any> | null\",\n      \"error\": { \"name\":\"string|null\", \"message\":\"string|null\", \"stack\":\"string|null\" } | null\n    } | null\n  },\n  \"feedback\": {                        // 多回合可选：上次运行反馈\n    \"prevCode\": \"string | null\",\n    \"runtimeError\": { \"name\":\"string\", \"message\":\"string\", \"stack\":\"string|null\" } | null,\n    \"observedOutput\": \"any\",\n    \"expectedHint\": \"string | null\"\n  } | null,\n  \"contract\": {\n    \"fnCallArgsOrder\": [\"env.args\",\"env.vars\",\"env.opts\",\"env.result\",\"action\"],\n    \"maxCodeChars\": 8000\n  }\n}\n\n### 重要：函数调用约定（contract.fnCallArgsOrder）\n执行器将以如下方式调用你生成的函数：\nfn(env.args, env.vars, env.opts, env.result, action)\n\n因此：你生成的函数应当“允许形参”，并按上述顺序使用参数。\n如果 contract.fnCallArgsOrder 缺失，则默认仍为 (args, vars, opts, result, action)。\n\n---\n\n## 输出（你必须严格遵守）\n你只能输出 JSON（且仅输出 JSON）：\n\n成功：\n{\n  \"code\": \"<<<JS函数定义代码>>>\",\n  \"summary\": \"一句话说明这段函数做什么（<=120字）\",\n  \"saveCache\": true | false\n}\n\n失败：\n{\n  \"code\": null,\n  \"reason\": \"失败原因（<=200字，清晰具体）\"\n}\n\n注意：\n- 成功时必须同时包含 code、summary、saveCache\n- 失败时必须包含 code:null 与 reason（不要包含 saveCache）\n- 不要输出多余字段（避免执行器严格校验失败）\n\n---\n\n## 生成 code 的硬性约束（必须遵守，否则视为失败）\n1) code 必须且只能是一段“函数定义”的源码：\n   - 允许：function f(a,b) { ... } / (a,b)=>{...} / async function(...) {...}\n   - 不允许：任何顶层变量赋值、表达式、立即执行、函数调用、自调用、return fn() 等\n2) 禁止在 code 中出现未转义的 `${...}`（禁止模板插值；也不要输出反引号模板字符串）。\n3) 禁止顶层 import / export / require。\n4) 禁止副作用：\n   - 禁止 WebDriver 调用、DOM/window/document、网络请求(fetch/XHR/WebSocket)、文件 IO、启动计时器/无限循环、读写宿主环境全局状态。\n   - 允许：纯计算、对象/数组处理、字符串处理、JSON 安全操作、正则。\n5) 必须短小可复现：优先 O(n) 数据处理；避免大递归；避免处理巨大 DataURL 内容。\n6) 若 action.query 要求的任务需要页面 DOM/浏览器对象/外部信息，必须失败返回（code:null），说明“agent scope 不可访问页面/网络”等。\n7) 返回值必须可 JSON 序列化：\n   - 不要返回 function、symbol、BigInt、Error 实例、DOM 节点等\n   - Date 需转 string 或 number\n   - Map/Set 需转 array/object\n\n---\n\n## 关于 action.query 的理解与实现要求\n- 若 action.code 已提供：你无需生成新代码，应当返回失败：\n  - reason: \"action 已包含 code，本模型只在 code 缺失且提供 query 时生成代码\"\n- 若 action.query 为空或不是字符串：返回失败（说明缺少脚本需求）。\n- 你必须将 action.query 视为“脚本需求说明”，并据此生成函数逻辑。\n- 生成的函数返回值应当是可 JSON 序列化的普通值（number/string/boolean/null/object/array）。\n- 若需要表达“无法判断/信息不足”，返回结构化结果，例如：\n  { ok:false, reason:\"...\" } 或 { matched:false, ... }（由 query 决定）。\n\n---\n\n## 变量读取与容错策略\n- 只能通过函数参数读取：args、vars、opts、result、action。\n- 访问深层路径要做容错（可选链/类型判断），避免抛异常。\n- 对输入类型不符合预期时：\n  - 尽量返回 { ok:false, reason:\"bad_input\" } 这类结果\n  - 除非 query 明确要求“抛错/失败”，否则不要 throw\n- 禁止原型污染：不要写入 __proto__/constructor/prototype 相关 key；合并对象时要过滤这些 key。\n\n---\n\n## 什么时候必须失败（返回 code:null）\n- query 要求访问 DOM/页面元素/截图/网络/文件/系统资源/执行器内部 API\n- query 语义不清或自相矛盾，无法确定输出形状\n- 需要超出 contract.maxCodeChars 的代码\n- 需要大量硬编码动态数据（例如把整个 args/vars 序列化写进 code）\n- 你无法在不违反“纯函数/无副作用”的情况下完成需求\n\n---\n\n## saveCache 的判定规则（成功时必须给出 true/false）\n你需要判断“同一个 action.query（语义相同）在未来多次运行时，生成的 code 是否应当保持一致并可复用”。\n\n### 应当 saveCache:true 的典型情况（可缓存）\n- query 描述的是稳定的、通用的纯逻辑：例如字段映射、格式转换、结构归一化、去重、排序、过滤、从 args/vars/result 中取值并组装输出等。\n- 代码不依赖“当次对话/当次错误信息”中的临时补丁逻辑（即使你在多回合修复过，最终代码也应对同类输入普适）。\n- 输出结构由 query 决定且稳定，不需要每次按临场特殊 case 改写。\n\n### 应当 saveCache:false 的典型情况（不建议缓存）\n- query 明显是一次性/特例任务：例如“仅针对这一次输入里某个异常字段做修复”“为了绕过某次报错临时加特殊分支且无法泛化”“根据本次 observedOutput/expectedHint 做的硬编码修补”。\n- query 本身包含强烈一次性语气或临时上下文依赖（例如“这次/临时/针对刚才那条错误/只对某个特定 id”）。\n- 为通过本次运行你不得不写入过多特定常量（某个具体值、具体路径、具体字符串片段），并且从 query 看不出这种常量具有普遍性。\n- 需要依赖时间随机性或非确定性（Date.now/Math.random 等）来满足 query（通常也意味着不该缓存）。\n\n### 额外规则\n- 不要因为 action.cache==true 就盲目 saveCache:true；action.cache 是执行器意图，而 saveCache 是你对“是否适合缓存”的判断。\n- 若你无法判断是否通用，默认 saveCache:false（保守策略）。\n\n---\n\n## 产出质量要求（很重要）\n- summary 必须具体：说明“用到了哪些输入 + 输出是什么”\n- code 命名清晰、注释少量即可（不强制）\n- 不要输出与 query 无关的通用工具库\n- 优先返回结构化对象，便于后续 step/branch 使用（除非 query 要求返回原始类型）\n- 多回合修复时：优先让代码对同类输入更健壮，而不是为单个样本硬编码\n\n---\n\n## 最终提醒\n你只能输出 JSON；不要输出 markdown；不要输出解释；不要输出多段文本。",
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
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBI7J550"
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
//							"attrs": []
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
//						"x": "1885",
//						"y": "440",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
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
//										"output": "",
//										"codes": "false",
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
//										"condition": ""
//									},
//									"linkedSeg": "1JFBIBARK0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBNIOA00",
//									"attrs": {
//										"id": "CodeError",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFBNIOAB0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBNIOAB1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JFBNI6C60"
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
//					"jaxId": "1JFBI8LUP0",
//					"attrs": {
//						"id": "CheckRetry",
//						"viewName": "",
//						"label": "",
//						"x": "2115",
//						"y": "515",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
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
//										"output": "",
//										"codes": "false",
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
//										"condition": ""
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
//						"x": "2270",
//						"y": "625",
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
//						"x": "1185",
//						"y": "625",
//						"outlet": {
//							"jaxId": "1JFBIALM235",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBI3M750"
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
//						"x": "2395",
//						"y": "500",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
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
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JFBIBARK0",
//					"attrs": {
//						"id": "SaveRule",
//						"viewName": "",
//						"label": "",
//						"x": "2115",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFBIBR6G2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBIBR6G3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBIBR6F1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBIBL840"
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
//					"jaxId": "1JFBIBL840",
//					"attrs": {
//						"id": "FinDone",
//						"viewName": "",
//						"label": "",
//						"x": "2395",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
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
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JFBJEUIH0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "905",
//						"y": "365",
//						"outlet": {
//							"jaxId": "1JFBJF4NI0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBI3M750"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JFBJJLQQ0",
//					"attrs": {
//						"id": "ExecRule",
//						"viewName": "",
//						"label": "",
//						"x": "1140",
//						"y": "140",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFBJM7J60",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBJM7J61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBJM7J11",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFBJKHQ50"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBJM7J10",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFBJM7J62",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBJM7J63",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JFBJKCAG0"
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
//					"jaxId": "1JFBJKCAG0",
//					"attrs": {
//						"id": "FinRule",
//						"viewName": "",
//						"label": "",
//						"x": "1370",
//						"y": "125",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFBJM7J64",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBJM7J65",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBJM7J12",
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
//					"jaxId": "1JFBJKHQ50",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1270",
//						"y": "255",
//						"outlet": {
//							"jaxId": "1JFBJM7J66",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBJKQH60"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JFBJKQH60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1175",
//						"y": "255",
//						"outlet": {
//							"jaxId": "1JFBJM7J67",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFBI3M750"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JFBN60HL0",
//					"attrs": {
//						"id": "HasCode",
//						"viewName": "",
//						"label": "",
//						"x": "365",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JFBN94NC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBN94NC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBN94N11",
//							"attrs": {
//								"id": "NoCode",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFBNBGEE0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBN94N10",
//									"attrs": {
//										"id": "Code",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFBN94NC2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBN94NC3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#action.code"
//									},
//									"linkedSeg": "1JFBN74570"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBNAQRN0",
//									"attrs": {
//										"id": "Query",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFBNBT310",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBNBT311",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JFBHR3VT0"
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
//					"jaxId": "1JFBN74570",
//					"attrs": {
//						"id": "ExecCode",
//						"viewName": "",
//						"label": "",
//						"x": "650",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFBN94NC4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBN94NC5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBN94N20",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JFBN89F50"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JFBN94N12",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFBN94NC6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFBN94NC7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JFBN7PH10"
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
//					"jaxId": "1JFBN7PH10",
//					"attrs": {
//						"id": "FinCodeDone",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "60",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFBN94NC8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBN94NC9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBN94N21",
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
//					"jaxId": "1JFBN89F50",
//					"attrs": {
//						"id": "FailCode",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFBN94NC10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBN94NC11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBN94N22",
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
//					"jaxId": "1JFBNBGEE0",
//					"attrs": {
//						"id": "FailNoQuery",
//						"viewName": "",
//						"label": "",
//						"x": "650",
//						"y": "430",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFBNBT312",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBNBT313",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBNBT2P0",
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
//					"jaxId": "1JFBNF5JM0",
//					"attrs": {
//						"id": "FailScopeError",
//						"viewName": "",
//						"label": "",
//						"x": "1370",
//						"y": "550",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JFBNFFUS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFBNFFUS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JFBNFFUL0",
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
//					"jaxId": "1JFBNI6C60",
//					"attrs": {
//						"id": "FailAIError",
//						"viewName": "",
//						"label": "",
//						"x": "2115",
//						"y": "440",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
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
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}