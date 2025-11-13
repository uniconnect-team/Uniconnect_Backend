"""Notification views derived from booking status updates."""
from __future__ import annotations

from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from services.authentication.users.models import BookingRequest
from services.authentication.users.serializers import SeekerBookingRequestSerializer
from services.authentication.users.views import IsSeekerProfile


class BookingNotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Expose booking decision notifications for seekers."""

    serializer_class = SeekerBookingRequestSerializer
    permission_classes = [IsAuthenticated, IsSeekerProfile]

    def get_queryset(self):
        user = self.request.user
        filters = Q(seeker_email=user.email)
        profile = getattr(user, "profile", None)
        if profile and profile.phone:
            filters |= Q(seeker_phone=profile.phone)

        return (
            BookingRequest.objects.filter(
                filters,
                status__in=[
                    BookingRequest.Status.APPROVED,
                    BookingRequest.Status.DECLINED,
                ],
            )
            .select_related("room", "room__dorm", "room__dorm__property")
            .order_by("-updated_at")
        )
