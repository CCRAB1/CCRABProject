from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from platforms_app.catalog_categories import (
    PLATFORM_CATALOG_CATEGORIES,
    group_catalog_platforms,
)


class CatalogCategoryTests(SimpleTestCase):
    def test_groups_statuses_once_and_preserves_order(self):
        features = []
        for active in (0, 1, None, 1):
            features.append({"properties": {"active": active}})

        groups = group_catalog_platforms(features)

        self.assertEqual(groups[0]["features"], [features[1], features[3]])
        self.assertEqual(groups[1]["features"], [features[0], features[2]])

    def test_new_category_can_precede_fallback_without_duplicates(self):
        categories = (
            PLATFORM_CATALOG_CATEGORIES[0],
            {"key": "planned", "label": "Planned", "matches": lambda p: p.get("planned")},
            PLATFORM_CATALOG_CATEGORIES[1],
        )
        feature = {"properties": {"active": 0, "planned": True}}

        groups = group_catalog_platforms([feature], categories)

        self.assertEqual(groups[0]["features"], [])
        self.assertEqual(groups[1]["features"], [feature])
        self.assertEqual(groups[2]["features"], [])

    @patch("platforms_app.views._platform_collection_payload", return_value={})
    @patch("platforms_app.views._platforms_dataset_query")
    def test_catalog_renders_cards_under_ordered_headings(self, dataset_query, collection):
        features = []
        for name, active in (("Retired", 0), ("Operating", 1)):
            features.append({"properties": {"short_name": name, "active": active}})
        dataset_query.return_value = {
            "platform_recs": {"features": features},
            "platforms_jts_docs": {},
        }

        response = self.client.get(reverse("platform_catalog"))

        self.assertContains(response, "Operating", count=3)
        html = response.content.decode()
        self.assertLess(html.index('id="platform-category-active"'), html.index("Operating"))
        self.assertLess(html.index("Operating"), html.index('id="platform-category-non-active"'))
        self.assertLess(html.index('id="platform-category-non-active"'), html.index("Retired"))

    def test_empty_catalog_keeps_both_categories(self):
        groups = group_catalog_platforms([])
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["features"], [])
        self.assertEqual(groups[1]["features"], [])
