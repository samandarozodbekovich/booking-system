from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.models import ALLOWED_TRANSITIONS, Booking, BookingStatus

from .helpers import at, make_booking

pytestmark = pytest.mark.django_db

ALL_STATUSES = list(BookingStatus)


@pytest.mark.parametrize("from_status", ALL_STATUSES)
@pytest.mark.parametrize("to_status", ALL_STATUSES)
def test_state_machine(from_status, to_status):
    booking = Booking(status=from_status)

    expected = to_status in ALLOWED_TRANSITIONS[from_status]

    assert booking.can_transition_to(to_status) is expected


@pytest.fixture
def pending_booking(customer, provider, service, booking_day):
    return make_booking(
        customer, provider, service, at(booking_day, "10:00"),
        status=BookingStatus.PENDING, expires_at=timezone.now() + timedelta(minutes=10),
    )


def url(booking, action):
    return f"/api/bookings/{booking.id}/{action}/"


def test_provider_confirms(client_for, provider, pending_booking):
    response = client_for(provider.user).post(url(pending_booking, "confirm"), {"note": "See you"}, format="json")

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["expires_at"] is None


def test_customer_cannot_confirm(client_for, customer, pending_booking):
    assert client_for(customer).post(url(pending_booking, "confirm")).status_code == 403


def test_other_provider_does_not_see_the_booking(client_for, other_provider, pending_booking):
    assert client_for(other_provider.user).post(url(pending_booking, "confirm")).status_code == 404


def test_cancelled_booking_cannot_be_confirmed(client_for, provider, customer, pending_booking):
    client_for(customer).post(url(pending_booking, "cancel"))

    response = client_for(provider.user).post(url(pending_booking, "confirm"))

    assert response.status_code == 409


def test_cannot_complete_before_start(client_for, provider, pending_booking):
    client = client_for(provider.user)
    client.post(url(pending_booking, "confirm"))

    response = client.post(url(pending_booking, "complete"))

    assert response.status_code == 409


def test_complete_after_start(client_for, customer, provider, service):
    now = timezone.now()
    booking = make_booking(customer, provider, service, now - timedelta(hours=2))

    response = client_for(provider.user).post(url(booking, "complete"))

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_customer_cannot_cancel_close_to_start(client_for, customer, provider, service):
    booking = make_booking(customer, provider, service, timezone.now() + timedelta(hours=1))

    customer_response = client_for(customer).post(url(booking, "cancel"))
    provider_response = client_for(provider.user).post(url(booking, "cancel"), {"note": "Sick"}, format="json")

    assert customer_response.status_code == 409
    assert provider_response.status_code == 200  # the policy applies to customers only


def test_expired_pending_cannot_be_confirmed(client_for, customer, provider, service, booking_day):
    booking = make_booking(
        customer, provider, service, at(booking_day, "10:00"),
        status=BookingStatus.PENDING, expires_at=timezone.now() - timedelta(minutes=1),
    )

    response = client_for(provider.user).post(url(booking, "confirm"))

    booking.refresh_from_db()
    assert response.status_code == 409
    assert booking.status == BookingStatus.CANCELLED


def test_history_records_every_change(client_for, customer, provider, pending_booking):
    client_for(provider.user).post(url(pending_booking, "confirm"))
    client_for(customer).post(url(pending_booking, "cancel"), {"note": "Plans changed"}, format="json")

    history = client_for(customer).get(url(pending_booking, "history")).json()

    assert [(h["from_status"], h["to_status"]) for h in history] == [
        ("pending", "confirmed"),
        ("confirmed", "cancelled"),
    ]
    assert history[-1]["changed_by"] == customer.username
    assert history[-1]["note"] == "Plans changed"