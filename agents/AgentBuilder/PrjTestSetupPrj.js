//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1HDBOSUN91MoreImports*/
import fsp from 'fs/promises';
/*}#1HDBOSUN91MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"dirPath":{
			"name":"dirPath","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"",
		}
	},
	/*#{1HDBOSUN91ArgsView*/
	/*}#1HDBOSUN91ArgsView*/
};

/*#{1HDBOSUN91StartDoc*/
/*}#1HDBOSUN91StartDoc*/
//----------------------------------------------------------------------------
let PrjTestSetupPrj=async function(session){
	let dirPath;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let StartTip,DelPrjDir,InitEnv,InitPrj,TipCheckSteps,TipCallSteps,CheckStepsFile,TipFindStepsFile,CheckSteps,TipCheckGudes,CheckGuides,TipCallGuides,CallSetup,Fin,IsBySteps,TipTryAgain,AskGuideNext,AskStepsNext,GenAgent,GenSteps,TipFinish,JumpFinish,FinNoGuide,FinStepError,TipNoSteps,JumpToGuides;
	let env=null;
	let project=null;
	let useSteps=false;
	let useGuides=false;
	
	/*#{1HDBOSUN91LocalVals*/
	/*}#1HDBOSUN91LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			dirPath=input.dirPath;
		}else{
			dirPath=undefined;
		}
		/*#{1HDBOSUN91ParseArgs*/
		/*}#1HDBOSUN91ParseArgs*/
	}
	
	/*#{1HDBOSUN91PreContext*/
	/*}#1HDBOSUN91PreContext*/
	context={};
	/*#{1HDBOSUN91PostContext*/
	/*}#1HDBOSUN91PostContext*/
	let $agent,agent,segs={};
	segs["StartTip"]=StartTip=async function(input){//:1IKSL2QSV0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="开始测试项目部署步骤，首先删除旧的项目目录";
		/*#{1IKSL2QSV0PreCodes*/
		/*}#1IKSL2QSV0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IKSL2QSV0PostCodes*/
		/*}#1IKSL2QSV0PostCodes*/
		return {seg:DelPrjDir,result:(result),preSeg:"1IKSL2QSV0",outlet:"1IKSL41380"};
	};
	StartTip.jaxId="1IKSL2QSV0"
	StartTip.url="StartTip@"+agentURL
	
	segs["DelPrjDir"]=DelPrjDir=async function(input){//:1IKREO31V0
		let result=input
		/*#{1IKREO31V0Code*/
		dirPath=dirPath||session.agentNode.path;
		if(dirPath[0]!=="/"){
			dirPath=pathLib.join(session.agentNode.hubPath,dirPath);
		}
		try {
			await fsp.rm(pathLib.join(dirPath,"prj"), { recursive: true, force: true });
		} catch (error) {
			//Do nothing here
		}
		/*}#1IKREO31V0Code*/
		return {seg:InitEnv,result:(result),preSeg:"1IKREO31V0",outlet:"1IKSERVH70"};
	};
	DelPrjDir.jaxId="1IKREO31V0"
	DelPrjDir.url="DelPrjDir@"+agentURL
	
	segs["InitEnv"]=InitEnv=async function(input){//:1IKT1O7920
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./SysInitWorkEnv.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1IKT1O7920Input*/
		/*}#1IKT1O7920Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1IKT1O7920Output*/
		env=globalContext.env;
		/*}#1IKT1O7920Output*/
		return {seg:InitPrj,result:(result),preSeg:"1IKT1O7920",outlet:"1IKT1O7932"};
	};
	InitEnv.jaxId="1IKT1O7920"
	InitEnv.url="InitEnv@"+agentURL
	
	segs["InitPrj"]=InitPrj=async function(input){//:1IKT1NPOJ0
		let result=input
		/*#{1IKT1NPOJ0Code*/
		let prjJSON,prjURL,gitURL,prjName,owner,rawURL,branch;
		try{
			prjJSON=await fsp.readFile(pathLib.join(dirPath,"project.json"),"utf8");
			prjJSON=JSON.parse(prjJSON);
		}catch(err){
			prjJSON={};
		}
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
		/*}#1IKT1NPOJ0Code*/
		return {seg:TipCheckSteps,result:(result),preSeg:"1IKT1NPOJ0",outlet:"1IKT1QFBB0"};
	};
	InitPrj.jaxId="1IKT1NPOJ0"
	InitPrj.url="InitPrj@"+agentURL
	
	segs["TipCheckSteps"]=TipCheckSteps=async function(input){//:1IKSL5QL40
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="prj目录已删除，检查是否存在安装步骤（setup_agent.js）或者安装指南（setup_guide.md）。";
		session.addChatText(role,content,opts);
		return {seg:CheckStepsFile,result:(result),preSeg:"1IKSL5QL40",outlet:"1IKSLDSFI0"};
	};
	TipCheckSteps.jaxId="1IKSL5QL40"
	TipCheckSteps.url="TipCheckSteps@"+agentURL
	
	segs["TipCallSteps"]=TipCallSteps=async function(input){//:1IKSL4LDB0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="获得了部署步骤，下面按照步骤尝试部署";
		session.addChatText(role,content,opts);
		return {seg:CallSetup,result:(result),preSeg:"1IKSL4LDB0",outlet:"1IKSL59CP0"};
	};
	TipCallSteps.jaxId="1IKSL4LDB0"
	TipCallSteps.url="TipCallSteps@"+agentURL
	
	segs["CheckStepsFile"]=CheckStepsFile=async function(input){//:1IKSLJH6C0
		let result=input;
		/*#{1IKSLJH6C0Start*/
		let stepFile=false;
		try {
			await fsp.access(pathLib.join(dirPath,"setup_agent.js"));
			stepFile=true;
		} catch {
			stepFile=false;
		}		
		/*}#1IKSLJH6C0Start*/
		if(stepFile){
			return {seg:TipFindStepsFile,result:(input),preSeg:"1IKSLJH6C0",outlet:"1IKSLQDTJ0"};
		}
		/*#{1IKSLJH6C0Post*/
		/*}#1IKSLJH6C0Post*/
		return {seg:TipCheckGudes,result:(result),preSeg:"1IKSLJH6C0",outlet:"1IKSLQDTJ1"};
	};
	CheckStepsFile.jaxId="1IKSLJH6C0"
	CheckStepsFile.url="CheckStepsFile@"+agentURL
	
	segs["TipFindStepsFile"]=TipFindStepsFile=async function(input){//:1IKSLKJM40
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="找到了setup_agent.js，尝试读取部署步骤。";
		session.addChatText(role,content,opts);
		return {seg:CheckSteps,result:(result),preSeg:"1IKSLKJM40",outlet:"1IKSLQDTJ2"};
	};
	TipFindStepsFile.jaxId="1IKSLKJM40"
	TipFindStepsFile.url="TipFindStepsFile@"+agentURL
	
	segs["CheckSteps"]=CheckSteps=async function(input){//:1IKSL6B7Q0
		let result=input;
		/*#{1IKSL6B7Q0Start*/
		let scriptPath=pathLib.join(dirPath,"setup_agent.js");
		let scriptError=false;
		let steps=null;
		try{
			let md=await import(scriptPath);
			steps=await md.default(env,project);
		}catch(err){
			scriptError=true;
		}
		/*}#1IKSL6B7Q0Start*/
		if(scriptError){
			return {seg:FinStepError,result:(input),preSeg:"1IKSL6B7Q0",outlet:"1IKSLDSFI1"};
		}
		if(!steps){
			return {seg:TipNoSteps,result:(input),preSeg:"1IKSL6B7Q0",outlet:"1IKSV6JHV0"};
		}
		/*#{1IKSL6B7Q0Post*/
		useSteps=true;
		useGuides=false;
		/*}#1IKSL6B7Q0Post*/
		return {seg:TipCallSteps,result:(result),preSeg:"1IKSL6B7Q0",outlet:"1IKSLDSFI2"};
	};
	CheckSteps.jaxId="1IKSL6B7Q0"
	CheckSteps.url="CheckSteps@"+agentURL
	
	segs["TipCheckGudes"]=TipCheckGudes=async function(input){//:1IKSLN9QR0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="没有找到\"setup_agent.js\"文件，检查是否有安装指南\"setup_guide.md\"文件";
		/*#{1IKSLN9QR0PreCodes*/
		useSteps=false;
		useGuides=true;
		/*}#1IKSLN9QR0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IKSLN9QR0PostCodes*/
		/*}#1IKSLN9QR0PostCodes*/
		return {seg:CheckGuides,result:(result),preSeg:"1IKSLN9QR0",outlet:"1IKSLQDTJ3"};
	};
	TipCheckGudes.jaxId="1IKSLN9QR0"
	TipCheckGudes.url="TipCheckGudes@"+agentURL
	
	segs["CheckGuides"]=CheckGuides=async function(input){//:1IKSLNVBL0
		let result=input;
		/*#{1IKSLNVBL0Start*/
		let guideFile=false;
		try {
			await fsp.access(pathLib.join(dirPath,"setup_guide.md"));
			guideFile=true;
		} catch {
			guideFile=false;
		}		
		/*}#1IKSLNVBL0Start*/
		if(guideFile){
			/*#{1IKSLQDTJ4Codes*/
			/*}#1IKSLQDTJ4Codes*/
			return {seg:TipCallGuides,result:(input),preSeg:"1IKSLNVBL0",outlet:"1IKSLQDTJ4"};
		}
		/*#{1IKSLNVBL0Post*/
		/*}#1IKSLNVBL0Post*/
		return {seg:FinNoGuide,result:(result),preSeg:"1IKSLNVBL0",outlet:"1IKSLQDTK0"};
	};
	CheckGuides.jaxId="1IKSLNVBL0"
	CheckGuides.url="CheckGuides@"+agentURL
	
	segs["TipCallGuides"]=TipCallGuides=async function(input){//:1IKSLP3PA0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="找到了部署指南（setup_guide.md），按照指南进行部署";
		session.addChatText(role,content,opts);
		return {seg:CallSetup,result:(result),preSeg:"1IKSLP3PA0",outlet:"1IKSLQDTK1"};
	};
	TipCallGuides.jaxId="1IKSLP3PA0"
	TipCallGuides.url="TipCallGuides@"+agentURL
	
	segs["CallSetup"]=CallSetup=async function(input){//:1IKRER38C0
		let result;
		let arg={"prjPath":dirPath};
		let agentNode=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"./PrjSetupBySteps.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {seg:Fin,result:(result),preSeg:"1IKRER38C0",outlet:"1IKSERVH71"};
	};
	CallSetup.jaxId="1IKRER38C0"
	CallSetup.url="CallSetup@"+agentURL
	
	segs["Fin"]=Fin=async function(input){//:1IKSM2DSS0
		let prompt=("部署执行完毕，请核对确认是否部署成功。")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"部署成功，项目可以执行",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"部署未成功，需要调整部署方案",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:IsBySteps,result:(result),preSeg:"1IKSM2DSS0",outlet:"1IKSM2DSA0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:IsBySteps,result:(result),preSeg:"1IKSM2DSS0",outlet:"1IKSM2DSA0"};
		}else if(item.code===1){
			return {seg:TipTryAgain,result:(result),preSeg:"1IKSM2DSS0",outlet:"1IKSM8JKU0"};
		}
		return {result:result};
	};
	Fin.jaxId="1IKSM2DSS0"
	Fin.url="Fin@"+agentURL
	
	segs["IsBySteps"]=IsBySteps=async function(input){//:1IKSMAKHJ0
		let result=input;
		if(useSteps){
			/*#{1IKSOLBBG0Codes*/
			/*}#1IKSOLBBG0Codes*/
			return {seg:AskStepsNext,result:(input),preSeg:"1IKSMAKHJ0",outlet:"1IKSOLBBG0"};
		}
		return {seg:AskGuideNext,result:(result),preSeg:"1IKSMAKHJ0",outlet:"1IKSOLBBG1"};
	};
	IsBySteps.jaxId="1IKSMAKHJ0"
	IsBySteps.url="IsBySteps@"+agentURL
	
	segs["TipTryAgain"]=TipTryAgain=async function(input){//:1IKSMC00M0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="有些项目部署可能非常困难，请分析问题，请调整部署方案后再次尝试。";
		session.addChatText(role,content,opts);
		return {result:result};
	};
	TipTryAgain.jaxId="1IKSMC00M0"
	TipTryAgain.url="TipTryAgain@"+agentURL
	
	segs["AskGuideNext"]=AskGuideNext=async function(input){//:1IKSMMSCT0
		let prompt=("请选择项目部署后的操作。")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"转化项目能力为智能体",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"根据指南生成部署脚本",code:1},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"完成，结束当前对话",code:2},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:GenAgent,result:(result),preSeg:"1IKSMMSCT0",outlet:"1IKSMMSCC1"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:GenAgent,result:(result),preSeg:"1IKSMMSCT0",outlet:"1IKSMMSCC1"};
		}else if(item.code===1){
			return {seg:GenSteps,result:(result),preSeg:"1IKSMMSCT0",outlet:"1IKSMMSCC0"};
		}else if(item.code===2){
			return {seg:JumpFinish,result:(result),preSeg:"1IKSMMSCT0",outlet:"1IKSOFDBG0"};
		}
		return {result:result};
	};
	AskGuideNext.jaxId="1IKSMMSCT0"
	AskGuideNext.url="AskGuideNext@"+agentURL
	
	segs["AskStepsNext"]=AskStepsNext=async function(input){//:1IKSMRNPN0
		let prompt=("请选择项目部署后的操作。")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"转化项目能力为智能体",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"完成，结束当前对话",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:GenAgent,result:(result),preSeg:"1IKSMRNPN0",outlet:"1IKSMRNP60"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:GenAgent,result:(result),preSeg:"1IKSMRNPN0",outlet:"1IKSMRNP60"};
		}else if(item.code===1){
			return {seg:TipFinish,result:(result),preSeg:"1IKSMRNPN0",outlet:"1IKSMRNP62"};
		}
		return {result:result};
	};
	AskStepsNext.jaxId="1IKSMRNPN0"
	AskStepsNext.url="AskStepsNext@"+agentURL
	
	segs["GenAgent"]=GenAgent=async function(input){//:1IKSOEKOJ0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	GenAgent.jaxId="1IKSOEKOJ0"
	GenAgent.url="GenAgent@"+agentURL
	
	segs["GenSteps"]=GenSteps=async function(input){//:1IKSOHALC0
		let result;
		let arg=input;
		let agentNode=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		return {result:result};
	};
	GenSteps.jaxId="1IKSOHALC0"
	GenSteps.url="GenSteps@"+agentURL
	
	segs["TipFinish"]=TipFinish=async function(input){//:1IKSOIOO80
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="会话结束。";
		session.addChatText(role,content,opts);
		return {result:result};
	};
	TipFinish.jaxId="1IKSOIOO80"
	TipFinish.url="TipFinish@"+agentURL
	
	segs["JumpFinish"]=JumpFinish=async function(input){//:1IKSOKGM20
		let result=input;
		return {seg:TipFinish,result:result,preSeg:"1IKSOIOO80",outlet:"1IKSOLBBH5"};
	
	};
	JumpFinish.jaxId="1IKSOIOO80"
	JumpFinish.url="JumpFinish@"+agentURL
	
	segs["FinNoGuide"]=FinNoGuide=async function(input){//:1IKSS84OM0
		let prompt=("没有找到安装指南。要部署项目，部署步骤脚本\"setup_agent.js\"和部署指南\"setup_guide.md\"两个文件至少有一个可用。请提供需要的文件后在试一次。")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"结束部署",code:0},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {result:result};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {result:result};
		}
		return {result:result};
	};
	FinNoGuide.jaxId="1IKSS84OM0"
	FinNoGuide.url="FinNoGuide@"+agentURL
	
	segs["FinStepError"]=FinStepError=async function(input){//:1IKSSABQO3
		let prompt=("没有找到安装指南。要部署项目，部署步骤脚本\"setup_agent.js\"和部署指南\"setup_guide.md\"两个文件至少有一个可用。请提供需要的文件后在试一次。")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"结束部署",code:0},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {result:result};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {result:result};
		}
		return {result:result};
	};
	FinStepError.jaxId="1IKSSABQO3"
	FinStepError.url="FinStepError@"+agentURL
	
	segs["TipNoSteps"]=TipNoSteps=async function(input){//:1IKSV9JF10
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="部署步骤脚本（setup_agent.js）没有返回针对当前环境的具体步骤。";
		session.addChatText(role,content,opts);
		return {seg:JumpToGuides,result:(result),preSeg:"1IKSV9JF10",outlet:"1IKSVD3KM0"};
	};
	TipNoSteps.jaxId="1IKSV9JF10"
	TipNoSteps.url="TipNoSteps@"+agentURL
	
	segs["JumpToGuides"]=JumpToGuides=async function(input){//:1IKSVA7S20
		let result=input;
		return {seg:TipCheckGudes,result:result,preSeg:"1IKSLN9QR0",outlet:"1IKSVD3KM1"};
	
	};
	JumpToGuides.jaxId="1IKSLN9QR0"
	JumpToGuides.url="JumpToGuides@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"PrjTestSetupPrj",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN91",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{dirPath}*/){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN91PreEntry*/
			/*}#1HDBOSUN91PreEntry*/
			result={seg:StartTip,"input":input};
			/*#{1HDBOSUN91PostEntry*/
			/*}#1HDBOSUN91PostEntry*/
			return result;
		},
		/*#{1HDBOSUN91MoreAgentAttrs*/
		/*}#1HDBOSUN91MoreAgentAttrs*/
	};
	/*#{1HDBOSUN91PostAgent*/
	/*}#1HDBOSUN91PostAgent*/
	return agent;
};
/*#{1HDBOSUN91ExCodes*/
/*}#1HDBOSUN91ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1HDBOSUN91PostDoc*/
/*}#1HDBOSUN91PostDoc*/


export default PrjTestSetupPrj;
export{PrjTestSetupPrj};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1HDBOSUN91",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1HDBOSUNA0",
//			"attrs": {
//				"PrjTestSetupPrj": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1HDBOSUNA4",
//					"attrs": {
//						"constructArgs": {
//							"jaxId": "1HDBOSUNB0",
//							"attrs": {}
//						},
//						"superClass": "",
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
//						"exportClass": "false"
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
//		"entry": "StartTip",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IKSERVH90",
//			"attrs": {
//				"dirPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IL2K6TC90",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {
//				"env": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"project": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"useSteps": {
//					"type": "bool",
//					"valText": "false"
//				},
//				"useGuides": {
//					"type": "bool",
//					"valText": "false"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1HDBOSUNA3",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1HDIJB7SK6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKSL2QSV0",
//					"attrs": {
//						"id": "StartTip",
//						"viewName": "",
//						"label": "",
//						"x": "65",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSL41390",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSL41391",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "开始测试项目部署步骤，首先删除旧的项目目录",
//						"outlet": {
//							"jaxId": "1IKSL41380",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKREO31V0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IKREO31V0",
//					"attrs": {
//						"id": "DelPrjDir",
//						"viewName": "",
//						"label": "",
//						"x": "270",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSERVH91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSERVH92",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKSERVH70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKT1O7920"
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
//					"jaxId": "1IKT1O7920",
//					"attrs": {
//						"id": "InitEnv",
//						"viewName": "",
//						"label": "",
//						"x": "495",
//						"y": "280",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKT1O7930",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKT1O7931",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysInitWorkEnv.js",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IKT1O7932",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKT1NPOJ0"
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
//					"jaxId": "1IKT1NPOJ0",
//					"attrs": {
//						"id": "InitPrj",
//						"viewName": "",
//						"label": "",
//						"x": "705",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKT1QFBF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKT1QFBF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKT1QFBB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKSL5QL40"
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
//					"jaxId": "1IKSL5QL40",
//					"attrs": {
//						"id": "TipCheckSteps",
//						"viewName": "",
//						"label": "",
//						"x": "915",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSLDSFL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSLDSFL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "prj目录已删除，检查是否存在安装步骤（setup_agent.js）或者安装指南（setup_guide.md）。",
//						"outlet": {
//							"jaxId": "1IKSLDSFI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKSLJH6C0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKSL4LDB0",
//					"attrs": {
//						"id": "TipCallSteps",
//						"viewName": "",
//						"label": "",
//						"x": "1940",
//						"y": "200",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSL59CQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSL59CQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "获得了部署步骤，下面按照步骤尝试部署",
//						"outlet": {
//							"jaxId": "1IKSL59CP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKRER38C0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IKSLJH6C0",
//					"attrs": {
//						"id": "CheckStepsFile",
//						"viewName": "",
//						"label": "",
//						"x": "1165",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSLQDTM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSLQDTM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKSLQDTJ1",
//							"attrs": {
//								"id": "Missing",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IKSLN9QR0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKSLQDTJ0",
//									"attrs": {
//										"id": "Exist",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSLQDTM2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSLQDTM3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#stepFile"
//									},
//									"linkedSeg": "1IKSLKJM40"
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
//					"jaxId": "1IKSLKJM40",
//					"attrs": {
//						"id": "TipFindStepsFile",
//						"viewName": "",
//						"label": "",
//						"x": "1425",
//						"y": "105",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSLQDTM4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSLQDTM5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "找到了setup_agent.js，尝试读取部署步骤。",
//						"outlet": {
//							"jaxId": "1IKSLQDTJ2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKSL6B7Q0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IKSL6B7Q0",
//					"attrs": {
//						"id": "CheckSteps",
//						"viewName": "",
//						"label": "",
//						"x": "1675",
//						"y": "105",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSLDSFL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSLDSFL3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKSLDSFI2",
//							"attrs": {
//								"id": "Loaded",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IKSL4LDB0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKSLDSFI1",
//									"attrs": {
//										"id": "Error",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSLDSFL4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSLDSFL5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#scriptError"
//									},
//									"linkedSeg": "1IKSSABQO3"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKSV6JHV0",
//									"attrs": {
//										"id": "NoSteps",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSV98TT0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSV98TT1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!steps"
//									},
//									"linkedSeg": "1IKSV9JF10"
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
//					"jaxId": "1IKSLN9QR0",
//					"attrs": {
//						"id": "TipCheckGudes",
//						"viewName": "",
//						"label": "",
//						"x": "1420",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSLQDTM6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSLQDTM7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "没有找到\"setup_agent.js\"文件，检查是否有安装指南\"setup_guide.md\"文件",
//						"outlet": {
//							"jaxId": "1IKSLQDTJ3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKSLNVBL0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IKSLNVBL0",
//					"attrs": {
//						"id": "CheckGuides",
//						"viewName": "",
//						"label": "",
//						"x": "1685",
//						"y": "380",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSLQDTM8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSLQDTM9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKSLQDTK0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IKSS84OM0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKSLQDTJ4",
//									"attrs": {
//										"id": "Guide",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IKSLQDTM10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSLQDTM11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#guideFile"
//									},
//									"linkedSeg": "1IKSLP3PA0"
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
//					"jaxId": "1IKSLP3PA0",
//					"attrs": {
//						"id": "TipCallGuides",
//						"viewName": "",
//						"label": "",
//						"x": "1940",
//						"y": "365",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSLQDTM12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSLQDTM13",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "找到了部署指南（setup_guide.md），按照指南进行部署",
//						"outlet": {
//							"jaxId": "1IKSLQDTK1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKRER38C0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IKRER38C0",
//					"attrs": {
//						"id": "CallSetup",
//						"viewName": "",
//						"label": "",
//						"x": "2200",
//						"y": "280",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSERVH93",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSERVH94",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/PrjSetupBySteps.js",
//						"argument": "{\"prjPath\":\"#dirPath\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IKSERVH71",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKSM2DSS0"
//						},
//						"outlets": {
//							"attrs": []
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IKSM2DSS0",
//					"attrs": {
//						"id": "Fin",
//						"viewName": "",
//						"label": "",
//						"x": "2420",
//						"y": "280",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"prompt": "部署执行完毕，请核对确认是否部署成功。",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IKSM72CD0",
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
//									"jaxId": "1IKSM2DSA0",
//									"attrs": {
//										"id": "Success",
//										"desc": "输出节点。",
//										"text": "部署成功，项目可以执行",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSM72CF0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSM72CF1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IKSMAKHJ0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IKSM8JKU0",
//									"attrs": {
//										"id": "Failed",
//										"desc": "输出节点。",
//										"text": "部署未成功，需要调整部署方案",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSOLBBL0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSOLBBL1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IKSMC00M0"
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
//					"def": "brunch",
//					"jaxId": "1IKSMAKHJ0",
//					"attrs": {
//						"id": "IsBySteps",
//						"viewName": "",
//						"label": "",
//						"x": "2630",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IKSOLBBL2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSOLBBL3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IKSOLBBG1",
//							"attrs": {
//								"id": "Guide",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IKSMMSCT0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IKSOLBBG0",
//									"attrs": {
//										"id": "Steps",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IKSOLBBL4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSOLBBL5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#useSteps"
//									},
//									"linkedSeg": "1IKSMRNPN0"
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
//					"jaxId": "1IKSMC00M0",
//					"attrs": {
//						"id": "TipTryAgain",
//						"viewName": "",
//						"label": "",
//						"x": "2635",
//						"y": "335",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IKSOLBBL6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSOLBBL7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "有些项目部署可能非常困难，请分析问题，请调整部署方案后再次尝试。",
//						"outlet": {
//							"jaxId": "1IKSOLBBG2",
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
//					"jaxId": "1IKSMMSCT0",
//					"attrs": {
//						"id": "AskGuideNext",
//						"viewName": "",
//						"label": "",
//						"x": "2855",
//						"y": "250",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "请选择项目部署后的操作。",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IKSOLBBH0",
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
//									"jaxId": "1IKSMMSCC1",
//									"attrs": {
//										"id": "GenAgent",
//										"desc": "输出节点。",
//										"text": "转化项目能力为智能体",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSOLBBL8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSOLBBL9",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1ILA3J8SA0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IKSMMSCC0",
//									"attrs": {
//										"id": "GenSteps",
//										"desc": "输出节点。",
//										"text": "根据指南生成部署脚本",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSOLBBL10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSOLBBL11",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IKSOHALC0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IKSOFDBG0",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"text": "完成，结束当前对话",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSOLBBL12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSOLBBL13",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IKSOKGM20"
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
//					"def": "askMenu",
//					"jaxId": "1IKSMRNPN0",
//					"attrs": {
//						"id": "AskStepsNext",
//						"viewName": "",
//						"label": "",
//						"x": "2855",
//						"y": "65",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "请选择项目部署后的操作。",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IKSOLBBH1",
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
//									"jaxId": "1IKSMRNP60",
//									"attrs": {
//										"id": "GenAgent",
//										"desc": "输出节点。",
//										"text": "转化项目能力为智能体",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSOLBBL16",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSOLBBL17",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1ILA3L3P70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IKSMRNP62",
//									"attrs": {
//										"id": "Finish",
//										"desc": "输出节点。",
//										"text": "完成，结束当前对话",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSOLBBL14",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSOLBBL15",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IKSOIOO80"
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
//					"jaxId": "1IKSOEKOJ0",
//					"attrs": {
//						"id": "GenAgent",
//						"viewName": "",
//						"label": "",
//						"x": "3460",
//						"y": "145",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IKSOLBBL18",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSOLBBL19",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IKSOLBBH2",
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
//					"jaxId": "1IKSOHALC0",
//					"attrs": {
//						"id": "GenSteps",
//						"viewName": "",
//						"label": "",
//						"x": "3135",
//						"y": "235",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IKSOLBBL20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSOLBBL21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "",
//						"argument": "#{}#>input",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IKSOLBBH3",
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
//					"def": "output",
//					"jaxId": "1IKSOIOO80",
//					"attrs": {
//						"id": "TipFinish",
//						"viewName": "",
//						"label": "",
//						"x": "3135",
//						"y": "65",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IKSOLBBL22",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSOLBBL23",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "会话结束。",
//						"outlet": {
//							"jaxId": "1IKSOLBBH4",
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
//					"def": "jumper",
//					"jaxId": "1IKSOKGM20",
//					"attrs": {
//						"id": "JumpFinish",
//						"viewName": "",
//						"label": "",
//						"x": "3135",
//						"y": "330",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "TipFinish",
//						"outlet": {
//							"jaxId": "1IKSOLBBH5",
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
//					"def": "askMenu",
//					"jaxId": "1IKSS84OM0",
//					"attrs": {
//						"id": "FinNoGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1940",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"prompt": "没有找到安装指南。要部署项目，部署步骤脚本\"setup_agent.js\"和部署指南\"setup_guide.md\"两个文件至少有一个可用。请提供需要的文件后在试一次。",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IKSSABEI0",
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
//									"jaxId": "1IKSS84O70",
//									"attrs": {
//										"id": "Fin",
//										"desc": "输出节点。",
//										"text": "结束部署",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSSABEI1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSSABEI2",
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
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IKSSABQO3",
//					"attrs": {
//						"id": "FinStepError",
//						"viewName": "",
//						"label": "",
//						"x": "1940",
//						"y": "-20",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"prompt": "没有找到安装指南。要部署项目，部署步骤脚本\"setup_agent.js\"和部署指南\"setup_guide.md\"两个文件至少有一个可用。请提供需要的文件后在试一次。",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IKSSABQP0",
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
//									"jaxId": "1IKSSABQP1",
//									"attrs": {
//										"id": "Fin",
//										"desc": "输出节点。",
//										"text": "结束部署",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IKSSABQP2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IKSSABQP3",
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
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IKSV9JF10",
//					"attrs": {
//						"id": "TipNoSteps",
//						"viewName": "",
//						"label": "",
//						"x": "1940",
//						"y": "105",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IKSVD3KQ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IKSVD3KQ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "部署步骤脚本（setup_agent.js）没有返回针对当前环境的具体步骤。",
//						"outlet": {
//							"jaxId": "1IKSVD3KM0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKSVA7S20"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IKSVA7S20",
//					"attrs": {
//						"id": "JumpToGuides",
//						"viewName": "",
//						"label": "",
//						"x": "2175",
//						"y": "105",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "TipCheckGudes",
//						"outlet": {
//							"jaxId": "1IKSVD3KM1",
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
//					"def": "connectorL",
//					"jaxId": "1ILA3IQGK0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3345",
//						"y": "-20",
//						"outlet": {
//							"jaxId": "1ILA3LHO60",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKSOEKOJ0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1ILA3J8SA0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3130",
//						"y": "145",
//						"outlet": {
//							"jaxId": "1ILA3LHO61",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IKSOEKOJ0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1ILA3L3P70",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3130",
//						"y": "-20",
//						"outlet": {
//							"jaxId": "1ILA3LHO62",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1ILA3IQGK0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}