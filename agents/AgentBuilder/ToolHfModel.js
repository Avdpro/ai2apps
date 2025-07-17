//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IJ44VPHU0MoreImports*/
/*}#1IJ44VPHU0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
const argsTemplate={
	properties:{
		"model":{
			"name":"model","type":"string",
			"defaultValue":"",
			"desc":"要下载的模型，通常格式为：<username>/<model_name>",
		},
		"localPath":{
			"name":"localPath","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"如果要下载到本地目录，目标目录路径",
		},
		"token":{
			"name":"token","type":"string",
			"required":false,
			"defaultValue":"",
			"desc":"如果模型下载需要授权，则需要token",
		}
	},
	/*#{1IJ44VPHU0ArgsView*/
	/*}#1IJ44VPHU0ArgsView*/
};

/*#{1IJ44VPHU0StartDoc*/
/*}#1IJ44VPHU0StartDoc*/
//----------------------------------------------------------------------------
let ToolHfModel=async function(session){
	let model,localPath,token;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,Download,Check,Switch,Install,CheckDownload,tip1,tip2,tip3,AskMirror,SetMirror,InputToken,CheckToken,FormatError,goto1,TryAgain,goto3,AbortDownload,CheckAgain,tip4,AskToken,asktoken,goto2,tip5,CheckModel,AskModel,InputModel,goto5;
	/*#{1IJ44VPHU0LocalVals*/
	/*}#1IJ44VPHU0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			model=input.model;
			localPath=input.localPath;
			token=input.token;
		}else{
			model=undefined;
			localPath=undefined;
			token=undefined;
		}
		/*#{1IJ44VPHU0ParseArgs*/
		/*}#1IJ44VPHU0ParseArgs*/
	}
	
	/*#{1IJ44VPHU0PreContext*/
	/*}#1IJ44VPHU0PreContext*/
	context={};
	/*#{1IJ44VPHU0PostContext*/
	/*}#1IJ44VPHU0PostContext*/
	let $agent,agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IJ45019V0
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(model===undefined || model==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:Check,result:(result),preSeg:"1IJ45019V0",outlet:"1IJ45342I0"};
	};
	FixArgs.jaxId="1IJ45019V0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Download"]=Download=async function(input){//:1IJ45B6Q50
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="";
		args['options']="";
		/*#{1IJ45B6Q50PreCodes*/
		let command = `huggingface-cli download`;
		if (token) {
			command += ` --token ${token}`;
		}
		if (model) {
			command += ` ${model}`;
		}
		if (localPath) {
			command += ` --local-dir ${localPath}`;
		}
		
		args['commands']= [`rm -rf ~/.cache/huggingface/hub/`,command];
		/*}#1IJ45B6Q50PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IJ45B6Q50PostCodes*/
		/*}#1IJ45B6Q50PostCodes*/
		return {seg:CheckDownload,result:(result),preSeg:"1IJ45B6Q50",outlet:"1IJ45SKMC0"};
	};
	Download.jaxId="1IJ45B6Q50"
	Download.url="Download@"+agentURL
	
	segs["Check"]=Check=async function(input){//:1IL0EDOSU0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="huggingface-cli";
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:Switch,result:(result),preSeg:"1IL0EDOSU0",outlet:"1IL0EDOSU1"};
	};
	Check.jaxId="1IL0EDOSU0"
	Check.url="Check@"+agentURL
	
	segs["Switch"]=Switch=async function(input){//:1IL0EEQ1N0
		let result=input;
		if(!input.includes("not found")){
			return {seg:CheckModel,result:(input),preSeg:"1IL0EEQ1N0",outlet:"1IL0EJLHS0"};
		}
		return {seg:Install,result:(result),preSeg:"1IL0EEQ1N0",outlet:"1IL0EJLHT0"};
	};
	Switch.jaxId="1IL0EEQ1N0"
	Switch.url="Switch@"+agentURL
	
	segs["Install"]=Install=async function(input){//:1IL0F6R660
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="pip install huggingface-hub";
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:CheckModel,result:(result),preSeg:"1IL0F6R660",outlet:"1IL0F8C2V0"};
	};
	Install.jaxId="1IL0F6R660"
	Install.url="Install@"+agentURL
	
	segs["CheckDownload"]=CheckDownload=async function(input){//:1IL0FKG9B0
		let result=input;
		if(input.includes("LocalEntryNotFoundError")){
			return {seg:tip1,result:(input),preSeg:"1IL0FKG9B0",outlet:"1IL0FM5SC0"};
		}
		if(input.includes("You must have access to it and be authenticated to access it.")){
			return {seg:tip2,result:(input),preSeg:"1IL0FKG9B0",outlet:"1IL0FL4HB0"};
		}
		if(input.includes("ConnectionError")){
			return {seg:tip3,result:(input),preSeg:"1IL0FKG9B0",outlet:"1IL0FL5S00"};
		}
		if(input.includes("rejected by the repo's authors")){
			return {seg:tip4,result:(input),preSeg:"1IL0FKG9B0",outlet:"1IL2U3HM60"};
		}
		if(input.includes("Repository Not Found for url")){
			return {seg:tip5,result:(input),preSeg:"1IL0FKG9B0",outlet:"1IL30U7430"};
		}
		return {seg:CheckAgain,result:(result),preSeg:"1IL0FKG9B0",outlet:"1IL0FM5SC1"};
	};
	CheckDownload.jaxId="1IL0FKG9B0"
	CheckDownload.url="CheckDownload@"+agentURL
	
	segs["tip1"]=tip1=async function(input){//:1IL0GBNQD0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="LocalEntryNotFoundError: An error happened while trying to locate the file\n原因：本地缓存缺失且网络连接失败、token权限问题\n解决方案：\n1、检查网络连接，尝试通过镜像站重试下载。\n2、手动下载模型文件并放置到缓存目录（默认路径为 ~/.cache/huggingface/hub）\n3、检查token是否是read权限";
		session.addChatText(role,content,opts);
		return {seg:goto1,result:(result),preSeg:"1IL0GBNQD0",outlet:"1IL0GH5VV0"};
	};
	tip1.jaxId="1IL0GBNQD0"
	tip1.url="tip1@"+agentURL
	
	segs["tip2"]=tip2=async function(input){//:1IL0GCLFE0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="下载需登录的私有模型失败\n原因：未提供有效 Token 或 Token 权限不足。\n解决方案：\n1、在命令中添加 --token hf_xxx 参数（hf_xxx 为官网生成的 Token）";
		session.addChatText(role,content,opts);
		return {seg:goto2,result:(result),preSeg:"1IL0GCLFE0",outlet:"1IL0GH5VV1"};
	};
	tip2.jaxId="1IL0GCLFE0"
	tip2.url="tip2@"+agentURL
	
	segs["tip3"]=tip3=async function(input){//:1IL0GD2U40
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="ConnectionError: Couldn't reach ... on the Hub (SSLError)\n原因：代理配置错误或 SSL 证书问题。\n解决方案：\n1、检查代理设置是否正确（如 export all_proxy=socks5://192.168.1.110:1080）。\n2、若使用科学上网工具，确保 Python 的 urllib3 库代理配置正确";
		session.addChatText(role,content,opts);
		return {seg:TryAgain,result:(result),preSeg:"1IL0GD2U40",outlet:"1IL0GH5VV2"};
	};
	tip3.jaxId="1IL0GD2U40"
	tip3.url="tip3@"+agentURL
	
	segs["AskMirror"]=AskMirror=async function(input){//:1IL0GMG890
		let prompt=("是否需要设置镜像加速下载")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"是",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"否",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:SetMirror,result:(result),preSeg:"1IL0GMG890",outlet:"1IL0GMG700"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:SetMirror,result:(result),preSeg:"1IL0GMG890",outlet:"1IL0GMG700"};
		}else if(item.code===1){
			return {seg:Download,result:(result),preSeg:"1IL0GMG890",outlet:"1IL0GMG701"};
		}
		return {result:result};
	};
	AskMirror.jaxId="1IL0GMG890"
	AskMirror.url="AskMirror@"+agentURL
	
	segs["SetMirror"]=SetMirror=async function(input){//:1IL0GQNI50
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="export HF_ENDPOINT=https://hf-mirror.com";
		args['options']="";
		/*#{1IL0GQNI50PreCodes*/
		/*}#1IL0GQNI50PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IL0GQNI50PostCodes*/
		context.set_mirror = true;
		/*}#1IL0GQNI50PostCodes*/
		return {seg:Download,result:(result),preSeg:"1IL0GQNI50",outlet:"1IL0GT9GV1"};
	};
	SetMirror.jaxId="1IL0GQNI50"
	SetMirror.url="SetMirror@"+agentURL
	
	segs["InputToken"]=InputToken=async function(input){//:1IL0H9PLO0
		let tip=("");
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
		return {seg:CheckToken,result:(result),preSeg:"1IL0H9PLO0",outlet:"1IL0HIUAD0"};
	};
	InputToken.jaxId="1IL0H9PLO0"
	InputToken.url="InputToken@"+agentURL
	
	segs["CheckToken"]=CheckToken=async function(input){//:1IL0HAJHS0
		let result=input;
		/*#{1IL0HAJHS0Start*/
		token = input;
		/*}#1IL0HAJHS0Start*/
		if(!input.startsWith("hf_")){
			/*#{1IL0HIUAD1Codes*/
			/*}#1IL0HIUAD1Codes*/
			return {seg:FormatError,result:(input),preSeg:"1IL0HAJHS0",outlet:"1IL0HIUAD1"};
		}
		if(context.set_mirror === false){
			return {seg:AskMirror,result:(input),preSeg:"1IL0HAJHS0",outlet:"1IL2UD8LN0"};
		}
		/*#{1IL0HAJHS0Post*/
		/*}#1IL0HAJHS0Post*/
		return {seg:Download,result:(result),preSeg:"1IL0HAJHS0",outlet:"1IL0HIUAD2"};
	};
	CheckToken.jaxId="1IL0HAJHS0"
	CheckToken.url="CheckToken@"+agentURL
	
	segs["FormatError"]=FormatError=async function(input){//:1IL0HDTOC0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="格式错误，请输入hf_xxx格式的token";
		session.addChatText(role,content,opts);
		return {seg:InputToken,result:(result),preSeg:"1IL0HDTOC0",outlet:"1IL0HIUAD3"};
	};
	FormatError.jaxId="1IL0HDTOC0"
	FormatError.url="FormatError@"+agentURL
	
	segs["goto1"]=goto1=async function(input){//:1IL0HQKGB0
		let result=input;
		return {seg:CheckModel,result:result,preSeg:"1IL313FAC0",outlet:"1IL0I5C610"};
	
	};
	goto1.jaxId="1IL313FAC0"
	goto1.url="goto1@"+agentURL
	
	segs["TryAgain"]=TryAgain=async function(input){//:1IL0I2CDI0
		let prompt=("是否重试")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"是",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"否",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:goto3,result:(result),preSeg:"1IL0I2CDI0",outlet:"1IL0I2CCB0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:goto3,result:(result),preSeg:"1IL0I2CDI0",outlet:"1IL0I2CCB0"};
		}else if(item.code===1){
			return {seg:AbortDownload,result:(result),preSeg:"1IL0I2CDI0",outlet:"1IL0I2CCB1"};
		}
		return {result:result};
	};
	TryAgain.jaxId="1IL0I2CDI0"
	TryAgain.url="TryAgain@"+agentURL
	
	segs["goto3"]=goto3=async function(input){//:1IL0I4DIU0
		let result=input;
		return {seg:CheckModel,result:result,preSeg:"1IL313FAC0",outlet:"1IL0I5C612"};
	
	};
	goto3.jaxId="1IL313FAC0"
	goto3.url="goto3@"+agentURL
	
	segs["AbortDownload"]=AbortDownload=async function(input){//:1IL0I5LN40
		let result=input
		/*#{1IL0I5LN40Code*/
		result={result:"Abort",content:(($ln==="CN")?("模型下载失败。"):/*EN*/("Failed to download the model."))};
		/*}#1IL0I5LN40Code*/
		return {result:result};
	};
	AbortDownload.jaxId="1IL0I5LN40"
	AbortDownload.url="AbortDownload@"+agentURL
	
	segs["CheckAgain"]=CheckAgain=async function(input){//:1IL0I9VCS0
		let prompt=("请确认模型是否下载成功")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"是",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"否",code:1},
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
		}else if(item.code===1){
			return {seg:TryAgain,result:(result),preSeg:"1IL0I9VCS0",outlet:"1IL0I9VBO1"};
		}
		return {result:result};
	};
	CheckAgain.jaxId="1IL0I9VCS0"
	CheckAgain.url="CheckAgain@"+agentURL
	
	segs["tip4"]=tip4=async function(input){//:1IL2R1CUR0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="你的访问权限被作者拒绝了，请重新检查权限或更换token。";
		session.addChatText(role,content,opts);
		return {seg:TryAgain,result:(result),preSeg:"1IL2R1CUR0",outlet:"1IL2U3HM80"};
	};
	tip4.jaxId="1IL2R1CUR0"
	tip4.url="tip4@"+agentURL
	
	segs["AskToken"]=AskToken=async function(input){//:1IL2TA3PK0
		let prompt=("部分模型需要官网的token才能下载，是否需要设置token")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"是",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"否",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:asktoken,result:(result),preSeg:"1IL2TA3PK0",outlet:"1IL2TA3OL0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:asktoken,result:(result),preSeg:"1IL2TA3PK0",outlet:"1IL2TA3OL0"};
		}else if(item.code===1){
			return {seg:goto5,result:(result),preSeg:"1IL2TA3PK0",outlet:"1IL2TA3OL1"};
		}
		return {result:result};
	};
	AskToken.jaxId="1IL2TA3PK0"
	AskToken.url="AskToken@"+agentURL
	
	segs["asktoken"]=asktoken=async function(input){//:1IL2TF5VG0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="请输入hf_xxx格式的token";
		session.addChatText(role,content,opts);
		return {seg:InputToken,result:(result),preSeg:"1IL2TF5VG0",outlet:"1IL2U3HM82"};
	};
	asktoken.jaxId="1IL2TF5VG0"
	asktoken.url="asktoken@"+agentURL
	
	segs["goto2"]=goto2=async function(input){//:1IL2U251T0
		let result=input;
		return {seg:CheckModel,result:result,preSeg:"1IL313FAC0",outlet:"1IL2U3HM83"};
	
	};
	goto2.jaxId="1IL313FAC0"
	goto2.url="goto2@"+agentURL
	
	segs["tip5"]=tip5=async function(input){//:1IL30V13H0
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="Respository Not Found for url\n原因：模型不存在或token不正确\n解决方案：\n1、检查模型名称是否正确\n2、检查token是否正确";
		session.addChatText(role,content,opts);
		return {seg:TryAgain,result:(result),preSeg:"1IL30V13H0",outlet:"1IL314B490"};
	};
	tip5.jaxId="1IL30V13H0"
	tip5.url="tip5@"+agentURL
	
	segs["CheckModel"]=CheckModel=async function(input){//:1IL313FAC0
		let prompt=(`请确认下载的模型是 ${model}`)||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"是",code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:"否",code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:AskToken,result:(result),preSeg:"1IL313FAC0",outlet:"1IL313F9M0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:AskToken,result:(result),preSeg:"1IL313FAC0",outlet:"1IL313F9M0"};
		}else if(item.code===1){
			return {seg:AskModel,result:(result),preSeg:"1IL313FAC0",outlet:"1IL313F9M1"};
		}
		return {result:result};
	};
	CheckModel.jaxId="1IL313FAC0"
	CheckModel.url="CheckModel@"+agentURL
	
	segs["AskModel"]=AskModel=async function(input){//:1IL3192400
		let result=input;
		let opts={txtHeader:($agent.showName||$agent.name||null)};
		let role="assistant";
		let content="请重新输入模型名称，通常格式为：<username>/<model_name>";
		/*#{1IL3192400PreCodes*/
		/*}#1IL3192400PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IL3192400PostCodes*/
		/*}#1IL3192400PostCodes*/
		return {seg:InputModel,result:(result),preSeg:"1IL3192400",outlet:"1IL31AE3M0"};
	};
	AskModel.jaxId="1IL3192400"
	AskModel.url="AskModel@"+agentURL
	
	segs["InputModel"]=InputModel=async function(input){//:1IL31AS6C0
		let tip=("");
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
		return {seg:CheckModel,result:(result),preSeg:"1IL31AS6C0",outlet:"1IL31DE6K0"};
	};
	InputModel.jaxId="1IL31AS6C0"
	InputModel.url="InputModel@"+agentURL
	
	segs["goto5"]=goto5=async function(input){//:1IL31NK370
		let result=input;
		return {seg:AskMirror,result:result,preSeg:"1IL0GMG890",outlet:"1IL31NTA80"};
	
	};
	goto5.jaxId="1IL0GMG890"
	goto5.url="goto5@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"ToolHfModel",
		url:agentURL,
		autoStart:true,
		jaxId:"1IJ44VPHU0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{model,localPath,token}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IJ44VPHU0PreEntry*/
			/*}#1IJ44VPHU0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IJ44VPHU0PostEntry*/
			/*}#1IJ44VPHU0PostEntry*/
			return result;
		},
		/*#{1IJ44VPHU0MoreAgentAttrs*/
		/*}#1IJ44VPHU0MoreAgentAttrs*/
	};
	/*#{1IJ44VPHU0PostAgent*/
	/*}#1IJ44VPHU0PostAgent*/
	return agent;
};
/*#{1IJ44VPHU0ExCodes*/
/*}#1IJ44VPHU0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "ToolHfModel",
		description: "这是通过huggingface下载模型的智能体，如果需要下载模型，请使用本智能体，而不是直接通过命令行下载。",
		parameters:{
			type: "object",
			properties:{
				model:{type:"string",description:"要下载的模型，通常格式为：<username>/<model_name>"},
				localPath:{type:"string",description:"如果要下载到本地目录，目标目录路径"},
				token:{type:"string",description:"如果模型下载需要授权，则需要token"}
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
		name:"ToolHfModel",showName:"ToolHfModel",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"model":{name:"model",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"localPath":{name:"localPath",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"token":{name:"token",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","model","localPath","token","codes","desc"],
		desc:"这是通过huggingface下载模型的智能体，如果需要下载模型，请使用本智能体，而不是直接通过命令行下载。"
	});
	
	DocAIAgentExporter.segTypeExporters["ToolHfModel"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['model']=");this.genAttrStatement(seg.getAttr("model"));coder.packText(";");coder.newLine();
			coder.packText("args['localPath']=");this.genAttrStatement(seg.getAttr("localPath"));coder.packText(";");coder.newLine();
			coder.packText("args['token']=");this.genAttrStatement(seg.getAttr("token"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/builder_new/ai/ToolHfModel.js",args,false);`);coder.newLine();
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
/*#{1IJ44VPHU0PostDoc*/
/*}#1IJ44VPHU0PostDoc*/


export default ToolHfModel;
export{ToolHfModel,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IJ44VPHU0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IJ44VPHV0",
//			"attrs": {
//				"ToolHfModel": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IJ44VPHV6",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IJ44VPHV7",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IJ44VPHV8",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IJ44VPHV9",
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
//			"jaxId": "1IJ44VPHV1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IJ44VPHV2",
//			"attrs": {
//				"model": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ45A5LC0",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "要下载的模型，通常格式为：<username>/<model_name>"
//					}
//				},
//				"localPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJ45A5LC1",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "如果要下载到本地目录，目标目录路径",
//						"required": "false"
//					}
//				},
//				"token": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IL0E4BPC0",
//					"attrs": {
//						"type": "string",
//						"mockup": "\"\"",
//						"desc": "如果模型下载需要授权，则需要token",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IJ44VPHV3",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IJ44VPHV4",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IJ44VPHV5",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IJ45019V0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "-1250",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1IJ45342I0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0EDOSU0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IJ45B6Q50",
//					"attrs": {
//						"id": "Download",
//						"viewName": "",
//						"label": "",
//						"x": "1355",
//						"y": "85",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJ45SKMC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ45SKMC2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IJ45SKMC0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0FKG9B0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IL0EDOSU0",
//					"attrs": {
//						"id": "Check",
//						"viewName": "",
//						"label": "",
//						"x": "-1010",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0F642C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0F642C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "huggingface-cli",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IL0EDOSU1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0EEQ1N0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IL0EEQ1N0",
//					"attrs": {
//						"id": "Switch",
//						"viewName": "",
//						"label": "",
//						"x": "-820",
//						"y": "275",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0F642C2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0F642C3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IL0EJLHT0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IL0F6R660"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IL0EJLHS0",
//									"attrs": {
//										"id": "Installed",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL0F642C4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0F642C5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!input.includes(\"not found\")"
//									},
//									"linkedSeg": "1IL313FAC0"
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
//					"jaxId": "1IL0F6R660",
//					"attrs": {
//						"id": "Install",
//						"viewName": "",
//						"label": "",
//						"x": "-520",
//						"y": "325",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0F8P9T0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0F8P9T1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "pip install huggingface-hub",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IL0F8C2V0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0F9GU30"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IL0F9GU30",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "-225",
//						"y": "240",
//						"outlet": {
//							"jaxId": "1IL0GTRD90",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0FAA400"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IL0FAA400",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "-510",
//						"y": "240",
//						"outlet": {
//							"jaxId": "1IL0GTRD91",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL313FAC0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IL0FKG9B0",
//					"attrs": {
//						"id": "CheckDownload",
//						"viewName": "",
//						"label": "",
//						"x": "1515",
//						"y": "-110",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0GTRD92",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0GTRD93",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IL0FM5SC1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IL0I9VCS0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IL0FM5SC0",
//									"attrs": {
//										"id": "LocalEntryNotFoundError",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL0GTRD94",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0GTRD95",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.includes(\"LocalEntryNotFoundError\")"
//									},
//									"linkedSeg": "1IL0GBNQD0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IL0FL4HB0",
//									"attrs": {
//										"id": "AuthorizedError",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL0GTRD96",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0GTRD97",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.includes(\"You must have access to it and be authenticated to access it.\")"
//									},
//									"linkedSeg": "1IL0GCLFE0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IL0FL5S00",
//									"attrs": {
//										"id": "ConnectionError",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL0GTRD98",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0GTRD99",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.includes(\"ConnectionError\")"
//									},
//									"linkedSeg": "1IL0GD2U40"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IL2U3HM60",
//									"attrs": {
//										"id": "Rejetced",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL2U548R0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL2U548R1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.includes(\"rejected by the repo's authors\")"
//									},
//									"linkedSeg": "1IL2R1CUR0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IL30U7430",
//									"attrs": {
//										"id": "NotFound",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL314I4F0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL314I4F1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.includes(\"Repository Not Found for url\")"
//									},
//									"linkedSeg": "1IL30V13H0"
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
//					"jaxId": "1IL0GBNQD0",
//					"attrs": {
//						"id": "tip1",
//						"viewName": "",
//						"label": "",
//						"x": "1845",
//						"y": "-245",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0GTRD910",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0GTRD911",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "LocalEntryNotFoundError: An error happened while trying to locate the file\n原因：本地缓存缺失且网络连接失败、token权限问题\n解决方案：\n1、检查网络连接，尝试通过镜像站重试下载。\n2、手动下载模型文件并放置到缓存目录（默认路径为 ~/.cache/huggingface/hub）\n3、检查token是否是read权限",
//						"outlet": {
//							"jaxId": "1IL0GH5VV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0HQKGB0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IL0GCLFE0",
//					"attrs": {
//						"id": "tip2",
//						"viewName": "",
//						"label": "",
//						"x": "1845",
//						"y": "-155",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0GTRD912",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0GTRD913",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "下载需登录的私有模型失败\n原因：未提供有效 Token 或 Token 权限不足。\n解决方案：\n1、在命令中添加 --token hf_xxx 参数（hf_xxx 为官网生成的 Token）",
//						"outlet": {
//							"jaxId": "1IL0GH5VV1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL2U251T0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IL0GD2U40",
//					"attrs": {
//						"id": "tip3",
//						"viewName": "",
//						"label": "",
//						"x": "1845",
//						"y": "-90",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0GTRD914",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0GTRD915",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "ConnectionError: Couldn't reach ... on the Hub (SSLError)\n原因：代理配置错误或 SSL 证书问题。\n解决方案：\n1、检查代理设置是否正确（如 export all_proxy=socks5://192.168.1.110:1080）。\n2、若使用科学上网工具，确保 Python 的 urllib3 库代理配置正确",
//						"outlet": {
//							"jaxId": "1IL0GH5VV2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0I2CDI0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IL0GMG890",
//					"attrs": {
//						"id": "AskMirror",
//						"viewName": "",
//						"label": "",
//						"x": "920",
//						"y": "-55",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"prompt": "是否需要设置镜像加速下载",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IL0GT9GV0",
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
//									"jaxId": "1IL0GMG700",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": "是",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL0GTRD916",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0GTRD917",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IL0GQNI50"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IL0GMG701",
//									"attrs": {
//										"id": "No",
//										"desc": "输出节点。",
//										"text": "否",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL0GTRD918",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0GTRD919",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IL31G3SS0"
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
//					"jaxId": "1IL0GQNI50",
//					"attrs": {
//						"id": "SetMirror",
//						"viewName": "",
//						"label": "",
//						"x": "1180",
//						"y": "-85",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0GTRD920",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0GTRD921",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "export HF_ENDPOINT=https://hf-mirror.com",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IL0GT9GV1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ45B6Q50"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IL0H9PLO0",
//					"attrs": {
//						"id": "InputToken",
//						"viewName": "",
//						"label": "",
//						"x": "460",
//						"y": "-55",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0HLOHK2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0HLOHK3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1IL0HIUAD0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0HAJHS0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IL0HAJHS0",
//					"attrs": {
//						"id": "CheckToken",
//						"viewName": "",
//						"label": "",
//						"x": "660",
//						"y": "-55",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0HLOHK4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0HLOHK5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IL0HIUAD2",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IL31FERQ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IL0HIUAD1",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IL0HLOHK6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0HLOHK7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!input.startsWith(\"hf_\")"
//									},
//									"linkedSeg": "1IL0HDTOC0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IL2UD8LN0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL2UG6AI0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL2UG6AI1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#context.set_mirror === false"
//									},
//									"linkedSeg": "1IL0GMG890"
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
//					"jaxId": "1IL0HDTOC0",
//					"attrs": {
//						"id": "FormatError",
//						"viewName": "",
//						"label": "",
//						"x": "900",
//						"y": "-165",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0HLOHK9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0HLOHK10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "格式错误，请输入hf_xxx格式的token",
//						"outlet": {
//							"jaxId": "1IL0HIUAD3",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL2U0ATR0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IL0HQKGB0",
//					"attrs": {
//						"id": "goto1",
//						"viewName": "",
//						"label": "",
//						"x": "2060",
//						"y": "-245",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "CheckModel",
//						"outlet": {
//							"jaxId": "1IL0I5C610",
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
//					"jaxId": "1IL0I2CDI0",
//					"attrs": {
//						"id": "TryAgain",
//						"viewName": "",
//						"label": "",
//						"x": "2045",
//						"y": "90",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "是否重试",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IL0I5C611",
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
//									"jaxId": "1IL0I2CCB0",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": "是",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL0I8BT70",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0I8BT71",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IL0I4DIU0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IL0I2CCB1",
//									"attrs": {
//										"id": "No",
//										"desc": "输出节点。",
//										"text": "否",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL0I8BT72",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0I8BT73",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IL0I5LN40"
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
//					"jaxId": "1IL0I4DIU0",
//					"attrs": {
//						"id": "goto3",
//						"viewName": "",
//						"label": "",
//						"x": "2280",
//						"y": "30",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "CheckModel",
//						"outlet": {
//							"jaxId": "1IL0I5C612",
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
//					"jaxId": "1IL0I5LN40",
//					"attrs": {
//						"id": "AbortDownload",
//						"viewName": "",
//						"label": "",
//						"x": "2280",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL0I5LN41",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL0I5LN42",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IL0I5LN43",
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
//					"jaxId": "1IL0I9VCS0",
//					"attrs": {
//						"id": "CheckAgain",
//						"viewName": "",
//						"label": "",
//						"x": "1795",
//						"y": "240",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "请确认模型是否下载成功",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IL0ICPFM0",
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
//									"jaxId": "1IL0I9VBO0",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": "是",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL0ICPG30",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0ICPG31",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									}
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IL0I9VBO1",
//									"attrs": {
//										"id": "No",
//										"desc": "输出节点。",
//										"text": "否",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL0ICPG32",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL0ICPG33",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IL0I2CDI0"
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
//					"jaxId": "1IL2R1CUR0",
//					"attrs": {
//						"id": "tip4",
//						"viewName": "",
//						"label": "",
//						"x": "1845",
//						"y": "0",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL2U548R2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL2U548R3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "你的访问权限被作者拒绝了，请重新检查权限或更换token。",
//						"outlet": {
//							"jaxId": "1IL2U3HM80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0I2CDI0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IL2TA3PK0",
//					"attrs": {
//						"id": "AskToken",
//						"viewName": "",
//						"label": "",
//						"x": "75",
//						"y": "85",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "部分模型需要官网的token才能下载，是否需要设置token",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IL2U3HM81",
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
//									"jaxId": "1IL2TA3OL0",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": "是",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL2U548R4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL2U548R5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IL2TF5VG0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IL2TA3OL1",
//									"attrs": {
//										"id": "No",
//										"desc": "输出节点。",
//										"text": "否",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL2U548R6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL2U548R7",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IL31NK370"
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
//					"jaxId": "1IL2TF5VG0",
//					"attrs": {
//						"id": "asktoken",
//						"viewName": "",
//						"label": "",
//						"x": "275",
//						"y": "-55",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL2U548R8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL2U548R9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "请输入hf_xxx格式的token",
//						"outlet": {
//							"jaxId": "1IL2U3HM82",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0H9PLO0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IL2U0ATR0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1060",
//						"y": "-290",
//						"outlet": {
//							"jaxId": "1IL2U548R10",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL2U0GB40"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IL2U0GB40",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "485",
//						"y": "-290",
//						"outlet": {
//							"jaxId": "1IL2U548R11",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0H9PLO0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IL2U251T0",
//					"attrs": {
//						"id": "goto2",
//						"viewName": "",
//						"label": "",
//						"x": "2060",
//						"y": "-155",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "CheckModel",
//						"outlet": {
//							"jaxId": "1IL2U3HM83",
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
//					"def": "output",
//					"jaxId": "1IL30V13H0",
//					"attrs": {
//						"id": "tip5",
//						"viewName": "",
//						"label": "",
//						"x": "1845",
//						"y": "85",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL314I4G0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL314I4G1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "Respository Not Found for url\n原因：模型不存在或token不正确\n解决方案：\n1、检查模型名称是否正确\n2、检查token是否正确",
//						"outlet": {
//							"jaxId": "1IL314B490",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0I2CDI0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IL313FAC0",
//					"attrs": {
//						"id": "CheckModel",
//						"viewName": "",
//						"label": "",
//						"x": "-585",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "",
//						"segMark": "None",
//						"prompt": "#`请确认下载的模型是 ${model}`",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IL314B491",
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
//									"jaxId": "1IL313F9M0",
//									"attrs": {
//										"id": "Yes",
//										"desc": "输出节点。",
//										"text": "是",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL314I4G2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL314I4G3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IL2TA3PK0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IL313F9M1",
//									"attrs": {
//										"id": "No",
//										"desc": "输出节点。",
//										"text": "否",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IL314I4G4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IL314I4G5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IL3192400"
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
//					"jaxId": "1IL3192400",
//					"attrs": {
//						"id": "AskModel",
//						"viewName": "",
//						"label": "",
//						"x": "-330",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL31DE6R0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL31DE6R1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "请重新输入模型名称，通常格式为：<username>/<model_name>",
//						"outlet": {
//							"jaxId": "1IL31AE3M0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL31AS6C0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IL31AS6C0",
//					"attrs": {
//						"id": "InputModel",
//						"viewName": "",
//						"label": "",
//						"x": "-115",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IL31DE6R2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IL31DE6R3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1IL31DE6K0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL31BFM60"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IL31BFM60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "-10",
//						"y": "240",
//						"outlet": {
//							"jaxId": "1IL31DE6R4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL0F9GU30"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IL31FERQ0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "870",
//						"y": "85",
//						"outlet": {
//							"jaxId": "1IL31IG750",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL31G3SS0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IL31G3SS0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1115",
//						"y": "85",
//						"outlet": {
//							"jaxId": "1IL31IG751",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ45B6Q50"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1IL31NK370",
//					"attrs": {
//						"id": "goto5",
//						"viewName": "",
//						"label": "",
//						"x": "340",
//						"y": "85",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"seg": "1IL0GMG890",
//						"outlet": {
//							"jaxId": "1IL31NTA80",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				}
//			]
//		},
//		"desc": "这是通过huggingface下载模型的智能体，如果需要下载模型，请使用本智能体，而不是直接通过命令行下载。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}