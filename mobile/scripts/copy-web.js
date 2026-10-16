// Copies the built web app (../docs) into mobile/www, which is what Capacitor packages.
const fs = require("fs"), path = require("path");
const src = path.join(__dirname, "..", "..", "docs"), dst = path.join(__dirname, "..", "www");
fs.rmSync(dst, { recursive: true, force: true });
fs.cpSync(src, dst, { recursive: true });
console.log("copied", src, "->", dst);
