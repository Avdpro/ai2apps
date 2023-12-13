require('dotenv').config();

var createError = require('http-errors');
var express = require('express');
var path = require('path');
var cookieParser = require('cookie-parser');
var logger = require('morgan');
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


module.exports = app;
