//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IN8IJT7O0MoreImports*/
import {webFetch,tabNT} from "/@tabos";
/*}#1IN8IJT7O0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"userPrompt":{
			"name":"userPrompt","type":"string",
			"defaultValue":"",
			"desc":"用户对要编写的HTML页面的需求描述",
		},
		"autoFix":{
			"name":"autoFix","type":"bool",
			"required":false,
			"defaultValue":true,
			"desc":"如果出现错误，是否自动修正重新编写代码",
		},
		"userCheck":{
			"name":"userCheck","type":"bool",
			"required":false,
			"defaultValue":true,
			"desc":"是否需要用户确认页面结果，给出修改建议",
		},
		"blueprintImage":{
			"name":"blueprintImage","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"页面参考设计图的URL",
		},
		"baseHtmlUrl":{
			"name":"baseHtmlUrl","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"如果存在，从初始参数中提取的初始HTML的URL",
		}
	},
	/*#{1IN8IJT7O0ArgsView*/
	/*}#1IN8IJT7O0ArgsView*/
};

/*#{1IN8IJT7O0StartDoc*/
/*}#1IN8IJT7O0StartDoc*/
//----------------------------------------------------------------------------
let CodeSingleHtml=async function(session){
	let userPrompt,autoFix,userCheck,blueprintImage,baseHtmlUrl;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,WriteHtml,ShowPage,CheckError,Finish,CheckFix,Failed,CheckChat,AskChat,ShowError,AIRetry,CheckUser,AskFin,AskFix,JumpFix,CheckSnap,FixWithSnap,ShowCode;
	let fixRound=0;
	let takeSnap=null;
	let fixPrompt="";
	let fixError=false;
	let htmlCode="";
	let codeMessages=[];
	let imageMessages=[];
	
	/*#{1IN8IJT7O0LocalVals*/
	/*}#1IN8IJT7O0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			userPrompt=input.userPrompt;
			autoFix=input.autoFix;
			userCheck=input.userCheck;
			blueprintImage=input.blueprintImage;
			baseHtmlUrl=input.baseHtmlUrl;
		}else{
			userPrompt=undefined;
			autoFix=undefined;
			userCheck=undefined;
			blueprintImage=undefined;
			baseHtmlUrl=undefined;
		}
		/*#{1IN8IJT7O0ParseArgs*/
		/*}#1IN8IJT7O0ParseArgs*/
	}
	
	/*#{1IN8IJT7O0PreContext*/
	/*}#1IN8IJT7O0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IN8IJT7O0PostContext*/
	/*}#1IN8IJT7O0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IN8IO9UM0
		let result=input;
		let missing=false;
		let smartAsk=false;
		/*#{1IN8IO9UM0PreCodes*/
		/*}#1IN8IO9UM0PreCodes*/
		if(userPrompt===undefined || userPrompt==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@aichat/ai/CompleteArgs.js",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		/*#{1IN8IO9UM0PostCodes*/
		if(blueprintImage){
			result={prompt:userPrompt+"\n\n图片为页面参考图。",assets:[blueprintImage]};
		}else{
			result=userPrompt;
		}
		if(baseHtmlUrl){
			let code,data;
			if(baseHtmlUrl.startsWith("hub://")){
				try{
					data=await session.loadHubFile(baseHtmlUrl);
					data=Base64.decodeBytes(data);
					const decoder = new TextDecoder('utf-8');
					htmlCode=decoder.decode(data)||"";
				}catch(err){
					//TODO: Notify read failed.
					htmlCode="";
				}
			}else{
				try{
					code=await (await webFetch(baseHtmlUrl)).text();
					htmlCode=code||"";
				}catch(err){
					//TODO: Notify read failed.
					htmlCode="";
				}
			}
		}
		/*}#1IN8IO9UM0PostCodes*/
		return {seg:WriteHtml,result:(result),preSeg:"1IN8IO9UM0",outlet:"1IN8IPUBH0"};
	};
	FixArgs.jaxId="1IN8IO9UM0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["WriteHtml"]=WriteHtml=async function(input){//:1IN8IQMJ40
		let prompt;
		let result=null;
		/*#{1IN8IQMJ40Input*/
		/*}#1IN8IQMJ40Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1",
			maxToken:16000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=WriteHtml.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
- - -
## 角色
你是一个根据用户需求，编写（包括调试/修正）简单的HTML页面的AI智能体。
- - -
## 对话
- 第一轮对话，用户会给出当前的HTML代码；你要编写的HTML文件的需求描述，可能还会包含页面设计的参考图。
- 之后的对话，用户会给出当前的HTML代码；当前的HTML代码的执行情况；还可能给出修改建议；或者回答你提出的问题。
- 你根据当前对话过程，用JSON回复用户
    - 如果你可以根据当前掌握信息可以输出HTML，请在JSON中的"html"属性中提供完整的HTML页面代码（包括必须的CSS/JS以及引用的外部脚本等）。例如：
    \`\`\`
    {
    	"html":"<html>...</html>"
    }
    \`\`\`
    
    - 如果你缺少必要的信息来生成HTML，请在JSON的"chat"属性中向用户提出问题或与用户对话完善编写网页所需的信息。例如：
    \`\`\`
    {
    	"chat":"请提供调用天气API的Key。"
    }
    \`\`\`
## 回复JSON对象属性
- "html" {string}: 你生成的HTML页面代码，注意一定是完整的HTML页面代码（包括必须的CSS/JS以及引用的外部脚本等）。
- "chat" {string}: 为了完善必要的信息或回答用户的疑问，与用户的对话信息。
`},
		];
		messages.push(...chatMem);
		/*#{1IN8IQMJ40PrePrompt*/
		/*}#1IN8IQMJ40PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IN8IQMJ40FilterMessage*/
			let assets=input.assets;
			if(assets){
				let content;
				prompt=input.prompt||prompt;
				content=[{type:"text",text:prompt}];
				for(let url of assets){
					if(url.startsWith("hub://")){
						url=await session.normURL(url);
					}
					content.push({type:"image_url","image_url":{"url":url}});
				}
				msg={role:"user",content:content};
			}
			//Push current html into messages:
			messages.push({role:"user",content:`当前HTML代码: \n\`\`\`\n${htmlCode?htmlCode:"无"}\n\`\`\`\n`});
			/*}#1IN8IQMJ40FilterMessage*/
			messages.push(msg);
		}
		/*#{1IN8IQMJ40PreCall*/
		/*}#1IN8IQMJ40PreCall*/
		result=(result===null)?(await session.callSegLLM("WriteHtml@"+agentURL,opts,messages,true)):result;
		/*#{1IN8IQMJ40PostLLM*/
		/*}#1IN8IQMJ40PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1IN8IQMJ40PostClear*/
			/*}#1IN8IQMJ40PostClear*/
		}
		result=trimJSON(result);
		/*#{1IN8IQMJ40PostCall*/
		let m1;
		m1=chatMem[chatMem.length-1];
		if(result.html){
			m1.content=`{"html":"<html>...</html>"}`;
			/*codeMessages.push(m1);
			if(codeMessages.length>3){
				m1=codeMessages.shift();
				m1.content=JSON.stringify({html:"<html>...</html>"});
			}*/
		}
		/*}#1IN8IQMJ40PostCall*/
		return {seg:CheckChat,result:(result),preSeg:"1IN8IQMJ40",outlet:"1IN8IRUKR0"};
	};
	WriteHtml.jaxId="1IN8IQMJ40"
	WriteHtml.url="WriteHtml@"+agentURL
	WriteHtml.messages=[];
	
	segs["ShowPage"]=ShowPage=async function(input){//:1IN8IRLCC0
		let result=input
		/*#{1IN8IRLCC0Code*/
		htmlCode=input.html;
		result=session.WSCall_WebSandbox(htmlCode);
		/*}#1IN8IRLCC0Code*/
		return {seg:CheckError,result:(result),preSeg:"1IN8IRLCC0",outlet:"1IN8IRUKR1"};
	};
	ShowPage.jaxId="1IN8IRLCC0"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["CheckError"]=CheckError=async function(input){//:1IN8ISD9N0
		let result=input;
		/*#{1IN8ISD9N0Start*/
		/*}#1IN8ISD9N0Start*/
		if(input.error){
			let output=input;
			/*#{1IN8ITC8S0Codes*/
			fixError=true;
			/*}#1IN8ITC8S0Codes*/
			return {seg:ShowError,result:(output),preSeg:"1IN8ISD9N0",outlet:"1IN8ITC8S0"};
		}
		/*#{1IN8ISD9N0Post*/
		fixError=false;
		/*}#1IN8ISD9N0Post*/
		return {seg:CheckUser,result:(result),preSeg:"1IN8ISD9N0",outlet:"1IN8ITC8S1"};
	};
	CheckError.jaxId="1IN8ISD9N0"
	CheckError.url="CheckError@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1IN8IT5CG0
		let result=input
		/*#{1IN8IT5CG0Code*/
		//Save file to hub:
		let codeData,hubFileName;
		codeData=Base64.encode(htmlCode);
		hubFileName=session.saveHubFile("sandbox.html",codeData);
		result={result:"Finish",content:"Sandbox page finished with: "+JSON.stringify(input.result)};
		/*}#1IN8IT5CG0Code*/
		return {result:result};
	};
	Finish.jaxId="1IN8IT5CG0"
	Finish.url="Finish@"+agentURL
	
	segs["CheckFix"]=CheckFix=async function(input){//:1IN8ITQN40
		let result=input;
		/*#{1IN8ITQN40Start*/
		/*}#1IN8ITQN40Start*/
		if(!!autoFix && fixRound<5){
			/*#{1IN8IV1BK0Codes*/
			fixRound=fixRound>0?fixRound+1:1;
			fixPrompt=`页面加载/执行任务出错：${input.error}。\n\n执行日志为：\n- - -\n${input.logs.join("\n\n")}。\n- - -\n请分析错误，参考日志，修正你的页面代码。`;
			/*}#1IN8IV1BK0Codes*/
			return {seg:JumpFix,result:(input),preSeg:"1IN8ITQN40",outlet:"1IN8IV1BK0"};
		}
		/*#{1IN8ITQN40Post*/
		/*}#1IN8ITQN40Post*/
		return {seg:Failed,result:(result),preSeg:"1IN8ITQN40",outlet:"1IN8IV1BK1"};
	};
	CheckFix.jaxId="1IN8ITQN40"
	CheckFix.url="CheckFix@"+agentURL
	
	segs["Failed"]=Failed=async function(input){//:1IN8IVBEC0
		let result=input
		/*#{1IN8IVBEC0Code*/
		result={result:"Failed",content:`经过多次尝试，未能写出符合要求的页面。\n\n最后一次尝试报错：${input.error}\n\n最后一次尝试的日志:\n\n- - -\n\n${input.logs.join("\n\n")}\n- - -\n`}
		/*}#1IN8IVBEC0Code*/
		return {result:result};
	};
	Failed.jaxId="1IN8IVBEC0"
	Failed.url="Failed@"+agentURL
	
	segs["CheckChat"]=CheckChat=async function(input){//:1IN8LTP420
		let result=input;
		if(input.chat){
			let output=input;
			return {seg:AskChat,result:(output),preSeg:"1IN8LTP420",outlet:"1IN8M0H2J0"};
		}
		if(input.html){
			let output=input;
			return {seg:ShowCode,result:(output),preSeg:"1IN8LTP420",outlet:"1IN8OUBKG0"};
		}
		return {seg:AIRetry,result:(result),preSeg:"1IN8LTP420",outlet:"1IN8M0H2J1"};
	};
	CheckChat.jaxId="1IN8LTP420"
	CheckChat.url="CheckChat@"+agentURL
	
	segs["AskChat"]=AskChat=async function(input){//:1IN8LVSMB0
		let tip=(input.chat);
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		if(askUpward && tip){
			result=await session.askUpward($agent,tip);
		}else{
			if(tip){
				session.addChatText(tipRole,tip);
			}
			result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		}
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		return {seg:WriteHtml,result:(result),preSeg:"1IN8LVSMB0",outlet:"1IN8M0H2K1"};
	};
	AskChat.jaxId="1IN8LVSMB0"
	AskChat.url="AskChat@"+agentURL
	
	segs["ShowError"]=ShowError=async function(input){//:1IN8O2EUH0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=`发现页面错误：${input.error}`;
		session.addChatText(role,content,opts);
		return {seg:CheckFix,result:(result),preSeg:"1IN8O2EUH0",outlet:"1IN8O4TMV0"};
	};
	ShowError.jaxId="1IN8O2EUH0"
	ShowError.url="ShowError@"+agentURL
	
	segs["AIRetry"]=AIRetry=async function(input){//:1IN8OVA0P0
		let result=input
		/*#{1IN8OVA0P0Code*/
		/*}#1IN8OVA0P0Code*/
		return {seg:WriteHtml,result:(result),preSeg:"1IN8OVA0P0",outlet:"1IN8P0G350"};
	};
	AIRetry.jaxId="1IN8OVA0P0"
	AIRetry.url="AIRetry@"+agentURL
	
	segs["CheckUser"]=CheckUser=async function(input){//:1INAM9HB70
		let result=input;
		if(!userCheck){
			return {seg:Finish,result:(input),preSeg:"1INAM9HB70",outlet:"1INAMGQAV0"};
		}
		return {seg:AskFin,result:(result),preSeg:"1INAM9HB70",outlet:"1INAMGQAV1"};
	};
	CheckUser.jaxId="1INAM9HB70"
	CheckUser.url="CheckUser@"+agentURL
	
	segs["AskFin"]=AskFin=async function(input){//:1INAMBT8D0
		let prompt=("当前页面是否符合你的要求？")||input;
		let countdown=false;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("是的，页面符合我的要求"):("Yes, the page meets my requirements")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("不，还需要修改"):("No, further modifications are required")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result=input;
			return {seg:Finish,result:(result),preSeg:"1INAMBT8D0",outlet:"1INAMBT7P0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			result=(input);
			return {seg:Finish,result:(result),preSeg:"1INAMBT8D0",outlet:"1INAMBT7P0"};
		}else if(item.code===1){
			return {seg:AskFix,result:(result),preSeg:"1INAMBT8D0",outlet:"1INAMBT7P1"};
		}
		return {result:result};
	};
	AskFin.jaxId="1INAMBT8D0"
	AskFin.url="AskFin@"+agentURL
	
	segs["AskFix"]=AskFix=async function(input){//:1INAMHF8T0
		let tip=((($ln==="CN")?("请输入修改指导"):("请输入修改指导")));
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		/*#{1INAMHF8T0PreCodes*/
		/*}#1INAMHF8T0PreCodes*/
		if(askUpward && tip){
			result=await session.askUpward($agent,tip);
		}else{
			if(tip){
				session.addChatText(tipRole,tip);
			}
			result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		}
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		/*#{1INAMHF8T0PostCodes*/
		fixPrompt=result;
		/*}#1INAMHF8T0PostCodes*/
		return {seg:CheckSnap,result:(result),preSeg:"1INAMHF8T0",outlet:"1INAMJOSQ0"};
	};
	AskFix.jaxId="1INAMHF8T0"
	AskFix.url="AskFix@"+agentURL
	
	segs["JumpFix"]=JumpFix=async function(input){//:1INB7152P0
		let result=input;
		return {seg:CheckSnap,result:result,preSeg:"1INB73H7L0",outlet:"1INB71BCQ0"};
	
	};
	JumpFix.jaxId="1INB73H7L0"
	JumpFix.url="JumpFix@"+agentURL
	
	segs["CheckSnap"]=CheckSnap=async function(input){//:1INB73H7L0
		let result=input;
		/*#{1INB73H7L0Start*/
		/*}#1INB73H7L0Start*/
		if(input.assets){
			return {seg:FixWithSnap,result:(input),preSeg:"1INB73H7L0",outlet:"1INB75NS10"};
		}
		/*#{1INB73H7L0Post*/
		if(fixError){
			result=fixPrompt;
		}else{
			result=`用户提出修改意见：${fixPrompt}。\n\n请根据用户的修改意见修改页面代码。`;
		}
		/*}#1INB73H7L0Post*/
		return {seg:WriteHtml,result:(result),preSeg:"1INB73H7L0",outlet:"1INBU07R41"};
	};
	CheckSnap.jaxId="1INB73H7L0"
	CheckSnap.url="CheckSnap@"+agentURL
	
	segs["FixWithSnap"]=FixWithSnap=async function(input){//:1INB7MLCQ0
		let result=input
		/*#{1INB7MLCQ0Code*/
		result.prompt=`用户提出修改意见：${input.prompt}。\n\n请根据用户的修改意见以及当前的页面截图修改页面代码。`
		/*}#1INB7MLCQ0Code*/
		return {seg:WriteHtml,result:(result),preSeg:"1INB7MLCQ0",outlet:"1INBU07R50"};
	};
	FixWithSnap.jaxId="1INB7MLCQ0"
	FixWithSnap.url="FixWithSnap@"+agentURL
	
	segs["ShowCode"]=ShowCode=async function(input){//:1INCMVE120
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=`
\`\`\`
${input.html}
\`\`\`
`;
		session.addChatText(role,content,opts);
		return {seg:ShowPage,result:(result),preSeg:"1INCMVE120",outlet:"1INCN08RS0"};
	};
	ShowCode.jaxId="1INCMVE120"
	ShowCode.url="ShowCode@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CodeSingleHtml",
		url:agentURL,
		autoStart:true,
		jaxId:"1IN8IJT7O0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{userPrompt,autoFix,userCheck,blueprintImage,baseHtmlUrl}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IN8IJT7O0PreEntry*/
			/*}#1IN8IJT7O0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IN8IJT7O0PostEntry*/
			/*}#1IN8IJT7O0PostEntry*/
			return result;
		},
		/*#{1IN8IJT7O0MoreAgentAttrs*/
		/*}#1IN8IJT7O0MoreAgentAttrs*/
	};
	/*#{1IN8IJT7O0PostAgent*/
	/*}#1IN8IJT7O0PostAgent*/
	return agent;
};
/*#{1IN8IJT7O0ExCodes*/
/*}#1IN8IJT7O0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "CodeSingleHtml",
		description: "这是根据用户需求，编写一个简单的HTML页面，通过沙箱展示给用户的智能体。请提供需求以及可用资源。\n",
		parameters:{
			type: "object",
			properties:{
				userPrompt:{type:"string",description:"用户对要编写的HTML页面的需求描述"},
				autoFix:{type:"bool",description:"如果出现错误，是否自动修正重新编写代码"},
				userCheck:{type:"bool",description:"是否需要用户确认页面结果，给出修改建议"},
				blueprintImage:{type:"string",description:"页面参考设计图的URL"},
				baseHtmlUrl:{type:"string",description:"如果存在，从初始参数中提取的初始HTML的URL"}
			}
		}
	},
	label: "{\"CN\":\"编写简单网页\",\"EN\":\"Create simple web page\"}",
	chatEntry: "Tool",
	icon: "edlit.svg",
	agent: CodeSingleHtml
}];

//:Export Edit-AddOn:
const DocAIAgentExporter=VFACT?VFACT.classRegs.DocAIAgentExporter:null;
if(DocAIAgentExporter){
	const EditAttr=VFACT.classRegs.EditAttr;
	const EditAISeg=VFACT.classRegs.EditAISeg;
	const EditAISegOutlet=VFACT.classRegs.EditAISegOutlet;
	const SegObjShellAttr=EditAISeg.SegObjShellAttr;
	const SegOutletDef=EditAISegOutlet.SegOutletDef;
	const docAIAgentExporter=DocAIAgentExporter.prototype;
	const packExtraCodes=docAIAgentExporter.packExtraCodes;
	const packResult=docAIAgentExporter.packResult;
	const varNameRegex = /^[a-zA-Z_$][a-zA-Z0-9_$]*$/;
	
	EditAISeg.regDef({
		name:"CodeSingleHtml",showName:"{\"CN\":\"编写简单网页\",\"EN\":\"Create simple web page\"}",icon:"edlit.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"userPrompt":{name:"userPrompt",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"autoFix":{name:"autoFix",showName:undefined,type:"bool",key:1,fixed:1,initVal:true},
			"userCheck":{name:"userCheck",showName:undefined,type:"bool",key:1,fixed:1,initVal:true},
			"blueprintImage":{name:"blueprintImage",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"baseHtmlUrl":{name:"baseHtmlUrl",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","userPrompt","autoFix","userCheck","blueprintImage","baseHtmlUrl","codes","desc"],
		desc:"这是根据用户需求，编写一个简单的HTML页面，通过沙箱展示给用户的智能体。请提供需求以及可用资源。\n"
	});
	
	DocAIAgentExporter.segTypeExporters["CodeSingleHtml"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['userPrompt']=");this.genAttrStatement(seg.getAttr("userPrompt"));coder.packText(";");coder.newLine();
			coder.packText("args['autoFix']=");this.genAttrStatement(seg.getAttr("autoFix"));coder.packText(";");coder.newLine();
			coder.packText("args['userCheck']=");this.genAttrStatement(seg.getAttr("userCheck"));coder.packText(";");coder.newLine();
			coder.packText("args['blueprintImage']=");this.genAttrStatement(seg.getAttr("blueprintImage"));coder.packText(";");coder.newLine();
			coder.packText("args['baseHtmlUrl']=");this.genAttrStatement(seg.getAttr("baseHtmlUrl"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/builder_new/ai/CodeSingleHtml.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
			this.packUpdateContext(coder,seg);
			this.packUpdateGlobal(coder,seg);
			this.packResult(coder,seg,seg.outlet);
		}
		coder.indentLess();coder.maybeNewLine();
		coder.packText(`};`);coder.newLine();
		if(exportDebug){
			coder.packText(`${segName}.jaxId="${seg.jaxId}"`);coder.newLine();
		}
		coder.packText(`${segName}.url="${segName}@"+agentURL`);coder.newLine();
		coder.newLine();
	};
}
//#CodyExport<<<
/*#{1IN8IJT7O0PostDoc*/
/*}#1IN8IJT7O0PostDoc*/


export default CodeSingleHtml;
export{CodeSingleHtml};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IN8IJT7O0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IN8IJT7O1",
//			"attrs": {
//				"CodeSingleHtml": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IN8IJT7O7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IN8IJT7P0",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IN8IJT7P1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IN8IJT7P2",
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
//			"jaxId": "1IN8IJT7O2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IN8IJT7O3",
//			"attrs": {
//				"userPrompt": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN8IPUBJ0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "用户对要编写的HTML页面的需求描述"
//					}
//				},
//				"autoFix": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN8KU5KG0",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "true",
//						"desc": "如果出现错误，是否自动修正重新编写代码",
//						"required": "false"
//					}
//				},
//				"userCheck": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1INAM1MGE0",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "true",
//						"desc": "是否需要用户确认页面结果，给出修改建议",
//						"required": "false"
//					}
//				},
//				"blueprintImage": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1INCK4MO60",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "页面参考设计图的URL",
//						"required": "false"
//					}
//				},
//				"baseHtmlUrl": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1INJ49D380",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "如果存在，从初始参数中提取的初始HTML的URL",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IN8IJT7O4",
//			"attrs": {
//				"fixRound": {
//					"type": "int",
//					"valText": "0"
//				},
//				"takeSnap": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"fixPrompt": {
//					"type": "string",
//					"valText": ""
//				},
//				"fixError": {
//					"type": "bool",
//					"valText": "false"
//				},
//				"htmlCode": {
//					"type": "string",
//					"valText": ""
//				},
//				"codeMessages": {
//					"type": "auto",
//					"valText": "[]"
//				},
//				"imageMessages": {
//					"type": "auto",
//					"valText": "[]"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IN8IJT7O5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IN8IJT7O6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IN8IO9UM0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "105",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1IN8IPUBH0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8IQMJ40"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IN8IQMJ40",
//					"attrs": {
//						"id": "WriteHtml",
//						"viewName": "",
//						"label": "",
//						"x": "310",
//						"y": "300",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN8IRUKS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN8IRUKS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1",
//						"system": "#`\n- - -\n## 角色\n你是一个根据用户需求，编写（包括调试/修正）简单的HTML页面的AI智能体。\n- - -\n## 对话\n- 第一轮对话，用户会给出当前的HTML代码；你要编写的HTML文件的需求描述，可能还会包含页面设计的参考图。\n- 之后的对话，用户会给出当前的HTML代码；当前的HTML代码的执行情况；还可能给出修改建议；或者回答你提出的问题。\n- 你根据当前对话过程，用JSON回复用户\n    - 如果你可以根据当前掌握信息可以输出HTML，请在JSON中的\"html\"属性中提供完整的HTML页面代码（包括必须的CSS/JS以及引用的外部脚本等）。例如：\n    \\`\\`\\`\n    {\n    \t\"html\":\"<html>...</html>\"\n    }\n    \\`\\`\\`\n    \n    - 如果你缺少必要的信息来生成HTML，请在JSON的\"chat\"属性中向用户提出问题或与用户对话完善编写网页所需的信息。例如：\n    \\`\\`\\`\n    {\n    \t\"chat\":\"请提供调用天气API的Key。\"\n    }\n    \\`\\`\\`\n## 回复JSON对象属性\n- \"html\" {string}: 你生成的HTML页面代码，注意一定是完整的HTML页面代码（包括必须的CSS/JS以及引用的外部脚本等）。\n- \"chat\" {string}: 为了完善必要的信息或回答用户的疑问，与用户的对话信息。\n`",
//						"temperature": "0",
//						"maxToken": "16000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IN8IRUKR0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8LTP420"
//						},
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IN8IRLCC0",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "990",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN8IRUKS2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN8IRUKS3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IN8IRUKR1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8ISD9N0"
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
//					"jaxId": "1IN8ISD9N0",
//					"attrs": {
//						"id": "CheckError",
//						"viewName": "",
//						"label": "",
//						"x": "1230",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN8ITC8U0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN8ITC8U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IN8ITC8S1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INAM9HB70"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IN8ITC8S0",
//									"attrs": {
//										"id": "Error",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IN8ITC8U2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IN8ITC8U3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.error"
//									},
//									"linkedSeg": "1IN8O2EUH0"
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
//					"jaxId": "1IN8IT5CG0",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "1980",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IN8ITC8U4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN8ITC8U5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IN8ITC8S2",
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
//					"def": "brunch",
//					"jaxId": "1IN8ITQN40",
//					"attrs": {
//						"id": "CheckFix",
//						"viewName": "",
//						"label": "",
//						"x": "1720",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN8IV1BL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN8IV1BL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IN8IV1BK1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IN8IVBEC0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IN8IV1BK0",
//									"attrs": {
//										"id": "Fix",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IN8IV1BL2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IN8IV1BL3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!autoFix && fixRound<5"
//									},
//									"linkedSeg": "1INB7152P0"
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
//					"jaxId": "1IN8IUPJ80",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "345",
//						"y": "130",
//						"outlet": {
//							"jaxId": "1IN8IV1BL5",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8IQMJ40"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IN8IVBEC0",
//					"attrs": {
//						"id": "Failed",
//						"viewName": "",
//						"label": "",
//						"x": "1980",
//						"y": "250",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IN8IVL6P0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN8IVL6P1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IN8IVL6N0",
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
//					"def": "brunch",
//					"jaxId": "1IN8LTP420",
//					"attrs": {
//						"id": "CheckChat",
//						"viewName": "",
//						"label": "",
//						"x": "530",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN8M0H2O0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN8M0H2O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IN8M0H2J1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IN8OVA0P0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IN8M0H2J0",
//									"attrs": {
//										"id": "Chat",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IN8M0H2O2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IN8M0H2O3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.chat"
//									},
//									"linkedSeg": "1IN8LVSMB0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IN8OUBKG0",
//									"attrs": {
//										"id": "Html",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IN8OV5VB0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IN8OV5VB1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.html"
//									},
//									"linkedSeg": "1INCMVE120"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IN8LVSMB0",
//					"attrs": {
//						"id": "AskChat",
//						"viewName": "",
//						"label": "",
//						"x": "765",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN8M0H2P2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN8M0H2P3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#input.chat",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1IN8M0H2K1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8M08BQ0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IN8M08BQ0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "895",
//						"y": "130",
//						"outlet": {
//							"jaxId": "1IN8M0H2P4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8IUPJ80"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IN8O2EUH0",
//					"attrs": {
//						"id": "ShowError",
//						"viewName": "",
//						"label": "",
//						"x": "1465",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN8O4TN20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN8O4TN21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`发现页面错误：${input.error}`",
//						"outlet": {
//							"jaxId": "1IN8O4TMV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8ITQN40"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IN8OVA0P0",
//					"attrs": {
//						"id": "AIRetry",
//						"viewName": "",
//						"label": "",
//						"x": "765",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN8P0G3B0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN8P0G3B1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IN8P0G350",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8P01NS0"
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
//					"def": "connector",
//					"jaxId": "1IN8P01NS0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "900",
//						"y": "475",
//						"outlet": {
//							"jaxId": "1IN8P0G3B2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8P0ACC0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IN8P0ACC0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "345",
//						"y": "475",
//						"outlet": {
//							"jaxId": "1IN8P0G3B3",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8IQMJ40"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1INAM9HB70",
//					"attrs": {
//						"id": "CheckUser",
//						"viewName": "",
//						"label": "",
//						"x": "1465",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INAMGQB60",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INAMGQB61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INAMGQAV1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INAMBT8D0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INAMGQAV0",
//									"attrs": {
//										"id": "NoCheck",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INAMGQB62",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INAMGQB63",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!userCheck"
//									},
//									"linkedSeg": "1IN8IT5CG0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1INAMBT8D0",
//					"attrs": {
//						"id": "AskFin",
//						"viewName": "",
//						"label": "",
//						"x": "1720",
//						"y": "445",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "当前页面是否符合你的要求？",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1INAMGQAV2",
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
//									"jaxId": "1INAMBT7P0",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Yes, the page meets my requirements",
//											"localize": {
//												"EN": "Yes, the page meets my requirements",
//												"CN": "是的，页面符合我的要求"
//											},
//											"localizable": true
//										},
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INAMGQB64",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INAMGQB65",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IN8IT5CG0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1INAMBT7P1",
//									"attrs": {
//										"id": "Fix",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "No, further modifications are required",
//											"localize": {
//												"EN": "No, further modifications are required",
//												"CN": "不，还需要修改"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INAMGQB66",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INAMGQB67",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1INAMHF8T0"
//								}
//							]
//						},
//						"silent": "false",
//						"countdown": "None",
//						"silentOutlet": "Finish"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1INAMHF8T0",
//					"attrs": {
//						"id": "AskFix",
//						"viewName": "",
//						"label": "",
//						"x": "1980",
//						"y": "490",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INAMJOT00",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INAMJOT01",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": {
//							"type": "string",
//							"valText": "请输入修改指导",
//							"localize": {
//								"EN": "请输入修改指导",
//								"CN": "请输入修改指导"
//							},
//							"localizable": true
//						},
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1INAMJOSQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INB73H7L0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1INAMKBR10",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2105",
//						"y": "595",
//						"outlet": {
//							"jaxId": "1INAMLI7M0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INAMKMMK0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1INAMKMMK0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1015",
//						"y": "595",
//						"outlet": {
//							"jaxId": "1INAMLI7M1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8P01NS0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1INB7152P0",
//					"attrs": {
//						"id": "JumpFix",
//						"viewName": "",
//						"label": "",
//						"x": "1980",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1INB73H7L0",
//						"outlet": {
//							"jaxId": "1INB71BCQ0",
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
//					"jaxId": "1INB73H7L0",
//					"attrs": {
//						"id": "CheckSnap",
//						"viewName": "",
//						"label": "",
//						"x": "2195",
//						"y": "490",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INBU07RB0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INBU07RB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INBU07R41",
//							"attrs": {
//								"id": "NotSnap",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INB7NO290"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INB75NS10",
//									"attrs": {
//										"id": "Snap",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INBU07RB2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INBU07RB3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.assets"
//									},
//									"linkedSeg": "1INB7MLCQ0"
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
//					"jaxId": "1INB7MLCQ0",
//					"attrs": {
//						"id": "FixWithSnap",
//						"viewName": "",
//						"label": "",
//						"x": "2455",
//						"y": "475",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INBU07RB12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INBU07RB13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INBU07R50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INB7QH6E0"
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
//					"def": "connector",
//					"jaxId": "1INB7NO290",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2360",
//						"y": "595",
//						"outlet": {
//							"jaxId": "1INBU07RB14",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INAMKBR10"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1INB7QH6E0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2610",
//						"y": "595",
//						"outlet": {
//							"jaxId": "1INBU07RB16",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INB7NO290"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1INCMVE120",
//					"attrs": {
//						"id": "ShowCode",
//						"viewName": "",
//						"label": "",
//						"x": "765",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INCN08S70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INCN08S71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`\n\\`\\`\\`\n${input.html}\n\\`\\`\\`\n`",
//						"outlet": {
//							"jaxId": "1INCN08RS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN8IRLCC0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "这是根据用户需求，编写一个简单的HTML页面，通过沙箱展示给用户的智能体。请提供需求以及可用资源。\n",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"{\\\"CN\\\":\\\"编写简单网页\\\",\\\"EN\\\":\\\"Create simple web page\\\"}\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":\"Tool\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"edlit.svg\",\"catalog\":\"AI Call\"}"
//	}
//}