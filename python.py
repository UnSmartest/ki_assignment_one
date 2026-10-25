from pyscript import document

#print() only displays in the console log

a = 7
if(a == 7):
    print("Hello, world!")
    document.querySelector("#output").innerText = "Hello, world!"
else:
    print("Goodbye, world!")
    document.querySelector("#output").innerText = "Goodbye, world!"