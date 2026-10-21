from datetime import datetime, timezone

from sqlalchemy.dialects.mysql import MEDIUMTEXT

from .extensions import db
from .markdown_utils import render_markdown


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False, default="Nouvelle conversation")
    category = db.Column(db.String(40), nullable=False, default="default", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    messages = db.relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def to_dict(self, include_messages=False):
        data = {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_messages:
            data["messages"] = [message.to_dict() for message in self.messages]
        return data


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    attachment_name = db.Column(db.String(255))
    # SQL dumps can exceed MySQL's ~64 KiB TEXT limit.
    attachment_text = db.Column(db.Text().with_variant(MEDIUMTEXT(), "mysql"))
    sql_report = db.Column(db.JSON)
    confidence_segments = db.Column(db.JSON)
    input_tokens = db.Column(db.Integer)
    output_tokens = db.Column(db.Integer)
    total_tokens = db.Column(db.Integer)
    response_time_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    conversation = db.relationship("Conversation", back_populates="messages")

    def to_dict(self):
        confidence_segments = []
        for segment in self.confidence_segments or []:
            serialized = dict(segment)
            serialized["html"] = str(render_markdown(serialized.get("text", "")))
            confidence_segments.append(serialized)

        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "content_html": str(render_markdown(self.content)) if self.role == "assistant" else None,
            "attachment_name": self.attachment_name,
            "sql_report": self.sql_report,
            "confidence_segments": confidence_segments,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "response_time_ms": self.response_time_ms,
            "created_at": self.created_at.isoformat(),
        }


class ErrorLog(db.Model):
    __tablename__ = "error_logs"

    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(20), nullable=False, default="ERROR", index=True)
    endpoint = db.Column(db.String(255))
    error_type = db.Column(db.String(160))
    message = db.Column(db.Text, nullable=False)
    traceback_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "level": self.level,
            "endpoint": self.endpoint,
            "error_type": self.error_type,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }
