from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsBusinessAdminOrReadOnly
from apps.scheduling.availability import get_available_slots
from apps.scheduling.serializers import (
    AvailabilityQuerySerializer,
    AvailabilityResponseSerializer,
    ProviderSerializer,
)
from apps.scheduling.serializers.service_brief import ServiceBriefSerializer

from ..models import Provider

class ProviderViewSet(viewsets.ModelViewSet):
    serializer_class = ProviderSerializer
    permission_classes = [IsBusinessAdminOrReadOnly]
    filterset_fields = ["services","is_active"]
    search_fields = ["user__first_name", "user__last_name", "user__username", "bio"]
    ordering_fields = ["created_at"]
    
    def get_queryset(self):
        queryset = (Provider.objects
                    .select_related("user")
                    .prefetch_related("services")
                    .order_by("id")
                    )
        if not getattr(self.request.user, "is_business_admin", False):
            queryset = queryset.filter(is_active=True)
        return queryset
    
    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        
    @extend_schema(
        parameters=[AvailabilityQuerySerializer],
        responses=AvailabilityResponseSerializer,
    )
    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        provider = self.get_object()
        query = AvailabilityQuerySerializer(
            data=request.query_params,
            context = {"provider":provider},
        )
        query.is_valid(raise_exception=True)
        service = query.validated_data["service"]
        day = query.validated_data["date"]
        
        slots = get_available_slots(provider, service, day)
        
        tz = provider.tz
        return Response({
            "date":day,
            "timezone":provider.timezone,
            "service":ServiceBriefSerializer(service).data,
            "slots":[
                {
                    "start":slot.start.astimezone(tz).isoformat(),
                    "end": slot.end.astimezone(tz).isoformat(),
                } for slot in slots
            ],  
        })