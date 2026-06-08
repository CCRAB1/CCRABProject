import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, constr

from .base_record import BaseRecord


class AttachmentModel(BaseModel):
    filename: constr(strip_whitespace=True, max_length=255)
    mime_type: Optional[str] = None
    storage_type: Optional[str] = Field(
        None, description="local, s3, gcs, azure_blob, etc."
    )
    storage_path: Optional[str] = None
    storage_bucket: Optional[str] = None
    storage_object_key: Optional[str] = None
    storage_url: Optional[HttpUrl] = None
    storage_meta: Optional[Dict[str, Any]] = None
    caption: Optional[str] = None
    file_size_bytes: Optional[int] = None
    uploaded_by: Optional[str] = None


class AnswerModel(BaseModel):
    key: constr(strip_whitespace=True, max_length=150)
    question_text: str = ""
    value_text: Optional[str] = None
    value_numeric: Optional[float] = None
    value_boolean: Optional[bool] = None
    value_json: Optional[Dict[str, Any]] = None
    answer_order: Optional[int] = 0
    qc_comment_field: Optional[str] = None
    qc_flag: Optional[int] = None
    note: Optional[str] = None


class SampleModel(BaseRecord):
    kind: Literal["samplerecord"] = "samplerecord"

    external_id: Optional[str] = None
    plugin_id: Optional[str] = None
    plugin_version: Optional[str] = None

    name: Optional[str] = None
    description: Optional[str] = None
    sample_date: datetime = datetime.strptime("1900-01-01", "%Y-%m-%d")

    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    street_address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)

    organization_id: Optional[int] = None
    collector_id: Optional[str] = None
    collector_name: Optional[str] = None

    answers: List[AnswerModel] = []
    attachments: List[AttachmentModel] = []
    attributes: Optional[Dict[str, Any]] = {}
    raw_payload: Optional[Dict[str, Any]] = None

    def export_to_csv(
        self,
        path: Union[str, Path],
        include_answers: bool = True,
        include_attachments: bool = True,
    ) -> Path:
        """
        Exports this SampleModel (and optionally its answers and attachments)
        into a CSV file. If answers are included, each answer becomes a row.
        """
        path = Path(path)
        rows = []

        if include_answers and self.answers:
            for ans in self.answers:
                rows.append(
                    {
                        "sample_external_id": self.external_id,
                        "plugin_id": self.plugin_id,
                        "sample_name": self.name,
                        "sample_date": self.sample_date.isoformat(),
                        "latitude": self.latitude,
                        "longitude": self.longitude,
                        "organization_id": self.organization_id,
                        "question_key": ans.key,
                        "question_text": ans.question_text,
                        "answer_order": ans.answer_order,
                        "value_text": ans.value_text,
                        "value_numeric": ans.value_numeric,
                        "value_boolean": ans.value_boolean,
                        "value_json": ans.value_json,
                    }
                )
        else:
            # Just write the sample-level info
            rows.append(self.model_dump())

        if include_attachments and self.attachments:
            for att in self.attachments:
                rows.append(
                    {
                        "sample_external_id": self.external_id,
                        "plugin_id": self.plugin_id,
                        "attachment_filename": att.filename,
                        "attachment_mime_type": att.mime_type,
                        "attachment_url": att.storage_url,
                    }
                )

        # Gather all unique keys for header
        fieldnames = sorted({k for r in rows for k in r.keys()})

        # Write CSV
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return path

    class Config:
        extra = "allow"  # tolerate plugins sending extra fields
