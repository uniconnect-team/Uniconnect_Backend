"""Tests for the users app."""
from __future__ import annotations

import re

from django.contrib.auth.models import User
from django.core import mail
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Profile, UniversityDomain, VerificationToken


class AuthFlowTests(APITestCase):
    """Verify authentication endpoints behave as expected."""

    @classmethod
    def setUpTestData(cls) -> None:
        UniversityDomain.objects.get_or_create(
            domain="mail.aub.edu",
            defaults={
                "university_name": "American University of Beirut",
                "country_code": "LB",
            },
        )

    def test_register_user(self) -> None:
        payload = {
            "full_name": "Alex Student",
            "phone": "+96171123456",
            "email": "Alex@mail.aub.edu",
            "password": "Passw0rd1",
            "role": "SEEKER",
        }
        response = self.client.post(reverse("users:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], payload["email"].lower())
        self.assertEqual(response.data["role"], payload["role"])

    def test_register_seeker_rejects_non_allow_list_email(self) -> None:
        payload = {
            "full_name": "Alex Student",
            "phone": "+96171123457",
            "email": "alex@gmail.com",
            "password": "Passw0rd1",
            "role": "SEEKER",
        }
        response = self.client.post(reverse("users:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("supported institutions", str(response.data))

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
            "email": "phone@mail.aub.edu",
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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class VerifyEmailFlowTests(APITestCase):
    """Validate the student email verification workflow."""

    def setUp(self) -> None:
        self.domain, _ = UniversityDomain.objects.get_or_create(
            domain="mail.aub.edu",
            defaults={
                "university_name": "American University of Beirut",
                "country_code": "LB",
            },
        )
        self.user = User.objects.create_user("student", "student@example.com", "Passw0rd1")
        Profile.objects.create(
            user=self.user,
            full_name="Student User",
            phone="+96171333000",
            role=Profile.Roles.SEEKER,
        )

    def test_request_verification_success(self) -> None:
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("users:verify-email-request"),
            {"email": "Name@mail.aub.edu"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
        self.assertIn("cooldownSeconds", response.data)
        self.assertEqual(len(mail.outbox), 1)

        token = VerificationToken.objects.get(user=self.user)
        self.assertEqual(token.email, "name@mail.aub.edu")
        self.assertEqual(token.university_domain, self.domain.domain)
        self.assertEqual(token.token_type, VerificationToken.Types.OTP)
        self.assertTrue(token.otp_code_hash)

        self.user.refresh_from_db()
        profile = self.user.profile
        self.assertFalse(profile.is_student_verified)
        self.assertIsNone(profile.email_verified_at)
        self.assertEqual(profile.university_domain, "")
        self.assertEqual(self.user.email, "name@mail.aub.edu")

    def test_request_verification_enforces_cooldown(self) -> None:
        self.client.force_authenticate(user=self.user)
        payload = {"email": "student@mail.aub.edu"}
        first_response = self.client.post(reverse("users:verify-email-request"), payload, format="json")
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        second_response = self.client.post(reverse("users:verify-email-request"), payload, format="json")
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("wait", " ".join(second_response.data.get("non_field_errors", [])))

    def test_confirm_verification_marks_profile_verified(self) -> None:
        self.client.force_authenticate(user=self.user)
        self.client.post(
            reverse("users:verify-email-request"),
            {"email": "student@mail.aub.edu"},
            format="json",
        )
        message = mail.outbox[-1]
        code_match = re.search(r"(\d{6})", message.body)
        self.assertIsNotNone(code_match)
        otp = code_match.group(1)

        response = self.client.post(
            reverse("users:verify-email-confirm"),
            {"email": "student@mail.aub.edu", "otp": otp},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])

        profile = Profile.objects.get(user=self.user)
        self.assertTrue(profile.is_student_verified)
        self.assertIsNotNone(profile.email_verified_at)
        self.assertEqual(profile.university_domain, self.domain.domain)

        token_record = VerificationToken.objects.get(user=self.user)
        self.assertIsNotNone(token_record.consumed_at)
