from django.test import SimpleTestCase
from django.urls import resolve, reverse

from platforms_app.openapi import build_schema


class PlatformsOpenAPITests(SimpleTestCase):
    def test_schema_is_public_and_paths_resolve(self):
        response = self.client.get(reverse("platforms-openapi-schema"))
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["openapi"], "3.0.3")
        self.assertEqual(len(schema["paths"]), 7)
        identifiers = set()
        for path, methods in schema["paths"].items():
            resolve(path.replace("{short_name}", "example"))
            operation = methods["get"]
            self.assertNotIn(operation["operationId"], identifiers)
            identifiers.add(operation["operationId"])
            self.assertIn("200", operation["responses"])

    def test_access_requirements(self):
        paths = build_schema()["paths"]
        for name in ("platform-list-api", "platforminfo", "platform_configuration"):
            self.assertEqual(
                paths[reverse(name)]["get"]["security"], [{"bearerAuth": []}]
            )
        for name in (
            "platform-configuration-api",
            "platform_data_request",
            "platform-list-web-data",
        ):
            self.assertEqual(paths[reverse(name)]["get"]["security"], [])
        self.assertIn(
            "403", paths[reverse("platform_configuration")]["get"]["responses"]
        )

    def test_help_page_renders_contract_and_examples_without_authentication(self):
        response = self.client.get(reverse("platforms-api-help"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("platforms-openapi-schema"))
        self.assertContains(response, "--data-urlencode")
        self.assertContains(response, "private_api_access")
        for methods in build_schema()["paths"].values():
            self.assertContains(response, methods["get"]["summary"])
