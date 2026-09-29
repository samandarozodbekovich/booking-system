"""
Concurrency tests. They use real threads and real transactions, so the data
must be committed (transaction=True) and each thread closes its own connection.
"""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.bookings.models import ACTIVE_STATUSES, Booking, BookingStatus
from apps.bookings.services import (
    InvalidTransitionError,
    SlotUnavailableError,
    create_booking,
    transition_booking,
)

from .factories import UserFactory
from .helpers import at, make_booking

pytestmark = pytest.mark.django_db(transaction=True)


def run_in_parallel(targets):
    """Start all callables at the same moment and collect their outcomes."""
    barrier = threading.Barrier(len(targets))
    results = []
    lock = threading.Lock()

    def worker(target):
        barrier.wait()  # every thread fires at the same time
        try:
            target()
            outcome = "ok"
        except (SlotUnavailableError, InvalidTransitionError) as exc:
            outcome = type(exc).__name__
        finally:
            connection.close()  # each thread has its own DB connection
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(target,)) for target in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def test_only_one_of_many_parallel_bookings_wins(provider, service, booking_day):
    customers = [UserFactory() for _ in range(10)]
    start = at(booking_day, "10:00")

    results = run_in_parallel([
        lambda customer=customer: create_booking(
            customer=customer, provider=provider, service=service, start=start
        )
        for customer in customers
    ])

    assert results.count("ok") == 1
    assert results.count("SlotUnavailableError") == 9
    assert Booking.objects.filter(provider=provider, status__in=ACTIVE_STATUSES).count() == 1


def test_parallel_confirms_change_status_once(customer, provider, service, admin_user, booking_day):
    booking = make_booking(
        customer, provider, service, at(booking_day, "10:00"),
        status=BookingStatus.PENDING, expires_at=timezone.now() + timedelta(minutes=10),
    )

    results = run_in_parallel([
        lambda: transition_booking(booking_id=booking.id, to_status="confirmed", actor=provider.user),
        lambda: transition_booking(booking_id=booking.id, to_status="confirmed", actor=admin_user),
    ])

    assert sorted(results) == ["InvalidTransitionError", "ok"]
    assert booking.status_logs.count() == 1