from __future__ import annotations

import json

import pytest

from datautilities.tsi_api import JSON_ACCEPT, TSIExternalAPIClient


class FakeResponse:
    def __init__(
        self,
        payload,
        *,
        status_code: int = 200,
        content_type: str = "application/json",
        url: str = "https://example.test",
    ):
        self.payload = payload
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.url = url
        if isinstance(payload, str):
            self.text = payload
            self.content = payload.encode()
        elif payload is None:
            self.text = ""
            self.content = b""
        else:
            self.text = json.dumps(payload)
            self.content = self.text.encode()

    def json(self):
        if isinstance(self.payload, str):
            raise ValueError("not json")
        return self.payload


class FakeSession:
    def __init__(self, *responses: FakeResponse):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return self.responses.pop(0)


def token_response(access_token: str = "abc123") -> FakeResponse:
    return FakeResponse(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": "3599",
            "issued_at": "1653336174629",
        }
    )


def test_authenticate_uses_client_credentials_form_body():
    session = FakeSession(token_response())
    client = TSIExternalAPIClient(
        client_id="client-id",
        client_secret="client-secret",
        session=session,
    )

    token = client.authenticate()

    assert token.access_token == "abc123"
    method, url, kwargs = session.requests[0]
    assert method == "POST"
    assert url.endswith("/oauth/client_credential/accesstoken")
    assert kwargs["params"] == {"grant_type": "client_credentials"}
    assert kwargs["data"] == {
        "client_id": "client-id",
        "client_secret": "client-secret",
    }
    assert kwargs["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert kwargs["headers"]["Accept"] == JSON_ACCEPT


def test_list_devices_adds_bearer_token_and_spec_filters():
    session = FakeSession(FakeResponse([{"device_id": "device-1"}]))
    client = TSIExternalAPIClient(access_token="token", session=session)

    devices = client.list_devices(model="8143", is_public=True, include_shared=False)

    assert devices == [{"device_id": "device-1"}]
    method, url, kwargs = session.requests[0]
    assert method == "GET"
    assert url.endswith("/devices")
    assert kwargs["headers"]["Authorization"] == "Bearer token"
    assert kwargs["headers"]["Accept"] == JSON_ACCEPT
    assert kwargs["params"] == {
        "model": "8143",
        "is_public": "true",
        "include_shared": "false",
    }


def test_flat_telemetry_sends_repeated_telem_parameters():
    session = FakeSession(FakeResponse([{"serial": "81431234567", "mcpm2x5": 4.2}]))
    client = TSIExternalAPIClient(access_token="token", session=session)

    payload = client.get_flat_telemetry(
        age=1,
        telem=["serial", "mcpm2x5"],
    )

    assert payload == [{"serial": "81431234567", "mcpm2x5": 4.2}]
    method, url, kwargs = session.requests[0]
    assert method == "GET"
    assert url.endswith("/telemetry/flat-format")
    assert kwargs["params"] == [
        ("age", 1),
        ("telem[]", "serial"),
        ("telem[]", "mcpm2x5"),
    ]


def test_flat_telemetry_rejects_fields_outside_spec_enum():
    client = TSIExternalAPIClient(access_token="token", session=FakeSession())

    with pytest.raises(ValueError, match="Unsupported flat telemetry field"):
        client.get_flat_telemetry(telem=["definitely_not_in_the_spec"])
