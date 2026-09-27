from rest_framework import generics
from rest_framework.permissions import AllowAny

from ..serializers.register import RegisterSerializer


class RegisterAPIView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    