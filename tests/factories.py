from datetime import time
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import User
from apps.catalog.models import Service
from apps.scheduling.models import Provider, WorkingHours

DEFAULT_PASSWORD = "Str0ng-pass!"


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    password = factory.django.Password(DEFAULT_PASSWORD)
    role = User.Role.CUSTOMER


class ServiceFactory(DjangoModelFactory):
    class Meta:
        model = Service

    name = factory.Sequence(lambda n: f"Service {n}")
    duration_minutes = 60
    price = Decimal("100000.00")


class ProviderFactory(DjangoModelFactory):
    class Meta:
        model = Provider

    user = factory.SubFactory(UserFactory, role=User.Role.PROVIDER)
    timezone = "Asia/Tashkent"


class WorkingHoursFactory(DjangoModelFactory):
    class Meta:
        model = WorkingHours

    provider = factory.SubFactory(ProviderFactory)
    weekday = 0
    start_time = time(9, 0)
    end_time = time(18, 0)