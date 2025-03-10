import VFACT from "/@vfact";
import {AppFrame} from "/@homekit/ui/AppFrame.js";

const runMeta={
	type:"app",
	name:"Run Agent",
	caption:"Run Agent",
	main:"/@AgentBuilder/app.html",
	package:"dev",
	catalog:["System"],
	icon:"/@tabos/shared/assets/agent.svg",
	iconApp:null,
	appFrame:{
		main:"/@AgentBuilder/app.html",
		group:"/@AgentBuilder/RunAgent.js",
		title:"Run Agent",
		caption:"Run Agent",
		icon:"/@tabos/shared/assets/agent.svg",
		multiFrame:true,
		width:1200,height:800,
		maxable:false,
	}
};

async function runAgent({agent,agentNode=null,args=null,title="Run Agent",callback=null,callerror=null,embed=null}){
	let app;
	let params={
		title:title||"Run Agent",
		file:agent,agentNode:agentNode,argument:args,callback:callback,callerror:callerror
	};
	app=VFACT.app;
	if(!app){
		let curWin=window;
		while(!app && curWin.parent!==curWin){
			curWin=curWin.parent;
			app=curWin.VFACT.app;
		}
		if(!app){
			return;
		}
	}
	if(!app.newFrameApp){
		if(!app.appFrame){
			return;
		}
		app=app.appFrame.app;
	}
	if(embed && embed.appendNewChild){
		return embed.appendNewChild({
			type:AppFrame(app,runMeta,params,{embed:true}),x:0,y:0
		});
	}else if(app && app.newFrameApp){
		return app.newFrameApp(runMeta,params);
	}
}

async function callAgent({agent,agentNode=null,args=null,title="Run Agent",embed=null}){
	let pms,callback,callerror,result,appFrame;
	pms=new Promise((resolve,reject)=>{
		callback=resolve;
		callerror=reject;
	});
	try{
		appFrame=await runAgent({agent:agent,agentNode:agentNode,args:args,title:title,callback:callback,callerror:callerror,embed:embed});
		appFrame.onNotify("FrameClosed",()=>{callerror("User aborted agent execution.");});
		result=await pms;
		appFrame.close();
		return result;
	}catch(err){
		appFrame.close();
		throw err;		
	}
}

export default runAgent;
export {runAgent,callAgent};