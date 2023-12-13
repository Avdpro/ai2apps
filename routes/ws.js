var express = require('express');
var chatAI,gitAPI,previewAPI,utilsAPI,fileAPI;
var router = express.Router();
var proxyCall=require('../util/ProxyCall.js').proxyCall;

module.exports =function(app) {
	var apiMap={};
	//Register chatAI:
	import("./APIChatAI.mjs").then((mode)=>{
		chatAI=mode.default;
		chatAI(app,router,apiMap);
	});
	
	//Register fileSync:
	import("./APIFiles.mjs").then((mode)=>{
		fileAPI=mode.default;
		fileAPI(app,router,apiMap);
	});
	//Register UtilsAPI:
	import("./APIUtils.mjs").then((mode)=>{
		utilsAPI=mode.default;
		utilsAPI(app,router,apiMap);
	});
	
	
	/* GET users listing. */
	router.post('/', function (req, res, next) {
		let msg,reqVO,handler,ret;
		reqVO = req.body;
		//console.log(reqVO);
		msg=reqVO.msg;
		switch (reqVO.msg) {
			default:
				handler=apiMap[msg]||proxyCall;
				if(handler){
					try {
						ret=handler(req, res, next);
						if(ret instanceof Promise){
							ret.then(()=>{
								//nothing
							}).catch(e=>{
								console.log(`Request 500 error: ${e}`);
								res.json({code:500,info:""+e});
							});
						}
					}catch(e){
						res.json({code:500,info:""+e});
					}
				}else{
					res.json({code:504,info:`${msg}: handler not found.`});
				}
				break;
		}
	});
	return router;
};
