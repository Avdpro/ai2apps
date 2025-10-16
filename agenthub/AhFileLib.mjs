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
			await asyncFS.writeFile(pathLib.join(dirPath,"_file_id.txt"),""+this.nextFileId);
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
			//await saveFileFromBase64(data,this.fileDir,"test-"+fileName,true);
		}catch(err){
			data="";
		}
		return data;
	};

	//----------------------------------------------------------------------
	// 分块文件上传管理
	ahFileLib.pendingUploads = new Map(); // 存储正在上传的文件信息

	ahFileLib.startChunkedUpload=async function(orgName, totalSize, chunkSize){
		let uploadId, fileName, uploadInfo;
		uploadId = Date.now() + "_" + Math.random().toString(36).substr(2, 9);
		// 在开始时就生成最终文件名，避免重复调用genFileName
		fileName = await this.genFileName(orgName);

		uploadInfo = {
			uploadId: uploadId,
			fileName: fileName,
			orgName: orgName,
			totalSize: totalSize,
			chunkSize: chunkSize,
			chunks: [],
			receivedSize: 0,
			tempDir: pathLib.join(this.fileDir, "temp_" + uploadId)
		};

		// 创建临时目录
		if (!fs.existsSync(uploadInfo.tempDir)) {
			await asyncFS.mkdir(uploadInfo.tempDir, {recursive: true});
		}

		this.pendingUploads.set(uploadId, uploadInfo);
		return {uploadId, fileName};
	};

	ahFileLib.uploadChunk=async function(uploadId, chunkIndex, base64Data){
		let uploadInfo, chunkPath;
		uploadInfo = this.pendingUploads.get(uploadId);
		if (!uploadInfo) {
			throw new Error("Upload session not found");
		}

		// 保存chunk到临时文件
		chunkPath = pathLib.join(uploadInfo.tempDir, `chunk_${chunkIndex}`);
		const buffer = Buffer.from(base64Data, 'base64');
		await asyncFS.writeFile(chunkPath, buffer);

		uploadInfo.chunks[chunkIndex] = true;
		uploadInfo.receivedSize += buffer.length;

		return {
			uploadId: uploadId,
			chunkIndex: chunkIndex,
			receivedSize: uploadInfo.receivedSize,
			totalSize: uploadInfo.totalSize
		};
	};

	ahFileLib.finishChunkedUpload=async function(uploadId){
		let uploadInfo, finalPath, chunkFiles, mergedBuffer;
		uploadInfo = this.pendingUploads.get(uploadId);
		if (!uploadInfo) {
			throw new Error("Upload session not found");
		}

		// 合并所有chunk
		chunkFiles = [];
		for (let i = 0; i < uploadInfo.chunks.length; i++) {
			if (uploadInfo.chunks[i]) {
				let chunkPath = pathLib.join(uploadInfo.tempDir, `chunk_${i}`);
				let chunkData = await asyncFS.readFile(chunkPath);
				chunkFiles.push(chunkData);
			}
		}

		// 合并buffer
		mergedBuffer = Buffer.concat(chunkFiles);

		// 写入最终文件
		finalPath = pathLib.join(this.fileDir, uploadInfo.fileName);
		await asyncFS.writeFile(finalPath, mergedBuffer);

		// 清理临时文件和目录
		try {
			let files = await asyncFS.readdir(uploadInfo.tempDir);
			for (let file of files) {
				await asyncFS.unlink(pathLib.join(uploadInfo.tempDir, file));
			}
			await asyncFS.rmdir(uploadInfo.tempDir);
		} catch (err) {
			console.warn("Failed to clean up temp files:", err);
		}

		// 移除上传会话
		this.pendingUploads.delete(uploadId);

		return uploadInfo.fileName;
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

		//-----------------------------------------------------------------------
		// 分块上传API
		apiMap['AhFileStartChunked']=async function(req,res,next){
			try {
				let reqVO = req.body.vo;
				let result = await appFileLib.startChunkedUpload(
					reqVO.fileName,
					reqVO.totalSize,
					reqVO.chunkSize || 1048576
				);
				res.json({ code: 200, ...result });
			} catch (err) {
				res.json({ code: 500, info: err.message });
			}
		};

		//-----------------------------------------------------------------------
		apiMap['AhFileUploadChunk']=async function(req,res,next){
			try {
				let reqVO = req.body.vo;
				let result = await appFileLib.uploadChunk(
					reqVO.uploadId,
					reqVO.chunkIndex,
					reqVO.data
				);
				res.json({ code: 200, ...result });
			} catch (err) {
				res.json({ code: 500, info: err.message });
			}
		};

		//-----------------------------------------------------------------------
		apiMap['AhFileFinishChunked']=async function(req,res,next){
			try {
				let reqVO = req.body.vo;
				let fileName = await appFileLib.finishChunkedUpload(reqVO.uploadId);
				res.json({ code: 200, fileName: fileName });
			} catch (err) {
				res.json({ code: 500, info: err.message });
			}
		};
		
		AhFileLib.toAbsolutePath=async function(url){
			if(url.startsWith("hub://")){
				url=url.substring(6);
			}
			return await appFileLib.getFilePath(url);
		};
		
		return appFileLib;
	};
}

export default AhFileLib;
export {AhFileLib};
