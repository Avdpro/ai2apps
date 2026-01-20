//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1JDUKACEC0MoreImports*/
import {readFileAsDataURL,ai2appsPrompt} from "./utils.js";
/*}#1JDUKACEC0MoreImports*/
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
			"defaultValue":"",
			"desc":"",
		},
		"login":{
			"name":"login","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"timeout":{
			"name":"timeout","type":"integer",
			"defaultValue":0,
			"desc":"",
		}
	},
	/*#{1JDUKACEC0ArgsView*/
	/*}#1JDUKACEC0ArgsView*/
};

/*#{1JDUKACEC0StartDoc*/
/**
* 判断当前页面是否“已登录”
* 返回：
*   - "no_login"：页面上没有可用的登录入口（当前状态下不可见/不可点击的不算）如果opts里带有onLogin属性，返回这个属性的值
*   - false     ：未登录，且存在可用的登录入口
*   - true      ：已登录（强信号：存在可用的“退出/登出”入口）
*
* 说明：
* - “可用”= 现在屏幕上可见 + 有尺寸 + 未被遮挡 + 不被禁用/不可点击（pointer-events 等）
* - 默认要求元素在视口内（因为你强调“不可见/不可点击”的不算）
*/
function detectLoginState(opt = {}) {
	const cfg = {
		allowOffscreen: false, // true: 允许视口外但可见(display!=none)的元素也算“可用”
		debug: false,
		...opt,
	};

	const KW = {
		// 登录入口（未登录时常见）
		login: [
			"login", "log in", "sign in", "signin",
			"登录", "登錄", "登入",
			"เข้าสู่ระบบ", "ล็อกอิน",
		],
		signup: [
			"sign up", "signup", "register", "create account", "join",
			"注册", "註冊", "注册账号", "註冊帳號",
			"สมัครสมาชิก", "ลงทะเบียน",
		],
		// 已登录强信号（优先级最高）
		logout: [
			"logout", "log out", "sign out", "signout",
			"退出", "登出", "注销", "登出帳號",
			"ออกจากระบบ",
		],
		// 弱信号：账号/个人中心（可能“未登录也显示”，所以不作为 true 的充分条件）
		account: [
			"account", "my account", "profile", "me", "dashboard", "settings", "orders",
			"账户", "帳戶", "账号", "個人中心", "我的", "个人资料", "个人主页", "设置", "订单",
			"บัญชี", "โปรไฟล์", "การตั้งค่า", "คำสั่งซื้อ",
		],
	};

	const normalize = (s) =>
	String(s || "")
	.replace(/\s+/g, " ")
	.trim()
	.toLowerCase();

	const hasAnyKw = (hay, kws) => {
		const h = normalize(hay);
		if (!h) return false;
		return kws.some((k) => h.includes(normalize(k)));
	};

	const getElTextPack = (el) => {
		// 尽量把可用于判断的文本都揉在一起（文本/可访问性属性/URL/类名）
		const parts = [];
		const push = (x) => {
			x = String(x || "").trim();
			if (x) parts.push(x);
		};

		push(el.innerText);
		push(el.textContent);

		// 常见可访问性/提示
		push(el.getAttribute("aria-label"));
		push(el.getAttribute("aria-labelledby"));
		push(el.getAttribute("title"));
		push(el.getAttribute("alt"));

		// href/action/on* 之类
		if (el.tagName === "A") push(el.getAttribute("href"));
		if (el.tagName === "FORM") push(el.getAttribute("action"));

		// 结构信息（弱一些，但能捞到“btn-login”之类）
		push(el.id);
		push(el.className);

		return normalize(parts.join(" | "));
	};

	const isInViewport = (rect) => {
		const vw = window.innerWidth || document.documentElement.clientWidth || 0;
		const vh = window.innerHeight || document.documentElement.clientHeight || 0;
		return rect.bottom > 0 && rect.right > 0 && rect.top < vh && rect.left < vw;
	};

	const isStyleVisible = (el) => {
		const cs = window.getComputedStyle(el);
		if (!cs) return false;
		if (cs.display === "none") return false;
		if (cs.visibility === "hidden" || cs.visibility === "collapse") return false;
		if (Number(cs.opacity) === 0) return false;
		return true;
	};

	const isDisabled = (el) => {
		if (el.hasAttribute("disabled")) return true;
		if (el.getAttribute("aria-disabled") === "true") return true;
		// fieldset disabled 会影响子元素
		const fs = el.closest("fieldset");
		if (fs && fs.disabled) return true;
		return false;
	};

	const isClickableByStyle = (el) => {
		const cs = window.getComputedStyle(el);
		if (!cs) return false;
		if (cs.pointerEvents === "none") return false;
		return true;
	};

	const isOccludedAtCenter = (el, rect) => {
		// 用中心点判断是否被遮挡（非常常见：遮罩层、sticky header 等）
		const cx = rect.left + rect.width / 2;
		const cy = rect.top + rect.height / 2;

		// 点在视口外就无法用 elementFromPoint 判断
		const vw = window.innerWidth || document.documentElement.clientWidth || 0;
		const vh = window.innerHeight || document.documentElement.clientHeight || 0;
		if (cx < 0 || cy < 0 || cx > vw || cy > vh) return true;

		const top = document.elementFromPoint(cx, cy);
		if (!top) return true;
		return !(top === el || el.contains(top) || top.contains(el));
	};

	const isVisibleClickable = (el) => {
		if (!el || el.nodeType !== 1) return false;
		if (el.hidden) return false;
		if (el.getAttribute("aria-hidden") === "true") return false;
		if (!isStyleVisible(el)) return false;
		if (isDisabled(el)) return false;
		if (!isClickableByStyle(el)) return false;

		const rect = el.getBoundingClientRect();
		if (!(rect.width >= 2 && rect.height >= 2)) return false;

		if (!cfg.allowOffscreen && !isInViewport(rect)) return false;

		// input[type=hidden] 直接排除
		if (el.tagName === "INPUT" && String(el.type || "").toLowerCase() === "hidden") return false;

		// 遮挡判定
		if (isOccludedAtCenter(el, rect)) return false;

		return true;
	};

	const isPotentialLoginForm = () => {
		// 若页面上有“可见的密码框”，通常是登录/注册页：视为“有登录入口”
		const pw = Array.from(document.querySelectorAll('input[type="password"]'))
		.filter((el) => isStyleVisible(el) && (cfg.allowOffscreen || isInViewport(el.getBoundingClientRect())));
		if (pw.length) return true;

		// 某些站用单字段 magic link / OTP，但这很难可靠判断；先不扩大误判面
		return false;
	};

	// 1) 收集“候选可点击元素”
	const selector =
		'a,button,summary,[role="button"],input[type="button"],input[type="submit"],input[type="image"],[onclick],[data-action],[data-testid]';
	const raw = Array.from(document.querySelectorAll(selector));

	const clickables = raw.filter(isVisibleClickable);

	// 2) 先找“已登录强信号”：退出/登出
	const logoutHits = [];
	for (const el of clickables) {
		const pack = getElTextPack(el);
		if (hasAnyKw(pack, KW.logout)) logoutHits.push({ el, pack });
	}
	if (logoutHits.length) {
		if (cfg.debug) console.debug("[detectLoginState] logoutHits:", logoutHits);
		console.log("[detectLoginState] exit 1");
		return true;
	}

	// 3) 再找“未登录入口”：登录/注册（只要有一个可用入口，就返回 false）
	const loginHits = [];
	for (const el of clickables) {
		const pack = getElTextPack(el);
		const hit = hasAnyKw(pack, KW.login) || hasAnyKw(pack, KW.signup);
		if (hit) loginHits.push({ el, pack });
	}

	// 额外：URL 里带 login/signin 的链接（即使按钮文案是图标）
	if (!loginHits.length) {
		for (const el of clickables) {
			if (el.tagName !== "A") continue;
			const href = normalize(el.getAttribute("href") || "");
			if (!href) continue;
			if (
				href.includes("login") ||
				href.includes("signin") ||
				href.includes("sign-in") ||
				href.includes("auth") ||
				href.includes("account/login") ||
				href.includes("เข้าสู่ระบบ")
			) {
				loginHits.push({ el, pack: href });
			}
		}
	}

	if (loginHits.length || isPotentialLoginForm()) {
		if (cfg.debug) console.debug("[detectLoginState] loginHits:", loginHits);
		console.log("[detectLoginState] exit 2");
		return false;
	}

	// 4) 没有“退出”，也没有“登录入口”，那就是 no_login
	// （账号/个人中心之类弱信号不作为已登录判断，否则容易把“点击Account跳转登录”的站误判为 true）
	console.log("[detectLoginState] exit 3");
	if("noLogin" in cfg){
		return cfg.noLogin;
	}else{
		return "no_login";
	}
}
/*}#1JDUKACEC0StartDoc*/
//----------------------------------------------------------------------------
let CaRpa_GenCheckLogin=async function(session){
	let pageRef,profile,url,waitAfter,login,timeout;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartRpa,CheckLogin,FinLogined,CheckInteractive,WaitAfter,FinNotLogined,FocusPage,WaitLogin,TipLogin,AwaitLogin,JumpError,JumpLogined,JumAbort,GoBack,WaitNetwork,CheckAgain,JumpWait,AbortBack,GoBack2,AskDone,JumpAbort;
	/*#{1JDUKACEC0LocalVals*/
	/*}#1JDUKACEC0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			pageRef=input.pageRef;
			profile=input.profile;
			url=input.url;
			waitAfter=input.waitAfter;
			login=input.login;
			timeout=input.timeout;
		}else{
			pageRef=undefined;
			profile=undefined;
			url=undefined;
			waitAfter=undefined;
			login=undefined;
			timeout=undefined;
		}
		/*#{1JDUKACEC0ParseArgs*/
		/*}#1JDUKACEC0ParseArgs*/
	}
	
	/*#{1JDUKACEC0PreContext*/
	/*}#1JDUKACEC0PreContext*/
	context={};
	/*#{1JDUKACEC0PostContext*/
	/*}#1JDUKACEC0PostContext*/
	let $agent,agent,segs={};
	segs["StartRpa"]=StartRpa=async function(input){//:1JDUKHIQS0
		let result=true;
		let aiQuery=true;
		let $alias=profile;
		let $url=url;
		let $ref=pageRef;
		let $waitBefore=0;
		let $waitAfter=pageRef?0:1000;
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
				aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1JDUKHIQS0"));
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
		return {seg:CheckLogin,result:(result),preSeg:"1JDUKHIQS0",outlet:"1JDUKICMI0"};
	};
	StartRpa.jaxId="1JDUKHIQS0"
	StartRpa.url="StartRpa@"+agentURL
	
	segs["CheckLogin"]=CheckLogin=async function(input){//:1JE2L00OE0
		let result=input;
		/*#{1JE2L00OE0Start*/
		let $page,res;
		$page=context.aaPage;
		res=await $page.callFunction(detectLoginState,[{allowOffscreen:true}],{});
		/*}#1JE2L00OE0Start*/
		if(!!res){
			return {seg:FinLogined,result:(input),preSeg:"1JE2L00OE0",outlet:"1JE2L6I0M0"};
		}
		/*#{1JE2L00OE0Post*/
		/*}#1JE2L00OE0Post*/
		return {seg:CheckInteractive,result:(result),preSeg:"1JE2L00OE0",outlet:"1JE2L6I0M1"};
	};
	CheckLogin.jaxId="1JE2L00OE0"
	CheckLogin.url="CheckLogin@"+agentURL
	
	segs["FinLogined"]=FinLogined=async function(input){//:1JE2LARPL0
		let result=input
		try{
			/*#{1JE2LARPL0Code*/
			result={status:"Done",result:"Finish",login:true};
			/*}#1JE2LARPL0Code*/
		}catch(error){
			/*#{1JE2LARPL0ErrorCode*/
			/*}#1JE2LARPL0ErrorCode*/
		}
		return {seg:WaitAfter,result:(result),preSeg:"1JE2LARPL0",outlet:"1JE2LEDV90"};
	};
	FinLogined.jaxId="1JE2LARPL0"
	FinLogined.url="FinLogined@"+agentURL
	
	segs["CheckInteractive"]=CheckInteractive=async function(input){//:1JE2LB7FT0
		let result=input;
		if(!login || !login.ensure){
			return {seg:FinNotLogined,result:(input),preSeg:"1JE2LB7FT0",outlet:"1JE2LEDV91"};
		}
		return {seg:FocusPage,result:(result),preSeg:"1JE2LB7FT0",outlet:"1JE2LEDV92"};
	};
	CheckInteractive.jaxId="1JE2LB7FT0"
	CheckInteractive.url="CheckInteractive@"+agentURL
	
	segs["WaitAfter"]=WaitAfter=async function(input){//:1JDVK00GO0
		let result=true;
		let pageVal="aaPage";
		let $flag="";
		let $waitBefore=0;
		let $waitAfter=waitAfter;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1JDVK00GO0PreCodes*/
		/*}#1JDVK00GO0PreCodes*/
		try{
			result=$flag?(await context[$flag]):input;
		}catch(error){
			return {result:error};
		}
		$waitAfter && (await sleep($waitAfter))
		/*#{1JDVK00GO0PostCodes*/
		/*}#1JDVK00GO0PostCodes*/
		return {result:result};
	};
	WaitAfter.jaxId="1JDVK00GO0"
	WaitAfter.url="WaitAfter@"+agentURL
	
	segs["FinNotLogined"]=FinNotLogined=async function(input){//:1JE2M9T0I0
		let result=input
		try{
			/*#{1JE2M9T0I0Code*/
			result={status:"Failed",result:"Failed",login:false};
			/*}#1JE2M9T0I0Code*/
		}catch(error){
			/*#{1JE2M9T0I0ErrorCode*/
			/*}#1JE2M9T0I0ErrorCode*/
		}
		return {seg:WaitAfter,result:(result),preSeg:"1JE2M9T0I0",outlet:"1JE2MAEMU0"};
	};
	FinNotLogined.jaxId="1JE2M9T0I0"
	FinNotLogined.url="FinNotLogined@"+agentURL
	
	segs["FocusPage"]=FocusPage=async function(input){//:1JE2T7OBA0
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
			/*#{1JE2T7OBA0ErrorCode*/
			/*}#1JE2T7OBA0ErrorCode*/
		}
		return {seg:TipLogin,result:(result),preSeg:"1JE2T7OBA0",outlet:"1JE2TAD820"};
	};
	FocusPage.jaxId="1JE2T7OBA0"
	FocusPage.url="FocusPage@"+agentURL
	
	segs["WaitLogin"]=WaitLogin=async function(input){//:1JE2TH24J0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $query=detectLoginState;
		let $queryHint="";
		let $waitBefore=1000;
		let $waitAfter=0;
		let $options={};
		let $timeout=timeout;
		let page=context[pageVal];
		let $args=[];
		
		if($timeout){$options.timeout=$timeout;}
		$waitBefore && (await sleep($waitBefore));
		/*#{1JE2TH24J0PreCodes*/
		$args=[{noLogin:true,debug:true}];
		/*}#1JE2TH24J0PreCodes*/
		context[$flag]=page.waitForFunction($query,$options,...$args);
		$waitAfter && (await sleep($waitAfter))
		/*#{1JE2TH24J0PostCodes*/
		/*}#1JE2TH24J0PostCodes*/
		return {seg:AwaitLogin,result:(result),preSeg:"1JE2TH24J0",outlet:"1JE2TM8KT2"};
	};
	WaitLogin.jaxId="1JE2TH24J0"
	WaitLogin.url="WaitLogin@"+agentURL
	
	segs["TipLogin"]=TipLogin=async function(input){//:1JE3PUQ4C0
		let result=input;
		/*#{1JE3PUQ4C0Start*/
		const $page=context.aaPage;
		let res=await $page.callFunction(ai2appsPrompt,[
			(($ln==="CN")?("请登录以便AI执行进一步的操作。如果在登录过程中遇到问题无法完成，请关闭页面。"):/*EN*/("Please log in to allow the AI to proceed with further actions. If you encounter issues during the login process and cannot complete it, please close the page.")),
			{
				caption:"AI2Apps",
				icon:await readFileAsDataURL("./ai2apps.svg"),
				okText:(($ln==="CN")?("确定"):/*EN*/("OK")),
				cancelText:(($ln==="CN")?("放弃"):/*EN*/("Abort")),
				showCancel:true
			}
		],{});
		/*}#1JE3PUQ4C0Start*/
		if(!res){
			return {seg:AbortBack,result:(input),preSeg:"1JE3PUQ4C0",outlet:"1JE3Q0Q8L0"};
		}
		/*#{1JE3PUQ4C0Post*/
		/*}#1JE3PUQ4C0Post*/
		return {seg:WaitLogin,result:(result),preSeg:"1JE3PUQ4C0",outlet:"1JE3Q0Q8L1"};
	};
	TipLogin.jaxId="1JE3PUQ4C0"
	TipLogin.url="TipLogin@"+agentURL
	
	segs["AwaitLogin"]=AwaitLogin=async function(input){//:1JE2TG01L0
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
			return {seg:GoBack2,result:(error),preSeg:"1JE2TG01L0",outlet:"1JE2TM8KT0"};
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:WaitNetwork,result:(result),preSeg:"1JE2TG01L0",outlet:"1JE2TM8KT1"};
	};
	AwaitLogin.jaxId="1JE2TG01L0"
	AwaitLogin.url="AwaitLogin@"+agentURL
	
	segs["JumpError"]=JumpError=async function(input){//:1JE2VBC5H0
		let result=input;
		return {seg:FinNotLogined,result:result,preSeg:"1JE2M9T0I0",outlet:"1JE2VBRJ50"};
	
	};
	JumpError.jaxId="1JE2M9T0I0"
	JumpError.url="JumpError@"+agentURL
	
	segs["JumpLogined"]=JumpLogined=async function(input){//:1JE2VDNQH0
		let result=input;
		return {seg:FinLogined,result:result,preSeg:"1JE2LARPL0",outlet:"1JE2VE94T0"};
	
	};
	JumpLogined.jaxId="1JE2LARPL0"
	JumpLogined.url="JumpLogined@"+agentURL
	
	segs["JumAbort"]=JumAbort=async function(input){//:1JE3Q09910
		let result=input;
		return {seg:FinNotLogined,result:result,preSeg:"1JE2M9T0I0",outlet:"1JE3Q0Q8L2"};
	
	};
	JumAbort.jaxId="1JE2M9T0I0"
	JumAbort.url="JumAbort@"+agentURL
	
	segs["GoBack"]=GoBack=async function(input){//:1JE3T5G5R0
		let result=input;
		let waitBefore=0;
		let waitAfter=3000;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		try{
			if(browser){
				await browser.backToApp();
			}
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1JE3T5G5R0ErrorCode*/
			/*}#1JE3T5G5R0ErrorCode*/
		}
		return {seg:AskDone,result:(result),preSeg:"1JE3T5G5R0",outlet:"1JE3T60SB0"};
	};
	GoBack.jaxId="1JE3T5G5R0"
	GoBack.url="GoBack@"+agentURL
	
	segs["WaitNetwork"]=WaitNetwork=async function(input){//:1JE4394D20
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
		context[$flag]=page.waitForNetworkIdle($options);
		$waitAfter && (await sleep($waitAfter))
		return {seg:CheckAgain,result:(result),preSeg:"1JE4394D20",outlet:"1JE439M650"};
	};
	WaitNetwork.jaxId="1JE4394D20"
	WaitNetwork.url="WaitNetwork@"+agentURL
	
	segs["CheckAgain"]=CheckAgain=async function(input){//:1JE43AQUO0
		let result=input;
		/*#{1JE43AQUO0Start*/
		let $page,res;
		$page=context.aaPage;
		res=await $page.callFunction(detectLoginState,[{allowOffscreen:true}],{});
		/*}#1JE43AQUO0Start*/
		if(!!res){
			return {seg:GoBack,result:(input),preSeg:"1JE43AQUO0",outlet:"1JE43AQUP3"};
		}
		/*#{1JE43AQUO0Post*/
		/*}#1JE43AQUO0Post*/
		return {seg:JumpWait,result:(result),preSeg:"1JE43AQUO0",outlet:"1JE43AQUP2"};
	};
	CheckAgain.jaxId="1JE43AQUO0"
	CheckAgain.url="CheckAgain@"+agentURL
	
	segs["JumpWait"]=JumpWait=async function(input){//:1JE43C2US0
		let result=input;
		return {seg:WaitLogin,result:result,preSeg:"1JE2TH24J0",outlet:"1JE43CQ9P0"};
	
	};
	JumpWait.jaxId="1JE2TH24J0"
	JumpWait.url="JumpWait@"+agentURL
	
	segs["AbortBack"]=AbortBack=async function(input){//:1JE5E23H70
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
			/*#{1JE5E23H70ErrorCode*/
			/*}#1JE5E23H70ErrorCode*/
		}
		return {seg:JumAbort,result:(result),preSeg:"1JE5E23H70",outlet:"1JE5E2LVQ0"};
	};
	AbortBack.jaxId="1JE5E23H70"
	AbortBack.url="AbortBack@"+agentURL
	
	segs["GoBack2"]=GoBack2=async function(input){//:1JE5E660L0
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
			/*#{1JE5E660L0ErrorCode*/
			/*}#1JE5E660L0ErrorCode*/
		}
		return {seg:JumpError,result:(result),preSeg:"1JE5E660L0",outlet:"1JE5E6QQS0"};
	};
	GoBack2.jaxId="1JE5E660L0"
	GoBack2.url="GoBack2@"+agentURL
	
	segs["AskDone"]=AskDone=async function(input){//:1JE5J6D5M0
		let prompt=((($ln==="CN")?("您是否已完成登录？如果还没有完成，请返回页面继续完成登录，再返回这里，确认登录继续执行后续的操作。"):("Have you completed the login? If not, please go back to the page to finish logging in, then return here and confirm the login to proceed with the next steps.")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{emoji:"✅",text:(($ln==="CN")?("确认已完成登录。"):("Confirm login is complete.")),code:0},
			{emoji:"❌",text:(($ln==="CN")?("无法完成登录，放弃操作"):("Unable to complete login, operation aborted")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:JumpLogined,result:(result),preSeg:"1JE5J6D5M0",outlet:"1JE5J6D580"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:JumpLogined,result:(result),preSeg:"1JE5J6D5M0",outlet:"1JE5J6D580"};
		}else if(item.code===1){
			return {seg:JumpAbort,result:(result),preSeg:"1JE5J6D5M0",outlet:"1JE5JDU9L0"};
		}
		return {result:result};
	};
	AskDone.jaxId="1JE5J6D5M0"
	AskDone.url="AskDone@"+agentURL
	
	segs["JumpAbort"]=JumpAbort=async function(input){//:1JE5JFPFL0
		let result=input;
		return {seg:FinNotLogined,result:result,preSeg:"1JE2M9T0I0",outlet:"1JE5JGK240"};
	
	};
	JumpAbort.jaxId="1JE2M9T0I0"
	JumpAbort.url="JumpAbort@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CaRpa_GenCheckLogin",
		url:agentURL,
		autoStart:true,
		jaxId:"1JDUKACEC0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{pageRef,profile,url,waitAfter,login,timeout}*/){
			let result;
			parseAgentArgs(input);
			/*#{1JDUKACEC0PreEntry*/
			/*}#1JDUKACEC0PreEntry*/
			result={seg:StartRpa,"input":input};
			/*#{1JDUKACEC0PostEntry*/
			/*}#1JDUKACEC0PostEntry*/
			return result;
		},
		/*#{1JDUKACEC0MoreAgentAttrs*/
		/*}#1JDUKACEC0MoreAgentAttrs*/
	};
	/*#{1JDUKACEC0PostAgent*/
	/*}#1JDUKACEC0PostAgent*/
	return agent;
};
/*#{1JDUKACEC0ExCodes*/
/*}#1JDUKACEC0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "CaRpa_GenCheckLogin",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				pageRef:{type:"auto",description:""},
				profile:{type:"auto",description:""},
				url:{type:"auto",description:""},
				waitAfter:{type:"integer",description:""},
				login:{type:"auto",description:""},
				timeout:{type:"integer",description:""}
			}
		}
	},
	agentNode: "genrpa",
	agentName: "CaRpa_GenCheckLogin.js",
	isChatApi: true,
	kind: "rpa",
	capabilities: ["login.check","login.interactive","login.ensure"],
	filters: [{"key":"domain","value":"*"}],
	metrics: {"quality":7,"costPerCall":0,"costPer1M":0,"speed":9,"size":0}
}];
//#CodyExport<<<
/*#{1JDUKACEC0PostDoc*/
/*}#1JDUKACEC0PostDoc*/


export default CaRpa_GenCheckLogin;
export{CaRpa_GenCheckLogin,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JDUKACEC0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JDUKACEC1",
//			"attrs": {
//				"CaRpa_GenCheckLogin": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JDUKACED0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JDUKACED1",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JDUKACED2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JDUKACED3",
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
//			"jaxId": "1JDUKACEC2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JDUKACEC3",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDUKH8II0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"profile": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDUKH8II1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDUKH8II2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"waitAfter": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JDVJ4H8R0",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"login": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE2LJR8B0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"timeout": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JE3PU1DC0",
//					"attrs": {
//						"type": "Integer",
//						"mockup": "0",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1JDUKACEC4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JDUKACEC5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1JDUKACEC6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1JDUKHIQS0",
//					"attrs": {
//						"id": "StartRpa",
//						"viewName": "",
//						"label": "",
//						"x": "125",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDUKICMJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDUKICMJ1",
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
//						"waitAfter": "#pageRef?0:1000",
//						"outlet": {
//							"jaxId": "1JDUKICMI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE2L00OE0"
//						},
//						"catchlet": {
//							"jaxId": "1JDUKICMJ2",
//							"attrs": {
//								"id": "NoAAE",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1JDUKICMJ3",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1JDUKICMJ4",
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
//					"jaxId": "1JE2L00OE0",
//					"attrs": {
//						"id": "CheckLogin",
//						"viewName": "",
//						"label": "",
//						"x": "355",
//						"y": "220",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE2L6I0S0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE2L6I0S1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE2L6I0M1",
//							"attrs": {
//								"id": "NotLogin",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE2LB7FT0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE2L6I0M0",
//									"attrs": {
//										"id": "Logined",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE2L6I0S2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE2L6I0S3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!res"
//									},
//									"linkedSeg": "1JE2LARPL0"
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
//					"jaxId": "1JE2LARPL0",
//					"attrs": {
//						"id": "FinLogined",
//						"viewName": "",
//						"label": "",
//						"x": "600",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE2LF18V0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE2LF18V1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE2LEDV90",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDVK00GO0"
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
//					"jaxId": "1JE2LB7FT0",
//					"attrs": {
//						"id": "CheckInteractive",
//						"viewName": "",
//						"label": "",
//						"x": "600",
//						"y": "425",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE2LF18V2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE2LF18V3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE2LEDV92",
//							"attrs": {
//								"id": "Login",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE2T7OBA0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE2LEDV91",
//									"attrs": {
//										"id": "DontLogin",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE2LF18V4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE2LF18V5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!login || !login.ensure"
//									},
//									"linkedSeg": "1JE2M9T0I0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JDVK00GO0",
//					"attrs": {
//						"id": "WaitAfter",
//						"viewName": "",
//						"label": "",
//						"x": "1160",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1JDVK1U260",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDVK1U261",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "",
//						"waitBefore": "0",
//						"waitAfter": "#waitAfter",
//						"outlet": {
//							"jaxId": "1JDVK0INL1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"catchlet": {
//							"jaxId": "1JDVK0INL0",
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
//					"def": "code",
//					"jaxId": "1JE2M9T0I0",
//					"attrs": {
//						"id": "FinNotLogined",
//						"viewName": "",
//						"label": "",
//						"x": "895",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE2MAEN50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE2MAEN51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE2MAEMU0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JDVK00GO0"
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
//					"jaxId": "1JE2T7OBA0",
//					"attrs": {
//						"id": "FocusPage",
//						"viewName": "",
//						"label": "",
//						"x": "895",
//						"y": "440",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE2TAD880",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE2TAD881",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true,\"switchBack\":0}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE2TAD820",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE3PUQ4C0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1JE2TH24J0",
//					"attrs": {
//						"id": "WaitLogin",
//						"viewName": "",
//						"label": "",
//						"x": "1425",
//						"y": "455",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE2TN2EF2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE2TN2EF3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Function",
//						"flag": "$WaitFlag",
//						"query": "#detectLoginState",
//						"queryHint": "",
//						"waitBefore": "1000",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE2TM8KT2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE2TG01L0"
//						},
//						"timeout": "#timeout"
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JE3PUQ4C0",
//					"attrs": {
//						"id": "TipLogin",
//						"viewName": "",
//						"label": "",
//						"x": "1160",
//						"y": "440",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE3Q1K4V0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE3Q1K4V1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE3Q0Q8L1",
//							"attrs": {
//								"id": "DoLogin",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE2TH24J0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE3Q0Q8L0",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE3Q1K4V2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE3Q1K4V3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!res"
//									},
//									"linkedSeg": "1JE5E23H70"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JE2TG01L0",
//					"attrs": {
//						"id": "AwaitLogin",
//						"viewName": "",
//						"label": "",
//						"x": "1675",
//						"y": "455",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE2TN2EF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE2TN2EF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JE2TM8KT1",
//							"attrs": {
//								"id": "Done",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE4394D20"
//						},
//						"catchlet": {
//							"jaxId": "1JE2TM8KT0",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5E660L0"
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JE2VBC5H0",
//					"attrs": {
//						"id": "JumpError",
//						"viewName": "",
//						"label": "",
//						"x": "2180",
//						"y": "555",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JE2M9T0I0",
//						"outlet": {
//							"jaxId": "1JE2VBRJ50",
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
//					"jaxId": "1JE2VDNQH0",
//					"attrs": {
//						"id": "JumpLogined",
//						"viewName": "",
//						"label": "",
//						"x": "2945",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JE2LARPL0",
//						"outlet": {
//							"jaxId": "1JE2VE94T0",
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
//					"jaxId": "1JE3Q09910",
//					"attrs": {
//						"id": "JumAbort",
//						"viewName": "",
//						"label": "",
//						"x": "1675",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JE2M9T0I0",
//						"outlet": {
//							"jaxId": "1JE3Q0Q8L2",
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
//					"jaxId": "1JE3T5G5R0",
//					"attrs": {
//						"id": "GoBack",
//						"viewName": "",
//						"label": "",
//						"x": "2445",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE3T60SL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE3T60SL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "3000",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JE3T60SB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE5J6D5M0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1JE4394D20",
//					"attrs": {
//						"id": "WaitNetwork",
//						"viewName": "",
//						"label": "",
//						"x": "1910",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE43CQ9V0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE43CQ9V1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "NetworkIdle",
//						"flag": "$WaitFlag",
//						"query": "",
//						"queryHint": "",
//						"waitBefore": "0",
//						"waitAfter": "",
//						"outlet": {
//							"jaxId": "1JE439M650",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE43AQUO0"
//						}
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JE43AQUO0",
//					"attrs": {
//						"id": "CheckAgain",
//						"viewName": "",
//						"label": "",
//						"x": "2180",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE43AQUP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE43AQUP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JE43AQUP2",
//							"attrs": {
//								"id": "NotLogin",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JE43C2US0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JE43AQUP3",
//									"attrs": {
//										"id": "Logined",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE43AQUP4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE43AQUP5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!res"
//									},
//									"linkedSeg": "1JE3T5G5R0"
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
//					"jaxId": "1JE43C2US0",
//					"attrs": {
//						"id": "JumpWait",
//						"viewName": "",
//						"label": "",
//						"x": "2445",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JE2TH24J0",
//						"outlet": {
//							"jaxId": "1JE43CQ9P0",
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
//					"jaxId": "1JE5E23H70",
//					"attrs": {
//						"id": "AbortBack",
//						"viewName": "",
//						"label": "",
//						"x": "1425",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE5E2M000",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5E2M001",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JE5E2LVQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE3Q09910"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JE5E660L0",
//					"attrs": {
//						"id": "GoBack2",
//						"viewName": "",
//						"label": "",
//						"x": "1910",
//						"y": "555",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE5E6QR40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE5E6QR41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"errorSeg": "",
//						"outlet": {
//							"jaxId": "1JE5E6QQS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE2VBC5H0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1JE5J6D5M0",
//					"attrs": {
//						"id": "AskDone",
//						"viewName": "",
//						"label": "",
//						"x": "2685",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Have you completed the login? If not, please go back to the page to finish logging in, then return here and confirm the login to proceed with the next steps.",
//							"localize": {
//								"EN": "Have you completed the login? If not, please go back to the page to finish logging in, then return here and confirm the login to proceed with the next steps.",
//								"CN": "您是否已完成登录？如果还没有完成，请返回页面继续完成登录，再返回这里，确认登录继续执行后续的操作。"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1JE5JDBPU0",
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
//									"jaxId": "1JE5J6D580",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Confirm login is complete.",
//											"localize": {
//												"EN": "Confirm login is complete.",
//												"CN": "确认已完成登录。"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE5JDBQD0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE5JDBQD1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"emoji": "✅"
//									},
//									"linkedSeg": "1JE2VDNQH0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JE5JDU9L0",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Unable to complete login, operation aborted",
//											"localize": {
//												"EN": "Unable to complete login, operation aborted",
//												"CN": "无法完成登录，放弃操作"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JE5JGK2B0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JE5JGK2B1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"emoji": "❌"
//									},
//									"linkedSeg": "1JE5JFPFL0"
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
//					"jaxId": "1JE5JFPFL0",
//					"attrs": {
//						"id": "JumpAbort",
//						"viewName": "",
//						"label": "",
//						"x": "2945",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JE2M9T0I0",
//						"outlet": {
//							"jaxId": "1JE5JGK240",
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
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"genrpa\",\"chatEntry\":false,\"isChatApi\":1,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\",\"kind\":\"rpa\",\"capabilities\":[\"login.check\",\"login.interactive\",\"login.ensure\"],\"filters\":[{\"key\":\"domain\",\"value\":\"*\"}],\"metrics\":{\"quality\":7,\"costPerCall\":0,\"costPer1M\":0,\"speed\":9,\"size\":0},\"meta\":\"\"}"
//	}
//}