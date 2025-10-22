//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IJ2K5IBR0MoreImports*/
import fsp from 'fs/promises';
/*}#1IJ2K5IBR0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"prjPath":{
			"name":"prjPath","type":"string",
			"defaultValue":"",
			"desc":"",
		},
		"folder":{
			"name":"folder","type":"auto",
			"defaultValue":"",
			"desc":"",
		},
		"repo":{
			"name":"repo","type":"auto",
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1IJ2K5IBR0ArgsView*/
	/*}#1IJ2K5IBR0ArgsView*/
};

/*#{1IJ2K5IBR0StartDoc*/
function extractSingleJsonBlock(md) {
	const match = md.match(/```json\s*([\s\S]*?)```/i); // 只匹配一次
	return match ? match[1].trim() : null;
}
/*}#1IJ2K5IBR0StartDoc*/
//----------------------------------------------------------------------------
let PrjSetupBySteps=async function(session){
	let prjPath,folder,repo;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,InitEnv,InitPrj,LoadSteps,HasSteps,LoadGuide,LoopSteps,SwitchAction,RunBrew,RunConda,RunTaskBot,CheckStepReuslt,SaveConda,ExposeAgent,ShowError,AskRetry,AbortStep,TipStep,HfDownLoad,AddNote,ShowGuide,GenGuideJs,Export,goto,RunCommand,Summary,OutputGuide,FixArgs,Path,Check,Fail,CheckStatus,OutputFail;
	let env=null;
	let project=null;
	let steps=null;
	let setupGuide="";
	let ragAddress=globalContext.rag?.solution||"http://localhost:222/solution/";
	
	/*#{1IJ2K5IBR0LocalVals*/
	let current_command, current_check_command, current_command_output, current_path, deploy_issues="", deploy_guide, status="yes";
	/*}#1IJ2K5IBR0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			prjPath=input.prjPath;
			folder=input.folder;
			repo=input.repo;
		}else{
			prjPath=undefined;
			folder=undefined;
			repo=undefined;
		}
		/*#{1IJ2K5IBR0ParseArgs*/
		/*}#1IJ2K5IBR0ParseArgs*/
	}
	
	/*#{1IJ2K5IBR0PreContext*/
	function extract(session, sep = '\n<<<###>>>\n') {
		const lines = session.split(/\r?\n/);
		const outputs = [];
		let i = 0;
	
		if (i < lines.length && !/__AGENT_SHELL__>/.test(lines[i])) {
			i++;
			const chunk = [];
			while (i < lines.length && !/__AGENT_SHELL__>/.test(lines[i])) {
			chunk.push(lines[i]);
			i++;
			}
			outputs.push(chunk.join('\n').trim());
		}
		while (i < lines.length) {
			const m = lines[i].match(/__AGENT_SHELL__>\s*(\S.*)$/);
			if (m) {
			i++;
			const chunk = [];
			while (i < lines.length && !/__AGENT_SHELL__>/.test(lines[i])) {
				chunk.push(lines[i]);
				i++;
			}
			outputs.push(chunk.join('\n').trim());
			} else {
			i++;
			}
		}
		return outputs
			.map(o => (o === '' ? ' ' : o))
			.join(sep);
	}
	/*}#1IJ2K5IBR0PreContext*/
	context={};
	/*#{1IJ2K5IBR0PostContext*/
	/*}#1IJ2K5IBR0PostContext*/
	let $agent,agent,segs={};
	segs["Start"]=Start=async function(input){//:1IJ2L44GS0
		let result=input;
		/*#{1IJ2L44GS0Code*/
		false
		/*}#1IJ2L44GS0Code*/
		return {seg:InitEnv,result:(result),preSeg:"1IJ2L44GS0",outlet:"1IJ2L5O0Q0",catchSeg:ShowError,catchlet:"1IJ2L5O0Q1"};
	};
	Start.jaxId="1IJ2L44GS0"
	Start.url="Start@"+agentURL
	
	segs["InitEnv"]=InitEnv=async function(input){//:1IJ2KABA10
		let result;
		let arg=input;
		let agentNode=("")||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/SysInitWorkEnv.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1IJ2KABA10Input*/
		/*}#1IJ2KABA10Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1IJ2KABA10Output*/
		env=globalContext.env;
		/*}#1IJ2KABA10Output*/
		return {seg:InitPrj,result:(result),preSeg:"1IJ2KABA10",outlet:"1IJ2L5O0Q2"};
	};
	InitEnv.jaxId="1IJ2KABA10"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["InitPrj"]=InitPrj=async function(input){//:1IJ2K9A670
		let result=input
		/*#{1IJ2K9A670Code*/
		let dirPath,prjJSON,prjURL,gitURL,prjName,owner,rawURL,branch;
		dirPath=prjPath;
		if(dirPath[0]!=="/"){
			prjPath=dirPath=pathLib.join(session.agentNode.hubPath,dirPath);
		}
		try{
			prjJSON=await fsp.readFile(pathLib.join(dirPath,"project.json"),"utf8");
			prjJSON=JSON.parse(prjJSON);
		}catch(err){
			prjJSON={};
		}
		prjPath=decodeURIComponent(prjPath);
		prjURL=prjJSON.github||prjJSON.gitURL;
		if(prjURL) {
			if (!prjURL.startsWith("https://")) {
				prjURL = "https://" + prjURL;
			}
			if (prjURL.endsWith(".git")) {
				gitURL = prjURL;
				prjURL = prjURL.slice(0, -4);
			} else {
				if (prjURL.endsWith("/")) {
					prjURL = prjURL.substring(0, prjURL.length - 1);
				}
				gitURL = prjURL + ".git";
			}
			let parts = prjURL.split('/');
			prjName = parts[parts.length - 1];
			owner = parts[parts.length - 2];
			branch = "main"
			rawURL = "https://raw.githubusercontent.com/" + prjURL.substring("https://github.com/".length) + "/refs/heads/" + branch;
		}else{
			owner=null;
			prjName=null;
			branch=null;
			prjURL=null;
			gitURL=null;
			rawURL=null;
		}
		project={
			owner:owner,
			repo:prjName,
			branch:branch,
			name:prjName,
			url:prjURL,
			gitURL:gitURL,
			rawURL:rawURL,
			dirPath:dirPath,
			requirements:{},
			conda:null,
			venv:null,
			progress:[],
			bashLogs:[]
		};
		globalContext.project=project;
		/*}#1IJ2K9A670Code*/
		return {seg:Path,result:(result),preSeg:"1IJ2K9A670",outlet:"1IJ2L5O0Q3"};
	};
	InitPrj.jaxId="1IJ2K9A670"
	InitPrj.url="InitPrj@"+agentURL
	
	segs["LoadSteps"]=LoadSteps=async function(input){//:1IJ2KGOHG0
		let result=input
		/*#{1IJ2KGOHG0Code*/
		try{
			let modual=await import(pathLib.join(prjPath,`setup_project.js?time=${Date.now()}`));
		// let modual2=await import(pathLib.join(prjPath,`setup_agent.js?time=${Date.now()}`));
			if(modual){
				try{
					steps=await modual.default(env,project);
				}catch(err){
					console.log("Read setup steps error:");
					console.error(err);
					steps=null;
				}
			}
			//steps=await modual2.default(env,project);
		}catch(err){
			console.log(err);
			steps=null;
		}
		/*}#1IJ2KGOHG0Code*/
		return {seg:HasSteps,result:(result),preSeg:"1IJ2KGOHG0",outlet:"1IJ2L5O0Q4"};
	};
	LoadSteps.jaxId="1IJ2KGOHG0"
	LoadSteps.url="LoadSteps@"+agentURL
	
	segs["HasSteps"]=HasSteps=async function(input){//:1IJ2OT4DU0
		let result=input;
		if(!!steps){
			return {seg:LoopSteps,result:(input),preSeg:"1IJ2OT4DU0",outlet:"1IJ2PM4NQ0"};
		}
		return {seg:LoadGuide,result:(result),preSeg:"1IJ2OT4DU0",outlet:"1IJ2PM4NQ1"};
	};
	HasSteps.jaxId="1IJ2OT4DU0"
	HasSteps.url="HasSteps@"+agentURL
	
	segs["LoadGuide"]=LoadGuide=async function(input){//:1IJ2SSKUN0
		let result=input
		/*#{1IJ2SSKUN0Code*/
		try{
			setupGuide=await fsp.readFile(pathLib.join(decodeURIComponent(prjPath),"setup_guide.md"),"utf8");
		}catch(err){
			setupGuide=null;
		}
		/*}#1IJ2SSKUN0Code*/
		return {seg:ShowGuide,result:(result),preSeg:"1IJ2SSKUN0",outlet:"1IJ2STPIS0"};
	};
	LoadGuide.jaxId="1IJ2SSKUN0"
	LoadGuide.url="LoadGuide@"+agentURL
	
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
		return {seg:CheckStatus,result:(result),preSeg:"1IJ2KJ0UK0",outlet:"1IJ2L5O0R1"};
	};
	LoopSteps.jaxId="1IJ2KJ0UK0"
	LoopSteps.url="LoopSteps@"+agentURL
	
	segs["SwitchAction"]=SwitchAction=async function(input){//:1IJ2KK3SJ0
		let result=input;
		if(input.action.toLowerCase()==="bash"){
			let output=input;
			return {seg:RunCommand,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ2L5O0R2"};
		}
		if(input.action.toLowerCase()==="brew"){
			let output=input;
			return {seg:RunBrew,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ2KKLVA0"};
		}
		if(input.action==="hf-model"){
			let output=input;
			return {seg:HfDownLoad,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ44KI9E0"};
		}
		if(input.action.toLowerCase()==="conda"){
			let output=input;
			return {seg:RunConda,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ2KKR2P0"};
		}
		if(input.action.toLowerCase()==="task"){
			let output=input;
			return {seg:RunTaskBot,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ2KL5AC0"};
		}
		return {result:result};
	};
	SwitchAction.jaxId="1IJ2KK3SJ0"
	SwitchAction.url="SwitchAction@"+agentURL
	
	segs["RunBrew"]=RunBrew=async function(input){//:1IJ2KN5JJ0
		let result;
		let arg={"action":"install","pkgName":input.install};
		let agentNode=("")||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/ToolBrew.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	RunBrew.jaxId="1IJ2KN5JJ0"
	RunBrew.url="RunBrew@"+agentURL
	
	segs["RunConda"]=RunConda=async function(input){//:1IJ2KNFK40
		let result;
		let arg={"refName":input.conda||input.name,"pyversion":input.pythonVersion,"installReq":input.installReq||input.installPkg||input.installDep};
		let agentNode=("")||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/PrjCheckCondaEnv.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1IJ2KNFK40Input*/
		/*}#1IJ2KNFK40Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1IJ2KNFK40Output*/
		/*}#1IJ2KNFK40Output*/
		return {seg:CheckStepReuslt,result:(result),preSeg:"1IJ2KNFK40",outlet:"1IJ2L5O0R6"};
	};
	RunConda.jaxId="1IJ2KNFK40"
	RunConda.url="RunConda@"+agentURL
	
	segs["RunTaskBot"]=RunTaskBot=async function(input){//:1IJ2KOMUM0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
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
	
	segs["SaveConda"]=SaveConda=async function(input){//:1IJEP433U0
		let result=input
		/*#{1IJEP433U0Code*/
		let dirPath=prjPath;
		if(dirPath[0]!=="/"){
			prjPath=dirPath=pathLib.join(session.agentNode.hubPath,dirPath);
		}
		if(project.conda){
			let agentJSON;
			try{
				agentJSON=await fsp.readFile(pathLib.join(dirPath,"agent.json"),"utf8");
				agentJSON=JSON.parse(agentJSON);
				agentJSON.conda=project.conda;
				await fsp.writeFile(pathLib.join(dirPath,"agent.json"),JSON.stringify(agentJSON,null,"\t"));
			}catch(err){
				agentJSON={};
			}
		}
		/*}#1IJEP433U0Code*/
		return {result:result};
	};
	SaveConda.jaxId="1IJEP433U0"
	SaveConda.url="SaveConda@"+agentURL
	
	segs["ExposeAgent"]=ExposeAgent=async function(input){//:1IJ2L1V3T0
		let result=input
		/*#{1IJ2L1V3T0Code*/
		let dirPath=prjPath;
		if(dirPath[0]!=="/"){
			prjPath=dirPath=pathLib.join(session.agentNode.hubPath,dirPath);
		}
		let agentJSON;
		try{
			agentJSON=await fsp.readFile(pathLib.join(dirPath,"agent.json"),"utf8");
			agentJSON=JSON.parse(agentJSON);
			//Expose agentNode:
			agentJSON.expose=true;
			await fsp.writeFile(pathLib.join(dirPath,"agent.json"),JSON.stringify(agentJSON,null,"\t"));
		}catch(err){
			agentJSON={};
		}
		/*}#1IJ2L1V3T0Code*/
		return {result:result};
	};
	ExposeAgent.jaxId="1IJ2L1V3T0"
	ExposeAgent.url="ExposeAgent@"+agentURL
	
	segs["ShowError"]=ShowError=async function(input){//:1IJ2L4VCN0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
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
		/*#{1IJ2L9VS90Code*/
		result={result:"Failed",content:`Setup project failed: ${input}`};
		/*}#1IJ2L9VS90Code*/
		return {result:result};
	};
	AbortStep.jaxId="1IJ2L9VS90"
	AbortStep.url="AbortStep@"+agentURL
	
	segs["TipStep"]=TipStep=async function(input){//:1IJ44HLQB0
		let result=input;
		let channel="Process";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=input.tip;
		session.addChatText(role,content,opts);
		return {seg:SwitchAction,result:(result),preSeg:"1IJ44HLQB0",outlet:"1IJ44KI9F0"};
	};
	TipStep.jaxId="1IJ44HLQB0"
	TipStep.url="TipStep@"+agentURL
	
	segs["HfDownLoad"]=HfDownLoad=async function(input){//:1IJ44IVQS0
		let result;
		let arg={"model":input.model,"localPath":input.localPath||input.localDir,"token":false};
		let agentNode=("")||null;
		let sourcePath=pathLib.join(basePath,"../AgentBuilder/ToolHfModel.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	HfDownLoad.jaxId="1IJ44IVQS0"
	HfDownLoad.url="HfDownLoad@"+agentURL
	
	segs["AddNote"]=AddNote=async function(input){//:1IJI789IM0
		let result=input
		/*#{1IJI789IM0Code*/
		let note;
		note={
			desc:`安装指南`,
			doc:input,
			env:{
				platform:env.platform,
				arch:env.arch
			},
			project:{
				name:project.name,
				url:project.url
			},
			tags:"agent"
		};
		//throw Error("测试 Catch Error 的异常");
		try{
			session.callClient("AddNote",{note:note});
		}catch(err){
			//Ignore err
		}
		result={conda: project.conda, guide: input};
		/*}#1IJI789IM0Code*/
		return {result:result};
	};
	AddNote.jaxId="1IJI789IM0"
	AddNote.url="AddNote@"+agentURL
	
	segs["ShowGuide"]=ShowGuide=async function(input){//:1IJL3NK8N0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=`### 找到安装指南：\n----\n${setupGuide}`;
		/*#{1IJL3NK8N0PreCodes*/
		globalContext.guide = setupGuide;
		/*}#1IJL3NK8N0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IJL3NK8N0PostCodes*/
		/*}#1IJL3NK8N0PostCodes*/
		return {seg:GenGuideJs,result:(result),preSeg:"1IJL3NK8N0",outlet:"1IJL3VU321"};
	};
	ShowGuide.jaxId="1IJL3NK8N0"
	ShowGuide.url="ShowGuide@"+agentURL
	
	segs["GenGuideJs"]=GenGuideJs=async function(input){//:1ILI9VIEO0
		let prompt;
		let result=null;
		{
			const $text="Plan the deployment process.";
			const $role=(undefined)||"assistant";
			const $roleText=("assistant")||undefined;
			await session.addChatText($role,$text,{"channel":"Process","txtHeader":$roleText});
		}
		/*#{1ILI9VIEO0Input*/
		/*}#1ILI9VIEO0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1",
			maxToken:32768,
			temperature:0.7,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=GenGuideJs.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`You are using a terminal on a MacOS/Linux or Windows device to help setup a project. The current path is a downloaded github project folder, so you don't need to git clone the project.

The detailed environment is:
${JSON.stringify(globalContext.env,null,"\t")}.

You are able to execute commands in the terminal based on the given task.
You can only interact with the terminal (no GUI access).

Your task is to provide **all subsequent actions** at once to complete the given task.
You should carefully consider the task and provide a list of actions in the correct order.

## Core Principles
1. **Efficiency First**: Always look for the simplest, most efficient deployment method
2. **Resource Awareness**: Consider memory, disk space, and processing requirements vs. available resources
3. **Alternative Analysis**: Check for easier alternatives (pip packages, pre-built tools, Docker images) before complex setups
4. **Platform Optimization**: Leverage platform-specific advantages and native optimizations
5. **Comprehensive Testing**: Ensure the project works end-to-end after setup

## Available Actions
- bash: Execute a series of bash commands.
- brew: Install a package using Homebrew.
- conda: Only for Set up or activate a conda environment, if use conda install, please choose bash action.
- hf-model: Download a model from Hugging Face.

Based on the task, please determine all the actions required to complete the task, including the commands, parameters, and additional details for each action.

## Output Format

{
"Reasoning": "Comprehensive analysis including: (1) Project requirements and complexity, (2) Available alternatives considered (pip packages, Docker, simpler tools), (3) Resource requirements vs. environment capacity (memory, disk, GPU), (4) Platform-specific considerations, (5) Chosen approach rationale with estimated setup time and resource usage, (6) Step-by-step plan with validation strategy",
"Actions": [
{
"action": "action_type", // One of: "bash", "brew", "conda", "hf-model"
"tip": "Clear description including: what this accomplishes",
"commands": [str], // Array of commands to execute (only for "bash" action)
"install": str, // Package to install (only for "brew" action)
"conda": str, // Conda environment name (only for "conda" action)
"pythonVersion": str, // Python version for conda environment (only for "conda" action)
"model": str, // Model to download (only for "hf-model" action)
"localPath": str // Local path to save the model (only for "hf-model" action)
}
// Additional actions including validation and usage examples...
]
}

## Enhanced Examples

### Example 1: Traditional Complex Setup with Full Validation
{
"Reasoning": "Setting up FishSpeech project requires full environment - no simpler alternatives available for complete functionality. Analyzed resources: needs ~8GB RAM, ~5GB disk, 10-15 minute setup. Current environment has sufficient resources. Plan: install system dependencies → create conda environment → install Python packages → download model → validate functionality → provide usage guidance.",
"Actions": [
{
"action": "conda",
"tip": "Create isolated Python 3.10 environment for FishSpeech.",
"conda": "fish-speech",
"pythonVersion": "3.10"
},
{
"action": "brew",
"tip": "Install FFmpeg for audio processing.",
"install": "ffmpeg"
},
{
"action": "brew",
"tip": "Install PortAudio for audio I/O.",
"install": "portaudio"
},
{
"action": "bash",
"tip": "Install PyTorch and core dependencies.",
"commands": [
"pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1",
"pip install websockets huggingface-hub openai nest_asyncio",
"pip install -e ."
]
},
{
"action": "hf-model",
"tip": "Download pre-trained FishSpeech model (~2GB).,
"model": "fishaudio/fish-speech-1.5",
"localPath": "checkpoints/fish-speech-1.5"
},
{
"action": "bash",
"tip": "Validate installation by testing import.",
"commands": ["python -c \"import fish_speech; print('Import successful')\""]
},
{
"action": "bash",
"tip": "Display usage examples and next steps. Shows how to run inference and training commands",
"commands": [
"echo 'Setup complete! Usage examples:'",
"echo ' python inference.py --text \"Hello world\"'",
"echo ' python train.py --config configs/base.yaml'",
"echo 'Check README.md for detailed usage instructions'"
]
}
]
}

### Example 2: Resource-Constrained Smart Setup
{
"Reasoning": "Setting up Stable Diffusion project on device with limited resources (27GB free disk). Analyzed options: (1) Full setup needs 20GB+, (2) Lightweight alternatives available. Choosing CPU-optimized approach with smaller models. Estimated: 5GB disk, 4GB RAM, 15 minutes setup. Plan: create environment → install optimized dependencies → download smaller model → validate → provide resource-conscious usage tips.",
"Actions": [
{
"action": "conda",
"tip": "Create Python 3.9 environment for compatibility.",
"conda": "stable-diffusion-lite",
"pythonVersion": "3.9"
},
{
"action": "bash",
"tip": "Install CPU-optimized PyTorch and essential packages.",
"commands": [
"pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu",
"pip install diffusers transformers accelerate",
"pip install pillow requests"
]
},
{
"action": "hf-model",
"tip": "Download compact Stable Diffusion model (~2GB vs 8GB full version).",
"model": "runwayml/stable-diffusion-v1-5",
"localPath": "models/stable-diffusion-v1-5"
},
{
"action": "bash",
"tip": "Test basic functionality with CPU inference.",
"commands": [
"python -c \"from diffusers import StableDiffusionPipeline; print('CPU setup successful')\"",
"echo 'Note: Using CPU inference - generation will be slower but uses less resources'"
]
},
{
"action": "bash",
"tip": "Provide resource-conscious usage examples and optimization tips for the constrained environment",
"commands": [
"echo 'Resource-optimized setup complete!'",
"echo 'Usage tips for limited resources:'",
"echo ' - Use smaller image sizes (512x512 or less)'",
"echo ' - Reduce inference steps (10-20 instead of 50)'",
"echo ' - Use low_cpu_mem_usage=True in pipeline loading'",
"echo 'Example: pipe = StableDiffusionPipeline.from_pretrained(model_path, low_cpu_mem_usage=True)'"
]
}
]
}

## Critical Guidelines

### ⚠️ **Mandatory Requirements**
1. **Always analyze alternatives** in Reasoning before choosing approach
2. **Consider resource constraints** vs. environment capabilities
3. **Include validation actions** to ensure functionality works
4. **Provide usage examples** as final actions
5. **Only use commands mentioned in project documentation**
6. **Optimize for target platform** and available resources
7. **Always create a conda environment first.**

### 🚫 **Prohibited Actions**
- Using commands not found in project documentation
- Ignoring simpler alternatives when available
- Skipping validation steps
- Assuming unlimited resources
- Creating unnecessarily complex setups

### 📋 **Quality Checklist for Reasoning**
- [ ] Checked for simpler installation alternatives (pip packages, Docker, etc.)
- [ ] Analyzed resource requirements vs. available resources (memory, disk, GPU)
- [ ] Considered platform-specific optimizations (Apple Silicon, etc.)
- [ ] Estimated setup time and resource usage
- [ ] Planned validation strategy

### Important Notes:
1. Provide all actions at once in the correct order with JSON format
2. Ensure commands are valid for the target operating system (MacOS/Linux or Windows)
3. Include all necessary parameters for each action
4. Include validation actions to test the project works correctly
5. Include usage example actions as final steps
6. If downloading from HuggingFace, must use hf-model tool
7. Only use bash/brew commands mentioned in the input documentation
8. **Always prioritize efficiency and resource optimization in your analysis**
9. **In the tip field, include expected output and fallback options**
10. If test with command that is impossible to terminate automatically, such as start a web service or api service, you need to set a timeout with 2 minute.
11. Do not give commands list that requires multiple lines of input in the terminal.
12. If you need to use pdf/png/... to test the function, you can use wget to download a simple example, for example, https://ontheline.trincoll.edu/images/bookdown/sample-local-pdf.pdf
` + (($ln==="CN")?("用中文输出。"):("Output in English."))},
		];
		/*#{1ILI9VIEO0PrePrompt*/
		/*}#1ILI9VIEO0PrePrompt*/
		prompt=globalContext.guide;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1ILI9VIEO0FilterMessage*/
			/*}#1ILI9VIEO0FilterMessage*/
			messages.push(msg);
		}
		/*#{1ILI9VIEO0PreCall*/
		/*}#1ILI9VIEO0PreCall*/
		result=(result===null)?(await session.callSegLLM("GenGuideJs@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1ILI9VIEO0PostCall*/
		deploy_guide=JSON.stringify(result);
		/*}#1ILI9VIEO0PostCall*/
		return {seg:Export,result:(result),preSeg:"1ILI9VIEO0",outlet:"1ILIA093U0"};
	};
	GenGuideJs.jaxId="1ILI9VIEO0"
	GenGuideJs.url="GenGuideJs@"+agentURL
	
	segs["Export"]=Export=async function(input){//:1ILIBLIQU0
		let result=input
		/*#{1ILIBLIQU0Code*/
		let actions = result.Actions;
		let code = `import pathLib from "path";
		
		//----------------------------------------------------------------------------
		function install(env,project){
		let $ln=env.$ln||"EN";
		let steps=null;
		let dirPath,gitPath,gitURL;
		dirPath=project.dirPath;
		gitPath=pathLib.join(dirPath,"prj");
		gitURL=project.gitURL;
		steps=${JSON.stringify(actions)};
		return steps;
		}
		
		//----------------------------------------------------------------------------
		function uninstall(env,project){
		let $ln=env.$ln||"EN";
		let steps;
		let dirPath,gitPath,gitURL;
		dirPath=project.dirPath;
		gitPath=pathLib.join(dirPath,"prj");
		gitURL=project.gitURL;
		if(env.platform==="darwin" && env.arch==="arm64"){
		steps=[
			{
				action:"bash",
				tip:(($ln==="CN")?("删除GitHub项目内容。"):/*EN*/("Delete GitHub project.")),
				commands:[
					\`cd \${dirPath}\`,
					\`rm -r prj\`,
				]
			},
		];
		}
		return steps;
		};
		
		export default install;
		export {install}`;
		const filePath = pathLib.join(prjPath, 'setup_project.js');
		await fsp.writeFile(filePath, code);
		/*}#1ILIBLIQU0Code*/
		return {seg:goto,result:(result),preSeg:"1ILIBLIQU0",outlet:"1ILIBMA7E0"};
	};
	Export.jaxId="1ILIBLIQU0"
	Export.url="Export@"+agentURL
	
	segs["goto"]=goto=async function(input){//:1ILIIHJ2K0
		let result=input;
		return {seg:LoadSteps,result:result,preSeg:"1IJ2KGOHG0",outlet:"1ILIII45L0"};
	
	};
	goto.jaxId="1IJ2KGOHG0"
	goto.url="goto@"+agentURL
	
	segs["RunCommand"]=RunCommand=async function(input){//:1IUIOCI2D0
		let result;
		let arg={"command":input.commands,"repo":repo};
		let agentNode=("")||null;
		let sourcePath=pathLib.join(basePath,"../AutoDeploy/ToolRunCommand.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1IUIOCI2D0Input*/
		/*}#1IUIOCI2D0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1IUIOCI2D0Output*/
		if(result.length > 0) deploy_issues += result + "\n";
		current_command=input.commands;
		/*}#1IUIOCI2D0Output*/
		return {seg:Check,result:(result),preSeg:"1IUIOCI2D0",outlet:"1IUIOD8G80"};
	};
	RunCommand.jaxId="1IUIOCI2D0"
	RunCommand.url="RunCommand@"+agentURL
	
	segs["Summary"]=Summary=async function(input){//:1IVJ2JPN90
		let prompt;
		let result;
		
		let opts={
			platform:"Claude",
			mode:"claude-3-7-sonnet-latest",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=Summary.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`请根据部署项目流程和其中部分运行命令存在的报错和解决方法，总结一份全面的部署指南。逐条列出每一步的运行命令，并指出如果遇到某个报错，如何解决，以markdown格式呈现。` + (($ln==="CN")?("用中文输出。"):("Output in English."))},
		];
		prompt=`部署流程：${deploy_guide}\n报错及解决方案：${deploy_issues}`;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("Summary@"+agentURL,opts,messages,true);
		return {seg:OutputGuide,result:(result),preSeg:"1IVJ2JPN90",outlet:"1IVJ2OCI50"};
	};
	Summary.jaxId="1IVJ2JPN90"
	Summary.url="Summary@"+agentURL
	
	segs["OutputGuide"]=OutputGuide=async function(input){//:1IVJ2POB40
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:AddNote,result:(result),preSeg:"1IVJ2POB40",outlet:"1IVJ2Q8R40"};
	};
	OutputGuide.jaxId="1IVJ2POB40"
	OutputGuide.url="OutputGuide@"+agentURL
	
	segs["FixArgs"]=FixArgs=async function(input){//:1IVPD3IRS0
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(prjPath===undefined || prjPath==="") missing=true;
		if(folder===undefined || folder==="") missing=true;
		if(repo===undefined || repo==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:Start,result:(result),preSeg:"1IVPD3IRS0",outlet:"1IVPD4MA00"};
	};
	FixArgs.jaxId="1IVPD3IRS0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Path"]=Path=async function(input){//:1J03OF97J0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=`cd "${decodeURIComponent(pathLib.join(prjPath,"projects",folder))}"`;
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:LoadGuide,result:(result),preSeg:"1J03OF97J0",outlet:"1J03OGT5L0"};
	};
	Path.jaxId="1J03OF97J0"
	Path.url="Path@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1J3IH1MMH0
		let result=input;
		if(input==="break"){
			return {seg:Fail,result:(input),preSeg:"1J3IH1MMH0",outlet:"1J3IH2C670"};
		}
		return {result:result};
	};
	Check.jaxId="1J3IH1MMH0"
	Check.url="Check@"+agentURL
	
	segs["Fail"]=Fail=async function(input){//:1J3IH3LP60
		let result=input
		/*#{1J3IH3LP60Code*/
		result="break";
		status="no";
		/*}#1J3IH3LP60Code*/
		return {result:result};
	};
	Fail.jaxId="1J3IH3LP60"
	Fail.url="Fail@"+agentURL
	
	segs["CheckStatus"]=CheckStatus=async function(input){//:1J3IH61PT0
		let result=input;
		if(status==="no"){
			return {seg:OutputFail,result:(input),preSeg:"1J3IH61PT0",outlet:"1J3IH71TH0"};
		}
		return {seg:Summary,result:(result),preSeg:"1J3IH61PT0",outlet:"1J3IH71TH1"};
	};
	CheckStatus.jaxId="1J3IH61PT0"
	CheckStatus.url="CheckStatus@"+agentURL
	
	segs["OutputFail"]=OutputFail=async function(input){//:1J3IH77PV0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("Bug修复失败，部署终止"):("Bug fix failed, deployment aborted"));
		/*#{1J3IH77PV0PreCodes*/
		/*}#1J3IH77PV0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1J3IH77PV0PostCodes*/
		result="Fail to deploy"
		/*}#1J3IH77PV0PostCodes*/
		return {result:result};
	};
	OutputFail.jaxId="1J3IH77PV0"
	OutputFail.url="OutputFail@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"PrjSetupBySteps",
		url:agentURL,
		autoStart:true,
		jaxId:"1IJ2K5IBR0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{prjPath,folder,repo}*/){
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
		name: "PrjSetupBySteps",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				prjPath:{type:"string",description:""},
				folder:{type:"auto",description:""},
				repo:{type:"auto",description:""}
			}
		}
	},
	agentNode: "builder_new",
	agentName: "PrjSetupBySteps.js",
	isChatApi: true
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
		name:"PrjSetupBySteps",showName:"PrjSetupBySteps",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"prjPath":{name:"prjPath",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"folder":{name:"folder",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"repo":{name:"repo",showName:undefined,type:"auto",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","prjPath","folder","repo","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["PrjSetupBySteps"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['prjPath']=");this.genAttrStatement(seg.getAttr("prjPath"));coder.packText(";");coder.newLine();
			coder.packText("args['folder']=");this.genAttrStatement(seg.getAttr("folder"));coder.packText(";");coder.newLine();
			coder.packText("args['repo']=");this.genAttrStatement(seg.getAttr("repo"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AutoDeploy/ai/PrjSetupBySteps.js",args,false);`);coder.newLine();
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
/*#{1IJ2K5IBR0PostDoc*/
/*}#1IJ2K5IBR0PostDoc*/


export default PrjSetupBySteps;
export{PrjSetupBySteps,ChatAPI};
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
//						"superClass": "",
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
//						"exportClass": "false"
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
//				"prjPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IVPLPH220",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"folder": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J03OGT5U0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"repo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J08OBG9C0",
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
//						"x": "125",
//						"y": "355",
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
//						"x": "370",
//						"y": "340",
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
//						"argument": "#input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ2L5O0Q2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2K9A670"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"mcp": {
//							"valText": "false"
//						},
//						"agentNode": ""
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ2K9A670",
//					"attrs": {
//						"id": "InitPrj",
//						"viewName": "",
//						"label": "",
//						"x": "570",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2L5O0T4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ2L5O0Q3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J03OF97J0"
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
//					"jaxId": "1IJ2KGOHG0",
//					"attrs": {
//						"id": "LoadSteps",
//						"viewName": "",
//						"label": "",
//						"x": "790",
//						"y": "340",
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
//						"result": "#input"
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
//						"x": "985",
//						"y": "340",
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
//							},
//							"linkedSeg": "1IJ2SSKUN0"
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
//					"def": "code",
//					"jaxId": "1IJ2SSKUN0",
//					"attrs": {
//						"id": "LoadGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1190",
//						"y": "515",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2STPJ10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2STPJ11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ2STPIS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJL3NK8N0"
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
//					"def": "loopArray",
//					"jaxId": "1IJ2KJ0UK0",
//					"attrs": {
//						"id": "LoopSteps",
//						"viewName": "",
//						"label": "",
//						"x": "1190",
//						"y": "80",
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
//							"linkedSeg": "1J3IH61PT0"
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
//						"x": "1655",
//						"y": "-60",
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
//									"linkedSeg": "1IUIOCI2D0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ2KKLVA0",
//									"attrs": {
//										"id": "brew",
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
//										"condition": "#input.action.toLowerCase()===\"brew\""
//									},
//									"linkedSeg": "1IJ2KN5JJ0"
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
//										"condition": "#input.action===\"hf-model\""
//									},
//									"linkedSeg": "1IJ44IVQS0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ2KKR2P0",
//									"attrs": {
//										"id": "conda",
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
//										"condition": "#input.action.toLowerCase()===\"conda\""
//									},
//									"linkedSeg": "1IJ2KNFK40"
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
//					"def": "aiBot",
//					"jaxId": "1IJ2KN5JJ0",
//					"attrs": {
//						"id": "RunBrew",
//						"viewName": "",
//						"label": "",
//						"x": "1905",
//						"y": "-140",
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
//						"argument": "#{\"action\":\"install\",\"pkgName\":input.install}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ2L5O0R5",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"mcp": {
//							"valText": "false"
//						},
//						"agentNode": ""
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IJ2KNFK40",
//					"attrs": {
//						"id": "RunConda",
//						"viewName": "",
//						"label": "",
//						"x": "1905",
//						"y": "-5",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ2L5O0T24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T25",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AgentBuilder/PrjCheckCondaEnv.js",
//						"argument": "#{\"refName\":input.conda||input.name,\"pyversion\":input.pythonVersion,\"installReq\":input.installReq||input.installPkg||input.installDep}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ2L5O0R6",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2KQHJP0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"mcp": {
//							"valText": "false"
//						},
//						"agentNode": ""
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
//						"x": "1905",
//						"y": "65",
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
//						},
//						"mcp": {
//							"valText": "false"
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
//						"x": "2150",
//						"y": "25",
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
//					"def": "code",
//					"jaxId": "1IJEP433U0",
//					"attrs": {
//						"id": "SaveConda",
//						"viewName": "",
//						"label": "",
//						"x": "2365",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJEP5CIL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJEP5CIL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJEP51F20",
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
//					"jaxId": "1IJ2L1V3T0",
//					"attrs": {
//						"id": "ExposeAgent",
//						"viewName": "",
//						"label": "",
//						"x": "2585",
//						"y": "340",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ2L5O0T42",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T43",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ2L5O0S0",
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
//					"jaxId": "1IJ2L4VCN0",
//					"attrs": {
//						"id": "ShowError",
//						"viewName": "",
//						"label": "",
//						"x": "370",
//						"y": "530",
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
//						"y": "530",
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
//						"y": "420",
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
//						"x": "395",
//						"y": "420",
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
//						"y": "530",
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
//						"result": "#input"
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
//						"x": "1420",
//						"y": "-60",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
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
//						"channel": "Process",
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
//						"x": "1905",
//						"y": "-75",
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
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"mcp": {
//							"valText": "false"
//						},
//						"agentNode": ""
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJI789IM0",
//					"attrs": {
//						"id": "AddNote",
//						"viewName": "",
//						"label": "",
//						"x": "2165",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJI797F40",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJI797F41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJI7915T0",
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
//					"jaxId": "1IJL3NK8N0",
//					"attrs": {
//						"id": "ShowGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1430",
//						"y": "515",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJL3VU374",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJL3VU375",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#`### 找到安装指南：\\n----\\n${setupGuide}`",
//						"outlet": {
//							"jaxId": "1IJL3VU321",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILI9VIEO0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1ILI9VIEO0",
//					"attrs": {
//						"id": "GenGuideJs",
//						"viewName": "",
//						"label": "",
//						"x": "1670",
//						"y": "515",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILIA7HN10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILIA7HN11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenAI",
//						"mode": "gpt-4.1",
//						"system": "#`You are using a terminal on a MacOS/Linux or Windows device to help setup a project. The current path is a downloaded github project folder, so you don't need to git clone the project.\n\nThe detailed environment is:\n${JSON.stringify(globalContext.env,null,\"\\t\")}.\n\nYou are able to execute commands in the terminal based on the given task.\nYou can only interact with the terminal (no GUI access).\n\nYour task is to provide **all subsequent actions** at once to complete the given task.\nYou should carefully consider the task and provide a list of actions in the correct order.\n\n## Core Principles\n1. **Efficiency First**: Always look for the simplest, most efficient deployment method\n2. **Resource Awareness**: Consider memory, disk space, and processing requirements vs. available resources\n3. **Alternative Analysis**: Check for easier alternatives (pip packages, pre-built tools, Docker images) before complex setups\n4. **Platform Optimization**: Leverage platform-specific advantages and native optimizations\n5. **Comprehensive Testing**: Ensure the project works end-to-end after setup\n\n## Available Actions\n- bash: Execute a series of bash commands.\n- brew: Install a package using Homebrew.\n- conda: Only for Set up or activate a conda environment, if use conda install, please choose bash action.\n- hf-model: Download a model from Hugging Face.\n\nBased on the task, please determine all the actions required to complete the task, including the commands, parameters, and additional details for each action.\n\n## Output Format\n\n{\n\"Reasoning\": \"Comprehensive analysis including: (1) Project requirements and complexity, (2) Available alternatives considered (pip packages, Docker, simpler tools), (3) Resource requirements vs. environment capacity (memory, disk, GPU), (4) Platform-specific considerations, (5) Chosen approach rationale with estimated setup time and resource usage, (6) Step-by-step plan with validation strategy\",\n\"Actions\": [\n{\n\"action\": \"action_type\", // One of: \"bash\", \"brew\", \"conda\", \"hf-model\"\n\"tip\": \"Clear description including: what this accomplishes\",\n\"commands\": [str], // Array of commands to execute (only for \"bash\" action)\n\"install\": str, // Package to install (only for \"brew\" action)\n\"conda\": str, // Conda environment name (only for \"conda\" action)\n\"pythonVersion\": str, // Python version for conda environment (only for \"conda\" action)\n\"model\": str, // Model to download (only for \"hf-model\" action)\n\"localPath\": str // Local path to save the model (only for \"hf-model\" action)\n}\n// Additional actions including validation and usage examples...\n]\n}\n\n## Enhanced Examples\n\n### Example 1: Traditional Complex Setup with Full Validation\n{\n\"Reasoning\": \"Setting up FishSpeech project requires full environment - no simpler alternatives available for complete functionality. Analyzed resources: needs ~8GB RAM, ~5GB disk, 10-15 minute setup. Current environment has sufficient resources. Plan: install system dependencies → create conda environment → install Python packages → download model → validate functionality → provide usage guidance.\",\n\"Actions\": [\n{\n\"action\": \"conda\",\n\"tip\": \"Create isolated Python 3.10 environment for FishSpeech.\",\n\"conda\": \"fish-speech\",\n\"pythonVersion\": \"3.10\"\n},\n{\n\"action\": \"brew\",\n\"tip\": \"Install FFmpeg for audio processing.\",\n\"install\": \"ffmpeg\"\n},\n{\n\"action\": \"brew\",\n\"tip\": \"Install PortAudio for audio I/O.\",\n\"install\": \"portaudio\"\n},\n{\n\"action\": \"bash\",\n\"tip\": \"Install PyTorch and core dependencies.\",\n\"commands\": [\n\"pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1\",\n\"pip install websockets huggingface-hub openai nest_asyncio\",\n\"pip install -e .\"\n]\n},\n{\n\"action\": \"hf-model\",\n\"tip\": \"Download pre-trained FishSpeech model (~2GB).,\n\"model\": \"fishaudio/fish-speech-1.5\",\n\"localPath\": \"checkpoints/fish-speech-1.5\"\n},\n{\n\"action\": \"bash\",\n\"tip\": \"Validate installation by testing import.\",\n\"commands\": [\"python -c \\\"import fish_speech; print('Import successful')\\\"\"]\n},\n{\n\"action\": \"bash\",\n\"tip\": \"Display usage examples and next steps. Shows how to run inference and training commands\",\n\"commands\": [\n\"echo 'Setup complete! Usage examples:'\",\n\"echo ' python inference.py --text \\\"Hello world\\\"'\",\n\"echo ' python train.py --config configs/base.yaml'\",\n\"echo 'Check README.md for detailed usage instructions'\"\n]\n}\n]\n}\n\n### Example 2: Resource-Constrained Smart Setup\n{\n\"Reasoning\": \"Setting up Stable Diffusion project on device with limited resources (27GB free disk). Analyzed options: (1) Full setup needs 20GB+, (2) Lightweight alternatives available. Choosing CPU-optimized approach with smaller models. Estimated: 5GB disk, 4GB RAM, 15 minutes setup. Plan: create environment → install optimized dependencies → download smaller model → validate → provide resource-conscious usage tips.\",\n\"Actions\": [\n{\n\"action\": \"conda\",\n\"tip\": \"Create Python 3.9 environment for compatibility.\",\n\"conda\": \"stable-diffusion-lite\",\n\"pythonVersion\": \"3.9\"\n},\n{\n\"action\": \"bash\",\n\"tip\": \"Install CPU-optimized PyTorch and essential packages.\",\n\"commands\": [\n\"pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu\",\n\"pip install diffusers transformers accelerate\",\n\"pip install pillow requests\"\n]\n},\n{\n\"action\": \"hf-model\",\n\"tip\": \"Download compact Stable Diffusion model (~2GB vs 8GB full version).\",\n\"model\": \"runwayml/stable-diffusion-v1-5\",\n\"localPath\": \"models/stable-diffusion-v1-5\"\n},\n{\n\"action\": \"bash\",\n\"tip\": \"Test basic functionality with CPU inference.\",\n\"commands\": [\n\"python -c \\\"from diffusers import StableDiffusionPipeline; print('CPU setup successful')\\\"\",\n\"echo 'Note: Using CPU inference - generation will be slower but uses less resources'\"\n]\n},\n{\n\"action\": \"bash\",\n\"tip\": \"Provide resource-conscious usage examples and optimization tips for the constrained environment\",\n\"commands\": [\n\"echo 'Resource-optimized setup complete!'\",\n\"echo 'Usage tips for limited resources:'\",\n\"echo ' - Use smaller image sizes (512x512 or less)'\",\n\"echo ' - Reduce inference steps (10-20 instead of 50)'\",\n\"echo ' - Use low_cpu_mem_usage=True in pipeline loading'\",\n\"echo 'Example: pipe = StableDiffusionPipeline.from_pretrained(model_path, low_cpu_mem_usage=True)'\"\n]\n}\n]\n}\n\n## Critical Guidelines\n\n### ⚠️ **Mandatory Requirements**\n1. **Always analyze alternatives** in Reasoning before choosing approach\n2. **Consider resource constraints** vs. environment capabilities\n3. **Include validation actions** to ensure functionality works\n4. **Provide usage examples** as final actions\n5. **Only use commands mentioned in project documentation**\n6. **Optimize for target platform** and available resources\n7. **Always create a conda environment first.**\n\n### 🚫 **Prohibited Actions**\n- Using commands not found in project documentation\n- Ignoring simpler alternatives when available\n- Skipping validation steps\n- Assuming unlimited resources\n- Creating unnecessarily complex setups\n\n### 📋 **Quality Checklist for Reasoning**\n- [ ] Checked for simpler installation alternatives (pip packages, Docker, etc.)\n- [ ] Analyzed resource requirements vs. available resources (memory, disk, GPU)\n- [ ] Considered platform-specific optimizations (Apple Silicon, etc.)\n- [ ] Estimated setup time and resource usage\n- [ ] Planned validation strategy\n\n### Important Notes:\n1. Provide all actions at once in the correct order with JSON format\n2. Ensure commands are valid for the target operating system (MacOS/Linux or Windows)\n3. Include all necessary parameters for each action\n4. Include validation actions to test the project works correctly\n5. Include usage example actions as final steps\n6. If downloading from HuggingFace, must use hf-model tool\n7. Only use bash/brew commands mentioned in the input documentation\n8. **Always prioritize efficiency and resource optimization in your analysis**\n9. **In the tip field, include expected output and fallback options**\n10. If test with command that is impossible to terminate automatically, such as start a web service or api service, you need to set a timeout with 2 minute.\n11. Do not give commands list that requires multiple lines of input in the terminal.\n12. If you need to use pdf/png/... to test the function, you can use wget to download a simple example, for example, https://ontheline.trincoll.edu/images/bookdown/sample-local-pdf.pdf\n` + (($ln===\"CN\")?(\"用中文输出。\"):(\"Output in English.\"))",
//						"temperature": "0.7",
//						"maxToken": "32768",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#globalContext.guide",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1ILIA093U0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILIBLIQU0"
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
//						"process": {
//							"type": "object",
//							"def": "ProcessMsg",
//							"jaxId": "1J1HOPK1D0",
//							"attrs": {
//								"text": "Plan the deployment process.",
//								"role": "Assistant",
//								"roleText": "",
//								"codes": "false"
//							}
//						}
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1ILIBLIQU0",
//					"attrs": {
//						"id": "Export",
//						"viewName": "",
//						"label": "",
//						"x": "1920",
//						"y": "515",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1ILIDJ3NP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1ILIDJ3NP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1ILIBMA7E0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILIIHJ2K0"
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
//					"jaxId": "1ILIIHJ2K0",
//					"attrs": {
//						"id": "goto",
//						"viewName": "",
//						"label": "",
//						"x": "2120",
//						"y": "515",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "LoadSteps",
//						"outlet": {
//							"jaxId": "1ILIII45L0",
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
//					"jaxId": "1IUIOCI2D0",
//					"attrs": {
//						"id": "RunCommand",
//						"viewName": "",
//						"label": "",
//						"x": "1905",
//						"y": "-210",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IUIOD8GH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IUIOD8GH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AutoDeploy/ToolRunCommand.js",
//						"argument": "{\"command\":\"#input.commands\", \"repo\":\"#repo\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IUIOD8G80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3IH1MMH0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"agentNode": ""
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IVJ2JPN90",
//					"attrs": {
//						"id": "Summary",
//						"viewName": "",
//						"label": "",
//						"x": "1685",
//						"y": "275",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVJ2OCII0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVJ2OCII1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "Claude",
//						"mode": "claude-3-7-sonnet-latest",
//						"system": "#`请根据部署项目流程和其中部分运行命令存在的报错和解决方法，总结一份全面的部署指南。逐条列出每一步的运行命令，并指出如果遇到某个报错，如何解决，以markdown格式呈现。` + (($ln===\"CN\")?(\"用中文输出。\"):(\"Output in English.\"))",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#`部署流程：${deploy_guide}\\n报错及解决方案：${deploy_issues}`",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IVJ2OCI50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVJ2POB40"
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
//						"responseFormat": "text",
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IVJ2POB40",
//					"attrs": {
//						"id": "OutputGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1920",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVJ2Q8RE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVJ2Q8RE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IVJ2Q8R40",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJI789IM0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IVPD3IRS0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "-75",
//						"y": "355",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1IVPD4MA00",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2L44GS0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1J03OF97J0",
//					"attrs": {
//						"id": "Path",
//						"viewName": "",
//						"label": "",
//						"x": "830",
//						"y": "405",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J03OGT5U1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J03OGT5U2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#`cd \"${decodeURIComponent(pathLib.join(prjPath,\"projects\",folder))}\"`",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J03OGT5L0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2SSKUN0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J3IH1MMH0",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "2170",
//						"y": "-210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3IH2C6C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3IH2C6C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J3IH2C671",
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
//									"jaxId": "1J3IH2C670",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J3IH2C6C2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J3IH2C6C3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input===\"break\""
//									},
//									"linkedSeg": "1J3IH3LP60"
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
//					"jaxId": "1J3IH3LP60",
//					"attrs": {
//						"id": "Fail",
//						"viewName": "",
//						"label": "",
//						"x": "2380",
//						"y": "-225",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3IH3OIE0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3IH3OIE1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J3IH3OI90",
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
//					"jaxId": "1J3IH61PT0",
//					"attrs": {
//						"id": "CheckStatus",
//						"viewName": "",
//						"label": "",
//						"x": "1420",
//						"y": "260",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3IH71TP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3IH71TP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J3IH71TH1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IVJ2JPN90"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J3IH71TH0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J3IH71TP2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J3IH71TP3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#status===\"no\""
//									},
//									"linkedSeg": "1J3IH77PV0"
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
//					"jaxId": "1J3IH77PV0",
//					"attrs": {
//						"id": "OutputFail",
//						"viewName": "",
//						"label": "",
//						"x": "1715",
//						"y": "175",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3IH7EI70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3IH7EI71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Bug fix failed, deployment aborted",
//							"localize": {
//								"EN": "Bug fix failed, deployment aborted",
//								"CN": "Bug修复失败，部署终止"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J3IH7EHT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "hudtxt.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"builder_new\",\"chatEntry\":false,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
//	}
//}