from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Service(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(5), MaxValueValidator(8 * 60)],
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    # Soft delete: old bookings keep pointing to the service.
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                name="service_duration_positive",
                condition=Q(duration_minutes__gt=0),
            ),
            models.CheckConstraint(
                name="service_price_non_negative",
                condition=Q(price__gte=0),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.duration_minutes} min)"