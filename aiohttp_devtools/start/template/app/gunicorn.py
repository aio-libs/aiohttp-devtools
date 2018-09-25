"""
This file allows your to serve your application using gunicorn. gunicorn is not installed by default
by the requirements file adev creates, you'll need to install it yourself and add it to requirements.txt.

To run the app using gunicorn, in the terminal run

    pip install gunicorn
    gunicorn app.gunicorn:app --worker-class aiohttp.worker.GunicornWebWorker

You could use a variant of the above with heroku (in the `Procfile`) or with Docker in the ENTRYPOINT statement.
"""
import asyncio
from .main import create_app

loop = asyncio.get_event_loop()

app = loop.run_until_complete(create_app())
