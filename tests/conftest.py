from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User

from .factories import ProviderFactory, ServiceFactory, UserFactory, WorkingHoursFactory
from .helpers import TASHKENT


@pytest.fixture
def client_for():
    """Return an API client authenticated as the given user."""

    def _client_for(user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user)
        return client

    return _client_for


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def customer(db):
    return UserFactory()


@pytest.fixture
def other_customer(db):
    return UserFactory()


@pytest.fixture
def admin_user(db):
    return UserFactory(role=User.Role.ADMIN)


@pytest.fixture
def service(db):
    return ServiceFactory(duration_minutes=60)


@pytest.fixture
def provider(db, service):
    """A provider working Monday-Friday, 09:00-18:00 Tashkent time."""
    provider = ProviderFactory()
    provider.services.add(service)
    for weekday in range(5):
        WorkingHoursFactory(provider=provider, weekday=weekday)
    return provider


@pytest.fixture
def other_provider(db, service):
    provider = ProviderFactory()
    provider.services.add(service)
    for weekday in range(5):
        WorkingHoursFactory(provider=provider, weekday=weekday)
    return provider


@pytest.fixture
def booking_day() -> date:
    """The next Monday that is at least 2 days away (inside the 60-day window)."""
    today = timezone.now().astimezone(TASHKENT).date()
    days_ahead = (0 - today.weekday()) % 7
    if days_ahead < 2:
        days_ahead += 7
    return today + timedelta(days=days_ahead)