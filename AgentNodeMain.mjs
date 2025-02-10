import dotEnv from "dotenv";
import pathLib from "path";
import AgentNode from "./agenthub/AgentNode.mjs";

let agentPath=process.argv[2];
let hostAddr=process.argv[3];
let name= process.argv[4];

let envFileName=process.argv[5];
if(envFileName){
	if(envFileName.indexOf("/")>=0){
		dotEnv.config({path:envFileName});
	}else{
		dotEnv.config({path:"./"+envFileName});
	}
}else {
	dotEnv.config();
}
await AgentNode.setupPath();
let agentNode=new AgentNode(agentPath,hostAddr,name);
agentNode.start();


