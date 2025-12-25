import uuid
from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import BaseModel


class PaymentEvent(BaseModel):
    __tablename__ = "payment_events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway = Column(String(32), nullable=False)
    event_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False)
    message = Column(String(255), nullable=True)
    payload = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "event_id": str(self.event_id),
            "gateway": self.gateway,
            "event_type": self.event_type,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
