from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date

# Validator function to ensure user's age is 15+
def validate_age(value):
    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 15:
        raise ValidationError("User must be at least 15 years old.")
    if value > today:
        raise ValidationError("Date of birth cannot be in the future.")
    
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Create a regular user: Requires full_name and dob for regular users.
        """
        if not email:
            raise ValueError("The email must be set")
        email = email.lower().strip()
        email = self.normalize_email(email)
        
        if not extra_fields.get("full_name"):
            raise ValueError("Full name is required for all users.")
        
        if not extra_fields.get("is_superuser", False) and not extra_fields.get("dob"):
            raise ValueError("Regular users require a date of birth.")
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create a superuser: Only requires email and full_name.
        """
        extra_fields.setdefault("full_name", "Admin")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        
        return self.create_user(email, password, **extra_fields)
    
class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model.
    """
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=False, null=False)
    dob = models.DateField(blank=True, null=True, validators=[validate_age])
    # institution = models.CharField(max_length=255, blank=True, null=True) # TODO
    # city = models.CharField(max_length=255, blank=True, null=True) # TODO
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False) 
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    objects = CustomUserManager()

    def clean(self):
        if not self.full_name:
            raise ValidationError({"full_name": "This field is required."})
        
        if not self.is_superuser and not self.dob:
            raise ValidationError({"dob": "Required for regular users."})

    def __str__(self):
        return f"{self.full_name} ({self.email})"
    
    def get_full_name(self):
        return self.full_name
    
    @property
    def short_name(self):
        return self.full_name.split()[0]


