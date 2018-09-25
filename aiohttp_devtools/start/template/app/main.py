from pathlib import Path

from aiohttp import web
# {% if database.is_pg_sqlalchemy %}
from aiopg.sa import create_engine
from sqlalchemy.engine.url import URL
# {% endif %}

# {% if template_engine.is_jinja %}
import aiohttp_jinja2
import jinja2
# {% endif %}
# {% if session.is_secure %}
import base64
import aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
# {% endif %}

from .settings import Settings
# {% if example.is_message_board %}
from .views import index, messages, message_data
# {% else %}
from .views import index
# {% endif %}


THIS_DIR = Path(__file__).parent
BASE_DIR = THIS_DIR.parent


# {% if database.is_pg_sqlalchemy %}
def pg_dsn(settings: Settings) -> str:
    """
    :param settings: settings including connection settings
    :return: DSN url suitable for sqlalchemy and aiopg.
    """
    return str(URL(
        database=settings.DB_NAME,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        username=settings.DB_USER,
        drivername='postgres',
    ))


async def startup(app: web.Application):
    app['pg_engine'] = await create_engine(pg_dsn(app['settings']), loop=app.loop)


async def cleanup(app: web.Application):
    app['pg_engine'].close()
    await app['pg_engine'].wait_closed()
# {% endif %}


def setup_routes(app):
    app.router.add_get('/', index, name='index')
    # {% if example.is_message_board %}
    app.router.add_route('*', '/messages', messages, name='messages')
    app.router.add_get('/messages/data', message_data, name='message-data')
    # {% endif %}


async def create_app():
    app = web.Application()
    settings = Settings()
    app.update(
        name='{{ name }}',
        settings=settings
    )
    # {% if template_engine.is_jinja %}

    jinja2_loader = jinja2.FileSystemLoader(str(THIS_DIR / 'templates'))
    aiohttp_jinja2.setup(app, loader=jinja2_loader)
    # {% endif %}
    # {% if database.is_pg_sqlalchemy %}

    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    # {% endif %}
    # {% if session.is_secure %}

    secret_key = base64.urlsafe_b64decode(settings.COOKIE_SECRET)
    aiohttp_session.setup(app, EncryptedCookieStorage(secret_key))
    # {% endif %}

    setup_routes(app)
    return app
