from django.contrib.auth.models import User
from django.db import models

from seher.common.models import TimeStampedModel


class Profile(TimeStampedModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=150, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return self.display_name or self.user.get_username()

    class Meta:
        verbose_name_plural = "Profiles"
