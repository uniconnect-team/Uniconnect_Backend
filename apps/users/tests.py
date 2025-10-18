"""Tests for the users app."""
from __future__ import annotations

import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import EmailOTP, PendingRegistration, Profile, UniversityDomain


class AuthFlowTests(APITestCase):
    """Verify authentication and email verification endpoints."""

    def setUp(self) -> None:
        super().setUp()
        # Ensure allow-listed domains exist for tests (migrations should seed these).
        UniversityDomain.objects.get_or_create(domain="mail.aub.edu", defaults={"university_name": "AUB"})

    def _register_user(
        self,
        role: str = Profile.Roles.SEEKER,
        email: str = "student@mail.aub.edu",
    ) -> "Response":
        payload = {
            "full_name": "Alex Student",
            "phone": "+96171123456",
            "email": email,
            "password": "Passw0rd1",
            "role": role,
        }
        response = self.client.post(reverse("users:register"), payload, format="json")
        return response

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
        response = self._register_user(email="alex@gmail.com")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertEqual(response.data["email"][0].code, "UNIVERSITY_EMAIL_REQUIRED")

    def test_register_owner_allows_non_university_email(self) -> None:
        data = self._complete_registration(role=Profile.Roles.OWNER, email="owner@gmail.com")
        self.assertEqual(data["user"]["email"], "owner@gmail.com")
        self.assertEqual(data["user"]["role"], Profile.Roles.OWNER)

    def test_registration_defers_user_creation_until_verified(self) -> None:
        response = self._register_user()
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(response.data["ok"])
        self.assertEqual(User.objects.filter(email="student@mail.aub.edu").count(), 0)

        confirm_payload = self._complete_registration()
        self.assertEqual(User.objects.filter(email="student@mail.aub.edu").count(), 1)
        self.assertIn("access", confirm_payload)
        self.assertIn("refresh", confirm_payload)

    def test_login_with_email(self) -> None:
        self._complete_registration(role=Profile.Roles.OWNER, email="owner@gmail.com")
        login_response = self.client.post(
            reverse("users:login"),
            {"identifier": "owner@gmail.com", "password": "Passw0rd1"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)
        self.assertFalse(login_response.data["user"]["is_student_verified"])

    def test_verification_request_and_confirm_flow(self) -> None:
        register_response = self._register_user()
        self.assertEqual(register_response.status_code, status.HTTP_202_ACCEPTED)
        mail.outbox.clear()
        request_response = self.client.post(
            reverse("users:verify-email-request"),
            {"email": "student@mail.aub.edu"},
            format="json",
        )
        self.assertEqual(request_response.status_code, status.HTTP_200_OK)
        self.assertTrue(request_response.data["ok"])
        self.assertGreater(len(mail.outbox), 0)

        message = mail.outbox[-1]
        self.assertEqual(message.from_email, settings.DEFAULT_FROM_EMAIL)
        match = re.search(r"(\d{6})", message.body)
        self.assertIsNotNone(match)
        code = match.group(1) if match else "000000"

        confirm_response = self.client.post(
            reverse("users:verify-email-confirm"),
            {"email": "student@mail.aub.edu", "code": code},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertTrue(confirm_response.data["ok"])

        self.assertFalse(PendingRegistration.objects.filter(email="student@mail.aub.edu").exists())

        user = User.objects.get(email="student@mail.aub.edu")
        profile = user.profile
        self.assertTrue(profile.is_student_verified)
        self.assertIsNotNone(profile.email_verified_at)
        self.assertIsNotNone(profile.university_domain)
        self.assertEqual(profile.university_domain.domain, "mail.aub.edu")

        otp = EmailOTP.objects.filter(email="student@mail.aub.edu").latest("created_at")
        self.assertIsNotNone(otp.used_at)

        # Check /me endpoint reflects verification status
        login_response = self.client.post(
            reverse("users:login"),
            {"identifier": "student@mail.aub.edu", "password": "Passw0rd1"},
            format="json",
        )
        access = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_response = self.client.get(reverse("users:me"))
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertTrue(me_response.data["is_student_verified"])
        self.assertEqual(me_response.data["university_domain"], "mail.aub.edu")

    def test_verification_request_creates_pending_registration(self) -> None:
        mail.outbox.clear()
        payload = {
            "full_name": "Sam Student",
            "phone": "+96171000000",
            "email": "sam@mail.aub.edu",
            "password": "Str0ngPass",
            "role": Profile.Roles.SEEKER,
        }

        request_response = self.client.post(
            reverse("users:seeker-verify-email-request"),
            payload,
            format="json",
        )
        self.assertEqual(request_response.status_code, status.HTTP_200_OK)
        self.assertTrue(request_response.data["ok"])
        self.assertTrue(request_response.data["requiresVerification"])

        pending = PendingRegistration.objects.get(email="sam@mail.aub.edu")
        self.assertEqual(pending.full_name, payload["full_name"])
        self.assertEqual(pending.phone, payload["phone"])
        self.assertEqual(pending.role, Profile.Roles.SEEKER)
        self.assertIsNotNone(pending.university_domain)

        self.assertGreater(len(mail.outbox), 0)
        message = mail.outbox[-1]
        match = re.search(r"(\d{6})", message.body)
        self.assertIsNotNone(match)
        code = match.group(1) if match else "000000"

        confirm_response = self.client.post(
            reverse("users:seeker-verify-email-confirm"),
            {"email": payload["email"], "code": code},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertTrue(confirm_response.data["ok"])
        self.assertTrue(User.objects.filter(email=payload["email"]).exists())

    def test_verification_request_respects_cooldown(self) -> None:
        self._register_user()
        first_response = self.client.post(
            reverse("users:verify-email-request"),
            {"email": "student@mail.aub.edu"},
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        second_response = self.client.post(
            reverse("users:verify-email-request"),
            {"email": "student@mail.aub.edu"},
            format="json",
        )
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second_response.data["non_field_errors"][0].code, "cooldown_active")

    def test_verification_request_respects_expiry(self) -> None:
        self._register_user()
        request_response = self.client.post(
            reverse("users:verify-email-request"),
            {"email": "student@mail.aub.edu"},
            format="json",
        )
        self.assertEqual(request_response.status_code, status.HTTP_200_OK)

        otp = EmailOTP.objects.latest("created_at")
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save(update_fields=["expires_at"])

        confirm_response = self.client.post(
            reverse("users:verify-email-confirm"),
            {"email": "student@mail.aub.edu", "code": "000000"},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(confirm_response.data["non_field_errors"][0].code, "expired_code")

    def test_seeker_alias_verification_endpoints(self) -> None:
        self._register_user()
        request_response = self.client.post(
            reverse("users:seeker-verify-email-request"),
            {"email": "student@mail.aub.edu"},
            format="json",
        )
        self.assertEqual(request_response.status_code, status.HTTP_200_OK)

        otp = EmailOTP.objects.latest("created_at")
        message = mail.outbox[-1]
        match = re.search(r"(\d{6})", message.body)
        code = match.group(1) if match else "000000"

        confirm_response = self.client.post(
            reverse("users:seeker-verify-email-confirm"),
            {"email": "student@mail.aub.edu", "code": code},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertTrue(confirm_response.data["ok"])
