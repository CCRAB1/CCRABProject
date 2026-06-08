from django.test import TestCase
from django.urls import reverse

from projects_catalog.tests.factories import (
    create_hosting_location,
    create_product_category,
    create_product_type,
    create_project,
)


class ProjectResourcePageTests(TestCase):
    def setUp(self):
        self.project = create_project(
            "Resource Project",
            project_description="Project paragraph one.\n\nProject paragraph two.",
            neighborhood="Neighborhood A",
            keywords="air, water, habitat",
        )

        self.product_category = create_product_category("Data")
        self.product_type_air = create_product_type("Air Quality")
        self.product_type_data = create_product_type("Data Products")

        self.primary_resource = create_hosting_location(
            self.project,
            data_type="Dataset",
            data_summary="Primary resource title.\n\nPrimary resource details.",
            product_category=self.product_category,
            product_types=[self.product_type_air, self.product_type_data],
            url="https://example.com/primary-resource",
        )

    def test_resource_detail_page_resolves_by_resource_slug(self):
        response = self.client.get(
            reverse(
                "project-resource-detail",
                kwargs={
                    "code": self.project.slug,
                    "resource_slug": self.primary_resource.slug,
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("resource_payload", response.context)
        payload = response.context["resource_payload"]
        self.assertEqual(payload["resource_title"], "Primary resource title.")
        self.assertEqual(payload["resource_category"], "Data")

    def test_resource_detail_page_resolves_by_resource_numeric_id(self):
        response = self.client.get(
            reverse(
                "project-resource-detail",
                kwargs={
                    "code": self.project.slug,
                    "resource_slug": str(self.primary_resource.pk),
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        payload = response.context["resource_payload"]
        self.assertEqual(payload["resource_title"], "Primary resource title.")

    def test_resource_detail_page_returns_404_for_missing_resource(self):
        response = self.client.get(
            reverse(
                "project-resource-detail",
                kwargs={
                    "code": self.project.slug,
                    "resource_slug": "missing-resource",
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_resource_detail_page_uses_fallback_resource_paragraphs(self):
        fallback_resource = create_hosting_location(
            self.project,
            data_type="Map",
            data_summary="",
            url="https://example.com/map-resource",
            product_category=None,
            product_types=[],
        )

        response = self.client.get(
            reverse(
                "project-resource-detail",
                kwargs={
                    "code": self.project.slug,
                    "resource_slug": fallback_resource.slug,
                },
            )
        )

        payload = response.context["resource_payload"]
        self.assertEqual(
            payload["about_resource_paragraphs"],
            [
                "This resource type is Map.",
                "Use the external link below to access the resource.",
            ],
        )
        self.assertEqual(payload["resource_category"], "Uncategorized")

    def test_resource_detail_page_uses_default_message_when_details_missing(self):
        fallback_resource = create_hosting_location(
            self.project,
            data_type="",
            data_summary="",
            url="",
            product_category=None,
            product_types=[],
        )

        response = self.client.get(
            reverse(
                "project-resource-detail",
                kwargs={
                    "code": self.project.slug,
                    "resource_slug": fallback_resource.slug,
                },
            )
        )

        payload = response.context["resource_payload"]
        self.assertEqual(
            payload["about_resource_paragraphs"],
            ["Resource details were not provided for this item."],
        )

    def test_resource_detail_page_normalizes_keywords_and_focus_areas(self):
        response = self.client.get(
            reverse(
                "project-resource-detail",
                kwargs={
                    "code": self.project.slug,
                    "resource_slug": self.primary_resource.slug,
                },
            )
        )

        payload = response.context["resource_payload"]
        self.assertEqual(payload["keywords"], ["air", "water", "habitat"])
        self.assertEqual(payload["focus_areas"], ["Air Quality", "Data Products"])
        self.assertEqual(payload["neighborhoods"], ["Neighborhood A"])
