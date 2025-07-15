/**
 * Module dependencies.
 */

var app = require('./app.js');
var debug = require('debug')('home:server');
var http = require('http');

/**
 * Get port from environment and store in Express.
 */

var port = normalizePort(process.env.PORT || '3105');
app.set("env","dev");
app.set('port', port);

//---------------------------------------------------------------------------
//初始化服务器系统
app.initCokeCodesApp().then(()=>{
	server = http.createServer(app);
	
	server.listen(port);
	server.on('error', onError);
	server.on('listening', onListening);
	
	if(app.setupWebSocket){
		app.setupWebSocket(server);
	}
});

/**
 * Normalize a port into a number, string, or false.
 */

function normalizePort(val) {
	var port = parseInt(val, 10);
	
	if (isNaN(port)) {
		// named pipe
		return val;
	}
	
	if (port >= 0) {
		// port number
		return port;
	}
	
	return false;
}

/**
 * Event listener for HTTP server "error" event.
 */

function onError(error) {
	if (error.syscall !== 'listen') {
		throw error;
	}
	
	var bind = typeof port === 'string'
		? 'Pipe ' + port
		: 'Port ' + port;
	
	// handle specific listen errors with friendly messages
	switch (error.code) {
		case 'EACCES':
			console.error(bind + ' requires elevated privileges');
			process.exit(1);
			break;
		case 'EADDRINUSE':
			console.error(bind + ' is already in use');
			process.exit(1);
			break;
		default:
			throw error;
	}
}

/**
 * Event listener for HTTP server "listening" event.
 */

function onListening() {
	var addr = server.address();
	var bind = typeof addr === 'string'
		? 'pipe ' + addr
		: 'port ' + addr.port;
	debug('Listening on ' + bind);
	console.log(`Node version: ${console.log(process.version)}`);
	console.log(`READY: Server running at http://localhost:${addr.port}`);
}
