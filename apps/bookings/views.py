from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsCustomer

from .models import Booking
from .serializers import BookingSerializer, BookingCreateSerializer
from .services import SlotUnavailableError, create_booking

class BookingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    serializer_class = BookingSerializer
    filterset_fields = ["status", "provider", "service"]
    ordering_fields = ["created_at", "period"]
    ordering = ["-created_at"]
    
    def get_permissions(self):
        if self.action == "create":
            return [IsCustomer()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        queryset = Booking.objects.select_related("customer", "provider__user", "service")
        user = self.request.user
        if getattr(self, "swagger_fake_view", False) or not user.is_authenticated:
            return queryset.none()
        
        if user.is_provider and hasattr(user, "provider_profile"):
            return queryset.filter(provider = user.provider_profile)
        return queryset.filter(customer = user)
    
    @extend_schema(
        request = BookingCreateSerializer,
        responses = {
            201:BookingSerializer,
            400:OpenApiResponse(description = "Validation error"),
            409:OpenApiResponse(description = "The time slot is not available"),
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = BookingCreateSerializer(data = request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = create_booking(customer = request.user, **serializer.validated_data)
        except SlotUnavailableError as exc:
            return Response({"detail":str(exc)}, status = status.HTTP_409_CONFLICT)
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED) 
        