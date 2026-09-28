from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.catalog.models import Service

MAX_DAYS_AHEAD = 60

class AvailabilityQuerySerializer(serializers.Serializer):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    date = serializers.DateField()
    
    def validate_service(self, service):
        if not self.context["provider"].services.filter(pk=service.pk).exists():
            raise serializers.ValidationError("This provider does not offer the selected service.")
        return service
    
    def validate_date(self, value):
        today = timezone.now().astimezone(self.context['provider'].tz).date()
        if value < today:
            raise serializers.ValidationError("Date is in the past")
        if value > today + timedelta(days=MAX_DAYS_AHEAD):
            raise serializers.ValidationError(f"Date must be within {MAX_DAYS_AHEAD} days")
        return value