from aiohttp import web
# {% if template_engine.is_jinja %}
from aiohttp_jinja2 import template
# {% endif %}

# {% if template_engine.is_jinja %}
@template('index.jinja')
async def index(request):
    return {'foo': 'bar'}

# {% else %}

async def index(request):
    return web.Response(text='<body>hello</body>', content_type='text/html')
# {% endif %}
