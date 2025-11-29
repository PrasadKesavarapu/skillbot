import datetime as dt
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.sqlite import JSON

from .db import Base


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    skills_json = Column(JSON, nullable=False)  # list of skills stored as JSON
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
