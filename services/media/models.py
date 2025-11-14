"""Media service models for dorm-related uploads."""
from __future__ import annotations

from django.db import models


def _dorm_cover_upload_path(instance, filename):
    owner_id = instance.property.owner_id if instance.property_id else "unassigned"
    return f"dorms/{owner_id}/covers/{filename}"


def _dorm_gallery_upload_path(instance, filename):
    owner_id = instance.dorm.property.owner_id if instance.dorm.property_id else "unassigned"
    return f"dorms/{owner_id}/gallery/{filename}"


def _room_gallery_upload_path(instance, filename):
    owner_id = instance.room.dorm.property.owner_id if instance.room.dorm.property_id else "unassigned"
    room_id = instance.room_id or "unassigned"
    return f"dorms/{owner_id}/rooms/{room_id}/{filename}"


class DormImage(models.Model):
    dorm = models.ForeignKey("users.Dorm", related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to=_dorm_gallery_upload_path)
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users_dormimage"
        ordering = ["-created_at"]
        managed = False

    def __str__(self) -> str:  # pragma: no cover - debugging helper
        return f"DormImage(dorm={self.dorm_id}, id={self.id})"


class DormRoomImage(models.Model):
    room = models.ForeignKey("users.DormRoom", related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to=_room_gallery_upload_path)
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users_dormroomimage"
        ordering = ["-created_at"]
        managed = False

    def __str__(self) -> str:  # pragma: no cover - debugging helper
        return f"DormRoomImage(room={self.room_id}, id={self.id})"


__all__ = [
    "_dorm_cover_upload_path",
    "_dorm_gallery_upload_path",
    "_room_gallery_upload_path",
    "DormImage",
    "DormRoomImage",
]
