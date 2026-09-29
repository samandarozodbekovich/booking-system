from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.models import BookingStatus
from apps.bookings.services import create_booking, expire_stale_pending_bookings
from apps.bookings.tasks import expire_pending_bookings

from .helpers import at, make_booking

pytestmark = pytest.mark.django_db


def test_only_expired_pending_bookings_are_cancelled(customer, provider, service, booking_day):
    now = timezone.now()
    expired = make_booking(customer, provider, service, at(booking_day, "10:00"),
                           status="pending", expires_at=now - timedelta(minutes=1))
    fresh = make_booking(customer, provider, service, at(booking_day, "12:00"),
                         status="pending", expires_at=now + timedelta(minutes=10))

    assert expire_stale_pending_bookings(now=now) == 1

    expired.refresh_from_db()
    fresh.refresh_from_db()
    assert expired.status == BookingStatus.CANCELLED
    assert expired.expires_at is None
    assert fresh.status == BookingStatus.PENDING

    log = expired.status_logs.get()
    assert (log.from_status, log.to_status, log.changed_by) == ("pending", "cancelled", None)


def test_celery_task_returns_number_of_expired_bookings(customer, provider, service, booking_day):
    make_booking(customer, provider, service, at(booking_day, "10:00"),
                 status="pending", expires_at=timezone.now() - timedelta(minutes=1))

    assert expire_pending_bookings() == 1  # called directly, no broker needed
    assert expire_pending_bookings() == 0  # idempotent


def test_expired_slot_can_be_booked_without_celery(customer, other_customer, provider, service, booking_day):
    # The exclusion constraint still sees the expired booking as active,
    # so create_booking must release it inside its own transaction.
    make_booking(customer, provider, service, at(booking_day, "10:00"),
                 status="pending", expires_at=timezone.now() - timedelta(minutes=1))

    booking = create_booking(
        customer=other_customer, provider=provider, service=service, start=at(booking_day, "10:00")
    )

    assert booking.status == BookingStatus.PENDING