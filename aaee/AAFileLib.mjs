import pathLib from "node:path";
import fs from 'node:fs';
import asyncFS from 'node:fs/promises';

const AABots_FileLibPath=process.env.AABOTS_FileLibPath||"filelib";

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
//AAFileLib
//***************************************************************************
let AAFileLib,aaFileLib;
{
	AAFileLib = function (msgSys) {
		this.msgSys = msgSys;
		this.fileDir = null;
		this.nextFileId=1;
	};
	aaFileLib = AAFileLib.prototype = {};
	
	//-----------------------------------------------------------------------
	AAFileLib.start=async function(msgSys){
		let fileLib;
		fileLib=new AAFileLib(msgSys);
		await fileLib.start();
		return fileLib;
	};
	
	//-----------------------------------------------------------------------
	aaFileLib.start=async function(){
		let dirPath;
		dirPath=AABots_FileLibPath;
		if(dirPath[0]!=="/"){
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
	aaFileLib.genFileName=async function(orgName){
		let basename,fileId;
		basename=pathLib.basename(orgName);
		fileId=""+(this.nextFileId++);
		fileId=fileId.padStart(6,"0");
		await asyncFS.writeFile(pathLib.join(this.fileDir,"_file_id.txt"),""+this.nextFileId);
		return `FILE-${fileId}-${basename}`;
	};
	
	//----------------------------------------------------------------------
	aaFileLib.writeFile=async function(orgName,base64Data){
		let dirPath,fileName;
		fileName=await this.genFileName(orgName);
		dirPath=this.fileDir;
		await saveFileFromBase64(base64Data,dirPath,fileName,true);
		return fileName;
	};
	
	//----------------------------------------------------------------------
	aaFileLib.readFile=async function(fileName){
		let buf,path,data;
		path=pathLib.join(this.fileDir,fileName);
		try {
			buf = await asyncFS.readFile(path);
			data = buf.toString("base64");
		}catch(err){
			data="";
		}
		return data;
	};
	
	AAFileLib.setup=async function(msgSys,app,router,apiMap){
		let appFileLib;
		appFileLib=await AAFileLib.start(msgSys);
		
		//-----------------------------------------------------------------------
		apiMap['AAEFileWrite']=async function(req,res,next){
			let reqVO,fileName,fileData;
			reqVO=req.body.vo;
			fileName=reqVO.fileName;
			fileData=reqVO.data;
			fileName=await appFileLib.writeFile(fileName,fileData);
			res.json({ code: 200,fileName:fileName});
		};
		
		//-----------------------------------------------------------------------
		apiMap['AAEFileRead']=async function(req,res,next){
			let reqVO,fileName,fileData;
			reqVO=req.body.vo;
			fileName=reqVO.fileName;
			fileData=await appFileLib.readFile(fileName);
			res.json({ code: 200,fileName:fileName,data:fileData});
		};
	};
}

export default AAFileLib;
export {AAFileLib};
