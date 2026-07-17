from __future__ import annotations
from enum import Enum
from typing import Optional, List, Dict, Any, Iterable, Union
from pathlib import Path
import json

from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator, ValidationError, constr, confloat




class SearchFilter(Enum):
    SOURCE_OBS_NAME_FILTER = 'source_obs_name'
    TARGET_OBS_NAME_FILTER = 'target_obs_name'
    SENSOR_ID_FILTER = 'sensor_id'
    M_TYPE_ID_FILTER = 'm_type_id'



class ObsMapError(Exception):
    """Base exception for ObsMap errors."""


class ObsMapValidationError(ObsMapError):
    """Raised when input mapping JSON contains invalid entries."""

    def __init__(self, message: str, errors: Optional[List[dict]] = None):
        super().__init__(message)
        self.errors = errors or []


def _norm_key(s: Optional[str]) -> Optional[str]:
    """Normalise keys used for lookups (strip + lower) or return None."""
    if s is None:
        return None
    return s.strip().lower() or None


class ObsMapRecord(BaseModel):
    target_obs: str = Field(..., min_length=1)
    target_uom: Optional[str] = None
    target_active: Optional[int] = None

    source_obs: Optional[str] = None
    source_uom: Optional[str] = None
    source_active: Optional[int] = None

    # s_order is required to be a positive integer (default 1)
    s_order: int = Field(default=1, ge=1)

    # other optional metadata...
    sensor_id: Optional[int] = None
    m_type_id: Optional[int] = None

    obs_description: Optional[str] = None
    uom_description: Optional[str] = None

    # private normalized keys
    _norm_source_obs: Optional[str] = PrivateAttr(default=None)
    _norm_target_obs: Optional[str] = PrivateAttr(default=None)
    _norm_source_uom: Optional[str] = PrivateAttr(default=None)
    _norm_target_uom: Optional[str] = PrivateAttr(default=None)

    @field_validator("target_obs", "source_obs", "target_uom", "source_uom", mode="before")
    @classmethod
    def _strip_strings(cls, v):
        if v is None:
            return None
        return str(v).strip()

    @model_validator(mode="after")
    def _set_norms(self):
        object.__setattr__(self, "_norm_source_obs", _norm_key(self.source_obs))
        object.__setattr__(self, "_norm_target_obs", _norm_key(self.target_obs))
        object.__setattr__(self, "_norm_source_uom", _norm_key(self.source_uom))
        object.__setattr__(self, "_norm_target_uom", _norm_key(self.target_uom))
        return self


class ObsMap:
    """
    Indexes records with s_order taken into account.

    _by_source_obs: Dict[norm_source_obs, Dict[s_order, ObsMapRecord]]
    _by_target_obs: Dict[norm_target_obs, Dict[s_order, ObsMapRecord]]
    """

    def __init__(self, records: Optional[Iterable[ObsMapRecord]] = None):
        self._records: List[ObsMapRecord] = []
        self._by_source_obs: Dict[str, Dict[int, ObsMapRecord]] = {}
        self._by_target_obs: Dict[str, Dict[int, ObsMapRecord]] = {}
        if records:
            for r in records:
                self.add_record(r, overwrite=True)

    def add_record(self, rec: ObsMapRecord, overwrite: bool = True):
        # source index
        if rec._norm_source_obs:
            src_map = self._by_source_obs.setdefault(rec._norm_source_obs, {})
            if rec.s_order in src_map and not overwrite:
                raise ValueError(f"Duplicate source '{rec.source_obs}' with s_order={rec.s_order}")
            src_map[rec.s_order] = rec

        # target index
        if rec._norm_target_obs:
            tgt_map = self._by_target_obs.setdefault(rec._norm_target_obs, {})
            if rec.s_order in tgt_map and not overwrite:
                raise ValueError(f"Duplicate target '{rec.target_obs}' with s_order={rec.s_order}")
            tgt_map[rec.s_order] = rec

        self._records.append(rec)

    def get_by_source(
        self,
        source_obs: str,
        s_order: Optional[int] = None,
        return_all: bool = False
    ) -> Optional[ObsMapRecord] | List[ObsMapRecord]:
        key = _norm_key(source_obs)
        if not key:
            return None if not return_all else []
        src_map = self._by_source_obs.get(key)
        if not src_map:
            return None if not return_all else []

        if s_order is not None:
            return src_map.get(s_order)

        # no s_order specified
        if return_all:
            # return list sorted by s_order ascending
            return [src_map[k] for k in sorted(src_map.keys())]
        # default: return highest-priority: smallest s_order
        min_key = min(src_map.keys())
        return src_map[min_key]

    def get_by_target(
        self,
        target_obs: str,
        s_order: Optional[int] = None,
        return_all: bool = False
    ) -> Optional[ObsMapRecord] | List[ObsMapRecord]:
        key = _norm_key(target_obs)
        if not key:
            return None if not return_all else []
        tgt_map = self._by_target_obs.get(key)
        if not tgt_map:
            return None if not return_all else []

        if s_order is not None:
            return tgt_map.get(s_order)
        if return_all:
            return [tgt_map[k] for k in sorted(tgt_map.keys())]
        min_key = min(tgt_map.keys())
        return tgt_map[min_key]

    def remove_by_source(self, source_obs: str, s_order: Optional[int] = None) -> bool:
        key = _norm_key(source_obs)
        if not key or key not in self._by_source_obs:
            return False
        src_map = self._by_source_obs[key]
        if s_order is None:
            # remove all
            for rec in list(src_map.values()):
                try:
                    self._records.remove(rec)
                except ValueError:
                    pass
            del self._by_source_obs[key]
            # also prune target index entries pointing to these recs
            for rec in list(src_map.values()):
                if rec._norm_target_obs and rec._norm_target_obs in self._by_target_obs:
                    tgt_map = self._by_target_obs[rec._norm_target_obs]
                    tgt_map.pop(rec.s_order, None)
                    if not tgt_map:
                        del self._by_target_obs[rec._norm_target_obs]
            return True
        else:
            rec = src_map.pop(s_order, None)
            if rec:
                try:
                    self._records.remove(rec)
                except ValueError:
                    pass
                # remove corresponding target index
                if rec._norm_target_obs and rec._norm_target_obs in self._by_target_obs:
                    self._by_target_obs[rec._norm_target_obs].pop(s_order, None)
                    if not self._by_target_obs[rec._norm_target_obs]:
                        del self._by_target_obs[rec._norm_target_obs]
                if not src_map:
                    del self._by_source_obs[key]
                return True
            return False

    # convenience: find best match with optional s_order
    def find_best_match(self, source_obs: str, s_order: Optional[int] = None) -> Optional[ObsMapRecord]:
        # try source lookup (honoring s_order)
        r = self.get_by_source(source_obs, s_order=s_order, return_all=False)
        if r:
            return r
        # fallback: maybe caller passed canonical target name; try target index
        return self.get_by_target(source_obs, s_order=s_order, return_all=False)

    def __iter__(self):
        for obs_rec in self._records:
            yield obs_rec




class PlatformCatalog(BaseModel):
    """
    Top-level catalog model that holds site-level info with multiple platforms.
    Root JSON structure:
      {
        "short_name": ...,
        "long_name": ...,
        "platforms": [ <Platform dicts> ]
      }
    """
    platforms: List[dict] = Field(default_factory=list)

    # internal mapping handle -> Platform model
    _platforms_by_handle: Dict[str, Platform] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def build_platforms(self):
        errors = []
        for idx, p in enumerate(self.platforms):
            try:
                plat = Platform(**p)
                handle = plat.platform_handle
                key = _norm_key(handle)
                if not key:
                    raise ValueError("platform_handle must be a non-empty string")
                if key in self._platforms_by_handle:
                    raise ValueError(f"Duplicate platform handle: {handle}")
                self._platforms_by_handle[key] = plat
            except ValidationError as ve:
                errors.append({"index": idx, "item": p, "errors": ve.errors()})
            except Exception as exc:
                errors.append({"index": idx, "item": p, "errors": str(exc)})
        if errors:
            raise ValidationError(errors, model=PlatformCatalog)
        return self

    def get_platform(self, platform_handle: str) -> Optional[Platform]:
        return self._platforms_by_handle.get(_norm_key(platform_handle))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlatformCatalog":
        """
        Create a PlatformCatalog from an in-memory JSON structure (a dict).
        This will run Pydantic validators and build the internal platform index.
        Raises pydantic.ValidationError on invalid input.
        """
        try:
            # Using direct construction so model validators run as normal
            return cls(**data)
        except ValidationError:
            # re-raise to surface structured errors to callers
            raise

    @classmethod
    def from_json(cls, json_str: str) -> "PlatformCatalog":
        """
        Create a PlatformCatalog from a JSON string.
        Parses JSON then calls from_dict.
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: str | Path):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**raw)

    def list_platform_handles(self) -> List[str]:
        return [p.platform_handle for p in self._platforms_by_handle.values()]

class Platform(BaseModel):
    """
    Platform model with canonical fields and a flexible 'properties' dict
    for application-specific configuration.
    """

    # canonical fields we always expect / validate
    platform_handle: constr(min_length=1)

    # location is optional but validated when present
    latitude: Optional[confloat(ge=-90.0, le=90.0)] = None
    longitude: Optional[confloat(ge=-180.0, le=180.0)] = None

    # optional canonical names
    short_name: Optional[str] = None
    long_name: Optional[str] = None
    external_identifier: Optional[str] = None
    country_code: Optional[str] = None
    neighborhood: Optional[str] = None

    # observations: keep as plain list-of-dicts — we'll validate later when building ObsMap
    observations: List[dict] = Field(default_factory=list)

    # properties collects any application-specific keys that were present in the input
    properties: Dict[str, Any] = Field(default_factory=dict)

    # Internal: store ObsMap or other derived structures in a PrivateAttr if needed
    _obs_map: ObsMap = PrivateAttr()  # set in a post-init validator if you build it
    # ... existing fields ...
    observations: List[dict] = Field(default_factory=list)
    _obs_map: ObsMap = PrivateAttr(None)

    @model_validator(mode="after")
    def build_obs_map_on_init(self):
        """
        Eagerly validate the observations list and create ObsMap.
        By default we treat any validation error in observations as fatal and raise a ValidationError
        containing details about which observation entries failed.
        """
        recs = []
        errors = []
        for idx, item in enumerate(self.observations):
            try:
                rec = ObsMapRecord(**item)
                recs.append(rec)
            except ValidationError as ve:
                errors.append({"index": idx, "item": item, "errors": ve.errors()})
        if errors:
            # Fail fast: surface which observation entries are invalid
            raise ValidationError(errors, model=Platform)
        self._obs_map = ObsMap(recs)
        return self

    # Lazy getter in case someone disabled eager validation or wants rebuild ability
    @property
    def obs_map(self) -> ObsMap:
        """
        Returns the ObsMap. If absent (e.g. created without running build), constructs it lazily.
        """
        if getattr(self, "_obs_map", None) is None:
            # Attempt to build lazily; collect errors and raise if invalid
            recs = []
            errors = []
            for idx, item in enumerate(self.observations):
                try:
                    rec = ObsMapRecord(**item)
                    recs.append(rec)
                except ValidationError as ve:
                    errors.append({"index": idx, "item": item, "errors": ve.errors()})
            if errors:
                raise ValidationError(errors, model=Platform)
            self._obs_map = ObsMap(recs)
        return self._obs_map

    def rebuild_obs_map(self, tolerant: bool = False, overwrite: bool = True) -> tuple[ObsMap, List[dict]]:
        """
        Rebuild the internal ObsMap from self.observations.

        Args:
          tolerant: if True, skip invalid observation entries and return them in the errors list instead
                   of raising ValidationError.
          overwrite: passed to ObsMap.add_record (controls duplicate behavior).

        Returns:
          (obs_map, errors) where errors is [] on success or a list of {"index", "item", "errors"} entries.
        """
        recs = []
        errors = []
        for idx, item in enumerate(self.observations):
            try:
                rec = ObsMapRecord(**item)
                recs.append(rec)
            except ValidationError as ve:
                err_info = {"index": idx, "item": item, "errors": ve.errors()}
                if tolerant:
                    errors.append(err_info)
                    continue
                # strict: raise immediately with structure
                raise ValidationError([err_info], model=Platform)
        om = ObsMap()
        for r in recs:
            om.add_record(r, overwrite=overwrite)
        self._obs_map = om
        return om, errors

    @model_validator(mode="before")
    @classmethod
    def _collect_extra_properties(cls, values: dict) -> dict:
        """
        Normalize input so that:
          - known/canonical keys remain top-level
          - any unknown keys are moved into `properties` dict
        Also supports the case where the input already contains a 'properties' map.
        """
        # Known keys are the field names of this model (we treat 'observations' specially)
        known = {"platform_handle", "latitude", "longitude", "short_name", "long_name", "observations", "properties"}
        # copy input to avoid mutating original
        incoming = dict(values) if values is not None else {}
        properties = {}

        # If the user supplied a 'properties' field explicitly, start with it (must be a dict)
        if "properties" in incoming and isinstance(incoming.get("properties"), dict):
            properties.update(incoming.pop("properties"))

        # Move any unknown top-level keys into properties
        for k in list(incoming.keys()):
            if k not in known:
                properties[k] = incoming.pop(k)

        # Place normalized properties back into the payload
        incoming["properties"] = properties
        return incoming

    @field_validator("platform_handle", mode="before")
    @classmethod
    def _strip_handle(cls, v):
        if v is None:
            return v
        return str(v).strip()

    # convenience typed accessors for properties
    def get_property(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)

    def get_property_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        v = self.properties.get(key, None)
        if v is None:
            return default
        try:
            return int(v)
        except (ValueError, TypeError):
            return default

    def get_property_float(self, key: str, default: Optional[float] = None) -> Optional[float]:
        v = self.properties.get(key, None)
        if v is None:
            return default
        try:
            return float(v)
        except (ValueError, TypeError):
            return default

    def get_property_list(self, key: str, default: Optional[List[Any]] = None) -> Optional[List[Any]]:
        v = self.properties.get(key, None)
        if v is None:
            return default
        if isinstance(v, list):
            return v
        # Try to parse comma-separated string
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return default

    # optional convenience factory
    @classmethod
    def from_dict(cls, data: dict) -> "Platform":
        # This will run model validators (including the before validator that collects properties)
        return cls(**data)

    # serialization
    def to_dict(self) -> dict:
        return self.model_dump()

class Organization(BaseModel):
    """
    Root object: organization containing platforms (the new catalog).
    """

    short_name: Optional[str] = None
    long_name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None

    platforms: List[dict] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)

    # private index handle -> Platform
    _platforms_by_handle: Dict[str, Platform] = PrivateAttr(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _collect_props(cls, values: dict) -> dict:
        # move unknown keys into properties (if user didn't supply properties explicitly)
        known = {"short_name", "long_name", "platforms", "properties"}
        incoming = dict(values or {})
        props = {}
        if isinstance(incoming.get("properties"), dict):
            props.update(incoming.pop("properties"))
        for k in list(incoming.keys()):
            if k not in known:
                props[k] = incoming.pop(k)
        incoming["properties"] = props
        return incoming

    @model_validator(mode="after")
    def build_platform_index(self):
        errors = []
        validated: List[Platform] = []
        for idx, p in enumerate(self.platforms):
            try:
                plat = p if isinstance(p, Platform) else Platform(**p)
                key = _norm_key(plat.platform_handle)
                if not key:
                    raise ValueError("platform_handle must be non-empty")
                if key in self._platforms_by_handle:
                    raise ValueError(f"Duplicate platform_handle: {plat.platform_handle}")
                self._platforms_by_handle[key] = plat
                validated.append(plat)
            except ValidationError as ve:
                errors.append({"index": idx, "item": p, "errors": ve.errors()})
            except Exception as exc:
                errors.append({"index": idx, "item": p, "errors": str(exc)})
        if errors:
            raise ValidationError(errors, model=Organization)
        # replace raw list with validated models
        object.__setattr__(self, "platforms", validated)
        return self

    # loaders
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Organization":
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "Organization":
        payload = json.loads(json_str)
        return cls.from_dict(payload)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Organization":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    # accessors
    def get_platform(self, platform_handle: str) -> Optional[Platform]:
        return self._platforms_by_handle.get(_norm_key(platform_handle))

    def list_platform_handles(self) -> List[str]:
        return [p.platform_handle for p in self._platforms_by_handle.values()]

    def to_dict(self) -> Dict[str, Any]:
        # serialize org plus platforms
        out = self.model_dump()
        out["platforms"] = [p.model_dump_with_props() for p in self.platforms]
        return out
