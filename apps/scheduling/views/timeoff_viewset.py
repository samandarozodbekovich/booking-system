from apps.scheduling.serializers.time_off import TimeOffSerializer
from apps.scheduling.views.provider_scoped_viewset import ProviderScopedViewSet
from ..models import TimeOff


class TimeOffViewSet(ProviderScopedViewSet):
    serializer_class = TimeOffSerializer
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TimeOff.objects.none()
        return TimeOff.objects.filter(provider=self.get_provider())