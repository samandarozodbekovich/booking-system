
from django.conf import settings
from django.db import models

from .booking_status import BookingStatus
from .booking import Booking


# Only these statuses occupy a time slot.
ACTIVE_STATUSES = [BookingStatus.PENDING, BookingStatus.CONFIRMED]

# State machine: current status -> statuses it may move to.
ALLOWED_TRANSITIONS = {
    BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {BookingStatus.COMPLETED, BookingStatus.CANCELLED},
    BookingStatus.CANCELLED: set(),
    BookingStatus.COMPLETED: set(),
}


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