from rest_framework.routers import SimpleRouter

from .views import ServiceViewSet

router = SimpleRouter()
router.register("services", ServiceViewSet, basename="service")

urlpatterns = router.urls