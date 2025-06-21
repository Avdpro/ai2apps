
async function InvokeApi(api,reqVO,...args){
	let pms,callback,callerror,res;
	if(!api){
		return "API-NOT-FOUND";
	}
	pms=new Promise((resolve, reject)=>{
		callback=resolve;
		callerror=reject;
	})
	res={
		async json(vo){
			callback(vo);
		}
	};
	try{
		api({body:{vo:reqVO}},res,null,...args);
	}catch (err){
		callback({code:500,info:err});
	}
	return await pms;
}

export default InvokeApi;
export {InvokeApi};