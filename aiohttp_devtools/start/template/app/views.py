from datetime import datetime
from pathlib import Path

from aiohttp import web
from aiohttp.hdrs import METH_POST
# {% if template_engine.is_jinja2 %}
from aiohttp.web_exceptions import HTTPFound
from aiohttp_jinja2 import template
# {% endif %}

# if no database is available we use a plain old file to store messages. Don't do this kind of thing in production!
MESSAGE_FILE = Path('messages.txt')

# {% if template_engine.is_jinja2 %}

@template('index.jinja')
async def index(request):
    """
    This is the view handler for the "/" url.

    :param request: the request object see http://aiohttp.readthedocs.io/en/stable/web_reference.html#request
    :return: context for the template. Not: we return a dict not a response because of the @template decorator
    """
    return {
        'title': request.app['name'],
        'message': "Success! you've setup a basic aiohttp app.",
    }


# {% else %}

async def index(request):
    """
    This is the view handler for the "/" url.

    :param request: the request object see http://aiohttp.readthedocs.io/en/stable/web_reference.html#request
    :return: aiohttp.web.Response object
    """
    content = """\
<!DOCTYPE html>
<head>
  <title>{title}</title>
  <link href="{styles_css}" rel="stylesheet">
</head>
<body>
  <h1>{title}</h1>
  <p>{message}</p>
</body>"""
    return web.Response(text='<body>hello</body>', content_type='text/html')
# {% endif %}


async def process_form(request):
    new_message, missing_fields = {}, []
    fields = ['username', 'message']
    data = await request.post()
    for f in fields:
        new_message[f] = data.get(f)
        if not new_message[f]:
            missing_fields.append(f)

    if missing_fields:
        return 'Invalid form submission, missing fields: {}'.format(', '.join(missing_fields))

    # hack: this very simple storage uses "|" to split fields so we need to replace it in username
    new_message['username'] = new_message['username'].replace('|', '')
    with MESSAGE_FILE.open('a') as f:
        now = datetime.now().isoformat()
        f.write('{username}|{timestamp:%Y-%m-%d %H:%M}|{message}'.format(timestamp=now, **new_message))
    raise HTTPFound(request.app.router['messages'].url())


# {% if template_engine.is_jinja2 %}
@template('messages.jinja')
# {% endif %}
async def messages(request):
    if request.method == METH_POST:
        # the 302 redirect is processed as an exception, so if this coroutine returns there's a form error
        form_errors = await process_form(request)
    else:
        form_errors = None

    messages = []
    if MESSAGE_FILE.exists():
        lines = MESSAGE_FILE.read_text().split('\n')
        for line in reversed(lines):
            if not line:
                continue
            username, ts, message = line.split('|', 2)
            ts = '{:%Y-%m-%d %H:%M:%S}'.format(datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S.%f'))
            messages.append({'username': username, 'timestamp':  ts, 'message': message})
    # {% if template_engine.is_jinja2 %}
    return {
        'title': 'Message board',
        'form_errors': form_errors,
        'messages': messages,
    }
    # {% else %}
    raise NotImplementedError()
    # {% endif %}
