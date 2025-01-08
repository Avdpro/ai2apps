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
	
	app.use(express.json({limit: '50mb'}));
	app.use(express.urlencoded({limit: '50mb', extended: false }));
	app.use(cookieParser());
	app.use(express.static(path.join(__dirname, 'public')));

	mongoDB=null;
	app.set('WebSocketSelectorMap',new Map());

	app.use('/', indexRouter);
	app.use('//', swrootRouter);
	app.use('/ws', wsRouter(app));
	
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
};

//---------------------------------------------------------------------------
app.setupWebSocket=async function(server){
	let wss,selectorMap;
	selectorMap=app.get("WebSocketSelectorMap");
	wss=app.wss=new WebSocket.Server({ server:server,maxPayload:10*1024*1024 });
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
