# {% if database.is_pg_sqlalchemy %}
import psycopg2

from .main import load_settings

from sqlalchemy import create_engine
from .main import pg_dsn
from .models import Base


def prepare_database(delete_existing: bool) -> bool:
    """
    (Re)create a fresh database and run migrations.

    :param delete_existing: whether or not to drop an existing database if it exists
    :return: whether or not a database has been (re)created
    """
    db = load_settings()['database']

    conn = psycopg2.connect(
        password=db['password'],
        host=db['host'],
        port=db['port'],
        user=db['user'],
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('SELECT EXISTS (SELECT datname FROM pg_catalog.pg_database WHERE datname=%s)', (db['name'],))
    already_exists = bool(cur.fetchone()[0])
    if already_exists:
        if not delete_existing:
            print('database "{name}" already exists, skipping'.format(**db))
            return False
        else:
            print('dropping database "{name}" as it already exists...'.format(**db))
            cur.execute('DROP DATABASE {name}'.format(**db))
    else:
        print('database "{name}" does not yet exist'.format(**db))

    print('creating database "{name}"...'.format(**db))
    cur.execute('CREATE DATABASE {name}'.format(**db))
    cur.close()
    conn.close()

    # {% if database.is_pg_sqlalchemy %}
    engine = create_engine(pg_dsn(db))
    print('creating tables from model definition...')
    Base.metadata.create_all(engine)
    engine.dispose()
    # {% else %}
    # TODO
    # {% endif %}
    return True
# {% endif %}
