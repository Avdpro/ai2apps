//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IJ2K5IBR0MoreImports*/
import fsp from 'fs/promises';
import axios from 'axios'
/*}#1IJ2K5IBR0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IJ2K5IBR0ArgsView*/
	/*}#1IJ2K5IBR0ArgsView*/
};

/*#{1IJ2K5IBR0StartDoc*/
async function getUserLocation() {
	try {
		const response = await axios.get('https://ipinfo.io/json');
		const data = response.data;
		const country = data.country;

		if (country === 'CN') {
			console.log('用户来自中国');
			return "China";
		} else {
			console.log('用户来自国外');
			return "Foreign";
		}
	} 
	catch (error) {
		console.error('无法获取地理位置:', error);
		return "None";
	}
}


/*}#1IJ2K5IBR0StartDoc*/
//----------------------------------------------------------------------------
let ModelDeploy=async function(session){
	let model;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,InitEnv,LoadSteps,HasSteps,LoopSteps,SwitchAction,RunBash,RunBrew,RunTaskBot,CheckStepReuslt,ShowError,AskRetry,AbortStep,TipStep,HfDownLoad,Network,CheckNetwork,Retry,GetLocation,Check,SetMirror,FixArgs,CheckSpace,GoTo,NoSpace,Confirm,RunConda,CheckBash,Finish,Welcome,Fail,Success,CheckStepFinish,CheckType,Finish2;
	let env=null;
	let project=null;
	let steps=null;
	let setupGuide="";
	let ragAddress=globalContext.rag?.solution||"http://localhost:222/solution/";
	
	/*#{1IJ2K5IBR0LocalVals*/
	let current_command="", platform="mac",freespace,needspace, flag=true, model_type;
	/*}#1IJ2K5IBR0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
		}else{
			model=undefined;
		}
		/*#{1IJ2K5IBR0ParseArgs*/
		/*}#1IJ2K5IBR0ParseArgs*/
	}
	
	/*#{1IJ2K5IBR0PreContext*/
	/*}#1IJ2K5IBR0PreContext*/
	context={};
	/*#{1IJ2K5IBR0PostContext*/
	/*}#1IJ2K5IBR0PostContext*/
	let $agent,agent,segs={};
	segs["Start"]=Start=async function(input){//:1IJ2L44GS0
		let result=input;
		try{
			/*#{1IJ2L44GS0Code*/
			false
			/*}#1IJ2L44GS0Code*/
		}catch(error){
			/*#{1IJ2L44GS0ErrorCode*/
			/*}#1IJ2L44GS0ErrorCode*/
		}
		return {seg:InitEnv,result:(result),preSeg:"1IJ2L44GS0",outlet:"1IJ2L5O0Q0",catchSeg:ShowError,catchlet:"1IJ2L5O0Q1"};
	};
	Start.jaxId="1IJ2L44GS0"
	Start.url="Start@"+agentURL
	
	segs["InitEnv"]=InitEnv=async function(input){//:1IJ2KABA10
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/SysInitWorkEnv.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1IJ2KABA10Input*/
		/*}#1IJ2KABA10Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1IJ2KABA10Output*/
		env=globalContext.env;
		freespace=parseFloat(env.freeDiskSpace);
		if(env.platform==="darwin") platform="mac";
		else if(env.platform==="linux") platform="linux";
		else if(env.platform==="win32") platform="windows";
		/*}#1IJ2KABA10Output*/
		return {seg:CheckSpace,result:(result),preSeg:"1IJ2KABA10",outlet:"1IJ2L5O0Q2"};
	};
	InitEnv.jaxId="1IJ2KABA10"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["LoadSteps"]=LoadSteps=async function(input){//:1IJ2KGOHG0
		let result=input
		try{
			/*#{1IJ2KGOHG0Code*/
			try{
				const apiUrl = process.env.MODELHUNT_API_URL;
				const deployUrl = `${apiUrl.replace(/\/$/, '')}/api/v1/models/${model}/deploy`;
			
				try {
					const response = await fetch(deployUrl);
					if (!response.ok) {
						throw new Error(`Failed to fetch deploy config: ${response.status} ${response.statusText}`);
					}
					const deployConfig = await response.json();
					if (deployConfig.platforms && deployConfig.platforms[platform]) {
						steps = deployConfig.platforms[platform].steps;
						console.log(`Loaded ${steps?.length || 0} steps for platform: ${platform}`);
					} else {
						console.log(`No steps found for platform: ${platform}`);
						steps = null;
					}
				} catch(err) {
					console.log("Failed to load deploy steps from API:");
					console.error(err);
					steps = null;
				}
			}catch(err){
				steps=null;
			}
			/*}#1IJ2KGOHG0Code*/
		}catch(error){
			/*#{1IJ2KGOHG0ErrorCode*/
			/*}#1IJ2KGOHG0ErrorCode*/
		}
		return {seg:HasSteps,result:(result),preSeg:"1IJ2KGOHG0",outlet:"1IJ2L5O0Q4"};
	};
	LoadSteps.jaxId="1IJ2KGOHG0"
	LoadSteps.url="LoadSteps@"+agentURL
	
	segs["HasSteps"]=HasSteps=async function(input){//:1IJ2OT4DU0
		let result=input;
		if(!!steps){
			return {seg:LoopSteps,result:(input),preSeg:"1IJ2OT4DU0",outlet:"1IJ2PM4NQ0"};
		}
		return {result:result};
	};
	HasSteps.jaxId="1IJ2OT4DU0"
	HasSteps.url="HasSteps@"+agentURL
	
	segs["LoopSteps"]=LoopSteps=async function(input){//:1IJ2KJ0UK0
		let result=input;
		let list=steps;
		let i,n,item,loopR;
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			loopR=await session.runAISeg(agent,TipStep,item,"1IJ2KJ0UK0","1IJ2L5O0R0")
			if(loopR==="break"){
				break;
			}
		}
		return {seg:Finish,result:(result),preSeg:"1IJ2KJ0UK0",outlet:"1IJ2L5O0R1"};
	};
	LoopSteps.jaxId="1IJ2KJ0UK0"
	LoopSteps.url="LoopSteps@"+agentURL
	
	segs["SwitchAction"]=SwitchAction=async function(input){//:1IJ2KK3SJ0
		let result=input;
		if(input.action.toLowerCase()==="bash"){
			let output=input;
			return {seg:RunBash,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ2L5O0R2"};
		}
		if(input.action.toLowerCase()==="conda"){
			let output=input;
			return {seg:RunConda,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ2KKLVA0"};
		}
		if(input.action==="hf_model"){
			let output=input;
			return {seg:HfDownLoad,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ44KI9E0"};
		}
		if(input.action.toLowerCase()==="brew"){
			let output=input;
			return {seg:RunBrew,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ2KKR2P0"};
		}
		if(input.action.toLowerCase()==="task"){
			let output=input;
			return {seg:RunTaskBot,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ2KL5AC0"};
		}
		return {result:result};
	};
	SwitchAction.jaxId="1IJ2KK3SJ0"
	SwitchAction.url="SwitchAction@"+agentURL
	
	segs["RunBash"]=RunBash=async function(input){//:1IJ2KMQM70
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=input.commands||input.command;
		args['options']="";
		/*#{1IJ2KMQM70PreCodes*/
		current_command=args['commands'];
		/*}#1IJ2KMQM70PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IJ2KMQM70PostCodes*/
		/*}#1IJ2KMQM70PostCodes*/
		return {seg:CheckBash,result:(result),preSeg:"1IJ2KMQM70",outlet:"1IJ2L5O0R4"};
	};
	RunBash.jaxId="1IJ2KMQM70"
	RunBash.url="RunBash@"+agentURL
	
	segs["RunBrew"]=RunBrew=async function(input){//:1IJ2KN5JJ0
		let result;
		let arg={"action":"install","pkgName":input.install};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/ToolBrew.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CheckStepFinish,result:(result),preSeg:"1IJ2KN5JJ0",outlet:"1IJ2L5O0R5"};
	};
	RunBrew.jaxId="1IJ2KN5JJ0"
	RunBrew.url="RunBrew@"+agentURL
	
	segs["RunTaskBot"]=RunTaskBot=async function(input){//:1IJ2KOMUM0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CheckStepReuslt,result:(result),preSeg:"1IJ2KOMUM0",outlet:"1IJ2L5O0R7"};
	};
	RunTaskBot.jaxId="1IJ2KOMUM0"
	RunTaskBot.url="RunTaskBot@"+agentURL
	
	segs["CheckStepReuslt"]=CheckStepReuslt=async function(input){//:1IJ2KQHJP0
		let result=input;
		if(input.result.toLowerCase()==="finish"){
			return {result:input};
		}
		if(input.result.toLowerCase()==="abort"){
			/*#{1IJ2KR7RE0Codes*/
			throw Error(`Run setup step failed: ${input.content}`);
			/*}#1IJ2KR7RE0Codes*/
			return {result:input};
		}
		if(input.result.toLowerCase()==="fail"||input.result.toLowerCase()==="failed"){
			/*#{1IJ2KRD5K0Codes*/
			throw Error(`Uesr abort setup: ${input.content}`);
			/*}#1IJ2KRD5K0Codes*/
			return {result:input};
		}
		return {result:result};
	};
	CheckStepReuslt.jaxId="1IJ2KQHJP0"
	CheckStepReuslt.url="CheckStepReuslt@"+agentURL
	
	segs["ShowError"]=ShowError=async function(input){//:1IJ2L4VCN0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=`执行安装时发生错误：${input}`;
		/*#{1IJ2L4VCN0PreCodes*/
		/*}#1IJ2L4VCN0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IJ2L4VCN0PostCodes*/
		/*}#1IJ2L4VCN0PostCodes*/
		return {seg:AskRetry,result:(result),preSeg:"1IJ2L4VCN0",outlet:"1IJ2L5O0S1"};
	};
	ShowError.jaxId="1IJ2L4VCN0"
	ShowError.url="ShowError@"+agentURL
	
	segs["AskRetry"]=AskRetry=async function(input){//:1IJ2L6AGP0
		let prompt=((($ln==="CN")?("是否再尝试一次?"):("Would you like to try again?")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{emoji:"🔄",text:"Retry",code:0},
			{emoji:"🛑",text:"Abort",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:InitEnv,result:(result),preSeg:"1IJ2L6AGP0",outlet:"1IJ2L6AG80"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:InitEnv,result:(result),preSeg:"1IJ2L6AGP0",outlet:"1IJ2L6AG80"};
		}else if(item.code===1){
			return {seg:AbortStep,result:(result),preSeg:"1IJ2L6AGP0",outlet:"1IJ2L6AG81"};
		}
		return {result:result};
	};
	AskRetry.jaxId="1IJ2L6AGP0"
	AskRetry.url="AskRetry@"+agentURL
	
	segs["AbortStep"]=AbortStep=async function(input){//:1IJ2L9VS90
		let result=input
		try{
			/*#{1IJ2L9VS90Code*/
			result={result:"Failed",content:`Setup project failed: ${input}`};
			/*}#1IJ2L9VS90Code*/
		}catch(error){
			/*#{1IJ2L9VS90ErrorCode*/
			/*}#1IJ2L9VS90ErrorCode*/
		}
		return {result:result};
	};
	AbortStep.jaxId="1IJ2L9VS90"
	AbortStep.url="AbortStep@"+agentURL
	
	segs["TipStep"]=TipStep=async function(input){//:1IJ44HLQB0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input.tip;
		/*#{1IJ44HLQB0PreCodes*/
		if($ln==="CN") content=content.zh;
		else content=content.en;
		/*}#1IJ44HLQB0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IJ44HLQB0PostCodes*/
		/*}#1IJ44HLQB0PostCodes*/
		return {seg:SwitchAction,result:(result),preSeg:"1IJ44HLQB0",outlet:"1IJ44KI9F0"};
	};
	TipStep.jaxId="1IJ44HLQB0"
	TipStep.url="TipStep@"+agentURL
	
	segs["HfDownLoad"]=HfDownLoad=async function(input){//:1IJ44IVQS0
		let result;
		let arg={"model":input.model,"localPath":input.localPath||input.localDir,"token":false};
		let agentNode=(undefined)||null;
		let $query=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/ToolHfModel.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:CheckStepFinish,result:(result),preSeg:"1IJ44IVQS0",outlet:"1IJ44KI9F1"};
	};
	HfDownLoad.jaxId="1IJ44IVQS0"
	HfDownLoad.url="HfDownLoad@"+agentURL
	
	segs["Network"]=Network=async function(input){//:1J58SM22D0
		let prompt;
		let $platform="OpenAI";
		let $model="gpt-4.1-mini";
		let $agent;
		let result;
		
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
		let chatMem=Network.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"你需要根据输入的终端命令输出，判断是否是由于网络问题导致的错误。请根据以下标准判断：\n\n- 如果输出中有与网络连接、服务器不可达、DNS解析错误、超时、无法连接等相关的错误信息，则可能是由于网络问题导致的。\n- 如果输出中有与文件、权限、磁盘空间、程序错误等无关的错误，则可能不是网络问题。\n- 请输出结果为一个JSON格式，包含两个字段：\n  - is_network_issue：布尔值，表示是否是网络问题导致的。\n  - message：一个字符串，描述判断的依据。\n示例： \n{\n\"is_network_issue\": true,\n\"message\": \"Output contains 'Network is unreachable' and 'Connection timed out', indicating a network issue.\"\n}"},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		if($agent){
			result=await session.callAgent($agent.agentNode,$agent.path,{messages:messages,maxToken:opts.maxToken,responseFormat:opts.responseFormat});
		}else{
			result=await session.callSegLLM("Network@"+agentURL,opts,messages,true);
		}
		result=trimJSON(result);
		return {seg:CheckNetwork,result:(result),preSeg:"1J58SM22D0",outlet:"1J58SM7TK0"};
	};
	Network.jaxId="1J58SM22D0"
	Network.url="Network@"+agentURL
	
	segs["CheckNetwork"]=CheckNetwork=async function(input){//:1J5DAI4RE0
		let result=input;
		if(input.is_network_issue){
			return {seg:Retry,result:(input),preSeg:"1J5DAI4RE0",outlet:"1J5DAMHU40"};
		}
		return {result:result};
	};
	CheckNetwork.jaxId="1J5DAI4RE0"
	CheckNetwork.url="CheckNetwork@"+agentURL
	
	segs["Retry"]=Retry=async function(input){//:1J5DAJI1R0
		let prompt=((($ln==="CN")?("网络错误。请检查你的网络连接后重试"):("Network Error. Please check your network connection and retry.")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("重试"):("Retry")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("终止"):("Abort")),code:1},
		];
		let result="";
		let item=null;
		
		/*#{1J5DAJI1R0PreCodes*/
		/*}#1J5DAJI1R0PreCodes*/
		if(silent){
			result={command:current_command};
			return {seg:RunBash,result:(result),preSeg:"1J5DAJI1R0",outlet:"1J5DAJI170"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1J5DAJI1R0PostCodes*/
		/*}#1J5DAJI1R0PostCodes*/
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			result=({command:current_command});
			return {seg:RunBash,result:(result),preSeg:"1J5DAJI1R0",outlet:"1J5DAJI170"};
		}else if(item.code===1){
			return {seg:Fail,result:(result),preSeg:"1J5DAJI1R0",outlet:"1J5DAJI171"};
		}
		/*#{1J5DAJI1R0FinCodes*/
		/*}#1J5DAJI1R0FinCodes*/
		return {result:result};
	};
	Retry.jaxId="1J5DAJI1R0"
	Retry.url="Retry@"+agentURL
	
	segs["GetLocation"]=GetLocation=async function(input){//:1JB1VU3M50
		let result=input
		try{
			/*#{1JB1VU3M50Code*/
			result=await getUserLocation();
			/*}#1JB1VU3M50Code*/
		}catch(error){
			/*#{1JB1VU3M50ErrorCode*/
			/*}#1JB1VU3M50ErrorCode*/
		}
		return {seg:Check,result:(result),preSeg:"1JB1VU3M50",outlet:"1JB1VUBUU0"};
	};
	GetLocation.jaxId="1JB1VU3M50"
	GetLocation.url="GetLocation@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1JB201NH10
		let result=input;
		if(input==="China"){
			return {seg:SetMirror,result:(input),preSeg:"1JB201NH10",outlet:"1JB204FF40"};
		}
		return {seg:LoadSteps,result:(result),preSeg:"1JB201NH10",outlet:"1JB204FF41"};
	};
	Check.jaxId="1JB201NH10"
	Check.url="Check@"+agentURL
	
	segs["SetMirror"]=SetMirror=async function(input){//:1JB203G190
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=["export HF_ENDPOINT=https://hf-mirror.com","export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple","export CONDA_CHANNELS=https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/","export HOMEBREW_BREW_GIT_REMOTE=https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/brew.git","export HOMEBREW_CORE_GIT_REMOTE=https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-core.git","export HOMEBREW_INSTALL_FROM_API=1"];
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:LoadSteps,result:(result),preSeg:"1JB203G190",outlet:"1JB204FF42"};
	};
	SetMirror.jaxId="1JB203G190"
	SetMirror.url="SetMirror@"+agentURL
	
	segs["FixArgs"]=FixArgs=async function(input){//:1JGTKFNIM0
		let result=input;
		let missing=false;
		let smartAsk=false;
		/*#{1JGTKFNIM0PreCodes*/
		/*}#1JGTKFNIM0PreCodes*/
		if(model===undefined || model==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		/*#{1JGTKFNIM0PostCodes*/
		const apiUrl = process.env.MODELHUNT_API_URL;
		const basicUrl = `${apiUrl.replace(/\/$/, '')}/api/v1/models/${model}`;
		const response = await fetch(basicUrl)
		if (!response.ok) {
			throw new Error(`Failed to fetch basic information: ${response.status} ${response.statusText}`);
		}
		const Config = await response.json();
		needspace = Config.size_info;
		model_type = Config.model_type;
		project={
			dirPath:null,
		};
		globalContext.project=project;
		/*}#1JGTKFNIM0PostCodes*/
		return {seg:Welcome,result:(result),preSeg:"1JGTKFNIM0",outlet:"1JGTKGBU20"};
	};
	FixArgs.jaxId="1JGTKFNIM0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["CheckSpace"]=CheckSpace=async function(input){//:1JGUS6QEE0
		let result=input;
		if(needspace < freespace){
			return {seg:Confirm,result:(input),preSeg:"1JGUS6QEE0",outlet:"1JGUS7C460"};
		}
		return {seg:NoSpace,result:(result),preSeg:"1JGUS6QEE0",outlet:"1JGUS7C461"};
	};
	CheckSpace.jaxId="1JGUS6QEE0"
	CheckSpace.url="CheckSpace@"+agentURL
	
	segs["GoTo"]=GoTo=async function(input){//:1JGUT246I0
		let result=input;
		return {seg:null,result:result,preSeg:"1JGUT246I0",outlet:"1JGUT4C180"};
	
	};
	GoTo.jaxId="1JGUT246I0"
	GoTo.url="GoTo@"+agentURL
	
	segs["NoSpace"]=NoSpace=async function(input){//:1JGUT2FMK0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:GoTo,result:(result),preSeg:"1JGUT2FMK0",outlet:"1JGUT4C181"};
	};
	NoSpace.jaxId="1JGUT2FMK0"
	NoSpace.url="NoSpace@"+agentURL
	
	segs["Confirm"]=Confirm=async function(input){//:1JGUT435M0
		let prompt=("Please confirm")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("是"):("Yes")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("否"):("No")),code:1},
		];
		let result="";
		let item=null;
		
		/*#{1JGUT435M0PreCodes*/
		const formatSpace = (gb) => {
			if (gb >= 1000) {
				return `${(gb / 1000).toFixed(2)} TB`;
			}
			return `${gb.toFixed(2)} GB`;
		};
		
		const needSpaceStr = formatSpace(needspace);
		const freeSpaceStr = formatSpace(freespace);
		
		if ($ln === "CN") {
			prompt = `📦 模型部署空间确认\n\n` +
				`此模型需要至少 ${needSpaceStr} 的磁盘空间\n` +
				`您的电脑当前可用空间: ${freeSpaceStr}\n\n` +
				`是否继续安装？`;
		} else {
			prompt = `📦 Model Deployment Space Confirmation\n\n` +
				`This model requires at least ${needSpaceStr} of disk space\n` +
				`Your available space: ${freeSpaceStr}\n\n` +
				`Would you like to continue?`;
		}
		/*}#1JGUT435M0PreCodes*/
		if(silent){
			result="";
			return {seg:GetLocation,result:(result),preSeg:"1JGUT435M0",outlet:"1JGUT43580"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1JGUT435M0PostCodes*/
		/*}#1JGUT435M0PostCodes*/
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:GetLocation,result:(result),preSeg:"1JGUT435M0",outlet:"1JGUT43580"};
		}else if(item.code===1){
			return {seg:GoTo,result:(result),preSeg:"1JGUT435M0",outlet:"1JGUT43581"};
		}
		/*#{1JGUT435M0FinCodes*/
		/*}#1JGUT435M0FinCodes*/
		return {result:result};
	};
	Confirm.jaxId="1JGUT435M0"
	Confirm.url="Confirm@"+agentURL
	
	segs["RunConda"]=RunConda=async function(input){//:1JGUUBSIU0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[`conda create -n ${input.conda} python=${input.pythonVersion} -y`, `conda activate ${input.conda} || source activate ${input.conda} && echo "Successful" || echo "Failed"`];
		args['options']="";
		/*#{1JGUUBSIU0PreCodes*/
		current_command=args['commands'];
		/*}#1JGUUBSIU0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1JGUUBSIU0PostCodes*/
		/*}#1JGUUBSIU0PostCodes*/
		return {seg:CheckBash,result:(result),preSeg:"1JGUUBSIU0",outlet:"1JGUUL0030"};
	};
	RunConda.jaxId="1JGUUBSIU0"
	RunConda.url="RunConda@"+agentURL
	
	segs["CheckBash"]=CheckBash=async function(input){//:1JGUUQ0GJ0
		let result=input;
		/*#{1JGUUQ0GJ0Start*/
		const lines = result.trim().split('\n');
		const lastTwoLines = lines.slice(-2).join('\n');
		/*}#1JGUUQ0GJ0Start*/
		if(!lastTwoLines.includes('Successful')){
			return {seg:Network,result:(input),preSeg:"1JGUUQ0GJ0",outlet:"1JGUUSD410"};
		}
		/*#{1JGUUQ0GJ0Post*/
		/*}#1JGUUQ0GJ0Post*/
		return {seg:Success,result:(result),preSeg:"1JGUUQ0GJ0",outlet:"1JGUUR5L50"};
	};
	CheckBash.jaxId="1JGUUQ0GJ0"
	CheckBash.url="CheckBash@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1JGUV82L40
		let result=input
		try{
			/*#{1JGUV82L40Code*/
			if(flag) result={result:"Finish"};
			else result={result:"Failed"};
			/*}#1JGUV82L40Code*/
		}catch(error){
			/*#{1JGUV82L40ErrorCode*/
			/*}#1JGUV82L40ErrorCode*/
		}
		return {result:result};
	};
	Finish.jaxId="1JGUV82L40"
	Finish.url="Finish@"+agentURL
	
	segs["Welcome"]=Welcome=async function(input){//:1JH01VEB30
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?(`正在为 ${model} 初始化运行环境，请稍候...`):(`Initializing runtime environment for ${model}, please wait...`));
		session.addChatText(role,content,opts);
		return {seg:CheckType,result:(result),preSeg:"1JH01VEB30",outlet:"1JH01VL760"};
	};
	Welcome.jaxId="1JH01VEB30"
	Welcome.url="Welcome@"+agentURL
	
	segs["Fail"]=Fail=async function(input){//:1JH06EVSO0
		let result=input
		try{
			/*#{1JH06EVSO0Code*/
			result={result:"Failed"};
			/*}#1JH06EVSO0Code*/
		}catch(error){
			/*#{1JH06EVSO0ErrorCode*/
			/*}#1JH06EVSO0ErrorCode*/
		}
		return {seg:CheckStepFinish,result:(result),preSeg:"1JH06EVSO0",outlet:"1JH06F8HO0"};
	};
	Fail.jaxId="1JH06EVSO0"
	Fail.url="Fail@"+agentURL
	
	segs["Success"]=Success=async function(input){//:1JH06IMIQ0
		let result=input
		try{
			/*#{1JH06IMIQ0Code*/
			result={result:"Finish"};
			/*}#1JH06IMIQ0Code*/
		}catch(error){
			/*#{1JH06IMIQ0ErrorCode*/
			/*}#1JH06IMIQ0ErrorCode*/
		}
		return {seg:CheckStepFinish,result:(result),preSeg:"1JH06IMIQ0",outlet:"1JH06IVRN0"};
	};
	Success.jaxId="1JH06IMIQ0"
	Success.url="Success@"+agentURL
	
	segs["CheckStepFinish"]=CheckStepFinish=async function(input){//:1JH06ND110
		let result=input;
		/*#{1JH06ND110Start*/
		/*}#1JH06ND110Start*/
		if(input.result==="Finish"){
			return {result:input};
		}
		/*#{1JH06ND110Post*/
		flag=false;
		result="break";
		/*}#1JH06ND110Post*/
		return {result:result};
	};
	CheckStepFinish.jaxId="1JH06ND110"
	CheckStepFinish.url="CheckStepFinish@"+agentURL
	
	segs["CheckType"]=CheckType=async function(input){//:1JH0QV62B0
		let result=input;
		if(model_type==="openrouter"){
			return {seg:Finish2,result:(input),preSeg:"1JH0QV62B0",outlet:"1JH0R0NV90"};
		}
		return {seg:Start,result:(result),preSeg:"1JH0QV62B0",outlet:"1JH0R0NV91"};
	};
	CheckType.jaxId="1JH0QV62B0"
	CheckType.url="CheckType@"+agentURL
	
	segs["Finish2"]=Finish2=async function(input){//:1JH0R118K0
		let result=input
		try{
			/*#{1JH0R118K0Code*/
			result={result:"Finish"};
			/*}#1JH0R118K0Code*/
		}catch(error){
			/*#{1JH0R118K0ErrorCode*/
			/*}#1JH0R118K0ErrorCode*/
		}
		return {result:result};
	};
	Finish2.jaxId="1JH0R118K0"
	Finish2.url="Finish2@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ModelDeploy",
		url:agentURL,
		autoStart:true,
		jaxId:"1IJ2K5IBR0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IJ2K5IBR0PreEntry*/
			/*}#1IJ2K5IBR0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IJ2K5IBR0PostEntry*/
			/*}#1IJ2K5IBR0PostEntry*/
			return result;
		},
		/*#{1IJ2K5IBR0MoreAgentAttrs*/
		/*}#1IJ2K5IBR0MoreAgentAttrs*/
	};
	/*#{1IJ2K5IBR0PostAgent*/
	/*}#1IJ2K5IBR0PostAgent*/
	return agent;
};
/*#{1IJ2K5IBR0ExCodes*/
/*}#1IJ2K5IBR0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ModelDeploy",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				model:{type:"auto",description:""}
			}
		}
	},
	agentNode: "AgentBuilder",
	agentName: "ModelDeploy.js",
	isChatApi: true
}];
//#CodyExport<<<
/*#{1IJ2K5IBR0PostDoc*/
/*}#1IJ2K5IBR0PostDoc*/


export default ModelDeploy;
export{ModelDeploy,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IJ2K5IBR0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IJ2K5IBR1",
//			"attrs": {
//				"PrjSetupBySteps": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IJ2K5IBR7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IJ2K5IBR8",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1IJ2K5IBR9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IJ2K5IBR10",
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
//			"jaxId": "1IJ2K5IBR2",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IJ2K5IBR3",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1JGTKHIC40",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IJ2K5IBR4",
//			"attrs": {
//				"env": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"project": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"steps": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"setupGuide": {
//					"type": "string",
//					"valText": ""
//				},
//				"ragAddress": {
//					"type": "string",
//					"valText": "#globalContext.rag?.solution||\"http://localhost:222/solution/\""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IJ2K5IBR5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IJ2K5IBR6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IJ2L44GS0",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "-550",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2L5O0T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ2L5O0Q0",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2KABA10"
//						},
//						"catchlet": {
//							"jaxId": "1IJ2L5O0Q1",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2L4VCN0"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IJ2KABA10",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "-315",
//						"y": "355",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2L5O0T2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/SysInitWorkEnv.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ2L5O0Q2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGUS6QEE0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ2KGOHG0",
//					"attrs": {
//						"id": "LoadSteps",
//						"viewName": "",
//						"label": "",
//						"x": "1100",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2L5O0T6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ2L5O0Q4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2OT4DU0"
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
//					"jaxId": "1IJ2OT4DU0",
//					"attrs": {
//						"id": "HasSteps",
//						"viewName": "",
//						"label": "",
//						"x": "1315",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2PM4NU0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2PM4NU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ2PM4NQ1",
//							"attrs": {
//								"id": "Guide",
//								"desc": "输出节点。",
//								"output": ""
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ2PM4NQ0",
//									"attrs": {
//										"id": "Steps",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ2PM4NU2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2PM4NU3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!steps"
//									},
//									"linkedSeg": "1IJ2KJ0UK0"
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
//					"jaxId": "1IJ2KJ0UK0",
//					"attrs": {
//						"id": "LoopSteps",
//						"viewName": "",
//						"label": "",
//						"x": "1530",
//						"y": "-45",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2L5O0T8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#steps",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1IJ2L5O0R0",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ44HLQB0"
//						},
//						"catchlet": {
//							"jaxId": "1IJ2L5O0R1",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGUV82L40"
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJ2KK3SJ0",
//					"attrs": {
//						"id": "SwitchAction",
//						"viewName": "",
//						"label": "",
//						"x": "1995",
//						"y": "-185",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2L5O0T10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ2L5O0R3",
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
//									"jaxId": "1IJ2L5O0R2",
//									"attrs": {
//										"id": "bash",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ2L5O0T12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2L5O0T13",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action.toLowerCase()===\"bash\""
//									},
//									"linkedSeg": "1IJ2KMQM70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ2KKLVA0",
//									"attrs": {
//										"id": "conda",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ2L5O0T14",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2L5O0T15",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action.toLowerCase()===\"conda\""
//									},
//									"linkedSeg": "1JGUUBSIU0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ44KI9E0",
//									"attrs": {
//										"id": "hfmodel",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ44KI9K0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ44KI9K1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"hf_model\""
//									},
//									"linkedSeg": "1IJ44IVQS0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ2KKR2P0",
//									"attrs": {
//										"id": "brew",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ2L5O0T16",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2L5O0T17",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action.toLowerCase()===\"brew\""
//									},
//									"linkedSeg": "1IJ2KN5JJ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ2KL5AC0",
//									"attrs": {
//										"id": "task",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ2L5O0T18",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2L5O0T19",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action.toLowerCase()===\"task\""
//									},
//									"linkedSeg": "1IJ2KOMUM0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IJ2KMQM70",
//					"attrs": {
//						"id": "RunBash",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "-335",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2L5O0T20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#input.commands||input.command",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IJ2L5O0R4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JGUUQ0GJ0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IJ2KN5JJ0",
//					"attrs": {
//						"id": "RunBrew",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "-135",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ2L5O0T22",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T23",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/ToolBrew.js",
//						"argument": "{\"action\":\"install\",\"pkgName\":\"#input.install\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ2L5O0R5",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JH06ND110"
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
//					"jaxId": "1IJ2KOMUM0",
//					"attrs": {
//						"id": "RunTaskBot",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "-60",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
//						"context": {
//							"jaxId": "1IJ2L5O0T26",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T27",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ2L5O0R7",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2KQHJP0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJ2KQHJP0",
//					"attrs": {
//						"id": "CheckStepReuslt",
//						"viewName": "",
//						"label": "",
//						"x": "2490",
//						"y": "50",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ2L5O0T28",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T29",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ2L5O0R9",
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
//									"jaxId": "1IJ2L5O0R8",
//									"attrs": {
//										"id": "Finsh",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ2L5O0T30",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2L5O0T31",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result.toLowerCase()===\"finish\""
//									}
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ2KR7RE0",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IJ2L5O0T32",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2L5O0T33",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result.toLowerCase()===\"abort\""
//									}
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ2KRD5K0",
//									"attrs": {
//										"id": "Failed",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IJ2L5O0T34",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2L5O0T35",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result.toLowerCase()===\"fail\"||input.result.toLowerCase()===\"failed\""
//									}
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
//					"jaxId": "1IJ2L4VCN0",
//					"attrs": {
//						"id": "ShowError",
//						"viewName": "",
//						"label": "",
//						"x": "-355",
//						"y": "545",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ2L5O0T44",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T45",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#`执行安装时发生错误：${input}`",
//						"outlet": {
//							"jaxId": "1IJ2L5O0S1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2L6AGP0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IJ2L6AGP0",
//					"attrs": {
//						"id": "AskRetry",
//						"viewName": "",
//						"label": "",
//						"x": "605",
//						"y": "545",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"prompt": {
//							"type": "string",
//							"valText": "Would you like to try again?",
//							"localize": {
//								"EN": "Would you like to try again?",
//								"CN": "是否再尝试一次?"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJ2LAAU60",
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
//									"jaxId": "1IJ2L6AG80",
//									"attrs": {
//										"id": "Retry",
//										"desc": "输出节点。",
//										"text": "Retry",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ2LAAU90",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2LAAU91",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"emoji": "🔄"
//									},
//									"linkedSeg": "1IJ2L8MAO0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ2L6AG81",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "Abort",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ2LAAU92",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2LAAU93",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"emoji": "🛑"
//									},
//									"linkedSeg": "1IJ2L9VS90"
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
//					"def": "connector",
//					"jaxId": "1IJ2L8MAO0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "760",
//						"y": "435",
//						"outlet": {
//							"jaxId": "1IJ2LAAU94",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2L8RCU0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IJ2L8RCU0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "-290",
//						"y": "435",
//						"outlet": {
//							"jaxId": "1IJ2LAAU95",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2KABA10"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ2L9VS90",
//					"attrs": {
//						"id": "AbortStep",
//						"viewName": "",
//						"label": "",
//						"x": "865",
//						"y": "545",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJ2LAAU96",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2LAAU97",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ2LAAU61",
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
//					"def": "output",
//					"jaxId": "1IJ44HLQB0",
//					"attrs": {
//						"id": "TipStep",
//						"viewName": "",
//						"label": "",
//						"x": "1760",
//						"y": "-185",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ44KI9K2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ44KI9K3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.tip",
//						"outlet": {
//							"jaxId": "1IJ44KI9F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2KK3SJ0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IJ44IVQS0",
//					"attrs": {
//						"id": "HfDownLoad",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "-200",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ44KI9K4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ44KI9K5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/ToolHfModel.js",
//						"argument": "{\"model\":\"#input.model\",\"localPath\":\"#input.localPath||input.localDir\",\"token\":false}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ44KI9F1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JH06ND110"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1J58SM22D0",
//					"attrs": {
//						"id": "Network",
//						"viewName": "",
//						"label": "",
//						"x": "2740",
//						"y": "-350",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J58SM7TQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J58SM7TQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "你需要根据输入的终端命令输出，判断是否是由于网络问题导致的错误。请根据以下标准判断：\n\n- 如果输出中有与网络连接、服务器不可达、DNS解析错误、超时、无法连接等相关的错误信息，则可能是由于网络问题导致的。\n- 如果输出中有与文件、权限、磁盘空间、程序错误等无关的错误，则可能不是网络问题。\n- 请输出结果为一个JSON格式，包含两个字段：\n  - is_network_issue：布尔值，表示是否是网络问题导致的。\n  - message：一个字符串，描述判断的依据。\n示例： \n{\n\"is_network_issue\": true,\n\"message\": \"Output contains 'Network is unreachable' and 'Connection timed out', indicating a network issue.\"\n}",
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
//							"jaxId": "1J58SM7TK0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J5DAI4RE0"
//						},
//						"stream": "true",
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
//					"def": "brunch",
//					"jaxId": "1J5DAI4RE0",
//					"attrs": {
//						"id": "CheckNetwork",
//						"viewName": "",
//						"label": "",
//						"x": "2945",
//						"y": "-350",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J5DAMHUK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J5DAMHUK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J5DAMHU41",
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
//									"jaxId": "1J5DAMHU40",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J5DAMHUK2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J5DAMHUK3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.is_network_issue"
//									},
//									"linkedSeg": "1J5DAJI1R0"
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
//					"jaxId": "1J5DAJI1R0",
//					"attrs": {
//						"id": "Retry",
//						"viewName": "",
//						"label": "",
//						"x": "3180",
//						"y": "-365",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Network Error. Please check your network connection and retry.",
//							"localize": {
//								"EN": "Network Error. Please check your network connection and retry.",
//								"CN": "网络错误。请检查你的网络连接后重试"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1J5DAMHU50",
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
//									"jaxId": "1J5DAJI170",
//									"attrs": {
//										"id": "Retry",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Retry",
//											"localize": {
//												"EN": "Retry",
//												"CN": "重试"
//											},
//											"localizable": true
//										},
//										"result": "#{command:current_command}",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J5DAMHUK4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J5DAMHUK5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1J5DATULS0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J5DAJI171",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Abort",
//											"localize": {
//												"EN": "Abort",
//												"CN": "终止"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J5DAMHUK6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J5DAMHUK7",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JH06EVSO0"
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
//					"def": "connector",
//					"jaxId": "1J5DATULS0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3335",
//						"y": "-515",
//						"outlet": {
//							"jaxId": "1J5DAU7GB0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J5DAU3GC0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J5DAU3GC0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2275",
//						"y": "-515",
//						"outlet": {
//							"jaxId": "1J5DAU7GB1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2KMQM70"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JB1VU3M50",
//					"attrs": {
//						"id": "GetLocation",
//						"viewName": "",
//						"label": "",
//						"x": "425",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB1VVH8J0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB1VVH8J1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JB1VUBUU0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB201NH10"
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
//					"jaxId": "1JB201NH10",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "680",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB204FFA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB204FFA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JB204FF41",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJ2KGOHG0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JB204FF40",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JB204FFA2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JB204FFA3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input===\"China\""
//									},
//									"linkedSeg": "1JB203G190"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1JB203G190",
//					"attrs": {
//						"id": "SetMirror",
//						"viewName": "",
//						"label": "",
//						"x": "885",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB204FFA4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB204FFA5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[\"export HF_ENDPOINT=https://hf-mirror.com\",\"export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple\",\"export CONDA_CHANNELS=https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/\",\"export HOMEBREW_BREW_GIT_REMOTE=https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/brew.git\",\"export HOMEBREW_CORE_GIT_REMOTE=https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-core.git\",\"export HOMEBREW_INSTALL_FROM_API=1\"]",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JB204FF42",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2KGOHG0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1JGTKFNIM0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "-1250",
//						"y": "355",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1JGTKGBU20",
//							"attrs": {
//								"id": "Next",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH01VEB30"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JGUS6QEE0",
//					"attrs": {
//						"id": "CheckSpace",
//						"viewName": "",
//						"label": "",
//						"x": "-100",
//						"y": "355",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGUSAQOH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGUSAQOH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JGUS7C461",
//							"attrs": {
//								"id": "Default",
//								"desc": "Outlet.",
//								"output": ""
//							},
//							"linkedSeg": "1JGUT2FMK0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JGUS7C460",
//									"attrs": {
//										"id": "Result",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGUSAQOH2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGUSAQOH3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#needspace < freespace"
//									},
//									"linkedSeg": "1JGUT435M0"
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
//					"jaxId": "1JGUT246I0",
//					"attrs": {
//						"id": "GoTo",
//						"viewName": "",
//						"label": "",
//						"x": "415",
//						"y": "370",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "",
//						"outlet": {
//							"jaxId": "1JGUT4C180",
//							"attrs": {
//								"id": "Next",
//								"desc": "Outlet."
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JGUT2FMK0",
//					"attrs": {
//						"id": "NoSpace",
//						"viewName": "",
//						"label": "",
//						"x": "155",
//						"y": "370",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGUT4C1C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGUT4C1C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JGUT4C181",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGUT246I0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1JGUT435M0",
//					"attrs": {
//						"id": "Confirm",
//						"viewName": "",
//						"label": "",
//						"x": "160",
//						"y": "230",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "Please confirm",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1JGUT4C182",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "Outlet.",
//								"codes": "false"
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JGUT43580",
//									"attrs": {
//										"id": "Yes",
//										"desc": "Outlet.",
//										"text": {
//											"type": "string",
//											"valText": "Yes",
//											"localize": {
//												"EN": "Yes",
//												"CN": "是"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGUT4C1C2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGUT4C1C3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JB1VU3M50"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1JGUT43581",
//									"attrs": {
//										"id": "No",
//										"desc": "Outlet.",
//										"text": {
//											"type": "string",
//											"valText": "No",
//											"localize": {
//												"EN": "No",
//												"CN": "否"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGUT4C1C4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGUT4C1C5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1JGUT246I0"
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
//					"def": "Bash",
//					"jaxId": "1JGUUBSIU0",
//					"attrs": {
//						"id": "RunConda",
//						"viewName": "",
//						"label": "",
//						"x": "2245",
//						"y": "-265",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGUUL00E0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGUUL00E1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[`conda create -n ${input.conda} python=${input.pythonVersion} -y`, `conda activate ${input.conda} || source activate ${input.conda} && echo \"Successful\" || echo \"Failed\"`]",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1JGUUL0030",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JGUUQ0GJ0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JGUUQ0GJ0",
//					"attrs": {
//						"id": "CheckBash",
//						"viewName": "",
//						"label": "",
//						"x": "2490",
//						"y": "-335",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGUUR5LC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGUUR5LC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JGUUR5L50",
//							"attrs": {
//								"id": "Success",
//								"desc": "Outlet.",
//								"output": ""
//							},
//							"linkedSeg": "1JH06IMIQ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JGUUSD410",
//									"attrs": {
//										"id": "Fail",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JGUV0AD10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JGUV0AD11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!lastTwoLines.includes('Successful')"
//									},
//									"linkedSeg": "1J58SM22D0"
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
//					"jaxId": "1JGUV82L40",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "1760",
//						"y": "-30",
//						"desc": "This is an AISeg.",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JGUV8CJ20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JGUV8CJ21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JGUV8CIM0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
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
//					"def": "output",
//					"jaxId": "1JH01VEB30",
//					"attrs": {
//						"id": "Welcome",
//						"viewName": "",
//						"label": "",
//						"x": "-1030",
//						"y": "355",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH01VL7B0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH01VL7B1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "#`Initializing runtime environment for ${model}, please wait...`",
//							"localize": {
//								"EN": "#`Initializing runtime environment for ${model}, please wait...`",
//								"CN": "#`正在为 ${model} 初始化运行环境，请稍候...`"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JH01VL760",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH0QV62B0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JH06EVSO0",
//					"attrs": {
//						"id": "Fail",
//						"viewName": "",
//						"label": "",
//						"x": "3410",
//						"y": "-365",
//						"desc": "This is an AISeg.",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH06FT290",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH06FT291",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH06F8HO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH06ND110"
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
//					"def": "code",
//					"jaxId": "1JH06IMIQ0",
//					"attrs": {
//						"id": "Success",
//						"viewName": "",
//						"label": "",
//						"x": "2740",
//						"y": "-280",
//						"desc": "This is an AISeg.",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH06JH5G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH06JH5G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH06IVRN0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1JH06ND110"
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
//					"jaxId": "1JH06ND110",
//					"attrs": {
//						"id": "CheckStepFinish",
//						"viewName": "",
//						"label": "",
//						"x": "3325",
//						"y": "-185",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH06P1H50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH06P1H51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH06P1GS1",
//							"attrs": {
//								"id": "Fail",
//								"desc": "Outlet.",
//								"output": ""
//							}
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JH06P1GS0",
//									"attrs": {
//										"id": "Finish",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JH06P1H52",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JH06P1H53",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.result===\"Finish\""
//									}
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
//					"jaxId": "1JH0QV62B0",
//					"attrs": {
//						"id": "CheckType",
//						"viewName": "",
//						"label": "",
//						"x": "-810",
//						"y": "355",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0R0NVO0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0R0NVO1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH0R0NV91",
//							"attrs": {
//								"id": "Default",
//								"desc": "Outlet.",
//								"output": ""
//							},
//							"linkedSeg": "1IJ2L44GS0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JH0R0NV90",
//									"attrs": {
//										"id": "Openrouter",
//										"desc": "Outlet.",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JH0R0NVO2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JH0R0NVO3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#model_type===\"openrouter\""
//									},
//									"linkedSeg": "1JH0R118K0"
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
//					"jaxId": "1JH0R118K0",
//					"attrs": {
//						"id": "Finish2",
//						"viewName": "",
//						"label": "",
//						"x": "-550",
//						"y": "225",
//						"desc": "This is an AISeg.",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JH0R1MTA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JH0R1MTA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JH0R1AKP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"AgentBuilder\",\"chatEntry\":false,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
//	}
//}