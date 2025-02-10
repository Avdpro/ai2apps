//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IJ2K5IBR0MoreImports*/
import fsp from 'fs/promises';
/*}#1IJ2K5IBR0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"prjPath":{
			"name":"prjPath","type":"string",
			"defaultValue":"",
			"desc":"要安装配置的工程的路径",
		}
	},
	/*#{1IJ2K5IBR0ArgsView*/
	/*}#1IJ2K5IBR0ArgsView*/
};

/*#{1IJ2K5IBR0StartDoc*/
/*}#1IJ2K5IBR0StartDoc*/
//----------------------------------------------------------------------------
let PrjSetupBySteps=async function(session){
	let prjPath;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let Start,InitEnv,InitPrj,LoadSteps,HasSteps,LoadGuide,LoopSteps,SwitchAction,RunBash,RunBrew,RunConda,RunTaskBot,CheckStepReuslt,TipFinish,AskActive,SaveConda,InstallAgent,ShowError,AskRetry,AbortStep,SetupByGuide,CheckGuide,TipNoGuide,TipStep,HfDownLoad,EndGuideSetup,AddNote,LoadRagGudie,CheckRagGude,CfmGuide,ShowGude,AbortGuide;
	let env=null;
	let project=null;
	let steps=null;
	let setupGuide="";
	let ragAddress=globalContext.rag?.solution||"http://localhost:222/solution/";
	
	/*#{1IJ2K5IBR0LocalVals*/
	/*}#1IJ2K5IBR0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			prjPath=input.prjPath;
		}else{
			prjPath=undefined;
		}
		/*#{1IJ2K5IBR0ParseArgs*/
		/*}#1IJ2K5IBR0ParseArgs*/
	}
	
	/*#{1IJ2K5IBR0PreContext*/
	/*}#1IJ2K5IBR0PreContext*/
	context={};
	/*#{1IJ2K5IBR0PostContext*/
	/*}#1IJ2K5IBR0PostContext*/
	let agent,segs={};
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
		let sourcePath=pathLib.join(basePath,"./SysInitWorkEnv.js");
		let arg=input;
		/*#{1IJ2KABA10Input*/
		/*}#1IJ2KABA10Input*/
		result= await session.pipeChat(sourcePath,arg,false);
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
		prjURL=prjJSON.github||prjJSON.gitURL;
		if(!prjURL.startsWith("https://")){
			prjURL="https://"+prjURL;
		}
		if(prjURL.endsWith(".git")){
			gitURL=prjURL;
			prjURL=prjURL.slice(0,-4);
		}else{
			if(prjURL.endsWith("/")){
				prjURL=prjURL.substring(0,prjURL.length-1);
			}
			gitURL=prjURL+".git";
		}
		let parts = prjURL.split('/');
		prjName=parts[parts.length - 1];
		owner=parts[parts.length - 2];
		branch="main"
		rawURL="https://raw.githubusercontent.com/"+prjURL.substring("https://github.com/".length)+"/refs/heads/"+branch;
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
		return {seg:LoadSteps,result:(result),preSeg:"1IJ2K9A670",outlet:"1IJ2L5O0Q3"};
	};
	InitPrj.jaxId="1IJ2K9A670"
	InitPrj.url="InitPrj@"+agentURL
	
	segs["LoadSteps"]=LoadSteps=async function(input){//:1IJ2KGOHG0
		let result=input
		/*#{1IJ2KGOHG0Code*/
		try{
			let modual=await import(pathLib.join(prjPath,"setup_agent.js"));
			if(modual){
				try{
					steps=await modual.default(env,project);
				}catch(err){
					console.log("Read setup steps error:");
					console.error(err);
					steps=null;
				}
			}
		}catch(err){
			steps=null;
		}
		/*}#1IJ2KGOHG0Code*/
		return {seg:LoadGuide,result:(result),preSeg:"1IJ2KGOHG0",outlet:"1IJ2L5O0Q4"};
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
			setupGuide=await fsp.readFile(pathLib.join(prjPath,"setup_guide.md"),"utf8");
		}catch(err){
			setupGuide=null;
		}
		/*}#1IJ2SSKUN0Code*/
		return {seg:CheckGuide,result:(result),preSeg:"1IJ2SSKUN0",outlet:"1IJ2STPIS0"};
	};
	LoadGuide.jaxId="1IJ2SSKUN0"
	LoadGuide.url="LoadGuide@"+agentURL
	
	segs["LoopSteps"]=LoopSteps=async function(input){//:1IJ2KJ0UK0
		let result=input;
		let list=steps;
		let i,n,item;
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			await session.runAISeg(agent,TipStep,item,"1IJ2KJ0UK0","1IJ2L5O0R0")
		}
		return {seg:SaveConda,result:(result),preSeg:"1IJ2KJ0UK0",outlet:"1IJ2L5O0R1"};
	};
	LoopSteps.jaxId="1IJ2KJ0UK0"
	LoopSteps.url="LoopSteps@"+agentURL
	
	segs["SwitchAction"]=SwitchAction=async function(input){//:1IJ2KK3SJ0
		let result=input;
		if(input.action.toLowerCase()==="bash"){
			let output=input;
			return {seg:RunBash,result:(output),preSeg:"1IJ2KK3SJ0",outlet:"1IJ2L5O0R2"};
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
	
	segs["RunBash"]=RunBash=async function(input){//:1IJ2KMQM70
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=input.commands||input.command;
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {result:result};
	};
	RunBash.jaxId="1IJ2KMQM70"
	RunBash.url="RunBash@"+agentURL
	
	segs["RunBrew"]=RunBrew=async function(input){//:1IJ2KN5JJ0
		let result;
		let sourcePath=pathLib.join(basePath,"./ToolBrew.js");
		let arg={"action":"install","pkgName":input.install};
		result= await session.pipeChat(sourcePath,arg,false);
		return {result:result};
	};
	RunBrew.jaxId="1IJ2KN5JJ0"
	RunBrew.url="RunBrew@"+agentURL
	
	segs["RunConda"]=RunConda=async function(input){//:1IJ2KNFK40
		let result;
		let sourcePath=pathLib.join(basePath,"./PrjCheckCondaEnv.js");
		let arg={"refName":input.conda||input.name,"pyversion":input.pythonVersion,"installReq":input.installReq||input.installPkg||input.installDep};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:CheckStepReuslt,result:(result),preSeg:"1IJ2KNFK40",outlet:"1IJ2L5O0R6"};
	};
	RunConda.jaxId="1IJ2KNFK40"
	RunConda.url="RunConda@"+agentURL
	
	segs["RunTaskBot"]=RunTaskBot=async function(input){//:1IJ2KOMUM0
		let result;
		let sourcePath=pathLib.join(basePath,"");
		let arg=input;
		result= await session.pipeChat(sourcePath,arg,false);
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
	
	segs["TipFinish"]=TipFinish=async function(input){//:1IJ2KTD7V0
		let result=input;
		let opts={};
		let role="assistant";
		let content="AgentNode 安装完毕，没有设置为公开。";
		session.addChatText(role,content,opts);
		return {result:result};
	};
	TipFinish.jaxId="1IJ2KTD7V0"
	TipFinish.url="TipFinish@"+agentURL
	
	segs["AskActive"]=AskActive=async function(input){//:1IJ2KUBNM0
		let prompt=((($ln==="CN")?("项目安装已完成，是否将本AgentNode设置为全局可见？"):("Project installation is complete, do you want to make this AgentNode public?")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("设置AI智能体公开可见"):("Set agent-node public")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("不共享AI智能体"):("Do not share AI agents")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:InstallAgent,result:(result),preSeg:"1IJ2KUBNM0",outlet:"1IJ2KUBN60"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:false,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:InstallAgent,result:(result),preSeg:"1IJ2KUBNM0",outlet:"1IJ2KUBN60"};
		}else if(item.code===1){
			return {seg:TipFinish,result:(result),preSeg:"1IJ2KUBNM0",outlet:"1IJ2KUBN61"};
		}
		return {result:result};
	};
	AskActive.jaxId="1IJ2KUBNM0"
	AskActive.url="AskActive@"+agentURL
	
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
		return {seg:AskActive,result:(result),preSeg:"1IJEP433U0",outlet:"1IJEP51F20"};
	};
	SaveConda.jaxId="1IJEP433U0"
	SaveConda.url="SaveConda@"+agentURL
	
	segs["InstallAgent"]=InstallAgent=async function(input){//:1IJ2L1V3T0
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
			//TODO: Expose agentNode:
			await fsp.writeFile(pathLib.join(dirPath,"agent.json"),JSON.stringify(agentJSON,null,"\t"));
		}catch(err){
			agentJSON={};
		}
		/*}#1IJ2L1V3T0Code*/
		return {result:result};
	};
	InstallAgent.jaxId="1IJ2L1V3T0"
	InstallAgent.url="InstallAgent@"+agentURL
	
	segs["ShowError"]=ShowError=async function(input){//:1IJ2L4VCN0
		let result=input;
		let opts={};
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
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:false,countdown:countdown,placeholder:placeholder});
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
	
	segs["SetupByGuide"]=SetupByGuide=async function(input){//:1IJ2OV1KT0
		let result;
		let sourcePath=pathLib.join(basePath,"./SysHandleTask.js");
		let arg={"task":null,"roleTask":"你是一个根据指南安装配置程序项目的AI智能体，请根据指南一步一步的安装/配置项目，分析并解决问题，直到项目安装完成。","prjDesc":"","guide":setupGuide,"tools":"guideSetup","handleIssue":true};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:EndGuideSetup,result:(result),preSeg:"1IJ2OV1KT0",outlet:"1IJ2PM4NQ2"};
	};
	SetupByGuide.jaxId="1IJ2OV1KT0"
	SetupByGuide.url="SetupByGuide@"+agentURL
	
	segs["CheckGuide"]=CheckGuide=async function(input){//:1IJ2ST21N0
		let result=input;
		if(setupGuide==="a"){
			/*#{1IJ2STPIS1Codes*/
			/*}#1IJ2STPIS1Codes*/
			return {seg:ShowGude,result:(input),preSeg:"1IJ2ST21N0",outlet:"1IJ2STPIS1"};
		}
		return {seg:LoadRagGudie,result:(result),preSeg:"1IJ2ST21N0",outlet:"1IJ2STPIS2"};
	};
	CheckGuide.jaxId="1IJ2ST21N0"
	CheckGuide.url="CheckGuide@"+agentURL
	
	segs["TipNoGuide"]=TipNoGuide=async function(input){//:1IJ2PL6OI0
		let result=input;
		let opts={};
		let role="assistant";
		let content="没有找到进一步安装配置本项目的指南。";
		/*#{1IJ2PL6OI0PreCodes*/
		/*}#1IJ2PL6OI0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IJ2PL6OI0PostCodes*/
		/*}#1IJ2PL6OI0PostCodes*/
		return {result:result};
	};
	TipNoGuide.jaxId="1IJ2PL6OI0"
	TipNoGuide.url="TipNoGuide@"+agentURL
	
	segs["TipStep"]=TipStep=async function(input){//:1IJ44HLQB0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input.tip;
		session.addChatText(role,content,opts);
		return {seg:SwitchAction,result:(result),preSeg:"1IJ44HLQB0",outlet:"1IJ44KI9F0"};
	};
	TipStep.jaxId="1IJ44HLQB0"
	TipStep.url="TipStep@"+agentURL
	
	segs["HfDownLoad"]=HfDownLoad=async function(input){//:1IJ44IVQS0
		let result;
		let sourcePath=pathLib.join(basePath,"./ToolHfModel.js");
		let arg={"model":input.model,"localPath":input.localPath||input.localDir};
		result= await session.pipeChat(sourcePath,arg,false);
		return {result:result};
	};
	HfDownLoad.jaxId="1IJ44IVQS0"
	HfDownLoad.url="HfDownLoad@"+agentURL
	
	segs["EndGuideSetup"]=EndGuideSetup=async function(input){//:1IJGRTTUL0
		let result=input
		/*#{1IJGRTTUL0Code*/
		if(project.conda){
			let agentJSON,dirPath;
			try{
				dirPath=prjPath;
				agentJSON=await fsp.readFile(pathLib.join(dirPath,"agent.json"),"utf8");
				agentJSON=JSON.parse(agentJSON);
				agentJSON.conda=project.conda;
				await fsp.writeFile(pathLib.join(dirPath,"agent.json"),JSON.stringify(agentJSON,null,"\t"));
			}catch(err){
				agentJSON={};
			}
		}
		/*}#1IJGRTTUL0Code*/
		return {result:result};
	};
	EndGuideSetup.jaxId="1IJGRTTUL0"
	EndGuideSetup.url="EndGuideSetup@"+agentURL
	
	segs["AddNote"]=AddNote=async function(input){//:1IJI789IM0
		let result=input
		/*#{1IJI789IM0Code*/
		let note;
		note={
			desc:`安装指南`,
			doc:setupGuide,
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
		/*}#1IJI789IM0Code*/
		return {seg:CfmGuide,result:(result),preSeg:"1IJI789IM0",outlet:"1IJI7915T0"};
	};
	AddNote.jaxId="1IJI789IM0"
	AddNote.url="AddNote@"+agentURL
	
	segs["LoadRagGudie"]=LoadRagGudie=async function(input){//:1IJL38S9B0
		let result;
		let sourcePath=pathLib.join(basePath,"./RagQuery.js");
		let arg={"address":ragAddress,"query":"","tags":""};
		/*#{1IJL38S9B0Input*/
		/*}#1IJL38S9B0Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IJL38S9B0Output*/
		if(result){
			setupGuide=result;
		}
		/*}#1IJL38S9B0Output*/
		return {seg:CheckRagGude,result:(result),preSeg:"1IJL38S9B0",outlet:"1IJL3EQAN0"};
	};
	LoadRagGudie.jaxId="1IJL38S9B0"
	LoadRagGudie.url="LoadRagGudie@"+agentURL
	
	segs["CheckRagGude"]=CheckRagGude=async function(input){//:1IJL3C2S10
		let result=input;
		if(!!setupGuide){
			return {seg:ShowGude,result:(input),preSeg:"1IJL3C2S10",outlet:"1IJL3EQAN1"};
		}
		return {seg:TipNoGuide,result:(result),preSeg:"1IJL3C2S10",outlet:"1IJL3EQAN2"};
	};
	CheckRagGude.jaxId="1IJL3C2S10"
	CheckRagGude.url="CheckRagGude@"+agentURL
	
	segs["CfmGuide"]=CfmGuide=async function(input){//:1IJL3N37R0
		let prompt=("是否按照该指南安装？")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"按照该指南安装",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"放弃安装",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:SetupByGuide,result:(result),preSeg:"1IJL3N37R0",outlet:"1IJL3N37A0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:false,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:SetupByGuide,result:(result),preSeg:"1IJL3N37R0",outlet:"1IJL3N37A0"};
		}else if(item.code===1){
			return {seg:AbortGuide,result:(result),preSeg:"1IJL3N37R0",outlet:"1IJL3N37A1"};
		}
		return {result:result};
	};
	CfmGuide.jaxId="1IJL3N37R0"
	CfmGuide.url="CfmGuide@"+agentURL
	
	segs["ShowGude"]=ShowGude=async function(input){//:1IJL3NK8N0
		let result=input;
		let opts={};
		let role="assistant";
		let content=`### 找到安装指南：\n----\n${setupGuide}`;
		session.addChatText(role,content,opts);
		return {seg:AddNote,result:(result),preSeg:"1IJL3NK8N0",outlet:"1IJL3VU321"};
	};
	ShowGude.jaxId="1IJL3NK8N0"
	ShowGude.url="ShowGude@"+agentURL
	
	segs["AbortGuide"]=AbortGuide=async function(input){//:1IJL3VDFC0
		let result=input
		/*#{1IJL3VDFC0Code*/
		result={result:"Abort",content:"用户放弃安装项目。"};
		/*}#1IJL3VDFC0Code*/
		return {result:result};
	};
	AbortGuide.jaxId="1IJL3VDFC0"
	AbortGuide.url="AbortGuide@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"PrjSetupBySteps",
		url:agentURL,
		autoStart:true,
		jaxId:"1IJ2K5IBR0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{prjPath}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IJ2K5IBR0PreEntry*/
			/*}#1IJ2K5IBR0PreEntry*/
			result={seg:Start,"input":input};
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
//#CodyExport<<<
/*#{1IJ2K5IBR0PostDoc*/
/*}#1IJ2K5IBR0PostDoc*/


export default PrjSetupBySteps;
export{PrjSetupBySteps};
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
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IJ2K5IBR3",
//			"attrs": {
//				"prjPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ2K953K0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要安装配置的工程的路径"
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
//						"source": "ai/SysInitWorkEnv.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ2L5O0Q2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2K9A670"
//						}
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
//							"linkedSeg": "1IJ2KGOHG0"
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
//						"x": "760",
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
//							"linkedSeg": "1IJGP4PCR0"
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
//						"x": "975",
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
//						"y": "465",
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
//							"linkedSeg": "1IJ2ST21N0"
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
//							"linkedSeg": "1IJEP433U0"
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
//									"linkedSeg": "1IJ2KMQM70"
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
//					"def": "Bash",
//					"jaxId": "1IJ2KMQM70",
//					"attrs": {
//						"id": "RunBash",
//						"viewName": "",
//						"label": "",
//						"x": "1905",
//						"y": "-210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
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
//							}
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
//						"source": "ai/ToolBrew.js",
//						"argument": "{\"action\":\"install\",\"pkgName\":\"#input.install\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ2L5O0R5",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
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
//						"codes": "false",
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
//						"source": "ai/PrjCheckCondaEnv.js",
//						"argument": "{\"refName\":\"#input.conda||input.name\",\"pyversion\":\"#input.pythonVersion\",\"installReq\":\"#input.installReq||input.installPkg||input.installDep\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ2L5O0R6",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2KQHJP0"
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
//					"def": "output",
//					"jaxId": "1IJ2KTD7V0",
//					"attrs": {
//						"id": "TipFinish",
//						"viewName": "",
//						"label": "",
//						"x": "1905",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJ2L5O0T36",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2L5O0T37",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "AgentNode 安装完毕，没有设置为公开。",
//						"outlet": {
//							"jaxId": "1IJ2L5O0R10",
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
//					"def": "askMenu",
//					"jaxId": "1IJ2KUBNM0",
//					"attrs": {
//						"id": "AskActive",
//						"viewName": "",
//						"label": "",
//						"x": "1655",
//						"y": "235",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"prompt": {
//							"type": "string",
//							"valText": "Project installation is complete, do you want to make this AgentNode public?",
//							"localize": {
//								"EN": "Project installation is complete, do you want to make this AgentNode public?",
//								"CN": "项目安装已完成，是否将本AgentNode设置为全局可见？"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJ2L5O0R11",
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
//									"jaxId": "1IJ2KUBN60",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Set agent-node public",
//											"localize": {
//												"EN": "Set agent-node public",
//												"CN": "设置AI智能体公开可见"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ2L5O0T38",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2L5O0T39",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ2L1V3T0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ2KUBN61",
//									"attrs": {
//										"id": "No",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Do not share AI agents",
//											"localize": {
//												"EN": "Do not share AI agents",
//												"CN": "不共享AI智能体"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ2L5O0T40",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2L5O0T41",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ2KTD7V0"
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
//					"jaxId": "1IJEP433U0",
//					"attrs": {
//						"id": "SaveConda",
//						"viewName": "",
//						"label": "",
//						"x": "1420",
//						"y": "235",
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
//							},
//							"linkedSeg": "1IJ2KUBNM0"
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
//						"id": "InstallAgent",
//						"viewName": "",
//						"label": "",
//						"x": "1905",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "working.svg",
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
//						"segMark": "working.svg",
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
//						"segMark": "working.svg",
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
//						"x": "390",
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
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IJ2OV1KT0",
//					"attrs": {
//						"id": "SetupByGuide",
//						"viewName": "",
//						"label": "",
//						"x": "2405",
//						"y": "370",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2PM4NU6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2PM4NU7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysHandleTask.js",
//						"argument": "{\"task\":\"#null\",\"roleTask\":\"你是一个根据指南安装配置程序项目的AI智能体，请根据指南一步一步的安装/配置项目，分析并解决问题，直到项目安装完成。\",\"prjDesc\":\"\",\"guide\":\"#setupGuide\",\"tools\":\"guideSetup\",\"handleIssue\":\"#true\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ2PM4NQ2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJGRTTUL0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJ2ST21N0",
//					"attrs": {
//						"id": "CheckGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1420",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ2STPJ12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2STPJ13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ2STPIS2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJL38S9B0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJ2STPIS1",
//									"attrs": {
//										"id": "Guide",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IJ2STPJ14",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ2STPJ15",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#setupGuide===\"a\""
//									},
//									"linkedSeg": "1IJL3NK8N0"
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
//					"jaxId": "1IJ2PL6OI0",
//					"attrs": {
//						"id": "TipNoGuide",
//						"viewName": "",
//						"label": "",
//						"x": "2150",
//						"y": "645",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJ2PM4NU8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ2PM4NU9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "没有找到进一步安装配置本项目的指南。",
//						"outlet": {
//							"jaxId": "1IJ2PM4NQ3",
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
//						"source": "ai/ToolHfModel.js",
//						"argument": "{\"model\":\"#input.model\",\"localPath\":\"#input.localPath||input.localDir\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJ44KI9F1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IJGP4PCR0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "975",
//						"y": "465",
//						"outlet": {
//							"jaxId": "1IJGP4V5J0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ2SSKUN0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJGRTTUL0",
//					"attrs": {
//						"id": "EndGuideSetup",
//						"viewName": "",
//						"label": "",
//						"x": "2665",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJGRUDE80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJGRUDE81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJGRUDE00",
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
//					"jaxId": "1IJI789IM0",
//					"attrs": {
//						"id": "AddNote",
//						"viewName": "",
//						"label": "",
//						"x": "1905",
//						"y": "400",
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
//							},
//							"linkedSeg": "1IJL3N37R0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IJL38S9B0",
//					"attrs": {
//						"id": "LoadRagGudie",
//						"viewName": "",
//						"label": "",
//						"x": "1680",
//						"y": "595",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJL3EQAT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJL3EQAT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/RagQuery.js",
//						"argument": "{\"address\":\"#ragAddress\",\"query\":\"\",\"tags\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJL3EQAN0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJL3C2S10"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJL3C2S10",
//					"attrs": {
//						"id": "CheckRagGude",
//						"viewName": "",
//						"label": "",
//						"x": "1905",
//						"y": "595",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJL3EQAT2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJL3EQAT3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJL3EQAN2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJ2PL6OI0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJL3EQAN1",
//									"attrs": {
//										"id": "Guide",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJL3EQAT4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJL3EQAT5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!setupGuide"
//									},
//									"linkedSeg": "1IJL3TU470"
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
//					"jaxId": "1IJL3N37R0",
//					"attrs": {
//						"id": "CfmGuide",
//						"viewName": "",
//						"label": "",
//						"x": "2145",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "是否按照该指南安装？",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJL3VU320",
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
//									"jaxId": "1IJL3N37A0",
//									"attrs": {
//										"id": "Setup",
//										"desc": "输出节点。",
//										"text": "按照该指南安装",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJL3VU370",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJL3VU371",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ2OV1KT0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJL3N37A1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "放弃安装",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJL3VU372",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJL3VU373",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJL3VDFC0"
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
//					"jaxId": "1IJL3NK8N0",
//					"attrs": {
//						"id": "ShowGude",
//						"viewName": "",
//						"label": "",
//						"x": "1680",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
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
//						"text": "#`### 找到安装指南：\\n----\\n${setupGuide}`",
//						"outlet": {
//							"jaxId": "1IJL3VU321",
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
//					"def": "connector",
//					"jaxId": "1IJL3TU470",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2080",
//						"y": "495",
//						"outlet": {
//							"jaxId": "1IJL3VU376",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJL3U1900"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IJL3U1900",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1710",
//						"y": "495",
//						"outlet": {
//							"jaxId": "1IJL3VU377",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJL3NK8N0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJL3VDFC0",
//					"attrs": {
//						"id": "AbortGuide",
//						"viewName": "",
//						"label": "",
//						"x": "2405",
//						"y": "480",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJL3VU378",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJL3VU379",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJL3VU322",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}