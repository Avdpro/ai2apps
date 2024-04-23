var express = require('express');
const querystring = require('querystring')
var router = express.Router();

/* GET home page. */
router.get('/', function(req, res, next) {
	const queryObj = req.query;
	const queryString = querystring.stringify(queryObj);
	if(queryString){
		res.redirect("/setup.html"+"?"+queryString);
	}else {
		res.redirect("/setup.html");
	}
});

module.exports = router;
