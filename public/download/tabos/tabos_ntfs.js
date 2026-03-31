import tabNT from "./tabos_nt.js";
import Base64 from "./utils/base64.js";

//****************************************************************************
//TabNTDisk
//****************************************************************************
let TabNTDisk,tabNTDisk;
{
	//------------------------------------------------------------------------
	TabNTDisk=function(name,localDisk,ntPath){
		this.name=name;
		this.ntPath=ntPath;
		this.localDisk=localDisk;
		this.dbStore=localDisk.dbStore;
		this.inMemory=false;
		this.memDisk=null;
		this.syncAcessPms=null;
		TabNTDisk.liveDisks[name]=this;
	};
	tabNTDisk=TabNTDisk.prototype={};
	TabNTDisk.liveDisks=null;
	
	//------------------------------------------------------------------------
	tabNTDisk.checkAlive=async function(){
		let res;
		res=await tabNT.makeCall("fileGetEntry",{dir:this.ntPath});
		if(!res || res.code!==200){
			return false;
		}
		return !!res.entry;
	};

	//-----------------------------------------------------------------------
	//Upgrade a disk for sync access:
	tabNTDisk.syncAccess=async function(){
		throw Error("TabNTDisk dosen't support syncAccess");
	};
	
	//-----------------------------------------------------------------------
	tabNTDisk.newDir=async function(dirPath,allowRoot=0,recursive=true){
		let res;
		res=await tabNT.makeCall("fileMakeDir",{dir:this.ntPath,path:dirPath,recursive:recursive});
		if(!res || res.code!==200){
			return false;
		}
		return await this.getEntry(dirPath);
	};
	
	//-----------------------------------------------------------------------
	//Delete an entry-item, if path is a dir, also delete the whole dir tree under it.
	tabNTDisk.del=tabNTDisk.delete=async function(path,opts=null){
		let res;
		res=await tabNT.makeCall("fileMakeDir",{dir:this.ntPath,path:path,recursive:true});
		if(!res || res.code!==200){
			return false;
		}
		return true;
	};
	
	//-----------------------------------------------------------------------
	//Write file, if encode!==null, read as text:
	tabNTDisk.writeFile=async function(path,fileObj,encode=null){
		let byteAry,buf,res;
		async function arrayBuffer(file){
			if(file.arrayBuffer){
				return file.arrayBuffer();
			}
			return new Promise((onDone,onError)=>{
				let reader=new FileReader();
				reader.onload=function(event) {
					let arrayBuffer = event.target.result;
					onDone(arrayBuffer);
				};
				reader.readAsArrayBuffer(file);
			});
		}

		if (typeof (fileObj) === 'string') {
			let encoder = new TextEncoder();
			byteAry = encoder.encode(fileObj);
		}else if (fileObj instanceof File) {
			byteAry=await arrayBuffer(fileObj);
		}else if (fileObj instanceof Uint8Array){
			byteAry = fileObj;
		}else if(fileObj instanceof ArrayBuffer){
			byteAry = new Uint8Array(fileObj);
		}else if(fileObj.name && fileObj.size>=0){//work around: fileObj from page?
			byteAry=await arrayBuffer(fileObj);
		}else if(fileObj.buffer && fileObj.byteLength===fileObj.length && fileObj.length>=0){
			byteAry = fileObj;
		}else if(fileObj.byteLength>=0){
			byteAry = new Uint8Array(fileObj);
		}
		buf=Base64.encode(byteAry);
		res=await tabNT.makeCall("fileUpload",{dir:this.ntPath,path:path,recursive:true,data:buf});
		if(!res || res.code!==200){
			throw Error(`Write NTFile error: ${res.info||"I/O error."}`);
		}
		return true;
	};
	
	//-----------------------------------------------------------------------
	//Load file data as ByteArray
	tabNTDisk.loadFile=async function(path){
		let res,buf;
		res=await tabNT.makeCall("fileDownload",{dir:this.ntPath,path:path});
		if(res.code!==200){
			return null;
		}
		buf=Base64.decode(res.data);
		return buf;
	};
	
	//-----------------------------------------------------------------------
	//Load file data as text
	tabNTDisk.loadText=async function(path,encode){
		let buf;
		buf=await this.loadFile(path);
		if(!buf){
			return null;
		}
		let enc = new TextDecoder("utf-8");
		return enc.decode(buf);
	};
	

	//-----------------------------------------------------------------------
	//Read file, if encode!==null, read as text:
	tabNTDisk.readFile=async function(path,encode=null){
		if(encode) {
			return this.loadText(path);
		}else {
			return this.loadFile(path);
		}
	};
	
	//-----------------------------------------------------------------------
	//List sub-item-vo under path, return null if path is a file:
	tabNTDisk.getEntries=async function(path){
		let res;
		res=await tabNT.makeCall("fileGetEntries",{dir:this.ntPath,path:path});
		if(!res || res.code!==200){
			return null;
		}
		return res.entries;
	};
	
	//-----------------------------------------------------------------------
	//Check if a path is existed:
	tabNTDisk.isExist=async function(path){
		let res;
		res=await tabNT.makeCall("fileGetEntry",{dir:this.ntPath,path:path});
		if(!res || res.code!==200 || (!res.entry)){
			return null;
		}
		return true;
	};
	
	//-----------------------------------------------------------------------
	//Get item entry(info) by path
	tabNTDisk.getEntry=async function(path){
		let res;
		if(!path){
			return {name:this.name,dir:true,disk:true};
		}
		res=await tabNT.makeCall("fileGetEntry",{dir:this.ntPath,path:path});
		if(!res || res.code!==200){
			return null;
		}
		return res.entry;
	};
	
	//-----------------------------------------------------------------------
	//Set item entry-info by path
	tabNTDisk.setEntryInfo=async function(path,info){
		return true;
	};
	
	//-----------------------------------------------------------------------
	//copy a file or dir, src can from another disk (orgDisk)
	tabNTDisk.copyFile=async function(path,newPath,overwrite=1,orgDisk=null){
		let res,self,entry;
		if(!orgDisk || orgDisk===this){
			res=await tabNT.makeCall("fileCopy",{dir:this.ntPath,path:path,newPath:newPath});
			if(!res || res.code!==200){
				return false;
			}
			return true;
		}
		self=this;
		async function copyOneFile(orgPath,newPath){
			let data;
			data=await orgDisk.readFile(orgPath);
			if(data!==null){
				await self.writeFile(newPath);
			}
		}
		async function copyDir(orgPath,newPath){
			let list,entry;
			list=await orgDisk.getEntries();
			if(list){
				for(entry of list){
					if(entry.dir){
						await copyDir(orgPath+"/"+entry.name,newPath+"/"+entry.name);
					}else{
						await copyOneFile(orgPath+"/"+entry.name,newPath+"/"+entry.name);
					}
				}
			}
		}
		entry=orgDisk.getEntry(path);
		if(entry.dir){
			await copyDir(path,newPath);
		}else{
			await copyOneFile(path,newPath);
		}
		return true;
	};
	
	//-----------------------------------------------------------------------
	//Rename a file/dir
	tabNTDisk.rename=async function(path,newPath){
		let res;
		res=await tabNT.makeCall("fileRename",{dir:this.ntPath,path:path,newPath});
		if(!res || res.code!==200){
			return false;
		}
		return true;
	};
	
	//-----------------------------------------------------------------------
	//Get all items path-name in a flat list:
	tabNTDisk.getAllItemPath=async function(){
		let allList,self;
		allList=[];
		self=this;
		async function readDir(path){
			let list,entry,dirList,dir;
			list=await self.getEntries(path);
			dirList=[];
			if(list){
				for(entry of list){
					allList.push(path+"/"+entry.name);
					if(entry.dir){
						dirList.push(path+"/"+entry.name);
					}
				}
			}
			for(dir of dirList){
				await readDir(dir);
			}
		}
		await readDir("");
		return allList;
	};

	//-----------------------------------------------------------------------
	//Load a file's base version:
	tabNTDisk.loadFileBase=async function(path,encode=null){
		return null;//Not support
	};
}
export default TabNTDisk;
export {TabNTDisk};