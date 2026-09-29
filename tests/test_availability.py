from datetime import timedelta

import pytest
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from apps.scheduling.availability import get_available_slots, is_slot_available
from apps.scheduling.models import TimeOff, WorkingHours

from .factories import ServiceFactory
from .helpers import TASHKENT, at, make_booking

pytestmark = pytest.mark.django_db


def local_starts(slots) -> list[str]:
    return [slot.start.astimezone(TASHKENT).strftime("%H:%M") for slot in slots]


def test_free_day_returns_full_grid(provider, service, booking_day):
    starts = local_starts(get_available_slots(provider, service, booking_day))

    # 09:00 ... 17:00 every 15 minutes: the last 60-min slot ends exactly at 18:00.
    assert starts[0] == "09:00"
    assert starts[-1] == "17:00"
    assert len(starts) == 33


def test_booking_blocks_overlapping_slots_but_not_touching_ones(provider, service, customer, booking_day):
    make_booking(customer, provider, service, at(booking_day, "10:00"))

    starts = local_starts(get_available_slots(provider, service, booking_day))

    assert "09:00" in starts  # 09:00-10:00 only touches the booking
    assert "11:00" in starts  # 11:00-12:00 only touches the booking
    for blocked in ["09:15", "09:45", "10:00", "10:45"]:
        assert blocked not in starts


def test_time_off_blocks_slots(provider, service, booking_day):
    TimeOff.objects.create(
        provider=provider,
        period=DateTimeTZRange(at(booking_day, "12:00"), at(booking_day, "13:00"), "[)"),
    )

    starts = local_starts(get_available_slots(provider, service, booking_day))

    assert "11:00" in starts
    assert "11:15" not in starts
    assert "12:30" not in starts
    assert "13:00" in starts


@pytest.mark.parametrize("status", ["cancelled", "completed"])
def test_inactive_bookings_do_not_block(provider, service, customer, booking_day, status):
    make_booking(customer, provider, service, at(booking_day, "10:00"), status=status)

    assert "10:00" in local_starts(get_available_slots(provider, service, booking_day))


def test_expired_pending_booking_does_not_block(provider, service, customer, booking_day):
    make_booking(
        customer, provider, service, at(booking_day, "10:00"),
        status="pending", expires_at=timezone.now() - timedelta(minutes=1),
    )

    assert "10:00" in local_starts(get_available_slots(provider, service, booking_day))


def test_active_pending_booking_blocks(provider, service, customer, booking_day):
    make_booking(
        customer, provider, service, at(booking_day, "10:00"),
        status="pending", expires_at=timezone.now() + timedelta(minutes=10),
    )

    assert "10:00" not in local_starts(get_available_slots(provider, service, booking_day))


def test_service_must_fit_inside_one_working_interval(provider, booking_day):
    WorkingHours.objects.filter(provider=provider, weekday=0).delete()
    WorkingHours.objects.create(provider=provider, weekday=0, start_time="09:00", end_time="13:00")
    WorkingHours.objects.create(provider=provider, weekday=0, start_time="14:00", end_time="18:00")
    long_service = ServiceFactory(duration_minutes=200)

    starts = local_starts(get_available_slots(provider, long_service, booking_day))

    # 09:30 + 200 min = 12:50 fits, 09:45 would end at 13:05 (lunch break).
    assert starts == ["09:00", "09:15", "09:30", "14:00", "14:15", "14:30"]


def test_past_slots_are_not_offered(provider, service, booking_day):
    now = at(booking_day, "14:20")

    starts = local_starts(get_available_slots(provider, service, booking_day, now=now))

    assert starts[0] == "14:30"


def test_day_without_working_hours_is_empty(provider, service, booking_day):
    saturday = booking_day + timedelta(days=5)

    assert get_available_slots(provider, service, saturday) == []


def test_is_slot_available_accepts_only_grid_slots(provider, service, booking_day):
    assert is_slot_available(provider, service, at(booking_day, "11:00"))
    assert not is_slot_available(provider, service, at(booking_day, "11:05"))  # off the grid
    assert not is_slot_available(provider, service, at(booking_day, "08:00"))  # before hours


def test_availability_endpoint_returns_local_times(client_for, customer, provider, service, booking_day):
    response = client_for(customer).get(
        f"/api/providers/{provider.id}/availability/",
        {"service": service.id, "date": booking_day.isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Asia/Tashkent"
    assert body["slots"][0]["start"].endswith("09:00:00+05:00")


def test_availability_rejects_service_not_offered(client_for, customer, provider, booking_day):
    other_service = ServiceFactory()

    response = client_for(customer).get(
        f"/api/providers/{provider.id}/availability/",
        {"service": other_service.id, "date": booking_day.isoformat()},
    )

    assert response.status_code == 400
    assert "service" in response.json()


def test_availability_rejects_past_date(client_for, customer, provider, service):
    response = client_for(customer).get(
        f"/api/providers/{provider.id}/availability/",
        {"service": service.id, "date": "2020-01-01"},
    )

    assert response.status_code == 400
    assert "date" in response.json()