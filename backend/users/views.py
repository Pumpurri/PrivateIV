from .models import CustomUser
from rest_framework import generics
from rest_framework.permissions import IsAdminUser, AllowAny, BasePermission
from .serializers import UserCreateSerializer
from django.contrib.auth import authenticate
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status

class IsOwnerOrAdmin(BasePermission):
    """
    Custom permission to allow users to manage their own profile,
    but allow admins to access all users.
    """
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj == request.user  # Admins OR Owner

class UserList(generics.ListCreateAPIView):
    """
    Handles listing all users (Admin only) and user registration (Open for all).
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserCreateSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAdminUser()]  # Only admins can see all users
        elif self.request.method == 'POST':
            return [AllowAny()]  # Anyone can register a new user
        return [IsAuthenticated()]  # Default permission

class UserDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Allows users to retrieve, update, or delete their own profile.
    Admins can access any user profile.
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [IsOwnerOrAdmin]  # Users can manage their own profile, Admins can manage all

class RegisterView(generics.CreateAPIView):
    """
    A separate registration view to handle user sign-ups.
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [AllowAny] 

@api_view(['POST'])
def login_view(request):
    username = request.data.get("username")
    password = request.data.get("password")
    
    user = authenticate(username=username, password=password)
    if user:
        return Response({"username": user.username, "message": "Login successful"})
    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
