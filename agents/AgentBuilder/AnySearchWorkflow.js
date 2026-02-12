//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1HDBOSUN90MoreImports*/
import { mkdirSync, appendFileSync } from 'fs';
import { dirname } from 'path';
import axios from 'axios';
import http from 'node:http';
import https from 'node:https';
/*}#1HDBOSUN90MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"searchNum":{
			"name":"searchNum","type":"number",
			"defaultValue":5,
			"desc":"",
		},
		"modelName":{
			"name":"modelName","type":"string",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1HDBOSUN90ArgsView*/
	/*}#1HDBOSUN90ArgsView*/
};

/*#{1HDBOSUN90StartDoc*/
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let AnySearchWorkflow=async function(session){
	let searchNum,modelName;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let fixargs,DefaultWaitTips,DefaultCallAPI,ShowDefaultCallAPIRes,InitAskUser,DefaultUserType,DefaultSearchWaitTips,CallInternalAPI,ShowInternalAPIRes,SelectQuestionWay,AskUserQuestion,UserTypeQuestion,RPA,IsReport,WaitTips_1,AxiosCallRpaAPI,CheckError,ShowError,GetAllLinks,ShowAllLinks,ContinueRPA,FileType,CheckLength,SimpleReport,ShowSimpleReport,WaitInfo,ConfirmAgain,ShowSelectedPlatform,ContinueRPA_1,ContinueAsk_2,Retry,RetryTips,ShowRetryError,SummarQuestion;
	/*#{1HDBOSUN90LocalVals*/
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			searchNum=input.searchNum;
			modelName=input.modelName;
		}else{
			searchNum=undefined;
			modelName=undefined;
		}
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
	/*}#1HDBOSUN90PreContext*/
	context={
		history: [],
		externalQuestion: "",
		rpaResult: "",
		rpaHistory: [],
		allLinks: [],
		platforms: [],
		modelInfo: "",
		/*#{1HDBOSUNA3ExCtxAttrs*/
		/*}#1HDBOSUNA3ExCtxAttrs*/
	};
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let $agent,agent,segs={};
	segs["fixargs"]=fixargs=async function(input){//:1JCFV0B9G0
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(searchNum===undefined || searchNum==="") missing=true;
		if(modelName===undefined || modelName==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:DefaultWaitTips,result:(result),preSeg:"1JCFV0B9G0",outlet:"1JCFV0GPE0"};
	};
	fixargs.jaxId="1JCFV0B9G0"
	fixargs.url="fixargs@"+agentURL
	
	segs["DefaultWaitTips"]=DefaultWaitTips=async function(input){//:1JFSGBHTU0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("正在为您获取模型信息，请稍候......"):("Fetching model information, please wait......"));
		/*#{1JFSGBHTU0PreCodes*/
		/*}#1JFSGBHTU0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JFSGBHTU0PostCodes*/
		/*}#1JFSGBHTU0PostCodes*/
		return {seg:DefaultCallAPI,result:(result),preSeg:"1JFSGBHTU0",outlet:"1JFSGBHTV0"};
	};
	DefaultWaitTips.jaxId="1JFSGBHTU0"
	DefaultWaitTips.url="DefaultWaitTips@"+agentURL
	
	segs["DefaultCallAPI"]=DefaultCallAPI=async function(input){//:1JFSFTQFT0
		let callVO=null;
		let result=input;
		let rsp=null;
		let url="http://ec2-54-234-128-29.compute-1.amazonaws.com:8000/qa";
		let method="POST";
		let headers={
		};
		/*#{1JFSFTQFT0PreCodes*/
		if($ln==="CN"){
			context.modelInfo = modelName + '，请用中文回答。';
		}else{
			context.modelInfo = modelName + ', Please answer in English.';
		};
		
		console.log(context.modelInfo,'context.modelInfo')
		/*}#1JFSFTQFT0PreCodes*/
		let json={
			"query":context.modelInfo,"history":[]
		};
		callVO={url:url,method:method,argMode:"JSON",headers:headers,json:json};
		/*#{1JFSFTQFT0AboutCall*/
		/*}#1JFSFTQFT0AboutCall*/
		rsp=await session.webCall(callVO,true,30000);
		if(rsp.code===200){
			result=JSON.parse(rsp.data);
		}else{
			throw Error("Error "+rsp.code+": "+rsp.info||"")
		}
		/*#{1JFSFTQFT0AfterCall*/
		context.history.push({
			user: modelName,
			assistant: result.answer,
		});
		/*}#1JFSFTQFT0AfterCall*/
		/*#{1JFSFTQFT0PostCodes*/
		/*}#1JFSFTQFT0PostCodes*/
		return {seg:ShowDefaultCallAPIRes,result:(result),preSeg:"1JFSFTQFT0",outlet:"1JFSFTQFT5"};
	};
	DefaultCallAPI.jaxId="1JFSFTQFT0"
	DefaultCallAPI.url="DefaultCallAPI@"+agentURL
	
	segs["ShowDefaultCallAPIRes"]=ShowDefaultCallAPIRes=async function(input){//:1JFSG88KP0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.answer;
		session.addChatText(role,content,opts);
		return {seg:InitAskUser,result:(result),preSeg:"1JFSG88KP0",outlet:"1JFSG88KP3"};
	};
	ShowDefaultCallAPIRes.jaxId="1JFSG88KP0"
	ShowDefaultCallAPIRes.url="ShowDefaultCallAPIRes@"+agentURL
	
	segs["InitAskUser"]=InitAskUser=async function(input){//:1JFSGHND40
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("你还想了解此模型的哪些信息？"):("What else would you like to know about this model?"));
		session.addChatText(role,content,opts);
		return {seg:DefaultUserType,result:(result),preSeg:"1JFSGHND40",outlet:"1JFSGHND43"};
	};
	InitAskUser.jaxId="1JFSGHND40"
	InitAskUser.url="InitAskUser@"+agentURL
	
	segs["DefaultUserType"]=DefaultUserType=async function(input){//:1JFSH6HBQ0
		let tip=("");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let allowEmpty=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		/*#{1JFSH6HBQ0PreCodes*/
		/*}#1JFSH6HBQ0PreCodes*/
		if(askUpward && tip){
			result=await session.askUpward($agent,tip);
		}else{
			if(tip){
				session.addChatText(tipRole,tip);
			}
			result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile,allowEmpty:allowEmpty});
		}
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		/*#{1JFSH6HBQ0PostCodes*/
		/*}#1JFSH6HBQ0PostCodes*/
		return {seg:DefaultSearchWaitTips,result:(result),preSeg:"1JFSH6HBQ0",outlet:"1JFSH6HBQ3"};
	};
	DefaultUserType.jaxId="1JFSH6HBQ0"
	DefaultUserType.url="DefaultUserType@"+agentURL
	
	segs["DefaultSearchWaitTips"]=DefaultSearchWaitTips=async function(input){//:1JFSH8ALP0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("好的，正在为您查询，请稍等......"):("Searching, please wait......"));
		/*#{1JFSH8ALP0PreCodes*/
		/*}#1JFSH8ALP0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JFSH8ALP0PostCodes*/
		/*}#1JFSH8ALP0PostCodes*/
		return {seg:CallInternalAPI,result:(result),preSeg:"1JFSH8ALP0",outlet:"1JFSH8ALP3"};
	};
	DefaultSearchWaitTips.jaxId="1JFSH8ALP0"
	DefaultSearchWaitTips.url="DefaultSearchWaitTips@"+agentURL
	
	segs["CallInternalAPI"]=CallInternalAPI=async function(input){//:1JFSHB9A70
		let callVO=null;
		let result=input;
		let rsp=null;
		let url="http://ec2-54-234-128-29.compute-1.amazonaws.com:8000/qa";
		let method="POST";
		let headers={
		};
		/*#{1JFSHB9A70PreCodes*/
		if($ln==="CN"){
			input = input + '，请用中文回答。';
		}else{
			input = input + ', Please answer in English.';
		};
		//console.log("CallInternalAPI",input)
		/*}#1JFSHB9A70PreCodes*/
		let json={
			"query":input,"history":context.history
		};
		callVO={url:url,method:method,argMode:"JSON",headers:headers,json:json};
		/*#{1JFSHB9A70AboutCall*/
		console.log("context.history",context.history);
		/*}#1JFSHB9A70AboutCall*/
		rsp=await session.webCall(callVO,true,30000);
		if(rsp.code===200){
			result=JSON.parse(rsp.data);
		}else{
			throw Error("Error "+rsp.code+": "+rsp.info||"")
		}
		/*#{1JFSHB9A70AfterCall*/
		context.history.push({
			user: input,
			assistant: result.answer,
		});
		/*}#1JFSHB9A70AfterCall*/
		/*#{1JFSHB9A70PostCodes*/
		/*}#1JFSHB9A70PostCodes*/
		return {seg:ShowInternalAPIRes,result:(result),preSeg:"1JFSHB9A70",outlet:"1JFSHB9A84"};
	};
	CallInternalAPI.jaxId="1JFSHB9A70"
	CallInternalAPI.url="CallInternalAPI@"+agentURL
	
	segs["ShowInternalAPIRes"]=ShowInternalAPIRes=async function(input){//:1JFSHITD60
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.answer;
		session.addChatText(role,content,opts);
		return {seg:SelectQuestionWay,result:(result),preSeg:"1JFSHITD60",outlet:"1JFSHITD63"};
	};
	ShowInternalAPIRes.jaxId="1JFSHITD60"
	ShowInternalAPIRes.url="ShowInternalAPIRes@"+agentURL
	
	segs["SelectQuestionWay"]=SelectQuestionWay=async function(input){//:1JFSHQOST0
		let prompt=((($ln==="CN")?("上述信息是否满足您的需求？如若不满足，您可按需联网搜索。"):("Continue asking or search online for more information?")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("继续提问"):("Continue asking")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("联网搜索"):("Online search")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:ContinueAsk_2,result:(result),preSeg:"1JFSHQOST0",outlet:"1JFSHQOST2"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:ContinueAsk_2,result:(result),preSeg:"1JFSHQOST0",outlet:"1JFSHQOST2"};
		}else if(item.code===1){
			return {seg:AskUserQuestion,result:(result),preSeg:"1JFSHQOST0",outlet:"1JFSHQOST5"};
		}
		return {result:result};
	};
	SelectQuestionWay.jaxId="1JFSHQOST0"
	SelectQuestionWay.url="SelectQuestionWay@"+agentURL
	
	segs["AskUserQuestion"]=AskUserQuestion=async function(input){//:1JC63DF8F0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("好的，AI 即将接管浏览器控制权限以执行联网搜索任务。请输入您的问题。"):("The AI is about to take control of the browser. Please enter your question."));
		session.addChatText(role,content,opts);
		return {seg:UserTypeQuestion,result:(result),preSeg:"1JC63DF8F0",outlet:"1JC63DF8F3"};
	};
	AskUserQuestion.jaxId="1JC63DF8F0"
	AskUserQuestion.url="AskUserQuestion@"+agentURL
	
	segs["UserTypeQuestion"]=UserTypeQuestion=async function(input){//:1JC63DTVT0
		let tip=("");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let allowEmpty=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		/*#{1JC63DTVT0PreCodes*/
		console.log("UserTypeQuestion ===",context.history);
		/*}#1JC63DTVT0PreCodes*/
		if(askUpward && tip){
			result=await session.askUpward($agent,tip);
		}else{
			if(tip){
				session.addChatText(tipRole,tip);
			}
			result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile,allowEmpty:allowEmpty});
		}
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		/*#{1JC63DTVT0PostCodes*/
		context.externalQuestion = result;
		const userContents = context.history.map(item => item.user).filter(Boolean).join('，');
		console.log(userContents);
		result = {
			userContents:userContents,
			search: result,
			searchNum: searchNum > 20 ? 20 : searchNum,
			platforms: (context.platforms && context.platforms.length) ? context.platforms : []
		};
		/*}#1JC63DTVT0PostCodes*/
		return {seg:SummarQuestion,result:(result),preSeg:"1JC63DTVT0",outlet:"1JC63DTVT3"};
	};
	UserTypeQuestion.jaxId="1JC63DTVT0"
	UserTypeQuestion.url="UserTypeQuestion@"+agentURL
	
	segs["RPA"]=RPA=async function(input){//:1JC0JAE5K0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/RpaEntry.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1JC0JAE5K0Input*/
		/*}#1JC0JAE5K0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1JC0JAE5K0Output*/
		//console.log(result.length,"RPA");
		context.rpaResult = result;
		context.allLinks.push(...result);
		/*}#1JC0JAE5K0Output*/
		return {seg:WaitInfo,result:(result),preSeg:"1JC0JAE5K0",outlet:"1JC0JAE5K3"};
	};
	RPA.jaxId="1JC0JAE5K0"
	RPA.url="RPA@"+agentURL
	
	segs["IsReport"]=IsReport=async function(input){//:1JC62L42T0
		let prompt=((($ln==="CN")?("请确认上述信息是否满足您的需求，是否需要生成深度报告？"):(" Would you like a detailed report generated?")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("生成报告"):("Generate Report")))||"OK";
		let button2=((($ln==="CN")?("继续提问"):("Continue asking")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		/*#{1JC62L42T0PreCodes*/
		/*}#1JC62L42T0PreCodes*/
		if(silent){
			result="";
			return {seg:WaitTips_1,result:(result),preSeg:"1JC62L42T0",outlet:"1JC62L42F0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		/*#{1JC62L42T0PostCodes*/
		result = input;
		if(value!==1){
			//const titles = input.map(it => it.title).join('、');
			context.rpaHistory.push({
				user: context.externalQuestion,
				assistant: input.assistant,
			});
			//console.log(context.rpaHistory,'rpaHistory===');
		};
		/*}#1JC62L42T0PostCodes*/
		if(value===1){
			result=("")||result;
			return {seg:WaitTips_1,result:(result),preSeg:"1JC62L42T0",outlet:"1JC62L42F0"};
		}
		result=("")||result;
		return {seg:ConfirmAgain,result:(result),preSeg:"1JC62L42T0",outlet:"1JC62L42F1"};
	
	};
	IsReport.jaxId="1JC62L42T0"
	IsReport.url="IsReport@"+agentURL
	
	segs["WaitTips_1"]=WaitTips_1=async function(input){//:1JC68VSRG0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("好的，正在为您生成报告，请稍等......"):("Generating report for you, please wait......"));
		/*#{1JC68VSRG0PreCodes*/
		/*}#1JC68VSRG0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JC68VSRG0PostCodes*/
		//	console.log(context.rpaHistory,'WaitTips_1');
			result = input.data.map(({ key, content, platform }) => {
				return { key, content, platform };
			});
			/*}#1JC68VSRG0PostCodes*/
		return {seg:AxiosCallRpaAPI,result:(result),preSeg:"1JC68VSRG0",outlet:"1JC68VSRG3"};
	};
	WaitTips_1.jaxId="1JC68VSRG0"
	WaitTips_1.url="WaitTips_1@"+agentURL
	
	segs["AxiosCallRpaAPI"]=AxiosCallRpaAPI=async function(input){//:1JC8K0M8V0
		let result=input
		try{
			/*#{1JC8K0M8V0Code*/
			let lang = ($ln==="CN") ? '，请用中文回答。' : ', Please answer in English.';
			const url = 'http://ec2-54-234-128-29.compute-1.amazonaws.com:8000/qa';
			const json = {
				query: context.externalQuestion + lang ,
				output_report: true,
				stream: false,
				web_search_result: input,
				history: context.rpaHistory
			};
			//console.log("json",json,"json");
			/* ---------- 写请求日志 ---------- */
			//const logFile = './logs/run.log';
			//mkdirSync(dirname(logFile), { recursive: true });
			//appendFileSync(logFile, `[${new Date().toISOString()}] ${JSON.stringify(json, null, 2)}\n`,'utf8');
			
			try {
				const rsp = await axios.post(url, json, {
					headers: { 'Content-Type': 'application/json' },
					timeout: 5 * 60 * 1000,
				});
				result = rsp.data;
				//console.log(result,'CallRpaAPI');
				context.rpaHistory.push({
					user: context.externalQuestion,
					assistant: result?.answer
				});
			} catch (err) {
				console.log("CallRpaAPI catch err", err, '===');
				
				const msg = err?.message === "socket hang up"
				? $ln === "CN"
					? "当前 VPN 不稳定，请检查并重试。"
					: "The current VPN is unstable. Please check and try again."
				: err;
				
				result = {
					res: "fail",
					web_search_result: input,
					errMsg: msg
				};
				//throw new Error(result.errMsg);
			};
			/*}#1JC8K0M8V0Code*/
		}catch(error){
			/*#{1JC8K0M8V0ErrorCode*/
			/*}#1JC8K0M8V0ErrorCode*/
		}
		return {seg:CheckError,result:(result),preSeg:"1JC8K0M8V0",outlet:"1JC8K0QBC0"};
	};
	AxiosCallRpaAPI.jaxId="1JC8K0M8V0"
	AxiosCallRpaAPI.url="AxiosCallRpaAPI@"+agentURL
	
	segs["CheckError"]=CheckError=async function(input){//:1JD2HUA490
		let result=input;
		if(input.errMsg){
			return {seg:ShowError,result:(input),preSeg:"1JD2HUA490",outlet:"1JD2I4PL50"};
		}
		return {seg:FileType,result:(result),preSeg:"1JD2HUA490",outlet:"1JD2HVHAT1"};
	};
	CheckError.jaxId="1JD2HUA490"
	CheckError.url="CheckError@"+agentURL
	
	segs["ShowError"]=ShowError=async function(input){//:1JD2IR51S0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.errMsg;
		/*#{1JD2IR51S0PreCodes*/
		/*}#1JD2IR51S0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JD2IR51S0PostCodes*/
		/*}#1JD2IR51S0PostCodes*/
		return {seg:Retry,result:(result),preSeg:"1JD2IR51S0",outlet:"1JD2IU2L60"};
	};
	ShowError.jaxId="1JD2IR51S0"
	ShowError.url="ShowError@"+agentURL
	
	segs["GetAllLinks"]=GetAllLinks=async function(input){//:1JC676I5O0
		let result=input
		try{
			/*#{1JC676I5O0Code*/
			//console.log(context.rpaResult.length,"ShowAllLinks");
			result = context.rpaResult;
			/*}#1JC676I5O0Code*/
		}catch(error){
			/*#{1JC676I5O0ErrorCode*/
			/*}#1JC676I5O0ErrorCode*/
		}
		return {seg:CheckLength,result:(result),preSeg:"1JC676I5O0",outlet:"1JC676TOK0"};
	};
	GetAllLinks.jaxId="1JC676I5O0"
	GetAllLinks.url="GetAllLinks@"+agentURL
	
	segs["ShowAllLinks"]=ShowAllLinks=async function(input){//:1JC669FLS0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content="";
		/*#{1JC669FLS0PreCodes*/
		const markdown = [
			($ln === "CN" ? "### 参考文献链接如下：" : "### The reference links are as follows:"),
			'',
			input.data                                         
				.filter(Boolean)                            
				.map((d, i) => {
					const t = d.title || '';                  
					return `${i + 1}. [${t.slice(0, 20)}${t.length > 20 ? '…' : ''}](${d.key})`;
				})
				.join('\n')
		].filter(line => line !== '').join('\n');
		
		content = markdown;
		/*}#1JC669FLS0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JC669FLS0PostCodes*/
		//result = context.allLinks;
		/*}#1JC669FLS0PostCodes*/
		return {seg:IsReport,result:(result),preSeg:"1JC669FLS0",outlet:"1JC66A45N0"};
	};
	ShowAllLinks.jaxId="1JC669FLS0"
	ShowAllLinks.url="ShowAllLinks@"+agentURL
	
	segs["ContinueRPA"]=ContinueRPA=async function(input){//:1JC87DURT0
		let result=input;
		return {seg:AskUserQuestion,result:result,preSeg:"1JC63DF8F0",outlet:"1JC87ETH40"};
	
	};
	ContinueRPA.jaxId="1JC63DF8F0"
	ContinueRPA.url="ContinueRPA@"+agentURL
	
	segs["FileType"]=FileType=async function(input){//:1JC8CQE880
		let prompt=((($ln==="CN")?("请选择报告的输出形式。"):("Please select the report output format.")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("Markdown 文档"):("Markdown Document")))||"OK";
		let button2=((($ln==="CN")?("Html 页面"):("Html Page")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		/*#{1JC8CQE880PreCodes*/
		/*}#1JC8CQE880PreCodes*/
		if(silent){
			result="";
			return {result:result};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		/*#{1JC8CQE880PostCodes*/
		//console.log("result",result);
		//result = input;
		// Html 页面 Html Page
		if(result === "Markdown 文档" || result === "Markdown Document"){
			result = {
				type: 'Md',
				userPrompt: input.answer
			};
		}else{
			result = { 
				type: 'Html',
				userPrompt: input.answer 
			};
		};
		/*}#1JC8CQE880PostCodes*/
		if(value===1){
			result=("")||result;
			return {result:result};
		}
		result=("")||result;
		return {result:result};
	
	};
	FileType.jaxId="1JC8CQE880"
	FileType.url="FileType@"+agentURL
	
	segs["CheckLength"]=CheckLength=async function(input){//:1JD2BIT1J0
		let result=input;
		if(input.length){
			return {seg:SimpleReport,result:(input),preSeg:"1JD2BIT1J0",outlet:"1JD2BKP070"};
		}
		return {result:result};
	};
	CheckLength.jaxId="1JD2BIT1J0"
	CheckLength.url="CheckLength@"+agentURL
	
	segs["SimpleReport"]=SimpleReport=async function(input){//:1JD7C9HUJ0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-4.1";
		let $agent;
		let result=null;
		/*#{1JD7C9HUJ0Input*/
		/*}#1JD7C9HUJ0Input*/
		
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
		let chatMem=SimpleReport.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:(($ln==="CN")?(`你是一位专业的内容总结 AI 助手。 - 任务：根据用户问题「${context.externalQuestion}」，仅提取 ${JSON.stringify(input,null,"\t")} 中所有 "content" 字段并进行总结，务必突出核心结论，不展开细节， 总结内容不超过 300 字，用中文回答。 - 最终输出为 json 格式： { "user": "${context.externalQuestion}", "assistant": "生成的总结内容" } `):(`You are a professional content summarization AI assistant. - Task: Based on the user question "${context.externalQuestion}", extract all "content" fields from ${JSON.stringify(input,null,"\t")} and summarize them, focusing on the core conclusion without expanding on details. The summary must not exceed 300 words, and please use english. - The final output should be in JSON format: { "user": "${context.externalQuestion}", "assistant": "Generated summary content" } `))},
		];
		messages.push(...chatMem);
		/*#{1JD7C9HUJ0PrePrompt*/
		/*}#1JD7C9HUJ0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JD7C9HUJ0FilterMessage*/
			/*}#1JD7C9HUJ0FilterMessage*/
			messages.push(msg);
		}
		/*#{1JD7C9HUJ0PreCall*/
		/*}#1JD7C9HUJ0PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("SimpleReport@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JD7C9HUJ0PostLLM*/
		/*}#1JD7C9HUJ0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1JD7C9HUJ0PostClear*/
			/*}#1JD7C9HUJ0PostClear*/
		}
		result=trimJSON(result);
		/*#{1JD7C9HUJ0PostCall*/
		result = {
			data: input,
			...result
		};
		/*}#1JD7C9HUJ0PostCall*/
		/*#{1JD7C9HUJ0PreResult*/
		/*}#1JD7C9HUJ0PreResult*/
		return {seg:ShowSimpleReport,result:(result),preSeg:"1JD7C9HUJ0",outlet:"1JD7CAI8T0"};
	};
	SimpleReport.jaxId="1JD7C9HUJ0"
	SimpleReport.url="SimpleReport@"+agentURL
	SimpleReport.messages=[];
	
	segs["ShowSimpleReport"]=ShowSimpleReport=async function(input){//:1JD7DAEAQ0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.assistant;
		session.addChatText(role,content,opts);
		return {seg:ShowAllLinks,result:(result),preSeg:"1JD7DAEAQ0",outlet:"1JD7DB3OL0"};
	};
	ShowSimpleReport.jaxId="1JD7DAEAQ0"
	ShowSimpleReport.url="ShowSimpleReport@"+agentURL
	
	segs["WaitInfo"]=WaitInfo=async function(input){//:1JD7E4EHN0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("正在为您总结搜索结果，请稍等......"):("Summarizing search results for you, please wait......"));
		/*#{1JD7E4EHN0PreCodes*/
		/*}#1JD7E4EHN0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JD7E4EHN0PostCodes*/
		const keys = [...new Set(input.map(r => r.platform))];
		const map = {
			baidu: '百度',
			google: '谷歌',
			redNote: '小红书',
			zhihu: '知乎',
			x: '推特', 
			reddit: 'Reddit',
		};
		
		const arr = $ln === 'CN'
		? keys.map(k => map[k] || k)
		: keys.map(k => (k === 'x' ? 'Twitter' : k.charAt(0).toUpperCase() + k.slice(1)));
		
		context.platforms = arr;
		/*}#1JD7E4EHN0PostCodes*/
		return {seg:GetAllLinks,result:(result),preSeg:"1JD7E4EHN0",outlet:"1JD7E7CF90"};
	};
	WaitInfo.jaxId="1JD7E4EHN0"
	WaitInfo.url="WaitInfo@"+agentURL
	
	segs["ConfirmAgain"]=ConfirmAgain=async function(input){//:1JD7IKO7D0
		let prompt=((($ln==="CN")?("是否需要重新选择搜索平台？"):("Do you need to reselect the search platform?")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("需要"):("Need")))||"OK";
		let button2=((($ln==="CN")?("不需要"):("Not needed")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		/*#{1JD7IKO7D0PreCodes*/
		/*}#1JD7IKO7D0PreCodes*/
		if(silent){
			result="";
			return {seg:ContinueRPA,result:(result),preSeg:"1JD7IKO7D0",outlet:"1JD7IKO6O0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		/*#{1JD7IKO7D0PostCodes*/
		if(value===1){
			context.platforms = [];
		}
		/*}#1JD7IKO7D0PostCodes*/
		if(value===1){
			result=("")||result;
			return {seg:ContinueRPA,result:(result),preSeg:"1JD7IKO7D0",outlet:"1JD7IKO6O0"};
		}
		result=("")||result;
		return {seg:ShowSelectedPlatform,result:(result),preSeg:"1JD7IKO7D0",outlet:"1JD7IKO6O1"};
	
	};
	ConfirmAgain.jaxId="1JD7IKO7D0"
	ConfirmAgain.url="ConfirmAgain@"+agentURL
	
	segs["ShowSelectedPlatform"]=ShowSelectedPlatform=async function(input){//:1JD7J7B7O0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?(`好的，我们将继续使用 ${JSON.stringify(context.platforms,null,"\t")} 平台进行搜索。`):(`We will continue to use the ${JSON.stringify(context.platforms,null,"\t")} platforms for the search. `));
		/*#{1JD7J7B7O0PreCodes*/
		/*}#1JD7J7B7O0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JD7J7B7O0PostCodes*/
		result = {
			search: context.externalQuestion,
			searchNum: searchNum,
			platforms: context.platforms
		};
		/*}#1JD7J7B7O0PostCodes*/
		return {seg:ContinueRPA_1,result:(result),preSeg:"1JD7J7B7O0",outlet:"1JD7J8EAT0"};
	};
	ShowSelectedPlatform.jaxId="1JD7J7B7O0"
	ShowSelectedPlatform.url="ShowSelectedPlatform@"+agentURL
	
	segs["ContinueRPA_1"]=ContinueRPA_1=async function(input){//:1JD9NAKND0
		let result=input;
		return {seg:AskUserQuestion,result:result,preSeg:"1JC63DF8F0",outlet:"1JD9NAKND1"};
	
	};
	ContinueRPA_1.jaxId="1JC63DF8F0"
	ContinueRPA_1.url="ContinueRPA_1@"+agentURL
	
	segs["ContinueAsk_2"]=ContinueAsk_2=async function(input){//:1JFSIFKH10
		let result=input;
		return {seg:InitAskUser,result:result,preSeg:"1JFSGHND40",outlet:"1JFSIFKH20"};
	
	};
	ContinueAsk_2.jaxId="1JFSGHND40"
	ContinueAsk_2.url="ContinueAsk_2@"+agentURL
	
	segs["Retry"]=Retry=async function(input){//:1JGJ5TCJT0
		let prompt=((($ln==="CN")?("是否再尝试一次？"):("Try again?")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("是"):("Yes")))||"OK";
		let button2=((($ln==="CN")?("否"):("No")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result=input.web_search_result;
			return {seg:RetryTips,result:(result),preSeg:"1JGJ5TCJT0",outlet:"1JGJ5TCJ80"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=(input.web_search_result)||result;
			return {seg:RetryTips,result:(result),preSeg:"1JGJ5TCJT0",outlet:"1JGJ5TCJ80"};
		}
		result=(input)||result;
		return {seg:ShowRetryError,result:(result),preSeg:"1JGJ5TCJT0",outlet:"1JGJ5TCJ81"};
	
	};
	Retry.jaxId="1JGJ5TCJT0"
	Retry.url="Retry@"+agentURL
	
	segs["RetryTips"]=RetryTips=async function(input){//:1JGJ7KERC0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("好的，正在为您生成报告，请稍等......"):("Generating report for you, please wait......"));
		/*#{1JGJ7KERC0PreCodes*/
		/*}#1JGJ7KERC0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JGJ7KERC0PostCodes*/
		/*}#1JGJ7KERC0PostCodes*/
		return {seg:AxiosCallRpaAPI,result:(result),preSeg:"1JGJ7KERC0",outlet:"1JGJ7KERD1"};
	};
	RetryTips.jaxId="1JGJ7KERC0"
	RetryTips.url="RetryTips@"+agentURL
	
	segs["ShowRetryError"]=ShowRetryError=async function(input){//:1JGJ7OET60
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?("当前任务因 VPN 连接不稳定已终止。请检查网络环境后重新尝试，或联系技术支持获取帮助。"):("The current task has been terminated due to an unstable VPN connection. Please check your network environment and try again, or contact technical support for assistance."));
		/*#{1JGJ7OET60PreCodes*/
		/*}#1JGJ7OET60PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JGJ7OET60PostCodes*/
		/*}#1JGJ7OET60PostCodes*/
		return {result:result};
	};
	ShowRetryError.jaxId="1JGJ7OET60"
	ShowRetryError.url="ShowRetryError@"+agentURL
	
	segs["SummarQuestion"]=SummarQuestion=async function(input){//:1JH04QDG10
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-4.1";
		let $agent;
		let result=null;
		/*#{1JH04QDG10Input*/
		//console.log("SummarQuestion",'-----');
		//console.log(JSON.stringify(context.history,null,"\t"))
		console.log('=====', input)
		/*}#1JH04QDG10Input*/
		
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
		let chatMem=SummarQuestion.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:(($ln==="CN")?(`你是一位专业的关键词提取助手。
- 任务：
1. 回顾对话历史数据${input.userContents} ，总结用户的核心需求主题
2. 结合当前输入的 ${input.search} 内容，提炼一个精准关键词

- 关联性判断：
1. 如果对话历史与当前输入语义相关，则融合生成关键词
2. 如果对话历史与当前输入完全无关，则仅以当前输入生成关键词，忽略历史

- 要求：
1. 关键词长度控制在2-10个字
2. 优先使用名词或名词短语
3. 需准确反映用户意图
4. 当历史与当前输入无关时，关键词必须完全基于当前输入，不得混入历史内容

- 最终输出为 json 格式： { "keyword": "关键词" }

- 示例1（有关联）
1. 输入历史：["sparktts", "该模型部署的环境要求"] + 当前输入："这个模型的研发团队"
2. 输出：{"keyword": "sparktts研发团队"}

- 示例2（有关联）
1. 输入历史：["sparktts", "部署的环境要求"] + 当前输入："这个模型的研发团队"
2. 输出：{"keyword": "sparktts研发团队"}

- 示例3（无关联）
1. 输入历史：["sparktts", "模型部署环境"] + 当前输入："今天天气怎么样"
2. 输出：{"keyword": "今日天气"}

- 示例4（无关联）
1. 输入历史：["python教程", "数据分析"] + 当前输入："北京旅游景点推荐"
2. 输出：{"keyword": "北京旅游景点"}
`

):(`You are a professional keyword extraction assistant.

- Task:
1. Review the conversation history data ${input.userContents} and summarize the user's core needs and themes
2. Combine with the current input ${input.search} to refine a precise keyword


- Relevance Judgment:
1. If the conversation history and current input are semantically related, fuse them to generate the keyword
2. If the conversation history and current input are completely unrelated, generate the keyword based solely on the current input, ignoring the history

- Requirements:
1. Keyword length should be controlled within 2-10 characters 2. Prioritize using nouns or noun phrases
3. Must accurately reflect user intent
4. When history and current input are unrelated, the keyword must be based entirely on the current input without mixing in historical content

- Final output in JSON format: { "keyword": "keyword" }

- Example 1 (Related)
1. Input history: ["sparktts", "environment requirements for deploying this model"] + Current input: "the R&D team of this model"
2. Output: {"keyword": "sparktts R&D team"}

- Example 2 (Related)
1. Input history: ["sparktts", "deployment environment requirements"] + Current input: "the R&D team of this model"
2. Output: {"keyword": "sparktts R&D team"}

- Example 3 (Unrelated)
1. Input history: ["sparktts", "model deployment environment"] + Current input: "how is the weather today"
2. Output: {"keyword": "today's weather"}

- Example 4 (Unrelated)
1. Input history: ["python tutorial", "data analysis"] + Current input: "Beijing tourist attractions recommendation"
2. Output: {"keyword": "Beijing tourist attractions"}
`))},
		];
		messages.push(...chatMem);
		/*#{1JH04QDG10PrePrompt*/
		/*}#1JH04QDG10PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1JH04QDG10FilterMessage*/
			/*}#1JH04QDG10FilterMessage*/
			messages.push(msg);
		}
		/*#{1JH04QDG10PreCall*/
		/*}#1JH04QDG10PreCall*/
		if($agent){
			result=(result===undefined)?(await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat})):result;
		}else{
			result=(result===null)?(await session.callSegLLM("SummarQuestion@"+agentURL,opts,messages,true)):result;
		}
		/*#{1JH04QDG10PostLLM*/
		/*}#1JH04QDG10PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1JH04QDG10PostClear*/
			/*}#1JH04QDG10PostClear*/
		}
		result=trimJSON(result);
		/*#{1JH04QDG10PostCall*/
		result = {
			search: result.keyword,
			searchNum: input.searchNum > 20 ? 20 : input.searchNum,
			platforms: (context.platforms && context.platforms.length) ? context.platforms : []
		};
		/*}#1JH04QDG10PostCall*/
		/*#{1JH04QDG10PreResult*/
		/*}#1JH04QDG10PreResult*/
		return {seg:RPA,result:(result),preSeg:"1JH04QDG10",outlet:"1JH04RCTC0"};
	};
	SummarQuestion.jaxId="1JH04QDG10"
	SummarQuestion.url="SummarQuestion@"+agentURL
	SummarQuestion.messages=[];
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"AnySearchWorkflow",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{searchNum,modelName}*/){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN90PreEntry*/
			/*}#1HDBOSUN90PreEntry*/
			result={seg:fixargs,"input":input};
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
//#CodyExport<<<
/*#{1HDBOSUN90PostDoc*/
/*}#1HDBOSUN90PostDoc*/


export default AnySearchWorkflow;
export{AnySearchWorkflow};
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
//		"entry": "fixargs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH2869AD0",
//			"attrs": {
//				"searchNum": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JCFV56QH1",
//					"attrs": {
//						"type": "Number",
//						"mockup": "5",
//						"desc": ""
//					}
//				},
//				"modelName": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JFD8OKV00",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1HDBOSUNA3",
//			"attrs": {
//				"history": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC5JTNC40",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"externalQuestion": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC63VE0S0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"rpaResult": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC68NP0S0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"rpaHistory": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC81QT9L0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"allLinks": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JC8NSHEJ0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"platforms": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JD7JAIBU0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "[]",
//						"desc": ""
//					}
//				},
//				"modelInfo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGGK6DR20",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
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
//					"def": "fixArgs",
//					"jaxId": "1JCFV0B9G0",
//					"attrs": {
//						"id": "fixargs",
//						"viewName": "",
//						"label": "",
//						"x": "100",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1JCFV0GPE0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSGBHTU0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JFSGBHTU0",
//					"attrs": {
//						"id": "DefaultWaitTips",
//						"viewName": "",
//						"label": "",
//						"x": "280",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFSGBHTU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFSGBHTU2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Fetching model information, please wait......",
//							"localize": {
//								"EN": "Fetching model information, please wait......",
//								"CN": "正在为您获取模型信息，请稍候......"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JFSGBHTV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSFTQFT0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "webCall",
//					"jaxId": "1JFSFTQFT0",
//					"attrs": {
//						"id": "DefaultCallAPI",
//						"viewName": "",
//						"label": "",
//						"x": "520",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFSFTQFT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFSFTQFT2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"url": "http://ec2-54-234-128-29.compute-1.amazonaws.com:8000/qa",
//						"method": "POST",
//						"argMode": "JOSN",
//						"format": "JOSN",
//						"args": {
//							"jaxId": "1JFSFTQFT3",
//							"attrs": {
//								"query": {
//									"type": "string",
//									"valText": "#context.modelInfo"
//								},
//								"history": {
//									"type": "auto",
//									"valText": "[]"
//								}
//							}
//						},
//						"text": "",
//						"timeout": "30000",
//						"headers": {
//							"jaxId": "1JFSFTQFT4",
//							"attrs": {}
//						},
//						"outlet": {
//							"jaxId": "1JFSFTQFT5",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSG88KP0"
//						}
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JFSG88KP0",
//					"attrs": {
//						"id": "ShowDefaultCallAPIRes",
//						"viewName": "",
//						"label": "",
//						"x": "755",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFSG88KP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFSG88KP2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.answer",
//						"outlet": {
//							"jaxId": "1JFSG88KP3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSGHND40"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JFSGHND40",
//					"attrs": {
//						"id": "InitAskUser",
//						"viewName": "",
//						"label": "",
//						"x": "1000",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFSGHND41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFSGHND42",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "What else would you like to know about this model?",
//							"localize": {
//								"EN": "What else would you like to know about this model?",
//								"CN": "你还想了解此模型的哪些信息？"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JFSGHND43",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSH6HBQ0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1JFSH6HBQ0",
//					"attrs": {
//						"id": "DefaultUserType",
//						"viewName": "",
//						"label": "",
//						"x": "1220",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFSH6HBQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFSH6HBQ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"allowEmpty": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1JFSH6HBQ3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSH8ALP0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JFSH8ALP0",
//					"attrs": {
//						"id": "DefaultSearchWaitTips",
//						"viewName": "",
//						"label": "",
//						"x": "1475",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFSH8ALP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFSH8ALP2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Searching, please wait......",
//							"localize": {
//								"EN": "Searching, please wait......",
//								"CN": "好的，正在为您查询，请稍等......"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JFSH8ALP3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSHB9A70"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "webCall",
//					"jaxId": "1JFSHB9A70",
//					"attrs": {
//						"id": "CallInternalAPI",
//						"viewName": "",
//						"label": "",
//						"x": "1725",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFSHB9A80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFSHB9A81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"url": "http://ec2-54-234-128-29.compute-1.amazonaws.com:8000/qa",
//						"method": "POST",
//						"argMode": "JOSN",
//						"format": "JOSN",
//						"args": {
//							"jaxId": "1JFSHB9A82",
//							"attrs": {
//								"query": {
//									"type": "string",
//									"valText": "#input"
//								},
//								"history": {
//									"type": "auto",
//									"valText": "#context.history"
//								}
//							}
//						},
//						"text": "",
//						"timeout": "30000",
//						"headers": {
//							"jaxId": "1JFSHB9A83",
//							"attrs": {}
//						},
//						"outlet": {
//							"jaxId": "1JFSHB9A84",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSHITD60"
//						}
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JFSHITD60",
//					"attrs": {
//						"id": "ShowInternalAPIRes",
//						"viewName": "",
//						"label": "",
//						"x": "1960",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JFSHITD61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JFSHITD62",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.answer",
//						"outlet": {
//							"jaxId": "1JFSHITD63",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSHS8RU0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1JFSHQOST0",
//					"attrs": {
//						"id": "SelectQuestionWay",
//						"viewName": "",
//						"label": "",
//						"x": "100",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Continue asking or search online for more information?",
//							"localize": {
//								"EN": "Continue asking or search online for more information?",
//								"CN": "上述信息是否满足您的需求？如若不满足，您可按需联网搜索。"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1JFSHQOST1",
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
//									"jaxId": "1JFSHQOST2",
//									"attrs": {
//										"id": "Internal",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Continue asking",
//											"localize": {
//												"EN": "Continue asking",
//												"CN": "继续提问"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFSHQOST3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFSHQOST4",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JFSIFKH10"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JFSHQOST5",
//									"attrs": {
//										"id": "External",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Online search",
//											"localize": {
//												"EN": "Online search",
//												"CN": "联网搜索"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JFSHQOST6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JFSHQOST7",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JC63DF8F0"
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
//					"def": "output",
//					"jaxId": "1JC63DF8F0",
//					"attrs": {
//						"id": "AskUserQuestion",
//						"viewName": "",
//						"label": "",
//						"x": "380",
//						"y": "460",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC63DF8F1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC63DF8F2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "The AI is about to take control of the browser. Please enter your question.",
//							"localize": {
//								"EN": "The AI is about to take control of the browser. Please enter your question.",
//								"CN": "好的，AI 即将接管浏览器控制权限以执行联网搜索任务。请输入您的问题。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JC63DF8F3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC63DTVT0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1JC63DTVT0",
//					"attrs": {
//						"id": "UserTypeQuestion",
//						"viewName": "",
//						"label": "",
//						"x": "670",
//						"y": "460",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC63DTVT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC63DTVT2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"allowEmpty": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1JC63DTVT3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JH04QDG10"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1JC0JAE5K0",
//					"attrs": {
//						"id": "RPA",
//						"viewName": "",
//						"label": "",
//						"x": "1250",
//						"y": "460",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC0JAE5K1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC0JAE5K2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/RpaEntry.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1JC0JAE5K3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JD7E4EHN0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1JC62L42T0",
//					"attrs": {
//						"id": "IsReport",
//						"viewName": "",
//						"label": "",
//						"x": "2790",
//						"y": "445",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": " Would you like a detailed report generated?",
//							"localize": {
//								"EN": " Would you like a detailed report generated?",
//								"CN": "请确认上述信息是否满足您的需求，是否需要生成深度报告？"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JC62L42F0",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Generate Report",
//											"localize": {
//												"EN": "Generate Report",
//												"CN": "生成报告"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JC62OKQD0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC62OKQD1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JC68VSRG0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JC62L42F1",
//									"attrs": {
//										"id": "No",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Continue asking",
//											"localize": {
//												"EN": "Continue asking",
//												"CN": "继续提问"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JC62OKQD2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC62OKQD3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JD7IKO7D0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JC68VSRG0",
//					"attrs": {
//						"id": "WaitTips_1",
//						"viewName": "",
//						"label": "",
//						"x": "2995",
//						"y": "430",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC68VSRG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC68VSRG2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Generating report for you, please wait......",
//							"localize": {
//								"EN": "Generating report for you, please wait......",
//								"CN": "好的，正在为您生成报告，请稍等......"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JC68VSRG3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC8K0M8V0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JC8K0M8V0",
//					"attrs": {
//						"id": "AxiosCallRpaAPI",
//						"viewName": "",
//						"label": "",
//						"x": "3230",
//						"y": "430",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC8K0QBL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC8K0QBL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JC8K0QBC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JD2HUA490"
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
//					"jaxId": "1JD2HUA490",
//					"attrs": {
//						"id": "CheckError",
//						"viewName": "",
//						"label": "",
//						"x": "3495",
//						"y": "430",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "#input.errMsg",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JD2HVHB50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JD2HVHB51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JD2HVHAT1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JC8CQE880"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JD2I4PL50",
//									"attrs": {
//										"id": "Error",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JD2I69HO0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JD2I69HO1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.errMsg"
//									},
//									"linkedSeg": "1JD2IR51S0"
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
//					"jaxId": "1JD2IR51S0",
//					"attrs": {
//						"id": "ShowError",
//						"viewName": "",
//						"label": "",
//						"x": "3745",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JD2IU2LJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JD2IU2LJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.errMsg",
//						"outlet": {
//							"jaxId": "1JD2IU2L60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJ5TCJT0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JC676I5O0",
//					"attrs": {
//						"id": "GetAllLinks",
//						"viewName": "",
//						"label": "",
//						"x": "1630",
//						"y": "460",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC676TOS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC676TOS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JC676TOK0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JD2BIT1J0"
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
//					"jaxId": "1JC669FLS0",
//					"attrs": {
//						"id": "ShowAllLinks",
//						"viewName": "",
//						"label": "",
//						"x": "2555",
//						"y": "445",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JC66A45U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JC66A45U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "",
//						"outlet": {
//							"jaxId": "1JC66A45N0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC62L42T0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JC87DURT0",
//					"attrs": {
//						"id": "ContinueRPA",
//						"viewName": "",
//						"label": "",
//						"x": "3240",
//						"y": "530",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JC63DF8F0",
//						"outlet": {
//							"jaxId": "1JC87ETH40",
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
//					"def": "askConfirm",
//					"jaxId": "1JC8CQE880",
//					"attrs": {
//						"id": "FileType",
//						"viewName": "",
//						"label": "",
//						"x": "3745",
//						"y": "475",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Please select the report output format.",
//							"localize": {
//								"EN": "Please select the report output format.",
//								"CN": "请选择报告的输出形式。"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JC8CQE7L0",
//									"attrs": {
//										"id": "Markdwon",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Markdown Document",
//											"localize": {
//												"EN": "Markdown Document",
//												"CN": "Markdown 文档"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JC8CS49O0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC8CS49O1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									}
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JC8CQE7L1",
//									"attrs": {
//										"id": "Html",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Html Page",
//											"localize": {
//												"EN": "Html Page",
//												"CN": "Html 页面"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JC8CS49O2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JC8CS49O3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									}
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JD2BIT1J0",
//					"attrs": {
//						"id": "CheckLength",
//						"viewName": "",
//						"label": "",
//						"x": "1845",
//						"y": "460",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JD2BKP100",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JD2BKP101",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JD2BKP080",
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
//									"jaxId": "1JD2BKP070",
//									"attrs": {
//										"id": "HasData",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JD2BKP102",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JD2BKP103",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.length"
//									},
//									"linkedSeg": "1JD7C9HUJ0"
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
//					"jaxId": "1JD7C9HUJ0",
//					"attrs": {
//						"id": "SimpleReport",
//						"viewName": "",
//						"label": "",
//						"x": "2080",
//						"y": "445",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JD7CAI920",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JD7CAI921",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1",
//						"system": {
//							"type": "string",
//							"valText": "#`You are a professional content summarization AI assistant. - Task: Based on the user question \"${context.externalQuestion}\", extract all \"content\" fields from ${JSON.stringify(input,null,\"\\t\")} and summarize them, focusing on the core conclusion without expanding on details. The summary must not exceed 300 words, and please use english. - The final output should be in JSON format: { \"user\": \"${context.externalQuestion}\", \"assistant\": \"Generated summary content\" } `",
//							"localize": {
//								"EN": "#`You are a professional content summarization AI assistant. - Task: Based on the user question \"${context.externalQuestion}\", extract all \"content\" fields from ${JSON.stringify(input,null,\"\\t\")} and summarize them, focusing on the core conclusion without expanding on details. The summary must not exceed 300 words, and please use english. - The final output should be in JSON format: { \"user\": \"${context.externalQuestion}\", \"assistant\": \"Generated summary content\" } `",
//								"CN": "#`你是一位专业的内容总结 AI 助手。 - 任务：根据用户问题「${context.externalQuestion}」，仅提取 ${JSON.stringify(input,null,\"\\t\")} 中所有 \"content\" 字段并进行总结，务必突出核心结论，不展开细节， 总结内容不超过 300 字，用中文回答。 - 最终输出为 json 格式： { \"user\": \"${context.externalQuestion}\", \"assistant\": \"生成的总结内容\" } `"
//							},
//							"localizable": true
//						},
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
//							"jaxId": "1JD7CAI8T0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JD7DAEAQ0"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "50 messages",
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
//					"jaxId": "1JD7DAEAQ0",
//					"attrs": {
//						"id": "ShowSimpleReport",
//						"viewName": "",
//						"label": "",
//						"x": "2300",
//						"y": "445",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JD7DB3OS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JD7DB3OS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.assistant",
//						"outlet": {
//							"jaxId": "1JD7DB3OL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC669FLS0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JD7E4EHN0",
//					"attrs": {
//						"id": "WaitInfo",
//						"viewName": "",
//						"label": "",
//						"x": "1435",
//						"y": "460",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JD7E7CFG0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JD7E7CFG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Summarizing search results for you, please wait......",
//							"localize": {
//								"EN": "Summarizing search results for you, please wait......",
//								"CN": "正在为您总结搜索结果，请稍等......"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JD7E7CF90",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC676I5O0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1JD7IKO7D0",
//					"attrs": {
//						"id": "ConfirmAgain",
//						"viewName": "",
//						"label": "",
//						"x": "2995",
//						"y": "545",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Do you need to reselect the search platform?",
//							"localize": {
//								"EN": "Do you need to reselect the search platform?",
//								"CN": "是否需要重新选择搜索平台？"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JD7IKO6O0",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Need",
//											"localize": {
//												"EN": "Need",
//												"CN": "需要"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JD7ILLKN0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JD7ILLKN1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JC87DURT0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JD7IKO6O1",
//									"attrs": {
//										"id": "No",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Not needed",
//											"localize": {
//												"EN": "Not needed",
//												"CN": "不需要"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JD7ILLKN2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JD7ILLKN3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JD7J7B7O0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JD7J7B7O0",
//					"attrs": {
//						"id": "ShowSelectedPlatform",
//						"viewName": "",
//						"label": "",
//						"x": "3240",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JD7J8EB40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JD7J8EB41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "#`We will continue to use the ${JSON.stringify(context.platforms,null,\"\\t\")} platforms for the search. `",
//							"localize": {
//								"EN": "#`We will continue to use the ${JSON.stringify(context.platforms,null,\"\\t\")} platforms for the search. `",
//								"CN": "#`好的，我们将继续使用 ${JSON.stringify(context.platforms,null,\"\\t\")} 平台进行搜索。`"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JD7J8EAT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JD9NAKND0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JD9NAKND0",
//					"attrs": {
//						"id": "ContinueRPA_1",
//						"viewName": "",
//						"label": "",
//						"x": "3495",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JC63DF8F0",
//						"outlet": {
//							"jaxId": "1JD9NAKND1",
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
//					"def": "connector",
//					"jaxId": "1JFSHS8RU0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2150",
//						"y": "315",
//						"outlet": {
//							"jaxId": "1JFSHTC660",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSHSDCM0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JFSHSDCM0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "130",
//						"y": "315",
//						"outlet": {
//							"jaxId": "1JFSHTC661",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JFSHQOST0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JFSIFKH10",
//					"attrs": {
//						"id": "ContinueAsk_2",
//						"viewName": "",
//						"label": "",
//						"x": "380",
//						"y": "390",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JFSGHND40",
//						"outlet": {
//							"jaxId": "1JFSIFKH20",
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
//					"def": "askConfirm",
//					"jaxId": "1JGJ5TCJT0",
//					"attrs": {
//						"id": "Retry",
//						"viewName": "",
//						"label": "",
//						"x": "3965",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Try again?",
//							"localize": {
//								"EN": "Try again?",
//								"CN": "是否再尝试一次？"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JGJ5TCJ80",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Yes",
//											"localize": {
//												"EN": "Yes",
//												"CN": "是"
//											},
//											"localizable": true
//										},
//										"result": "#input.web_search_result",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGJ5U0VU0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGJ5U0VU1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JGJ7KERC0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JGJ5TCJ81",
//									"attrs": {
//										"id": "No",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "No",
//											"localize": {
//												"EN": "No",
//												"CN": "否"
//											},
//											"localizable": true
//										},
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGJ5U0VU2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGJ5U0VU3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JGJ7OET60"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JGJ6QMPL0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "4285",
//						"y": "290",
//						"outlet": {
//							"jaxId": "1JGJ6VLIE0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJ6R44P0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1JGJ6R44P0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3255",
//						"y": "290",
//						"outlet": {
//							"jaxId": "1JGJ6VLIE1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC8K0M8V0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JGJ7KERC0",
//					"attrs": {
//						"id": "RetryTips",
//						"viewName": "",
//						"label": "",
//						"x": "4145",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGJ7KERC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGJ7KERD0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Generating report for you, please wait......",
//							"localize": {
//								"EN": "Generating report for you, please wait......",
//								"CN": "好的，正在为您生成报告，请稍等......"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JGJ7KERD1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGJ6QMPL0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JGJ7OET60",
//					"attrs": {
//						"id": "ShowRetryError",
//						"viewName": "",
//						"label": "",
//						"x": "4145",
//						"y": "425",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGJ7OET61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGJ7OET62",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "The current task has been terminated due to an unstable VPN connection. Please check your network environment and try again, or contact technical support for assistance.",
//							"localize": {
//								"EN": "The current task has been terminated due to an unstable VPN connection. Please check your network environment and try again, or contact technical support for assistance.",
//								"CN": "当前任务因 VPN 连接不稳定已终止。请检查网络环境后重新尝试，或联系技术支持获取帮助。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JGJ7OET70",
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
//					"jaxId": "1JH04QDG10",
//					"attrs": {
//						"id": "SummarQuestion",
//						"viewName": "",
//						"label": "",
//						"x": "945",
//						"y": "460",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH04RCTN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH04RCTN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1",
//						"system": {
//							"type": "string",
//							"valText": "#`You are a professional keyword extraction assistant.\n\n- Task:\n1. Review the conversation history data ${input.userContents} and summarize the user's core needs and themes\n2. Combine with the current input ${input.search} to refine a precise keyword\n\n\n- Relevance Judgment:\n1. If the conversation history and current input are semantically related, fuse them to generate the keyword\n2. If the conversation history and current input are completely unrelated, generate the keyword based solely on the current input, ignoring the history\n\n- Requirements:\n1. Keyword length should be controlled within 2-10 characters 2. Prioritize using nouns or noun phrases\n3. Must accurately reflect user intent\n4. When history and current input are unrelated, the keyword must be based entirely on the current input without mixing in historical content\n\n- Final output in JSON format: { \"keyword\": \"keyword\" }\n\n- Example 1 (Related)\n1. Input history: [\"sparktts\", \"environment requirements for deploying this model\"] + Current input: \"the R&D team of this model\"\n2. Output: {\"keyword\": \"sparktts R&D team\"}\n\n- Example 2 (Related)\n1. Input history: [\"sparktts\", \"deployment environment requirements\"] + Current input: \"the R&D team of this model\"\n2. Output: {\"keyword\": \"sparktts R&D team\"}\n\n- Example 3 (Unrelated)\n1. Input history: [\"sparktts\", \"model deployment environment\"] + Current input: \"how is the weather today\"\n2. Output: {\"keyword\": \"today's weather\"}\n\n- Example 4 (Unrelated)\n1. Input history: [\"python tutorial\", \"data analysis\"] + Current input: \"Beijing tourist attractions recommendation\"\n2. Output: {\"keyword\": \"Beijing tourist attractions\"}\n`",
//							"localize": {
//								"EN": "#`You are a professional keyword extraction assistant.\n\n- Task:\n1. Review the conversation history data ${input.userContents} and summarize the user's core needs and themes\n2. Combine with the current input ${input.search} to refine a precise keyword\n\n\n- Relevance Judgment:\n1. If the conversation history and current input are semantically related, fuse them to generate the keyword\n2. If the conversation history and current input are completely unrelated, generate the keyword based solely on the current input, ignoring the history\n\n- Requirements:\n1. Keyword length should be controlled within 2-10 characters 2. Prioritize using nouns or noun phrases\n3. Must accurately reflect user intent\n4. When history and current input are unrelated, the keyword must be based entirely on the current input without mixing in historical content\n\n- Final output in JSON format: { \"keyword\": \"keyword\" }\n\n- Example 1 (Related)\n1. Input history: [\"sparktts\", \"environment requirements for deploying this model\"] + Current input: \"the R&D team of this model\"\n2. Output: {\"keyword\": \"sparktts R&D team\"}\n\n- Example 2 (Related)\n1. Input history: [\"sparktts\", \"deployment environment requirements\"] + Current input: \"the R&D team of this model\"\n2. Output: {\"keyword\": \"sparktts R&D team\"}\n\n- Example 3 (Unrelated)\n1. Input history: [\"sparktts\", \"model deployment environment\"] + Current input: \"how is the weather today\"\n2. Output: {\"keyword\": \"today's weather\"}\n\n- Example 4 (Unrelated)\n1. Input history: [\"python tutorial\", \"data analysis\"] + Current input: \"Beijing tourist attractions recommendation\"\n2. Output: {\"keyword\": \"Beijing tourist attractions\"}\n`",
//								"CN": "#`你是一位专业的关键词提取助手。\n- 任务：\n1. 回顾对话历史数据${input.userContents} ，总结用户的核心需求主题\n2. 结合当前输入的 ${input.search} 内容，提炼一个精准关键词\n\n- 关联性判断：\n1. 如果对话历史与当前输入语义相关，则融合生成关键词\n2. 如果对话历史与当前输入完全无关，则仅以当前输入生成关键词，忽略历史\n\n- 要求：\n1. 关键词长度控制在2-10个字\n2. 优先使用名词或名词短语\n3. 需准确反映用户意图\n4. 当历史与当前输入无关时，关键词必须完全基于当前输入，不得混入历史内容\n\n- 最终输出为 json 格式： { \"keyword\": \"关键词\" }\n\n- 示例1（有关联）\n1. 输入历史：[\"sparktts\", \"该模型部署的环境要求\"] + 当前输入：\"这个模型的研发团队\"\n2. 输出：{\"keyword\": \"sparktts研发团队\"}\n\n- 示例2（有关联）\n1. 输入历史：[\"sparktts\", \"部署的环境要求\"] + 当前输入：\"这个模型的研发团队\"\n2. 输出：{\"keyword\": \"sparktts研发团队\"}\n\n- 示例3（无关联）\n1. 输入历史：[\"sparktts\", \"模型部署环境\"] + 当前输入：\"今天天气怎么样\"\n2. 输出：{\"keyword\": \"今日天气\"}\n\n- 示例4（无关联）\n1. 输入历史：[\"python教程\", \"数据分析\"] + 当前输入：\"北京旅游景点推荐\"\n2. 输出：{\"keyword\": \"北京旅游景点\"}\n`\n\n"
//							},
//							"localizable": true
//						},
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
//							"jaxId": "1JH04RCTC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JC0JAE5K0"
//						},
//						"stream": "true",
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "50 messages",
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
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}