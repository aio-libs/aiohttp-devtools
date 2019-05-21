from pathlib import Path

import aiohttp_jinja2
import aiohttp_session
import asyncpg
import jinja2
from aiohttp import web
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from .db import prepare_database
from .settings import Settings
from .views import index, message_data, messages

THIS_DIR = Path(__file__).parent


async def startup(app: web.Application):
    settings: Settings = app['settings']
    await prepare_database(settings, False)
    app['pg'] = await asyncpg.create_pool(dsn=settings.pg_dsn, min_size=2)


async def cleanup(app: web.Application):
    await app['pg'].close()


async def create_app():
    app = web.Application()
    settings = Settings()
    app.update(
        settings=settings,
        static_root_url='/static/',
    )

    jinja2_loader = jinja2.FileSystemLoader(str(THIS_DIR / 'templates'))
    aiohttp_jinja2.setup(app, loader=jinja2_loader)

    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    aiohttp_session.setup(app, EncryptedCookieStorage(settings.auth_key, cookie_name=settings.cookie_name))

    app.router.add_get('/', index, name='index')
    app.router.add_route('*', '/messages', messages, name='messages')
    app.router.add_get('/messages/data', message_data, name='message-data')
    return app
