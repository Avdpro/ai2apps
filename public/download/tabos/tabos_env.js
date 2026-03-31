import {tabFS} from "/@tabos";
import CokeTTY from "./tabos_tty.js"
import {EventEmitter} from "./utils/events.js";
import pathApi from "./utils/path.js";
import {parseShellArgs} from "./shell_parse.js";

let jaxExecPackage,jaxExecKillOne,jaxExecKillAll,jaxClientExec;
let url=import.meta.url;
let tabosDir=pathApi.dirname(url);

let CokeEnv,cokeEnv;
let HostEnv,hostEnv;
let process=window.process;
//***************************************************************************
//CokeEnv:
//***************************************************************************
{
	CokeEnv = function () {
		EventEmitter.call(this);
		this.argLine = null;
		this.argv = [];
		this.stdin = null;
		this.stdout = null;
		this.stderr = null;
		this.tty = null;
		this.host = null;
		this.envVals = {
			get curPath () {
				return tabFS.appPath;
			},
			set curPath (path) {
				return tabFS.appPath = path;
			},
			//curPath:this.curDiskPath,
		};
		this.execPath = null;
		this.exitCode = 0;
		this.exitData=null;
		
		this.waitCmd=false;
		this.inCmd=false;
		this.curCmd=null;
		this.cmdProcessStub=null;
		this.cmdTextList=[];
		this.cmdTextIdx=-1;
		
		this.OnToolKey=this.OnToolKey.bind(this);
		this.OnExecKey=this.OnExecKey.bind(this);
		
		this.quickCmdMap={};
		
		if(process && !process.cokeEnv){
			process.cokeEnv=this;
		}
	};
	
	cokeEnv = CokeEnv.prototype = new EventEmitter();

	//-----------------------------------------------------------------------
	//Init env:
	cokeEnv.init = function (argLine, envVals, ttyDiv = null, host = null, seq = "") {
		argLine = argLine || "";
		this.argLine = argLine;
		this.host = host?(new HostEnv(this,host,seq)):null;
		Object.assign(this.envVals, envVals||{});
		this.argv = parseShellArgs(argLine,this.envVals).argv;
		this.execPath = tabFS.appPath;
		
		//init the tty，get stdin/stdout/stderr:
		this.tty = new CokeTTY(ttyDiv, this.host);
		this.stdin = this.tty.stdin;
		this.stdout = this.tty.stdout;
		this.stderr = this.tty.stdout;
	}

	//-----------------------------------------------------------------------
	//Exit env:
	cokeEnv.exit = function (code) {
		this.exitCode = code;
	};
	
	//-----------------------------------------------------------------------
	//Get current path
	CokeEnv.cwd=cokeEnv.cwd = function () {
		return tabFS.appPath;
	};
	
	//-----------------------------------------------------------------------
	//Get current path's diskName:
	CokeEnv.diskName=cokeEnv.diskName = function (path) {
		let pts;
		path=path||tabFS.appPath;
		pts=path.split("/");
		return pts[1];
	};
	
	//-----------------------------------------------------------------------
	//Get current path's related path to it's disk:
	CokeEnv.pathByDisk=cokeEnv.pathByDisk =cokeEnv.cwdDiskPath = function (path) {
		let pts;
		path=path||tabFS.appPath;
		pts=path.split("/");
		pts.splice(0,2);
		if(pts.length) {
			return pts.join("/");
		}
		return "";
	};
	
	//-----------------------------------------------------------------------
	//Set current path:
	CokeEnv.chdir=cokeEnv.chdir = function (dirPath) {
		if(dirPath[0]!=="/") {
			dirPath = pathApi.join(tabFS.appPath, dirPath);
		}
		tabFS.appPath = dirPath;
	}

	//-----------------------------------------------------------------------
	//Set a env variable
	cokeEnv.set = function (key, val) {
		this.envVals[key] = val;
	};

	//-----------------------------------------------------------------------
	//Get a env variable
	cokeEnv.get = function (key) {
		return this.envVals[key];
	};
	
	//-----------------------------------------------------------------------
	//Get a clone of current env variables' VO:
	cokeEnv.getEnvVals=function(){
		let vo={};
		Object.assign(vo,this.envVals);
		return vo;
	};
	
	//***********************************************************************
	//Process(Web pages/iFrames) interactive/ communicate:
	//***********************************************************************
	{
		//-------------------------------------------------------------------
		//Send message to [client] process:
		cokeEnv.postRemoteMsg=function(client,msg){
			msg.msgCatalog="FrameEXECHost";
			client.postMessage(msg);
		};
		
		//-------------------------------------------------------------------
		//Handle client的 message:
		cokeEnv.handleRemoteMsg = function (data,client) {
			let msg;
			msg=data.msg;
			switch(msg){
				case "StartInput":{
					this.tty.startInput(data.prefix,data.password||false,data.initText);
					this.tty.once("LineInput",(text)=>{
						this.postRemoteMsg(client,{msg:"LineInput",text:text});
					});
					break;
				}
				case "LineInput":{
					this.tty.endInput(data.text);
					break;
				}
				case "tty":
					this.tty[data.func].apply(this.tty,data.args);
					break;
			}
		};
	}
	
	//***********************************************************************
	//Execute command related functions:
	//***********************************************************************
	{
		//------------------------------------------------------------------------
		//Execute a command:
		cokeEnv.execCmd=async function(cmdText){
			let items,cmd,cmdFunc,stdout,retVO;
			
			this.inCmd=true;
			if(this.waitCmd){
				//Show the command:
				this.tty.setInputText(cmdText);
				this.tty.endInput("");
			}else {
				this.tty.textOut(`\n${cmdText}\n`);
			}
			
			this.cmdTextList.push(cmdText);
			stdout=this.stdout;
			
			let parseVO;
			parseVO=parseShellArgs(cmdText,this.envVals);
			if(parseVO.error){
				stdout.write("CokeEnv: parse error: "+parseVO.error);
				this.inCmd=false;
				this.cmdProcessStub=null;
				throw Error(parseVO.error);
			}
			items=parseVO.argv;
			cmd=items[0];
			this.curCmd=cmd;
			if(!cmd){
				this.inCmd=false;
				return;
			}
			cmdFunc=await this.getCmdFunc(cmd,cmdText);
			if(!cmdFunc){
				stdout.write("CokeEnv: "+cmd+": command not found.");
				this.inCmd=false;
				this.cmdProcessStub=null;
				throw Error("Can't find cmd: "+cmd);
				return;
			}
			if(cmdFunc){
				try{
					this.inCmd=true;
					this.emit("ExecCmdStart",cmd);
					retVO=await cmdFunc(this,items,cmdText);
					this.inCmd=false;
					this.emit("ExecCmdDone",retVO);
				}catch(e){
					stdout.write("CokeEnv: "+cmd+": error in exec command: "+e);
					this.emit("ExecCmdError",e);
					throw e;
				}
				this.cmdProcessStub=null;
				this.curCmd=null;
				this.inCmd=false;
				return retVO;
			}
			return null;
		};
		
		//------------------------------------------------------------------------
		cokeEnv.getCmdFunc=async function(cmd,cmdText){
			let vo;
			//check cmd's package:
			vo=await this.checkPkg(cmd);
			if(vo && vo.main){
				if(vo.type==="cmd"){
					return (env,items,cmdText)=>{
							return new Promise(resolve=>{
								this.cmdProcessStub=jaxExecPackage(this,cmd,vo.main,cmdText,(code,cwd,data,envVals)=>{
									if(cwd){
										this.chdir(cwd);
									}
									if(envVals && typeof(envVals)==="object"){
										let key,oldKeys;
										oldKeys=Object.keys(this.envVals||{});
										for(key of oldKeys){
											if(!(key in envVals) && key!=="curPath"){
												delete this.envVals[key];
											}
										}
										for(key in envVals){
											this.set(key,envVals[key]);
										}
									}
									resolve(data);
								});
							})
						};
				}else if(vo.type==="app"){
					return (env,items,cmdText)=> {
						let urlVO={
							cmd:cmdText,
							path:tabFS.appPath,
							cwd:tabFS.appPath,
							vals:this.envVals
						}
						//Open a new page add cmdText and path in the URL:
						window.open(`${vo.main}?cokeExecCmd=${encodeURIComponent(JSON.stringify(urlVO))}`);
					}
				}
			}
			return this.quickCmdMap[cmd]||null;
		};
		
		//------------------------------------------------------------------------
		cokeEnv.checkPkg=async function(pkgName){
			let res,binJSON;
			//Check local disk bin for json:
			try{
				let disk;
				disk=this.diskName();
				if(disk){
					//binJSON=await fsp.readFile(`/${disk}/bin/${pkgName}.json`,"utf8");
					binJSON=await tabFS.readFile(`/${disk}/bin/${pkgName}.json`,"utf8");
					binJSON=JSON.parse(binJSON);
					if(binJSON.main){
						return {
							type:binJSON.type||"cmd",
							main:document.location.origin+"/"+binJSON.main
						};
					}
				}
			}catch(err){
			}
			
			//Check system disk bin for json:
			try{
				//binJSON=await fsp.readFile(`/coke/bin/${pkgName}.json`,"utf8");
				binJSON=await tabFS.readFile(`/coke/bin/${pkgName}.json`,"utf8");
				binJSON=JSON.parse(binJSON);
				if(binJSON.main){
					return {
						type:binJSON.type||"cmd",
						main:document.location.origin+"/"+binJSON.main
					}
				}
			}catch(err){
			}
			return false;
		};
	}
	
	//***********************************************************************
	//Advanced user interactions:
	//***********************************************************************
	{
		//------------------------------------------------------------------------
		//Input and exec command:
		cokeEnv.cmdInput=async function(execCmd=true,loop=true){
			let text;
			do{
				this.cmdTextIdx=this.cmdTextList.length;
				this.tty.on("ToolKey",this.OnToolKey);
				this.emit("StartInput");
				this.waitCmd=true;
				text=await this.tty.readLine();
				this.waitCmd=false;
				this.tty.off("ToolKey",this.OnToolKey);
				if(execCmd && !this.inCmd) {
					if(text) {
						this.tty.on("KeyInExec", this.OnExecKey);
						try {
							await this.execCmd(text);
						}catch(err){
						}
						this.tty.off("KeyInExec", this.OnExecKey);
					}
				}else if(!loop){
					return text;
				}
			}while(!this.inCmd);
		};
		
		//------------------------------------------------------------------------
		//Hand tool keys while execing command:
		cokeEnv.OnExecKey=function(key) {
			if (this.inCmd) {
				if (key === "BreakCmd") {
					//Kill sub process:
					if (this.cmdProcessStub) {
						jaxExecKillOne(this.cmdProcessStub)
						this.cmdProcessStub = false;
						this.inCmd = false;
						this.curCmd = null;
					}
					this.stdout.write("\n^C\n");
				}
				return;
			}
		}
		
		//------------------------------------------------------------------------
		//Hand tool keys while command input :
		cokeEnv.OnToolKey=function(key){
			switch(key){
				case "ArrowUp":{
					let text;
					if(this.cmdTextIdx>0){
						this.cmdTextIdx-=1;
						text=this.cmdTextList[this.cmdTextIdx];
						this.tty.setInputText(text);
					}
					break;
				}
				case "ArrowDown":{
					let text;
					if(this.cmdTextIdx<this.cmdTextList.length){
						this.cmdTextIdx+=1;
						text=this.cmdTextList[this.cmdTextIdx]||"";
						this.tty.setInputText(text);
					}
					break;
				}
				case "BreakCmd": {
					break;
				}
				case "Tab":{
					let line,text,pts,path,pos,lead;
					line=this.tty.getInputText();
					pts=line.split(" ");
					text=pts[pts.length-1]||"";
					if(!text){
						return;
					}
					pos=text.lastIndexOf("/");
					if(pos===0){
						path="/";
						lead=text.substring(1);
					}else if(pos>0){
						path=text.substring(0,pos);
						lead=text.substring(pos+1);
						if(!path.startsWith("/")) {
							path = pathApi.join(this.cwd(), path);
						}
					}else{
						path=this.cwd();
						lead=text;
					}
					//得到目录下全部的entry
//					fsp.readdir(path).then(list=>{
					tabFS.getEntryNames(path).then(list=>{
						let n;
						list=list.filter(item=>item.startsWith(lead));
						n=list.length;
						if(n===1){
							//补全文件名
							this.tty.setInputText(line+list[0].substring(lead.length));
						}else if(n>1){
							let oldLead=list[0].substring(0,lead.length);
							let newLead;
							let done;
							do{
								newLead=list[0].substring(0,oldLead.length+1);
								if(newLead.length>oldLead.length) {
									done = list.some(text => !text.startsWith(newLead))
									oldLead=done?oldLead:newLead;
								}else{
									done = true;
								}
							}while(!done);
							if(oldLead.length>lead.length){
								this.tty.setInputText(line+oldLead.substring(lead.length));
							}
							this.tty.textOut("<Choice:> "+list+"\n");
						}
					});
					break;
				}
			}
		};
	}
}

//***************************************************************************
//HostEnv:
//***************************************************************************
{
	HostEnv=function(env,host,seq){
		this.env=env;
		this.host=host;
		this.seq=seq;
	};
	hostEnv=HostEnv.prototype={};
	
	//-------------------------------------------------------------------
	hostEnv.sendRemoteMsg=function(msg){
		msg.msgCatalog = "FrameEXECClient";
		msg.frameSeq = this.seq;
		this.host.postMessage(msg);
	};
}

//****************************************************************************
//execPackage
//****************************************************************************
{
	let freeFrames=[];
	let frameSeq=0;
	let liveFrames={};
	let hostMsgHooked=0;
	let clientMsgHooked=0;

	//---------------------------------------------------------------------------
	jaxExecPackage=function(env,pkgName,htmlPath,line,callback){
		let ifm,seq,stub,textOutMethod;

		if(!hostMsgHooked){
			hostMsgHooked=1;
			window.addEventListener("message",(evt)=>{
				let seq,stub,frame,callback;
				if(evt.data.msgCatalog!=="FrameEXECClient"){
					//其它消息:
					return;
				}

				seq=evt.data.frameSeq;
				stub=liveFrames[seq];
				if(!stub){
					return;
				}
				frame=stub.frame;
				if(!frame){
					return;
				}
				if(!stub.remote) {
					stub.remote = evt.source;
				}
				if(stub.kill) {
					if(!stub.killed){
						evt.source.postMessage({
							msgCatalog:"FrameEXECHost",
							msg:"Kill"
						});
						stub.killed=true;
						delete liveFrames[seq];
						callback&&callback(-100,env.cwd(),{});
						setTimeout(()=>{
							document.body.removeChild(stub.frame);
						},0);
					}
				}else {
					switch (evt.data.msg) {
						case "Ready"://准备就绪，可以执行消息了
							evt.source.postMessage({
								msgCatalog: "FrameEXECHost",
								msg: "Exec",
								cmdLine: stub.line,
								envVals: stub.env.getEnvVals && env.getEnvVals()
							});
							break;
						default:
							stub.env.handleRemoteMsg(evt.data, evt.source);
							break;
						case "TextOut":
							textOutMethod = evt.data.method || "out";
							if (stub.env[textOutMethod]) {
								stub.env[textOutMethod](evt.data.text);
							}
							break;
						case "ExecDone"://执行完毕
							callback = stub.callback;
							delete liveFrames[seq];
							callback && callback(evt.data.code, evt.data.cwd, evt.data.data,evt.data.envVals);
							document.body.removeChild(stub.frame);
							break;
					}
				}
			},false);
		}

		ifm=freeFrames.pop();
		seq="JAXEXECFrame"+(frameSeq++);
		if(!ifm){
			ifm=document.createElement("iframe");
			ifm.style.width="10px";
			ifm.style.height="10px";
			ifm.style.left="0px";
			ifm.style.top="-100px";
			ifm.style.position="absolute";
		}
		let ext;
		ext=pathApi.extname(htmlPath).toLowerCase();
		if(ext===".html" || ext===".htm"){
			ifm.src=htmlPath+"?"+seq;
		}else if(ext===".js" || ext===".mjs"){
			//ifm.src=`${document.location.origin}//coke/bin/cmd.html?cmdFrameSeq=${seq}&src=${encodeURIComponent(htmlPath)}`;
			ifm.src=`${tabosDir}/cmd.html?cmdFrameSeq=${seq}&src=${encodeURIComponent(htmlPath)}`;
		}
		ifm.name=seq;
		liveFrames[seq]=stub={
			env:env,seq:seq,pkgName:pkgName,line:line,frame:ifm,callback:callback,remote:null,kill:false,killed:false
		};
		document.body.appendChild(ifm);
		return stub;
	};

	//---------------------------------------------------------------------------
	//Kill a child processes:
	jaxExecKillOne=function(stub){
		let seq,callback;
		seq=stub.seq;
		callback=stub.callback;
		if(stub.remote){
			stub.remote.postMessage({
				msgCatalog:"FrameEXECHost",
				msg:"Kill"
			});
			stub.killed=true;
			delete liveFrames[seq];
			callback&&callback(-100,stub.env.cwd(),{});
			setTimeout(()=>{
				document.body.removeChild(stub.frame);
			},0);
		}else{
			stub.kill=true;
			stub.killed=false;
		}
	};

	//---------------------------------------------------------------------------
	//Kill all child processes:
	jaxExecKillAll=function(){
		let list;
		list=Object.values(liveFrames);
		list.forEach(stub=>{
			jaxExecKillOne(stub);
		})
	};

	//---------------------------------------------------------------------------
	//as client, execute a function:
	jaxClientExec=function(func){
		let seq,host,env;
		seq=window.cmdFrameSeq;
		if(!seq){
			throw "jaxClientExec: No client frame seq for exec!";
		}
		host=window.parent;
		if(!clientMsgHooked){
			clientMsgHooked=1;
			env=null;
			window.addEventListener("message",async (evt)=>{
				if(evt.data.msgCatalog!=="FrameEXECHost"){
					//Other messages
					return;
				}
				switch(evt.data.msg){
					case "Exec": {//Start execution:
						let cmdLine,envVals;
						cmdLine=evt.data.cmdLine;
						envVals=evt.data.envVals;
						env=new CokeEnv(null);
						env.init(cmdLine,envVals,null,host,seq);
						try {
							await func(env, cmdLine);
						}catch(e){
							env.stderr.write("Error: "+e);
						}
						env.host.sendRemoteMsg({
							msg:"ExecDone",
							cwd:env.cwd(),
							code:env.exitCode||0,
							data:env.exitData||null,
							envVals:env.getEnvVals?env.getEnvVals():null
						});
						break;
					}
					case "Kill":{
						//Kill all child process:
						jaxExecKillAll();
					}
					default:{
						if(env){
							env.handleRemoteMsg(evt.data,evt.source);
						}
						break;
					}
				}
			},false);

			host.postMessage({
				msgCatalog:"FrameEXECClient",
				msg:"Ready",
				frameSeq:seq
			});
		}

	};
}

let CokeFrame,cokeFrame,liveFrames,nextSeq,makeCokeFrame;

liveFrames={};
nextSeq=1;
//****************************************************************************
//CokeFrame
//****************************************************************************
{
	//------------------------------------------------------------------------
	CokeFrame=function(){
		let ifm,seq;
		EventEmitter.call(this);
		seq=""+(nextSeq++);
		this.frame=ifm=document.createElement("iframe");
		//ifm.src=`${document.location.origin}//-terminal/frame.html?${seq}`;
		ifm.src=`${tabosDir}/frame.html?${seq}`;
		this.frameStub=liveFrames[seq]={
			cokeFrame:this,seq:seq,frame:ifm,client:null
		};
		this.inCmd=false;
	};
	cokeFrame=CokeFrame.prototype=new EventEmitter();
	
	//-----------------------------------------------------------------------
	//Bind CokeFrame to a div:
	cokeFrame.createFrame=function(div){
		let ifm;
		ifm=this.frame;
		this.frameDiv=div;
		ifm.style.position="absolute";
		ifm.style.left="0px";
		ifm.style.top="0px";
		ifm.style.width="100%";
		ifm.style.height="100%";
		ifm.style.border="none";
		div.appendChild(ifm);
	};
	
	//-----------------------------------------------------------------------
	//Exec a command line in client iframe:
	cokeFrame.execCmd=function(text){
		return new Promise((resolve,reject)=>{
			let doneCbk,errorCbk,self;
			self=this;
			doneCbk=function(data){
				self.inCmd=false;
				this.off("ExecCommandDone",doneCbk);
				this.off("ExecCommandError",errorCbk);
				resolve(data);
				if(!self.inCmd){
					self.emit("ShellIdle");
				}
			}
			errorCbk=function(data){
				self.inCmd=false;
				this.off("ExecCommandDone",doneCbk);
				this.off("ExecCommandError",errorCbk);
				resolve(data);
				if(!self.inCmd){
					self.emit("ShellIdle");
				}
			}
			if(this.inCmd){
				reject(new Error("CokeFrame is executing another command."));
				return;
			}
			if(!this.frameStub.client){
				reject(new Error("CokeFrame is not ready yet."));
				return;
			}
			this.inCmd=true;
			this.on("ExecCommandDone",doneCbk);
			this.on("ExecCommandError",errorCbk);
			this.frameStub.client.postMessage({
				msgCatalog:"CokeFrameH2C",
				msg:"ExecCommand",
				cmd:text
			});
			
		});
	};
	
	//-----------------------------------------------------------------------
	//Wait cmd to finish:
	cokeFrame.waitCmd=function() {
		return new Promise((resolve,reject)=>{
			let doneCbk,errorCbk;
			doneCbk=function(){
				resolve();
				this.off("ShellIdle",doneCbk);
			}
			if(!this.inCmd){
				resolve();
				return;
			}
			this.on("ShellIdle",doneCbk);
		});
	}
	
	//-----------------------------------------------------------------------
	//Start user input command:
	cokeFrame.startInputCmd=function(){
		this.inCmd=false;
		this.frameStub.client.postMessage({
			msgCatalog:"CokeFrameH2C",
			msg:"StartInputCmd",
		});
	};
	
	//-----------------------------------------------------------------------
	//Handle client2Host messages:
	window.addEventListener("message",async (evt)=>{
		let seq,stub,frame;
		//Filter messages:
		if(evt.data.msgCatalog!=="CokeFrameC2H"){
			return;
		}
		seq=evt.data.frameSeq;
		stub=liveFrames[seq];
		if(!stub){
			return;
		}
		frame=stub.frame;
		if(!frame){
			return;
		}
		switch(evt.data.msg){
			case "ClientReady": {
				stub.client=evt.source;
				stub.cokeFrame.emit("ClientReady")
				break;
			}
			case "ExecCommandDone": {
				if(stub.cokeFrame.execError) {
					stub.cokeFrame.emit("ExecCommandError",evt.data.msg.error);
				}else {
					stub.cokeFrame.emit("ExecCommandDone",evt.data.msg.result);
				}
				break;
			}
		}
	},false);

	//------------------------------------------------------------------------
	//Make a i-frame inside [div] that runs a cokeEnv with tty:
	makeCokeFrame=function(div){
		return new Promise((resolve,reject)=>{
			let cfm;
			cfm=new CokeFrame();
			cfm.on("ClientReady",()=>{
				resolve(cfm);
			});
			cfm.createFrame(div);
		});
	};
	
}
CokeEnv.instance=null;


let TabEnv=CokeEnv;
let execPackage=jaxExecPackage,clientExec=jaxClientExec,execKill=jaxExecKillOne,execKillAll=jaxExecKillAll;
let TabFrame=CokeFrame,makeTabFrame=makeCokeFrame;
export default CokeEnv;
export {
	CokeEnv,TabEnv,
	jaxExecPackage,jaxClientExec,jaxExecKillOne,jaxExecKillAll,
	execPackage,clientExec,execKill,execKillAll,
	makeCokeFrame,makeTabFrame,TabFrame
};
