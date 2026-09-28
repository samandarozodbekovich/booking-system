from rest_framework import serializers

from .slot import SlotSerializer
from .service_brief import ServiceBriefSerializer

class AvailabilityResponseSerializer(serializers.Serializer):
    date = serializers.DateField()
    timezone = serializers.CharField()
    service = ServiceBriefSerializer()
    slots = SlotSerializer(many=True)