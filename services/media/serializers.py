"""Serializers for media service models."""
from __future__ import annotations

from rest_framework import serializers

from .models import DormImage, DormRoomImage


class DormImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DormImage
        fields = "__all__"


class DormRoomImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DormRoomImage
        fields = "__all__"
