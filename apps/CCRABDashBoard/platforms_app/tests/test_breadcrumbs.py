from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse


class PlatformBreadcrumbTests(SimpleTestCase):
    @patch("platforms_app.views._platform_collection_payload")
    @patch("platforms_app.views._platforms_dataset_query")
    def test_catalog_page_renders_breadcrumb(self, dataset_query, collection_payload):
        collection_payload.return_value = {}
        dataset_query.return_value = {
            "platform_recs": {"features": []},
            "platforms_jts_docs": {},
        }

        response = self.client.get(reverse("platform_catalog"))

        self.assertContains(response, 'aria-label="breadcrumbs"')
        self.assertContains(response, 'aria-current="page">Platforms</a>')

    def test_map_page_renders_breadcrumb(self):
        response = self.client.get(reverse("platforms_map"))

        self.assertContains(response, 'aria-label="breadcrumbs"')
        self.assertContains(response, 'aria-current="page">Map View</a>')

    def test_detail_page_renders_breadcrumb(self):
        response = self.client.get(reverse("platform_info", args=["Test Platform"]))

        self.assertContains(response, 'aria-label="breadcrumbs"')
        self.assertContains(response, "Test Platform")
