from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from rest_framework import serializers

from apps.catalog.models import Service
from ..models import Provider
from .service_brief import ServiceBriefSerializer

User = get_user_model()


class ProviderSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=User.objects.all(),
        write_only=True
        )
    name = serializers.SerializerMethodField()
    services = ServiceBriefSerializer(many=True, read_only=True)
    service_ids = serializers.PrimaryKeyRelatedField(
        source="services",
        queryset=Service.objects.filter(is_active=True),
        many=True,
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Provider
        fields = (
            'id',
            'user_id',
            'name',
            'bio',
            'timezone',
            'services',
            'is_active',
            'service_ids',
            'created_at',
        )
        read_only_fields = (
            'id',
            'created_at',
        )
    def get_name(self, obj) -> str:
        return str(obj)
    
    def validate_user_id(self, user):
        if self.instance and user.pk != self.instance.user_id:
            raise serializers.ValidationError("The user of a provider can't be changed.")
        if user.is_business_admin:
            raise serializers.ValidationError("An admin account can't be a provider.")
        exists = Provider.objects.filter(user=user)
        if self.instance:
            exists = exists.exclude(pk=self.instance.pk)
        if exists.exists():
            raise serializers.ValidationError("This user is already a provider.")
        return user
    
    def create(self, validated_data):
        user = validated_data["user"]
        try:
            with transaction.atomic():
                if user.role != User.Role.PROVIDER:
                    user.role = User.Role.PROVIDER
                    user.save(update_fields=["role"])
                return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"user_id": "This user is already a provider."})