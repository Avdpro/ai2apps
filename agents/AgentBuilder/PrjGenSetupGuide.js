//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1IH3DV3E30MoreImports*/
import fsp from 'fs/promises';
/*}#1IH3DV3E30MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const VFACT=null;
/*#{1IH3DV3E30StartDoc*/
/*}#1IH3DV3E30StartDoc*/
//----------------------------------------------------------------------------
let PrjGenSetupGuide=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let RAGQuery,GetRagGuide,HasRagGuide,GenGuide,ReadMe,ShowGuide,FixGuide,AskFix,InputFix,EditGuide,CheckChange,PushRag,Finish,ShowRAG,AskUseRAG;
	let guide="";
	let env=globalContext.env;
	let project=globalContext.project;
	let guidesJSON={};
	let guideChanged=false;
	let taskJob=`你是一个生成已下载到本地的GitHub项目的安装部署指南的AI。
请找到并阅读项目的ReadMe文件及相关的文档，生成下载项目后，安装/配置/部署项目需要的操作的指导说明，例如：
- 安装依赖库
- 下载运行需要的资料如模型等
- 环境配置
- 如果需要的话，编译

你的输出应该分步骤，尽量清晰简洁，不要包括与当前平台的安装配置无关的信息。
请最终输出Markdown格式的安装部署指南。
`;
	let ragAddress=globalContext.rag?.solution||"http://localhost:222/solution/";
	
	/*#{1IH3DV3E30LocalVals*/
	if(globalContext.rag && globalContext.rag.solution){
		ragAddress=globalContext.rag.solution;
	}
	/*}#1IH3DV3E30LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IH3DV3E30ParseArgs*/
		/*}#1IH3DV3E30ParseArgs*/
	}
	
	/*#{1IH3DV3E30PreContext*/
	/*}#1IH3DV3E30PreContext*/
	context={};
	/*#{1IH3DV3E30PostContext*/
	/*}#1IH3DV3E30PostContext*/
	let agent,segs={};
	segs["RAGQuery"]=RAGQuery=async function(input){//:1II9TCPO20
		let result;
		let sourcePath=pathLib.join(basePath,"./RagQuery.js");
		let arg={"address":ragAddress,"query":"","tags":""};
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:GetRagGuide,result:(result),preSeg:"1II9TCPO20",outlet:"1II9TDFD60"};
	};
	RAGQuery.jaxId="1II9TCPO20"
	RAGQuery.url="RAGQuery@"+agentURL
	
	segs["GetRagGuide"]=GetRagGuide=async function(input){//:1IH3DVL000
		let result=input
		/*#{1IH3DVL000Code*/
		let path,json;
		if(result){
			guide=result;
		}else{
			path=pathLib.join(env.rootPath,"guides.json");
			try{
				json=await fsp.readFile(path,"utf8");
				json=JSON.parse(json);
				guide=json[project.url]||"";
				guidesJSON=json;
			}catch(err){
				guidesJSON={};			
				guide="";
			}
		}
		/*}#1IH3DVL000Code*/
		return {seg:HasRagGuide,result:(result),preSeg:"1IH3DVL000",outlet:"1IH3EFDB70"};
	};
	GetRagGuide.jaxId="1IH3DVL000"
	GetRagGuide.url="GetRagGuide@"+agentURL
	
	segs["HasRagGuide"]=HasRagGuide=async function(input){//:1IH3E0A720
		let result=input;
		if(!!guide){
			return {seg:ShowRAG,result:(input),preSeg:"1IH3E0A720",outlet:"1IH3EFDB71"};
		}
		return {seg:ReadMe,result:(result),preSeg:"1IH3E0A720",outlet:"1IH3EFDB72"};
	};
	HasRagGuide.jaxId="1IH3E0A720"
	HasRagGuide.url="HasRagGuide@"+agentURL
	
	segs["GenGuide"]=GenGuide=async function(input){//:1IH3E0TBC0
		let prompt;
		let result=null;
		/*#{1IH3E0TBC0Input*/
		/*}#1IH3E0TBC0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"text"
		};
		let chatMem=GenGuide.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
### 你是一个精简、修正项目安装指南的AI

当前有一个从GitHub下载的项目 ${project.name}。
项目下载后的本地项目路径是：${project.dirPath}。

当前的软硬件环境描述JSON为：
\`\`\`json
${JSON.stringify(env)}
\`\`\`

项目的ReadMe内容是：
\`\`\`markdown
${project.readme}
\`\`\`

${project.conda?`注意：当前已经为工程创建/选择了conda环境：${project.conda}, 无需再创建新的conda环境了。`:""}

---
### 当前的安装指南为：
${guide}

- 不要包括与安装配置无关的项目简介等冗余信息
- 输出应该分步骤，尽量清晰简洁，不要包括与当前平台的安装配置无关的信息。
- 当前项目已下载完毕，删除指南中使用Git下载项目的部分
- 安装指南应只包含安装配置步骤，不要包括测试运行项目的内容。
`},
		];
		/*#{1IH3E0TBC0PrePrompt*/
		/*}#1IH3E0TBC0PrePrompt*/
		prompt="请输出总结";
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		/*#{1IH3E0TBC0PreCall*/
		/*}#1IH3E0TBC0PreCall*/
		result=(result===null)?(await session.callSegLLM("GenGuide@"+agentURL,opts,messages,true)):result;
		/*#{1IH3E0TBC0PostCall*/
		guide=result;
		guideChanged=true;
		/*}#1IH3E0TBC0PostCall*/
		return {seg:ShowGuide,result:(result),preSeg:"1IH3E0TBC0",outlet:"1IH3EFDB73"};
	};
	GenGuide.jaxId="1IH3E0TBC0"
	GenGuide.url="GenGuide@"+agentURL
	
	segs["ReadMe"]=ReadMe=async function(input){//:1II2F5URC0
		let result;
		let sourcePath=pathLib.join(basePath,"./SysHandleTask.js");
		let arg={"task":"生成项目安装部署指南","roleTask":taskJob,"prjDesc":"","guide":"","tools":"genGuide","handleIssue":false};
		/*#{1II2F5URC0Input*/
		/*}#1II2F5URC0Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1II2F5URC0Output*/
		if(result && result.result==="Finish"){
			guide=result.content;
			guideChanged=true;
		}
		/*}#1II2F5URC0Output*/
		return {seg:GenGuide,result:(result),preSeg:"1II2F5URC0",outlet:"1II2FC6DK0"};
	};
	ReadMe.jaxId="1II2F5URC0"
	ReadMe.url="ReadMe@"+agentURL
	
	segs["ShowGuide"]=ShowGuide=async function(input){//:1IH3E1F0B0
		let result=input;
		let opts={};
		let role="assistant";
		let content=(($ln==="CN")?(`## ${guideChanged?"修改后的":""}安装指南 \n${guide}`):(`## ${guideChanged?"Modified ":""}Setup Guide \n${guide}`));
		session.addChatText(role,content,opts);
		return {seg:AskFix,result:(result),preSeg:"1IH3E1F0B0",outlet:"1IH3EFDB74"};
	};
	ShowGuide.jaxId="1IH3E1F0B0"
	ShowGuide.url="ShowGuide@"+agentURL
	
	segs["FixGuide"]=FixGuide=async function(input){//:1IH3FVJBE0
		let prompt;
		let result=null;
		/*#{1IH3FVJBE0Input*/
		/*}#1IH3FVJBE0Input*/
		
		let opts={
			platform:"OpenAI",
			mode:"gpt-4o",
			maxToken:2000,
			temperature:0,
			topP:1,
			fqcP:0,
			prcP:0,
			secret:false,
			responseFormat:"json_object"
		};
		let chatMem=FixGuide.messages
		let seed="";
		if(seed!==undefined){opts.seed=seed;}
		let messages=[
			{role:"system",content:`
你是一个根据用户Prompt修改GitHub项目安装部署指南的AI：
---
当前有一个从GitHub下载的项目 ${project.name}。
项目下载后的本地项目路径是：${project.dirPath}。

当前的软硬件环境描述JSON为：
\`\`\`json
${JSON.stringify(env)}
\`\`\`

项目的ReadMe内容是：
\`\`\`markdown
${project.readme}
\`\`\`

${project.conda?`注意：当前已经为工程创建/选择了conda环境：${project.conda}, 无需再创建新的conda环境了。`:""}

生成的安装部署说明的内容是下载项目后要部署/测试/运行项目需要的额外操作的指导说明，例如：
- 安装依赖库
- 下载运行需要的模型等
- 环境配置
- 编译
- 运行/测试方法

你的输出应该分步骤，尽量清晰简洁，不要包括与安装配资好以及当前平台无关的信息。

当前的安装指南是：
\`\`\`markdown
${guide}
\`\`\`

请根据用户的指导修改并重新用JSON输出安装部署指南。

输出JSON例子：
\`\`\`
{
	guide:"...modified guide content..."
}
\`\`\`
属性 "guide" 里是你修改后的安装指南内容
`},
		];
		/*#{1IH3FVJBE0PrePrompt*/
		/*}#1IH3FVJBE0PrePrompt*/
		prompt=`用户修改指导：${input}`;
		if(prompt!==null){
			if(typeof(prompt)!=="string"){
				prompt=JSON.stringify(prompt,null,"	");
			}
			messages.push({role:"user",content:prompt});
		}
		/*#{1IH3FVJBE0PreCall*/
		/*}#1IH3FVJBE0PreCall*/
		result=(result===null)?(await session.callSegLLM("FixGuide@"+agentURL,opts,messages,true)):result;
		result=trimJSON(result);
		/*#{1IH3FVJBE0PostCall*/
		guide=result.guide;
		guideChanged=true;
		/*}#1IH3FVJBE0PostCall*/
		return {seg:ShowGuide,result:(result),preSeg:"1IH3FVJBE0",outlet:"1IH3G0AP10"};
	};
	FixGuide.jaxId="1IH3FVJBE0"
	FixGuide.url="FixGuide@"+agentURL
	
	segs["AskFix"]=AskFix=async function(input){//:1IH3E6K5Q0
		let prompt=("是否修改当前安装指南？")||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("确认指南"):("Guide OK")))||"OK";
		let button2=((($ln==="CN")?("修改指南"):("Modify Guide")))||"Cancel";
		let button3=((($ln==="CN")?("编辑"):("Edit")))||"";
		let result="";
		let value=0;
		if(silent){
			result=input;
			return {seg:CheckChange,result:(result),preSeg:"1IH3E6K5Q0",outlet:"1IH3E6K520"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=(input)||result;
			return {seg:CheckChange,result:(result),preSeg:"1IH3E6K5Q0",outlet:"1IH3E6K520"};
		}
		if(value===2){
			result=("")||result;
			return {seg:EditGuide,result:(result),preSeg:"1IH3E6K5Q0",outlet:"1IHUBGC2T0"};
		}
		result=("")||result;
		return {seg:InputFix,result:(result),preSeg:"1IH3E6K5Q0",outlet:"1IH3E6K521"};
	
	};
	AskFix.jaxId="1IH3E6K5Q0"
	AskFix.url="AskFix@"+agentURL
	
	segs["InputFix"]=InputFix=async function(input){//:1IH3EGTKC0
		let tip=((($ln==="CN")?("请给出修改建议"):("Please provide suggestions for modification")));
		let tipRole=("assistant");
		let placeholder=((($ln==="CN")?("修改指导"):("Editing prompt")));
		let text=("");
		let result="";
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		return {seg:FixGuide,result:(result),preSeg:"1IH3EGTKC0",outlet:"1IH3EIESO0"};
	};
	InputFix.jaxId="1IH3EGTKC0"
	InputFix.url="InputFix@"+agentURL
	
	segs["EditGuide"]=EditGuide=async function(input){//:1IHUBDPA20
		let result;
		let role="assistant";
		let tip="";
		let showResult=false;
		let dlgVO={title:"Eidt guide",text:guide};
		/*#{1IHUBDPA20Pre*/
		/*}#1IHUBDPA20Pre*/
		result= await session.askUserDlg({"dlgPath":"/@editkit/ui/DlgLongText.js","arg":dlgVO,"role":role,tip:tip,showResult:showResult});
		/*#{1IHUBDPA20Codes*/
		if(result!==null){
			guide=result;
			guideChanged=true;
		}
		/*}#1IHUBDPA20Codes*/
		return {seg:ShowGuide,result:(result),preSeg:"1IHUBDPA20",outlet:"1IHUBGC2T1"};
	};
	EditGuide.jaxId="1IHUBDPA20"
	EditGuide.url="EditGuide@"+agentURL
	
	segs["CheckChange"]=CheckChange=async function(input){//:1IHUERB330
		let result=input;
		if(guideChanged){
			return {seg:PushRag,result:(input),preSeg:"1IHUERB330",outlet:"1IHUEUBIT0"};
		}
		return {seg:Finish,result:(result),preSeg:"1IHUERB330",outlet:"1IHUEUBIU0"};
	};
	CheckChange.jaxId="1IHUERB330"
	CheckChange.url="CheckChange@"+agentURL
	
	segs["PushRag"]=PushRag=async function(input){//:1IHUF8D7J0
		let result;
		let sourcePath=pathLib.join(basePath,"./RagPush.js");
		let arg={"desc":`GitHub 项目 ${project.url} 安装指南`,"doc":guide,"tags":"github,setup","env":env};
		/*#{1IHUF8D7J0Input*/
		let path;
		guidesJSON[project.url]=guide;
		path=pathLib.join(env.rootPath,"guides.json");
		await fsp.writeFile(path,JSON.stringify(guidesJSON,null,"\t"));
		/*}#1IHUF8D7J0Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IHUF8D7J0Output*/
		/*}#1IHUF8D7J0Output*/
		return {seg:Finish,result:(result),preSeg:"1IHUF8D7J0",outlet:"1IHUFF7730"};
	};
	PushRag.jaxId="1IHUF8D7J0"
	PushRag.url="PushRag@"+agentURL
	
	segs["Finish"]=Finish=async function(input){//:1IH3EBOUE0
		let result=input
		/*#{1IH3EBOUE0Code*/
		result=guide;
		/*}#1IH3EBOUE0Code*/
		return {result:result};
	};
	Finish.jaxId="1IH3EBOUE0"
	Finish.url="Finish@"+agentURL
	
	segs["ShowRAG"]=ShowRAG=async function(input){//:1II2MG6ME0
		let result=input;
		let opts={};
		let role="assistant";
		let content=`知识库中找到的安装指南 \n${guide}`;
		session.addChatText(role,content,opts);
		return {seg:AskUseRAG,result:(result),preSeg:"1II2MG6ME0",outlet:"1II2MS12Q0"};
	};
	ShowRAG.jaxId="1II2MG6ME0"
	ShowRAG.url="ShowRAG@"+agentURL
	
	segs["AskUseRAG"]=AskUseRAG=async function(input){//:1II2MIEL00
		let prompt=((($ln==="CN")?("是否使用来自知识库的指南？"):("Do you want to use the guides from the knowledge base?")))||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=((($ln==="CN")?("使用"):("Use")))||"OK";
		let button2=((($ln==="CN")?("重新生成"):("Regenerate")))||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			return {seg:AskFix,result:(result),preSeg:"1II2MIEL00",outlet:"1II2MIEKL0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			return {seg:AskFix,result:(result),preSeg:"1II2MIEL00",outlet:"1II2MIEKL0"};
		}
		result=("")||result;
		return {seg:ReadMe,result:(result),preSeg:"1II2MIEL00",outlet:"1II2MIEKL1"};
	
	};
	AskUseRAG.jaxId="1II2MIEL00"
	AskUseRAG.url="AskUseRAG@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"PrjGenSetupGuide",
		url:agentURL,
		autoStart:true,
		jaxId:"1IH3DV3E30",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IH3DV3E30PreEntry*/
			/*}#1IH3DV3E30PreEntry*/
			result={seg:RAGQuery,"input":input};
			/*#{1IH3DV3E30PostEntry*/
			/*}#1IH3DV3E30PostEntry*/
			return result;
		},
		/*#{1IH3DV3E30MoreAgentAttrs*/
		/*}#1IH3DV3E30MoreAgentAttrs*/
	};
	/*#{1IH3DV3E30PostAgent*/
	/*}#1IH3DV3E30PostAgent*/
	return agent;
};
/*#{1IH3DV3E30ExCodes*/
/*}#1IH3DV3E30ExCodes*/

//#CodyExport>>>
let ChatAPI=[{
	def:{
		name: "PrjGenSetupGuide",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	path: "/@AgentBuilder/PrjGenSetupGuide.js"
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
		name:"PrjGenSetupGuide",showName:"PrjGenSetupGuide",icon:"agent.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["PrjGenSetupGuide"]=
	function(seg){
		let coder=this.coder;
		let segName=seg.idVal.val;
		let exportDebug=this.isExportDebug();
		segName=(segName &&varNameRegex.test(segName))?segName:("SEG"+seg.jaxId);
		coder.packText(`segs["${segName}"]=${segName}=async function(input){//:${seg.jaxId}`);
		coder.indentMore();coder.newLine();
		{
			coder.packText(`let result,args={};`);coder.newLine();
			this.packExtraCodes(coder,seg,"PreCodes");
			coder.packText(`result= await session.pipeChat("/@AgentBuilder/PrjGenSetupGuide.js",args,false);`);coder.newLine();
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
/*#{1IH3DV3E30PostDoc*/
/*}#1IH3DV3E30PostDoc*/


export default PrjGenSetupGuide;
export{PrjGenSetupGuide,ChatAPI};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IH3DV3E30",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IH3DV3E31",
//			"attrs": {
//				"PrjGenSetupGuide": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IH3DV3E37",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IH3DV3E38",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IH3DV3E39",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IH3DV3E310",
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
//			"jaxId": "1IH3DV3E32",
//			"attrs": {}
//		},
//		"entry": "RAGQuery",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH3DV3E33",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IH3DV3E34",
//			"attrs": {
//				"guide": {
//					"type": "string",
//					"valText": ""
//				},
//				"env": {
//					"type": "auto",
//					"valText": "#globalContext.env"
//				},
//				"project": {
//					"type": "auto",
//					"valText": "#globalContext.project"
//				},
//				"guidesJSON": {
//					"type": "auto",
//					"valText": "{}"
//				},
//				"guideChanged": {
//					"type": "bool",
//					"valText": "false"
//				},
//				"taskJob": {
//					"type": "string",
//					"valText": "#`你是一个生成已下载到本地的GitHub项目的安装部署指南的AI。\n请找到并阅读项目的ReadMe文件及相关的文档，生成下载项目后，安装/配置/部署项目需要的操作的指导说明，例如：\n- 安装依赖库\n- 下载运行需要的资料如模型等\n- 环境配置\n- 如果需要的话，编译\n\n你的输出应该分步骤，尽量清晰简洁，不要包括与当前平台的安装配置无关的信息。\n请最终输出Markdown格式的安装部署指南。\n`"
//				},
//				"ragAddress": {
//					"type": "string",
//					"valText": "#globalContext.rag?.solution||\"http://localhost:222/solution/\""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IH3DV3E35",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IH3DV3E36",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "aiBot",
//					"jaxId": "1II9TCPO20",
//					"attrs": {
//						"id": "RAGQuery",
//						"viewName": "",
//						"label": "",
//						"x": "90",
//						"y": "205",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II9TDFDF0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II9TDFDF1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/RagQuery.js",
//						"argument": "{\"address\":\"#ragAddress\",\"query\":\"\",\"tags\":\"\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1II9TDFD60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3DVL000"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH3DVL000",
//					"attrs": {
//						"id": "GetRagGuide",
//						"viewName": "",
//						"label": "",
//						"x": "330",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH3EFDBA0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH3EFDBA1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH3EFDB70",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3E0A720"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IH3E0A720",
//					"attrs": {
//						"id": "HasRagGuide",
//						"viewName": "",
//						"label": "",
//						"x": "575",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH3EFDBA2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH3EFDBA3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH3EFDB72",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1II2F5URC0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IH3EFDB71",
//									"attrs": {
//										"id": "RagGuide",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH3EFDBA4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH3EFDBA5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!guide"
//									},
//									"linkedSeg": "1II2MG6ME0"
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
//					"jaxId": "1IH3E0TBC0",
//					"attrs": {
//						"id": "GenGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1090",
//						"y": "285",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH3EFDBA6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH3EFDBA7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`\n### 你是一个精简、修正项目安装指南的AI\n\n当前有一个从GitHub下载的项目 ${project.name}。\n项目下载后的本地项目路径是：${project.dirPath}。\n\n当前的软硬件环境描述JSON为：\n\\`\\`\\`json\n${JSON.stringify(env)}\n\\`\\`\\`\n\n项目的ReadMe内容是：\n\\`\\`\\`markdown\n${project.readme}\n\\`\\`\\`\n\n${project.conda?`注意：当前已经为工程创建/选择了conda环境：${project.conda}, 无需再创建新的conda环境了。`:\"\"}\n\n---\n### 当前的安装指南为：\n${guide}\n\n- 不要包括与安装配置无关的项目简介等冗余信息\n- 输出应该分步骤，尽量清晰简洁，不要包括与当前平台的安装配置无关的信息。\n- 当前项目已下载完毕，删除指南中使用Git下载项目的部分\n- 安装指南应只包含安装配置步骤，不要包括测试运行项目的内容。\n`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "请输出总结",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IH3EFDB73",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3E1F0B0"
//						},
//						"secret": "false",
//						"allowCheat": "false",
//						"GPTCheats": {
//							"attrs": [
//								{
//									"type": "object",
//									"def": "GPTCheat",
//									"jaxId": "1IH5R5JAF0",
//									"attrs": {
//										"prompt": "",
//										"reply": "#\"根据当前的环境和项目的ReadMe，以下是下载项目后在本地部署、测试和运行AI2Apps项目所需的步骤：\\n\\n### 步骤1：项目下载\\n确保已经通过以下命令克隆项目：\\n```bash\\ngit clone https://github.com/Avdpro/ai2apps.git\\n```\\n\\n### 步骤2：环境配置\\n1. **无需修改.env文件：**\\n   - 请确保已经正确配置了OpenAI API Key和服务器端口（默认是3015），无需在项目中修改`.env`文件。\\n\\n### 步骤3：安装依赖\\n1. **确保使用的是Node.js（版本应与v20.11.0兼容）：**\\n   - 已经通过环境信息确认Node路径为`/usr/local/bin/node`。\\n\\n2. **安装项目依赖：**\\n   - 在项目目录下运行以下命令安装所需的Node.js依赖：\\n     ```bash\\n     npm install\\n     ```\\n\\n### 步骤4：启动服务\\n1. **启动项目：**\\n   - 在项目目录下执行以下命令来启动项目服务：\\n     ```bash\\n     node ./start.js\\n     ```\\n   - 假设使用默认端口3015，在浏览器中打开以下URL访问项目：\\n     ```\\n     http://localhost:3015/\\n     ```\\n\\n### 步骤5：项目测试\\n1. **首次访问：**\\n   - 初次访问时，系统将进行安装和配置过程。\\n\\n2. **使用项目向导：**\\n   - 成功启动后，点击\\\"Project Wizard\\\"开始创建AI Agent项目。\\n\\n这样就成功在本地部署并运行了AI2Apps项目，您可以根据需要进行进一步的开发和测试。\""
//									}
//								}
//							]
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
//					"def": "aiBot",
//					"jaxId": "1II2F5URC0",
//					"attrs": {
//						"id": "ReadMe",
//						"viewName": "",
//						"label": "",
//						"x": "870",
//						"y": "285",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II2FC6DM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II2FC6DM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/SysHandleTask.js",
//						"argument": "{\"task\":\"生成项目安装部署指南\",\"roleTask\":\"#taskJob\",\"prjDesc\":\"\",\"guide\":\"\",\"tools\":\"genGuide\",\"handleIssue\":\"#false\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1II2FC6DK0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3E0TBC0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IH3E1F0B0",
//					"attrs": {
//						"id": "ShowGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1335",
//						"y": "285",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH3EFDBA8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH3EFDBA9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "#`## ${guideChanged?\"Modified \":\"\"}Setup Guide \\n${guide}`",
//							"localize": {
//								"EN": "#`## ${guideChanged?\"Modified \":\"\"}Setup Guide \\n${guide}`",
//								"CN": "#`## ${guideChanged?\"修改后的\":\"\"}安装指南 \\n${guide}`"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IH3EFDB74",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3E6K5Q0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "callLLM",
//					"jaxId": "1IH3FVJBE0",
//					"attrs": {
//						"id": "FixGuide",
//						"viewName": "",
//						"label": "",
//						"x": "2025",
//						"y": "225",
//						"desc": "执行一次LLM调用。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH3G0AP20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH3G0AP21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"platform": "\"OpenAI\"",
//						"mode": "gpt-4o",
//						"system": "#`\n你是一个根据用户Prompt修改GitHub项目安装部署指南的AI：\n---\n当前有一个从GitHub下载的项目 ${project.name}。\n项目下载后的本地项目路径是：${project.dirPath}。\n\n当前的软硬件环境描述JSON为：\n\\`\\`\\`json\n${JSON.stringify(env)}\n\\`\\`\\`\n\n项目的ReadMe内容是：\n\\`\\`\\`markdown\n${project.readme}\n\\`\\`\\`\n\n${project.conda?`注意：当前已经为工程创建/选择了conda环境：${project.conda}, 无需再创建新的conda环境了。`:\"\"}\n\n生成的安装部署说明的内容是下载项目后要部署/测试/运行项目需要的额外操作的指导说明，例如：\n- 安装依赖库\n- 下载运行需要的模型等\n- 环境配置\n- 编译\n- 运行/测试方法\n\n你的输出应该分步骤，尽量清晰简洁，不要包括与安装配资好以及当前平台无关的信息。\n\n当前的安装指南是：\n\\`\\`\\`markdown\n${guide}\n\\`\\`\\`\n\n请根据用户的指导修改并重新用JSON输出安装部署指南。\n\n输出JSON例子：\n\\`\\`\\`\n{\n\tguide:\"...modified guide content...\"\n}\n\\`\\`\\`\n属性 \"guide\" 里是你修改后的安装指南内容\n`",
//						"temperature": "0",
//						"maxToken": "2000",
//						"topP": "1",
//						"fqcP": "0",
//						"prcP": "0",
//						"messages": {
//							"attrs": []
//						},
//						"prompt": "#`用户修改指导：${input}`",
//						"seed": "",
//						"outlet": {
//							"jaxId": "1IH3G0AP10",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3EIHIN0"
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
//					"def": "askConfirm",
//					"jaxId": "1IH3E6K5Q0",
//					"attrs": {
//						"id": "AskFix",
//						"viewName": "",
//						"label": "",
//						"x": "1570",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "是否修改当前安装指南？",
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IH3E6K520",
//									"attrs": {
//										"id": "GuideOK",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Guide OK",
//											"localize": {
//												"EN": "Guide OK",
//												"CN": "确认指南"
//											},
//											"localizable": true
//										},
//										"result": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH3EFDBA10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH3EFDBA11",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHUERB330"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IH3E6K521",
//									"attrs": {
//										"id": "Modify",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Modify Guide",
//											"localize": {
//												"EN": "Modify Guide",
//												"CN": "修改指南"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IH3EFDBA12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IH3EFDBA13",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IH3EGTKC0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IHUBGC2T0",
//									"attrs": {
//										"id": "Edit",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Edit",
//											"localize": {
//												"EN": "Edit",
//												"CN": "编辑"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHUBGC300",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHUBGC301",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IHUBDPA20"
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
//					"jaxId": "1IH3EGTKC0",
//					"attrs": {
//						"id": "InputFix",
//						"viewName": "",
//						"label": "",
//						"x": "1780",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IH3EIESP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH3EIESP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": {
//							"type": "string",
//							"valText": "Please provide suggestions for modification",
//							"localize": {
//								"EN": "Please provide suggestions for modification",
//								"CN": "请给出修改建议"
//							},
//							"localizable": true
//						},
//						"tipRole": "Assistant",
//						"placeholder": {
//							"type": "string",
//							"valText": "Editing prompt",
//							"localize": {
//								"EN": "Editing prompt",
//								"CN": "修改指导"
//							},
//							"localizable": true
//						},
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IH3EIESO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3FVJBE0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IH3EIHIN0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2155",
//						"y": "390",
//						"outlet": {
//							"jaxId": "1IH3EJ31S0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHUBQ9BG0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IH3EIQH10",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1365",
//						"y": "390",
//						"outlet": {
//							"jaxId": "1IH3EJ31S1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3E1F0B0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IHUBQ9BG0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1915",
//						"y": "390",
//						"outlet": {
//							"jaxId": "1IHUBQPCT0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3EIQH10"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askUIDlg",
//					"jaxId": "1IHUBDPA20",
//					"attrs": {
//						"id": "EditGuide",
//						"viewName": "",
//						"label": "",
//						"x": "1780",
//						"y": "300",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHUBGC302",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHUBGC303",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "/@editkit/ui/DlgLongText.js",
//						"callArg": "#{title:\"Eidt guide\",text:guide}",
//						"role": "Assistant",
//						"tip": "",
//						"showResult": "false",
//						"outlet": {
//							"jaxId": "1IHUBGC2T1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IHUBQ9BG0"
//						}
//					},
//					"icon": "idcard.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IHUERB330",
//					"attrs": {
//						"id": "CheckChange",
//						"viewName": "",
//						"label": "",
//						"x": "1780",
//						"y": "125",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHUEUBJ30",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHUEUBJ31",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IHUEUBIU0",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IH3EBOUE0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IHUEUBIT0",
//									"attrs": {
//										"id": "Changed",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IHUEUBJ32",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IHUEUBJ33",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#guideChanged"
//									},
//									"linkedSeg": "1IHUF8D7J0"
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
//					"jaxId": "1IHUF8D7J0",
//					"attrs": {
//						"id": "PushRag",
//						"viewName": "",
//						"label": "",
//						"x": "2025",
//						"y": "80",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IHUFGTD70",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IHUFGTD71",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/RagPush.js",
//						"argument": "{\"desc\":\"#`GitHub 项目 ${project.url} 安装指南`\",\"doc\":\"#guide\",\"tags\":\"github,setup\",\"env\":\"#env\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IHUFF7730",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3EBOUE0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IH3EBOUE0",
//					"attrs": {
//						"id": "Finish",
//						"viewName": "",
//						"label": "",
//						"x": "2260",
//						"y": "140",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IH3EFDBA14",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IH3EFDBA15",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IH3EFDB80",
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
//					"jaxId": "1II2MG6ME0",
//					"attrs": {
//						"id": "ShowRAG",
//						"viewName": "",
//						"label": "",
//						"x": "870",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1II2MS12S0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1II2MS12S1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`知识库中找到的安装指南 \\n${guide}`",
//						"outlet": {
//							"jaxId": "1II2MS12Q0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II2MIEL00"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1II2MIEL00",
//					"attrs": {
//						"id": "AskUseRAG",
//						"viewName": "",
//						"label": "",
//						"x": "1090",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": {
//							"type": "string",
//							"valText": "Do you want to use the guides from the knowledge base?",
//							"localize": {
//								"EN": "Do you want to use the guides from the knowledge base?",
//								"CN": "是否使用来自知识库的指南？"
//							},
//							"localizable": true
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1II2MIEKL0",
//									"attrs": {
//										"id": "Use",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Use",
//											"localize": {
//												"EN": "Use",
//												"CN": "使用"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1II2MS12S2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1II2MS12S3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1II2S0PU60"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1II2MIEKL1",
//									"attrs": {
//										"id": "Regenerate",
//										"desc": "输出节点。",
//										"text": {
//											"type": "string",
//											"valText": "Regenerate",
//											"localize": {
//												"EN": "Regenerate",
//												"CN": "重新生成"
//											},
//											"localizable": true
//										},
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1II2MS12S4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1II2MS12S5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1II2MOCDQ0"
//								}
//							]
//						},
//						"silent": "false"
//					},
//					"icon": "help.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1II2MOCDQ0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1275",
//						"y": "205",
//						"outlet": {
//							"jaxId": "1II2MS12S6",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II2MOERT0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1II2MOERT0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "895",
//						"y": "205",
//						"outlet": {
//							"jaxId": "1II2MS12S7",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1II2F5URC0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1II2S0PU60",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1455",
//						"y": "105",
//						"outlet": {
//							"jaxId": "1II2SHFHG0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IH3E6K5Q0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				}
//			]
//		},
//		"desc": "这是一个AI智能体。",
//		"exportAPI": "true",
//		"exportAddOn": "true",
//		"addOnOpts": "{\"name\":\"\",\"label\":\"\",\"path\":\"/@AgentBuilder/PrjGenSetupGuide.js\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"\",\"catalog\":\"AI Call\"}"
//	}
//}