import pathLib from "node:path";
import fs from 'node:fs';
import asyncFS from 'node:fs/promises';

const AgentHub_FileLibPath=process.env.AGENT_HUB_FileLibDir||process.env.AABOTS_FileLibPath||"filelib";

//---------------------------------------------------------------------------
async function saveFileFromBase64(base64String, targetDir, fileName,recursive) {
	// Ensure dir:
	if (!fs.existsSync(targetDir)) {
		await asyncFS.mkdir(targetDir,{recursive:recursive});
	}
	// Convert Base64 to Buffer
	const buffer = Buffer.from(base64String, 'base64');
	await asyncFS.writeFile(pathLib.join(targetDir,fileName),buffer);
}

//***************************************************************************
//AhFileLib
//***************************************************************************
let AhFileLib,ahFileLib;
{
	AhFileLib = function (agentHub) {
		this.agentHub = agentHub;
		this.app=agentHub.app;
		this.fileDir = null;
		this.nextFileId=1;
	};
	ahFileLib = AhFileLib.prototype = {};
	
	//-----------------------------------------------------------------------
	AhFileLib.start=async function(agentHub){
		let fileLib;
		fileLib=new AhFileLib(agentHub);
		await fileLib.start();
		return fileLib;
	};
	
	//-----------------------------------------------------------------------
	ahFileLib.start=async function(){
		let dirPath;
		dirPath=AgentHub_FileLibPath;
		//if(dirPath[0]!=="/"){
		if(!pathLib.isAbsolute(dirPath)){
			dirPath=pathLib.join(this.app.get("AppHomePath"),dirPath);
		}
		this.fileDir=dirPath;
		try {
			let fileMsgId = await asyncFS.readFile(pathLib.join(dirPath,"_file_id.txt"), "utf8");
			this.nextFileId=parseInt(fileMsgId);
		}catch (err){
			this.nextFileId=1;
		}
	};
	
	//-----------------------------------------------------------------------
	const checkNameRegex = /[%$#^&*!@\/<>:"'`\\\u4e00-\u9fa5\s]/;
	ahFileLib.genFileName=async function(orgName){
		let basename,fileId;
		basename=pathLib.basename(orgName);
		if(checkNameRegex.test(basename)){
			let ext;
			ext=pathLib.extname(basename);
			basename="File"+ext;
		}
		fileId=""+(this.nextFileId++);
		fileId=fileId.padStart(6,"0");
		await asyncFS.writeFile(pathLib.join(this.fileDir,"_file_id.txt"),""+this.nextFileId);
		return `FILE-${fileId}-${basename}`;
	};
	
	//----------------------------------------------------------------------
	ahFileLib.writeFile=async function(orgName,base64Data){
		let dirPath,fileName;
		fileName=await this.genFileName(orgName);
		dirPath=this.fileDir;
		await saveFileFromBase64(base64Data,dirPath,fileName,true);
		return fileName;
	};
	
	//----------------------------------------------------------------------
	ahFileLib.getFilePath=async function(fileName){
		return pathLib.join(this.fileDir,fileName);
	};
	
	//----------------------------------------------------------------------
	ahFileLib.readFile=async function(fileName){
		let buf,path,data;
		path=pathLib.join(this.fileDir,fileName);
		try {
			data = await asyncFS.readFile(path, {encoding: "base64"});
			//data = buf.toString("base64");
			await saveFileFromBase64(data,this.fileDir,"test-"+fileName,true);
		}catch(err){
			data="";
		}
		return data;
	};
	
	AhFileLib.setup=async function(agentHub,app,router,apiMap){
		let appFileLib;
		appFileLib=await AhFileLib.start(agentHub);
		
		//-----------------------------------------------------------------------
		apiMap['AhFileWrite']=apiMap['AhFileSave']=async function(req,res,next){
			let reqVO,fileName,fileData;
			reqVO=req.body.vo;
			fileName=reqVO.fileName;
			fileData=reqVO.data;
			fileName=await appFileLib.writeFile(fileName,fileData);
			res.json({ code: 200,fileName:fileName});
		};
		
		//-----------------------------------------------------------------------
		apiMap['AhFileRead']=apiMap['AhFileLoad']=async function(req,res,next){
			let reqVO,fileName,fileData;
			reqVO=req.body.vo;
			fileName=reqVO.fileName;
			fileData=await appFileLib.readFile(fileName);
			res.json({ code: 200,fileName:fileName,data:fileData});
		};
		
		//-----------------------------------------------------------------------
		apiMap['AhFilePath']=async function(req,res,next){
			let reqVO,fileName,filePath;
			reqVO=req.body.vo;
			fileName=reqVO.fileName;
			filePath=await appFileLib.getFilePath(fileName);
			res.json({ code: 200,fileName:fileName,path:filePath});
		};
		
		return appFileLib;
	};
}

export default AhFileLib;
export {AhFileLib};
