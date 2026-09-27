from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers.logout import LogoutSerializer


class LogoutAPIView(generics.GenericAPIView):
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:    
            token = RefreshToken(serializer.validated_data["refresh"])
            if str(token.get('user_id')) != str(request.user.pk):
                return Response({
                    "detail": "Token user does not match the logged-in user."}, 
                    status=status.HTTP_403_FORBIDDEN)
            token.blacklist()
        except TokenError:
            return Response({
                "detail": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)
            