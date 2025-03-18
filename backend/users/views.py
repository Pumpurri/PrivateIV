from django.contrib.auth import login, logout, authenticate
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from .models import CustomUser
from .serializers import UserCreateSerializer, CustomUserSerializer

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if request.user.is_authenticated:
            logout(request)
            
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            login(request, user) 
            return Response(
                CustomUserSerializer(user).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').lower().strip()
        password = request.data.get('password', '')
        
        if not email or not password:
            return Response(
                {"error": "Both email and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, email=email, password=password)
        if not user:
            return Response(
                {"error": "Invalid credentials"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        login(request, user)
        return Response(CustomUserSerializer(user).data)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        response = Response({"detail": "Logged out"})
        return response

class UserList(generics.ListCreateAPIView):
    """
    Allows admins to list all users.
    """
    queryset = CustomUser.objects.all()
    permission_classes = [IsAdminUser]
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer 
        return CustomUserSerializer

class UserDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Allows admins to retrieve, update, or delete any user.
    """
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAdminUser]

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Allows a logged-in user to retrieve or update their own profile.
    """
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user



# TODO: Add a view for password change



# Possibly change email, email verification (and resend), deactivate account
