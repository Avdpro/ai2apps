import {Buffer} from "./buffer.js";
import {JAXDisk} from "../lib/JAXDisk.js";
import {constants} from "./fsconst.js";
import pathLib from "./path.js";

var fs={};
var fsPromises={};
fs.constants=constants;
fs.fsPromises=fsPromises;
var fdIdxMap=new Map();
var fdPathMap=new Map();
var nextFdIdx=1;

//----------------------------------------------------------------------------
//Prase diskPath to disk and path-to-disk
function parseDiskPath(diskPath,callback){
	let diskName,path,disk,pts;
	if(!diskPath.startsWith("/")){
		let basePath;
		basePath=JAXDisk.appPath||"/";
		diskPath=pathLib.join(basePath,diskPath);
	}
	if(diskPath==="/"){
		callback(null,"","");
		return;
	}
	pts=diskPath.split("/");
	diskName=pts[1];
	pts=pts.slice(2);
	path=pts.join("/");
	JAXDisk.openDisk(diskName,0).then(disk=>{
		callback(disk,diskName,path);
	});
}

//----------------------------------------------------------------------------
//Prase diskPath to disk and path-to-disk, Promise version
async function parseDiskPathPM(diskPath){
	let diskName,path,disk,pts;
	if(!diskPath.startsWith("/")){
		let basePath;
		basePath=JAXDisk.appPath||"/";
		diskPath=pathLib.join(basePath,diskPath);
	}
	if(diskPath==="/"){
		return {disk:null,diskName:"",path:""};
	}
	pts=diskPath.split("/");
	diskName=pts[1];
	pts=pts.slice(2);
	path=pts.join("/");
	disk=await JAXDisk.openDisk(diskName,0);
	return {disk:disk,diskName:diskName,path:path};
}

//****************************************************************************
//fs.stats
//****************************************************************************
{
	//------------------------------------------------------------------------
	//Entry info:
	fs.Stats=function(entry){
		this.dev=0;
		this.ino=0;
		this.mode=0;
		this.nlink=0;
		this.uid=0;
		this.gid=0;
		this.rdev=0;
		this.size=entry.size||0;
		this.blksize=entry.size||0;
		this.blocks=1;
		this.atimeMs=Date.now();
		this.mtimeMs=entry.modifyTime||0;
		this.ctimeMS=entry.modifyTime||0;
		this.birthtimeMs=entry.createTime||0;
		this.atime=new Date(this.atimeMs);
		this.mtime=new Date(this.mtimeMs);
		this.ctime=new Date(this.ctimeMs);
		this.birthtime=new Date(this.birthtimeMs);
		
		this.isBlockDevice=function(){return false;};
		this.isCharacterDevice=function(){return false;};
		this.isDirectory=function(){return entry.dir;};
		this.isFIFO=function(){return false;};
		this.isFile=function(){return entry.dir?false:true;};
		this.isSymbolicLink=function(){return false;};
	};
}

//****************************************************************************
//fs.Dirent
//****************************************************************************
{
	//------------------------------------------------------------------------
	fs.Dirent=function(entry){
		this.name=entry.name;
		
		//------------------------------------------------------------------------
		this.isBlockDevice=function(){
			return entry.disk?true:false;
		};
		
		//------------------------------------------------------------------------
		this.isCharacterDevice=function(){
			return false;
		};
		
		//------------------------------------------------------------------------
		this.isDirectory=function(){
			return entry.dir?true:false;
		};
		
		//------------------------------------------------------------------------
		this.isFIFO=function(){
			return false;
		};
		
		//------------------------------------------------------------------------
		this.isFile=function(){
			return entry.dir?false:true;
		};
		
		//------------------------------------------------------------------------
		this.isSocket=function(){
			return false;
		};
		
		//------------------------------------------------------------------------
		this.isSymbolicLink=function(){
			return false;
		};
	};
}

//****************************************************************************
//fs.Dir
//****************************************************************************
{
	let dir;
	//------------------------------------------------------------------------
	//dir object in file-system
	fs.Dir=function(diskPath,disk,path){
		this.path=diskPath;
		this.disk=disk;
		this.dirPath=path;
		this.entries=null;
		this.entryIdx=0;
	};
	dir=fs.Dir.prototype={};
	
	//------------------------------------------------------------------------
	//close handle:
	let _closeDir=async function(){
		return;
	};
	dir.close=function(callback){
		if(callback){
			_closeDir().then(()=>{
				callback(null);
			});
		}else{
			return _closeDir();
		}
	};
	
	//------------------------------------------------------------------------
	//Read next entry:
	let _read=async function(dir){
		var list,entry;
		list=dir.entries;
		if(!list){
			list=await dir.disk.getEntries(dir.dirPath);
			dir.entryIdx=0;
			dir.entries=list;
			list=list.map(item=>new fs.Dirent(item));
		}
		if(!list){
			return null;
		}
		return list[this.entryIdx++];
	};
	dir.read=function(callback){
		if(callback){
			_read(this).then(item=>{
				callback(null,item);
			}).catch(e=>{
				callback(e);
			});
		}else{
			return _read(this);
		}
	};
}

//****************************************************************************
//fs.FileHandle
//****************************************************************************
{
	let filehandle;
	
	//------------------------------------------------------------------------
	//Opened file handle
	fs.FileHandle=function(diskPath,disk,path,flags,fd,data){
		this.openFlags=flags;
		this.fd=fd;
		this.diskPath=diskPath;
		this.disk=disk;
		this.path=path;
		this.dataPos=0;
		this.data=Buffer.from(data);
		this.isClose=0;
		this.readOnly=0;
		//Prase flag:
		switch(flags){
			//Not supports:
			case "as":
			case "as+":
			case "rs+":
				throw "Not supported";
			case "r":
				this.readOnly=1;
				this.dataPos=0;
				break;
			case "a+":
			case "ax+":
			case "a":
			case "ax":
				this.readOnly=0;
				this.dataPos=this.data.length;
				break;
			case "w+":
			case "wx+":
			case "w":
			case "wx":
				this.readOnly=0;
				this.dataPos=0;
				break;
		}
	};
	filehandle=fs.FileHandle.prototype={};
	
	//------------------------------------------------------------------------
	//Append data to file:
	filehandle.appendFile=async function(data,options){
		let buf,buf1,buf2,encode;
		if(typeof(options)==="string"){
			encode=options;
		}else if(options &&options.encode){
			encode=options.encode;
		}
		buf1=Buffer.from(this.data,0,this.dataPos);
		buf2=Buffer.from(data,encode);
		buf=Buffer.concat([buf1,buf2]);
		this.data=buf;
		this.dataPos=buf.length;
	};
	
	//------------------------------------------------------------------------
	//Change file mod: not supported
	filehandle.chmod=async function(mode){
		return;
	};
	
	//------------------------------------------------------------------------
	//Change file owner: not supported
	filehandle.chown=async function(uid, gid){
		return;
	};
	
	//------------------------------------------------------------------------
	//Close file handle
	filehandle.close=async function(){
		let list;
		//Ensure we saved:
		await this.datasync();
		fdIdxMap.delete(this.fd);
		list=fdPathMap.get(this.diskPath);
		if(list){
			let idx=list.indexOf(this);
			if(idx>=0){
				list.splice(idx,1);
			}
			if(!list.length){
				fdPathMap.delete(this.diskPath);
			}
		}
		this.closed=true;
		this.data=null;
		this.dataPos=0;
	};
	
	//------------------------------------------------------------------------
	//Sync data, save data to disk
	filehandle.datasync=async function(){
		let flag=this.openFlags;
		//Check if need write by open flags:
		switch(flag){
			case "a+":
			case "ax+":
			case "w":
			case "w+":
			case "wx":
			case "wx+":
				return await this.disk.writeFile(this.path,this.data);
		}
	};
	
	//------------------------------------------------------------------------
	//Read part of data:
	filehandle.read=async function(buffer, offset, length, position){
		let buf,pos,remainLen;
		if(buffer && (!(buffer instanceof Buffer))){
			let options=buffer;
			buffer=options.buffer;
			offset=options.offset;
			length=options.length;
			position=options.position;
		}
		if(!buffer){
			buffer=Buffer.alloc(16384);
		}
		if(offset===undefined){
			offset=0;
		}
		if(length===undefined){
			length=buffer.length;
		}
		if(position===undefined){
			position=null;
		}
		pos=position>=0?position:this.dataPos;
		remainLen=this.data.length-pos;
		if(remainLen<length){
			length=remainLen;
		}
		this.data.copy(buffer,offset,pos,length);
		if(position===null){
			this.dataPos=this.dataPos+length;
		}
		return {buffer:buffer,bytesRead:length};
	};
	
	//------------------------------------------------------------------------
	//Read all data:
	filehandle.readFile=function(options){
		let encoding,data;
		if(typeof(options)==="string"){
			encoding=options;
		}else if(options && options.encoding){
			encoding=options.encoding;
		}
		data=Buffer.from(this.data);
		if(encoding){
			return data.toString(encoding);
		}
		return data;
	};
	
	//------------------------------------------------------------------------
	//Read multi-parts of data:
	filehandle.readv=async function(buffers, position){
		let pos,bytesRead,i,n,res;
		if(position===undefined){
			pos=this.dataPos;
		}else{
			pos=position;
		}
		pos=pos<0?0:pos;
		pos=pos>this.data.length?this.data.length:pos;
		this.dataPos=pos;
		bytesRead=0;
		n=buffers.length;
		for(i=0;i<n;i++){
			res=await this.read(buffers[i]);
			bytesRead+=res.bytesRead;
			if(!res.bytesRead){
				break;
			}
		}
		//TODO: We only support buffer type at this moment:
		return {buffers:buffers,bytesRead:bytesRead};
	};
	
	//------------------------------------------------------------------------
	//Get file state
	filehandle.stat=async function(options){
		let entry;
		entry=await this.disk.getEntry(this.path);
		if(entry){
			return new fs.Stats(entry);
		}
		return null;
	};
	
	//------------------------------------------------------------------------
	//Sync data with disk
	filehandle.sync=async function(){
		let flag=this.openFlags;
		//Save if open flag with w/a:
		switch(flag){
			case "a+":
			case "ax+":
			case "w":
			case "w+":
			case "wx":
			case "wx+":
				return await this.disk.writeFile(this.path,this.data);
		}
	};
	
	//------------------------------------------------------------------------
	//Limit data size:
	filehandle.truncate=async function(len){
		if(!(len>=0)){
			len=0;
		}
		if(len>this.data.length){
			this.data=Buffer.concat([this.data,Buffer.alloc(len-this.data.length,0)]);
		}else if(len<this.data.length){
			this.data=Buffer.from(this.data,0,len);
		}
		this.dataPos=this.data.length;
	};
	
	//------------------------------------------------------------------------
	//Update file modify time:
	filehandle.utimes=async function(atime, mtime){
		if(mtime instanceof Date){
			mtime=mtime.getTime();
		}
		return await this.disk.setEntryInfo(this.path,{modifyTime:mtime});
	};
	
	//------------------------------------------------------------------------
	//Write data:
	filehandle.write=async function(buffer, offset, length, position){
		let pos,buf1,buf2;
		if(!(buffer instanceof Buffer)){
			return this._writeString(buffer,offset,length);
		}
		offset=offset||0;
		length=length||buffer.length;
		if(position>=0){
			pos=position;
		}else{
			pos=this.dataPos;
		}
		pos=pos>this.data.length?this.data.length:pos;
		buf1=Buffer.from(this.data,0,pos);
		buf2=Buffer.from(buffer,offset,length);
		this.data=Buffer.concat([buf1,buf2]);
		return {buffer:buf2,bytesWritten:buf2.length};
	};
	
	//------------------------------------------------------------------------
	//Write string:
	filehandle._writeString=async function(text, position,encoding){
		let buf1,buf2;
		text=""+text;
		position=position>=0?position:this.dataPos;
		buf1=Buffer.from(this.data,0,position);
		buf2=Buffer.from(text,encoding);
		this.data=Buffer.concat([buf1,buf2]);
		return {buffer:text,bytesWritten:buf2.length};
	};
	
	//------------------------------------------------------------------------
	//Write the whole file:
	filehandle.writeFile=async function(data, options){
		let encoding;
		if(typeof(options)==="string"){
			encoding=options;
		}else if(options && options.encoding){
			encoding=options.encoding;
		}
		this.data=Buffer.from(data,encoding);
		this.dataPos=this.data.length;
		return;
	};
	
	//------------------------------------------------------------------------
	//Write multi-parts data into file::
	filehandle.writev=async function(buffers, position){
		let pos,bytesWritten,i,n,res;
		if(position===undefined){
			pos=this.dataPos;
		}else{
			pos=position;
		}
		pos=pos<0?0:pos;
		pos=pos>this.data.length?this.data.length:pos;
		this.dataPos=pos;
		bytesWritten=0;
		n=buffers.length;
		for(i=0;i<n;i++){
			res=await this.write(buffers[i]);
			bytesWritten+=res.bytesWritten;
			if(!res.bytesWritten){
				break;
			}
		}
		return;
	};
}

//****************************************************************************
//Promised functions:
//****************************************************************************
{
	//------------------------------------------------------------------------
	//Acess the file:
	fsPromises.access=function(path, mode){
		return new Promise((doneFunc,failFunc)=>{
			fs.access(path,mode,(err)=>{
				if(!err){
					doneFunc();
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Append data to file:
	fsPromises.appendFile=function(path, data, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.appendFile(path,data,options,(err)=>{
				if(err){
					failFunc(err);
				}else{
					doneFunc();
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Change file mode, do nothing now
	fsPromises.chmod=function(path, mode){
		return new Promise((doneFunc,failFunc)=>{
			doneFunc();
		});
	};
	
	//------------------------------------------------------------------------
	//Change file owner, do nothing now
	fsPromises.chown=function(path, uid, gid){
		return new Promise((doneFunc,failFunc)=>{
			doneFunc();
		});
	};
	
	//------------------------------------------------------------------------
	//Copy file:
	fsPromises.copyFile=function(src, dest, mode){
		return new Promise((doneFunc,failFunc)=>{
			fs.copyFile(src,dest,mode,(err)=>{
				if(err){
					failFunc(err);
				}else{
					doneFunc();
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Copy item (file or dir)
	fsPromises.cp=function(src, dest, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.cp(src,dest,options,(err)=>{
				if(err){
					failFunc(err);
				}else{
					doneFunc();
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Change link mode, not support:
	fsPromises.lchmod=function(path, mode){
		return new Promise((doneFunc,failFunc)=>{
			failFunc("File system link is not supported.");
		});
	};
	
	//------------------------------------------------------------------------
	//Change link owner, not support
	fsPromises.lchown=function(path, uid, gid){
		return new Promise((doneFunc,failFunc)=>{
			failFunc("File system link is not supported.");
		});
	};
	
	//------------------------------------------------------------------------
	//Change link time, not support
	fsPromises.lutimes=function(path, atime, mtime){
		return new Promise((doneFunc,failFunc)=>{
			failFunc("File system link is not supported.");
		});
	};
	
	//------------------------------------------------------------------------
	//Create link, not support
	fsPromises.link=function(existingPath, newPath){
		return new Promise((doneFunc,failFunc)=>{
			failFunc("File system link is not supported.");
		});
	};
	
	//------------------------------------------------------------------------
	//Get link state, not support
	fsPromises.lstat=function(path, options){
		return new Promise((doneFunc,failFunc)=>{
			failFunc("File system link is not supported.");
		});
	};
	
	//------------------------------------------------------------------------
	//Create a new dir:
	fsPromises.mkdir=function(path, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.mkdir(path,options,(err,path)=>{
				if(!err){
					doneFunc(path);
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Create temp dir:
	fsPromises.mkdtemp=function(prefix, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.mkdtemp(prefix,options,(err,path)=>{
				if(!err){
					doneFunc(path);
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Open a file handl:
	fsPromises.open=async function(diskPath, flags, mode){
		let meta,disk,diskName,path,entry,newFile,buf;
		let fd,list,fileObj,onlyRead;
		fd=0;
		list=fdPathMap.get(diskPath);
		if(list && list[0]){
			if(flags!=="r" || list[0].openFlags!=="r"){
				throw "File is not accessable.";
			}
		}
		meta=await parseDiskPathPM(diskPath);
		disk=meta.disk;
		diskName=meta.diskName;
		path=meta.path;
		if(!disk){
			return null;
		}
		entry=await disk.getEntry(path);
		if(!entry || entry.dir){
			newFile=1;
		}
		//Parse if file should exist
		switch(flags){
			case "ax+":
			case "wx+":
			case "ax":
			case "wx":
				throw "File not exist: "+diskPath;
		}
		//Prase if will read:
		switch(flags){
			//Mode we don't support:
			case "as":
			case "as+":
			case "rs+":
				throw "Not supported";
			case "a+":
			case "ax+":
			case "r":
			case "w+":
			case "wx+":
				if(newFile){
					buf=Buffer.alloc(0);
				}else{
					let data;
					data=disk.loadFile(path);
					buf=Buffer.from(data);
				}
				break;
			case "a":
			case "ax":
			case "w":
			case "wx":
				buf=Buffer.alloc(0);
				break;
		}
		fd=nextFdIdx++;
		fileObj=new fs.FileHandle(disk,path,flags,fd,buf);
		fdIdxMap.set(fd,fileObj);
		if(list){
			list.push(fileObj);
		}else{
			fdPathMap.set(diskPath,[fileObj]);
		}
		return fileObj;
	};
	
	//------------------------------------------------------------------------
	//Open a dir to read entries:
	fsPromises.opendir=function(path, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.opendir(path,options,(err,dir)=>{
				if(!err){
					doneFunc(dir);
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Read all entries in dir:
	fsPromises.readdir=function(path, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.readdir(path,options,(err,list)=>{
				if(!err){
					doneFunc(list);
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Read a file's data:
	fsPromises.readFile=function(path, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.readFile(path,options,(err,data)=>{
				if(!err){
					doneFunc(data);
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Read a link's data, not support
	fsPromises.readlink=function(path, options){
		return new Promise((doneFunc,failFunc)=>{
			failFunc("File system link is not supported.");
		});
	};
	
	//------------------------------------------------------------------------
	//Get absolute path:
	fsPromises.realpath=function(path, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.realpath(path,options,(err,path)=>{
				if(!err){
					doneFunc(path);
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Change path name:
	fsPromises.rename=function(oldPath, newPath){
		return new Promise((doneFunc,failFunc)=>{
			fs.rename(oldPath,newPath,(err)=>{
				if(!err){
					doneFunc();
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Remove a dir:
	fsPromises.rmdir=function(path, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.rmdir(path,options,(err)=>{
				if(!err){
					doneFunc();
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Remove a entry (file or dir)
	fsPromises.rm=function(path, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.rm(path,options,(err)=>{
				if(!err){
					doneFunc();
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Get a info of an entry:
	fsPromises.stat=function(path, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.stat(path,options,(err,stat)=>{
				if(!err){
					doneFunc(stat);
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//symlink: Not support:
	fsPromises.symlink=function(target, path, type){
		return new Promise((doneFunc,failFunc)=>{
			failFunc("File system link is not supported.");
		});
	};
	
	//------------------------------------------------------------------------
	//Limit file size:
	fsPromises.truncate=function(path, len){
		return new Promise((doneFunc,failFunc)=>{
			fs.truncate(path,len,(err)=>{
				if(!err){
					doneFunc();
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//unlink, not supported:
	fsPromises.unlink=function(path){
		return new Promise((doneFunc,failFunc)=>{
			failFunc("File system link is not supported.");
		});
	};
	
	//------------------------------------------------------------------------
	//Change file time:
	fsPromises.utimes=function(path, atime, mtime){
		return new Promise((doneFunc,failFunc)=>{
			fs.utimes(path,atime,mtime,(err)=>{
				if(!err){
					doneFunc();
				}else{
					failFunc(err);
				}
			});
		});
	};
	
	//------------------------------------------------------------------------
	//Watch a file:
	fsPromises.watch=function(filename, options){
		return new Promise((doneFunc,failFunc)=>{
			//TODO: Code this:
			failFunc("File system link is not supported.");
		});
	};
	
	//------------------------------------------------------------------------
	//Write data to a file:
	fsPromises.writeFile=function(file, data, options){
		return new Promise((doneFunc,failFunc)=>{
			fs.writeFile(file,data,options,(err)=>{
				if(!err){
					doneFunc();
				}else{
					failFunc(err);
				}
			});
		});
	};
}

//****************************************************************************
//Call-back functions:
//****************************************************************************
{
	//----------------------------------------------------------------------------
	//Access a file:
	fs.access=function(diskPath,mode,callback)
	{
		if(mode instanceof Function){
			mode=constants.F_OK;
			callback=mode;
		}
		//解析路径:
		parseDiskPath(diskPath,(disk,diskName,path)=>{
			if(!disk){
				if(diskName==="" && path===""){
					callback(0);
				}
				callback("Disk error");
				return;
			}
			if(!path){//就是磁盘本身
				callback(0);
				return;
			}
			disk.isExist(path).then(exist=>{
				if(exist){
					callback(0);
					return;
				}
				callback("File is not exist: "+diskPath);
			});
		});
	};
	
	//----------------------------------------------------------------------------
	//Append data to a file:
	fs.appendFile=function(diskPath,data,options,callback)
	{
		if(options instanceof Function){
			callback=options;
		}
		
		//first, parse file path:
		parseDiskPath(diskPath,(disk,diskName,path)=>{
			if(!disk){
				callback("Disk not found: "+diskName);
				return;
			}
			if(!path){
				callback("File name missing: "+diskPath);
				return;
			}
			disk.getEntry(path).then(entry=>{
				if(entry && entry.dir){
					callback("Target path is dir");
					return;
				}
				//Read current file data then append:
				disk.loadFile(path).then(fileData=>{
					let oldBuf,dataBuf,newBuf;
					if(typeof(data)==="string"){
						dataBuf=Buffer.from(data,typeof(options)==="string"?options:"utf8");
					}else if(data instanceof Buffer){
						dataBuf=data;
					}else{
						callback("Error data type");
						return;
					}
					if(fileData){
						oldBuf=Buffer.from(fileData);
					}else{
						oldBuf=Buffer.from([]);
					}
					//Append data:
					newBuf=Buffer.concat([oldBuf,dataBuf]);
					disk.saveFile(path,newBuf).then(()=>{
						callback(0);
					}).catch(e=>{
						callback(e);
					});
					
				});
			});
		});
	};
	
	//----------------------------------------------------------------------------
	//Change file mode, not supported
	fs.chmod=function(path, mode, callback){
		setTimeout(callback(0),0);
	};
	
	//----------------------------------------------------------------------------
	//Change file owner, not supported
	fs.chown=function(path, uid, gid, callback){
		setTimeout(callback(0),0);
	};
	
	//----------------------------------------------------------------------------
	//Close file handle
	fs.close=function(fdIdx, callback){
		let fdObj;
		fdObj=fdIdxMap.get(fdIdx);
		if(!fdObj){
			return;
		}
		fdObj.close().then(()=>{
			callback(0);
		});
	};
	
	//----------------------------------------------------------------------------
	//Copy file:
	fs.copyFile=function(src, dest, mode, callback){
		if(mode instanceof Function){
			return fs.copyFile(src,dest,0,mode);
		}
		
		//Parse src-path:
		parseDiskPath(src,(srcDisk,srcDiskName,srcPath)=>{
			if(!srcDisk){
				callback("Src disk not found: "+src);
				return;
			}
			if(!srcPath){
				callback("Src file name missing: "+src);
				return;
			}
			//Prase dst-Path:
			parseDiskPath(dest,(dstDisk,dstDiskName,dstPath)=>{
				if(!dstDisk){
					callback("Dest disk not found: "+dest);
					return;
				}
				if(!dstPath){
					callback("Dest file name missing: "+dest);
					return;
				}
				dstDisk.copyFile(srcPath,dstPath,(mode&constants.COPYFILE_EXCL)?0:1,srcDisk).then(()=>{
					callback(null);
				}).catch(err=>{
					callback(err);
				});
			});
		});
	};
	
	//----------------------------------------------------------------------------
	//Copy file or dir:
	fs.cp=function(src,dst,options,callback){
		if(options instanceof Function){
			return fs.cp(src,dst,{},options);
		}
		fs.copyFile(src,dst,0,callback);
	};
	
	//----------------------------------------------------------------------------
	//Create a stream to read this file, not supported at this moment:
	fs.createReadStream=function(path,options){
		//TODO: Code this: B
		return null;
	};
	
	//----------------------------------------------------------------------------
	//Create a stream to write into file, not supported at this moment:
	fs.createWriteStream=function(path, options){
		//TODO: Code this: B
		return null;
	};
	
	//----------------------------------------------------------------------------
	//Check a path is available
	fs.exists=function(path, callback){
		//Use access:
		fs.access(path,constants.F_OK,callback);
	};
	
	//----------------------------------------------------------------------------
	//Change file mode by file-descriptor, not supported:
	fs.fchmod=function(fdIdx, mode, callback){
		let fdObj;
		fdObj=fdIdxMap.get(fdIdx);
		if(!fdObj){
			callback("File handle not found: "+fdIdx);
		}
		fdObj.chmod(mode).then(()=>{
			callback(null);
		}).catch(err=>{
			callback(err);
		});
	};
	
	//----------------------------------------------------------------------------
	//Change file owner by file-descriptor, not supported:
	fs.fchown=function(fdIdx, uid, gid, callback){
		let fdObj;
		fdObj=fdIdxMap.get(fdIdx);
		if(!fdObj){
			callback("File handle not found: "+fdIdx);
		}
		fdObj.chown(uid, gid).then(()=>{
			callback(null);
		}).catch(err=>{
			callback(err);
		});
	};
	
	//----------------------------------------------------------------------------
	//Force file descriptor to sync
	fs.fdatasync=function(fdIdx, callback){
		let fdObj;
		fdObj=fdIdxMap.get(fdIdx);
		if(!fdObj){
			callback("File handle not found: "+fdIdx);
		}
		fdObj.datasync().then(()=>{
			callback(null);
		}).catch(err=>{
			callback(err);
		});
	};
	
	//----------------------------------------------------------------------------
	//Get file state by descriptor:
	fs.fstat=function(fdIdx, options, callback){
		let fdObj;
		fdObj=fdIdxMap.get(fdIdx);
		if(!fdObj){
			callback("File handle not found: "+fdIdx);
		}
		fdObj.stat().then((stat)=>{
			callback(null,stat);
		}).catch(err=>{
			callback(err);
		});
	};
	
	//----------------------------------------------------------------------------
	//Sync file descriptor
	fs.fsync=function(fdIdx, callback){
		let fdObj;
		fdObj=fdIdxMap.get(fdIdx);
		if(!fdObj){
			callback("File handle not found: "+fdIdx);
		}
		fdObj.sync().then(()=>{
			callback(null);
		}).catch(err=>{
			callback(err);
		});
	};
	
	//----------------------------------------------------------------------------
	//Limit file size by descriptor:
	fs.ftruncate=function(fdIdx, len, callback){
		let fdObj;
		fdObj=fdIdxMap.get(fdIdx);
		if(!fdObj){
			callback("File handle not found: "+fdIdx);
		}
		fdObj.truncate(len).then(()=>{
			callback(null);
		}).catch(err=>{
			callback(err);
		});
	};
	
	//----------------------------------------------------------------------------
	//Update file times by descriptor:
	fs.futimes=function(fdIdx, atime, mtime, callback){
		let fdObj;
		fdObj=fdIdxMap.get(fdIdx);
		if(!fdObj){
			callback("File handle not found: "+fdIdx);
		}
		fdObj.utimes(atime,mtime).then(()=>{
			callback(null);
		}).catch(err=>{
			callback(err);
		});
	};
	
	//----------------------------------------------------------------------------
	//Change link mode, not supported:
	fs.lchmod=function(path, mode, callback){
		//TODO: Code this D
		setTimeout(()=>callback("Not supported."),0);
	};
	
	//----------------------------------------------------------------------------
	//Change link owner, not supported:
	fs.lchown=function(path, uid, gid, callback){
		//TODO: Code this D
		setTimeout(()=>callback("Not supported."),0);
	};
	
	//----------------------------------------------------------------------------
	//Change link time, not supported:
	fs.lutimes=function(path, atime, mtime, callback){
		//TODO: Code this D
		setTimeout(()=>callback("Not supported."),0);
	};
	
	//----------------------------------------------------------------------------
	//link file,not supported:
	fs.link=function(existingPath, newPath, callback){
		//TODO: Code this D
		setTimeout(()=>callback("Not supported."),0);
	};
	
	//----------------------------------------------------------------------------
	//Get link state, not supported:
	fs.lstat=function(path, options, callback){
		//TODO: Code this D
		setTimeout(()=>callback("Not supported."),0);
	};
	
	//----------------------------------------------------------------------------
	//Create a new dir:
	fs.mkdir=function(diskPath, options, callback){
		if(options instanceof Function){
			return fs.mkdir(diskPath,{},options);
		}
		let recursive=options.recursive||0;
		
		parseDiskPath(diskPath,(disk,diskName,path)=>{
			if(!disk){
				callback("Disk error: "+diskPath);
				return;
			}
			disk.newDir(path,0,recursive).then((dirObj)=>{
				callback(null,diskPath);
			}).catch(e=>{
				callback("mkdir error: "+e);
			});
		});
	};
	
	//----------------------------------------------------------------------------
	//Create a temp dir:
	fs.mkdtemp=function(prefix, options, callback){
		if(options instanceof Function){
			return fs.mkdtemp(prefix,{},options);
		}
		return fs.mkdir(prefix+""+Math.floor(Math.random()*1000000),options,callback);
	};
	
	//----------------------------------------------------------------------------
	//Open a file descriptor:
	fs.open=function(path, flags, mode, callback){
		if(flags instanceof Function){
			return fs.open(path,"r",0o666,flags);
		}
		if(mode instanceof Function){
			return fs.open(path,flags,0o666,mode);
		}
		
		fsPromises.open(path,flags,mode).then(handle=>{
			if(handle){
				callback(null,handle.fd);
			}else{
				callback("Open failed");
			}
		}).catch(e=>{
			callback("Open failed");
		});
	};
	
	//----------------------------------------------------------------------------
	//Open a dir handle:
	fs.opendir=function(diskPath, options, callback){
		if(options instanceof Function){
			return fs.opendir(diskPath,{},options);
		}
		
		parseDiskPath(diskPath,(disk,diskName,path)=>{
			let dir;
			if(!disk){
				callback("Disk error: "+diskPath);
				return;
			}
			dir=new fs.Dir(diskPath,disk,path);
			callback(null,dir);
		});
	};
	
	//----------------------------------------------------------------------------
	//Read data from file descriptor:
	fs.read=function(fd, buffer, offset, length, position, callback){
		if(buffer instanceof Function){
			let buf;
			buf=Buffer.alloc(16384);
			return fs.read(fd,buf,0,buf.byteLength,null,buffer);
		}
		if(offset instanceof Function){
			let opts=buffer;
			let buf;
			buf=opts.buffer||Buffer.alloc(16384);
			return fs.read(fd,buf,0,opts.length,buf.byteLength,opts.position||null,offset);
		}
		let handle;
		handle=fdIdxMap.get(fd);
		if(!handle){
			callback("FD is invalid.");
		}else{
			handle.read(buffer,offset,length,position).then(stub=>{
				callback(null,stub.bytesRead,stub.buffer);
			}).catch(e=>{
				callback(e);
			});
		}
	};
	
	//----------------------------------------------------------------------------
	//Read dir entries:
	fs.readdir=function(diskPath, options, callback){
		if(options instanceof Function){
			return fs.readdir(diskPath,"utf8",options);
		}
		if(!options){
			options={encoding:"utf8"};
		}
		if(typeof(options)==="string"){
			options={encoding:options};
		}
		options.encoding=options.encoding||"utf8";
		if(options.encoding!=="utf8" && options.encoding!=="utf-8"){
			//TODO: Code this:
			setTimeout(()=>callback("Not supported.",null),0);
			return;
		}
		if(diskPath==="/"){
			//Return all disk names:
			JAXDisk.getDiskNames().then(list=>{
				if(options.withFileTypes){
					list=list.map(item=>new fs.Dirent({name:item,dir:1,disk:1}));
				}
				callback(null,list);
			});
		}else{
			parseDiskPath(diskPath,(disk,diskName,path)=>{
				if(!disk){
					callback("Disk error: "+diskPath);
					return;
				}
				disk.getEntries(path).then(list=>{
					if(!list){
						callback("Path is not dir: "+diskPath);
						return;
					}
					if(options.withFileTypes){
						list=list.map(item=>new fs.Dirent(item.name));
					}else{
						list=list.map(item=>item.name);
					}
					callback(null,list);
				});
			});
		}
	};
	
	//----------------------------------------------------------------------------
	//Readf file data
	fs.readFile=function(diskPath, options, callback){
		if(options instanceof Function){
			return fs.readFile(diskPath,null,options);
		}
		
		if(typeof(options)==="string"){
			options={encoding:options};
		}
		
		parseDiskPath(diskPath,(disk,diskName,path)=>{
			if(!disk){
				callback("Disk error: "+diskPath);
				return;
			}
			if(options && options.encoding){
				disk.loadText(path).then(text=>{
					if(text===null){
						callback("readFile error: file not found.");
					}
					callback(null,text);
				}).catch(e=>{
					callback("readFile error: "+e);
				});
			}else{
				disk.loadFile(path).then(data=>{
					let buf;
					if(data===null){
						callback("readFile error: file not found.");
					}
					buf=Buffer.from(data);
					callback(null,buf);
				}).catch(e=>{
					callback("readFile error: "+e);
				});
			}
		});
	};
	
	//----------------------------------------------------------------------------
	//Read link data: not supported:
	fs.readlink=function(path, options, callback){
		if(options instanceof Function){
			return fs.readlink(path,"utf8",options);
		}
		//TODO: Code this: D
		setTimeout(()=>callback("Not supported.",null),0);
	};
	
	//----------------------------------------------------------------------------
	//Read file data to multi-buffers:
	fs.readv=function(fd, buffers, position, callback){
		if(position instanceof Function){
			return fs.readv(fd,buffers,null,callback);
		}
		//TODO: Check this: A
		let handle;
		handle=fdIdxMap.get(fd);
		if(!handle){
			callback("FD is invalid.");
		}else{
			handle.readv(buffers,position).then(stub=>{
				callback(null,stub.bytesRead,stub.buffers);
			}).catch(e=>{
				callback(e);
			});
		}
	};
	
	//----------------------------------------------------------------------------
	//Return absolute path：
	fs.realpath=function(diskPath, options, callback){
		if(options instanceof Function){
			return fs.realpath(diskPath,'utf8',options);
		}
		
		if(!diskPath.startsWith("/")){
			let basePath;
			basePath=JAXDisk.appPath||"/";
			diskPath=pathLib.join(basePath,diskPath);
		}
		callback(null,diskPath);
	};
	
	//----------------------------------------------------------------------------
	//Return native path:
	fs.realpath.native=function(path, options, callback){
		return fs.realpath(path,options,callback);
	};
	
	//----------------------------------------------------------------------------
	//Rename:
	fs.rename=function(src, dest, callback){
		//Prase src path:
		parseDiskPath(src,(srcDisk,srcDiskName,srcPath)=>{
			if(!srcDisk){
				callback("Src disk not found: "+src);
				return;
			}
			if(!srcPath){
				callback("Src file name missing: "+src);
				return;
			}
			//Prase dst path
			parseDiskPath(dest,(dstDisk,dstDiskName,dstPath)=>{
				if(!dstDisk){
					callback("Dest disk not found: "+dest);
					return;
				}
				if(!dstPath){
					callback("Dest file name missing: "+dest);
					return;
				}
				if(dstDisk===srcDisk){
					dstDisk.rename(srcPath,dstPath).then(()=>{
						callback(null);
					});
				}else{
					dstDisk.copyFile(srcPath,dstPath,true,srcDisk).then(()=>{
						srcDisk.del(srcPath);
					});
				}
			});
		});
	};
	
	//----------------------------------------------------------------------------
	//Remove dir:
	fs.rmdir=function(diskPath, options, callback){
		if(options instanceof Function){
			return fs.rmdir(diskPath,{recursive:false},options);
		}
		let force=(options&&options.force)||0;
		let recursive=(options&&options.recursive)||0;
		parseDiskPath(diskPath,(disk,diskName,path)=>{
			if(!disk){
				if(!force){
					callback("Disk not found: "+diskPath);
				}else{
					callback(null);
				}
				return;
			}
			if(!path){
				if(!force){
					callback("Dir name missing: "+diskPath);
				}else{
					callback(null);
				}
				return;
			}
			disk.getEntry(path).then(entry=>{
				if(!entry){
					callback("Dir not found: "+path);
					return;
				}
				if(!entry.dir){
					if(!force){
						callback("Entry is not dir: "+path);
					}else{
						callback(null);
					}
					return;
				}
				if(recursive){
					disk.del(path).then(()=>{
						callback(null);
					});
				}else{
					disk.getEntries(path).then(list=>{
						if(list.length>0){
							callback("Dir is not empty: "+diskPath);
							return;
						}
						disk.del(path).then(()=>{
							callback(null);
						});
					});
				}
			});
		});
	};
	
	//----------------------------------------------------------------------------
	//Remove a entry (file or dir):
	fs.rm=function(diskPath, options, callback){
		if(options instanceof Function){
			return fs.rm(diskPath,{force:false,recursive:false},options);
		}
		
		let recursive=(options&&options.recursive)||0;
		let force=(options&&options.force)||0;
		parseDiskPath(diskPath,(disk,diskName,path)=>{
			if(!disk){
				if(force){
					callback(null);
					return;
				}
				callback("Path not found: "+diskPath);
				return;
			}
			if(!path){
				if(force){
					callback(null);
					return;
				}
				callback("Path name missing: "+diskPath);
				return;
			}
			disk.getEntry(path).then(entry=>{
				if(!entry){
					if(force){
						callback(null);
						return;
					}
					callback("Path not found: "+path);
					return;
				}
				if(!entry.dir){
					disk.del(path).then(()=>{
						callback(null);
					});
					return;
				}
				if(recursive){
					disk.del(path).then(()=>{
						callback(null);
					});
				}else{
					disk.getEntries(path).then(list=>{
						if(list.length>0){
							callback("Dis is not empty: "+diskPath);
							return;
						}
						disk.del(path).then(()=>{
							callback(null);
						});
					});
				}
			});
		});
	};
	
	//----------------------------------------------------------------------------
	//Get state of a path entry:
	fs.stat=function(diskPath, options, callback){
		if(options instanceof Function){
			return fs.stat(diskPath,{bigint:false},options);
		}
		
		parseDiskPath(diskPath,(disk,diskName,path)=>{
			if(!disk){
				callback("Disk not found: "+diskPath);
				return;
			}
			if(!path){
				callback("Dir name missing: "+diskPath);
				return;
			}
			disk.getEntry(path).then(entry=>{
				if(entry){
					callback(null,new fs.Stats(entry));
				}else{
					callback("File not found.");
				}
			});
		});
	};
	
	//----------------------------------------------------------------------------
	//Create link: not supported:
	fs.symlink=function(target, path, type, callback){
		if(type instanceof Function){
			return fs.symlink(target,path,"",type);
		}
		//TODO: Code this: D
		setTimeout(()=>callback("Not supported.",null),0);
	};
	
	//----------------------------------------------------------------------------
	//Limit file size:
	fs.truncate=function(diskPath, len, callback){
		if(len instanceof Function){
			return fs.truncate(diskPath,0,len);
		}
		len=len||0;
		parseDiskPath(diskPath,(disk,diskName,path)=>{
			if(!disk){
				callback("Disk not found: "+diskPath);
				return;
			}
			if(!path){
				callback("Dir name missing: "+diskPath);
				return;
			}
			disk.loadFile(path).then(data=>{
				let buf;
				if(!data){
					callback("File not found: "+diskPath);
					return;
				}
				if(data.length>len){
					buf=Buffer.from(data,0,len);
					disk.saveFile(path,buf).then(()=>{
						callback(null);
					});
				}else if(data.length<len){
					let buf1,buf2;
					buf1=Buffer.from(data,0,len);
					buf2=Buffer.alloc(len-data.length,0);
					buf.Buffer.concat([buf1,buf2]);
					disk.saveFile(path,buf).then(()=>{
						callback(null);
					});
				}else{
					callback(null);
				}
			});
		});
	};
	
	//----------------------------------------------------------------------------
	//unlink path: not supported:
	fs.unlink=function(path, callback){
		//TODO: Code this: D
		setTimeout(()=>callback("Not supported.",null),0);
	};
	
	//----------------------------------------------------------------------------
	//stop watring file: not supported:
	fs.unwatchFile=function(filename, listener){
		//TODO: Code this: C
		throw new Error("Not supported.");
	};
	
	//----------------------------------------------------------------------------
	//update file time:
	fs.utimes=function(diskPath, atime, mtime, callback){
		parseDiskPath(diskPath,(disk,diskName,path)=>{
			if(!disk){
				callback("Disk not found: "+diskPath);
				return;
			}
			if(!path){
				callback("Dir name missing: "+diskPath);
				return;
			}
			if(mtime instanceof Date){
				mtime=mtime.getTime();
			}
			disk.setEntryInfo(path,{modifyTime:mtime}).then(()=>{
				callback(null);
			}).catch(e=>{
				callback(e);
			});
		});
	};
	
	//----------------------------------------------------------------------------
	//Watch file change: not supported:
	fs.watch=function(diskPath, options, listener){
		//TODO: Code this: C
		throw new Error("Not supported.");
	};
	
	//----------------------------------------------------------------------------
	//Watch file change: not supported:
	fs.watchFile=function(filename, options, listener){
		//TODO: Code this: C
		throw new Error("Not supported.");
	};
	
	//----------------------------------------------------------------------------
	//Write data to file descriptor
	fs.write=function(fd, buffer, offset, length, position, callback){
		let handle;
		handle=fdIdxMap.get(fd);
		if(!handle){
			callback("FD is invalid.");
		}else{
			handle.write(buffer,offset,length,position).then(stub=>{
				if(stub){
					callback(null,stub.bytesRead,stub.buffer);
				}else{
					callback("Write failed.");
				}
			}).catch(e=>{
				callback(e);
			});
		}
	};
	
	//----------------------------------------------------------------------------
	//Write(replace) data to file:
	fs.writeFile=function(file, data, options, callback){
		if(options instanceof Function){
			return fs.writeFile(file,data,"utf8",options);
		}
		if(typeof(file)==="string"){
			let diskPath;
			diskPath=file;
			parseDiskPath(diskPath,(disk,diskName,path)=>{
				if(!disk){
					callback("Disk not found: "+diskPath);
					return;
				}
				if(!path){
					callback("Dir name missing: "+diskPath);
					return;
				}
				disk.saveFile(path,data).then(()=>{
					callback(null);
				});
			});
		}else if(file>=0){
			let handle;
			handle=fdIdxMap.get(file);
			if(!handle){
				callback("FD is invalid.");
			}else{
				handle.writeFile(data,options).then(()=>{
					callback(null);
				}).catch(e=>{
					callback(e);
				});
			}
		}
	};
	
	//----------------------------------------------------------------------------
	//Write multi-buffers into file:
	fs.writev=function(fd, buffers, position, callback){
		let handle;
		handle=fdIdxMap.get(fd);
		if(!handle){
			callback("FD is invalid.");
		}else{
			handle.writev(buffers,position).then(stub=>{
				if(stub){
					callback(null,stub.bytesWritten,stub.buffers);
				}else{
					callback("Write failed.");
				}
			}).catch(e=>{
				callback(e);
			});
		}
	};
}

//****************************************************************************
//Sync functions:
//****************************************************************************
{
	//TODO: code this:
}
export default fs;
export {fs,fsPromises};
