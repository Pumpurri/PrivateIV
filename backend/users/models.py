from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError

# Validator function to ensure user's age is 13+
def validate_age(value):
    today = timezone.now().date()
    age = relativedelta(today, value).years
    if age < 13:
        raise ValidationError("User must be at least 13 years old.")
    

# Custom user model that extends AbstractUser
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True, blank=True, null=True)  # ✅ Optional email
    date_of_birth = models.DateField(null=True, blank=True)

    USERNAME_FIELD = "username"
    def __str__(self):
        return self.username


