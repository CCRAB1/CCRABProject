from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse


class PlatformDataEndpointTests(SimpleTestCase):
    def test_platform_list_api_requires_authentication(self):
        response = self.client.get(reverse("platform-list-api"))

        self.assertEqual(response.status_code, 401)

    def test_legacy_platform_list_api_requires_authentication(self):
        response = self.client.get(reverse("platforminfo"))

        self.assertEqual(response.status_code, 401)

    @patch("platforms_app.views._platform_collection_payload")
    def test_platform_list_web_data_is_public(self, payload_mock):
        payload_mock.return_value = [{"type": "FeatureCollection", "features": []}]

        response = self.client.get(reverse("platform-list-web-data"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"type": "FeatureCollection", "features": []}])

    @patch("platforms_app.views._platform_detail_payload")
    def test_platform_detail_api_requires_authentication(self, payload_mock):
        payload_mock.return_value = (
            object(),
            {"type": "Feature", "properties": {"short_name": "PA-01"}},
        )

        response = self.client.get(
            reverse("platform-detail-api", kwargs={"short_name": "PA-01"})
        )

        self.assertEqual(response.status_code, 401)

    @patch("platforms_app.views._platform_detail_payload")
    def test_platform_detail_web_data_is_public(self, payload_mock):
        payload_mock.return_value = (
            object(),
            {"type": "Feature", "properties": {"short_name": "PA-01"}},
        )

        response = self.client.get(
            reverse("platform-detail-web-data", kwargs={"short_name": "PA-01"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"type": "Feature", "properties": {"short_name": "PA-01"}},
        )

    @patch("platforms_app.views._platform_detail_payload")
    def test_platform_configuration_api_matches_page_payload(self, payload_mock):
        payload = {
            "type": "Feature",
            "properties": {
                "short_name": "PA-01",
                "long_name": "PurpleAir 01",
                "sensors": [],
                "images": [],
            },
        }
        payload_mock.return_value = (object(), payload)

        response = self.client.get(
            reverse("platform-configuration-api"),
            {"short_name": "PA-01"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        payload_mock.assert_called_once()
        self.assertEqual(payload_mock.call_args.kwargs["short_name"], "PA-01")

    def test_platform_configuration_api_requires_short_name(self):
        response = self.client.get(reverse("platform-configuration-api"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"short_name": ["This query parameter is required."]},
        )
