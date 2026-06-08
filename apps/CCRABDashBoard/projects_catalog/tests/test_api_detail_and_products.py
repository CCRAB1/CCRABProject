from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from projects_catalog.tests.factories import (
    create_hosting_location,
    create_partner,
    create_picture,
    create_product_category,
    create_product_type,
    create_project,
    utc_datetime,
)


class ProjectDetailAndProductsApiTests(TestCase):
    def setUp(self):
        self.category_reports = create_product_category("Reports")
        self.category_dashboards = create_product_category("Dashboards")

        self.type_air = create_product_type("Air Quality")
        self.type_data = create_product_type("Data Products")
        self.type_water = create_product_type("Water Quality")

        self.project_one = create_project(
            "Project One",
            project_full_title="Project One Full Title",
            project_description=(
                "Project one paragraph one.\n\nProject one paragraph two."
            ),
            start_date=utc_datetime(2022, 1, 1),
            end_date=utc_datetime(2022, 6, 1),
            neighborhood="North Reserve",
            keywords=["north", "restoration"],
        )
        self.project_two = create_project(
            "Project Two",
            project_full_title="Project Two Full Title",
            project_description=(
                "Project two first paragraph.\n\nProject two second paragraph."
            ),
            project_impact="- Improve quality\n- Expand coverage",
            neighborhood="Central Reserve",
            keywords=["central", "monitoring"],
        )
        self.project_three = create_project(
            "Project Three",
            project_full_title="Project Three Full Title",
            neighborhood="South Reserve",
        )

        create_partner(self.project_two, "Partner One", "Org One")
        create_partner(self.project_two, "Partner Two", "Org Two")
        create_picture(
            self.project_two,
            name="Featured",
            picture_path="projects_catalog/project_pictures/2/featured.jpg",
        )
        create_picture(
            self.project_two,
            name="Gallery Two",
            picture_path="projects_catalog/project_pictures/2/gallery-two.jpg",
        )

        self.project_two_report_location = create_hosting_location(
            self.project_two,
            data_type="Report",
            data_summary="Annual report summary",
            product_category=self.category_reports,
            product_types=[self.type_water, self.type_air],
        )
        self.project_two_dashboard_location = create_hosting_location(
            self.project_two,
            data_type="Dashboard",
            data_summary="Dashboard summary",
            product_category=self.category_dashboards,
            product_types=[self.type_data, self.type_air],
        )
        self.project_two_uncategorized_location = create_hosting_location(
            self.project_two,
            data_type="Dataset",
            data_summary="Open dataset summary",
            product_category=None,
            product_types=[self.type_data],
            url="https://example.com/open-dataset",
        )

        self.fallback_project = create_project(
            "Harbor Cleanup 2025!",
            slug="harbor-cleanup-custom",
        )
        user_model = get_user_model()
        self.api_user = user_model.objects.create_user(
            username="api-user-detail",
            password="test-pass-123",
        )
        refresh = RefreshToken.for_user(self.api_user)
        self.access_token = str(refresh.access_token)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {self.access_token}"

    def test_project_detail_api_requires_authentication(self):
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)

        response = self.client.get(
            reverse("project-detail-api", kwargs={"code": self.project_two.slug})
        )

        self.assertEqual(response.status_code, 401)

    def test_project_detail_api_resolves_project_by_slug(self):
        response = self.client.get(
            reverse("project-detail-api", kwargs={"code": self.project_two.slug})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["slug"], self.project_two.slug)
        self.assertEqual(
            payload["project_full_title"],
            self.project_two.project_full_title,
        )

    def test_project_detail_api_resolves_project_by_numeric_id(self):
        response = self.client.get(
            reverse("project-detail-api", kwargs={"code": str(self.project_two.pk)})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["slug"], self.project_two.slug)

    def test_project_detail_api_resolves_project_by_slugified_name_fallback(self):
        response = self.client.get(
            reverse("project-detail-api", kwargs={"code": "harbor-cleanup-2025"})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["slug"], self.fallback_project.slug)
        self.assertEqual(
            payload["project_full_title"],
            self.fallback_project.project_full_title,
        )

    def test_project_detail_api_returns_404_for_unknown_project(self):
        response = self.client.get(
            reverse("project-detail-api", kwargs={"code": "does-not-exist"})
        )

        self.assertEqual(response.status_code, 404)

    def test_project_detail_api_payload_contract(self):
        response = self.client.get(
            reverse("project-detail-api", kwargs={"code": self.project_two.slug})
        )

        payload = response.json()
        self.assertIn("partners", payload)
        self.assertIn("pictures", payload)
        self.assertIn("hosting_locations", payload)
        self.assertIn("previous_project", payload)
        self.assertIn("next_project", payload)
        self.assertNotIn("team", payload)
        self.assertNotIn("taxonomy", payload)
        self.assertNotIn("gallery", payload)
        self.assertNotIn("nav", payload)
        self.assertEqual(
            payload["project_description"],
            self.project_two.project_description,
        )
        self.assertEqual(payload["project_impact"], self.project_two.project_impact)
        self.assertEqual(payload["project_lead"], self.project_two.project_lead)
        self.assertEqual(len(payload["pictures"]), 2)
        self.assertEqual(len(payload["partners"]), 2)

        product_type_names = []
        for location in payload["hosting_locations"]:
            self.assertIn("data_summary", location)
            self.assertNotIn("data_summary_file", location)
            for product_type in location.get("product_types", []):
                name = product_type.get("name")
                if name and name not in product_type_names:
                    product_type_names.append(name)
        product_type_names.sort()
        self.assertEqual(
            product_type_names,
            ["Air Quality", "Data Products", "Water Quality"],
        )

    def test_project_detail_api_previous_and_next_navigation(self):
        response = self.client.get(
            reverse("project-detail-api", kwargs={"code": self.project_two.slug})
        )

        payload = response.json()
        previous_project = payload["previous_project"]
        next_project = payload["next_project"]
        self.assertIsNotNone(previous_project)
        self.assertIsNotNone(next_project)
        self.assertEqual(
            previous_project["project_full_title"],
            self.project_one.project_full_title,
        )
        self.assertIn(
            f"/projects_catalog/{self.project_one.slug}/",
            previous_project["project_detail_url"],
        )
        self.assertEqual(
            next_project["project_full_title"],
            self.project_three.project_full_title,
        )
        self.assertIn(
            f"/projects_catalog/{self.project_three.slug}/",
            next_project["project_detail_url"],
        )

    def test_project_products_api_groups_locations_by_category(self):
        response = self.client.get(
            reverse("project-products-api", kwargs={"code": self.project_two.slug})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["slug"], self.project_two.slug)

        categories = payload["categories"]
        self.assertIn("Reports", categories)
        self.assertIn("Dashboards", categories)
        self.assertIn("Uncategorized", categories)
        self.assertEqual(len(categories["Reports"]), 1)
        self.assertEqual(len(categories["Dashboards"]), 1)
        self.assertEqual(len(categories["Uncategorized"]), 1)

    def test_project_products_api_uses_resource_detail_url(self):
        response = self.client.get(
            reverse("project-products-api", kwargs={"code": self.project_two.slug})
        )

        payload = response.json()
        report_items = payload["categories"]["Reports"]
        first_item = report_items[0]
        expected_path = (
            f"/projects_catalog/{self.project_two.slug}/resource/"
            f"{self.project_two_report_location.slug}/"
        )
        self.assertEqual(first_item["project_id"], self.project_two.id)
        self.assertEqual(first_item["product_category_id"], self.category_reports.id)
        self.assertEqual(
            sorted(first_item["product_type_id"]),
            sorted([self.type_water.id, self.type_air.id]),
        )
        self.assertIn(expected_path, first_item["resource_detail_url"])
