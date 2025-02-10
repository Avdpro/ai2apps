import fs from 'fs';
import asyncFS from 'node:fs/promises';
import { Readable } from 'stream';
import { pipeline } from 'stream/promises';
import unzipper from 'unzipper';
import pathLib from "path";

//---------------------------------------------------------------------------
async function extractZipFromBase64(base64String, targetDir) {
	// Ensure dir:
	if (!fs.existsSync(targetDir)) {
		await asyncFS.mkdir(targetDir,{recursive:true});
	}
	
	// Convert Base64 to Buffer
	const buffer = Buffer.from(base64String, 'base64');
	//const readStream=createReadStream(buffer);
	const readStream = new Readable({
		read() {
			this.push(buffer); // 将buffer推送到可读流
			this.push(null); // 表示数据已经读取完毕
		}
	});
	
	// Create unzip stream.
	const unzipStream = unzipper.Extract({ path: targetDir });
	
	// Pipe stream:
	await pipeline(
		readStream,
		unzipStream
	);
}

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

//---------------------------------------------------------------------------
//API for AI calls
export default function(app,router,apiMap) {
	const dbUser = app.get("DBUser");
	const dbPreview= app.get("DBPreview");
	const env =process.env;
	const previewRootDir=process.env.PREVIEW_DIR;
	
	//***********************************************************************
	//Share previews:
	//***********************************************************************
	{
		//-----------------------------------------------------------------------
		//Check sync name:
		apiMap["fileCheckSyncName"]= async function (req, res, next) {
			let reqVO;
			let dir,dirBase;
			reqVO=req.body.vo;
			dir=reqVO.dir;
			{
				let pos;
				pos=dir.indexOf("/");
				if(pos){
					dir=dir.substring(0,pos);
				}
			}
			dirBase=env["FILEDIR_"+dir];
			if(!dirBase){
				res.json({code:400,info:"Dir invalid."});
				return;
			}
			res.json({code:200});
		};
		
		//-----------------------------------------------------------------------
		//Get dir's entries
		apiMap["fileGetEntries"] = async function (req, res, next) {
			let reqVO;
			let dir,path,dirBase,recursive;
			let list,fname,fpath,results,state;
			let isDir,stub;
			reqVO=req.body.vo;
			dir=reqVO.dir;
			path=reqVO.path||"";
			recursive=reqVO.recursive||false;
			
			if(path.startsWith("..")||path.startsWith("/")){
				res.json({code:400,info:"Path invalid."});
				return;
			}
			{
				let pos;
				pos=dir.indexOf("/");
				if(pos){
					path=pathLib.join(dir.substring(pos+1),path);
					dir=dir.substring(0,pos);
				}
			}
			dirBase=env["FILEDIR_"+dir];
			if(!dirBase){
				res.json({code:400,info:"Dir invalid."});
				return;
			}
			if(dirBase[0]!=="/"){
				dirBase=pathLib.join(app.get("AppHomePath"),dirBase);
			}
			path=pathLib.join(dirBase,path);
			async function getEntries(path){
				results=[];
				try {
					list = await asyncFS.readdir(path);
				}catch(err){
					return null;
				}
				for(fname of list){
					fpath=pathLib.join(path,fname);
					state=await asyncFS.stat(fpath);
					stub={name:fname};
					isDir=state.isDirectory();
					results.push(stub);
					if(isDir){
						stub.dir=true;
						if(recursive){
							let subs;
							subs=await getEntries(pathLib.join(path,fname));
							if(subs){
								results=results.concat(subs);
							}
						}
					}else{
						stub.size=state.size;
						stub.modifyTime=state.mtime.getTime();
					}
				}
				return results;
			}
			let entries=await getEntries(path);
			res.json({code:200,entries:entries});
		};
		
		//-----------------------------------------------------------------------
		//Get entry-info:
		apiMap["fileGetEntry"]= async function (req, res, next) {
			let reqVO;
			let dir,path,dirBase;
			let state,stub,isDir;
			reqVO=req.body.vo;
			dir=reqVO.dir;
			path=reqVO.path||"";
			if(path.startsWith("..")||path.startsWith("/")){
				res.json({code:400,info:"Path invalid."});
				return;
			}
			
			{
				let pos;
				pos=dir.indexOf("/");
				if(pos){
					path=pathLib.join(dir.substring(pos+1),path);
					dir=dir.substring(0,pos);
				}
			}
			dirBase=env["FILEDIR_"+dir];
			if(!dirBase){
				res.json({code:400,info:"Dir invalid."});
				return;
			}
			if(dirBase[0]!=="/"){
				dirBase=pathLib.join(app.get("AppHomePath"),dirBase);
			}
			path=pathLib.join(dirBase,path);
			try {
				let fname=pathLib.basename(path);
				state = await asyncFS.stat(path);
				stub = { name: fname };
				isDir = state.isDirectory();
				if (isDir) {
					stub.dir = true;
				} else {
					stub.size = state.size;
					stub.modifyTime = state.mtime;
				}
				res.json({ code: 200, entry: stub });
			}catch(err){
				res.json({ code: 200, entry: null });
			}
		};
		
		//-----------------------------------------------------------------------
		//Sync a file up:
		apiMap["fileMakeDir"]= async function (req, res, next) {
			let reqVO;
			let dir,path,dirBase,recursive;
			let state,stub,isDir;
			reqVO=req.body.vo;
			dir=reqVO.dir;
			path=reqVO.path||"";
			recursive=reqVO.recursive||false;
			
			if(path.startsWith("..")||path.startsWith("/")){
				res.json({code:400,info:"Path invalid."});
				return;
			}
			
			{
				let pos;
				pos=dir.indexOf("/");
				if(pos){
					path=pathLib.join(dir.substring(pos+1),path);
					dir=dir.substring(0,pos);
				}
			}
			dirBase=env["FILEDIR_"+dir];
			if(!dirBase){
				res.json({code:400,info:"Dir invalid."});
				return;
			}
			if(dirBase[0]!=="/"){
				dirBase=pathLib.join(app.get("AppHomePath"),dirBase);
			}
			path=pathLib.join(dirBase,path);
			try {
				await asyncFS.mkdir(path,{recursive});
				res.json({code:200});
			}catch(err){
				res.json({code:500,info:"New dir failed."});
				return;
			}
		};

		//-----------------------------------------------------------------------
		//Sync a file up:
		apiMap["fileUpload"]= async function (req, res, next) {
			let reqVO;
			let dir,path,dirBase,recursive,data;
			let dirPath,fname,modifyTime;
			reqVO=req.body.vo;
			dir=reqVO.dir;
			path=reqVO.path||"";
			recursive=reqVO.recursive||false;
			data=reqVO.data||null;
			modifyTime=reqVO.time;
			modifyTime=modifyTime?(new Date(modifyTime)):new Date();
			
			
			if(!data){
				res.json({code:400,info:"Data invalid."});
				return;
			}
			
			if(path.startsWith("..")||path.startsWith("/")){
				res.json({code:400,info:"Path invalid."});
				return;
			}
			
			{
				let pos;
				pos=dir.indexOf("/");
				if(pos){
					path=pathLib.join(dir.substring(pos+1),path);
					dir=dir.substring(0,pos);
				}
			}
			dirBase=env["FILEDIR_"+dir];
			if(!dirBase){
				res.json({code:400,info:"Dir invalid."});
				return;
			}
			if(dirBase[0]!=="/"){
				dirBase=pathLib.join(app.get("AppHomePath"),dirBase);
			}
			path=pathLib.join(dirBase,path);
			dirPath=pathLib.dirname(path);
			fname=pathLib.basename(path);
			await saveFileFromBase64(data,dirPath,fname,recursive);
			await asyncFS.utimes(path,modifyTime,modifyTime);
			res.json({code:200});
		};
		
		//-----------------------------------------------------------------------
		//Download a file:
		apiMap["fileDownload"]= async function (req, res, next) {
			let reqVO;
			let dir,path,dirBase,buf,data;
			reqVO=req.body.vo;
			dir=reqVO.dir;
			path=reqVO.path||"";
			
			if(path.startsWith("..")||path.startsWith("/")){
				res.json({code:400,info:"Path invalid."});
				return;
			}
			
			{
				let pos;
				pos=dir.indexOf("/");
				if(pos){
					path=pathLib.join(dir.substring(pos+1),path);
					dir=dir.substring(0,pos);
				}
			}
			dirBase=env["FILEDIR_"+dir];
			if(!dirBase){
				res.json({code:400,info:"Dir invalid."});
				return;
			}
			if(dirBase[0]!=="/"){
				dirBase=pathLib.join(app.get("AppHomePath"),dirBase);
			}
			path=pathLib.join(dirBase,path);
			try{
				buf=await asyncFS.readFile(path);
				data=buf.toString("base64");
				res.json({code:200,data:data});
			}catch(err){
				res.json({code:500,info:"Read file error."});
			}
		};
		
		//-----------------------------------------------------------------------
		//Download a file:
		apiMap["fileDelete"]= async function (req, res, next) {
			let reqVO;
			let dir,path,dirBase,buf,recursive;
			reqVO=req.body.vo;
			dir=reqVO.dir;
			path=reqVO.path||"";
			recursive=reqVO.recursive||false;
			
			if(path.startsWith("..")||path.startsWith("/")){
				res.json({code:400,info:"Path invalid."});
				return;
			}
			
			{
				let pos;
				pos=dir.indexOf("/");
				if(pos){
					path=pathLib.join(dir.substring(pos+1),path);
					dir=dir.substring(0,pos);
				}
			}
			dirBase=env["FILEDIR_"+dir];
			if(!dirBase){
				res.json({code:400,info:"Dir invalid."});
				return;
			}
			if(dirBase[0]!=="/"){
				dirBase=pathLib.join(app.get("AppHomePath"),dirBase);
			}
			path=pathLib.join(dirBase,path);
			try{
				buf=await asyncFS.rm(path,{recursive:recursive,force:true});
				res.json({code:200});
			}catch(err){
				res.json({code:500,info:"Delete error."});
			}
		};
		
		//-----------------------------------------------------------------------
		//Copy a file up:
		apiMap["fileCopy"]= async function (req, res, next) {
			let reqVO;
			let dir,path,dirBase,buf,data,newPath;
			reqVO=req.body.vo;
			dir=reqVO.dir;
			path=reqVO.path||"";
			newPath=reqVO.newPath;
			{
				let pos;
				pos=dir.indexOf("/");
				if(pos){
					path=pathLib.join(dir.substring(pos+1),path);
					newPath=pathLib.join(dir.substring(pos+1),newPath);
					dir=dir.substring(0,pos);
				}
			}
			dirBase=env["FILEDIR_"+dir];
			if(!dirBase){
				res.json({code:400,info:"Dir invalid."});
				return;
			}
			if(dirBase[0]!=="/"){
				dirBase=pathLib.join(app.get("AppHomePath"),dirBase);
			}
			path=pathLib.join(dirBase,path);
			newPath=pathLib.join(dirBase,newPath);
			try {
				await asyncFS.cp(path, newPath, { recursive: true, force: true });
				res.json({code:200});
			}catch (e){
				res.json({code:500,info:"Copy error."});
			}
		};
		
		//-----------------------------------------------------------------------
		//Rename a file up:
		apiMap["fileRename"]= async function (req, res, next) {
			let reqVO;
			let dir,path,dirBase,buf,data,newPath;
			reqVO=req.body.vo;
			dir=reqVO.dir;
			path=reqVO.path||"";
			newPath=reqVO.newPath;
			{
				let pos;
				pos=dir.indexOf("/");
				if(pos){
					path=pathLib.join(dir.substring(pos+1),path);
					newPath=pathLib.join(dir.substring(pos+1),newPath);
					dir=dir.substring(0,pos);
				}
			}
			dirBase=env["FILEDIR_"+dir];
			if(!dirBase){
				res.json({code:400,info:"Dir invalid."});
				return;
			}
			if(dirBase[0]!=="/"){
				dirBase=pathLib.join(app.get("AppHomePath"),dirBase);
			}
			path=pathLib.join(dirBase,path);
			newPath=pathLib.join(dirBase,newPath);
			try {
				await asyncFS.rename(path, newPath);
				res.json({code:200});
			}catch(err){
				res.json({code:500,info:`Rename error: ${err}`});
			}
		};
	}
}
