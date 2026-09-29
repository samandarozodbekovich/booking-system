from rest_framework import serializers

from ..models import Booking, BookingStatusLog

class BookingNoteSerializer(serializers.Serializer):
    """Optional comment for a status change (e.g. a cancellation reason)."""

    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
