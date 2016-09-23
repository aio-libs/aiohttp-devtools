from datetime import datetime
from pathlib import Path

from aiohttp import web
from aiohttp.hdrs import METH_POST
from aiohttp.web_exceptions import HTTPFound
from aiohttp.web_reqrep import json_response
# {% if template_engine.is_jinja2 %}
from aiohttp_jinja2 import template
# {% endif %}

# {% if database.is_none and example.message_board %}
# if no database is available we use a plain old file to store messages. Don't do this kind of thing in production!
MESSAGE_FILE = Path('messages.txt')
# {% endif %}


# {% if template_engine.is_jinja2 %}
@template('index.jinja')
async def index(request):
    """
    This is the view handler for the "/" url.

    :param request: the request object see http://aiohttp.readthedocs.io/en/stable/web_reference.html#request
    :return: context for the template.
    """
    # Note: we return a dict not a response because of the @template decorator
    return {
        'title': request.app['name'],
        'message': "Success! you've setup a basic aiohttp app.",
    }

# {% else %}

# in the name of brevity we return stripped down html, this works fine on chrome but shouldn't be used in production
# the <body> tag is required to activate aiohttp-debugtoolbar.
BASE_PAGE = """\
<title>{title}</title>
<link href="{styles_css_url}" rel="stylesheet">
<body>
<main>
  <h1>{title}</h1>
  {content}
</main>
</body>"""

async def index(request):
    """
    This is the view handler for the "/" url.

    **Note: returning html without a template engine like jinja2 is ugly, no way around that.**

    :param request: the request object see http://aiohttp.readthedocs.io/en/stable/web_reference.html#request
    :return: aiohttp.web.Response object
    """
    # {% if database.is_none and example.message_board %}
    # app.router allows us to generate urls based on their names,
    # see http://aiohttp.readthedocs.io/en/stable/web.html#reverse-url-constructing-using-named-resources
    message_url = request.app.router['messages'].url()
    ctx = dict(
        title=request.app['name'],
        styles_css_url=request.app['static_url'] + '/styles.css',
        content="""\
  <p>Success! you've setup a basic aiohttp app.</p>
  <p>To demonstrate a little of the functionality of aiohttp this app implements a very simple message board.</p>
  <b>
    <a href="{message_url}">View and add messages</a>
  </b>""".format(message_url=message_url)
    )
    # {% else %}
    ctx = dict(
        title=request.app['name'],
        styles_css_url=request.app['static_url'] + '/styles.css',
        content="<p>Success! you've setup a basic aiohttp app.</p>",
    )
    # {% endif %}
    # with the base web.Response type we have to manually set the content type, otherwise text/plain will be used.
    return web.Response(text=BASE_PAGE.format(**ctx), content_type='text/html')
# {% endif %}


# {% if database.is_none and example.message_board %}
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
        f.write('{username}|{timestamp}|{message}'.format(timestamp=now, **new_message))
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

    # {% if template_engine.is_jinja2 %}
    return {
        'title': 'Message board',
        'form_errors': form_errors,
    }
    # {% else %}
    ctx = dict(
        title='Message board',
        styles_css_url=request.app['static_url'] + '/styles.css',
        content="""\
  <h2>Add a new message:</h2>
  <form method="post" action="{message_url}">
    {form_errors}
    <p>
      <label for="username">Your name:</label>
      <input type="text" name="username" id="username" placeholder="fred blogs">
      <label for="message">Message:</label>
      <input type="text" name="message" id="message" placeholder="hello there">
    </p>
  <button type="submit">Post Message</button>
  </form>

  <h2>Messages:</h2>
  <div id="messages" data-url="{message_data_url}"></div>
  <script src="{message_display_js_url}"></script>""".format(
            message_url=request.app.router['messages'].url(),
            message_data_url=request.app.router['message-data'].url(),
            message_display_js_url=request.app['static_url'] + '/message_display.js',
            form_errors=form_errors and '<div class="form-errors">{}</div>'.format(form_errors)
        )
    )
    return web.Response(text=BASE_PAGE.format(**ctx), content_type='text/html')
    # {% endif %}


async def message_data(request):
    """
    As an example of aiohttp providing a non-html response, we load the actual messages for the "messages" view above
    via ajax using this endpoint to get data. see static/message_display.js for details of rendering.
    """
    messages = []
    if MESSAGE_FILE.exists():
        # read the message file and split it into lines
        lines = MESSAGE_FILE.read_text().split('\n')
        for line in reversed(lines):
            if not line:
                # ignore blank lines eg. end of file
                continue
            # split the line into it constituent parts, see process_form above
            username, ts, message = line.split('|', 2)
            # parse the datetime string and render it in a more readable format.
            ts = '{:%Y-%m-%d %H:%M:%S}'.format(datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S.%f'))
            messages.append({'username': username, 'timestamp':  ts, 'message': message})
    return json_response(messages)
# {% endif %}
