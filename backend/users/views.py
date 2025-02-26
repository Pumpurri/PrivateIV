from .models import CustomUser
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from .serializers import UserCreateSerializer, CustomUserSerializer, CustomJWTSerializer
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import logging

class UserList(generics.ListCreateAPIView):
    """
    Allows admins to list all users.
    """
    queryset = CustomUser.objects.all()
    permission_classes = [IsAdminUser]
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer  # Registration
        return CustomUserSerializer

class UserDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Allows admins to retrieve, update, or delete any user.
    """
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAdminUser]

class RegisterView(generics.CreateAPIView):
    """
    Handles user registration.
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [AllowAny] 
    authentication_classes = []

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Allows a logged-in user to retrieve or update their own profile.
    """
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
    
class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom token refresh view that retrieves the refresh token from cookies 
    and injects it into the request.
    """
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:  
            return Response(
                {"error": "Refresh token missing"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        request.data['refresh'] = refresh_token
        return super().post(request, *args, **kwargs)

logger = logging.getLogger(__name__)
class CustomLogoutView(APIView):
    """
    Handles user logout by blacklisting the refresh token and clearing cookies.
    """
    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            logger.warning("No refresh token received in cookies!")
            return Response({"error": "No refresh token"}, status=400)

        try:
            token = RefreshToken(refresh_token)
            try:
                token.blacklist()
            except TokenError as e:
                logger.warning(f"Token already blacklisted: {e}")

            response = Response({"detail": "Logged out"}, status=200)
            for cookie_name in ['access_token', 'refresh_token']:
                response.delete_cookie(
                    cookie_name, 
                    path='/',
                )
            return response

        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({"error": "Invalid token"}, status=400)

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Handles user authentication by issuing JWT access and refresh tokens.
    Stores tokens in HTTP-only cookies.
    """
    serializer_class = CustomJWTSerializer
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access_lifetime = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
            refresh_lifetime = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']

            cookie_config = {
                'httponly': True,
                'secure': True,
                'samesite': 'None',
                'path': '/',
                'domain': settings.JWT_COOKIE_DOMAIN,
                'max_age': int(access_lifetime.total_seconds()),
                'expires': timezone.now() + access_lifetime,
            }
        
            response.set_cookie(
                'access_token',
                response.data['access'],
                **cookie_config
            )

            response.set_cookie(
                'refresh_token',
                response.data['refresh'],
                **{
                    **cookie_config,
                    'max_age': int(refresh_lifetime.total_seconds()),
                    'expires': timezone.now() + refresh_lifetime,
                }
            )

            response.data.pop('access', None)
            response.data.pop('refresh', None)

        return response

# TODO: Add a view for password change
# TODO: Add a view for password reset



# Possibly change email, email verification (and resend), deactivate account
