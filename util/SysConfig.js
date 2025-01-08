const configMap=new Map();
let dbSys=null;
//--------------------------------------------------------------------------
function initSysConfig(app){
	dbSys=app.get("DBSys");
}

//---------------------------------------------------------------------------
async function getSysConfig(cfgName){
	let stub,vo,nowTime,config;
	if(!dbSys){
		return null;
	}
	nowTime=Date.now();
	stub=configMap.get(cfgName);
	if(stub && stub.isReading){
		return stub.config;
	}else if(!stub || (nowTime-stub.time>1000*60)){
		vo={};
		vo._id=cfgName;
		if(stub){
			stub.isReading=true;
		}
		config=await dbSys.findOne(vo);
		stub={time:nowTime,config:config};
		configMap.set(cfgName,stub);
	}
	return stub.config;
}

module.exports= {
	initSysConfig,
	getSysConfig
};
