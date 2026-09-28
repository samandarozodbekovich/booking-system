from rest_framework.routers import SimpleRouter

from .views import ProviderViewSet, TimeOffViewSet, WorkingHoursViewSet

router = SimpleRouter()
router.register("providers", ProviderViewSet, basename="provider")
router.register(
    r"providers/(?P<provider_pk>\d+)/working-hours",
    WorkingHoursViewSet,
    basename="provider-working-hours",
)
router.register(
    r"providers/(?P<provider_pk>\d+)/time-offs",
    TimeOffViewSet,
    basename="provider-time-offs",
)

urlpatterns = router.urls