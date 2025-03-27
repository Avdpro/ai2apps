//Auto genterated by Cody
import {$P,VFACT,callAfter,sleep} from "/@vfact";
import pathLib from "/@path";
import inherits from "/@inherits";
import Base64 from "/@tabos/utils/base64.js";
import {trimJSON} from "/@aichat/utils.js";
/*#{1IJP4B4TO0MoreImports*/
import {tabFS,tabNT} from "/@tabos";
import {AppLib} from "/@homekit/data/AppLib.js";
/*}#1IJP4B4TO0MoreImports*/
const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);
const $ln=VFACT.lanCode||"EN";
const argsTemplate={
	properties:{
		"dirPath":{
			"name":"dirPath","type":"auto",
			"required":true,
			"defaultValue":"",
			"desc":"",
		},
		"setupType":{
			"name":"setupType","type":"string",
			"required":false,
			"defaultValue":"setup",
			"desc":"",
		}
	},
	/*#{1IJP4B4TO0ArgsView*/
	/*}#1IJP4B4TO0ArgsView*/
};

/*#{1IJP4B4TO0StartDoc*/
/*}#1IJP4B4TO0StartDoc*/
//----------------------------------------------------------------------------
let PrjTabOSPrjSetup=async function(session){
	let dirPath,setupType;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let FixArgs,StartSetup,ReadSetup,TipNoSetup,OnAction,TipActionError,DoCopy,DoClean,DoDelete,CallFunction,DoPackage,AskRaw,TipEnd,TipError,CallAgent,CallHubAgent,AskChat,AskMenu,GetNext,CheckEnd,DoSyncPrj;
	let setupVO=null;
	let curStep=undefined;
	
	/*#{1IJP4B4TO0LocalVals*/
	let app=VFACT.app;
	/*}#1IJP4B4TO0LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			dirPath=input.dirPath;
			setupType=input.setupType;
		}else{
			dirPath=undefined;
			setupType=undefined;
		}
		/*#{1IJP4B4TO0ParseArgs*/
		setupType=setupType||"setupAgent";
		/*}#1IJP4B4TO0ParseArgs*/
	}
	
	/*#{1IJP4B4TO0PreContext*/
	/*}#1IJP4B4TO0PreContext*/
	context={};
	context=VFACT.flexState(context);
	/*#{1IJP4B4TO0PostContext*/
	async function makeClean(vo){
		let dirs,srcDir,rootPath,files,srcFile,dels;
		rootPath=dirPath;
		dirs=vo.dirs||vo.dir;
		if(dirs){
			let entries,entry;
			for(srcDir of dirs){
				if(srcDir.startsWith("../")||srcDir.startsWith("/")||srcDir==="."||srcDir===""){
					session.addChatText("log",`Waring: clean path "${srcDir}" is out of project scope.\n`);
				}
				if(srcDir==="."||srcDir===""){
					throw Error(`Clean dir ${srcDir} is not allowed.`);
				}
				srcDir=srcDir[0]==="/"?srcDir:pathLib.join(rootPath,srcDir);
				session.addChatText("log",`Clean dir: ${srcDir}\n`);
				entries=await tabFS.getEntries(srcDir);
				if(entries){
					for(entry of entries){
						await tabFS.del(pathLib.join(srcDir,entry.name));
					}
				}
			}
		}
		dels=vo.deletes||vo.delete;
		files=vo.files||vo.file;
		if(dels){
			if(!files){
				files=dels;
			}else{
				files.push(...dels);
			}
		}
		if(files){
			for(srcFile of files){
				if(srcFile.startsWith("../")||srcFile.startsWith("/")||srcFile==="."||srcFile===""){
					session.addChatText("log",`Waring: delete item "${srcFile}" is out of project scope.\n`);
				}
				if(srcFile==="."||srcFile===""){
					throw Error(`Delete item ${srcFile} is out allowed.`);
				}
				srcFile=pathLib.join(rootPath,srcFile);
				session.addChatText("log",`Delete item: ${srcFile}\n`);
				await tabFS.del(srcFile);
			}
		}
	}
	
	function mask2VO(mskPath){
		let pos;
		pos=mskPath.indexOf("*");
		if(pos<0){
			return null;
		}
		return {pre:mskPath.substring(0,pos),post:mskPath.substring(pos+1)};
	}
	
	async function getMaskFiles(mskPath,subDir=false,list=null){
		let vo,pre,post,dirPath,entries,entry,path;
		vo=mask2VO(mskPath);
		if(!vo)
			return;
		list=list||[];
		pre=vo.pre;post=vo.post;
		dirPath=pathLib.dirname(pre);
		entries=await tabFS.getEntries(dirPath);
		for(entry of entries){
			if(entry.dir){
				if(subDir){
					path=mskPath.substring(dirPath.length);
					path=pathLib.join(dirPath,entry.name,path);
					await getMaskFiles(path,true,list);
				}
			}else{
				if(entry.name.endsWith(post)){
					list.push(pathLib.join(dirPath,entry.name));
				}
			}
		}
		return list;
	}
	
	function checkMasks(path,exMasks){
		let i,n,stub,pre,post;
		n=exMasks.length;
		for(i=0;i<n;i++){
			stub=exMasks[i];
			pre=stub.pre;
			post=stub.post;
			if(pre && !path.startsWith(pre)){
				return false;
			}
			if(post && !path.endsWith(post)){
				return false;
			}
		}
		return true;		
	}
	
	async function copyOneFile(srcFile,tgtFile,vo){
		let exFiles=vo.exFiles;
		let exMasks=vo.exMasks;
		if(exFiles && exFiles.indexOf(srcFile)>=0){
			return;
		}
		if(exMasks && checkMasks(srcFile,exMasks)){
			return;
		}
		if(srcFile===tgtFile){
			session.addChatText("log",`Copy file skiped: ${srcFile} to ${tgtFile}\n`);
			return;
		}
		session.addChatText("log",`Copy file: ${srcFile} to ${tgtFile}\n`);
		if(vo.copy){
			if(await vo.copy(srcFile,tgtFile,vo)){
				return;
			}
		}
		await tabFS.copy(srcFile,tgtFile,{force:1});
	}
	
	async function copyOneDir(orgPath,tgtPath,opts){
		let entries;
		let exDirs,exFiles,exMasks;
	
		exDirs=opts.exDirs;
		exFiles=opts.exFiles;
		exMasks=opts.exMasks;
		function checkMasks(path,exMasks){
			let i,n,stub,pre,post;
			n=exMasks.length;
			for(i=0;i<n;i++){
				stub=exMasks[i];
				pre=stub.pre;
				post=stub.post;
				if(pre && !path.startsWith(pre)){
					return false;
				}
				if(post && !path.endsWith(post)){
					return false;
				}
			}
			return true;		
		}
	
		async function copyOneFile(srcFile,tgtFile,vo){
			let exFiles=vo.exFiles;
			let exMasks=vo.exMasks;
			if(exFiles && exFiles.indexOf(srcFile)>=0){
				return;
			}
			if(exMasks && checkMasks(srcFile,exMasks)){
				return;
			}
			session.addChatText("log",`Copy file: ${srcFile} to ${tgtFile}\n`);
			if(vo.copy){
				if(await vo.copy(srcFile,tgtFile,vo)){
					return;
				}
			}
			await tabFS.copy(srcFile,tgtFile,{force:1});
		}
	
		exDirs=opts.exDirs;
		exFiles=opts.exFiles;
		entries=await tabFS.getEntries(orgPath);
		if(!entries){
			return true;
		}
		session.addChatText("log",`Copy dir ${orgPath} to ${tgtPath}\n`);
		for(let entry of entries){
			let entryName,orgItemPath,tgtItemPath,newPath,newPlugin;
			entryName=entry.name;
			DoCopy:{
				if(entryName[0]==="."){
					//We don't convert path starts with "."
					break DoCopy;
				}
				orgItemPath=pathLib.join(orgPath,entryName);
				tgtItemPath=pathLib.join(tgtPath,entryName);
				if(entry.dir){
					if((!exDirs) || (exDirs.indexOf(orgItemPath)<0)){
						await copyOneDir(orgItemPath,tgtItemPath,opts);
					}
				}else{
					await copyOneFile(orgItemPath,tgtItemPath,opts);
				}
			}
		}
	};
	
	async function makeCopy(vo){
		let rootPath,exDirs,exFiles,exMasks,i,n,path,subVO;
		let dirs,srcDir,tgtDir,tgtFile,opts,files,srcFile;
		rootPath=dirPath;
		if(vo.exclude){
			exDirs=vo.exclude.dirs||null;
			exFiles=vo.exclude.files||null;
		}else{
			exDirs=vo.exDirs||null;
			exFiles=vo.exFiles||null;
		}
		exMasks=[];
		if(exDirs){
			exDirs=exDirs.map((path)=>{return pathLib.join(rootPath,path);});
			n=exDirs.length;
			for(i=n-1;i>=0;i--){
				path=exDirs[i];
				subVO=mask2VO(path);
				if(subVO){
					exDirs.splice(i,1);
					exMasks.push(subVO);
				}
			}
		}
		if(exFiles){
			exFiles=exFiles.map((path)=>{return pathLib.join(rootPath,path);});
			n=exFiles.length;
			for(i=n-1;i>=0;i--){
				path=exFiles[i];
				subVO=mask2VO(path);
				if(subVO){
					exFiles.splice(i,1);
					exMasks.push(subVO);
				}
			}
		}
		exMasks=exMasks.length>0?exMasks:null;
		vo={...vo,exDirs:exDirs,exFiles:exFiles,exMasks:exMasks};
		dirs=vo.dirs;
		if(dirs){
			for(srcDir in dirs){
				tgtDir=dirs[srcDir];
				if(tgtDir.endsWith("/")){
					tgtFile=pathLib.join(tgtDir,pathLib.basename(srcDir));
				}
				tgtDir=tgtDir[0]==="/"?tgtDir:pathLib.join(rootPath,tgtDir);
				srcDir=srcDir[0]==="/"?srcDir:pathLib.join(rootPath,srcDir);
				await copyOneDir(srcDir,tgtDir,vo);
			}
		}
		files=vo.files;
		if(files){
			let pos,mskList,mskFile;
			for(srcFile in files){
				pos=srcFile.indexOf("*");
				if(pos>0){
					tgtDir=files[srcFile];
					srcFile=srcFile[0]==="/"?srcFile:pathLib.join(rootPath,srcFile);
					mskList=await getMaskFiles(srcFile,false,null);
					for(mskFile of mskList){
						tgtFile=pathLib.join(tgtDir,pathLib.basename(mskFile));
						await copyOneFile(mskFile,tgtFile,vo);
					}
				}else{
					tgtFile=files[srcFile];
					if(tgtFile.endsWith("/")){
						tgtFile=pathLib.join(tgtFile,pathLib.basename(srcFile));
					}
					srcFile=srcFile[0]==="/"?srcFile:pathLib.join(rootPath,srcFile);
					tgtFile=tgtFile[0]==="/"?tgtFile:pathLib.join(rootPath,tgtFile);
					await copyOneFile(srcFile,tgtFile,vo);
				}
			}
		}
	}
	
	/*}#1IJP4B4TO0PostContext*/
	let agent,segs={};
	segs["FixArgs"]=FixArgs=async function(input){//:1IJP4BEIG0
		let result=input;
		let missing=false;
		if(dirPath===undefined || dirPath==="") missing=true;
		if(missing){
			result=await session.pipeChat("/@aichat/ai/CompleteArgs.js",{"argsTemplate":argsTemplate,"command":input},false);
			parseAgentArgs(result);
		}
		return {seg:StartSetup,result:(result),preSeg:"1IJP4BEIG0",outlet:"1IJP4DHGJ0"};
	};
	FixArgs.jaxId="1IJP4BEIG0"
	FixArgs.url="FixArgs@"+agentURL
	
	segs["StartSetup"]=StartSetup=async function(input){//:1IJP6LKNT0
		let result=input;
		/*#{1IJP6LKNT0Code*/
		false
		/*}#1IJP6LKNT0Code*/
		return {seg:ReadSetup,result:(result),preSeg:"1IJP6LKNT0",outlet:"1IJP6MK9210",catchSeg:TipError,catchlet:"1IJP6MK9211"};
	};
	StartSetup.jaxId="1IJP6LKNT0"
	StartSetup.url="StartSetup@"+agentURL
	
	segs["ReadSetup"]=ReadSetup=async function(input){//:1IJP4C8O50
		let result=input;
		/*#{1IJP4C8O50Start*/
		let entry;
		try{
			let mdPath="/~"+pathLib.join(dirPath,"setup.js");
			let md=await import(mdPath);
			let setupFunc=md[setupType];
			if(setupFunc){
				setupVO=await setupFunc(session,dirPath,$ln);
				entry=setupVO.start;
			}
		}catch(err){
			setupVO=null;
		}
		/*}#1IJP4C8O50Start*/
		if(entry){
			let output=entry;
			/*#{1IJP4DHGJ1Codes*/
			/*}#1IJP4DHGJ1Codes*/
			return {seg:OnAction,result:(output),preSeg:"1IJP4C8O50",outlet:"1IJP4DHGJ1"};
		}
		/*#{1IJP4C8O50Post*/
		/*}#1IJP4C8O50Post*/
		return {seg:TipNoSetup,result:(result),preSeg:"1IJP4C8O50",outlet:"1IJP4DHGJ2"};
	};
	ReadSetup.jaxId="1IJP4C8O50"
	ReadSetup.url="ReadSetup@"+agentURL
	
	segs["TipNoSetup"]=TipNoSetup=async function(input){//:1IJP63GLR0
		let result=input;
		let opts={};
		let role="assistant";
		let content=(($ln==="CN")?("没有找到安装信息"):("Setup information not found"));
		/*#{1IJP63GLR0PreCodes*/
		/*}#1IJP63GLR0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IJP63GLR0PostCodes*/
		result={result:"Failed",content:"Setup information not found."};
		/*}#1IJP63GLR0PostCodes*/
		return {result:result};
	};
	TipNoSetup.jaxId="1IJP63GLR0"
	TipNoSetup.url="TipNoSetup@"+agentURL
	
	segs["OnAction"]=OnAction=async function(input){//:1IJP4N4J20
		let result=input;
		/*#{1IJP4N4J20Start*/
		let info;
		curStep=input;
		info=input.text||input.description;
		if(info){
			session.addChatText("assistant",info,{});
		}
		/*}#1IJP4N4J20Start*/
		if(input.action==="ShowText"||input.action==="showtext"||input.action==="Info"||input.action==="info"){
			let output=input;
			return {seg:GetNext,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP6RDP90"};
		}
		if(input.action==="Copy"||input.action==="copy"){
			let output=input;
			return {seg:DoCopy,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP63GLR2"};
		}
		if(input.action==="Clean"||input.action==="clean"){
			let output=input;
			return {seg:DoClean,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP4PHUE0"};
		}
		if(input.action==="Delete"||input.action==="delete"){
			let output=input;
			return {seg:DoDelete,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP4PRTA0"};
		}
		if(input.action==="Function"||input.action==="function"){
			let output=input;
			return {seg:CallFunction,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP62N180"};
		}
		if(input.action==="SyncDir"||input.action==="syncdir"){
			let output=input;
			return {seg:DoSyncPrj,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP4Q0PA0"};
		}
		if(input.action==="Package"||input.action==="package"||input.action==="Packages"||input.action==="packages"||input.action==="Pkg"||input.action==="pkg"||input.action==="Pkgs"||input.action==="pkgs"){
			let output=input;
			return {seg:DoPackage,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP4QAD70"};
		}
		if(input.action==="CallAgent"||input.action==="CallAgent"){
			let output=input;
			return {seg:CallAgent,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP60VT10"};
		}
		if(input.action==="CallHubAgent"||input.action==="callhubagent"){
			let output=input;
			return {seg:CallHubAgent,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP628G10"};
		}
		if(input.action==="AskChat"||input.action==="askChat"){
			let output=input;
			return {seg:AskChat,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP64NBC0"};
		}
		if(input.action==="AskMenu"||input.action==="askmenu"){
			let output=input;
			return {seg:AskMenu,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP651PP0"};
		}
		if(input.action==="AskRaw"||input.action==="askraw"){
			let output=input;
			return {seg:AskRaw,result:(output),preSeg:"1IJP4N4J20",outlet:"1IJP65L850"};
		}
		/*#{1IJP4N4J20Post*/
		/*}#1IJP4N4J20Post*/
		return {seg:TipActionError,result:(result),preSeg:"1IJP4N4J20",outlet:"1IJP63GLR3"};
	};
	OnAction.jaxId="1IJP4N4J20"
	OnAction.url="OnAction@"+agentURL
	
	segs["TipActionError"]=TipActionError=async function(input){//:1IJP6CN5H0
		let result=input;
		let opts={};
		let role="assistant";
		let content=`Wrong setup step-vo: ${JSON.stringify(input)}`;
		session.addChatText(role,content,opts);
		return {result:result};
	};
	TipActionError.jaxId="1IJP6CN5H0"
	TipActionError.url="TipActionError@"+agentURL
	
	segs["DoCopy"]=DoCopy=async function(input){//:1IJP6BBKK0
		let result=input
		/*#{1IJP6BBKK0Code*/
		await makeCopy(input);
		/*}#1IJP6BBKK0Code*/
		return {seg:GetNext,result:(result),preSeg:"1IJP6BBKK0",outlet:"1IJP6MK910"};
	};
	DoCopy.jaxId="1IJP6BBKK0"
	DoCopy.url="DoCopy@"+agentURL
	
	segs["DoClean"]=DoClean=async function(input){//:1IJP6D9BK0
		let result=input
		/*#{1IJP6D9BK0Code*/
		await makeClean(input);
		/*}#1IJP6D9BK0Code*/
		return {seg:GetNext,result:(result),preSeg:"1IJP6D9BK0",outlet:"1IJP6MK912"};
	};
	DoClean.jaxId="1IJP6D9BK0"
	DoClean.url="DoClean@"+agentURL
	
	segs["DoDelete"]=DoDelete=async function(input){//:1IJP6DHQT0
		let result=input
		/*#{1IJP6DHQT0Code*/
		await makeClean(input);
		/*}#1IJP6DHQT0Code*/
		return {seg:GetNext,result:(result),preSeg:"1IJP6DHQT0",outlet:"1IJP6MK913"};
	};
	DoDelete.jaxId="1IJP6DHQT0"
	DoDelete.url="DoDelete@"+agentURL
	
	segs["CallFunction"]=CallFunction=async function(input){//:1IJP6DS9Q0
		let result=input
		/*#{1IJP6DS9Q0Code*/
		let func=input.function;
		result=await func(session);
		/*}#1IJP6DS9Q0Code*/
		return {seg:GetNext,result:(result),preSeg:"1IJP6DS9Q0",outlet:"1IJP6MK914"};
	};
	CallFunction.jaxId="1IJP6DS9Q0"
	CallFunction.url="CallFunction@"+agentURL
	
	segs["DoPackage"]=DoPackage=async function(input){//:1IJP6F0T40
		let result=input
		/*#{1IJP6F0T40Code*/
		let packages=input.packages||input.package;
		if(typeof(packages)==="string"){
			if(packages.indexOf(",")>=0){
				packages = packages.split(',');
			}else{
				packages=[packages];
			}
		}
		for(let pkg of packages){
			result=await AppLib.ensurePackageInstalled(app,pkg);
			if(!result){
				throw Error(`Install package error: ${pkg}.`);
			}
		}
		result=true;
		/*}#1IJP6F0T40Code*/
		return {seg:GetNext,result:(result),preSeg:"1IJP6F0T40",outlet:"1IJP6MK920"};
	};
	DoPackage.jaxId="1IJP6F0T40"
	DoPackage.url="DoPackage@"+agentURL
	
	segs["AskRaw"]=AskRaw=async function(input){//:1IJP6H8SH0
		let result=input
		/*#{1IJP6H8SH0Code*/
		result=await session.askUserRaw(input.vo);
		/*}#1IJP6H8SH0Code*/
		return {seg:GetNext,result:(result),preSeg:"1IJP6H8SH0",outlet:"1IJP6MK925"};
	};
	AskRaw.jaxId="1IJP6H8SH0"
	AskRaw.url="AskRaw@"+agentURL
	
	segs["TipEnd"]=TipEnd=async function(input){//:1IJP6KMNR0
		let result=input;
		let opts={};
		let role="assistant";
		let content=(($ln==="CN")?("安装完毕。"):("Setup completed."));
		/*#{1IJP6KMNR0PreCodes*/
		/*}#1IJP6KMNR0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IJP6KMNR0PostCodes*/
		result={result:"Finish",content:"Setup completed."};
		/*}#1IJP6KMNR0PostCodes*/
		return {result:result};
	};
	TipEnd.jaxId="1IJP6KMNR0"
	TipEnd.url="TipEnd@"+agentURL
	
	segs["TipError"]=TipError=async function(input){//:1IJP6MAPQ0
		let result=input;
		let opts={};
		let role="assistant";
		let content=input;
		/*#{1IJP6MAPQ0PreCodes*/
		/*}#1IJP6MAPQ0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1IJP6MAPQ0PostCodes*/
		result={result:"Failed",content:""+input};
		/*}#1IJP6MAPQ0PostCodes*/
		return {result:result};
	};
	TipError.jaxId="1IJP6MAPQ0"
	TipError.url="TipError@"+agentURL
	
	segs["CallAgent"]=CallAgent=async function(input){//:1IJP7OKKE0
		let result;
		let arg=input.args;
		let sourcePath=(input.agent)||"";
		sourcePath=sourcePath[0]==="/"?sourcePath:pathLib.joinTabOSURL(basePath,"../"+sourcePath);
		/*#{1IJP7OKKE0Input*/
		/*}#1IJP7OKKE0Input*/
		result= await session.pipeChat(sourcePath,arg,false);
		/*#{1IJP7OKKE0Output*/
		/*}#1IJP7OKKE0Output*/
		return {seg:GetNext,result:(result),preSeg:"1IJP7OKKE0",outlet:"1IJP7SO6F0"};
	};
	CallAgent.jaxId="1IJP7OKKE0"
	CallAgent.url="CallAgent@"+agentURL
	
	segs["CallHubAgent"]=CallHubAgent=async function(input){//:1IJP7PJP70
		let result,args={};
		args['nodeName']=input.agentNode;
		args['callAgent']=input.agent;
		args['callArg']=input.args;
		args['checkUpdate']=true;
		/*#{1IJP7PJP70PreCodes*/
		/*}#1IJP7PJP70PreCodes*/
		result= await session.pipeChat("/@aichat/ai/RemoteChat.js",args,false);
		/*#{1IJP7PJP70PostCodes*/
		/*}#1IJP7PJP70PostCodes*/
		return {seg:GetNext,result:(result),preSeg:"1IJP7PJP70",outlet:"1IJP7SO6F1"};
	};
	CallHubAgent.jaxId="1IJP7PJP70"
	CallHubAgent.url="CallHubAgent@"+agentURL
	
	segs["AskChat"]=AskChat=async function(input){//:1IJP7R6NB0
		let tip=(input.prompt);
		let tipRole=("assistant");
		let placeholder=(input.placeholder||"");
		let text=("");
		let result="";
		/*#{1IJP7R6NB0PreCodes*/
		/*}#1IJP7R6NB0PreCodes*/
		if(tip){
			session.addChatText(tipRole,tip);
		}
		result=await session.askChatInput({type:"input",placeholder:placeholder,text:text});
		session.addChatText("user",result);
		/*#{1IJP7R6NB0PostCodes*/
		/*}#1IJP7R6NB0PostCodes*/
		return {seg:GetNext,result:(result),preSeg:"1IJP7R6NB0",outlet:"1IJP7SO6F2"};
	};
	AskChat.jaxId="1IJP7R6NB0"
	AskChat.url="AskChat@"+agentURL
	
	segs["AskMenu"]=AskMenu=async function(input){//:1IJP7RT860
		let prompt=(input.prompt)||input;
		let countdown=undefined;
		let placeholder=(undefined)||null;
		let withChat=input.allowInput;
		let items=[
		];
		let result="";
		let item=null;
		
		/*#{1IJP7RT860PreCodes*/
		items=input.items;
		/*}#1IJP7RT860PreCodes*/
		[result,item]=await session.askUserRaw({type:"menu",prompt:prompt,multiSelect:false,items:items,withChat:withChat,countdown:countdown,placeholder:placeholder});
		/*#{1IJP7RT860PostCodes*/
		/*}#1IJP7RT860PostCodes*/
		if(typeof(item)==='string'){
			result=item;
			return {seg:GetNext,result:(result),preSeg:"1IJP7RT860",outlet:"1IJP7SO6F3"};
		}
		/*#{1IJP7RT860FinCodes*/
		result=item;
		/*}#1IJP7RT860FinCodes*/
		return {seg:GetNext,result:(result),preSeg:"1IJP7RT860",outlet:"1IJP7SO6F3"};
	};
	AskMenu.jaxId="1IJP7RT860"
	AskMenu.url="AskMenu@"+agentURL
	
	segs["GetNext"]=GetNext=async function(input){//:1IJP6HNHD0
		let result=input
		/*#{1IJP6HNHD0Code*/
		let next=curStep.next;
		if(next instanceof Function){
			next=await next(input);
			next=setupVO[next];
		}else{
			next=setupVO[next];
		}
		result=next;
		/*}#1IJP6HNHD0Code*/
		return {seg:CheckEnd,result:(result),preSeg:"1IJP6HNHD0",outlet:"1IJP6MK926"};
	};
	GetNext.jaxId="1IJP6HNHD0"
	GetNext.url="GetNext@"+agentURL
	
	segs["CheckEnd"]=CheckEnd=async function(input){//:1IJP6JC8F0
		let result=input;
		if(!!input){
			return {seg:OnAction,result:(input),preSeg:"1IJP6JC8F0",outlet:"1IJP6MK927"};
		}
		return {seg:TipEnd,result:(result),preSeg:"1IJP6JC8F0",outlet:"1IJP6MK928"};
	};
	CheckEnd.jaxId="1IJP6JC8F0"
	CheckEnd.url="CheckEnd@"+agentURL
	
	segs["DoSyncPrj"]=DoSyncPrj=async function(input){//:1IJRTGNQ30
		let result;
		let arg={"dirPath":dirPath};
		let sourcePath=pathLib.joinTabOSURL(basePath,"./ToolSetupPrjSyncDir.js");
		result= await session.pipeChat(sourcePath,arg,false);
		return {seg:GetNext,result:(result),preSeg:"1IJRTGNQ30",outlet:"1IJRTHCN60"};
	};
	DoSyncPrj.jaxId="1IJRTGNQ30"
	DoSyncPrj.url="DoSyncPrj@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"PrjTabOSPrjSetup",
		url:agentURL,
		autoStart:true,
		jaxId:"1IJP4B4TO0",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{dirPath,setupType}*/){
			let result;
			parseAgentArgs(input);
			/*#{1IJP4B4TO0PreEntry*/
			/*}#1IJP4B4TO0PreEntry*/
			result={seg:FixArgs,"input":input};
			/*#{1IJP4B4TO0PostEntry*/
			/*}#1IJP4B4TO0PostEntry*/
			return result;
		},
		/*#{1IJP4B4TO0MoreAgentAttrs*/
		/*}#1IJP4B4TO0MoreAgentAttrs*/
	};
	/*#{1IJP4B4TO0PostAgent*/
	/*}#1IJP4B4TO0PostAgent*/
	return agent;
};
/*#{1IJP4B4TO0ExCodes*/
/*}#1IJP4B4TO0ExCodes*/

//#CodyExport>>>
export const ChatAPI=[{
	def:{
		name: "PrjTabOSPrjSetup",
		description: "这是一个AI智能体。",
		parameters:{
			type: "object",
			properties:{
				dirPath:{type:"auto",description:""},
				setupType:{type:"string",description:""}
			}
		}
	},
	agent: PrjTabOSPrjSetup
}];
//#CodyExport<<<
/*#{1IJP4B4TO0PostDoc*/
/*}#1IJP4B4TO0PostDoc*/


export default PrjTabOSPrjSetup;
export{PrjTabOSPrjSetup};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1IJP4B4TO0",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1IJP4B4TO1",
//			"attrs": {
//				"PrjTabOSPrjSetup": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1IJP4B4TO7",
//					"attrs": {
//						"exportType": "UI Data Template",
//						"constructArgs": {
//							"jaxId": "1IJP4B4TO8",
//							"attrs": {}
//						},
//						"superClass": "",
//						"properties": {
//							"jaxId": "1IJP4B4TO9",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1IJP4B4TO10",
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
//			"jaxId": "1IJP4B4TO2",
//			"attrs": {}
//		},
//		"entry": "",
//		"autoStart": "true",
//		"inBrowser": "true",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IJP4B4TO3",
//			"attrs": {
//				"dirPath": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJP4DHGK0",
//					"attrs": {
//						"type": "Auto",
//						"mockup": "\"\"",
//						"desc": "",
//						"required": "true"
//					}
//				},
//				"setupType": {
//					"type": "object",
//					"def": "AgentCallArgument",
//					"jaxId": "1IJSIV2I50",
//					"attrs": {
//						"type": "String",
//						"mockup": "setup",
//						"desc": "",
//						"required": "false"
//					}
//				}
//			}
//		},
//		"localVars": {
//			"jaxId": "1IJP4B4TO4",
//			"attrs": {
//				"setupVO": {
//					"type": "auto",
//					"valText": "null"
//				},
//				"curStep": {
//					"type": "auto",
//					"valText": ""
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1IJP4B4TO5",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1IJP4B4TO6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "fixArgs",
//					"jaxId": "1IJP4BEIG0",
//					"attrs": {
//						"id": "FixArgs",
//						"viewName": "",
//						"label": "",
//						"x": "70",
//						"y": "555",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"outlet": {
//							"jaxId": "1IJP4DHGJ0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6LKNT0"
//						}
//					},
//					"icon": "args.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "tryCatch",
//					"jaxId": "1IJP6LKNT0",
//					"attrs": {
//						"id": "StartSetup",
//						"viewName": "",
//						"label": "",
//						"x": "280",
//						"y": "555",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJP6MK9740",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK9741",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP6MK9210",
//							"attrs": {
//								"id": "Try",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP4C8O50"
//						},
//						"catchlet": {
//							"jaxId": "1IJP6MK9211",
//							"attrs": {
//								"id": "Catch",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6MAPQ0"
//						}
//					},
//					"icon": "trycatch.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJP4C8O50",
//					"attrs": {
//						"id": "ReadSetup",
//						"viewName": "",
//						"label": "",
//						"x": "515",
//						"y": "540",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJP4DHGK1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP4DHGK2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP4DHGJ2",
//							"attrs": {
//								"id": "NoSteup",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJP63GLR0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP4DHGJ1",
//									"attrs": {
//										"id": "Setup",
//										"desc": "输出节点。",
//										"output": "#entry",
//										"codes": "true",
//										"context": {
//											"jaxId": "1IJP4DHGK3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP4DHGK4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#entry"
//									},
//									"linkedSeg": "1IJP4N4J20"
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
//					"jaxId": "1IJP63GLR0",
//					"attrs": {
//						"id": "TipNoSetup",
//						"viewName": "",
//						"label": "",
//						"x": "760",
//						"y": "720",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJP63GLU0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP63GLU1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "Setup information not found",
//							"localize": {
//								"EN": "Setup information not found",
//								"CN": "没有找到安装信息"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IJP63GLR1",
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
//					"def": "brunch",
//					"jaxId": "1IJP4N4J20",
//					"attrs": {
//						"id": "OnAction",
//						"viewName": "",
//						"label": "",
//						"x": "760",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJP63GLU2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP63GLU3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP63GLR3",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJP6CN5H0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP6RDP90",
//									"attrs": {
//										"id": "ShowText",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP6T6BO0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP6T6BO1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"ShowText\"||input.action===\"showtext\"||input.action===\"Info\"||input.action===\"info\""
//									},
//									"linkedSeg": "1IK22GD7R0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP63GLR2",
//									"attrs": {
//										"id": "Copy",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP63GLU4",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP63GLU5",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Copy\"||input.action===\"copy\""
//									},
//									"linkedSeg": "1IJP6BBKK0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP4PHUE0",
//									"attrs": {
//										"id": "Clean",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP63GLU6",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP63GLU7",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Clean\"||input.action===\"clean\""
//									},
//									"linkedSeg": "1IJP6D9BK0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP4PRTA0",
//									"attrs": {
//										"id": "Delete",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP63GLU8",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP63GLU9",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Delete\"||input.action===\"delete\""
//									},
//									"linkedSeg": "1IJP6DHQT0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP62N180",
//									"attrs": {
//										"id": "Function",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP63GLU10",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP63GLU11",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Function\"||input.action===\"function\""
//									},
//									"linkedSeg": "1IJP6DS9Q0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP4Q0PA0",
//									"attrs": {
//										"id": "SyncDir",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP63GLU12",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP63GLU13",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"SyncDir\"||input.action===\"syncdir\""
//									},
//									"linkedSeg": "1IJRTGNQ30"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP4QAD70",
//									"attrs": {
//										"id": "Package",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP63GLU14",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP63GLU15",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"Package\"||input.action===\"package\"||input.action===\"Packages\"||input.action===\"packages\"||input.action===\"Pkg\"||input.action===\"pkg\"||input.action===\"Pkgs\"||input.action===\"pkgs\""
//									},
//									"linkedSeg": "1IJP6F0T40"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP60VT10",
//									"attrs": {
//										"id": "CallAgent",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP63GLU16",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP63GLU17",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"CallAgent\"||input.action===\"CallAgent\""
//									},
//									"linkedSeg": "1IJP7OKKE0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP628G10",
//									"attrs": {
//										"id": "CallHubAgent",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP63GLU18",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP63GLU19",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"CallHubAgent\"||input.action===\"callhubagent\""
//									},
//									"linkedSeg": "1IJP7PJP70"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP64NBC0",
//									"attrs": {
//										"id": "AskChat",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP6MK970",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP6MK971",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"AskChat\"||input.action===\"askChat\""
//									},
//									"linkedSeg": "1IJP7R6NB0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP651PP0",
//									"attrs": {
//										"id": "AskMenu",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP6MK972",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP6MK973",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"AskMenu\"||input.action===\"askmenu\""
//									},
//									"linkedSeg": "1IJP7RT860"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP65L850",
//									"attrs": {
//										"id": "AskRaw",
//										"desc": "输出节点。",
//										"output": "#input",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP6MK974",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP6MK975",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#input.action===\"AskRaw\"||input.action===\"askraw\""
//									},
//									"linkedSeg": "1IJP6H8SH0"
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
//					"jaxId": "1IJP6CN5H0",
//					"attrs": {
//						"id": "TipActionError",
//						"viewName": "",
//						"label": "",
//						"x": "1045",
//						"y": "830",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJP6MK978",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK979",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#`Wrong setup step-vo: ${JSON.stringify(input)}`",
//						"outlet": {
//							"jaxId": "1IJP6MK911",
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
//					"jaxId": "1IJP6BBKK0",
//					"attrs": {
//						"id": "DoCopy",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "95",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP6MK976",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK977",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP6MK910",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJP6D9BK0",
//					"attrs": {
//						"id": "DoClean",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "160",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP6MK9710",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK9711",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP6MK912",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJP6DHQT0",
//					"attrs": {
//						"id": "DoDelete",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "225",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP6MK9712",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK9713",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP6MK913",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJP6DS9Q0",
//					"attrs": {
//						"id": "CallFunction",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "290",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP6MK9714",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK9715",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP6MK914",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJP6F0T40",
//					"attrs": {
//						"id": "DoPackage",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP6MK9718",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK9719",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP6MK920",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1IJP6H8SH0",
//					"attrs": {
//						"id": "AskRaw",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "740",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP6MK9728",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK9729",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP6MK925",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IJP6K0JJ0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1745",
//						"y": "-30",
//						"outlet": {
//							"jaxId": "1IJP6MK9736",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6K7850"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connector",
//					"jaxId": "1IJP6K7850",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "795",
//						"y": "-30",
//						"outlet": {
//							"jaxId": "1IJP6MK9737",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP4N4J20"
//						},
//						"dir": "R2L"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1IJP6KMNR0",
//					"attrs": {
//						"id": "TipEnd",
//						"viewName": "",
//						"label": "",
//						"x": "1860",
//						"y": "435",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "flag.svg",
//						"context": {
//							"jaxId": "1IJP6MK9738",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK9739",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": {
//							"type": "string",
//							"valText": "Setup completed.",
//							"localize": {
//								"EN": "Setup completed.",
//								"CN": "安装完毕。"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1IJP6MK929",
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
//					"jaxId": "1IJP6MAPQ0",
//					"attrs": {
//						"id": "TipError",
//						"viewName": "",
//						"label": "",
//						"x": "515",
//						"y": "720",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJP6MK9742",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK9743",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1IJP6MK9212",
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
//					"jaxId": "1IJP7OKKE0",
//					"attrs": {
//						"id": "CallAgent",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "480",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP7SO6L0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP7SO6L1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "#input.agent",
//						"argument": "#{}#>input.args",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJP7SO6F0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "RemoteChat",
//					"jaxId": "1IJP7PJP70",
//					"attrs": {
//						"id": "CallHubAgent",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "545",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP7SO6L2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP7SO6L3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"nodeName": "#input.agentNode",
//						"callAgent": "#input.agent",
//						"callArg": "#input.args",
//						"checkUpdate": "true",
//						"outlet": {
//							"jaxId": "1IJP7SO6F1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
//						}
//					},
//					"icon": "cloudact.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askChat",
//					"jaxId": "1IJP7R6NB0",
//					"attrs": {
//						"id": "AskChat",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "605",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP7SO6L4",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP7SO6L5",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"tip": "#input.prompt",
//						"tipRole": "Assistant",
//						"placeholder": "#input.placeholder||\"\"",
//						"text": "",
//						"file": "false",
//						"showText": "true",
//						"outlet": {
//							"jaxId": "1IJP7SO6F2",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
//						}
//					},
//					"icon": "chat.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "askMenu",
//					"jaxId": "1IJP7RT860",
//					"attrs": {
//						"id": "AskMenu",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "675",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"prompt": "#input.prompt",
//						"multi": "false",
//						"withChat": "#input.allowInput",
//						"outlet": {
//							"jaxId": "1IJP7SO6F3",
//							"attrs": {
//								"id": "ChatInput",
//								"desc": "输出节点。",
//								"codes": "false"
//							},
//							"linkedSeg": "1IJP6HNHD0"
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
//					"jaxId": "1IJP6HNHD0",
//					"attrs": {
//						"id": "GetNext",
//						"viewName": "",
//						"label": "",
//						"x": "1370",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP6MK9730",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK9731",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP6MK926",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6JC8F0"
//						},
//						"result": "#input"
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1IJP6JC8F0",
//					"attrs": {
//						"id": "CheckEnd",
//						"viewName": "",
//						"label": "",
//						"x": "1580",
//						"y": "420",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "faces.svg",
//						"context": {
//							"jaxId": "1IJP6MK9732",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJP6MK9733",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1IJP6MK928",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1IJP6KMNR0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1IJP6MK927",
//									"attrs": {
//										"id": "NextAction",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1IJP6MK9734",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1IJP6MK9735",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#!!input"
//									},
//									"linkedSeg": "1IJP6K0JJ0"
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
//					"jaxId": "1IJRTGNQ30",
//					"attrs": {
//						"id": "DoSyncPrj",
//						"viewName": "",
//						"label": "",
//						"x": "1050",
//						"y": "355",
//						"desc": "调用其它AI Agent，把调用的结果作为输出",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1IJRTHCNC0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1IJRTHCNC1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"source": "ai/ToolSetupPrjSyncDir.js",
//						"argument": "{\"dirPath\":\"#dirPath\"}",
//						"secret": "false",
//						"outlet": {
//							"jaxId": "1IJRTHCN60",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
//						}
//					},
//					"icon": "agent.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IK22GD7R0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1030",
//						"y": "35",
//						"outlet": {
//							"jaxId": "1IK22GSLD0",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IK22GJ3J0"
//						},
//						"dir": "L2R"
//					},
//					"icon": "arrowright.svg",
//					"isConnector": true
//				},
//				{
//					"type": "aiseg",
//					"def": "connectorL",
//					"jaxId": "1IK22GJ3J0",
//					"attrs": {
//						"id": "",
//						"label": "New AI Seg",
//						"x": "1160",
//						"y": "35",
//						"outlet": {
//							"jaxId": "1IK22GSLD1",
//							"attrs": {
//								"id": "Outlet",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1IJP6HNHD0"
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
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}