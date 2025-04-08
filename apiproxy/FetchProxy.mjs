import {ApiProxy} from	"./ApiProxy.mjs";
import ProxyYahooFinance from "./ProxyYahooFinance.mjs";

//Register proxies:
ApiProxy.regProxy(new ProxyYahooFinance());

export default ApiProxy;