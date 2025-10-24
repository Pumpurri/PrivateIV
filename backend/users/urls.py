from django.urls import path
from . import views
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.middleware.csrf import get_token

@ensure_csrf_cookie
def get_csrf(request):
    # Get the CSRF token and send it in the response
    csrf_token = get_token(request)
    response = JsonResponse({"detail": "CSRF cookie set"})
    response['X-CSRFToken'] = csrf_token
    return response

urlpatterns = [
    # Admin endpoints
    path('users/', views.UserList.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserDetail.as_view(), name='user-detail'), 

    # Auth endpoints
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.UserProfileView.as_view(), name="user-profile"),
    path("csrf/", get_csrf, name="csrf"),
]