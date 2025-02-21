# from django.test import TestCase
# from django.core.exceptions import ValidationError
# from .models import CustomUser
# from datetime import date

# # Create your tests here.

# class CustomUserModelTest(TestCase):
#     def test_validate_age_under_13(self):
#         # User younger than 13
#         with self.assertRaises(ValidationError):
#             date_of_birth = date.today().replace(year=date.today().year - 12)
#             user = CustomUser(username='testuser', date_of_birth=date_of_birth, password='testpass')
#             user.full_clean()  # This will trigger the validation

#     def test_validate_age_over_13(self):
#         # User older than 13
#         try:
#             date_of_birth = date.today().replace(year=date.today().year - 14)
#             user = CustomUser(username='testuser', date_of_birth=date_of_birth, password='testpass')
#             user.full_clean()  # This will trigger the validation
#         except ValidationError:
#             self.fail("ValidationError raised for user older than 13")