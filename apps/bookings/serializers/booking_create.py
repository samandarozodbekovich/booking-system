from rest_framework import serializers

from apps.catalog.models import Service
from apps.scheduling.models import Provider


class BookingCreateSerializer(serializers.Serializer):
    provider = serializers.PrimaryKeyRelatedField(queryset=Provider.objects.filter(is_active=True))
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    start = serializers.DateTimeField()
    customer_note = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    
    def validate(self, attrs):
        if not attrs["provider"].services.filter(pk=attrs["service"].pk).exists():
            raise serializers.ValidationError(
                {
                    "service":"this provider does not offer this selected service"
                }
            )
        return attrs    
        
    