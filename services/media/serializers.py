"""Serializers for media service models."""
from __future__ import annotations

from rest_framework import serializers

from .models import DormImage, DormRoomImage


class AbsoluteURLImageField(serializers.ImageField):
    """Image field that expands the stored path into an absolute URL."""

    def to_representation(self, value):  # type: ignore[override]
        url = super().to_representation(value)
        request = self.context.get("request")
        if url and request is not None:
            return request.build_absolute_uri(url)
        return url


class DormImageSerializer(serializers.ModelSerializer):
    image = AbsoluteURLImageField()

    class Meta:
        model = DormImage
        fields = "__all__"


class DormRoomImageSerializer(serializers.ModelSerializer):
    image = AbsoluteURLImageField()

    class Meta:
        model = DormRoomImage
        fields = "__all__"


__all__ = [
    "AbsoluteURLImageField",
    "DormImageSerializer",
    "DormRoomImageSerializer",
]
