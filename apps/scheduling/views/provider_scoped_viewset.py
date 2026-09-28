from django.shortcuts import get_object_or_404
from rest_framework import viewsets

from ..models import Provider
from ..permissions import CanManageProviderSchedule


class ProviderScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageProviderSchedule]
    pagination_class = None  
    
    def get_provider(self) -> Provider:
        if not hasattr(self, "_provider"):
            self._provider = get_object_or_404(Provider, pk=self.kwargs["provider_pk"])
        return self._provider
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "provider_pk" in self.kwargs:
            context["provider"] = self.get_provider()
        return context
    
    def perform_create(self, serializer):
        serializer.save(provider=self.get_provider())