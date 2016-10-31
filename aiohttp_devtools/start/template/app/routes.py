# {% if example.is_message_board %}
# {% else %}
from .views import index, message_data, messages


# {% endif %}


def setup_routes(app):
    app.router.add_get('/', index, name='index')
    # {% if example.is_message_board %}
    app.router.add_route('*', '/messages', messages, name='messages')
    app.router.add_get('/messages/data', message_data, name='message-data')
    # {% endif %}
