var express = require('express');
var router = express.Router();

/* GET home page. */
router.all('*', function(req, res, next) {
  res.redirect("/setup.html?path="+encodeURIComponent(req.originalUrl));
});

module.exports = router;
