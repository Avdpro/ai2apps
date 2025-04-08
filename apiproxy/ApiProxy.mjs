//***************************************************************************
//APProxy
//***************************************************************************
let ApiProxy,apiProxy;
{
	const proxys=[];
	ApiProxy = function () {
	};
	apiProxy=ApiProxy.prototype = {}
	
	ApiProxy.regProxy=function(proxy){
		proxys.push(proxy);
	};
	
	ApiProxy.proxy=async function(req,res){
		let pxy,result;
		for(pxy of proxys){
			result=await pxy.proxy(req,res);
			if(result){
				return result;
			}
		}
		return null;
	};
	
	apiProxy.proxy=async function(req,res){
		return null;
	};
}

export default  ApiProxy;
export {ApiProxy, apiProxy};