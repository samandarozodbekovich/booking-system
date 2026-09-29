from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

from apps.accounts.permissions import IsCustomer

from .models import Booking, BookingStatus
from .serializers import (
    BookingCreateSerializer,
    BookingNoteSerializer,
    BookingSerializer,
    BookingStatusLogSerializer,
)
from .services import (
    BookingPermissionError,
    InvalidTransitionError,
    SlotUnavailableError,
    create_booking,
    transition_booking,
)

TRANSITION_RESPONSES = {
    200: BookingSerializer,
    403: OpenApiResponse(description="Not allowed for this user"),
    404: OpenApiResponse(description="Booking not found"),
    409: OpenApiResponse(description="Status change conflicts with the current state"),
}

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
        # Each role sees only what belongs to it.
        if user.is_business_admin:
            return queryset
        if user.is_provider and hasattr(user, "provider_profile"):
            return queryset.filter(provider=user.provider_profile)
        return queryset.filter(customer=user)
    
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
    
        # ---------- status transitions ----------

    def _transition(self, request, to_status: str):
        booking = self.get_object()  # 404 if the user can't see this booking
        note_serializer = BookingNoteSerializer(data=request.data)
        note_serializer.is_valid(raise_exception=True)
        try:
            booking = transition_booking(
                booking_id=booking.pk,
                to_status=to_status,
                actor=request.user,
                note=note_serializer.validated_data["note"],
            )
        except BookingPermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(BookingSerializer(booking).data)

    @extend_schema(request=BookingNoteSerializer, responses=TRANSITION_RESPONSES)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._transition(request, BookingStatus.CONFIRMED)

    @extend_schema(request=BookingNoteSerializer, responses=TRANSITION_RESPONSES)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(request, BookingStatus.CANCELLED)

    @extend_schema(request=BookingNoteSerializer, responses=TRANSITION_RESPONSES)
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._transition(request, BookingStatus.COMPLETED)

    @extend_schema(responses=BookingStatusLogSerializer(many=True))
    @action(detail=True, methods=["get"], pagination_class=None)
    def history(self, request, pk=None):
        booking = self.get_object()
        logs = booking.status_logs.select_related("changed_by")
        return Response(BookingStatusLogSerializer(logs, many=True).data)
        