#!/usr/bin/env python
from aiohttp import web
from aiohttp_devtools import cli
import ssl

async def hello(request):
    return web.Response(text="<h1>hello world</h1>", content_type="text/html")

async def create_app():
    a = web.Application()
    a.router.add_get("/", hello)
    return a

def get_ssl_context():
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain('/home/roman/Projects/SemanticStoreSuite/SSArchive/SS_PWA&UI_Resarch/certs/server.crt', 
                                '/home/roman/Projects/SemanticStoreSuite/SSArchive/SS_PWA&UI_Resarch/certs/server.key')
    return ssl_context
    # return False

if __name__ == '__main__':
    cli.cli()