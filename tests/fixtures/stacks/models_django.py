import uuid
from django.db import models

ROLE_CHOICES = [("admin", "Admin"), ("member", "Member")]


class User(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.EmailField(max_length=255, unique=True)
    display_name = models.CharField(max_length=80)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    created_at = models.DateTimeField(auto_now_add=True)


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    owner_id = models.UUIDField()
    name = models.CharField(max_length=120)
    description = models.TextField(null=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
