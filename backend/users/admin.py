from django.contrib import admin
from .models import CustomUser

# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'date_of_birth', 'is_staff')
    list_filter = ('is_staff', 'is_superuser')
    search_fields = ('username', 'email')