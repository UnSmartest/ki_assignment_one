**Brainstorm Google Docs :** <br>
<https://docs.google.com/document/d/1XWqRCrBJO_s07ngF0-HA73mmmTc5uSqpCRKntHB5P6M/edit?usp=sharing>

# HOW TO RUN PROJECT
1. Make sure you have NodeJS installed <br>
   You can check by `node --version`
2. Make sure your terminal is at the ki_assignment_one directory <br>
   You can check by `ls` and it should be like this more-or-less like this image: <br><br>
  <img width="715" height="336" alt="image" src="https://github.com/user-attachments/assets/4ab59862-814d-4e6e-8c6b-7f218c630de4" /><br><br>
3. Run `node server.js` <br>
   VERY IMPORTANT BECAUSE WE NEED THE SERVER.JS TO BE THE MIDDLE-MAN BETWEEN HTML JAVASCRIPT AND NODEJS JAVASCRIPT
4. Your terminal will say, "Go to http://localhost:3000" so open that URL in your web browser

# ADDING NEW PAGES/FILES
If you're making new pages, make sure you add that page's path into the `server.js` by doing:
1. `const whateverPagePath = "./pages/whateverPage.html"; near the top
2. If you just need to read that file or execute it, you can use GET method and the req.url value bebas, but that value will be that page's address
3. If you're still unsure, ask in the groupchat (or Krisna, backend guy), or ask ChatGPT or Gemini
4. Try not to let ChatGPT/Gemini/whatever change `server.js` too much
5. I do not like their overcomplicated code; if you have to ask them, state the problem, your hypothesis, and ask them to point out the flaw in your logic.

The most minimalist template for GET is:
```
if(req.method === "GET" && req.url === "/whateverAddressYouWantToGiveThisFile"){
  res.writeHead(200, {"Content-Type": "text/html"});
  fs.createReadStream(whateverPagePath).pipe(res);
  return;
}
```

And some example for when you need to go that page or need it's data:
```
<a href="/whateverAddressYouWantToGiveThisFile>Click me for free robux!</a>
```
or
```
try{
  const response = await fetch("/whateverAddressYouWantToGiveThisFile",{
    method: "GET",
  });
  const result = await response.json(); //or response.text(); depends on what format you need
} catch (error) {
  console.log(error);
}
```
or
```

```

content-type is usually either "text/html" or "application/json" <br>
.pipe(res) returns what fs reads <br>
(fs is the file manager from NodeJS that doesn't exist in Web JavaScript, which is why we need server.js) <br>

## AI Disclosure:
- https://claude.ai/share/d3b6786c-e4a9-4f5e-b205-150546b3352b 
- https://share.gemini.google/SmldziHxr63A
- https://chatgpt.com/share/6adf29bf-271c-83ec-a221-20f474b0bcd9
