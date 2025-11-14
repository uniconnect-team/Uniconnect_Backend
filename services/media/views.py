"""Media service viewsets."""
from __future__ import annotations

from rest_framework import permissions, viewsets

from .models import DormImage, DormRoomImage
from .serializers import DormImageSerializer, DormRoomImageSerializer


class OwnerDormImageViewSet(viewsets.ModelViewSet):
    queryset = DormImage.objects.all()
    serializer_class = DormImageSerializer
    permission_classes = [permissions.IsAuthenticated]


class OwnerDormRoomImageViewSet(viewsets.ModelViewSet):
    queryset = DormRoomImage.objects.all()
    serializer_class = DormRoomImageSerializer
    permission_classes = [permissions.IsAuthenticated]
