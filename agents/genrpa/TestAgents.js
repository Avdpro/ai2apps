//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1JDVK5JNN0MoreImports*/
/*}#1JDVK5JNN0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1JDVK5JNN0StartDoc*/
/*}#1JDVK5JNN0StartDoc*/
//----------------------------------------------------------------------------
let TestAgents=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,TestShowMore,Blocker,CheckLogin,Search,ReadList,ShowMore,TestReadList,TestReadArticle,ReadArticle,Output,TestSearch,TestSelector,FindSelector,FindSelector2,ClickStart,TestCompose,StartCompose,InputTitle,CompseDone,InputConent,AddImages,TestLogin,Publish;
	/*#{1JDVK5JNN0LocalVals*/
	/*}#1JDVK5JNN0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1JDVK5JNN0ParseArgs*/
		/*}#1JDVK5JNN0ParseArgs*/
	}
	
	/*#{1JDVK5JNN0PreContext*/
	/*}#1JDVK5JNN0PreContext*/
	context={
		pageRef: "",
		/*#{1JDVK5JNN5ExCtxAttrs*/
		/*}#1JDVK5JNN5ExCtxAttrs*/
	};
	/*#{1JDVK5JNN0PostContext*/
	/*}#1JDVK5JNN0PostContext*/
	let $agent,agent,segs={};
	segs["Start"]=Start=async function(input){//:1JEO9JJ170
		let result=input
		try{
			/*#{1JEO9JJ170Code*/
			/*}#1JEO9JJ170Code*/
		}catch(error){
			/*#{1JEO9JJ170ErrorCode*/
			/*}#1JEO9JJ170ErrorCode*/
		}
		return {seg:TestCompose,result:(result),preSeg:"1JEO9JJ170",outlet:"1JEO9JRRT0"};
	};
	Start.jaxId="1JEO9JJ170"
	Start.url="Start@"+agentURL
	
	segs["TestShowMore"]=TestShowMore=async function(input){//:1JDVK5R100
		let result;
		let arg={"url":"https://www.xiaohongshu.com/explore","profile":"","headless":"","waitAfter":1000,"open":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_OpenBrowser.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:ShowMore,result:(result),preSeg:"1JDVK5R100",outlet:"1JDVK6F730"};
	};
	TestShowMore.jaxId="1JDVK5R100"
	TestShowMore.url="TestShowMore@"+agentURL
	
	segs["Blocker"]=Blocker=async function(input){//:1JDVKNQFM0
		let result;
		let arg={"pageRef":input.pageRef,"blocker":{remove:true},"waitAfter":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenBlockers.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	Blocker.jaxId="1JDVKNQFM0"
	Blocker.url="Blocker@"+agentURL
	
	segs["CheckLogin"]=CheckLogin=async function(input){//:1JE3LRKOO0
		let result;
		let arg={"pageRef":input.pageRef,"profile":"","url":"","waitAfter":"","login":{ensure:true},"timeout":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenCheckLogin.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:Output,result:(result),preSeg:"1JE3LRKOO0",outlet:"1JE3LSG0F0"};
	};
	CheckLogin.jaxId="1JE3LRKOO0"
	CheckLogin.url="CheckLogin@"+agentURL
	
	segs["Search"]=Search=async function(input){//:1JE8UADJB0
		let result;
		let arg={"pageRef":input.pageRef,"url":"","profile":"","search":"劳力士 万年历","searchNum":"","waitAfter":"","opts":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenSearch.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:Output,result:(result),preSeg:"1JE8UADJB0",outlet:"1JE916VGM0"};
	};
	Search.jaxId="1JE8UADJB0"
	Search.url="Search@"+agentURL
	
	segs["ReadList"]=ReadList=async function(input){//:1JEGPL5LI0
		let result;
		let arg={"pageRef":input.pageRef,"url":"","profile":"","waitAfter":"","read":{listTarget:"article", fields:["title","url"]},"minItems":80,"maxItems":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenReadList.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:Output,result:(result),preSeg:"1JEGPL5LI0",outlet:"1JEGPLN3D0"};
	};
	ReadList.jaxId="1JEGPL5LI0"
	ReadList.url="ReadList@"+agentURL
	
	segs["ShowMore"]=ShowMore=async function(input){//:1JEJ9RPSP0
		let result;
		let arg={"pageRef":input.pageRef,"profile":"","url":"","waitAfter":"","listCode":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenMoreItems.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:Output,result:(result),preSeg:"1JEJ9RPSP0",outlet:"1JEJ9S9420"};
	};
	ShowMore.jaxId="1JEJ9RPSP0"
	ShowMore.url="ShowMore@"+agentURL
	
	segs["TestReadList"]=TestReadList=async function(input){//:1JEO9FBOG0
		let result;
		let arg={"url":"https://www.fratellowatches.com/archives/","profile":"","headless":"","waitAfter":1000,"open":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_OpenBrowser.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:ReadList,result:(result),preSeg:"1JEO9FBOG0",outlet:"1JEO9FBOG3"};
	};
	TestReadList.jaxId="1JEO9FBOG0"
	TestReadList.url="TestReadList@"+agentURL
	
	segs["TestReadArticle"]=TestReadArticle=async function(input){//:1JESE1AJB0
		let result;
		let arg={"url":"https://watchesbysjx.com/2026/01/omega-speedmaster-moonwatch-reverse-panda.html","profile":"","headless":"","waitAfter":1000,"open":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_OpenBrowser.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:ReadArticle,result:(result),preSeg:"1JESE1AJB0",outlet:"1JESE1AJC2"};
	};
	TestReadArticle.jaxId="1JESE1AJB0"
	TestReadArticle.url="TestReadArticle@"+agentURL
	
	segs["ReadArticle"]=ReadArticle=async function(input){//:1JESE1V890
		let result;
		let arg={"pageRef":input.pageRef,"url":"","profile":"","read":{detail:true}};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenReadArticle.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:Output,result:(result),preSeg:"1JESE1V890",outlet:"1JESE38J70"};
	};
	ReadArticle.jaxId="1JESE1V890"
	ReadArticle.url="ReadArticle@"+agentURL
	
	segs["Output"]=Output=async function(input){//:1JESE9M5T0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=`### 执行结果：
\`\`\`
${JSON.stringify(input,null,"\t")}
\`\`\`
`;
		session.addChatText(role,content,opts);
		return {result:result};
	};
	Output.jaxId="1JESE9M5T0"
	Output.url="Output@"+agentURL
	
	segs["TestSearch"]=TestSearch=async function(input){//:1JESEQIB40
		let result;
		let arg={"url":"https://www.google.com","profile":"","headless":"","waitAfter":1000,"open":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_OpenBrowser.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:Search,result:(result),preSeg:"1JESEQIB40",outlet:"1JESEQIB43"};
	};
	TestSearch.jaxId="1JESEQIB40"
	TestSearch.url="TestSearch@"+agentURL
	
	segs["TestSelector"]=TestSelector=async function(input){//:1JEVTL0IG0
		let result;
		let arg={"url":"https://weibo.com","profile":"","headless":"","waitAfter":1000,"open":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_OpenBrowser.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		context["pageRef"]=result.pageRef;
		return {seg:FindSelector,result:(result),preSeg:"1JEVTL0IG0",outlet:"1JEVTL0IG3"};
	};
	TestSelector.jaxId="1JEVTL0IG0"
	TestSelector.url="TestSelector@"+agentURL
	
	segs["FindSelector"]=FindSelector=async function(input){//:1JEVTLNO30
		let result;
		let arg={"pageRef":input.pageRef,"url":"","profile":"","selectDesc":"微博帖子","multiSelect":true,"useManual":true,"allowManual":true};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./Util_FindSelector.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:Output,result:(result),preSeg:"1JEVTLNO30",outlet:"1JEVTO7VB0"};
	};
	FindSelector.jaxId="1JEVTLNO30"
	FindSelector.url="FindSelector@"+agentURL
	
	segs["FindSelector2"]=FindSelector2=async function(input){//:1JF1F9OKG0
		let result;
		let arg={"pageRef":context.pageRef,"url":"","profile":"","selectDesc":"输入帖子内容区域","multiSelect":false,"useManual":true,"allowManual":true};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./Util_FindSelector.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	FindSelector2.jaxId="1JF1F9OKG0"
	FindSelector2.url="FindSelector2@"+agentURL
	
	segs["ClickStart"]=ClickStart=async function(input){//:1JF1FA4SL0
		let result=true;
		let pageVal="aaPage";
		let $query=input.selector;
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
		try{
			if($query||$queryHint){
				$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JF1FA4SL0")):$query;
				if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
				$pms=page.click($query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
			}else{
				$pms=page.mouse.click($x,$y,$options||{});
			}
			if($pms && (!$async)){$done=await $pms;}
			$waitAfter && (await sleep($waitAfter))
		}catch(error){
			/*#{1JF1FA4SL0ErrorCode*/
			/*}#1JF1FA4SL0ErrorCode*/
		}
		return {seg:FindSelector2,result:(result),preSeg:"1JF1FA4SL0",outlet:"1JF1FDQBD0"};
	};
	ClickStart.jaxId="1JF1FA4SL0"
	ClickStart.url="ClickStart@"+agentURL
	
	segs["TestCompose"]=TestCompose=async function(input){//:1JFC8TRVB0
		let result;
		let arg={"url":"https://www.weibo.com","profile":"","headless":"","waitAfter":1000,"open":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_OpenBrowser.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JFC8TRVB0Input*/
		/*}#1JFC8TRVB0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JFC8TRVB0Output*/
		/*}#1JFC8TRVB0Output*/
		context["pageRef"]=result.pageRef;
		return {seg:StartCompose,result:(result),preSeg:"1JFC8TRVB0",outlet:"1JFC8TRVB3"};
	};
	TestCompose.jaxId="1JFC8TRVB0"
	TestCompose.url="TestCompose@"+agentURL
	
	segs["StartCompose"]=StartCompose=async function(input){//:1JFC9099O0
		let result;
		let arg={"pageRef":input.pageRef,"url":"","profile":"","compose":{action:"start"},"opts":{useManual:true,allowManual:true}};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenCompose.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:InputTitle,result:(result),preSeg:"1JFC9099O0",outlet:"1JFC9117E0"};
	};
	StartCompose.jaxId="1JFC9099O0"
	StartCompose.url="StartCompose@"+agentURL
	
	segs["InputTitle"]=InputTitle=async function(input){//:1JFIGJJL80
		let result;
		let arg={"pageRef":context.pageRef,"url":"","profile":"","compose":{action:"input",field:"title",text:"上海好冷啊"},"opts":{useManual:true,allowManual:true}};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenCompose.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	InputTitle.jaxId="1JFIGJJL80"
	InputTitle.url="InputTitle@"+agentURL
	
	segs["CompseDone"]=CompseDone=async function(input){//:1JFIGN1D80
		let result=input;
		return {seg:Output,result:result,preSeg:"1JESE9M5T0",outlet:"1JFIGNEL70"};
	
	};
	CompseDone.jaxId="1JESE9M5T0"
	CompseDone.url="CompseDone@"+agentURL
	
	segs["InputConent"]=InputConent=async function(input){//:1JFPQSVQN0
		let result;
		let arg={"pageRef":context.pageRef,"url":"","profile":"","compose":{action:"input",field:"content",text:"这都赶上北京了……"},"opts":{useManual:true,allowManual:true}};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenCompose.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:AddImages,result:(result),preSeg:"1JFPQSVQN0",outlet:"1JFPQSVQO2"};
	};
	InputConent.jaxId="1JFPQSVQN0"
	InputConent.url="InputConent@"+agentURL
	
	segs["AddImages"]=AddImages=async function(input){//:1JFQCHT4E0
		let result;
		let arg={"pageRef":context.pageRef,"url":"","profile":"","compose":{action:"file",field:"image",files:["/Users/avdpropang/Downloads/IMG_9560.JPG"]},"opts":{useManual:true,allowManual:true}};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenCompose.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	AddImages.jaxId="1JFQCHT4E0"
	AddImages.url="AddImages@"+agentURL
	
	segs["TestLogin"]=TestLogin=async function(input){//:1JG2NAHD90
		let result;
		let arg={"url":"https://www.weibo.com","profile":"","headless":"","waitAfter":1000,"open":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_OpenBrowser.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CheckLogin,result:(result),preSeg:"1JG2NAHD90",outlet:"1JG2NAHDA2"};
	};
	TestLogin.jaxId="1JG2NAHD90"
	TestLogin.url="TestLogin@"+agentURL
	
	segs["Publish"]=Publish=async function(input){//:1JG3IH98A0
		let result;
		let arg={"pageRef":context.pageRef,"url":"","profile":"","compose":{action:"publish","visibility":""},"opts":""};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./CaRpa_GenCompose.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CompseDone,result:(result),preSeg:"1JG3IH98A0",outlet:"1JG3IHKBC0"};
	};
	Publish.jaxId="1JG3IH98A0"
	Publish.url="Publish@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"TestAgents",
		url:agentURL,
		autoStart:true,
		jaxId:"1JDVK5JNN0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1JDVK5JNN0PreEntry*/
			/*}#1JDVK5JNN0PreEntry*/
			result={seg:Start,"input":input};
			/*#{1JDVK5JNN0PostEntry*/
			/*}#1JDVK5JNN0PostEntry*/
			return result;
		},
		/*#{1JDVK5JNN0MoreAgentAttrs*/
		/*}#1JDVK5JNN0MoreAgentAttrs*/
	};
	/*#{1JDVK5JNN0PostAgent*/
	/*}#1JDVK5JNN0PostAgent*/
	return agent;
};
/*#{1JDVK5JNN0ExCodes*/
/*}#1JDVK5JNN0ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1JDVK5JNN0PostDoc*/
/*}#1JDVK5JNN0PostDoc*/


export default TestAgents;
export{TestAgents};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1JDVK5JNN0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1JDVK5JNN1",
//			"attrs": {
//				"TestAgents": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1JDVK5JNN7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1JDVK5JNN8",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1JDVK5JNN9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1JDVK5JNN10",
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
//			"jaxId": "1JDVK5JNN2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1JDVK5JNN3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1JDVK5JNN4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1JDVK5JNN5",
//			"attrs": {
//				"pageRef": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JF1FGJD80",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1JDVK5JNN6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JEO9JJ170",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "80",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEO9JRRU0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEO9JRRU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JEO9JRRT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFC8TRVB0"
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
//					"jaxId": "1JDVK5R100",
//					"attrs": {
//						"id": "TestShowMore",
//						"viewName": "",
//						"label": "",
//						"x": "365",
//						"y": "545",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDVK6F750",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDVK6F751",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_OpenBrowser.js",
//						"argument": "{\"url\":\"https://www.xiaohongshu.com/explore\",\"profile\":\"\",\"headless\":\"\",\"waitAfter\":1000,\"open\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JDVK6F730",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEJ9RPSP0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JDVKNQFM0",
//					"attrs": {
//						"id": "Blocker",
//						"viewName": "",
//						"label": "",
//						"x": "655",
//						"y": "180",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JDVKOBJP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JDVKOBJP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenBlockers.js",
//						"argument": "{\"pageRef\":\"#input.pageRef\",\"blocker\":\"#{remove:true}\",\"waitAfter\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JDVKOBJO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JE3LRKOO0",
//					"attrs": {
//						"id": "CheckLogin",
//						"viewName": "",
//						"label": "",
//						"x": "655",
//						"y": "270",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE3LSG0G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE3LSG0G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenCheckLogin.js",
//						"argument": "{\"pageRef\":\"#input.pageRef\",\"profile\":\"\",\"url\":\"\",\"waitAfter\":\"\",\"login\":\"#{ensure:true}\",\"timeout\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JE3LSG0F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESE9M5T0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JE8UADJB0",
//					"attrs": {
//						"id": "Search",
//						"viewName": "",
//						"label": "",
//						"x": "655",
//						"y": "355",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JE916VGN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JE916VGN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenSearch.js",
//						"argument": "{\"pageRef\":\"#input.pageRef\",\"url\":\"\",\"profile\":\"\",\"search\":\"劳力士 万年历\",\"searchNum\":\"\",\"waitAfter\":\"\",\"opts\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JE916VGM0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESE9M5T0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JEGPL5LI0",
//					"attrs": {
//						"id": "ReadList",
//						"viewName": "",
//						"label": "",
//						"x": "655",
//						"y": "455",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEGPLN3G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEGPLN3G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenReadList.js",
//						"argument": "{\"pageRef\":\"#input.pageRef\",\"url\":\"\",\"profile\":\"\",\"waitAfter\":\"\",\"read\":\"#{listTarget:\\\"article\\\", fields:[\\\"title\\\",\\\"url\\\"]}\",\"minItems\":80,\"maxItems\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JEGPLN3D0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESE9M5T0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JEJ9RPSP0",
//					"attrs": {
//						"id": "ShowMore",
//						"viewName": "",
//						"label": "",
//						"x": "655",
//						"y": "545",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEJ9S9430",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEJ9S9431",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenMoreItems.js",
//						"argument": "{\"pageRef\":\"#input.pageRef\",\"profile\":\"\",\"url\":\"\",\"waitAfter\":\"\",\"listCode\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JEJ9S9420",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESE9M5T0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JEO9FBOG0",
//					"attrs": {
//						"id": "TestReadList",
//						"viewName": "",
//						"label": "",
//						"x": "365",
//						"y": "455",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEO9FBOG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEO9FBOG2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_OpenBrowser.js",
//						"argument": "{\"url\":\"https://www.fratellowatches.com/archives/\",\"profile\":\"\",\"headless\":\"\",\"waitAfter\":1000,\"open\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JEO9FBOG3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEGPL5LI0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JESE1AJB0",
//					"attrs": {
//						"id": "TestReadArticle",
//						"viewName": "",
//						"label": "",
//						"x": "365",
//						"y": "635",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JESE1AJC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JESE1AJC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_OpenBrowser.js",
//						"argument": "{\"url\":\"https://watchesbysjx.com/2026/01/omega-speedmaster-moonwatch-reverse-panda.html\",\"profile\":\"\",\"headless\":\"\",\"waitAfter\":1000,\"open\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JESE1AJC2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESE1V890"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JESE1V890",
//					"attrs": {
//						"id": "ReadArticle",
//						"viewName": "",
//						"label": "",
//						"x": "655",
//						"y": "635",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JESE38JA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JESE38JA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenReadArticle.js",
//						"argument": "{\"pageRef\":\"#input.pageRef\",\"url\":\"\",\"profile\":\"\",\"read\":\"#{detail:true}\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JESE38J70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESE9M5T0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JESE9M5T0",
//					"attrs": {
//						"id": "Output",
//						"viewName": "",
//						"label": "",
//						"x": "990",
//						"y": "455",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JESECV680",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JESECV681",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#`### 执行结果：\n\\`\\`\\`\n${JSON.stringify(input,null,\"\\t\")}\n\\`\\`\\`\n`",
//						"outlet": {
//							"jaxId": "1JESECV650",
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
//					"def": "aiBot",
//					"jaxId": "1JESEQIB40",
//					"attrs": {
//						"id": "TestSearch",
//						"viewName": "",
//						"label": "",
//						"x": "365",
//						"y": "355",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JESEQIB41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JESEQIB42",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_OpenBrowser.js",
//						"argument": "{\"url\":\"https://www.google.com\",\"profile\":\"\",\"headless\":\"\",\"waitAfter\":1000,\"open\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JESEQIB43",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE8UADJB0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JEVTL0IG0",
//					"attrs": {
//						"id": "TestSelector",
//						"viewName": "",
//						"label": "",
//						"x": "365",
//						"y": "720",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEVTL0IG1",
//							"attrs": {
//								"cast": "{\"pageRef\":\"#result.pageRef\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1JEVTL0IG2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_OpenBrowser.js",
//						"argument": "{\"url\":\"https://weibo.com\",\"profile\":\"\",\"headless\":\"\",\"waitAfter\":1000,\"open\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JEVTL0IG3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JEVTLNO30"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JEVTLNO30",
//					"attrs": {
//						"id": "FindSelector",
//						"viewName": "",
//						"label": "",
//						"x": "655",
//						"y": "720",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JEVTO7VE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JEVTO7VE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Util_FindSelector.js",
//						"argument": "{\"pageRef\":\"#input.pageRef\",\"url\":\"\",\"profile\":\"\",\"selectDesc\":\"微博帖子\",\"multiSelect\":true,\"useManual\":true,\"allowManual\":true}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JEVTO7VB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JESE9M5T0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JF1F9OKG0",
//					"attrs": {
//						"id": "FindSelector2",
//						"viewName": "",
//						"label": "",
//						"x": "1135",
//						"y": "720",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1F9OKG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1F9OKG2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/Util_FindSelector.js",
//						"argument": "{\"pageRef\":\"#context.pageRef\",\"url\":\"\",\"profile\":\"\",\"selectDesc\":\"输入帖子内容区域\",\"multiSelect\":false,\"useManual\":true,\"allowManual\":true}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JF1F9OKG3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JF1FA4SL0",
//					"attrs": {
//						"id": "ClickStart",
//						"viewName": "",
//						"label": "",
//						"x": "905",
//						"y": "720",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JF1FDQBE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JF1FDQBE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "#input.selector",
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
//							"jaxId": "1JF1FDQBD0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JF1F9OKG0"
//						},
//						"errorSeg": "",
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JFC8TRVB0",
//					"attrs": {
//						"id": "TestCompose",
//						"viewName": "",
//						"label": "",
//						"x": "365",
//						"y": "80",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFC8TRVB1",
//							"attrs": {
//								"cast": "{\"pageRef\":\"#result.pageRef\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1JFC8TRVB2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_OpenBrowser.js",
//						"argument": "{\"url\":\"https://www.weibo.com\",\"profile\":\"\",\"headless\":\"\",\"waitAfter\":1000,\"open\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JFC8TRVB3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFC9099O0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JFC9099O0",
//					"attrs": {
//						"id": "StartCompose",
//						"viewName": "",
//						"label": "",
//						"x": "655",
//						"y": "80",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFC9117F0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFC9117F1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenCompose.js",
//						"argument": "{\"pageRef\":\"#input.pageRef\",\"url\":\"\",\"profile\":\"\",\"compose\":\"#{action:\\\"start\\\"}\",\"opts\":\"#{useManual:true,allowManual:true}\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JFC9117E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFIGJJL80"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JFIGJJL80",
//					"attrs": {
//						"id": "InputTitle",
//						"viewName": "",
//						"label": "",
//						"x": "930",
//						"y": "80",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFIGMMFF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFIGMMFF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenCompose.js",
//						"argument": "{\"pageRef\":\"#context.pageRef\",\"url\":\"\",\"profile\":\"\",\"compose\":\"#{action:\\\"input\\\",field:\\\"title\\\",text:\\\"上海好冷啊\\\"}\",\"opts\":\"#{useManual:true,allowManual:true}\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JFIGMMFA0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JFIGN1D80",
//					"attrs": {
//						"id": "CompseDone",
//						"viewName": "",
//						"label": "",
//						"x": "1945",
//						"y": "80",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JESE9M5T0",
//						"outlet": {
//							"jaxId": "1JFIGNEL70",
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
//					"def": "aiBot",
//					"jaxId": "1JFPQSVQN0",
//					"attrs": {
//						"id": "InputConent",
//						"viewName": "",
//						"label": "",
//						"x": "1190",
//						"y": "80",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFPQSVQO0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFPQSVQO1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenCompose.js",
//						"argument": "{\"pageRef\":\"#context.pageRef\",\"url\":\"\",\"profile\":\"\",\"compose\":\"#{action:\\\"input\\\",field:\\\"content\\\",text:\\\"这都赶上北京了……\\\"}\",\"opts\":\"#{useManual:true,allowManual:true}\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JFPQSVQO2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFQCHT4E0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JFQCHT4E0",
//					"attrs": {
//						"id": "AddImages",
//						"viewName": "",
//						"label": "",
//						"x": "1450",
//						"y": "80",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFQCHT4E1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFQCHT4E2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenCompose.js",
//						"argument": "{\"pageRef\":\"#context.pageRef\",\"url\":\"\",\"profile\":\"\",\"compose\":\"#{action:\\\"file\\\",field:\\\"image\\\",files:[\\\"/Users/avdpropang/Downloads/IMG_9560.JPG\\\"]}\",\"opts\":\"#{useManual:true,allowManual:true}\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JFQCHT4F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JG2NAHD90",
//					"attrs": {
//						"id": "TestLogin",
//						"viewName": "",
//						"label": "",
//						"x": "365",
//						"y": "270",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JG2NAHDA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG2NAHDA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_OpenBrowser.js",
//						"argument": "{\"url\":\"https://www.weibo.com\",\"profile\":\"\",\"headless\":\"\",\"waitAfter\":1000,\"open\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JG2NAHDA2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JE3LRKOO0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JG3IH98A0",
//					"attrs": {
//						"id": "Publish",
//						"viewName": "",
//						"label": "",
//						"x": "1705",
//						"y": "80",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JG3IHKBH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JG3IHKBH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/CaRpa_GenCompose.js",
//						"argument": "{\"pageRef\":\"#context.pageRef\",\"url\":\"\",\"profile\":\"\",\"compose\":\"#{action:\\\"publish\\\",\\\"visibility\\\":\\\"\\\"}\",\"opts\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JG3IHKBC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFIGN1D80"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JG3J3HLS0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "610",
//						"y": "-30",
//						"outlet": {
//							"jaxId": "1JG3J3U7G0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG3J3MCE0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1JG3J3MCE0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1550",
//						"y": "-30",
//						"outlet": {
//							"jaxId": "1JG3J3U7G1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JG3IH98A0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}