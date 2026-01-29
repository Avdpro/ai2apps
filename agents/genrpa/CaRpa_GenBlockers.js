//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JDULJF8N0MoreImports*/
import {urlToJsonName,readJson,saveJson,resolveUrl,buildRpaMicroDeciderPrompt,readRule,saveRule} from "./utils.js";
/*}#1JDULJF8N0MoreImports*/
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
		"blockers":{
			"name":"blockers","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"waitAfter":{
			"name":"waitAfter","type":"integer",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1JDULJF8N0ArgsView*/
	/*}#1JDULJF8N0ArgsView*/
};

/*#{1JDULJF8N0StartDoc*/
function detectBlockersWebDriver(opts) {
	opts = opts || {};
	const maxScan = Number.isFinite(opts.maxScan) ? opts.maxScan : 1500;
	const minCoverRatio = Number.isFinite(opts.minCoverRatio) ? opts.minCoverRatio : 0.25;
	const extraSelectors = Array.isArray(opts.extraSelectors) ? opts.extraSelectors : [];

	function isElementVisible(el) {
		let showLog=el.id==="cm";
		showLog && console.log("Check node: ",el);
		if (!el || el.nodeType !== 1){
			showLog && console.log("Exit 1");
			return false;
		}
		if (el.hidden){
			showLog && console.log("Exit 2");
			return false;
		}

		const style = window.getComputedStyle(el);
		if (!style){
			showLog && console.log("Exit 3");
			return false;
		}

		if (style.display === "none"){
			showLog && console.log("Exit 4");
			return false;
		}
		if (style.visibility === "hidden" || style.visibility === "collapse"){
			showLog && console.log("Exit 5: "+style.visibility);
			return false;
		}
		if (parseFloat(style.opacity || "1") < 0.02){
			showLog && console.log("Exit 5.5");
			return false;
		}
		if (style.pointerEvents === "none"){
			showLog && console.log("Exit 6");
			return false;
		}

		const ariaHidden = el.getAttribute("aria-hidden");
		if (ariaHidden === "true"){
			showLog && console.log("Exit 7");
			return false;
		}

		const rect = el.getBoundingClientRect();
		if (!rect || rect.width < 2 || rect.height < 2){
			showLog && console.log("Exit 8");
			return false;
		}

		const vw = Math.max(document.documentElement.clientWidth, window.innerWidth || 0);
		const vh = Math.max(document.documentElement.clientHeight, window.innerHeight || 0);

		const inViewport =
			rect.bottom > 0 &&
			rect.right > 0 &&
			rect.top < vh &&
			rect.left < vw;

		if (!inViewport){
			showLog && console.log("Exit 9");
			return false;
		}
		if (el.getClientRects().length === 0){
			showLog && console.log("Exit 10");
			return false;
		}

		return true;
	}

	function getZIndex(el) {
		const style = window.getComputedStyle(el);
		const z = parseInt(style.zIndex, 10);
		return Number.isFinite(z) ? z : 0;
	}

	function coversViewportEnough(el, ratio) {
		const showLog=el.id==="cm";
		const rect = el.getBoundingClientRect();
		const vw = Math.max(document.documentElement.clientWidth, window.innerWidth || 0);
		const vh = Math.max(document.documentElement.clientHeight, window.innerHeight || 0);

		const w = Math.max(0, Math.min(rect.right, vw) - Math.max(rect.left, 0));
		const h = Math.max(0, Math.min(rect.bottom, vh) - Math.max(rect.top, 0));
		const area = w * h;
		const viewportArea = vw * vh;
		
		if((w>=vw*0.8 && h>=50)||(h>=vh*0.8 && w>=50)){
			return true;
		}
		if((w/vw>0.2) && (h/vh>0.2)){
			return true;
		}

		if (viewportArea <= 0)
			return false;
		showLog && console.log("vw: "+vw+" x vh: "+vh+", w:"+w+" x h:"+h);
		showLog && console.log("ah: "+w/vw+" ah: "+h/vh);
		showLog && console.log("area: "+area+" / viewportArea: "+viewportArea+" = "+area / viewportArea+ " vs "+ratio);
		return area / viewportArea >= ratio;
	}

	function looksLikeBlockerBySemantics(el) {
		const role = (el.getAttribute("role") || "").toLowerCase();
		if (role === "dialog" || role === "alertdialog") return true;

		const ariaModal = (el.getAttribute("aria-modal") || "").toLowerCase();
		if (ariaModal === "true") return true;

		const hay = [
			el.id || "",
			el.className || "",
			el.getAttribute("data-testid") || "",
			el.getAttribute("data-test") || "",
			el.getAttribute("data-cy") || "",
			el.getAttribute("data-qa") || "",
			el.getAttribute("data-name") || "",
		].join(" ").toLowerCase();

		const keywords = [
			"cookie", "consent", "gdpr", "ccpa",
			"subscribe", "newsletter", "signup", "register",
			"paywall", "meter", "wall",
			"modal", "dialog", "popup",
			"overlay", "backdrop", "lightbox",
			"interstitial", "gate", "banner"
		];

		return keywords.some(k => hay.includes(k));
	}

	function likelyBlocksInteraction(el) {
		const showLog=el.id==="cm";
		const style = window.getComputedStyle(el);
		const pos = (style.position || "").toLowerCase();
		const fixedLike = pos === "fixed" || pos === "sticky";

		const bigEnough = coversViewportEnough(el, minCoverRatio);
		showLog && console.log("Big enough: "+bigEnough);
		const z = getZIndex(el);
		
		if(!bigEnough){
			showLog && console.log("likelyBlocksInteraction false exit 1.");
			return false;
		}
		if ((fixedLike && z >= 10) || (z >= 100)){
			showLog && console.log("likelyBlocksInteraction true exit 1.");
			return true;
		}
		if (looksLikeBlockerBySemantics(el) && (fixedLike || z >= 10)){
			showLog && console.log("likelyBlocksInteraction true exit 2.");
			return true;
		}
		showLog && console.log("likelyBlocksInteraction false exit 2.");
		return false;
	}

	function interceptsClicks(el) {
		const rect = el.getBoundingClientRect();
		const vw = Math.max(document.documentElement.clientWidth, window.innerWidth || 0);
		const vh = Math.max(document.documentElement.clientHeight, window.innerHeight || 0);

		const points = [
			[rect.left + rect.width * 0.5, rect.top + rect.height * 0.5],
			[rect.left + rect.width * 0.2, rect.top + rect.height * 0.2],
			[rect.left + rect.width * 0.8, rect.top + rect.height * 0.2],
			[rect.left + rect.width * 0.2, rect.top + rect.height * 0.8],
			[rect.left + rect.width * 0.8, rect.top + rect.height * 0.8],
		];

		for (const p of points) {
			const x = Math.min(vw - 1, Math.max(0, Math.floor(p[0])));
			const y = Math.min(vh - 1, Math.max(0, Math.floor(p[1])));
			const topEl = document.elementFromPoint(x, y);
			if (!topEl) continue;
			if (topEl === el || el.contains(topEl)) return true;
		}
		return false;
	}

	const selectors = [
		'[role="dialog"]',
		'[role="alertdialog"]',
		'[aria-modal="true"]',
		'.modal, .dialog, .popup, .overlay, .backdrop, .lightbox',
		'[id*="cookie" i], [class*="cookie" i], [id*="consent" i], [class*="consent" i]',
		'[id*="subscribe" i], [class*="subscribe" i], [id*="newsletter" i], [class*="newsletter" i]',
		'[id*="paywall" i], [class*="paywall" i], [id*="interstitial" i], [class*="interstitial" i]',
		...extraSelectors,
	].join(",");

	const nodes = Array.from(document.querySelectorAll(selectors)).slice(0, maxScan);
	//console.log("Rough nodes: ",nodes);

	const vw = Math.max(document.documentElement.clientWidth, window.innerWidth || 0);
	const vh = Math.max(document.documentElement.clientHeight, window.innerHeight || 0);
	const viewportArea = Math.max(1, vw * vh);

	const candidates = [];
	for (const el of nodes) {
		//console.log("Check node: ",el);
		if (!isElementVisible(el))
			continue;
		//console.log("View node: ",el);

		const semantic = looksLikeBlockerBySemantics(el);
		const coverOk = coversViewportEnough(el, minCoverRatio);

		if(!coverOk) continue;
		// quick filter: semantic-ish OR overlay-ish
		if (!semantic && !coverOk && !likelyBlocksInteraction(el)) continue;

		// stricter: likely to block + actually on top
		if (!likelyBlocksInteraction(el) && !(semantic && getZIndex(el) >= 10)) continue;
		if (!interceptsClicks(el)) continue;

		const rect = el.getBoundingClientRect();
		const area =
			Math.max(0, Math.min(rect.right, vw) - Math.max(rect.left, 0)) *
			Math.max(0, Math.min(rect.bottom, vh) - Math.max(rect.top, 0));
		const coverRatio = area / viewportArea;

		candidates.push({
			selectorHint: (el.id ? `#${el.id}` : (el.className ? `.${String(el.className).trim().split(/\s+/)[0]}` : el.tagName)),
			coverRatio,
			zIndex: getZIndex(el),
			semantic,
			text: (el.innerText || "").trim().slice(0, 120),
		});
	}

	candidates.sort((a, b) => (b.coverRatio - a.coverRatio) || (b.zIndex - a.zIndex));

	const hasBlocker = candidates.length > 0;
	const top = candidates[0];

	return {
		hasBlocker,
		reason: hasBlocker
		? `Top blocker: cover=${(top.coverRatio * 100).toFixed(1)}% z=${top.zIndex} semantic=${top.semantic}`
		: "No visible interaction-blocking overlay detected",
		top: top || null,
		blockers: candidates,
	};
}
/*}#1JDULJF8N0StartDoc*/
//----------------------------------------------------------------------------
let CaRpa_GenBlockers=async function(session){
	let pageRef,blockers,waitAfter;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,CheckRule,LoopRules,CheckBlocker,NoBlocker,CheckRemove,ReadHtml,HasBlocker,FindSelector,DoClick,FindClick,ClickRule,CheckClicked,SaveRule,CheckUsed,LoopAgain,WaitAfter,Jump,CheckMaxClick,JumpEnd,IsAllowManual,ManualFailed,ActivePage,TipManual,WaitManue,ManualDone,JumpManualFailed,StillBlocker,JumpFin;
	let ruleClicked=false;
	let clickNum=0;
	let loopNum=0;
	let wrongSelectors=[];
	
	/*#{1JDULJF8N0LocalVals*/
	/*}#1JDULJF8N0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			blockers=input.blockers;
			waitAfter=input.waitAfter;
		}else{
			pageRef=undefined;
			blockers=undefined;
			waitAfter=undefined;
		}
		/*#{1JDULJF8N0ParseArgs*/
		/*}#1JDULJF8N0ParseArgs*/
	}
	
	/*#{1JDULJF8N0PreContext*/
	/*}#1JDULJF8N0PreContext*/
	context={
		url: "",
		hostname: "",
		rules: "",
		usedRules: [],
		/*#{1JDULJF8N5ExCtxAttrs*/
		/*}#1JDULJF8N5ExCtxAttrs*/
	};
	/*#{1JDULJF8N0PostContext*/
	/*}#1JDULJF8N0PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JDULJK530
		let result=true;
		let aiQuery=true;
		let $alias="RPAHOME";
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JDULJK530"));
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
		return {seg:CheckRule,result:(result),preSeg:"1JDULJK530",outlet:"1JDULKOI20"};
	};
	StartRpa.jaxId="1JDULJK530"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["CheckRule"]=CheckRule=async function(input){//:1JDUSTGN90
		let result=input;
		/*#{1JDUSTGN90Start*/
		let rule=await readRule(session,context.aaPage,"blockers.selectors",{query:"解决页面阻挡需要点击的HTML元素",loose:true});
		context.url=await context.aaPage.url();
		context.hostname=(() => { try { return new URL(context.url).hostname; } catch (e) { return ""; } })();
		/*}#1JDUSTGN90Start*/
		if(rule){
			let output=rule;
			return {seg:LoopRules,result:(output),preSeg:"1JDUSTGN90",outlet:"1JDUT5P5R0"};
		}
		/*#{1JDUSTGN90Post*/
		/*}#1JDUSTGN90Post*/
		return {seg:CheckBlocker,result:(result),preSeg:"1JDUSTGN90",outlet:"1JDUT5P5S0"};
	};
	CheckRule.jaxId="1JDUSTGN90"
	CheckRule.url="CheckRule@"+agentURL
	
	segs["LoopRules"]=LoopRules=async function(input){//:1JDVC2HMM0
		let result=input;
		let list=input;
		let i,n,item,loopR;
		/*#{1JDVC2HMM0PreLoop*/
		ruleClicked=false;
		loopNum+=1;
		/*}#1JDVC2HMM0PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1JDVC2HMM0InLoopPre*/
			/*}#1JDVC2HMM0InLoopPre*/
			loopR=await session.runAISeg(agent,FindClick,item,"1JDVC2HMM0","1JDVD2JJE0")
			if(loopR==="break"){
				break;
			}
			/*#{1JDVC2HMM0InLoopPost*/
			/*}#1JDVC2HMM0InLoopPost*/
		}
		/*#{1JDVC2HMM0PostCodes*/
		/*}#1JDVC2HMM0PostCodes*/
		return {seg:StillBlocker,result:(result),preSeg:"1JDVC2HMM0",outlet:"1JDVD2JJE1"};
	};
	LoopRules.jaxId="1JDVC2HMM0"
	LoopRules.url="LoopRules@"+agentURL
	
	segs["CheckBlocker"]=CheckBlocker=async function(input){//:1JDUM5BGU0
		let result=input;
		/*#{1JDUM5BGU0Start*/
		let $page,res;
		$page=context.aaPage;
		res=await $page.callFunction(detectBlockersWebDriver,[],{});
		/*}#1JDUM5BGU0Start*/
		if(res.hasBlocker){
			return {seg:CheckRemove,result:(input),preSeg:"1JDUM5BGU0",outlet:"1JDUM9GE30"};
		}
		/*#{1JDUM5BGU0Post*/
		/*}#1JDUM5BGU0Post*/
		return {seg:CheckClicked,result:(result),preSeg:"1JDUM5BGU0",outlet:"1JDUM9GE31"};
	};
	CheckBlocker.jaxId="1JDUM5BGU0"
	CheckBlocker.url="CheckBlocker@"+agentURL
	
	segs["NoBlocker"]=NoBlocker=async function(input){//:1JDUM82720
		let result=input
		try{
			/*#{1JDUM82720Code*/
			result={status:"done",value:{blocked:false,cleared:context.usedRules?.length>0},blocker:false};
			/*}#1JDUM82720Code*/
		}catch(error){
			/*#{1JDUM82720ErrorCode*/
			/*}#1JDUM82720ErrorCode*/
		}
		return {seg:WaitAfter,result:(result),preSeg:"1JDUM82720",outlet:"1JDUM9GE32"};
	};
	NoBlocker.jaxId="1JDUM82720"
	NoBlocker.url="NoBlocker@"+agentURL
	
	segs["CheckRemove"]=CheckRemove=async function(input){//:1JDUM8RH40
		let result=input;
		if(blockers && (blockers.clear||blockers.remove)){
			return {seg:ReadHtml,result:(input),preSeg:"1JDUM8RH40",outlet:"1JDUM9GE33"};
		}
		return {seg:HasBlocker,result:(result),preSeg:"1JDUM8RH40",outlet:"1JDUM9GE34"};
	};
	CheckRemove.jaxId="1JDUM8RH40"
	CheckRemove.url="CheckRemove@"+agentURL
	
	segs["ReadHtml"]=ReadHtml=async function(input){//:1JDURSUK30
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
			/*#{1JDURSUK30ErrorCode*/
			/*}#1JDURSUK30ErrorCode*/
		}
		return {seg:FindSelector,result:(result),preSeg:"1JDURSUK30",outlet:"1JDUS35OR0"};
	};
	ReadHtml.jaxId="1JDURSUK30"
	ReadHtml.url="ReadHtml@"+agentURL
	
	segs["HasBlocker"]=HasBlocker=async function(input){//:1JDURTLAI0
		let result=input
		try{
			/*#{1JDURTLAI0Code*/
			result={status:"done",value:{blocked:true},blocker:true};
			/*}#1JDURTLAI0Code*/
		}catch(error){
			/*#{1JDURTLAI0ErrorCode*/
			/*}#1JDURTLAI0ErrorCode*/
		}
		return {seg:WaitAfter,result:(result),preSeg:"1JDURTLAI0",outlet:"1JDUS35OR1"};
	};
	HasBlocker.jaxId="1JDURTLAI0"
	HasBlocker.url="HasBlocker@"+agentURL
	
	segs["FindSelector"]=FindSelector=async function(input){//:1JE7UC9690
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-5";
		let $agent;
		let result=null;
		/*#{1JE7UC9690Input*/
		let $system=buildRpaMicroDeciderPrompt(
			"给定当前页面清洗后的HTML代码，确认当前页面是否有阻挡的情况，如果是，返回解决页面阻挡需要点击的HTML元素的定位语句，或者请求人工干预。",
			`如果找到需要点击解除blocker的元素，返回"selector"动作.`+
			`如果当前页面不存在任何blocker，返回"done"动作。`+
			`如果要解除blocker，比如登录等，必须通过用户人工干预，当前页面不存在任何blocker，返回"ask_assist"动作。`+
			`存在即使人工都无法解除的blocker，返回"abort"动作`+
			wrongSelectors.length?`\n\n重要: 已知：${JSON.stringify(wrongSelectors)} 这些selector是错误无效的，不要重复给出重复的错误答案。`:"",
			["selector","ask_assist"]
		);
		/*}#1JE7UC9690Input*/
		
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
		/*#{1JE7UC9690PrePrompt*/
		/*}#1JE7UC9690PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JE7UC9690FilterMessage*/
			/*}#1JE7UC9690FilterMessage*/
			messages.push(msg);
		}
		/*#{1JE7UC9690PreCall*/
		/*}#1JE7UC9690PreCall*/
		result=FindSelector.cheats[prompt]||FindSelector.cheats[input]||(chatMem && FindSelector.cheats[""+chatMem.length])||FindSelector.cheats[""];
		if(!result){
			if($agent){
				result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
			}else{
				result=(result===undefined)?(await session.callSegLLM("FindSelector@"+agentURL,opts,messages,true)):result;
			}
		}
		result=trimJSON(result);
		/*#{1JE7UC9690PostCall*/
		/*}#1JE7UC9690PostCall*/
		if(result && result.action &&  result.action.type==="selector"){
			let output=result.action.by;
			return {seg:DoClick,result:(output),preSeg:"1JE7UC9690",outlet:"1JE7UK42T0"};
		}
		if(result && result.action &&  result.action.type==="ask_assist"){
			return {seg:IsAllowManual,result:(input),preSeg:"1JE7UC9690",outlet:"1JE7UDE1S0"};
		}
		/*#{1JE7UC9690PreResult*/
		/*}#1JE7UC9690PreResult*/
		return {seg:Jump,result:(result),preSeg:"1JE7UC9690",outlet:"1JE7UK42U0"};
	};
	FindSelector.jaxId="1JE7UC9690"
	FindSelector.url="FindSelector@"+agentURL
	FindSelector.cheats={
		"":"{ \"action\": { \"type\": \"selector\", \"by\": \"css: #CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll\" }, \"reason\": \"检测到 Cookiebot 同意对话框覆盖页面（role=dialog，display:flex）；需点击同意按钮以解除遮挡。\", \"summary\": \"Cookie 同意弹窗（Cookiebot）遮挡；返回“Allow all”按钮选择器以点击；预期关闭弹窗恢复页面可操作；风险：站点A/B可能更换按钮文案。\" }"
	};
	
	segs["DoClick"]=DoClick=async function(input){//:1JDUS0NJM0
		let result=true;
		let pageVal="aaPage";
		let $query=input;
		let $queryHint="";
		let $x=0;
		let $y=0;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=1000;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		/*#{1JDUS0NJM0PreCodes*/
		/*}#1JDUS0NJM0PreCodes*/
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JDUS0NJM0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.click($query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
			}else{
				$pms=page.mouse.click($x,$y,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JDUS0NJM0ErrorCode*/
			wrongSelectors.push($query);
			/*}#1JDUS0NJM0ErrorCode*/
			return {seg:FindSelector,result:error,preSeg:"1JDUS0NJM0",outlet:null};
		}
		/*#{1JDUS0NJM0PostCodes*/
		if(context.usedRules.indexOf($query)<0){
			context.usedRules.push($query);
		}
		/*}#1JDUS0NJM0PostCodes*/
		return {seg:CheckMaxClick,result:(result),preSeg:"1JDUS0NJM0",outlet:"1JDUS35OS1"};
	};
	DoClick.jaxId="1JDUS0NJM0"
	DoClick.url="DoClick@"+agentURL
	
	segs["FindClick"]=FindClick=async function(input){//:1JDUSV9N10
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
		/*#{1JDUSV9N10PreCodes*/
		/*}#1JDUSV9N10PreCodes*/
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			/*#{1JDUSV9N10CheckItem*/
			/*}#1JDUSV9N10CheckItem*/
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JDUSV9N10ErrorCode*/
			error=null;
			/*}#1JDUSV9N10ErrorCode*/
			return {seg:CheckBlocker,result:error,preSeg:"1JDUSV9N10",outlet:"1JDUSV9MJ0"};
		}
		/*#{1JDUSV9N10PostCodes*/
		result=$query;
		/*}#1JDUSV9N10PostCodes*/
		return {seg:ClickRule,result:(result),preSeg:"1JDUSV9N10",outlet:"1JDUT5P5S1"};
	};
	FindClick.jaxId="1JDUSV9N10"
	FindClick.url="FindClick@"+agentURL
	
	segs["ClickRule"]=ClickRule=async function(input){//:1JDUT34I10
		let result=true;
		let pageVal="aaPage";
		let $query=input;
		let $queryHint="";
		let $x=0;
		let $y=0;
		let $options=null;
		let $waitBefore=0;
		let $waitAfter=1000;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		/*#{1JDUT34I10PreCodes*/
		/*}#1JDUT34I10PreCodes*/
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JDUT34I10")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.click($query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
			}else{
				$pms=page.mouse.click($x,$y,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JDUT34I10ErrorCode*/
			wrongSelectors.push($query);
			/*}#1JDUT34I10ErrorCode*/
			return {seg:CheckBlocker,result:error,preSeg:"1JDUT34I10",outlet:null};
		}
		/*#{1JDUT34I10PostCodes*/
		ruleClicked=true;
		if(context.usedRules.indexOf($query)<0){
			context.usedRules.push($query);
		}
		//result="braek";
		/*}#1JDUT34I10PostCodes*/
		return {result:result};
	};
	ClickRule.jaxId="1JDUT34I10"
	ClickRule.url="ClickRule@"+agentURL
	
	segs["CheckClicked"]=CheckClicked=async function(input){//:1JDUU2NIQ0
		let result=input;
		if(context.usedRules.length>0){
			return {seg:SaveRule,result:(input),preSeg:"1JDUU2NIQ0",outlet:"1JDUU4QMD0"};
		}
		return {seg:NoBlocker,result:(result),preSeg:"1JDUU2NIQ0",outlet:"1JDUU4QMD1"};
	};
	CheckClicked.jaxId="1JDUU2NIQ0"
	CheckClicked.url="CheckClicked@"+agentURL
	
	segs["SaveRule"]=SaveRule=async function(input){//:1JDUU3KQR0
		let result=input
		try{
			/*#{1JDUU3KQR0Code*/
			let used,selector,idx,newRule;
			let rules=(await readRule(session,context.aaPage,"blockers.selectors",{query:"解决页面阻挡需要点击的HTML元素",loose:true}))||[];
			newRule=false;
			used=context.usedRules;
			for(selector of used){
				idx=rules.indexOf(selector);
				if(idx>=0){
					rules.splice(idx,1);
				}else{
					newRule=true;
				}
				rules.unshift(selector);
			}
			if(newRule){
				if(rules.length>10){
					rules=rules.slice(0,10);
				}
				await saveRule(session,context.aaPage,"blockers.selectors",rules,"解决页面阻挡需要点击的HTML元素");
			}
			/*}#1JDUU3KQR0Code*/
		}catch(error){
			/*#{1JDUU3KQR0ErrorCode*/
			/*}#1JDUU3KQR0ErrorCode*/
		}
		return {seg:NoBlocker,result:(result),preSeg:"1JDUU3KQR0",outlet:"1JDUU4QMD2"};
	};
	SaveRule.jaxId="1JDUU3KQR0"
	SaveRule.url="SaveRule@"+agentURL
	
	segs["CheckUsed"]=CheckUsed=async function(input){//:1JDVCV9NT0
		let result=input;
		if(ruleClicked && loopNum<5){
			return {seg:LoopAgain,result:(input),preSeg:"1JDVCV9NT0",outlet:"1JDVD2JJE2"};
		}
		return {seg:CheckBlocker,result:(result),preSeg:"1JDVCV9NT0",outlet:"1JDVD2JJE3"};
	};
	CheckUsed.jaxId="1JDVCV9NT0"
	CheckUsed.url="CheckUsed@"+agentURL
	
	segs["LoopAgain"]=LoopAgain=async function(input){//:1JDVD24AF0
		let result=input;
		return {seg:LoopRules,result:result,preSeg:"1JDVC2HMM0",outlet:"1JDVD2JJE4"};
	
	};
	LoopAgain.jaxId="1JDVC2HMM0"
	LoopAgain.url="LoopAgain@"+agentURL
	
	segs["WaitAfter"]=WaitAfter=async function(input){//:1JDVJF8VJ0
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
	WaitAfter.jaxId="1JDVJF8VJ0"
	WaitAfter.url="WaitAfter@"+agentURL
	
	segs["Jump"]=Jump=async function(input){//:1JDVO27B80
		let result=input;
		return {seg:CheckClicked,result:result,preSeg:"1JDUU2NIQ0",outlet:"1JDVO3RJQ2"};
	
	};
	Jump.jaxId="1JDUU2NIQ0"
	Jump.url="Jump@"+agentURL
	
	segs["CheckMaxClick"]=CheckMaxClick=async function(input){//:1JE00IIE40
		let result=input;
		/*#{1JE00IIE40Start*/
		clickNum+=1;
		/*}#1JE00IIE40Start*/
		if(clickNum<5){
			return {seg:CheckBlocker,result:(input),preSeg:"1JE00IIE40",outlet:"1JE00JQ1B0"};
		}
		/*#{1JE00IIE40Post*/
		result={status:"failed",value:{blocked:true},blocker:true,reason:"Max retry."};
		/*}#1JE00IIE40Post*/
		return {seg:JumpEnd,result:(result),preSeg:"1JE00IIE40",outlet:"1JE00JQ1B1"};
	};
	CheckMaxClick.jaxId="1JE00IIE40"
	CheckMaxClick.url="CheckMaxClick@"+agentURL
	
	segs["JumpEnd"]=JumpEnd=async function(input){//:1JE00N9I10
		let result=input;
		return {seg:HasBlocker,result:result,preSeg:"1JDURTLAI0",outlet:"1JE00NN200"};
	
	};
	JumpEnd.jaxId="1JDURTLAI0"
	JumpEnd.url="JumpEnd@"+agentURL
	
	segs["IsAllowManual"]=IsAllowManual=async function(input){//:1JE6O9B1L0
		let result=input;
		if(input==="Allow"){
			return {seg:ActivePage,result:(input),preSeg:"1JE6O9B1L0",outlet:"1JE6OFCLT0"};
		}
		return {seg:ManualFailed,result:(result),preSeg:"1JE6O9B1L0",outlet:"1JE6OFCLT1"};
	};
	IsAllowManual.jaxId="1JE6O9B1L0"
	IsAllowManual.url="IsAllowManual@"+agentURL
	
	segs["ManualFailed"]=ManualFailed=async function(input){//:1JE6OC1HK0
		let result=input
		try{
			/*#{1JE6OC1HK0Code*/
			result={status:"failed",value:{blocked:true},reason:"Can't clear blockers with user assistant.",blocked:true};
			/*}#1JE6OC1HK0Code*/
		}catch(error){
			/*#{1JE6OC1HK0ErrorCode*/
			/*}#1JE6OC1HK0ErrorCode*/
		}
		return {result:result};
	};
	ManualFailed.jaxId="1JE6OC1HK0"
	ManualFailed.url="ManualFailed@"+agentURL
	
	segs["ActivePage"]=ActivePage=async function(input){//:1JE6OD4GJ0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let $options=null;
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
			/*#{1JE6OD4GJ0ErrorCode*/
			/*}#1JE6OD4GJ0ErrorCode*/
		}
		return {seg:TipManual,result:(result),preSeg:"1JE6OD4GJ0",outlet:"1JE6OFCLT3"};
	};
	ActivePage.jaxId="1JE6OD4GJ0"
	ActivePage.url="ActivePage@"+agentURL
	
	segs["TipManual"]=TipManual=async function(input){//:1JE6ODH6T0
		let result=input
		try{
			/*#{1JE6ODH6T0Code*/
			/*}#1JE6ODH6T0Code*/
		}catch(error){
			/*#{1JE6ODH6T0ErrorCode*/
			/*}#1JE6ODH6T0ErrorCode*/
		}
		return {seg:WaitManue,result:(result),preSeg:"1JE6ODH6T0",outlet:"1JE6OFCLT4"};
	};
	TipManual.jaxId="1JE6ODH6T0"
	TipManual.url="TipManual@"+agentURL
	
	segs["WaitManue"]=WaitManue=async function(input){//:1JE6OEL380
		let prompt=("Please confirm")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Item 1",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Item 2",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:ManualDone,result:(result),preSeg:"1JE6OEL380",outlet:"1JE6OEL2L0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:ManualDone,result:(result),preSeg:"1JE6OEL380",outlet:"1JE6OEL2L0"};
		}else if(item.code===1){
			return {seg:JumpManualFailed,result:(result),preSeg:"1JE6OEL380",outlet:"1JE6OEL2L1"};
		}
		return {result:result};
	};
	WaitManue.jaxId="1JE6OEL380"
	WaitManue.url="WaitManue@"+agentURL
	
	segs["ManualDone"]=ManualDone=async function(input){//:1JE6OILT50
		let result=input;
		return {seg:CheckClicked,result:result,preSeg:"1JDUU2NIQ0",outlet:"1JE6OJA0E0"};
	
	};
	ManualDone.jaxId="1JDUU2NIQ0"
	ManualDone.url="ManualDone@"+agentURL
	
	segs["JumpManualFailed"]=JumpManualFailed=async function(input){//:1JE6OK52M0
		let result=input;
		return {seg:ManualFailed,result:result,preSeg:"1JE6OC1HK0",outlet:"1JE6OL0DC0"};
	
	};
	JumpManualFailed.jaxId="1JE6OC1HK0"
	JumpManualFailed.url="JumpManualFailed@"+agentURL
	
	segs["StillBlocker"]=StillBlocker=async function(input){//:1JE81T9Q80
		let result=input;
		/*#{1JE81T9Q80Start*/
		let $page,res;
		$page=context.aaPage;
		res=await $page.callFunction(detectBlockersWebDriver,[],{});
		/*}#1JE81T9Q80Start*/
		if(!res.hasBlocker){
			return {seg:JumpFin,result:(input),preSeg:"1JE81T9Q80",outlet:"1JE81UJ110"};
		}
		/*#{1JE81T9Q80Post*/
		/*}#1JE81T9Q80Post*/
		return {seg:CheckUsed,result:(result),preSeg:"1JE81T9Q80",outlet:"1JE81UJ111"};
	};
	StillBlocker.jaxId="1JE81T9Q80"
	StillBlocker.url="StillBlocker@"+agentURL
	
	segs["JumpFin"]=JumpFin=async function(input){//:1JG235CSJ0
		let result=input;
		return {seg:CheckClicked,result:result,preSeg:"1JDUU2NIQ0",outlet:"1JG236L620"};
	
	};
	JumpFin.jaxId="1JDUU2NIQ0"
	JumpFin.url="JumpFin@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CaRpa_GenBlockers",
		url:agentURL,
		autoStart:true,
		jaxId:"1JDULJF8N0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,blockers,waitAfter}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JDULJF8N0PreEntry*/
			/*}#1JDULJF8N0PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JDULJF8N0PostEntry*/
			/*}#1JDULJF8N0PostEntry*/
			return result;
		},
		/*#{1JDULJF8N0MoreAgentAttrs*/
		/*}#1JDULJF8N0MoreAgentAttrs*/
	};
	/*#{1JDULJF8N0PostAgent*/
	/*}#1JDULJF8N0PostAgent*/
	return agent;
};
/*#{1JDULJF8N0ExCodes*/
/*}#1JDULJF8N0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CaRpa_GenBlockers",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				blockers:{type:"auto",description:""},
				waitAfter:{type:"integer",description:""}
			}
		}
	},
	agentNode: "genrpa",
	agentName: "CaRpa_GenBlockers.js",
	isChatApi: true,
	kind: "rpa",
	capabilities: ["blockers.check","blockers.clear"],
	filters: [{"key":"domain","value":"*"}],
	metrics: {"quality":6.5,"costPerCall":0.05,"costPer1M":"","speed":6,"size":0}
}];
//#CodyExport<<<
/*#{1JDULJF8N0PostDoc*/
/*}#1JDULJF8N0PostDoc*/


export default CaRpa_GenBlockers;
export{CaRpa_GenBlockers,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JDULJF8N0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JDULJF8N1",
//			"attrs": {
//				"CaRpa_GenBlockers": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JDULJF8N7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JDULJF8N8",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JDULJF8N9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JDULJF8N10",
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
//			"jaxId": "1JDULJF8N2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JDULJF8N3",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDULKOI21",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"blockers": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDULKOI22",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"waitAfter": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDVJ4B5G0",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JDULJF8N4",
//			"attrs": {
//				"ruleClicked": {
//					"type": "bool",
//					"valText": "false"
//				},
//				"clickNum": {
//					"type": "int",
//					"valText": "0"
//				},
//				"loopNum": {
//					"type": "int",
//					"valText": "0"
//				},
//				"wrongSelectors": {
//					"type": "auto",
//					"valText": "#[]"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1JDULJF8N5",
//			"attrs": {
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDUUD9BB0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"hostname": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDUU7F6U0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"rules": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDUVK1HM0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"usedRules": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDUU7F6U1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1JDULJF8N6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JDULJK530",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "90",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDULKOI23",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDULKOI24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"browser": "RPAHOME",
//						"headless": "false",
//						"devtools": "false",
//						"url": "",
//						"valName": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JDULKOI20",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDUSTGN90"
//						},
//						"catchlet": {
//							"jaxId": "1JDULKOI25",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JDULKOI26",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JDULKOI27",
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
//					"jaxId": "1JDUSTGN90",
//					"attrs": {
//						"id": "CheckRule",
//						"viewName": "",
//						"label": "",
//						"x": "350",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUT5P620",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUT5P621",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDUT5P5S0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JDUM5BGU0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JDUT5P5R0",
//									"attrs": {
//										"id": "Rule",
//										"desc": "输出节点。",
//										"output": "#rule",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JDUT5P622",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JDUT5P623",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#rule"
//									},
//									"linkedSeg": "1JDVC2HMM0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1JDVC2HMM0",
//					"attrs": {
//						"id": "LoopRules",
//						"viewName": "",
//						"label": "",
//						"x": "605",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDVD2JJJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDVD2JJJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1JDVD2JJE0",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDUSV9N10"
//						},
//						"catchlet": {
//							"jaxId": "1JDVD2JJE1",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE81T9Q80"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JDUM5BGU0",
//					"attrs": {
//						"id": "CheckBlocker",
//						"viewName": "",
//						"label": "",
//						"x": "605",
//						"y": "680",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUM9GE50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUM9GE51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDUM9GE31",
//							"attrs": {
//								"id": "Free",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JDUU2NIQ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JDUM9GE30",
//									"attrs": {
//										"id": "Blocker",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JDUM9GE52",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JDUM9GE53",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#res.hasBlocker"
//									},
//									"linkedSeg": "1JDUM8RH40"
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
//					"jaxId": "1JDUM82720",
//					"attrs": {
//						"id": "NoBlocker",
//						"viewName": "",
//						"label": "",
//						"x": "1380",
//						"y": "1015",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUM9GE54",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUM9GE55",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDUM9GE32",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDVJF8VJ0"
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
//					"jaxId": "1JDUM8RH40",
//					"attrs": {
//						"id": "CheckRemove",
//						"viewName": "",
//						"label": "",
//						"x": "865",
//						"y": "665",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUM9GE56",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUM9GE57",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDUM9GE34",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JDURTLAI0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JDUM9GE33",
//									"attrs": {
//										"id": "Remove",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JDUM9GE58",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JDUM9GE59",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#blockers && (blockers.clear||blockers.remove)"
//									},
//									"linkedSeg": "1JDURSUK30"
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
//					"jaxId": "1JDURSUK30",
//					"attrs": {
//						"id": "ReadHtml",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "650",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUS35P00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUS35P01",
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
//							"jaxId": "1JDUS35OR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE7UC9690"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JDURTLAI0",
//					"attrs": {
//						"id": "HasBlocker",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "840",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUS35P02",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUS35P03",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDUS35OR1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDVJF8VJ0"
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
//					"jaxId": "1JE7UC9690",
//					"attrs": {
//						"id": "FindSelector",
//						"viewName": "",
//						"label": "",
//						"x": "1380",
//						"y": "650",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "lab.svg",
//						"context": {
//							"jaxId": "1JE7UK4340",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE7UK4341",
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
//							"jaxId": "1JE7UK42U0",
//							"attrs": {
//								"id": "NoBlocker",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDVO27B80"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "true",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1JEANV1040",
//									"attrs": {
//										"reply": "{ \"action\": { \"type\": \"selector\", \"by\": \"css: #CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll\" }, \"reason\": \"检测到 Cookiebot 同意对话框覆盖页面（role=dialog，display:flex）；需点击同意按钮以解除遮挡。\", \"summary\": \"Cookie 同意弹窗（Cookiebot）遮挡；返回“Allow all”按钮选择器以点击；预期关闭弹窗恢复页面可操作；风险：站点A/B可能更换按钮文案。\" }",
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
//									"jaxId": "1JE7UK42T0",
//									"attrs": {
//										"id": "Selector",
//										"desc": "输出节点。",
//										"output": "#result.action.by",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE7UK4342",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE7UK4343",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action &&  result.action.type===\"selector\""
//									},
//									"linkedSeg": "1JDUS0NJM0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE7UDE1S0",
//									"attrs": {
//										"id": "Manual",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE7UK4344",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE7UK4345",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result && result.action &&  result.action.type===\"ask_assist\""
//									},
//									"linkedSeg": "1JE6O9B1L0"
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
//					"jaxId": "1JDUS0NJM0",
//					"attrs": {
//						"id": "DoClick",
//						"viewName": "",
//						"label": "",
//						"x": "1645",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUS35P06",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUS35P07",
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
//						"waitAfter": "1000",
//						"outlet": {
//							"jaxId": "1JDUS35OS1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE00IIE40"
//						},
//						"errorSeg": "1JE7UC9690",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JDUS26T30",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2100",
//						"y": "460",
//						"outlet": {
//							"jaxId": "1JDUS35P08",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE8216KD0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JDUS2CUT0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "640",
//						"y": "555",
//						"outlet": {
//							"jaxId": "1JDUS35P09",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDUM5BGU0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1JDUSV9N10",
//					"attrs": {
//						"id": "FindClick",
//						"viewName": "",
//						"label": "",
//						"x": "865",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUT5P624",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUT5P625",
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
//							"jaxId": "1JDUT5P5S1",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDUT34I10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JDUSV9MJ0",
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
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JDUT34I10",
//					"attrs": {
//						"id": "ClickRule",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUT5P627",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUT5P628",
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
//						"waitAfter": "1000",
//						"outlet": {
//							"jaxId": "1JDUT5P5S2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"errorSeg": "1JDUM5BGU0",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JDUT3KBD0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1130",
//						"y": "555",
//						"outlet": {
//							"jaxId": "1JDUT5P629",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDUS2CUT0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JDUU2NIQ0",
//					"attrs": {
//						"id": "CheckClicked",
//						"viewName": "",
//						"label": "",
//						"x": "865",
//						"y": "1000",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUU4QMK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUU4QMK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDUU4QMD1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JDUM82720"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JDUU4QMD0",
//									"attrs": {
//										"id": "Clicked",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JDUU4QMK2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JDUU4QMK3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#context.usedRules.length>0"
//									},
//									"linkedSeg": "1JDUU3KQR0"
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
//					"jaxId": "1JDUU3KQR0",
//					"attrs": {
//						"id": "SaveRule",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "945",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "check_fat.svg",
//						"context": {
//							"jaxId": "1JDUU4QMK4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUU4QMK5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDUU4QMD2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDUM82720"
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
//					"jaxId": "1JDVCV9NT0",
//					"attrs": {
//						"id": "CheckUsed",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "360",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDVD2JJJ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDVD2JJJ3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JDVD2JJE3",
//							"attrs": {
//								"id": "Clean",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE8216KD0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JDVD2JJE2",
//									"attrs": {
//										"id": "Clicked",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JDVD2JJJ4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JDVD2JJJ5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#ruleClicked && loopNum<5"
//									},
//									"linkedSeg": "1JDVD24AF0"
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
//					"jaxId": "1JDVD24AF0",
//					"attrs": {
//						"id": "LoopAgain",
//						"viewName": "",
//						"label": "",
//						"x": "1400",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JDVC2HMM0",
//						"outlet": {
//							"jaxId": "1JDVD2JJE4",
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
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JDVJF8VJ0",
//					"attrs": {
//						"id": "WaitAfter",
//						"viewName": "",
//						"label": "",
//						"x": "1645",
//						"y": "840",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JDVJFGNR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDVJFGNR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "",
//						"waitBefore": "0",
//						"waitAfter": "#waitAfter",
//						"outlet": {
//							"jaxId": "1JDVJFGNL1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"catchlet": {
//							"jaxId": "1JDVJFGNL0",
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
//					"def": "jumper",
//					"jaxId": "1JDVO27B80",
//					"attrs": {
//						"id": "Jump",
//						"viewName": "",
//						"label": "",
//						"x": "1645",
//						"y": "745",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JDUU2NIQ0",
//						"outlet": {
//							"jaxId": "1JDVO3RJQ2",
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
//					"jaxId": "1JE00IIE40",
//					"attrs": {
//						"id": "CheckMaxClick",
//						"viewName": "",
//						"label": "",
//						"x": "1900",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE00K0N30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE00K0N31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE00JQ1B1",
//							"attrs": {
//								"id": "MaxClicked",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE00N9I10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE00JQ1B0",
//									"attrs": {
//										"id": "Check",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE00K0N32",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE00K0N33",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#clickNum<5"
//									},
//									"linkedSeg": "1JDUS26T30"
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
//					"jaxId": "1JE00N9I10",
//					"attrs": {
//						"id": "JumpEnd",
//						"viewName": "",
//						"label": "",
//						"x": "2190",
//						"y": "555",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JDURTLAI0",
//						"outlet": {
//							"jaxId": "1JE00NN200",
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
//					"jaxId": "1JE6O9B1L0",
//					"attrs": {
//						"id": "IsAllowManual",
//						"viewName": "",
//						"label": "",
//						"x": "1645",
//						"y": "650",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE6OFCM60",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE6OFCM61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE6OFCLT1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE6OC1HK0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE6OFCLT0",
//									"attrs": {
//										"id": "Allow",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE6OFCM62",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE6OFCM63",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1JE6OD4GJ0"
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
//					"jaxId": "1JE6OC1HK0",
//					"attrs": {
//						"id": "ManualFailed",
//						"viewName": "",
//						"label": "",
//						"x": "1900",
//						"y": "760",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JE6OFCM64",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE6OFCM65",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE6OFCLT2",
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
//					"def": "WebRpaActivePage",
//					"jaxId": "1JE6OD4GJ0",
//					"attrs": {
//						"id": "ActivePage",
//						"viewName": "",
//						"label": "",
//						"x": "1900",
//						"y": "635",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE6OFCM66",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE6OFCM67",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE6OFCLT3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE6ODH6T0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JE6ODH6T0",
//					"attrs": {
//						"id": "TipManual",
//						"viewName": "",
//						"label": "",
//						"x": "2190",
//						"y": "635",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1JE6OFCM68",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE6OFCM69",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE6OFCLT4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE6OEL380"
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
//					"def": "askMenu",
//					"jaxId": "1JE6OEL380",
//					"attrs": {
//						"id": "WaitManue",
//						"viewName": "",
//						"label": "",
//						"x": "2445",
//						"y": "635",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"prompt": "Please confirm",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1JE6OFCLT5",
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
//									"jaxId": "1JE6OEL2L0",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"text": "Item 1",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE6OFCM610",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE6OFCM611",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JE6OILT50"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JE6OEL2L1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "Item 2",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE6OFCM612",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE6OFCM613",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JE6OK52M0"
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
//					"jaxId": "1JE6OILT50",
//					"attrs": {
//						"id": "ManualDone",
//						"viewName": "",
//						"label": "",
//						"x": "2700",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JDUU2NIQ0",
//						"outlet": {
//							"jaxId": "1JE6OJA0E0",
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
//					"jaxId": "1JE6OK52M0",
//					"attrs": {
//						"id": "JumpManualFailed",
//						"viewName": "",
//						"label": "",
//						"x": "2700",
//						"y": "695",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JE6OC1HK0",
//						"outlet": {
//							"jaxId": "1JE6OL0DC0",
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
//					"jaxId": "1JE81T9Q80",
//					"attrs": {
//						"id": "StillBlocker",
//						"viewName": "",
//						"label": "",
//						"x": "865",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE81UJ180",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE81UJ181",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE81UJ111",
//							"attrs": {
//								"id": "Blocker",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JDVCV9NT0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE81UJ110",
//									"attrs": {
//										"id": "Free",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE81UJ182",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE81UJ183",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!res.hasBlocker"
//									},
//									"linkedSeg": "1JG235CSJ0"
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
//					"jaxId": "1JE8216KD0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1280",
//						"y": "460",
//						"outlet": {
//							"jaxId": "1JE821O130",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDUT3KBD0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JG235CSJ0",
//					"attrs": {
//						"id": "JumpFin",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "260",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JDUU2NIQ0",
//						"outlet": {
//							"jaxId": "1JG236L620",
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
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"genrpa\",\"chatEntry\":false,\"isChatApi\":1,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\",\"kind\":\"rpa\",\"capabilities\":[\"blockers.check\",\"blockers.clear\"],\"filters\":[{\"key\":\"domain\",\"value\":\"*\"}],\"metrics\":{\"quality\":6.5,\"costPerCall\":0.05,\"costPer1M\":\"\",\"speed\":6,\"size\":0},\"meta\":\"\"}"
//	}
//}