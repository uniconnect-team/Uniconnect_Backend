"""Tests for the users app."""
from __future__ import annotations

import re

from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PendingRegistration, Profile, Property, UniversityDomain


class AuthFlowTests(APITestCase):
    """Verify registration, authentication, and profile endpoints."""

    def setUp(self) -> None:
        super().setUp()
        UniversityDomain.objects.get_or_create(
            domain="mail.aub.edu",
            defaults={"university_name": "AUB"},
        )

    def _register_payload(self, **overrides):
        data = {
            "full_name": "Alex Student",
            "phone": "+96171123456",
            "email": "student@mail.aub.edu",
            "password": "Passw0rd1",
            "role": Profile.Roles.SEEKER,
        }
        data.update(overrides)
        return data

    def _owner_register_payload(self, **overrides):
        data = {
            "full_name": "Olivia Owner",
            "phone": "+96171110000",
            "email": "owner@gmail.com",
            "password": "Own3rPass",
            "properties": [
                {"name": "Sunset Dorms", "location": "Beirut"},
            ],
        }
        data.update(overrides)
        return data

    def _complete_registration(
        self,
        role: str = Profile.Roles.SEEKER,
        email: str = "student@mail.aub.edu",
    ) -> dict:
        if not PendingRegistration.objects.filter(email=email).exists():
            mail.outbox.clear()
            response = self._register_user(role=role, email=email)
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertTrue(response.data["ok"])

        self.assertTrue(PendingRegistration.objects.filter(email=email).exists())
        self.assertGreater(len(mail.outbox), 0)

        message = mail.outbox[-1]
        match = re.search(r"(\d{6})", message.body)
        self.assertIsNotNone(match)
        code = match.group(1) if match else "000000"

        confirm_response = self.client.post(
            reverse("users:verify-email-confirm"),
            {"email": email, "code": code},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertTrue(confirm_response.data["ok"])
        self.assertIn("user", confirm_response.data)
        self.assertFalse(PendingRegistration.objects.filter(email=email).exists())
        return confirm_response.data

    def test_register_seeker_requires_university_email(self) -> None:
        payload = self._register_payload(email="alex@gmail.com")
        response = self.client.post(reverse("users:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertEqual(response.data["email"][0].code, "UNIVERSITY_EMAIL_REQUIRED")

    def test_register_seeker_creates_user_and_marks_verified(self) -> None:
        payload = self._register_payload()
        response = self.client.post(reverse("users:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        user = User.objects.get(email=payload["email"])
        profile = user.profile
        self.assertTrue(profile.is_student_verified)
        self.assertIsNotNone(profile.email_verified_at)
        self.assertIsNotNone(profile.university_domain)
        self.assertEqual(profile.university_domain.domain, "mail.aub.edu")

    def test_register_owner_allows_non_university_email(self) -> None:
        payload = self._owner_register_payload()
        response = self.client.post(
            reverse("users:register-owner"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="owner@gmail.com")
        self.assertEqual(user.profile.role, Profile.Roles.OWNER)
        self.assertFalse(user.profile.is_student_verified)
        self.assertEqual(Property.objects.filter(owner=user.profile).count(), 1)

    def test_register_owner_requires_property_information(self) -> None:
        payload = self._owner_register_payload(properties=[])
        response = self.client.post(
            reverse("users:register-owner"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("properties", response.data)

    def test_register_owner_rejects_duplicate_email_or_phone(self) -> None:
        first_response = self.client.post(
            reverse("users:register-owner"),
            self._owner_register_payload(),
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        duplicate_email = self._owner_register_payload(phone="+96171110001")
        response_email = self.client.post(
            reverse("users:register-owner"), duplicate_email, format="json"
        )
        self.assertEqual(response_email.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response_email.data)

        duplicate_phone = self._owner_register_payload(
            email="different_owner@gmail.com"
        )
        response_phone = self.client.post(
            reverse("users:register-owner"), duplicate_phone, format="json"
        )
        self.assertEqual(response_phone.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response_phone.data)

    def test_register_owner_allows_multiple_properties(self) -> None:
        payload = self._owner_register_payload(
            properties=[
                {"name": "Sunset Dorms", "location": "Beirut"},
                {"name": "Cedars Residence", "location": "Byblos"},
            ]
        )
        response = self.client.post(
            reverse("users:register-owner"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="owner@gmail.com")
        self.assertEqual(Property.objects.filter(owner=user.profile).count(), 2)

    def test_login_with_email(self) -> None:
        self.test_register_owner_allows_non_university_email()
        response = self.client.post(
            reverse("users:login"),
            {"identifier": "owner@gmail.com", "password": "Own3rPass"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["email"], "owner@gmail.com")

    def test_login_with_phone(self) -> None:
        self.test_register_seeker_creates_user_and_marks_verified()
        response = self.client.post(
            reverse("users:login"),
            {"identifier": "+96171123456", "password": "Passw0rd1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["phone"], "+96171123456")

    def test_me_endpoint_returns_profile(self) -> None:
        register_response = self.client.post(
            reverse("users:register"),
            self._register_payload(),
            format="json",
        )
        token = register_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get(reverse("users:me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "student@mail.aub.edu")
        self.assertTrue(response.data["is_student_verified"])
