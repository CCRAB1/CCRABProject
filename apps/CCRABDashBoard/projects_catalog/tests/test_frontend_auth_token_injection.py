from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class FrontendAuthTokenInjectionTests(TestCase):
    def test_projects_index_injects_token_for_authenticated_user(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="frontend-token-user",
            password="test-pass-123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("projects-index"))

        self.assertEqual(response.status_code, 200)
        api_access_token = response.context.get("api_access_token")
        self.assertTrue(api_access_token)

    def test_project_detail_injects_token_for_authenticated_user(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="frontend-token-user-detail",
            password="test-pass-123",
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("project-detail", kwargs={"code": "sample-project"})
        )

        self.assertEqual(response.status_code, 200)
        api_access_token = response.context.get("api_access_token")
        self.assertTrue(api_access_token)

    def test_platform_map_injects_token_for_authenticated_user(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="frontend-token-user-platform-map",
            password="test-pass-123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("platforms_map"))

        self.assertEqual(response.status_code, 200)
        api_access_token = response.context.get("api_access_token")
        self.assertTrue(api_access_token)

    def test_projects_index_has_no_token_for_anonymous_user(self):
        response = self.client.get(reverse("projects-index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.get("api_access_token"), "")
