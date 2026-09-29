from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.backends.postgresql.psycopg_any import DateTimeTZRange

from apps.bookings.models import Booking

TASHKENT = ZoneInfo("Asia/Tashkent")


def at(day: date, hhmm: str) -> datetime:
    """Aware datetime for a local Tashkent time on the given day."""
    hours, minutes = map(int, hhmm.split(":"))
    return datetime.combine(day, time(hours, minutes), tzinfo=TASHKENT)


def make_booking(customer, provider, service, start, status="confirmed", **extra) -> Booking:
    """Insert a booking directly, bypassing business checks (for test setup)."""
    end = start + timedelta(minutes=service.duration_minutes)
    return Booking.objects.create(
        customer=customer,
        provider=provider,
        service=service,
        period=DateTimeTZRange(start, end, "[)"),
        price=service.price,
        status=status,
        **extra,
    )