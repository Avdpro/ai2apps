//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IMU8PCBA1MoreImports*/
import {tabNT} from "/@tabos";
import {} from "../data/RAGData.js";
/*}#1IMU8PCBA1MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
/*#{1IMU8PCBA1StartDoc*/
/*}#1IMU8PCBA1StartDoc*/
//----------------------------------------------------------------------------
let RagAdmin=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let AskAction,AskSubmitType,AskQueryType,InputEnvPrj,AskGuideMD,SubmitSetupDoc,ShowPushResult,QueryEnvPrj,QuerySetupDoc,ShowSetupDoc,QueryInfo,ShowInfoDoc,AskQuery,QueryDocInfo,ShowInfo,AskSolutionFile,SubmitIssueDoc,InputURL,AskDocType,AskDocFile,SEG1IN5V9DEV0,PushToHub,SubmitDoc,InputIssue,AskIssue,AskDocKB,AskKb,_1,_2,ReadPage,ShowHTML,AskSubmit,TipWork;
	/*#{1IMU8PCBA1LocalVals*/
	/*}#1IMU8PCBA1LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1IMU8PCBA1ParseArgs*/
		/*}#1IMU8PCBA1ParseArgs*/
	}
	
	/*#{1IMU8PCBA1PreContext*/
	/*}#1IMU8PCBA1PreContext*/
	context={
		prjSetupIndexVo: "",
		prjSetupQueryVo: "",
		issueIndexVo: "",
		issueQueryVo: "",
		metaDocIndexVo: "",
		metaDocQuery: "",
		metaDocQueryVo: "",
		prjSetupContent: "",
		issueContent: "",
		metaDocName: "",
		metaDocPath: "",
		htmlUrl: "",
		metaDocData: "",
		metaDocContent: "",
		/*#{1IMU8PCBA5ExCtxAttrs*/
		/*}#1IMU8PCBA5ExCtxAttrs*/
	};
	context=VFACT.flexState(context);
	/*#{1IMU8PCBA1PostContext*/
	/*}#1IMU8PCBA1PostContext*/
	let agent,segs={};
	segs["AskAction"]=AskAction=async function(input){//:1IMU8U52S0
		let prompt=("你想执行什么有关RAG的操作？")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/dbsave.svg"||"/~/-tabos/shared/assets/dot.svg",text:"提交资料",code:0},
			{icon:"/~/-tabos/shared/assets/dbload.svg"||"/~/-tabos/shared/assets/dot.svg",text:"查询知识",code:1},
			{icon:"/~/-tabos/shared/assets/help.svg"||"/~/-tabos/shared/assets/dot.svg",text:"知识库安装、使用指南",code:2},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:AskSubmitType,result:(result),preSeg:"1IMU8U52S0",outlet:"1IMU8U52C0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:AskSubmitType,result:(result),preSeg:"1IMU8U52S0",outlet:"1IMU8U52C0"};
		}else if(item.code===1){
			return {seg:AskQueryType,result:(result),preSeg:"1IMU8U52S0",outlet:"1IMU8U52C1"};
		}else if(item.code===2){
			return {seg:TipWork,result:(result),preSeg:"1IMU8U52S0",outlet:"1IN6183KL0"};
		}
		return {result:result};
	};
	AskAction.jaxId="1IMU8U52S0"
	AskAction.url="AskAction@"+agentURL
	
	segs["AskSubmitType"]=AskSubmitType=async function(input){//:1IMU9JC1G0
		let prompt=("要提交什么资料？")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/prj.svg"||"/~/-tabos/shared/assets/dot.svg",text:"提交项目部署文档",code:0},
			{icon:"/~/-tabos/shared/assets/help.svg"||"/~/-tabos/shared/assets/dot.svg",text:"提交问题解决方案文档",code:1},
			{icon:"/~/-tabos/shared/assets/hudmemo.svg"||"/~/-tabos/shared/assets/dot.svg",text:"提交本地知识文档/网页",code:2},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:InputEnvPrj,result:(result),preSeg:"1IMU9JC1G0",outlet:"1IMU9JC0U0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:InputEnvPrj,result:(result),preSeg:"1IMU9JC1G0",outlet:"1IMU9JC0U0"};
		}else if(item.code===1){
			return {seg:InputIssue,result:(result),preSeg:"1IMU9JC1G0",outlet:"1IMU9JC0U1"};
		}else if(item.code===2){
			return {seg:AskDocType,result:(result),preSeg:"1IMU9JC1G0",outlet:"1IMU9JC0U2"};
		}
		return {result:result};
	};
	AskSubmitType.jaxId="1IMU9JC1G0"
	AskSubmitType.url="AskSubmitType@"+agentURL
	
	segs["AskQueryType"]=AskQueryType=async function(input){//:1IMU9LK4D0
		let prompt=("请选择你要查询的内容")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/prj.svg"||"/~/-tabos/shared/assets/dot.svg",text:"获取项目部署文档",code:0},
			{icon:"/~/-tabos/shared/assets/help.svg"||"/~/-tabos/shared/assets/dot.svg",text:"获取问题解决方案",code:1},
			{icon:"/~/-tabos/shared/assets/hudmemo.svg"||"/~/-tabos/shared/assets/dot.svg",text:"收纳的文档信息",code:2},
		];
		let result="";
		let item=null;
		
		if(silent){
			result="";
			return {seg:QueryEnvPrj,result:(result),preSeg:"1IMU9LK4D0",outlet:"1IMU9LK3U0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:QueryEnvPrj,result:(result),preSeg:"1IMU9LK4D0",outlet:"1IMU9LK3U0"};
		}else if(item.code===1){
			return {seg:AskIssue,result:(result),preSeg:"1IMU9LK4D0",outlet:"1IMU9LK3U1"};
		}else if(item.code===2){
			return {seg:AskQuery,result:(result),preSeg:"1IMU9LK4D0",outlet:"1IMU9LK3U2"};
		}
		return {result:result};
	};
	AskQueryType.jaxId="1IMU9LK4D0"
	AskQueryType.url="AskQueryType@"+agentURL
	
	segs["InputEnvPrj"]=InputEnvPrj=async function(input){//:1IMUA9J4F0
		let result,resultText;
		let role="assistant";
		let text="输入当前环境信息和项目名称";
		let template="1IMUACQDA0";
		let data=input;
		let edit=true;
		if(typeof(template)==="string"){
			template=VFACT.getEditUITemplate(template)||VFACT.getUITemplate(template);
		}
		let inputVO={template:template,data:data,options:{edit:edit}};
		/*#{1IMUA9J4F0Pre*/
		/*}#1IMUA9J4F0Pre*/
		[resultText,result]=await session.askUserRaw({type:"object",text:text,data:data,template:template,role:role,edit:edit});
		context["prjSetupIndexVo"]=result;
		/*#{1IMUA9J4F0Codes*/
		/*}#1IMUA9J4F0Codes*/
		return {seg:AskGuideMD,result:(result),preSeg:"1IMUA9J4F0",outlet:"1IMUARBKO0"};
	};
	InputEnvPrj.jaxId="1IMUA9J4F0"
	InputEnvPrj.url="InputEnvPrj@"+agentURL
	
	segs["AskGuideMD"]=AskGuideMD=async function(input){//:1IMUB2F0L0
		let prompt=("请选择安装指南文件")||input;
		let resultText="";
		let fileData=null;
		let enc=null;
		let ext=null;
		let fileSys="native";
		let result="";
		let path=("");
		let filter=("");
		[resultText,result]=await session.askUserRaw({type:"input",prompt:prompt,text:"",path:path,file:fileSys,filter:filter,});
		fileData=result||(await (await fetch(resultText)).arrayBuffer());
		result=(new TextDecoder()).decode(fileData)
		context["prjSetupContent"]=result;
		return {seg:SubmitSetupDoc,result:(result),preSeg:"1IMUB2F0L0",outlet:"1IMUB3TB90"};
	};
	AskGuideMD.jaxId="1IMUB2F0L0"
	AskGuideMD.url="AskGuideMD@"+agentURL
	
	segs["SubmitSetupDoc"]=SubmitSetupDoc=async function(input){//:1IMUB42820
		let result=input
		/*#{1IMUB42820Code*/
		let res,indexVo,callVo;
		indexVo=context.prjSetupIndexVo;
		callVo={
			index:{
				env_info:{
					platform:indexVo.platform,
					arch:indexVo.arch
				},
				project_meta:{
					name:indexVo.project
				},
				procedure:context.prjSetupContent
			},
			postToRoot:indexVo.postToRoot
		};
		await tabNT.checkLogin();
		res=await tabNT.makeCall("RagIndexPrjSetup",callVo);
		if(!res){
			result=`Rag-Index network error.`;
		}else if(res.code===200){
			result=`Rag-Index success 200: ${JSON.stringify(res)}.`;
		}else{
			result=`Rag-Index error ${res.code}: ${res.info||"Error"}.`;
		}
		/*}#1IMUB42820Code*/
		return {seg:ShowPushResult,result:(result),preSeg:"1IMUB42820",outlet:"1IMUB5M7A0"};
	};
	SubmitSetupDoc.jaxId="1IMUB42820"
	SubmitSetupDoc.url="SubmitSetupDoc@"+agentURL
	
	segs["ShowPushResult"]=ShowPushResult=async function(input){//:1IMUB53210
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:AskAction,result:(result),preSeg:"1IMUB53210",outlet:"1IMUB5M7A1"};
	};
	ShowPushResult.jaxId="1IMUB53210"
	ShowPushResult.url="ShowPushResult@"+agentURL
	
	segs["QueryEnvPrj"]=QueryEnvPrj=async function(input){//:1IMUBBFHD0
		let result,resultText;
		let role="assistant";
		let text="请输入要部署的项目和目标环境信息";
		let template="1IMUACQDA0";
		let data=input;
		let edit=true;
		if(typeof(template)==="string"){
			template=VFACT.getEditUITemplate(template)||VFACT.getUITemplate(template);
		}
		let inputVO={template:template,data:data,options:{edit:edit}};
		[resultText,result]=await session.askUserRaw({type:"object",text:text,data:data,template:template,role:role,edit:edit});
		context["prjSetupQueryVo"]=result;
		return {seg:QuerySetupDoc,result:(result),preSeg:"1IMUBBFHD0",outlet:"1IMUBISF50"};
	};
	QueryEnvPrj.jaxId="1IMUBBFHD0"
	QueryEnvPrj.url="QueryEnvPrj@"+agentURL
	
	segs["QuerySetupDoc"]=QuerySetupDoc=async function(input){//:1IMUBC5KU0
		let result=input
		/*#{1IMUBC5KU0Code*/
		let queryVo,callVo,res;
		queryVo=context.prjSetupQueryVo;
		callVo={
			query:{
				env_info:{
					platform:queryVo.platform,
					arch:queryVo.arch
				},
				project_meta:{
					name:queryVo.project
				},
				procedure:context.prjSetupContent
			}
		};
		await tabNT.checkLogin();
		res=await tabNT.makeCall("RagQueryPrjSetup",callVo);
		if(!res){
			result=`Rag-Query network error.`;
		}else if(res.code===200){
			result=`# RAG系统找到的项目安装文档：\n- - -\n${res.guide}`;
		}else{
			result=`Rag-Query error ${res.code}: ${res.info||"Error"}.`;
		}
		/*}#1IMUBC5KU0Code*/
		return {seg:ShowSetupDoc,result:(result),preSeg:"1IMUBC5KU0",outlet:"1IMUBISF51"};
	};
	QuerySetupDoc.jaxId="1IMUBC5KU0"
	QuerySetupDoc.url="QuerySetupDoc@"+agentURL
	
	segs["ShowSetupDoc"]=ShowSetupDoc=async function(input){//:1IMUBF1UF0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:AskAction,result:(result),preSeg:"1IMUBF1UF0",outlet:"1IMUBISF52"};
	};
	ShowSetupDoc.jaxId="1IMUBF1UF0"
	ShowSetupDoc.url="ShowSetupDoc@"+agentURL
	
	segs["QueryInfo"]=QueryInfo=async function(input){//:1IMUBGANT0
		let result=input
		/*#{1IMUBGANT0Code*/
		let queryVo,callVo,res,tags;
		queryVo=context.issueQueryVo;
		tags=queryVo.tags?queryVo.tags.split(","):undefined;
		callVo={
			query:{
				error_desc:queryVo.issue,
				tags:tags
			}
		};
		await tabNT.checkLogin();
		res=await tabNT.makeCall("RagQueryIssue",callVo);
		if(!res){
			result=`Rag-Query network error.`;
		}else if(res.code===200){
			let docs,doc,text;
			text="";
			docs=res.docs;
			for(doc of docs){
				text+=`- - -\n${doc.metadata.solution}\n\n`;
			}
			result=`# RAG系统找到的问题解决方案文档：\n${text}`;
		}else{
			result=`Rag-Query error ${res.code}: ${res.info||"Error"}.`;
		}
		/*}#1IMUBGANT0Code*/
		return {seg:ShowInfoDoc,result:(result),preSeg:"1IMUBGANT0",outlet:"1IMUBISF54"};
	};
	QueryInfo.jaxId="1IMUBGANT0"
	QueryInfo.url="QueryInfo@"+agentURL
	
	segs["ShowInfoDoc"]=ShowInfoDoc=async function(input){//:1IMUBGU8J0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:AskAction,result:(result),preSeg:"1IMUBGU8J0",outlet:"1IMUBISF55"};
	};
	ShowInfoDoc.jaxId="1IMUBGU8J0"
	ShowInfoDoc.url="ShowInfoDoc@"+agentURL
	
	segs["AskQuery"]=AskQuery=async function(input){//:1IMUBHK0P0
		let tip=("请输入你要查询的内容");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let text=("");
		let result="";
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		context["metaDocIndexVo"]=result;
		context["metaDocQuery"]=result;
		return {seg:AskKb,result:(result),preSeg:"1IMUBHK0P0",outlet:"1IMUBISF56"};
	};
	AskQuery.jaxId="1IMUBHK0P0"
	AskQuery.url="AskQuery@"+agentURL
	
	segs["QueryDocInfo"]=QueryDocInfo=async function(input){//:1IMUBI1EE0
		let result=input
		/*#{1IMUBI1EE0Code*/
		let queryVo,callVo,res;
		queryVo=context.metaDocQueryVo;
		callVo={
			query:{
				query:context.metaDocQuery,
				knowledge_name:queryVo.kbName||"public",
				identifier:queryVo.identifier||""
			}
		};
		await tabNT.checkLogin();
		res=await tabNT.makeCall("RagQueryMetaDoc",callVo);
		if(!res){
			result=`Rag-Query network error.`;
		}else if(res.code===200){
			let docs,doc,text;
			text="";
			docs=res.docs;
			for(doc of docs){
				text+=`- - -\n${doc.page_content}\n\n`;
			}
			result=`# RAG系统找到的问题解决方案文档：\n${text}`;
		}else{
			result=`Rag-Query error ${res.code}: ${res.info||"Error"}.`;
		}
		/*}#1IMUBI1EE0Code*/
		return {seg:ShowInfo,result:(result),preSeg:"1IMUBI1EE0",outlet:"1IMUBISF57"};
	};
	QueryDocInfo.jaxId="1IMUBI1EE0"
	QueryDocInfo.url="QueryDocInfo@"+agentURL
	
	segs["ShowInfo"]=ShowInfo=async function(input){//:1IMUBIGPI0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		session.addChatText(role,content,opts);
		return {seg:AskAction,result:(result),preSeg:"1IMUBIGPI0",outlet:"1IMUBISF58"};
	};
	ShowInfo.jaxId="1IMUBIGPI0"
	ShowInfo.url="ShowInfo@"+agentURL
	
	segs["AskSolutionFile"]=AskSolutionFile=async function(input){//:1IMUBJVCC0
		let prompt=("请选择文档")||input;
		let resultText="";
		let fileData=null;
		let enc=null;
		let ext=null;
		let fileSys="native";
		let result="";
		let path=("");
		let filter=("");
		[resultText,result]=await session.askUserRaw({type:"input",prompt:prompt,text:"",path:path,file:fileSys,filter:filter,});
		fileData=result||(await (await fetch(resultText)).arrayBuffer());
		result=(new TextDecoder()).decode(fileData)
		context["issueContent"]=result;
		return {seg:SubmitIssueDoc,result:(result),preSeg:"1IMUBJVCC0",outlet:"1IMUBSUDB1"};
	};
	AskSolutionFile.jaxId="1IMUBJVCC0"
	AskSolutionFile.url="AskSolutionFile@"+agentURL
	
	segs["SubmitIssueDoc"]=SubmitIssueDoc=async function(input){//:1IMUBKC9O0
		let result=input
		/*#{1IMUBKC9O0Code*/
		let res,indexVo,callVo,tags;
		indexVo=context.issueIndexVo;
		tags=indexVo.tags?indexVo.tags.split(","):[];
		callVo={
			index:{
				error_desc:indexVo.issue,
				error_solution:context.issueContent,
				tags:tags
			},
			postToRoot:indexVo.postToRoot
		};
		await tabNT.checkLogin();
		res=await tabNT.makeCall("RagIndexIssue",callVo);
		if(!res){
			result=`Rag-Index network error.`;
		}else if(res.code===200){
			result=`Rag-Index success 200: ${JSON.stringify(res)}.`;
		}else{
			result=`Rag-Index error ${res.code}: ${res.info||"Error"}.`;
		}
		/*}#1IMUBKC9O0Code*/
		return {seg:ShowPushResult,result:(result),preSeg:"1IMUBKC9O0",outlet:"1IMUBSUDB2"};
	};
	SubmitIssueDoc.jaxId="1IMUBKC9O0"
	SubmitIssueDoc.url="SubmitIssueDoc@"+agentURL
	
	segs["InputURL"]=InputURL=async function(input){//:1IMUBOIGH0
		let tip=("请输入网页URL");
		let tipRole=("assistant");
		let placeholder=("");
		let allowFile=(false)||false;
		let text=("");
		let result="";
		/*#{1IMUBOIGH0PreCodes*/
		/*}#1IMUBOIGH0PreCodes*/
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text,allowFile:allowFile});
		if(typeof(result)==="string"){
			session.addChatText("user",result);
		}else if(result.assets && result.prompt){
			session.addChatText("user",`${result.prompt}\n- - -\n${result.assets.join("\n- - -\n")}`,{render:true});
		}else{
			session.addChatText("user",result.text||result.prompt||result);
		}
		/*#{1IMUBOIGH0PostCodes*/
		/*}#1IMUBOIGH0PostCodes*/
		context["htmlUrl"]=result;
		return {seg:ReadPage,result:(result),preSeg:"1IMUBOIGH0",outlet:"1IMUBSUDB4"};
	};
	InputURL.jaxId="1IMUBOIGH0"
	InputURL.url="InputURL@"+agentURL
	
	segs["AskDocType"]=AskDocType=async function(input){//:1IN0I2S520
		let prompt=("提交哪里的文档？")||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=false;
		let silent=false;
		let items=[
			{icon:"/~/-tabos/shared/assets/folder.svg"||"/~/-tabos/shared/assets/dot.svg",text:"上传本地设备文档文件",code:0},
			{icon:"/~/-tabos/shared/assets/cklogo.svg"||"/~/-tabos/shared/assets/dot.svg",text:"上传Tab-OS内文档",code:1},
			{icon:"/~/-tabos/shared/assets/browser.svg"||"/~/-tabos/shared/assets/dot.svg",text:"HTML网页",code:2},
		];
		let result="";
		let item=null;
		
		/*#{1IN0I2S520PreCodes*/
		context.htmlUrl=null;
		/*}#1IN0I2S520PreCodes*/
		if(silent){
			result="";
			return {seg:AskDocFile,result:(result),preSeg:"1IN0I2S520",outlet:"1IN0I2S4H0"};
		}
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1IN0I2S520PostCodes*/
		/*}#1IN0I2S520PostCodes*/
		if(typeof(item)==='string'){
			result=item;
			return {result:result};
		}else if(item.code===0){
			return {seg:AskDocFile,result:(result),preSeg:"1IN0I2S520",outlet:"1IN0I2S4H0"};
		}else if(item.code===1){
			return {seg:SEG1IN5V9DEV0,result:(result),preSeg:"1IN0I2S520",outlet:"1IN5V198Q0"};
		}else if(item.code===2){
			return {seg:InputURL,result:(result),preSeg:"1IN0I2S520",outlet:"1IN0I2S4H2"};
		}
		/*#{1IN0I2S520FinCodes*/
		/*}#1IN0I2S520FinCodes*/
		return {result:result};
	};
	AskDocType.jaxId="1IN0I2S520"
	AskDocType.url="AskDocType@"+agentURL
	
	segs["AskDocFile"]=AskDocFile=async function(input){//:1IN0J04L80
		let prompt=("请选择要提交的文档文件")||input;
		let resultText="";
		let fileData=null;
		let enc=null;
		let ext=null;
		let fileSys="native";
		let result="";
		let path=("");
		let filter=("");
		/*#{1IN0J04L80PreCodes*/
		/*}#1IN0J04L80PreCodes*/
		[resultText,result]=await session.askUserRaw({type:"input",prompt:prompt,text:"",path:path,file:fileSys,filter:filter,});
		fileData=result||(await (await fetch(resultText)).arrayBuffer());
		result=Base64.encode(fileData);
		/*#{1IN0J04L80PostCodes*/
		context.metaDocName=resultText;
		/*}#1IN0J04L80PostCodes*/
		context["metaDocData"]=result;
		return {seg:PushToHub,result:(result),preSeg:"1IN0J04L80",outlet:"1IN0J7M171"};
	};
	AskDocFile.jaxId="1IN0J04L80"
	AskDocFile.url="AskDocFile@"+agentURL
	
	segs["SEG1IN5V9DEV0"]=SEG1IN5V9DEV0=async function(input){//:1IN5V9DEV0
		let prompt=("请选择要提交的文档文件")||input;
		let resultText="";
		let fileData=null;
		let enc=null;
		let ext=null;
		let fileSys="tabos";
		let result="";
		let path=("");
		let filter=("");
		/*#{1IN5V9DEV0PreCodes*/
		/*}#1IN5V9DEV0PreCodes*/
		[resultText,result]=await session.askUserRaw({type:"input",prompt:prompt,text:"",path:path,file:fileSys,filter:filter,});
		fileData=result||(await (await fetch(resultText)).arrayBuffer());
		result=Base64.encode(fileData);
		/*#{1IN5V9DEV0PostCodes*/
		context.metaDocName=resultText;
		/*}#1IN5V9DEV0PostCodes*/
		context["metaDocData"]=result;
		return {seg:PushToHub,result:(result),preSeg:"1IN5V9DEV0",outlet:"1IN5VBMV90"};
	};
	SEG1IN5V9DEV0.jaxId="1IN5V9DEV0"
	SEG1IN5V9DEV0.url="SEG1IN5V9DEV0@"+agentURL
	
	segs["PushToHub"]=PushToHub=async function(input){//:1IN0J18DI0
		let result=input
		/*#{1IN0J18DI0Code*/
		let hubName,localFilePath;
		hubName=await session.saveHubFile(context.metaDocName,context.metaDocData);
		context.metaDocPath=await session.getHubPath(hubName);
		/*}#1IN0J18DI0Code*/
		return {seg:AskDocKB,result:(result),preSeg:"1IN0J18DI0",outlet:"1IN0J7M172"};
	};
	PushToHub.jaxId="1IN0J18DI0"
	PushToHub.url="PushToHub@"+agentURL
	
	segs["SubmitDoc"]=SubmitDoc=async function(input){//:1IN0J2BVH0
		let result=input
		/*#{1IN0J2BVH0Code*/
		let res,indexVo,callVo,tags;
		indexVo=context.metaDocIndexVo;
		callVo={
			index:{
				file_path:context.metaDocPath,
				knowledge_name:indexVo.kbName||"public",
				identifier:indexVo.identifier||""
			},
			postToRoot:indexVo.postToRoot
		};
		if(context.htmlUrl){
			callVo.index.metadata={url:context.htmlUrl};
		}
		await tabNT.checkLogin();
		res=await tabNT.makeCall("RagIndexMetaDoc",callVo);
		if(!res){
			result=`Rag-Index network error.`;
		}else if(res.code===200){
			result=`Rag-Index success 200: ${JSON.stringify(res)}.`;
		}else{
			result=`Rag-Index error ${res.code}: ${res.info||"Error"}.`;
		}
		/*}#1IN0J2BVH0Code*/
		return {seg:ShowPushResult,result:(result),preSeg:"1IN0J2BVH0",outlet:"1IN0J7M173"};
	};
	SubmitDoc.jaxId="1IN0J2BVH0"
	SubmitDoc.url="SubmitDoc@"+agentURL
	
	segs["InputIssue"]=InputIssue=async function(input){//:1IN0K868F0
		let result,resultText;
		let role="assistant";
		let text="请填写问题和标签";
		let template="1IN0JHEB20";
		let data=input;
		let edit=true;
		if(typeof(template)==="string"){
			template=VFACT.getEditUITemplate(template)||VFACT.getUITemplate(template);
		}
		let inputVO={template:template,data:data,options:{edit:edit}};
		[resultText,result]=await session.askUserRaw({type:"object",text:text,data:data,template:template,role:role,edit:edit});
		context["issueIndexVo"]=result;
		return {seg:AskSolutionFile,result:(result),preSeg:"1IN0K868F0",outlet:"1IN0LPENH0"};
	};
	InputIssue.jaxId="1IN0K868F0"
	InputIssue.url="InputIssue@"+agentURL
	
	segs["AskIssue"]=AskIssue=async function(input){//:1IN0OHTL10
		let result,resultText;
		let role="assistant";
		let text="请输入问题：";
		let template="1IN0OGMTF0";
		let data=input;
		let edit=true;
		if(typeof(template)==="string"){
			template=VFACT.getEditUITemplate(template)||VFACT.getUITemplate(template);
		}
		let inputVO={template:template,data:data,options:{edit:edit}};
		[resultText,result]=await session.askUserRaw({type:"object",text:text,data:data,template:template,role:role,edit:edit});
		context["issueQueryVo"]=result;
		return {seg:QueryInfo,result:(result),preSeg:"1IN0OHTL10",outlet:"1IN0OJKFO0"};
	};
	AskIssue.jaxId="1IN0OHTL10"
	AskIssue.url="AskIssue@"+agentURL
	
	segs["AskDocKB"]=AskDocKB=async function(input){//:1IN0TIS420
		let result,resultText;
		let role="assistant";
		let text="输入目标知识库，空白则为默认值";
		let template="1IN0TOFMS0";
		let data=input;
		let edit=true;
		if(typeof(template)==="string"){
			template=VFACT.getEditUITemplate(template)||VFACT.getUITemplate(template);
		}
		let inputVO={template:template,data:data,options:{edit:edit}};
		[resultText,result]=await session.askUserRaw({type:"object",text:text,data:data,template:template,role:role,edit:edit});
		context["metaDocIndexVo"]=result;
		return {seg:SubmitDoc,result:(result),preSeg:"1IN0TIS420",outlet:"1IN0TKLRH0"};
	};
	AskDocKB.jaxId="1IN0TIS420"
	AskDocKB.url="AskDocKB@"+agentURL
	
	segs["AskKb"]=AskKb=async function(input){//:1IN0UR41S0
		let result,resultText;
		let role="assistant";
		let text="输入目标知识库，空白则为默认值";
		let template="1IN0TOFMS0";
		let data=input;
		let edit=true;
		if(typeof(template)==="string"){
			template=VFACT.getEditUITemplate(template)||VFACT.getUITemplate(template);
		}
		let inputVO={template:template,data:data,options:{edit:edit}};
		[resultText,result]=await session.askUserRaw({type:"object",text:text,data:data,template:template,role:role,edit:edit});
		context["metaDocQueryVo"]=result;
		return {seg:QueryDocInfo,result:(result),preSeg:"1IN0UR41S0",outlet:"1IN0UR41T0"};
	};
	AskKb.jaxId="1IN0UR41S0"
	AskKb.url="AskKb@"+agentURL
	
	segs["ReadPage"]=ReadPage=async function(input){//:1IN16KO430
		let result,args={};
		args['nodeName']="AgentBuilder";
		args['callAgent']="RpaReadPage.js";
		args['callArg']={url:context.htmlUrl,format:"markdown"};
		args['checkUpdate']=true;
		/*#{1IN16KO430PreCodes*/
		/*}#1IN16KO430PreCodes*/
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		/*#{1IN16KO430PostCodes*/
		context.metaDocContent=result.content;
		result=Base64.encode(result.content);
		context.metaDocName="WebPage.md";
		/*}#1IN16KO430PostCodes*/
		context["metaDocData"]=result;
		return {seg:ShowHTML,result:(result),preSeg:"1IN16KO430",outlet:"1IN16ND3H0"};
	};
	ReadPage.jaxId="1IN16KO430"
	ReadPage.url="ReadPage@"+agentURL
	
	segs["ShowHTML"]=ShowHTML=async function(input){//:1IN4NK8C60
		let result=input;
		let opts={};
		let role="assistant";
		let content=context.metaDocContent;
		session.addChatText(role,content,opts);
		return {seg:AskSubmit,result:(result),preSeg:"1IN4NK8C60",outlet:"1IN4NRUFJ0"};
	};
	ShowHTML.jaxId="1IN4NK8C60"
	ShowHTML.url="ShowHTML@"+agentURL
	
	segs["AskSubmit"]=AskSubmit=async function(input){//:1IN4NKS5N0
		let prompt=("是否提交网页内容")||input;
		let silent=false;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let button1=("提交内容")||"OK";
		let button2=("放弃提交")||"Cancel";
		let button3="";
		let result="";
		let value=0;
		if(silent){
			result="";
			/*#{1IN4NKS5A0Silent*/
			/*}#1IN4NKS5A0Silent*/
			return {seg:PushToHub,result:(result),preSeg:"1IN4NKS5N0",outlet:"1IN4NKS5A0"};
		}
		[result,value]=await session.askUserRaw({type:"confirm",prompt:prompt,button1:button1,button2:button2,button3:button3,countdown:countdown,withChat:undefined,placeholder:placeholder});
		if(value===1){
			result=("")||result;
			/*#{1IN4NKS5A0Btn1*/
			/*}#1IN4NKS5A0Btn1*/
			return {seg:PushToHub,result:(result),preSeg:"1IN4NKS5N0",outlet:"1IN4NKS5A0"};
		}
		result=("")||result;
		return {seg:AskAction,result:(result),preSeg:"1IN4NKS5N0",outlet:"1IN4NKS5A1"};
	
	};
	AskSubmit.jaxId="1IN4NKS5N0"
	AskSubmit.url="AskSubmit@"+agentURL
	
	segs["TipWork"]=TipWork=async function(input){//:1IN73QP1T0
		let result=input;
		let opts={};
		let role="assistant";
		let content="抱歉，此功能暂未实现";
		session.addChatText(role,content,opts);
		return {seg:AskAction,result:(result),preSeg:"1IN73QP1T0",outlet:"1IN73SONF0"};
	};
	TipWork.jaxId="1IN73QP1T0"
	TipWork.url="TipWork@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"RagAdmin",
		url:agentURL,
		autoStart:true,
		jaxId:"1IMU8PCBA1",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1IMU8PCBA1PreEntry*/
			/*}#1IMU8PCBA1PreEntry*/
			result={seg:AskAction,"input":input};
			/*#{1IMU8PCBA1PostEntry*/
			/*}#1IMU8PCBA1PostEntry*/
			return result;
		},
		/*#{1IMU8PCBA1MoreAgentAttrs*/
		/*}#1IMU8PCBA1MoreAgentAttrs*/
	};
	/*#{1IMU8PCBA1PostAgent*/
	/*}#1IMU8PCBA1PostAgent*/
	return agent;
};
/*#{1IMU8PCBA1ExCodes*/
/*}#1IMU8PCBA1ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "RagAdmin",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
			}
		}
	},
	label: "{\"EN\":\"RAG operations\",\"CN\":\"RAG知识库操作\"}",
	chatEntry: "Root",
	icon: "db.svg",
	agent: RagAdmin
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
		name:"RagAdmin",showName:"{\"EN\":\"RAG operations\",\"CN\":\"RAG知识库操作\"}",icon:"db.svg",catalog:["AI Call"],
		attrs:{
			...SegObjShellAttr,
			"outlet":{name:"outlet",type:"aioutlet",def:SegOutletDef,key:1,fixed:1,edit:false,navi:"doc"}
		},
		listHint:["id","codes","desc"],
		desc:"这是一个AI智能体。"
	});
	
	DocAIAgentExporter.segTypeExporters["RagAdmin"]=
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
			coder.packText(`result= await session.pipeChat("/~/AgentBuilder/ai/RagAdmin.js",args,false);`);coder.newLine();
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
/*#{1IMU8PCBA1PostDoc*/
/*}#1IMU8PCBA1PostDoc*/


export default RagAdmin;
export{RagAdmin};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IMU8PCBA1",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IMU8PCBA1",
//			"attrs": {
//				"RagAdmin": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IMU8PCBA7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IMU8PCBA8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IMU8PCBA9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IMU8PCBA10",
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
//			"jaxId": "1IMU8PCBA2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IMU8PCBA3",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1IMU8PCBA4",
//			"attrs": {}
//		},
//		"context": {
//			"jaxId": "1IMU8PCBA5",
//			"attrs": {
//				"prjSetupIndexVo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN09VCIC0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"prjSetupQueryVo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN09VCIC1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"issueIndexVo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN09VCIC2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"issueQueryVo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN09VCIC3",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"metaDocIndexVo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN09VCIC4",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"metaDocQuery": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN27S2MF0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"metaDocQueryVo": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN09VCIC5",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"prjSetupContent": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN0ACCUB0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"issueContent": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN0ACCUB1",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"metaDocName": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN0SK6GN0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"metaDocPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN0ACCUB2",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"htmlUrl": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN0ACCUB3",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"metaDocData": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN5L4KD40",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				},
//				"metaDocContent": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IN5MF7L30",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": ""
//					}
//				}
//			}
//		},
//		"globalMockup": {
//			"jaxId": "1IMU8PCBA6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IMU8U52S0",
//					"attrs": {
//						"id": "AskAction",
//						"viewName": "",
//						"label": "",
//						"x": "125",
//						"y": "310",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "你想执行什么有关RAG的操作？",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IMUA03TQ0",
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
//									"jaxId": "1IMU8U52C0",
//									"attrs": {
//										"id": "Submit",
//										"desc": "输出节点。",
//										"text": "提交资料",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMUA03TS0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMUA03TS1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/dbsave.svg"
//									},
//									"linkedSeg": "1IMU9JC1G0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IMU8U52C1",
//									"attrs": {
//										"id": "Query",
//										"desc": "输出节点。",
//										"text": "查询知识",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMUA03TS2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMUA03TS3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/dbload.svg"
//									},
//									"linkedSeg": "1IMU9LK4D0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IN6183KL0",
//									"attrs": {
//										"id": "Help",
//										"desc": "输出节点。",
//										"text": "知识库安装、使用指南",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IN61DNKJ0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IN61DNKJ1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/help.svg"
//									},
//									"linkedSeg": "1IN73QP1T0"
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
//					"jaxId": "1IMU9JC1G0",
//					"attrs": {
//						"id": "AskSubmitType",
//						"viewName": "",
//						"label": "",
//						"x": "405",
//						"y": "105",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "要提交什么资料？",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IMUA03TR0",
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
//									"jaxId": "1IMU9JC0U0",
//									"attrs": {
//										"id": "SetupDoc",
//										"desc": "输出节点。",
//										"text": "提交项目部署文档",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMUA03TS4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMUA03TS5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/prj.svg"
//									},
//									"linkedSeg": "1IMUA9J4F0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IMU9JC0U1",
//									"attrs": {
//										"id": "IssueDoc",
//										"desc": "输出节点。",
//										"text": "提交问题解决方案文档",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMUA03TS6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMUA03TS7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/help.svg"
//									},
//									"linkedSeg": "1IN0K868F0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IMU9JC0U2",
//									"attrs": {
//										"id": "MetaDoc",
//										"desc": "输出节点。",
//										"text": "提交本地知识文档/网页",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMUA03TS8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMUA03TS9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/hudmemo.svg"
//									},
//									"linkedSeg": "1IN0I2S520"
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
//					"jaxId": "1IMU9LK4D0",
//					"attrs": {
//						"id": "AskQueryType",
//						"viewName": "",
//						"label": "",
//						"x": "405",
//						"y": "570",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "请选择你要查询的内容",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IMUA03TR1",
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
//									"jaxId": "1IMU9LK3U0",
//									"attrs": {
//										"id": "SetupDoc",
//										"desc": "输出节点。",
//										"text": "获取项目部署文档",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMUA03TS10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMUA03TS11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/prj.svg"
//									},
//									"linkedSeg": "1IMUBBFHD0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IMU9LK3U1",
//									"attrs": {
//										"id": "IssueDoc",
//										"desc": "输出节点。",
//										"text": "获取问题解决方案",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMUA03TS12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMUA03TS13",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/help.svg"
//									},
//									"linkedSeg": "1IN0OHTL10"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IMU9LK3U2",
//									"attrs": {
//										"id": "MetaDoc",
//										"desc": "输出节点。",
//										"text": "收纳的文档信息",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IMUA03TS14",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IMUA03TS15",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/hudmemo.svg"
//									},
//									"linkedSeg": "1IMUBHK0P0"
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
//					"def": "askEditObj",
//					"jaxId": "1IMUA9J4F0",
//					"attrs": {
//						"id": "InputEnvPrj",
//						"viewName": "",
//						"label": "",
//						"x": "695",
//						"y": "-10",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUARBKP0",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"result\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"\",\"metaDocQueryVo\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IMUARBKP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"text": "输入当前环境信息和项目名称",
//						"role": "Assistant",
//						"data": "#input",
//						"template": "\"1IMUACQDA0\"",
//						"editData": "true",
//						"outlet": {
//							"jaxId": "1IMUARBKO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUB2F0L0"
//						}
//					},
//					"icon": "rename.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askFile",
//					"jaxId": "1IMUB2F0L0",
//					"attrs": {
//						"id": "AskGuideMD",
//						"viewName": "",
//						"label": "",
//						"x": "955",
//						"y": "-10",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUB3TBC0",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"result\",\"issueContent\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"htmlContent\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IMUB3TBC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"prompt": "请选择安装指南文件",
//						"path": "",
//						"fileSys": "naive",
//						"filter": "",
//						"read": "Text",
//						"outlet": {
//							"jaxId": "1IMUB3TB90",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUB42820"
//						}
//					},
//					"icon": "folder.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IMUB42820",
//					"attrs": {
//						"id": "SubmitSetupDoc",
//						"viewName": "",
//						"label": "",
//						"x": "1200",
//						"y": "-10",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUB5M7E0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMUB5M7E1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IMUB5M7A0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUB53210"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IMUB53210",
//					"attrs": {
//						"id": "ShowPushResult",
//						"viewName": "",
//						"label": "",
//						"x": "1480",
//						"y": "-10",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUB5M7E2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMUB5M7E3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IMUB5M7A1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0THVGG0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askEditObj",
//					"jaxId": "1IMUBBFHD0",
//					"attrs": {
//						"id": "QueryEnvPrj",
//						"viewName": "",
//						"label": "",
//						"x": "700",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBISF90",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"result\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"\",\"issueContent\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"htmlContent\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBISF91",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"text": "请输入要部署的项目和目标环境信息",
//						"role": "Assistant",
//						"data": "#input",
//						"template": "\"1IMUACQDA0\"",
//						"editData": "true",
//						"outlet": {
//							"jaxId": "1IMUBISF50",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBC5KU0"
//						}
//					},
//					"icon": "rename.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IMUBC5KU0",
//					"attrs": {
//						"id": "QuerySetupDoc",
//						"viewName": "",
//						"label": "",
//						"x": "960",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBISF92",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBISF93",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IMUBISF51",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBF1UF0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IMUBF1UF0",
//					"attrs": {
//						"id": "ShowSetupDoc",
//						"viewName": "",
//						"label": "",
//						"x": "1205",
//						"y": "465",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBISF94",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBISF95",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IMUBISF52",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0UTD0G0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IMUBGANT0",
//					"attrs": {
//						"id": "QueryInfo",
//						"viewName": "",
//						"label": "",
//						"x": "960",
//						"y": "555",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBISF98",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBISF99",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IMUBISF54",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBGU8J0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IMUBGU8J0",
//					"attrs": {
//						"id": "ShowInfoDoc",
//						"viewName": "",
//						"label": "",
//						"x": "1205",
//						"y": "555",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBISF910",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBISF911",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IMUBISF55",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0UTD0G0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IMUBHK0P0",
//					"attrs": {
//						"id": "AskQuery",
//						"viewName": "",
//						"label": "",
//						"x": "700",
//						"y": "645",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBISF912",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"result\",\"metaDocQuery\":\"result\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"\",\"issueContent\":\"\",\"metaDocName\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"htmlContent\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBISF913",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "请输入你要查询的内容",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IMUBISF56",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0UR41S0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IMUBI1EE0",
//					"attrs": {
//						"id": "QueryDocInfo",
//						"viewName": "",
//						"label": "",
//						"x": "1205",
//						"y": "645",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBISF914",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBISF915",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IMUBISF57",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBIGPI0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IMUBIGPI0",
//					"attrs": {
//						"id": "ShowInfo",
//						"viewName": "",
//						"label": "",
//						"x": "1485",
//						"y": "645",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBISF916",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBISF917",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IMUBISF58",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBRCV50"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askFile",
//					"jaxId": "1IMUBJVCC0",
//					"attrs": {
//						"id": "AskSolutionFile",
//						"viewName": "",
//						"label": "",
//						"x": "955",
//						"y": "90",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBSUDI2",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"\",\"issueContent\":\"result\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"htmlContent\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBSUDI3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"prompt": "请选择文档",
//						"path": "",
//						"fileSys": "naive",
//						"filter": "",
//						"read": "Text",
//						"outlet": {
//							"jaxId": "1IMUBSUDB1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBKC9O0"
//						}
//					},
//					"icon": "folder.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IMUBKC9O0",
//					"attrs": {
//						"id": "SubmitIssueDoc",
//						"viewName": "",
//						"label": "",
//						"x": "1200",
//						"y": "90",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBSUDI4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBSUDI5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IMUBSUDB2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUB53210"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IMUBOIGH0",
//					"attrs": {
//						"id": "InputURL",
//						"viewName": "",
//						"label": "",
//						"x": "955",
//						"y": "360",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IMUBSUDI8",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"\",\"issueContent\":\"\",\"metaDocName\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"result\",\"htmlContent\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IMUBSUDI9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "请输入网页URL",
//						"tipRole": "Assistant",
//						"placeholder": "",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IMUBSUDB4",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN16KO430"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IMUBQ7750",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "2020",
//						"y": "375",
//						"outlet": {
//							"jaxId": "1IMUBSUDI12",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0V0R070"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IMUBRCV50",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1705",
//						"y": "555",
//						"outlet": {
//							"jaxId": "1IMUBSUDI13",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBS4910"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IMUBS4910",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1730",
//						"y": "800",
//						"outlet": {
//							"jaxId": "1IMUBSUDI15",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBSALP0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IMUBSALP0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "170",
//						"y": "800",
//						"outlet": {
//							"jaxId": "1IMUBSUDI16",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMU8U52S0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IN0I2S520",
//					"attrs": {
//						"id": "AskDocType",
//						"viewName": "",
//						"label": "",
//						"x": "695",
//						"y": "245",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "提交哪里的文档？",
//						"multi": "false",
//						"withChat": "false",
//						"outlet": {
//							"jaxId": "1IN0J7M170",
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
//									"jaxId": "1IN0I2S4H0",
//									"attrs": {
//										"id": "LocalFile",
//										"desc": "输出节点。",
//										"text": "上传本地设备文档文件",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IN0J7M1D0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IN0J7M1D1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/folder.svg"
//									},
//									"linkedSeg": "1IN0J04L80"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IN5V198Q0",
//									"attrs": {
//										"id": "TabOSFile",
//										"desc": "输出节点。",
//										"text": "上传Tab-OS内文档",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IN5V2BQ30",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IN5V2BQ31",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/cklogo.svg"
//									},
//									"linkedSeg": "1IN5V9DEV0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IN0I2S4H2",
//									"attrs": {
//										"id": "HTML",
//										"desc": "输出节点。",
//										"text": "HTML网页",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IN0J7M1D2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IN0J7M1D3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"icon": "/~/-tabos/shared/assets/browser.svg"
//									},
//									"linkedSeg": "1IMUBOIGH0"
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
//					"def": "askFile",
//					"jaxId": "1IN0J04L80",
//					"attrs": {
//						"id": "AskDocFile",
//						"viewName": "",
//						"label": "",
//						"x": "955",
//						"y": "165",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN0J7M1D4",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"\",\"metaDocQuery\":\"\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"\",\"issueContent\":\"\",\"metaDocName\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"metaDocData\":\"result\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IN0J7M1D5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"prompt": "请选择要提交的文档文件",
//						"path": "",
//						"fileSys": "naive",
//						"filter": "",
//						"read": "Base64",
//						"outlet": {
//							"jaxId": "1IN0J7M171",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0J18DI0"
//						}
//					},
//					"icon": "folder.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askFile",
//					"jaxId": "1IN5V9DEV0",
//					"attrs": {
//						"id": "AskT-OSFile",
//						"viewName": "",
//						"label": "",
//						"x": "955",
//						"y": "265",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN5VBMVG0",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"\",\"metaDocQuery\":\"\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"\",\"issueContent\":\"\",\"metaDocName\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"metaDocData\":\"result\",\"metaDocContent\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IN5VBMVG1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"prompt": "请选择要提交的文档文件",
//						"path": "",
//						"fileSys": "tabos",
//						"filter": "",
//						"read": "Base64",
//						"outlet": {
//							"jaxId": "1IN5VBMV90",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0J18DI0"
//						}
//					},
//					"icon": "folder.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IN0J18DI0",
//					"attrs": {
//						"id": "PushToHub",
//						"viewName": "",
//						"label": "",
//						"x": "1200",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN0J7M1D6",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN0J7M1D7",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IN0J7M172",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0TIS420"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IN0J2BVH0",
//					"attrs": {
//						"id": "SubmitDoc",
//						"viewName": "",
//						"label": "",
//						"x": "1755",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN0J7M1D8",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN0J7M1D9",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IN0J7M173",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN160QUV0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askEditObj",
//					"jaxId": "1IN0K868F0",
//					"attrs": {
//						"id": "InputIssue",
//						"viewName": "",
//						"label": "",
//						"x": "695",
//						"y": "90",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN0LPENK0",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"result\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"\",\"issueContent\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"htmlContent\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IN0LPENK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"text": "请填写问题和标签",
//						"role": "Assistant",
//						"data": "#input",
//						"template": "\"1IN0JHEB20\"",
//						"editData": "true",
//						"outlet": {
//							"jaxId": "1IN0LPENH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBJVCC0"
//						}
//					},
//					"icon": "rename.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askEditObj",
//					"jaxId": "1IN0OHTL10",
//					"attrs": {
//						"id": "AskIssue",
//						"viewName": "",
//						"label": "",
//						"x": "700",
//						"y": "555",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN0OJKFU0",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"result\",\"metaDocIndexVo\":\"\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"\",\"issueContent\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"htmlContent\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IN0OJKFU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"text": "请输入问题：",
//						"role": "Assistant",
//						"data": "#input",
//						"template": "\"1IN0OGMTF0\"",
//						"editData": "true",
//						"outlet": {
//							"jaxId": "1IN0OJKFO0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBGANT0"
//						}
//					},
//					"icon": "rename.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IN0PBM430",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1905",
//						"y": "300",
//						"outlet": {
//							"jaxId": "1IN0PD0N10",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0PC59Q0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IN0PC59Q0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1220",
//						"y": "300",
//						"outlet": {
//							"jaxId": "1IN0PD0N11",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0J18DI0"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IN0THVGG0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1930",
//						"y": "-10",
//						"outlet": {
//							"jaxId": "1IN0TKLRP0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBQ7750"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "askEditObj",
//					"jaxId": "1IN0TIS420",
//					"attrs": {
//						"id": "AskDocKB",
//						"viewName": "",
//						"label": "",
//						"x": "1480",
//						"y": "215",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN0TKLRP1",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"result\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"\",\"issueContent\":\"\",\"metaDocName\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"htmlContent\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IN0TKLRP2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"text": "输入目标知识库，空白则为默认值",
//						"role": "Assistant",
//						"data": "#input",
//						"template": "\"1IN0TOFMS0\"",
//						"editData": "true",
//						"outlet": {
//							"jaxId": "1IN0TKLRH0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN0J2BVH0"
//						}
//					},
//					"icon": "rename.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askEditObj",
//					"jaxId": "1IN0UR41S0",
//					"attrs": {
//						"id": "AskKb",
//						"viewName": "",
//						"label": "",
//						"x": "960",
//						"y": "645",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN0UR41S1",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"\",\"metaDocQueryVo\":\"result\",\"prjSetupContent\":\"\",\"issueContent\":\"\",\"metaDocName\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"htmlContent\":\"\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IN0UR41S2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"text": "输入目标知识库，空白则为默认值",
//						"role": "Assistant",
//						"data": "#input",
//						"template": "\"1IN0TOFMS0\"",
//						"editData": "true",
//						"outlet": {
//							"jaxId": "1IN0UR41T0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBI1EE0"
//						}
//					},
//					"icon": "rename.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IN0UTD0G0",
//					"attrs": {
//						"id": "_1",
//						"label": "New AI Seg",
//						"x": "1470",
//						"y": "555",
//						"outlet": {
//							"jaxId": "1IN0UTD0G1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBRCV50"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IN0V0R070",
//					"attrs": {
//						"id": "_2",
//						"label": "New AI Seg",
//						"x": "2045",
//						"y": "800",
//						"outlet": {
//							"jaxId": "1IN0V0R071",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBS4910"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IN160QUV0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1900",
//						"y": "110",
//						"outlet": {
//							"jaxId": "1IN161QMK0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN160VT80"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IN160VT80",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1510",
//						"y": "110",
//						"outlet": {
//							"jaxId": "1IN161QMK1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUB53210"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1IN16KO430",
//					"attrs": {
//						"id": "ReadPage",
//						"viewName": "",
//						"label": "",
//						"x": "1205",
//						"y": "360",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN16ND3N0",
//							"attrs": {
//								"cast": "{\"prjSetupIndexVo\":\"\",\"prjSetupQueryVo\":\"\",\"issueIndexVo\":\"\",\"issueQueryVo\":\"\",\"metaDocIndexVo\":\"\",\"metaDocQuery\":\"\",\"metaDocQueryVo\":\"\",\"prjSetupContent\":\"\",\"issueContent\":\"\",\"metaDocName\":\"\",\"metaDocPath\":\"\",\"htmlUrl\":\"\",\"metaDocData\":\"result\"}"
//							}
//						},
//						"global": {
//							"jaxId": "1IN16ND3N1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "AgentBuilder",
//						"callAgent": "RpaReadPage.js",
//						"callArg": "#{url:context.htmlUrl,format:\"markdown\"}",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1IN16ND3H0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN4NK8C60"
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IN4NK8C60",
//					"attrs": {
//						"id": "ShowHTML",
//						"viewName": "",
//						"label": "",
//						"x": "1480",
//						"y": "360",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN4NRUFP0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN4NRUFP1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#context.metaDocContent",
//						"outlet": {
//							"jaxId": "1IN4NRUFJ0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN4NKS5N0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askConfirm",
//					"jaxId": "1IN4NKS5N0",
//					"attrs": {
//						"id": "AskSubmit",
//						"viewName": "",
//						"label": "",
//						"x": "1755",
//						"y": "360",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"prompt": "是否提交网页内容",
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IN4NKS5A0",
//									"attrs": {
//										"id": "Submit",
//										"desc": "输出节点。",
//										"text": "提交内容",
//										"result": "",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IN4NRUFP2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IN4NRUFP3",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IN0PBM430"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIButtonOutlet",
//									"jaxId": "1IN4NKS5A1",
//									"attrs": {
//										"id": "Abort",
//										"desc": "输出节点。",
//										"text": "放弃提交",
//										"result": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IN4NRUFP4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IN4NRUFP5",
//											"attrs": {
//												"cast": ""
//											}
//										}
//									},
//									"linkedSeg": "1IMUBQ7750"
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
//					"jaxId": "1IN73QP1T0",
//					"attrs": {
//						"id": "TipWork",
//						"viewName": "",
//						"label": "",
//						"x": "405",
//						"y": "720",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IN73SONN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IN73SONN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "抱歉，此功能暂未实现",
//						"outlet": {
//							"jaxId": "1IN73SONF0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IN73SBBK0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IN73SBBK0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1595",
//						"y": "720",
//						"outlet": {
//							"jaxId": "1IN73SONN2",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IMUBRCV50"
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
//		"addOnOpts": "{\"name\":\"\",\"label\":\"{\\\"EN\\\":\\\"RAG operations\\\",\\\"CN\\\":\\\"RAG知识库操作\\\"}\",\"path\":\"\",\"pathInHub\":\"\",\"chatEntry\":\"Root\",\"isRPA\":0,\"rpaHost\":\"\",\"segIcon\":\"db.svg\",\"catalog\":\"AI Call\"}"
//	}
//}