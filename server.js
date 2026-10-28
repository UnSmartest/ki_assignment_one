import http from "node:http";
import fs from "node:fs";
import path from "node:path"; 
import Busboy from "busboy";
import { spawn, spawnSync } from "node:child_process";

const userDbPath = "./data/userDB.json";

const signUpPath = "./pages/sign-up.html";
const testPath = "./pages/test.html";
const signInPath = "./pages/sign-in.html";
const documentPath = "./pages/document-upload.html";

const userUploadsFolder = "./user_uploads";
const encryptedFolder = "./encrypted";
const stylepath = "./pages/style.css";

// Ensure dirs
if (!fs.existsSync("./data")) fs.mkdirSync("./data");
if (!fs.existsSync("./user_uploads")) fs.mkdirSync("./user_uploads");
if (!fs.existsSync("./encrypted")) {
    fs.mkdirSync("./encrypted");
    fs.mkdirSync("./encrypted/AES");
    fs.mkdirSync("./encrypted/DES");
    fs.mkdirSync("./encrypted/RC4");
}
if (!fs.existsSync(userDbPath)) {
    fs.writeFileSync(userDbPath, JSON.stringify({users: []}, null, 2));
}

function readJson(file) {
    try {
        return JSON.parse(fs.readFileSync(file, "utf-8"));
    } catch {
        return file === userDbPath ? {users: []} : {};
    }
}

function writeJson(file, data) {
    fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

// Usernames end up in file names, so keep them simple
const USERNAME_RE = /^[A-Za-z0-9_-]{1,32}$/;
const hasUser = (db, name) => (db.users || []).some(u => u.usernameText === name);

// Run a python script, send `input` to its stdin (so secrets never show up in the command line)
function runPython(args, input = "") {
    return new Promise((resolve, reject) => {
        const py = spawn("python", args);
        let out = "", err = "";
        py.stdout.on("data", d => out += d);
        py.stderr.on("data", d => err += d);
        py.on("error", reject);
        py.on("close", code => code === 0 ? resolve(out) : reject(new Error(err || out || `exit ${code}`)));
        py.stdin.end(input);
    });
}

// One-time migration: encrypt passwords left over from the old (plaintext) userDB.json
{
    const db = readJson(userDbPath);
    let changed = false;
    for (const u of db.users || []) {
        if (u.passwordText === undefined) continue;
        const r = spawnSync("python", ["py_files/crypto_user.py", "encrypt_password", u.usernameText],
                            { input: u.passwordText, encoding: "utf-8" });
        if (r.status === 0) {
            u.passwordEnc = r.stdout.trim();
            delete u.passwordText;
            changed = true;
        } else {
            console.error(`[MIGRATE ERR] ${u.usernameText}: ${r.stderr || r.stdout}`);
        }
    }
    if (changed) writeJson(userDbPath, db);
}

// Saves are queued so two sections saved at the same time can't collide
let saveQueue = Promise.resolve();

const server = http.createServer((req, res) => {
    // Static
    if (req.method === "GET" && req.url === "/style.css") {
        res.writeHead(200, { "Content-Type": "text/css" });
        fs.createReadStream(stylepath).pipe(res);
        return;
    }
    if (req.method === "GET" && req.url.startsWith("/img/")) {
        const imagePath = "./pages" + req.url;
        res.writeHead(200, { "Content-Type": "image/jpeg" });
        fs.createReadStream(imagePath).pipe(res);
        return;
    }
    
    if(req.method === "GET" && req.url === "/"){ 
        res.writeHead(200, {"Content-Type": "text/html"});
        fs.createReadStream(signUpPath).pipe(res);
        return;
    }
    if(req.method === "GET" && req.url === "/test"){ 
        res.writeHead(200, {"Content-Type": "text/html"});
        fs.createReadStream(testPath).pipe(res);
        return;
    }
    if(req.method === "GET" && req.url === "/sign-in"){ 
        res.writeHead(200, {"Content-Type": "text/html"});
        fs.createReadStream(signInPath).pipe(res);
        return;
    }
    if(req.method === "GET" && req.url === "/document-upload"){
        res.writeHead(200, {"Content-Type": "text/html"});
        fs.createReadStream(documentPath).pipe(res);
        return;
    }
    if(req.method === "GET" && req.url === "/users"){ 
        const names = (readJson(userDbPath).users || []).map(u => ({ usernameText: u.usernameText }));
        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ users: names }));
        return;
    }

    // Sign up (password is stored AES-encrypted, never in plaintext)
    if(req.method === "POST" && req.url === "/sign-up"){ 
        let body = "";
        req.on("data", (chunk) => { body += chunk.toString(); });
        req.on("end", async () => {
            try{
                const formData = new URLSearchParams(body);
                const usernameText = formData.get("usernameText") || "";
                const passwordText = formData.get("passwordText") || "";

                if (!USERNAME_RE.test(usernameText) || !passwordText) {
                    res.writeHead(400, { "Content-Type": "application/json" });
                    res.end(JSON.stringify({ error: "Username may only contain letters, numbers, _ and - (max 32)" }));
                    return;
                }
                if (hasUser(readJson(userDbPath), usernameText)) {
                    res.writeHead(409, { "Content-Type": "application/json" });
                    res.end(JSON.stringify({ error: "Username already exists" }));
                    return;
                }

                const passwordEnc = (await runPython(["py_files/crypto_user.py", "encrypt_password", usernameText], passwordText)).trim();

                const dbData = readJson(userDbPath);   // re-read: file may have changed while python ran
                if (!dbData.users) dbData.users = [];
                if (hasUser(dbData, usernameText)) {
                    res.writeHead(409, { "Content-Type": "application/json" });
                    res.end(JSON.stringify({ error: "Username already exists" }));
                    return;
                }
                dbData.users.push({ usernameText, passwordEnc });
                writeJson(userDbPath, dbData);

                res.writeHead(201, { "Content-Type": "application/json" });
                res.end(JSON.stringify({ success: true }));
            } catch (error) {
                console.error(`[PY ERR]: ${error.message}`);
                res.writeHead(400, { "Content-Type": "application/json" });
                res.end(JSON.stringify({ error: "Invalid request"}));
            }
        });
        return;
    }

    // Sign in (python decrypts the stored password and logs it as a Decryption)
    if(req.method === "POST" && req.url === "/sign-in"){
        let body = "";
        req.on("data", (chunk) => { body += chunk.toString(); });
        req.on("end", async () => {
            const formData = new URLSearchParams(body);
            const usernameText = formData.get("usernameText") || "";
            const passwordText = formData.get("passwordText") || "";
            const user = (readJson(userDbPath).users || []).find(u => u.usernameText === usernameText);
            if (!user) {
                res.writeHead(404, { "Content-Type": "application/json" });
                res.end(JSON.stringify({ error: "username doesn't exist" }));
                return;
            }
            try {
                const out = await runPython(["py_files/crypto_user.py", "check_password", usernameText, user.passwordEnc], passwordText);
                if (out.trim() === "OK") {
                    res.writeHead(200, { "Content-Type": "application/json" });
                    res.end(JSON.stringify({ success: true }));
                } else {
                    res.writeHead(401, { "Content-Type": "application/json" });
                    res.end(JSON.stringify({ error: "password is incorrect" }));
                }
            } catch (e) {
                console.error(`[PY ERR]: ${e.message}`);
                res.writeHead(500, { "Content-Type": "application/json" });
                res.end(JSON.stringify({ error: "sign in failed" }));
            }
        });
        return;
    }

    // Get user registration data (decrypted via python)
    if(req.method === "GET" && req.url.startsWith("/user-data/")){
        const username = decodeURIComponent(req.url.split("/user-data/")[1]);
        const py = spawn("python", ["py_files/crypto_user.py", "decrypt_user", username, "AES"]);
        let out = "";
        let err = "";
        py.stdout.on("data", d => out += d);
        py.stderr.on("data", d => err += d);
        py.on("close", () => {
            try {
                const data = JSON.parse(out);
                res.writeHead(200, { "Content-Type": "application/json" });
                res.end(JSON.stringify(data));
            } catch {
                res.writeHead(404, { "Content-Type": "application/json" });
                res.end(JSON.stringify({ error: "No data found" }));
            }
        });
        return;
    }

    // Save user registration data per section (encrypted with AES, DES and RC4; no plaintext copy is kept)
    if(req.method === "POST" && req.url === "/save-user-data"){
        let body = "";
        req.on("data", (chunk) => { body += chunk.toString(); });
        req.on("end", () => {
            let payload;
            try { payload = JSON.parse(body); } catch { payload = null; }
            const { username, section, data } = payload || {};
            if (!username || !section || !data || typeof data !== "object") {
                res.writeHead(400, { "Content-Type": "application/json" });
                res.end(JSON.stringify({ error: "Invalid data" }));
                return;
            }
            saveQueue = saveQueue
                .then(() => runPython(["py_files/crypto_user.py", "save_section", username, section], JSON.stringify(data)))
                .then((out) => {
                    console.log(`[PY]: ${out}`);
                    res.writeHead(200, { "Content-Type": "application/json" });
                    res.end(JSON.stringify({ success: true }));
                })
                .catch((e) => {
                    console.error(`[PY ERR]: ${e.message}`);
                    res.writeHead(500, { "Content-Type": "application/json" });
                    res.end(JSON.stringify({ error: "Could not save" }));
                });
        });
        return;
    }

    // View file: /view-file/<username>/<filename>
    // python decrypts the AES copy AND writes the "Decryption" line to crypto_log.txt / crypto_state.txt
    if(req.method === "GET" && req.url.startsWith("/view-file/")){
        let username, filename;
        try {
            [username, filename] = req.url.split("?")[0].split("/view-file/")[1].split("/").map(decodeURIComponent);
        } catch {}
        if (!username || !filename) {
            res.writeHead(400);
            res.end("Bad request");
            return;
        }

        const ext = path.extname(filename).toLowerCase();
        let contentType = "application/octet-stream";
        if (ext === ".jpg" || ext === ".jpeg") contentType = "image/jpeg";
        else if (ext === ".png") contentType = "image/png";
        else if (ext === ".pdf") contentType = "application/pdf";
        else if (ext === ".mp4") contentType = "video/mp4";
        else if (ext === ".txt") contentType = "text/plain";

        const py = spawn("python", ["py_files/file_encrypt.py", "decrypt_file", username, filename]);
        const chunks = [];
        py.stdout.on("data", c => chunks.push(c));
        py.stderr.on("data", d => console.error(`[PY ERR]: ${d}`));
        py.on("error", () => {
            if (res.headersSent) return;
            res.writeHead(500);
            res.end("Error");
        });
        py.on("close", (code) => {
            if (res.headersSent) return;
            if (code !== 0) {
                res.writeHead(404);
                res.end("Not found");
                return;
            }
            const buf = Buffer.concat(chunks);
            res.writeHead(200, { "Content-Type": contentType, "Content-Length": buf.length });
            res.end(buf);
        });
        return;
    }

        // Upload file with validation
    // The page sends username + field BEFORE the file, so they are known when the file arrives.
    // We answer only AFTER the file is fully written AND encrypted.
    if(req.method === "POST" && req.url === "/upload-file"){
        const busboy = Busboy({headers: req.headers});
        let uploadedFilename = null;
        let username = null;
        let field = null;
        const pending = [];

        const fail = (code, msg) => {
            if (res.headersSent) return;
            res.writeHead(code, {"Content-Type": "application/json"});
            res.end(JSON.stringify({error: msg}));
        };

        busboy.on("field", (name, val) => {
            if (name === "username") username = val;
            if (name === "field") field = val;
        });

        busboy.on("file", (fieldname, file, info) => {
            const filename = path.basename(info.filename || "");   // no ../ tricks
            const ext = path.extname(filename).toLowerCase();

            if (!filename ||
                (field === "nationalId" && ![".jpg", ".jpeg", ".png"].includes(ext)) ||
                ((field === "transcript" || field === "motivation") && ![".pdf", ".docx", ".xls", ".xlsx"].includes(ext)) ||
                (field === "video" && ext !== ".mp4")) {
                file.resume();
                return;
            }

            uploadedFilename = filename;
            const writeStream = fs.createWriteStream(path.join(userUploadsFolder, filename));
            pending.push(new Promise((resolve, reject) => {
                writeStream.on("finish", resolve);
                writeStream.on("error", reject);
            }));
            file.pipe(writeStream);
        });

        busboy.on("close", async () => {
            try {
                await Promise.all(pending);
                if (!uploadedFilename || !username || !USERNAME_RE.test(username)) {
                    return fail(400, "Invalid file or username");
                }
                await runPython(["py_files/file_encrypt.py", "encrypt_file", username, uploadedFilename, field || "general"]);
                res.writeHead(201, {"Content-Type": "application/json"});
                res.end(JSON.stringify({message: "File uploaded and encrypted", filename: uploadedFilename}));
            } catch (e) {
                console.error(`[PY ERR]: ${e.message}`);
                fail(500, "Could not store file");
            }
        });

        req.pipe(busboy);
        return;
    }

});

server.listen(3000, () => {
    console.log("Go to http://localhost:3000\n");
})
