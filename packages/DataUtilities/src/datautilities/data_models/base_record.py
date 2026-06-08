from datetime import datetime

from pydantic import BaseModel


class BaseRecord(BaseModel):
    source: str
    timestamp: datetime
