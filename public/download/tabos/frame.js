//Tab-OS in-frame-div terminal:
import {CokeEnv} from "./tabos_env.js";

let appURL=document.location.href;
let pts=appURL.split("?");
window.isJAXEXECFrame=1;
let frameSeq=window.cmdFrameSeq=pts[1]||window.name;

let cokeDiv=document.getElementById("CokeFrame");
cokeDiv.style.height="100%";
let cokeEnv=new CokeEnv(null);
cokeEnv.init("",{},cokeDiv,null);
cokeEnv.chdir("/");
let tty=cokeEnv.tty;
cokeDiv.onclick=e=>{
	if(e.target!==tty.divInput){
		if(tty.divInput){
			tty.divInput.focus();
			window.getSelection().collapse(tty.divInput.firstChild, tty.divInput.innerText.length);
		}
	}
};
//cokeEnv.cmdInput(true,true);

let host=window.parent;

window.addEventListener("message",async (evt)=>{
	if(evt.data.msgCatalog!=="CokeFrameH2C"){
		return;
	}
	switch(evt.data.msg){
		case "ExecCommand": {//Execute a command line:
			let cmdLine,envVals,result;
			cmdLine=evt.data.cmd;
			try{
				result=await cokeEnv.execCmd(cmdLine);
				tty.textOut("\n");
				host.postMessage({
					msgCatalog:"CokeFrameC2H",
					frameSeq:frameSeq,
					msg:"ExecCommandDone",
					result:result
				});
			}catch(e){
				host.postMessage({
					msgCatalog:"CokeFrameC2H",
					frameSeq:frameSeq,
					msg:"ExecCommandError",
					error:""+e
				});
			}
			break;
		}
		case "ExecCommands": {//Execute a command line:
			let list,i,n,cmdLine,envVals,result;
			list=evt.data.cmdLines;
			n=list.length;
			for(i=0;i<n;i++){
				cmdLine=list[i];
				try{
					await cokeEnv.execCmd(cmdLine);
				}catch(e){
					host.postMessage({
						msgCatalog:"CokeFrameC2H",
						frameSeq:frameSeq,
						msg:"ExecCommandError",
						error:""+e
					});
				}
			}
			break;
		}
		case "StartInputCmd":{//Start user input loop:
			cokeEnv.cmdInput(true,true);
			break;
		}
		case "chdir": {//Set dir:
			cokeEnv.chdir(evt.data.dir);
			host.postMessage({
				msgCatalog:"CokeFrameC2H",
				frameSeq:frameSeq,
				msg:"ExecCommandDone",
				result:0
			});
			break;
		}
		case "setEnv": {//Set env variable:
			cokeEnv.set(evt.data.key,evt.data.val);
			host.postMessage({
				msgCatalog:"CokeFrameC2H",
				frameSeq:frameSeq,
				msg:"ExecCommandDone",
				result:0
			});
			break;
		}
	}
},false);

host.postMessage({
	msgCatalog:"CokeFrameC2H",
	frameSeq:frameSeq,
	msg:"ClientReady",
});


