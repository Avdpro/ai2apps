import Base64 from "./base64.js";
let panndingCalls=[];
let basePath="/ws/";
let callSeq=0;
const orgFetch=window.fetch;

//----------------------------------------------------------------------------
//JAX用来进行WebAPI调用的类:
var WebAPI={
	path:null,
};

//----------------------------------------------------------------------------
//API调用:
WebAPI.makeCall=function(msg,vo,timeOut=0){
	var msgVO,text,self,path;
	path=this.path||basePath;
	self=this;
	msgVO={msg:msg,vo:vo,seq:callSeq++};
	text=JSON.stringify(msgVO);
	if(timeOut>0){
		return new Promise((okFunc,errFunc)=>{
			let canceled=0;
			window.setTimeout(()=>{
				canceled=1;
				errFunc({code:503,info:"Web API call time out."});
			},timeOut);
			orgFetch(self.path||basePath,{
				method: 'POST',
				cache: 'no-cache',
				headers: {
					'Content-Type': 'application/json'
				},
				body:text
			}).then(res=>{
				if(!canceled){
					okFunc(res.json());
				}
			}).catch(err=>{
				if(!canceled){
					errFunc(err);
				}
			});
		});
	}
	return orgFetch(self.path||basePath,{
		method: 'POST',
		cache: 'no-cache',
		headers: {
			'Content-Type': 'application/json'
		},
		body:text
	}).then(res=>{
		return res.json().then(resVO=>{
			if(!("code" in resVO)){
				resVO.code=res.status;
			}
			return resVO;
		});
	});
};

//----------------------------------------------------------------------------
//设置APIPath:
WebAPI.setAPIPath=function(path){
	this.path=path;
};

//----------------------------------------------------------------------------
//得到API的Path
WebAPI.getPath=async function(){
	let vo;
	if(this.path){
		return this.path;
	}
	vo=await this.makeCall("apiPath",{});
	if(vo.code===200){
		this.path=vo.path;
		return this.path;
	}
	return null;
};

//----------------------------------------------------------------------------
WebAPI.fetch=async function(url,options){
	let msgVO,callVO,text,body;
	callVO={
		url:url,
		...options
	};
	msgVO={
		msg:"WebFetch",vo:callVO,seq:callSeq++
	};
	body=callVO.body;
	if(body){
		if(body instanceof Uint8Array){
			body=Base64.encode(body);
		}else if(typeof(body)==="string"){
			body=Base64.encode(body);
		}else if(body instanceof ArrayBuffer){
			body=Base64.encode(body);
		}else if(typeof(body)==="object"){
			body=JSON.stringify(body);
			body=Base64.encode(body);
		}
		callVO.body=body;
	}
	text=JSON.stringify(msgVO);
	return orgFetch(self.path||basePath,{
		method: 'POST',
		cache: 'no-cache',
		headers: {
			'Content-Type': 'application/json'
		},
		body:text
	})
};

export default WebAPI;
const webFetch=WebAPI.fetch;
export {WebAPI,webFetch};