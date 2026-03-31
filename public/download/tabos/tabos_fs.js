import { clear, del, drop, get, JAXDiskStore, keys, set } from './tabos_fsdb.js';
import TabNTDisk from "./tabos_ntfs.js";

//****************************************************************************
//Utility functions:
//****************************************************************************
let pathLib,digestBytes,divPath,readStream;
{
	pathLib={
		join:function(path1,path2){
			if(path1==="/"){
				return path1+path2;
			}
			if(!path1){
				return path2;
			}
			while(path1.endsWith("/")){
				path1=path1.substring(0,path1.length-1);
			}
			while(path2.startsWith("/")){
				path2=path2.substring(1);
			}
			return path1+"/"+path2
		},
		extname:function(path){
			let pos;
			pos=path.lastIndexOf(".");
			if(pos>=0){
				return path.substring(pos);
			}
			return "";
		}
	};
	
	//------------------------------------------------------------------------
	digestBytes=async function(buf){
		let hex;
		const hashBuffer = await crypto.subtle.digest('SHA-256', buf);       	    	// hash the message
		const hashArray = Array.from(new Uint8Array(hashBuffer));                     			// convert buffer to byte array
		hex= hashArray.map(b => b.toString(16).padStart(2, '0')).join(''); // convert bytes to hex string
		return hex;
	};
	
	//------------------------------------------------------------------------
	divPath=function(dirPath){
		let pos,dirName,upPath;
		//Split dir upper and base:
		if(dirPath.endsWith("/")){
			dirPath=dirPath.substring(0,dirPath.length-1);
		}
		pos=dirPath.lastIndexOf("/");
		if(pos>=0){
			dirName=dirPath.substring(pos+1);
			upPath=dirPath.substring(0,pos);
		}else{
			dirName=dirPath;
			upPath="";
		}
		if(upPath.startsWith("/")){
			upPath=upPath.substring(1);
		}
		return [dirName,upPath];
	}
	
	//------------------------------------------------------------------------
	readStream=async function(stream){
		let chunks=[];
		let done,value,vo,block;
		let reader,totalSize,data,offset;
		reader=stream.getReader();
		totalSize=0;
		do {
			vo = await reader.read();
			done=vo.done;
			value=vo.value;
			if(value){
				chunks.push(value);
				totalSize+=value.length;
			}
		}while(!done);
		data=new Uint8Array(totalSize);
		offset=0;
		for(let i=0,n=chunks.length;i<n;i++){
			block=chunks[i];
			data.set(block,offset);
			offset+=block.length;
		}
		return data;
	};
}

var JAXDisk,jaxDisk;
var JAXMemDisk,jaxMemDisk;
var swClient=null;
let notifyModifyAct;

//****************************************************************************
//JAX's virtual disk system for web
//****************************************************************************
JAXDisk=function(diskName,majorDisk=null,code="")
{
	this.name=diskName;
	
	this.dbStore=new JAXDiskStore(diskName);
	this.writeObj=null;
	this.writeVsn=0;
	if(majorDisk){
		majorDisk.subDisk[code]=this;
	}else {
		JAXDisk.liveDisks[diskName] = this;
		this.subDisk={};
	}
	this.refCount=1;
	this.infoStore=new JAXDiskStore(diskName, "info");
	this.baseStore=new JAXDiskStore(diskName, "base");
	this.inMemory=false;
	this.memDisk=null;
	this.syncAcessPms=null;
};
jaxDisk=JAXDisk.prototype={};

{
	let dlv;
	dlv=localStorage.getItem("TABOS-DISKLIST");
	if(!dlv){
		dlv="1";
		localStorage.setItem("TABOS-DISKLIST",dlv);
	}
	JAXDisk.diskListVsn=dlv;
}

//----------------------------------------------------------------------------
//All available disk:
//JAXDisk.sysStore=new Store('JAXDisk_', "System");
JAXDisk.sysStore=JAXDiskStore.systemStore();
JAXDisk.disks=null;
JAXDisk.liveDisks=TabNTDisk.liveDisks={};


//****************************************************************************
//JAXDisk static-system functions:
//****************************************************************************
{
	//---------------------------------------------------------------------------
	//Init jax-disk system.
	JAXDisk.init=async function(_swClient,refresh=false) {
		let list;
		swClient=_swClient;
		if(JAXDisk.disks && !refresh){
			return;
		}
		list=await get("disks",JAXDisk.sysStore);
		if (Array.isArray(list)) {
			JAXDisk.disks = new Set(list);
		} else {
			JAXDisk.disks = new Set();
			set("disks", [], JAXDisk.sysStore);
		}
	};
	
	//------------------------------------------------------------------------
	JAXDisk.checkDisks=async function(){
		let list,name,disk,disks,liveDisks,needSync,entry;
		
		let deleteDisk=(name)=>{
			console.log("CheckDisk: delete disk: "+name);
			disks.delete(name);
			delete this.liveDisks[name];
			needSync=true;
		}
		
		needSync=false;
		disks=this.disks;
		liveDisks=this.liveDisks;
		for(name of disks){
			try{
				//console.log("CheckDisk: "+name);
				disk=await this.openDisk(name,false);
				if(!disk){
					deleteDisk(name);
				}else{
					entry=await get(".",disk.dbStore)
					if(!entry){
						deleteDisk(name);
					}
				}
			}catch(err){
				deleteDisk(name);
			}
		}
		if(indexedDB.databases){
			let stub,store,rootObj;
			list=await indexedDB.databases();
			for(stub of list){
				//console.log("Check DB: ",stub);
				name=stub.name;
				if(name && name.startsWith("Disk_")){
					name=name.substring("Disk_".length);
					store=new JAXDiskStore(name);
					rootObj=await get(".",store);
					if(rootObj && typeof(rootObj)==="object"){
						//TODO: Add this disk:
						if(!disks.has(name)){
							needSync=true;
							disks.add(name);
							console.log("CheckDisk: resotre disk: "+name);
						}
					}
				}
			}
		}
		if(needSync){
			await set('disks', Array.from(disks), this.sysStore);
		}
		console.log("Check disk: done.");
	};
	
	//------------------------------------------------------------------------
	JAXDisk.syncDiskSet=async function(){
		let list,name,diskSet,liveDisks;
		list=await get("disks", JAXDisk.sysStore);
		if(!Array.isArray(list)){
			//Disk list lost...
			return;
		}
		diskSet=JAXDisk.disks=new Set(list);
		liveDisks=JAXDisk.liveDisks;
		for(name in liveDisks){
			if(!diskSet.has(name)){
				delete liveDisks[name];
			}
		}
	};
	
	//------------------------------------------------------------------------
	JAXDisk.checkDiskIdx=async function(){
		let dlv;
		dlv=localStorage.getItem("TABOS-DISKLIST");
		if(dlv){
			if(dlv===JAXDisk.diskListVsn){
				return;
			}
			await JAXDisk.syncDiskSet();
			JAXDisk.diskListVsn=dlv;
		}else{
			//Something wrong... big.
		}
	};
	
	//------------------------------------------------------------------------
	JAXDisk.incDiskIdx=function(){
		let dlv;
		dlv=parseInt(JAXDisk.diskListVsn)||1;
		dlv=""+(dlv+1);
		localStorage.setItem("TABOS-DISKLIST",dlv);
	};
	
	//------------------------------------------------------------------------
	//Open an disk, may create new disk if param create is true:
	JAXDisk.openDisk = async function (diskName, create) {
		let disk,dlv;
		async function checkAlive(disk){
			let alive,ntPath;
			//Check disk alive
			alive=await disk.checkAlive();
			if(alive){
				let infoStore=disk.infoStore;
				if(!infoStore){
					disk.infoStore=infoStore=new JAXDiskStore(diskName, "info");
				}
				ntPath=await get("attr_ntPath",infoStore);
				if(ntPath){
					return new TabNTDisk(diskName,disk,ntPath);
				}
			}
			return alive?disk:null;
		}
		if(!JAXDisk.disks) {
			await JAXDisk.init();
		}else{
			await JAXDisk.checkDiskIdx();
		}
		disk = JAXDisk.liveDisks[diskName];
		if (disk) {
			//Check if the disk is still there:
			return await checkAlive(disk);
		}
		if (JAXDisk.disks.has(diskName)) {
			disk=new JAXDisk(diskName);
			return await checkAlive(disk);
		}//else:
		if(create) {
			disk=await JAXDisk.newDisk(diskName);
			return await checkAlive(disk);
		}
		return null;
	};
	
	//---------------------------------------------------------------------------
	//Check if a disk is exist:
	JAXDisk.isDiskExist = async function (diskName) {
		if(!JAXDisk.disks) {
			await JAXDisk.init();
		}else{
			await JAXDisk.checkDiskIdx();
		}
		if(JAXDisk.disks.has(diskName)){
			return true;
		}
		return false;
	};

	//---------------------------------------------------------------------------
	//Check if a disk is exist:
	JAXDisk.diskExist = function (diskName,doubleCheck=0) {
		return JAXDisk.disks.has(diskName);
	};
	
	//---------------------------------------------------------------------------
	//Create a new disk:
	JAXDisk.newDisk = async function (diskName) {
		let self=this,diskObj,store,rootObj;
		if(diskName.indexOf("/")>=0 || diskName.indexOf("*")>=0){
			throw new Error("New disk: illegal name.");
		}
		await JAXDisk.checkDiskIdx();
		if (JAXDisk.disks.has(diskName)) {
			diskObj=await JAXDisk.openDisk(diskName,0)
			if(diskObj){
				return diskObj;
			}
		}
		JAXDisk.disks.add(diskName);
		await set('disks', Array.from(self.disks), self.sysStore);
		store=new JAXDiskStore(diskName);
		rootObj=await get(".",store);
		if(!rootObj || typeof(rootObj)!=="object"){
			await set(".",{},store);
		}
		diskObj=new JAXDisk(diskName);
		//Update DiksList
		JAXDisk.incDiskIdx();
		return diskObj;
	};

	//---------------------------------------------------------------------------
	//Create a new NT-disk:
	JAXDisk.newNTDisk = async function (diskName,ntPath) {
		let self=this,localDisk,diskObj,store,rootObj,infoStore;
		if(diskName.indexOf("/")>=0 || diskName.indexOf("*")>=0){
			throw new Error("New disk: illegal name.");
		}
		await JAXDisk.checkDiskIdx();
		if (JAXDisk.disks.has(diskName)) {
			diskObj=await JAXDisk.openDisk(diskName,0)
			if(diskObj){
				return diskObj;
			}
		}
		JAXDisk.disks.add(diskName);
		await set('disks', Array.from(self.disks), self.sysStore);
		store=new JAXDiskStore(diskName);
		rootObj=await get(".",store);
		if(!rootObj || typeof(rootObj)!=="object"){
			await set(".",{},store);
		}
		localDisk=new JAXDisk(diskName);
		infoStore=localDisk.infoStore;
		if(!infoStore){
			localDisk.infoStore=infoStore=new JAXDiskStore(diskName, "info");
		}
		await set("attr_ntPath",ntPath,infoStore);
		
		diskObj=new TabNTDisk(diskName,localDisk,ntPath);
		//Update DiksList
		JAXDisk.incDiskIdx();
		return diskObj;
	};
	
	//---------------------------------------------------------------------------
	//Get a disk's info VO:
	JAXDisk.getDiskInfo=async function(diskName){
		let disk,infoStore,info;
		if(!this.disks) {
			await this.init();
		}
		disk=await this.openDisk(diskName,false);
		if(!disk){
			return null;
		}
		infoStore=disk.infoStore;
		if(!infoStore){
			disk.infoStore=infoStore=new JAXDiskStore(diskName, "info");
		}
		return await get("info",infoStore);
	};
	
	//---------------------------------------------------------------------------
	//Set a disk's info VO:
	JAXDisk.setDiskInfo=async function(diskName,info){
		let disk,infoStore,pms;
		if(!this.disks) {
			await this.init();
		}
		disk=await this.openDisk(diskName);
		if(!disk){
			return null;
		}
		infoStore=disk.infoStore;
		if(!infoStore){
			//disk.infoStore=infoStore=new Store('JAXDiskInfo_'+diskName, diskName,1);
			disk.infoStore=infoStore=new JAXDiskStore(diskName, "info");
			await set("info",info,infoStore);
			return;
		}
		if(disk.writeObj){
			await disk.writeObj;
		}
		pms=set("info",info,infoStore);
		disk.writeObj=pms;
		pms.writeVsn=disk.writeVsn++;
		return pms;
	};
	
	//---------------------------------------------------------------------------
	//Get a disk's info VO:
	JAXDisk.getDiskAttr=async function(diskName,attr){
		let disk,infoStore,info;
		if(!this.disks) {
			await this.init();
		}
		disk=await this.openDisk(diskName,false);
		if(!disk){
			return null;
		}
		infoStore=disk.infoStore;
		if(!infoStore){
			disk.infoStore=infoStore=new JAXDiskStore(diskName, "info");
		}
		return await get("attr_"+attr,infoStore);
	};
	
	//---------------------------------------------------------------------------
	//Set a disk's attr:
	JAXDisk.setDiskAttr=async function(diskName,key,val){
		let disk,infoStore,pms;
		if(!this.disks) {
			await this.init();
		}
		disk=await this.openDisk(diskName);
		if(!disk){
			return null;
		}
		infoStore=disk.infoStore;
		if(!infoStore){
			disk.infoStore=infoStore=new JAXDiskStore(diskName, "info");
			await set("attr_"+key,val,infoStore);
			return;
		}
		if(disk.writeObj){
			await disk.writeObj;
		}
		pms=set("attr_"+key,val,infoStore);
		disk.writeObj=pms;
		pms.writeVsn=disk.writeVsn++;
		return pms;
	};
	
	//---------------------------------------------------------------------------
	//Remove a disk, clear the DB(but not drop the db)
	JAXDisk.dropDisk = async function (diskName,dropDB=false) {
		let self,diskObj;
		self=this;
		diskObj=await JAXDisk.openDisk(diskName,false);
		if(diskObj){
			try {
				if (diskObj.dbStore) {
					await clear(diskObj.dbStore);
					if (diskObj.infoStore) {
						await clear(diskObj.infoStore);
					}
					if (diskObj.baseStore) {
						await clear(diskObj.baseStore);
					}
				}
			}catch(err){
				console.log(`Drop disk ${diskName} error: ${err}`);
				return false;
			}
		}else{
			JAXDisk.disks.delete(diskName);
			delete JAXDisk.liveDisks[diskName];
			await set('disks', Array.from(JAXDisk.disks), JAXDisk.sysStore);
			JAXDisk.incDiskIdx();
			return false;
		}
		JAXDisk.disks.delete(diskName);
		delete JAXDisk.liveDisks[diskName];
		await set('disks', Array.from(JAXDisk.disks), JAXDisk.sysStore);
		if(dropDB){
			drop(diskObj.dbStore.dbName);
		}
		JAXDisk.incDiskIdx();
		return true;
	};
	
	//---------------------------------------------------------------------------
	//Get current disks list:
	JAXDisk.getDisks=function(sync=false){
		if(sync){
			JAXDisk.checkDiskIdx();
		}
		return Array.from(this.disks);
	};
	
	//---------------------------------------------------------------------------
	//Get current disk names
	JAXDisk.getDiskNames=async function(sync=false){
		let list,i,n,name,disk;
		if(!JAXDisk.disks) {
			await JAXDisk.init();
		}
		await JAXDisk.checkDiskIdx();
		list=Array.from((this.disks));
		return list;
	};
	
	//---------------------------------------------------------------------------
	//Make a disk in-memory so can sync accessed
	JAXDisk.syncDisk=async function(diskName,create=false){
		let disk;
		disk=await JAXDisk.openDisk(diskName,create);
		if(!disk)
			return false;
		if(disk.memDisk){
			await disk.syncAcessPms;
			return true;
		}
		return await disk.syncAccess();
	};
	
	//---------------------------------------------------------------------------
	//Get package path's real path:
	JAXDisk.getPkgPath=async function(pkgPath){
		let pkgName,path,pos,pkgJSON,pkgRoot;
		if(!pkgPath.startsWith("/@")){
			throw new Error(`${pkgPath} is not a packages path (starts with "/@").`);
		}
		pos=pkgPath.indexOf("/",2);
		if(pos>0){
			pkgName=pkgPath.substring(2,pos);
			path=pkgPath.substring(pos+1);
		}else{
			pkgName=pkgPath.substring(2);
			path="";
		}
		try {
			pkgJSON = await JAXDisk.readFile(`/coke/lib/${pkgName}.json`, "utf8");
			pkgJSON=JSON.parse(pkgJSON);
			pkgRoot=pkgJSON.path;
			if(!path){
				return pkgRoot;
			}
			return pathLib.join(pkgRoot,path);
		}catch(err){
			throw new Error(`${pkgName} is not a installed pkg`);
		}
	};
	
	//-----------------------------------------------------------------------
	//Get package's main entry absolute-path:
	JAXDisk.getPkgMain=async function(pkgName){
		try {
			let pkgJSON;
			pkgJSON = await JAXDisk.readFile(`/coke/lib/${pkgName}.json`, "utf8");
			pkgJSON=JSON.parse(pkgJSON);
			return pkgJSON.main;
		}catch(err){
			throw new Error(`${pkgName} is not a installed pkg`);
		}
	}
}

//****************************************************************************
//JAXDisk member functions
//****************************************************************************
{
	//------------------------------------------------------------------------
	jaxDisk.checkAlive=async function(){
		let fileObj;
		try{
			fileObj=await get(".",this.dbStore);
			if(fileObj&&typeof(fileObj)==="object"){
				return true;
			}
			return false;
		}catch(err){
			return false;
		}
	};
	
	//-----------------------------------------------------------------------
	//Upgrade a disk for sync access:
	jaxDisk.syncAccess=async function(){
		let memDisk;
		if(this.memDisk) {
			await this.syncAcessPms;
			return true;
		}
		memDisk=new JAXMemDisk(this);
		this.memDisk=memDisk;
		this.syncAcessPms=memDisk.init();
		await this.syncAcessPms;
		return true;
	};
	
	jaxDisk.newDir=async function(dirPath,allowRoot=0,recursive=true){
		var self=this;
		let writeVsn,actorId;
		if(typeof(allowRoot)==="object"){
			let opts=allowRoot;
			allowRoot=opts.allowRoot||false;
			recursive=opts.recursive!==undefined?opts.recursive:true;
			actorId=opts.actor||null;
		}else{
			actorId=null;
		}
		if(dirPath==='.'){
			if(!allowRoot) {
				throw "Error: '.' is not allowed for folder name.";
			}
		}
		
		if(dirPath.endsWith("/")){
			dirPath=dirPath.substring(0,dirPath.length-1);
		}
		if(dirPath.startsWith("/")){
			dirPath=dirPath.substring(1);
		}
		
		async function mkDirList(list){
			let i,n,stub;
			n=list.length;
			for(i=0;i<n;i++) {
				stub=list[i];
				await set(stub.path, stub.obj,self.dbStore);
			}
			return list[0];
		}
		
		async function doNewDir() {
			let waitPath;
			if(self.writeObj && self.writeObj.writeVsn!==writeVsn){
				await self.writeObj;
			}
			
			return get(dirPath, self.dbStore).then(async curDirObj => {
				let upPath, pos, dirName;
				let dirList;
				let time = Date.now();
				
				dirList=[];
				
				//Check if path is already there and if it's dir?
				if (curDirObj instanceof Uint8Array) {
					throw "Can't create dir on file!";
				} else if (typeof (curDirObj) === 'object') {
					return curDirObj;
				}
				
				//Path is empty, create dir:
				dirList.push({path:dirPath,obj:{}});
				[dirName, upPath] = divPath(dirPath);
				if(!upPath){
					upPath=".";
				}
				while(upPath){
					let dirObj;
					dirObj=await get(upPath, self.dbStore);
					if(!dirObj){
						if(!recursive){
							return null;
						}
						dirObj={};
						dirObj[dirName]={
							name: dirName, dir: 1, createTime: time, modifyTime: time,
						};
						dirList.push({path:upPath,obj:dirObj});
					}else{
						dirObj[dirName]={
							name: dirName, dir: 1, createTime: time, modifyTime: time,
						};
						dirList.push({path:upPath,obj:dirObj});
						break;
					}
					if(upPath==="."){
						throw "newDir: Bad disk structure!";
					}
					[dirName, upPath] = divPath(upPath);
					if(!upPath){
						upPath=".";
					}
				}
				await mkDirList(dirList);
				//Call cross-tab notify:
				notifyModifyAct("NewDir","/"+self.name+"/"+dirPath,actorId);
				return dirList[0].obj;
			})
		}
		//Sync write operation:
		writeVsn=this.writeVsn++;
		self.writeObj=doNewDir();
		self.writeObj.writeVsn=writeVsn;
		self.writeObj.path=dirPath;
		return self.writeObj;
	};
	
	//-----------------------------------------------------------------------
	//Delete an entry-item, if path is a dir, also delete the whole dir tree under it.
	jaxDisk.del=jaxDisk.delete=async function(path,opts=null){
		let self=this;
		let writeVsn,actorId,delPath;
		
		if(opts){
			actorId=opts.actor||null;
		}
		
		//console.log("Disk.del: "+path);
		if(path.endsWith("/")){
			path=path.substring(0,path.length-1);
		}
		if(path.startsWith("/")){
			path=path.substring(1);
		}
		if(path.startsWith("./")){
			path=path.substring(2);
		}
		delPath=path;
		
		//-------------------------------------------------------------------
		//Delete file/dir item array(list)
		async function doDelList(list){
			let i,n,item,pList;
			n=list.length;
			pList=[];
			for(i=0;i<n;i++){
				item=list[i];
				pList.push(del(item,self.dbStore));//Delete one item
			}
			return Promise.allSettled(pList);
		}
		
		//-------------------------------------------------------------------
		//List an dir's all sub-tree items including sub in sub
		async function doMakeList(tgtPath,tgtList){
			let list,i,n,stub;
			tgtList.push(tgtPath);
			list=await self.getEntries(tgtPath);
			n=list.length;
			for(i=0;i<n;i++){
				stub=list[i];
				if(stub.dir){
					await doMakeList((tgtPath?(tgtPath+"/"+stub.name):stub.name),tgtList);
				}else{
					tgtList.push((tgtPath?(tgtPath+"/"+stub.name):stub.name));
				}
			}
		}
		
		//-------------------------------------------------------------------
		//Erase item's entry in upper dir record:
		async function doDelEntry(tgtPath){
			let tgtName,upPath;
			[tgtName,upPath]=divPath(tgtPath);
			if(!upPath){
				upPath=".";
			}
			return get(upPath,self.dbStore).then((upDirObj)=>{
				if(upDirObj){
					delete upDirObj[tgtName];
					return set(upPath,upDirObj,self.dbStore);
				}
			});
		}
		
		//-------------------------------------------------------------------
		//Check delete item type, exec the del operation:
		async function checkAndDel(){
			let waitPath;
			if(self.writeObj && self.writeObj.writeVsn!==writeVsn){
				waitPath=self.writeObj.path;
				await self.writeObj;
			}
			
			return get(path,self.dbStore).then(async (delObj)=> {
				let delList;
				
				//Do the delete:
				delList=[];
				if(delObj instanceof Uint8Array) {
					//File, nothing more.
					delList.push(path);
					return doDelList(delList).then(()=>{
						return doDelEntry(path);
					});
				}else if(delObj){
					//Dir, generate the sub-item list to delete
					await doMakeList(path,delList);
					return doDelList(delList).then(()=>{
						return doDelEntry(path);
					});
				}else{
					return doDelEntry(path);
				}
			}).then(()=>{
				notifyModifyAct("Del","/"+self.name+"/"+delPath,actorId);
			});
		}
		writeVsn=this.writeVsn++;
		self.writeObj=checkAndDel();
		self.writeObj.writeVsn=writeVsn;
		self.writeObj.path=path;
		//console.log("Set wait obj: "+path);
		return self.writeObj;
	};
	
	//-----------------------------------------------------------------------
	//Save a file, fileObj can be string, File-Object, etc.
	jaxDisk.saveFile=function(path,fileObj,opts=null){
		let self,tgtName,upPath,byteAry,time,writeVsn,byteHex;
		let actorId,filepath,recursive=true;
		self=this;
		
		if(opts){
			actorId=opts.actor||null;
			recursive=opts.recursive!==undefined?opts.recursive:true;
		}
		
		//console.log("JAXDisk.saveFile: Disk.saveFile: "+path);
		if(path.endsWith("/")){
			throw "JAXDisk.saveFile: Error: filename can't end with '/'!";
		}
		if(path.startsWith("/")){
			path=path.substring(1);
		}
		filepath=path;
		
		[tgtName,upPath]=divPath(path);
		time=Date.now();
		
		//Save byte content to DB, update entry info, make base backup if needed:
		async function saveByteAry(){
			let dirVO,stub,oldData,oldHash;
			//console.log("saveByteAry: "+path+", writeObj: "+(self.writeObj?self.writeObj.filePath:"null"));
			//wait for current update file:
			if(self.writeObj && self.writeObj.writeVsn!==writeVsn){
				await self.writeObj;
			}
			//get upper dirVO:
			dirVO=await get(upPath?upPath:".",self.dbStore);
			if(!dirVO){
				throw "Path is not available: "+upPath;
			}
			stub=dirVO[tgtName];
			if(stub){
				//file exists, update stub, save base if 1st :
				oldHash=stub.hash;
				stub.modifyTime=time;
				if(!stub.modified && (oldHash!==byteHex || stub.size!==byteAry.byteLength)) {
					oldData=await get(upPath ? (upPath + "/" + tgtName) : tgtName, self.dbStore);
					//save the base file content:
					if(oldData) {
						set(upPath ? (upPath + "/" + tgtName) : tgtName, oldData, self.baseStore);
					}
					stub.modified=true;
				}
				stub.size=byteAry.byteLength;
				stub.hash=byteHex;
				//update stub:
			}else{
				//new file, create stub:
				dirVO[tgtName]={
					name:tgtName,dir:0,createTime:time,modifyTime:time,size:byteAry.byteLength,modified:true,
					hash:byteHex
				};
			}
			await set(upPath?(upPath+"/"+tgtName):tgtName,byteAry,self.dbStore);
			await set(upPath?upPath:".",dirVO,self.dbStore);
			//Call cross-tab notify:
			notifyModifyAct("File","/"+self.name+"/"+filepath,actorId);
		}
		
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
			})
		}
		
		function doCopy(){
			//Ensure saved object is ByteArray
			if (typeof (fileObj) === 'string') {
				let encoder = new TextEncoder();
				byteAry = encoder.encode(fileObj);
				return digestBytes(byteAry).then(hex=>{
					writeVsn = self.writeVsn++;
					byteHex=hex;
					self.writeObj =saveByteAry();
					self.writeObj.filePath = path;
					self.writeObj.writeVsn = writeVsn;
					return self.writeObj;
				});
			} else if (fileObj instanceof File) {
				return arrayBuffer(fileObj).then(async buf => {
					byteAry = new Uint8Array(buf);
					return digestBytes(byteAry).then(hex=>{
						writeVsn = self.writeVsn++;
						byteHex=hex;
						self.writeObj =saveByteAry();
						self.writeObj.filePath = path;
						self.writeObj.writeVsn = writeVsn;
						return self.writeObj;
					});
				});
			} else if (fileObj instanceof Uint8Array) {
				byteAry = fileObj;
				return digestBytes(byteAry).then(hex=>{
					writeVsn = self.writeVsn++;
					byteHex=hex;
					self.writeObj =saveByteAry();
					self.writeObj.filePath = path;
					self.writeObj.writeVsn = writeVsn;
					return self.writeObj;
				});
			}else if(fileObj instanceof ArrayBuffer){
				byteAry = new Uint8Array(fileObj);
				return digestBytes(byteAry).then(hex=>{
					writeVsn = self.writeVsn++;
					byteHex=hex;
					self.writeObj =saveByteAry();
					self.writeObj.filePath = path;
					self.writeObj.writeVsn = writeVsn;
					return self.writeObj;
				});
			}else if(fileObj.name && fileObj.size>=0){//work around: fileObj from page?
				return arrayBuffer(fileObj).then(async buf => {
					byteAry = new Uint8Array(buf);
					return digestBytes(byteAry).then(hex=>{
						writeVsn = self.writeVsn++;
						byteHex=hex;
						self.writeObj =saveByteAry();
						self.writeObj.filePath = path;
						self.writeObj.writeVsn = writeVsn;
						return self.writeObj;
					});
				});
			}else if(fileObj.buffer && fileObj.byteLength===fileObj.length && fileObj.length>=0){
				//work around of Uint8Array:
				byteAry = fileObj;
				return digestBytes(byteAry).then(hex=>{
					writeVsn = self.writeVsn++;
					byteHex=hex;
					self.writeObj =saveByteAry();
					self.writeObj.filePath = path;
					self.writeObj.writeVsn = writeVsn;
					return self.writeObj;
				});
			}else if(fileObj.byteLength>=0){
				byteAry = new Uint8Array(fileObj);
				return digestBytes(byteAry).then(hex=>{
					writeVsn = self.writeVsn++;
					byteHex=hex;
					self.writeObj =saveByteAry();
					self.writeObj.filePath = path;
					self.writeObj.writeVsn = writeVsn;
					return self.writeObj;
				});
			}
		}
		
		if(upPath){
			return get(upPath,self.dbStore).then(pathObj=>{
				//Ensure the target dir is there:
				if(pathObj) {
					if (pathObj instanceof Uint8Array) {
						//upPath is a file, can't go on:
						throw Error(`${upPath} is a file, can't write new file ${path} under it.`);
					}
					return doCopy();
				}else if(recursive){
					return self.newDir(upPath).then(()=>{
						return doCopy();
					});
				}
			});
		}else{
			return doCopy();
		}
	};
	
	//-----------------------------------------------------------------------
	//Load file data as ByteArray
	jaxDisk.loadFile=function(path){
		var self;
		self=this;
		if(path.startsWith("/")){
			path=path.substring(1);
		}
		return get(path,self.dbStore).then(fileObj=>{
			if(fileObj instanceof Uint8Array){
				return fileObj;
			}
			return null;
		});
	};
	
	//-----------------------------------------------------------------------
	//Load file data as text
	jaxDisk.loadText=function(path){
		var self;
		self=this;
		if(path.startsWith("/")){
			path=path.substring(1);
		}
		return get(path,self.dbStore).then(fileObj=>{
			if(fileObj instanceof Uint8Array){
				let enc = new TextDecoder("utf-8");
				return enc.decode(fileObj);
			}
			return null;
		}).catch(err=>{
			return null;
		});
	};
	
	//-----------------------------------------------------------------------
	//Write file, if encode!==null, read as text:
	jaxDisk.writeFile=function(path,obj,encode=null){
		let opts;
		if(!path){
			throw Error("jaxDisk.writeFile: Missing filename.");
		}
		if(path.startsWith("./")){
			path=path.substring(2);
		}
		if(encode && typeof(encode)==="object"){
			opts=encode;
			encode=opts.encode||null;
		}else{
			opts=null;
		}
		if(encode) {
			obj=""+obj;//Lazy convert
		}
		return this.saveFile(path,obj,opts);
	};
	
	//-----------------------------------------------------------------------
	//Read file, if encode!==null, read as text:
	jaxDisk.readFile=function(path,encode=null){
		if(encode) {
			return this.loadText(path);
		}else {
			return this.loadFile(path);
		}
	};
	
	//-----------------------------------------------------------------------
	//List sub-item-vo under path, return null if path is a file:
	jaxDisk.getEntries=function(path){
		var self;
		self=this;
		if(path.startsWith("/")){
			path=path.substring(1);
		}
		if(!path){
			path='.';
		}
		return get(path,self.dbStore).then(fileObj=>{
			if(fileObj instanceof Uint8Array || !fileObj){
				return null;//this is file, not dir
			}
			return Object.values(fileObj);
		});
	};
	
	//-----------------------------------------------------------------------
	//Check if a path is existed:
	jaxDisk.isExist=function(path){
		var self=this;
		if(path.startsWith("/")){
			path=path.substring(1);
		}
		if(!path){
			path='.';
		}
		return get(path,self.dbStore).then(fileObj=>{
			return !!fileObj;
		});
	};
	
	//-----------------------------------------------------------------------
	//Get item entry(info) by path
	jaxDisk.getEntry=async function(path){
		let self=this;
		let dir,fileName;
		[fileName,dir]=divPath(path);
		if(dir.startsWith("/")){
			dir=dir.substring(1);
		}
		if(dir.endsWith("/")){
			dir=dir.substring(0,dir.length-1);
		}
		if(!dir){
			dir='.';
			if(fileName===""){
				let info=await JAXDisk.getDiskAttr(self.name,"FSEntryInfo");
				return {...info,name:self.name,dir:1,disk:1};
			}
		}
		let dirObj=await get(dir,self.dbStore);
		if(dirObj) {
			let entry=dirObj[fileName];
			if(entry instanceof Object){
				return entry;
			}
			return null;
		}
		return null;
	};
	
	//-----------------------------------------------------------------------
	//Set item entry-info by path
	jaxDisk.setEntryInfo=async function(path,info){
		let self=this;
		let entry,pms;
		delete info.name;
		delete info.dir;
		delete info.disk;
		entry=await this.getEntry(path);
		if(entry && typeof(entry)==="object"){
			let dir,fileName,writeVersion;
			if(entry.disk){
				let orgInfo=await JAXDisk.getDiskAttr(self.name,"FSEntryInfo");
				info={...orgInfo,...info};
				await JAXDisk.setDiskAttr(self.name,"FSEntryInfo",info);
			}else{
				[fileName,dir]=divPath(path);
				if(dir.startsWith("/")){
					dir=dir.substring(1);
				}
				if(!dir){
					dir='.';
				}
				if(self.writeObj){
					await self.writeObj;
				}
				entry=await this.getEntry(path);
				if(entry){
					Object.assign(entry,info);
					writeVersion=self.writeVsn++;
					self.writeObj=pms=get(dir,self.dbStore).then((dirInfo)=>{
						dirInfo[fileName]=entry;
						return set(dir,dirInfo,self.dbStore);
					});
					pms.writeVsn=writeVersion;
				}
				return pms;
			}
		}
	};
	
	//-----------------------------------------------------------------------
	//copy a file or dir, src can from another disk (orgDisk)
	jaxDisk.copyFile=function(path,newPath,overwrite=1,orgDisk=null){
		var self=this;
		var dirList,fileList;
		orgDisk=orgDisk||this;
		if(path.startsWith("/")){
			path=path.substring(1);
		}
		if(path.endsWith("/")){
			path=path.substring(0,path.length-1);
		}
		if(!path){
			path='.';
		}
		
		if(newPath.startsWith("/")){
			newPath=newPath.substring(1);
		}
		if(newPath.endsWith("/")){
			newPath=newPath.substring(0,newPath.length-1);
		}
		if(!newPath){
			newPath='.';
		}
		
		dirList=[];
		fileList=[];
		
		async function checkInItem(itemPath,tgtPath) {
			var itemObj,subPath,subTgtPath,curItem;
			itemObj=await get(itemPath,orgDisk.dbStore);
			if(itemObj instanceof Uint8Array){
				curItem=await get(tgtPath,self.dbStore);//Is target there?
				if(curItem) {
					if(overwrite && curItem instanceof Uint8Array) {//Can't overwrite a dir with file!
						fileList.push({org: itemPath, tgt: tgtPath});
					}
				}else{
					fileList.push({org: itemPath, tgt: tgtPath});
				}
			}else if(typeof(itemObj)==="object"){
				var stub,itemName,name;
				dirList.push({org:itemPath,tgt:tgtPath});
				for(itemName in itemObj){
					name=itemName;
					stub=itemObj[name];
					subPath=itemPath?(itemPath+"/"+stub.name):stub.name;
					subTgtPath=tgtPath?(tgtPath+"/"+stub.name):stub.name;
					await checkInItem(subPath,subTgtPath);
				}
			}
		}
		
		async function copyOneFile(stub){
			let fileData,info;
			fileData=await orgDisk.loadFile(stub.org);
			await self.writeFile(stub.tgt,fileData);
			info=await orgDisk.getEntry(stub.org);
			if(info){
				await self.setEntryInfo(stub.tgt,{modifyTime:info.modifyTime});
			}
			/*
			return orgDisk.loadFile(stub.org).then(fileData=>{
				return self.writeFile(stub.tgt,fileData);
			});*/
		}
		
		return get(path,orgDisk.dbStore).then(async fileObj=>{
			let i,n,pList;
			if(!fileObj){
				throw "Missing copy source: "+path;
			}
			await checkInItem(path,newPath);
			pList=[];
			n=dirList.length;
			for(i=0;i<n;i++){
				pList.push(self.newDir(dirList[i].tgt));
			}
			return Promise.allSettled(pList).then(async ()=>{
				let pList=[],p,stub;
				n=fileList.length;
				for(i=0;i<n;i++){
					stub=fileList[i];
					p=copyOneFile(stub);
					pList.push(p);
				}
				return Promise.allSettled(pList).then(()=>{
					return dirList.map((item)=>{
						return item.tgt;
					}).concat(fileList.map(item=>{
						return item.tgt;
					}));
				});
			});
		});
	};
	
	//-----------------------------------------------------------------------
	//Rename a file/dir
	jaxDisk.rename=function(path,newPath){
		var self=this;
		let orgName,orgPath,tgtName,tgtPath;
		
		if(path.startsWith("/")){
			path=path.substring(1);
		}
		if(path.endsWith("/")){
			path=path.substring(0,path.length-1);
		}
		if(!path){
			path='.';
		}
		[orgName, orgPath] = divPath(path);
		
		if(newPath.startsWith("/")){
			newPath=newPath.substring(1);
		}
		if(newPath.endsWith("/")){
			newPath=newPath.substring(0,newPath.length-1);
		}
		if(!newPath){
			newPath='.';
		}
		[tgtName, tgtPath] = divPath(newPath);
		
		if(tgtPath!==orgPath){
			throw "Path error."
		}
		if(orgName===tgtName){//Same name:
			return (async function(){return true})();
		}
		
		return self.copyFile(path,newPath).then(()=>{
			return self.del(path);
		});
	};
	
	//-----------------------------------------------------------------------
	//Get all items path-name in a flat list:
	jaxDisk.getAllItemPath=async function(){
		return await keys(this.dbStore);
	};
	
	//-----------------------------------------------------------------------
	//Load a file's base version:
	jaxDisk.loadFileBase=async function(path,encode=null){
		let self,fileObj;
		self=this;
		if(path.startsWith("/")){
			path=path.substring(1);
		}
		if(!self.baseStore){
			return null;
		}
		fileObj=await get(path,self.baseStore);
		if(fileObj instanceof Uint8Array){
			if(encode) {
				let enc = new TextDecoder("utf-8");
				return enc.decode(fileObj);
			}else{
				return fileObj;
			}
		}
		return null;
	};
}

//****************************************************************************
//JAXDisk functions based on jaxDisk
//****************************************************************************
{
	//------------------------------------------------------------------------
	JAXDisk.cwd=function(){
		return JAXDisk.appPath;
	};
	
	//------------------------------------------------------------------------
	JAXDisk.chdir=JAXDisk.setPath=function(path){
		if(path[0]!=='/'){
			path=pathLib.join(JAXDisk.appPath,path);
			if(path[0]!=='/') {
				throw Error('Full path must starts with "/"');
			}
		}
		JAXDisk.appPath=path;
	};
	
	//-----------------------------------------------------------------------
	JAXDisk.parsePath=function (fullPath){
		let pos,diskName,diskPath;
		if(fullPath[0]!=='/'){
			fullPath=pathLib.join(JAXDisk.appPath,fullPath);
			if(fullPath[0]!=='/') {
				throw Error('Full path must starts with "/"');
			}
		}
		pos=fullPath.indexOf("/",1);
		if(pos<0){
			diskName=fullPath.substring(1);
			diskPath="";
		}else{
			diskName=fullPath.substring(1,pos);
			diskPath=fullPath.substring(pos+1);
		}
		return [diskName,diskPath];
	};

	//-----------------------------------------------------------------------
	//Get disk and path-on-disk:
	let parseDiskPath=JAXDisk.parseDiskPath=async function (fullPath){
		let pos,diskName,diskPath,disk;
		if(fullPath[0]!=='/'){
			fullPath=pathLib.join(JAXDisk.appPath,fullPath);
			if(fullPath[0]!=='/') {
				throw Error('Full path must starts with "/"');
			}
		}
		pos=fullPath.indexOf("/",1);
		if(pos<0){
			diskName=fullPath.substring(1);
			diskPath="";
		}else{
			diskName=fullPath.substring(1,pos);
			diskPath=fullPath.substring(pos+1);
		}
		disk=await JAXDisk.openDisk(diskName,false);
		return [disk,diskPath,diskName];
	};
	
	//-----------------------------------------------------------------------
	//Get disk and path-on-disk:
	let parseDiskPathSync=JAXDisk.parseDiskPath=function (fullPath){
		let pos,diskName,diskPath,disk;
		if(fullPath[0]!=='/'){
			fullPath=pathLib.join(JAXDisk.appPath,fullPath);
			if(fullPath[0]!=='/') {
				throw Error('Full path must starts with "/"');
			}
		}
		pos=fullPath.indexOf("/",1);
		if(pos<0){
			diskName=fullPath.substring(1);
			diskPath="";
		}else{
			diskName=fullPath.substring(1,pos);
			diskPath=fullPath.substring(pos+1);
		}
		disk=JAXDisk.liveDisks[diskName];
		return [disk,diskPath,diskName];
	};
	
	//-----------------------------------------------------------------------
	JAXDisk.getPathDiskName=function(fullPath){
		let pos,diskName;
		if(fullPath[0]!=='/'){
			fullPath=pathLib.join(JAXDisk.appPath,fullPath);
			if(fullPath[0]!=='/') {
				throw Error('Full path must starts with "/"');
			}
		}
		pos=fullPath.indexOf("/",1);
		if(pos<0){
			diskName=fullPath.substring(1);
		}else{
			diskName=fullPath.substring(1,pos);
		}
		return diskName;
		
	};
	
	//-----------------------------------------------------------------------
	JAXDisk.getPathDisk=function(fullPath){
		let pos,diskName,disk;
		if(fullPath[0]!=='/'){
			fullPath=pathLib.join(JAXDisk.appPath,fullPath);
			if(fullPath[0]!=='/') {
				throw Error('Full path must starts with "/"');
			}
		}
		pos=fullPath.indexOf("/",1);
		if(pos<0){
			diskName=fullPath.substring(1);
		}else{
			diskName=fullPath.substring(1,pos);
		}
		disk=JAXDisk.liveDisks[diskName];
		return disk;
	
	};
	
	//-----------------------------------------------------------------------
	//Make a new dir:
	JAXDisk.newDir=async function(fullPath,allowDisk=false,recursive=true){
		let [disk,diskPath,diskName]=await parseDiskPath(fullPath);
		if(typeof(allowDisk)==="object"){
			let options=allowDisk;
			allowDisk=options.allowDisk||false;
			recursive=options.recursive||false;
		}
		if(!disk){
			if(!allowDisk) {
				return false;
			}else{
				disk=await JAXDisk.newDisk(diskName);
				if(!diskPath){
					return true;
				}
			}
		}
		await disk.newDir(diskPath,false,recursive);
		return true;
	};
	
	JAXDisk.newDirSync=function(fullPath,recursive=true){
		let [disk,diskPath,diskName]=parseDiskPathSync(fullPath);
		if(typeof(recursive)==="object"){
			recursive=recursive.recursive||false;
		}
		if(!disk){
			return false;
		}
		disk.newDirSync(diskPath,recursive);
	}
	
	//-----------------------------------------------------------------------
	//Delete a entry:
	JAXDisk.del=async function(fullPath,allowDisk=false,recursive=true){
		let list;
		let [disk,diskPath,diskName]=await parseDiskPath(fullPath);
		if(typeof(allowDisk)==="object"){
			let options=allowDisk;
			allowDisk=options.allowDisk||false;
			recursive=options.recursive||false;
		}
		if(!disk){
			if(!allowDisk) {
				return false;
			}
		}
		list=await JAXDisk.getEntries(fullPath);
		if(list && list.length>0 && !recursive){
			return false;
		}
		if(!diskPath){
			if(!allowDisk){
				return false;
			}
			await JAXDisk.dropDisk(diskName);
			return true;
		}
		await disk.del(diskPath);
		return true;
	};
	
	JAXDisk.delSync=function(fullPath,recursive=true){
		let [disk,diskPath,diskName]=parseDiskPathSync(fullPath);
		if(typeof(recursive)==="object"){
			recursive=recursive.recursive||false;
		}
		if(!disk){
			return false;
		}
		disk.delSync(diskPath,recursive);
	};
	
	//-----------------------------------------------------------------------
	//Read a file with full path:
	JAXDisk.readFile=async function(path,encode){
		let data;
		let [disk,diskPath]=await parseDiskPath(path);
		data=await disk.readFile(diskPath,encode);
		if(data===null){
			throw Error(`${path}: can't read contents.`);
		}
		return data;
	};
	
	JAXDisk.readFileSync=function(fullPath,encode){
		let data;
		let [disk,diskPath,diskName]=parseDiskPathSync(fullPath);
		if(!disk){
			return false;
		}
		data=disk.readFileSync(diskPath,encode);
		if(data===null){
			throw Error(`${fullPath}: can't read contents.`);
		}
		return data;
	};
	
	//-----------------------------------------------------------------------
	//Write a file with full path:
	JAXDisk.writeFile=async function(path,data,encode){
		let [disk,diskPath]=await parseDiskPath(path);
		return await disk.writeFile(diskPath,data,encode);
	};
	
	JAXDisk.writeFileSync=function(fullPath,data,encode){
		let [disk,diskPath,diskName]=parseDiskPathSync(fullPath);
		if(!disk){
			return false;
		}
		return disk.writeFileSync(diskPath,data,encode);
	};
	
	//-----------------------------------------------------------------------
	//Get a entry with full path:
	JAXDisk.getEntry=async function(path){
		if(path==="/") {
			return {name:"/",dir:1,root:1};
		}
		let [disk,diskPath]=await parseDiskPath(path);
		if(disk){
			return await disk.getEntry(diskPath);
		}else{
			return null;
		}
	};
	
	JAXDisk.getEntrySync=function(fullPath){
		let [disk,diskPath,diskName]=parseDiskPathSync(fullPath);
		if(!disk){
			return null;
		}
		return disk.getEntrySync(diskPath);
	};
	
	//-----------------------------------------------------------------------
	//Set a entry info with full path:
	JAXDisk.setEntryInfo=async function(path,infoVO){
		let [disk,diskPath]=await parseDiskPath(path);
		return await disk.setEntryInfo(diskPath,infoVO);
	};
	
	JAXDisk.setEntryInfoSync=function(fullPath,infoVO){
		let [disk,diskPath,diskName]=parseDiskPathSync(fullPath);
		if(!disk){
			return false;
		}
		return disk.setEntryInfoSync(diskPath,infoVO);
	};
	
	//-----------------------------------------------------------------------
	//Get entries under a full path:
	JAXDisk.getEntries=async function(path){
		if(path==="/"){
			let list= await JAXDisk.getDiskNames();
			list=list.map(name=>{return {name:name,dir:1,disk:1}});
			return list;
		}else {
			let [disk, diskPath] = await parseDiskPath(path);
			if(disk){
				return await disk.getEntries(diskPath);
			}else{
				return null;
			}
		}
	};
	
	JAXDisk.getEntriesSync=function(fullPath){
		let [disk,diskPath,diskName]=parseDiskPathSync(fullPath);
		if(!disk){
			return null;
		}
		return disk.getEntriesSync(diskPath);
	};
	
	//-----------------------------------------------------------------------
	//Get entry names under a full path:
	JAXDisk.getEntryNames=async function(path){
		if(path==="/"){
			return await JAXDisk.getDiskNames();
		}
		let list=await JAXDisk.getEntries(path);
		if(!list){
			return null;
		}
		return list.map(item=>item.name);
	};
	JAXDisk.readDir=JAXDisk.getEntryNames;
	
	JAXDisk.getEntryNamesSync=function(fullPath){
		let list=JAXDisk.getEntriesSync(fullPath);
		if(!list){
			return null;
		}
		return list.map(item=>item.name);
	};
	JAXDisk.readDirSync=JAXDisk.getEntryNamesSync;
	
	//-----------------------------------------------------------------------
	//Check if a entry is there
	JAXDisk.isExist=async function(path){
		let entry=await JAXDisk.getEntry(path);
		return !!entry;
	};
	
	JAXDisk.isExistSync=function(fullPath){
		let [disk,diskPath,diskName]=parseDiskPathSync(fullPath);
		if(!disk){
			return false;
		}
		return disk.isExistSync(diskPath);
	};
	
	//-----------------------------------------------------------------------
	//Copy a file or a dir to a new path:
	JAXDisk.copy=async function(orgPath,tgtPath,options){
		let [orgDisk,orgDiskPath]=await parseDiskPath(orgPath);
		let [tgtDisk,tgtDiskPath]=await parseDiskPath(tgtPath);
		let overwrite=typeof(options)==="object"?(options.force||false):(options||false);
		await tgtDisk.copyFile(orgDiskPath,tgtDiskPath,overwrite,orgDisk);
	};
	
	JAXDisk.copySync=function(orgPath,tgtPath,options){
		let [orgDisk,orgDiskPath]=parseDiskPathSync(orgPath);
		let [tgtDisk,tgtDiskPath]=parseDiskPathSync(tgtPath);
		let overwrite=typeof(options)==="object"?(options.force||false):(options||false);
		tgtDisk.copySync(orgDiskPath,tgtDiskPath,overwrite,orgDisk);
	};
	
	//-----------------------------------------------------------------------
	//Move/ rename path:
	JAXDisk.move=async function(orgPath,tgtPath,options){
		let entry,overwrite;
		overwrite=options?options.force||false:false;
		if(orgPath.endsWith("/")){
			orgPath=orgPath.substring(0,orgPath.length-1);
		}
		if(tgtPath.endsWith("/")){
			tgtPath=tgtPath.substring(0,tgtPath.length-1);
		}
		entry=await JAXDisk.getEntry(orgPath);
		if(!entry){
			return false;
		}
		entry=await JAXDisk.getEntry(tgtPath);
		if(entry && !overwrite){
			return false;
		}
		if(orgPath===tgtPath || tgtPath.startsWith(orgPath+"/") || orgPath.startsWith(tgtPath+"/")){
			return false;
		}
		await JAXDisk.copy(orgPath,tgtPath,options);
		await JAXDisk.del(orgPath);
		return true;
	};

	JAXDisk.moveSync=function(orgPath,tgtPath,options){
		let entry,overwrite;
		overwrite=options?options.force||false:false;
		entry=JAXDisk.getEntrySync(orgPath);
		if(!entry){
			return false;
		}
		entry=JAXDisk.getEntrySync(tgtPath);
		if(entry && !overwrite){
			return false;
		}
		if(orgPath===tgtPath || tgtPath.startsWith(orgPath+"/") || orgPath.startsWith(tgtPath+"/")){
			return false;
		}
		JAXDisk.copySync(orgPath,tgtPath,options);
		JAXDisk.delSync(orgPath);
		return true;
	};
	
	//--------------------------------------------------------------------------
	//Base version access:
	JAXDisk.loadFileBase=async function(path,encode=null){
		let data;
		let [disk,diskPath]=await parseDiskPath(path);
		return disk.loadFileBase(diskPath,encode);
	};
}

//****************************************************************************
//JAXMemDisk
//****************************************************************************
{
	//-----------------------------------------------------------------------
	//Constructor:
	JAXMemDisk=function(disk){
		this.disk=disk;
		this.entries=new Map();
		this.name=disk.name;
		this.inMemory=true;
		disk.memDisk=this;
		this.actorId=null;
	};
	jaxMemDisk=JAXMemDisk.prototype={};
	
	//-----------------------------------------------------------------------
	//Init memery disk, read all entries into memory
	jaxMemDisk.init=async function(){
		let disk,keys,plist,entries,pathPrefix;
		console.warn(`Sync-init disk: ${this.name}. Better use async access whenever possible.`);
		disk=this.disk;
		entries=this.entries;
		keys=await disk.getAllItemPath();
		plist=[];
		function readEntry(path){
			return get(path,disk.dbStore).then(fileObj=>{
				entries.set(path,fileObj);
			});
		}
		for(let key of keys){
			plist.push(readEntry(key));
		}
		await Promise.all(plist);
		pathPrefix="/"+this.name+"/";
		this.actorId=await JAXDisk.watch("/"+this.name,(act,path,actorId)=>{
			if(actorId===this.actorId){
				return;
			}
			switch(act){
				case "NewDir":{
					this.newDirSync(path);
					break;
				}
				case "Del":{
					this.delSync(path);
					break;
				}
				case "File":{
					this.disk.readFile().then(data=>{
						this.writeFileSync(path,data);
					});
					break;
				}
			}
		})
		return true;
	}
	//***********************************************************************
	//Sync functions:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		//Create a new dir
		jaxMemDisk.newDirSync=function(path){
			let upDir,tgtName,upDirObj,time,curEntry;
			if(path.startsWith("/")){
				path=path.substring(1);
			}
			if(path.endsWith("/")){
				path=path.substring(0,path.length-1);
			}
			if(path==="."||path===""){
				throw Error(`Illegal dir name: ${path}`);
			}
			curEntry=this.entries.get(path);
			if(curEntry){
				if(curEntry.dir){
					return true;
				}
				throw Error(`/${this.name}/path is a file, can't create dir at same place.`);
			}
			[tgtName,upDir]=divPath(path);
			if(!upDir){
				upDirObj=this.entries.get(".");
			}else{
				upDirObj=this.entries.get(upDir);
			}
			if(!upDirObj){
				this.newDirSync(upDir);
				upDirObj=this.entries.get(upDir);
				if(!upDirObj){
					return false;
				}
			}
			time=Date.now();
			upDirObj[tgtName]={name:tgtName,createTime:time,dir:1};
			this.entries.set(path,{});
			this.disk.newDir(path,{actor:this.actorId});
			return true;
		};
		jaxDisk.newDirSync=function(...args){
			if(!this.memDisk){
				throw Error(`Disk ${this.name} is not in memory to async access.`);
			}
			return this.memDisk.newDirSync(...args);
		};
		
		//-------------------------------------------------------------------
		//Delete a entry item:
		jaxMemDisk.delSync=function(path){
			let upDir,tgtName,curEntry,upDirObj;
			if(path.startsWith("/")){
				path=path.substring(1);
			}
			if(path.endsWith("/")){
				path=path.substring(0,path.length-1);
			}
			if(path==="."||path===""){
				throw Error(`Illegal dir name: ${path}`);
			}
			curEntry=this.entries.get(path);
			if(!curEntry){
				return true;
			}
			[tgtName,upDir]=divPath(path);
			if(!upDir){
				upDirObj=this.entries.get(".");
			}else{
				upDirObj=this.entries.get(upDir);
			}
			if(!upDirObj){
				throw Error(`Path: /${this.name}/${upDir} is not available.`);
			}
			if(curEntry.dir){
				let list=this.getEntriesSync(path);
				for(let subItem of list){
					this.delSync(path+"/"+subItem.name);
				}
			}
			delete upDirObj[tgtName];
			this.entries.delete(path);
			this.disk.del(path,{actor:this.actorId});
			return true;
		};
		jaxDisk.delSync=function(...args){
			if(!this.memDisk){
				throw Error(`Disk ${this.name} is not in memory to async access.`);
			}
			return this.memDisk.delSync(...args);
		};
		
		//-------------------------------------------------------------------
		//Read a file content
		jaxMemDisk.readFileSync=function(path,encode){
			let data;
			data=this.entries.get(path);
			if(!(data instanceof Uint8Array)){
				return null;
			}
			if(encode){
				let enc = new TextDecoder("utf-8");
				return enc.decode(data);
			}
			return data;
		};
		jaxDisk.readFileSync=function(...args){
			if(!this.memDisk){
				throw Error(`Disk ${this.name} is not in memory to async access.`);
			}
			return this.memDisk.readFileSync(...args);
		};
		
		//-------------------------------------------------------------------
		//Write a file
		jaxMemDisk.writeFileSync=function(path,data,encode){
			let byteAry,tgtName,upPath,time,upObj,fileStub,orgStub;
			if(encode) {
				data=""+data;//Lazy convert
			}
			if(path.startsWith("/")){
				path=path.substring(1);
			}
			if(path.endsWith("/")){
				throw Error(`${path} can't be a file name.`)
			}
			
			[tgtName,upPath]=divPath(path);
			time=Date.now();
			
			//Ensure saved object is ByteArray
			if (typeof (data) === 'string') {
				let encoder = new TextEncoder();
				byteAry = encoder.encode(data);
			} else if (data instanceof File) {
				throw Error("File object can't do sync write, convert to Uint8Array before write.");
			} else if (data instanceof Uint8Array) {
				byteAry = data;
			}else if(data instanceof ArrayBuffer){
				byteAry = new Uint8Array(data);
			}
			upObj=this.entries.get(upPath);
			if(upObj) {
				if(!upObj.dir){
					throw Error(`${upPath} is not a dir, can't write file under it.`)
				}
			}else{
				this.newDirSync(upPath);
				upObj=this.entries.get(upPath);
				if(!upObj){
					throw Error(`${upPath} can't be create.`)
				}
			}
			orgStub=upObj[tgtName];
			if(orgStub){
				if(orgStub.dir){
					throw Error(`/${this.name}/${path} is a dir, can't be overwrite by a file.`);
				}
				fileStub=orgStub;
			}else {
				fileStub = {
					name: tgtName,
					modified:true,
					createTime:time
				};
				upObj[tgtName]=fileStub;
			}
			fileStub.size=byteAry.length;
			fileStub.modifyTime=time;
			digestBytes(byteAry).then(hex=>{
				fileStub.hash=hex;
			});
			this.entries.set(path,byteAry);
			this.disk.writeFile(path,byteAry,encode);
		}
		jaxDisk.writeFileSync=function(...args){
			if(!this.memDisk){
				throw Error(`Disk ${this.name} is not in memory to async access.`);
			}
			return this.memDisk.writeFileSync(...args);
		};
		
		//-------------------------------------------------------------------
		//Check entry exist:
		jaxMemDisk.isExistSync=function(path){
			if(path.endsWith("/")){
				path=path.substring(0,path.length-1);
			}
			if(path==="" || path==="."){
				return true;
			}
			return !!this.entries.get(path);
			
		};
		jaxDisk.isExistSync=function(...args){
			if(!this.memDisk){
				throw Error(`Disk ${this.name} is not in memory to async access.`);
			}
			return this.memDisk.isExistSync(...args);
		};
		
		//-------------------------------------------------------------------
		//Get a file entry:
		jaxMemDisk.getEntrySync=function(path){
			let dir,fileName;
			[fileName,dir]=divPath(path);
			if(dir.startsWith("/")){
				dir=dir.substring(1);
			}
			if(dir.endsWith("/")){
				dir=dir.substring(0,dir.length-1);
			}
			if(!dir){
				dir='.';
				if(fileName===""){
					return {name:this.name,dir:1,disk:1};
				}
			}
			dir=this.entries.get(dir);
			if(dir) {
				let entry=dir[fileName];
				if(entry instanceof Object){
					return entry;
				}
				return null;
			}
			return null;
		};
		jaxDisk.getEntrySync=function(...args){
			if(!this.memDisk){
				throw Error(`Disk ${this.name} is not in memory to async access.`);
			}
			return this.memDisk.getEntrySync(...args);
		};
		
		//-------------------------------------------------------------------
		//Get sub items' entry under a path
		jaxMemDisk.getEntriesSync=function(path){
			let dir;
			if(path.startsWith("/")){
				path=path.substring(1);
			}
			if(path.endsWith("/")){
				path=path.substring(0,path.length-1);
			}
			if(path===""){
				path=".";
			}
			dir=this.entries.get(path);
			if(dir){
				if(dir instanceof Uint8Array){
					return null;//This is a file, not dir
				}
				return Object.values(dir);
			}
			return null;
		};
		jaxDisk.getEntriesSync=function(...args){
			if(!this.memDisk){
				throw Error(`Disk ${this.name} is not in memory to async access.`);
			}
			return this.memDisk.getEntriesSync(...args);
		};
		
		//-------------------------------------------------------------------
		//Set a entry info:
		jaxMemDisk.setEntryInfoSync=function(path,info){
			let dir,fileName;
			[fileName,dir]=divPath(path);
			if(dir.startsWith("/")){
				dir=dir.substring(1);
			}
			if(dir.endsWith("/")){
				dir=dir.substring(0,dir.length-1);
			}
			if(!dir){
				return;//Can't set disk root info
			}
			dir=this.entries.get(dir);
			if(dir && !(dir instanceof Uint8Array)) {
				let orgInfo=dir[fileName];
				if(!orgInfo){
					return false;
				}
				//These key is critical and not to be changed here:
				delete info.name;
				delete info.dir;
				delete info.disk;
				Object.assign(orgInfo,info);
				return true;
			}
			return false;
		};
		jaxDisk.setEntryInfoSync=function(...args){
			if(!this.memDisk){
				throw Error(`Disk ${this.name} is not in memory to async access.`);
			}
			return this.memDisk.setEntryInfoSync(...args);
		};
		
		//-------------------------------------------------------------------
		//Copy a file/dir:
		jaxMemDisk.copySync=function (orgPath,newPath,overwrite=1,orgDisk=null){
			let self=this;
			let orgEntry,tgtEntry;
			if(orgPath.endsWith("/")){
				orgPath=orgPath.substring(0,orgPath.length-1);
			}
			if(newPath.startsWith("/")){
				newPath=newPath.substring(1);
			}
			if(newPath.endsWith("/")){
				newPath=newPath.substring(0,newPath.length-1);
			}
			if(orgPath.startsWith("/")){
				orgPath=orgPath.substring(1);
			}
			orgDisk=orgDisk||this;
			if(orgDisk.memDisk){
				orgDisk=orgDisk.memDisk;
			}
			if(!orgDisk.readFileSync){
				throw Error(`orgDisk ${orgDisk.name} can not sync access.`);
			}
			function copyOneFile(orgDisk,orgPath,tgtPath){
				let data;
				data=orgDisk.readFileSync(orgPath);
				self.writeFileSync(tgtPath,data);
			}
			orgEntry=orgDisk.getEntrySync(orgPath);
			tgtEntry=self.getEntrySync(newPath);
			if(orgEntry.dir){
				let list,subItem;
				if(tgtEntry && !tgtEntry.dir) {
					if(!overwrite) {
						return false;
					}
					self.delSync(newPath);
				}
				self.newDirSync(newPath);
				list=orgDisk.getEntriesSync(orgPath);
				for(subItem of list){
					if(subItem.dir){
						self.copySync(orgPath+"/"+subItem.name,newPath+"/"+subItem.name,overwrite,orgDisk);
					}else{
						let tgtPath=newPath+"/"+subItem.name;
						tgtEntry=self.getEntrySync(tgtPath)
						if(tgtEntry){
							if(tgtEntry.dir || !overwrite){
								continue;
							}
						}
						copyOneFile(orgDisk,orgPath+"/"+subItem.name,tgtPath);
					}
				}
				return true;
			}else{
				if(tgtEntry){
					if(!overwrite)
						return false;
					if(tgtEntry.dir) {
						throw Error(`/${self.name}/${newPath} is a dir, can't overwrite by file /${orgDisk.name}/${orgPath}`);
					}
				}
				
				copyOneFile(orgDisk,orgPath,newPath);
				return true;
			}
		};
		jaxDisk.copySync=function(...args){
			if(!this.memDisk){
				throw Error(`Disk ${this.name} is not in memory to async access.`);
			}
			return this.memDisk.copySync(...args);
		};
		
		//-------------------------------------------------------------------
		//Move a file/dir:
		jaxMemDisk.moveSync=function (orgPath,newPath,overwrite=1,orgDisk=null){
			this.copySync(orgPath,newPath,overwrite,orgDisk);
			orgDisk.delSync(orgPath);
		};
		jaxDisk.moveSync=function(...args){
			if(!this.memDisk){
				throw Error(`Disk ${this.name} is not in memory to async access.`);
			}
			return this.memDisk.moveSync(...args);
		};
	}
}

//****************************************************************************
//Watch API:
//****************************************************************************
{
	//------------------------------------------------------------------------
	notifyModifyAct=function(act,path,actor){
		//let sw=navigator.serviceWorker.controller;
		let sw=JAXDisk.swControler;
		if (sw) {
			actor=actor||"";
			sw.postMessage({msg:"WatchAct",act:act,path:path,actor:actor});
		}
	};
}
export {JAXDisk};
export default JAXDisk;
