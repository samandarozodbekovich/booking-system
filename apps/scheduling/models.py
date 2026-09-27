from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib.postgres.fields import DateTimeRangeField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


def validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError(f"Unknown timezone: {value}")


class Provider(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="provider_profile",
    )
    services = models.ManyToManyField(
        "catalog.Service",
        related_name="providers",
        blank=True,
    )
    bio = models.TextField(blank=True)
    # WorkingHours are interpreted in this timezone.
    timezone = models.CharField(
        max_length=64,
        default="Asia/Tashkent",
        validators=[validate_timezone],
    )
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.user.get_full_name() or self.user.username

    def clean(self) -> None:
        # Invariant: a provider profile belongs only to a user with the provider role.
        if self.user_id and self.user.role != self.user.Role.PROVIDER:
            raise ValidationError({"user": "User must have the 'provider' role."})

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


class WorkingHours(models.Model):
    """
    Weekly recurring schedule in the provider's local time.
    Several rows per weekday are allowed, e.g. 09:00-13:00 and 14:00-18:00
    (a lunch break is simply a gap between two rows).
    """

    class Weekday(models.IntegerChoices):
        # Matches Python's date.weekday(): Monday == 0
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="working_hours",
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["provider", "weekday", "start_time"]
        verbose_name_plural = "working hours"
        constraints = [
            models.CheckConstraint(
                name="working_hours_end_after_start",
                condition=Q(end_time__gt=models.F("start_time")),
            ),
        ]

    def clean(self) -> None:
        # Postgres has no native time-range type, so overlap between
        # intervals of the same weekday is checked at application level.
        if not (self.provider_id and self.start_time and self.end_time):
            return
        overlapping = WorkingHours.objects.filter(
            provider_id=self.provider_id,
            weekday=self.weekday,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError("Working hours overlap with an existing interval.")

    def __str__(self) -> str:
        return f"{self.provider} {self.get_weekday_display()} {self.start_time}-{self.end_time}"


class TimeOff(models.Model):
    """Absolute blocked period (vacation, sick day, one-off break). Stored in UTC."""

    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="time_offs",
    )
    period = DateTimeRangeField()
    reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["provider", "period"]
        constraints = [
            models.CheckConstraint(
                name="time_off_period_valid",
                condition=Q(period__isempty=False)
                & Q(period__lower_inf=False)
                & Q(period__upper_inf=False),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.provider} off {self.period.lower} - {self.period.upper}"