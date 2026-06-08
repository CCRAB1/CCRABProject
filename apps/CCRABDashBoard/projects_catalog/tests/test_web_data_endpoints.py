from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from projects_catalog.tests.factories import (
    create_hosting_location,
    create_picture,
    create_product_category,
    create_product_type,
    create_project,
)


class ProjectWebDataEndpointTests(TestCase):
    def setUp(self):
        self.project_type = create_product_type("Air Quality")
        self.category = create_product_category("Data")

        self.project = create_project(
            "Canal Restoration",
            project_full_title="Canal Restoration Initiative",
            project_description=(
                "Improves water quality in Uptown neighborhoods."
                "\n\nSecond paragraph for detail payload."
            ),
            neighborhood="Uptown",
        )
        create_picture(
            self.project,
            name="Canal Hero",
            picture_path="projects_catalog/project_pictures/1/canal-hero.jpg",
        )
        create_hosting_location(
            self.project,
            data_type="Dataset",
            data_summary="Canal data feed",
            product_category=self.category,
            product_types=[self.project_type],
        )

    def test_project_list_web_data_is_public(self):
        response = self.client.get(reverse("project-list-web-data"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("results", payload)
        self.assertGreaterEqual(payload.get("count", 0), 1)

    def test_project_facets_web_data_is_public(self):
        response = self.client.get(reverse("project-facets-web-data"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("project_types", payload)
        self.assertIn("Air Quality", payload["project_types"])

    def test_project_detail_web_data_is_public(self):
        response = self.client.get(
            reverse("project-detail-web-data", kwargs={"code": self.project.slug})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["slug"], self.project.slug)
        self.assertEqual(payload["project_full_title"], self.project.project_full_title)
        self.assertEqual(
            payload["project_description"],
            self.project.project_description,
        )

    def test_project_products_web_data_is_public(self):
        response = self.client.get(
            reverse("project-products-web-data", kwargs={"code": self.project.slug})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["slug"], self.project.slug)
        self.assertIn("Data", payload["categories"])

    def test_project_list_web_data_matches_api_payload(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="shared-payload-user",
            password="test-pass-123",
        )
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        api_response = self.client.get(
            reverse("project-list-api"),
            {"q": "Canal"},
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        web_response = self.client.get(
            reverse("project-list-web-data"),
            {"q": "Canal"},
        )

        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(web_response.status_code, 200)
        api_payload = api_response.json()
        web_payload = web_response.json()
        self.assertEqual(api_payload["count"], web_payload["count"])
        self.assertEqual(api_payload["results"], web_payload["results"])
