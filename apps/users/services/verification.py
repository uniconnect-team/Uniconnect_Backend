"""Helpers for managing email verification one-time passwords."""
from __future__ import annotations

import datetime
import hashlib
import hmac
import secrets
from typing import Tuple

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from ..models import EmailOTP


def generate_code(length: int = 6) -> str:
    """Return a zero-padded numeric OTP of ``length`` digits."""

    return f"{secrets.randbelow(10**length):0{length}d}"


def hash_code(code: str) -> str:
    """Hash an OTP using SHA256."""

    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def send_verification(
    *,
    email: str,
    full_name: str = "",
    university_domain: str = "",
    ip: str | None = None,
) -> EmailOTP:
    """Create and email a verification OTP for the supplied address."""

    normalized_email = email.strip().lower()
    now = timezone.now()
    ttl_minutes = int(getattr(settings, "VERIFY_TOKEN_TTL_MIN", 15))
    expires_at = now + datetime.timedelta(minutes=ttl_minutes)

    # Ensure only one active OTP exists per email at a time.
    EmailOTP.objects.filter(
        email=normalized_email,
        used_at__isnull=True,
        expires_at__gt=now,
    ).delete()

    code = generate_code()
    otp = EmailOTP.objects.create(
        email=normalized_email,
        code_hash=hash_code(code),
        expires_at=expires_at,
        created_ip=ip,
    )

    context = {
        "full_name": full_name or normalized_email.split("@")[0],
        "code": code,
        "expiry_minutes": ttl_minutes,
        "university_domain": university_domain or normalized_email.split("@")[-1],
    }

    subject = "Verify your UniConnect student email"
    text_body = render_to_string("emails/verify_student_email.txt", context)
    html_body = render_to_string("emails/verify_student_email.html", context)

    message = EmailMultiAlternatives(
        subject,
        text_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[normalized_email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)

    return otp


def confirm_code(email: str, code: str) -> Tuple[bool, EmailOTP | str]:
    """Validate an OTP and record the attempt.

    Returns ``(True, EmailOTP)`` when the code is valid, otherwise
    ``(False, reason)`` where ``reason`` is ``"invalid"`` or ``"expired"``.
    """

    normalized_email = email.strip().lower()
    otp = (
        EmailOTP.objects.filter(email=normalized_email)
        .order_by("-created_at")
        .first()
    )
    if not otp:
        return False, "invalid"

    now = timezone.now()
    if otp.used_at is not None:
        return False, "invalid"
    if otp.expires_at <= now:
        return False, "expired"

    max_attempts = int(getattr(settings, "VERIFY_MAX_ATTEMPTS", 5))
    if otp.attempts >= max_attempts:
        if otp.expires_at > now:
            otp.expires_at = now
            otp.save(update_fields=["expires_at"])
        return False, "expired"

    otp.attempts += 1
    hashed_input = hash_code(code)
    if not hmac.compare_digest(otp.code_hash, hashed_input):
        update_fields = ["attempts"]
        if otp.attempts >= max_attempts:
            otp.expires_at = now
            update_fields.append("expires_at")
        otp.save(update_fields=update_fields)
        return False, "invalid"

    otp.used_at = now
    otp.save(update_fields=["attempts", "used_at"])
    return True, otp
