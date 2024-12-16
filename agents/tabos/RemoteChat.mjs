import pathLib from "path";
import {RemoteSession} from "./remotesession.mjs";

const agentURL=(new URL(import.meta.url)).pathname;
const basePath=pathLib.dirname(agentURL);

//----------------------------------------------------------------------------
let RemoteChat=async function(session){
	let nodeName,callAgent,callArg,checkUpdate;
	const $ln=session.language||"EN";let context,globalContext;
	let self;
	let Exec;
	/*#{1ICJD7Q850LocalVals*/
	/*}#1ICJD7Q850LocalVals*/
	
	function parseAgentArgs(input){
		if(typeof(input)=='object'){
			nodeName=input.nodeName;
			callAgent=input.callAgent;
			callArg=input.callArg;
			checkUpdate=input.checkUpdate;
		}else{
			nodeName=undefined;
			callAgent=undefined;
			callArg=undefined;
			checkUpdate=undefined;
		}
		/*#{1ICJD7Q850ParseArgs*/
		/*}#1ICJD7Q850ParseArgs*/
	}
	
	/*#{1ICJD7Q850PreContext*/
	/*}#1ICJD7Q850PreContext*/
	globalContext=session.globalContext;
	context={};
	/*#{1ICJD7Q850PostContext*/
	/*}#1ICJD7Q850PostContext*/
	let agent,segs={};
	segs["Exec"]=Exec=async function(input){//:1ICSOGS7J0
		let result=input
		/*#{1ICSOGS7J0Code*/
		result=await RemoteSession.exec(session,nodeName,callAgent,callArg,{checkUpdate:!!checkUpdate});
		/*}#1ICSOGS7J0Code*/
		return {result:result};
	};
	Exec.jaxId="1ICSOGS7J0"
	Exec.url="Exec@"+agentURL
	
	agent={
		isAIAgent:true,
		session:session,
		name:"RemoteChat",
		url:agentURL,
		autoStart:true,
		jaxId:"1ICJD7Q850",
		context:context,
		livingSeg:null,
		execChat:async function(input/*{nodeName,callAgent,callArg,checkUpdate}*/){
			let result;
			parseAgentArgs(input);
			/*#{1ICJD7Q850PreEntry*/
			/*}#1ICJD7Q850PreEntry*/
			result={seg:Exec,"input":input};
			/*#{1ICJD7Q850PostEntry*/
			/*}#1ICJD7Q850PostEntry*/
			return result;
		},
		/*#{1ICJD7Q850MoreAgentAttrs*/
		/*}#1ICJD7Q850MoreAgentAttrs*/
	};
	/*#{1ICJD7Q850PostAgent*/
	/*}#1ICJD7Q850PostAgent*/
	return agent;
};
/*#{1ICJD7Q850ExCodes*/
/*}#1ICJD7Q850ExCodes*/

export default RemoteChat;
export{RemoteChat};