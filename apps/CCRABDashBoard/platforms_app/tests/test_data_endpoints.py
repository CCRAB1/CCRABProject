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
