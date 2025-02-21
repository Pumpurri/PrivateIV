from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.UserList.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserDetail.as_view(), name='user-detail'),
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.login_view, name="login"),
]