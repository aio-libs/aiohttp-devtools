# {% if database.is_pg_sqlalchemy %}
import psycopg2

from .settings import Settings

from sqlalchemy import create_engine
from .main import pg_dsn
from .models import Base


def prepare_database(delete_existing: bool) -> bool:
    """
    (Re)create a fresh database and run migrations.

    :param delete_existing: whether or not to drop an existing database if it exists
    :return: whether or not a database has been (re)created
    """
    settings = Settings()

    conn = psycopg2.connect(
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
    )
    conn.autocommit = True
    cur = conn.cursor()
    db_name = settings.DB_NAME
    cur.execute('SELECT EXISTS (SELECT datname FROM pg_catalog.pg_database WHERE datname=%s)', (db_name,))
    already_exists = bool(cur.fetchone()[0])
    if already_exists:
        if not delete_existing:
            print('database "{}" already exists, skipping'.format(db_name))
            return False
        else:
            print('dropping database "{}" as it already exists...'.format(db_name))
            cur.execute('DROP DATABASE {}'.format(db_name))
    else:
        print('database "{}" does not yet exist'.format(db_name))

    print('creating database "{}"...'.format(db_name))
    cur.execute('CREATE DATABASE {}'.format(db_name))
    cur.close()
    conn.close()

    # {% if database.is_pg_sqlalchemy %}
    engine = create_engine(pg_dsn(settings))
    print('creating tables from model definition...')
    Base.metadata.create_all(engine)
    engine.dispose()
    # {% else %}
    # TODO
    # {% endif %}
    return True
# {% endif %}
