from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class BookingStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"


# Only these statuses occupy a time slot.
ACTIVE_STATUSES = [BookingStatus.PENDING, BookingStatus.CONFIRMED]

# State machine: current status -> statuses it may move to.
ALLOWED_TRANSITIONS = {
    BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {BookingStatus.COMPLETED, BookingStatus.CANCELLED},
    BookingStatus.CANCELLED: set(),
    BookingStatus.COMPLETED: set(),
}


class Booking(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    provider = models.ForeignKey(
        "scheduling.Provider",
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    service = models.ForeignKey(
        "catalog.Service",
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    # [start, end) in UTC. End is computed from service duration at booking
    # time and stored, so changing the service later does not move bookings.
    period = DateTimeRangeField()
    # Price snapshot at booking time.
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
        db_index=True,
    )
    # Deadline for confirming a pending booking. Cleared once it leaves "pending".
    # The exclusion constraint can't use now(), so expired pending bookings are
    # cancelled explicitly: inside create_booking() and by a periodic Celery task.
    expires_at = models.DateTimeField(null=True, blank=True)
    customer_note = models.TextField(blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["provider", "status"]),
            # Used by the cleanup of expired pending bookings.
            models.Index(fields=["status", "expires_at"]),
        ]
        constraints = [
            # Core guarantee: a provider can't have two active bookings
            # whose periods overlap. Enforced by Postgres, so it holds even
            # under concurrent requests. Requires the btree_gist extension.
            ExclusionConstraint(
                name="no_overlapping_provider_bookings",
                expressions=[
                    ("provider", RangeOperators.EQUAL),
                    ("period", RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=ACTIVE_STATUSES),
            ),
            # Product decision: a customer can't be in two places at once.
            ExclusionConstraint(
                name="no_overlapping_customer_bookings",
                expressions=[
                    ("customer", RangeOperators.EQUAL),
                    ("period", RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=ACTIVE_STATUSES),
            ),
            models.CheckConstraint(
                name="booking_period_valid",
                condition=Q(period__isempty=False)
                & Q(period__lower_inf=False)
                & Q(period__upper_inf=False),
            ),
            models.CheckConstraint(
                name="booking_price_non_negative",
                condition=Q(price__gte=0),
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {self.service} with {self.provider} at {self.start}"

    @property
    def start(self):
        return self.period.lower

    @property
    def end(self):
        return self.period.upper

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in ALLOWED_TRANSITIONS[BookingStatus(self.status)]


class BookingStatusLog(models.Model):
    """Audit trail of every status change (booking history)."""

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="status_logs",
    )
    # Null on the first entry (creation).
    from_status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        null=True,
        blank=True,
    )
    to_status = models.CharField(max_length=20, choices=BookingStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    note = models.CharField(max_length=255, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"#{self.booking_id}: {self.from_status} -> {self.to_status}"