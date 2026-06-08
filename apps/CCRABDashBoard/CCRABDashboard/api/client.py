"""Small Python client for the CCRAB Dashboard REST API.

The client is intentionally independent of Django runtime setup so scripts can
import it from this repository and call the deployed API over HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


@dataclass
class TokenBundle:
    """JWT tokens returned by the CCRAB API."""

    access: str
    refresh: str | None = None


class CCRABApiError(RuntimeError):
    """Raised when the CCRAB API returns a non-success response."""

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


class CCRABAuthenticationError(CCRABApiError):
    """Raised when authentication or authorization fails."""


class CCRABRestClient:
    """Reusable REST client for scripts that need CCRAB API data."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
        api_prefix: str = "api",
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_prefix = api_prefix.strip("/")
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.timeout = timeout
        self.session = session or requests.Session()

    @classmethod
    def from_credentials(
        cls,
        username: str,
        password: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        **kwargs: Any,
    ) -> CCRABRestClient:
        client = cls(base_url=base_url, **kwargs)
        client.obtain_token(username=username, password=password)
        return client

    @classmethod
    def from_registration(
        cls,
        username: str,
        password: str,
        *,
        email: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        **kwargs: Any,
    ) -> CCRABRestClient:
        client = cls(base_url=base_url, **kwargs)
        client.register_user(username=username, password=password, email=email)
        return client

    @property
    def tokens(self) -> TokenBundle | None:
        if not self.access_token:
            return None
        return TokenBundle(access=self.access_token, refresh=self.refresh_token)

    def set_tokens(self, access: str, refresh: str | None = None) -> TokenBundle:
        self.access_token = access
        if refresh is not None:
            self.refresh_token = refresh
        return TokenBundle(access=self.access_token, refresh=self.refresh_token)

    def register_user(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
        store_tokens: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "username": username,
            "password": password,
        }
        if email is not None:
            payload["email"] = email

        data = self.post("register/", json=payload, auth=False)
        if store_tokens:
            self._store_tokens_from_payload(data)
        return data

    def obtain_token(self, username: str, password: str) -> dict[str, Any]:
        payload = {
            "username": username,
            "password": password,
        }
        data = self.post("token/", json=payload, auth=False)
        self._store_tokens_from_payload(data)
        return data

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        return self.obtain_token(username=username, password=password)

    def refresh_access_token(self) -> dict[str, Any]:
        if not self.refresh_token:
            raise CCRABAuthenticationError("No refresh token is available.")

        payload = {"refresh": self.refresh_token}
        data = self.post("token/refresh/", json=payload, auth=False)
        self._store_tokens_from_payload(data)
        return data

    def list_projects(
        self,
        *,
        q: str | None = None,
        keywords: str | None = None,
        project_type: str | None = None,
        neighborhood: str | None = None,
        region: str | None = None,
        page: int | str | None = None,
        **params: Any,
    ) -> Any:
        query_params = self._params(
            params,
            q=q,
            keywords=keywords,
            project_type=project_type,
            neighborhood=neighborhood,
            region=region,
            page=page,
        )
        return self.get("projects/", params=query_params)

    def project_facets(self) -> Any:
        return self.get("projects/facets/")

    def get_project(self, code: str | int) -> Any:
        return self.get(f"projects/{self._path_part(code)}/")

    def get_project_products(self, code: str | int) -> Any:
        return self.get(f"projects/{self._path_part(code)}/products/")

    def list_platforms(
        self,
        *,
        name: str | None = None,
        bbox: str | tuple[Any, Any, Any, Any] | list[Any] | None = None,
        **params: Any,
    ) -> Any:
        query_params = self._params(
            params,
            name=name,
            bbox=self._format_bbox(bbox),
        )
        return self.get("platforms/", params=query_params)

    def get_platform(
        self,
        short_name: str,
        *,
        bbox: str | tuple[Any, Any, Any, Any] | list[Any] | None = None,
        **params: Any,
    ) -> Any:
        query_params = self._params(params, bbox=self._format_bbox(bbox))
        return self.get(
            f"platforms/{self._path_part(short_name)}/",
            params=query_params,
        )

    def legacy_platform_info(
        self,
        *,
        name: str | None = None,
        bbox: str | tuple[Any, Any, Any, Any] | list[Any] | None = None,
        **params: Any,
    ) -> Any:
        query_params = self._params(
            params,
            name=name,
            bbox=self._format_bbox(bbox),
        )
        return self.get("v1/platform_info/", params=query_params)

    def platform_configuration(
        self,
        *,
        data_source: str = "purple_air",
        **params: Any,
    ) -> Any:
        query_params = self._params(params, data_source=data_source)
        return self.get("system/platform_configuration/", params=query_params)

    def get_platform_configuration(self, **params: Any) -> Any:
        return self.platform_configuration(**params)

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
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Any:
        url = self._url(path)
        request_headers = self._headers(headers, auth=auth)
        request_kwargs = dict(kwargs)
        request_kwargs["headers"] = request_headers
        request_kwargs.setdefault("timeout", self.timeout)

        response = self.session.request(method.upper(), url, **request_kwargs)
        if (
            response.status_code == 401
            and auth
            and retry_on_unauthorized
            and self.refresh_token
        ):
            self.refresh_access_token()
            return self.request(
                method,
                path,
                auth=auth,
                retry_on_unauthorized=False,
                headers=headers,
                **kwargs,
            )

        self._raise_for_status(response)
        return self._decode_response(response)

    def _store_tokens_from_payload(self, payload: Any) -> TokenBundle:
        if not isinstance(payload, dict):
            raise CCRABAuthenticationError(
                "Authentication response was not a JSON object."
            )

        access = payload.get("access")
        refresh = payload.get("refresh")

        if not access:
            raise CCRABAuthenticationError(
                "Authentication response did not include an access token."
            )

        return self.set_tokens(access=access, refresh=refresh)

    def _url(self, path: str) -> str:
        clean_path = path.lstrip("/")
        if self.api_prefix and clean_path.startswith(f"{self.api_prefix}/"):
            clean_path = clean_path[len(self.api_prefix) + 1 :]
        if not self.api_prefix:
            return f"{self.base_url}/{clean_path}"
        return f"{self.base_url}/{self.api_prefix}/{clean_path}"

    def _headers(
        self,
        headers: dict[str, str] | None,
        *,
        auth: bool,
    ) -> dict[str, str]:
        request_headers: dict[str, str] = {}
        if headers:
            for key, value in headers.items():
                request_headers[key] = value

        if auth and self.access_token:
            request_headers["Authorization"] = f"Bearer {self.access_token}"

        return request_headers

    def _params(
        self,
        params: dict[str, Any] | None = None,
        **values: Any,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        if params:
            for key, value in params.items():
                merged[key] = value

        for key, value in values.items():
            merged[key] = value

        cleaned: dict[str, Any] = {}
        for key, value in merged.items():
            if value is None or value == "":
                continue
            cleaned[key] = value
        return cleaned

    def _format_bbox(
        self,
        bbox: str | tuple[Any, Any, Any, Any] | list[Any] | None,
    ) -> str | None:
        if bbox is None or bbox == "":
            return None
        if isinstance(bbox, str):
            return bbox

        values = []
        for value in bbox:
            values.append(str(value))

        if len(values) != 4:
            raise ValueError("bbox must contain min_lon, min_lat, max_lon, max_lat.")
        return ",".join(values)

    def _path_part(self, value: str | int) -> str:
        return quote(str(value).strip("/"), safe="")

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.status_code < 400:
            return

        payload = self._safe_json(response)
        url = getattr(response, "url", None)
        message = f"CCRAB API request failed with status {response.status_code}"
        if url:
            message = f"{message}: {url}"

        error_class = CCRABApiError
        if response.status_code in (401, 403):
            error_class = CCRABAuthenticationError

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

        try:
            return response.json()
        except ValueError:
            return response.text

    def _safe_json(self, response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None
