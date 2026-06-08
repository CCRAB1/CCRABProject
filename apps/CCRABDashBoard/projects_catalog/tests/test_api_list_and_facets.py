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
    utc_datetime,
)


class ProjectListAndFacetsApiTests(TestCase):
    def setUp(self):
        self.project_type_air = create_product_type("Air Quality")
        self.project_type_water = create_product_type("Water Quality")
        self.category_data = create_product_category("Data")

        self.project_one = create_project(
            "Canal Restoration",
            project_full_title="Canal Restoration Initiative",
            project_description="Improves water quality in Uptown neighborhoods.",
            keywords=["uptown", "canal"],
            neighborhood="Uptown",
            start_date=utc_datetime(2023, 1, 1),
            end_date=utc_datetime(2023, 12, 1),
        )
        self.project_two = create_project(
            "Harbor Cleanup",
            project_full_title="Harbor Cleanup Program",
            project_description="Cleans downtown shorelines and wetlands.",
            keywords=["downtown", "harbor"],
            neighborhood="Downtown",
        )
        self.project_three = create_project(
            "Regional Research",
            neighborhood="",
            keywords=["research"],
        )

        create_picture(
            self.project_one,
            name="Canal Hero",
            picture_path="projects_catalog/project_pictures/1/canal-hero.jpg",
        )

        create_hosting_location(
            self.project_one,
            data_type="Dataset",
            data_summary="Canal data feed",
            product_category=self.category_data,
            product_types=[self.project_type_air],
        )
        create_hosting_location(
            self.project_one,
            data_type="Dashboard",
            data_summary="Canal dashboard",
            product_category=self.category_data,
            product_types=[self.project_type_air],
        )
        create_hosting_location(
            self.project_two,
            data_type="Report",
            data_summary="Harbor report",
            product_category=self.category_data,
            product_types=[self.project_type_water],
        )
        user_model = get_user_model()
        self.api_user = user_model.objects.create_user(
            username="api-user",
            password="test-pass-123",
        )
        refresh = RefreshToken.for_user(self.api_user)
        self.access_token = str(refresh.access_token)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {self.access_token}"

    def _result_slugs(self, payload):
        slugs = []
        for row in payload.get("results", []):
            slugs.append(row.get("slug"))
        return slugs

    def test_project_list_requires_authentication(self):
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)

        response = self.client.get(reverse("project-list-api"))

        self.assertEqual(response.status_code, 401)

    def test_project_list_returns_expected_envelope(self):
        response = self.client.get(reverse("project-list-api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("count", payload)
        self.assertIn("page", payload)
        self.assertIn("total_pages", payload)
        self.assertIn("displaying", payload)
        self.assertIn("results", payload)
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["displaying"]["start"], 1)
        self.assertEqual(payload["displaying"]["end"], 3)

    def test_project_list_result_uses_database_field_names_and_project_url(self):
        response = self.client.get(reverse("project-list-api"))

        payload = response.json()
        first_row = payload["results"][0]
        self.assertEqual(first_row["slug"], self.project_one.slug)
        self.assertEqual(first_row["project_name"], self.project_one.project_name)
        self.assertEqual(
            first_row["project_full_title"],
            self.project_one.project_full_title,
        )
        self.assertIn(
            f"/projects_catalog/{self.project_one.slug}/",
            first_row["project_detail_url"],
        )
        self.assertEqual(len(first_row["pictures"]), 1)
        self.assertIn("picture_path", first_row["pictures"][0])

    def test_project_list_filters_by_query(self):
        response = self.client.get(reverse("project-list-api"), {"q": "wetlands"})

        payload = response.json()
        slugs = self._result_slugs(payload)
        self.assertEqual(slugs, [self.project_two.slug])

    def test_project_list_keywords_filter_takes_precedence_over_query(self):
        response = self.client.get(
            reverse("project-list-api"),
            {"q": "wetlands", "keywords": "uptown"},
        )

        payload = response.json()
        slugs = self._result_slugs(payload)
        self.assertEqual(slugs, [self.project_one.slug])

    def test_project_list_filters_by_project_type_case_insensitive(self):
        response = self.client.get(
            reverse("project-list-api"),
            {"project_type": "air quality"},
        )

        payload = response.json()
        slugs = self._result_slugs(payload)
        self.assertEqual(slugs, [self.project_one.slug])

    def test_project_list_distinct_avoids_duplicate_rows_from_joins(self):
        response = self.client.get(
            reverse("project-list-api"),
            {"project_type": self.project_type_air.name},
        )

        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(len(payload["results"]), 1)

    def test_project_list_filters_by_neighborhood(self):
        response = self.client.get(
            reverse("project-list-api"),
            {"neighborhood": "down"},
        )

        payload = response.json()
        slugs = self._result_slugs(payload)
        self.assertEqual(slugs, [self.project_two.slug])

    def test_project_list_filters_by_region(self):
        response = self.client.get(
            reverse("project-list-api"),
            {"region": "uptown"},
        )

        payload = response.json()
        slugs = self._result_slugs(payload)
        self.assertEqual(slugs, [self.project_one.slug])

    def test_project_list_paginates_results(self):
        next_index = 1
        while next_index <= 13:
            create_project(f"Extra Project {next_index}")
            next_index += 1

        response_page_one = self.client.get(reverse("project-list-api"), {"page": 1})
        response_page_two = self.client.get(reverse("project-list-api"), {"page": 2})

        payload_one = response_page_one.json()
        payload_two = response_page_two.json()
        self.assertEqual(payload_one["count"], 16)
        self.assertEqual(payload_one["total_pages"], 2)
        self.assertEqual(len(payload_one["results"]), 12)
        self.assertEqual(payload_one["displaying"]["start"], 1)
        self.assertEqual(payload_one["displaying"]["end"], 12)

        self.assertEqual(len(payload_two["results"]), 4)
        self.assertEqual(payload_two["displaying"]["start"], 13)
        self.assertEqual(payload_two["displaying"]["end"], 16)

    def test_project_facets_returns_sorted_types_and_distinct_neighborhoods(self):
        response = self.client.get(reverse("project-facets-api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["project_types"], ["Air Quality", "Water Quality"])
        self.assertEqual(payload["neighborhoods"], ["Downtown", "Uptown"])
        self.assertEqual(payload["neighborhood"], payload["neighborhoods"])
        self.assertEqual(payload["regions"], payload["neighborhoods"])
