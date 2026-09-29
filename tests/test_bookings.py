from decimal import Decimal

import pytest

from apps.bookings.models import Booking, BookingStatus

from .factories import ServiceFactory
from .helpers import at, make_booking

pytestmark = pytest.mark.django_db


def book(client, provider, service, start):
    return client.post(
        "/api/bookings/",
        {"provider": provider.id, "service": service.id, "start": start.isoformat()},
        format="json",
    )


def test_customer_creates_pending_booking(client_for, customer, provider, service, booking_day):
    response = book(client_for(customer), provider, service, at(booking_day, "10:00"))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["end"].endswith("11:00:00+05:00")  # computed by the server
    assert body["price"] == "100000.00"  # snapshot of the service price
    assert body["expires_at"] is not None

    booking = Booking.objects.get(pk=body["id"])
    log = booking.status_logs.get()
    assert (log.from_status, log.to_status, log.changed_by) == (None, "pending", customer)


def test_same_slot_twice_returns_409(client_for, customer, other_customer, provider, service, booking_day):
    book(client_for(customer), provider, service, at(booking_day, "10:00"))

    response = book(client_for(other_customer), provider, service, at(booking_day, "10:00"))

    assert response.status_code == 409


def test_overlapping_slot_returns_409(client_for, customer, other_customer, provider, service, booking_day):
    book(client_for(customer), provider, service, at(booking_day, "10:00"))

    response = book(client_for(other_customer), provider, service, at(booking_day, "10:30"))

    assert response.status_code == 409


@pytest.mark.parametrize("hhmm", ["11:05", "08:00", "17:30"])
def test_invalid_start_times_return_409(client_for, customer, provider, service, booking_day, hhmm):
    # off the grid / before working hours / would end after 18:00
    response = book(client_for(customer), provider, service, at(booking_day, hhmm))

    assert response.status_code == 409


def test_customer_cannot_be_in_two_places_at_once(
    client_for, customer, provider, other_provider, service, booking_day
):
    client = client_for(customer)
    book(client, provider, service, at(booking_day, "10:00"))

    response = book(client, other_provider, service, at(booking_day, "10:00"))

    assert response.status_code == 409
    assert response.json()["detail"] == "You already have another booking at this time."


def test_provider_must_offer_the_service(client_for, customer, provider, booking_day):
    response = book(client_for(customer), provider, ServiceFactory(), at(booking_day, "10:00"))

    assert response.status_code == 400
    assert "service" in response.json()


def test_provider_cannot_create_bookings(client_for, provider, service, booking_day):
    response = book(client_for(provider.user), provider, service, at(booking_day, "10:00"))

    assert response.status_code == 403


def test_price_snapshot_survives_price_change(client_for, customer, provider, service, booking_day):
    booking_id = book(client_for(customer), provider, service, at(booking_day, "10:00")).json()["id"]

    service.price = Decimal("999999.00")
    service.save()

    assert Booking.objects.get(pk=booking_id).price == Decimal("100000.00")


def test_each_role_sees_only_its_own_bookings(
    client_for, customer, other_customer, provider, other_provider, service, admin_user, booking_day
):
    make_booking(customer, provider, service, at(booking_day, "10:00"))
    make_booking(other_customer, other_provider, service, at(booking_day, "10:00"))

    def count(user):
        return client_for(user).get("/api/bookings/").json()["count"]

    assert count(customer) == 1
    assert count(provider.user) == 1
    assert count(admin_user) == 2


def test_foreign_booking_is_not_found(client_for, customer, other_customer, provider, service, booking_day):
    booking = make_booking(customer, provider, service, at(booking_day, "10:00"))

    response = client_for(other_customer).get(f"/api/bookings/{booking.id}/")

    assert response.status_code == 404


def test_cancelled_slot_can_be_booked_again(client_for, customer, other_customer, provider, service, booking_day):
    make_booking(customer, provider, service, at(booking_day, "10:00"), status=BookingStatus.CANCELLED)

    response = book(client_for(other_customer), provider, service, at(booking_day, "10:00"))

    assert response.status_code == 201