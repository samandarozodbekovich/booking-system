from rest_framework import serializers
from rest_framework.exceptions import ValidationError
 
from ..models import WorkingHours

class WorkingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingHours
        fields = ["id", "weekday", "start_time", "end_time"]
        read_only_fields = ["id"]
        
    def validate(self, attrs):
        weekday = attrs.get("weekday", getattr(self.instance, "weekday", None))
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        
        if end <= start:
            raise serializers.ValidationError("End time must be after start time.")
        
        candidate = WorkingHours(
            pk = getattr(self.instance, "pk", None),
            provider = self.context["provider"],
            weekday = weekday,
            start_time = start,
            end_time = end
        )
        
        try:
            candidate.clean()
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        return attrs
            

