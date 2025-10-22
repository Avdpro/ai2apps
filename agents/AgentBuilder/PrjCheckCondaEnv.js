//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IGAU4QB50MoreImports*/
import fsp from 'fs/promises';
import { promisify } from 'util';
import child_process from "child_process";
/*}#1IGAU4QB50MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"refName":{
			"name":"refName","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"推荐的Conda环境名字",
		},
		"pyversion":{
			"name":"pyversion","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"需要的Python版本号",
		},
		"installReq":{
			"name":"installReq","type":"bool",
			"required":false,
			"defaultValue":"",
			"desc":"是否安装依赖库，默认调用不必安装",
		}
	},
	/*#{1IGAU4QB50ArgsView*/
	/*}#1IGAU4QB50ArgsView*/
};

/*#{1IGAU4QB50StartDoc*/
async function getCondaEnvList() {
	let execPromise = promisify(child_process.exec);
	try {
		// 异步执行conda env list命令
		const { stdout, stderr } = await execPromise('conda env list');
		// 解析输出
		const lines = stdout.trim().split('\n').slice(2);
		const envNames = lines
		.map((line) => {
			let name=line.trim().split(/\s+/)[0]
			return name;
		})  // 提取环境名
		.filter(env => !!env);  // 过滤空行
		return envNames;
	} catch (error) {
		console.error('Error fetching conda environments:', error.message);
		return [];
	}
}
/*}#1IGAU4QB50StartDoc*/
//----------------------------------------------------------------------------
let PrjCheckCondaEnv=async function(session){
	let refName,pyversion,installReq;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,ReadReq,CheckReq,Result,GetReqType,CheckReqType,TryConda,TryPip,TipIssue,NoType,AskEnv,AskPythonVersion,NewEnv,End2,ChooseEnv,GenEnvName,ConfirmName,AskEnvName,CheckEnvName,SelectEnv,UseEnv,AskNewName,AskPrjEnv,NewSourceEnv;
	let env=globalContext.env;
	let project=globalContext.project;
	let dirPath=project.dirPath;
	let reqText="";
	let envName="";
	let condaEnvs="";
	let pythonVersion="3.9";
	let prjConda=undefined;
	
	/*#{1IGAU4QB50LocalVals*/
	/*}#1IGAU4QB50LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			refName=input.refName;
			pyversion=input.pyversion;
			installReq=input.installReq;
		}else{
			refName=undefined;
			pyversion=undefined;
			installReq=undefined;
		}
		/*#{1IGAU4QB50ParseArgs*/
		refName=refName||project.name;
		pyversion=pyversion||(($ln==="CN")?("无"):/*EN*/("NA"));
		installReq=installReq||false;
		/*}#1IGAU4QB50ParseArgs*/
	}
	
	/*#{1IGAU4QB50PreContext*/
	/*}#1IGAU4QB50PreContext*/
	context={};
	/*#{1IGAU4QB50PostContext*/
	async function addLog(log,notify=true){
		let logs=globalContext.agentBuilderLogs;
		if(!logs){
			logs=globalContext.agentBuilderLogs=[];
		}
		logs.push(log);
		if(notify){
			session.addChatText("log",JSON.stringify(log));
		}
	}
	/*}#1IGAU4QB50PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IJ40H5E60
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:ReadReq,result:(result),preSeg:"1IJ40H5E60",outlet:"1IJ40I84H0"};
	};
	FixArgs.jaxId="1IJ40H5E60"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["ReadReq"]=ReadReq=async function(input){//:1IGAU72M10
		let result=input
		/*#{1IGAU72M10Code*/
		if(installReq!==false){
			try{
				reqText=await fsp.readFile(pathLib.join(dirPath,"requirements.txt"),"utf8");
			}catch(err){
				reqText=null;
			}
			result=reqText;
		}
		/*}#1IGAU72M10Code*/
		return {seg:CheckReq,result:(result),preSeg:"1IGAU72M10",outlet:"1IGAUQE2K0"};
	};
	ReadReq.jaxId="1IGAU72M10"
	ReadReq.url="ReadReq@"+agentURL
	
	segs["CheckReq"]=CheckReq=async function(input){//:1IGAU7N830
		let result=input;
		if(!!input){
			return {seg:GetReqType,result:(input),preSeg:"1IGAU7N830",outlet:"1IGAUQE2K1"};
		}
		return {seg:Result,result:(result),preSeg:"1IGAU7N830",outlet:"1IGAUQE2K2"};
	};
	CheckReq.jaxId="1IGAU7N830"
	CheckReq.url="CheckReq@"+agentURL
	
	segs["Result"]=Result=async function(input){//:1IGAU8E150
		let result=input
		/*#{1IGAU8E150Code*/
		result={"missing":false,"conflict":false};
		/*}#1IGAU8E150Code*/
		return {seg:AskEnv,result:(result),preSeg:"1IGAU8E150",outlet:"1IGAUQE2K3"};
	};
	Result.jaxId="1IGAU8E150"
	Result.url="Result@"+agentURL
	
	segs["GetReqType"]=GetReqType=async function(input){//:1IGAU8VK60
		let result=input
		/*#{1IGAU8VK60Code*/
		const lines = reqText.split('\n');
		const pipRegex = /^[a-zA-Z0-9_.-]+==[0-9]+(\.[0-9]+)*$/;  // pip 格式 (numpy==1.21.0)
		const condaRegex = /^[a-zA-Z0-9_.-]+=[0-9]+(\.[0-9]+)*$/;  // conda 格式 (numpy=1.21.0)
		let pipCount = 0;
		let condaCount = 0;
		for (let line of lines) {
			line = line.trim();
			if (!line || line.startsWith('#')) continue;
			if (pipRegex.test(line)) {
				pipCount++;
			} else if (condaRegex.test(line)) {
				condaCount++;
			}
		}
		if (pipCount > condaCount){
			result='pip';
		}else if(condaCount > pipCount){
			result='conda';
		}else{
			result='unknown';
		}
		/*}#1IGAU8VK60Code*/
		return {seg:CheckReqType,result:(result),preSeg:"1IGAU8VK60",outlet:"1IGAUQE2K4"};
	};
	GetReqType.jaxId="1IGAU8VK60"
	GetReqType.url="GetReqType@"+agentURL
	
	segs["CheckReqType"]=CheckReqType=async function(input){//:1IGAU98UF0
		let result=input;
		if(input==="conda"){
			return {seg:TryConda,result:(input),preSeg:"1IGAU98UF0",outlet:"1IGAUQE2K5"};
		}
		if(input==="pip"){
			return {seg:TryPip,result:(input),preSeg:"1IGAU98UF0",outlet:"1IGB16AQS0"};
		}
		return {seg:NoType,result:(result),preSeg:"1IGAU98UF0",outlet:"1IGAUQE2K6"};
	};
	CheckReqType.jaxId="1IGAU98UF0"
	CheckReqType.url="CheckReqType@"+agentURL
	
	segs["TryConda"]=TryConda=async function(input){//:1IGB23HH50
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[
	`cd ${dirPath}`,
	"conda install --file ./requirements.txt --dry-run"
];
		args['options']={clear:true};
		/*#{1IGB23HH50PreCodes*/
		let missing,conflict;
		missing=false;
		conflict=false;
		/*}#1IGB23HH50PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IGB23HH50PostCodes*/
		addLog(`Conda dry-run result: ${result}`);
		if (result.includes('PackagesNotFoundError')) {
			missing=true;
		}else{
			missing=false;
			if(result.includes('Solving environment') && result.includes('done')) {
				conflict=false;
			} else {
				conflict=true;
			}
		}
		result={missing:missing,conflict:conflict};
		/*}#1IGB23HH50PostCodes*/
		return {seg:TipIssue,result:(result),preSeg:"1IGB23HH50",outlet:"1IGB281MF0"};
	};
	TryConda.jaxId="1IGB23HH50"
	TryConda.url="TryConda@"+agentURL
	
	segs["TryPip"]=TryPip=async function(input){//:1IGB2G48K0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[	`cd ${dirPath}`,	"pip install -r ./requirements.txt --dry-run"];
		args['options']={clear:true};
		/*#{1IGB2G48K0PreCodes*/
		let missing,conflict;
		/*}#1IGB2G48K0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IGB2G48K0PostCodes*/
		addLog(`pip dry-run result: ${result}`);
		if (result.includes('Requirement already satisfied')) {
			missing=false;
			conflict=false;
			if (result.includes('Collecting')) {
				missing=true;
			}
			if (result.includes('ERROR')) {
				conflict=true;
			}
			if (result.includes('Could not find a version')) {
				conflict=true;
			}
		}
		result={missing:missing,conflict:conflict};
		/*}#1IGB2G48K0PostCodes*/
		return {seg:TipIssue,result:(result),preSeg:"1IGB2G48K0",outlet:"1IGB2GDFT0"};
	};
	TryPip.jaxId="1IGB2G48K0"
	TryPip.url="TryPip@"+agentURL
	
	segs["TipIssue"]=TipIssue=async function(input){//:1IGB4O4R30
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=input;
		/*#{1IGB4O4R30PreCodes*/
		if(input.missing && input.conflict){
			content=`当前环境 "${env.conda.default}" 缺失一些必要的功能包且有部分功能包版本可能存在冲突，建议创建一个新的conda环境部署项目。`;
		}else if(input.missing){
			content=`当前环境 "${env.conda.default}" 缺失一些必要的功能包，且存在冲突，可以在当前环境中安装缺失的功能包并部署项目，或者创建一个新的conda环境部署。`;
		}else if(input.conflict){
			content=`当前环境 "${env.conda.default}" 的一些功能包和项目需求存在冲突，建议创建一个新的conda环境部署。`;
		}else{
			content=`当前环境 "${env.conda.default}" 满足项目部署需求，你也可以创建一个新的conda环境部署项目。`;
		}
		/*}#1IGB4O4R30PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IGB4O4R30PostCodes*/
		/*}#1IGB4O4R30PostCodes*/
		return {seg:AskEnv,result:(result),preSeg:"1IGB4O4R30",outlet:"1IGB5QNSJ0"};
	};
	TipIssue.jaxId="1IGB4O4R30"
	TipIssue.url="TipIssue@"+agentURL
	
	segs["NoType"]=NoType=async function(input){//:1IGB15TE40
		let result=input
		/*#{1IGB15TE40Code*/
		result={"missing":false,"conflict":false};
		/*}#1IGB15TE40Code*/
		return {seg:AskEnv,result:(result),preSeg:"1IGB15TE40",outlet:"1IGB16AQT0"};
	};
	NoType.jaxId="1IGB15TE40"
	NoType.url="NoType@"+agentURL
	
	segs["AskEnv"]=AskEnv=async function(input){//:1IGB4NMLD0
		let prompt=((($ln==="CN")?("选择项目的conda环境：创建新的，使用默认的，还是选择一个已有的环境："):("Select the conda environment for the project: create a new one, use the default one, or choose an existing environment:")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=("新环境")||"OK";
		let button2=("当前环境")||"Cancel";
		let button3=("选择环境")||"";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:GenEnvName,result:(result),preSeg:"1IGB4NMLD0",outlet:"1IGB4NMKQ0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:GenEnvName,result:(result),preSeg:"1IGB4NMLD0",outlet:"1IGB4NMKQ0"};
		}
		if(value===2){
			result=("")||result;
			return {seg:ChooseEnv,result:(result),preSeg:"1IGB4NMLD0",outlet:"1IGB57IE20"};
		}
		result=("")||result;
		return {seg:End2,result:(result),preSeg:"1IGB4NMLD0",outlet:"1IGB4NMKQ1"};
	
	};
	AskEnv.jaxId="1IGB4NMLD0"
	AskEnv.url="AskEnv@"+agentURL
	
	segs["AskPythonVersion"]=AskPythonVersion=async function(input){//:1IGG3ILB70
		let prompt=(pyversion?(($ln==="CN")?(`系统推荐的Python版本是: ${pyversion}，你也可以选择一个`):/*EN*/(`The recommended Python version is: ${pyversion}, you can also choose one`)):(($ln==="CN")?("请选择新环境的Python版本"):/*EN*/("Please select the Python version for the new environment")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"3.9",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"3.10",code:1},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"3.11",code:2},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"3.12",code:3},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"Default",code:4},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			/*#{1IGG3ILAR0Silent*/
			/*}#1IGG3ILAR0Silent*/
			return {seg:NewEnv,result:(result),preSeg:"1IGG3ILB70",outlet:"1IGG3ILAR0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			/*#{1IGG3ILAR0*/
			pythonVersion="3.9";
			/*}#1IGG3ILAR0*/
			return {seg:NewEnv,result:(result),preSeg:"1IGG3ILB70",outlet:"1IGG3ILAR0"};
		}else if(item.code===1){
			/*#{1IGG3ILAR1*/
			pythonVersion="3.10";
			/*}#1IGG3ILAR1*/
			return {seg:NewEnv,result:(result),preSeg:"1IGG3ILB70",outlet:"1IGG3ILAR1"};
		}else if(item.code===2){
			/*#{1IGG3ILAR2*/
			pythonVersion="3.11";
			/*}#1IGG3ILAR2*/
			return {seg:NewEnv,result:(result),preSeg:"1IGG3ILB70",outlet:"1IGG3ILAR2"};
		}else if(item.code===3){
			/*#{1J0B3D2LI0*/
			pythonVersion="3.12";
			/*}#1J0B3D2LI0*/
			return {seg:NewEnv,result:(result),preSeg:"1IGG3ILB70",outlet:"1J0B3D2LI0"};
		}else if(item.code===4){
			/*#{1J0B3ECO40*/
			pythonVersion=pyversion;
			/*}#1J0B3ECO40*/
			return {seg:NewEnv,result:(result),preSeg:"1IGG3ILB70",outlet:"1J0B3ECO40"};
		}
		return {result:result};
	};
	AskPythonVersion.jaxId="1IGG3ILB70"
	AskPythonVersion.url="AskPythonVersion@"+agentURL
	
	segs["NewEnv"]=NewEnv=async function(input){//:1IGB4V6D30
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[`conda create -n ${envName} python=${pythonVersion} -y`,`conda activate ${envName}`];
		args['options']={clear:true};
		/*#{1IGB4V6D30PreCodes*/
		/*}#1IGB4V6D30PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IGB4V6D30PostCodes*/
		project.conda=envName;
		result={result:"Finish",content:`创建了新的conda环境："${envName}"，作为项目的python环境。`};
		project.progress.push(`创建了新的conda环境："${envName}"，作为项目的python环境。`);
		/*}#1IGB4V6D30PostCodes*/
		return {result:result};
	};
	NewEnv.jaxId="1IGB4V6D30"
	NewEnv.url="NewEnv@"+agentURL
	
	segs["End2"]=End2=async function(input){//:1IGB50VR80
		let result=input
		/*#{1IGB50VR80Code*/
		envName=env.conda.default;
		project.conda=envName;
		result={result:"Finish",context:`选定conda环境："${envName}"，作为项目的python环境。`};
		project.progress.push(`选定conda环境："${envName}"，作为项目的python环境。`);
		/*}#1IGB50VR80Code*/
		return {result:result};
	};
	End2.jaxId="1IGB50VR80"
	End2.url="End2@"+agentURL
	
	segs["ChooseEnv"]=ChooseEnv=async function(input){//:1IGB5D9570
		let prompt=((($ln==="CN")?("请选择一个当前系统内的Conda环境"):("Please select a Conda environment within the current system")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let items=[
		];
		let result="";
		let item=null;
		
		/*#{1IGB5D9570PreCodes*/
		condaEnvs=await getCondaEnvList();
		items=condaEnvs.map((name)=>{return {icon:"/~/-tabos/shared/assets/hudbox.svg",text:name}});
		/*}#1IGB5D9570PreCodes*/
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1IGB5D9570PostCodes*/
		if(item && item.text){
			item=item.text;
		}
		/*}#1IGB5D9570PostCodes*/
		if(typeof(item)==='string'){
			result=item;
			return {seg:SelectEnv,result:(result),preSeg:"1IGB5D9570",outlet:"1IGB5QNSK0"};
		}
		/*#{1IGB5D9570FinCodes*/
		/*}#1IGB5D9570FinCodes*/
		return {seg:SelectEnv,result:(result),preSeg:"1IGB5D9570",outlet:"1IGB5QNSK0"};
	};
	ChooseEnv.jaxId="1IGB5D9570"
	ChooseEnv.url="ChooseEnv@"+agentURL
	
	segs["GenEnvName"]=GenEnvName=async function(input){//:1IGB5E9310
		let result=input
		/*#{1IGB5E9310Code*/
		//Generate a new conda name for project:
		let nameIdx;
		condaEnvs=await getCondaEnvList();
		envName=refName||project.name;
		nameIdx=1;
		while(condaEnvs.indexOf(envName)>=0){
			envName=project.name+"-"+(nameIdx++);
		}
		/*}#1IGB5E9310Code*/
		return {seg:ConfirmName,result:(result),preSeg:"1IGB5E9310",outlet:"1IGB5QNSK1"};
	};
	GenEnvName.jaxId="1IGB5E9310"
	GenEnvName.url="GenEnvName@"+agentURL
	
	segs["ConfirmName"]=ConfirmName=async function(input){//:1IGB5EMM00
		let prompt=((($ln==="CN")?(`确认使用新的环境名称：${envName}？`):(`Confirm using the new environment name: ${envName}?`)))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=("使用")||"OK";
		let button2=("指定环境名")||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:AskPythonVersion,result:(result),preSeg:"1IGB5EMM00",outlet:"1IGB5EMLH0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:AskPythonVersion,result:(result),preSeg:"1IGB5EMM00",outlet:"1IGB5EMLH0"};
		}
		result=("")||result;
		return {seg:AskEnvName,result:(result),preSeg:"1IGB5EMM00",outlet:"1IGB5EMLH1"};
	
	};
	ConfirmName.jaxId="1IGB5EMM00"
	ConfirmName.url="ConfirmName@"+agentURL
	
	segs["AskEnvName"]=AskEnvName=async function(input){//:1IGB5FMAJ0
		let tip=((($ln==="CN")?("请输入环境名"):("Please enter the environment name")));
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let allowEmpty=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
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
		return {seg:CheckEnvName,result:(result),preSeg:"1IGB5FMAJ0",outlet:"1IGB5QNSK2"};
	};
	AskEnvName.jaxId="1IGB5FMAJ0"
	AskEnvName.url="AskEnvName@"+agentURL
	
	segs["CheckEnvName"]=CheckEnvName=async function(input){//:1IGB5GSU20
		let result=input;
		/*#{1IGB5GSU20Start*/
		let condaEnvRegex = /^(?!\d+$)[a-zA-Z0-9._-]{1,30}$/;
		/*}#1IGB5GSU20Start*/
		if(condaEnvs.indexOf(input)<0 && condaEnvRegex.test(input)){
			/*#{1IGB5QNSK3Codes*/
			envName=input;
			/*}#1IGB5QNSK3Codes*/
			return {seg:AskPythonVersion,result:(input),preSeg:"1IGB5GSU20",outlet:"1IGB5QNSK3"};
		}
		/*#{1IGB5GSU20Post*/
		/*}#1IGB5GSU20Post*/
		return {seg:AskNewName,result:(result),preSeg:"1IGB5GSU20",outlet:"1IGB5QNSK4"};
	};
	CheckEnvName.jaxId="1IGB5GSU20"
	CheckEnvName.url="CheckEnvName@"+agentURL
	
	segs["SelectEnv"]=SelectEnv=async function(input){//:1IGB5Q4LI0
		let result=input
		/*#{1IGB5Q4LI0Code*/
		envName=input;
		project.conda=envName;
		result={finish:true};
		/*}#1IGB5Q4LI0Code*/
		return {seg:UseEnv,result:(result),preSeg:"1IGB5Q4LI0",outlet:"1IGB5QNSL1"};
	};
	SelectEnv.jaxId="1IGB5Q4LI0"
	SelectEnv.url="SelectEnv@"+agentURL
	
	segs["UseEnv"]=UseEnv=async function(input){//:1IGO1NK0L0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[`conda init`,`conda activate ${envName}`];
		args['options']="";
		/*#{1IGO1NK0L0PreCodes*/
		/*}#1IGO1NK0L0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IGO1NK0L0PostCodes*/
		addLog(`Conda env ${envName} activate result:\n${result}`);
		project.progress.push(`选定conda环境："${envName}"，作为项目的python环境。`);
		project.conda=envName;
		result={result:"Finish",content:`选定conda环境："${envName}"，作为项目的python环境。`}
		/*}#1IGO1NK0L0PostCodes*/
		return {result:result};
	};
	UseEnv.jaxId="1IGO1NK0L0"
	UseEnv.url="UseEnv@"+agentURL
	
	segs["AskNewName"]=AskNewName=async function(input){//:1IGB5JNC20
		let tip=((($ln==="CN")?(`环境名'${input}'已被使用，请选择另一个名字。`):(`The environment name '${input}' is already in use, please choose another name.`)));
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let allowEmpty=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
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
		return {seg:CheckEnvName,result:(result),preSeg:"1IGB5JNC20",outlet:"1IGB5QNSL0"};
	};
	AskNewName.jaxId="1IGB5JNC20"
	AskNewName.url="AskNewName@"+agentURL
	
	segs["AskPrjEnv"]=AskPrjEnv=async function(input){//:1IHC8O6CQ0
		let prompt=("是否为项目创建专有source环境？")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"创建虚拟环境",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"使用当前环境，不创建souce环境",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			/*#{1IHC8O6C00Silent*/
			/*}#1IHC8O6C00Silent*/
			return {seg:NewSourceEnv,result:(result),preSeg:"1IHC8O6CQ0",outlet:"1IHC8O6C00"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			/*#{1IHC8O6C00*/
			/*}#1IHC8O6C00*/
			return {seg:NewSourceEnv,result:(result),preSeg:"1IHC8O6CQ0",outlet:"1IHC8O6C00"};
		}else if(item.code===1){
			return {result:result};
		}
		return {result:result};
	};
	AskPrjEnv.jaxId="1IHC8O6CQ0"
	AskPrjEnv.url="AskPrjEnv@"+agentURL
	
	segs["NewSourceEnv"]=NewSourceEnv=async function(input){//:1IHC8T4DO0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[
	"python -m venv ./.venv",
    "source ./.venv/bin/activate"
];
		args['options']="";
		/*#{1IHC8T4DO0PreCodes*/
		/*}#1IHC8T4DO0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IHC8T4DO0PostCodes*/
		project.venv=".venv";
		project.progress.push(`为项目创建了venv环境，位于项目目录内的 ".venv"目录。`);
		/*}#1IHC8T4DO0PostCodes*/
		return {result:result};
	};
	NewSourceEnv.jaxId="1IHC8T4DO0"
	NewSourceEnv.url="NewSourceEnv@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"PrjCheckCondaEnv",
		url:agentURL,
		autoStart:true,
		jaxId:"1IGAU4QB50",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{refName,pyversion,installReq}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IGAU4QB50PreEntry*/
			/*}#1IGAU4QB50PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IGAU4QB50PostEntry*/
			/*}#1IGAU4QB50PostEntry*/
			return result;
		},
		/*#{1IGAU4QB50MoreAgentAttrs*/
		/*}#1IGAU4QB50MoreAgentAttrs*/
	};
	/*#{1IGAU4QB50PostAgent*/
	/*}#1IGAU4QB50PostAgent*/
	return agent;
};
/*#{1IGAU4QB50ExCodes*/
/*}#1IGAU4QB50ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "PrjCheckCondaEnv",
		description: "这是安装配置项目的conda环境的AI智能体。请提供：1）要推荐安装的conda环境名字。2）需要的python版本号。3）是否测试安装项目依赖，通常不需要这样做。",
		parameters:{
			type: "object",
			properties:{
				refName:{type:"string",description:"推荐的Conda环境名字"},
				pyversion:{type:"string",description:"需要的Python版本号"},
				installReq:{type:"bool",description:"是否安装依赖库，默认调用不必安装"}
			}
		}
	},
	isChatApi: true
}];
//#CodyExport<<<
/*#{1IGAU4QB50PostDoc*/
/*}#1IGAU4QB50PostDoc*/


export default PrjCheckCondaEnv;
export{PrjCheckCondaEnv,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IGAU4QB50",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IGAU4QB51",
//			"attrs": {
//				"PrjCheckCondaEnv": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IGAU4QB60",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IGAU4QB61",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IGAU4QB62",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IGAU4QB63",
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
//			"jaxId": "1IGAU4QB52",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IGAU4QB53",
//			"attrs": {
//				"refName": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ3UQ5A90",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "推荐的Conda环境名字",
//						"required": "false"
//					}
//				},
//				"pyversion": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ3UQ5A91",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "需要的Python版本号",
//						"required": "false"
//					}
//				},
//				"installReq": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ3UQ5A92",
//					"attrs": {
//						"type": "Boolean",
//						"mockup": "\"\"",
//						"desc": "是否安装依赖库，默认调用不必安装",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IGAU4QB54",
//			"attrs": {
//				"env": {
//					"type": "auto",
//					"valText": "#globalContext.env"
//				},
//				"project": {
//					"type": "auto",
//					"valText": "#globalContext.project"
//				},
//				"dirPath": {
//					"type": "string",
//					"valText": "#project.dirPath"
//				},
//				"reqText": {
//					"type": "string",
//					"valText": ""
//				},
//				"envName": {
//					"type": "string",
//					"valText": ""
//				},
//				"condaEnvs": {
//					"type": "string",
//					"valText": ""
//				},
//				"pythonVersion": {
//					"type": "string",
//					"valText": "3.9"
//				},
//				"prjConda": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IGAU4QB55",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IGAU4QB56",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IJ40H5E60",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "95",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1IJ40I84H0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGAU72M10"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IGAU72M10",
//					"attrs": {
//						"id": "ReadReq",
//						"viewName": "",
//						"label": "",
//						"x": "310",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGAUQE2M0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGAUQE2M1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGAUQE2K0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGAU7N830"
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
//					"jaxId": "1IGAU7N830",
//					"attrs": {
//						"id": "CheckReq",
//						"viewName": "",
//						"label": "",
//						"x": "545",
//						"y": "400",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGAUQE2M2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGAUQE2M3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGAUQE2K2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IGAU8E150"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IGAUQE2K1",
//									"attrs": {
//										"id": "HasReq",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IGAUQE2M4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGAUQE2M5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!input"
//									},
//									"linkedSeg": "1IGAU8VK60"
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
//					"jaxId": "1IGAU8E150",
//					"attrs": {
//						"id": "Result",
//						"viewName": "",
//						"label": "",
//						"x": "775",
//						"y": "555",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IGAUQE2M6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGAUQE2M7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGAUQE2K3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB4P45I0"
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
//					"jaxId": "1IGAU8VK60",
//					"attrs": {
//						"id": "GetReqType",
//						"viewName": "",
//						"label": "",
//						"x": "775",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGAUQE2M8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGAUQE2M9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGAUQE2K4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGAU98UF0"
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
//					"jaxId": "1IGAU98UF0",
//					"attrs": {
//						"id": "CheckReqType",
//						"viewName": "",
//						"label": "",
//						"x": "1010",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "#input===\"conda\"",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGAUQE2M10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGAUQE2M11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGAUQE2K6",
//							"attrs": {
//								"id": "NoType",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IGB15TE40"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IGAUQE2K5",
//									"attrs": {
//										"id": "Conda",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IGAUQE2M12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGAUQE2M13",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input===\"conda\""
//									},
//									"linkedSeg": "1IGB23HH50"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IGB16AQS0",
//									"attrs": {
//										"id": "Pip",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IGB16AR30",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGB16AR31",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input===\"pip\""
//									},
//									"linkedSeg": "1IGB2G48K0"
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
//					"jaxId": "1IGB23HH50",
//					"attrs": {
//						"id": "TryConda",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGB281MK0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB281MK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[\n\t`cd ${dirPath}`,\n\t\"conda install --file ./requirements.txt --dry-run\"\n]",
//						"options": "#{clear:true}",
//						"outlet": {
//							"jaxId": "1IGB281MF0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB4O4R30"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IGB2G48K0",
//					"attrs": {
//						"id": "TryPip",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGB2GDG30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB2GDG31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[\t`cd ${dirPath}`,\t\"pip install -r ./requirements.txt --dry-run\"]",
//						"options": "#{clear:true}",
//						"outlet": {
//							"jaxId": "1IGB2GDFT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB4O4R30"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IGB4O4R30",
//					"attrs": {
//						"id": "TipIssue",
//						"viewName": "",
//						"label": "",
//						"x": "1475",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGB5QNSR6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB5QNSR7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IGB5QNSJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB4NMLD0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IGB15TE40",
//					"attrs": {
//						"id": "NoType",
//						"viewName": "",
//						"label": "",
//						"x": "1260",
//						"y": "470",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IGB16AR32",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB16AR33",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGB16AQT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB4NMLD0"
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
//					"def": "askConfirm",
//					"jaxId": "1IGB4NMLD0",
//					"attrs": {
//						"id": "AskEnv",
//						"viewName": "",
//						"label": "",
//						"x": "1715",
//						"y": "470",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Select the conda environment for the project: create a new one, use the default one, or choose an existing environment:",
//							"localize": {
//								"EN": "Select the conda environment for the project: create a new one, use the default one, or choose an existing environment:",
//								"CN": "选择项目的conda环境：创建新的，使用默认的，还是选择一个已有的环境："
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IGB4NMKQ0",
//									"attrs": {
//										"id": "NewEnv",
//										"desc": "输出节点。",
//										"text": "新环境",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IGB5QNSR0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGB5QNSR1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IGB5E9310"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IGB4NMKQ1",
//									"attrs": {
//										"id": "CurEnv",
//										"desc": "输出节点。",
//										"text": "当前环境",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IGB5QNSR2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGB5QNSR3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IGB50VR80"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IGB57IE20",
//									"attrs": {
//										"id": "Select",
//										"desc": "输出节点。",
//										"text": "选择环境",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IGB5QNSR4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGB5QNSR5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IGB5D9570"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IGB4P45I0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1360",
//						"y": "555",
//						"outlet": {
//							"jaxId": "1IGB5QNSR8",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB4NMLD0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IGG3ILB70",
//					"attrs": {
//						"id": "AskPythonVersion",
//						"viewName": "",
//						"label": "",
//						"x": "2975",
//						"y": "195",
//						"desc": "TODO: Python版本应该可以从Readme里提取？",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"prompt": "#pyversion?(($ln===\"CN\")?(`系统推荐的Python版本是: ${pyversion}，你也可以选择一个`):/*EN*/(`The recommended Python version is: ${pyversion}, you can also choose one`)):(($ln===\"CN\")?(\"请选择新环境的Python版本\"):/*EN*/(\"Please select the Python version for the new environment\"))",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IGG3M9A20",
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
//									"jaxId": "1IGG3ILAR0",
//									"attrs": {
//										"id": "309",
//										"desc": "输出节点。",
//										"text": "3.9",
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IGG3M9A70",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGG3M9A71",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IGB4V6D30"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IGG3ILAR1",
//									"attrs": {
//										"id": "310",
//										"desc": "输出节点。",
//										"text": "3.10",
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IGG3M9A72",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGG3M9A73",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IGB4V6D30"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IGG3ILAR2",
//									"attrs": {
//										"id": "311",
//										"desc": "输出节点。",
//										"text": "3.11",
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IGG3M9A74",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGG3M9A75",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IGB4V6D30"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J0B3D2LI0",
//									"attrs": {
//										"id": "312",
//										"desc": "输出节点。",
//										"text": "3.12",
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1J0B3D2LP0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J0B3D2LP1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IGB4V6D30"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J0B3ECO40",
//									"attrs": {
//										"id": "Default",
//										"desc": "输出节点。",
//										"text": "Default",
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1J0B3FQV30",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J0B3FQV31",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IGB4V6D30"
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
//					"jaxId": "1IGB4V6D30",
//					"attrs": {
//						"id": "NewEnv",
//						"viewName": "",
//						"label": "",
//						"x": "3265",
//						"y": "180",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IGB5QNSR9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB5QNSR10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[`conda create -n ${envName} python=${pythonVersion} -y`,`conda activate ${envName}`]",
//						"options": "#{clear:true}",
//						"outlet": {
//							"jaxId": "1IGB5QNSJ1",
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
//					"def": "code",
//					"jaxId": "1IGB50VR80",
//					"attrs": {
//						"id": "End2",
//						"viewName": "",
//						"label": "",
//						"x": "1945",
//						"y": "470",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IGB5QNSR11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB5QNSR12",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGB5QNSJ2",
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
//					"jaxId": "1IGB5D9570",
//					"attrs": {
//						"id": "ChooseEnv",
//						"viewName": "",
//						"label": "",
//						"x": "1945",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Please select a Conda environment within the current system",
//							"localize": {
//								"EN": "Please select a Conda environment within the current system",
//								"CN": "请选择一个当前系统内的Conda环境"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IGB5QNSK0",
//							"attrs": {
//								"id": "Choose",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1IGB5Q4LI0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"silent": "false"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IGB5E9310",
//					"attrs": {
//						"id": "GenEnvName",
//						"viewName": "",
//						"label": "",
//						"x": "1945",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGB5QNSR15",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB5QNSR16",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGB5QNSK1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB5EMM00"
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
//					"def": "askConfirm",
//					"jaxId": "1IGB5EMM00",
//					"attrs": {
//						"id": "ConfirmName",
//						"viewName": "",
//						"label": "",
//						"x": "2185",
//						"y": "210",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "#`Confirm using the new environment name: ${envName}?`",
//							"localize": {
//								"EN": "#`Confirm using the new environment name: ${envName}?`",
//								"CN": "#`确认使用新的环境名称：${envName}？`"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IGB5EMLH0",
//									"attrs": {
//										"id": "OK",
//										"desc": "输出节点。",
//										"text": "使用",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IGB5QNSR17",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGB5QNSR18",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IGG3ILB70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IGB5EMLH1",
//									"attrs": {
//										"id": "Change",
//										"desc": "输出节点。",
//										"text": "指定环境名",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IGB5QNSR19",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGB5QNSR20",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IGB5FMAJ0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IGB5FMAJ0",
//					"attrs": {
//						"id": "AskEnvName",
//						"viewName": "",
//						"label": "",
//						"x": "2440",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGB5QNSR21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB5QNSR22",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": {
//							"type": "string",
//							"valText": "Please enter the environment name",
//							"localize": {
//								"EN": "Please enter the environment name",
//								"CN": "请输入环境名"
//							},
//							"localizable": true
//						},
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"allowEmpty": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1IGB5QNSK2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB5GSU20"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IGB5GSU20",
//					"attrs": {
//						"id": "CheckEnvName",
//						"viewName": "",
//						"label": "",
//						"x": "2695",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGB5QNSR23",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB5QNSR24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGB5QNSK4",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IGB5JNC20"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IGB5QNSK3",
//									"attrs": {
//										"id": "NameOK",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IGB5QNSR25",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGB5QNSR26",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#condaEnvs.indexOf(input)<0 && condaEnvRegex.test(input)"
//									},
//									"linkedSeg": "1IGG3ILB70"
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
//					"jaxId": "1IGB5ITNU0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "3135",
//						"y": "400",
//						"outlet": {
//							"jaxId": "1IGB5QNSR27",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB5J25M0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IGB5J25M0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2720",
//						"y": "400",
//						"outlet": {
//							"jaxId": "1IGB5QNSR28",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB5GSU20"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IGB5Q4LI0",
//					"attrs": {
//						"id": "SelectEnv",
//						"viewName": "",
//						"label": "",
//						"x": "2190",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IGB5QNSR31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB5QNSR32",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGB5QNSL1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGO1NK0L0"
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
//					"def": "Bash",
//					"jaxId": "1IGO1NK0L0",
//					"attrs": {
//						"id": "UseEnv",
//						"viewName": "",
//						"label": "",
//						"x": "2430",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IGO1O50G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGO1O50G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[`conda init`,`conda activate ${envName}`]",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IGO1O5080",
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
//					"def": "askChat",
//					"jaxId": "1IGB5JNC20",
//					"attrs": {
//						"id": "AskNewName",
//						"viewName": "",
//						"label": "",
//						"x": "2975",
//						"y": "315",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGB5QNSR29",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB5QNSR30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": {
//							"type": "string",
//							"valText": "#`The environment name '${input}' is already in use, please choose another name.`",
//							"localize": {
//								"EN": "#`The environment name '${input}' is already in use, please choose another name.`",
//								"CN": "#`环境名'${input}'已被使用，请选择另一个名字。`"
//							},
//							"localizable": true
//						},
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"allowEmpty": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1IGB5QNSL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IGB5ITNU0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IHC8O6CQ0",
//					"attrs": {
//						"id": "AskPrjEnv",
//						"viewName": "",
//						"label": "",
//						"x": "2680",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "是否为项目创建专有source环境？",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IHC8TV0T0",
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
//									"jaxId": "1IHC8O6C00",
//									"attrs": {
//										"id": "Create",
//										"desc": "输出节点。",
//										"text": "创建虚拟环境",
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IHC8TV142",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHC8TV143",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHC8T4DO0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHC8O6C01",
//									"attrs": {
//										"id": "Cancel",
//										"desc": "输出节点。",
//										"text": "使用当前环境，不创建souce环境",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHC8TV144",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHC8TV145",
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
//					"def": "Bash",
//					"jaxId": "1IHC8T4DO0",
//					"attrs": {
//						"id": "NewSourceEnv",
//						"viewName": "",
//						"label": "",
//						"x": "2915",
//						"y": "530",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHC8TV148",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHC8TV149",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[\n\t\"python -m venv ./.venv\",\n    \"source ./.venv/bin/activate\"\n]",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IHC8TV0U1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "terminal.svg"
//				}
//			]
//		},
//		"desc": "这是安装配置项目的conda环境的AI智能体。请提供：1）要推荐安装的conda环境名字。2）需要的python版本号。3）是否测试安装项目依赖，通常不需要这样做。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}