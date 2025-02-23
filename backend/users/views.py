from .models import CustomUser
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from .serializers import UserCreateSerializer
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
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
    authentication_classes = []

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
        print("Refresh token from cookies:", refresh_token)  # Debugging

        if not refresh_token:
            logger.warning("No refresh token received in cookies!")
            return Response({"error": "No refresh token"}, status=400)

        try:
            token = RefreshToken(refresh_token)
            print("Token payload:", token.payload)  # Debugging
            try:
                token.blacklist()
            except TokenError as e:
                logger.warning(f"Token already blacklisted: {e}")

            response = Response({"detail": "Successfully logged out"}, status=200)
            
            response.delete_cookie('access_token', path='/')
            response.delete_cookie('refresh_token', path='/')
            return response

        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({"error": "Invalid token"}, status=400)

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Handles user authentication by issuing JWT access and refresh tokens.
    Stores tokens in HTTP-only cookies.
    """
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            data = response.data
            access_token = data.get('access')
            refresh_token = data.get('refresh')

            if access_token:
                response.set_cookie(
                    'access_token',
                    access_token,
                    httponly=True,
                    secure=True,
                    samesite='None', 
                    path='/',
                    domain='localhost',
                )
            if refresh_token:
                response.set_cookie(
                    'refresh_token',
                    refresh_token,
                    httponly=True,
                    secure=True,
                    samesite='None',
                    path='/',
                    domain='localhost',
                )

        return response

# TODO: Add a view for password change
# TODO: Add a view for password reset



# Possibly change email, email verification (and resend), deactivate account