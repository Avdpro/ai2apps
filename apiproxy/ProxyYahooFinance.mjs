import {ApiProxy,apiProxy} from './ApiProxy.mjs';
import yahooFinance from 'yahoo-finance2';
import ProxyCall from '../util/ProxyCall.js'
const { callProxy,proxyCall }=ProxyCall;

let ProxyYahooFinance,proxyYahooFinance;

ProxyYahooFinance=function(){
	ApiProxy.call(this);
}
proxyYahooFinance=ProxyYahooFinance.prototype=Object.create(apiProxy);
proxyYahooFinance.constructor=ProxyYahooFinance;

proxyYahooFinance.proxy=async function(req,res){
	let reqVO=req.body.vo;
	let url=reqVO.url;
	if(!url.startsWith("https://query1.finance.yahoo.com")){
		return null;
	}
	await proxyCall(req,res,null);
	return true;
};
export default ProxyYahooFinance;
export {ProxyYahooFinance};