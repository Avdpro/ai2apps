import {getUserInfo} from "../util/UserUtils.js";
import followRedirects from "follow-redirects";
const DAYTIME=24*3600*1000;

const WEATHERMAP_API_KEY=process.env.WEATHERMAP_API_KEY;
//API for AI calls
export default function(app,router,apiMap) {
	const dbUser = app.get("DBUser");
	let env = app.get("env");
	
	//-------------------------------------------------------------------
	async function makeHttpJSONCall(url,isHTTPS=true,postJSON,headers){
		let apiURL,httpCall,httpOpts,postText;
		
		httpCall=isHTTPS?followRedirects.https:followRedirects.http;
		apiURL=url;
		headers={
			'User-Agent': 'node.js',
			'Accept': 'application/json',
			...headers
		};
		postText=null;
		if(postJSON){
			postText=JSON.stringify(postJSON);
			headers["Content-Type"]="application/json";
			headers["Content-Length"]=Buffer.byteLength(postText);
		}
		httpOpts={
			method:"GET",
			headers: {
				'User-Agent': 'node.js',
				'Accept': 'application/json',
				...headers
			}
		};
		return new Promise(async(resolve,reject)=>{
			const httpReq = httpCall.request(apiURL,httpOpts, (res) => {
				if(res.statusCode!==200){
					reject(`Http error ${res.statusCode}: ${res.statusMessage||"Network Error"}`);
				}
				res.setEncoding('utf8');
				let rawData = '';
				res.on('data', (chunk) => { rawData += chunk; });
				res.on('end', () => {
					try {
						resolve(JSON.parse(rawData));
					}catch (err) {
						reject(err);
					}
				});
			});
			
			httpReq.on('error', (e) => {
				console.error(`problem with request: ${e.message}`);
			});
			if(postText){
				httpReq.write(postText);
			}
			httpReq.end();
		});
		
	}

	//-------------------------------------------------------------------
	//General API calls:
	apiMap['getWeather'] = async function (req, res, next) {
		let reqVO, userId, token, userInfo, weatherJSON,city;
		
		reqVO = req.body.vo;
		userId = reqVO.userId;
		token = reqVO.token;
		city = reqVO.city||"Beijing";
		userInfo=await getUserInfo(req,userId,token);
		if(!userInfo){
			res.json({code:-100,info:"UserId / token error."});
		}
		try{
			weatherJSON=await makeHttpJSONCall(`http://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${WEATHERMAP_API_KEY}`,false);
			res.json({code:200,...weatherJSON});
		}catch (err) {
			res.json({ code: 500, info:""+err});
		}
	};
};
