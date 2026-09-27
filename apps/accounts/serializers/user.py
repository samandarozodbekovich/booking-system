
from rest_framework import serializers

from .register import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "phone", "role")
        read_only_fields = ("id", 'username',"email", "role")