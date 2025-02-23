from django.urls import path
from dj_rest_auth.views import LoginView
from . import views
from .views import CustomTokenObtainPairView, CustomLogoutView, CustomTokenRefreshView
from .serializers import CustomJWTSerializer
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse


@ensure_csrf_cookie
def csrf_token_view(request):
    return JsonResponse({"detail": "CSRF cookie set"})

urlpatterns = [
    # Admin endpoints
    path('users/', views.UserList.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserDetail.as_view(), name='user-detail'), 

    # Auth endpoints
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="login"),
    path("auth/logout/", CustomLogoutView.as_view(), name="logout"),
    path("auth/me/", views.UserProfileView.as_view(), name="user-profile"),
    path("auth/token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/csrf/", csrf_token_view, name="csrf_token"),
]