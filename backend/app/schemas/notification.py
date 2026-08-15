import uuid

from pydantic import BaseModel


class ReminderResponse(BaseModel):
    event_id: uuid.UUID
    target_parents: int
    sent: int
    failed: int
