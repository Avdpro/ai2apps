import {getUserInfo} from "../util/UserUtils.js";
import followRedirects from "follow-redirects";
import { exec } from 'child_process';
import util from 'util';
const execPromise = util.promisify(exec);
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
	apiMap['RunBashCmd'] = async function(req, res) {
		const reqVO = req.body.vo;
		const cmd = reqVO && reqVO.cmd;
		if (!cmd) {
			res.json({ code: 400, info: "Missing cmd" });
			return;
		}
		try {
			const { stdout, stderr } = await execPromise(cmd, { timeout: 30000, maxBuffer: 1024 * 1024 });
			res.json({ code: 200, stdout: stdout || "", stderr: stderr || "" });
		} catch (err) {
			// exec throws on non-zero exit; still return the output
			res.json({ code: 200, stdout: err.stdout || "", stderr: err.stderr || String(err.message) });
		}
	};

	//-------------------------------------------------------------------
	const bashJobs = new Map();

	apiMap['RunBashCmdStart'] = function(req, res) {
		const cmd = req.body.vo && req.body.vo.cmd;
		if (!cmd) { res.json({code:400, info:'Missing cmd'}); return; }
		const jobId = Date.now() + '-' + Math.random().toString(36).slice(2,8);
		const job = {output:'', done:false};
		bashJobs.set(jobId, job);
		// Use exec (same mechanism as RunBashCmd which is proven to work)
		execPromise(cmd, {timeout:30000, maxBuffer:1024*1024}).then(function(r){
			job.output = (r.stdout||'') + (r.stderr||'');
			job.done = true;
			setTimeout(function(){ bashJobs.delete(jobId); }, 300000);
		}).catch(function(err){
			job.output = (err.stdout||'') + (err.stderr||String(err.message));
			job.done = true;
			setTimeout(function(){ bashJobs.delete(jobId); }, 300000);
		});
		res.json({code:200, jobId});
	};

	apiMap['RunBashCmdPoll'] = function(req, res) {
		const jobId = req.body.vo && req.body.vo.jobId;
		if (!jobId) { res.json({code:400, info:'Missing jobId'}); return; }
		const job = bashJobs.get(jobId);
		if (!job) { res.json({code:404, info:'Job not found'}); return; }
		res.json({code:200, output:job.output, done:job.done});
	};

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
