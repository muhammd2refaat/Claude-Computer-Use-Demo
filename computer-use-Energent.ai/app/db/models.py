"""
Database Models - SQLAlchemy ORM Models
"""
from sqlalchemy import Column, String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


class Session(Base):
    """Agent session model"""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=True)
    status = Column(String(50), default="active")  # active, completed, error
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, default={})

    # Relationships
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    """Conversation message model"""
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, default={})

    # Relationships
    session = relationship("Session", back_populates="messages")


class ToolCall(Base):
    """Tool execution log (optional)"""
    __tablename__ = "tool_calls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    tool_name = Column(String(100), nullable=False)
    tool_input = Column(JSON, nullable=False)
    tool_output = Column(JSON, nullable=True)
    status = Column(String(20), default="pending")  # pending, success, error
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
