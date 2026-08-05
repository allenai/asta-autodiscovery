const Module = require('node:module');

Module._initPaths();
require(process.env.AUTODISCOVERY_UI_SERVER);