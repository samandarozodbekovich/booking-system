"""Manual check for step 7: availability, double booking and role-based lists."""

from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.bookings.models import Booking

settings.ALLOWED_HOSTS = ["*"]


def client_for(user):
    client = APIClient()
    client.force_authenticate(user) 
    return client


booking = Booking.objects.select_related("customer", "provider__user").get(pk=1)
first_customer = booking.customer
provider_user = booking.provider.user
second_customer, _ = User.objects.get_or_create(
    username="second_customer",
    defaults={"email": "second_customer@example.com"},
)

expired = booking.status == "pending" and booking.expires_at <= timezone.now()
print("Booking #1:", booking.status, "| expired:", expired)

url = (
    f"/api/providers/{booking.provider_id}/availability/"
    f"?service={booking.service_id}&date=2026-10-06"
)
slots = client_for(first_customer).get(url).json()["slots"]
print("1) Availability slots:", [slot["start"][11:16] for slot in slots])

if expired:
    print("2) Skipped: booking #1 expired, so the slot is free again (expected).")
else:
    payload = {
        "provider": booking.provider_id,
        "service": booking.service_id,
        "start": "2026-10-06T09:00:00+05:00",
    }
    response = client_for(second_customer).post("/api/bookings/", payload, format="json")
    print("2) Second customer:", response.status_code, response.json())

for label, user in [
    ("first customer", first_customer),
    ("second customer", second_customer),
    ("provider", provider_user),
]:
    count = client_for(user).get("/api/bookings/").json()["count"]
    print(f"3) {label}: {count} booking(s)")