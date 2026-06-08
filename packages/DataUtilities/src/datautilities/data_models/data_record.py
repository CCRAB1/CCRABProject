from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel

from .base_record import BaseRecord


class PlatformDataRecord(BaseRecord):
    organization: str
    platform_handle: str
    obs_type: str
    uom_type: str
    s_order: int
    value: float
    date_time: datetime
    latitude: float
    longitude: float
    altitude: float


class DataRecord(BaseModel):
    obs_type: str
    uom_type: str
    s_order: int
    value: float


class PlatformRecord(BaseRecord):
    kind: Literal["platformrecord"] = "platformrecord"
    organization: str
    platform_handle: str
    date_time: datetime
    latitude: float
    longitude: float
    altitude: float
    samples: List[DataRecord]
