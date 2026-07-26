from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    is_banned = models.BooleanField(
        default=False,
        help_text="Banned users keep historical content but cannot create or change public data.",
    )

    def __str__(self) -> str:
        return self.email or self.username
