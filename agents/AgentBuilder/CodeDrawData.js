//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IOGIVKVU0MoreImports*/
import {webFetch,tabNT} from "/@tabos";
/*}#1IOGIVKVU0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"drawPrompt":{
			"name":"drawPrompt","type":"auto",
			"defaultValue":"",
			"desc":"绘制的图表需求描述，以及每一个数据文件的内容说明。",
		},
		"dataFiles":{
			"name":"dataFiles","type":"auto",
			"defaultValue":"",
			"desc":"字符串数组，绘制图表的数据文件的URL字符串数组",
		}
	},
	/*#{1IOGIVKVU0ArgsView*/
	/*}#1IOGIVKVU0ArgsView*/
};

/*#{1IOGIVKVU0StartDoc*/
/*}#1IOGIVKVU0StartDoc*/
//----------------------------------------------------------------------------
let CodeDrawData=async function(session){
	let drawPrompt,dataFiles;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,ShowTarget,LoopFiles,PreviewDataFile,TipPreview,TipStart,WriteCode,CheckCode,AskChat,BadReply,ShowCode,RunCode,ShowResult,CheckError,ShowError,AskFix,Finish,FixError,FixWithPic,ManualFix,CheckFix,Failed,CheckImage,AskRetry,JumpFix,Review;
	let filePreviews={};
	let curCode="";
	let runLogs=[];
	let codeResult=undefined;
	let fixRound=0;
	let htmlCode="";
	let isFixError=false;
	
	/*#{1IOGIVKVU0LocalVals*/
	/*}#1IOGIVKVU0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			drawPrompt=input.drawPrompt;
			dataFiles=input.dataFiles;
		}else{
			drawPrompt=undefined;
			dataFiles=undefined;
		}
		/*#{1IOGIVKVU0ParseArgs*/
		/*}#1IOGIVKVU0ParseArgs*/
	}
	
	/*#{1IOGIVKVU0PreContext*/
	/*}#1IOGIVKVU0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IOGIVKVU0PostContext*/
	/*}#1IOGIVKVU0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IOGJACVV0
		let result=input;
		let missing=false;
		let smartAsk=true;
		if(drawPrompt===undefined || drawPrompt==="") missing=true;
		if(dataFiles===undefined || dataFiles==="") missing=true;
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
		let content=(($ln==="CN")?(`绘制指令: ${drawPrompt}`):(`Drawing command: ${drawPrompt}`));
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
		let content=(($ln==="CN")?("开始编写绘制函数"):("Start writing the drawing function"));
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
你是一个根据用户需求，编写（包括调试/修正）使用用户给出的文件绘制图表的Javascript函数的AI编程智能体。

- - -
## 用户需求
${drawPrompt}

- - -
## 数据文件内容概览：
${JSON.stringify(filePreviews,null,"\t")}

- - -
## 读取数据文件
- 你可以用fetch函数读取数据文件。

- - -
## 绘制环境
- 执行环境：你输出的Javascript函数将运行在Web环境而不是Node.js环境里
- 页面：当前页面是空白页面，你需要自己用代码添加绘制的Canvas等元素
- 当前页面 已经引入Chart.js库了，你可以直接使用。如果需要别的库，请在回复JOSN里的"imports"属性中列出来。

- - - 
## 编写函数
- 函数：你输出的代码必须是函数名为drawData的异步无参数javascript函数。你的函数应该：创建绘制Canvas；读取数据文件；绘制图表

- 返回值：函数执行后返回绘制图表的PNG格式的DataURL字符串

- 跨域访问：执行环境中的fetch方法是支持跨越访问的，你编写的函数应该使用fetch方法调用网络API。

- 延时输出：Chart.js绘制通常会带有动画，绘制后要等大概1～2秒再读取Canvas里的内容返回

- Log: 在执行函数的重要节点添加输出log（使用console.log函数就好）的代码，方便调试纠错。

- - -
## 对话
- 第一轮对话，用户会指示你开始编写绘制函数
- 之后的对话，用户会给出当前的函数代码；当前的函数代码的执行情况；还可能给出修改建议；或者回答你提出的问题。
- 你根据当前对话过程，用JSON回复用户
    - 如果你可以根据当前掌握信息可以输出函数代码，请在JSON中的"code"属性中提供完整的getData函数代码。如果你需要使用出了Char.js以外的库，请把库文件的链接，放在"imports"数组属性中例如：
    \`\`\`
    {
    	"code":"async function getData(){...}",
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
- "code" {string}: 你生成的drawData函数，注意一定是完整的函数代码。
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
		result=(result===null)?(await session.callSegLLM("WriteCode@"+agentURL,opts,messages,true)):result;
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
	
	segs["CheckCode"]=CheckCode=async function(input){//:1IOGJEOI10
		let result=input;
		if(input.chat && (!input.code)){
			let output=input.chat;
			return {seg:AskChat,result:(output),preSeg:"1IOGJEOI10",outlet:"1IOGJU6180"};
		}
		if(input.code){
			return {seg:ShowCode,result:(input),preSeg:"1IOGJEOI10",outlet:"1IOGJF0P50"};
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
### 绘制函数
\`\`\`
${input.code}
\`\`\`
### 需要额外引入的脚本
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
				<title>${(($ln==="CN")?("绘制图表"):/*EN*/("Fetch data"))}</title>
			</head>
			<body>
			</body>
			<script>
				function handleScriptError(url) {
					window.console.log(\`Load script failed:: \${url}\`);
				}
			</script>
			<script src="https://cdn.jsdelivr.net/npm/chart.js" onerror="handleScriptError(this.src)"></script>
			<script src="https://cdn.jsdelivr.net/npm/chartjs-chart-financial" onerror="handleScriptError(this.src)"></script>
			<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns" onerror="handleScriptError(this.src)"></script>
			<script src="https://cdn.jsdelivr.net/npm/luxon" onerror="handleScriptError(this.src)"></script>
			${importLines}
			<script type="module">
			${input.code}
			window.drawData=drawData;
			</script>
			<script type="module">
				window.run=async function(){
					return await drawData();
				}
			</script>
		</html>
		`;
		result=await session.WSCall_WebSandbox(htmlCode);
		runLogs=result.logs;
		if(result.result && result.result.startsWith("data:image")){
			codeResult=result.result;
		}else{
			codeResult=null;
		}
		/*}#1IOGJJ4QM0Code*/
		return {seg:CheckError,result:(result),preSeg:"1IOGJJ4QM0",outlet:"1IOGJU6185"};
	};
	RunCode.jaxId="1IOGJJ4QM0"
	RunCode.url="RunCode@"+agentURL
	
	segs["ShowResult"]=ShowResult=async function(input){//:1IOGJJRHJ0
		let result=input;
		let role="assistant";
		let content="智能体绘制的图表：";
		let vo={image:codeResult};
		session.addChatText(role,content,vo);
		return {seg:AskFix,result:(result),preSeg:"1IOGJJRHJ0",outlet:"1IOGJU6186"};
	};
	ShowResult.jaxId="1IOGJJRHJ0"
	ShowResult.url="ShowResult@"+agentURL
	
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
		return {seg:CheckImage,result:(result),preSeg:"1IOGJKH1Q0",outlet:"1IOGJKH1Q3"};
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
		let prompt=("当前图表是否满足需求？如果需要修改，请直接输入修改指导。")||input;
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
			return {seg:Finish,result:(result),preSeg:"1IOGJNELB0",outlet:"1IOGJNEKP0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			/*#{1IOGJU6187ChatInput*/
			/*}#1IOGJU6187ChatInput*/
			return {seg:FixWithPic,result:(result),preSeg:"1IOGJNELB0",outlet:"1IOGJU6187"};
		}else if(item.code===0){
			return {seg:Finish,result:(result),preSeg:"1IOGJNELB0",outlet:"1IOGJNEKP0"};
		}else if(item.code===1){
			return {seg:Review,result:(result),preSeg:"1IOGJNELB0",outlet:"1IOK3P3NB0"};
		}
		/*#{1IOGJU6187DefaultOutlet*/
		/*}#1IOGJU6187DefaultOutlet*/
		return {seg:FixWithPic,result:(result),preSeg:"1IOGJNELB0",outlet:"1IOGJU6187"};
	};
	AskFix.jaxId="1IOGJNELB0"
	AskFix.url="AskFix@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1IOGJR48U0
		let result=input
		/*#{1IOGJR48U0Code*/
		let hubUrl;
		hubUrl="hub://"+session.saveHubFile("drawChart.png",codeResult);
		result={result:"Finish",content:`图表已生成：${hubUrl}`,assets:[hubUrl]};
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
	
	segs["FixWithPic"]=FixWithPic=async function(input){//:1IOGJRU5V0
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
		result={
			prompt:`
		对于当前用户提出修改意见: ${input}
		
		附件是本次执行绘制的图表
		- - - 
		当前页面加载执行Log：
		
		${JSON.stringify(logs,null,"\t")}
		
		请参考当前页面结果和日志，根据用户的修改意见，修改代码后重新输出。如果缺失重要内容再与用户对话，否则不要打搅用户。
		`,
			assets:[codeResult]
		};
		/*}#1IOGJRU5V0Code*/
		return {seg:WriteCode,result:(result),preSeg:"1IOGJRU5V0",outlet:"1IOGJU6191"};
	};
	FixWithPic.jaxId="1IOGJRU5V0"
	FixWithPic.url="FixWithPic@"+agentURL
	
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
		result={"result":"Failed","content":(($ln==="CN")?("编写绘制程序尝试失败。"):/*EN*/("Attempt to write drawing program failed."))};
		/*}#1IOIIM6AK0Code*/
		return {result:result};
	};
	Failed.jaxId="1IOIIM6AK0"
	Failed.url="Failed@"+agentURL
	
	segs["CheckImage"]=CheckImage=async function(input){//:1IOINJR3R0
		let result=input;
		if(!codeResult){
			/*#{1IOINMGTI0Codes*/
			input.error="错误：函数没有输出任何图表。"
			/*}#1IOINMGTI0Codes*/
			return {seg:CheckFix,result:(input),preSeg:"1IOINJR3R0",outlet:"1IOINMGTI0"};
		}
		return {seg:ShowResult,result:(result),preSeg:"1IOINJR3R0",outlet:"1IOINMGTI1"};
	};
	CheckImage.jaxId="1IOINJR3R0"
	CheckImage.url="CheckImage@"+agentURL
	
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
			responseFormat:"text"
		};
		let chatMem=Review.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
## 角色
你是一个评估AI编写的绘图函数执行结果，提出修改建议的智能体

## 当前绘制函数执行目标：
${drawPrompt}

## 结果图片
用户输入的附件是AI编写的绘制结果图片

- - -
## 代码执行日志
${JSON.stringify(logs,null,"\t")}

- - -
## 对话
请根据**当前绘制函数执行目标**，分析并指出执行结果图片与目标存在哪些差异，存在什么问题，可以进行哪些优化。
`},
		];
		/*#{1IOK3BRBV0PrePrompt*/
		input={
			prompt:"图片是AI编写的函数执行结果，请提出修改建议。",
			assets:[codeResult]
		};
		/*}#1IOK3BRBV0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IOK3BRBV0FilterMessage*/
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
			messages.push({role:"user",content:`当前的函数代码: \n\`\`\`\n${curCode?curCode:"无"}\n\`\`\`\n`});
			/*}#1IOK3BRBV0FilterMessage*/
			messages.push(msg);
		}
		/*#{1IOK3BRBV0PreCall*/
		/*}#1IOK3BRBV0PreCall*/
		result=(result===null)?(await session.callSegLLM("Review@"+agentURL,opts,messages,true)):result;
		/*#{1IOK3BRBV0PostCall*/
		/*}#1IOK3BRBV0PostCall*/
		return {seg:FixWithPic,result:(result),preSeg:"1IOK3BRBV0",outlet:"1IOK3P3NC0"};
	};
	Review.jaxId="1IOK3BRBV0"
	Review.url="Review@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"CodeDrawData",
		url:agentURL,
		autoStart:true,
		jaxId:"1IOGIVKVU0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{drawPrompt,dataFiles}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IOGIVKVU0PreEntry*/
			/*}#1IOGIVKVU0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IOGIVKVU0PostEntry*/
			/*}#1IOGIVKVU0PostEntry*/
			return result;
		},
		/*#{1IOGIVKVU0MoreAgentAttrs*/
		/*}#1IOGIVKVU0MoreAgentAttrs*/
	};
	/*#{1IOGIVKVU0PostAgent*/
	/*}#1IOGIVKVU0PostAgent*/
	return agent;
};
/*#{1IOGIVKVU0ExCodes*/
/*}#1IOGIVKVU0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "CodeDrawData",
		description: "这是根据要求，基于提供的数据文件绘制图表的智能体。每次可以绘制一张图表，请说明要绘制的图表要求，并提供绘制该图表需要的数据文件，以及每一个文件内容的说明。",
		parameters:{
			type: "object",
			properties:{
				drawPrompt:{type:"auto",description:"绘制的图表需求描述，以及每一个数据文件的内容说明。"},
				dataFiles:{type:"auto",description:"字符串数组，绘制图表的数据文件的URL字符串数组"}
			}
		}
	},
	agent: CodeDrawData
}];
//#CodyExport<<<
/*#{1IOGIVKVU0PostDoc*/
/*}#1IOGIVKVU0PostDoc*/


export default CodeDrawData;
export{CodeDrawData};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IOGIVKVU0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IOGIVKVU1",
//			"attrs": {
//				"CodeDrawData": {
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
//				"drawPrompt": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOGJ4KD00",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "绘制的图表需求描述，以及每一个数据文件的内容说明。"
//					}
//				},
//				"dataFiles": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IOGJ4KD01",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "字符串数组，绘制图表的数据文件的URL字符串数组"
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
//							"valText": "#`Drawing command: ${drawPrompt}`",
//							"localize": {
//								"EN": "#`Drawing command: ${drawPrompt}`",
//								"CN": "#`绘制指令: ${drawPrompt}`"
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
//							"valText": "Start writing the drawing function",
//							"localize": {
//								"EN": "Start writing the drawing function",
//								"CN": "开始编写绘制函数"
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
//						"system": "#`\n## 环境:\n现在是: ${\"\"+(new Date()).toString()}\n\n- - -\n## 角色\n你是一个根据用户需求，编写（包括调试/修正）使用用户给出的文件绘制图表的Javascript函数的AI编程智能体。\n\n- - -\n## 用户需求\n${drawPrompt}\n\n- - -\n## 数据文件内容概览：\n${JSON.stringify(filePreviews,null,\"\\t\")}\n\n- - -\n## 读取数据文件\n- 你可以用fetch函数读取数据文件。\n\n- - -\n## 绘制环境\n- 执行环境：你输出的Javascript函数将运行在Web环境而不是Node.js环境里\n- 页面：当前页面是空白页面，你需要自己用代码添加绘制的Canvas等元素\n- 当前页面 已经引入Chart.js库了，你可以直接使用。如果需要别的库，请在回复JOSN里的\"imports\"属性中列出来。\n\n- - - \n## 编写函数\n- 函数：你输出的代码必须是函数名为drawData的异步无参数javascript函数。你的函数应该：创建绘制Canvas；读取数据文件；绘制图表\n\n- 返回值：函数执行后返回绘制图表的PNG格式的DataURL字符串\n\n- 跨域访问：执行环境中的fetch方法是支持跨越访问的，你编写的函数应该使用fetch方法调用网络API。\n\n- 延时输出：Chart.js绘制通常会带有动画，绘制后要等大概1～2秒再读取Canvas里的内容返回\n\n- Log: 在执行函数的重要节点添加输出log（使用console.log函数就好）的代码，方便调试纠错。\n\n- - -\n## 对话\n- 第一轮对话，用户会指示你开始编写绘制函数\n- 之后的对话，用户会给出当前的函数代码；当前的函数代码的执行情况；还可能给出修改建议；或者回答你提出的问题。\n- 你根据当前对话过程，用JSON回复用户\n    - 如果你可以根据当前掌握信息可以输出函数代码，请在JSON中的\"code\"属性中提供完整的getData函数代码。如果你需要使用出了Char.js以外的库，请把库文件的链接，放在\"imports\"数组属性中例如：\n    \\`\\`\\`\n    {\n    \t\"code\":\"async function getData(){...}\",\n        \"imports\":[\"https://cdn.jsdelivr.net...lib1.js\",\"https://cdn.jsdelivr.net...lib2.js\"]\n    }\n    \\`\\`\\`\n    \n    - 如果你缺少必要的信息来生成函数，请在JSON的\"chat\"属性中向用户提出问题或与用户对话完善编写网页所需的信息。例如：\n    \\`\\`\\`\n    {\n    \t\"chat\":\"请提供调用比特币实时价格 API XXXXXXXX 的Key。你可以通过.....获得你的Key。\"\n    }\n    \\`\\`\\`\n## 回复JSON对象属性\n- \"code\" {string}: 你生成的drawData函数，注意一定是完整的函数代码。\n- \"imports\" {array<string>} 执行你的函数，页面需要引入的额外脚本文件链接，页面会用<script>标记引入\n- \"chat\" {string}: 为了完善必要的信息或回答用户的疑问，与用户的对话信息。\n\n## 引入脚本和库文件\n如果执行你的函数需要HTML页面引入额外的脚本/库，请把它们列在在回复JSON的\"imports\"属性中。\n\n`",
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
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1IOIF31GN0",
//									"attrs": {
//										"prompt": "0",
//										"reply": "{\"code\":\"async function drawData() {\\n console.log('Starting drawData function');\\n\\n // Create a canvas element\\n const canvas = document.createElement('canvas');\\n canvas.id = 'teslaChart';\\n document.body.appendChild(canvas);\\n console.log('Canvas element created');\\n\\n // Fetch the data file\\n const response = await fetch('hub://FILE-000248-FILE-000246-tesla_price.csv');\\n const dataText = await response.text();\\n console.log('Data file fetched');\\n\\n // Parse the CSV data\\n const rows = dataText.trim().split('\\\\n');\\n const labels = [];\\n const openPrices = [];\\n const highPrices = [];\\n const lowPrices = [];\\n const closePrices = [];\\n\\n for (let i = 1; i < rows.length; i++) {\\n const [date, open, high, low, close] = rows[i].split(',');\\n labels.push(date);\\n openPrices.push(parseFloat(open));\\n highPrices.push(parseFloat(high));\\n lowPrices.push(parseFloat(low));\\n closePrices.push(parseFloat(close));\\n }\\n console.log('CSV data parsed');\\n\\n // Prepare the data for Chart.js\\n const ctx = document.getElementById('teslaChart').getContext('2d');\\n const teslaChart = new Chart(ctx, {\\n type: 'candlestick',\\n data: {\\n labels: labels,\\n datasets: [{\\n label: 'Tesla Stock Price',\\n data: labels.map((label, index) => ({\\n t: label,\\n o: openPrices[index],\\n h: highPrices[index],\\n l: lowPrices[index],\\n c: closePrices[index],\\n })),\\n borderColor: 'rgba(75, 192, 192, 1)',\\n borderWidth: 1\\n }]\\n },\\n options: {\\n responsive: true,\\n scales: {\\n x: {\\n type: 'time',\\n time: {\\n unit: 'day'\\n }\\n },\\n y: {\\n beginAtZero: false\\n }\\n }\\n }\\n });\\n console.log('Chart created');\\n\\n // Wait for animations to complete\\n await new Promise(resolve => setTimeout(resolve, 2000));\\n\\n // Get the data URL of the chart\\n const dataURL = canvas.toDataURL('image/png');\\n console.log('Data URL generated');\\n\\n return dataURL;\\n}\",\"imports\":[\"https://cdn.jsdelivr.net/npm/chart.js\",\"https://cdn.jsdelivr.net/npm/chartjs-chart-financial\"]}"
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
//						"x": "2000",
//						"y": "210",
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
//						"x": "2125",
//						"y": "25",
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
//						"x": "1565",
//						"y": "25",
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
//						"x": "2000",
//						"y": "385",
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
//						"x": "2125",
//						"y": "485",
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
//						"x": "1565",
//						"y": "485",
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
//						"x": "2000",
//						"y": "300",
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
//						"text": "#`\n### 绘制函数\n\\`\\`\\`\n${input.code}\n\\`\\`\\`\n### 需要额外引入的脚本\n${input.imports?JSON.stringify(input.imports,null,\"\\t\"):\"无\"}\n`",
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
//						"x": "2240",
//						"y": "300",
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
//					"def": "image",
//					"jaxId": "1IOGJJRHJ0",
//					"attrs": {
//						"id": "ShowResult",
//						"viewName": "",
//						"label": "",
//						"x": "2980",
//						"y": "330",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOGJU61C18",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOGJU61C19",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"text": "智能体绘制的图表：",
//						"image": "#codeResult",
//						"role": "Assistant",
//						"sizeLimit": "",
//						"format": "JEPG",
//						"outlet": {
//							"jaxId": "1IOGJU6186",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJNELB0"
//						}
//					},
//					"icon": "hudimg.svg"
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
//						"y": "300",
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
//							"linkedSeg": "1IOINJR3R0"
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
//						"x": "2720",
//						"y": "165",
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
//						"x": "3225",
//						"y": "330",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "当前图表是否满足需求？如果需要修改，请直接输入修改指导。",
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
//									"linkedSeg": "1IOGJR48U0"
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
//						"silent": "false"
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
//						"x": "3450",
//						"y": "255",
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
//						"x": "3195",
//						"y": "115",
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
//						"id": "FixWithPic",
//						"viewName": "",
//						"label": "",
//						"x": "3665",
//						"y": "400",
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
//							"linkedSeg": "1IOGJSCQB0"
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
//						"x": "3870",
//						"y": "260",
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
//							"linkedSeg": "1IOJ6C5FU0"
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
//					"jaxId": "1IOGJSCQB0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3810",
//						"y": "485",
//						"outlet": {
//							"jaxId": "1IOGJU61C26",
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
//					"def": "connector",
//					"jaxId": "1IOGJSI950",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2730",
//						"y": "485",
//						"outlet": {
//							"jaxId": "1IOGJU61C27",
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
//					"def": "connector",
//					"jaxId": "1IOGJTTR00",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3325",
//						"y": "25",
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
//						"x": "2980",
//						"y": "165",
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
//						"x": "3870",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
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
//					"def": "brunch",
//					"jaxId": "1IOINJR3R0",
//					"attrs": {
//						"id": "CheckImage",
//						"viewName": "",
//						"label": "",
//						"x": "2720",
//						"y": "315",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IOINO47C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IOINO47C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IOINMGTI1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IOGJJRHJ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IOINMGTI0",
//									"attrs": {
//										"id": "NoImage",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IOINO47C2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IOINO47C3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!codeResult"
//									},
//									"linkedSeg": "1IOIIK8TJ0"
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
//					"jaxId": "1IOJ63UOM0",
//					"attrs": {
//						"id": "AskRetry",
//						"viewName": "",
//						"label": "",
//						"x": "3630",
//						"y": "180",
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
//								"id": "ChatInput",
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
//						"x": "3870",
//						"y": "100",
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
//						"x": "4005",
//						"y": "485",
//						"outlet": {
//							"jaxId": "1IOJ6CE0O0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJSCQB0"
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
//						"x": "3450",
//						"y": "330",
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
//						"system": "#`\n## 角色\n你是一个评估AI编写的绘图函数执行结果，提出修改建议的智能体\n\n## 当前绘制函数执行目标：\n${drawPrompt}\n\n## 结果图片\n用户输入的附件是AI编写的绘制结果图片\n\n- - -\n## 代码执行日志\n${JSON.stringify(logs,null,\"\\t\")}\n\n- - -\n## 对话\n请根据**当前绘制函数执行目标**，分析并指出执行结果图片与目标存在哪些差异，存在什么问题，可以进行哪些优化。\n`",
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
//							"jaxId": "1IOK3P3NC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IOGJRU5V0"
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
//						"responseFormat": "text",
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
//						"x": "3445",
//						"y": "400",
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
//				}
//			]
//		},
//		"desc": "这是根据要求，基于提供的数据文件绘制图表的智能体。每次可以绘制一张图表，请说明要绘制的图表要求，并提供绘制该图表需要的数据文件，以及每一个文件内容的说明。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}