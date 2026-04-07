const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
if (pkg.devDependencies) {
  delete pkg.devDependencies['@emergentbase/visual-edits'];
}
fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
console.log('Cleaned package.json for Docker build');
