from django.test import TestCase

from projects_catalog.serializers import (
    HostingLocationSerializer,
    ProjectCatalogPageSerializer,
)
from projects_catalog.tests.factories import (
    create_hosting_location,
    create_partner,
    create_picture,
    create_product_category,
    create_product_type,
    create_project,
)


class CatalogSerializerTests(TestCase):
    def setUp(self):
        self.project = create_project("Serializer Project")
        self.category = create_product_category("Data")
        self.product_type_air = create_product_type("Air Quality")
        self.product_type_data = create_product_type("Data Products")

    def test_hosting_location_serializer_exposes_database_field_names(self):
        location = create_hosting_location(
            self.project,
            data_type="Dataset",
            data_summary="Summary file text",
            product_category=self.category,
            product_types=[self.product_type_air],
        )

        serializer = HostingLocationSerializer(location)
        payload = serializer.data

        self.assertEqual(payload["project_id"], self.project.id)
        self.assertEqual(payload["data_summary"], "Summary file text")
        self.assertEqual(payload["product_category_id"], self.category.id)
        self.assertEqual(payload["product_type_id"], [self.product_type_air.id])
        self.assertEqual(len(payload["product_types"]), 1)
        self.assertEqual(payload["product_types"][0]["name"], "Air Quality")

    def test_hosting_location_serializer_accepts_database_field_names(self):
        serializer = HostingLocationSerializer(
            data={
                "project_id": self.project.id,
                "data_type": "Dashboard",
                "data_summary": "Dashboard summary",
                "url": "https://example.com/dashboard",
                "product_category_id": self.category.id,
                "product_type_id": [
                    self.product_type_air.id,
                    self.product_type_data.id,
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        location = serializer.save()
        self.assertEqual(location.data_summary, "Dashboard summary")
        self.assertEqual(location.product_category_id, self.category.id)

        product_type_ids = []
        for product_type in location.product_types.order_by("id"):
            product_type_ids.append(product_type.id)
        self.assertEqual(
            product_type_ids,
            [self.product_type_air.id, self.product_type_data.id],
        )

    def test_project_catalog_page_serializer_includes_nested_relations(self):
        create_partner(self.project, "Partner Name", "Partner Org")
        create_picture(
            self.project,
            name="Project Hero",
            picture_path="projects_catalog/project_pictures/serializer/hero.jpg",
        )
        create_hosting_location(
            self.project,
            data_type="Report",
            data_summary="Report summary",
            product_category=self.category,
            product_types=[self.product_type_air],
        )

        serializer = ProjectCatalogPageSerializer(self.project)
        payload = serializer.data

        self.assertEqual(payload["id"], self.project.id)
        self.assertEqual(payload["project_name"], self.project.project_name)
        self.assertEqual(len(payload["partners"]), 1)
        self.assertEqual(payload["partners"][0]["name"], "Partner Name")
        self.assertEqual(len(payload["pictures"]), 1)
        self.assertEqual(payload["pictures"][0]["name"], "Project Hero")
        self.assertEqual(len(payload["hosting_locations"]), 1)
        self.assertEqual(payload["hosting_locations"][0]["data_type"], "Report")
