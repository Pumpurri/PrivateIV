from django.urls import path
from . import views

urlpatterns = [
    path('stocks/', views.StockListCreateView.as_view(), name='stock-list'),
    path('stocks/<int:pk>/', views.StockRetrieveUpdateView.as_view(), name='stock-detail'),
]