var express = require('express');
const querystring = require('querystring')
var router = express.Router();

/* GET home page. */
router.get('/', function(req, res, next) {
	const queryObj = req.query;
	if(!process.env.dev_mode) {
		queryObj.notdev=1
	}
	const queryString = querystring.stringify(queryObj);
	console.log(`dev_mode:${process.env.dev_mode} index queryString`, queryString);
	if(queryString){
		res.redirect("/setup.html"+"?"+queryString);
	}else {
		res.redirect("/setup.html");
	}
});

module.exports = router;
