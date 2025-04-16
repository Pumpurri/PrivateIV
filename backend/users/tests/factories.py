import factory
from factory import SelfAttribute
from users.models import CustomUser
from portfolio.models import Portfolio
from portfolio.tests.factories import PortfolioFactory

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CustomUser
    
    email = factory.Sequence(lambda n: f'user{n}@test.com')
    full_name = factory.Faker('name')
    password = factory.PostGeneration(
        lambda obj, create, extracted: obj.set_password('testpass123!')
    )
    is_superuser = False

    dob = factory.Maybe(
        SelfAttribute('is_superuser'),
        yes_declaration=None,
        no_declaration=factory.Faker('date_of_birth', minimum_age=15)
    )

    class Params:
        superuser = factory.Trait(
            is_superuser=True,
            is_staff=True,
            dob=None,
        )

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        """Mirror production object creation flow"""
        if create:
            instance.save()