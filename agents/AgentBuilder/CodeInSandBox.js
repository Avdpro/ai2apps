//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IOPMMTJ60MoreImports*/
import {webFetch,tabNT} from "/@tabos";
/*}#1IOPMMTJ60MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"codePrompt":{
			"name":"codePrompt","type":"auto",
			"defaultValue":"",
			"desc":"要编写代码的需求描述，以及每一个数据文件的内容说明。",
		},
		"dataFiles":{
			"name":"dataFiles","type":"auto",
			"required":false,
			"defaultValue":[],
			"desc":"字符串数组：如果有，要处理的数据文件的URL字符串数组。",
		},
		"autoFix":{
			"name":"autoFix","type":"bool",
			"required":false,
			"defaultValue":true,
			"desc":"",
		}
	},
	/*#{1IOPMMTJ60ArgsView*/
	/*}#1IOPMMTJ60ArgsView*/
};

/*#{1IOPMMTJ60StartDoc*/
/*}#1IOPMMTJ60StartDoc*/
//----------------------------------------------------------------------------
let CodeInSandBox=async function(session){
	let codePrompt,dataFiles,autoFix;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,ShowTarget,LoopFiles,PreviewDataFile,TipPreview,TipStart,WriteCode,CheckCode,AskChat,BadReply,ShowCode,RunCode,CheckError,ShowError,AskFix,Finish,FixError,FixCode,ManualFix,CheckFix,Failed,AskRetry,JumpFix,Review,TryTool,ToolError,TipTool,CallTool,ToolResult,ReplyTool,ShowResult,HasAssets,ReadAssets,AutoFix,JumpReview,ReviewResult,CheckRetry,Failed2;
	let filePreviews={};
	let curCode="";
	let runLogs=[];
	let codeResult=undefined;
	let fixRound=0;
	let htmlCode="";
	let isFixError=false;
	let assetPreviews={};
	
	/*#{1IOPMMTJ60LocalVals*/
	/*}#1IOPMMTJ60LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			codePrompt=input.codePrompt;
			dataFiles=input.dataFiles;
			autoFix=input.autoFix;
		}else{
			codePrompt=undefined;
			dataFiles=undefined;
			autoFix=undefined;
		}
		/*#{1IOPMMTJ60ParseArgs*/
		/*}#1IOPMMTJ60ParseArgs*/
	}
	
	/*#{1IOPMMTJ60PreContext*/
	/*}#1IOPMMTJ60PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IOPMMTJ60PostContext*/
	/*}#1IOPMMTJ60PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IOGJACVV0
		let result=input;
		let missing=false;
		let smartAsk=true;
		if(codePrompt===undefined || codePrompt==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@aichat/ai/CompleteArgs.js",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:ShowTarget,result:(result),preSeg:"1IOGJACVV0",outlet:"1IOGJAKMK0"};
	};
	FixArgs.jaxId="1IOGJACVV0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["ShowTarget"]=ShowTarget=async function(input){//:1IOLB69NF0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=(($ln==="CN")?(`编程指令: ${codePrompt}`):(`Coding command: ${codePrompt}`));
		session.addChatText(role,content,opts);
		return {seg:LoopFiles,result:(result),preSeg:"1IOLB69NF0",outlet:"1IOLB8BLG0"};
	};
	ShowTarget.jaxId="1IOLB69NF0"
	ShowTarget.url="ShowTarget@"+agentURL
	
	segs["LoopFiles"]=LoopFiles=async function(input){//:1IOGJBC210
		let result=input;
		let list=dataFiles;
		let i,n,item,loopR;
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			loopR=await session.runAISeg(agent,TipPreview,item,"1IOGJBC210","1IOGJDPK50")
			if(loopR==="break"){
				break;
			}
		}
		return {seg:TipStart,result:(result),preSeg:"1IOGJBC210",outlet:"1IOGJDPK51"};
	};
	LoopFiles.jaxId="1IOGJBC210"
	LoopFiles.url="LoopFiles@"+agentURL
	
	segs["PreviewDataFile"]=PreviewDataFile=async function(input){//:1IOGJCG480
		let result=input
		/*#{1IOGJCG480Code*/
		let url,data;
		url=input;
		if(url.startsWith("hub://")){
			try{
				data=await session.loadHubFile(url);
				data=Base64.decodeBytes(data);
				const decoder = new TextDecoder('utf-8');
				data=decoder.decode(data)||"";
			}catch(err){
				//Read failed.
				data="NA.";
			}
		}else{
			try{
				data=await (await webFetch(url)).text();
			}catch(err){
				//Read failed
				data="NA";
			}
		}
		if(data.length>512){
			data=data.substring(0,256)+"...\n...\n..."+data.substring(data.length-256);
		}
		filePreviews[url]=data;
		/*}#1IOGJCG480Code*/
		return {result:result};
	};
	PreviewDataFile.jaxId="1IOGJCG480"
	PreviewDataFile.url="PreviewDataFile@"+agentURL
	
	segs["TipPreview"]=TipPreview=async function(input){//:1IOLB92070
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="log";
		let content=(($ln==="CN")?(`正在分析数据文件：${input}`):(`Analyzing data file: ${input}`));
		session.addChatText(role,content,opts);
		return {seg:PreviewDataFile,result:(result),preSeg:"1IOLB92070",outlet:"1IOLBBTB30"};
	};
	TipPreview.jaxId="1IOLB92070"
	TipPreview.url="TipPreview@"+agentURL
	
	segs["TipStart"]=TipStart=async function(input){//:1IOLBGCNQ0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="log";
		let content=(($ln==="CN")?("开始编写代码"):("Start writing code"));
		session.addChatText(role,content,opts);
		return {seg:WriteCode,result:(result),preSeg:"1IOLBGCNQ0",outlet:"1IOLBI1V60"};
	};
	TipStart.jaxId="1IOLBGCNQ0"
	TipStart.url="TipStart@"+agentURL
	
	segs["WriteCode"]=WriteCode=async function(input){//:1IOGJDDV50
		let prompt;
		let result=null;
		/*#{1IOGJDDV50Input*/
		/*}#1IOGJDDV50Input*/
		
		let opts={
			platform:"Claude",
			mode:"claude-3-7-sonnet-latest",
			maxToken:15000,
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
你是一个根据用户需求，编写（包括调试/修正）: ${(filePreviews&&filePreviews.length)?"使用用户给出的数据文件":""}，运行并输出所需要结果的函数代码的AI智能体。

- - -
## 用户需求
${codePrompt}

- - -
## 数据文件内容概览：
${JSON.stringify(filePreviews,null,"\t")}

- - -
## 读取数据文件
- 你可以用fetch函数读取数据文件。

- - -
## 运行环境
- 执行环境：你输出的Javascript函数将运行在Web环境而不是Node.js环境里
- 页面：当前页面是空白页面
- 当前页面 没有引入任何库。如果需要引入库，请在回复JOSN里的"imports"属性中列出来。

- - - 
## 编写函数
- runCode函数：你输出的代码必须是函数名为runCode的异步无参数javascript函数。你的函数应该：如果存在数据文件，读取数据文件；根据需求计算结果；返回结果。

- runCode函数返回值：runCode函数返回结果必须是一个JOSN对象，包含两个属性："result"和"assets".
    - "result" {string}: 执行结果，如果函数的返回内容很简单，"result"属性可以是直接的结果。如果返回内容比较复杂，或者返回多内容是在文件中，"result"应该是执行结果的自然语言描述，如果结果包含输出文件，result也应该包括每个输出的文件的内容解释。注意：解释文件时，你应该使用文件url（调用saveFile函数的返回值）而不是文件名。
    - "assets" {arrary<string>|null}: 函数执行保存的结果文件的文件url（调用saveFile函数的返回值）数组。如果函数不需要输出文件，这个属性为null.

- 复杂/大数据量返回值：如果函数执行后的结果数据比较复杂，或者数据量很大，或者是多媒体文件，例如视频/图片。你要把结果保存在文件里

- 保存文件API：如果需要向文件中输出结果（例如数据列表、图片、视频）。请调用saveFile全局函数。saveFile是一个异步全局函数，需要两个参数："fileName"和"data"其中："fileName"是要保存的文件名，不要包括任何路径。"data"是要保存的数据内容，可以是字符串、ArrayBuffer和ByteArray。saveFile函数会返回保存后文件的访问url。

- 抛出异常：如果执行遇到问题，应该抛出对应的异常，用于分析调试。

- 跨域访问：执行环境中的fetch方法是支持跨越访问的，你编写的函数应该使用fetch方法调用网络API。

- Log: 在执行函数的重要节点添加输出log（使用console.log函数就好）的代码，方便调试纠错。

- - -
## 对话
- 第一轮对话，用户会指示你开始编写函数
- 之后的对话，用户会给出当前的函数代码；当前的函数代码的执行情况；还可能给出修改建议；或者回答你提出的问题。
- 你根据当前对话过程，用JSON回复用户
    - 如果你可以根据当前掌握信息可以输出函数代码，请在JSON中的"code"属性中提供完整的getData函数代码。如果你需要使用额外的代码库，请把库文件的链接，放在"imports"数组属性中例如：
    \`\`\`
    {
    	"code":"async function runCode(){...}",
        "imports":["https://cdn.jsdelivr.net...lib1.js","https://cdn.jsdelivr.net...lib2.js"]
    }
    \`\`\`
    
    - 如果你缺少必要的信息来生成函数，请在JSON的"chat"属性中向用户提出问题或与用户对话完善编写网页所需的信息。例如：
    \`\`\`
    {
    	"chat":"请提供调用比特币实时价格 API XXXXXXXX 的Key。你可以通过.....获得你的Key。"
    }
    \`\`\`
## 回复JSON对象属性
- "code" {string}: 你生成的runCode函数，注意一定是完整的函数代码。
- "imports" {array<string>} 执行你的函数，页面需要引入的额外脚本文件链接，页面会用<script>标记引入
- "chat" {string}: 为了完善必要的信息或回答用户的疑问，与用户的对话信息。

## 引入脚本和库文件
如果执行你的函数需要HTML页面引入额外的脚本/库，请把它们列在在回复JSON的"imports"属性中。

`},
		];
		messages.push(...chatMem);
		/*#{1IOGJDDV50PrePrompt*/
		/*}#1IOGJDDV50PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IOGJDDV50FilterMessage*/
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
			if(isFixError){
				//Push current html into messages:
				messages.push({role:"user",content:`当前的包含函数的HTML代码: \n\`\`\`\n${htmlCode?htmlCode:"无"}\n\`\`\`\n`});
			}else{
				//Push current code into messages:
				messages.push({role:"user",content:`当前的函数代码: \n\`\`\`\n${curCode?curCode:"无"}\n\`\`\`\n`});
			}
			/*}#1IOGJDDV50FilterMessage*/
			messages.push(msg);
		}
		/*#{1IOGJDDV50PreCall*/
		/*}#1IOGJDDV50PreCall*/
		result=WriteCode.cheats[prompt]||WriteCode.cheats[input]||WriteCode.cheats[""+chatMem.length]||WriteCode.cheats[""];
		if(!result){
			result=(result===undefined)?(await session.callSegLLM("WriteCode@"+agentURL,opts,messages,true)):result;
		
		}
		/*#{1IOGJDDV50PostLLM*/
		/*}#1IOGJDDV50PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		result=trimJSON(result);
		/*#{1IOGJDDV50PostCall*/
		let m1,code;
		m1=chatMem[chatMem.length-1];
		code=result.code
		if(code){
			if(code.length>100){
				code=code.substring(0,100)+"...\n...\n..."+code.substring(code.length-100);
			}
			m1.content=JSON.stringify({...result,code:code});
		}
		/*}#1IOGJDDV50PostCall*/
		return {seg:CheckCode,result:(result),preSeg:"1IOGJDDV50",outlet:"1IOGJDPK53"};
	};
	WriteCode.jaxId="1IOGJDDV50"
	WriteCode.url="WriteCode@"+agentURL
	WriteCode.messages=[];
	WriteCode.cheats={
		"0":"{\"code\":\"async function runCode() {\\n    // 使用埃拉托斯特尼筛法(Sieve of Eratosthenes)找出1000以内的所有质数\\n    function findPrimes(limit) {\\n        // 创建一个布尔数组，初始假设所有数字都是质数\\n        const isPrime = Array(limit + 1).fill(true);\\n        \\n        // 0和1不是质数\\n        isPrime[0] = isPrime[1] = false;\\n        \\n        // 埃拉托斯特尼筛法\\n        for (let i = 2; i * i <= limit; i++) {\\n            if (isPrime[i]) {\\n                // 将i的所有倍数标记为非质数\\n                for (let j = i * i; j <= limit; j += i) {\\n                    isPrime[j] = false;\\n                }\\n            }\\n        }\\n        \\n        // 收集所有质数\\n        const primes = [];\\n        for (let i = 2; i <= limit; i++) {\\n            if (isPrime[i]) {\\n                primes.push(i);\\n            }\\n        }\\n        \\n        return primes;\\n    }\\n    \\n    // 找出1000以内的所有质数\\n    const primes = findPrimes(1000);\\n    const count = primes.length;\\n    \\n    // 将质数列表转换为字符串\\n    const primesStr = primes.join('\\\\n');\\n    \\n    // 保存质数到文件\\n    const fileUrl = await saveFile('primes.txt', primesStr);\\n    \\n    console.log(`找到了${count}个1000以内的质数`);\\n    console.log(`质数已保存到文件: ${fileUrl}`);\\n    \\n    return {\\n        result: `1000以内共有${count}个质数。所有质数已保存到文件中: ${fileUrl}`,\\n        assets: [fileUrl]\\n    };\\n}\",\"imports\":[]}"
	};
	
	segs["CheckCode"]=CheckCode=async function(input){//:1IOGJEOI10
		let result=input;
		if(input.chat && (!input.code)){
			let output=input.chat;
			return {seg:AskChat,result:(output),preSeg:"1IOGJEOI10",outlet:"1IOGJU6180"};
		}
		if(input.code){
			return {seg:ShowCode,result:(input),preSeg:"1IOGJEOI10",outlet:"1IOGJF0P50"};
		}
		if(input.tool){
			return {seg:TryTool,result:(input),preSeg:"1IOGJEOI10",outlet:"1IOPP6NI30"};
		}
		return {seg:BadReply,result:(result),preSeg:"1IOGJEOI10",outlet:"1IOGJU6181"};
	};
	CheckCode.jaxId="1IOGJEOI10"
	CheckCode.url="CheckCode@"+agentURL
	
	segs["AskChat"]=AskChat=async function(input){//:1IOGJG3610
		let tip=(input);
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
		return {seg:WriteCode,result:(result),preSeg:"1IOGJG3610",outlet:"1IOGJU6182"};
	};
	AskChat.jaxId="1IOGJG3610"
	AskChat.url="AskChat@"+agentURL
	
	segs["BadReply"]=BadReply=async function(input){//:1IOGJHFDB0
		let result=input
		/*#{1IOGJHFDB0Code*/
		result=`错误：你的回复没有包含代码或者与用户的对话。`;
		/*}#1IOGJHFDB0Code*/
		return {seg:WriteCode,result:(result),preSeg:"1IOGJHFDB0",outlet:"1IOGJU6183"};
	};
	BadReply.jaxId="1IOGJHFDB0"
	BadReply.url="BadReply@"+agentURL
	
	segs["ShowCode"]=ShowCode=async function(input){//:1IOGJIN1C0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=`
#### ${(($ln==="CN")?("执行函数"):/*EN*/("Execute function"))}
\`\`\`
${input.code}
\`\`\`
#### ${(($ln==="CN")?("需要额外引入的脚本"):/*EN*/("Additional script needed"))}
${input.imports?JSON.stringify(input.imports,null,"\t"):"无"}
`;
		session.addChatText(role,content,opts);
		return {seg:RunCode,result:(result),preSeg:"1IOGJIN1C0",outlet:"1IOGJU6184"};
	};
	ShowCode.jaxId="1IOGJIN1C0"
	ShowCode.url="ShowCode@"+agentURL
	
	segs["RunCode"]=RunCode=async function(input){//:1IOGJJ4QM0
		let result=input
		/*#{1IOGJJ4QM0Code*/
		let imports,importLines;
		imports=input.imports;
		if(imports){
			let i,n;
			importLines=[];
			n=imports.length;
			for(i=0;i<n;i++){
				importLines.push(`<script src="${imports[i]}" onerror="handleScriptError(this.src)"></script>`);
			}
			importLines=importLines.join("\n");
		}else{
			importLines="";
		}
		curCode=input.code;
		htmlCode=`
		<html>
			<head>
				<meta charset="UTF-8">
				<title>${(($ln==="CN")?("执行代码"):/*EN*/("Run code"))}</title>
			</head>
			<body>
			</body>
			<script>
				function handleScriptError(url) {
					window.console.log(\`Load script failed:: \${url}\`);
				}
			</script>
			${importLines}
			<script type="module">
			${input.code}
			window.runCode=runCode;
			</script>
			<script type="module">
				window.run=async function(){
					return await runCode();
				}
			</script>
		</html>
		`;
		result=await session.WSCall_WebSandbox(htmlCode);
		runLogs=result.logs;
		if(result.result){
			codeResult=result.result;
		}else{
			codeResult=null;
		}
		/*}#1IOGJJ4QM0Code*/
		return {seg:CheckError,result:(result),preSeg:"1IOGJJ4QM0",outlet:"1IOGJU6185"};
	};
	RunCode.jaxId="1IOGJJ4QM0"
	RunCode.url="RunCode@"+agentURL
	
	segs["CheckError"]=CheckError=async function(input){//:1IOGJKH1Q0
		let result=input;
		/*#{1IOGJKH1Q0Start*/
		/*}#1IOGJKH1Q0Start*/
		if(input.error){
			let output=input;
			/*#{1IOGJKH1Q4Codes*/
			/*}#1IOGJKH1Q4Codes*/
			return {seg:ShowError,result:(output),preSeg:"1IOGJKH1Q0",outlet:"1IOGJKH1Q4"};
		}
		/*#{1IOGJKH1Q0Post*/
		/*}#1IOGJKH1Q0Post*/
		return {seg:ShowResult,result:(result),preSeg:"1IOGJKH1Q0",outlet:"1IOGJKH1Q3"};
	};
	CheckError.jaxId="1IOGJKH1Q0"
	CheckError.url="CheckError@"+agentURL
	
	segs["ShowError"]=ShowError=async function(input){//:1IOGJLB760
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=`发现页面错误：${input.error}`;
		session.addChatText(role,content,opts);
		return {seg:CheckFix,result:(result),preSeg:"1IOGJLB760",outlet:"1IOGJLB763"};
	};
	ShowError.jaxId="1IOGJLB760"
	ShowError.url="ShowError@"+agentURL
	
	segs["AskFix"]=AskFix=async function(input){//:1IOGJNELB0
		let prompt=("当前结果是否满足需求？如果需要修改，请直接输入修改指导。")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=true;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"图片符合需求，结束。",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"自我评估改进",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:Review,result:(result),preSeg:"1IOGJNELB0",outlet:"1IOK3P3NB0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			/*#{1IOGJU6187ChatInput*/
			/*}#1IOGJU6187ChatInput*/
			return {seg:FixCode,result:(result),preSeg:"1IOGJNELB0",outlet:"1IOGJU6187"};
		}else if(item.code===0){
			return {seg:Finish,result:(result),preSeg:"1IOGJNELB0",outlet:"1IOGJNEKP0"};
		}else if(item.code===1){
			return {seg:Review,result:(result),preSeg:"1IOGJNELB0",outlet:"1IOK3P3NB0"};
		}
		/*#{1IOGJU6187DefaultOutlet*/
		/*}#1IOGJU6187DefaultOutlet*/
		return {seg:FixCode,result:(result),preSeg:"1IOGJNELB0",outlet:"1IOGJU6187"};
	};
	AskFix.jaxId="1IOGJNELB0"
	AskFix.url="AskFix@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1IOGJR48U0
		let result=input
		/*#{1IOGJR48U0Code*/
		result={result:"Finish",content:`执行结果：${codeResult.result}`,assets:codeResult.assets};
		/*}#1IOGJR48U0Code*/
		return {result:result};
	};
	Finish.jaxId="1IOGJR48U0"
	Finish.url="Finish@"+agentURL
	
	segs["FixError"]=FixError=async function(input){//:1IOGJTKJ90
		let result=input
		/*#{1IOGJTKJ90Code*/
		let log,logs;
		isFixError=true;
		logs=input.logs||[];
		logs=logs.map((item)=>{
			if(typeof(item)!=="string"){
				try{
					item=JSON.stringify(item);
				}catch(err){
					item=""+item;
				}
			}
			if(item.length>200){
				item=item.substring(0,200)+"...";
			}
			return item;
		});
		fixRound+=1;
		result=`
		页面加载/函数运行出现错误: ${input.error}.
		- - - 
		页面输出的日志：
		
		${JSON.stringify(logs,null,"\t")}
		
		- - -
		请分析错误及日志，修改并重新输出代码，如果缺失重要内容再与用户对话，否则不要打搅用户。
		`;
		/*}#1IOGJTKJ90Code*/
		return {seg:WriteCode,result:(result),preSeg:"1IOGJTKJ90",outlet:"1IOGJU6192"};
	};
	FixError.jaxId="1IOGJTKJ90"
	FixError.url="FixError@"+agentURL
	
	segs["FixCode"]=FixCode=async function(input){//:1IOGJRU5V0
		let result=input
		/*#{1IOGJRU5V0Code*/
		let log,logs;
		isFixError=false;
		logs=input.logs||[];
		logs=logs.map((item)=>{
			if(typeof(item)!=="string"){
				try{
					item=JSON.stringify(item);
				}catch(err){
					item=""+item;
				}
			}
			if(item.length>200){
				item=item.substring(0,200)+"...";
			}
			return item;
		});
		result=`
		对于当前结果，用户提出修改意见: ${input.issue}
		
		本次的执行结果：
		${codeResult.result}
		- - - 
		当前页面加载执行Log：
		
		${JSON.stringify(logs,null,"\t")}
		
		请参考当前页面结果和日志，根据用户的修改意见，修改代码后重新输出。如果缺失重要内容再与用户对话，否则不要打搅用户。
		`;
		/*}#1IOGJRU5V0Code*/
		return {seg:CheckRetry,result:(result),preSeg:"1IOGJRU5V0",outlet:"1IOGJU6191"};
	};
	FixCode.jaxId="1IOGJRU5V0"
	FixCode.url="FixCode@"+agentURL
	
	segs["ManualFix"]=ManualFix=async function(input){//:1IOJ68MHG0
		let result=input
		/*#{1IOJ68MHG0Code*/
		let log,logs;
		fixRound=0;
		logs=input.logs||[];
		logs=logs.map((item)=>{
			if(typeof(item)!=="string"){
				try{
					item=JSON.stringify(item);
				}catch(err){
					item=""+item;
				}
			}
			if(item.length>200){
				item=item.substring(0,200)+"...";
			}
			return item;
		});
		result={
			prompt:`
		页面加载/函数运行出现错误: ${input.error}.
		- - - 
		当前页面加载执行Log：
		
		${JSON.stringify(logs,null,"\t")}
		- - - 
		对于当前用户提出修改意见: ${input}
		- - - 
		请参考当前页面结果和日志，根据用户的修改意见，修改代码后重新输出。如果缺失重要内容再与用户对话，否则不要打搅用户。
		`,
			assets:[codeResult]
		};
		/*}#1IOJ68MHG0Code*/
		return {seg:WriteCode,result:(result),preSeg:"1IOJ68MHG0",outlet:"1IOJ6BPTA2"};
	};
	ManualFix.jaxId="1IOJ68MHG0"
	ManualFix.url="ManualFix@"+agentURL
	
	segs["CheckFix"]=CheckFix=async function(input){//:1IOIIK8TJ0
		let result=input;
		if(fixRound<0){
			let output=input;
			return {seg:FixError,result:(output),preSeg:"1IOIIK8TJ0",outlet:"1IOIINA380"};
		}
		return {seg:AskRetry,result:(result),preSeg:"1IOIIK8TJ0",outlet:"1IOIINA381"};
	};
	CheckFix.jaxId="1IOIIK8TJ0"
	CheckFix.url="CheckFix@"+agentURL
	
	segs["Failed"]=Failed=async function(input){//:1IOIIM6AK0
		let result=input
		/*#{1IOIIM6AK0Code*/
		result={"result":"Failed","content":(($ln==="CN")?("编写/执行程序尝试失败。"):/*EN*/("Attempt to write and run program failed."))};
		/*}#1IOIIM6AK0Code*/
		return {result:result};
	};
	Failed.jaxId="1IOIIM6AK0"
	Failed.url="Failed@"+agentURL
	
	segs["AskRetry"]=AskRetry=async function(input){//:1IOJ63UOM0
		let prompt=("修改代码次数过多，是否继续修改，或者请提出修改指导")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=true;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"继续尝试修改",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"放弃绘制",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result=input;
			return {seg:JumpFix,result:(result),preSeg:"1IOJ63UOM0",outlet:"1IOJ63UO30"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {seg:ManualFix,result:(result),preSeg:"1IOJ63UOM0",outlet:"1IOJ6BPTA0"};
		}else if(item.code===0){
			result=(input);
			return {seg:JumpFix,result:(result),preSeg:"1IOJ63UOM0",outlet:"1IOJ63UO30"};
		}else if(item.code===1){
			return {seg:Failed,result:(result),preSeg:"1IOJ63UOM0",outlet:"1IOJ63UO31"};
		}
		return {seg:ManualFix,result:(result),preSeg:"1IOJ63UOM0",outlet:"1IOJ6BPTA0"};
	};
	AskRetry.jaxId="1IOJ63UOM0"
	AskRetry.url="AskRetry@"+agentURL
	
	segs["JumpFix"]=JumpFix=async function(input){//:1IOJ66R7R0
		let result=input;
		/*#{1IOJ66R7R0PreCodes*/
		fixRound=0;
		/*}#1IOJ66R7R0PreCodes*/
		return {seg:FixError,result:result,preSeg:"1IOGJTKJ90",outlet:"1IOJ6BPTA1"};
	
	};
	JumpFix.jaxId="1IOGJTKJ90"
	JumpFix.url="JumpFix@"+agentURL
	
	segs["Review"]=Review=async function(input){//:1IOK3BRBV0
		let prompt;
		let result=null;
		/*#{1IOK3BRBV0Input*/
		let log,logs;
		logs=input.logs||[];
		logs=logs.map((item)=>{
			if(typeof(item)!=="string"){
				try{
					item=JSON.stringify(item);
				}catch(err){
					item=""+item;
				}
			}
			if(item.length>200){
				item=item.substring(0,200)+"...";
			}
			return item;
		});
		/*}#1IOK3BRBV0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=Review.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
## 角色
你是一个评估AI编写的代码函数执行结果，提出修改建议的智能体

## 当前AI编写的函数执行目标：
${codePrompt}

## AI编写的函数执行结果:
${JSON.stringify(codeResult.result)}

## 执行输出文件(如果有)的内容预览
${JSON.stringify(assetPreviews,null,"\t")}

- - -
## 代码执行日志
${JSON.stringify(logs,null,"\t")}

- - -
## 对话
- 请根据**当前函数执行目标**，分析并指出执行结果以及附件是否有符合需求，如果存在问题，指出问题并提出修改方案
- 你必须用JSON回复问题
- 回复JSON参数：
    - "result" {"Finish"|"Fix"}: 当执行结果正确并满足需求，设置"result"属性为"Finish"。反之，如果需要修改，设置为"Fix"。
    - "issue" {string|null}: 如果存在问题需要修改，这个属性是问题描述和修改指导。
    例如，如果不需要修改：
    {
    	"result":"Finsish",
        "issue":null
    }
    例如，如果存在问题：
    {
    	"result":"Fix",
        "issue":"返回的数据单位与要求不同，要求的是摄氏度，返回的是华氏度。请修改确保返回的是摄氏度。"
    }
`},
		];
		/*#{1IOK3BRBV0PrePrompt*/
		input={
			prompt:"图片是AI编写的函数执行结果，请提出修改建议。",
			assets:[codeResult]
		};
		/*}#1IOK3BRBV0PrePrompt*/
		prompt="请分析并返回结果";
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IOK3BRBV0FilterMessage*/
			/*}#1IOK3BRBV0FilterMessage*/
			messages.push(msg);
		}
		/*#{1IOK3BRBV0PreCall*/
		/*}#1IOK3BRBV0PreCall*/
		result=(result===null)?(await session.callSegLLM("Review@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IOK3BRBV0PostCall*/
		/*}#1IOK3BRBV0PostCall*/
		return {seg:ReviewResult,result:(result),preSeg:"1IOK3BRBV0",outlet:"1IOK3P3NC0"};
	};
	Review.jaxId="1IOK3BRBV0"
	Review.url="Review@"+agentURL
	
	segs["TryTool"]=TryTool=async function(input){//:1IOPOTF0Q0
		let result=input;
		/*#{1IOPOTF0Q0Code*/
		false
		/*}#1IOPOTF0Q0Code*/
		return {seg:TipTool,result:(result),preSeg:"1IOPOTF0Q0",outlet:"1IOPP6NI50",catchSeg:ToolError,catchlet:"1IOPP6NI51"};
	};
	TryTool.jaxId="1IOPOTF0Q0"
	TryTool.url="TryTool@"+agentURL
	
	segs["ToolError"]=ToolError=async function(input){//:1IOPOU4QL0
		let result=input
		/*#{1IOPOU4QL0Code*/
		/*}#1IOPOU4QL0Code*/
		return {seg:WriteCode,result:(result),preSeg:"1IOPOU4QL0",outlet:"1IOPP6NI52"};
	};
	ToolError.jaxId="1IOPOU4QL0"
	ToolError.url="ToolError@"+agentURL
	
	segs["TipTool"]=TipTool=async function(input){//:1IOPOUH1F0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:CallTool,result:(result),preSeg:"1IOPOUH1F0",outlet:"1IOPP6NI53"};
	};
	TipTool.jaxId="1IOPOUH1F0"
	TipTool.url="TipTool@"+agentURL
	
	segs["CallTool"]=CallTool=async function(input){//:1IOPOUS1O0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let sourcePath=pathLib.joinTabOSURL(basePath,"");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:ReplyTool};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:ToolResult,result:(result),preSeg:"1IOPOUS1O0",outlet:"1IOPP6NI54"};
	};
	CallTool.jaxId="1IOPOUS1O0"
	CallTool.url="CallTool@"+agentURL
	
	segs["ToolResult"]=ToolResult=async function(input){//:1IOPP1MS70
		let result=input
		/*#{1IOPP1MS70Code*/
		/*}#1IOPP1MS70Code*/
		return {seg:WriteCode,result:(result),preSeg:"1IOPP1MS70",outlet:"1IOPP6NI55"};
	};
	ToolResult.jaxId="1IOPP1MS70"
	ToolResult.url="ToolResult@"+agentURL
	
	segs["ReplyTool"]=ReplyTool=async function(input){//:1IOPP2FML0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let sourcePath=pathLib.joinTabOSURL(basePath,"");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	ReplyTool.jaxId="1IOPP2FML0"
	ReplyTool.url="ReplyTool@"+agentURL
	
	segs["ShowResult"]=ShowResult=async function(input){//:1IQC4A1K40
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content=input;
		/*#{1IQC4A1K40PreCodes*/
		let res=input.result;
		let assets=res.assets;
		if(assets){
			content=`#### ${(($ln==="CN")?("执行结果"):/*EN*/("Execution result"))}:\n`+res.result;
			content+=`\n### ${(($ln==="CN")?("附件"):/*EN*/("Assets:"))}:\n`;
			for(let url of assets){
				content+=`- [${url}](${url})\n`;
			}
		}else{
			content=`#### ${(($ln==="CN")?("执行结果"):/*EN*/("Execution result"))}:\n`+res.result;
		}
		/*}#1IQC4A1K40PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IQC4A1K40PostCodes*/
		/*}#1IQC4A1K40PostCodes*/
		return {seg:AutoFix,result:(result),preSeg:"1IQC4A1K40",outlet:"1IQC4CBAQ0"};
	};
	ShowResult.jaxId="1IQC4A1K40"
	ShowResult.url="ShowResult@"+agentURL
	
	segs["HasAssets"]=HasAssets=async function(input){//:1IQKHP2G80
		let result=input;
		/*#{1IQKHP2G80Start*/
		/*}#1IQKHP2G80Start*/
		if(codeResult.assets && codeResult.assets.length){
			return {seg:ReadAssets,result:(input),preSeg:"1IQKHP2G80",outlet:"1IQMHH4HA0"};
		}
		/*#{1IQKHP2G80Post*/
		/*}#1IQKHP2G80Post*/
		return {seg:JumpReview,result:(result),preSeg:"1IQKHP2G80",outlet:"1IQMHH4HA1"};
	};
	HasAssets.jaxId="1IQKHP2G80"
	HasAssets.url="HasAssets@"+agentURL
	
	segs["ReadAssets"]=ReadAssets=async function(input){//:1IQKJB1N50
		let result=input
		/*#{1IQKJB1N50Code*/
		let list,i,n,url,data;
		list=codeResult.assets;
		n=list.length;
		for(i=0;i<n;i++){
			url=list[i];
			if(url.startsWith("hub://")){
				try{
					data=await session.loadHubFile(url);
					data=Base64.decodeBytes(data);
					const decoder = new TextDecoder('utf-8');
					data=decoder.decode(data)||"";
				}catch(err){
					//Read failed.
					data="NA.";
				}
			}else{
				try{
					data=await (await webFetch(url)).text();
				}catch(err){
					//Read failed
					data="NA";
				}
			}
			if(data.length>512){
				data=data.substring(0,256)+"...\n...\n..."+data.substring(data.length-256);
			}
			assetPreviews[url]=data;
		}
		/*}#1IQKJB1N50Code*/
		return {seg:JumpReview,result:(result),preSeg:"1IQKJB1N50",outlet:"1IQMHH4HA2"};
	};
	ReadAssets.jaxId="1IQKJB1N50"
	ReadAssets.url="ReadAssets@"+agentURL
	
	segs["AutoFix"]=AutoFix=async function(input){//:1IQKJDJFQ0
		let result=input;
		if(!!autoFix){
			return {seg:HasAssets,result:(input),preSeg:"1IQKJDJFQ0",outlet:"1IQMHH4HA3"};
		}
		return {seg:AskFix,result:(result),preSeg:"1IQKJDJFQ0",outlet:"1IQMHH4HA4"};
	};
	AutoFix.jaxId="1IQKJDJFQ0"
	AutoFix.url="AutoFix@"+agentURL
	
	segs["JumpReview"]=JumpReview=async function(input){//:1IQP0HO3L0
		let result=input;
		return {seg:Review,result:result,preSeg:"1IOK3BRBV0",outlet:"1IQP36VGG0"};
	
	};
	JumpReview.jaxId="1IOK3BRBV0"
	JumpReview.url="JumpReview@"+agentURL
	
	segs["ReviewResult"]=ReviewResult=async function(input){//:1IQP0L6L20
		let result=input;
		if((input.result==="Finish") && (!input.issue)){
			let output=input;
			return {seg:Finish,result:(output),preSeg:"1IQP0L6L20",outlet:"1IQP36VGG1"};
		}
		result=input;
		return {seg:FixCode,result:(result),preSeg:"1IQP0L6L20",outlet:"1IQP36VGG2"};
	};
	ReviewResult.jaxId="1IQP0L6L20"
	ReviewResult.url="ReviewResult@"+agentURL
	
	segs["CheckRetry"]=CheckRetry=async function(input){//:1IQVH8R6H0
		let result=input;
		/*#{1IQVH8R6H0Start*/
		fixRound+=1;
		/*}#1IQVH8R6H0Start*/
		if(fixRound>0){
			return {seg:Failed2,result:(input),preSeg:"1IQVH8R6H0",outlet:"1IQVH9RON0"};
		}
		/*#{1IQVH8R6H0Post*/
		/*}#1IQVH8R6H0Post*/
		return {seg:WriteCode,result:(result),preSeg:"1IQVH8R6H0",outlet:"1IQVH9RON1"};
	};
	CheckRetry.jaxId="1IQVH8R6H0"
	CheckRetry.url="CheckRetry@"+agentURL
	
	segs["Failed2"]=Failed2=async function(input){//:1IQVHB8AI0
		let result=input
		/*#{1IQVHB8AI0Code*/
		result={"result":"Failed","content":(($ln==="CN")?("编写程序尝试失败。"):/*EN*/("Attempt to write and run program failed."))};
		/*}#1IQVHB8AI0Code*/
		return {result:result};
	};
	Failed2.jaxId="1IQVHB8AI0"
	Failed2.url="Failed2@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CodeInSandBox",
		url:agentURL,
		autoStart:true,
		jaxId:"1IOPMMTJ60",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{codePrompt,dataFiles,autoFix}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IOPMMTJ60PreEntry*/
			/*}#1IOPMMTJ60PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IOPMMTJ60PostEntry*/
			/*}#1IOPMMTJ60PostEntry*/
			return result;
		},
		/*#{1IOPMMTJ60MoreAgentAttrs*/
		/*}#1IOPMMTJ60MoreAgentAttrs*/
	};
	/*#{1IOPMMTJ60PostAgent*/
	/*}#1IOPMMTJ60PostAgent*/
	return agent;
};
/*#{1IOPMMTJ60ExCodes*/
/*}#1IOPMMTJ60ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "CodeInSandBox",
		description: "这是根据要求（可以额外提供数据文件），编写在Web-Sandbox中运行代码，输出结果的智能体。通常用来进行复杂的数据统计运算等。",
		parameters:{
			type: "object",
			properties:{
				codePrompt:{type:"auto",description:"要编写代码的需求描述，以及每一个数据文件的内容说明。"},
				dataFiles:{type:"auto",description:"字符串数组：如果有，要处理的数据文件的URL字符串数组。"},
				autoFix:{type:"bool",description:""}
			}
		}
	},
	agent: CodeInSandBox
}];
//#CodyExport<<<
/*#{1IOPMMTJ60PostDoc*/
/*}#1IOPMMTJ60PostDoc*/


export default CodeInSandBox;
export{CodeInSandBox};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IOPMMTJ60",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IOGIVKVU1",
//			"attrs": {
//				"CodeInSandBox": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IOGIVKVU7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IOGIVKVU8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IOGIVKVU9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IOGIVKVU10",
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
//			"jaxId": "1IOGIVKVU2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IOGIVKVU3",
//			"attrs": {
//				"codePrompt": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOGJ4KD00",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "要编写代码的需求描述，以及每一个数据文件的内容说明。"
//					}
//				},
//				"dataFiles": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOGJ4KD01",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "#[]",
//						"desc": "字符串数组：如果有，要处理的数据文件的URL字符串数组。",
//						"required": "false"
//					}
//				},
//				"autoFix": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IQMHH4HD0",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "true",
//						"desc": "",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IOGIVKVU4",
//			"attrs": {
//				"filePreviews": {
//					"type": "auto",
//					"valText": "{}"
//				},
//				"curCode": {
//					"type": "string",
//					"valText": ""
//				},
//				"runLogs": {
//					"type": "auto",
//					"valText": "[]"
//				},
//				"codeResult": {
//					"type": "auto",
//					"valText": ""
//				},
//				"fixRound": {
//					"type": "int",
//					"valText": "0"
//				},
//				"htmlCode": {
//					"type": "string",
//					"valText": ""
//				},
//				"isFixError": {
//					"type": "bool",
//					"valText": "false"
//				},
//				"assetPreviews": {
//					"type": "auto",
//					"valText": "#{}"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IOGIVKVU5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IOGIVKVU6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IOGJACVV0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "100",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "true",
//						"outlet": {
//							"jaxId": "1IOGJAKMK0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOLB69NF0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IOLB69NF0",
//					"attrs": {
//						"id": "ShowTarget",
//						"viewName": "",
//						"label": "",
//						"x": "325",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOLB8BLM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOLB8BLM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "#`Coding command: ${codePrompt}`",
//							"localize": {
//								"EN": "#`Coding command: ${codePrompt}`",
//								"CN": "#`编程指令: ${codePrompt}`"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IOLB8BLG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJBC210"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1IOGJBC210",
//					"attrs": {
//						"id": "LoopFiles",
//						"viewName": "",
//						"label": "",
//						"x": "575",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJDPK70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJDPK71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#dataFiles",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1IOGJDPK50",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOLB92070"
//						},
//						"catchlet": {
//							"jaxId": "1IOGJDPK51",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOLBG0AT0"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IOGJCG480",
//					"attrs": {
//						"id": "PreviewDataFile",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJDPK72",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJDPK73",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOGJDPK52",
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
//					"def": "output",
//					"jaxId": "1IOLB92070",
//					"attrs": {
//						"id": "TipPreview",
//						"viewName": "",
//						"label": "",
//						"x": "810",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOLBD4E40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOLBD4E41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Log",
//						"text": {
//							"type": "string",
//							"valText": "#`Analyzing data file: ${input}`",
//							"localize": {
//								"EN": "#`Analyzing data file: ${input}`",
//								"CN": "#`正在分析数据文件：${input}`"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IOLBBTB30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJCG480"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IOLBGCNQ0",
//					"attrs": {
//						"id": "TipStart",
//						"viewName": "",
//						"label": "",
//						"x": "1280",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOLBI1VA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOLBI1VA2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Log",
//						"text": {
//							"type": "string",
//							"valText": "Start writing code",
//							"localize": {
//								"EN": "Start writing code",
//								"CN": "开始编写代码"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IOLBI1V60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJDDV50"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IOGJDDV50",
//					"attrs": {
//						"id": "WriteCode",
//						"viewName": "",
//						"label": "",
//						"x": "1535",
//						"y": "300",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJDPK74",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJDPK75",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "Claude",
//						"mode": "claude-3-7-sonnet-latest",
//						"system": "#`\n## 环境:\n现在是: ${\"\"+(new Date()).toString()}\n\n- - -\n## 角色\n你是一个根据用户需求，编写（包括调试/修正）: ${(filePreviews&&filePreviews.length)?\"使用用户给出的数据文件\":\"\"}，运行并输出所需要结果的函数代码的AI智能体。\n\n- - -\n## 用户需求\n${codePrompt}\n\n- - -\n## 数据文件内容概览：\n${JSON.stringify(filePreviews,null,\"\\t\")}\n\n- - -\n## 读取数据文件\n- 你可以用fetch函数读取数据文件。\n\n- - -\n## 运行环境\n- 执行环境：你输出的Javascript函数将运行在Web环境而不是Node.js环境里\n- 页面：当前页面是空白页面\n- 当前页面 没有引入任何库。如果需要引入库，请在回复JOSN里的\"imports\"属性中列出来。\n\n- - - \n## 编写函数\n- runCode函数：你输出的代码必须是函数名为runCode的异步无参数javascript函数。你的函数应该：如果存在数据文件，读取数据文件；根据需求计算结果；返回结果。\n\n- runCode函数返回值：runCode函数返回结果必须是一个JOSN对象，包含两个属性：\"result\"和\"assets\".\n    - \"result\" {string}: 执行结果，如果函数的返回内容很简单，\"result\"属性可以是直接的结果。如果返回内容比较复杂，或者返回多内容是在文件中，\"result\"应该是执行结果的自然语言描述，如果结果包含输出文件，result也应该包括每个输出的文件的内容解释。注意：解释文件时，你应该使用文件url（调用saveFile函数的返回值）而不是文件名。\n    - \"assets\" {arrary<string>|null}: 函数执行保存的结果文件的文件url（调用saveFile函数的返回值）数组。如果函数不需要输出文件，这个属性为null.\n\n- 复杂/大数据量返回值：如果函数执行后的结果数据比较复杂，或者数据量很大，或者是多媒体文件，例如视频/图片。你要把结果保存在文件里\n\n- 保存文件API：如果需要向文件中输出结果（例如数据列表、图片、视频）。请调用saveFile全局函数。saveFile是一个异步全局函数，需要两个参数：\"fileName\"和\"data\"其中：\"fileName\"是要保存的文件名，不要包括任何路径。\"data\"是要保存的数据内容，可以是字符串、ArrayBuffer和ByteArray。saveFile函数会返回保存后文件的访问url。\n\n- 抛出异常：如果执行遇到问题，应该抛出对应的异常，用于分析调试。\n\n- 跨域访问：执行环境中的fetch方法是支持跨越访问的，你编写的函数应该使用fetch方法调用网络API。\n\n- Log: 在执行函数的重要节点添加输出log（使用console.log函数就好）的代码，方便调试纠错。\n\n- - -\n## 对话\n- 第一轮对话，用户会指示你开始编写函数\n- 之后的对话，用户会给出当前的函数代码；当前的函数代码的执行情况；还可能给出修改建议；或者回答你提出的问题。\n- 你根据当前对话过程，用JSON回复用户\n    - 如果你可以根据当前掌握信息可以输出函数代码，请在JSON中的\"code\"属性中提供完整的getData函数代码。如果你需要使用额外的代码库，请把库文件的链接，放在\"imports\"数组属性中例如：\n    \\`\\`\\`\n    {\n    \t\"code\":\"async function runCode(){...}\",\n        \"imports\":[\"https://cdn.jsdelivr.net...lib1.js\",\"https://cdn.jsdelivr.net...lib2.js\"]\n    }\n    \\`\\`\\`\n    \n    - 如果你缺少必要的信息来生成函数，请在JSON的\"chat\"属性中向用户提出问题或与用户对话完善编写网页所需的信息。例如：\n    \\`\\`\\`\n    {\n    \t\"chat\":\"请提供调用比特币实时价格 API XXXXXXXX 的Key。你可以通过.....获得你的Key。\"\n    }\n    \\`\\`\\`\n## 回复JSON对象属性\n- \"code\" {string}: 你生成的runCode函数，注意一定是完整的函数代码。\n- \"imports\" {array<string>} 执行你的函数，页面需要引入的额外脚本文件链接，页面会用<script>标记引入\n- \"chat\" {string}: 为了完善必要的信息或回答用户的疑问，与用户的对话信息。\n\n## 引入脚本和库文件\n如果执行你的函数需要HTML页面引入额外的脚本/库，请把它们列在在回复JSON的\"imports\"属性中。\n\n`",
//						"temperature": "0",
//						"maxToken": "15000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#input",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IOGJDPK53",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJEOI10"
//						},
//						"secret": "false",
//						"allowCheat": "true",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1IOIF31GN0",
//									"attrs": {
//										"prompt": "0",
//										"reply": "{\"code\":\"async function runCode() {\\n    // 使用埃拉托斯特尼筛法(Sieve of Eratosthenes)找出1000以内的所有质数\\n    function findPrimes(limit) {\\n        // 创建一个布尔数组，初始假设所有数字都是质数\\n        const isPrime = Array(limit + 1).fill(true);\\n        \\n        // 0和1不是质数\\n        isPrime[0] = isPrime[1] = false;\\n        \\n        // 埃拉托斯特尼筛法\\n        for (let i = 2; i * i <= limit; i++) {\\n            if (isPrime[i]) {\\n                // 将i的所有倍数标记为非质数\\n                for (let j = i * i; j <= limit; j += i) {\\n                    isPrime[j] = false;\\n                }\\n            }\\n        }\\n        \\n        // 收集所有质数\\n        const primes = [];\\n        for (let i = 2; i <= limit; i++) {\\n            if (isPrime[i]) {\\n                primes.push(i);\\n            }\\n        }\\n        \\n        return primes;\\n    }\\n    \\n    // 找出1000以内的所有质数\\n    const primes = findPrimes(1000);\\n    const count = primes.length;\\n    \\n    // 将质数列表转换为字符串\\n    const primesStr = primes.join('\\\\n');\\n    \\n    // 保存质数到文件\\n    const fileUrl = await saveFile('primes.txt', primesStr);\\n    \\n    console.log(`找到了${count}个1000以内的质数`);\\n    console.log(`质数已保存到文件: ${fileUrl}`);\\n    \\n    return {\\n        result: `1000以内共有${count}个质数。所有质数已保存到文件中: ${fileUrl}`,\\n        assets: [fileUrl]\\n    };\\n}\",\"imports\":[]}"
//									}
//								}
//							]
//						},
//						"shareChatName": "",
//						"keepChat": "All messages",
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
//					"jaxId": "1IOGJEOI10",
//					"attrs": {
//						"id": "CheckCode",
//						"viewName": "",
//						"label": "",
//						"x": "1755",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJU61C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJU61C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOGJU6181",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IOGJHFDB0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IOGJU6180",
//									"attrs": {
//										"id": "Chat",
//										"desc": "输出节点。",
//										"output": "#input.chat",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOGJU61C2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOGJU61C3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.chat && (!input.code)"
//									},
//									"linkedSeg": "1IOGJG3610"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IOGJF0P50",
//									"attrs": {
//										"id": "Code",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOGJU61C4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOGJU61C5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.code"
//									},
//									"linkedSeg": "1IOGJIN1C0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IOPP6NI30",
//									"attrs": {
//										"id": "Tool",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOPP6NIA0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOPP6NIB0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.tool"
//									},
//									"linkedSeg": "1IOPOTF0Q0"
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
//					"jaxId": "1IOGJG3610",
//					"attrs": {
//						"id": "AskChat",
//						"viewName": "",
//						"label": "",
//						"x": "2005",
//						"y": "125",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJU61C6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJU61C7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#input",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "No",
//						"outlet": {
//							"jaxId": "1IOGJU6182",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJGDFR0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IOGJGDFR0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2135",
//						"y": "-105",
//						"outlet": {
//							"jaxId": "1IOGJU61C8",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJGK3H0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IOGJGK3H0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1560",
//						"y": "-105",
//						"outlet": {
//							"jaxId": "1IOGJU61C9",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJDDV50"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IOGJHFDB0",
//					"attrs": {
//						"id": "BadReply",
//						"viewName": "",
//						"label": "",
//						"x": "2005",
//						"y": "475",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJU61C10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJU61C11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOGJU6183",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJI38R0"
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
//					"jaxId": "1IOGJI38R0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2140",
//						"y": "555",
//						"outlet": {
//							"jaxId": "1IOGJU61C12",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJI8RK0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IOGJI8RK0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1560",
//						"y": "555",
//						"outlet": {
//							"jaxId": "1IOGJU61C13",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJDDV50"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IOGJIN1C0",
//					"attrs": {
//						"id": "ShowCode",
//						"viewName": "",
//						"label": "",
//						"x": "2005",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJU61C14",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJU61C15",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`\n#### ${(($ln===\"CN\")?(\"执行函数\"):/*EN*/(\"Execute function\"))}\n\\`\\`\\`\n${input.code}\n\\`\\`\\`\n#### ${(($ln===\"CN\")?(\"需要额外引入的脚本\"):/*EN*/(\"Additional script needed\"))}\n${input.imports?JSON.stringify(input.imports,null,\"\\t\"):\"无\"}\n`",
//						"outlet": {
//							"jaxId": "1IOGJU6184",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJJ4QM0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IOGJJ4QM0",
//					"attrs": {
//						"id": "RunCode",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJU61C16",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJU61C17",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOGJU6185",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJKH1Q0"
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
//					"jaxId": "1IOGJKH1Q0",
//					"attrs": {
//						"id": "CheckError",
//						"viewName": "",
//						"label": "",
//						"x": "2480",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJKH1Q1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJKH1Q2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOGJKH1Q3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IQC4A1K40"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IOGJKH1Q4",
//									"attrs": {
//										"id": "Error",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IOGJKH1Q5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOGJKH1Q6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.error"
//									},
//									"linkedSeg": "1IOGJLB760"
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
//					"jaxId": "1IOGJLB760",
//					"attrs": {
//						"id": "ShowError",
//						"viewName": "",
//						"label": "",
//						"x": "2725",
//						"y": "45",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJLB761",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJLB762",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`发现页面错误：${input.error}`",
//						"outlet": {
//							"jaxId": "1IOGJLB763",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOIIK8TJ0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IOGJNELB0",
//					"attrs": {
//						"id": "AskFix",
//						"viewName": "",
//						"label": "",
//						"x": "3200",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "当前结果是否满足需求？如果需要修改，请直接输入修改指导。",
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1IOGJU6187",
//							"attrs": {
//								"id": "FixInput",
//								"desc": "输出节点。",
//								"codes": "true"
//							},
//							"linkedSeg": "1IOK3R1BI0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IOGJNEKP0",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"text": "图片符合需求，结束。",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOGJU61C20",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOGJU61C21",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IQP361A70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IOK3P3NB0",
//									"attrs": {
//										"id": "Auto",
//										"desc": "输出节点。",
//										"text": "自我评估改进",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOK3P3NJ0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOK3P3NJ1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IOK3BRBV0"
//								}
//							]
//						},
//						"silent": "false",
//						"silentOutlet": "Auto"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IOGJR48U0",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "3905",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IOGJU61C22",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJU61C23",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOGJU6190",
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
//					"def": "code",
//					"jaxId": "1IOGJTKJ90",
//					"attrs": {
//						"id": "FixError",
//						"viewName": "",
//						"label": "",
//						"x": "3200",
//						"y": "-5",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJU61C28",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJU61C29",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOGJU6192",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJTTR00"
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
//					"def": "code",
//					"jaxId": "1IOGJRU5V0",
//					"attrs": {
//						"id": "FixCode",
//						"viewName": "",
//						"label": "",
//						"x": "3905",
//						"y": "455",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJU61C24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJU61C25",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOGJU6191",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQVH8R6H0"
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
//					"def": "code",
//					"jaxId": "1IOJ68MHG0",
//					"attrs": {
//						"id": "ManualFix",
//						"viewName": "",
//						"label": "",
//						"x": "3705",
//						"y": "140",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOJ6BPTH4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOJ6BPTH5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOJ6BPTA2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQP0K5720"
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
//					"jaxId": "1IOGJSI950",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2860",
//						"y": "555",
//						"outlet": {
//							"jaxId": "1IOGJU61C27",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOPP44LG0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IOGJTTR00",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3330",
//						"y": "-105",
//						"outlet": {
//							"jaxId": "1IOGJU61C30",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJGDFR0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IOIIK8TJ0",
//					"attrs": {
//						"id": "CheckFix",
//						"viewName": "",
//						"label": "",
//						"x": "2985",
//						"y": "45",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOIINA3F0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOIINA3F1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOIINA381",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IOJ63UOM0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IOIINA380",
//									"attrs": {
//										"id": "Fix",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOIINA3F2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOIINA3F3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#fixRound<0"
//									},
//									"linkedSeg": "1IOGJTKJ90"
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
//					"jaxId": "1IOIIM6AK0",
//					"attrs": {
//						"id": "Failed",
//						"viewName": "",
//						"label": "",
//						"x": "3705",
//						"y": "60",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IOIINA3F4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOIINA3F5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOIINA390",
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
//					"def": "askMenu",
//					"jaxId": "1IOJ63UOM0",
//					"attrs": {
//						"id": "AskRetry",
//						"viewName": "",
//						"label": "",
//						"x": "3465",
//						"y": "60",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "修改代码次数过多，是否继续修改，或者请提出修改指导",
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1IOJ6BPTA0",
//							"attrs": {
//								"id": "Manual",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1IOJ68MHG0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IOJ63UO30",
//									"attrs": {
//										"id": "Retry",
//										"desc": "输出节点。",
//										"text": "继续尝试修改",
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOJ6BPTH0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOJ6BPTH1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IOJ66R7R0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IOJ63UO31",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "放弃绘制",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOJ6BPTH2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOJ6BPTH3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IOIIM6AK0"
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
//					"jaxId": "1IOJ66R7R0",
//					"attrs": {
//						"id": "JumpFix",
//						"viewName": "",
//						"label": "",
//						"x": "3705",
//						"y": "-20",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1IOGJTKJ90",
//						"outlet": {
//							"jaxId": "1IOJ6BPTA1",
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
//					"jaxId": "1IOJ6C5FU0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "4290",
//						"y": "555",
//						"outlet": {
//							"jaxId": "1IOJ6CE0O0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJSI950"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IOK3BRBV0",
//					"attrs": {
//						"id": "Review",
//						"viewName": "",
//						"label": "",
//						"x": "3430",
//						"y": "380",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOK3P3NJ2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOK3P3NJ3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`\n## 角色\n你是一个评估AI编写的代码函数执行结果，提出修改建议的智能体\n\n## 当前AI编写的函数执行目标：\n${codePrompt}\n\n## AI编写的函数执行结果:\n${JSON.stringify(codeResult.result)}\n\n## 执行输出文件(如果有)的内容预览\n${JSON.stringify(assetPreviews,null,\"\\t\")}\n\n- - -\n## 代码执行日志\n${JSON.stringify(logs,null,\"\\t\")}\n\n- - -\n## 对话\n- 请根据**当前函数执行目标**，分析并指出执行结果以及附件是否有符合需求，如果存在问题，指出问题并提出修改方案\n- 你必须用JSON回复问题\n- 回复JSON参数：\n    - \"result\" {\"Finish\"|\"Fix\"}: 当执行结果正确并满足需求，设置\"result\"属性为\"Finish\"。反之，如果需要修改，设置为\"Fix\"。\n    - \"issue\" {string|null}: 如果存在问题需要修改，这个属性是问题描述和修改指导。\n    例如，如果不需要修改：\n    {\n    \t\"result\":\"Finsish\",\n        \"issue\":null\n    }\n    例如，如果存在问题：\n    {\n    \t\"result\":\"Fix\",\n        \"issue\":\"返回的数据单位与要求不同，要求的是摄氏度，返回的是华氏度。请修改确保返回的是摄氏度。\"\n    }\n`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "请分析并返回结果",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IOK3P3NC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQP0L6L20"
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
//					"def": "connectorL",
//					"jaxId": "1IOK3R1BI0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3425",
//						"y": "455",
//						"outlet": {
//							"jaxId": "1IOK3S55C0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJRU5V0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IOLBG0AT0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "985",
//						"y": "300",
//						"outlet": {
//							"jaxId": "1IOLBI1VA0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOLBGCNQ0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IOPOTF0Q0",
//					"attrs": {
//						"id": "TryTool",
//						"viewName": "",
//						"label": "",
//						"x": "2005",
//						"y": "360",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOPP6NIB1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOPP6NIB2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOPP6NI50",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOPOUH1F0"
//						},
//						"catchlet": {
//							"jaxId": "1IOPP6NI51",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOPOU4QL0"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IOPOU4QL0",
//					"attrs": {
//						"id": "ToolError",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOPP6NIB3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOPP6NIB4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOPP6NI52",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOPP44LG0"
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
//					"def": "output",
//					"jaxId": "1IOPOUH1F0",
//					"attrs": {
//						"id": "TipTool",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOPP6NIB5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOPP6NIB6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IOPP6NI53",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOPOUS1O0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IOPOUS1O0",
//					"attrs": {
//						"id": "CallTool",
//						"viewName": "",
//						"label": "",
//						"x": "2485",
//						"y": "345",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOPP6NIB7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOPP6NIB8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IOPP6NI54",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOPP1MS70"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIAgentAskOutlet",
//									"jaxId": "1IOPP6NIB9",
//									"attrs": {
//										"id": "Ask",
//										"desc": "回复智能体执行时提出问题的路径",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IOPP6NIB10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOPP6NIB11",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IOPP2FML0"
//								}
//							]
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IOPP1MS70",
//					"attrs": {
//						"id": "ToolResult",
//						"viewName": "",
//						"label": "",
//						"x": "2725",
//						"y": "330",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOPP6NIB12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOPP6NIB13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOPP6NI55",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJSI950"
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
//					"def": "aiBot",
//					"jaxId": "1IOPP2FML0",
//					"attrs": {
//						"id": "ReplyTool",
//						"viewName": "",
//						"label": "",
//						"x": "2725",
//						"y": "420",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOPP6NIB14",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOPP6NIB15",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IOPP6NI56",
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
//					"def": "connector",
//					"jaxId": "1IOPP44LG0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2385",
//						"y": "555",
//						"outlet": {
//							"jaxId": "1IOPP6NIB16",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJI38R0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IQC4A1K40",
//					"attrs": {
//						"id": "ShowResult",
//						"viewName": "",
//						"label": "",
//						"x": "2725",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IQC4CBAT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQC4CBAT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IQC4CBAQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQKJDJFQ0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IQKHP2G80",
//					"attrs": {
//						"id": "HasAssets",
//						"viewName": "",
//						"label": "",
//						"x": "3200",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IQMHH4HE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQMHH4HE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IQMHH4HA1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IQP0HO3L0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IQMHH4HA0",
//									"attrs": {
//										"id": "Assets",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IQMHH4HE2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IQMHH4HE3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#codeResult.assets && codeResult.assets.length"
//									},
//									"linkedSeg": "1IQKJB1N50"
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
//					"jaxId": "1IQKJB1N50",
//					"attrs": {
//						"id": "ReadAssets",
//						"viewName": "",
//						"label": "",
//						"x": "3425",
//						"y": "175",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IQMHH4HE4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQMHH4HE5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IQMHH4HA2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IQP0HO3L0"
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
//					"jaxId": "1IQKJDJFQ0",
//					"attrs": {
//						"id": "AutoFix",
//						"viewName": "",
//						"label": "",
//						"x": "2985",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IQMHH4HE6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQMHH4HE7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IQMHH4HA4",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IOGJNELB0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IQMHH4HA3",
//									"attrs": {
//										"id": "Auto",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IQMHH4HE8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IQMHH4HE9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!autoFix"
//									},
//									"linkedSeg": "1IQKHP2G80"
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
//					"jaxId": "1IQP0HO3L0",
//					"attrs": {
//						"id": "JumpReview",
//						"viewName": "",
//						"label": "",
//						"x": "3675",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1IOK3BRBV0",
//						"outlet": {
//							"jaxId": "1IQP36VGG0",
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
//					"jaxId": "1IQP0K5720",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3850",
//						"y": "-105",
//						"outlet": {
//							"jaxId": "1IQP36VGL0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJTTR00"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IQP0L6L20",
//					"attrs": {
//						"id": "ReviewResult",
//						"viewName": "",
//						"label": "",
//						"x": "3640",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IQP36VGL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQP36VGL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IQP36VGG2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": "#input"
//							},
//							"linkedSeg": "1IOGJRU5V0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IQP36VGG1",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IQP36VGL3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IQP36VGL4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#(input.result===\"Finish\") && (!input.issue)"
//									},
//									"linkedSeg": "1IOGJR48U0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IQP361A70",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3425",
//						"y": "300",
//						"outlet": {
//							"jaxId": "1IQP36VGL5",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJR48U0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IQVH8R6H0",
//					"attrs": {
//						"id": "CheckRetry",
//						"viewName": "",
//						"label": "",
//						"x": "4115",
//						"y": "455",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IQVHAB5P0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQVHAB5P1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IQVH9RON1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IOJ6C5FU0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IQVH9RON0",
//									"attrs": {
//										"id": "MaxRetry",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IQVHAB5P2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IQVHAB5P3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#fixRound>0"
//									},
//									"linkedSeg": "1IQVHB8AI0"
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
//					"jaxId": "1IQVHB8AI0",
//					"attrs": {
//						"id": "Failed2",
//						"viewName": "",
//						"label": "",
//						"x": "4370",
//						"y": "440",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IQVHBU8N0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IQVHBU8N1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IQVHBIDO0",
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
//				}
//			]
//		},
//		"desc": "这是根据要求（可以额外提供数据文件），编写在Web-Sandbox中运行代码，输出结果的智能体。通常用来进行复杂的数据统计运算等。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}