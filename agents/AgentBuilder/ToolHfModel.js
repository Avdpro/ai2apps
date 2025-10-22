//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IJ44VPHU0MoreImports*/
/*}#1IJ44VPHU0MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
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
	let FixArgs,Download,Check,Switch,Install,CheckDownload,tip1,tip2,tip3,SetMirror,InputToken,CheckToken,FormatError,TryAgain,AbortDownload,CheckAgain,tip4,asktoken,tip5,InputModel,CheckInstall,Success,Install2,CheckInstall2,Success2,LLMCheckDownload,CheckError,CheckModelDownload,output,errortoken,Retry,LocalPath,DownloadLocalPath,AskRetry;
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
		/*
		if (localPath) {
			command += ` --local-dir ${localPath}`;
		}
		*/
		
		args['commands']= [`rm -rf ~/.cache/huggingface/hub/models--${model.split("/")[0]}--${model.split("/")[1]}`,command];
		/*}#1IJ45B6Q50PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IJ45B6Q50PostCodes*/
		/*}#1IJ45B6Q50PostCodes*/
		return {seg:LLMCheckDownload,result:(result),preSeg:"1IJ45B6Q50",outlet:"1IJ45SKMC0"};
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
			return {seg:Download,result:(input),preSeg:"1IL0EEQ1N0",outlet:"1IL0EJLHS0"};
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
		return {seg:CheckInstall,result:(result),preSeg:"1IL0F6R660",outlet:"1IL0F8C2V0"};
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
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content="LocalEntryNotFoundError: An error happened while trying to locate the file原因：本地缓存缺失且网络连接失败、token权限问题解决方案：1、检查网络连接，尝试通过镜像站重试下载。2、手动下载模型文件并放置到缓存目录（默认路径为 ~/.cache/huggingface/hub）3、检查token是否是read权限";
		session.addChatText(role,content,opts);
		return {result:result};
	};
	tip1.jaxId="1IL0GBNQD0"
	tip1.url="tip1@"+agentURL
	
	segs["tip2"]=tip2=async function(input){//:1IL0GCLFE0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content="下载需登录的私有模型失败原因：未提供有效 Token 或 Token 权限不足。解决方案：1、在命令中添加 --token hf_xxx 参数（hf_xxx 为官网生成的 Token）";
		session.addChatText(role,content,opts);
		return {result:result};
	};
	tip2.jaxId="1IL0GCLFE0"
	tip2.url="tip2@"+agentURL
	
	segs["tip3"]=tip3=async function(input){//:1IL0GD2U40
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content="ConnectionError: Couldn't reach ... on the Hub (SSLError)\n原因：代理配置错误或 SSL 证书问题。\n解决方案：\n1、检查代理设置是否正确（如 export all_proxy=socks5://192.168.1.110:1080）。\n2、若使用科学上网工具，确保 Python 的 urllib3 库代理配置正确";
		session.addChatText(role,content,opts);
		return {seg:TryAgain,result:(result),preSeg:"1IL0GD2U40",outlet:"1IL0GH5VV2"};
	};
	tip3.jaxId="1IL0GD2U40"
	tip3.url="tip3@"+agentURL
	
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
		return {seg:Retry,result:(result),preSeg:"1IL0GQNI50",outlet:"1IL0GT9GV1"};
	};
	SetMirror.jaxId="1IL0GQNI50"
	SetMirror.url="SetMirror@"+agentURL
	
	segs["InputToken"]=InputToken=async function(input){//:1IL0H9PLO0
		let tip=("");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let allowEmpty=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		/*#{1IL0H9PLO0PreCodes*/
		/*}#1IL0H9PLO0PreCodes*/
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
		/*#{1IL0H9PLO0PostCodes*/
		token=result;
		/*}#1IL0H9PLO0PostCodes*/
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
		/*#{1IL0HAJHS0Post*/
		/*}#1IL0HAJHS0Post*/
		return {seg:Retry,result:(result),preSeg:"1IL0HAJHS0",outlet:"1IL0HIUAD2"};
	};
	CheckToken.jaxId="1IL0HAJHS0"
	CheckToken.url="CheckToken@"+agentURL
	
	segs["FormatError"]=FormatError=async function(input){//:1IL0HDTOC0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content="格式错误，请输入hf_xxx格式的token";
		session.addChatText(role,content,opts);
		return {seg:InputToken,result:(result),preSeg:"1IL0HDTOC0",outlet:"1IL0HIUAD3"};
	};
	FormatError.jaxId="1IL0HDTOC0"
	FormatError.url="FormatError@"+agentURL
	
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
			return {result:result};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {result:result};
		}else if(item.code===1){
			return {seg:AbortDownload,result:(result),preSeg:"1IL0I2CDI0",outlet:"1IL0I2CCB1"};
		}
		return {result:result};
	};
	TryAgain.jaxId="1IL0I2CDI0"
	TryAgain.url="TryAgain@"+agentURL
	
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
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content="你的访问权限被作者拒绝了，请重新检查权限或更换token。";
		session.addChatText(role,content,opts);
		return {seg:TryAgain,result:(result),preSeg:"1IL2R1CUR0",outlet:"1IL2U3HM80"};
	};
	tip4.jaxId="1IL2R1CUR0"
	tip4.url="tip4@"+agentURL
	
	segs["asktoken"]=asktoken=async function(input){//:1IL2TF5VG0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("当前模型需要官网的token才能下载，请输入hf_xxx格式的token"):("This model requires an official website token for download, please enter the token in the format hf_xxx"));
		session.addChatText(role,content,opts);
		return {seg:InputToken,result:(result),preSeg:"1IL2TF5VG0",outlet:"1IL2U3HM82"};
	};
	asktoken.jaxId="1IL2TF5VG0"
	asktoken.url="asktoken@"+agentURL
	
	segs["tip5"]=tip5=async function(input){//:1IL30V13H0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content="Respository Not Found for url\n原因：模型不存在\n解决方案：\n1、检查模型名称是否正确";
		session.addChatText(role,content,opts);
		return {seg:TryAgain,result:(result),preSeg:"1IL30V13H0",outlet:"1IL314B490"};
	};
	tip5.jaxId="1IL30V13H0"
	tip5.url="tip5@"+agentURL
	
	segs["InputModel"]=InputModel=async function(input){//:1IL31AS6C0
		let tip=((($ln==="CN")?("模型不存在，请重新输入模型名称，通常格式为：<username>/<model_name>"):("Model does not exist, please enter the model name again, usually in the format: <username>/<model_name>")));
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let allowEmpty=(false)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		/*#{1IL31AS6C0PreCodes*/
		/*}#1IL31AS6C0PreCodes*/
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
		/*#{1IL31AS6C0PostCodes*/
		model=result;
		/*}#1IL31AS6C0PostCodes*/
		return {seg:Retry,result:(result),preSeg:"1IL31AS6C0",outlet:"1IL31DE6K0"};
	};
	InputModel.jaxId="1IL31AS6C0"
	InputModel.url="InputModel@"+agentURL
	
	segs["CheckInstall"]=CheckInstall=async function(input){//:1J216PG2G0
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=CheckInstall.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"用户正在通过pip安装huggingface-hub库，请根据终端的输出判断是否安装成功，输出json格式，{\"success\":true/false}"},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("CheckInstall@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:Success,result:(result),preSeg:"1J216PG2G0",outlet:"1J216R8ML0"};
	};
	CheckInstall.jaxId="1J216PG2G0"
	CheckInstall.url="CheckInstall@"+agentURL
	
	segs["Success"]=Success=async function(input){//:1J216V91J0
		let result=input;
		if(input.success){
			return {seg:Download,result:(input),preSeg:"1J216V91J0",outlet:"1J2172D750"};
		}
		return {seg:Install2,result:(result),preSeg:"1J216V91J0",outlet:"1J2172D751"};
	};
	Success.jaxId="1J216V91J0"
	Success.url="Success@"+agentURL
	
	segs["Install2"]=Install2=async function(input){//:1J2173H5L0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="pip install huggingface-hub -i https://pypi.tuna.tsinghua.edu.cn/simple";
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:CheckInstall2,result:(result),preSeg:"1J2173H5L0",outlet:"1J2174N0N0"};
	};
	Install2.jaxId="1J2173H5L0"
	Install2.url="Install2@"+agentURL
	
	segs["CheckInstall2"]=CheckInstall2=async function(input){//:1J2176E080
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=CheckInstall2.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"用户正在通过pip安装huggingface-hub库，请根据终端的输出判断是否安装成功，输出json格式，{\"success\":true/false}"},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("CheckInstall2@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:Success2,result:(result),preSeg:"1J2176E080",outlet:"1J2176E083"};
	};
	CheckInstall2.jaxId="1J2176E080"
	CheckInstall2.url="CheckInstall2@"+agentURL
	
	segs["Success2"]=Success2=async function(input){//:1J2176SFI0
		let result=input;
		/*#{1J2176SFI0Start*/
		/*}#1J2176SFI0Start*/
		if(input.success){
			return {seg:Download,result:(input),preSeg:"1J2176SFI0",outlet:"1J2176SFI4"};
		}
		/*#{1J2176SFI0Post*/
		result="break";
		/*}#1J2176SFI0Post*/
		return {result:result};
	};
	Success2.jaxId="1J2176SFI0"
	Success2.url="Success2@"+agentURL
	
	segs["LLMCheckDownload"]=LLMCheckDownload=async function(input){//:1J21KPET10
		let prompt;
		let result;
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=LLMCheckDownload.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`你是一个专门分析 Hugging Face CLI 下载模型终端输出的助手。收到用户提供的一段终端输出（纯文本），请你完成以下步骤：

1. 判断本次下载是否成功。  

2. 如果失败，请根据终端输出内容，匹配以下四种错误类型之一：  
   - network_interruption：网络中断、连接超时、DNS 失败等，提示“重试下载”；  
   - requires_token：模型私有，需要登录 token，但用户未设置任何 token；  
   - invalid_token：检测到用户已设置 token，但 token 无效（返回 401/403 授权失败等）；  
   - add_mirror：网络环境受限，需要添加 HF 镜像源（如国内环境）。
   - no_model：Repository not found，模型不存在。

3. 生成并返回一个 JSON 对象，格式如下：

{
  "success": true|false,
  "error_type": null|"network_interruption"|"requires_token"|"invalid_token"|"add_mirror"|"no_model",
  "suggestion": "针对错误的操作建议文字"
}


* 当 success 为 true 时，error_type 和 suggestion 均应为 null。

* 当 success 为 false 时，error_type 必须是上述四种之一，suggestion 为对应的具体操作提示。

请严格按照上述流程和 JSON 模板输出，且不要额外输出其他内容。
` + (($ln==="CN")?("用中文输出。"):("Output in English."))

},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("LLMCheckDownload@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:CheckModelDownload,result:(result),preSeg:"1J21KPET10",outlet:"1J21KQ0HG0"};
	};
	LLMCheckDownload.jaxId="1J21KPET10"
	LLMCheckDownload.url="LLMCheckDownload@"+agentURL
	
	segs["CheckError"]=CheckError=async function(input){//:1J21L9QU90
		let result=input;
		if(input.error_type==="network_interruption"){
			return {seg:AskRetry,result:(input),preSeg:"1J21L9QU90",outlet:"1J21LBGBI0"};
		}
		if(input.error_type==="requires_token"){
			return {seg:asktoken,result:(input),preSeg:"1J21L9QU90",outlet:"1J21LCD6G0"};
		}
		if(input.error_type==="invalid_token"){
			return {seg:errortoken,result:(input),preSeg:"1J21L9QU90",outlet:"1J21LCM7O0"};
		}
		if(input.error_type==="add_mirror"){
			return {seg:SetMirror,result:(input),preSeg:"1J21L9QU90",outlet:"1J21LD8C80"};
		}
		if(input.error_type==="no_model"){
			return {seg:InputModel,result:(input),preSeg:"1J21L9QU90",outlet:"1J21LQ2BJ0"};
		}
		return {seg:LocalPath,result:(result),preSeg:"1J21L9QU90",outlet:"1J21LC4CC1"};
	};
	CheckError.jaxId="1J21L9QU90"
	CheckError.url="CheckError@"+agentURL
	
	segs["CheckModelDownload"]=CheckModelDownload=async function(input){//:1J21LHRVE0
		let result=input;
		if(input.success){
			return {result:input};
		}
		return {seg:output,result:(result),preSeg:"1J21LHRVE0",outlet:"1J21LNBML1"};
	};
	CheckModelDownload.jaxId="1J21LHRVE0"
	CheckModelDownload.url="CheckModelDownload@"+agentURL
	
	segs["output"]=output=async function(input){//:1J21LJ1QU0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=input.suggestion;
		session.addChatText(role,content,opts);
		return {seg:CheckError,result:(result),preSeg:"1J21LJ1QU0",outlet:"1J21LNBMM0"};
	};
	output.jaxId="1J21LJ1QU0"
	output.url="output@"+agentURL
	
	segs["errortoken"]=errortoken=async function(input){//:1J21LLQ1U0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("当前token无效或权限不足，请检查后输入新的token"):("The current token is invalid or lacks sufficient permissions, please check and input a new token"));
		session.addChatText(role,content,opts);
		return {seg:InputToken,result:(result),preSeg:"1J21LLQ1U0",outlet:"1J21LNBMM1"};
	};
	errortoken.jaxId="1J21LLQ1U0"
	errortoken.url="errortoken@"+agentURL
	
	segs["Retry"]=Retry=async function(input){//:1J21LTNVA0
		let result=input;
		return {seg:Download,result:result,preSeg:"1IJ45B6Q50",outlet:"1J21LTV680"};
	
	};
	Retry.jaxId="1IJ45B6Q50"
	Retry.url="Retry@"+agentURL
	
	segs["LocalPath"]=LocalPath=async function(input){//:1J21M30ET0
		let result=input;
		if(localPath){
			return {seg:DownloadLocalPath,result:(input),preSeg:"1J21M30ET0",outlet:"1J21M4JC90"};
		}
		return {result:result};
	};
	LocalPath.jaxId="1J21M30ET0"
	LocalPath.url="LocalPath@"+agentURL
	
	segs["DownloadLocalPath"]=DownloadLocalPath=async function(input){//:1J21M45510
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="";
		args['options']="";
		/*#{1J21M45510PreCodes*/
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
		/*}#1J21M45510PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1J21M45510PostCodes*/
		/*}#1J21M45510PostCodes*/
		return {result:result};
	};
	DownloadLocalPath.jaxId="1J21M45510"
	DownloadLocalPath.url="DownloadLocalPath@"+agentURL
	
	segs["AskRetry"]=AskRetry=async function(input){//:1J5QL7MF00
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
		
		if(silent){
			result="";
			return {seg:Download,result:(result),preSeg:"1J5QL7MF00",outlet:"1J5QL7ME90"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:Download,result:(result),preSeg:"1J5QL7MF00",outlet:"1J5QL7ME90"};
		}else if(item.code===1){
			return {result:result};
		}
		return {result:result};
	};
	AskRetry.jaxId="1J5QL7MF00"
	AskRetry.url="AskRetry@"+agentURL
	
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
	},
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
//						"x": "-565",
//						"y": "15",
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
//							"linkedSeg": "1J21KPET10"
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
//									"linkedSeg": "1IJ45B6Q50"
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
//						"x": "-545",
//						"y": "290",
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
//							"linkedSeg": "1J216PG2G0"
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
//						"y": "225",
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
//						"y": "225",
//						"outlet": {
//							"jaxId": "1IL0GTRD91",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ45B6Q50"
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
//						"x": "260",
//						"y": "-795",
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
//						"x": "640",
//						"y": "-925",
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
//						"channel": "Chat",
//						"text": "LocalEntryNotFoundError: An error happened while trying to locate the file原因：本地缓存缺失且网络连接失败、token权限问题解决方案：1、检查网络连接，尝试通过镜像站重试下载。2、手动下载模型文件并放置到缓存目录（默认路径为 ~/.cache/huggingface/hub）3、检查token是否是read权限",
//						"outlet": {
//							"jaxId": "1IL0GH5VV0",
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
//					"jaxId": "1IL0GCLFE0",
//					"attrs": {
//						"id": "tip2",
//						"viewName": "",
//						"label": "",
//						"x": "640",
//						"y": "-835",
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
//						"channel": "Chat",
//						"text": "下载需登录的私有模型失败原因：未提供有效 Token 或 Token 权限不足。解决方案：1、在命令中添加 --token hf_xxx 参数（hf_xxx 为官网生成的 Token）",
//						"outlet": {
//							"jaxId": "1IL0GH5VV1",
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
//					"jaxId": "1IL0GD2U40",
//					"attrs": {
//						"id": "tip3",
//						"viewName": "",
//						"label": "",
//						"x": "640",
//						"y": "-770",
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
//						"channel": "Chat",
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
//					"def": "Bash",
//					"jaxId": "1IL0GQNI50",
//					"attrs": {
//						"id": "SetMirror",
//						"viewName": "",
//						"label": "",
//						"x": "715",
//						"y": "50",
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
//							"linkedSeg": "1J21LTNVA0"
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
//						"x": "965",
//						"y": "-65",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
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
//						"allowEmpty": "false",
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
//						"x": "1200",
//						"y": "-65",
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
//							"linkedSeg": "1J21LTNVA0"
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
//						"x": "1440",
//						"y": "-110",
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
//						"channel": "Chat",
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
//					"def": "askMenu",
//					"jaxId": "1IL0I2CDI0",
//					"attrs": {
//						"id": "TryAgain",
//						"viewName": "",
//						"label": "",
//						"x": "840",
//						"y": "-590",
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
//									}
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
//					"def": "code",
//					"jaxId": "1IL0I5LN40",
//					"attrs": {
//						"id": "AbortDownload",
//						"viewName": "",
//						"label": "",
//						"x": "1075",
//						"y": "-510",
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
//						"x": "655",
//						"y": "-430",
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
//						"x": "640",
//						"y": "-680",
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
//						"channel": "Chat",
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
//					"def": "output",
//					"jaxId": "1IL2TF5VG0",
//					"attrs": {
//						"id": "asktoken",
//						"viewName": "",
//						"label": "",
//						"x": "715",
//						"y": "-65",
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
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "This model requires an official website token for download, please enter the token in the format hf_xxx",
//							"localize": {
//								"EN": "This model requires an official website token for download, please enter the token in the format hf_xxx",
//								"CN": "当前模型需要官网的token才能下载，请输入hf_xxx格式的token"
//							},
//							"localizable": true
//						},
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
//						"x": "1600",
//						"y": "-235",
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
//						"x": "990",
//						"y": "-235",
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
//					"def": "output",
//					"jaxId": "1IL30V13H0",
//					"attrs": {
//						"id": "tip5",
//						"viewName": "",
//						"label": "",
//						"x": "640",
//						"y": "-595",
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
//						"channel": "Chat",
//						"text": "Respository Not Found for url\n原因：模型不存在\n解决方案：\n1、检查模型名称是否正确",
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
//					"def": "askChat",
//					"jaxId": "1IL31AS6C0",
//					"attrs": {
//						"id": "InputModel",
//						"viewName": "",
//						"label": "",
//						"x": "715",
//						"y": "115",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
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
//						"tip": {
//							"type": "string",
//							"valText": "Model does not exist, please enter the model name again, usually in the format: <username>/<model_name>",
//							"localize": {
//								"EN": "Model does not exist, please enter the model name again, usually in the format: <username>/<model_name>",
//								"CN": "模型不存在，请重新输入模型名称，通常格式为：<username>/<model_name>"
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
//							"jaxId": "1IL31DE6K0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J21LVCD40"
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
//						"x": "-5",
//						"y": "225",
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
//					"def": "callLLM",
//					"jaxId": "1J216PG2G0",
//					"attrs": {
//						"id": "CheckInstall",
//						"viewName": "",
//						"label": "",
//						"x": "-345",
//						"y": "290",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J216R8MR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J216R8MR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "用户正在通过pip安装huggingface-hub库，请根据终端的输出判断是否安装成功，输出json格式，{\"success\":true/false}",
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
//							"jaxId": "1J216R8ML0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J216V91J0"
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J216V91J0",
//					"attrs": {
//						"id": "Success",
//						"viewName": "",
//						"label": "",
//						"x": "-125",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J2172D790",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J2172D7A0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J2172D751",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J2173H5L0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J2172D750",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J2172D7A1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J2172D7A2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.success"
//									},
//									"linkedSeg": "1IL31BFM60"
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
//					"jaxId": "1J2173H5L0",
//					"attrs": {
//						"id": "Install2",
//						"viewName": "",
//						"label": "",
//						"x": "95",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J2174N100",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J2174N101",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "pip install huggingface-hub -i https://pypi.tuna.tsinghua.edu.cn/simple",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J2174N0N0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J2176E080"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1J2176E080",
//					"attrs": {
//						"id": "CheckInstall2",
//						"viewName": "",
//						"label": "",
//						"x": "290",
//						"y": "305",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J2176E081",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J2176E082",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "用户正在通过pip安装huggingface-hub库，请根据终端的输出判断是否安装成功，输出json格式，{\"success\":true/false}",
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
//							"jaxId": "1J2176E083",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J2176SFI0"
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J2176SFI0",
//					"attrs": {
//						"id": "Success2",
//						"viewName": "",
//						"label": "",
//						"x": "515",
//						"y": "305",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J2176SFI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J2176SFI2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J2176SFI3",
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
//									"jaxId": "1J2176SFI4",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J2176SFI5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J2176SFI6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.success"
//									},
//									"linkedSeg": "1J21776HH0"
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
//					"jaxId": "1J21776HH0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "660",
//						"y": "230",
//						"outlet": {
//							"jaxId": "1J2177FN70",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IL31BFM60"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1J21KPET10",
//					"attrs": {
//						"id": "LLMCheckDownload",
//						"viewName": "",
//						"label": "",
//						"x": "-345",
//						"y": "15",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J21KQ0HM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J21KQ0HM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "#`你是一个专门分析 Hugging Face CLI 下载模型终端输出的助手。收到用户提供的一段终端输出（纯文本），请你完成以下步骤：\n\n1. 判断本次下载是否成功。  \n\n2. 如果失败，请根据终端输出内容，匹配以下四种错误类型之一：  \n   - network_interruption：网络中断、连接超时、DNS 失败等，提示“重试下载”；  \n   - requires_token：模型私有，需要登录 token，但用户未设置任何 token；  \n   - invalid_token：检测到用户已设置 token，但 token 无效（返回 401/403 授权失败等）；  \n   - add_mirror：网络环境受限，需要添加 HF 镜像源（如国内环境）。\n   - no_model：Repository not found，模型不存在。\n\n3. 生成并返回一个 JSON 对象，格式如下：\n\n{\n  \"success\": true|false,\n  \"error_type\": null|\"network_interruption\"|\"requires_token\"|\"invalid_token\"|\"add_mirror\"|\"no_model\",\n  \"suggestion\": \"针对错误的操作建议文字\"\n}\n\n\n* 当 success 为 true 时，error_type 和 suggestion 均应为 null。\n\n* 当 success 为 false 时，error_type 必须是上述四种之一，suggestion 为对应的具体操作提示。\n\n请严格按照上述流程和 JSON 模板输出，且不要额外输出其他内容。\n` + (($ln===\"CN\")?(\"用中文输出。\"):(\"Output in English.\"))\n\n",
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
//							"jaxId": "1J21KQ0HG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J21LHRVE0"
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
//						"formatDef": "\"\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J21L9QU90",
//					"attrs": {
//						"id": "CheckError",
//						"viewName": "",
//						"label": "",
//						"x": "355",
//						"y": "30",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J21LC4CH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J21LC4CH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J21LC4CC1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J21M30ET0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J21LBGBI0",
//									"attrs": {
//										"id": "Network_Interruption",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J21LC4CH4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J21LC4CH5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.error_type===\"network_interruption\""
//									},
//									"linkedSeg": "1J5QL7MF00"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J21LCD6G0",
//									"attrs": {
//										"id": "Requires_Token",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J21LDIUT0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J21LDIUT1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.error_type===\"requires_token\""
//									},
//									"linkedSeg": "1IL2TF5VG0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J21LCM7O0",
//									"attrs": {
//										"id": "Invalid_Token",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J21LDIUT2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J21LDIUT3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.error_type===\"invalid_token\""
//									},
//									"linkedSeg": "1J21LLQ1U0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J21LD8C80",
//									"attrs": {
//										"id": "Add_Mirror",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J21LDIUT4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J21LDIUT5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.error_type===\"add_mirror\""
//									},
//									"linkedSeg": "1IL0GQNI50"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J21LQ2BJ0",
//									"attrs": {
//										"id": "No_Model",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J21LQN5I0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J21LQN5I1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.error_type===\"no_model\""
//									},
//									"linkedSeg": "1IL31AS6C0"
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
//					"jaxId": "1J21LHRVE0",
//					"attrs": {
//						"id": "CheckModelDownload",
//						"viewName": "",
//						"label": "",
//						"x": "-105",
//						"y": "15",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J21LNBMU0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J21LNBMU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J21LNBML1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J21LJ1QU0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J21LNBML0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J21LNBMU2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J21LNBMU3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.success"
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
//					"jaxId": "1J21LJ1QU0",
//					"attrs": {
//						"id": "output",
//						"viewName": "",
//						"label": "",
//						"x": "145",
//						"y": "30",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J21LNBMU4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J21LNBMU5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input.suggestion",
//						"outlet": {
//							"jaxId": "1J21LNBMM0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J21L9QU90"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J21LLQ1U0",
//					"attrs": {
//						"id": "errortoken",
//						"viewName": "",
//						"label": "",
//						"x": "715",
//						"y": "-10",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J21LNBMU6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J21LNBMU7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "The current token is invalid or lacks sufficient permissions, please check and input a new token",
//							"localize": {
//								"EN": "The current token is invalid or lacks sufficient permissions, please check and input a new token",
//								"CN": "当前token无效或权限不足，请检查后输入新的token"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J21LNBMM1",
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
//					"def": "jumper",
//					"jaxId": "1J21LTNVA0",
//					"attrs": {
//						"id": "Retry",
//						"viewName": "",
//						"label": "",
//						"x": "1440",
//						"y": "50",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1IJ45B6Q50",
//						"outlet": {
//							"jaxId": "1J21LTV680",
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
//					"jaxId": "1J21LVCD40",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1330",
//						"y": "115",
//						"outlet": {
//							"jaxId": "1J21M0NOU0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J21LTNVA0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J21LVVCF0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "295",
//						"y": "-135",
//						"outlet": {
//							"jaxId": "1J21M0NOU1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J21M07NE0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J21M07NE0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "-530",
//						"y": "-130",
//						"outlet": {
//							"jaxId": "1J21M0NOU2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ45B6Q50"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J21M30ET0",
//					"attrs": {
//						"id": "LocalPath",
//						"viewName": "",
//						"label": "",
//						"x": "715",
//						"y": "185",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J21M4JCD0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J21M4JCD1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J21M4JC91",
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
//									"jaxId": "1J21M4JC90",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J21M4JCD2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J21M4JCD3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#localPath"
//									},
//									"linkedSeg": "1J21M45510"
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
//					"jaxId": "1J21M45510",
//					"attrs": {
//						"id": "DownloadLocalPath",
//						"viewName": "",
//						"label": "",
//						"x": "935",
//						"y": "170",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J21M4JCD4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J21M4JCD5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J21M4JC92",
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
//					"def": "askMenu",
//					"jaxId": "1J5QL7MF00",
//					"attrs": {
//						"id": "AskRetry",
//						"viewName": "",
//						"label": "",
//						"x": "715",
//						"y": "-185",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "Please confirm",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1J5QLB4PD0",
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
//									"jaxId": "1J5QL7ME90",
//									"attrs": {
//										"id": "Item1",
//										"desc": "输出节点。",
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
//											"jaxId": "1J5QLB4PH0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J5QLB4PH1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1J5QLBOO20"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J5QL7MEA0",
//									"attrs": {
//										"id": "Item2",
//										"desc": "输出节点。",
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
//											"jaxId": "1J5QLB4PH2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J5QLB4PH3",
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
//					"def": "connector",
//					"jaxId": "1J5QLBOO20",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "860",
//						"y": "-295",
//						"outlet": {
//							"jaxId": "1J5QLC2560",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J5QLBTA80"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J5QLBTA80",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "395",
//						"y": "-295",
//						"outlet": {
//							"jaxId": "1J5QLC2561",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J21LVVCF0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是通过huggingface下载模型的智能体，如果需要下载模型，请使用本智能体，而不是直接通过命令行下载。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": ""
//	}
//}