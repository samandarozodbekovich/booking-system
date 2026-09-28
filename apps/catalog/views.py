from rest_framework import viewsets

from .serializers import ServiceSerializer
from .models import Service
from apps.accounts.permissions import IsBusinessAdminOrReadOnly


class ServiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsBusinessAdminOrReadOnly]
    serializer_class = ServiceSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "price", "duration_minutes", "created_at"]
    
    def get_queryset(self):
        queryset = Service.objects.all()
        if not getattr(self.request.user, "is_business_admin", False):
            queryset = queryset.filter(is_active=True)
        return queryset
    
    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])