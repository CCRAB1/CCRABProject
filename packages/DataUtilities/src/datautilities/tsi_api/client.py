"""Python interface for the TSI Link External API v3.

The methods in this module map to the endpoints documented by
``tsi-external-api.yaml``:

* ``POST /oauth/client_credential/accesstoken``
* ``GET /devices``
* ``GET /devices/legacy-format``
* ``GET /telemetry``
* ``GET /telemetry/legacy-format``
* ``GET /telemetry/flat-format``
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import requests

DEFAULT_BASE_URL = "https://api-prd.tsilink.com/api/v3/external"
CLIENT_CREDENTIALS_GRANT_TYPE = "client_credentials"
JSON_ACCEPT = "application/json"
CSV_ACCEPT = "text/csv"

FLAT_TELEMETRY_FIELDS: tuple[str, ...] = (
    "model",
    "serial",
    "location",
    "is_public",
    "is_indoor",
    "mcpm1x0",
    "mcpm2x5",
    "mcpm4x0",
    "mcpm10",
    "ncpm0x5",
    "ncpm1x0",
    "ncpm2x5",
    "ncpm4x0",
    "ncpm10",
    "tpsize",
    "mcpm2x5_aqi",
    "mcpm10_aqi",
    "co2_ppm",
    "co_ppm",
    "baro_inhg",
    "o3_ppb",
    "no2_ppb",
    "so2_ppb",
    "ch2o_ppb",
    "voc_mgm3",
    "temperature",
    "rh",
)

DateParameter = str | date | datetime


@dataclass(frozen=True)
class TSIAccessToken:
    """OAuth access token returned by the TSI client-credentials flow."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    issued_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def authorization_header(self) -> str:
        token_type = self.token_type or "Bearer"
        return f"{token_type} {self.access_token}"

    @property
    def expires_at(self) -> datetime | None:
        if self.issued_at is None or self.expires_in is None:
            return None
        return self.issued_at + timedelta(seconds=self.expires_in)

    def is_expired(self, *, buffer_seconds: int = 60) -> bool:
        expires_at = self.expires_at
        if expires_at is None:
            return False
        return datetime.now(timezone.utc) >= expires_at - timedelta(
            seconds=buffer_seconds
        )


class TSIAPIError(RuntimeError):
    """Raised when the TSI API returns a non-success response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        payload: Any = None,
        response: requests.Response | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.payload = payload
        self.response = response


class TSIAuthenticationError(TSIAPIError):
    """Raised when OAuth credentials or bearer-token authorization fails."""


class TSIExternalAPIClient:
    """Reusable client for the TSI Link External API.

    The client can be constructed with either an existing bearer token or the
    OAuth client credentials. If client credentials are present, authenticated
    requests automatically obtain a token when needed.
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | TSIAccessToken | None = None,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.session = session or requests.Session()

        if isinstance(access_token, TSIAccessToken):
            self.token = access_token
        elif access_token:
            self.token = TSIAccessToken(access_token=access_token)
        else:
            self.token = None

    @classmethod
    def from_client_credentials(
        cls,
        client_id: str,
        client_secret: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        **kwargs: Any,
    ) -> TSIExternalAPIClient:
        client = cls(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            **kwargs,
        )
        client.authenticate()
        return client

    def authenticate(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> TSIAccessToken:
        """Request and store an OAuth access token using client credentials."""

        if client_id is not None:
            self.client_id = client_id
        if client_secret is not None:
            self.client_secret = client_secret

        if not self.client_id or not self.client_secret:
            raise TSIAuthenticationError(
                "TSI client_id and client_secret are required to request a token."
            )

        payload = self.post(
            "oauth/client_credential/accesstoken",
            auth=False,
            params={"grant_type": CLIENT_CREDENTIALS_GRANT_TYPE},
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            accept=JSON_ACCEPT,
        )
        if not isinstance(payload, dict):
            raise TSIAuthenticationError(
                "TSI token response did not contain a JSON object.",
                payload=payload,
            )
        return self._store_token_from_payload(payload)

    def set_access_token(
        self,
        access_token: str,
        *,
        token_type: str = "Bearer",
        expires_in: int | str | None = None,
        issued_at: datetime | str | int | None = None,
        raw: Mapping[str, Any] | None = None,
    ) -> TSIAccessToken:
        """Set a bearer token obtained outside this client."""

        token = TSIAccessToken(
            access_token=access_token,
            token_type=token_type,
            expires_in=self._coerce_int(expires_in),
            issued_at=self._parse_issued_at(issued_at),
            raw=dict(raw or {}),
        )
        self.token = token
        return token

    def list_devices(
        self,
        *,
        model: str | None = None,
        is_public: bool | None = None,
        is_indoor: bool | None = None,
        serial: str | None = None,
        account_id: str | None = None,
        include_shared: bool | None = None,
        device_id: str | None = None,
        legacy_format: bool = False,
        accept: str = JSON_ACCEPT,
        **params: Any,
    ) -> Any:
        """Retrieve devices for the authenticated account.

        Set ``legacy_format=True`` to call ``/devices/legacy-format``.
        """

        query_params = self._params(
            params,
            model=model,
            is_public=is_public,
            is_indoor=is_indoor,
            serial=serial,
            account_id=account_id,
            include_shared=include_shared,
            device_id=device_id,
        )
        path = "devices/legacy-format" if legacy_format else "devices"
        return self.get(path, params=query_params, accept=accept)

    def get_devices(self, **kwargs: Any) -> Any:
        """Alias for :meth:`list_devices`."""

        return self.list_devices(**kwargs)

    def list_devices_legacy(self, **kwargs: Any) -> Any:
        """Retrieve devices using the legacy response shape."""

        return self.list_devices(legacy_format=True, **kwargs)

    def get_telemetry(
        self,
        *,
        device_id: str | None = None,
        is_public: bool | None = None,
        serial: str | None = None,
        is_indoor: bool | None = None,
        include_shared: bool | None = None,
        model: str | None = None,
        age: int | None = None,
        start_date: DateParameter | None = None,
        end_date: DateParameter | None = None,
        latest_as_of_date: DateParameter | None = None,
        accept: str = JSON_ACCEPT,
        **params: Any,
    ) -> Any:
        """Retrieve telemetry in the current TSI v3 nested format."""

        query_params = self._telemetry_params(
            params,
            device_id=device_id,
            is_public=is_public,
            serial=serial,
            is_indoor=is_indoor,
            include_shared=include_shared,
            model=model,
            age=age,
            start_date=start_date,
            end_date=end_date,
            latest_as_of_date=latest_as_of_date,
        )
        return self.get("telemetry", params=query_params, accept=accept)

    def get_telemetry_csv(self, **kwargs: Any) -> str:
        """Retrieve telemetry using the API's CSV response option."""

        kwargs["accept"] = CSV_ACCEPT
        data = self.get_telemetry(**kwargs)
        if data is None:
            return ""
        return str(data)

    def get_telemetry_legacy(
        self,
        *,
        device_id: str | None = None,
        is_public: bool | None = None,
        serial: str | None = None,
        is_indoor: bool | None = None,
        include_shared: bool | None = None,
        model: str | None = None,
        age: int | None = None,
        start_date: DateParameter | None = None,
        end_date: DateParameter | None = None,
        latest_as_of_date: DateParameter | None = None,
        accept: str = JSON_ACCEPT,
        **params: Any,
    ) -> Any:
        """Retrieve telemetry using the legacy response shape."""

        query_params = self._telemetry_params(
            params,
            device_id=device_id,
            is_public=is_public,
            serial=serial,
            is_indoor=is_indoor,
            include_shared=include_shared,
            model=model,
            age=age,
            start_date=start_date,
            end_date=end_date,
            latest_as_of_date=latest_as_of_date,
        )
        return self.get("telemetry/legacy-format", params=query_params, accept=accept)

    def get_flat_telemetry(
        self,
        *,
        device_id: str | None = None,
        is_public: bool | None = None,
        serial: str | None = None,
        is_indoor: bool | None = None,
        include_shared: bool | None = None,
        model: str | None = None,
        age: int | None = None,
        start_date: DateParameter | None = None,
        end_date: DateParameter | None = None,
        latest_as_of_date: DateParameter | None = None,
        telem: Iterable[str] | None = None,
        **params: Any,
    ) -> Any:
        """Retrieve telemetry using the spec's flat table-like format.

        ``telem`` maps to repeated ``telem[]`` query parameters.
        """

        query_params = self._telemetry_params(
            params,
            device_id=device_id,
            is_public=is_public,
            serial=serial,
            is_indoor=is_indoor,
            include_shared=include_shared,
            model=model,
            age=age,
            start_date=start_date,
            end_date=end_date,
            latest_as_of_date=latest_as_of_date,
        )
        query_items = self._param_items(query_params)

        if telem is not None:
            for field_name in self._validate_flat_fields(telem):
                query_items.append(("telem[]", field_name))

        return self.get("telemetry/flat-format", params=query_items, accept=JSON_ACCEPT)

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = True,
        retry_on_unauthorized: bool = True,
        accept: str | None = JSON_ACCEPT,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make a request and return decoded JSON, text, or ``None``."""

        if auth:
            self._ensure_access_token()

        request_headers = self._headers(headers, auth=auth, accept=accept)
        request_kwargs = dict(kwargs)
        request_kwargs["headers"] = request_headers
        request_kwargs["timeout"] = self.timeout
        if params is not None:
            request_kwargs["params"] = params

        response = self.session.request(
            method.upper(),
            self._url(path),
            **request_kwargs,
        )
        if (
            response.status_code == 401
            and auth
            and retry_on_unauthorized
            and self.client_id
            and self.client_secret
        ):
            self.token = None
            self.authenticate()
            return self.request(
                method,
                path,
                auth=auth,
                retry_on_unauthorized=False,
                accept=accept,
                headers=headers,
                params=params,
                **kwargs,
            )

        self._raise_for_status(response)
        return self._decode_response(response)

    def _ensure_access_token(self) -> None:
        if self.token and not self.token.is_expired():
            return

        if self.client_id and self.client_secret:
            self.authenticate()
            return

        raise TSIAuthenticationError(
            "No valid TSI access token is available. Call authenticate(), pass "
            "client credentials, or initialize with access_token."
        )

    def _store_token_from_payload(self, payload: Mapping[str, Any]) -> TSIAccessToken:
        access_token = payload.get("access_token")
        if not access_token:
            raise TSIAuthenticationError(
                "TSI token response did not include an access_token.",
                payload=dict(payload),
            )

        return self.set_access_token(
            access_token=str(access_token),
            token_type=str(payload.get("token_type") or "Bearer"),
            expires_in=payload.get("expires_in"),
            issued_at=payload.get("issued_at"),
            raw=payload,
        )

    def _headers(
        self,
        headers: Mapping[str, str] | None,
        *,
        auth: bool,
        accept: str | None,
    ) -> dict[str, str]:
        request_headers: dict[str, str] = {}
        if accept:
            request_headers["Accept"] = accept
        if headers:
            request_headers.update(headers)
        if auth and self.token:
            request_headers["Authorization"] = self.token.authorization_header
        return request_headers

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _params(
        self,
        params: Mapping[str, Any] | None = None,
        **values: Any,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        if params:
            merged.update(params)
        for key, value in values.items():
            if value is not None and value != "":
                merged[key] = value

        cleaned: dict[str, Any] = {}
        for key, value in merged.items():
            if value is None or value == "":
                continue
            cleaned[key] = self._format_query_value(value)
        return cleaned

    def _telemetry_params(
        self,
        params: Mapping[str, Any] | None = None,
        **values: Any,
    ) -> dict[str, Any]:
        return self._params(params, **values)

    def _param_items(self, params: Mapping[str, Any]) -> list[tuple[str, Any]]:
        items: list[tuple[str, Any]] = []
        for key, value in params.items():
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                for item in value:
                    items.append((key, self._format_query_value(item)))
            else:
                items.append((key, value))
        return items

    def _validate_flat_fields(self, fields: Iterable[str]) -> list[str]:
        values = list(fields)
        allowed = set(FLAT_TELEMETRY_FIELDS)
        invalid = [value for value in values if value not in allowed]
        if invalid:
            allowed_text = ", ".join(FLAT_TELEMETRY_FIELDS)
            invalid_text = ", ".join(invalid)
            raise ValueError(
                f"Unsupported flat telemetry field(s): {invalid_text}. "
                f"Allowed fields: {allowed_text}."
            )
        return values

    def _format_query_value(self, value: Any) -> Any:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, datetime):
            return value.isoformat().replace("+00:00", "Z")
        if isinstance(value, date):
            return value.isoformat()
        return value

    def _path_part(self, value: str | int) -> str:
        return quote(str(value).strip("/"), safe="")

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.status_code < 400:
            return

        payload = self._safe_json(response)
        message = f"TSI API request failed with status {response.status_code}"
        url = getattr(response, "url", None)
        if url:
            message = f"{message}: {url}"

        detail = self._error_detail(payload)
        if detail:
            message = f"{message}: {detail}"

        error_class = TSIAuthenticationError
        if response.status_code not in (401, 403):
            error_class = TSIAPIError

        raise error_class(
            message,
            status_code=response.status_code,
            url=url,
            payload=payload,
            response=response,
        )

    def _decode_response(self, response: requests.Response) -> Any:
        content = getattr(response, "content", b"")
        if response.status_code == 204 or not content:
            return None

        content_type = response.headers.get("Content-Type", "").lower()
        if "application/json" in content_type:
            return response.json()

        text = response.text
        if not text:
            return None
        return text

    def _safe_json(self, response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return getattr(response, "text", None)

    def _error_detail(self, payload: Any) -> str | None:
        if isinstance(payload, str):
            return payload.strip() or None
        if not isinstance(payload, Mapping):
            return None

        fault = payload.get("fault")
        if isinstance(fault, Mapping):
            faultstring = fault.get("faultstring")
            if faultstring:
                return str(faultstring)

        for key in ("Error", "error", "message", "detail"):
            value = payload.get(key)
            if value:
                return str(value)

        return None

    def _parse_issued_at(self, value: datetime | str | int | None) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)

        text = str(value)
        if text.isdigit():
            return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc)

        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        except ValueError:
            return None

    def _coerce_int(self, value: int | str | None) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
