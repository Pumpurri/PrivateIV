from django.contrib import admin
from django.urls import path, include

from .health import healthz

urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('admin/', admin.site.urls),
    path('api/', include('users.urls')),   
    path('api/', include('stocks.urls')), 
    path('api/', include('portfolio.urls')),
]
