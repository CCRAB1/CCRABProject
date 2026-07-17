"""Pydantic models for the schemas in the Environet API v2 specification."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
)

ObjectId = Annotated[str, Field(pattern=r"^[0-9a-f]{24}$")]
MeasurementValue = float | bool | tuple[float, float]


class SearchQuery(BaseModel):
    """Shared request body accepted by the three search endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: list[ObjectId] | None = None
    data_point_id: list[ObjectId] | None = None
    from_timestamp: int | None = Field(None, alias="from", ge=0, le=1577836800000)
    to_timestamp: int | None = Field(None, alias="to", ge=0, le=1577836800000)
    last: int | None = Field(None, le=100)
    includes: Literal["data_points"] | None = None

    @field_validator("node_id", "data_point_id")
    @classmethod
    def ids_must_be_unique(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("IDs must be unique")
        return value


class Error(BaseModel):
    """Error response returned for invalid or unauthorized requests."""

    error: str


class Device(BaseModel):
    """Device attached to an Environet node."""

    id: str | None = Field(None, alias="_id")
    name: str | None = None
    connection: str | None = None
    tag: str | None = None


class Measurement(RootModel[tuple[int, MeasurementValue]]):
    """A ``[Unix timestamp in milliseconds, value]`` measurement tuple."""

    @property
    def timestamp(self) -> int:
        return self.root[0]

    @property
    def value(self) -> MeasurementValue:
        return self.root[1]


class DataPoint(BaseModel):
    """An Environet measurement data point."""

    id: ObjectId | None = Field(None, alias="_id")
    device_id: str | None = None
    path: str | None = None
    node_id: ObjectId | None = None
    name: str | None = None
    unit: str | None = None
    round: int | None = None
    type: str | None = Field(None, alias="_type")
    backend: str | None = None
    attached_node: ObjectId | None = None
    linked_data_points: list[ObjectId] | None = None
    measurements: list[Measurement] | None = None


class AlertConditions(RootModel[dict[str, list[Any]]]):
    """Flexible, recursively nestable alert condition functions."""


class Node(BaseModel):
    """A physical or alert node returned by Environet."""

    id: ObjectId | None = Field(None, alias="_id")
    serial: str | None = None
    name: str | None = None
    description: str | None = None
    type: Literal["thiamis", "alert"] | None = Field(None, alias="_type")
    status: str | None = None
    actions: list[str] | None = None
    organization_id: ObjectId | None = None
    devices: list[Device] | None = None
    data_points: list[DataPoint] | None = None
    notification_level: str | None = None
    attached_nodes: list[ObjectId] | None = None
    conditions: AlertConditions | None = None


class MeasurementsResponse(RootModel[dict[str, list[Measurement]]]):
    """Measurements keyed by data-point ID."""

    def for_data_point(self, data_point_id: str) -> list[Measurement]:
        """Return measurements for one data point, or an empty list."""

        return self.root.get(data_point_id, [])
