# {% if database.is_postgres_sqlalchemy %}
from sqlalchemy import Column, String, Text, func, DateTime, Integer, Sequence
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, Sequence('msg_id_seq'), primary_key=True, nullable=False)
    username = Column(String(40), nullable=False)
    message = Column(Text)
    timestamp = Column(DateTime(), server_default=func.now(), nullable=False)

sa_messages = Message.__table__
# {% endif %}
