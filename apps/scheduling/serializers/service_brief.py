from rest_framework import serializers

from apps.catalog.models import Service


class ServiceBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("id", "name", "duration_minutes", "price")