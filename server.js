import http from "node:http";
import fs from "node:fs";
import url from "node:url";

const dbPath = "./unecrypted/userDB.json";
const signInPath = "./sign-in.html";

const server = http.createServer((req, res) => {
    //ok. so this is just like framework programming. ok.
    //which means the request consists of method, path, and body
    //right now we only need POST and prob "/sign-in", and the JSON data
    
    if(req.method === "GET" && req.url === "/"){
        res.writeHead(200, {"Content-Type": "text/html"});
        fs.createReadStream(signInPath).pipe(res);
        return;
    }

    if(req.method === "POST" && req.url === "/sign-in"){
        console.log("POST method found & it's a /sign-in");
        let body = "";
        req.on("data", (chunk) => {
            body += chunk.toString();
        });
        req.on("end", () => {
            console.log("HTTP request end called");
            try{
                const formData = new URLSearchParams(body);
                const usernameText = formData.get("usernameText");
                const passwordText = formData.get("passwordText");
                
                const dbData = fs.readFileSync(dbPath);
                const jsonData = JSON.parse(dbData);
                jsonData.users.push({usernameText, passwordText});
                const jsonString = JSON.stringify(jsonData);

                fs.writeFileSync(dbPath, jsonString, "utf-8", (err) => {
                    if(err) throw err;
                });
                
                res.writeHead(201, { "Content-Type": "application/json" });
                res.end(JSON.stringify(jsonData));
            } catch (error) {
                res.writeHead(400, { "Content-Type": "application/json" });
                res.end(JSON.stringify({ error: "Invalid JSON"}));
            }
        });
        return;
    }
});

server.listen(3000, () => {
    console.log("Go to http://localhost:3000\n");
})