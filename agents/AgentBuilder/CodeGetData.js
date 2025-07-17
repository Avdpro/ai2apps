//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1INLFJ4NJ0MoreImports*/
/*}#1INLFJ4NJ0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"userPrompt":{
			"name":"userPrompt","type":"auto",
			"defaultValue":"",
			"desc":"用户需求描述",
		},
		"autoFix":{
			"name":"autoFix","type":"bool",
			"required":false,
			"defaultValue":true,
			"desc":"是否自动修正代码错误",
		}
	},
	/*#{1INLFJ4NJ0ArgsView*/
	/*}#1INLFJ4NJ0ArgsView*/
};

/*#{1INLFJ4NJ0StartDoc*/
/*}#1INLFJ4NJ0StartDoc*/
//----------------------------------------------------------------------------
let CodeGetData=async function(session){
	let userPrompt,autoFix;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,WriteCode,CheckChat,AskChat,ShowCode,RunCodeInPage,CheckError,ShowError,CheckFix,Failed,JumpFix,AIRetry,SaveResults,CheckFiles,CheckResult,FixCode,ShowResult,ShowFix,CheckRound;
	let curCode="";
	let fixRound=0;
	let codeResult=undefined;
	let briefResult=undefined;
	let runLogs=undefined;
	
	/*#{1INLFJ4NJ0LocalVals*/
	/*}#1INLFJ4NJ0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			userPrompt=input.userPrompt;
			autoFix=input.autoFix;
		}else{
			userPrompt=undefined;
			autoFix=undefined;
		}
		/*#{1INLFJ4NJ0ParseArgs*/
		/*}#1INLFJ4NJ0ParseArgs*/
	}
	
	/*#{1INLFJ4NJ0PreContext*/
	/*}#1INLFJ4NJ0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1INLFJ4NJ0PostContext*/
	/*}#1INLFJ4NJ0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1INLFLHLM0
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(userPrompt===undefined || userPrompt==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@aichat/ai/CompleteArgs.js",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:WriteCode,result:(result),preSeg:"1INLFLHLM0",outlet:"1INLFO27Q0"};
	};
	FixArgs.jaxId="1INLFLHLM0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["WriteCode"]=WriteCode=async function(input){//:1INLFM0K90
		let prompt;
		let result=null;
		/*#{1INLFM0K90Input*/
		/*}#1INLFM0K90Input*/
		
		let opts={
			platform:"",
			mode:"$coding",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=WriteCode.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
## 环境:
现在是: ${""+(new Date()).toString()}

- - -
## 角色
你是一个根据用户需求，编写（包括调试/修正）通过各种公开API（例如雅虎财经）收集获取数据的Javascript函数的AI编程智能体。
- - - 
## 编写函数
- 函数：你输出的代码必须是函数名为getData的异步无参数javascript函数

- 执行环境：你输出的Javascript函数将运行在Web环境而不是Node.js环境里

- 返回值：函数执行后返回一个**数据文件JSON对象**数组，里面的每一个元素应该是一个**数据文件JSON对象**
   - 每一个**数据文件JSON对象**必须包含以下参数:
        - "name" {string}: 文件名，需要有意义且反应数据格式例如: "apple_price.csv"
        - "content" {string}: 文件数据内容
        - "description" {string}: 文件内容的描述

- 跨域访问：执行环境中的fetch方法是支持跨越访问的，你编写的函数应该使用fetch方法调用网络API。

- 如果你使用YahooFinance读取股价：
	- 请使用"/v7/finance/quote"API，而不要使用其它API，例如："/v7/finance/download"
	- 请调用API时一次只读取一支股票的信息。
    - 调用API时请明确给出起始、结束时间，不要省略

- - -
## 对话
- 第一轮对话，用户会给出需要收集的数据描述。
- 之后的对话，用户会给出当前的函数代码；当前的函数代码的执行情况；还可能给出修改建议；或者回答你提出的问题。
- 你根据当前对话过程，用JSON回复用户
    - 如果你可以根据当前掌握信息可以输出函数代码，请在JSON中的"code"属性中提供完整的getData函数代码。例如：
    \`\`\`
    {
    	"code":"async function getData(){...}"
    }
    \`\`\`
    
    - 如果你缺少必要的信息来生成函数，请在JSON的"chat"属性中向用户提出问题或与用户对话完善编写网页所需的信息。例如：
    \`\`\`
    {
    	"chat":"请提供调用比特币实时价格 API XXXXXXXX 的Key。你可以通过.....获得你的Key。"
    }
    \`\`\`
## 回复JSON对象属性
- "code" {string}: 你生成的getData函数，注意一定是完整的函数代码。
- "chat" {string}: 为了完善必要的信息或回答用户的疑问，与用户的对话信息。
`},
		];
		messages.push(...chatMem);
		/*#{1INLFM0K90PrePrompt*/
		/*}#1INLFM0K90PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1INLFM0K90FilterMessage*/
			/*}#1INLFM0K90FilterMessage*/
			messages.push(msg);
		}
		/*#{1INLFM0K90PreCall*/
		/*}#1INLFM0K90PreCall*/
		result=(result===null)?(await session.callSegLLM("WriteCode@"+agentURL,opts,messages,true)):result;
		/*#{1INLFM0K90PostLLM*/
		/*}#1INLFM0K90PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		if(chatMem.length>50){
			let removedMsgs=chatMem.splice(0,2);
			/*#{1INLFM0K90PostClear*/
			/*}#1INLFM0K90PostClear*/
		}
		result=trimJSON(result);
		/*#{1INLFM0K90PostCall*/
		/*}#1INLFM0K90PostCall*/
		return {seg:CheckChat,result:(result),preSeg:"1INLFM0K90",outlet:"1INLFO27Q1"};
	};
	WriteCode.jaxId="1INLFM0K90"
	WriteCode.url="WriteCode@"+agentURL
	WriteCode.messages=[];
	
	segs["CheckChat"]=CheckChat=async function(input){//:1INLFOCVV0
		let result=input;
		if(input.chat){
			let output=input;
			return {seg:AskChat,result:(output),preSeg:"1INLFOCVV0",outlet:"1INLFOCVV4"};
		}
		if(input.code){
			let output=input;
			return {seg:ShowCode,result:(output),preSeg:"1INLFOCVV0",outlet:"1INLFOCVV7"};
		}
		return {seg:AIRetry,result:(result),preSeg:"1INLFOCVV0",outlet:"1INLFOCVV3"};
	};
	CheckChat.jaxId="1INLFOCVV0"
	CheckChat.url="CheckChat@"+agentURL
	
	segs["AskChat"]=AskChat=async function(input){//:1INLFOOT20
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
		return {seg:WriteCode,result:(result),preSeg:"1INLFOOT20",outlet:"1INLFOOT30"};
	};
	AskChat.jaxId="1INLFOOT20"
	AskChat.url="AskChat@"+agentURL
	
	segs["ShowCode"]=ShowCode=async function(input){//:1INLFPQQS0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=`
\`\`\`
${input.code}
\`\`\`
`;
		session.addChatText(role,content,opts);
		return {seg:RunCodeInPage,result:(result),preSeg:"1INLFPQQS0",outlet:"1INLFPQQS3"};
	};
	ShowCode.jaxId="1INLFPQQS0"
	ShowCode.url="ShowCode@"+agentURL
	
	segs["RunCodeInPage"]=RunCodeInPage=async function(input){//:1INLFQ4FR0
		let result=input
		/*#{1INLFQ4FR0Code*/
		let htmlCode;
		curCode=input.code;
		htmlCode=`
		<html>
			<head>
				<meta charset="UTF-8">
				<title>${(($ln==="CN")?("获取数据"):/*EN*/("Fetch data"))}</title>
			</head>
			<body>
				<h1>${(($ln==="CN")?("获取数据"):/*EN*/("Fetch data"))}</h1>
			</body>
			<script type="module">
			${input.code}
			window.getData=getData;
			</script>
			<script type="module">
				window.run=async function(){
					return await getData();
				}
			</script>
		</html>
		`;
		result=await session.WSCall_WebSandbox(htmlCode);
		runLogs=result.logs;
		if(result.result){
			let fileObj,content;
			codeResult=result.result;
			briefResult=[];
			if(Array.isArray(codeResult)){
				for(fileObj of codeResult){
					content=fileObj.content;
					if(content.length>10*1024){
						content=content.substring(0,5*1024)+"\n...\n"+content.substring(content.length-5*1024);
					}
					briefResult.push({...fileObj,content:content});
				}
			}
		}
		/*}#1INLFQ4FR0Code*/
		return {seg:ShowResult,result:(result),preSeg:"1INLFQ4FR0",outlet:"1INLFQ4FR3"};
	};
	RunCodeInPage.jaxId="1INLFQ4FR0"
	RunCodeInPage.url="RunCodeInPage@"+agentURL
	
	segs["CheckError"]=CheckError=async function(input){//:1INLFSV790
		let result=input;
		/*#{1INLFSV790Start*/
		/*}#1INLFSV790Start*/
		if(input.error){
			let output=input;
			/*#{1INLFSV794Codes*/
			/*}#1INLFSV794Codes*/
			return {seg:ShowError,result:(output),preSeg:"1INLFSV790",outlet:"1INLFSV794"};
		}
		/*#{1INLFSV790Post*/
		/*}#1INLFSV790Post*/
		return {seg:CheckFiles,result:(result),preSeg:"1INLFSV790",outlet:"1INLFSV793"};
	};
	CheckError.jaxId="1INLFSV790"
	CheckError.url="CheckError@"+agentURL
	
	segs["ShowError"]=ShowError=async function(input){//:1INLFTDIP0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=`发现页面错误：${input.error}`;
		session.addChatText(role,content,opts);
		return {seg:CheckFix,result:(result),preSeg:"1INLFTDIP0",outlet:"1INLFTDIQ2"};
	};
	ShowError.jaxId="1INLFTDIP0"
	ShowError.url="ShowError@"+agentURL
	
	segs["CheckFix"]=CheckFix=async function(input){//:1INLFTOVC0
		let result=input;
		/*#{1INLFTOVC0Start*/
		/*}#1INLFTOVC0Start*/
		if(!!autoFix && fixRound<5){
			/*#{1INLFTOVC4Codes*/
			fixRound+=1;
			result=`
			执行函数发生错误: ${input.error},
			- - -
			执行函数的日志：
			${input.logs}
			`;
			/*}#1INLFTOVC4Codes*/
			return {seg:JumpFix,result:(input),preSeg:"1INLFTOVC0",outlet:"1INLFTOVC4"};
		}
		/*#{1INLFTOVC0Post*/
		/*}#1INLFTOVC0Post*/
		return {seg:Failed,result:(result),preSeg:"1INLFTOVC0",outlet:"1INLFTOVC3"};
	};
	CheckFix.jaxId="1INLFTOVC0"
	CheckFix.url="CheckFix@"+agentURL
	
	segs["Failed"]=Failed=async function(input){//:1INLFUA2Q0
		let result=input
		/*#{1INLFUA2Q0Code*/
		result={result:"Failed",content:"获取数据失败，尝试多次修改代码后，还是无法获得需要的数据。"};
		/*}#1INLFUA2Q0Code*/
		return {result:result};
	};
	Failed.jaxId="1INLFUA2Q0"
	Failed.url="Failed@"+agentURL
	
	segs["JumpFix"]=JumpFix=async function(input){//:1INLFUO8S0
		let result=input;
		return {seg:ShowFix,result:result,preSeg:"1INP9SILV0",outlet:"1INLG0AJU0"};
	
	};
	JumpFix.jaxId="1INP9SILV0"
	JumpFix.url="JumpFix@"+agentURL
	
	segs["AIRetry"]=AIRetry=async function(input){//:1INLFVI9E0
		let result=input
		/*#{1INLFVI9E0Code*/
		/*}#1INLFVI9E0Code*/
		return {seg:WriteCode,result:(result),preSeg:"1INLFVI9E0",outlet:"1INLFVI9F2"};
	};
	AIRetry.jaxId="1INLFVI9E0"
	AIRetry.url="AIRetry@"+agentURL
	
	segs["SaveResults"]=SaveResults=async function(input){//:1INLG0KG70
		let result=input
		/*#{1INLG0KG70Code*/
		let list,i,n,fileObj,hubName,resultFiles,urls;
		resultFiles=[];
		urls=[];
		list=codeResult;
		n=list.length;
		for(i=0;i<n;i++){
			fileObj=list[i];
			hubName=await session.saveHubFile(fileObj.name,Base64.encode(fileObj.content));
			resultFiles.push({url:"hub://"+hubName,description:fileObj.description});
			urls.push(fileObj.url);
		}
		result={result:"Finish",content:`所需的数据已经存在以下文件里：\n\n${JSON.stringify(resultFiles,null,"\t")}`,assets:urls}
		/*}#1INLG0KG70Code*/
		return {result:result};
	};
	SaveResults.jaxId="1INLG0KG70"
	SaveResults.url="SaveResults@"+agentURL
	
	segs["CheckFiles"]=CheckFiles=async function(input){//:1INLHNRO90
		let prompt;
		let result;
		
		let opts={
			platform:"",
			mode:"$lite",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=CheckFiles.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
## 环境:
现在是: ${""+(new Date()).toString()}

- - - 
## 角色
你是一个检验获取数据程序执行结果的AI。
你根据用户提出的需求，检验程序的输出文件及其内容是否符合用户的需求

## 用户需求
用户对于数据的需求描述是：  
${userPrompt}

## 执行结果说明
函数执行后返回一个**数据文件JSON对象**数组，里面的每一个元素应该是一个**数据文件JSON对象**
- 每一个**数据文件JSON对象**必须包含以下参数:
    - "name" {string}: 文件名，需要有意义且反应数据格式例如: "apple_price.csv"
    - "content" {string}: 文件数据内容
    - "description" {string}: 文件内容的描述

## 代码执行结果，注意为了节省资源，文件内容可能会有部分省略。
\`\`\`
${JSON.stringify(briefResult)}
\`\`\`

## 回答
请分析结果，用JSON对象返回对结果评估结果
返回的JSON对象属性说明：
- "checkName" {boolean}: 文件名是否正确
- "checkContent" {boolean}: 文件中是否包含内容
- "checkFormat" {boolean}: 文件内容的格式是否符合用户需求且正确
- "reqNumber" {integer}: 用户需求大概需要多少的数据量？
- "checkNumber" {boolean}: 文件内容里是否包含足够数量的数据内容？
- "result" {string} 取值范围：["pass","error"]
    - 如果结果符合要求: "pass"
    - 如果结果不符合要求，或数据不合理: "error"
- "content" {string} 你的评估结果的文本描述，如果存在错误，请详细指出问题，以便修改
`
},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("CheckFiles@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:CheckResult,result:(result),preSeg:"1INLHNRO90",outlet:"1INLHSQ930"};
	};
	CheckFiles.jaxId="1INLHNRO90"
	CheckFiles.url="CheckFiles@"+agentURL
	
	segs["CheckResult"]=CheckResult=async function(input){//:1INLHOEJ80
		let result=input;
		if(input.result==="error"){
			return {seg:CheckRound,result:(input),preSeg:"1INLHOEJ80",outlet:"1INLHSQ931"};
		}
		return {seg:SaveResults,result:(result),preSeg:"1INLHOEJ80",outlet:"1INLHSQ932"};
	};
	CheckResult.jaxId="1INLHOEJ80"
	CheckResult.url="CheckResult@"+agentURL
	
	segs["FixCode"]=FixCode=async function(input){//:1INLHQCSA0
		let result=input
		/*#{1INLHQCSA0Code*/
		result=`
		代码执行返回的内容错误：${input.content},
		- - -
		代码执行结果：
		\`\`\`
		${JSON.stringify(briefResult,null,"\t")}
		\`\`\`
		- - -
		代码执行日志: 
		\`\`\`
		${JSON.stringify(runLogs)}
		\`\`\`
		- - -
		请分析问题，重新编写代码。
		`
		fixRound+=1;
		/*}#1INLHQCSA0Code*/
		return {seg:ShowFix,result:(result),preSeg:"1INLHQCSA0",outlet:"1INLHSQ933"};
	};
	FixCode.jaxId="1INLHQCSA0"
	FixCode.url="FixCode@"+agentURL
	
	segs["ShowResult"]=ShowResult=async function(input){//:1INNK4NUE0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=`
\`\`\`
${JSON.stringify(briefResult)}
\`\`\`
`;
		session.addChatText(role,content,opts);
		return {seg:CheckError,result:(result),preSeg:"1INNK4NUE0",outlet:"1INNK6ABV0"};
	};
	ShowResult.jaxId="1INNK4NUE0"
	ShowResult.url="ShowResult@"+agentURL
	
	segs["ShowFix"]=ShowFix=async function(input){//:1INP9SILV0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:WriteCode,result:(result),preSeg:"1INP9SILV0",outlet:"1INP9TKOJ0"};
	};
	ShowFix.jaxId="1INP9SILV0"
	ShowFix.url="ShowFix@"+agentURL
	
	segs["CheckRound"]=CheckRound=async function(input){//:1INPBFE3R0
		let result=input;
		if(fixRound>=5){
			return {seg:Failed,result:(input),preSeg:"1INPBFE3R0",outlet:"1INPBI0KQ0"};
		}
		return {seg:FixCode,result:(result),preSeg:"1INPBFE3R0",outlet:"1INPBI0KQ1"};
	};
	CheckRound.jaxId="1INPBFE3R0"
	CheckRound.url="CheckRound@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CodeGetData",
		url:agentURL,
		autoStart:true,
		jaxId:"1INLFJ4NJ0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{userPrompt,autoFix}*/){
			let result;
			parseAgentArgs(input);
			/*#{1INLFJ4NJ0PreEntry*/
			/*}#1INLFJ4NJ0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1INLFJ4NJ0PostEntry*/
			/*}#1INLFJ4NJ0PostEntry*/
			return result;
		},
		/*#{1INLFJ4NJ0MoreAgentAttrs*/
		/*}#1INLFJ4NJ0MoreAgentAttrs*/
	};
	/*#{1INLFJ4NJ0PostAgent*/
	/*}#1INLFJ4NJ0PostAgent*/
	return agent;
};
/*#{1INLFJ4NJ0ExCodes*/
/*}#1INLFJ4NJ0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "CodeGetData",
		description: "这是根据需求，编写从网络获取数据，并保存到文件的智能体",
		parameters:{
			type: "object",
			properties:{
				userPrompt:{type:"auto",description:"用户需求描述"},
				autoFix:{type:"bool",description:"是否自动修正代码错误"}
			}
		}
	},
	label: "Get Data",
	chatEntry: "Tool",
	agent: CodeGetData
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
		name:"CodeGetData",showName:"Get Data",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"userPrompt":{name:"userPrompt",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"autoFix":{name:"autoFix",showName:undefined,type:"bool",key:1,fixed:1,initVal:true},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","userPrompt","autoFix","codes","desc"],
		desc:"这是根据需求，编写从网络获取数据，并保存到文件的智能体"
	});
	
	DocAIAgentExporter.segTypeExporters["CodeGetData"]=
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
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/CodeGetData.js",args,false);`);coder.newLine();
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
/*#{1INLFJ4NJ0PostDoc*/
/*}#1INLFJ4NJ0PostDoc*/


export default CodeGetData;
export{CodeGetData};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1INLFJ4NJ0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1INLFJ4NJ1",
//			"attrs": {
//				"CodeGetData": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1INLFJ4NK0",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1INLFJ4NK1",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1INLFJ4NK2",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1INLFJ4NK3",
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
//			"jaxId": "1INLFJ4NJ2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "TestCall",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1INLFJ4NJ3",
//			"attrs": {
//				"userPrompt": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1INLFKPPJ0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "用户需求描述"
//					}
//				},
//				"autoFix": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1INLHSQ970",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "true",
//						"desc": "是否自动修正代码错误",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1INLFJ4NJ4",
//			"attrs": {
//				"curCode": {
//					"type": "string",
//					"valText": ""
//				},
//				"fixRound": {
//					"type": "int",
//					"valText": "0"
//				},
//				"codeResult": {
//					"type": "auto",
//					"valText": ""
//				},
//				"briefResult": {
//					"type": "auto",
//					"valText": ""
//				},
//				"runLogs": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1INLFJ4NJ5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1INLFJ4NJ6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1INLFLHLM0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "145",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1INLFO27Q0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFM0K90"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1INLFM0K90",
//					"attrs": {
//						"id": "WriteCode",
//						"viewName": "",
//						"label": "",
//						"x": "385",
//						"y": "265",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLFO27R0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLFO27R1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "",
//						"mode": "$coding",
//						"system": "#`\n## 环境:\n现在是: ${\"\"+(new Date()).toString()}\n\n- - -\n## 角色\n你是一个根据用户需求，编写（包括调试/修正）通过各种公开API（例如雅虎财经）收集获取数据的Javascript函数的AI编程智能体。\n- - - \n## 编写函数\n- 函数：你输出的代码必须是函数名为getData的异步无参数javascript函数\n\n- 执行环境：你输出的Javascript函数将运行在Web环境而不是Node.js环境里\n\n- 返回值：函数执行后返回一个**数据文件JSON对象**数组，里面的每一个元素应该是一个**数据文件JSON对象**\n   - 每一个**数据文件JSON对象**必须包含以下参数:\n        - \"name\" {string}: 文件名，需要有意义且反应数据格式例如: \"apple_price.csv\"\n        - \"content\" {string}: 文件数据内容\n        - \"description\" {string}: 文件内容的描述\n\n- 跨域访问：执行环境中的fetch方法是支持跨越访问的，你编写的函数应该使用fetch方法调用网络API。\n\n- 如果你使用YahooFinance读取股价：\n\t- 请使用\"/v7/finance/quote\"API，而不要使用其它API，例如：\"/v7/finance/download\"\n\t- 请调用API时一次只读取一支股票的信息。\n    - 调用API时请明确给出起始、结束时间，不要省略\n\n- - -\n## 对话\n- 第一轮对话，用户会给出需要收集的数据描述。\n- 之后的对话，用户会给出当前的函数代码；当前的函数代码的执行情况；还可能给出修改建议；或者回答你提出的问题。\n- 你根据当前对话过程，用JSON回复用户\n    - 如果你可以根据当前掌握信息可以输出函数代码，请在JSON中的\"code\"属性中提供完整的getData函数代码。例如：\n    \\`\\`\\`\n    {\n    \t\"code\":\"async function getData(){...}\"\n    }\n    \\`\\`\\`\n    \n    - 如果你缺少必要的信息来生成函数，请在JSON的\"chat\"属性中向用户提出问题或与用户对话完善编写网页所需的信息。例如：\n    \\`\\`\\`\n    {\n    \t\"chat\":\"请提供调用比特币实时价格 API XXXXXXXX 的Key。你可以通过.....获得你的Key。\"\n    }\n    \\`\\`\\`\n## 回复JSON对象属性\n- \"code\" {string}: 你生成的getData函数，注意一定是完整的函数代码。\n- \"chat\" {string}: 为了完善必要的信息或回答用户的疑问，与用户的对话信息。\n`",
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
//							"jaxId": "1INLFO27Q1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFOCVV0"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1INNKK3GS0",
//									"attrs": {
//										"prompt": "",
//										"reply": "{\"code\":\"async function getData() {\\n    const apiUrl = 'https://query1.finance.yahoo.com/v7/finance/download/TSLA';\\n    const endDate = new Date();\\n    const startDate = new Date();\\n    startDate.setDate(endDate.getDate() - 7);\\n    const params = new URLSearchParams({\\n        period1: Math.floor(startDate.getTime() / 1000),\\n        period2: Math.floor(endDate.getTime() / 1000),\\n        interval: '1d',\\n        events: 'history',\\n        includeAdjustedClose: 'true'\\n    });\\n\\n    try {\\n        const response = await fetch(`${apiUrl}?${params}`);\\n        if (!response.ok) throw new Error('Network response was not ok');\\n        const data = await response.text();\\n        return [{\\n            name: 'tesla_price.csv',\\n            content: data,\\n            description: 'Tesla stock prices for the past week.'\\n        }];\\n    } catch (error) {\\n        console.error('Error fetching data:', error);\\n        return [{\\n            name: 'error.txt',\\n            content: error.toString(),\\n            description: 'An error occurred while fetching Tesla stock prices.'\\n        }];\\n    }\\n}\"}"
//									}
//								}
//							]
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
//					"def": "brunch",
//					"jaxId": "1INLFOCVV0",
//					"attrs": {
//						"id": "CheckChat",
//						"viewName": "",
//						"label": "",
//						"x": "615",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLFOCVV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLFOCVV2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INLFOCVV3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INLFVI9E0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INLFOCVV4",
//									"attrs": {
//										"id": "Chat",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INLFOCVV5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INLFOCVV6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.chat"
//									},
//									"linkedSeg": "1INLFOOT20"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INLFOCVV7",
//									"attrs": {
//										"id": "Code",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INLFOCVV8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INLFOCVV9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.code"
//									},
//									"linkedSeg": "1INLFPQQS0"
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
//					"jaxId": "1INLFOOT20",
//					"attrs": {
//						"id": "AskChat",
//						"viewName": "",
//						"label": "",
//						"x": "870",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLFOOT21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLFOOT22",
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
//						"askUpward": "No",
//						"outlet": {
//							"jaxId": "1INLFOOT30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFP03N0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1INLFP03N0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1000",
//						"y": "90",
//						"outlet": {
//							"jaxId": "1INLFPCCN0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFP56T0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1INLFP56T0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "405",
//						"y": "90",
//						"outlet": {
//							"jaxId": "1INLFPCCN1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFM0K90"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1INLFPQQS0",
//					"attrs": {
//						"id": "ShowCode",
//						"viewName": "",
//						"label": "",
//						"x": "870",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLFPQQS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLFPQQS2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`\n\\`\\`\\`\n${input.code}\n\\`\\`\\`\n`",
//						"outlet": {
//							"jaxId": "1INLFPQQS3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFQ4FR0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1INLFQ4FR0",
//					"attrs": {
//						"id": "RunCodeInPage",
//						"viewName": "",
//						"label": "",
//						"x": "1110",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLFQ4FR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLFQ4FR2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INLFQ4FR3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INNK4NUE0"
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
//					"jaxId": "1INLFSV790",
//					"attrs": {
//						"id": "CheckError",
//						"viewName": "",
//						"label": "",
//						"x": "1640",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLFSV791",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLFSV792",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INLFSV793",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INLHNRO90"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INLFSV794",
//									"attrs": {
//										"id": "Error",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "true",
//										"context": {
//											"jaxId": "1INLFSV795",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INLFSV796",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.error"
//									},
//									"linkedSeg": "1INLFTDIP0"
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
//					"jaxId": "1INLFTDIP0",
//					"attrs": {
//						"id": "ShowError",
//						"viewName": "",
//						"label": "",
//						"x": "1890",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLFTDIQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLFTDIQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`发现页面错误：${input.error}`",
//						"outlet": {
//							"jaxId": "1INLFTDIQ2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFTOVC0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1INLFTOVC0",
//					"attrs": {
//						"id": "CheckFix",
//						"viewName": "",
//						"label": "",
//						"x": "2150",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLFTOVC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLFTOVC2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INLFTOVC3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INLFUA2Q0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INLFTOVC4",
//									"attrs": {
//										"id": "Fix",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1INLFTOVC5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INLFTOVC6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!autoFix && fixRound<5"
//									},
//									"linkedSeg": "1INLFUO8S0"
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
//					"jaxId": "1INLFUA2Q0",
//					"attrs": {
//						"id": "Failed",
//						"viewName": "",
//						"label": "",
//						"x": "2650",
//						"y": "195",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1INLFUA2R0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLFUA2R1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INLFUA2R2",
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
//					"def": "jumper",
//					"jaxId": "1INLFUO8S0",
//					"attrs": {
//						"id": "JumpFix",
//						"viewName": "",
//						"label": "",
//						"x": "2395",
//						"y": "90",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1INP9SILV0",
//						"outlet": {
//							"jaxId": "1INLG0AJU0",
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
//					"def": "code",
//					"jaxId": "1INLFVI9E0",
//					"attrs": {
//						"id": "AIRetry",
//						"viewName": "",
//						"label": "",
//						"x": "870",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLFVI9F0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLFVI9F1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INLFVI9F2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFVU9B0"
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
//					"jaxId": "1INLFVU9B0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "990",
//						"y": "435",
//						"outlet": {
//							"jaxId": "1INLG0AK00",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLG05R30"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1INLG05R30",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "415",
//						"y": "435",
//						"outlet": {
//							"jaxId": "1INLG0AK01",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFM0K90"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1INLG0KG70",
//					"attrs": {
//						"id": "SaveResults",
//						"viewName": "",
//						"label": "",
//						"x": "2395",
//						"y": "470",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1INLG1J3L0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLG1J3L1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INLG1J3K0",
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
//					"def": "callLLM",
//					"jaxId": "1INLHNRO90",
//					"attrs": {
//						"id": "CheckFiles",
//						"viewName": "",
//						"label": "",
//						"x": "1890",
//						"y": "370",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLHSQ971",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLHSQ972",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "",
//						"mode": "$lite",
//						"system": "#`\n## 环境:\n现在是: ${\"\"+(new Date()).toString()}\n\n- - - \n## 角色\n你是一个检验获取数据程序执行结果的AI。\n你根据用户提出的需求，检验程序的输出文件及其内容是否符合用户的需求\n\n## 用户需求\n用户对于数据的需求描述是：  \n${userPrompt}\n\n## 执行结果说明\n函数执行后返回一个**数据文件JSON对象**数组，里面的每一个元素应该是一个**数据文件JSON对象**\n- 每一个**数据文件JSON对象**必须包含以下参数:\n    - \"name\" {string}: 文件名，需要有意义且反应数据格式例如: \"apple_price.csv\"\n    - \"content\" {string}: 文件数据内容\n    - \"description\" {string}: 文件内容的描述\n\n## 代码执行结果，注意为了节省资源，文件内容可能会有部分省略。\n\\`\\`\\`\n${JSON.stringify(briefResult)}\n\\`\\`\\`\n\n## 回答\n请分析结果，用JSON对象返回对结果评估结果\n返回的JSON对象属性说明：\n- \"checkName\" {boolean}: 文件名是否正确\n- \"checkContent\" {boolean}: 文件中是否包含内容\n- \"checkFormat\" {boolean}: 文件内容的格式是否符合用户需求且正确\n- \"reqNumber\" {integer}: 用户需求大概需要多少的数据量？\n- \"checkNumber\" {boolean}: 文件内容里是否包含足够数量的数据内容？\n- \"result\" {string} 取值范围：[\"pass\",\"error\"]\n    - 如果结果符合要求: \"pass\"\n    - 如果结果不符合要求，或数据不合理: \"error\"\n- \"content\" {string} 你的评估结果的文本描述，如果存在错误，请详细指出问题，以便修改\n`\n",
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
//							"jaxId": "1INLHSQ930",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLHOEJ80"
//						},
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1INLHOEJ80",
//					"attrs": {
//						"id": "CheckResult",
//						"viewName": "",
//						"label": "",
//						"x": "2125",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLHSQ973",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLHSQ974",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INLHSQ932",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INLG0KG70"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INLHSQ931",
//									"attrs": {
//										"id": "Error",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INLHSQ975",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INLHSQ976",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result===\"error\""
//									},
//									"linkedSeg": "1INPBFE3R0"
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
//					"jaxId": "1INLHQCSA0",
//					"attrs": {
//						"id": "FixCode",
//						"viewName": "",
//						"label": "",
//						"x": "2660",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INLHSQ977",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INLHSQ978",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INLHSQ933",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INP9SILV0"
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
//					"jaxId": "1INLHRHGM0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3020",
//						"y": "580",
//						"outlet": {
//							"jaxId": "1INLHSQ979",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLHRUQK0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1INLHRUQK0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1095",
//						"y": "580",
//						"outlet": {
//							"jaxId": "1INLHSQ9710",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFVU9B0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1INNK4NUE0",
//					"attrs": {
//						"id": "ShowResult",
//						"viewName": "",
//						"label": "",
//						"x": "1385",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INNK6AC30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INNK6AC31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`\n\\`\\`\\`\n${JSON.stringify(briefResult)}\n\\`\\`\\`\n`",
//						"outlet": {
//							"jaxId": "1INNK6ABV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLFSV790"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1INP9SILV0",
//					"attrs": {
//						"id": "ShowFix",
//						"viewName": "",
//						"label": "",
//						"x": "2895",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INP9TKOP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INP9TKOP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1INP9TKOJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1INLHRHGM0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1INPBFE3R0",
//					"attrs": {
//						"id": "CheckRound",
//						"viewName": "",
//						"label": "",
//						"x": "2395",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1INPBJLTN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1INPBJLTN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1INPBI0KQ1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1INLHQCSA0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1INPBI0KQ0",
//									"attrs": {
//										"id": "MaxRound",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1INPBJLTN2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1INPBJLTN3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#fixRound>=5"
//									},
//									"linkedSeg": "1INLFUA2Q0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				}
//			]
//		},
//		"desc": "这是根据需求，编写从网络获取数据，并保存到文件的智能体",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"Get Data\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":\"Tool\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
//	}
//}