from unittest import TestCase

from CCRABDashboard.api.client import (
    CCRABApiError,
    CCRABAuthenticationError,
    CCRABRestClient,
)


class FakeResponse:
    def __init__(self, status_code, payload=None, text="", url=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.url = url
        if payload is None and not text:
            self.content = b""
        else:
            self.content = b"response-body"

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append(
            {
                "method": method,
                "url": url,
                "kwargs": kwargs,
            }
        )
        response = self.responses.pop(0)
        response.url = url
        return response


class CCRABRestClientTests(TestCase):
    def test_register_user_stores_returned_tokens(self):
        session = FakeSession(
            [
                FakeResponse(
                    201,
                    {
                        "id": 10,
                        "username": "new-user",
                        "access": "access-token",
                        "refresh": "refresh-token",
                    },
                )
            ]
        )
        client = CCRABRestClient(base_url="http://example.test", session=session)

        payload = client.register_user(
            username="new-user",
            password="StrongPass123!",
            email="new-user@example.test",
        )

        self.assertEqual(payload["username"], "new-user")
        self.assertEqual(client.access_token, "access-token")
        self.assertEqual(client.refresh_token, "refresh-token")

        request = session.requests[0]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["url"], "http://example.test/api/register/")
        self.assertNotIn("Authorization", request["kwargs"]["headers"])
        self.assertEqual(
            request["kwargs"]["json"],
            {
                "username": "new-user",
                "password": "StrongPass123!",
                "email": "new-user@example.test",
            },
        )

    def test_obtain_token_stores_jwt_pair(self):
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "access": "access-token",
                        "refresh": "refresh-token",
                    },
                )
            ]
        )
        client = CCRABRestClient(session=session)

        client.obtain_token(username="api-user", password="secret")

        self.assertEqual(client.tokens.access, "access-token")
        self.assertEqual(client.tokens.refresh, "refresh-token")
        request = session.requests[0]
        self.assertEqual(request["url"], "http://127.0.0.1:8000/api/token/")
        self.assertEqual(
            request["kwargs"]["json"],
            {
                "username": "api-user",
                "password": "secret",
            },
        )

    def test_list_projects_adds_bearer_header_and_cleans_query_params(self):
        session = FakeSession([FakeResponse(200, {"results": []})])
        client = CCRABRestClient(
            access_token="access-token",
            base_url="http://example.test/",
            session=session,
        )

        client.list_projects(q="air", page=2, region="")

        request = session.requests[0]
        self.assertEqual(request["url"], "http://example.test/api/projects/")
        self.assertEqual(
            request["kwargs"]["headers"]["Authorization"],
            "Bearer access-token",
        )
        self.assertEqual(
            request["kwargs"]["params"],
            {
                "q": "air",
                "page": 2,
            },
        )

    def test_refreshes_access_token_once_after_unauthorized_response(self):
        session = FakeSession(
            [
                FakeResponse(401, {"detail": "expired"}),
                FakeResponse(200, {"access": "new-access"}),
                FakeResponse(200, {"results": []}),
            ]
        )
        client = CCRABRestClient(
            access_token="old-access",
            refresh_token="refresh-token",
            session=session,
        )

        client.list_projects()

        first_request = session.requests[0]
        refresh_request = session.requests[1]
        retry_request = session.requests[2]

        self.assertEqual(
            first_request["kwargs"]["headers"]["Authorization"],
            "Bearer old-access",
        )
        self.assertEqual(
            refresh_request["url"],
            "http://127.0.0.1:8000/api/token/refresh/",
        )
        self.assertNotIn("Authorization", refresh_request["kwargs"]["headers"])
        self.assertEqual(
            retry_request["kwargs"]["headers"]["Authorization"],
            "Bearer new-access",
        )

    def test_platform_configuration_defaults_to_purple_air_data_source(self):
        session = FakeSession([FakeResponse(200, {"organizations": {}})])
        client = CCRABRestClient(access_token="access-token", session=session)

        client.platform_configuration()

        request = session.requests[0]
        self.assertEqual(
            request["url"],
            "http://127.0.0.1:8000/api/system/platform_configuration/",
        )
        self.assertEqual(request["kwargs"]["params"], {"data_source": "purple_air"})

    def test_bbox_sequence_is_serialized_for_platform_queries(self):
        session = FakeSession([FakeResponse(200, [])])
        client = CCRABRestClient(access_token="access-token", session=session)

        client.list_platforms(name="PA", bbox=(-75.1, 39.9, -74.9, 40.2))

        request = session.requests[0]
        self.assertEqual(
            request["kwargs"]["params"],
            {
                "name": "PA",
                "bbox": "-75.1,39.9,-74.9,40.2",
            },
        )

    def test_authentication_error_raised_for_forbidden_response(self):
        session = FakeSession([FakeResponse(403, {"detail": "forbidden"})])
        client = CCRABRestClient(access_token="access-token", session=session)

        with self.assertRaises(CCRABAuthenticationError) as context:
            client.platform_configuration()

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.payload, {"detail": "forbidden"})

    def test_api_error_raised_for_other_error_responses(self):
        session = FakeSession([FakeResponse(500, {"detail": "server error"})])
        client = CCRABRestClient(access_token="access-token", session=session)

        with self.assertRaises(CCRABApiError) as context:
            client.list_projects()

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.payload, {"detail": "server error"})
