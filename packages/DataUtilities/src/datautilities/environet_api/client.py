"""Python interface for the Environet Search API v2.

The methods in this module map to the endpoints documented by Environet:

* ``POST /search/nodes``
* ``POST /search/data_points``
* ``POST /search/measurements``
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

import requests

DEFAULT_BASE_URL = "https://api.environet.io/v2"
JSON_ACCEPT = "application/json"
DATA_POINTS_INCLUDE = "data_points"

TimestampParameter = int | datetime


class EnvironetAPIError(RuntimeError):
    """Raised when the Environet API returns a non-success response."""

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


class EnvironetAuthenticationError(EnvironetAPIError):
    """Raised when a bearer token is missing or rejected."""


class EnvironetAPIClient:
    """Reusable client for the Environet Search API v2."""

    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ):
        if not access_token or not access_token.strip():
            raise EnvironetAuthenticationError(
                "An Environet bearer access token is required."
            )

        self.access_token = self._strip_bearer_prefix(access_token.strip())
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def search_nodes(
        self,
        *,
        node_ids: Sequence[str] | None = None,
        data_point_ids: Sequence[str] | None = None,
        from_timestamp: TimestampParameter | None = None,
        to_timestamp: TimestampParameter | None = None,
        last: int | None = None,
        include_data_points: bool = False,
        **query: Any,
    ) -> Any:
        """Retrieve nodes available to the authenticated account."""

        payload = self._search_query(
            query,
            node_ids=node_ids,
            data_point_ids=data_point_ids,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            last=last,
            includes=DATA_POINTS_INCLUDE if include_data_points else None,
        )
        return self.post("search/nodes", json=payload)

    def get_nodes(self, **kwargs: Any) -> Any:
        """Alias for :meth:`search_nodes`."""

        return self.search_nodes(**kwargs)

    def search_data_points(
        self,
        *,
        node_ids: Sequence[str] | None = None,
        data_point_ids: Sequence[str] | None = None,
        from_timestamp: TimestampParameter | None = None,
        to_timestamp: TimestampParameter | None = None,
        last: int | None = None,
        **query: Any,
    ) -> Any:
        """Retrieve data points available to the authenticated account."""

        payload = self._search_query(
            query,
            node_ids=node_ids,
            data_point_ids=data_point_ids,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            last=last,
        )
        return self.post("search/data_points", json=payload)

    def get_data_points(self, **kwargs: Any) -> Any:
        """Alias for :meth:`search_data_points`."""

        return self.search_data_points(**kwargs)

    def search_measurements(
        self,
        *,
        node_ids: Sequence[str] | None = None,
        data_point_ids: Sequence[str] | None = None,
        from_timestamp: TimestampParameter | None = None,
        to_timestamp: TimestampParameter | None = None,
        last: int | None = None,
        **query: Any,
    ) -> Any:
        """Retrieve measurements, optionally filtered by IDs or time range."""

        payload = self._search_query(
            query,
            node_ids=node_ids,
            data_point_ids=data_point_ids,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            last=last,
        )
        return self.post("search/measurements", json=payload)

    def get_measurements(self, **kwargs: Any) -> Any:
        """Alias for :meth:`search_measurements`."""

        return self.search_measurements(**kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make an authenticated request and return decoded JSON, text, or ``None``."""

        request_headers = {
            "Accept": JSON_ACCEPT,
            "Authorization": f"Bearer {self.access_token}",
        }
        if headers:
            request_headers.update(headers)

        request_kwargs = dict(kwargs)
        request_kwargs["headers"] = request_headers
        request_kwargs["timeout"] = self.timeout
        response = self.session.request(
            method.upper(),
            self._url(path),
            **request_kwargs,
        )
        self._raise_for_status(response)
        return self._decode_response(response)

    def _search_query(
        self,
        query: Mapping[str, Any] | None = None,
        *,
        node_ids: Sequence[str] | None = None,
        data_point_ids: Sequence[str] | None = None,
        from_timestamp: TimestampParameter | None = None,
        to_timestamp: TimestampParameter | None = None,
        last: int | None = None,
        includes: str | None = None,
    ) -> dict[str, Any]:
        if last is not None and (last < 0 or last > 100):
            raise ValueError("last must be between 0 and 100.")

        payload = dict(query or {})
        values = {
            "node_id": list(node_ids) if node_ids is not None else None,
            "data_point_id": (
                list(data_point_ids) if data_point_ids is not None else None
            ),
            "from": self._timestamp_milliseconds(from_timestamp),
            "to": self._timestamp_milliseconds(to_timestamp),
            "last": last,
            "includes": includes,
        }
        for key, value in values.items():
            if value is not None:
                payload[key] = value
        return payload

    def _timestamp_milliseconds(
        self, value: TimestampParameter | None
    ) -> int | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return int(value.timestamp() * 1000)
        if value < 0:
            raise ValueError("timestamps must be non-negative Unix milliseconds.")
        return value

    def _strip_bearer_prefix(self, access_token: str) -> str:
        prefix, separator, token = access_token.partition(" ")
        if separator and prefix.lower() == "bearer":
            if not token.strip():
                raise EnvironetAuthenticationError(
                    "An Environet bearer access token is required."
                )
            return token.strip()
        return access_token

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.status_code < 400:
            return

        payload = self._safe_json(response)
        message = f"Environet API request failed with status {response.status_code}"
        url = getattr(response, "url", None)
        if url:
            message = f"{message}: {url}"

        detail = self._error_detail(payload)
        if detail:
            message = f"{message}: {detail}"

        error_class = EnvironetAPIError
        if response.status_code in (401, 403):
            error_class = EnvironetAuthenticationError

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
        return response.text or None

    def _safe_json(self, response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return getattr(response, "text", None)

    def _error_detail(self, payload: Any) -> str | None:
        if isinstance(payload, str):
            return payload.strip() or None
        if isinstance(payload, Mapping):
            error = payload.get("error")
            if error:
                return str(error)
        return None
