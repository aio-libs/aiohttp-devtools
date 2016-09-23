# {% if example.message_board %}
from .views import index, messages, message_data
# {% else %}
from .views import index
# {% endif %}


def setup_routes(app):
    app.router.add_get('/', index, name='index')
    # {% if example.message_board %}
    app.router.add_route('*', '/messages', messages, name='messages')
    app.router.add_get('/messages/data', message_data, name='message-data')
    # {% endif %}

