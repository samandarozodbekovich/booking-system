"""
Availability calculation.

free time = working hours - time offs - active bookings

"""

from dataclasses import dataclass
from datetime import UTC, date,datetime, time, timedelta

from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.db.models import Q
from django.utils import timezone

from apps.bookings.models import Booking, BookingStatus
from apps.catalog.models import Service

from .models import TimeOff, WorkingHours, Provider

SLOT_STEP = timedelta(minutes=15)

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime
    
def _day_window(provider: Provider, day:date) -> Interval:
    tz = provider.tz
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)

def _working_intervals(provider: Provider, day:date)-> list[Interval]:
    tz = provider.tz
    rows = WorkingHours.objects.filter(provider=provider, weekday=day.weekday()).order_by("start_time")
    return [
        (
            datetime.combine(day, row.start_time, tzinfo=tz).astimezone(UTC),
            datetime.combine(day, row.end_time, tzinfo=tz).astimezone(UTC),
        )
        for row in rows
    ]
    
def _busy_intervals(provider: Provider, window: Interval, now: datetime) -> list[Interval]:
    window_range = DateTimeTZRange(window[0], window[1], "[)")

    busy = [
        (off.start, off.end)
        for off in TimeOff.objects.filter(provider=provider, period__overlap=window_range)
    ]

    active = Q(status=BookingStatus.CONFIRMED) | (
        Q(status=BookingStatus.PENDING) & (Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    )
    bookings = Booking.objects.filter(active, provider=provider, period__overlap=window_range)
    busy += [(booking.start, booking.end) for booking in bookings]
    return busy


def _overlaps(start: datetime, end: datetime, intervals: list[Interval]) -> bool:
      # Half-open intervals [start, end): touching edges do not overlap.
    return any(start < busy_end and busy_start < end for busy_start, busy_end in intervals)

def get_available_slots(
    provider:Provider, service:Service, day:date, now:datetime | None = None 
)-> list[Slot]:
    now = now or timezone.now()
    duration = timedelta(minutes=service.duration_minutes)
    busy = _busy_intervals(provider, _day_window(provider,day), now)
    
    slots = []
    for work_start, work_end in _working_intervals(provider, day):
        candidate = work_start
        while candidate + duration <= work_end:
            end = candidate + duration
            if candidate > now and not _overlaps(candidate, end, busy):
                slots.append(Slot(candidate, end))
            candidate += SLOT_STEP
    return slots

def is_slot_available(
    provider:Provider,
    service:Service,
    start: datetime,
    now:datetime | None=None,
)-> bool:
    local_day = start.astimezone(provider.tz).date()
    start_utc = start.astimezone(UTC)
    return any(slot.start == start_utc for slot in get_available_slots(provider, service, local_day, now))