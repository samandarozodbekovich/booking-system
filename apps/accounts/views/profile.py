from rest_framework import generics

from apps.accounts.serializers.user import UserSerializer


class ProfileAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    http_method_names = ['get', 'options', 'patch']

    def get_object(self):
        return self.request.user