import { clear, del, drop, get, JAXDiskStore, keys, set } from './tabos_fsdb.js';
let JAXDeviceDisk=function(JAXDisk,diskName,majorDisk=null,code=""){
	this.name=diskName;
	if(majorDisk){
		majorDisk.subDisk[code]=this;
	}else {
		JAXDisk.diskHash[diskName] = this;
		this.subDisk={};
	}
	this.refCount=1;
	this.inMemory=false;
	this.memDisk=null;
	this.syncAcessPms=null;
};
let jaxDeviceDisk=JAXDeviceDisk.prototype={};

//----------------------------------------------------------------------------
jaxDeviceDisk.syncAccess=function(){
};

//----------------------------------------------------------------------------
jaxDeviceDisk.newDir=async function(dirPath,allowRoot=0,recursive=true){
};

//-----------------------------------------------------------------------
//Delete an entry-item, if path is a dir, also delete the whole dir tree under it.
jaxDeviceDisk.del=async function(path,opts=null){
};

//-----------------------------------------------------------------------
//Save a file, fileObj can be string, File-Object, etc.
jaxDeviceDisk.saveFile=function(path,fileObj,opts=null){
};

//-----------------------------------------------------------------------
//Load file data as ByteArray
jaxDeviceDisk.loadFile=function(path){
};

//-----------------------------------------------------------------------
//Load file data as text
jaxDeviceDisk.loadText=function(path){
};

//-----------------------------------------------------------------------
//Write file, if encode!==null, read as text:
jaxDeviceDisk.writeFile=function(path,obj,encode=null){
};

//-----------------------------------------------------------------------
//Read file, if encode!==null, read as text:
jaxDeviceDisk.readFile=function(path,encode=null){
};

//-----------------------------------------------------------------------
//List sub-item-vo under path, return null if path is a file:
jaxDeviceDisk.getEntries=function(path){
};

//-----------------------------------------------------------------------
//Check if a path is existed:
jaxDeviceDisk.isExist=function(path){
};

//-----------------------------------------------------------------------
//Get item entry(info) by path
jaxDeviceDisk.getEntry=async function(path){
};

//-----------------------------------------------------------------------
//Set item entry-info by path
jaxDeviceDisk.setEntryInfo=async function(path,info){
};

//-----------------------------------------------------------------------
//copy a file or dir, src can from another disk (orgDisk)
jaxDeviceDisk.copyFile=function(path,newPath,overwrite=1,orgDisk=null){
};

//-----------------------------------------------------------------------
//Rename a file/dir
jaxDeviceDisk.rename=function(path,newPath){
};

//-----------------------------------------------------------------------
//Get all items path-name in a flat list:
jaxDeviceDisk.getAllItemPath=async function(){
};

//-----------------------------------------------------------------------
//Load a file's base version:
jaxDeviceDisk.loadFileBase=async function(path,encode=null){
	return 0;
};


