
async function forwardCall(req,res){
	try {
		const targetUrl = new URL(req.originalUrl, 'https://www.ai2apps.com');
		const headers = { ...req.headers };
		delete headers.host;
		const fetchOptions = {
			method: req.method,
			headers,
			body: ['GET', 'HEAD'].includes(req.method) ? undefined : JSON.stringify(req.body),
			redirect: 'manual',
		};
		
		const response = await fetch(targetUrl, fetchOptions);
		
		// 设置响应头（排除 hop-by-hop headers）
		for (const [key, value] of response.headers.entries()) {
			if (!['transfer-encoding', 'content-encoding', 'content-length', 'connection'].includes(key.toLowerCase())) {
				res.setHeader(key, value);
			}
		}
		
		res.status(response.status);
		const buffer = await response.arrayBuffer();
		res.send(Buffer.from(buffer));
	} catch (err) {
		console.error('代理失败:', err);
		res.status(502).send('Bad Gateway');
	}
}

export default function(app) {
	app.use('/payments', async (req, res) => {
		await forwardCall(req,res);
	});
};
