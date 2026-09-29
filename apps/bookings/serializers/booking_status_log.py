from rest_framework import serializers

from ..models import BookingStatusLog

class BookingStatusLogSerializer(serializers.ModelSerializer):
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = BookingStatusLog
        fields = ("from_status", "to_status", "changed_by", "note", "changed_at")
        read_only_fields = fields

    def get_changed_by(self, obj) -> str:
        return obj.changed_by.username if obj.changed_by else "system"