require('dotenv').config();

var createError = require('http-errors');
var express = require('express');
var path = require('path');
var cookieParser = require('cookie-parser');
var logger = require('morgan');
const WebSocket = require('ws');
//const cors = require('cors');
var envCfg=null;

var indexRouter = require('./routes/index');
var swrootRouter= require('./routes/swroot');
var wsRouter=require('./routes/ws');

var app = express();
let AgentHub_FileLibPath=process.env.AGENT_HUB_FileLibDir||process.env.AABOTS_FileLibPath||"filelib";
if(!path.isAbsolute(AgentHub_FileLibPath)){
	AgentHub_FileLibPath=path.join(__dirname,AgentHub_FileLibPath);
}
//app.use(cors());
app.initCokeCodesApp=async function(){
	let mongoDB,mongoURL;

	envCfg=app.get("env");
	mongoURL=app.get("mongoURL")||"mongodb://127.0.0.1:20000";
	console.log("Application env: "+envCfg);
	// view engine setup
	app.set('views', path.join(__dirname, 'views'));
	app.set('view engine', 'pug');
	app.set("AppHomePath",__dirname);

	app.use(logger('dev'));
	
	app.use(express.json({limit: '200mb'}));
	app.use(express.urlencoded({limit: '200mb', extended: false }));
	app.use(cookieParser());
	app.use(express.static(path.join(__dirname, 'public')));
	app.use("/-hub",express.static(AgentHub_FileLibPath));
	//app.use("/-+hubfile",express.static(AgentHub_FileLibPath));

	mongoDB=null;
	app.set('WebSocketSelectorMap',new Map());

	app.use('/', indexRouter);
	app.use('//', swrootRouter);
	app.use('/ws', wsRouter(app));

	// ModelHunt sync: browser pushes model.json to local filesystem
	{
		const fsp = require('fs').promises;
		const os = require('os');
		const modelHuntFile = require('path').join(os.homedir(), '.modelhunt', 'model.json');
		const corsHeaders = (res) => {
			res.setHeader('Access-Control-Allow-Origin', '*');
			res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
			res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
		};
		app.options('/api/modelhunt/sync', (req, res) => { corsHeaders(res); res.sendStatus(204); });
		app.post('/api/modelhunt/sync', async (req, res) => {
			corsHeaders(res);
			try {
				await fsp.mkdir(require('path').dirname(modelHuntFile), {recursive: true});
				await fsp.writeFile(modelHuntFile, JSON.stringify(req.body, null, '\t'));
				res.json({ok: true});
			} catch(e) {
				res.status(500).json({ok: false, error: e.message});
			}
		});
		app.options('/api/modelhunt/models', (req, res) => { corsHeaders(res); res.sendStatus(204); });
		app.get('/api/modelhunt/models', async (req, res) => {
			corsHeaders(res);
			try {
				const data = await fsp.readFile(modelHuntFile, 'utf8');
				res.json(JSON.parse(data));
			} catch(e) {
				res.status(404).json({ok: false, error: 'not found'});
			}
		});

		// SSE: frontend subscribes to push events
		const sseClients = new Set();
		app.get('/api/modelhunt/events', (req, res) => {
			corsHeaders(res);
			res.setHeader('Content-Type', 'text/event-stream');
			res.setHeader('Cache-Control', 'no-cache');
			res.setHeader('Connection', 'keep-alive');
			res.flushHeaders();
			sseClients.add(res);
			req.on('close', () => sseClients.delete(res));
		});

		// Install trigger: external caller POSTs { model }, SSE pushes to frontend
		// AND we stream logs back to the caller
		const installWaiters = new Map(); // taskId -> res
		app.options('/api/modelhunt/install', (req, res) => { corsHeaders(res); res.sendStatus(204); });
		app.post('/api/modelhunt/install', (req, res) => {
			corsHeaders(res);
			const { model } = req.body || {};
			if (!model) return res.status(400).json({ ok: false, error: 'missing model' });
			if (sseClients.size === 0) return res.status(503).json({ ok: false, error: 'AI2Apps is not running or page not open' });

			// Set up SSE to stream logs back to curl/Claude Code
			res.setHeader('Content-Type', 'text/event-stream');
			res.setHeader('Cache-Control', 'no-cache');
			res.setHeader('Connection', 'keep-alive');
			res.flushHeaders();

			const taskId = Date.now().toString();
			installWaiters.set(taskId, res);
			res.on('close', () => installWaiters.delete(taskId));

			// Notify frontend to start install
			const data = `data: ${JSON.stringify({ type: 'install', model, taskId })}\n\n`;
			sseClients.forEach(client => client.write(data));
			res.write(`data: {"status": "started", "clients": ${sseClients.size}}\n\n`);
		});

		// Delete trigger: external caller POSTs { model }, SSE pushes to frontend
		app.options('/api/modelhunt/delete', (req, res) => { corsHeaders(res); res.sendStatus(204); });
		app.post('/api/modelhunt/delete', (req, res) => {
			corsHeaders(res);
			const { model } = req.body || {};
			if (!model) return res.status(400).json({ ok: false, error: 'missing model' });
			if (sseClients.size === 0) return res.status(503).json({ ok: false, error: 'AI2Apps is not running or page not open' });

			res.setHeader('Content-Type', 'text/event-stream');
			res.setHeader('Cache-Control', 'no-cache');
			res.setHeader('Connection', 'keep-alive');
			res.flushHeaders();

			const taskId = Date.now().toString();
			installWaiters.set(taskId, res);
			res.on('close', () => installWaiters.delete(taskId));

			const data = `data: ${JSON.stringify({ type: 'delete', model, taskId })}\n\n`;
			sseClients.forEach(client => client.write(data));
			res.write(`data: {"status": "started", "clients": ${sseClients.size}}\n\n`);
		});


		app.options('/api/modelhunt/test', (req, res) => {
		corsHeaders(res);
		res.sendStatus(204);
		});

		app.post('/api/modelhunt/test', (req, res) => {
			corsHeaders(res);

			const { model, task } = req.body || {};
			if (!model) return res.status(400).json({ ok: false, error: 'missing model' });

			if (sseClients.size === 0) {
				return res.status(503).json({ ok: false, error: 'AI2Apps is not running or page not open' });
			}

			res.setHeader('Content-Type', 'text/event-stream');
			res.setHeader('Cache-Control', 'no-cache');
			res.setHeader('Connection', 'keep-alive');
			res.flushHeaders();

			const taskId = Date.now().toString();
			installWaiters.set(taskId, res);
			res.on('close', () => installWaiters.delete(taskId));

			const data = `data: ${JSON.stringify({ type: 'test', model, task, taskId })}\n\n`;
			sseClients.forEach(client => client.write(data));

			res.write(`data: {"status":"started","clients":${sseClients.size}}\n\n`);
		});

		// Frontend sends logs here
		app.options('/api/modelhunt/log', (req, res) => { corsHeaders(res); res.sendStatus(204); });
		app.post('/api/modelhunt/log', (req, res) => {
			corsHeaders(res);
			const { taskId, log, done, error } = req.body || {};
			const waiter = installWaiters.get(taskId);
			if (waiter) {
				waiter.write(`data: ${JSON.stringify(req.body)}\n\n`);
				if (done || error) {
					waiter.end();
					installWaiters.delete(taskId);
				}
			}
			res.json({ ok: true });
		});
	}
	
	//Shadow chat:
	{
		if (process.env.SHADOW_CHAT === "TRUE") {
			const shadowRouter = express.Router();
			await (async () => {
				const esmModule = await import('./handlers/APIShadowChat.mjs');
				esmModule.default(app, shadowRouter);
			})();
			app.use('/shadow', shadowRouter);
		}
	}
	
	//Payments:
	{
		if(process.env.PAYMENT==="TRUE") {
			const paymentsRouter = express.Router();
			//Paypal handlers::
			await (async () => {
				const esmModule = await import('./payments/paypal.mjs');
				esmModule.default(app, paymentsRouter);
			})();
			
			//Stripe-WX handlers:
			/*await (async () => {
				const esmModule = await import('./payments//stripe_ap.mjs');
				esmModule.default(app, paymentsRouter);
			})();*/
			app.use('/payments', paymentsRouter);
		}else{
			//Forward all calls to root:
			await (async () => {
				const esmModule = await import('./payments/local.mjs');
				esmModule.default(app);
			})();
		}
	}
	// catch 404 and forward to error handler
	app.use(function(req, res, next) {
		next(createError(404));
	});

	// error handler
	app.use(function(err, req, res, next) {
		// set locals, only providing error in development
		res.locals.message = err.message;
		res.locals.error = req.app.get('env') === 'development' ? err : {};

		// render the error page
		res.status(err.status || 500);
		res.render('error');
	});
	
	//Test WebDrive
	if(false){
		await (async () => {
			const esmModule = await import('./rpa/test.mjs');
			esmModule.default();
		})();
	}
};

//---------------------------------------------------------------------------
app.setupWebSocket=async function(server){
	let wss,selectorMap;
	selectorMap=app.get("WebSocketSelectorMap");
	wss=app.wss=new WebSocket.Server({ server:server,maxPayload:100*1024*1024 });
	wss.on('connection',(ws)=>{
		function handleMessage(message){
			let msgJSON,selector;
			if (message instanceof Buffer || message instanceof Uint8Array) {
				message = message.toString();
			}
			if(typeof(message)!=='string'){
				ws.close(1003,"Only JSON-text message allowed");
				return;
			}
			try{
				msgJSON=JSON.parse(message);
			}catch (err){
				ws.close(1003,"Only JSON-text message allowed");
				return;
			}
			if(msgJSON.msg!=="CONNECT"){
				ws.close(1002,"First message must be CONNECT");
				return;
			}
			selector=msgJSON.selector;
			selector=selectorMap.get(selector);
			if(!selector){
				ws.close(1002,"Can't find handler");
				return;
			}
			selector(ws,msgJSON);
			ws.aaConnected=true;
			ws.off('message',handleMessage);
		}
		ws.aaConnected=false;
		ws.on('message',handleMessage);
	});
};

module.exports = app;
