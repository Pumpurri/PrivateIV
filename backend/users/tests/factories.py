import factory
from factory import SelfAttribute
from users.models import CustomUser

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CustomUser
    
    email = factory.Sequence(lambda n: f'user{n}@test.com')
    full_name = factory.Faker('name')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123!')
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