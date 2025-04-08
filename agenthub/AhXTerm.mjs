import child_process,{spawn} from 'child_process';
import { promisify } from 'util';
import pty from "node-pty";

//----------------------------------------------------------------------------
async function getCondaPath() {
	let execPromise = promisify(child_process.exec);
	try {
		const { stdout, stderr } = await execPromise('conda env list --json');
		const condaVO=JSON.parse(stdout);
		return condaVO.root_prefix;
	} catch (error) {
		console.error('Error fetching conda environments:', error.message);
		return null;
	}
}

//***************************************************************************
//AhXTerm
let nextTermId=1;
let AhXTerm,ahXTerm;
{
	AhXTerm=function(ahNode){
		this.agentNode=ahNode;
		this.system=ahNode.system;
		this.app=ahNode.app;
		this.id=""+(nextTermId++);
		this.sessionId="XTERM_"+this.id;
		this.nodeWS=ahNode.nodeWS;
		this.clientWS=null;
		this.starting=false;
		this.waitPms=null;
		this.buffedData="";
	};
	ahXTerm=AhXTerm.prototype={};
	
	//-----------------------------------------------------------------------
	ahXTerm.start=async function(options,commands){
		let selectorMap,selectCode,callback;
		if(this.waitPms){
			return await this.waitPms;
		}
		selectorMap=this.app.get("WebSocketSelectorMap");
		selectCode=this.sessionId;
		this.waitPms=new Promise((resolve,reject)=>{
			callback=resolve;
		});
		selectorMap.set(selectCode,(ws)=>{
			selectorMap.delete(selectCode);
			this.clientWS=ws;
			ws.on('message',async (message)=>{
				if (message instanceof Buffer || message instanceof Uint8Array) {
					message = message.toString();
				}
				try{
					message=JSON.parse(message);
				}catch{
					message={};
				}
				try{
					switch(message.msg){
						case "Data": {//Client write data into terminal:
							if(this.nodeWS){
								this.nodeWS.send(JSON.stringify({msg:"XTermData",session:this.sessionId,data:message.data}))
							}
							return;
						}
					}
				}catch (err){
					console.log("Handle bot message error:");
					console.error(err);
				}
			});
			
			ws.on('close',async(event)=>{
				this.clientWS=null;
			});
			ws.send(JSON.stringify({msg:"CONNECTED"}));
			callback();
		});
		return await this.waitPms;
	};
	
	//-----------------------------------------------------------------------
	ahXTerm.close=async function(){
		if(this.clientWS){
			await this.clientWS.close();
		}
		this.waitPms=null;
	};
	
	//-----------------------------------------------------------------------
	ahXTerm.write=async function(data){
		let msgVO;
		if(this.clientWS){
			data=this.buffedData+data;
			msgVO={
				msg:"Data",
				data:data
			};
			this.buffedData="";
			await this.sendToClient(msgVO);
		}else{
			this.buffedData+=data;
		}
	};
	
	//-----------------------------------------------------------------------
	ahXTerm.sendToClient=async function(msgVO){
		if(!this.clientWS){
			throw Error("XTerm is not ready.");
		}
		this.clientWS.send(JSON.stringify(msgVO));
	};
}
export default AhXTerm;
export {AhXTerm};