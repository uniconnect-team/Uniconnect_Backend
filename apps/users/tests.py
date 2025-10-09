"""Tests for the users app."""
from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class AuthFlowTests(APITestCase):
    """Verify authentication endpoints behave as expected."""

    def test_register_user(self) -> None:
        payload = {
            "full_name": "Alex Student",
            "phone": "+96171123456",
            "email": "alex@test.com",
            "password": "Passw0rd1",
            "role": "SEEKER",
        }
        response = self.client.post(reverse("users:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], payload["email"])
        self.assertEqual(response.data["role"], payload["role"])

    def test_login_with_email(self) -> None:
        register_payload = {
            "full_name": "Owner User",
            "phone": "+96171123457",
            "email": "owner@test.com",
            "password": "Passw0rd1",
            "role": "OWNER",
        }
        self.client.post(reverse("users:register"), register_payload, format="json")

        response = self.client.post(
            reverse("users:login"),
            {"identifier": register_payload["email"], "password": register_payload["password"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["email"], register_payload["email"])

    def test_login_with_phone(self) -> None:
        register_payload = {
            "full_name": "Phone User",
            "phone": "+96171123458",
            "email": "phone@test.com",
            "password": "Passw0rd1",
            "role": "SEEKER",
        }
        self.client.post(reverse("users:register"), register_payload, format="json")

        response = self.client.post(
            reverse("users:login"),
            {"identifier": register_payload["phone"], "password": register_payload["password"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["phone"], register_payload["phone"])
