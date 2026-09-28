from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ..models import Booking


class BookingSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    provider = serializers.SerializerMethodField()
    service = serializers.SerializerMethodField()
    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = (
            "id",
            "customer",
            "provider",
            "service",
            "start",
            "end",
            "price",
            "status",
            "expires_at",
            "customer_note",
            "cancel_reason",
            "created_at",
        )
        read_only_fields = fields
        
    def get_customer(self, obj) -> dict:
        return {"id":obj.customer_id, "username":obj.customer.username}
    
    def get_provider(self, obj) -> dict:
        return {"id":obj.provider_id, "name": str(obj.provider)}
    
    def get_service(self, obj) -> dict:
        return {
            "id": obj.service_id,
            "name": obj.service.name,
            "duration_minutes": obj.service.duration_minutes
        }
        
    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_start(self, obj):
        return obj.start.astimezone(obj.provider.tz).isoformat()
    
    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_end(self, obj):
        return obj.end.astimezone(obj.provider.tz).isoformat()