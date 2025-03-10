//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*#{1ILSUCFLA0MoreImports*/
import AATools from "../../agenthub/AATools.mjs";
import AATask from "./Task.js";
/*}#1ILSUCFLA0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"webRpa":{
			"name":"webRpa","type":"auto",
			"required":false,
			"defaultValue":"",
			"desc":"",
		},
		"browser":{
			"name":"browser","type":"auto",
			"required":false,
			"defaultValue":"",
			"desc":"",
		},
		"page":{
			"name":"page","type":"auto",
			"required":false,
			"defaultValue":"",
			"desc":"",
		},
		"entryUrl":{
			"name":"entryUrl","type":"auto",
			"required":false,
			"defaultValue":"",
			"desc":"",
		},
		"task":{
			"name":"task","type":"auto",
			"required":true,
			"defaultValue":"",
			"desc":"",
		},
		"guide":{
			"name":"guide","type":"auto",
			"required":false,
			"defaultValue":"",
			"desc":"",
		},
		"tools":{
			"name":"tools","type":"auto",
			"required":false,
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1ILSUCFLA0ArgsView*/
	/*}#1ILSUCFLA0ArgsView*/
};

/*#{1ILSUCFLA0StartDoc*/
/*}#1ILSUCFLA0StartDoc*/
//----------------------------------------------------------------------------
let SysPageTask=async function(session){
	let webRpa,browser,page,entryUrl,task,guide,tools;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Init,CheckRpa,InitRpa,HasPage,HasBrowser,OpenBrowser,OpenPage,HasEntry,OpenEntry,Start,SnapPage,ReadPage,GenStep,CheckFlag,FlagNavi,FlagPickFile,OnAction,DoClick,DoInput,DoScroll,DoGoto,DoPressKey,DoDrag,DoHover,HasWait,DoPickFile,Wait,SumStep,CheckState,Finish,Failed,WrongState,WrongAction,TryStep,StepError,WaitError,UserHelp,DoAskUser,CallTool,NoRpa,TipStep,FixArgs;
	let pageUrl="";
	let pageHtml="";
	let pageImage="";
	let curStepVO=undefined;
	let curExecVO=undefined;
	let curWait=false;
	
	/*#{1ILSUCFLA0LocalVals*/
	/*}#1ILSUCFLA0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			webRpa=input.webRpa;
			browser=input.browser;
			page=input.page;
			entryUrl=input.entryUrl;
			task=input.task;
			guide=input.guide;
			tools=input.tools;
		}else{
			webRpa=undefined;
			browser=undefined;
			page=undefined;
			entryUrl=undefined;
			task=undefined;
			guide=undefined;
			tools=undefined;
		}
		/*#{1ILSUCFLA0ParseArgs*/
		/*}#1ILSUCFLA0ParseArgs*/
	}
	
	/*#{1ILSUCFLA0PreContext*/
	/*}#1ILSUCFLA0PreContext*/
	context={};
	/*#{1ILSUCFLA0PostContext*/
	/*}#1ILSUCFLA0PostContext*/
	let agent,segs={};
	segs["Init"]=Init=async function(input){//:1ILSUENVM0
		let result=input
		/*#{1ILSUENVM0Code*/
		if(tools){
			let toolsPath;
			toolsPath=tools;
			tools=new AATools(session,basePath);
			await tools.load(toolsPath);
		}
		/*}#1ILSUENVM0Code*/
		return {seg:CheckRpa,result:(result),preSeg:"1ILSUENVM0",outlet:"1ILSV1U4D0"};
	};
	Init.jaxId="1ILSUENVM0"
	Init.url="Init@"+agentURL
	
	segs["CheckRpa"]=CheckRpa=async function(input){//:1ILTCFS5E0
		let result=input;
		/*#{1ILTCFS5E0Start*/
		/*}#1ILTCFS5E0Start*/
		if(!webRpa){
			/*#{1ILTCKSHO3Codes*/
			/*}#1ILTCKSHO3Codes*/
			return {seg:InitRpa,result:(input),preSeg:"1ILTCFS5E0",outlet:"1ILTCKSHO3"};
		}
		/*#{1ILTCFS5E0Post*/
		context.webRpa=webRpa;
		/*}#1ILTCFS5E0Post*/
		return {seg:HasPage,result:(result),preSeg:"1ILTCFS5E0",outlet:"1ILTCKSHO4"};
	};
	CheckRpa.jaxId="1ILTCFS5E0"
	CheckRpa.url="CheckRpa@"+agentURL
	
	segs["InitRpa"]=InitRpa=async function(input){//:1ILTCBK3K0
		let result=true;
		let aiQuery=true;
		try{
			context.webRpa=new WebRpa(session);
			aiQuery && (await context.webRpa.setupAIQuery(session,context,basePath,"1ILTCBK3K0"));
		}catch(err){
			return {seg:NoRpa,result:(err),preSeg:"1ILTCBK3K0",outlet:"1ILTCKSHO0",catchSeg:NoRpa,catchlet:"1ILTCKSHO0"};
		}
		return {seg:OpenBrowser,result:(result),preSeg:"1ILTCBK3K0",outlet:"1ILTCKSHO1"};
	};
	InitRpa.jaxId="1ILTCBK3K0"
	InitRpa.url="InitRpa@"+agentURL
	
	segs["HasPage"]=HasPage=async function(input){//:1ILSUG4L80
		let result=input;
		/*#{1ILSUG4L80Start*/
		/*}#1ILSUG4L80Start*/
		if(!page){
			return {seg:HasBrowser,result:(input),preSeg:"1ILSUG4L80",outlet:"1ILSV1U4D1"};
		}
		/*#{1ILSUG4L80Post*/
		context.aaPage=page;
		/*}#1ILSUG4L80Post*/
		return {seg:HasEntry,result:(result),preSeg:"1ILSUG4L80",outlet:"1ILSV1U4D2"};
	};
	HasPage.jaxId="1ILSUG4L80"
	HasPage.url="HasPage@"+agentURL
	
	segs["HasBrowser"]=HasBrowser=async function(input){//:1ILT9OF6F0
		let result=input;
		/*#{1ILT9OF6F0Start*/
		/*}#1ILT9OF6F0Start*/
		if(!browser){
			return {seg:OpenBrowser,result:(input),preSeg:"1ILT9OF6F0",outlet:"1ILTAB5IH0"};
		}
		/*#{1ILT9OF6F0Post*/
		context.rpaBrowser=browser;
		/*}#1ILT9OF6F0Post*/
		return {seg:OpenPage,result:(result),preSeg:"1ILT9OF6F0",outlet:"1ILTAB5IH1"};
	};
	HasBrowser.jaxId="1ILT9OF6F0"
	HasBrowser.url="HasBrowser@"+agentURL
	
	segs["OpenBrowser"]=OpenBrowser=async function(input){//:1ILT9PNF50
		let result=true;
		let browser=null;
		let headless=false;
		let devtools=false;
		let dataDir=true;
		let alias="RPAHOME";
		context.rpaBrowser=browser=await context.webRpa.openBrowser(alias,{headless,devtools,autoDataDir:dataDir});
		context.rpaHostPage=browser.hostPage;
		return {seg:OpenPage,result:(result),preSeg:"1ILT9PNF50",outlet:"1ILTAB5IH2"};
	};
	OpenBrowser.jaxId="1ILT9PNF50"
	OpenBrowser.url="OpenBrowser@"+agentURL
	
	segs["OpenPage"]=OpenPage=async function(input){//:1ILSUI0F60
		let pageVal="aaPage";
		let $url=entryUrl;
		let $waitBefore=0;
		let $waitAfter=0;
		let $width=800;
		let $height=600;
		let $userAgent="";
		let page=null;
		$waitBefore && (await sleep($waitBefore));
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url);
		$waitAfter && (await sleep($waitAfter));
		return {seg:Start,result:(page),preSeg:"1ILSUI0F60",outlet:"1ILSV1U4D3"};
	};
	OpenPage.jaxId="1ILSUI0F60"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["HasEntry"]=HasEntry=async function(input){//:1ILSUJ5V80
		let result=input;
		if(input==="Entry"){
			return {seg:OpenEntry,result:(input),preSeg:"1ILSUJ5V80",outlet:"1ILSV1U4D4"};
		}
		return {seg:Start,result:(result),preSeg:"1ILSUJ5V80",outlet:"1ILSV1U4D5"};
	};
	HasEntry.jaxId="1ILSUJ5V80"
	HasEntry.url="HasEntry@"+agentURL
	
	segs["OpenEntry"]=OpenEntry=async function(input){//:1ILSUK12R0
		let result=true;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let url=entryUrl;
		let page=context[pageVal];
		let opts={};
		waitBefore && (await sleep(waitBefore));
		await page.goto(url,opts);
		waitAfter && (await sleep(waitAfter))
		return {seg:Start,result:(result),preSeg:"1ILSUK12R0",outlet:"1ILSV1U4E0"};
	};
	OpenEntry.jaxId="1ILSUK12R0"
	OpenEntry.url="OpenEntry@"+agentURL
	
	segs["Start"]=Start=async function(input){//:1ILTPM0KH0
		let result="开始执行任务"
		/*#{1ILTPM0KH0Code*/
		/*}#1ILTPM0KH0Code*/
		return {seg:SnapPage,result:(result),preSeg:"1ILTPM0KH0",outlet:"1ILTPN8GN0"};
	};
	Start.jaxId="1ILTPM0KH0"
	Start.url="Start@"+agentURL
	
	segs["SnapPage"]=SnapPage=async function(input){//:1ILSUR7J30
		let result=null;
		let data=null;
		let pageVal="aaPage";
		let fullPage=true;
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		/*#{1ILSUR7J30PreCodes*/
		/*}#1ILSUR7J30PreCodes*/
		result=await page.screenshot({encoding: 'base64',type:'png,fullPage:fullPage});
		result="data:image/png;base64,"+result;
		waitAfter && (await sleep(waitAfter));
		/*#{1ILSUR7J30PostCodes*/
		pageImage=result;
		/*}#1ILSUR7J30PostCodes*/
		return {seg:ReadPage,result:(result),preSeg:"1ILSUR7J30",outlet:"1ILSV1U4E3"};
	};
	SnapPage.jaxId="1ILSUR7J30"
	SnapPage.url="SnapPage@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1ILTE8QDF0
		let result=null;
		let pageVal="aaPage";
		let $node=null;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1ILTE8QDF0PreCodes*/
		pageUrl=page.url();
		/*}#1ILTE8QDF0PreCodes*/
		result=await context.webRpa.readInnerHTML(page,$node,{removeHidden:true,...$options});
		$waitAfter && (await sleep($waitAfter))
		/*#{1ILTE8QDF0PostCodes*/
		pageHtml=result;
		/*}#1ILTE8QDF0PostCodes*/
		return {seg:GenStep,result:(result),preSeg:"1ILTE8QDF0",outlet:"1ILTEA4H80"};
	};
	ReadPage.jaxId="1ILTE8QDF0"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["GenStep"]=GenStep=async function(input){//:1ILSUQ3SF0
		let prompt;
		let result=null;
		/*#{1ILSUQ3SF0Input*/
		/*}#1ILSUQ3SF0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:{
				"type":"json_schema",
				"json_schema":{
					"name":"WebStep",
					"schema":{
						"type":"object",
						"description":"",
						"properties":{
							"state":{
								"type":"string",
								"description":"当前执行任务的状态，Execute代表要执行操作网页的步骤",
								"enum":[
									"Execute","Finish","Failed","Abort"
								]
							},
							"content":{
								"type":"string",
								"description":"当前步骤的说明或者任务执行结果"
							},
							"execute":{
								"$ref":"#/$defs/WebAction"
							}
						},
						"required":[
							"state","content","execute"
						],
						"additionalProperties":false,
						"$defs":{
							"WebAction":{
								"type":"object",
								"description":"",
								"properties":{
									"action":{
										"type":"string",
										"description":"要执行的网页操作动作类型，如果不用执行操作：NA",
										"enum":[
											"Click","Input","PressKey","Goto","Hover","Back","Scroll","Tool","UserAction","Ask","NA"
										]
									},
									"queryHint":{
										"type":[
											"string","null"
										],
										"description":"用于定位要操作的目标HTML元素的描述。"
									},
									"targetAAEId":{
										"type":[
											"string","null"
										],
										"description":"要操作的目标元素的aaeid属性"
									},
									"waitEvent":{
										"type":[
											"string","null"
										],
										"description":"如果步骤会导致页面切换或者打开上传文件的对话框，相应的设定此属性",
										"enum":[
											"Navi","PickFile"
										]
									},
									"text":{
										"type":[
											"string","null"
										],
										"description":"如果action是\"input\"，要输入的文本内容。"
									},
									"key":{
										"type":[
											"string","null"
										],
										"description":"如果action是\"PressKey\"，要按的键的键码"
									},
									"url":{
										"type":[
											"string","null"
										],
										"description":"如果actoin是\"Goto\"，目标网址"
									},
									"file":{
										"type":[
											"string","null"
										],
										"description":"如果action是\"PickFIle\"，要上传的文件的地址/路径，通常是hub://开始的"
									},
									"scroll":{
										"type":[
											"integer","null"
										],
										"description":"当action为\"scroll\"时，滚动的距离，正数为向下滚动，负数为向上滚动"
									},
									"tool":{
										"type":[
											"string","null"
										],
										"description":"要调用的外部工具名称"
									},
									"toolArg":{
										"type":[
											"string","null"
										],
										"description":"调用工具/智能体的指令/参数的文本"
									}
								},
								"required":[
									"action","queryHint","targetAAEId","waitEvent","text","key","url","file","scroll","tool","toolArg"
								],
								"additionalProperties":false
							}
						}
					},
					"strict":true
				}
			}
		};
		let chatMem=GenStep.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
### 角色
你是一个强大的网页分析，动作规划智能体。
- 你根据任务描述，以及当前任务的执行状态，通过网页图像以及网页的HTML代码分析并推导为了完成任务，下一步要进行的操作。

---
### 当前要执行的任务：
${task}

${tools?`---\n### 外部工具/智能体: \n执行任务的时候可能需要调用外部的工具/AI智能体，当前可以调用的工具/AI智能体有:\n\`\`\`\n${JSON.stringify(tools.getScope(),null,"\t")}\n\`\`\`\n`:""}

---
### 对话
- 每一轮对话时，会用告诉你：当前网页的URL，当前网页的截图，当前网页的HTML代码。你根据任务目标和当前执行状态生成下一步要进行的操作。

- HTML代码说明：每个对话回合中包含的HTML代码中每个元素除了标准的HTML属性外，还包含以下几个特殊属性，用来帮助你更好的解析内容和定位元素：
    - "aaeid": 每个元素都有一个唯一的aaeid属性，用来快速定位/找到具体元素
    - "aaerect": 每个元素在页面中的位置尺寸信息

- 请用JSON格式进行回复，例如：
\`\`\`
{
	"state":"Execute",
   	"content":"Click the search button."
	"execute":{
	   	"action":"Click",
    	"queryHint":"Search button",
	    "targetAAEId":"123",
	    "waitEvent":null
    }
}
\`\`\`

---
### 回复JSON属性

- "state" {string}: 任务执行状态。
    - 如果继续执行任务: "Execute"，在属性"execute"中设定下一个步骤的具体执行内容。
    - 如果任务已完成: "Finish"，在"content"属性里总结任务结果
    - 如果任务执行失败: "Failed"，在"content"属性里说明失败原因
    - 如果任务被放弃执行: "Abort"，在"content"属性里说明放弃的原因

- "content" {string}: 当前步骤/状态/结果描述。 
    - 如果是前步骤描述或执行结果。如果是步骤描述，说明步骤的目的以及执行该步骤的做法。
    - 如果是结束/失败/放弃，请详细说明执行结果或者失败/放弃的原因。

- "execute" {object}: 如果要执行一个操作步骤，这个对象是步骤的详细内容。下面是"execute"对象属性说明：
    - "action" {string}: 步骤动作类型，可以选择的动作类型有：
        - "Click": 点击一个网页元素
        - "Hover": 把鼠标移到某个元素上面
        - "Input": 输入文本
        - "PressKey": 按键
        - "Goto": 前往一个网址
        - "Back": 回退浏览
        - "Scroll": 滚动页面
        - "Ask": 如果遇到需要用户提供额外信息或做决定的情况（例如：买不到机票时询问用户是否尝试其它日期），询问用户，询问的内容放在text属性里
        - "UserHelp": 如果你通过以上操作无法完成某个页面操作，提示用帮助你完成操作（例如：用光标在页面上绘制图形），在text属性里描述需要用户的具体操作内容
        ${tools?`- "Tool": 调用外部工具完成特定任务，调用的工具名称放在'tool'属性里， 调用的参数/描述放在'toolArg'属性里`:""}

    - "queryHint" {string}: 当要对具体某个元素操作（点击，输入等）时，对元素的说明，例如: "搜索输入框"，"注册新帐户按钮"等。
    - "targetAAEId" {string}: 当要对具体某个元素操作（点击，输入等）时，该目标元素的aaeid属性值，用来唯一确定目标元素。
    - "waitEvent" {string}: 当要执行的步骤会引起：页面切换，打开文件选择对话框等需要等待发生的事件时，该属性为要等待事件的类型，否则为null。以下是当前支持的事件类型：
        - "Navi": 当前步骤会导致一次页面切换/跳转/加载，需要等待新页面加载后再执行下一个步骤。
        - "PickFile": 当前步骤执行后，网页会弹出让用户选择上传文件的对话框，需要等待对话框弹出后再提供文件执行下一个步骤。
    - "text" {string}: 当"action"是"Input"时，这个属性是要输入的内容；当"action"为"Ask"或者"UserHelp"时，告知用户的内容；否则为null
    - "key" {string}: 当"action"是"PressKey"时，这个属性是要按的键，否则为null
    - "url" {string}: 当"action"是"Goto"时，这个属性是要前往的网址，否则为null
    - "file" {string}: 如果当前步骤会触发上传文件对话框，要上传的文件
    - "scroll" {int}: 当"action"是"Scroll"时，这个属性时滚动的距离，正值是向下滚，负值是向上滚
    ${tools?`- 属性"tool": 要调用的外部工具名称\n`:""}
    ${tools?`- 属性"toolArg": 调用的外部工具的参数/自然语言任务描述，例如："将README.md翻译为中文。\n"`:""}
`},
		];
		messages.push(...chatMem);
		/*#{1ILSUQ3SF0PrePrompt*/
		messages.push({role:"user",content:[
			{type:"text",text:`当前页面的网址为: ${pageUrl}\n\n---\n\n当前网页的HTML内容为:  \n${pageHtml}`},
			{type:"image_url","image_url":{"url":pageImage}}}
		]});
		/*}#1ILSUQ3SF0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1ILSUQ3SF0FilterMessage*/
			/*}#1ILSUQ3SF0FilterMessage*/
			messages.push(msg);
		}
		/*#{1ILSUQ3SF0PreCall*/
		/*}#1ILSUQ3SF0PreCall*/
		result=(result===null)?(await session.callSegLLM("GenStep@"+agentURL,opts,messages,true)):result;
		/*#{1ILSUQ3SF0PostLLM*/
		/*}#1ILSUQ3SF0PostLLM*/
		chatMem.push({role:"user",content:prompt});
		chatMem.push({role:"assistant",content:result});
		result=trimJSON(result);
		/*#{1ILSUQ3SF0PostCall*/
		/*}#1ILSUQ3SF0PostCall*/
		return {seg:TipStep,result:(result),preSeg:"1ILSUQ3SF0",outlet:"1ILSV1U4E2"};
	};
	GenStep.jaxId="1ILSUQ3SF0"
	GenStep.url="GenStep@"+agentURL
	GenStep.messages=[];
	
	segs["CheckFlag"]=CheckFlag=async function(input){//:1ILSUTJSD0
		let result=input;
		/*#{1ILSUTJSD0Start*/
		/*}#1ILSUTJSD0Start*/
		if(input==="Navi"){
			let output=input;
			/*#{1ILSV1U4E4Codes*/
			curWait=true;
			/*}#1ILSV1U4E4Codes*/
			return {seg:FlagNavi,result:(output),preSeg:"1ILSUTJSD0",outlet:"1ILSV1U4E4"};
		}
		if(input==="PickFile"){
			let output=input;
			/*#{1ILSUU7MQ0Codes*/
			curWait=true;
			/*}#1ILSUU7MQ0Codes*/
			return {seg:FlagPickFile,result:(output),preSeg:"1ILSUTJSD0",outlet:"1ILSUU7MQ0"};
		}
		/*#{1ILSUTJSD0Post*/
		curWait=false;
		/*}#1ILSUTJSD0Post*/
		return {seg:OnAction,result:(result),preSeg:"1ILSUTJSD0",outlet:"1ILSV1U4E5"};
	};
	CheckFlag.jaxId="1ILSUTJSD0"
	CheckFlag.url="CheckFlag@"+agentURL
	
	segs["FlagNavi"]=FlagNavi=async function(input){//:1ILSUV6QV0
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
		context[$flag]=page.waitForNavigation($options);
		$waitAfter && (await sleep($waitAfter))
		return {seg:OnAction,result:(result),preSeg:"1ILSUV6QV0",outlet:"1ILSV1U4E6"};
	};
	FlagNavi.jaxId="1ILSUV6QV0"
	FlagNavi.url="FlagNavi@"+agentURL
	
	segs["FlagPickFile"]=FlagPickFile=async function(input){//:1ILSUVPAI0
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
		context[$flag]=page.waitForFileChooser($options);
		$waitAfter && (await sleep($waitAfter))
		return {seg:OnAction,result:(result),preSeg:"1ILSUVPAI0",outlet:"1ILSV1U4E7"};
	};
	FlagPickFile.jaxId="1ILSUVPAI0"
	FlagPickFile.url="FlagPickFile@"+agentURL
	
	segs["OnAction"]=OnAction=async function(input){//:1ILSV0HOH0
		let result=input;
		/*#{1ILSV0HOH0Start*/
		input=curExecVO;
		/*}#1ILSV0HOH0Start*/
		if(curExecVO.action==="Click"){
			let output=input;
			return {seg:DoClick,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILSVPE1R0"};
		}
		if(curExecVO.action==="Hover"){
			let output=input;
			return {seg:DoHover,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILSV438N0"};
		}
		if(curExecVO.action==="Input"){
			let output=input;
			return {seg:DoInput,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILSV290J0"};
		}
		if(curExecVO.action==="PressKey"){
			let output=input;
			return {seg:DoPressKey,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILSV2TE70"};
		}
		if(curExecVO.action==="Goto"){
			let output=input;
			return {seg:DoGoto,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILSV2NNE0"};
		}
		if(curExecVO.action==="Scroll"){
			let output=input;
			return {seg:DoScroll,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILSV2FIQ0"};
		}
		if(curExecVO.action==="Drag"){
			let output=input;
			return {seg:DoDrag,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILSV3LH80"};
		}
		if(curExecVO.action==="PickFile"){
			let output=input;
			return {seg:DoPickFile,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILSVFB7J0"};
		}
		if(curExecVO.action==="Tool"){
			let output=input;
			return {seg:CallTool,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILT9L9270"};
		}
		if(curExecVO.action==="Ask"){
			let output=input;
			return {seg:DoAskUser,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILT8MUHA0"};
		}
		if(curExecVO.action==="UserHelp"){
			let output=input;
			return {seg:UserHelp,result:(output),preSeg:"1ILSV0HOH0",outlet:"1ILT8M04R0"};
		}
		/*#{1ILSV0HOH0Post*/
		/*}#1ILSV0HOH0Post*/
		return {seg:WrongAction,result:(result),preSeg:"1ILSV0HOH0",outlet:"1ILSV1U4E8"};
	};
	OnAction.jaxId="1ILSV0HOH0"
	OnAction.url="OnAction@"+agentURL
	
	segs["DoClick"]=DoClick=async function(input){//:1ILSV80GQ0
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint="";
		let $x=0;
		let $y=0;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1ILSV80GQ0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			await page.click("::-p-xpath"+$query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
		}else{
			await page.mouse.click($x,$y,$options||{});
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:HasWait,result:(result),preSeg:"1ILSV80GQ0",outlet:"1ILSVPE1S0"};
	};
	DoClick.jaxId="1ILSV80GQ0"
	DoClick.url="DoClick@"+agentURL
	
	segs["DoInput"]=DoInput=async function(input){//:1ILSV8K710
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="";
		let $queryHint="";
		let $key="Enter";
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1ILSV8K710")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			await page.type("::-p-xpath"+$query,$key,$options||{});
		}else{
			await page.keyboard.type($key,$options||{});
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:HasWait,result:(result),preSeg:"1ILSV8K710",outlet:"1ILSVPE1S1"};
	};
	DoInput.jaxId="1ILSV8K710"
	DoInput.url="DoInput@"+agentURL
	
	segs["DoScroll"]=DoScroll=async function(input){//:1ILSV92DC0
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint="";
		let $x=0;
		let $y=0;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1ILSV92DC0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			await page.click("::-p-xpath"+$query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
		}else{
			await page.mouse.click($x,$y,$options||{});
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:HasWait,result:(result),preSeg:"1ILSV92DC0",outlet:"1ILSVPE1S2"};
	};
	DoScroll.jaxId="1ILSV92DC0"
	DoScroll.url="DoScroll@"+agentURL
	
	segs["DoGoto"]=DoGoto=async function(input){//:1ILSV9GQG0
		let result=true;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let url="https://www.google.com";
		let page=context[pageVal];
		let opts={};
		waitBefore && (await sleep(waitBefore));
		await page.goto(url,opts);
		waitAfter && (await sleep(waitAfter))
		return {seg:HasWait,result:(result),preSeg:"1ILSV9GQG0",outlet:"1ILSVPE1S3"};
	};
	DoGoto.jaxId="1ILSV9GQG0"
	DoGoto.url="DoGoto@"+agentURL
	
	segs["DoPressKey"]=DoPressKey=async function(input){//:1ILSVAQCQ0
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="";
		let $queryHint="";
		let $key="Enter";
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1ILSVAQCQ0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			await page.type("::-p-xpath"+$query,$key,$options||{});
		}else{
			await page.keyboard.type($key,$options||{});
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:HasWait,result:(result),preSeg:"1ILSVAQCQ0",outlet:"1ILSVPE1S4"};
	};
	DoPressKey.jaxId="1ILSVAQCQ0"
	DoPressKey.url="DoPressKey@"+agentURL
	
	segs["DoDrag"]=DoDrag=async function(input){//:1ILSVBBU70
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint="";
		let $x=0;
		let $y=0;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1ILSVBBU70")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			await page.click("::-p-xpath"+$query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
		}else{
			await page.mouse.click($x,$y,$options||{});
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:HasWait,result:(result),preSeg:"1ILSVBBU70",outlet:"1ILSVPE1S5"};
	};
	DoDrag.jaxId="1ILSVBBU70"
	DoDrag.url="DoDrag@"+agentURL
	
	segs["DoHover"]=DoHover=async function(input){//:1ILSVC11H0
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint="";
		let $x=0;
		let $y=0;
		let $options=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1ILSVC11H0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			await page.click("::-p-xpath"+$query,{...$options,offset:((!!$x) || (!!$y))?{x:$x||0,y:$y||0}:undefined});
		}else{
			await page.mouse.click($x,$y,$options||{});
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:HasWait,result:(result),preSeg:"1ILSVC11H0",outlet:"1ILSVPE1S6"};
	};
	DoHover.jaxId="1ILSVC11H0"
	DoHover.url="DoHover@"+agentURL
	
	segs["HasWait"]=HasWait=async function(input){//:1ILSVDM1F0
		let result=input;
		if(!curWait){
			let output=input;
			return {seg:SumStep,result:(output),preSeg:"1ILSVDM1F0",outlet:"1ILSVPE1S7"};
		}
		result=input;
		return {seg:Wait,result:(result),preSeg:"1ILSVDM1F0",outlet:"1ILSVPE1T0"};
	};
	HasWait.jaxId="1ILSVDM1F0"
	HasWait.url="HasWait@"+agentURL
	
	segs["DoPickFile"]=DoPickFile=async function(input){//:1ILSVIDC60
		let result=true;
		let $fileName="";
		let $fileData=undefined;
		let $waitBefore=0;
		let $waitAfter=0;
		$waitBefore && (await sleep($waitBefore));
		await context.webRpa.saveFile(aaBrowser,$fileName,$fileData);
		$waitAfter && (await sleep($waitAfter))
		return {seg:HasWait,result:(result),preSeg:"1ILSVIDC60",outlet:"1ILSVPE1T1"};
	};
	DoPickFile.jaxId="1ILSVIDC60"
	DoPickFile.url="DoPickFile@"+agentURL
	
	segs["Wait"]=Wait=async function(input){//:1ILSVK78S0
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		try{
			await context[$flag];
		}catch(error){
			return {seg:WaitError,result:(error),preSeg:"1ILSVK78S0",outlet:"1ILSVPE1T2"};
		}
		$waitAfter && (await sleep($waitAfter))
		return {seg:SumStep,result:(result),preSeg:"1ILSVK78S0",outlet:"1ILSVPE1T3"};
	};
	Wait.jaxId="1ILSVK78S0"
	Wait.url="Wait@"+agentURL
	
	segs["SumStep"]=SumStep=async function(input){//:1ILSVNKE10
		let result=input
		/*#{1ILSVNKE10Code*/
		result="步骤/操作执行完毕，请继续完成任务。";
		/*}#1ILSVNKE10Code*/
		return {seg:SnapPage,result:(result),preSeg:"1ILSVNKE10",outlet:"1ILSVPE1T4"};
	};
	SumStep.jaxId="1ILSVNKE10"
	SumStep.url="SumStep@"+agentURL
	
	segs["CheckState"]=CheckState=async function(input){//:1ILSVQUN80
		let result=input;
		/*#{1ILSVQUN80Start*/
		curStepVO=input;
		curExecVO=input.execute;
		/*}#1ILSVQUN80Start*/
		if(input.state==="Execute"){
			let output=input;
			return {seg:CheckFlag,result:(output),preSeg:"1ILSVQUN80",outlet:"1ILSVR5HA0"};
		}
		if(input.state==="Finish"){
			let output=input;
			return {seg:Finish,result:(output),preSeg:"1ILSVQUN80",outlet:"1ILT06JN00"};
		}
		if(input.state==="Failed"||input.state==="Abort"){
			let output=input;
			return {seg:Failed,result:(output),preSeg:"1ILSVQUN80",outlet:"1ILSVRHOU0"};
		}
		result=input;
		/*#{1ILSVQUN80Post*/
		/*}#1ILSVQUN80Post*/
		return {seg:WrongState,result:(result),preSeg:"1ILSVQUN80",outlet:"1ILT06JN01"};
	};
	CheckState.jaxId="1ILSVQUN80"
	CheckState.url="CheckState@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1ILT0264T0
		let result=input
		/*#{1ILT0264T0Code*/
		/*}#1ILT0264T0Code*/
		return {result:result};
	};
	Finish.jaxId="1ILT0264T0"
	Finish.url="Finish@"+agentURL
	
	segs["Failed"]=Failed=async function(input){//:1ILT02H7P0
		let result=input
		/*#{1ILT02H7P0Code*/
		/*}#1ILT02H7P0Code*/
		return {result:result};
	};
	Failed.jaxId="1ILT02H7P0"
	Failed.url="Failed@"+agentURL
	
	segs["WrongState"]=WrongState=async function(input){//:1ILT03OC90
		let result=input
		/*#{1ILT03OC90Code*/
		result=`错误的state属性：${input.state}。重新生成步骤内容。`;
		/*}#1ILT03OC90Code*/
		return {seg:SnapPage,result:(result),preSeg:"1ILT03OC90",outlet:"1ILT06JN04"};
	};
	WrongState.jaxId="1ILT03OC90"
	WrongState.url="WrongState@"+agentURL
	
	segs["WrongAction"]=WrongAction=async function(input){//:1ILT07R4B0
		let result=input
		/*#{1ILT07R4B0Code*/
		result=`错误的action属性：${input.execute.action}。重新生成步骤内容。`;
		/*}#1ILT07R4B0Code*/
		return {seg:SnapPage,result:(result),preSeg:"1ILT07R4B0",outlet:"1ILT08VB10"};
	};
	WrongAction.jaxId="1ILT07R4B0"
	WrongAction.url="WrongAction@"+agentURL
	
	segs["TryStep"]=TryStep=async function(input){//:1ILT0BHKD0
		let result=input;
		/*#{1ILT0BHKD0Code*/
		false
		/*}#1ILT0BHKD0Code*/
		return {seg:CheckState,result:(result),preSeg:"1ILT0BHKD0",outlet:"1ILT0CR6N0",catchSeg:StepError,catchlet:"1ILT0CR6O0"};
	};
	TryStep.jaxId="1ILT0BHKD0"
	TryStep.url="TryStep@"+agentURL
	
	segs["StepError"]=StepError=async function(input){//:1ILT0D8NK0
		let result=input
		/*#{1ILT0D8NK0Code*/
		result=`执行步骤出错：${input}`;
		/*}#1ILT0D8NK0Code*/
		return {seg:SnapPage,result:(result),preSeg:"1ILT0D8NK0",outlet:"1ILT0EQL80"};
	};
	StepError.jaxId="1ILT0D8NK0"
	StepError.url="StepError@"+agentURL
	
	segs["WaitError"]=WaitError=async function(input){//:1ILT0LRHB0
		let result=input
		/*#{1ILT0LRHB0Code*/
		result=`等待步骤执行出错：${input}，请分析原因继续完成任务。`;
		/*}#1ILT0LRHB0Code*/
		return {seg:SnapPage,result:(result),preSeg:"1ILT0LRHB0",outlet:"1ILT0MD8U0"};
	};
	WaitError.jaxId="1ILT0LRHB0"
	WaitError.url="WaitError@"+agentURL
	
	segs["UserHelp"]=UserHelp=async function(input){//:1ILT8S7BH0
		let prompt=(input.text)||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=true;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("操作完成，继续执行"):("Operation completed, continue")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("无法完成操作，放弃执行"):("Operation cannot be completed, aborting")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			/*#{1ILT8S7AS0Silent*/
			/*}#1ILT8S7AS0Silent*/
			return {seg:SnapPage,result:(result),preSeg:"1ILT8S7BH0",outlet:"1ILT8S7AS0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {seg:SnapPage,result:(result),preSeg:"1ILT8S7BH0",outlet:"1ILT97VVC0"};
		}else if(item.code===0){
			/*#{1ILT8S7AS0*/
			/*}#1ILT8S7AS0*/
			return {seg:SnapPage,result:(result),preSeg:"1ILT8S7BH0",outlet:"1ILT8S7AS0"};
		}else if(item.code===1){
			/*#{1ILT8S7AS1*/
			/*}#1ILT8S7AS1*/
			return {seg:SnapPage,result:(result),preSeg:"1ILT8S7BH0",outlet:"1ILT8S7AS1"};
		}
		return {seg:SnapPage,result:(result),preSeg:"1ILT8S7BH0",outlet:"1ILT97VVC0"};
	};
	UserHelp.jaxId="1ILT8S7BH0"
	UserHelp.url="UserHelp@"+agentURL
	
	segs["DoAskUser"]=DoAskUser=async function(input){//:1ILT8UD980
		let result;
		let sourcePath=pathLib.join(basePath,"./SysAskUser.js");
		let arg=input.content;
		/*#{1ILT8UD980Input*/
		/*}#1ILT8UD980Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1ILT8UD980Output*/
		/*}#1ILT8UD980Output*/
		return {seg:SnapPage,result:(result),preSeg:"1ILT8UD980",outlet:"1ILT97VVC1"};
	};
	DoAskUser.jaxId="1ILT8UD980"
	DoAskUser.url="DoAskUser@"+agentURL
	
	segs["CallTool"]=CallTool=async function(input){//:1ILT9DK710
		let result=input
		/*#{1ILT9DK710Code*/
		result=await tools.runTool(input.tool,input.toolArg);
		/*}#1ILT9DK710Code*/
		return {seg:SnapPage,result:(result),preSeg:"1ILT9DK710",outlet:"1ILT9L9290"};
	};
	CallTool.jaxId="1ILT9DK710"
	CallTool.url="CallTool@"+agentURL
	
	segs["NoRpa"]=NoRpa=async function(input){//:1ILTCD3PV0
		let result=input
		/*#{1ILTCD3PV0Code*/
		/*}#1ILTCD3PV0Code*/
		return {result:result};
	};
	NoRpa.jaxId="1ILTCD3PV0"
	NoRpa.url="NoRpa@"+agentURL
	
	segs["TipStep"]=TipStep=async function(input){//:1ILTTFKLB0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input.content;
		session.addChatText(role,content,opts);
		return {seg:TryStep,result:(result),preSeg:"1ILTTFKLB0",outlet:"1ILTTGDMS0"};
	};
	TipStep.jaxId="1ILTTFKLB0"
	TipStep.url="TipStep@"+agentURL
	
	segs["FixArgs"]=FixArgs=async function(input){//:1ILUQMHJU0
		let result=input;
		let missing=false;
		if(task===undefined || task==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:Init,result:(result),preSeg:"1ILUQMHJU0",outlet:"1ILUQN5P70"};
	};
	FixArgs.jaxId="1ILUQMHJU0"
	FixArgs.url="FixArgs@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"SysPageTask",
		url:agentURL,
		autoStart:true,
		jaxId:"1ILSUCFLA0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{webRpa,browser,page,entryUrl,task,guide,tools}*/){
			let result;
			parseAgentArgs(input);
			/*#{1ILSUCFLA0PreEntry*/
			/*}#1ILSUCFLA0PreEntry*/
			result={seg:Init,"input":input};
			/*#{1ILSUCFLA0PostEntry*/
			/*}#1ILSUCFLA0PostEntry*/
			return result;
		},
		/*#{1ILSUCFLA0MoreAgentAttrs*/
		/*}#1ILSUCFLA0MoreAgentAttrs*/
	};
	/*#{1ILSUCFLA0PostAgent*/
	/*}#1ILSUCFLA0PostAgent*/
	return agent;
};
/*#{1ILSUCFLA0ExCodes*/
/*}#1ILSUCFLA0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "SysPageTask",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				webRpa:{type:"auto",description:""},
				browser:{type:"auto",description:""},
				page:{type:"auto",description:""},
				entryUrl:{type:"auto",description:""},
				task:{type:"auto",description:""},
				guide:{type:"auto",description:""},
				tools:{type:"auto",description:""}
			}
		}
	}
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
		name:"SysPageTask",showName:"SysPageTask",icon:"agent.svg",catalog:["WebRPA"],
		attrs:{
			...SegObjShellAttr,
			"webRpa":{name:"webRpa",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"browser":{name:"browser",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"page":{name:"page",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"entryUrl":{name:"entryUrl",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"task":{name:"task",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"guide":{name:"guide",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"tools":{name:"tools",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","webRpa","browser","page","entryUrl","task","guide","tools","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["SysPageTask"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['webRpa']=");this.genAttrStatement(seg.getAttr("webRpa"));coder.packText(";");coder.newLine();
			coder.packText("args['browser']=");this.genAttrStatement(seg.getAttr("browser"));coder.packText(";");coder.newLine();
			coder.packText("args['page']=");this.genAttrStatement(seg.getAttr("page"));coder.packText(";");coder.newLine();
			coder.packText("args['entryUrl']=");this.genAttrStatement(seg.getAttr("entryUrl"));coder.packText(";");coder.newLine();
			coder.packText("args['task']=");this.genAttrStatement(seg.getAttr("task"));coder.packText(";");coder.newLine();
			coder.packText("args['guide']=");this.genAttrStatement(seg.getAttr("guide"));coder.packText(";");coder.newLine();
			coder.packText("args['tools']=");this.genAttrStatement(seg.getAttr("tools"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/SysPageTask.js",args,false);`);coder.newLine();
			this.packExtraCodes(coder,seg,"PostCodes");
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
/*#{1ILSUCFLA0PostDoc*/
/*}#1ILSUCFLA0PostDoc*/


export default SysPageTask;
export{SysPageTask,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1ILSUCFLA0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1ILSUCFLA1",
//			"attrs": {
//				"SysPageTask": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1ILSUCFLA7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1ILSUCFLA8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1ILSUCFLA9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1ILSUCFLA10",
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
//			"jaxId": "1ILSUCFLA2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1ILSUCFLA3",
//			"attrs": {
//				"webRpa": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILTCKSI20",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				},
//				"browser": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILSUEI170",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				},
//				"page": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILSUEI171",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				},
//				"entryUrl": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILSUEI172",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				},
//				"task": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILSUEI173",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "true"
//					}
//				},
//				"guide": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILSUEI174",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				},
//				"tools": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1ILT9L92L0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1ILSUCFLA4",
//			"attrs": {
//				"pageUrl": {
//					"type": "string",
//					"valText": ""
//				},
//				"pageHtml": {
//					"type": "string",
//					"valText": ""
//				},
//				"pageImage": {
//					"type": "string",
//					"valText": ""
//				},
//				"curStepVO": {
//					"type": "auto",
//					"valText": ""
//				},
//				"curExecVO": {
//					"type": "auto",
//					"valText": ""
//				},
//				"curWait": {
//					"type": "bool",
//					"valText": "false"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1ILSUCFLA5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1ILSUCFLA6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILSUENVM0",
//					"attrs": {
//						"id": "Init",
//						"viewName": "",
//						"label": "",
//						"x": "280",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSV1U4D0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILTCFS5E0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILTCFS5E0",
//					"attrs": {
//						"id": "CheckRpa",
//						"viewName": "",
//						"label": "",
//						"x": "500",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILTCKSI32",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILTCKSI33",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILTCKSHO4",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILTCI6FB0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILTCKSHO3",
//									"attrs": {
//										"id": "NoRpa",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1ILTCKSI34",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILTCKSI35",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!webRpa"
//									},
//									"linkedSeg": "1ILTCBK3K0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaStart",
//					"jaxId": "1ILTCBK3K0",
//					"attrs": {
//						"id": "InitRpa",
//						"viewName": "",
//						"label": "",
//						"x": "745",
//						"y": "165",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILTCKSI21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILTCKSI22",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILTCKSHO1",
//							"attrs": {
//								"id": "Done",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILTCIOJG0"
//						},
//						"catchlet": {
//							"jaxId": "1ILTCKSHO0",
//							"attrs": {
//								"id": "NoRpa",
//								"desc": "输出节点。",
//								"output": "",
//								"codes": "false",
//								"context": {
//									"jaxId": "1ILTCKSI23",
//									"attrs": {
//										"cast": ""
//									}
//								},
//								"global": {
//									"jaxId": "1ILTCKSI24",
//									"attrs": {
//										"cast": ""
//									}
//								}
//							},
//							"linkedSeg": "1ILTCD3PV0"
//						},
//						"aiQuery": "true"
//					},
//					"icon": "start.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILSUG4L80",
//					"attrs": {
//						"id": "HasPage",
//						"viewName": "",
//						"label": "",
//						"x": "945",
//						"y": "395",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSV1U4D2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILSUJ5V80"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSV1U4D1",
//									"attrs": {
//										"id": "NoPage",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSV1U4G4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSV1U4G5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!page"
//									},
//									"linkedSeg": "1ILT9OF6F0"
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
//					"jaxId": "1ILT9OF6F0",
//					"attrs": {
//						"id": "HasBrowser",
//						"viewName": "",
//						"label": "",
//						"x": "1170",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILTAFHO80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILTAFHO81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILTAB5IH1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILSUI0F60"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILTAB5IH0",
//									"attrs": {
//										"id": "NoBrowser",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILTAFHO82",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILTAFHO83",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!browser"
//									},
//									"linkedSeg": "1ILT9PNF50"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenBrowser",
//					"jaxId": "1ILT9PNF50",
//					"attrs": {
//						"id": "OpenBrowser",
//						"viewName": "",
//						"label": "",
//						"x": "1415",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILTAFHO84",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILTAFHO85",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"alias": "RPAHOME",
//						"headless": "false",
//						"devtools": "false",
//						"dataDir": "true",
//						"outlet": {
//							"jaxId": "1ILTAB5IH2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSUI0F60"
//						},
//						"run": ""
//					},
//					"icon": "web.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1ILSUI0F60",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "1675",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "#entryUrl",
//						"vpWidth": "800",
//						"vpHeight": "600",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSV1U4D3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILTBGCNA0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILSUJ5V80",
//					"attrs": {
//						"id": "HasEntry",
//						"viewName": "",
//						"label": "",
//						"x": "1890",
//						"y": "410",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSV1U4D5",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILTPM0KH0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSV1U4D4",
//									"attrs": {
//										"id": "Entry",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSV1U4G10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSV1U4G11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1ILSUK12R0"
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
//					"jaxId": "1ILSUK12R0",
//					"attrs": {
//						"id": "OpenEntry",
//						"viewName": "",
//						"label": "",
//						"x": "2095",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"url": "#entryUrl",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSV1U4E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILTPM0KH0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/wait_goto.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILTPM0KH0",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "2340",
//						"y": "425",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILTPNOAD0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILTPNOAD1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILTPN8GN0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSUR7J30"
//						},
//						"result": "开始执行任务"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaCapturePage",
//					"jaxId": "1ILSUR7J30",
//					"attrs": {
//						"id": "SnapPage",
//						"viewName": "",
//						"label": "",
//						"x": "2545",
//						"y": "425",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G18",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G19",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"fullPage": "true",
//						"dataURL": "true",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSV1U4E3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILTE8QDF0"
//						}
//					},
//					"icon": "/@aae/assets/tab_cam.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaReadPage",
//					"jaxId": "1ILTE8QDF0",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "2780",
//						"y": "425",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILTEA4HC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILTEA4HC1",
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
//							"jaxId": "1ILTEA4H80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSUQ3SF0"
//						},
//						"run": ""
//					},
//					"icon": "read.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1ILSUQ3SF0",
//					"attrs": {
//						"id": "GenStep",
//						"viewName": "",
//						"label": "",
//						"x": "3015",
//						"y": "425",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G16",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G17",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`\n### 角色\n你是一个强大的网页分析，动作规划智能体。\n- 你根据任务描述，以及当前任务的执行状态，通过网页图像以及网页的HTML代码分析并推导为了完成任务，下一步要进行的操作。\n\n---\n### 当前要执行的任务：\n${task}\n\n${tools?`---\\n### 外部工具/智能体: \\n执行任务的时候可能需要调用外部的工具/AI智能体，当前可以调用的工具/AI智能体有:\\n\\`\\`\\`\\n${JSON.stringify(tools.getScope(),null,\"\\t\")}\\n\\`\\`\\`\\n`:\"\"}\n\n---\n### 对话\n- 每一轮对话时，会用告诉你：当前网页的URL，当前网页的截图，当前网页的HTML代码。你根据任务目标和当前执行状态生成下一步要进行的操作。\n\n- HTML代码说明：每个对话回合中包含的HTML代码中每个元素除了标准的HTML属性外，还包含以下几个特殊属性，用来帮助你更好的解析内容和定位元素：\n    - \"aaeid\": 每个元素都有一个唯一的aaeid属性，用来快速定位/找到具体元素\n    - \"aaerect\": 每个元素在页面中的位置尺寸信息\n\n- 请用JSON格式进行回复，例如：\n\\`\\`\\`\n{\n\t\"state\":\"Execute\",\n   \t\"content\":\"Click the search button.\"\n\t\"execute\":{\n\t   \t\"action\":\"Click\",\n    \t\"queryHint\":\"Search button\",\n\t    \"targetAAEId\":\"123\",\n\t    \"waitEvent\":null\n    }\n}\n\\`\\`\\`\n\n---\n### 回复JSON属性\n\n- \"state\" {string}: 任务执行状态。\n    - 如果继续执行任务: \"Execute\"，在属性\"execute\"中设定下一个步骤的具体执行内容。\n    - 如果任务已完成: \"Finish\"，在\"content\"属性里总结任务结果\n    - 如果任务执行失败: \"Failed\"，在\"content\"属性里说明失败原因\n    - 如果任务被放弃执行: \"Abort\"，在\"content\"属性里说明放弃的原因\n\n- \"content\" {string}: 当前步骤/状态/结果描述。 \n    - 如果是前步骤描述或执行结果。如果是步骤描述，说明步骤的目的以及执行该步骤的做法。\n    - 如果是结束/失败/放弃，请详细说明执行结果或者失败/放弃的原因。\n\n- \"execute\" {object}: 如果要执行一个操作步骤，这个对象是步骤的详细内容。下面是\"execute\"对象属性说明：\n    - \"action\" {string}: 步骤动作类型，可以选择的动作类型有：\n        - \"Click\": 点击一个网页元素\n        - \"Hover\": 把鼠标移到某个元素上面\n        - \"Input\": 输入文本\n        - \"PressKey\": 按键\n        - \"Goto\": 前往一个网址\n        - \"Back\": 回退浏览\n        - \"Scroll\": 滚动页面\n        - \"Ask\": 如果遇到需要用户提供额外信息或做决定的情况（例如：买不到机票时询问用户是否尝试其它日期），询问用户，询问的内容放在text属性里\n        - \"UserHelp\": 如果你通过以上操作无法完成某个页面操作，提示用帮助你完成操作（例如：用光标在页面上绘制图形），在text属性里描述需要用户的具体操作内容\n        ${tools?`- \"Tool\": 调用外部工具完成特定任务，调用的工具名称放在'tool'属性里， 调用的参数/描述放在'toolArg'属性里`:\"\"}\n\n    - \"queryHint\" {string}: 当要对具体某个元素操作（点击，输入等）时，对元素的说明，例如: \"搜索输入框\"，\"注册新帐户按钮\"等。\n    - \"targetAAEId\" {string}: 当要对具体某个元素操作（点击，输入等）时，该目标元素的aaeid属性值，用来唯一确定目标元素。\n    - \"waitEvent\" {string}: 当要执行的步骤会引起：页面切换，打开文件选择对话框等需要等待发生的事件时，该属性为要等待事件的类型，否则为null。以下是当前支持的事件类型：\n        - \"Navi\": 当前步骤会导致一次页面切换/跳转/加载，需要等待新页面加载后再执行下一个步骤。\n        - \"PickFile\": 当前步骤执行后，网页会弹出让用户选择上传文件的对话框，需要等待对话框弹出后再提供文件执行下一个步骤。\n    - \"text\" {string}: 当\"action\"是\"Input\"时，这个属性是要输入的内容；当\"action\"为\"Ask\"或者\"UserHelp\"时，告知用户的内容；否则为null\n    - \"key\" {string}: 当\"action\"是\"PressKey\"时，这个属性是要按的键，否则为null\n    - \"url\" {string}: 当\"action\"是\"Goto\"时，这个属性是要前往的网址，否则为null\n    - \"file\" {string}: 如果当前步骤会触发上传文件对话框，要上传的文件\n    - \"scroll\" {int}: 当\"action\"是\"Scroll\"时，这个属性时滚动的距离，正值是向下滚，负值是向上滚\n    ${tools?`- 属性\"tool\": 要调用的外部工具名称\\n`:\"\"}\n    ${tools?`- 属性\"toolArg\": 调用的外部工具的参数/自然语言任务描述，例如：\"将README.md翻译为中文。\\n\"`:\"\"}\n`",
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
//							"jaxId": "1ILSV1U4E2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILTTFKLB0"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": []
//						},
//						"shareChatName": "",
//						"keepChat": "All messages",
//						"clearChat": "2",
//						"apiFiles": {
//							"attrs": []
//						},
//						"parallelFunction": "false",
//						"responseFormat": "json_object",
//						"formatDef": "\"1ILTMHV9J2\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILSUTJSD0",
//					"attrs": {
//						"id": "CheckFlag",
//						"viewName": "",
//						"label": "",
//						"x": "3910",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSV1U4E5",
//							"attrs": {
//								"id": "NoWait",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILSV18OR0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSV1U4E4",
//									"attrs": {
//										"id": "Navi",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "true",
//										"context": {
//											"jaxId": "1ILSV1U4G22",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSV1U4G23",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1ILSUV6QV0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSUU7MQ0",
//									"attrs": {
//										"id": "PickFile",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "true",
//										"context": {
//											"jaxId": "1ILSV1U4G24",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSV1U4G25",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": ""
//									},
//									"linkedSeg": "1ILSUVPAI0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1ILSUV6QV0",
//					"attrs": {
//						"id": "FlagNavi",
//						"viewName": "",
//						"label": "",
//						"x": "4130",
//						"y": "295",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G26",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G27",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Navigate",
//						"flag": "$WaitFlag",
//						"query": "",
//						"queryHint": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSV1U4E6",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSV0HOH0"
//						}
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaFlagWait",
//					"jaxId": "1ILSUVPAI0",
//					"attrs": {
//						"id": "FlagPickFile",
//						"viewName": "",
//						"label": "",
//						"x": "4130",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G28",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G29",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "FileChooser",
//						"flag": "$WaitFlag",
//						"query": "",
//						"queryHint": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSV1U4E7",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSV0HOH0"
//						}
//					},
//					"icon": "/@aae/assets/wait_flag.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILSV0HOH0",
//					"attrs": {
//						"id": "OnAction",
//						"viewName": "",
//						"label": "",
//						"x": "4360",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSV1U4G30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSV1U4G31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSV1U4E8",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1ILT07R4B0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSVPE1R0",
//									"attrs": {
//										"id": "Click",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSVPE1U0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSVPE1U1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"Click\""
//									},
//									"linkedSeg": "1ILSV80GQ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSV438N0",
//									"attrs": {
//										"id": "Hover",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSVPE1U2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSVPE1U3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"Hover\""
//									},
//									"linkedSeg": "1ILSVC11H0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSV290J0",
//									"attrs": {
//										"id": "Input",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSVPE1U4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSVPE1U5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"Input\""
//									},
//									"linkedSeg": "1ILSV8K710"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSV2TE70",
//									"attrs": {
//										"id": "PressKey",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSVPE1U6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSVPE1U7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"PressKey\""
//									},
//									"linkedSeg": "1ILSVAQCQ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSV2NNE0",
//									"attrs": {
//										"id": "Goto",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSVPE1U8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSVPE1U9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"Goto\""
//									},
//									"linkedSeg": "1ILSV9GQG0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSV2FIQ0",
//									"attrs": {
//										"id": "Scroll",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSVPE1U10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSVPE1U11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"Scroll\""
//									},
//									"linkedSeg": "1ILSV92DC0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSV3LH80",
//									"attrs": {
//										"id": "Drag",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSVPE1U12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSVPE1U13",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"Drag\""
//									},
//									"linkedSeg": "1ILSVBBU70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSVFB7J0",
//									"attrs": {
//										"id": "PickFile",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSVPE1U14",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSVPE1U15",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"PickFile\""
//									},
//									"linkedSeg": "1ILSVIDC60"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILT9L9270",
//									"attrs": {
//										"id": "Tool",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILT9L92L1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILT9L92L2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"Tool\""
//									},
//									"linkedSeg": "1ILT9DK710"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILT8MUHA0",
//									"attrs": {
//										"id": "Ask",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILT97VVF0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILT97VVF1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"Ask\""
//									},
//									"linkedSeg": "1ILT8UD980"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILT8M04R0",
//									"attrs": {
//										"id": "UserHelp",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILT97VVF2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILT97VVF3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#curExecVO.action===\"UserHelp\""
//									},
//									"linkedSeg": "1ILT8S7BH0"
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
//					"jaxId": "1ILSV18OR0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "4130",
//						"y": "440",
//						"outlet": {
//							"jaxId": "1ILSV1U4G32",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSV1GF40"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1ILSV1GF40",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "4235",
//						"y": "440",
//						"outlet": {
//							"jaxId": "1ILSV1U4G33",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSV0HOH0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1ILSV80GQ0",
//					"attrs": {
//						"id": "DoClick",
//						"viewName": "",
//						"label": "",
//						"x": "4645",
//						"y": "5",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1U16",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1U17",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSVPE1S0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVDM1F0"
//						},
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1ILSV8K710",
//					"attrs": {
//						"id": "DoInput",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1U18",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1U19",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Type",
//						"query": "",
//						"queryHint": "",
//						"key": "Enter",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSVPE1S1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVDM1F0"
//						},
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1ILSV92DC0",
//					"attrs": {
//						"id": "DoScroll",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "330",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1U20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1U21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSVPE1S2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVDM1F0"
//						},
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaPageGoto",
//					"jaxId": "1ILSV9GQG0",
//					"attrs": {
//						"id": "DoGoto",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1U22",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1U23",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"url": "https://www.google.com",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSVPE1S3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVDM1F0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/wait_goto.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1ILSVAQCQ0",
//					"attrs": {
//						"id": "DoPressKey",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1U24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1U25",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Type",
//						"query": "",
//						"queryHint": "",
//						"key": "Enter",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSVPE1S4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVDM1F0"
//						},
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1ILSVBBU70",
//					"attrs": {
//						"id": "DoDrag",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "395",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1U26",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1U27",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSVPE1S5",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVDM1F0"
//						},
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1ILSVC11H0",
//					"attrs": {
//						"id": "DoHover",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "70",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1U28",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1U29",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Click",
//						"query": "",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"options": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSVPE1S6",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVDM1F0"
//						},
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILSVDM1F0",
//					"attrs": {
//						"id": "HasWait",
//						"viewName": "",
//						"label": "",
//						"x": "4915",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1U30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1U31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSVPE1T0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": "#input"
//							},
//							"linkedSeg": "1ILSVK78S0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSVPE1S7",
//									"attrs": {
//										"id": "NoWait",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILSVPE1U32",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILSVPE1U33",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!curWait"
//									},
//									"linkedSeg": "1ILSVNKE10"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaUploadFile",
//					"jaxId": "1ILSVIDC60",
//					"attrs": {
//						"id": "DoPickFile",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "460",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1U34",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1U35",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"fileName": "",
//						"fileData": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSVPE1T1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVDM1F0"
//						}
//					},
//					"icon": "/@aae/assets/wait_upload.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1ILSVK78S0",
//					"attrs": {
//						"id": "Wait",
//						"viewName": "",
//						"label": "",
//						"x": "5120",
//						"y": "410",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1V0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1V1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1ILSVPE1T3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVNKE10"
//						},
//						"catchlet": {
//							"jaxId": "1ILSVPE1T2",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT0LRHB0"
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILSVNKE10",
//					"attrs": {
//						"id": "SumStep",
//						"viewName": "",
//						"label": "",
//						"x": "5325",
//						"y": "350",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILSVPE1V2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILSVPE1V3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILSVPE1T4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVOAOH0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1ILSVOAOH0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "5470",
//						"y": "850",
//						"outlet": {
//							"jaxId": "1ILSVPE1V4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT08I650"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1ILSVOIOF0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2580",
//						"y": "850",
//						"outlet": {
//							"jaxId": "1ILSVPE1V5",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSUR7J30"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1ILSVQUN80",
//					"attrs": {
//						"id": "CheckState",
//						"viewName": "",
//						"label": "",
//						"x": "3665",
//						"y": "410",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILT06JN30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILT06JN31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILT06JN01",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": "#input"
//							},
//							"linkedSeg": "1ILT03OC90"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSVR5HA0",
//									"attrs": {
//										"id": "Action",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILT06JN32",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILT06JN33",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.state===\"Execute\""
//									},
//									"linkedSeg": "1ILSUTJSD0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILT06JN00",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILT06JN34",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILT06JN35",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.state===\"Finish\""
//									},
//									"linkedSeg": "1ILT0264T0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1ILSVRHOU0",
//									"attrs": {
//										"id": "Failed",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1ILT06JN36",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILT06JN37",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.state===\"Failed\"||input.state===\"Abort\""
//									},
//									"linkedSeg": "1ILT02H7P0"
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
//					"jaxId": "1ILT0264T0",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "3910",
//						"y": "505",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILT06JN38",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILT06JN39",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILT06JN02",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILT02H7P0",
//					"attrs": {
//						"id": "Failed",
//						"viewName": "",
//						"label": "",
//						"x": "3910",
//						"y": "600",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILT06JN310",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILT06JN311",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILT06JN03",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILT03OC90",
//					"attrs": {
//						"id": "WrongState",
//						"viewName": "",
//						"label": "",
//						"x": "3910",
//						"y": "675",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILT06JN312",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILT06JN313",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILT06JN04",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT04DHI0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1ILT04DHI0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "4055",
//						"y": "850",
//						"outlet": {
//							"jaxId": "1ILT06JN314",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT0DP170"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILT07R4B0",
//					"attrs": {
//						"id": "WrongAction",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "785",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILT08VB20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILT08VB21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILT08VB10",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT9HJBF0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1ILT08I650",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "4960",
//						"y": "850",
//						"outlet": {
//							"jaxId": "1ILT08VB22",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT04DHI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1ILT0BHKD0",
//					"attrs": {
//						"id": "TryStep",
//						"viewName": "",
//						"label": "",
//						"x": "3455",
//						"y": "425",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILT0CR6Q0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILT0CR6Q1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILT0CR6N0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVQUN80"
//						},
//						"catchlet": {
//							"jaxId": "1ILT0CR6O0",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT0D8NK0"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILT0D8NK0",
//					"attrs": {
//						"id": "StepError",
//						"viewName": "",
//						"label": "",
//						"x": "3665",
//						"y": "675",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILT0EQL90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILT0EQL91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILT0EQL80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT0DP170"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1ILT0DP170",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3785",
//						"y": "850",
//						"outlet": {
//							"jaxId": "1ILT0EQL92",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVOIOF0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILT0LRHB0",
//					"attrs": {
//						"id": "WaitError",
//						"viewName": "",
//						"label": "",
//						"x": "5325",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILT0MD900",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILT0MD901",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILT0MD8U0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSVOAOH0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1ILT8S7BH0",
//					"attrs": {
//						"id": "UserHelp",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "690",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "#input.text",
//						"multi": "false",
//						"withChat": "true",
//						"outlet": {
//							"jaxId": "1ILT97VVC0",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1ILT9HJBF0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1ILT8S7AS0",
//									"attrs": {
//										"id": "Done",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Operation completed, continue",
//											"localize": {
//												"EN": "Operation completed, continue",
//												"CN": "操作完成，继续执行"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1ILT97VVF4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILT97VVF5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1ILT9HJBF0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1ILT8S7AS1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Operation cannot be completed, aborting",
//											"localize": {
//												"EN": "Operation cannot be completed, aborting",
//												"CN": "无法完成操作，放弃执行"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1ILT97VVF6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1ILT97VVF7",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1ILT9HJBF0"
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
//					"def": "aiBot",
//					"jaxId": "1ILT8UD980",
//					"attrs": {
//						"id": "DoAskUser",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "595",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILT97VVF8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILT97VVF9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysAskUser.js",
//						"argument": "#{}#>input.content",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1ILT97VVC1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT9HJBF0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILT9DK710",
//					"attrs": {
//						"id": "CallTool",
//						"viewName": "",
//						"label": "",
//						"x": "4650",
//						"y": "525",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILT9L92M0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILT9L92M1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILT9L9290",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT9HJBF0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1ILT9HJBF0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "4935",
//						"y": "660",
//						"outlet": {
//							"jaxId": "1ILT9L92M2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT08I650"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1ILTBGCNA0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2230",
//						"y": "305",
//						"outlet": {
//							"jaxId": "1ILTBGJ0B1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILTPM0KH0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILTCD3PV0",
//					"attrs": {
//						"id": "NoRpa",
//						"viewName": "",
//						"label": "",
//						"x": "945",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1ILTCKSI30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILTCKSI31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILTCKSHO2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1ILTCI6FB0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "765",
//						"y": "395",
//						"outlet": {
//							"jaxId": "1ILTCKSI36",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSUG4L80"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1ILTCIOJG0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1295",
//						"y": "150",
//						"outlet": {
//							"jaxId": "1ILTCKSI37",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT9PNF50"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1ILTTFKLB0",
//					"attrs": {
//						"id": "TipStep",
//						"viewName": "",
//						"label": "",
//						"x": "3235",
//						"y": "425",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILTTGDNA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILTTGDNA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input.content",
//						"outlet": {
//							"jaxId": "1ILTTGDMS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILT0BHKD0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1ILUQMHJU0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "55",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1ILUQN5P70",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILSUENVM0"
//						}
//					},
//					"icon": "args.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"WebRPA\"}"
//	}
//}