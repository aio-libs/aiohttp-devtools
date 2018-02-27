{{ name }}
{{ '=' * name|length }}

Your new web app is ready to go!

To run your app you'll need to:

1. Activate a python 3.5 or 3.6 environment
2. Install the required packages with `pip install -r requirements.txt`
3. Make sure the app's settings are configured correctly (see `activate_settings.sh` and `app/settings.py`). You can also
 use environment variables to define sensitive settings, eg. DB connection variables
4. You can then run your app during development with `adev runserver .`

