const fs = require('node:fs');
const path = require('node:path');

function prepareDataRoot(root) {
  fs.mkdirSync(path.join(root, 'data'), { recursive: true });
  return root;
}

module.exports = { prepareDataRoot };