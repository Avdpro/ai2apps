import {makeNotify} from "./utils/events.js";
import {WebAPI,webFetch} from "./utils/webAPI.js";

//CokeCodes could API helper:
let CokeNT=function(){
	makeNotify(this);
	this.loginVO=null;				//Cloud-Login-VO
	this.loginDone=0;				//Is login done and ok
	this.loginPreview=false;		//Is logined as a preview user?
	this.previewVO=null;			//Preview login-info
	this.checkLoginTimer=null;		//Timer to check login
};
let cokeNT=CokeNT.prototype={};


//----------------------------------------------------------------------------
//Genterate a string's SHA code.
let digestMessage=cokeNT.digestMessage=async function(message) {
	const msgUint8 = new TextEncoder().encode(message);                           // encode as (utf-8) Uint8Array
	const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);           // hash the message
	const hashArray = Array.from(new Uint8Array(hashBuffer));                     // convert buffer to byte array
	const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join(''); // convert bytes to hex string
	return hashHex;
};

//----------------------------------------------------------------------------
//User login callVO={email:string,passwordSHA:string}
cokeNT.login=async function(callVO){
	let vo,self,savedVO;
	let time;

	time=Date.now();
	self=this;
	if(callVO){
		let sha=callVO.passwordSHA;
		if(sha){
			callVO.time=time;
			callVO.passwordSHA=await digestMessage(""+time+sha);
		}
	}else{
		savedVO=this.loadLoginInfo();
		if(!savedVO || !savedVO.userId){
			throw "No saved login info.";
		}
		callVO={
			"userId":savedVO.userId,
			"time":Date.now(),
		};
		if(savedVO.token){
			if(time>savedVO.tokenExpire){
				//token expired:
				this.loginVO=null;
				this.loginDone=0;
				localStorage.removeItem("LoginVO");
				throw "Login token is expired.";
			}
			callVO.token=savedVO.token;
		}else{
			//没有token
			this.loginVO=null;
			this.loginDone=0;
			localStorage.removeItem("LoginVO");
			throw "Login token is invalid.";
		}
	}
	vo=await WebAPI.makeCall("apiPath",{});
	if(vo && vo.path){
		let tabOS;
		tabOS=window.tabOS;
		WebAPI.setAPIPath(vo.path);
		vo=await WebAPI.makeCall("userLogin",callVO);
		if(vo.code===200){
			vo.apiPath=WebAPI.path;
			self.saveLoginInfo(vo);	
			this.loginDone=1;
			this.loginVO=vo;
			this.userId=vo.userid;
			this.emitNotify("Online");
			if(tabOS){
				tabOS.emitGlobalNotify("Online");
			}
			return true;
		}else{
			if(this.loginDone){
				this.emitNotify("Offline");
				if(tabOS){
					tabOS.emitGlobalNotify("Offline");
				}
			}
			this.loginVO=null;
			this.loginDone=0;
			localStorage.removeItem("LoginVO");
			throw new Error(`Login error ${vo.code}: ${vo.info}`);
		}
	}
	throw new Error("Login error: can't get API-Path.");
};

//----------------------------------------------------------------------------
//Log out cokecodes:
cokeNT.logout=async function(){
	let tabOS=window.tabOS;
	if(this.loginDone){
		localStorage.setItem("LastAccount",this.loginVO.email);
	}
	this.loginVO=null;
	this.loginDone=0;
	localStorage.removeItem("LoginVO");
	this.emitNotify("Offline");
	if(tabOS){
		tabOS.emitGlobalNotify("Offline");
	}
	return true;
};

//----------------------------------------------------------------------------
cokeNT.getLastAccount=function(){
	return localStorage.getItem("LastAccount");
};

//----------------------------------------------------------------------------
//Check if logined://
cokeNT.checkLogin=async function(readInfo=false,checkNT=false){
	let loginVO,time,tabOS;
	tabOS=window.tabOS;
	if(this.checkLoginTimer){
		clearTimeout(this.checkLoginTimer);
		this.checkLoginTimer=null;
	}
	if(this.loginDone && this.loginVO &&!readInfo){
		return true;
	}
	time=Date.now();
	loginVO=this.loadLoginInfo();
	if(!loginVO){
		this.loginVO=null;
		if(this.loginDone){
			this.loginDone=0;
			this.emitNotify("Offline");
		}
		localStorage.removeItem("LoginVO");
		return false;
	}
	if(!loginVO.apiPath || !loginVO.userId || !loginVO.token || loginVO.tokenExipre<=time){
		this.loginVO=null;
		if(this.loginDone){
			this.loginDone=0;
			this.emitNotify("Offline");
		}
		localStorage.removeItem("LoginVO");
		return false;
	}
	this.loginVO=loginVO;
	if(checkNT){
		let res;
		try{
			res=await this.makeCall("userCurrency",{});
			if(res && res.code===403){
				localStorage.removeItem("LoginVO");
			}
			if(!res || res.code!==200){
				throw "Offline";
			}
			loginVO.coins=res.coins||0;
			loginVO.points=res.points||0;
		}catch(err){
			this.loginDone=0;
			this.emitNotify("Offline");
			if(tabOS){
				tabOS.emitGlobalNotify("Offline");
			}
			return false;
		}
	}
	if(!this.loginDone){
		this.loginDone=1;
		this.emitNotify("Online");
	}
	return true;
};

//----------------------------------------------------------------------------
cokeNT.maybePreview=async function(){
	let voText,vo;
	let res;
	if(this.loginDone && this.loginVO){
		return true;
	}
	voText=localStorage.getItem("PreviewLogin");
	if(!voText){
		this.loginPreview=false;
		return false;
	}
	try{
		vo=JSON.parse(voText);
	}catch(err){
		this.loginPreview=false;
		return false;
	}
	try{
		res=await this.makeCall("previewLogin",vo);
		if(!res || res.code!==200){
			this.loginPreview=false;
			return false;
		}
	}catch(err){
		this.loginPreview=false;
		return false;
	}
	this.loginPreview=true;
	this.previewVO=vo;
	return true;
};

//----------------------------------------------------------------------------
//Save login info:
cokeNT.saveLoginInfo=function(vo){
	let voText;
	this.loginVO=vo;
	voText=JSON.stringify(vo);
	localStorage.setItem("LoginVO",voText);
};

//----------------------------------------------------------------------------
//Read login info
cokeNT.loadLoginInfo=function(){
	let voText,vo;
	voText=localStorage.getItem("LoginVO");
	if(voText){
		vo=JSON.parse(voText);
		this.loginVO=vo;
		return vo;
	}
	return null;
};

//----------------------------------------------------------------------------
//Register a new user: regVO={email:string,passwordSHA:string,name:string}
cokeNT.register=async function(regVO){
	var self,vo,tabOS;
	self=this;
	tabOS=window.tabOS;
	vo=await WebAPI.makeCall("userReg",regVO);
	if(vo.code===200){
		vo.apiPath=await WebAPI.getPath();
		self.saveLoginInfo(vo);	
		self.loginDone=1;
		self.loginVO=vo;
		self.userId=vo.userid;
		self.emitNotify("Online");
		if(tabOS){
			tabOS.emitGlobalNotify("Online");
		}
		return true;
	}else{
		throw "Register error "+vo.code+": "+vo.info;
	}
	return false;
};

//----------------------------------------------------------------------------
//Make a call, if logined, append userId and token
cokeNT.makeCall=async function(msg,vo,timeout=0){
	if(this.loginVO){
		vo.userId=this.loginVO.userId;
		vo.token=this.loginVO.token;
	}else{
		let pvVO=this.previewVO;
		if(pvVO){
			vo.pvUserId=pvVO.userId;
			vo.pvSlot=pvVO.slot;
			vo.pvKey=pvVO.key;
		}
	}
	try{
		return await WebAPI.makeCall(msg,vo,timeout);
	}catch(e){
		return {code:0,info:""+e};
		/*if(e.code===503){
			//TODO: Network error.
		}
		throw e;*/
	}
};

let theCokeNT=new CokeNT(null);
let tabNT=theCokeNT;
export {theCokeNT as cokeNT,tabNT,webFetch};
export default theCokeNT;