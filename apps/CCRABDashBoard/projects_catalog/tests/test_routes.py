from django.test import SimpleTestCase
from django.urls import reverse


class CatalogRoutesTests(SimpleTestCase):
    def test_user_register_route_resolves(self):
        url = reverse("user_register")
        self.assertEqual(url, "/api/register/")

    def test_token_obtain_route_resolves(self):
        url = reverse("token_obtain_pair")
        self.assertEqual(url, "/api/token/")

    def test_token_refresh_route_resolves(self):
        url = reverse("token_refresh")
        self.assertEqual(url, "/api/token/refresh/")

    def test_projects_index_route_resolves(self):
        url = reverse("projects-index")
        self.assertEqual(url, "/projects_catalog/")

    def test_projects_map_route_resolves(self):
        url = reverse("projects-map")
        self.assertEqual(url, "/projects_catalog/map/")

    def test_project_detail_route_resolves(self):
        url = reverse("project-detail", kwargs={"code": "sample-project"})
        self.assertEqual(url, "/projects_catalog/sample-project/")

    def test_project_resource_detail_route_resolves(self):
        url = reverse(
            "project-resource-detail",
            kwargs={"code": "sample-project", "resource_slug": "sample-resource"},
        )
        self.assertEqual(
            url,
            "/projects_catalog/sample-project/resource/sample-resource/",
        )

    def test_project_list_api_route_resolves(self):
        url = reverse("project-list-api")
        self.assertEqual(url, "/api/projects/")

    def test_project_facets_api_route_resolves(self):
        url = reverse("project-facets-api")
        self.assertEqual(url, "/api/projects/facets/")

    def test_project_detail_api_route_resolves(self):
        url = reverse("project-detail-api", kwargs={"code": "sample-project"})
        self.assertEqual(url, "/api/projects/sample-project/")

    def test_project_products_api_route_resolves(self):
        url = reverse("project-products-api", kwargs={"code": "sample-project"})
        self.assertEqual(url, "/api/projects/sample-project/products/")

    def test_project_list_web_data_route_resolves(self):
        url = reverse("project-list-web-data")
        self.assertEqual(url, "/projects_catalog/data/projects/")

    def test_project_facets_web_data_route_resolves(self):
        url = reverse("project-facets-web-data")
        self.assertEqual(url, "/projects_catalog/data/projects/facets/")

    def test_project_detail_web_data_route_resolves(self):
        url = reverse("project-detail-web-data", kwargs={"code": "sample-project"})
        self.assertEqual(url, "/projects_catalog/data/projects/sample-project/")

    def test_project_products_web_data_route_resolves(self):
        url = reverse("project-products-web-data", kwargs={"code": "sample-project"})
        self.assertEqual(url, "/projects_catalog/data/projects/sample-project/products/")
