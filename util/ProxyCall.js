const followRedirects =require("follow-redirects");

const APIRoot=process.env.APIROOT||"https://www.tab-os.com/ws/";
module.exports = {
	callProxy:async function(api,vo){
		let apiURL, httpOpts, httpReq, postText,callDone,postAPI;
		let pms,callback,callerror;
		
		pms=new Promise((resolve,reject)=>{
			callback=resolve;
			callerror=reject;
		});
		
		callDone=false;
		apiURL = APIRoot;
		postText = JSON.stringify({msg:api,vo:vo});
		httpOpts = {
			method: "POST",
			headers: {
				'User-Agent': 'node.js',
				'Content-Type': 'application/json',
				'Content-Length': Buffer.byteLength(postText),
			}
		};
		if(apiURL.startsWith("http://")){
			postAPI=followRedirects.http;
		}else{
			postAPI=followRedirects.https;
		}
		httpReq = postAPI.request(apiURL, httpOpts, (response) => {
			let data = [];
			if (response.statusCode !== 200) {
				httpReq.destroy();
				if(callback) {
					callback({ code: response.statusCode, info: response.statusMessage || "Network error" });
					callback=null;
				}
				callDone=true;
				return;
			}
			response.on('data', function (chunk) {
				data.push(chunk);
			});
			response.on('end', function () {
				try {
					let buffer = Buffer.concat(data);
					let text = buffer.toString();
					let json = JSON.parse(text);
					callDone=true;
					if(callback) {
						callback(json);
						callback=null;
					}
				} catch (err) {
					callDone=true;
					if(callback) {
						callback({ code: 500, info: "" + err });
						callback=null;
					}
				}
			});
		});
		httpReq.on('error', (e) => {
			if(callback) {
				callback({ code: 500, info: "" + e });
				callback=null;
			}
		});
		httpReq.write(postText);
		httpReq.end();
		return await pms;
	},
	proxyCall:async function (req, res, next) {
		let apiURL, httpOpts, httpReq, postText,callDone,postAPI;
		callDone=false;
		apiURL = APIRoot;
		postText = JSON.stringify(req.body);
		httpOpts = {
			method: "POST",
			headers: {
				'User-Agent': 'node.js',
				'Content-Type': 'application/json',
				'Content-Length': Buffer.byteLength(postText),
			}
		};
		if(apiURL.startsWith("http://")){
			postAPI=followRedirects.http;
		}else{
			postAPI=followRedirects.https;
		}
		httpReq = postAPI.request(apiURL, httpOpts, (response) => {
			let data = [];
			if (response.statusCode !== 200) {
				httpReq.destroy();
				res.json({ code: response.statusCode, info: response.statusMessage || "Network error" });
				callDone=true;
				return;
			}
			response.on('data', function (chunk) {
				data.push(chunk);
			});
			response.on('end', function () {
				try {
					let buffer = Buffer.concat(data);
					let text = buffer.toString();
					let json = JSON.parse(text);
					callDone=true;
					if(json.code===200){
						if(req.body.vo.userId && req.body.vo.token){
							process.env.localUserId=req.body.vo.userId;
							process.env.localUserToken=req.body.vo.token;
						}
					}
					res.json(json);
				} catch (err) {
					callDone=true;
					res.json({ code: 500, info: "" + err });
				}
			});
		});
		httpReq.on('error', (e) => {
			if(!callDone) {
				res.json({ code: 500, info: "" + e });
			}
		});
		httpReq.write(postText);
		httpReq.end();
	}
};
