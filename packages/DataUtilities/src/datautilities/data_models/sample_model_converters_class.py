"""
Class-based converters between Pydantic models in sampling_data_record.py and SQLAlchemy table classes
in sample_answer_tables.py.

Usage:
    # initialize with the concrete classes (recommended)
    from sampling_data_record import SampleModel, AnswerModel, AttachmentModel
    from sample_answer_tables import sample as SampleTable, sample_answer as AnswerTable, sample_attachment as AttachmentTable
    conv = Converters(SampleModel, AnswerModel, AttachmentModel, SampleTable, AnswerTable, AttachmentTable)

    sample_row, answer_rows, attachment_rows = conv.pydantic_to_sqlalchemy_sample(pydantic_sample)
    conv.attach_rows_to_sample(sample_row, answer_rows, attachment_rows)
    pydantic = conv.sqlalchemy_sample_to_pydantic(sample_row)

Notes:
- Instances returned are SQLAlchemy ORM class instances (not persisted).
- The converter does not start/commit DB sessions.
- The class allows injecting custom mappings via the `field_map` argument to the constructor.
"""

from typing import Any, Dict, List, Optional, Tuple, Type

# Type aliases for readability
PydanticSample = Any
PydanticAnswer = Any
PydanticAttachment = Any
SATableClass = Any
SARow = Any


class Converters:
    def __init__(
        self,
        pydantic_sample_cls: Type[PydanticSample],
        pydantic_answer_cls: Type[PydanticAnswer],
        pydantic_attachment_cls: Type[PydanticAttachment],
        sa_sample_cls: Type[SATableClass],
        sa_answer_cls: Type[SATableClass],
        sa_attachment_cls: Type[SATableClass],
        field_map: Optional[Dict[str, str]] = None,
    ):
        """
        Create a Converters instance.

        field_map: optional mapping from pydantic field name -> sqlalchemy column name when names differ.
                   e.g. {"id": "row_id", "sample_date_iso": "sample_date"}
        """
        self.pydantic_sample_cls = pydantic_sample_cls
        self.pydantic_answer_cls = pydantic_answer_cls
        self.pydantic_attachment_cls = pydantic_attachment_cls
        self.sa_sample_cls = sa_sample_cls
        self.sa_answer_cls = sa_answer_cls
        self.sa_attachment_cls = sa_attachment_cls
        self.field_map = field_map or {}

    # ---------------------
    # low-level helpers
    # ---------------------
    def _table_column_names(self, sa_class: Type[SATableClass]) -> List[str]:
        """Return list of column names defined on a SQLAlchemy declarative class."""
        if not hasattr(sa_class, "__table__"):
            raise ValueError(
                f"Provided SQLAlchemy class {sa_class} does not expose __table__"
            )
        return [c.name for c in sa_class.__table__.columns]

    def _apply_field_map(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remap keys in data according to field_map.
        field_map maps source_name -> target_name.
        """
        if not self.field_map:
            return data
        remapped = {}
        for k, v in data.items():
            target = self.field_map.get(k, k)
            remapped[target] = v
        return remapped

    def _dict_to_sa(
        self, sa_class: Type[SATableClass], values: Dict[str, Any]
    ) -> SARow:
        """
        Create an instance of sa_class mapping keys in values to column names where possible.
        Ignores keys that do not correspond to columns.
        """
        columns = set(self._table_column_names(sa_class))
        mapped = self._apply_field_map(values)
        filtered = {k: v for k, v in mapped.items() if k in columns}
        return sa_class(**filtered)

    # ---------------------
    # pydantic -> sqlalchemy
    # ---------------------
    def answer_model_to_row(
        self, answer: PydanticAnswer, sample_row_id: Optional[int] = None
    ) -> SARow:
        """
        Convert AnswerModel -> sample_answer row instance.
        If sample_row_id is provided, it will be set to the sample_id column.
        """
        # If it's a pydantic model instance, use .dict(); otherwise parse using the cls
        if hasattr(answer, "dict"):
            d = answer.dict(exclude_none=True)
        else:
            d = self.pydantic_answer_cls.parse_obj(answer).dict(exclude_none=True)
        if sample_row_id is not None:
            d["sample_id"] = sample_row_id
        return self._dict_to_sa(self.sa_answer_cls, d)

    def attachment_model_to_row(
        self, att: PydanticAttachment, sample_row_id: Optional[int] = None
    ) -> SARow:
        """
        Convert AttachmentModel -> sample_attachment row instance.
        If sample_row_id is provided, it will be set to the sample_id column.
        """
        if hasattr(att, "dict"):
            d = att.dict(exclude_none=True)
        else:
            d = self.pydantic_attachment_cls.parse_obj(att).dict(exclude_none=True)
        if sample_row_id is not None:
            d["sample_id"] = sample_row_id
        # Convert storage_url to string if present
        if "storage_url" in d and d["storage_url"] is not None:
            d["storage_url"] = str(d["storage_url"])
        return self._dict_to_sa(self.sa_attachment_cls, d)

    def pydantic_to_sqlalchemy_sample(
        self, p: PydanticSample
    ) -> Tuple[SARow, List[SARow], List[SARow]]:
        """
        Convert a SampleModel pydantic object to a SQLAlchemy sample row plus its related answers
        and attachments as SQLAlchemy objects.

        Returns (sample_row_instance, [answer_row_instances], [attachment_row_instances])

        Note: the returned sample_row_instance will NOT have its row_id set (until persisted).
        """
        if hasattr(p, "dict"):
            pd = p.dict(exclude_none=True)
        else:
            pd = self.pydantic_sample_cls.parse_obj(p).dict(exclude_none=True)

        answers = pd.pop("answers", [])
        attachments = pd.pop("attachments", [])
        sample_row = self._dict_to_sa(self.sa_sample_cls, pd)

        answer_rows = [
            self.answer_model_to_row(
                a if hasattr(a, "dict") else self.pydantic_answer_cls.parse_obj(a), None
            )
            for a in answers
        ]
        attachment_rows = [
            self.attachment_model_to_row(
                a if hasattr(a, "dict") else self.pydantic_attachment_cls.parse_obj(a),
                None,
            )
            for a in attachments
        ]
        return sample_row, answer_rows, attachment_rows

    def attach_rows_to_sample(
        self,
        sample_row: SARow,
        answer_rows: Optional[List[SARow]] = None,
        attachment_rows: Optional[List[SARow]] = None,
    ):
        """
        Convenience: set sample_id on answer/attachment rows using sample_row.row_id
        (call after sample_row has been persisted and has row_id set).
        """
        if not hasattr(sample_row, "row_id") or sample_row.row_id is None:
            raise ValueError(
                "sample_row must have row_id set before attaching children."
            )
        sid = sample_row.row_id
        for a in answer_rows or []:
            if hasattr(a, "sample_id"):
                a.sample_id = sid
        for at in attachment_rows or []:
            if hasattr(at, "sample_id"):
                at.sample_id = sid

    # ---------------------
    # sqlalchemy -> pydantic
    # ---------------------
    def sqlalchemy_sample_to_pydantic(self, sample_row: SARow) -> PydanticSample:
        """
        Convert a SQLAlchemy sample row to the pydantic SampleModel.
        This will also try to convert related answers and attachments if the row has
        attributes 'answers' or 'attachments' (typical when using relationship(...) in ORM).
        """
        cols = self._table_column_names(type(sample_row))
        data: Dict[str, Any] = {}
        for col in cols:
            data[col] = getattr(sample_row, col, None)
        answers = getattr(sample_row, "answers", None)
        attachments = getattr(sample_row, "attachments", None)
        if answers is not None:
            data["answers"] = [self._sa_answer_to_dict(a) for a in answers]
        if attachments is not None:
            data["attachments"] = [self._sa_attachment_to_dict(a) for a in attachments]
        return self.pydantic_sample_cls.parse_obj(data)

    def _sa_answer_to_dict(self, a_row: SARow) -> Dict[str, Any]:
        cols = self._table_column_names(type(a_row))
        return {c: getattr(a_row, c, None) for c in cols}

    def _sa_attachment_to_dict(self, at_row: SARow) -> Dict[str, Any]:
        cols = self._table_column_names(type(at_row))
        return {c: getattr(at_row, c, None) for c in cols}

    # convenience utility
    def pydantic_list_to_sqlalchemy(
        self, samples: List[PydanticSample]
    ) -> List[Tuple[SARow, List[SARow], List[SARow]]]:
        out = []
        for s in samples:
            out.append(self.pydantic_to_sqlalchemy_sample(s))
        return out
