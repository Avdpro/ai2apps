//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1HDBOSUN90MoreImports*/
import fsp from 'fs/promises';
import axios from 'axios'
/*}#1HDBOSUN90MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
const argsTemplate={
	properties:{
		"url":{
			"name":"url","type":"string",
			"required":true,
			"defaultValue":"",
			"desc":"用户需要部署的github项目的链接，如https://github.com/Avdpro/ai2apps",
		}
	},
	/*#{1HDBOSUN90ArgsView*/
	/*}#1HDBOSUN90ArgsView*/
};

/*#{1HDBOSUN90StartDoc*/
function getTypeEmoji(type) {
	const emojiMap = {
		readme: '📖',
		install: '🚀',
		setup: '⚙️',
		deploy: '🚀',
		docker: '🐳',
		kubernetes: '☸️',
		build: '🔨',
		config: '📋',
		docs: '📚'
	};
	return emojiMap[type] || '📄';
}
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let agent=async function(session){
	let url;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let InitBash,Get,Clone,GetPath,FindGuide,CheckGuide,NoReadme,WriteSetupGuide,SetupProject,FixArgs,Tip1,LLMCheckClone,CheckClone,Failure,Retry,goto,Navigate,Test,CheckDeploy,OutputFail,OutputSuccess,RegisterProject,Start,RegisterFail,TestAPI,Process,CheckInput,InputText,CheckRegister,InputFile,Again,Fetch,CheckStart,RegisterSuccess,FakeSetup,ExtracUsage,Summary,Output,ListFiles,GetPath2,InitBash2;
	/*#{1HDBOSUN90LocalVals*/
	let repo, folder;
	let input_type, output_type, api, usage_md, output_suffix, output_path, conda_name, server_start=false, all_files, guide_md, dir, deploy_md;
	
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			url=input.url;
		}else{
			url=undefined;
		}
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
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
	/*}#1HDBOSUN90PreContext*/
	context={};
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let $agent,agent,segs={};
	segs["InitBash"]=InitBash=async function(input){//:1IVIQJIRE0
		let result,args={};
		args['bashId']="";
		args['action']="Create";
		args['commands']="";
		args['options']={client:true};
		/*#{1IVIQJIRE0PreCodes*/
		/*}#1IVIQJIRE0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IVIQJIRE0PostCodes*/
		globalContext.bash=result;
		/*}#1IVIQJIRE0PostCodes*/
		return {seg:Navigate,result:(result),preSeg:"1IVIQJIRE0",outlet:"1IVIQK39F0"};
	};
	InitBash.jaxId="1IVIQJIRE0"
	InitBash.url="InitBash@"+agentURL
	
	segs["Get"]=Get=async function(input){//:1IVIQNTGJ0
		let prompt;
		let result=null;
		/*#{1IVIQNTGJ0Input*/
		/*}#1IVIQNTGJ0Input*/
		
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
		let chatMem=Get.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:"用户有一个github项目的链接，请给出使用git clone需要的url, repo和git clone之后在当前目录生成的文件夹名称，以json格式给出，如 {url:\"https://github.com/Avdpro/ai2apps.git\",repo:\"Avdpro/ai2apps\",dir:\"ai2apps\"}"},
		];
		/*#{1IVIQNTGJ0PrePrompt*/
		/*}#1IVIQNTGJ0PrePrompt*/
		prompt=url;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1IVIQNTGJ0FilterMessage*/
			/*}#1IVIQNTGJ0FilterMessage*/
			messages.push(msg);
		}
		/*#{1IVIQNTGJ0PreCall*/
		/*}#1IVIQNTGJ0PreCall*/
		result=(result===null)?(await session.callSegLLM("Get@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IVIQNTGJ0PostCall*/
		folder=result.dir;
		repo=result.repo;
		/*}#1IVIQNTGJ0PostCall*/
		return {seg:Clone,result:(result),preSeg:"1IVIQNTGJ0",outlet:"1IVIQUBK60"};
	};
	Get.jaxId="1IVIQNTGJ0"
	Get.url="Get@"+agentURL
	
	segs["Clone"]=Clone=async function(input){//:1IVIR0M3A0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[`rm -rf ${input.dir}`, `git clone ${input.url}`, `cd ${input.dir}`];
		args['options']="";
		/*#{1IVIR0M3A0PreCodes*/
		/*}#1IVIR0M3A0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IVIR0M3A0PostCodes*/
		/*}#1IVIR0M3A0PostCodes*/
		return {seg:LLMCheckClone,result:(result),preSeg:"1IVIR0M3A0",outlet:"1IVIR283T0"};
	};
	Clone.jaxId="1IVIR0M3A0"
	Clone.url="Clone@"+agentURL
	
	segs["GetPath"]=GetPath=async function(input){//:1IVIR603S0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']='find "$(pwd)" -type f -not -path "*/.git/*" -not -path "*/__pycache__/*" -not -path "*/.pytest_cache/*" -not -path "*/.tox/*" -not -path "*/venv/*" -not -path "*/.venv/*" -not -path "*/env/*" -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" -not -path "*/*.egg-info/*" -not -path "*/.mypy_cache/*" -not -path "*/.coverage/*"';
		args['options']="";
		/*#{1IVIR603S0PreCodes*/
		/*}#1IVIR603S0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1IVIR603S0PostCodes*/
		// all_files = extract(result);
		/*}#1IVIR603S0PostCodes*/
		return {seg:FindGuide,result:(result),preSeg:"1IVIR603S0",outlet:"1IVIRB74M1"};
	};
	GetPath.jaxId="1IVIR603S0"
	GetPath.url="GetPath@"+agentURL
	
	segs["FindGuide"]=FindGuide=async function(input){//:1IVIRJAV80
		let prompt;
		let result;
		{
			const $text=(($ln==="CN")?("查找部署相关的参考资料。"):("Search for references related to deployment."));
			const $role=(undefined)||"assistant";
			const $roleText=("assistant")||undefined;
			await session.addChatText($role,$text,{"channel":"Process","txtHeader":$roleText});
		}
		
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
		let chatMem=FindGuide.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`用户输入了find "$(pwd)" -type f命令的得到了输出，请根据输出的结果给出所有可能帮助安装和部署项目的文件完整绝对路径，以json格式给出。

## 需要查找的文件类型包括：

**安装相关文件:**
- README.md, readme.md, README.txt, README.rst, README
- INSTALL.md, install.md, INSTALL.txt, INSTALL.rst, INSTALL
- SETUP.md, setup.md, SETUP.txt, SETUP.rst, SETUP
- GETTING_STARTED.md, getting_started.md, GettingStarted.md
- QUICKSTART.md, quickstart.md, QuickStart.md

**部署相关文件:**
- DEPLOY.md, deploy.md, DEPLOYMENT.md, deployment.md
- DOCKER.md, docker.md, Dockerfile, docker-compose.yml, docker-compose.yaml
- KUBERNETES.md, k8s.md, kubernetes.yaml, kubernetes.yml
- HELM.md, helm.md, Chart.yaml, values.yaml

**构建相关文件:**
- BUILD.md, build.md, BUILDING.md, building.md
- COMPILE.md, compile.md, COMPILATION.md
- Makefile, makefile, CMakeLists.txt
- package.json, requirements.txt, Pipfile, poetry.lock
- build.gradle, pom.xml, Cargo.toml

**配置相关文件:**
- CONFIG.md, config.md, CONFIGURATION.md, configuration.md
- SETTINGS.md, settings.md, ENV.md, environment.md
- .env.example, .env.template, config.example.yml

**文档相关文件:**
- DOCS.md, docs.md, DOCUMENTATION.md, documentation.md
- API.md, api.md, USAGE.md, usage.md
- EXAMPLES.md, examples.md, TUTORIAL.md, tutorial.md

## 输出格式：

如果找到相关文件：
{
  "exists": true,
  "installation_files": [
    {
      "type": "readme",
      "path": "/Users/xxx/project/README.md"
    },
    {
      "type": "install",
      "path": "/Users/xxx/project/INSTALL.md"
    },
    {
      "type": "docker",
      "path": "/Users/xxx/project/Dockerfile"
    },
    {
      "type": "build",
      "path": "/Users/xxx/project/package.json"
    }
  ],
  "total_count": 4
}

如果没有找到任何相关文件：
{
  "exists": false,
  "installation_files": [],
  "total_count": 0
}

## 文件类型分类：
- \`readme\`: README相关文件
- \`install\`: 安装说明文件
- \`deploy\`: 部署相关文件
- \`docker\`: Docker相关文件
- \`kubernetes\`: Kubernetes相关文件
- \`build\`: 构建配置文件
- \`config\`: 配置相关文件
- \`docs\`: 文档相关文件
- \`setup\`: 设置相关文件

请根据find命令的输出结果，识别并返回所有可能帮助项目安装、部署、构建和配置的文件路径。`},
		];
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};messages.push(msg);
		}
		result=await session.callSegLLM("FindGuide@"+agentURL,opts,messages,true);
		result=trimJSON(result);
		return {seg:CheckGuide,result:(result),preSeg:"1IVIRJAV80",outlet:"1IVIRMVDS0"};
	};
	FindGuide.jaxId="1IVIRJAV80"
	FindGuide.url="FindGuide@"+agentURL
	
	segs["CheckGuide"]=CheckGuide=async function(input){//:1IVIRNBT70
		let result=input;
		if(input.exists){
			return {seg:WriteSetupGuide,result:(input),preSeg:"1IVIRNBT70",outlet:"1IVIROKCD0"};
		}
		return {seg:NoReadme,result:(result),preSeg:"1IVIRNBT70",outlet:"1IVIROKCD1"};
	};
	CheckGuide.jaxId="1IVIRNBT70"
	CheckGuide.url="CheckGuide@"+agentURL
	
	segs["NoReadme"]=NoReadme=async function(input){//:1IVIRNSHQ0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("未找到部署指南，部署终止"):("Deployment guide is not found, aborted."));
		session.addChatText(role,content,opts);
		return {result:result};
	};
	NoReadme.jaxId="1IVIRNSHQ0"
	NoReadme.url="NoReadme@"+agentURL
	
	segs["WriteSetupGuide"]=WriteSetupGuide=async function(input){//:1IVIRP9RP0
		let result=input
		/*#{1IVIRP9RP0Code*/
		// Read and organize all installation files
		let combinedContent = `# Comprehensive Setup Guide
		
		This guide combines information from multiple project documentation files.
		
		---
		
		`;
		
		// Group files by type for better organization
		const filesByType = {
			readme: [],
			install: [],
			setup: [],
			deploy: [],
			docker: [],
			kubernetes: [],
			build: [],
			config: [],
			docs: []
		};
		
		// Categorize files
		for (const file of input.installation_files) {
			if (filesByType[file.type]) {
				filesByType[file.type].push(file);
			}
		}
		
		// Define the order of sections
		const sectionOrder = [
			{ type: 'readme', title: '📖 Project Overview' },
			{ type: 'install', title: '🚀 Installation Instructions' },
			{ type: 'setup', title: '⚙️ Setup Configuration' },
			{ type: 'build', title: '🔨 Build Instructions' },
			{ type: 'config', title: '📋 Configuration' },
			{ type: 'docker', title: '🐳 Docker Deployment' },
			{ type: 'kubernetes', title: '☸️ Kubernetes Deployment' },
			{ type: 'deploy', title: '🚀 Deployment Guide' },
			{ type: 'docs', title: '📚 Additional Documentation' }
		];
		
		// Process each section
		for (const section of sectionOrder) {
			const filesInSection = filesByType[section.type];
			if (filesInSection && filesInSection.length > 0) {
				combinedContent += `## ${section.title}\n\n`;
				
				for (const file of filesInSection) {
					try {
						// Read file content
						const content = await fsp.readFile(file.path, "utf-8");
						const fileName = pathLib.basename(file.path);
						
						combinedContent += `### From ${fileName}\n\n`;
						combinedContent += `*Source: \`${file.path}\`*\n\n`;
						
						// Clean up the content (remove title if it duplicates our section)
						let cleanContent = content;
						
						// Remove common markdown titles that might conflict
						cleanContent = cleanContent.replace(/^#\s+.*$/gm, (match) => {
							// Convert top-level headers to lower level
							return match.replace(/^#\s+/, '#### ');
						});
						
						combinedContent += cleanContent;
						combinedContent += '\n\n---\n\n';
						
					} catch (error) {
						console.warn(`Failed to read file ${file.path}:`, error.message);
						combinedContent += `### ${pathLib.basename(file.path)} (Failed to read)\n\n`;
						combinedContent += `*Error reading file: \`${file.path}\`*\n\n`;
						combinedContent += '---\n\n';
					}
				}
			}
		}
		
		// Add summary section
		combinedContent += `## 📝 Summary
		
		This setup guide was automatically generated from ${input.total_count} documentation file(s):
		
		`;
		
		// List all processed files
		for (const file of input.installation_files) {
			const fileName = pathLib.basename(file.path);
			const typeEmoji = getTypeEmoji(file.type);
			combinedContent += `- ${typeEmoji} **${fileName}** (${file.type}) - \`${file.path}\`\n`;
		}
		
		combinedContent += `\n*Generated on: ${new Date().toISOString()}*\n`;
		
		guide_md = combinedContent;
		// Write the combined content to setup_guide.md
		const filePath = pathLib.join(decodeURIComponent(basePath), 'setup_guide.md');
		await fsp.writeFile(filePath, combinedContent);
			/*}#1IVIRP9RP0Code*/
		return {seg:SetupProject,result:(result),preSeg:"1IVIRP9RP0",outlet:"1IVIRQEDP0"};
	};
	WriteSetupGuide.jaxId="1IVIRP9RP0"
	WriteSetupGuide.url="WriteSetupGuide@"+agentURL
	
	segs["SetupProject"]=SetupProject=async function(input){//:1IVIS07O60
		let result;
		let arg={"prjPath":basePath,"folder":folder,"repo":repo};
		let agentNode=("")||null;
		let sourcePath=pathLib.join(basePath,"../AutoDeploy/PrjSetupBySteps.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		{
			const $text=(($ln==="CN")?("开始部署项目。"):("Start deploying the project."));
			const $role=(undefined)||"assistant";
			const $roleText=("assistant")||undefined;
			await session.addChatText($role,$text,{"channel":"Process","txtHeader":$roleText});
		}
		/*#{1IVIS07O60Input*/
		/*}#1IVIS07O60Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1IVIS07O60Output*/
		conda_name=result.conda;
		deploy_md = result.guide;
		dir = pathLib.join(basePath,"projects",folder);
		/*}#1IVIS07O60Output*/
		return {seg:CheckDeploy,result:(result),preSeg:"1IVIS07O60",outlet:"1IVIS0ONQ0"};
	};
	SetupProject.jaxId="1IVIS07O60"
	SetupProject.url="SetupProject@"+agentURL
	
	segs["FixArgs"]=FixArgs=async function(input){//:1J0997VD40
		let result=input;
		let missing=false;
		let smartAsk=false;
		if(url===undefined || url==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@tabos/HubFixArgs.mjs",{"argsTemplate":argsTemplate,"command":input,smartAsk:smartAsk},false);
			parseAgentArgs(result);
		}
		return {seg:InitBash,result:(result),preSeg:"1J0997VD40",outlet:"1J0997VD41"};
	};
	FixArgs.jaxId="1J0997VD40"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["Tip1"]=Tip1=async function(input){//:1J1FJS9EU0
		let result=input;
		let channel="Process";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("开始克隆项目到本地。"):("Start cloning project to local."));
		session.addChatText(role,content,opts);
		return {seg:Get,result:(result),preSeg:"1J1FJS9EU0",outlet:"1J1FJT4EK0"};
	};
	Tip1.jaxId="1J1FJS9EU0"
	Tip1.url="Tip1@"+agentURL
	
	segs["LLMCheckClone"]=LLMCheckClone=async function(input){//:1J1FPDPRA0
		let prompt;
		let result=null;
		/*#{1J1FPDPRA0Input*/
		/*}#1J1FPDPRA0Input*/
		
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
		let chatMem=LLMCheckClone.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`你是一个 Git 克隆结果分析助手。  
当用户输入 Git 克隆命令（例如 git clone <仓库地址> [<目录>]）时，你不实际执行命令，而是基于以下维度进行推断和分析：  
1. 仓库地址格式是否正确（协议、域名、路径）。  
2. 仓库是否公开或需要认证/授权。  
3. 网络连通性（如域名是否能够解析）。  
4. 本地目标目录权限问题（磁盘容量、读写权限等）。  
5. 其他常见错误（如仓库不存在、SSH key 未配置、HTTP 认证失败等）。  

然后，你必须按照下面的 JSON 格式返回结果（仅返回 JSON，不要额外输出其他文本）：

成功示例：  
{
  "status": "success"
}

失败示例：
{
  "status": "failure",
  "reason": "<简要失败原因，例如：仓库不存在、权限被拒绝>",
  "solution": "<针对该原因的具体解决方案，例如：检查仓库 URL 是否正确；配置 SSH key 或使用 HTTPS 并输入用户名/密码>"
}
请严格按照上述格式输出，并保证字段完整。`

},
		];
		/*#{1J1FPDPRA0PrePrompt*/
		/*}#1J1FPDPRA0PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1J1FPDPRA0FilterMessage*/
			/*}#1J1FPDPRA0FilterMessage*/
			messages.push(msg);
		}
		/*#{1J1FPDPRA0PreCall*/
		/*}#1J1FPDPRA0PreCall*/
		result=(result===null)?(await session.callSegLLM("LLMCheckClone@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1J1FPDPRA0PostCall*/
		/*}#1J1FPDPRA0PostCall*/
		return {seg:CheckClone,result:(result),preSeg:"1J1FPDPRA0",outlet:"1J1FPEO370"};
	};
	LLMCheckClone.jaxId="1J1FPDPRA0"
	LLMCheckClone.url="LLMCheckClone@"+agentURL
	
	segs["CheckClone"]=CheckClone=async function(input){//:1J1FPKQPB0
		let result=input;
		if(input.status === "success"){
			return {seg:GetPath,result:(input),preSeg:"1J1FPKQPB0",outlet:"1J1FPMUEC0"};
		}
		return {seg:Failure,result:(result),preSeg:"1J1FPKQPB0",outlet:"1J1FPMUEC1"};
	};
	CheckClone.jaxId="1J1FPKQPB0"
	CheckClone.url="CheckClone@"+agentURL
	
	segs["Failure"]=Failure=async function(input){//:1J1FPNJ1A0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?(`项目克隆失败，${input.reason}\n请参考以下解决方案尝试解决并重试解决方案：${input.solution}`):(`Project cloning failed, ${input.reason}. \nPlease refer to the following solutions to try and resolve it and retry the solution: ${input.solution}`));
		session.addChatText(role,content,opts);
		return {seg:Retry,result:(result),preSeg:"1J1FPNJ1A0",outlet:"1J1FPPRQ30"};
	};
	Failure.jaxId="1J1FPNJ1A0"
	Failure.url="Failure@"+agentURL
	
	segs["Retry"]=Retry=async function(input){//:1J1FPS0KL0
		let prompt=((($ln==="CN")?("是否重新克隆项目"):("Whether to re-clone the project")))||input;
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
			return {seg:goto,result:(result),preSeg:"1J1FPS0KL0",outlet:"1J1FPS0K20"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:goto,result:(result),preSeg:"1J1FPS0KL0",outlet:"1J1FPS0K20"};
		}else if(item.code===1){
			return {result:result};
		}
		return {result:result};
	};
	Retry.jaxId="1J1FPS0KL0"
	Retry.url="Retry@"+agentURL
	
	segs["goto"]=goto=async function(input){//:1J1FPV5SF0
		let result=input;
		return {seg:Tip1,result:result,preSeg:"1J1FJS9EU0",outlet:"1J1FPVOU10"};
	
	};
	goto.jaxId="1J1FJS9EU0"
	goto.url="goto@"+agentURL
	
	segs["Navigate"]=Navigate=async function(input){//:1J1FTHV9E0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[`cd "${decodeURIComponent(basePath)}"`,`mkdir -p projects`,`cd projects`];
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:Tip1,result:(result),preSeg:"1J1FTHV9E0",outlet:"1J1FTKE6J0"};
	};
	Navigate.jaxId="1J1FTHV9E0"
	Navigate.url="Navigate@"+agentURL
	
	segs["Test"]=Test=async function(input){//:1J3I4OI7M0
		let prompt=((($ln==="CN")?("是否需要体验项目功能"):("Do you want to test the project feature")))||input;
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
		
		/*#{1J3I4OI7M0PreCodes*/
		/*}#1J3I4OI7M0PreCodes*/
		if(silent){
			result="";
			return {seg:InitBash2,result:(result),preSeg:"1J3I4OI7M0",outlet:"1J3I4OI710"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1J3I4OI7M0PostCodes*/
		/*}#1J3I4OI7M0PostCodes*/
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:InitBash2,result:(result),preSeg:"1J3I4OI7M0",outlet:"1J3I4OI710"};
		}else if(item.code===1){
			return {result:result};
		}
		/*#{1J3I4OI7M0FinCodes*/
		/*}#1J3I4OI7M0FinCodes*/
		return {result:result};
	};
	Test.jaxId="1J3I4OI7M0"
	Test.url="Test@"+agentURL
	
	segs["CheckDeploy"]=CheckDeploy=async function(input){//:1J3NPAI790
		let result=input;
		if(input==="Fail to Deploy"){
			return {seg:OutputFail,result:(input),preSeg:"1J3NPAI790",outlet:"1J3NPC0030"};
		}
		return {seg:OutputSuccess,result:(result),preSeg:"1J3NPAI790",outlet:"1J3NPC0031"};
	};
	CheckDeploy.jaxId="1J3NPAI790"
	CheckDeploy.url="CheckDeploy@"+agentURL
	
	segs["OutputFail"]=OutputFail=async function(input){//:1J3NPC9JQ0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("部署失败"):("Deployment failed"));
		session.addChatText(role,content,opts);
		return {result:result};
	};
	OutputFail.jaxId="1J3NPC9JQ0"
	OutputFail.url="OutputFail@"+agentURL
	
	segs["OutputSuccess"]=OutputSuccess=async function(input){//:1J3NPP7BT0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("部署成功"):("Deployment success"));
		/*#{1J3NPP7BT0PreCodes*/
		/*}#1J3NPP7BT0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1J3NPP7BT0PostCodes*/
		/*}#1J3NPP7BT0PostCodes*/
		return {seg:Test,result:(result),preSeg:"1J3NPP7BT0",outlet:"1J3NPQ9AU0"};
	};
	OutputSuccess.jaxId="1J3NPP7BT0"
	OutputSuccess.url="OutputSuccess@"+agentURL
	
	segs["RegisterProject"]=RegisterProject=async function(input){//:1J3NQE9OT0
		let result=input
		{
			const $text=(($ln==="CN")?("正在将项目注册为API"):("Registering project as API"));
			const $role=(undefined)||"assistant";
			const $roleText=("assistant")||undefined;
			await session.addChatText($role,$text,{"channel":"Process","txtHeader":$roleText});
		}
		/*#{1J3NQE9OT0Code*/
		// input_type=input.input_type;
		// output_type=input.output_type;
		let arg={project_path:decodeURIComponent(pathLib.join(basePath,"projects",folder)),usage_md:usage_md,project_name:folder};
		// session.addChatText("assistant", `### Arguments\n\`\`\`json\n${JSON.stringify(arg, null, 2)}\n\`\`\``);
		result = await fetch('http://127.0.0.1:8082/projects', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(arg)
		});
		result=await result.json();
		/*}#1J3NQE9OT0Code*/
		return {seg:CheckRegister,result:(result),preSeg:"1J3NQE9OT0",outlet:"1J3NQH0NO0"};
	};
	RegisterProject.jaxId="1J3NQE9OT0"
	RegisterProject.url="RegisterProject@"+agentURL
	
	segs["Start"]=Start=async function(input){//:1J4C6KPQA0
		let result;
		let arg={};
		let agentNode=("AAlgorithm")||null;
		let sourcePath="agent.py";
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		/*#{1J4C6KPQA0Input*/
		/*}#1J4C6KPQA0Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1J4C6KPQA0Output*/
		result=input;
		/*}#1J4C6KPQA0Output*/
		return {seg:RegisterProject,result:(result),preSeg:"1J4C6KPQA0",outlet:"1J4C6LHNB0"};
	};
	Start.jaxId="1J4C6KPQA0"
	Start.url="Start@"+agentURL
	
	segs["RegisterFail"]=RegisterFail=async function(input){//:1J4C75SK10
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("项目注册API失败"):("Project registration API failed"));
		session.addChatText(role,content,opts);
		return {result:result};
	};
	RegisterFail.jaxId="1J4C75SK10"
	RegisterFail.url="RegisterFail@"+agentURL
	
	segs["TestAPI"]=TestAPI=async function(input){//:1J4C7UH540
		let result;
		let arg={input_type:input_type, output_type:output_type,api:api,input_content:input,output_path:output_path};
		let agentNode=(undefined)||null;
		let sourcePath=pathLib.join(basePath,"../AutoDeploy/AutoAPI.js");
		let opts={secrect:false,fromAgent:$agent,askUpwardSeg:null};
		{
			const $text=(($ln==="CN")?("正在调用API"):("Calling API"));
			const $role=(undefined)||"assistant";
			const $roleText=("assistant")||undefined;
			await session.addChatText($role,$text,{"channel":"Process","txtHeader":$roleText});
		}
		/*#{1J4C7UH540Input*/
		/*}#1J4C7UH540Input*/
		result= await session.callAgent(agentNode,sourcePath,arg,opts);
		/*#{1J4C7UH540Output*/
		/*}#1J4C7UH540Output*/
		return {seg:Again,result:(result),preSeg:"1J4C7UH540",outlet:"1J4C842OF0"};
	};
	TestAPI.jaxId="1J4C7UH540"
	TestAPI.url="TestAPI@"+agentURL
	
	segs["Process"]=Process=async function(input){//:1J4C8795B0
		let result=input
		/*#{1J4C8795B0Code*/
		api=result.api_routes.registered_routes;
		api=api[0];
		/*}#1J4C8795B0Code*/
		return {seg:CheckInput,result:(result),preSeg:"1J4C8795B0",outlet:"1J4C87K0K0"};
	};
	Process.jaxId="1J4C8795B0"
	Process.url="Process@"+agentURL
	
	segs["CheckInput"]=CheckInput=async function(input){//:1J4C8AJCH0
		let result=input;
		if(input_type==="text"){
			return {seg:InputText,result:(input),preSeg:"1J4C8AJCH0",outlet:"1J4C8QQ9M0"};
		}
		return {seg:InputFile,result:(result),preSeg:"1J4C8AJCH0",outlet:"1J4C8QQ9N0"};
	};
	CheckInput.jaxId="1J4C8AJCH0"
	CheckInput.url="CheckInput@"+agentURL
	
	segs["InputText"]=InputText=async function(input){//:1J4C8BP190
		let tip=((($ln==="CN")?("请输入测试的文本"):("Please enter the test text")));
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
		return {seg:TestAPI,result:(result),preSeg:"1J4C8BP190",outlet:"1J4C8QQ9N1"};
	};
	InputText.jaxId="1J4C8BP190"
	InputText.url="InputText@"+agentURL
	
	segs["CheckRegister"]=CheckRegister=async function(input){//:1J4C8TQ9V0
		let result=input;
		/*#{1J4C8TQ9V0Start*/
		/*}#1J4C8TQ9V0Start*/
		if(result.success){
			return {seg:RegisterSuccess,result:(input),preSeg:"1J4C8TQ9V0",outlet:"1J4C8UAK40"};
		}
		/*#{1J4C8TQ9V0Post*/
		/*}#1J4C8TQ9V0Post*/
		return {seg:RegisterFail,result:(result),preSeg:"1J4C8TQ9V0",outlet:"1J4C8UAK41"};
	};
	CheckRegister.jaxId="1J4C8TQ9V0"
	CheckRegister.url="CheckRegister@"+agentURL
	
	segs["InputFile"]=InputFile=async function(input){//:1J4C964JH0
		let tip=((($ln==="CN")?("请选择测试的文件"):("Please select the test file")));
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(true)||false;
		let allowEmpty=(true)||false;
		let askUpward=(false);
		let text=("");
		let result="";
		/*#{1J4C964JH0PreCodes*/
		/*}#1J4C964JH0PreCodes*/
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
		/*#{1J4C964JH0PostCodes*/
		if(result.assets){
			let assets = result.assets;
			result=await session.getHubPath(assets[0]);
		}
		/*}#1J4C964JH0PostCodes*/
		return {seg:TestAPI,result:(result),preSeg:"1J4C964JH0",outlet:"1J4C96Q7S0"};
	};
	InputFile.jaxId="1J4C964JH0"
	InputFile.url="InputFile@"+agentURL
	
	segs["Again"]=Again=async function(input){//:1J4CAH8QI0
		let prompt=((($ln==="CN")?("是否重新测试"):("Whether to retest")))||input;
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
			return {seg:CheckInput,result:(result),preSeg:"1J4CAH8QI0",outlet:"1J4CAH8PS0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:CheckInput,result:(result),preSeg:"1J4CAH8QI0",outlet:"1J4CAH8PS0"};
		}else if(item.code===1){
			return {result:result};
		}
		return {result:result};
	};
	Again.jaxId="1J4CAH8QI0"
	Again.url="Again@"+agentURL
	
	segs["Fetch"]=Fetch=async function(input){//:1J4CFJC4C0
		let result=input
		/*#{1J4CFJC4C0Code*/
		try{
			let res = await fetch("http://127.0.0.1:8082/health");
			server_start=true;
		}
		catch(err){
			server_start=false;
		}
		/*}#1J4CFJC4C0Code*/
		return {seg:CheckStart,result:(result),preSeg:"1J4CFJC4C0",outlet:"1J4CFLVS10"};
	};
	Fetch.jaxId="1J4CFJC4C0"
	Fetch.url="Fetch@"+agentURL
	
	segs["CheckStart"]=CheckStart=async function(input){//:1J4CFRF8P0
		let result=input;
		if(!server_start){
			return {seg:Start,result:(input),preSeg:"1J4CFRF8P0",outlet:"1J4CFSORT0"};
		}
		return {seg:RegisterProject,result:(result),preSeg:"1J4CFRF8P0",outlet:"1J4CFSORT1"};
	};
	CheckStart.jaxId="1J4CFRF8P0"
	CheckStart.url="CheckStart@"+agentURL
	
	segs["RegisterSuccess"]=RegisterSuccess=async function(input){//:1J4EB0N190
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=(($ln==="CN")?("项目注册API成功"):("Project registration API successful"));
		session.addChatText(role,content,opts);
		return {seg:Process,result:(result),preSeg:"1J4EB0N190",outlet:"1J4EB0N193"};
	};
	RegisterSuccess.jaxId="1J4EB0N190"
	RegisterSuccess.url="RegisterSuccess@"+agentURL
	
	segs["FakeSetup"]=FakeSetup=async function(input){//:1J4KBBMRK0
		let result=input
		/*#{1J4KBBMRK0Code*/
		conda_name = "fastvlm";
		dir = pathLib.join(basePath,"projects",folder);
		/*}#1J4KBBMRK0Code*/
		return {result:result};
	};
	FakeSetup.jaxId="1J4KBBMRK0"
	FakeSetup.url="FakeSetup@"+agentURL
	
	segs["ExtracUsage"]=ExtracUsage=async function(input){//:1J4KMNBDP0
		let prompt;
		let result=null;
		/*#{1J4KMNBDP0Input*/
		/*}#1J4KMNBDP0Input*/
		
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
		let chatMem=ExtracUsage.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`请你作为用户助手，根据已部署的项目文档中 **Quick Start**、**Usage**、**Examples**、**Command Line Tools** 等使用说明部分，以及部署成功时总结的部署指南，面向普通用户提取并整理以下信息：

1. 基本使用示例
2. 命令行使用方式
3. 主要功能列表

重点关注项目提供的1个核心功能（如 OCR、TTS 等），并对该功能尝试识别：
**功能名称**
**功能描述**
**使用方法**（命令行示例）

注意:
1. 你所选择的功能在命令行使用中必须存在输入参数，且参数必须为text或filePath，其余参数均应该有默认且可以直接使用的参数，不需要用户自己填写或修改，即在命令行示例中只能有输入文本/输入文件路径/输出文件路径，其余参数均应选择最合适的值，并和功能描述相对应。
2. 输入的文本/文件路径只能有一个。
3. 如果输出的filePath是一个文件夹/目录的路径，请在output_description中指明需要压缩为zip文件，输出的格式是zip的路径，内容是A zip file containing ...。
4. 如果命令行执行示例中包含文件路径，请使用绝对路径，例如：python /Users/agenthub/code/ai2apps/agents/AutoDeploy/projects/ml-fastvlm/predict.py ...。
5. 请你仔细检查需要用到的文件都存在并且路径正确，尤其是模型权重的目录，确保其中包含正确的模型文件。
6. 由于实际的部署方案与项目文档中可能有出入，生成命令后你需要仔细检查部署指南和本地文件，确保你的命令可以在本地直接复制粘贴运行。

请严格按照以下 JSON 格式输出：

{
  "reason": "你的思考过程",
  "features": [
    {
      "name": "功能名称（简洁明了）",
      "description": "功能详细描述（说明具体作用和适用场景）",
      "input_type": "text/filePath",
      "input_description": "输入参数的具体描述",
      "output_type": "text/filePath",
      "output_is_directory_path": true/false,
      "need_zip": true/false,
      "output_suffix":"输出结果的文件后缀名，如zip, png, md, txt 等等"
      "output_description": "输出结果的详细描述（文件格式、内容说明）",
      "command": "完整的命令行执行示例（可以直接复制粘贴运行）",
    }
  ]
}
` + (($ln==="CN")?("用中文输出。"):("Output in English."))

},
		];
		/*#{1J4KMNBDP0PrePrompt*/
		/*}#1J4KMNBDP0PrePrompt*/
		prompt=`部署指南：
${deploy_md}
项目文档：
${guide_md}
项目内包含的文件有：
${all_files}
`;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1J4KMNBDP0FilterMessage*/
			/*}#1J4KMNBDP0FilterMessage*/
			messages.push(msg);
		}
		/*#{1J4KMNBDP0PreCall*/
		/*}#1J4KMNBDP0PreCall*/
		result=(result===null)?(await session.callSegLLM("ExtracUsage@"+agentURL,opts,messages,true)):result;
		/*#{1J4KMNBDP0PostCall*/
		result = trimJSON(result);
		result = result.features[0];
		input_type = result.input_type;
		output_type = result.output_type;
		output_suffix = result.output_suffix;
		const str = Math.random().toString().slice(2);
		output_path = `/tmp/${str}.${output_suffix}`;
		/*}#1J4KMNBDP0PostCall*/
		return {seg:Summary,result:(result),preSeg:"1J4KMNBDP0",outlet:"1J4KMNUEQ0"};
	};
	ExtracUsage.jaxId="1J4KMNBDP0"
	ExtracUsage.url="ExtracUsage@"+agentURL
	
	segs["Summary"]=Summary=async function(input){//:1J4KN30G00
		let prompt;
		let result=null;
		/*#{1J4KN30G00Input*/
		/*}#1J4KN30G00Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4.1",
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
			{role:"system",content:`请把输入总结成使用指南，严格按照输入给出的input_type和output_type，输出markdown格式的文本。在指南中加上这句话：已经在本机的 conda 环境 ${conda_name} 安装相关依赖，运行相关 cli 需要先激活虚拟环境。` + (($ln==="CN")?("用中文输出。"):("Output in English."))},
		];
		/*#{1J4KN30G00PrePrompt*/
		/*}#1J4KN30G00PrePrompt*/
		prompt=input;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			let msg={role:"user",content:prompt};
			/*#{1J4KN30G00FilterMessage*/
			/*}#1J4KN30G00FilterMessage*/
			messages.push(msg);
		}
		/*#{1J4KN30G00PreCall*/
		/*}#1J4KN30G00PreCall*/
		result=(result===null)?(await session.callSegLLM("Summary@"+agentURL,opts,messages,true)):result;
		/*#{1J4KN30G00PostCall*/
		usage_md = result;
		/*}#1J4KN30G00PostCall*/
		return {seg:Output,result:(result),preSeg:"1J4KN30G00",outlet:"1J4KN4BRT0"};
	};
	Summary.jaxId="1J4KN30G00"
	Summary.url="Summary@"+agentURL
	
	segs["Output"]=Output=async function(input){//:1J4KNAFFS0
		let result=input;
		let channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:channel};
		let role="assistant";
		let content=input;
		/*#{1J4KNAFFS0PreCodes*/
		/*}#1J4KNAFFS0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1J4KNAFFS0PostCodes*/
		result = {guide:input,input_type:input_type,output_type:output_type,output_suffix:output_suffix};
		/*}#1J4KNAFFS0PostCodes*/
		return {seg:Fetch,result:(result),preSeg:"1J4KNAFFS0",outlet:"1J4KNAOVI0"};
	};
	Output.jaxId="1J4KNAFFS0"
	Output.url="Output@"+agentURL
	
	segs["ListFiles"]=ListFiles=async function(input){//:1J5NMNSHC0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']='find "$(pwd)" -type f -not -path "*/.git/*" -not -path "*/__pycache__/*" -not -path "*/.pytest_cache/*" -not -path "*/.tox/*" -not -path "*/venv/*" -not -path "*/.venv/*" -not -path "*/env/*" -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" -not -path "*/*.egg-info/*" -not -path "*/.mypy_cache/*" -not -path "*/.coverage/*"';
		args['options']="";
		/*#{1J5NMNSHC0PreCodes*/
		/*}#1J5NMNSHC0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1J5NMNSHC0PostCodes*/
		all_files = extract(result);
		/*}#1J5NMNSHC0PostCodes*/
		return {seg:ExtracUsage,result:(result),preSeg:"1J5NMNSHC0",outlet:"1J5NMOVBL0"};
	};
	ListFiles.jaxId="1J5NMNSHC0"
	ListFiles.url="ListFiles@"+agentURL
	
	segs["GetPath2"]=GetPath2=async function(input){//:1J5NMVNBD0
		let result,args={};
		args['bashId']=globalContext.bash;
		args['action']="Command";
		args['commands']=[`cd ${dir}`];
		args['options']="";
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		return {seg:ListFiles,result:(result),preSeg:"1J5NMVNBD0",outlet:"1J5NN19GV0"};
	};
	GetPath2.jaxId="1J5NMVNBD0"
	GetPath2.url="GetPath2@"+agentURL
	
	segs["InitBash2"]=InitBash2=async function(input){//:1J5NNUJMV0
		let result,args={};
		args['bashId']="";
		args['action']="Create";
		args['commands']="";
		args['options']={client: true};
		/*#{1J5NNUJMV0PreCodes*/
		/*}#1J5NNUJMV0PreCodes*/
		result= await session.pipeChat("/@AgentBuilder/Bash.js",args,false);
		/*#{1J5NNUJMV0PostCodes*/
		globalContext.bash=result;
		/*}#1J5NNUJMV0PostCodes*/
		return {seg:GetPath2,result:(result),preSeg:"1J5NNUJMV0",outlet:"1J5NNVFAV0"};
	};
	InitBash2.jaxId="1J5NNUJMV0"
	InitBash2.url="InitBash2@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"agent",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{url}*/){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN90PreEntry*/
			/*}#1HDBOSUN90PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1HDBOSUN90PostEntry*/
			/*}#1HDBOSUN90PostEntry*/
			return result;
		},
		/*#{1HDBOSUN90MoreAgentAttrs*/
		/*}#1HDBOSUN90MoreAgentAttrs*/
	};
	/*#{1HDBOSUN90PostAgent*/
	/*}#1HDBOSUN90PostAgent*/
	return agent;
};
/*#{1HDBOSUN90ExCodes*/
/*}#1HDBOSUN90ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "agent",
		description: "这是一个帮助用户自动部署github项目的agent，需要给出github的链接如https://github.com/Avdpro/ai2apps或repo的名称如Avdpro/ai2apps。",
		parameters:{
			type: "object",
			properties:{
				url:{type:"string",description:"用户需要部署的github项目的链接，如https://github.com/Avdpro/ai2apps"}
			}
		}
	},
	agentNode: "AutoDeploy",
	agentName: "agent.js",
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
		name:"agent",showName:"agent",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"url":{name:"url",showName:undefined,type:"string",key:1,fixed:1,initVal:""},
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","url","codes","desc"],
		desc:"这是一个帮助用户自动部署github项目的agent，需要给出github的链接如https://github.com/Avdpro/ai2apps或repo的名称如Avdpro/ai2apps。"
	});
	
	DocAIAgentExporter.segTypeExporters["agent"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			coder.packText("args['url']=");this.genAttrStatement(seg.getAttr("url"));coder.packText(";");coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/~/AutoDeploy/ai/agent.js",args,false);`);coder.newLine();
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
/*#{1HDBOSUN90PostDoc*/
/*}#1HDBOSUN90PostDoc*/


export default agent;
export{agent,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1HDBOSUN90",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1HDBOSUNA0",
//			"attrs": {
//				"agent": {
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
//		"entry": "FixArgs",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IVIQH5MC0",
//			"attrs": {
//				"url": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1J0997VD60",
//					"attrs": {
//						"type": "String",
//						"mockup": "\"\"",
//						"desc": "用户需要部署的github项目的链接，如https://github.com/Avdpro/ai2apps",
//						"required": "true"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {}
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
//					"def": "Bash",
//					"jaxId": "1IVIQJIRE0",
//					"attrs": {
//						"id": "InitBash",
//						"viewName": "",
//						"label": "",
//						"x": "280",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIQK39H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIQK39H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "\"\"",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client:true}",
//						"outlet": {
//							"jaxId": "1IVIQK39F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1FTHV9E0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IVIQNTGJ0",
//					"attrs": {
//						"id": "Get",
//						"viewName": "",
//						"label": "",
//						"x": "950",
//						"y": "135",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIQUBKH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIQUBKH1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "用户有一个github项目的链接，请给出使用git clone需要的url, repo和git clone之后在当前目录生成的文件夹名称，以json格式给出，如 {url:\"https://github.com/Avdpro/ai2apps.git\",repo:\"Avdpro/ai2apps\",dir:\"ai2apps\"}",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#url",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IVIQUBK60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIR0M3A0"
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
//					"def": "Bash",
//					"jaxId": "1IVIR0M3A0",
//					"attrs": {
//						"id": "Clone",
//						"viewName": "",
//						"label": "",
//						"x": "1125",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIR28410",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIR28411",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[`rm -rf ${input.dir}`, `git clone ${input.url}`, `cd ${input.dir}`]",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IVIR283T0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1FPDPRA0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1IVIR603S0",
//					"attrs": {
//						"id": "GetPath",
//						"viewName": "",
//						"label": "",
//						"x": "360",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIRB7554",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIRB7555",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#'find \"$(pwd)\" -type f -not -path \"*/.git/*\" -not -path \"*/__pycache__/*\" -not -path \"*/.pytest_cache/*\" -not -path \"*/.tox/*\" -not -path \"*/venv/*\" -not -path \"*/.venv/*\" -not -path \"*/env/*\" -not -path \"*/node_modules/*\" -not -path \"*/dist/*\" -not -path \"*/build/*\" -not -path \"*/*.egg-info/*\" -not -path \"*/.mypy_cache/*\" -not -path \"*/.coverage/*\"'",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1IVIRB74M1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIRJAV80"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IVIRJAV80",
//					"attrs": {
//						"id": "FindGuide",
//						"viewName": "",
//						"label": "",
//						"x": "570",
//						"y": "370",
//						"desc": "执行一次LLM调用。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIRMVE20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIRMVE21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "OpenAI",
//						"mode": "gpt-4.1-mini",
//						"system": "#`用户输入了find \"$(pwd)\" -type f命令的得到了输出，请根据输出的结果给出所有可能帮助安装和部署项目的文件完整绝对路径，以json格式给出。\n\n## 需要查找的文件类型包括：\n\n**安装相关文件:**\n- README.md, readme.md, README.txt, README.rst, README\n- INSTALL.md, install.md, INSTALL.txt, INSTALL.rst, INSTALL\n- SETUP.md, setup.md, SETUP.txt, SETUP.rst, SETUP\n- GETTING_STARTED.md, getting_started.md, GettingStarted.md\n- QUICKSTART.md, quickstart.md, QuickStart.md\n\n**部署相关文件:**\n- DEPLOY.md, deploy.md, DEPLOYMENT.md, deployment.md\n- DOCKER.md, docker.md, Dockerfile, docker-compose.yml, docker-compose.yaml\n- KUBERNETES.md, k8s.md, kubernetes.yaml, kubernetes.yml\n- HELM.md, helm.md, Chart.yaml, values.yaml\n\n**构建相关文件:**\n- BUILD.md, build.md, BUILDING.md, building.md\n- COMPILE.md, compile.md, COMPILATION.md\n- Makefile, makefile, CMakeLists.txt\n- package.json, requirements.txt, Pipfile, poetry.lock\n- build.gradle, pom.xml, Cargo.toml\n\n**配置相关文件:**\n- CONFIG.md, config.md, CONFIGURATION.md, configuration.md\n- SETTINGS.md, settings.md, ENV.md, environment.md\n- .env.example, .env.template, config.example.yml\n\n**文档相关文件:**\n- DOCS.md, docs.md, DOCUMENTATION.md, documentation.md\n- API.md, api.md, USAGE.md, usage.md\n- EXAMPLES.md, examples.md, TUTORIAL.md, tutorial.md\n\n## 输出格式：\n\n如果找到相关文件：\n{\n  \"exists\": true,\n  \"installation_files\": [\n    {\n      \"type\": \"readme\",\n      \"path\": \"/Users/xxx/project/README.md\"\n    },\n    {\n      \"type\": \"install\",\n      \"path\": \"/Users/xxx/project/INSTALL.md\"\n    },\n    {\n      \"type\": \"docker\",\n      \"path\": \"/Users/xxx/project/Dockerfile\"\n    },\n    {\n      \"type\": \"build\",\n      \"path\": \"/Users/xxx/project/package.json\"\n    }\n  ],\n  \"total_count\": 4\n}\n\n如果没有找到任何相关文件：\n{\n  \"exists\": false,\n  \"installation_files\": [],\n  \"total_count\": 0\n}\n\n## 文件类型分类：\n- \\`readme\\`: README相关文件\n- \\`install\\`: 安装说明文件\n- \\`deploy\\`: 部署相关文件\n- \\`docker\\`: Docker相关文件\n- \\`kubernetes\\`: Kubernetes相关文件\n- \\`build\\`: 构建配置文件\n- \\`config\\`: 配置相关文件\n- \\`docs\\`: 文档相关文件\n- \\`setup\\`: 设置相关文件\n\n请根据find命令的输出结果，识别并返回所有可能帮助项目安装、部署、构建和配置的文件路径。`",
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
//							"jaxId": "1IVIRMVDS0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIRNBT70"
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
//							"jaxId": "1J1HO118T0",
//							"attrs": {
//								"text": {
//									"type": "string",
//									"valText": "Search for references related to deployment.",
//									"localize": {
//										"EN": "Search for references related to deployment.",
//										"CN": "查找部署相关的参考资料。"
//									},
//									"localizable": true
//								},
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
//					"def": "brunch",
//					"jaxId": "1IVIRNBT70",
//					"attrs": {
//						"id": "CheckGuide",
//						"viewName": "",
//						"label": "",
//						"x": "775",
//						"y": "370",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIROKCJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIROKCJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IVIROKCD1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IVIRNSHQ0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IVIROKCD0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IVIROKCJ2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IVIROKCJ3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.exists"
//									},
//									"linkedSeg": "1IVIRP9RP0"
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
//					"jaxId": "1IVIRNSHQ0",
//					"attrs": {
//						"id": "NoReadme",
//						"viewName": "",
//						"label": "",
//						"x": "1040",
//						"y": "385",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIROKCJ4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIROKCJ5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Deployment guide is not found, aborted.",
//							"localize": {
//								"EN": "Deployment guide is not found, aborted.",
//								"CN": "未找到部署指南，部署终止"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IVIROKCD2",
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
//					"def": "code",
//					"jaxId": "1IVIRP9RP0",
//					"attrs": {
//						"id": "WriteSetupGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1040",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIS010L0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIS010L1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IVIRQEDP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIS07O60"
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
//					"jaxId": "1IVIS07O60",
//					"attrs": {
//						"id": "SetupProject",
//						"viewName": "",
//						"label": "",
//						"x": "1285",
//						"y": "270",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IVIS0ONV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IVIS0ONV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AutoDeploy/PrjSetupBySteps.js",
//						"argument": "{\"prjPath\":\"#basePath\",\"folder\":\"#folder\",\"repo\":\"#repo\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IVIS0ONQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3NPAI790"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"agentNode": "",
//						"process": {
//							"type": "object",
//							"def": "ProcessMsg",
//							"jaxId": "1J1HO118T1",
//							"attrs": {
//								"text": {
//									"type": "string",
//									"valText": "Start deploying the project.",
//									"localize": {
//										"EN": "Start deploying the project.",
//										"CN": "开始部署项目。"
//									},
//									"localizable": true
//								},
//								"role": "Assistant",
//								"roleText": "",
//								"codes": "false"
//							}
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1J0997VD40",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "65",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"smartAsk": "false",
//						"outlet": {
//							"jaxId": "1J0997VD41",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIQJIRE0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J1FJS9EU0",
//					"attrs": {
//						"id": "Tip1",
//						"viewName": "",
//						"label": "",
//						"x": "770",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1FJT4EO0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1FJT4EO1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Process",
//						"text": {
//							"type": "string",
//							"valText": "Start cloning project to local.",
//							"localize": {
//								"EN": "Start cloning project to local.",
//								"CN": "开始克隆项目到本地。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J1FJT4EK0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IVIQNTGJ0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1J1FPDPRA0",
//					"attrs": {
//						"id": "LLMCheckClone",
//						"viewName": "",
//						"label": "",
//						"x": "1320",
//						"y": "135",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1FPEO3E0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1FPEO3E1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1-mini",
//						"system": "#`你是一个 Git 克隆结果分析助手。  \n当用户输入 Git 克隆命令（例如 git clone <仓库地址> [<目录>]）时，你不实际执行命令，而是基于以下维度进行推断和分析：  \n1. 仓库地址格式是否正确（协议、域名、路径）。  \n2. 仓库是否公开或需要认证/授权。  \n3. 网络连通性（如域名是否能够解析）。  \n4. 本地目标目录权限问题（磁盘容量、读写权限等）。  \n5. 其他常见错误（如仓库不存在、SSH key 未配置、HTTP 认证失败等）。  \n\n然后，你必须按照下面的 JSON 格式返回结果（仅返回 JSON，不要额外输出其他文本）：\n\n成功示例：  \n{\n  \"status\": \"success\"\n}\n\n失败示例：\n{\n  \"status\": \"failure\",\n  \"reason\": \"<简要失败原因，例如：仓库不存在、权限被拒绝>\",\n  \"solution\": \"<针对该原因的具体解决方案，例如：检查仓库 URL 是否正确；配置 SSH key 或使用 HTTPS 并输入用户名/密码>\"\n}\n请严格按照上述格式输出，并保证字段完整。`\n\n",
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
//							"jaxId": "1J1FPEO370",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1FPLFMH0"
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
//					"jaxId": "1J1FPKQPB0",
//					"attrs": {
//						"id": "CheckClone",
//						"viewName": "",
//						"label": "",
//						"x": "125",
//						"y": "460",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1FPMUEP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1FPMUEP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J1FPMUEC1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J1FPNJ1A0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J1FPMUEC0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J1FPMUEP2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J1FPMUEP3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.status === \"success\""
//									},
//									"linkedSeg": "1IVIR603S0"
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
//					"jaxId": "1J1FPLFMH0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1490",
//						"y": "215",
//						"outlet": {
//							"jaxId": "1J1FPMUEP4",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1FPLKI30"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J1FPLKI30",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "150",
//						"y": "215",
//						"outlet": {
//							"jaxId": "1J1FPMUEP5",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1FPKQPB0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J1FPNJ1A0",
//					"attrs": {
//						"id": "Failure",
//						"viewName": "",
//						"label": "",
//						"x": "360",
//						"y": "475",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1FPPRQ80",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1FPPRQ81",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "#`Project cloning failed, ${input.reason}. \\nPlease refer to the following solutions to try and resolve it and retry the solution: ${input.solution}`",
//							"localize": {
//								"EN": "#`Project cloning failed, ${input.reason}. \\nPlease refer to the following solutions to try and resolve it and retry the solution: ${input.solution}`",
//								"CN": "#`项目克隆失败，${input.reason}\\n请参考以下解决方案尝试解决并重试解决方案：${input.solution}`"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J1FPPRQ30",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1FPS0KL0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1J1FPS0KL0",
//					"attrs": {
//						"id": "Retry",
//						"viewName": "",
//						"label": "",
//						"x": "570",
//						"y": "475",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Whether to re-clone the project",
//							"localize": {
//								"EN": "Whether to re-clone the project",
//								"CN": "是否重新克隆项目"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1J1FPVOU00",
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
//									"jaxId": "1J1FPS0K20",
//									"attrs": {
//										"id": "Yes",
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
//											"jaxId": "1J1FPVOU50",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J1FPVOU51",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1J1FPV5SF0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J1FPS0K21",
//									"attrs": {
//										"id": "No",
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
//											"jaxId": "1J1FPVOU52",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J1FPVOU53",
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
//					"def": "jumper",
//					"jaxId": "1J1FPV5SF0",
//					"attrs": {
//						"id": "goto",
//						"viewName": "",
//						"label": "",
//						"x": "775",
//						"y": "445",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1J1FJS9EU0",
//						"outlet": {
//							"jaxId": "1J1FPVOU10",
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
//					"def": "Bash",
//					"jaxId": "1J1FTHV9E0",
//					"attrs": {
//						"id": "Navigate",
//						"viewName": "",
//						"label": "",
//						"x": "540",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J1FTKMAT0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J1FTKMAT1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[`cd \"${decodeURIComponent(basePath)}\"`,`mkdir -p projects`,`cd projects`]",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J1FTKE6J0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J1FJS9EU0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1J3I4OI7M0",
//					"attrs": {
//						"id": "Test",
//						"viewName": "",
//						"label": "",
//						"x": "125",
//						"y": "710",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Do you want to test the project feature",
//							"localize": {
//								"EN": "Do you want to test the project feature",
//								"CN": "是否需要体验项目功能"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1J3I4QBTI0",
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
//									"jaxId": "1J3I4OI710",
//									"attrs": {
//										"id": "Yes",
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
//											"jaxId": "1J3I4QBTP0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J3I4QBTP1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1J5NNUJMV0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J3I4OI711",
//									"attrs": {
//										"id": "No",
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
//											"jaxId": "1J3I4QBTP2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J3I4QBTP3",
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
//					"def": "brunch",
//					"jaxId": "1J3NPAI790",
//					"attrs": {
//						"id": "CheckDeploy",
//						"viewName": "",
//						"label": "",
//						"x": "1525",
//						"y": "270",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3NPC0050",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3NPC0051",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J3NPC0031",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J3NPP7BT0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J3NPC0030",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J3NPC0052",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J3NPC0053",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input===\"Fail to Deploy\""
//									},
//									"linkedSeg": "1J3NPC9JQ0"
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
//					"jaxId": "1J3NPC9JQ0",
//					"attrs": {
//						"id": "OutputFail",
//						"viewName": "",
//						"label": "",
//						"x": "1790",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3NPCSME0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3NPCSME1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Deployment failed",
//							"localize": {
//								"EN": "Deployment failed",
//								"CN": "部署失败"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J3NPCSMA0",
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
//					"jaxId": "1J3NPP7BT0",
//					"attrs": {
//						"id": "OutputSuccess",
//						"viewName": "",
//						"label": "",
//						"x": "1790",
//						"y": "345",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3NPQ9B70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3NPQ9B71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Deployment success",
//							"localize": {
//								"EN": "Deployment success",
//								"CN": "部署成功"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J3NPQ9AU0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4M7RC9C0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J3NQE9OT0",
//					"attrs": {
//						"id": "RegisterProject",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "900",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J3NQILQL0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J3NQILQL1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J3NQH0NO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4C8TQ9V0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"process": {
//							"type": "object",
//							"def": "ProcessMsg",
//							"jaxId": "1J4ENBH2O0",
//							"attrs": {
//								"text": {
//									"type": "string",
//									"valText": "Registering project as API",
//									"localize": {
//										"EN": "Registering project as API",
//										"CN": "正在将项目注册为API"
//									},
//									"localizable": true
//								},
//								"role": "Assistant",
//								"roleText": "",
//								"codes": "false"
//							}
//						}
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1J4C6KPQA0",
//					"attrs": {
//						"id": "Start",
//						"viewName": "",
//						"label": "",
//						"x": "815",
//						"y": "885",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4C6LHNJ0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4C6LHNJ1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "agent.py",
//						"argument": "#{}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1J4C6LHNB0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3NQE9OT0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"agentNode": "AAlgorithm"
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J4C75SK10",
//					"attrs": {
//						"id": "RegisterFail",
//						"viewName": "",
//						"label": "",
//						"x": "1585",
//						"y": "990",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4C778A24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4C778A25",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Project registration API failed",
//							"localize": {
//								"EN": "Project registration API failed",
//								"CN": "项目注册API失败"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J4C7789P2",
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
//					"def": "aiBot",
//					"jaxId": "1J4C7UH540",
//					"attrs": {
//						"id": "TestAPI",
//						"viewName": "",
//						"label": "",
//						"x": "2560",
//						"y": "900",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4C842OP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4C842OP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "AutoDeploy/AutoAPI.js",
//						"argument": "#{input_type:input_type, output_type:output_type,api:api,input_content:input,output_path:output_path}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1J4C842OF0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4CAH8QI0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"process": {
//							"type": "object",
//							"def": "ProcessMsg",
//							"jaxId": "1J4END1OQ0",
//							"attrs": {
//								"text": {
//									"type": "string",
//									"valText": "Calling API",
//									"localize": {
//										"EN": "Calling API",
//										"CN": "正在调用API"
//									},
//									"localizable": true
//								},
//								"role": "Assistant",
//								"roleText": "",
//								"codes": "false"
//							}
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J4C8795B0",
//					"attrs": {
//						"id": "Process",
//						"viewName": "",
//						"label": "",
//						"x": "1850",
//						"y": "885",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4C883410",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4C883411",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J4C87K0K0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4C8AJCH0"
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
//					"jaxId": "1J4C8AJCH0",
//					"attrs": {
//						"id": "CheckInput",
//						"viewName": "",
//						"label": "",
//						"x": "2070",
//						"y": "885",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4C8QQA20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4C8QQA21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J4C8QQ9N0",
//							"attrs": {
//								"id": "File",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J4C964JH0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J4C8QQ9M0",
//									"attrs": {
//										"id": "Text",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J4C8QQA22",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J4C8QQA23",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input_type===\"text\""
//									},
//									"linkedSeg": "1J4C8BP190"
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
//					"jaxId": "1J4C8BP190",
//					"attrs": {
//						"id": "InputText",
//						"viewName": "",
//						"label": "",
//						"x": "2290",
//						"y": "830",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4C8QQA24",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4C8QQA25",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": {
//							"type": "string",
//							"valText": "Please enter the test text",
//							"localize": {
//								"EN": "Please enter the test text",
//								"CN": "请输入测试的文本"
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
//							"jaxId": "1J4C8QQ9N1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4C7UH540"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1J4C8TQ9V0",
//					"attrs": {
//						"id": "CheckRegister",
//						"viewName": "",
//						"label": "",
//						"x": "1330",
//						"y": "900",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4C8VELR0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4C8VELR1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J4C8UAK41",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J4C75SK10"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J4C8UAK40",
//									"attrs": {
//										"id": "Success",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J4C8VELR2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J4C8VELR3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#result.success"
//									},
//									"linkedSeg": "1J4EB0N190"
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
//					"jaxId": "1J4C964JH0",
//					"attrs": {
//						"id": "InputFile",
//						"viewName": "",
//						"label": "",
//						"x": "2290",
//						"y": "900",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4C96Q800",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4C96Q801",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": {
//							"type": "string",
//							"valText": "Please select the test file",
//							"localize": {
//								"EN": "Please select the test file",
//								"CN": "请选择测试的文件"
//							},
//							"localizable": true
//						},
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "true",
//						"allowEmpty": "true",
//						"showText": "true",
//						"askUpward": "false",
//						"outlet": {
//							"jaxId": "1J4C96Q7S0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4C7UH540"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1J4CAH8QI0",
//					"attrs": {
//						"id": "Again",
//						"viewName": "",
//						"label": "",
//						"x": "2775",
//						"y": "900",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Whether to retest",
//							"localize": {
//								"EN": "Whether to retest",
//								"CN": "是否重新测试"
//							},
//							"localizable": true
//						},
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1J4CAIJ490",
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
//									"jaxId": "1J4CAH8PS0",
//									"attrs": {
//										"id": "Yes",
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
//											"jaxId": "1J4CAIJ4C0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J4CAIJ4C1",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1J4CAJDI00"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1J4CAH8PS1",
//									"attrs": {
//										"id": "No",
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
//											"jaxId": "1J4CAIJ4C2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J4CAIJ4C3",
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
//					"jaxId": "1J4CAJDI00",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2890",
//						"y": "690",
//						"outlet": {
//							"jaxId": "1J4CAL9DD0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4CAJM7Q0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J4CAJM7Q0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2095",
//						"y": "690",
//						"outlet": {
//							"jaxId": "1J4CAL9DD1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4C8AJCH0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J4CFJC4C0",
//					"attrs": {
//						"id": "Fetch",
//						"viewName": "",
//						"label": "",
//						"x": "370",
//						"y": "900",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4CFO4I50",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4CFO4I51",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J4CFLVS10",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4CFRF8P0"
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
//					"jaxId": "1J4CFRF8P0",
//					"attrs": {
//						"id": "CheckStart",
//						"viewName": "",
//						"label": "",
//						"x": "580",
//						"y": "900",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4CFSOS90",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4CFSOS91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J4CFSORT1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1J4CFSHD70"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1J4CFSORT0",
//									"attrs": {
//										"id": "Result",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1J4CFSOS92",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1J4CFSOS93",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!server_start"
//									},
//									"linkedSeg": "1J4C6KPQA0"
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
//					"jaxId": "1J4CFSHD70",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "845",
//						"y": "970",
//						"outlet": {
//							"jaxId": "1J4CFSOS94",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3NQE9OT0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1J4EB0N190",
//					"attrs": {
//						"id": "RegisterSuccess",
//						"viewName": "",
//						"label": "",
//						"x": "1585",
//						"y": "885",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4EB0N191",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4EB0N192",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "Project registration API successful",
//							"localize": {
//								"EN": "Project registration API successful",
//								"CN": "项目注册API成功"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1J4EB0N193",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4C8795B0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J4KBBMRK0",
//					"attrs": {
//						"id": "FakeSetup",
//						"viewName": "",
//						"label": "",
//						"x": "1290",
//						"y": "370",
//						"desc": "This is an AISeg.",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4KBE0500",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4KBE0501",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J4KBC9ST0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
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
//					"def": "callLLM",
//					"jaxId": "1J4KMNBDP0",
//					"attrs": {
//						"id": "ExtracUsage",
//						"viewName": "",
//						"label": "",
//						"x": "1060",
//						"y": "650",
//						"desc": "Excute a LLM call.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4KNCR3K0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4KNCR3K1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "Claude",
//						"mode": "claude-3-7-sonnet-latest",
//						"system": "#`请你作为用户助手，根据已部署的项目文档中 **Quick Start**、**Usage**、**Examples**、**Command Line Tools** 等使用说明部分，以及部署成功时总结的部署指南，面向普通用户提取并整理以下信息：\n\n1. 基本使用示例\n2. 命令行使用方式\n3. 主要功能列表\n\n重点关注项目提供的1个核心功能（如 OCR、TTS 等），并对该功能尝试识别：\n**功能名称**\n**功能描述**\n**使用方法**（命令行示例）\n\n注意:\n1. 你所选择的功能在命令行使用中必须存在输入参数，且参数必须为text或filePath，其余参数均应该有默认且可以直接使用的参数，不需要用户自己填写或修改，即在命令行示例中只能有输入文本/输入文件路径/输出文件路径，其余参数均应选择最合适的值，并和功能描述相对应。\n2. 输入的文本/文件路径只能有一个。\n3. 如果输出的filePath是一个文件夹/目录的路径，请在output_description中指明需要压缩为zip文件，输出的格式是zip的路径，内容是A zip file containing ...。\n4. 如果命令行执行示例中包含文件路径，请使用绝对路径，例如：python /Users/agenthub/code/ai2apps/agents/AutoDeploy/projects/ml-fastvlm/predict.py ...。\n5. 请你仔细检查需要用到的文件都存在并且路径正确，尤其是模型权重的目录，确保其中包含正确的模型文件。\n6. 由于实际的部署方案与项目文档中可能有出入，生成命令后你需要仔细检查部署指南和本地文件，确保你的命令可以在本地直接复制粘贴运行。\n\n请严格按照以下 JSON 格式输出：\n\n{\n  \"reason\": \"你的思考过程\",\n  \"features\": [\n    {\n      \"name\": \"功能名称（简洁明了）\",\n      \"description\": \"功能详细描述（说明具体作用和适用场景）\",\n      \"input_type\": \"text/filePath\",\n      \"input_description\": \"输入参数的具体描述\",\n      \"output_type\": \"text/filePath\",\n      \"output_is_directory_path\": true/false,\n      \"need_zip\": true/false,\n      \"output_suffix\":\"输出结果的文件后缀名，如zip, png, md, txt 等等\"\n      \"output_description\": \"输出结果的详细描述（文件格式、内容说明）\",\n      \"command\": \"完整的命令行执行示例（可以直接复制粘贴运行）\",\n    }\n  ]\n}\n` + (($ln===\"CN\")?(\"用中文输出。\"):(\"Output in English.\"))\n\n",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#`部署指南：\n${deploy_md}\n项目文档：\n${guide_md}\n项目内包含的文件有：\n${all_files}\n`",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1J4KMNUEQ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1J4KN30G00"
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
//					"def": "callLLM",
//					"jaxId": "1J4KN30G00",
//					"attrs": {
//						"id": "Summary",
//						"viewName": "",
//						"label": "",
//						"x": "1320",
//						"y": "650",
//						"desc": "Excute a LLM call.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4KNCR3K2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4KNCR3K3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4.1",
//						"system": "#`请把输入总结成使用指南，严格按照输入给出的input_type和output_type，输出markdown格式的文本。在指南中加上这句话：已经在本机的 conda 环境 ${conda_name} 安装相关依赖，运行相关 cli 需要先激活虚拟环境。` + (($ln===\"CN\")?(\"用中文输出。\"):(\"Output in English.\"))",
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
//							"jaxId": "1J4KN4BRT0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1J4KNAFFS0"
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
//					"jaxId": "1J4KNAFFS0",
//					"attrs": {
//						"id": "Output",
//						"viewName": "",
//						"label": "",
//						"x": "1570",
//						"y": "650",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J4KNCR3K4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J4KNCR3K5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1J4KNAOVI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1J5NVTI6L0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J4M7RC9C0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1950",
//						"y": "570",
//						"outlet": {
//							"jaxId": "1J4M7ST6L0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J4M7RKJG0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J4M7RKJG0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "150",
//						"y": "570",
//						"outlet": {
//							"jaxId": "1J4M7ST6L1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J3I4OI7M0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1J5NMNSHC0",
//					"attrs": {
//						"id": "ListFiles",
//						"viewName": "",
//						"label": "",
//						"x": "830",
//						"y": "650",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J5NNNV2N0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J5NNNV2N1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#'find \"$(pwd)\" -type f -not -path \"*/.git/*\" -not -path \"*/__pycache__/*\" -not -path \"*/.pytest_cache/*\" -not -path \"*/.tox/*\" -not -path \"*/venv/*\" -not -path \"*/.venv/*\" -not -path \"*/env/*\" -not -path \"*/node_modules/*\" -not -path \"*/dist/*\" -not -path \"*/build/*\" -not -path \"*/*.egg-info/*\" -not -path \"*/.mypy_cache/*\" -not -path \"*/.coverage/*\"'",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J5NMOVBL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1J4KMNBDP0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1J5NMVNBD0",
//					"attrs": {
//						"id": "GetPath2",
//						"viewName": "",
//						"label": "",
//						"x": "595",
//						"y": "650",
//						"desc": "This is an AISeg.",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J5NNNV2N2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J5NNNV2N3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "#globalContext.bash",
//						"action": "Command",
//						"commands": "#[`cd ${dir}`]",
//						"options": "\"\"",
//						"outlet": {
//							"jaxId": "1J5NN19GV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1J5NMNSHC0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "Bash",
//					"jaxId": "1J5NNUJMV0",
//					"attrs": {
//						"id": "InitBash2",
//						"viewName": "",
//						"label": "",
//						"x": "360",
//						"y": "650",
//						"desc": "This is an AISeg.",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J5NO1GUH0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J5NO1GUI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"bashId": "\"\"",
//						"action": "Create",
//						"commands": "\"\"",
//						"options": "#{client: true}",
//						"outlet": {
//							"jaxId": "1J5NNVFAV0",
//							"attrs": {
//								"id": "Result",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1J5NMVNBD0"
//						}
//					},
//					"icon": "terminal.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J5NVTI6L0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1695",
//						"y": "780",
//						"outlet": {
//							"jaxId": "1J5O011E40",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1J5NVTTCV0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1J5NVTTCV0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "400",
//						"y": "780",
//						"outlet": {
//							"jaxId": "1J5O011E41",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "Outlet."
//							},
//							"linkedSeg": "1J4CFJC4C0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个帮助用户自动部署github项目的agent，需要给出github的链接如https://github.com/Avdpro/ai2apps或repo的名称如Avdpro/ai2apps。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"\",\"pathInHub\":\"AutoDeploy\",\"chatEntry\":false,\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
//	}
//}