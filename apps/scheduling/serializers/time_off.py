from rest_framework import serializers

from apps.bookings.models import ACTIVE_STATUSES, Booking
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange

from ..models import TimeOff


class TimeOffSerializer(serializers.ModelSerializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    
    class Meta:
        model = TimeOff
        fields = ["id", "start", "end", 'reason', "created_at"]
        read_only_fields = ["id", "created_at"]
        
    def validate(self, attrs):
        start = attrs.pop("start", getattr(self.instance, "start", None))
        end = attrs.pop("end", getattr(self.instance, "end", None))
        
        if end <= start:
            raise serializers.ValidationError("End time must be after start time.")
        
        period = DateTimeTZRange(start, end, "[)")
        conflicts = Booking.objects.filter(
            provider=self.context["provider"],
            status__in = ACTIVE_STATUSES,
            period__overlap=period
        ).count()
        
        if conflicts:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        f"This time off period {conflicts} with existing bookings."
                        "Cancel or reschedule them first"
                    ]
                }
            )
        attrs["period"] = period
        return attrs