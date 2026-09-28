from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError 
from django.db import IntegrityError, transaction
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type":"password"})
    
    class Meta:
        model = User
        fields = ("id", 'username',"email", "password", "first_name", "last_name", "phone")
        read_only_fields = ("id",)
        extra_kwargs = {"email": {"required":True}}
        
    def validate_email(self, value:str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate_username(self, value:str) -> str:
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value
    
    def validate(self, attrs):
        user = User(**{k:v for k,v in attrs.items() if k != "password"})
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs
    
    def create(self, validated_data):
        password = validated_data.pop("password")
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    password=password,
                    role = User.Role.CUSTOMER,
                    **validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"email": ["A user with this email already exists."]})