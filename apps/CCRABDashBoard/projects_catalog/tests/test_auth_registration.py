import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class UserRegistrationApiTests(TestCase):
    def setUp(self):
        self.register_url = reverse("user_register")
        self.token_url = reverse("token_obtain_pair")

    def test_register_creates_user_and_returns_tokens(self):
        payload = {
            "username": "new_api_user",
            "password": "StrongPass123!",
            "email": "new_api_user@example.com",
        }

        response = self.client.post(
            self.register_url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn("id", body)
        self.assertEqual(body["username"], payload["username"])
        self.assertIn("access", body)
        self.assertIn("refresh", body)

        user_model = get_user_model()
        self.assertTrue(user_model.objects.filter(username=payload["username"]).exists())

    def test_register_rejects_duplicate_username(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="dupe_user",
            password="StrongPass123!",
        )

        response = self.client.post(
            self.register_url,
            data=json.dumps(
                {
                    "username": "dupe_user",
                    "password": "AnotherStrongPass123!",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("username", body)

    def test_register_requires_username_and_password(self):
        response = self.client.post(
            self.register_url,
            data=json.dumps({"username": ""}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("username", body)
        self.assertIn("password", body)

    def test_register_user_can_fetch_token_with_same_credentials(self):
        credentials = {
            "username": "token_user",
            "password": "StrongPass123!",
        }
        register_response = self.client.post(
            self.register_url,
            data=json.dumps(credentials),
            content_type="application/json",
        )
        self.assertEqual(register_response.status_code, 201)

        token_response = self.client.post(
            self.token_url,
            data=json.dumps(credentials),
            content_type="application/json",
        )

        self.assertEqual(token_response.status_code, 200)
        body = token_response.json()
        self.assertIn("access", body)
        self.assertIn("refresh", body)
