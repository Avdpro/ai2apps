const express = require('express');
const router = express.Router();

/* GET users listing.*/
module.exports =function(app) {
	router.get('/', function (req, res, next) {
		console.log(req);
		//TODO: check
	});
};