
from apps.scheduling.serializers.working_hours import WorkingHoursSerializer
from apps.scheduling.views.provider_scoped_viewset import ProviderScopedViewSet
from ..models import WorkingHours


class WorkingHoursViewSet(ProviderScopedViewSet):
    serializer_class = WorkingHoursSerializer
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return WorkingHours.objects.none()
        return WorkingHours.objects.filter(provider=self.get_provider()).order_by("weekday")