//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1HDBOSUN90MoreImports*/
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*}#1HDBOSUN90MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1HDBOSUN90StartDoc*/
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let BaiduSearch=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let OpenPage,Notify,TypeText,ClickSearchBtn,CheckContentElement,DoExist,ShowError,ReadContentRes,GetHtml,CheckDataLength,GoToNextPage,TipResult,ShowRes,ClosePage,ReadSearchRes,ShowAllRes;
	let data=undefined;
	
	/*#{1HDBOSUN90LocalVals*/
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
	/*}#1HDBOSUN90PreContext*/
	context={
		search: "",
		searchNum: "",
		pageNo: 0,
		/*#{1HDBOSUNA3ExCtxAttrs*/
		/*}#1HDBOSUNA3ExCtxAttrs*/
	};
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let $agent,agent,segs={};
	segs["OpenPage"]=OpenPage=async function(input){//:1IH28P38Q0
		let pageVal="aaPage";
		let $url="https://www.baidu.com";
		let $waitBefore=0;
		let $waitAfter=500;
		let $width=1200;
		let $height=900;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		/*#{1IH28P38Q0PreCodes*/
		context.rpaBrowser = globalContext.rpaBrowser;
		context.webRpa = globalContext.webRpa;
		/*}#1IH28P38Q0PreCodes*/
		try{
			context[pageVal]=page=await context.rpaBrowser.newPage();
			($width && $height) && (await page.setViewport({width:$width,height:$height}));
			$userAgent && (await page.setUserAgent($userAgent));
			await page.goto($url,$openOpts);
			$waitAfter && (await sleep($waitAfter));
		}catch(error){
			/*#{1IH28P38Q0ErrorCode*/
			/*}#1IH28P38Q0ErrorCode*/
		}
		/*#{1IH28P38Q0PostCodes*/
		globalContext.aaPage = context[pageVal];
		context.search = input.search;
		context.searchNum = input.searchNum;
		/*}#1IH28P38Q0PostCodes*/
		return {seg:Notify,result:(true),preSeg:"1IH28P38Q0",outlet:"1IH28P9TV0"};
	};
	OpenPage.jaxId="1IH28P38Q0"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["Notify"]=Notify=async function(input){//:1IH28Q6DB0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("百度已打开。"):("Baidu has been opened."));
		session.addChatText(role,content,opts);
		return {seg:TypeText,result:(result),preSeg:"1IH28Q6DB0",outlet:"1IH28R1BB0"};
	};
	Notify.jaxId="1IH28Q6DB0"
	Notify.url="Notify@"+agentURL
	
	segs["TypeText"]=TypeText=async function(input){//:1J0TKOVEG0
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="(//textarea[@id='chat-textarea'])";
		let $queryHint="";
		let $key=context.search;
		let $options={};
		let $waitBefore=200;
		let $waitAfter=200;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		/*#{1J0TKOVEG0PreCodes*/
		/*}#1J0TKOVEG0PreCodes*/
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1J0TKOVEG0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.type($query,$key,$options||{});
			}else{
				$pms=page.keyboard.type($key,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1J0TKOVEG0ErrorCode*/
			/*}#1J0TKOVEG0ErrorCode*/
		}
		/*#{1J0TKOVEG0PostCodes*/
		/*}#1J0TKOVEG0PostCodes*/
		return {seg:ClickSearchBtn,result:(result),preSeg:"1J0TKOVEG0",outlet:"1J0TKP1OU0"};
	};
	TypeText.jaxId="1J0TKOVEG0"
	TypeText.url="TypeText@"+agentURL
	
	segs["ClickSearchBtn"]=ClickSearchBtn=async function(input){//:1J0TKRJ230
		let result=true;
		let pageVal="aaPage";
		let $query="(//button[@id='chat-submit-button'])";
		let $queryHint="";
		let $x=0;
		let $y=0;
		let $options={};
		let $waitBefore=0;
		let $waitAfter=500;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		let $done=false;
		$waitBefore && (await sleep($waitBefore));
		/*#{1J0TKRJ230PreCodes*/
		context.webRpa = globalContext.webRpa;
		/*}#1J0TKRJ230PreCodes*/
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1J0TKRJ230")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.click($query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
			}else{
				$pms=page.mouse.click($x,$y,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1J0TKRJ230ErrorCode*/
			/*}#1J0TKRJ230ErrorCode*/
		}
		/*#{1J0TKRJ230PostCodes*/
		/*}#1J0TKRJ230PostCodes*/
		return {seg:CheckContentElement,result:(result),preSeg:"1J0TKRJ230",outlet:"1J0TKRLAF0"};
	};
	ClickSearchBtn.jaxId="1J0TKRJ230"
	ClickSearchBtn.url="ClickSearchBtn@"+agentURL
	
	segs["CheckContentElement"]=CheckContentElement=async function(input){//:1J3KOKJMN0
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query="(//div[@id='content_left'])";
		let $multi=false;
		let $options=undefined;
		let $waitBefore=1000;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			if($multi){
				result=await context.webRpa.queryNodes(page,$node,$query,$options);
			}else{
				result=await context.webRpa.queryNode(page,$node,$query,$options);
			}
			if((!result)||($multi && !result.length)){
				throw "Querry not found";
			}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1J3KOKJMN0ErrorCode*/
			/*}#1J3KOKJMN0ErrorCode*/
		}
		return {seg:DoExist,result:(result),preSeg:"1J3KOKJMN0",outlet:"1J3KOL1NP0"};
	};
	CheckContentElement.jaxId="1J3KOKJMN0"
	CheckContentElement.url="CheckContentElement@"+agentURL
	
	segs["DoExist"]=DoExist=async function(input){//:1J1V28TIS0
		let result=input;
		if( JSON.stringify(input) !== "{}" && JSON.stringify(input) !== undefined){
			let output=(($ln==="CN")?("正在搜索，请稍等..."):("Searching, please wait..."));
			return {seg:ReadContentRes,result:(output),preSeg:"1J1V28TIS0",outlet:"1J1V2AVP20"};
		}
		return {seg:ShowError,result:(result),preSeg:"1J1V28TIS0",outlet:"1J1V2AVP21"};
	};
	DoExist.jaxId="1J1V28TIS0"
	DoExist.url="DoExist@"+agentURL
	
	segs["ShowError"]=ShowError=async function(input){//:1J1V2OG2B0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {result:result};
	};
	ShowError.jaxId="1J1V2OG2B0"
	ShowError.url="ShowError@"+agentURL
	
	segs["ReadContentRes"]=ReadContentRes=async function(input){//:1J3KPQB720
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options={};
		let $waitBefore=3000;
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
			/*#{1J3KPQB720ErrorCode*/
			/*}#1J3KPQB720ErrorCode*/
		}
		return {seg:GetHtml,result:(result),preSeg:"1J3KPQB720",outlet:"1J3KPQTN10"};
	};
	ReadContentRes.jaxId="1J3KPQB720"
	ReadContentRes.url="ReadContentRes@"+agentURL
	
	segs["GetHtml"]=GetHtml=async function(input){//:1J3KPV5CC0
		let result=input
		try{
			/*#{1J3KPV5CC0Code*/
			try {
				const page = context.aaPage;
				const searchResults = await page.callFunction((searchNumber) => {
					const isAd = (el) => {
						const adSelectors = ['.ec_tuiguang', '[data-tuiguang]', '.c-container[tpl*="ad"]'];
						const adTitleSelector = 'span[title="广告"], .ec_tuiguang';
						const adTextContent = /广告/;
			
						return adSelectors.some(selector => el.closest(selector)) ||
							el.querySelector(adTitleSelector) ||
							adTextContent.test(el.textContent);
					};
			
					return Array.from(document.querySelectorAll('#content_left .result, #content_left [tpl]'))
						.filter(el => !isAd(el))
						.map((el, idx) => ({
							title: el.querySelector('h3 a') ? el.querySelector('h3 a').textContent.trim() : '',
							url: el.querySelector('h3 a') ? el.querySelector('h3 a').href : '',
							platform: 'baidu'
						}))
						.filter(r => r.title && r.url && !/最新相关信息/i.test(r.title) && r.url.includes('baidu.com/link?'));
				},[context.searchNum]);
				
				if (Array.isArray(context.data)) {
					context.data = context.data.concat(searchResults);
				} else {
					context.data = searchResults;
				}
				context.data = context.data.filter((item, index, self) =>
						index === self.findIndex((t) => (
							t.title === item.title 
						))
				);
				context.data = context.data.slice(0, context.searchNum);
			
				console.log("searchResults baidu", context.data.length);
			
				const markdown = [
					context.data.map((d,i)=>`${i+1}. [${d.title}](${d.url})`).join('\n')
				].filter(line => line !== '').join('\n');
			
				result = { res: 'Finish', length: context.data.length, keyword: context.search, platform: 'baidu', finds: context.data , markdown };
			} catch (e) {
				result = { res: 'Fail', info: e.message };
			}
			/*}#1J3KPV5CC0Code*/
		}catch(error){
			/*#{1J3KPV5CC0ErrorCode*/
			/*}#1J3KPV5CC0ErrorCode*/
		}
		return {seg:CheckDataLength,result:(result),preSeg:"1J3KPV5CC0",outlet:"1J3KPVHKK0"};
	};
	GetHtml.jaxId="1J3KPV5CC0"
	GetHtml.url="GetHtml@"+agentURL
	
	segs["CheckDataLength"]=CheckDataLength=async function(input){//:1J3KSTVII0
		let result=input;
		if( input.length >= context.searchNum){
			return {seg:TipResult,result:(input),preSeg:"1J3KSTVII0",outlet:"1J3KSVDPS0"};
		}
		return {seg:GoToNextPage,result:(result),preSeg:"1J3KSTVII0",outlet:"1J3KSUCCJ0"};
	};
	CheckDataLength.jaxId="1J3KSTVII0"
	CheckDataLength.url="CheckDataLength@"+agentURL
	
	segs["GoToNextPage"]=GoToNextPage=async function(input){//:1J3KTH1430
		let result=true;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let timeout=(undefined)||0;
		let url=`https://www.baidu.com/s?wd=${encodeURIComponent(context.search)}&pn=${context.pageNo * 10}`;
		let page=context[pageVal];
		let opts={timeout:timeout};
		waitBefore && (await sleep(waitBefore));
		/*#{1J3KTH1430PreCodes*/
		context.pageNo = (context.pageNo || 0) + 1;
		/*}#1J3KTH1430PreCodes*/
		try{
			await page.goto(url,opts);
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1J3KTH1430ErrorCode*/
			/*}#1J3KTH1430ErrorCode*/
		}
		/*#{1J3KTH1430PostCodes*/
		/*}#1J3KTH1430PostCodes*/
		return {seg:ReadContentRes,result:(result),preSeg:"1J3KTH1430",outlet:"1J3KTHNG40"};
	};
	GoToNextPage.jaxId="1J3KTH1430"
	GoToNextPage.url="GoToNextPage@"+agentURL
	
	segs["TipResult"]=TipResult=async function(input){//:1JBH2EPUA0
		let result=input;
		let $channel="Process";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JBH2EPUA0PreCodes*/
		content= ($ln==="CN") ? `共找到：${input.finds.length} 条笔记。` : `Find ${input.finds.length} notes.`;
		/*}#1JBH2EPUA0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JBH2EPUA0PostCodes*/
		result = input;
		/*}#1JBH2EPUA0PostCodes*/
		return {seg:ShowRes,result:(result),preSeg:"1JBH2EPUA0",outlet:"1JBH2G2920"};
	};
	TipResult.jaxId="1JBH2EPUA0"
	TipResult.url="TipResult@"+agentURL
	
	segs["ShowRes"]=ShowRes=async function(input){//:1J0TLS7LH0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?(`
${input.markdown}
`):(`
${input.markdown}
`));
		session.addChatText(role,content,opts);
		return {seg:ClosePage,result:(result),preSeg:"1J0TLS7LH0",outlet:"1J0TLS9MJ0"};
	};
	ShowRes.jaxId="1J0TLS7LH0"
	ShowRes.url="ShowRes@"+agentURL
	
	segs["ClosePage"]=ClosePage=async function(input){//:1J2GMS02K0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		try{
			await page.close();
			context[pageVal]=null;
			waitAfter && (await sleep(waitAfter))
		}catch(error){
			/*#{1J2GMS02K0ErrorCode*/
			/*}#1J2GMS02K0ErrorCode*/
		}
		return {result:result};
	};
	ClosePage.jaxId="1J2GMS02K0"
	ClosePage.url="ClosePage@"+agentURL
	
	segs["ReadSearchRes"]=ReadSearchRes=async function(input){//:1J1A396C50
		let result=input
		try{
			/*#{1J1A396C50Code*/
			/*}#1J1A396C50Code*/
		}catch(error){
			/*#{1J1A396C50ErrorCode*/
			/*}#1J1A396C50ErrorCode*/
		}
		return {seg:ShowAllRes,result:(result),preSeg:"1J1A396C50",outlet:"1J1A39R980"};
	};
	ReadSearchRes.jaxId="1J1A396C50"
	ReadSearchRes.url="ReadSearchRes@"+agentURL
	
	segs["ShowAllRes"]=ShowAllRes=async function(input){//:1J1A3UQ580
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=`
\`\`\`
${JSON.stringify(input,null,"\t")}
\`\`\`
`;
		session.addChatText(role,content,opts);
		return {result:result};
	};
	ShowAllRes.jaxId="1J1A3UQ580"
	ShowAllRes.url="ShowAllRes@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"BaiduSearch",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN90PreEntry*/
			/*}#1HDBOSUN90PreEntry*/
			result={seg:OpenPage,"input":input};
			/*#{1HDBOSUN90PostEntry*/
			/*}#1HDBOSUN90PostEntry*/
			return result;
		},
		/*#{1HDBOSUN90MoreAgentAttrs*/
		/*}#1HDBOSUN90MoreAgentAttrs*/
	};
	/*#{1HDBOSUN90PostAgent*/
	/*}#1HDBOSUN90PostAgent*/
	return agent;
};
/*#{1HDBOSUN90ExCodes*/
/*}#1HDBOSUN90ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "BaiduSearch",
		description: "这是一个AI代理。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1HDBOSUN90PostDoc*/
/*}#1HDBOSUN90PostDoc*/


export default BaiduSearch;
export{BaiduSearch,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1HDBOSUN90",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1HDBOSUNA0",
//			"attrs": {
//				"agent": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1HDBOSUNA4",
//					"attrs": {
//						"constructArgs": {
//							"jaxId": "1HDBOSUNB0",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1HDBOSUNB1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1HDBOSUNB2",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportType": "UI Data Template",
//						"exportClass": "false",
//						"superClass": ""
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1HDBOSUNA1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "OpenPage",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH2869AD0",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {
//				"data": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1HDBOSUNA3",
//			"attrs": {
//				"search": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JBCDEB8I0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"searchNum": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JBCDEB8I1",
//					"attrs": {
//						"type": "Number",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"pageNo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JBCE0HGN0",
//					"attrs": {
//						"type": "Number",
//						"mockup": "0",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1HDIJB7SK6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1IH28P38Q0",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "90",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH28P9U10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH28P9U11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "https://www.baidu.com",
//						"vpWidth": "1200",
//						"vpHeight": "900",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1IH28P9TV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH28Q6DB0"
//						},
//						"run": "",
//						"errorSeg": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IH28Q6DB0",
//					"attrs": {
//						"id": "Notify",
//						"viewName": "",
//						"label": "",
//						"x": "340",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH28R1BC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH28R1BC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Baidu has been opened.",
//							"localize": {
//								"EN": "Baidu has been opened.",
//								"CN": "百度已打开。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IH28R1BB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0TKOVEG0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1J0TKOVEG0",
//					"attrs": {
//						"id": "TypeText",
//						"viewName": "",
//						"label": "",
//						"x": "610",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0TKP1P10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0TKP1P11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Type",
//						"query": "(//textarea[@id='chat-textarea'])",
//						"queryHint": "",
//						"key": "#context.search",
//						"async": "false",
//						"options": "{}",
//						"waitBefore": "200",
//						"waitAfter": "200",
//						"outlet": {
//							"jaxId": "1J0TKP1OU0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0TKRJ230"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1J0TKRJ230",
//					"attrs": {
//						"id": "ClickSearchBtn",
//						"viewName": "",
//						"label": "",
//						"x": "835",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0TKRLAK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0TKRLAK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "(//button[@id='chat-submit-button'])",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"deltaX": "0",
//						"deltaY": "100",
//						"async": "false",
//						"options": "{}",
//						"waitBefore": "0",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1J0TKRLAF0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3KOKJMN0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1J3KOKJMN0",
//					"attrs": {
//						"id": "CheckContentElement",
//						"viewName": "",
//						"label": "",
//						"x": "1095",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3KONDES0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3KONDES1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "(//div[@id='content_left'])",
//						"queryHint": "",
//						"multi": "false",
//						"options": "",
//						"errorSeg": "",
//						"waitBefore": "1000",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J3KOL1NP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1V28TIS0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1JAVFIMAT0",
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
//					"def": "brunch",
//					"jaxId": "1J1V28TIS0",
//					"attrs": {
//						"id": "DoExist",
//						"viewName": "",
//						"label": "",
//						"x": "1375",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1V2AVP40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1V2AVP41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J1V2AVP21",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J1V2OG2B0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J1V2AVP20",
//									"attrs": {
//										"id": "Exist",
//										"desc": "输出节点。",
//										"output": {
//											"type": "string",
//											"valText": "#\"Searching, please wait...\"",
//											"localize": {
//												"EN": "#\"Searching, please wait...\"",
//												"CN": "#\"正在搜索，请稍等...\""
//											},
//											"localizable": true
//										},
//										"codes": "false",
//										"context": {
//											"jaxId": "1J1V2AVP42",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J1V2AVP43",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "# JSON.stringify(input) !== \"{}\" && JSON.stringify(input) !== undefined"
//									},
//									"linkedSeg": "1J3KPQB720"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J1V2OG2B0",
//					"attrs": {
//						"id": "ShowError",
//						"viewName": "",
//						"label": "",
//						"x": "1590",
//						"y": "250",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1V2OG750",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1V2OG751",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1J1V2OG752",
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
//					"def": "WebRpaReadPage",
//					"jaxId": "1J3KPQB720",
//					"attrs": {
//						"id": "ReadContentRes",
//						"viewName": "",
//						"label": "",
//						"x": "2110",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3KPQTN90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3KPQTN91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"target": "CleanHTML",
//						"node": "null",
//						"options": "{}",
//						"waitBefore": "3000",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J3KPQTN10",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3KPV5CC0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J3KPV5CC0",
//					"attrs": {
//						"id": "GetHtml",
//						"viewName": "",
//						"label": "",
//						"x": "2390",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3KPVHKN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3KPVHKO0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J3KPVHKK0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3KSTVII0"
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
//					"jaxId": "1J3KSTVII0",
//					"attrs": {
//						"id": "CheckDataLength",
//						"viewName": "",
//						"label": "",
//						"x": "2640",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3KSUCCN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3KSUCCN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J3KSUCCJ0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J3KTH1430"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J3KSVDPS0",
//									"attrs": {
//										"id": "Greater",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J3KSVDQ00",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J3KSVDQ01",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "# input.length >= context.searchNum"
//									},
//									"linkedSeg": "1JBH2EPUA0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaPageGoto",
//					"jaxId": "1J3KTH1430",
//					"attrs": {
//						"id": "GoToNextPage",
//						"viewName": "",
//						"label": "",
//						"x": "3080",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3KTHNG90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3KTHNG91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"url": "#`https://www.baidu.com/s?wd=${encodeURIComponent(context.search)}&pn=${context.pageNo * 10}`",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J3KTHNG40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3KVDUK30"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/wait_goto.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JBH2EPUA0",
//					"attrs": {
//						"id": "TipResult",
//						"viewName": "",
//						"label": "",
//						"x": "2965",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBH2HNII0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBH2HNII1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Process",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JBH2G2920",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J0TLS7LH0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J0TLS7LH0",
//					"attrs": {
//						"id": "ShowRes",
//						"viewName": "",
//						"label": "",
//						"x": "3185",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J0TLS9MT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J0TLS9MT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "#`\n${input.markdown}\n`",
//							"localize": {
//								"EN": "#`\n${input.markdown}\n`",
//								"CN": "#`\n${input.markdown}\n`"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J0TLS9MJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J2GMS02K0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1J2GMS02K0",
//					"attrs": {
//						"id": "ClosePage",
//						"viewName": "",
//						"label": "",
//						"x": "3405",
//						"y": "145",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J2GMSBLJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J2GMSBLJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J2GMSBLD0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J1A396C50",
//					"attrs": {
//						"id": "ReadSearchRes",
//						"viewName": "",
//						"label": "",
//						"x": "1290",
//						"y": "1180",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1A39R9D0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1A39R9D1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J1A39R980",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1A3UQ580"
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
//					"def": "output",
//					"jaxId": "1J1A3UQ580",
//					"attrs": {
//						"id": "ShowAllRes",
//						"viewName": "",
//						"label": "",
//						"x": "1650",
//						"y": "1175",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1A3VMNH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1A3VMNH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#`\n\\`\\`\\`\n${JSON.stringify(input,null,\"\\t\")}\n\\`\\`\\`\n`",
//						"outlet": {
//							"jaxId": "1J1A3VMNF0",
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
//					"def": "connector",
//					"jaxId": "1J3KVDUK30",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3250",
//						"y": "340",
//						"outlet": {
//							"jaxId": "1J3KVEJ5E0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3KVE2H30"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J3KVE2H30",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2140",
//						"y": "340",
//						"outlet": {
//							"jaxId": "1J3KVEJ5E1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3KPQB720"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}