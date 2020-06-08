import random

from crawler_module import gol

def updateIP():
    gol.set_value("proxy", {
        "http": gol.get_value("proxyList")[int(random.random() * len(gol.get_value("proxyList")))],
        "https": gol.get_value("proxyList")[int(random.random() * len(gol.get_value("proxyList")))]
    })
    return gol.get_value("proxy")

def updateHeaders():
    gol.set_value("headers", {
        # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.18363",
        "User-Agent": "Mozilla/5.0",
        'Authorization': 'token ' + random.choice(gol.get_value("tokenList")),
        'Content-Type': 'application/json',
        'method': 'GET',
        'Accept': 'application/json'
    })
    return gol.get_value("headers")
