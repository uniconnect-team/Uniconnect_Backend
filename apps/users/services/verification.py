"""Utilities for managing student email verification."""
from __future__ import annotations

import secrets
from typing import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..models import Profile, UniversityDomain, VerificationToken


class VerificationFailure(Exception):
    """Raised when verification cannot be completed."""

    def __init__(self, message: str, *, code: str = "invalid") -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class VerificationRequestResult:
    """Outcome of a verification request."""

    cooldown_seconds: int
    expires_at: datetime


def normalize_email(email: str) -> str:
    """Return a trimmed, lowercased email."""

    return email.strip().lower()


def extract_domain(email: str) -> str:
    """Return the domain portion of an email address."""

    return email.split("@", 1)[1].lower()


def get_matching_domain(domain: str) -> UniversityDomain | None:
    """Return the matching allow-listed university domain if available."""

    domain = domain.lower()
    parts = domain.split(".")
    candidates = [".".join(parts[i:]) for i in range(len(parts))]

    for candidate in candidates:
        match = UniversityDomain.objects.active().filter(domain__iexact=candidate).first()
        if match:
            return match
    return None


def _build_verification_email(
    *, user: User, email: str, otp_code: str, university: UniversityDomain, expires_at: datetime
) -> tuple[str, str, str]:
    """Return subject, plain text, and HTML bodies for the verification email."""

    full_name = getattr(user.profile, "full_name", "") or user.get_full_name() or user.username
    subject = _("Verify your UniConnect student email")
    minutes = int((expires_at - timezone.now()).total_seconds() // 60)

    context = {
        "name": full_name,
        "otp_code": otp_code,
        "university_name": university.university_name,
        "expires_in_minutes": minutes or 1,
        "support_email": settings.MAIL_FROM,
        "app_url": settings.APP_URL.rstrip("/"),
    }

    text_body = render_to_string("emails/verify_student_email.txt", context)
    html_body = render_to_string("emails/verify_student_email.html", context)

    return subject, text_body, html_body


def send_verification_email(
    *, user: User, email: str, otp_code: str, university: UniversityDomain, expires_at: datetime
) -> None:
    """Send the verification email with both HTML and plain-text bodies."""

    subject, text_body, html_body = _build_verification_email(
        user=user,
        email=email,
        otp_code=otp_code,
        university=university,
        expires_at=expires_at,
    )

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.MAIL_FROM,
        to=[email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send()


def request_verification(
    *,
    user: User,
    email: str,
    university: UniversityDomain,
    created_ip: str | None,
    created_ua: str,
) -> VerificationRequestResult:
    """Create and dispatch a student email verification token."""

    cooldown_seconds = getattr(settings, "VERIFY_RESEND_COOLDOWN_SEC", 60)
    ttl_minutes = getattr(settings, "VERIFY_TOKEN_TTL_MIN", 15)

    now = timezone.now()
    expires_at = now + timedelta(minutes=ttl_minutes)
    token = secrets.token_urlsafe(32)
    otp_code = f"{secrets.randbelow(1_000_000):06d}"

    with transaction.atomic():
        # Ensure only a single active token remains.
        VerificationToken.objects.for_user(user).active().update(consumed_at=now)

        normalized_email = normalize_email(email)
        email_changed = user.email.lower() != normalized_email if user.email else True
        if email_changed:
            if User.objects.filter(email__iexact=normalized_email).exclude(pk=user.pk).exists():
                raise ValueError("Email already in use")
            user.email = normalized_email
            user.save(update_fields=["email"])

        profile = Profile.objects.select_for_update().get(user=user)
        profile.is_student_verified = False
        profile.email_verified_at = None
        profile.university_domain = ""
        profile.save(update_fields=["is_student_verified", "email_verified_at", "university_domain"])

    verification = VerificationToken.create_for_user(
        user,
        token=token,
        email=normalized_email,
        university_domain=university.domain,
        expires_at=expires_at,
        created_ip=created_ip,
        created_ua=created_ua,
        token_type=VerificationToken.Types.OTP,
        otp_code=otp_code,
    )

    send_verification_email(
        user=user,
        email=email,
        otp_code=otp_code,
        university=university,
        expires_at=verification.expires_at,
    )

    return VerificationRequestResult(cooldown_seconds=cooldown_seconds, expires_at=verification.expires_at)


def _get_active_tokens_for_email(normalized_email: str) -> Iterable[VerificationToken]:
    """Return active OTP verification tokens for an email."""

    now = timezone.now()
    return (
        VerificationToken.objects.select_related("user", "user__profile")
        .filter(
            email__iexact=normalized_email,
            token_type=VerificationToken.Types.OTP,
            consumed_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by("-created_at")
    )


def confirm_verification(email: str, otp_code: str) -> User:
    """Validate an OTP verification code and mark the profile as verified."""

    normalized_email = normalize_email(email)
    otp_hash = VerificationToken.build_hash(otp_code)

    active_tokens = list(_get_active_tokens_for_email(normalized_email))
    if not active_tokens:
        raise VerificationFailure(_("Verification code is invalid or has expired."), code="invalid")

    latest_token = active_tokens[0]
    if latest_token.is_locked:
        raise VerificationFailure(
            _("Too many invalid attempts. Please request a new verification email."), code="locked"
        )

    matching = next((token for token in active_tokens if token.otp_code_hash == otp_hash), None)
    if not matching:
        latest_token.mark_failed_attempt()
        if latest_token.is_locked:
            raise VerificationFailure(
                _("Too many invalid attempts. Please request a new verification email."),
                code="locked",
            )
        raise VerificationFailure(_("Verification code is invalid or has expired."), code="invalid")

    now = timezone.now()
    if matching.expires_at <= now:
        matching.mark_failed_attempt()
        raise VerificationFailure(_("Verification code is invalid or has expired."), code="invalid")

    matching.mark_consumed()

    user = matching.user
    if not user.email or user.email.lower() != matching.email.lower():
        user.email = matching.email
        user.save(update_fields=["email"])

    profile: Profile = user.profile
    profile.email_verified_at = now
    profile.is_student_verified = True
    profile.university_domain = matching.university_domain
    profile.save(update_fields=["email_verified_at", "is_student_verified", "university_domain"])

    return user
