import { EventEmitter } from 'events';
import {inherits} from 'util';

//***************************************************************************
//AABot:
//***************************************************************************
let AABot,aaBot;
{
	AABot = function (botNode) {
		EventEmitter.call(this);
		this.app=botNode.app;
		this.botNode=botNode;
		this.id="";
		this.name = "";
		this.type = "";
		this.active = false;
		this.description = "This is a bot";
	};
	inherits(AABot,EventEmitter);
	aaBot = AABot.prototype;
	
	//-----------------------------------------------------------------------
	aaBot.start=async function(){
	};
	
	//-----------------------------------------------------------------------
	aaBot.stop=async function(){
	};
	
	//-----------------------------------------------------------------------
	aaBot.getInfo=function() {
	};
	
	//-----------------------------------------------------------------------
	aaBot.getStats=async function(){
	
	};
	
	//-----------------------------------------------------------------------
	aaBot.appendMessage=async function(msgVO){
	};
}

export {AABot};
