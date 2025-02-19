//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IG65D1UE0MoreImports*/
import AATask from "./Task.js";
import fsp from 'fs/promises';
/*}#1IG65D1UE0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
/*#{1IG65D1UE0StartDoc*/
//----------------------------------------------------------------------------
const dirPathExists = async (path) => {
	try {
		const stats = await fsp.stat(path);
		return true;
	} catch (error) {
		if (error.code === 'ENOENT') {
			return false;  // 目录不存在
		}
		throw error;  // 其他错误抛出
	}
};
//----------------------------------------------------------------------------
function compressMarkdownImageLinks(markdownText) {
	if (typeof markdownText !== 'string') {
		throw new TypeError('Input must be a string');
	}
	const compressedText = markdownText.replace(/(!\[.*?\])\((.*?)\)/g, '$1(...)');
	return compressedText;
}
/*}#1IG65D1UE0StartDoc*/
//----------------------------------------------------------------------------
let PrjSetupPrjDir=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let CheckDirPath,CheckDirName,FixName,CheckDirUsed,GenNewName,MakeDir,GitDownload,CheckDownLoad,CheckPython,DirOK,AskRetry,ShowGitError,GitFailed,ClearDir,CheckPythonEnv,LoadReadme,PreviewPrj,TipPreview,ShowSummary,AbortSetup,AskSetup;
	let project=globalContext.project;
	let dirName=project.name;
	let dirPath="";
	let env=globalContext.env;
	let task=undefined;
	
	/*#{1IG65D1UE0LocalVals*/
	let orgName;
	let nextNameIdx=1;
	async function addLog(log,notify=true){
		if(task){
			task.log(log,notify);
		}
	}
	/*}#1IG65D1UE0LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IG65D1UE0ParseArgs*/
		/*}#1IG65D1UE0ParseArgs*/
	}
	
	/*#{1IG65D1UE0PreContext*/
	/*}#1IG65D1UE0PreContext*/
	context={};
	/*#{1IG65D1UE0PostContext*/
	/*}#1IG65D1UE0PostContext*/
	let agent,segs={};
	segs["CheckDirPath"]=CheckDirPath=async function(input){//:1IGNGQ4NK0
		let result=input;
		/*#{1IGNGQ4NK0Start*/
		dirPath=project.dirPath;
		task=new AATask(session,"创建工程目录");
		/*}#1IGNGQ4NK0Start*/
		if(!dirPath){
			return {seg:CheckDirName,result:(input),preSeg:"1IGNGQ4NK0",outlet:"1IGNGVIRM0"};
		}
		/*#{1IGNGQ4NK0Post*/
		dirName=pathLib.basename(dirPath);
		project.dirName=dirName;
		/*}#1IGNGQ4NK0Post*/
		return {seg:LoadReadme,result:(result),preSeg:"1IGNGQ4NK0",outlet:"1IGNGVIRM1"};
	};
	CheckDirPath.jaxId="1IGNGQ4NK0"
	CheckDirPath.url="CheckDirPath@"+agentURL
	
	segs["CheckDirName"]=CheckDirName=async function(input){//:1IG65G1DJ0
		let result=input;
		/*#{1IG65G1DJ0Start*/
		const validDirRegex = /^(?!^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$)(?!.*[<>:"/\\|?*])(?!\s)(?!.*\s$)(?!.*\.$)[^\x00-\x1F]{1,255}$/;
		let nameOK=false;
		nameOK=validDirRegex.test(dirName)
		/*}#1IG65G1DJ0Start*/
		if(nameOK){
			/*#{1IG65HVEH0Codes*/
			addLog(`Dir name: "${dirName}" checked.`);
			/*}#1IG65HVEH0Codes*/
			return {seg:CheckDirUsed,result:(input),preSeg:"1IG65G1DJ0",outlet:"1IG65HVEH0"};
		}
		/*#{1IG65G1DJ0Post*/
		addLog(`Dir name: "${dirName}" need fix.`);
		/*}#1IG65G1DJ0Post*/
		return {seg:FixName,result:(result),preSeg:"1IG65G1DJ0",outlet:"1IG65HVEH1"};
	};
	CheckDirName.jaxId="1IG65G1DJ0"
	CheckDirName.url="CheckDirName@"+agentURL
	
	segs["FixName"]=FixName=async function(input){//:1IG65QUQE0
		let prompt;
		let result=null;
		/*#{1IG65QUQE0Input*/
		/*}#1IG65QUQE0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"$fast",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=FixName.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
你是一个修正要创建的目录名的AI。
用户的输入是一个不合法的目录名，不合法的原因可能是包含非法的字符或者格式错我。
你输出一个JSON对象，里面包括你修改后的，尽量保持原有目录名意义的，合法目录名。
例如输入：input/prj
返回：
{
	"fixed":"input_prj"
}
返回JSON的 "fixed" 属性是你修正后的目录名。
`},
		];
		/*#{1IG65QUQE0PrePrompt*/
		/*}#1IG65QUQE0PrePrompt*/
		prompt=dirName;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		/*#{1IG65QUQE0PreCall*/
		/*}#1IG65QUQE0PreCall*/
		result=(result===null)?(await session.callSegLLM("FixName@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IG65QUQE0PostCall*/
		dirName=result.fixed;
		addLog(`Fixed dir name: "${dirName}".`);
		/*}#1IG65QUQE0PostCall*/
		return {seg:CheckDirName,result:(result),preSeg:"1IG65QUQE0",outlet:"1IG65SUOF0"};
	};
	FixName.jaxId="1IG65QUQE0"
	FixName.url="FixName@"+agentURL
	
	segs["CheckDirUsed"]=CheckDirUsed=async function(input){//:1IG668F5S0
		let result=input;
		/*#{1IG668F5S0Start*/
		let pathUsed;
		if(!orgName){
			orgName=dirName;
		}
		dirPath=pathLib.join(env.rootPath,dirName);
		pathUsed=await dirPathExists(dirPath);
		/*}#1IG668F5S0Start*/
		if(pathUsed){
			/*#{1IG6Q27330Codes*/
			addLog(`Dir ${dirPath} is used.`);
			/*}#1IG6Q27330Codes*/
			return {seg:GenNewName,result:(input),preSeg:"1IG668F5S0",outlet:"1IG6Q27330"};
		}
		/*#{1IG668F5S0Post*/
		addLog(`Dir ${dirPath} is OK.`);
		/*}#1IG668F5S0Post*/
		return {seg:MakeDir,result:(result),preSeg:"1IG668F5S0",outlet:"1IG6Q27331"};
	};
	CheckDirUsed.jaxId="1IG668F5S0"
	CheckDirUsed.url="CheckDirUsed@"+agentURL
	
	segs["GenNewName"]=GenNewName=async function(input){//:1IG66AF3H0
		let result=input
		/*#{1IG66AF3H0Code*/
		let pathUsed;
		do{
			dirName=orgName+(nextNameIdx++);
			dirPath=pathLib.join(env.rootPath,dirName);
			pathUsed=await dirPathExists(dirPath);
		}while(pathUsed);
		addLog(`New dir path: ${dirPath}.`);
		/*}#1IG66AF3H0Code*/
		return {seg:MakeDir,result:(result),preSeg:"1IG66AF3H0",outlet:"1IG6Q27340"};
	};
	GenNewName.jaxId="1IG66AF3H0"
	GenNewName.url="GenNewName@"+agentURL
	
	segs["MakeDir"]=MakeDir=async function(input){//:1IG66C4030
		let result=input
		/*#{1IG66C4030Code*/
		//We don't need 
		await fsp.mkdir(dirPath, { recursive: true });
		addLog(`Dir "${dirPath}" created.`);
		project.progress.push(`项目目录已创建：${dirPath}`);
		/*}#1IG66C4030Code*/
		return {seg:GitDownload,result:(result),preSeg:"1IG66C4030",outlet:"1IG6Q27341"};
	};
	MakeDir.jaxId="1IG66C4030"
	MakeDir.url="MakeDir@"+agentURL
	
	segs["GitDownload"]=GitDownload=async function(input){//:1IG7TP40A0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="";
		args['options']="";
		/*#{1IG7TP40A0PreCodes*/
		addLog(`Download from git: "${project.gitURL}"`);
		args.commands=[
			`cd "${dirPath}"\r`,
			`git clone "${project.gitURL}" .\r`
		];
		/*}#1IG7TP40A0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IG7TP40A0PostCodes*/
		addLog(`Download result:  \n\`\`\`${result}\n\`\`\``);
		/*}#1IG7TP40A0PostCodes*/
		return {seg:CheckDownLoad,result:(result),preSeg:"1IG7TP40A0",outlet:"1IG7TPPI80"};
	};
	GitDownload.jaxId="1IG7TP40A0"
	GitDownload.url="GitDownload@"+agentURL
	
	segs["CheckDownLoad"]=CheckDownLoad=async function(input){//:1IG66EL0I0
		let result=input;
		/*#{1IG66EL0I0Start*/
		let dirOK=false;
		if(input.indexOf("Receiving objects: 100%")>0 && input.indexOf("Resolving deltas: 100%")){
			dirOK=true
		}
		if(!(await dirPathExists(pathLib.join(dirPath,".git")))){
			dirOK=false;
		}
		/*}#1IG66EL0I0Start*/
		if(!dirOK){
			let output=input;
			return {seg:ShowGitError,result:(output),preSeg:"1IG66EL0I0",outlet:"1IG6Q27343"};
		}
		/*#{1IG66EL0I0Post*/
		project.progress.push(`已从GitHub上下载了最新项目内容。`);
		project.dirPath=dirPath;
		project.dirName=dirName;
		/*}#1IG66EL0I0Post*/
		return {seg:LoadReadme,result:(result),preSeg:"1IG66EL0I0",outlet:"1IG6Q27344"};
	};
	CheckDownLoad.jaxId="1IG66EL0I0"
	CheckDownLoad.url="CheckDownLoad@"+agentURL
	
	segs["CheckPython"]=CheckPython=async function(input){//:1IG66HGKR0
		let result=input;
		/*#{1IG66HGKR0Start*/
		/*}#1IG66HGKR0Start*/
		if(!!project.requirements.python){
			return {seg:CheckPythonEnv,result:(input),preSeg:"1IG66HGKR0",outlet:"1IG6Q27345"};
		}
		/*#{1IG66HGKR0Post*/
		/*}#1IG66HGKR0Post*/
		return {seg:DirOK,result:(result),preSeg:"1IG66HGKR0",outlet:"1IG6Q27346"};
	};
	CheckPython.jaxId="1IG66HGKR0"
	CheckPython.url="CheckPython@"+agentURL
	
	segs["DirOK"]=DirOK=async function(input){//:1IG66KEUC0
		let result=input;
		let opts={};
		let role="assistant";
		let content="项目工程目录准备好了。";
		/*#{1IG66KEUC0PreCodes*/
		/*}#1IG66KEUC0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IG66KEUC0PostCodes*/
		addLog(`Project dir create and git-download success.`);
		result={result:"Finish",content:"Project dir create and git-download success."};
		task.finish("Project dir create and git-download success.");
		/*}#1IG66KEUC0PostCodes*/
		return {result:result};
	};
	DirOK.jaxId="1IG66KEUC0"
	DirOK.url="DirOK@"+agentURL
	
	segs["AskRetry"]=AskRetry=async function(input){//:1IG98UOF60
		let prompt=("是否再试一次Git安装？")||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=("再试一次")||"OK";
		let button2=("终止")||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:ClearDir,result:(result),preSeg:"1IG98UOF60",outlet:"1IG98UOEL0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:ClearDir,result:(result),preSeg:"1IG98UOF60",outlet:"1IG98UOEL0"};
		}
		result=("")||result;
		return {seg:GitFailed,result:(result),preSeg:"1IG98UOF60",outlet:"1IG98UOEL1"};
	
	};
	AskRetry.jaxId="1IG98UOF60"
	AskRetry.url="AskRetry@"+agentURL
	
	segs["ShowGitError"]=ShowGitError=async function(input){//:1IG98VL0V0
		let result=input;
		let opts={};
		let role="assistant";
		let content=`
Git安装失败：
\`\`\`
${input}
\`\`\`
`;
		session.addChatText(role,content,opts);
		return {seg:AskRetry,result:(result),preSeg:"1IG98VL0V0",outlet:"1IG9A1AOV0"};
	};
	ShowGitError.jaxId="1IG98VL0V0"
	ShowGitError.url="ShowGitError@"+agentURL
	
	segs["GitFailed"]=GitFailed=async function(input){//:1IG99A55C0
		let result=input
		/*#{1IG99A55C0Code*/
		addLog(`Abort: git download error.`);
		result={result:"Failed",content:"Git download error."};
		task.abort("git download error.");
		/*}#1IG99A55C0Code*/
		return {result:result};
	};
	GitFailed.jaxId="1IG99A55C0"
	GitFailed.url="GitFailed@"+agentURL
	
	segs["ClearDir"]=ClearDir=async function(input){//:1IG99UC990
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']="rm -r *";
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:GitDownload,result:(result),preSeg:"1IG99UC990",outlet:"1IG9A1AP01"};
	};
	ClearDir.jaxId="1IG99UC990"
	ClearDir.url="ClearDir@"+agentURL
	
	segs["CheckPythonEnv"]=CheckPythonEnv=async function(input){//:1IGB60OJ80
		let result;
		let sourcePath=pathLib.join(basePath,"./PrjCheckCondaEnv.js");
		let arg={};
		/*#{1IGB60OJ80Input*/
		project.dirPath=dirPath;
		project.dirName=dirName;
		/*}#1IGB60OJ80Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IGB60OJ80Output*/
		task.finish("Project dir create, git-download and python-env setup success.");
		/*}#1IGB60OJ80Output*/
		return {result:result};
	};
	CheckPythonEnv.jaxId="1IGB60OJ80"
	CheckPythonEnv.url="CheckPythonEnv@"+agentURL
	
	segs["LoadReadme"]=LoadReadme=async function(input){//:1IHBDHHPD0
		let result=input
		/*#{1IHBDHHPD0Code*/
		//Make sure we have readme:
		if(!project.readme){
			let readme;
			try{
				readme=await fsp.readFile(pathLib.join(project.dirPath,"README.md"),"utf8");
				//TODO: Check readme size before compress?
				readme=compressMarkdownImageLinks(readme);
				if(readme){
					project.readme=readme;
				}
			}catch(err){
				project.readme="";
			}
		}
		/*}#1IHBDHHPD0Code*/
		return {seg:TipPreview,result:(result),preSeg:"1IHBDHHPD0",outlet:"1IHBDKSG30"};
	};
	LoadReadme.jaxId="1IHBDHHPD0"
	LoadReadme.url="LoadReadme@"+agentURL
	
	segs["PreviewPrj"]=PreviewPrj=async function(input){//:1IHBDIFBT0
		let prompt;
		let result=null;
		/*#{1IHBDIFBT0Input*/
		/*}#1IHBDIFBT0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o-mini",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:{
				"type":"json_schema",
				"json_schema":{
					"name":"ResultPreview",
					"schema":{
						"type":"object",
						"description":"",
						"properties":{
							"brief":{
								"type":"string",
								"description":"当前项目的简短总结，包括采用了什么技术，达到什么目的，有什么优势。"
							},
							"aiPrj":{
								"type":"boolean",
								"description":"项目是否是AI相关的"
							},
							"aiType":{
								"type":[
									"string","null"
								],
								"description":"如果是AI项目，属于那种类型",
								"enum":[
									"Chat"," Graphic","Voice","Video","Coding","Others"
								]
							},
							"diffusers":{
								"type":[
									"boolean","null"
								],
								"description":"是否可以用diffusers来执行"
							},
							"diffusersPipeline":{
								"type":"boolean",
								"description":"是否有diffusers pipline"
							},
							"comfyUI":{
								"type":"boolean",
								"description":"是否是一个comfyUI项目"
							},
							"setup":{
								"type":"boolean",
								"description":"本地是否可以部署项目"
							},
							"node":{
								"type":"boolean",
								"description":"项目是否需要node环境"
							},
							"python":{
								"type":"boolean",
								"description":"项目是否需要python环境"
							},
							"warn":{
								"type":"string",
								"description":"部署时可能遇到的问题"
							},
							"error":{
								"type":[
									"string","null"
								],
								"description":"如果不能部署项目，不能部署的错误原因"
							},
							"summary":{
								"type":"string",
								"description":"总结：项目用途，项目技术要点，以及在本地部署项目的可行性总结。"
							}
						},
						"required":[
							"brief","aiPrj","aiType","diffusers","diffusersPipeline","comfyUI","setup","node","python","warn","error","summary"
						],
						"additionalProperties":false
					},
					"strict":true
				}
			}
		};
		let chatMem=PreviewPrj.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
你是一个根据GitHub项目的readme以及本地当前软硬件环境来判断是否可以在本地部署/测试GitHub项目的AI。
---
要部署测试的项目是: ${project.url}

---
当前的环境信息：
${JSON.stringify(globalContext.env,null,"\t")}

---
项目的Readme内容：
\`\`\`markdown
${project.readme}
\`\`\`

---
你必须请用JSON格式返回结果，例如：
{
	"brief":"项目XXX是一个……",
    "aiPrj":true,
    "aiType": "AIGraphic",
    "diffusers": true,
    "diffusersPipeline": true,
    "comfyUI": false,
    "node": true,
    "python": false,
	"setup":true,
    "warn":"当前项目处于Beta阶段，可能并不稳定",
    "error":null,
    "summary":"项目XXX是一个……当前系统可以部署本项目，注意本项目处于测试阶段，可能存在问题。"
}

---
返回JSON属性:
- "brief" {string}: 当前项目的简短总结，包括采用了什么技术，达到什么目的，有什么优势。
- "aiPrj" {bool}: 项目是否是AI相关的
- "aiType" {string}: 如果是AI项目，属于那种类型，可以选择的类型有:
	- "Chat": 用LLM等AI模型聊天的项目
    - "Graphic": 用AI进行图像绘制/识别相关功能的项目
    - "Voice": 与语音相关的AI项目，包括语音识别或语音合成
    - "Video": 用AI生成视频的项目
    - "Others": 其他类型的AI项目
- "diffusers" {bool}: 这个项目是否可以用diffusers来执行
- "diffusersPipeline" {bool}: 如果这个项目可以用diffusers执行，这个项目是否有现成的pipeline可以使用
- "comfyUI" {bool}: 这个项目是用comfyUI进行图像/视频/音频处理的
- "node" {bool}: 部署本项目是否需要Node.js环境
- "python" {bool}: 部署本项目是否需要python环境
- "setup": 如果当前环境可以部署项目，为true；如果当前环境无法部署项目，为false。
- 返回JSON属性 "warn": 部署本项目可能遇到或引起的问题，比如版本不稳定，项目已废弃，可能产生冲突，占用过多空间等。
- 返回JSON属性 "error": 如果本地无法部署该项目，具体的原因描述。
- 返回JSON属性 "summary": 用简洁的语言描述当前项目的用途，用到的技术，总结该项目在本地部署的可行性。
`},
		];
		/*#{1IHBDIFBT0PrePrompt*/
		/*}#1IHBDIFBT0PrePrompt*/
		prompt="请评估并用JSON返回结果";
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		/*#{1IHBDIFBT0PreCall*/
		/*}#1IHBDIFBT0PreCall*/
		result=(result===null)?(await session.callSegLLM("PreviewPrj@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IHBDIFBT0PostCall*/
		project.requirements.node=result.node;
		project.requirements.python=result.python;
		/*}#1IHBDIFBT0PostCall*/
		return {seg:ShowSummary,result:(result),preSeg:"1IHBDIFBT0",outlet:"1IHBDKSG31"};
	};
	PreviewPrj.jaxId="1IHBDIFBT0"
	PreviewPrj.url="PreviewPrj@"+agentURL
	
	segs["TipPreview"]=TipPreview=async function(input){//:1II1BCUQH0
		let result=input;
		let opts={};
		let role="assistant";
		let content=(($ln==="CN")?("项目已下载完毕，评估项目需求。"):("Project downloaded successfully, checking project requirements."));
		session.addChatText(role,content,opts);
		return {seg:PreviewPrj,result:(result),preSeg:"1II1BCUQH0",outlet:"1II1BIEUQ0"};
	};
	TipPreview.jaxId="1II1BCUQH0"
	TipPreview.url="TipPreview@"+agentURL
	
	segs["ShowSummary"]=ShowSummary=async function(input){//:1IJ0RFB3T0
		let result=input;
		let opts={};
		let role="assistant";
		let content=`
### 项目简介
${input.brief}

### 存在问题
${input.error}

### 注意事项
${input.warn}

### 总结：
${input.summary}
`;
		session.addChatText(role,content,opts);
		return {seg:AskSetup,result:(result),preSeg:"1IJ0RFB3T0",outlet:"1IJ0RJS5G0"};
	};
	ShowSummary.jaxId="1IJ0RFB3T0"
	ShowSummary.url="ShowSummary@"+agentURL
	
	segs["AbortSetup"]=AbortSetup=async function(input){//:1IJ0RJ6910
		let result=input
		/*#{1IJ0RJ6910Code*/
		result={result:"Abort",content:"User aborted."};
		/*}#1IJ0RJ6910Code*/
		return {result:result};
	};
	AbortSetup.jaxId="1IJ0RJ6910"
	AbortSetup.url="AbortSetup@"+agentURL
	
	segs["AskSetup"]=AskSetup=async function(input){//:1IJ0SEMOH0
		let prompt=((($ln==="CN")?("是否继续安装/部署本项目？"):("Do you want to continue installing/deploying this project?")))||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("继续设置"):("Continue setup")),code:0},
			{icon:"/~/-tabos/shared/assets/dot.svg",text:(($ln==="CN")?("放弃，终止安装"):("Abort setup")),code:1},
		];
		let result="";
		let item=null;
		
		if(silent){
			result=input;
			return {seg:CheckPython,result:(result),preSeg:"1IJ0SEMOH0",outlet:"1IJ0SEMNU0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			result=(input);
			return {seg:CheckPython,result:(result),preSeg:"1IJ0SEMOH0",outlet:"1IJ0SEMNU0"};
		}else if(item.code===1){
			return {seg:AbortSetup,result:(result),preSeg:"1IJ0SEMOH0",outlet:"1IJ0SEMNU1"};
		}
		return {result:result};
	};
	AskSetup.jaxId="1IJ0SEMOH0"
	AskSetup.url="AskSetup@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"PrjSetupPrjDir",
		url:agentURL,
		autoStart:true,
		jaxId:"1IG65D1UE0",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IG65D1UE0PreEntry*/
			/*}#1IG65D1UE0PreEntry*/
			result={seg:CheckDirPath,"input":input};
			/*#{1IG65D1UE0PostEntry*/
			/*}#1IG65D1UE0PostEntry*/
			return result;
		},
		/*#{1IG65D1UE0MoreAgentAttrs*/
		endChat:async function(result){
			if(task && task.endTask){
				task.endTask();
			}
			return result;
		}
		/*}#1IG65D1UE0MoreAgentAttrs*/
	};
	/*#{1IG65D1UE0PostAgent*/
	/*}#1IG65D1UE0PostAgent*/
	return agent;
};
/*#{1IG65D1UE0ExCodes*/
/*}#1IG65D1UE0ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "PrjSetupPrjDir",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	}
}];
//#CodyExport<<<
/*#{1IG65D1UE0PostDoc*/
/*}#1IG65D1UE0PostDoc*/


export default PrjSetupPrjDir;
export{PrjSetupPrjDir,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IG65D1UE0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IG65D1UE1",
//			"attrs": {
//				"PrjSetupPrjDir": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IG65D1UE7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IG65D1UF0",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IG65D1UF1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IG65D1UF2",
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
//			"jaxId": "1IG65D1UE2",
//			"attrs": {}
//		},
//		"entry": "CheckDIrPath",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IG65D1UE3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IG65D1UE4",
//			"attrs": {
//				"project": {
//					"type": "auto",
//					"valText": "#{name:\"llama3.170b\"}#>globalContext.project"
//				},
//				"dirName": {
//					"type": "string",
//					"valText": "#project.name"
//				},
//				"dirPath": {
//					"type": "string",
//					"valText": ""
//				},
//				"env": {
//					"type": "auto",
//					"valText": "#globalContext.env"
//				},
//				"task": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IG65D1UE5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IG65D1UE6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IGNGQ4NK0",
//					"attrs": {
//						"id": "CheckDirPath",
//						"viewName": "",
//						"label": "",
//						"x": "80",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IGNGVIRR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGNGVIRR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IGNGVIRM1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IGNGUK370"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IGNGVIRM0",
//									"attrs": {
//										"id": "NoPath",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IGNGVIRR2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IGNGVIRR3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!dirPath"
//									},
//									"linkedSeg": "1IG65G1DJ0"
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
//					"jaxId": "1IG65G1DJ0",
//					"attrs": {
//						"id": "CheckDirName",
//						"viewName": "",
//						"label": "",
//						"x": "425",
//						"y": "330",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG65HVEI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG65HVEI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG65HVEH1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IG65QUQE0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IG65HVEH0",
//									"attrs": {
//										"id": "NameOK",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IG65HVEI2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG65HVEI3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#nameOK"
//									},
//									"linkedSeg": "1IG668F5S0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IG65QUQE0",
//					"attrs": {
//						"id": "FixName",
//						"viewName": "",
//						"label": "",
//						"x": "690",
//						"y": "380",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG65T3P50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG65T3P51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "$fast",
//						"system": "#`\n你是一个修正要创建的目录名的AI。\n用户的输入是一个不合法的目录名，不合法的原因可能是包含非法的字符或者格式错我。\n你输出一个JSON对象，里面包括你修改后的，尽量保持原有目录名意义的，合法目录名。\n例如输入：input/prj\n返回：\n{\n\t\"fixed\":\"input_prj\"\n}\n返回JSON的 \"fixed\" 属性是你修正后的目录名。\n`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#dirName",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IG65SUOF0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG666US90"
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
//					"def": "connector",
//					"jaxId": "1IG666US90",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "820",
//						"y": "460",
//						"outlet": {
//							"jaxId": "1IG667TSC0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG6670TK0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IG6670TK0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "455",
//						"y": "460",
//						"outlet": {
//							"jaxId": "1IG667TSC1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG65G1DJ0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IG668F5S0",
//					"attrs": {
//						"id": "CheckDirUsed",
//						"viewName": "",
//						"label": "",
//						"x": "690",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG6Q273C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG6Q273C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG6Q27331",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IG66C4030"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IG6Q27330",
//									"attrs": {
//										"id": "NameUsed",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IG6Q273C2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG6Q273C3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#pathUsed"
//									},
//									"linkedSeg": "1IG66AF3H0"
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
//					"jaxId": "1IG66AF3H0",
//					"attrs": {
//						"id": "GenNewName",
//						"viewName": "",
//						"label": "",
//						"x": "950",
//						"y": "255",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG6Q273C4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG6Q273C5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG6Q27340",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG66C4030"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IG66C4030",
//					"attrs": {
//						"id": "MakeDir",
//						"viewName": "",
//						"label": "",
//						"x": "1185",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG6Q273C6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG6Q273C7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG6Q27341",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG7TP40A0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IG7TP40A0",
//					"attrs": {
//						"id": "GitDownload",
//						"viewName": "",
//						"label": "",
//						"x": "1405",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG7TPPIF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG7TPPIF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "\"\"",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IG7TPPI80",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG66EL0I0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IG66EL0I0",
//					"attrs": {
//						"id": "CheckDownLoad",
//						"viewName": "",
//						"label": "",
//						"x": "1630",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG6Q273C10",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG6Q273C11",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG6Q27344",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IG66H0F40"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IG6Q27343",
//									"attrs": {
//										"id": "Error",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG6Q273C12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG6Q273C13",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!dirOK"
//									},
//									"linkedSeg": "1IG98VL0V0"
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
//					"jaxId": "1IG66H0F40",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1815",
//						"y": "400",
//						"outlet": {
//							"jaxId": "1IG6Q273C14",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG66H6GP0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IG66H6GP0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "975",
//						"y": "400",
//						"outlet": {
//							"jaxId": "1IG6Q273C15",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHBDHHPD0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IG66HGKR0",
//					"attrs": {
//						"id": "CheckPython",
//						"viewName": "",
//						"label": "",
//						"x": "2110",
//						"y": "445",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG6Q273C16",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG6Q273C17",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG6Q27346",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IG66KEUC0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IG6Q27345",
//									"attrs": {
//										"id": "Python",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG6Q273C18",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG6Q273C19",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!project.requirements.python"
//									},
//									"linkedSeg": "1IGB60OJ80"
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
//					"jaxId": "1IG66KEUC0",
//					"attrs": {
//						"id": "DirOK",
//						"viewName": "",
//						"label": "",
//						"x": "2360",
//						"y": "505",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IG6Q273C20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG6Q273C21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "项目工程目录准备好了。",
//						"outlet": {
//							"jaxId": "1IG6Q27350",
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
//					"def": "askConfirm",
//					"jaxId": "1IG98UOF60",
//					"attrs": {
//						"id": "AskRetry",
//						"viewName": "",
//						"label": "",
//						"x": "2135",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "是否再试一次Git安装？",
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IG98UOEL0",
//									"attrs": {
//										"id": "Retry",
//										"desc": "输出节点。",
//										"text": "再试一次",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG9A1AP70",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG9A1AP71",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IG99UC990"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IG98UOEL1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "终止",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IG9A1AP72",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IG9A1AP73",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IG99A55C0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IG98VL0V0",
//					"attrs": {
//						"id": "ShowGitError",
//						"viewName": "",
//						"label": "",
//						"x": "1895",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG9A1AP74",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG9A1AP75",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`\nGit安装失败：\n\\`\\`\\`\n${input}\n\\`\\`\\`\n`",
//						"outlet": {
//							"jaxId": "1IG9A1AOV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG98UOF60"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IG99A55C0",
//					"attrs": {
//						"id": "GitFailed",
//						"viewName": "",
//						"label": "",
//						"x": "2340",
//						"y": "335",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IG9A1AP76",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG9A1AP77",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IG9A1AP00",
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
//					"def": "Bash",
//					"jaxId": "1IG99UC990",
//					"attrs": {
//						"id": "ClearDir",
//						"viewName": "",
//						"label": "",
//						"x": "2340",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IG9A1AP78",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IG9A1AP79",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "rm -r *",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IG9A1AP01",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG9A03VV0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IG9A03VV0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2470",
//						"y": "185",
//						"outlet": {
//							"jaxId": "1IG9A1AP710",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG9A0HBT0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IG9A0HBT0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1430",
//						"y": "185",
//						"outlet": {
//							"jaxId": "1IG9A1AP711",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IG7TP40A0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1IGB60OJ80",
//					"attrs": {
//						"id": "CheckPythonEnv",
//						"viewName": "",
//						"label": "",
//						"x": "2360",
//						"y": "430",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IGB62I5M0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IGB62I5M1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/PrjCheckCondaEnv.js",
//						"argument": "{}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IGB62I5G0",
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
//					"jaxId": "1IGNGUK370",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "325",
//						"y": "505",
//						"outlet": {
//							"jaxId": "1IGNGVIRR4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHBDHHPD0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IHBDHHPD0",
//					"attrs": {
//						"id": "LoadReadme",
//						"viewName": "",
//						"label": "",
//						"x": "950",
//						"y": "505",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHBDKSG60",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHBDKSG61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHBDKSG30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II1BCUQH0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IHBDIFBT0",
//					"attrs": {
//						"id": "PreviewPrj",
//						"viewName": "",
//						"label": "",
//						"x": "1405",
//						"y": "505",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHBDKSG62",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHBDKSG63",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o-mini",
//						"system": "#`\n你是一个根据GitHub项目的readme以及本地当前软硬件环境来判断是否可以在本地部署/测试GitHub项目的AI。\n---\n要部署测试的项目是: ${project.url}\n\n---\n当前的环境信息：\n${JSON.stringify(globalContext.env,null,\"\\t\")}\n\n---\n项目的Readme内容：\n\\`\\`\\`markdown\n${project.readme}\n\\`\\`\\`\n\n---\n你必须请用JSON格式返回结果，例如：\n{\n\t\"brief\":\"项目XXX是一个……\",\n    \"aiPrj\":true,\n    \"aiType\": \"AIGraphic\",\n    \"diffusers\": true,\n    \"diffusersPipeline\": true,\n    \"comfyUI\": false,\n    \"node\": true,\n    \"python\": false,\n\t\"setup\":true,\n    \"warn\":\"当前项目处于Beta阶段，可能并不稳定\",\n    \"error\":null,\n    \"summary\":\"项目XXX是一个……当前系统可以部署本项目，注意本项目处于测试阶段，可能存在问题。\"\n}\n\n---\n返回JSON属性:\n- \"brief\" {string}: 当前项目的简短总结，包括采用了什么技术，达到什么目的，有什么优势。\n- \"aiPrj\" {bool}: 项目是否是AI相关的\n- \"aiType\" {string}: 如果是AI项目，属于那种类型，可以选择的类型有:\n\t- \"Chat\": 用LLM等AI模型聊天的项目\n    - \"Graphic\": 用AI进行图像绘制/识别相关功能的项目\n    - \"Voice\": 与语音相关的AI项目，包括语音识别或语音合成\n    - \"Video\": 用AI生成视频的项目\n    - \"Others\": 其他类型的AI项目\n- \"diffusers\" {bool}: 这个项目是否可以用diffusers来执行\n- \"diffusersPipeline\" {bool}: 如果这个项目可以用diffusers执行，这个项目是否有现成的pipeline可以使用\n- \"comfyUI\" {bool}: 这个项目是用comfyUI进行图像/视频/音频处理的\n- \"node\" {bool}: 部署本项目是否需要Node.js环境\n- \"python\" {bool}: 部署本项目是否需要python环境\n- \"setup\": 如果当前环境可以部署项目，为true；如果当前环境无法部署项目，为false。\n- 返回JSON属性 \"warn\": 部署本项目可能遇到或引起的问题，比如版本不稳定，项目已废弃，可能产生冲突，占用过多空间等。\n- 返回JSON属性 \"error\": 如果本地无法部署该项目，具体的原因描述。\n- 返回JSON属性 \"summary\": 用简洁的语言描述当前项目的用途，用到的技术，总结该项目在本地部署的可行性。\n`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "请评估并用JSON返回结果",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IHBDKSG31",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ0RFB3T0"
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
//						"formatDef": "\"1IG5ML8LS0\""
//					},
//					"icon": "llm.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1II1BCUQH0",
//					"attrs": {
//						"id": "TipPreview",
//						"viewName": "",
//						"label": "",
//						"x": "1185",
//						"y": "505",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II1BIEV60",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II1BIEV61",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "Project downloaded successfully, checking project requirements.",
//							"localize": {
//								"EN": "Project downloaded successfully, checking project requirements.",
//								"CN": "项目已下载完毕，评估项目需求。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1II1BIEUQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHBDIFBT0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IJ0RFB3T0",
//					"attrs": {
//						"id": "ShowSummary",
//						"viewName": "",
//						"label": "",
//						"x": "1630",
//						"y": "505",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "",
//						"context": {
//							"jaxId": "1IJ0RJS5O0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0RJS5O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`\n### 项目简介\n${input.brief}\n\n### 存在问题\n${input.error}\n\n### 注意事项\n${input.warn}\n\n### 总结：\n${input.summary}\n`",
//						"outlet": {
//							"jaxId": "1IJ0RJS5G0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJ0SEMOH0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJ0RJ6910",
//					"attrs": {
//						"id": "AbortSetup",
//						"viewName": "",
//						"label": "",
//						"x": "2110",
//						"y": "535",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJ0RJS5O6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJ0RJS5O7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJ0RJS5H1",
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
//					"def": "askMenu",
//					"jaxId": "1IJ0SEMOH0",
//					"attrs": {
//						"id": "AskSetup",
//						"viewName": "",
//						"label": "",
//						"x": "1875",
//						"y": "505",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Do you want to continue installing/deploying this project?",
//							"localize": {
//								"EN": "Do you want to continue installing/deploying this project?",
//								"CN": "是否继续安装/部署本项目？"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IJ0SIP0E0",
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
//									"jaxId": "1IJ0SEMNU0",
//									"attrs": {
//										"id": "Continue",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Continue setup",
//											"localize": {
//												"EN": "Continue setup",
//												"CN": "继续设置"
//											},
//											"localizable": true
//										},
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0SIP0O0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0SIP0O1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IG66HGKR0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IJ0SEMNU1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Abort setup",
//											"localize": {
//												"EN": "Abort setup",
//												"CN": "放弃，终止安装"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJ0SIP0O2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJ0SIP0O3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IJ0RJ6910"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "menu.svg",
//					"reverseOutlets": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}