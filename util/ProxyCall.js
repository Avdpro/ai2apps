const followRedirects =require("follow-redirects");

const APIRoot=process.env.APIROOT||"https://www.tab-os.com/ws/";
module.exports = {
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
}