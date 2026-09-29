"""
Booking business logic.

Views stay thin: they validate input and call these functions.
The database (exclusion constraints) is the final authority on double booking.
"""

from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from apps.catalog.models import Service
from apps.scheduling.availability import is_slot_available
from apps.scheduling.models import Provider

from .models import Booking, BookingStatus, BookingStatusLog

# How long a pending booking holds its slot before it expires (product decision).
PENDING_TTL = timedelta(minutes=15)


class SlotUnavailableError(Exception):
    """The requested time can't be booked (taken, outside hours, or in the past)."""


def expire_stale_pending_bookings(provider: Provider | None = None, now: datetime | None = None) -> int:
    """
    Cancel pending bookings whose confirmation deadline has passed.
    Called before creating a booking and periodically by a Celery task.
    """
    now = now or timezone.now()
    with transaction.atomic():
        queryset = Booking.objects.filter(status=BookingStatus.PENDING, expires_at__lte=now)
        if provider is not None:
            queryset = queryset.filter(provider=provider)
        # skip_locked: rows being handled by another transaction are left to it.
        expired = list(queryset.select_for_update(skip_locked=True))
        for booking in expired:
            booking.status = BookingStatus.CANCELLED
            booking.cancel_reason = "Expired: not confirmed in time."
            booking.expires_at = None
        Booking.objects.bulk_update(expired, ["status", "cancel_reason", "expires_at", "updated_at"])
        BookingStatusLog.objects.bulk_create(
            BookingStatusLog(
                booking=booking,
                from_status=BookingStatus.PENDING,
                to_status=BookingStatus.CANCELLED,
                changed_by=None,  # system
                note="Expired",
            )
            for booking in expired
        )
    return len(expired)


def _conflict_message(exc: IntegrityError) -> str:
    """Turn the violated constraint into a message the user understands."""
    constraint = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
    if constraint == "no_overlapping_customer_bookings":
        return "You already have another booking at this time."
    return "This time slot is no longer available."


def create_booking(
    *,
    customer,
    provider: Provider,
    service: Service,
    start: datetime,
    customer_note: str = "",
    now: datetime | None = None,
) -> Booking:
    now = now or timezone.now()

    with transaction.atomic():
        # Expired pending bookings still count for the exclusion constraint,
        # so release them first, inside the same transaction.
        expire_stale_pending_bookings(provider=provider, now=now)

        # Business check. Gives a clear error early, but it is NOT the
        # protection against races.
        if not is_slot_available(provider, service, start, now):
            raise SlotUnavailableError("The selected time is not available.")

        end = start + timedelta(minutes=service.duration_minutes)
        try:
            # Savepoint: if the insert fails, the outer transaction stays usable.
            with transaction.atomic():
                booking = Booking.objects.create(
                    customer=customer,
                    provider=provider,
                    service=service,
                    period=DateTimeTZRange(start, end, "[)"),
                    price=service.price,  # snapshot
                    status=BookingStatus.PENDING,
                    expires_at=now + PENDING_TTL,
                    customer_note=customer_note,
                )
        except IntegrityError as exc:
            # A parallel request won the race; the exclusion constraint rejected us.
            raise SlotUnavailableError(_conflict_message(exc)) from exc

        BookingStatusLog.objects.create(
            booking=booking,
            from_status=None,
            to_status=BookingStatus.PENDING,
            changed_by=customer,
            note="Created",
        )
    return booking


CANCELLATION_WINDOW = timedelta(hours=2)


class InvalidTransitionError(Exception):
    """The status change conflicts with the booking's current state."""


class BookingPermissionError(Exception):
    """The user is not allowed to perform this status change."""


def _check_actor(booking: Booking, to_status: str, actor) -> None:
    is_admin = actor.is_business_admin
    profile = getattr(actor, "provider_profile", None)
    is_own_provider = profile is not None and profile.pk == booking.provider_id
    is_own_customer = booking.customer_id == actor.pk

    if to_status in (BookingStatus.CONFIRMED, BookingStatus.COMPLETED):
        allowed = is_admin or is_own_provider
    else:  
        allowed = is_admin or is_own_provider or is_own_customer

    if not allowed:
        raise BookingPermissionError("You are not allowed to perform this action.")


def _check_business_rules(booking: Booking, to_status: str, actor, now: datetime) -> None:
    if to_status == BookingStatus.COMPLETED and now < booking.start:
        raise InvalidTransitionError("A booking can't be completed before it starts.")

    if to_status == BookingStatus.CANCELLED and booking.customer_id == actor.pk:
        # The cancellation policy applies to customers only;
        # providers and admins can cancel at any time.
        if booking.start - now < CANCELLATION_WINDOW:
            hours = int(CANCELLATION_WINDOW.total_seconds() // 3600)
            raise InvalidTransitionError(
                f"Bookings can't be cancelled less than {hours} hours before the start."
            )


def transition_booking(
    *,
    booking_id: int,
    to_status: str,
    actor,
    note: str = "",
    now: datetime | None = None,
) -> Booking:
    now = now or timezone.now()

    # Release expired pending bookings first (own transaction), so an expired
    # booking is already "cancelled" when we look at it below.
    provider_id = Booking.objects.values_list("provider_id", flat=True).get(pk=booking_id)
    expire_stale_pending_bookings(provider=provider_id, now=now)

    with transaction.atomic():
        # Lock the row: two parallel requests (e.g. confirm + cancel) are
        # serialized, and the second one sees the result of the first.
        booking = Booking.objects.select_for_update().get(pk=booking_id)

        _check_actor(booking, to_status, actor)

        if not booking.can_transition_to(to_status):
            raise InvalidTransitionError(
                f"Can't change status from '{booking.status}' to '{to_status}'."
            )

        _check_business_rules(booking, to_status, actor, now)

        from_status = booking.status
        booking.status = to_status
        booking.expires_at = None  # only pending bookings have a deadline
        if to_status == BookingStatus.CANCELLED:
            booking.cancel_reason = note
        booking.save(update_fields=["status", "expires_at", "cancel_reason", "updated_at"])

        BookingStatusLog.objects.create(
            booking=booking,
            from_status=from_status,
            to_status=to_status,
            changed_by=actor,
            note=note,
        )
    return booking