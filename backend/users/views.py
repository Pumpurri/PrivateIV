from .models import CustomUser
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from .serializers import UserCreateSerializer
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
import logging

class UserList(generics.ListCreateAPIView):
    """
    Allows admins to list all users.
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [IsAdminUser]

class UserDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Allows admins to retrieve, update, or delete any user.
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [IsAdminUser]

class RegisterView(generics.CreateAPIView):
    """
    Handles user registration.
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [AllowAny] 

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Allows a logged-in user to retrieve or update their own profile.
    """
    serializer_class = UserCreateSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
    
class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom token refresh view that retrieves the refresh token from cookies 
    and injects it into the request.
    """
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')  # Gets from cookie
        if refresh_token:
            request.data['refresh'] = refresh_token  # Injects into request
        return super().post(request, *args, **kwargs)

logger = logging.getLogger(__name__)
class CustomLogoutView(APIView):
    """
    Handles user logout by blacklisting the refresh token and clearing cookies.
    """
    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({"error": "No refresh token"}, status=400)

        try:
            token = RefreshToken(refresh_token)
            try:
                token.blacklist()
            except TokenError as e:
                logger.warning(f"Token already blacklisted: {e}")

            response = Response({"detail": "Successfully logged out"}, status=200)
            
            cookie_attrs = {
                'path': '/',
                # Add 'secure': True in PRODUCTION
            }
            
            response.delete_cookie('access_token', **cookie_attrs)
            response.delete_cookie('refresh_token', **cookie_attrs)
            return response

        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({"error": "Invalid token"}, status=400)


# TODO: Add a view for password change
# TODO: Add a view for password reset



# Possibly change email, email verification (and resend), deactivate account