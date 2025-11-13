"""Create dorm management models for owners."""
from __future__ import annotations

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_auto_20251020_0904"),
    ]

    operations = [
        migrations.CreateModel(
            name="Dorm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "cover_image",
                    models.ImageField(blank=True, null=True, upload_to="apps.users.models._dorm_cover_upload_path"),
                ),
                ("amenities", models.JSONField(blank=True, default=list)),
                ("room_service_available", models.BooleanField(default=False)),
                ("electricity_included", models.BooleanField(default=True)),
                ("water_included", models.BooleanField(default=True)),
                ("internet_included", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "property",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dorms",
                        to="users.property",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="DormImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="apps.users.models._dorm_gallery_upload_path")),
                ("caption", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "dorm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="users.dorm",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="DormRoom",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                (
                    "room_type",
                    models.CharField(
                        choices=[
                            ("SINGLE", "Single"),
                            ("DOUBLE", "Double"),
                            ("TRIPLE", "Triple"),
                            ("QUAD", "Quad"),
                            ("STUDIO", "Studio"),
                            ("OTHER", "Other"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "capacity",
                    models.PositiveSmallIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("price_per_month", models.DecimalField(decimal_places=2, max_digits=10)),
                ("amenities", models.JSONField(blank=True, default=list)),
                (
                    "total_units",
                    models.PositiveIntegerField(
                        default=1,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("available_units", models.PositiveIntegerField(default=1)),
                ("is_available", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "dorm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rooms",
                        to="users.dorm",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="DormRoomImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="apps.users.models._room_gallery_upload_path")),
                ("caption", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="users.dormroom",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="BookingRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seeker_name", models.CharField(max_length=255)),
                ("seeker_email", models.EmailField(max_length=254)),
                ("seeker_phone", models.CharField(blank=True, max_length=20)),
                ("message", models.TextField(blank=True)),
                ("move_in_date", models.DateField(blank=True, null=True)),
                ("move_out_date", models.DateField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("APPROVED", "Approved"),
                            ("DECLINED", "Declined"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("owner_note", models.TextField(blank=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="booking_requests",
                        to="users.dormroom",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="dorm",
            index=models.Index(fields=["property", "name"], name="users_dorm_propert_0a0e52_idx"),
        ),
        migrations.AddIndex(
            model_name="dormroom",
            index=models.Index(fields=["dorm", "room_type"], name="users_dorm_dorm_id_6f0ced_idx"),
        ),
        migrations.AddIndex(
            model_name="bookingrequest",
            index=models.Index(fields=["room", "status"], name="users_book_room_id_5c41d4_idx"),
        ),
    ]
